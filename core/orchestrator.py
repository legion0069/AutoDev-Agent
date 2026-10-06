"""
orchestrator.py - AutoDev Central Autonomous Orchestrator (Version 3)

Coordinates the complete multi-task autonomous software engineering lifecycle:
1. Load StateManager and persistent state
2. Load and verify project_plan.json
3. Build project context (ContextBuilder)
4. Generate today's atomic task list (TaskPlannerAgent)
5. Filter completed tasks via StateManager
6. Sort remaining tasks by priority
7. Sequentially execute every pending task for the active day:
   - CoderAgent.execute()
   - FileWriterAgent.write()
   - TesterAgent.run_tests()
   - ReviewerAgent.review()
   - RetryEngine.execute() if regeneration required
   - GitAgent.commit()
   - StateManager.record_task_execution()
   - StateManager.mark_task_completed()
8. Advance day & mark phase completed when all tasks for the active day finish
9. Mark project status="completed" when all planned days are finished
10. Return comprehensive ExecutionSummary telemetry
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure project root is available on sys.path for direct execution
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.coder_agent import CoderAgent, GeneratedFile, GeneratedResult
from agents.file_writer_agent import FileWriterAgent, WriteResult
from agents.git_agent import CommitResult, GitAgent
from agents.reviewer_agent import ReviewerAgent, ReviewResult
from agents.task_planner_agent import Task, TaskPlannerAgent
from agents.tester_agent import TesterAgent, TestResult
from core.architecture_manager import (
    ArchitectureDecision,
    ArchitectureManager,
    DesignValidator,
    ValidationReport,
    ViolationSeverity,
)
from core.engineering_decision_engine import (
    DecisionEvaluation,
    DecisionOption,
    DecisionReport,
    EngineeringDecision,
    EngineeringDecisionEngine,
)
from core.change_planner import ChangePlan, ChangePlanner
from core.code_context_retriever import CodeContextRetriever
from core.context_builder import ContextBuilder
from core.impact_analyzer import ImpactAnalyzer
from core.llm import BaseLLM
from core.refactoring_planner import RefactoringPlan, RefactoringPlanner
from core.repository_analyzer import RepositoryAnalyzer, RepositoryOverview
from core.requirement_planner import RequirementPlanner
from core.refactoring_engine import (
    DebtCategory,
    DebtSeverity,
    RefactoringCandidate,
    RefactoringEngine,
    RefactoringMetrics,
    RefactoringPlan as TechnicalDebtPlan,
    RefactoringReport as TechnicalDebtReport,
    TechnicalDebtIssue,
)
from core.retry_engine import RetryEngine, RetryResult
from core.state_manager import ExecutionRecord, ProjectState, StateManager

# Configure module logger
logger = logging.getLogger("AutoDev.Orchestrator")


def setup_logger(log_dir: str | Path = "logs") -> logging.Logger:
    """
    Configures and returns the AutoDev system logger with console and file output.
    """
    log = logging.getLogger("AutoDev.Orchestrator")
    log.setLevel(logging.INFO)

    if not log.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-5s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)
        log.addHandler(console_handler)

        try:
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(
                log_path / "orchestrator.log", encoding="utf-8"
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            log.addHandler(file_handler)
        except (OSError, PermissionError):
            pass

    return log


@dataclass
class ExecutionSummary:
    """
    Comprehensive outcome and aggregated telemetry returned by Orchestrator Version 3.
    """
    __test__ = False

    overall_success: bool
    tasks_completed: List[str] = field(default_factory=list)
    tasks_failed: List[str] = field(default_factory=list)
    generated_files: List[str] = field(default_factory=list)
    commits_created: List[str] = field(default_factory=list)
    average_quality_score: float = 0.0
    average_test_pass_rate: float = 0.0
    current_day: int = 1
    next_day: Optional[int] = None
    execution_duration: float = 0.0
    execution_history: List[ExecutionRecord] = field(default_factory=list)
    status: str = "in_progress"
    message: str = ""
    error: Optional[str] = None
    state_before: Optional[ProjectState] = None
    state_after: Optional[ProjectState] = None
    executed_task: Optional[Task] = None
    test_result: Optional[TestResult] = None
    review_result: Optional[ReviewResult] = None

    # Backward compatibility properties
    @property
    def current_task(self) -> Optional[Task]:
        """Alias for executed_task."""
        return self.executed_task

    @property
    def duration(self) -> float:
        """Alias for execution_duration."""
        return self.execution_duration

    @property
    def completed_tasks(self) -> List[str]:
        """Alias for tasks_completed."""
        return self.tasks_completed

    @property
    def completed_phases(self) -> List[int]:
        """Returns completed phases from state_after if available."""
        if self.state_after:
            return self.state_after.completed_phases
        return []

    @property
    def files_written(self) -> List[str]:
        """Alias for generated_files."""
        return self.generated_files

    @property
    def written_files(self) -> List[str]:
        """Alias for generated_files."""
        return self.generated_files

    def to_dict(self) -> Dict[str, Any]:
        """Converts execution summary to a serializable dictionary."""
        return {
            "overall_success": self.overall_success,
            "tasks_completed": list(self.tasks_completed),
            "tasks_failed": list(self.tasks_failed),
            "generated_files": list(self.generated_files),
            "commits_created": list(self.commits_created),
            "average_quality_score": self.average_quality_score,
            "average_test_pass_rate": self.average_test_pass_rate,
            "current_day": self.current_day,
            "next_day": self.next_day,
            "execution_duration": self.execution_duration,
            "execution_history": [r.to_dict() for r in self.execution_history],
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "state_before": self.state_before.to_dict() if self.state_before else None,
            "state_after": self.state_after.to_dict() if self.state_after else None,
            "executed_task": self.executed_task.to_dict() if self.executed_task else None,
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "test_result": self.test_result.to_dict() if self.test_result else None,
            "review_result": self.review_result.to_dict() if self.review_result else None,
        }


# Alias for backwards compatibility
ExecutionResult = ExecutionSummary


class Orchestrator:
    """
    Central Controller (Version 3) with autonomous multi-task daily execution loop.
    Executes all pending tasks for the active development day sequentially.
    """

    def __init__(
        self,
        project_root: Optional[Union[str, Path]] = None,
        plan_path: Union[str, Path] = "memory/project_plan.json",
        state_path: Union[str, Path] = "memory/state.json",
        tasks_path: Union[str, Path] = "memory/tasks.json",
        log_dir: Union[str, Path] = "logs",
        state_manager: Optional[StateManager] = None,
        context_builder: Optional[ContextBuilder] = None,
        task_planner: Optional[TaskPlannerAgent] = None,
        coder_agent: Optional[CoderAgent] = None,
        file_writer: Optional[FileWriterAgent] = None,
        tester_agent: Optional[TesterAgent] = None,
        reviewer_agent: Optional[ReviewerAgent] = None,
        retry_engine: Optional[RetryEngine] = None,
        git_agent: Optional[GitAgent] = None,
        impact_analyzer: Optional[ImpactAnalyzer] = None,
        refactoring_planner: Optional[RefactoringPlanner] = None,
        repository_analyzer: Optional[RepositoryAnalyzer] = None,
        change_planner: Optional[ChangePlanner] = None,
        architecture_manager: Optional[ArchitectureManager] = None,
        design_validator: Optional[DesignValidator] = None,
        decision_engine: Optional[EngineeringDecisionEngine] = None,
        refactoring_engine: Optional[RefactoringEngine] = None,
        code_context_retriever: Optional[CodeContextRetriever] = None,
        requirement_planner: Optional[RequirementPlanner] = None,
        requirement: Optional[str] = None,
        llm: Optional[BaseLLM] = None,
    ) -> None:
        """
        Initializes Orchestrator Version 3 with injectable subsystems.
        """
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd()
        self.plan_path = Path(plan_path).resolve()
        self.state_path = Path(state_path).resolve()
        self.tasks_path = Path(tasks_path).resolve()
        self.logger = setup_logger(log_dir=log_dir)
        self.llm = llm
        self.requirement = requirement
        self.requirement_planner = requirement_planner

        # Dependency Injection / Subsystem Defaults
        self.state_manager = state_manager or StateManager(
            state_path=self.state_path,
            auto_create=True,
        )
        self.context_builder = context_builder or ContextBuilder(
            plan_path=self.plan_path,
            state_path=self.state_path,
            project_root=self.project_root,
        )
        self.task_planner = task_planner or TaskPlannerAgent(
            output_path=self.tasks_path,
            llm=self.llm,
        )
        self.coder_agent = coder_agent or CoderAgent(llm=self.llm)
        self.file_writer = file_writer or FileWriterAgent(
            project_root=self.project_root,
            overwrite_existing=True,
            create_backups=True,
        )
        self.tester_agent = tester_agent or TesterAgent()
        self.reviewer_agent = reviewer_agent or ReviewerAgent(llm=self.llm)
        self.retry_engine = retry_engine or RetryEngine(
            coder_agent=self.coder_agent,
            file_writer=self.file_writer,
            tester_agent=self.tester_agent,
            reviewer_agent=self.reviewer_agent,
            project_root=self.project_root,
        )
        self.git_agent = git_agent or GitAgent(
            project_root=self.project_root,
            auto_init=True,
        )
        self.impact_analyzer = impact_analyzer
        self.refactoring_planner = refactoring_planner
        self.repository_analyzer = repository_analyzer
        self.change_planner = change_planner
        self.architecture_manager = architecture_manager
        self.design_validator = design_validator or (DesignValidator(architecture_manager=self.architecture_manager) if self.architecture_manager else None)
        self.decision_engine = decision_engine
        self.refactoring_engine = refactoring_engine
        self.code_context_retriever = code_context_retriever



    # -------------------------------------------------------------------------
    # Helper Steps
    # -------------------------------------------------------------------------

    def _verify_project_plan(self) -> Dict[str, Any]:
        """
        Verifies that project_plan.json exists and contains phases.
        If missing and requirement or requirement_planner is provided, generates it automatically.
        """
        self.logger.info("Verifying project plan at '%s'...", self.plan_path)
        if not self.plan_path.is_file():
            if self.requirement or self.requirement_planner:
                req_text = self.requirement or "Autonomous Software Engineering Implementation"
                planner = self.requirement_planner or RequirementPlanner(llm=self.llm)
                self.logger.info("Project plan missing at '%s'. Generating plan via RequirementPlanner...", self.plan_path)
                try:
                    plan_obj = planner.generate_plan(req_text)
                    planner.save_plan(plan_obj, self.plan_path)
                    self.logger.info("Plan automatically generated and saved to '%s'.", self.plan_path)
                except Exception as exc:
                    raise RuntimeError(f"RequirementPlanner failed to generate plan: {exc}") from exc
            else:
                raise FileNotFoundError(f"Project plan missing at '{self.plan_path}'.")

        try:
            with open(self.plan_path, "r", encoding="utf-8") as f:
                plan = json.load(f)
            if not isinstance(plan, dict) or not plan.get("phases"):
                raise ValueError("Project plan is empty or lacks development phases.")
            return plan
        except Exception as exc:
            raise RuntimeError(f"Invalid project plan at '{self.plan_path}': {exc}") from exc

    # -------------------------------------------------------------------------
    # Main Autonomous Execution Loop
    # -------------------------------------------------------------------------

    def run(self) -> ExecutionSummary:
        """
        Executes the autonomous development workflow for all pending tasks of the active day.

        Returns:
            ExecutionSummary containing complete telemetry, metrics, and state snapshots.
        """
        start_time = time.time()
        self.logger.info("=" * 60)
        self.logger.info("Starting AutoDev Orchestrator (Version 3 - Autonomous Loop)")
        self.logger.info("Target Workspace: %s", self.project_root)
        self.logger.info("=" * 60)

        # 1. Load StateManager
        self.logger.info("Loading project state...")
        state_before = ProjectState.from_dict(self.state_manager.get_state().to_dict())
        current_day = state_before.current_day

        tasks_completed: List[str] = []
        tasks_failed: List[str] = []
        generated_files_set: set[str] = set()
        commits_created: List[str] = []
        quality_scores: List[int] = []
        pass_rates: List[float] = []
        execution_records: List[ExecutionRecord] = []

        last_executed_task: Optional[Task] = None
        last_test_result: Optional[TestResult] = None
        last_review_result: Optional[ReviewResult] = None
        last_error: Optional[str] = None

        try:
            # 2. Load project plan
            plan = self._verify_project_plan()
            total_days = int(plan.get("total_days", len(plan.get("phases", []))))

            # Check if project is already complete
            if current_day > total_days:
                self.logger.info("Project is already completed (Day %d > Total %d).", current_day, total_days)
                state = self.state_manager.get_state()
                state.status = "completed"
                self.state_manager.save_state(state)

                duration = round(time.time() - start_time, 3)
                return ExecutionSummary(
                    overall_success=True,
                    tasks_completed=[],
                    tasks_failed=[],
                    generated_files=[],
                    commits_created=[],
                    average_quality_score=0.0,
                    average_test_pass_rate=100.0,
                    current_day=current_day,
                    next_day=None,
                    execution_duration=duration,
                    execution_history=self.state_manager.get_state().execution_history,
                    status="completed",
                    message="All project development days are already completed.",
                    state_before=state_before,
                    state_after=self.state_manager.get_state(),
                    executed_task=None,
                )

            # 3. Build context
            self.logger.info("Building project context with ContextBuilder...")
            context = self.context_builder.build(project_root=self.project_root)

            # Repository Intelligence Analysis (v1.7)
            if hasattr(self, "repository_analyzer") and self.repository_analyzer:
                try:
                    self.logger.info("Executing Repository Intelligence Analysis...")
                    repo_analysis = self.repository_analyzer.analyze(
                        project_root=self.project_root,
                        symbol_graph=context.get("symbol_graph"),
                        project_files=context.get("project_files"),
                    )
                    context["repository_analysis"] = repo_analysis
                    try:
                        self.repository_analyzer.save_report(repo_analysis)
                    except Exception:
                        pass
                except Exception as err:
                    self.logger.warning("RepositoryAnalyzer execution warning: %s", err)
            elif "symbol_graph" in context and context["symbol_graph"] is not None:
                try:
                    analyzer = RepositoryAnalyzer(project_root=self.project_root, symbol_graph=context["symbol_graph"])
                    repo_analysis = analyzer.analyze(
                        project_root=self.project_root,
                        symbol_graph=context["symbol_graph"],
                        project_files=context.get("project_files"),
                    )
                    context["repository_analysis"] = repo_analysis
                except Exception as err:
                    self.logger.warning("RepositoryAnalyzer fallback warning: %s", err)

            # 4. Generate task list
            self.logger.info("Generating today's atomic tasks with TaskPlannerAgent...")

            all_today_tasks = self.task_planner.execute(context)

            # 5. Filter completed tasks
            self.logger.info("Selecting highest-priority pending task...")
            completed_set = set(self.state_manager.get_state().completed_tasks)
            pending_tasks = [
                t for t in all_today_tasks
                if t.id not in completed_set and t.status.lower() != "completed"
            ]

            # 6. Sort remaining tasks by priority (1 is highest)
            pending_tasks.sort(key=lambda t: t.priority)

            self.logger.info(
                "Active Day: %d/%d | Total Tasks: %d | Completed: %d | Pending to execute: %d",
                current_day,
                total_days,
                len(all_today_tasks),
                len(completed_set),
                len(pending_tasks),
            )

            if not pending_tasks:
                self.logger.info("Workflow completed: No pending tasks found for execution.")
                today_all_ids = {t.id for t in all_today_tasks}
                next_day = current_day
                if today_all_ids.issubset(completed_set) and len(today_all_ids) > 0:
                    if current_day not in self.state_manager.get_state().completed_phases:
                        self.state_manager.mark_phase_completed(current_day)
                    if current_day < total_days:
                        next_day = self.state_manager.advance_day()
                    else:
                        next_day = None
                        state = self.state_manager.get_state()
                        state.status = "completed"
                        self.state_manager.save_state(state)

                duration = round(time.time() - start_time, 3)
                return ExecutionSummary(
                    overall_success=True,
                    tasks_completed=[],
                    tasks_failed=[],
                    generated_files=[],
                    commits_created=[],
                    average_quality_score=0.0,
                    average_test_pass_rate=100.0,
                    current_day=current_day,
                    next_day=next_day,
                    execution_duration=duration,
                    execution_history=self.state_manager.get_state().execution_history,
                    status=self.state_manager.get_state().status,
                    message="No pending tasks found for execution. All tasks for active phase are already completed.",
                    state_before=state_before,
                    state_after=self.state_manager.get_state(),
                    executed_task=None,
                )

            # 7. Execute every pending task sequentially
            for task in pending_tasks:
                self.logger.info("-" * 50)
                self.logger.info("Executing Task [%s] (Priority %d): %s", task.id, task.priority, task.title)
                last_executed_task = task
                task_start = time.time()

                try:
                    # 1. Impact Analysis
                    impact_report = None
                    if hasattr(self, "impact_analyzer") and self.impact_analyzer:
                        try:
                            self.logger.info("Performing Dependency Impact Analysis for Task [%s]...", task.id)
                            impact_report = self.impact_analyzer.analyze(task=task, context=context)
                            context["impact_report"] = impact_report
                        except Exception as err:
                            self.logger.warning("ImpactAnalyzer execution non-blocking warning: %s", err)

                    # 2. Refactoring Planning (v1.7)
                    if hasattr(self, "refactoring_planner") and self.refactoring_planner:
                        try:
                            self.logger.info("Generating Safe Refactoring Plan for Task [%s]...", task.id)
                            refactoring_plan = self.refactoring_planner.plan(task=task, context=context)
                            context["refactoring_plan"] = refactoring_plan
                        except Exception as err:
                            self.logger.warning("RefactoringPlanner execution non-blocking warning: %s", err)

                    # 2.5 Semantic Change Planning (v1.8)
                    if hasattr(self, "change_planner") and self.change_planner:
                        try:
                            self.logger.info("Computing Semantic Change Plan for Task [%s]...", task.id)
                            change_plan = self.change_planner.plan(
                                task=task,
                                context=context,
                                symbol_graph=context.get("symbol_graph"),
                                repository_overview=context.get("repository_analysis"),
                                impact_report=context.get("impact_report"),
                            )
                            context["change_plan"] = change_plan
                            try:
                                self.change_planner.export(change_plan)
                            except Exception:
                                pass
                        except Exception as err:
                            self.logger.warning("ChangePlanner execution non-blocking warning: %s", err)


                    # 2.7 Architecture Decision Retrieval & Design Validation (ADR Engine)
                    val_report = None
                    if hasattr(self, "architecture_manager") and self.architecture_manager:
                        try:
                            adrs = self.architecture_manager.search_relevant_for_task(task, context)
                            context["architecture_decisions"] = adrs
                            context["architecture_manager"] = self.architecture_manager
                        except Exception as err:
                            self.logger.warning("ArchitectureManager search warning: %s", err)

                    validator_engine = getattr(self, "design_validator", None) or (self.architecture_manager.validator if getattr(self, "architecture_manager", None) else None)
                    if validator_engine:
                        try:
                            self.logger.info("Validating Task [%s] against Architecture Decisions...", task.id)
                            val_report = validator_engine.validate(
                                task=task,
                                code_context=context.get("context_bundle") or context.get("project_files"),
                                impact_report=impact_report,
                                architecture_decisions=context.get("architecture_decisions"),
                                symbol_graph=context.get("symbol_graph"),
                                repository_overview=context.get("repository_analysis"),
                            )
                            context["validation_report"] = val_report
                        except Exception as err:
                            self.logger.warning("DesignValidator execution non-blocking warning: %s", err)

                    # Check for critical blocking violations
                    if val_report and val_report.is_critical:
                        crit_msg = f"Critical Architectural Violation in Task [{task.id}]: {val_report.summary}"
                        self.logger.error("Aborting code generation for Task [%s] due to critical design violation: %s", task.id, val_report.warnings)
                        tasks_failed.append(task.id)
                        last_error = crit_msg
                        record = self.state_manager.record_task_execution(
                            task_id=task.id,
                            success=False,
                            quality_score=0,
                            test_summary="Aborted: Critical Architectural Violation",
                            details={"error": crit_msg, "warnings": val_report.warnings},
                            auto_save=True,
                        )
                        execution_records.append(record)
                        continue

                    # 3. Code Context Retrieval
                    if hasattr(self, "code_context_retriever") and self.code_context_retriever:
                        try:
                            self.logger.info("Retrieving Relevant Code Context for Task [%s]...", task.id)
                            context_bundle = self.code_context_retriever.retrieve(
                                task=task,
                                impact_report=impact_report,
                                context=context,
                            )
                            context["context_bundle"] = context_bundle
                            context["code_context_result"] = context_bundle
                        except Exception as err:
                            self.logger.warning("CodeContextRetriever execution non-blocking warning: %s", err)

                    # 3.4 Autonomous Technical Debt & Refactoring Engine (v1.9)
                    refact_engine = getattr(self, "refactoring_engine", None) or context.get("refactoring_engine")
                    if refact_engine and hasattr(refact_engine, "analyze_project"):
                        try:
                            self.logger.info("Analyzing Technical Debt with RefactoringEngine for Task [%s]...", task.id)
                            refact_report = refact_engine.analyze_project(
                                project_root=self.project_root,
                                task=task,
                            )
                            context["refactoring_report"] = refact_report
                            context["technical_debt"] = refact_report
                            if refact_report.should_refactor_first:
                                self.logger.warning(
                                    "🚨 Technical Debt Alert: Refactoring recommended before implementing Task [%s] (Debt Score: %.1f/100, Maintainability Index: %.1f/100).",
                                    task.id,
                                    refact_report.metrics.technical_debt_score,
                                    refact_report.metrics.maintainability_index,
                                )
                        except Exception as err:
                            self.logger.warning("RefactoringEngine execution non-blocking warning: %s", err)

                    # 3.5 Autonomous Engineering Decision Engine (v1.8)
                    eng_decision_engine = getattr(self, "decision_engine", None) or context.get("decision_engine")
                    if eng_decision_engine and hasattr(eng_decision_engine, "decide"):
                        try:
                            self.logger.info("Evaluating Architectural Strategies with EngineeringDecisionEngine for Task [%s]...", task.id)
                            decision_report = eng_decision_engine.decide(
                                task=task,
                                impact_report=impact_report,
                                code_context=context.get("context_bundle") or context.get("project_files"),
                                symbol_graph=context.get("symbol_graph"),
                                repository_overview=context.get("repository_analysis"),
                                architecture_decisions=context.get("architecture_decisions"),
                                refactoring_report=context.get("refactoring_report"),
                            )
                            context["engineering_decision"] = decision_report
                            context["decision_report"] = decision_report
                            self.logger.info("Selected Strategy: '%s' (Confidence: %.2f)", decision_report.selected_option.title, decision_report.telemetry.get("confidence", 0.90))
                        except Exception as err:
                            self.logger.warning("EngineeringDecisionEngine execution non-blocking warning: %s", err)

                    # 4. CoderAgent.execute()
                    self.logger.info("Executing CoderAgent for Task [%s]...", task.id)
                    generated_result = self.coder_agent.execute(context=context, task=task)

                    # • FileWriterAgent.write()
                    self.logger.info("Writing %d generated file(s) with FileWriterAgent...", len(generated_result.files))
                    write_result = self.file_writer.write(generated_result, target_dir=self.project_root)
                    if not write_result.success:
                        raise RuntimeError(
                            f"FileWriterAgent failed writing files. FileWriterAgent encountered failures: {write_result.failed_files}"
                        )
                    for f in write_result.files_written:
                        generated_files_set.add(f)

                    # • TesterAgent.run_tests()
                    self.logger.info("Executing automated test suite with TesterAgent...")
                    test_result = self.tester_agent.run_tests(project_root=self.project_root)
                    last_test_result = test_result

                    # • ReviewerAgent.review()
                    self.logger.info("Performing AI code review with ReviewerAgent...")
                    review_result = self.reviewer_agent.review(
                        context=context,
                        generated_result=generated_result,
                        test_result=test_result,
                    )
                    last_review_result = review_result

                    # • RetryEngine.execute() if should_regenerate=True or quality score low
                    if review_result.should_regenerate or not test_result.success or review_result.overall_quality_score < self.retry_engine.default_minimum_quality_score:
                        self.logger.warning(
                            "Task [%s] triggered self-healing RetryEngine (Score: %d, Regenerate: %s, Tests OK: %s)...",
                            task.id,
                            review_result.overall_quality_score,
                            review_result.should_regenerate,
                            test_result.success,
                        )
                        retry_res = self.retry_engine.execute(context=context, task=task)
                        if retry_res.final_generated_result:
                            generated_result = retry_res.final_generated_result
                        if retry_res.final_test_result:
                            test_result = retry_res.final_test_result
                            last_test_result = test_result
                        if retry_res.final_review_result:
                            review_result = retry_res.final_review_result
                            last_review_result = review_result

                    # Evaluate task success
                    task_success = bool(
                        write_result.success
                        and review_result.success
                        and not review_result.should_regenerate
                    )

                    # Record metrics
                    quality_scores.append(review_result.overall_quality_score)
                    if test_result.total_tests > 0:
                        pass_rates.append((test_result.passed / test_result.total_tests) * 100.0)
                    else:
                        pass_rates.append(100.0 if test_result.success else 0.0)

                    # • GitAgent.commit()
                    if task_success:
                        commit_res = self.git_agent.commit(task=task, review_result=review_result)
                        if commit_res.success and commit_res.commit_hash:
                            commits_created.append(commit_res.commit_hash)

                    # • StateManager.record_task_execution()
                    record = self.state_manager.record_task_execution(
                        task_id=task.id,
                        success=task_success,
                        quality_score=review_result.overall_quality_score,
                        test_summary=test_result.message if test_result else None,
                        details={
                            "should_regenerate": review_result.should_regenerate,
                            "written_files": len(write_result.files_written),
                        },
                        auto_save=True,
                    )
                    execution_records.append(record)

                    # • StateManager.mark_task_completed() on success
                    if task_success:
                        self.state_manager.mark_task_completed(task.id)
                        tasks_completed.append(task.id)
                        self.logger.info("Task [%s] PASSED in %.2fs (Score: %d/100).", task.id, time.time() - task_start, review_result.overall_quality_score)

                        # Automatic promotion of architectural improvements into ArchitectureManager
                        if hasattr(self, "architecture_manager") and self.architecture_manager and review_result.overall_quality_score >= 85:
                            try:
                                for rec in getattr(review_result, "recommendations", []):
                                    if any(k in rec.lower() for k in ["pattern", "architecture", "refactor", "isolate", "repository"]):
                                        self.architecture_manager.record_decision(
                                            title=f"Architectural pattern from Task {task.id}",
                                            decision=rec,
                                            context=f"Established during task '{task.title}'.",
                                            category="ARCHITECTURE",
                                        )
                                        break
                            except Exception:
                                pass
                    else:
                        tasks_failed.append(task.id)
                        last_error = f"Task [{task.id}] validation failed (Quality: {review_result.overall_quality_score}/100, Regenerate: {review_result.should_regenerate})"
                        self.logger.warning("Task [%s] FAILED review validation or retry budget exhausted.", task.id)

                except Exception as task_exc:
                    self.logger.error("Error executing task [%s]: %s", task.id, task_exc, exc_info=True)
                    tasks_failed.append(task.id)
                    last_error = str(task_exc)

                    try:
                        record = self.state_manager.record_task_execution(
                            task_id=task.id,
                            success=False,
                            test_summary="Task execution threw exception",
                            details={"error": str(task_exc)},
                            auto_save=True,
                        )
                        execution_records.append(record)
                    except Exception:
                        pass

            # 8. Check if all tasks for the active day are complete
            current_completed_set = set(self.state_manager.get_state().completed_tasks)
            today_all_ids = {t.id for t in all_today_tasks}

            next_day: Optional[int] = current_day
            project_status = "in_progress"

            if today_all_ids.issubset(current_completed_set) and len(today_all_ids) > 0:
                self.logger.info("All %d task(s) for Day %d completed!", len(today_all_ids), current_day)
                if current_day not in self.state_manager.get_state().completed_phases:
                    self.state_manager.mark_phase_completed(current_day)

                if current_day < total_days:
                    next_day = self.state_manager.advance_day()
                    self.logger.info("Advanced active development day to Day %d.", next_day)
                else:
                    next_day = None
                    project_status = "completed"
                    state = self.state_manager.get_state()
                    state.status = "completed"
                    self.state_manager.save_state(state)
                    self.logger.info("🎉 All %d development days finished! Project status is COMPLETED.", total_days)

            state_after = self.state_manager.get_state()
            duration = round(time.time() - start_time, 3)

            avg_score = round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0.0
            avg_pass_rate = round(sum(pass_rates) / len(pass_rates), 2) if pass_rates else 100.0

            overall_success = len(tasks_failed) == 0 and (len(tasks_completed) > 0 or len(pending_tasks) == 0)

            self.logger.info("=" * 60)
            self.logger.info(
                "Workflow Completed (%s) in %.3fs | Completed: %d | Failed: %d | Avg Score: %.1f",
                "SUCCESS" if overall_success else "PARTIAL / FAILED",
                duration,
                len(tasks_completed),
                len(tasks_failed),
                avg_score,
            )
            self.logger.info("=" * 60)

            return ExecutionSummary(
                overall_success=overall_success,
                tasks_completed=tasks_completed,
                tasks_failed=tasks_failed,
                generated_files=sorted(list(generated_files_set)),
                commits_created=commits_created,
                average_quality_score=avg_score,
                average_test_pass_rate=avg_pass_rate,
                current_day=current_day,
                next_day=next_day,
                execution_duration=duration,
                execution_history=execution_records or self.state_manager.get_state().execution_history,
                status=project_status,
                message=(
                    f"Executed {len(tasks_completed) + len(tasks_failed)} task(s). "
                    f"{len(tasks_completed)} succeeded, {len(tasks_failed)} failed."
                ),
                error=last_error,
                state_before=state_before,
                state_after=state_after,
                executed_task=last_executed_task,
                test_result=last_test_result,
                review_result=last_review_result,
            )

        except Exception as exc:
            duration = round(time.time() - start_time, 3)
            self.logger.error("Orchestrator encountered fatal failure: %s", exc, exc_info=True)
            state_after = self.state_manager.get_state()

            return ExecutionSummary(
                overall_success=False,
                tasks_completed=tasks_completed,
                tasks_failed=tasks_failed,
                generated_files=sorted(list(generated_files_set)),
                commits_created=commits_created,
                average_quality_score=round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0.0,
                average_test_pass_rate=round(sum(pass_rates) / len(pass_rates), 2) if pass_rates else 0.0,
                current_day=current_day,
                next_day=current_day,
                execution_duration=duration,
                execution_history=execution_records or self.state_manager.get_state().execution_history,
                status="failed",
                message=f"Orchestration halted due to error: {exc}",
                error=str(exc),
                state_before=state_before,
                state_after=state_after,
                executed_task=last_executed_task,
                test_result=last_test_result,
                review_result=last_review_result,
            )


if __name__ == "__main__":
    orchestrator = Orchestrator()
    summary = orchestrator.run()

    print("\n" + "=" * 60)
    print("           ORCHESTRATOR VERSION 3 EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Overall Success      : {summary.overall_success}")
    print(f"Status               : {summary.status}")
    print(f"Tasks Completed      : {summary.tasks_completed}")
    print(f"Tasks Failed         : {summary.tasks_failed}")
    print(f"Generated Files      : {summary.generated_files}")
    print(f"Commits Created      : {summary.commits_created}")
    print(f"Avg Quality Score    : {summary.average_quality_score}/100")
    print(f"Avg Test Pass Rate   : {summary.average_test_pass_rate}%")
    print(f"Duration             : {summary.execution_duration}s")
    print(f"Summary Message      : {summary.message}")
    print("=" * 60 + "\n")
