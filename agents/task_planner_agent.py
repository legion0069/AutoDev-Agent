"""
task_planner_agent.py - Task Planner Agent for AutoDev (Version 1)

Responsible for converting the current day's phase from the project context
into an ordered list of atomic implementation tasks saved to memory/tasks.json.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to sys.path if run directly as script
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.llm import BaseLLM


@dataclass
class Task:
    """
    Represents an atomic, actionable implementation task.
    """
    id: str
    title: str
    description: str
    priority: int = 1
    status: str = "pending"
    dependencies: List[str] = field(default_factory=list)
    estimated_files: List[str] = field(default_factory=list)
    estimated_duration: str = "15 min"

    def to_dict(self) -> Dict[str, Any]:
        """Converts task instance to a serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        """Creates a Task instance from a dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            priority=data.get("priority", 1),
            status=data.get("status", "pending"),
            dependencies=data.get("dependencies", []),
            estimated_files=data.get("estimated_files", []),
            estimated_duration=data.get("estimated_duration", "15 min"),
        )


class TaskPlannerAgent:
    """
    Breaks down the active development phase into atomic engineering tasks.
    Supports deterministic synthesis for Version 1 and future LLM integration.
    """

    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        output_path: str | Path = "memory/tasks.json",
    ) -> None:
        """
        Initializes the TaskPlannerAgent.

        Args:
            llm: Optional LLM provider instance for future model-driven planning.
            output_path: Target path for saving generated tasks (default: memory/tasks.json).
        """
        self.llm = llm
        self.output_path = Path(output_path)

    def plan_tasks(self, context: Dict[str, Any]) -> List[Task]:
        """
        Decomposes the current phase within the context into a list of Task objects.

        Args:
            context: Context dictionary produced by ContextBuilder.

        Returns:
            List of structured Task instances.
        """
        if self.llm is not None:
            return self._plan_tasks_with_llm(context)
        return self._plan_tasks_deterministic(context)

    def _plan_tasks_deterministic(self, context: Dict[str, Any]) -> List[Task]:
        """
        Deterministic task generator for Version 1. Converts phase goals,
        tasks, and deliverables into ordered atomic tasks with dependencies.
        """
        current_day = context.get("current_day", 1)
        current_phase = context.get("current_phase", {}) or {}
        project_name = context.get("project_name", "Project")
        phase_name = current_phase.get("phase_name", f"Day {current_day} Execution")

        raw_tasks = current_phase.get("tasks", [])
        deliverables = current_phase.get("deliverables", [])
        testing_focus = current_phase.get("testing_focus", "Unit and integration tests")

        # Fallback if phase tasks are unspecified
        if not raw_tasks:
            raw_tasks = [
                f"Initialize and configure components for {phase_name}",
                f"Implement core logic for {phase_name}",
                f"Write tests and verify deliverables for {phase_name}",
            ]

        tasks: List[Task] = []
        previous_task_id: Optional[str] = None

        for idx, task_text in enumerate(raw_tasks, start=1):
            task_id = f"DAY{current_day}-TASK{idx:02d}"
            dependencies = [previous_task_id] if previous_task_id else []

            # Estimate files relevant to this atomic step
            est_files: List[str] = []
            if idx <= len(deliverables):
                est_files.append(deliverables[idx - 1])

            tasks.append(
                Task(
                    id=task_id,
                    title=task_text,
                    description=f"Execute: {task_text} as part of {phase_name} on {project_name}.",
                    priority=idx,
                    status="pending",
                    dependencies=dependencies,
                    estimated_files=est_files,
                    estimated_duration=f"{15 + (idx * 5)} min",
                )
            )
            previous_task_id = task_id

        # Append validation / testing task
        test_task_id = f"DAY{current_day}-TASK{len(raw_tasks) + 1:02d}"
        tasks.append(
            Task(
                id=test_task_id,
                title=f"Execute automated validation & {testing_focus}",
                description=f"Verify all Day {current_day} deliverables pass test suite and quality checks.",
                priority=len(raw_tasks) + 1,
                status="pending",
                dependencies=[previous_task_id] if previous_task_id else [],
                estimated_files=["tests/"],
                estimated_duration="20 min",
            )
        )

        return tasks

    def _plan_tasks_with_llm(self, context: Dict[str, Any]) -> List[Task]:
        """
        Placeholder for future LLM-driven task decomposition.

        Args:
            context: Project context dictionary.

        Returns:
            List of Task instances synthesized by the LLM.
        """
        # In future versions, this will prompt self.llm to produce JSON tasks
        # and parse them into Task instances.
        return self._plan_tasks_deterministic(context)

    def save_tasks(
        self,
        tasks: List[Task],
        output_path: Optional[str | Path] = None,
    ) -> Path:
        """
        Serializes and saves tasks to a JSON file.

        Args:
            tasks: List of Task objects.
            output_path: Target file path override.

        Returns:
            Path object of the saved tasks file.
        """
        target_path = Path(output_path) if output_path else self.output_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        serializable = [task.to_dict() for task in tasks]

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)

        return target_path

    def load_tasks(self, path: Optional[str | Path] = None) -> List[Task]:
        """
        Loads tasks from a JSON file into Task objects.

        Args:
            path: Optional file path override.

        Returns:
            List of Task objects.
        """
        target_path = Path(path) if path else self.output_path
        if not target_path.is_file():
            raise FileNotFoundError(f"Tasks file not found at '{target_path}'.")

        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return [Task.from_dict(item) for item in data]

    def execute(self, context: Dict[str, Any]) -> List[Task]:
        """
        Orchestrates planning and saving tasks from context.

        Args:
            context: Context dictionary produced by ContextBuilder.

        Returns:
            List of generated Task objects.
        """
        tasks = self.plan_tasks(context)
        self.save_tasks(tasks)
        return tasks


if __name__ == "__main__":
    from core.context_builder import build_context

    ctx = build_context()
    planner = TaskPlannerAgent()
    generated_tasks = planner.execute(ctx)

    print(f"Generated {len(generated_tasks)} atomic tasks saved to '{planner.output_path}'.")
    for t in generated_tasks:
        print(f"[{t.id}] (Priority {t.priority}) {t.title} -> {t.status} ({t.estimated_duration})")
