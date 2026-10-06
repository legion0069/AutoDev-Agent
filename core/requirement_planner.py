"""
requirement_planner.py - Requirement Planner Subsystem for AutoDev (Version 1.6)

Converts high-level natural language software requirements into complete,
multi-day, production-grade implementation roadmaps (project_plan.json).

Acts as the very first stage before orchestration begins. Provider-independent
and fully compatible with BaseLLM.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from core.llm import BaseLLM
from core.providers.mock_provider import MockProvider

logger = logging.getLogger("AutoDev.RequirementPlanner")

VALID_PRIORITIES: Set[str] = {"critical", "high", "medium", "low"}


# =============================================================================
# Structured Exceptions
# =============================================================================

class RequirementPlannerError(Exception):
    """Base exception for all requirement planning failures."""
    pass


class PlanParsingError(RequirementPlannerError):
    """Raised when LLM response cannot be parsed into valid JSON or schema."""
    pass


class PlanValidationError(RequirementPlannerError):
    """Raised when a generated or loaded plan violates architectural or consistency rules."""
    pass


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass
class ProjectSpecification:
    """
    High-level project specification metadata.
    """
    project_name: str
    description: str
    technology_stack: List[str] = field(default_factory=list)
    target_platform: str = "cross-platform"
    constraints: List[str] = field(default_factory=list)
    deliverables: List[str] = field(default_factory=list)
    estimated_days: int = 1
    priority: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        """Converts specification to serializable dictionary."""
        return {
            "project_name": self.project_name,
            "description": self.description,
            "technology_stack": list(self.technology_stack),
            "target_platform": self.target_platform,
            "constraints": list(self.constraints),
            "deliverables": list(self.deliverables),
            "estimated_days": self.estimated_days,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectSpecification:
        """Instantiates specification from dictionary."""
        tech_stack = data.get("technology_stack", [])
        if isinstance(tech_stack, str):
            tech_stack = [s.strip() for s in tech_stack.split(",") if s.strip()]
        return cls(
            project_name=str(data.get("project_name", "")),
            description=str(data.get("description", "")),
            technology_stack=list(tech_stack),
            target_platform=str(data.get("target_platform", "cross-platform")),
            constraints=list(data.get("constraints", [])),
            deliverables=list(data.get("deliverables", [])),
            estimated_days=int(data.get("estimated_days", 1)),
            priority=str(data.get("priority", "medium")),
        )


@dataclass
class ProjectTask:
    """
    Represents an atomic, actionable implementation task in a roadmap phase.
    """
    id: str
    title: str
    description: str = ""
    priority: str = "medium"
    estimated_files: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    estimated_hours: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Converts task to serializable dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "estimated_files": list(self.estimated_files),
            "dependencies": list(self.dependencies),
            "estimated_hours": self.estimated_hours,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectTask:
        """Instantiates task from dictionary."""
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            priority=data.get("priority", "medium"),
            estimated_files=list(data.get("estimated_files", [])),
            dependencies=list(data.get("dependencies", [])),
            estimated_hours=float(data.get("estimated_hours", 1.0)),
        )


@dataclass
class ProjectPhase:
    """
    Represents a single day's development milestone containing atomic tasks.
    """
    day_number: int
    goal: str
    deliverables: List[str] = field(default_factory=list)
    tasks: List[ProjectTask] = field(default_factory=list)

    # Backward compatibility properties
    @property
    def day(self) -> int:
        return self.day_number

    @property
    def phase_name(self) -> str:
        return self.goal

    @property
    def goals(self) -> List[str]:
        return [self.goal] if self.goal else []

    def to_dict(self) -> Dict[str, Any]:
        """Converts phase to serializable dictionary."""
        return {
            "day": self.day_number,
            "day_number": self.day_number,
            "phase_name": self.goal,
            "goal": self.goal,
            "goals": [self.goal] if self.goal else [],
            "deliverables": list(self.deliverables),
            "tasks": [t.to_dict() if isinstance(t, ProjectTask) else t for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectPhase:
        """Instantiates phase from dictionary."""
        day_num = data.get("day_number", data.get("day", 1))
        goal_text = data.get("goal", data.get("phase_name", ""))
        if not goal_text and "goals" in data and isinstance(data["goals"], list) and data["goals"]:
            goal_text = data["goals"][0]

        raw_tasks = data.get("tasks", [])
        tasks_list: List[ProjectTask] = []
        for i, t in enumerate(raw_tasks):
            if isinstance(t, ProjectTask):
                tasks_list.append(t)
            elif isinstance(t, dict):
                tasks_list.append(ProjectTask.from_dict(t))
            elif isinstance(t, str):
                tasks_list.append(
                    ProjectTask(
                        id=f"DAY{day_num}-TASK{i+1:02d}",
                        title=t,
                        description=t,
                        priority="medium",
                        estimated_files=[],
                        dependencies=[],
                        estimated_hours=1.0,
                    )
                )

        return cls(
            day_number=int(day_num) if day_num is not None else 1,
            goal=str(goal_text),
            deliverables=list(data.get("deliverables", [])),
            tasks=tasks_list,
        )


@dataclass
class ProjectPlan:
    """
    Comprehensive multi-day project execution plan roadmap.
    """
    project_name: str
    summary: str
    technology_stack: List[str] = field(default_factory=list)
    phases: List[ProjectPhase] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.6"

    # Backward compatibility properties
    @property
    def project_description(self) -> str:
        return self.summary

    @property
    def total_days(self) -> int:
        return len(self.phases)

    def to_dict(self) -> Dict[str, Any]:
        """Converts plan to serializable dictionary."""
        return {
            "project_name": self.project_name,
            "project_description": self.summary,
            "summary": self.summary,
            "technology_stack": list(self.technology_stack),
            "total_days": len(self.phases),
            "phases": [p.to_dict() for p in self.phases],
            "generated_at": self.generated_at,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectPlan:
        """Instantiates plan from dictionary."""
        summary = data.get("summary", data.get("project_description", ""))
        tech_stack = data.get("technology_stack", [])
        if isinstance(tech_stack, str):
            tech_stack = [s.strip() for s in tech_stack.split(",") if s.strip()]

        raw_phases = data.get("phases", [])
        phases = [
            p if isinstance(p, ProjectPhase) else ProjectPhase.from_dict(p)
            for p in raw_phases
        ]
        return cls(
            project_name=str(data.get("project_name", "")),
            summary=str(summary),
            technology_stack=list(tech_stack),
            phases=phases,
            generated_at=str(
                data.get("generated_at", data.get("created_at", datetime.now().isoformat()))
            ),
            version=str(data.get("version", "1.6")),
        )

    def to_json(self, indent: int = 2) -> str:
        """Serializes plan to JSON formatted string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> ProjectPlan:
        """Deserializes plan from JSON formatted string."""
        return cls.from_dict(json.loads(json_str))


