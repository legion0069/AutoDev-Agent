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
from core.change_execution_planner import (
    ChangeExecutionPlan,
    ChangeExecutionPlanner,
    ChangeOperation,
    CommitPlanEntry,
    ExecutionStage,
    RollbackPoint,
    ValidationGate,
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
from core.quality_models import QualityAssessmentResult, QualityGateStatus
from core.predictive_quality_engine import PredictiveQualityEngine
from core.retry_engine import RetryEngine, RetryResult
from core.state_manager import ExecutionRecord, ProjectState, StateManager
from core.collaboration import (
    CollaborationManager,
    CollaborationConfig,
    TaskAssignment,
    TaskPriority,
    SyncCheckpointType,
)
from agents import (
    ArchitectureAgent,
    BackendAgent,
    FrontendAgent,
    TestingAgent,
    SecurityAgent,
    PerformanceAgent,
    DocumentationAgent,
    ReleaseAgent,
)
from core.cluster import (
    ClusterConfig,
    ClusterJob,
    ClusterManager,
    TaskSpec,
)
from core.enterprise import (
    EnterpriseCompany,
)
from core.learning import (
    SelfEvolvingEngine,
)
from core.ecosystem import (
    ExternalIntelligenceEngine,
    EcosystemEngine,
)
from core.multi_agent import (
    DistributedEngineeringCompany,
    WorkItem,
    WorkItemStatus,
)

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
        project_dir: Optional[Union[str, Path]] = None,
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
        change_execution_planner: Optional[ChangeExecutionPlanner] = None,
        execution_engine: Optional[Any] = None,
        code_context_retriever: Optional[CodeContextRetriever] = None,
        requirement_planner: Optional[RequirementPlanner] = None,
        requirement: Optional[str] = None,
        llm: Optional[BaseLLM] = None,
        coordination_mode: str = "single",
        ha_coordinator: Optional[Any] = None,
        artifact_transfer_manager: Optional[Any] = None,
        kubernetes_controller: Optional[Any] = None,
        terminal_gateway: Optional[Any] = None,
        predictive_quality_engine: Optional[PredictiveQualityEngine] = None,
        collaboration_manager: Optional[CollaborationManager] = None,
        cluster_manager: Optional[ClusterManager] = None,
        enterprise_company: Optional[EnterpriseCompany] = None,
        evolving_engine: Optional[SelfEvolvingEngine] = None,
        ecosystem_engine: Optional[ExternalIntelligenceEngine] = None,
        multi_agent_company: Optional[DistributedEngineeringCompany] = None,
        enterprise_organization: Optional[Any] = None,
        enterprise_federation: Optional[Any] = None,
        research_lab: Optional[Any] = None,
    ) -> None:
        """
        Initializes Orchestrator Version 3 with injectable subsystems (v2.0 - v3.0).
        """
        chosen_root = project_dir or project_root
        self.project_root = Path(chosen_root).resolve() if chosen_root else Path.cwd()
        self.plan_path = Path(plan_path).resolve()
        self.state_path = Path(state_path).resolve()
        self.tasks_path = Path(tasks_path).resolve()
        self.logger = setup_logger(log_dir=log_dir)
        self.coordination_mode = coordination_mode
        self.ha_coordinator = ha_coordinator
        self.artifact_transfer_manager = artifact_transfer_manager
        self.kubernetes_controller = kubernetes_controller
        self.terminal_gateway = terminal_gateway
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
        self.change_execution_planner = change_execution_planner
        self.code_context_retriever = code_context_retriever
        self.predictive_quality_engine = predictive_quality_engine or PredictiveQualityEngine(workspace_path=str(self.project_root))

        # AutoDev v2.1 Execution Engine
        if execution_engine is not None:
            self.execution_engine = execution_engine
        else:
            try:
                from core.execution_engine import ExecutionEngine
                self.execution_engine = ExecutionEngine(
                    workspace_root=self.project_root,
                    file_writer=self.file_writer,
                    tester_agent=self.tester_agent,
                    reviewer_agent=self.reviewer_agent,
                    git_agent=self.git_agent,
                    retry_engine=self.retry_engine,
                    architecture_manager=self.architecture_manager,
                    journal_root=self.project_root / "memory" / "execution_journal",
                    report_dir=self.project_root / "memory" / "execution_reports",
                )
            except Exception:
                self.execution_engine = None

        # AutoDev v2.8 Multi-Agent Collaboration Framework
        if collaboration_manager is not None:
            self.collaboration_manager = collaboration_manager
        else:
            self.collaboration_manager = CollaborationManager()
            # Register specialized engineering agents
            self.collaboration_manager.register_agent(ArchitectureAgent(llm_client=self.llm))
            self.collaboration_manager.register_agent(BackendAgent(llm_client=self.llm))
            self.collaboration_manager.register_agent(FrontendAgent(llm_client=self.llm))
            self.collaboration_manager.register_agent(TestingAgent(llm_client=self.llm))
            self.collaboration_manager.register_agent(SecurityAgent(llm_client=self.llm))
            self.collaboration_manager.register_agent(PerformanceAgent(llm_client=self.llm))
            self.collaboration_manager.register_agent(DocumentationAgent(llm_client=self.llm))
            self.collaboration_manager.register_agent(ReleaseAgent(llm_client=self.llm))

        # AutoDev v2.9 Distributed Cluster Execution Engine
        if cluster_manager is not None:
            self.cluster_manager = cluster_manager
        else:
            self.cluster_manager = ClusterManager(
                storage_dir=str(self.project_root / "memory" / "cluster")
            )

        # AutoDev v3.0 Autonomous AI Software Company Framework
        if enterprise_company is not None:
            self.enterprise_company = enterprise_company
        else:
            self.enterprise_company = EnterpriseCompany()

        # AutoDev v3.1 Self-Evolving Intelligence Engine
        if evolving_engine is not None:
            self.evolving_engine = evolving_engine
        else:
            self.evolving_engine = SelfEvolvingEngine(
                storage_dir=str(self.project_root / "memory" / "learning"),
                project_root=str(self.project_root),
                llm=self.llm,
            )

        # AutoDev v3.2 External Intelligence & Ecosystem Awareness Engine
        if ecosystem_engine is not None:
            self.ecosystem_engine = ecosystem_engine
        else:
            self.ecosystem_engine = ExternalIntelligenceEngine(
                cache_dir=str(self.project_root / "memory" / "ecosystem_cache")
            )

        # AutoDev v3.3 Distributed Multi-Agent Collaboration Platform
        self._multi_agent_company = multi_agent_company

        # AutoDev v3.4 Autonomous AI Organization Framework
        self._enterprise_organization = enterprise_organization

        # AutoDev v3.5 Autonomous Enterprise Ecosystem Federation
        self._enterprise_federation = enterprise_federation

        # AutoDev v3.6 Autonomous AI Research Lab & Scientific Discovery Framework
        self._research_lab = research_lab

    @property
    def project_dir(self) -> Path:
        """Alias for project_root."""
        return self.project_root

    @property
    def learning_coordinator(self) -> SelfEvolvingEngine:
        """Alias for evolving_engine."""
        return self.evolving_engine

    @property
    def external_intelligence(self) -> ExternalIntelligenceEngine:
        """Alias for ecosystem_engine."""
        return self.ecosystem_engine

    @property
    def multi_agent_company(self) -> DistributedEngineeringCompany:
        """Distributed multi-agent engineering company simulation engine (v3.3)."""
        if self._multi_agent_company is None:
            self._multi_agent_company = DistributedEngineeringCompany()
        return self._multi_agent_company

    @property
    def enterprise_organization(self) -> Any:
        """Autonomous AI Organization multi-department enterprise engine (v3.4)."""
        if self._enterprise_organization is None:
            from core.organization import EnterpriseOrganization
            self._enterprise_organization = EnterpriseOrganization(
                company_name="AutoDev Autonomous Technologies Inc.",
                storage_dir=self.project_root / "memory" / "organization",
            )
        return self._enterprise_organization

    @property
    def enterprise_federation(self) -> Any:
        """Autonomous Enterprise Ecosystem Federation of AI Companies (v3.5)."""
        if self._enterprise_federation is None:
            from core.enterprise_federation import EnterpriseFederation
            self._enterprise_federation = EnterpriseFederation(
                enterprise_name="AutoDev Global Enterprise Group",
            )
        return self._enterprise_federation

    @property
    def research_lab(self) -> Any:
        """Autonomous AI Research Lab and Scientific Discovery Framework (v3.6)."""
        if self._research_lab is None:
            from core.research_lab import ResearchLab
            self._research_lab = ResearchLab()
        return self._research_lab

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

            # Ecosystem Awareness & Intelligence Analysis (v3.2)
            if hasattr(self, "ecosystem_engine") and self.ecosystem_engine:
                try:
                    self.logger.info("Executing Ecosystem Intelligence Analysis (v3.2)...")
                    ecosystem_analysis = self.ecosystem_engine.analyze_ecosystem(
                        project_dir=str(self.project_root),
                        source_files=context.get("project_files"),
                        project_type="web_api",
                        primary_runtime="Python",
                        runtime_version="3.12",
                    )
                    context["ecosystem_intelligence"] = ecosystem_analysis
                    context["ecosystem_analysis"] = ecosystem_analysis
                except Exception as err:
                    self.logger.warning("EcosystemEngine execution non-blocking warning: %s", err)

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

                    # 3.6 Autonomous Change Execution Planning Engine (v2.0)
                    change_exec_engine = getattr(self, "change_execution_planner", None) or context.get("change_execution_planner")
                    if change_exec_engine and hasattr(change_exec_engine, "plan_changes"):
                        try:
                            self.logger.info("Synthesizing Change Execution Plan for Task [%s]...", task.id)
                            change_execution_plan = change_exec_engine.plan_changes(
                                task=task,
                                impact_report=impact_report,
                                repository_overview=context.get("repository_analysis"),
                                architecture_manager=getattr(self, "architecture_manager", None) or context.get("architecture_manager"),
                                refactoring_engine=refact_engine,
                                decision_engine=eng_decision_engine,
                                symbol_graph=context.get("symbol_graph"),
                                context=context,
                            )
                            context["change_execution_plan"] = change_execution_plan
                            try:
                                plan_file = self.project_root / "memory" / "change_execution_plan.json"
                                change_exec_engine.save_plan(change_execution_plan, plan_file)
                            except Exception:
                                pass
                            self.logger.info(
                                "Change Execution Plan generated: %d stages, Risk: %s, Estimated duration: %.1fm",
                                len(change_execution_plan.ordered_stages),
                                change_execution_plan.risk,
                                change_execution_plan.estimated_duration,
                            )
                        except Exception as err:
                            self.logger.warning("ChangeExecutionPlanner execution non-blocking warning: %s", err)

                    # 3.7 Autonomous Predictive Failure Prevention & Quality Intelligence Engine (v2.7)
                    if hasattr(self, "predictive_quality_engine") and self.predictive_quality_engine:
                        try:
                            self.logger.info("Executing Predictive Quality Assessment for Task [%s]...", task.id)
                            quality_assessment = self.predictive_quality_engine.assess_workspace(
                                files_content=context.get("project_files"),
                                task_id=task.id,
                                impact_summary={"impact_score": getattr(impact_report, "risk_score", 0.0) if impact_report else 0.0},
                            )
                            context["quality_assessment"] = quality_assessment
                            context["predictive_quality_result"] = quality_assessment

                            if getattr(getattr(quality_assessment, "gate_result", None), "status", None) == QualityGateStatus.REJECTED:
                                self.logger.warning(
                                    "🚨 Quality Gate REJECTED code generation for Task [%s]: %s (Score: %.1f)",
                                    task.id,
                                    quality_assessment.gate_result.reasons,
                                    quality_assessment.gate_result.score,
                                )
                        except Exception as err:
                            self.logger.warning("PredictiveQualityEngine execution non-blocking warning: %s", err)

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

                    # Version 3.1 Autonomous Learning Engine Hook
                    if hasattr(self, "evolving_engine") and self.evolving_engine:
                        try:
                            written_paths = [str(f.path) for f in getattr(write_result, "files_written", [])] if write_result else []
                            self.evolving_engine.on_task_completed(
                                task_id=task.id,
                                task_title=task.title,
                                success=task_success,
                                quality_score=float(review_result.overall_quality_score) if review_result else 0.0,
                                test_pass_rate=float(test_result.pass_rate) if test_result else 100.0,
                                files_affected=written_paths,
                                execution_time=time.time() - task_start,
                                retry_count=int(getattr(retry_result, "attempts", 0)) if retry_result else 0,
                                review_feedback=getattr(review_result, "feedback", "") if review_result else "",
                                root_cause=last_error if not task_success else "",
                                solution="Resolved via coder/retry pipeline" if task_success else "",
                                project=self.project_root.name if hasattr(self.project_root, "name") else "autodev",
                            )
                        except Exception as learn_exc:
                            self.logger.debug("Learning engine hook exception: %s", learn_exc)

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

                    # Version 3.1 Autonomous Learning Hook on Exception
                    if hasattr(self, "evolving_engine") and self.evolving_engine:
                        try:
                            self.evolving_engine.on_task_completed(
                                task_id=task.id,
                                task_title=task.title,
                                success=False,
                                quality_score=0.0,
                                test_pass_rate=0.0,
                                files_affected=[],
                                execution_time=time.time() - task_start,
                                retry_count=0,
                                review_feedback=str(task_exc),
                                root_cause=str(task_exc),
                                solution="",
                                project=self.project_root.name if hasattr(self.project_root, "name") else "autodev",
                            )
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

    def execute_collaborative_cycle(
        self,
        tasks: Optional[List[Task]] = None,
        context: Optional[Dict[str, Any]] = None,
        max_workers: int = 4,
    ) -> Dict[str, Any]:
        """
        Executes a collaborative multi-agent software engineering cycle (v2.8).
        Discovers tasks, allocates to specialized agents, executes DAG parallel batches,
        conducts peer reviews, handles conflicts, and performs synchronization validation.
        """
        ctx = context or self.context_builder.build_context(current_day=self.state_manager.get_current_day())
        task_list = tasks or self.task_planner.execute(ctx)

        # Convert Task objects into TaskAssignment models
        assignments = []
        for t in task_list:
            t_id = getattr(t, "id", getattr(t, "task_id", f"task_{int(time.time()*1000)}"))
            t_title = getattr(t, "title", str(t))
            t_desc = getattr(t, "description", "")
            t_prio_str = str(getattr(t, "priority", "MEDIUM")).upper()
            t_prio = TaskPriority[t_prio_str] if t_prio_str in TaskPriority.__members__ else TaskPriority.MEDIUM
            t_skills = getattr(t, "skills", getattr(t, "required_skills", []))
            t_files = getattr(t, "files", getattr(t, "estimated_files", []))
            t_deps = getattr(t, "dependencies", [])

            assignments.append(TaskAssignment(
                task_id=t_id,
                title=t_title,
                description=t_desc,
                required_skills=list(t_skills),
                priority=t_prio,
                estimated_files=list(t_files),
                dependencies=list(t_deps),
            ))

        self.collaboration_manager.submit_tasks(assignments)
        cycle_result = self.collaboration_manager.execute_multi_agent_cycle(context=ctx, max_workers=max_workers)
        telemetry_report = self.collaboration_manager.generate_collaboration_report()

        return {
            "cycle_result": cycle_result,
            "telemetry_report": telemetry_report,
            "tasks_assigned_count": len(assignments),
        }

    # -------------------------------------------------------------------------
    # AutoDev v2.9 Distributed Cluster Execution API
    # -------------------------------------------------------------------------

    def execute_cluster(
        self,
        prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        num_tasks: int = 4,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Executes distributed software engineering workloads across the cluster fleet (v2.9).
        Dispatches multi-stage tasks to worker nodes, manages locks, syncs artifacts,
        and aggregates real-time cluster telemetry.
        """
        ctx = context or self.context_builder.build_context(current_day=self.state_manager.get_current_day())
        req_prompt = prompt or self.requirement or ctx.get("description", "Distributed Software Engineering Workload")

        return self.cluster_manager.execute_cluster(
            prompt=req_prompt,
            context=ctx,
            num_tasks=num_tasks,
            timeout=timeout,
        )

    def execute_remote(
        self,
        task: TaskSpec,
        worker_id: str,
    ) -> Dict[str, Any]:
        """
        Directly executes a single task on an authorized remote worker node (v2.9).
        """
        return self.cluster_manager.execute_remote(task=task, worker_id=worker_id)

    def submit_job(
        self,
        title: str,
        tasks: List[TaskSpec],
        description: str = "",
    ) -> str:
        """
        Submits an asynchronous multi-task DAG job to the cluster (v2.9).
        """
        return self.cluster_manager.submit_job(title=title, tasks=tasks, description=description)

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancels an active distributed cluster job (v2.9).
        """
        return self.cluster_manager.master.cancel_job(job_id=job_id)

    def query_cluster(self) -> Dict[str, Any]:
        """
        Queries live cluster status, node health, queue depth, and metrics (v2.9).
        """
        return self.cluster_manager.query_cluster()

    def execute_enterprise(
        self,
        strategic_goal: str = "Autonomous Enterprise Software Delivery",
        target_version: str = "3.0.0",
        budget_usd: float = 250000.0,
    ) -> Dict[str, Any]:
        """
        Executes the full Version 3.0 Autonomous AI Software Company lifecycle:
        CEO Vision -> Product Roadmap -> Sprint Planning -> Architecture Board ->
        Engineering Allocation -> QA/Security -> Release Train -> Deployment -> Support -> Analytics.
        """
        return self.enterprise_company.run_enterprise_lifecycle(
            strategic_goal=strategic_goal,
            target_version=target_version,
            budget_usd=budget_usd,
        )

    def simulate_company(
        self,
        timeframe: str = "workday",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Simulates autonomous enterprise operations across discrete timeframes (workday, sprint, release, quarter, year).
        """
        tf = timeframe.lower()
        if tf == "workday":
            return self.enterprise_company.simulator.simulate_workday(kwargs.get("day_index", 1))
        elif tf == "sprint":
            return self.enterprise_company.simulator.simulate_sprint(
                sprint_number=kwargs.get("sprint_number", 1),
                duration_days=kwargs.get("duration_days", 14),
            )
        elif tf == "release":
            return self.enterprise_company.simulator.simulate_release(kwargs.get("version", "3.0.0"))
        elif tf == "quarter":
            return self.enterprise_company.simulator.simulate_quarter(
                quarter=kwargs.get("quarter", "Q1"),
                year=kwargs.get("year", 2026),
            )
        elif tf == "year":
            return self.enterprise_company.simulator.simulate_year(kwargs.get("year", 2026))
        else:
            return self.enterprise_company.simulator.simulate_workday(1)

    def query_company(self) -> Dict[str, Any]:
        """
        Queries live enterprise status, C-Suite decisions, financials, headcount, and DORA metrics.
        """
        return self.enterprise_company.get_company_overview()

    # -------------------------------------------------------------------------
    # AutoDev v3.1 Self-Evolving Intelligence Engine Public APIs
    # -------------------------------------------------------------------------

    def recommend_architecture(
        self,
        requirement: str = "",
        requirements: Optional[str] = None,
        project_name: Optional[str] = None,
        domain: str = "general",
        language: str = "python",
        scale: str = "medium",
        **kwargs: Any,
    ) -> ArchitectureRecommendation:
        """
        Recommends folder structure, design patterns, database, API style,
        and testing strategy based on historical project success (v3.1).
        """
        req = requirement or requirements or kwargs.get("req_text", "") or "General Software Architecture"
        p_name = project_name or kwargs.get("name", "project")
        rec = self.evolving_engine.recommend_architecture(
            requirement=req,
            requirements=req,
            project_name=p_name,
            domain=domain,
            language=language,
            scale=scale,
            **kwargs,
        )
        return rec

    def run_learning_cycle(
        self,
        timeframe_or_payload: Union[str, Dict[str, Any]] = "task",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Executes autonomous reflection, pattern mining, memory evolution,
        and self-improvement planning across discrete timeframes (v3.1).
        """
        if isinstance(timeframe_or_payload, dict):
            task_dict = dict(timeframe_or_payload)
            task_dict.update(kwargs)
            res = self.evolving_engine.on_task_completed(
                task_id=task_dict.get("task_id", "T-MANUAL"),
                task_title=task_dict.get("title", task_dict.get("task_title", "Manual Task")),
                success=task_dict.get("success", True),
                quality_score=task_dict.get("review_score", task_dict.get("quality_score", 95.0)),
                test_pass_rate=100.0 if task_dict.get("tests_passed", True) else 0.0,
                files_affected=task_dict.get("affected_files", task_dict.get("files_affected", [])),
                execution_time=task_dict.get("execution_time", 1.0),
                retry_count=task_dict.get("retries", task_dict.get("retry_count", 0)),
                project=task_dict.get("project", self.project_root.name),
            )
            res["reflection"] = self.evolving_engine.reflection_engine.to_dict()
            res["event"] = self.evolving_engine.learning_engine.get_event(res.get("learning_event_id", ""))
            res["analytics"] = self.evolving_engine.analytics_engine.compute_aggregated_statistics()
            return res

        tf = str(kwargs.get("timeframe", timeframe_or_payload)).lower()
        if tf == "task":
            res = self.evolving_engine.on_task_completed(
                task_id=kwargs.get("task_id", "T-MANUAL"),
                task_title=kwargs.get("task_title", kwargs.get("title", "Manual Task")),
                success=kwargs.get("success", True),
                quality_score=kwargs.get("quality_score", kwargs.get("review_score", 95.0)),
                test_pass_rate=kwargs.get("test_pass_rate", 100.0),
                files_affected=kwargs.get("files_affected", kwargs.get("affected_files", [])),
                execution_time=kwargs.get("execution_time", 1.0),
                retry_count=kwargs.get("retry_count", kwargs.get("retries", 0)),
                review_feedback=kwargs.get("review_feedback", ""),
                root_cause=kwargs.get("root_cause", ""),
                solution=kwargs.get("solution", ""),
                project=kwargs.get("project", self.project_root.name),
            )
            res["reflection"] = self.evolving_engine.reflection_engine.to_dict()
            res["event"] = self.evolving_engine.learning_engine.get_event(res.get("learning_event_id", ""))
            res["analytics"] = self.evolving_engine.analytics_engine.compute_aggregated_statistics()
            return res
        elif tf == "sprint":
            rep = self.evolving_engine.run_sprint_reflection(
                sprint_id=kwargs.get("sprint_id", "SPRINT-1"),
                task_records=kwargs.get("task_records", []),
            )
            return rep.to_dict()
        elif tf == "release":
            rep = self.evolving_engine.run_release_reflection(
                release_version=kwargs.get("version", "3.1.0"),
                release_notes=kwargs.get("notes", ""),
                metrics=kwargs.get("metrics", {}),
            )
            return rep.to_dict()
        elif tf in ("monthly", "month", "evaluation"):
            return self.evolving_engine.run_monthly_evolution_cycle(
                evaluation_period=kwargs.get("period", "2026-10"),
            )
        else:
            return self.evolving_engine.get_learning_dashboard()

    def get_learning_report(self) -> Dict[str, Any]:
        """
        Generates comprehensive multi-dimensional learning reports (v3.1).
        """
        return self.evolving_engine.generate_comprehensive_learning_report()

    def query_learning_state(self) -> Dict[str, Any]:
        """
        Queries live learning dashboard, discovered patterns, playbooks,
        and longitudinal performance telemetry (v3.1).
        """
        return self.evolving_engine.get_learning_dashboard()

    def optimize_prompt(
        self,
        raw_prompt: str,
        task_type: str = "coding",
        target_tokens: int = 1500,
    ) -> PromptOptimizationRecord:
        """
        Optimizes and compresses prompts using discovered patterns and token efficiency heuristics (v3.1).
        """
        return self.evolving_engine.optimize_prompt(
            raw_prompt=raw_prompt,
            task_type=task_type,
            target_tokens=target_tokens,
        )

    # -------------------------------------------------------------------------
    # AutoDev v3.2 External Intelligence & Ecosystem Awareness Public APIs
    # -------------------------------------------------------------------------

    def analyze_ecosystem(
        self,
        project_dir: Optional[str] = None,
        source_files: Optional[Dict[str, str]] = None,
        project_type: str = "web_api",
        primary_runtime: str = "Python",
        runtime_version: str = "3.12",
    ) -> Dict[str, Any]:
        """
        Executes unified multi-dimensional ecosystem analysis:
        Dependencies, security scan, compatibility, recommendations, radar (v3.2).
        """
        target_dir = project_dir or str(self.project_root)
        return self.ecosystem_engine.analyze_ecosystem(
            project_dir=target_dir,
            source_files=source_files,
            project_type=project_type,
            primary_runtime=primary_runtime,
            runtime_version=runtime_version,
        )

    def get_dependency_report(self, project_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates full dependency scan, graph, and vulnerability/conflict analysis (v3.2).
        """
        target_dir = project_dir or str(self.project_root)
        return self.ecosystem_engine.generate_dependency_report(target_dir)

    def get_security_report(
        self,
        dependencies: Optional[List[Any]] = None,
        source_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generates security advisory, CVE risk, and secret/crypto vulnerability scan (v3.2).
        """
        return self.ecosystem_engine.generate_security_report(
            dependencies=dependencies,
            source_files=source_files,
        )

    def get_framework_report(self, framework_name: str, current_version: str) -> Dict[str, Any]:
        """
        Evaluates framework lifecycle status, breaking changes, and migration pathways (v3.2).
        """
        return self.ecosystem_engine.generate_framework_report(framework_name, current_version)

    def get_migration_report(self, technology: str, from_version: str, to_version: str) -> Dict[str, Any]:
        """
        Generates actionable migration plan with breaking changes, code updates, and rollbacks (v3.2).
        """
        return self.ecosystem_engine.generate_migration_report(technology, from_version, to_version)

    def get_technology_radar(self) -> Dict[str, Any]:
        """
        Generates organization-wide technology radar across Adopt/Trial/Assess/Hold rings (v3.2).
        """
        return self.ecosystem_engine.generate_technology_radar_report()

    def get_compatibility_report(
        self,
        runtime: str = "Python",
        runtime_version: str = "3.12",
        dependencies: Optional[List[tuple]] = None,
    ) -> Dict[str, Any]:
        """
        Generates multi-dimensional compatibility matrix across OS, runtimes, containers, clouds (v3.2).
        """
        return self.ecosystem_engine.generate_compatibility_report(
            runtime=runtime,
            runtime_version=runtime_version,
            dependencies=dependencies or [],
        )

    def get_release_intelligence_report(
        self,
        updates: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Tracks releases and generates semantic version upgrade impact reports (v3.2).
        """
        return self.ecosystem_engine.generate_release_intelligence_report(updates or [])

    def get_ecosystem_recommendations(
        self,
        project_type: str = "web_api",
        language: str = "python",
    ) -> Dict[str, Any]:
        """
        Generates architectural, testing, CI/CD, and library recommendations based on project attributes (v3.2).
        """
        return self.ecosystem_engine.generate_engineering_recommendation_report(
            project_type=project_type,
            language=language,
        )

    def query_ecosystem_cache(self, query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Searches persisted external knowledge cache with inverted index full-text search (v3.2).
        """
        results = self.ecosystem_engine.knowledge_cache.search(query, category=category)
        return [r.to_dict() if hasattr(r, "to_dict") else r for r in results]

    def record_external_knowledge(
        self,
        key: str,
        category: str,
        title: str,
        content: str,
        version: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Persists structured external engineering knowledge into searchable cache (v3.2).
        """
        meta = metadata or {}
        if tags:
            meta["tags"] = tags
        entry = self.ecosystem_engine.knowledge_cache.put(
            key=key,
            category=category,
            title=title,
            content=content,
            version=version or "1.0",
            metadata=meta,
        )
        return entry.to_dict() if hasattr(entry, "to_dict") else entry

    # -------------------------------------------------------------------------
    # AutoDev v3.3 Multi-Agent Collaboration & Company Execution
    # -------------------------------------------------------------------------

    def execute(self) -> ExecutionSummary:
        """
        Sequential execution mode (v1.0 - v3.2 compatibility alias for run()).
        """
        return self.run()

    def execute_company(
        self,
        tasks: Optional[List[Any]] = None,
        custom_runner_fn: Optional[Callable] = None,
        simulate_ceremonies: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes engineering workload in Distributed Multi-Agent Company Mode (v3.3).
        Simulates corporate organization with standups, architecture reviews,
        concurrent engineering tasks, peer code reviews, retrospectives, and releases.
        """
        company = self.multi_agent_company

        # 1. Daily Standup
        standup_info = company.simulate_daily_standup() if simulate_ceremonies else None

        # 2. Convert / prepare tasks
        company_tasks: List[WorkItem] = []
        if tasks:
            for t in tasks:
                if isinstance(t, WorkItem):
                    company_tasks.append(t)
                elif isinstance(t, dict):
                    company_tasks.append(
                        WorkItem(
                            task_id=t.get("task_id", t.get("id", "task_auto")),
                            title=t.get("title", "Engineering Task"),
                            description=t.get("description", ""),
                            priority=t.get("priority", 50),
                            resources_required=t.get("resources_required", t.get("resources", [])),
                        )
                    )
                elif hasattr(t, "id") and hasattr(t, "title"):
                    company_tasks.append(
                        WorkItem(
                            task_id=str(t.id),
                            title=str(t.title),
                            description=getattr(t, "description", ""),
                            priority=getattr(t, "priority", 50),
                        )
                    )
        else:
            # Default smoke engineering tasks if none passed
            company_tasks = [
                WorkItem(
                    task_id="task_arch_spec",
                    title="Design system architecture specification",
                    priority=80,
                    resources_required=["architecture_spec.md"],
                ),
                WorkItem(
                    task_id="task_core_impl",
                    title="Implement core business logic module",
                    priority=70,
                    dependencies={"task_arch_spec"},
                    resources_required=["core_module.py"],
                ),
                WorkItem(
                    task_id="task_qa_tests",
                    title="Develop automated regression test suite",
                    priority=60,
                    dependencies={"task_core_impl"},
                    resources_required=["test_core.py"],
                ),
            ]

        # 3. Design Review if ceremonies enabled
        design_review = None
        if simulate_ceremonies:
            design_review = company.simulate_design_review(
                title="Engineering Architecture Review",
                target_artifact="core_architecture",
            )

        # 4. Dispatch and Execute Tasks Simultaneously
        exec_results = company.submit_and_execute_tasks(
            company_tasks,
            custom_runner_fn=custom_runner_fn,
        )

        # 5. Code Review if ceremonies enabled
        code_review = None
        if simulate_ceremonies and exec_results:
            first_task_id = exec_results[0].task_id
            code_review = company.simulate_code_review(task_id=first_task_id)

        # 6. Retrospective & Release Meeting
        retro_info = company.simulate_retrospective() if simulate_ceremonies else None
        release_info = company.simulate_release_meeting(version="v3.3.0") if simulate_ceremonies else None

        telemetry = company.engine.get_telemetry()

        return {
            "mode": "distributed_company",
            "company_name": company.company_name,
            "tasks_executed": len(exec_results),
            "completed_tasks": telemetry.completed_tasks,
            "failed_tasks": telemetry.failed_tasks,
            "results": [r.to_dict() for r in exec_results],
            "telemetry": asdict(telemetry),
            "standup": standup_info,
            "design_review": design_review.to_dict() if design_review else None,
            "code_review": code_review.to_dict() if code_review else None,
            "retrospective": retro_info,
            "release": release_info,
            "reports": {
                "company_report": company.generate_company_report(),
                "engineering_report": company.generate_engineering_report(),
                "performance_report": company.generate_agent_performance_report(),
                "communication_report": company.generate_communication_graph_report(),
                "task_timeline": company.generate_task_timeline_report(),
                "parallel_timeline": company.generate_parallel_execution_timeline_report(),
                "consensus_report": company.generate_consensus_report(),
                "conflict_report": company.generate_conflict_resolution_report(),
                "resource_report": company.generate_resource_utilization_report(),
                "daily_report": company.generate_daily_engineering_report(),
            },
        }

    def run_company(
        self,
        tasks: Optional[List[Any]] = None,
        custom_runner_fn: Optional[Callable] = None,
        simulate_ceremonies: bool = True,
    ) -> Dict[str, Any]:
        """Alias for execute_company() in Distributed Company Mode (v3.3)."""
        return self.execute_company(
            tasks=tasks,
            custom_runner_fn=custom_runner_fn,
            simulate_ceremonies=simulate_ceremonies,
        )

    # -------------------------------------------------------------------------
    # AutoDev v3.4 Autonomous AI Organization Methods
    # -------------------------------------------------------------------------

    def simulate_organization(
        self,
        customer_request: str = "Build a high-performance transactional payments API with JWT authentication and audit trails.",
        target_version: str = "3.4.0",
    ) -> Dict[str, Any]:
        """
        Executes end-to-end Autonomous AI Organization workflow across 16 departments (v3.4).
        """
        return self.enterprise_organization.simulate_company_workflow(
            customer_request=customer_request,
            target_version=target_version,
        )

    def query_organization(self) -> Dict[str, Any]:
        """
        Queries organizational structure, department health scores, budget, and metrics (v3.4).
        """
        return self.enterprise_organization.get_organization_summary()

    def conduct_organization_meetings(self) -> List[Dict[str, Any]]:
        """
        Conducts autonomous corporate meetings (Standup, Planning, Review, Retro, etc.) (v3.4).
        """
        return self.enterprise_organization.conduct_all_standard_meetings()

    def resolve_organization_dispute(
        self,
        title: str,
        domain: str,
        options: List[str],
        voter_preferences: Dict[str, str],
        evidence_dict: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Resolves inter-departmental technical or architectural dispute via Decision Engine (v3.4).
        """
        return self.enterprise_organization.resolve_departmental_dispute(
            title=title,
            domain=domain,
            options=options,
            voter_preferences=voter_preferences,
            evidence_dict=evidence_dict,
        )

    def simulate_enterprise_federation(
        self,
        num_cycles: int = 5,
        messages_per_cycle: int = 20,
    ) -> Dict[str, Any]:
        """
        Simulates multi-company enterprise ecosystem activity (v3.5).
        """
        return self.enterprise_federation.simulate_ecosystem(
            num_cycles=num_cycles,
            messages_per_cycle=messages_per_cycle,
        )

    def execute_cross_company_collaboration(
        self,
        algorithm_name: str = "QuantumDeterministicAttention-v2",
        expected_business_impact_usd: float = 5000000.0,
    ) -> Dict[str, Any]:
        """
        Executes end-to-end autonomous cross-company AI collaboration pipeline (v3.5).
        """
        return self.enterprise_federation.execute_cross_company_ai_collaboration(
            algorithm_name=algorithm_name,
            expected_business_impact_usd=expected_business_impact_usd,
        )

    def query_global_dashboard(self) -> Dict[str, Any]:
        """
        Retrieves macroscopic enterprise executive telemetry dashboard (v3.5).
        """
        return self.enterprise_federation.get_global_dashboard().to_dict()

    def conduct_autonomous_research_cycle(
        self,
        module_name: str = "orchestrator",
        candidate_code: str = "def fast_execution(): return True",
        baseline_code: str = "def slow_execution(): return False",
    ) -> Dict[str, Any]:
        """
        Executes end-to-end autonomous scientific discovery and R&D pipeline (v3.6).
        """
        return self.research_lab.conduct_research_cycle(
            module_name=module_name,
            candidate_code=candidate_code,
            baseline_code=baseline_code,
        )

    def query_research_metrics(self) -> Dict[str, Any]:
        """
        Retrieves global R&D productivity and scientific rigor metrics (v3.6).
        """
        return self.research_lab.compute_global_metrics().to_dict()

    def query_patent_portfolio(self) -> List[Dict[str, Any]]:
        """
        Retrieves corporate patent portfolio and filings (v3.6).
        """
        return [pat.to_dict() for pat in self.research_lab.patent_generator.get_all_applications()]

    def query_paper_repository(self) -> List[Dict[str, Any]]:
        """
        Retrieves registered scientific papers and pre-prints (v3.6).
        """
        return [p.to_dict() for p in self.research_lab.paper_generator.get_all_papers()]


# Backwards compatibility alias
AutoDevOrchestrator = Orchestrator


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
