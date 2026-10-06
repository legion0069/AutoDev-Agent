"""
developer_agent.py - Developer Agent for AutoDev (Version 1)

Responsible for loading the project plan, parsing today's phase,
synthesizing development prompts, and displaying execution goals.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class DeveloperAgent:
    """
    DeveloperAgent coordinates daily implementation tasks based on
    the structured project plan.
    """

    def __init__(self, plan_path: str | Path = "memory/project_plan.json") -> None:
        self.plan_path = Path(plan_path)
        self.project_plan: Optional[Dict[str, Any]] = None

    def load_project_plan(self, plan_path: Optional[str | Path] = None) -> Dict[str, Any]:
        """
        Loads and caches the structured project plan from JSON file.

        Args:
            plan_path: Optional custom path to project_plan.json.

        Returns:
            The loaded plan dictionary.
        """
        target_path = Path(plan_path) if plan_path else self.plan_path
        if not target_path.is_file():
            raise FileNotFoundError(f"Project plan not found at '{target_path}'.")

        with open(target_path, "r", encoding="utf-8") as f:
            self.project_plan = json.load(f)

        return self.project_plan

    def get_today_phase(self, day: int = 1) -> Dict[str, Any]:
        """
        Retrieves the phase specification for a specific day.

        Args:
            day: Day number (1-indexed).

        Returns:
            The phase dictionary corresponding to the day.
        """
        if self.project_plan is None:
            self.load_project_plan()

        phases: List[Dict[str, Any]] = self.project_plan.get("phases", [])
        for phase in phases:
            if phase.get("day") == day:
                return phase

        raise ValueError(
            f"Phase for Day {day} not found in project plan. "
            f"Total available phases: {len(phases)}."
        )

    def generate_prompt(self, phase: Optional[Dict[str, Any]] = None, day: int = 1) -> str:
        """
        Generates the structured prompt representation for an AI model.

        Args:
            phase: Optional phase dictionary. If not provided, loads for specified day.
            day: Day number if phase is not provided.

        Returns:
            Formatted prompt string.
        """
        target_phase = phase if phase is not None else self.get_today_phase(day)

        project_name = (
            self.project_plan.get("project_name", "Unknown Project")
            if self.project_plan
            else "Unknown Project"
        )
        tech_stack = (
            self.project_plan.get("technology_stack", "N/A")
            if self.project_plan
            else "N/A"
        )

        goals_text = "\n".join(f"- {g}" for g in target_phase.get("goals", []))
        tasks_text = "\n".join(f"- {t}" for t in target_phase.get("tasks", []))
        deliverables_text = "\n".join(f"- {d}" for d in target_phase.get("deliverables", []))

        prompt = (
            f"You are the Lead Developer on project '{project_name}'.\n"
            f"Technology Stack: {tech_stack}\n"
            f"Current Milestone: Day {target_phase.get('day')} - {target_phase.get('phase_name')}\n\n"
            f"Goals:\n{goals_text}\n\n"
            f"Tasks:\n{tasks_text}\n\n"
            f"Deliverables:\n{deliverables_text}\n\n"
            f"Testing Focus: {target_phase.get('testing_focus', 'N/A')}\n"
            f"Expected Git Commit Message: {target_phase.get('git_commit_message', 'N/A')}\n"
        )
        return prompt

    def execute(self, day: int = 1) -> None:
        """
        Executes today's development phase.

        In Version 1, this only prints Today's Phase, Goals, Tasks,
        and Git Commit Message without generating code or modifying files.

        Args:
            day: The day to execute (defaults to 1).
        """
        phase = self.get_today_phase(day)

        print("\n" + "=" * 60)
        print(f"            DEVELOPER AGENT - DAY {phase.get('day', day)} EXECUTION")
        print("=" * 60)
        print(f"\nToday's Phase:")
        print(f"  {phase.get('phase_name', 'N/A')}")

        print(f"\nGoals:")
        for goal in phase.get("goals", []):
            print(f"  - {goal}")

        print(f"\nTasks:")
        for task in phase.get("tasks", []):
            print(f"  * {task}")

        print(f"\nGit Commit Message:")
        print(f"  \"{phase.get('git_commit_message', 'N/A')}\"")
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    agent = DeveloperAgent()
    agent.execute(day=1)