# =============================================================================
# Requirement Planner Subsystem
# =============================================================================

PLANNER_SYSTEM_PROMPT = """You are a Principal Software Architect and Technical Lead.
Your mission is to analyze high-level software requirements and decompose them into a comprehensive, multi-day, production-grade implementation roadmap.

You MUST respond with a single valid JSON object strictly matching the schema below. Do NOT output any conversational text or markdown explanation outside the JSON.

SCHEMA:
{
  "project_name": "Project Name",
  "summary": "High-level summary of the architecture and goals",
  "technology_stack": ["Python", "Pytest", "..."],
  "version": "1.6",
  "phases": [
    {
      "day_number": 1,
      "goal": "Project Setup & Architectural Skeleton",
      "deliverables": [
        "Repository structure scaffold",
        "Base configuration and entry point"
      ],
      "tasks": [
        {
          "id": "DAY1-TASK01",
          "title": "Initialize project structure and configuration",
          "description": "Create core modules, configuration loader, and base environment settings.",
          "priority": "critical",
          "estimated_files": ["core/config.py", "core/__init__.py"],
          "dependencies": [],
          "estimated_hours": 2.0
        },
        {
          "id": "DAY1-TASK02",
          "title": "Implement domain models and schemas",
          "description": "Define data structures, schemas, and base validation logic.",
          "priority": "high",
          "estimated_files": ["models/schemas.py"],
          "dependencies": ["DAY1-TASK01"],
          "estimated_hours": 3.0
        }
      ]
    },
    {
      "day_number": 2,
      "goal": "Core Business Logic & Testing",
      "deliverables": [
        "Core service implementation",
        "Automated unit and integration test suite"
      ],
      "tasks": [
        {
          "id": "DAY2-TASK01",
          "title": "Implement core services and engine",
          "description": "Implement business logic workflows and service operations.",
          "priority": "high",
          "estimated_files": ["services/engine.py"],
          "dependencies": ["DAY1-TASK02"],
          "estimated_hours": 4.0
        },
        {
          "id": "DAY2-TASK02",
          "title": "Implement test suite and verification",
          "description": "Add comprehensive unit and edge case tests.",
          "priority": "medium",
          "estimated_files": ["tests/test_engine.py"],
          "dependencies": ["DAY2-TASK01"],
          "estimated_hours": 2.5
        }
      ]
    },
    {
      "day_number": 3,
      "goal": "Hardening, Documentation & Release Readiness",
      "deliverables": [
        "Production documentation and README",
        "Passing test suite verification"
      ],
      "tasks": [
        {
          "id": "DAY3-TASK01",
          "title": "Write comprehensive documentation and README",
          "description": "Create user documentation, API references, and architecture guides.",
          "priority": "medium",
          "estimated_files": ["README.md"],
          "dependencies": ["DAY2-TASK02"],
          "estimated_hours": 2.0
        }
      ]
    }
  ]
}

STRICT CONSTRAINTS:
1. Every task ID must follow the pattern: DAY<DayNumber>-TASK<TaskIndexNumber> (e.g. DAY1-TASK01, DAY1-TASK02, DAY2-TASK01).
2. All task IDs must be globally unique across the entire roadmap.
3. Tasks may only depend on previously existing task IDs.
4. Circular dependencies are strictly forbidden.
5. Priority must be one of: "critical", "high", "medium", "low".
6. Estimated hours must be non-negative numbers (e.g. 1.0, 2.5).
7. Each day phase must contain day_number >= 1, a goal, non-empty deliverables, and atomic tasks.
"""


