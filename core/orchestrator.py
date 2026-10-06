"""
orchestrator.py - Central Brain & Pipeline Controller for AutoDev

Responsible for coordinating all autonomous agents (Planner, ContextBuilder,
TaskPlanner, Coder, Reviewer, Tester, Git, and Scheduler) through an extensible,
resilient execution pipeline.
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is available on sys.path for direct script execution
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.developer_agent import DeveloperAgent
from agents.task_planner_agent import Task, TaskPlannerAgent
from core.context_builder import ContextBuilder


# Configure unified module logger
def setup_logger(log_dir: str | Path = "logs") -> logging.Logger:
    """
    Sets up and configures the AutoDev system logger.
    """
    logger = logging.getLogger("AutoDev.Orchestrator")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Console output handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-5s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File output handler (if log_dir is specified)
        try:
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(
                log_path / "orchestrator.log", encoding="utf-8"
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (OSError, PermissionError):
            pass

    return logger


@dataclass
class ExecutionResult:
    """
    Structured summary result returned by the Orchestrator pipeline.
    """
    status: str
    started_at: str
    finished_at: str
    duration_seconds: float
    steps_completed: List[str] = field(default_factory=list)
    steps_failed: List[str] = field(default_factory=list)
    context_loaded: bool = False
    tasks_generated: int = 0
    message: str = ""
    error: Optional[str] = None


class Orchestrator:
    """
    The central coordinator and pipeline controller of the AutoDev system.

    Coordinates the execution sequence:
    1. Plan Verification (PlannerAgent hook)
    2. Context Aggregation (ContextBuilder)
    3. Task Decomposition (TaskPlannerAgent)
    4. Code Implementation (CoderAgent hook)
    5. Review & Verification (ReviewerAgent / TesterAgent hooks)
    6. Version Control Sync (GitAgent hook)
    """

    def __init__(
        self,
        plan_path: str | Path = "memory/project_plan.json",
        state_path: str | Path = "memory/state.json",
        tasks_path: str | Path = "memory/tasks.json",
        project_root: Optional[str | Path] = None,
        log_dir: str | Path = "logs",
    ) -> None:
        """
        Initializes the Orchestrator with memory paths and configurations.

        Args:
            plan_path: Path to memory/project_plan.json.
            state_path: Path to memory/state.json.
            tasks_path: Path to memory/tasks.json.
            project_root: Optional target workspace root directory.
            log_dir: Directory for runtime logs.
        """
        self.plan_path = Path(plan_path)
        self.state_path = Path(state_path)
        self.tasks_path = Path(tasks_path)
        self.project_root = Path(project_root) if project_root else None
        self.logger = setup_logger(log_dir=log_dir)

        # Agent & service components (extensible instances)
        self.context_builder = ContextBuilder(
            plan_path=self.plan_path,
            state_path=self.state_path,
            project_root=self.project_root,
        )
        self.task_planner = TaskPlannerAgent(output_path=self.tasks_path)
        self.developer_agent = DeveloperAgent(plan_path=self.plan_path)

    # -------------------------------------------------------------------------
    # Pipeline Step Implementations
    # -------------------------------------------------------------------------

    def _step_verify_or_create_plan(self) -> None:
        """
        Step 1: Checks for existing project_plan.json.
        Invokes PlannerAgent placeholder if the plan is missing.
        """
        self.logger.info("Checking project plan status...")
        if not self.plan_path.is_file():
            self.logger.warning("Project plan missing.")
            self.logger.info("PlannerAgent would execute here.")
            # In future versions: invoke PlannerAgent to generate project_plan.json interactively or via LLM
        else:
            self.logger.info(f"Verified existing project plan at '{self.plan_path}'.")

    def _step_build_context(self) -> Dict[str, Any]:
        """
        Step 2: Gathers comprehensive workspace and plan context.
        """
        self.logger.info("Loading Context...")
        context = self.context_builder.build(project_root=self.project_root)
        self.logger.info(
            f"Context loaded successfully. Project: '{context.get('project_name')}', "
            f"Day: {context.get('current_day')}, Loaded Files: {len(context.get('project_files', {}))}."
        )
        return context

    def _step_build_tasks(self, context: Dict[str, Any]) -> List[Task]:
        """
        Step 3: Decomposes active phase into atomic implementation tasks.
        """
        self.logger.info("Building Tasks...")
        tasks = self.task_planner.execute(context)
        self.logger.info(f"Generated {len(tasks)} atomic task(s) saved to '{self.tasks_path}'.")
        return tasks

    def _step_execute_coder(self, context: Dict[str, Any], tasks: List[Task]) -> None:
        """
        Step 4: Executes CoderAgent (placeholder in Version 1).
        """
        self.logger.info("Executing CoderAgent...")
        self.logger.info("CoderAgent execution placeholder.")
        # Future implementation: pass tasks and context to CoderAgent for LLM code generation

    def _step_execute_tester(self, context: Dict[str, Any]) -> None:
        """
        Step 5 (Future Hook): Automated testing and quality verification.
        """
        # Placeholder for TesterAgent
        pass

    def _step_execute_git(self, context: Dict[str, Any]) -> None:
        """
        Step 6 (Future Hook): Git commit and remote push synchronization.
        """
        # Placeholder for GitAgent
        pass

    # -------------------------------------------------------------------------
    # Main Workflow Entrypoint
    # -------------------------------------------------------------------------

    def run(self) -> ExecutionResult:
        """
        Executes the central AutoDev coordination workflow.

        Returns:
            ExecutionResult dataclass detailing pipeline execution metrics.
        """
        start_time = time.time()
        started_at = datetime.now().isoformat(timespec="seconds")

        steps_completed: List[str] = []
        steps_failed: List[str] = []
        context_loaded = False
        tasks_count = 0

        self.logger.info("=" * 50)
        self.logger.info("Starting AutoDev")
        self.logger.info("=" * 50)

        try:
            # Stage 1: Plan Verification / Creation
            self._step_verify_or_create_plan()
            steps_completed.append("PlannerAgent")

            # Stage 2: Context Building
            context = self._step_build_context()
            context_loaded = True
            steps_completed.append("ContextBuilder")

            # Stage 3: Task Decomposition
            tasks = self._step_build_tasks(context)
            tasks_count = len(tasks)
            steps_completed.append("TaskPlanner")

            # Stage 4: Code Generation (Placeholder)
            self._step_execute_coder(context, tasks)
            steps_completed.append("CoderAgent")

            # Stage 5 & 6 (Future Extensions)
            self._step_execute_tester(context)
            self._step_execute_git(context)

            self.logger.info("Workflow Complete")
            self.logger.info("=" * 50)

            duration = round(time.time() - start_time, 2)
            finished_at = datetime.now().isoformat(timespec="seconds")

            return ExecutionResult(
                status="SUCCESS",
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                context_loaded=context_loaded,
                tasks_generated=tasks_count,
                message="Workflow completed successfully.",
            )

        except Exception as exc:
            self.logger.error(f"Execution failed with exception: {exc}", exc_info=True)
            failed_step = (
                "ContextBuilder"
                if "ContextBuilder" not in steps_completed
                else ("TaskPlanner" if "TaskPlanner" not in steps_completed else "CoderAgent")
            )
            steps_failed.append(failed_step)

            duration = round(time.time() - start_time, 2)
            finished_at = datetime.now().isoformat(timespec="seconds")

            return ExecutionResult(
                status="FAILED",
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                context_loaded=context_loaded,
                tasks_generated=tasks_count,
                message=f"Workflow failed at stage '{failed_step}'.",
                error=str(exc),
            )


if __name__ == "__main__":
    orchestrator = Orchestrator()
    result = orchestrator.run()
    print("\nExecution Result Summary:")
    print(result)