class RequirementPlanner:
    """
    Automated Requirement Planner subsystem for AutoDev.
    Translates natural language project requirements into structured multi-day plans.
    """

    def __init__(self, llm: Optional[BaseLLM] = None) -> None:
        """
        Initializes RequirementPlanner with an optional BaseLLM provider.
        """
        self.llm: BaseLLM = llm if llm is not None else MockProvider()

    def generate_plan(self, requirement: str) -> ProjectPlan:
        """
        Generates a complete multi-day ProjectPlan from a software requirement.

        Args:
            requirement: High-level software requirement description.

        Returns:
            Validated ProjectPlan instance.

        Raises:
            RequirementPlannerError: If requirement is empty or invalid.
            PlanParsingError: If LLM response cannot be parsed.
            PlanValidationError: If the generated plan fails validation rules.
        """
        if not requirement or not isinstance(requirement, str) or not requirement.strip():
            raise RequirementPlannerError("Requirement must be a non-empty string.")

        clean_req = requirement.strip()
        logger.info("Generating implementation plan for requirement: '%s'...", clean_req[:80])

        prompt = f"{PLANNER_SYSTEM_PROMPT}\n\nUSER REQUIREMENT:\n{clean_req}\n\nRespond with valid JSON only:"

        # Generate response from LLM provider
        raw_response = self.llm.generate(prompt)

        # Check if fallback deterministic plan should be used for default mock provider
        if (
            isinstance(self.llm, MockProvider)
            and not getattr(self.llm, "responses", None)
            and raw_response.startswith("# [MockLLM Response]")
        ):
            logger.info("MockProvider default response detected. Synthesizing deterministic plan...")
            plan = self._synthesize_default_mock_plan(clean_req)
            self.validate_plan(plan)
            return plan

        # Extract and parse JSON
        json_text = self._extract_json(raw_response)
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise PlanParsingError(
                f"Failed to parse LLM response as JSON: {exc}\nRaw response snippet:\n{raw_response[:300]}"
            ) from exc

        if not isinstance(data, dict):
            raise PlanParsingError(f"Expected top-level JSON dictionary, got {type(data).__name__}.")

        plan = ProjectPlan.from_dict(data)
        self.validate_plan(plan)
        return plan

    def validate_plan(self, plan: ProjectPlan) -> bool:
        """
        Validates a ProjectPlan against all structural, uniqueness, and dependency rules.

        Args:
            plan: ProjectPlan to validate.

        Returns:
            True if the plan is valid.

        Raises:
            PlanValidationError: If any rule is violated.
        """
        if not isinstance(plan, ProjectPlan):
            raise PlanValidationError(f"Expected ProjectPlan instance, got {type(plan).__name__}.")

        # 1. Project name validation
        if not plan.project_name or not str(plan.project_name).strip():
            raise PlanValidationError("Project plan is missing a project name.")

        # 2. Phases validation
        if not plan.phases or not isinstance(plan.phases, list) or len(plan.phases) == 0:
            raise PlanValidationError("Project plan must contain at least one development phase.")

        seen_phase_days: Set[int] = set()
        seen_task_ids: Set[str] = set()
        all_tasks: List[ProjectTask] = []
        task_dep_graph: Dict[str, List[str]] = {}

        for phase in plan.phases:
            # Phase day number validation
            if phase.day_number is None or phase.day_number <= 0:
                raise PlanValidationError(
                    f"Invalid phase day number: {phase.day_number}. Must be >= 1."
                )
            if phase.day_number in seen_phase_days:
                raise PlanValidationError(
                    f"Duplicate phase day number found: {phase.day_number}."
                )
            seen_phase_days.add(phase.day_number)

            # Phase goal validation
            if not phase.goal or not str(phase.goal).strip():
                raise PlanValidationError(f"Phase {phase.day_number} is missing a goal.")

            # Deliverables validation
            if not phase.deliverables or not any(str(d).strip() for d in phase.deliverables):
                raise PlanValidationError(
                    f"Phase {phase.day_number} is missing required deliverables."
                )

            # Tasks validation
            if not phase.tasks or len(phase.tasks) == 0:
                raise PlanValidationError(
                    f"Phase {phase.day_number} must contain at least one task."
                )

            for task in phase.tasks:
                if not isinstance(task, ProjectTask):
                    raise PlanValidationError(
                        f"Expected ProjectTask object, got {type(task).__name__}."
                    )

                # Task ID validation
                if not task.id or not str(task.id).strip():
                    raise PlanValidationError("Task ID cannot be empty.")
                if task.id in seen_task_ids:
                    raise PlanValidationError(f"Duplicate task ID found: '{task.id}'.")
                seen_task_ids.add(task.id)

                # Task title validation
                if not task.title or not str(task.title).strip():
                    raise PlanValidationError(
                        f"Task '{task.id}' in Phase {phase.day_number} has an empty title."
                    )

                # Priority validation
                if isinstance(task.priority, str):
                    if task.priority.lower() not in VALID_PRIORITIES:
                        raise PlanValidationError(
                            f"Task '{task.id}' has invalid priority '{task.priority}'. Allowed: {VALID_PRIORITIES}."
                        )
                elif isinstance(task.priority, int):
                    if task.priority < 1 or task.priority > 5:
                        raise PlanValidationError(
                            f"Task '{task.id}' has invalid priority level '{task.priority}'."
                        )
                else:
                    raise PlanValidationError(
                        f"Task '{task.id}' has unsupported priority type '{type(task.priority)}'."
                    )

                # Estimated hours validation
                if task.estimated_hours is not None and task.estimated_hours < 0:
                    raise PlanValidationError(
                        f"Task '{task.id}' has negative estimated hours: {task.estimated_hours}."
                    )

                all_tasks.append(task)
                task_dep_graph[task.id] = list(task.dependencies)

        # 3. Dependencies & cycle validation
        for task in all_tasks:
            for dep in task.dependencies:
                if dep not in seen_task_ids:
                    raise PlanValidationError(
                        f"Task '{task.id}' references non-existent dependency target '{dep}'."
                    )

        # 4. Cycle detection (DFS with 3-state coloring)
        visited_state: Dict[str, int] = {}  # 0: unvisited, 1: visiting (stack), 2: visited

        def dfs_detect_cycle(node_id: str, path: List[str]) -> None:
            visited_state[node_id] = 1
            for dep_id in task_dep_graph.get(node_id, []):
                if visited_state.get(dep_id, 0) == 1:
                    cycle_repr = " -> ".join(path + [dep_id])
                    raise PlanValidationError(
                        f"Dependency cycle detected involving tasks: {cycle_repr}."
                    )
                if visited_state.get(dep_id, 0) == 0:
                    dfs_detect_cycle(dep_id, path + [dep_id])
            visited_state[node_id] = 2

        for task_id in seen_task_ids:
            if visited_state.get(task_id, 0) == 0:
                dfs_detect_cycle(task_id, [task_id])

        return True

    def save_plan(self, plan: ProjectPlan, path: Union[str, Path]) -> None:
        """
        Validates and saves a ProjectPlan to disk in JSON format.

        Args:
            plan: ProjectPlan instance to serialize.
            path: Target file path.
        """
        self.validate_plan(plan)
        target_path = Path(path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(plan.to_json(indent=2))
        logger.info("Project plan successfully saved to '%s'.", target_path)

    def load_plan(self, path: Union[str, Path]) -> ProjectPlan:
        """
        Loads and validates a ProjectPlan from disk.

        Args:
            path: File path of the project plan JSON.

        Returns:
            Validated ProjectPlan instance.

        Raises:
            FileNotFoundError: If the plan file does not exist.
            PlanParsingError: If the JSON is invalid.
            PlanValidationError: If validation rules fail.
        """
        target_path = Path(path).resolve()
        if not target_path.is_file():
            raise FileNotFoundError(f"Project plan file not found at '{target_path}'.")

        with open(target_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as exc:
                raise PlanParsingError(
                    f"Malformed JSON in plan file '{target_path}': {exc}"
                ) from exc

        if not isinstance(data, dict):
            raise PlanParsingError(f"Plan file root must be a JSON object, got {type(data).__name__}.")

        plan = ProjectPlan.from_dict(data)
        self.validate_plan(plan)
        return plan

    def summarize(self, plan: ProjectPlan) -> str:
        """
        Generates a human-readable roadmap summary of the project plan.

        Args:
            plan: ProjectPlan instance.

        Returns:
            Formatted string summary.
        """
        tech_str = ", ".join(plan.technology_stack) if plan.technology_stack else "Unspecified"
        total_tasks = sum(len(phase.tasks) for phase in plan.phases)
        total_hours = sum(
            t.estimated_hours for phase in plan.phases for t in phase.tasks
        )

        lines = [
            "=" * 60,
            f"PROJECT IMPLEMENTATION ROADMAP: {plan.project_name}",
            f"Version: {plan.version} | Generated: {plan.generated_at}",
            f"Technology Stack: {tech_str}",
            f"Total Phases: {len(plan.phases)} | Total Tasks: {total_tasks} | Est. Hours: {total_hours:.1f}h",
            "=" * 60,
            f"Summary: {plan.summary}",
            "",
            "DAILY MILESTONES & PHASES:",
        ]

        for phase in plan.phases:
            lines.append(f"\nPhase Day {phase.day_number}: {phase.goal}")
            lines.append(f"  Deliverables: {', '.join(phase.deliverables)}")
            lines.append(f"  Tasks ({len(phase.tasks)}):")
            for task in phase.tasks:
                deps_str = ", ".join(task.dependencies) if task.dependencies else "None"
                files_str = ", ".join(task.estimated_files) if task.estimated_files else "None"
                lines.append(
                    f"    - [{task.id}] {task.title} (Priority: {task.priority}, Est: {task.estimated_hours}h)"
                )
                if task.description:
                    lines.append(f"        Description  : {task.description}")
                lines.append(f"        Dependencies : {deps_str}")
                lines.append(f"        Target Files : {files_str}")

        lines.append("=" * 60)
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _extract_json(self, raw_text: str) -> str:
        """Extracts JSON content from text, stripping markdown fences if present."""
        text = raw_text.strip()
        if "```" in text:
            pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            if matches:
                text = matches[0].strip()
            else:
                lines = text.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
        return text

    def _synthesize_default_mock_plan(self, requirement: str) -> ProjectPlan:
        """Generates a structured default 3-day roadmap for offline testing."""
        words = requirement.split()
        title = " ".join(words[:4]).title() if words else "AutoDev System"

        phase1 = ProjectPhase(
            day_number=1,
            goal="Project Setup & Architectural Skeleton",
            deliverables=["Directory scaffold", "Configuration loader", "Core data models"],
            tasks=[
                ProjectTask(
                    id="DAY1-TASK01",
                    title=f"Scaffold project structure for {title}",
                    description="Set up base directory structure, dependencies, and entry point.",
                    priority="critical",
                    estimated_files=["core/config.py", "core/__init__.py"],
                    dependencies=[],
                    estimated_hours=2.0,
                ),
                ProjectTask(
                    id="DAY1-TASK02",
                    title="Implement core schemas and data models",
                    description="Define domain models and input validation schemas.",
                    priority="high",
                    estimated_files=["models/schemas.py"],
                    dependencies=["DAY1-TASK01"],
                    estimated_hours=3.0,
                ),
            ],
        )

        phase2 = ProjectPhase(
            day_number=2,
            goal="Core Business Logic & Service Implementation",
            deliverables=["Core business service engine", "Automated test suite"],
            tasks=[
                ProjectTask(
                    id="DAY2-TASK01",
                    title="Implement core business logic workflows",
                    description="Develop service handlers and computational workflows.",
                    priority="high",
                    estimated_files=["services/engine.py"],
                    dependencies=["DAY1-TASK02"],
                    estimated_hours=4.0,
                ),
                ProjectTask(
                    id="DAY2-TASK02",
                    title="Implement comprehensive unit test suite",
                    description="Write automated pytest test cases for core services.",
                    priority="medium",
                    estimated_files=["tests/test_engine.py"],
                    dependencies=["DAY2-TASK01"],
                    estimated_hours=2.5,
                ),
            ],
        )

        phase3 = ProjectPhase(
            day_number=3,
            goal="Hardening, Documentation & Release Readiness",
            deliverables=["Complete README documentation", "Release bundle"],
            tasks=[
                ProjectTask(
                    id="DAY3-TASK01",
                    title="Write comprehensive documentation and README",
                    description="Create setup guide, architecture overview, and API references.",
                    priority="medium",
                    estimated_files=["README.md"],
                    dependencies=["DAY2-TASK02"],
                    estimated_hours=2.0,
                ),
            ],
        )

        return ProjectPlan(
            project_name=title,
            summary=f"Implementation roadmap for: {requirement}",
            technology_stack=["Python", "Pytest"],
            phases=[phase1, phase2, phase3],
            generated_at=datetime.now().isoformat(),
            version="1.6",
        )
