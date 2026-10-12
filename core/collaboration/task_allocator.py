"""
AutoDev Task Allocator (v2.8)
=============================
Intelligent, skill-affinity and workload-aware task assignment engine for specialized AI engineering agents.
Evaluates required skills, complexity, priority, dependencies, and concurrency opportunities.
"""

from __future__ import annotations

import collections
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from core.collaboration.collaboration_models import (
    AgentRole,
    TaskAssignment,
    TaskPriority,
    TaskStatus,
)

logger = logging.getLogger("AutoDev.TaskAllocator")

ROLE_SKILL_PATTERNS: Dict[AgentRole, List[str]] = {
    AgentRole.ARCHITECTURE: [
        "architect", "architecture", "adr", "module boundary", "design pattern",
        "interface", "coupling", "subsystem", "refactor", "monolith", "microservice",
        "system design", "component diagram", "pipeline structure", "abstractions",
    ],
    AgentRole.BACKEND: [
        "backend", "api", "endpoint", "rest", "graphql", "database", "sql", "orm",
        "model", "crud", "server", "controller", "service", "handler", "business logic",
        "authentication", "authorization", "fastapi", "flask", "django", "middleware",
        "route", "query", "repository", "schema", "postgres", "sqlite", "python",
    ],
    AgentRole.FRONTEND: [
        "frontend", "ui", "ux", "component", "view", "template", "html", "css",
        "javascript", "typescript", "react", "vue", "dashboard", "widget", "button",
        "styling", "layout", "form", "client", "render", "modal", "page", "state management",
    ],
    AgentRole.TESTING: [
        "test", "testing", "pytest", "unittest", "mock", "fixture", "assertion",
        "coverage", "edge case", "regression", "integration test", "unit test",
        "e2e", "scenario", "benchmark", "validation test", "fuzzing",
    ],
    AgentRole.SECURITY: [
        "security", "vulnerability", "auth", "crypto", "encryption", "sanitiz",
        "owasp", "xss", "injection", "csrf", "token", "secret", "permission",
        "sandbox", "ebpf", "fencing", "threat", "cve", "audit", "jwt",
    ],
    AgentRole.PERFORMANCE: [
        "performance", "optimizi", "profil", "cache", "caching", "redis", "latency",
        "throughput", "async", "concurrency", "thread", "pool", "bottleneck",
        "memory leak", "load", "scaling", "speed", "fast",
    ],
    AgentRole.DOCUMENTATION: [
        "document", "documentation", "readme", "api doc", "docstring", "guide",
        "manual", "tutorial", "changelog", "markdown", "specification", "rfc", "docs",
    ],
    AgentRole.RELEASE: [
        "release", "package", "packaging", "version", "versioning", "deploy",
        "deployment", "build", "dockerfile", "wheel", "setup.py", "pyproject.toml",
        "tag", "publish", "artifact", "dist",
    ],
}


@dataclass
class AgentCapacity:
    """Tracks active workload and task capacity for an agent."""
    agent_id: str
    role: AgentRole = AgentRole.GENERAL
    max_capacity_hours: float = 40.0
    current_workload_hours: float = 0.0
    assigned_task_ids: List[str] = field(default_factory=list)

    @property
    def allocated_hours(self) -> float:
        return self.current_workload_hours

    @allocated_hours.setter
    def allocated_hours(self, val: float):
        self.current_workload_hours = val

    @property
    def active_tasks(self) -> List[str]:
        return self.assigned_task_ids

    @property
    def utilization_pct(self) -> float:
        return min(100.0, (self.current_workload_hours / max(1.0, self.max_capacity_hours)) * 100.0)


class TaskAllocator:
    """
    Intelligent skill-affinity and workload-aware task assignment engine for specialized AI engineering agents.
    """

    def __init__(self, default_agents: Optional[List[Dict[str, Any]]] = None):
        self._lock = threading.RLock()
        self._capacities: Dict[str, AgentCapacity] = {}
        self._tasks: Dict[str, TaskAssignment] = {}
        self._completed_tasks: Set[str] = set()

        if default_agents:
            for ag in default_agents:
                self.register_agent_capacity(
                    agent_id=ag["agent_id"],
                    role=ag.get("role", AgentRole.GENERAL),
                    max_capacity_hours=ag.get("max_capacity_hours", 40.0),
                )
        else:
            self._register_default_organization_roster()

    def _register_default_organization_roster(self) -> None:
        """Registers a full default AI engineering team roster."""
        roster = [
            ("ArchitectureAgent", AgentRole.ARCHITECTURE),
            ("BackendAgent", AgentRole.BACKEND),
            ("FrontendAgent", AgentRole.FRONTEND),
            ("TestingAgent", AgentRole.TESTING),
            ("SecurityAgent", AgentRole.SECURITY),
            ("PerformanceAgent", AgentRole.PERFORMANCE),
            ("DocumentationAgent", AgentRole.DOCUMENTATION),
            ("ReleaseAgent", AgentRole.RELEASE),
        ]
        for aid, role in roster:
            self.register_agent_capacity(aid, role)

    def register_agent_capacity(
        self,
        agent_id: str,
        role: Union[AgentRole, str] = AgentRole.GENERAL,
        max_capacity_hours: float = 40.0,
    ) -> None:
        """Register or update capacity tracking for an agent."""
        if isinstance(role, str):
            try:
                role = AgentRole(role)
            except ValueError:
                role = AgentRole.GENERAL

        with self._lock:
            if agent_id not in self._capacities:
                self._capacities[agent_id] = AgentCapacity(
                    agent_id=agent_id,
                    role=role,
                    max_capacity_hours=max_capacity_hours,
                )
            else:
                self._capacities[agent_id].role = role
                self._capacities[agent_id].max_capacity_hours = max_capacity_hours

    # Alias for backwards compatibility
    register_agent = register_agent_capacity

    def get_capacity(self, agent_id: str) -> Optional[AgentCapacity]:
        with self._lock:
            return self._capacities.get(agent_id)

    def get_capacities(self) -> Dict[str, AgentCapacity]:
        with self._lock:
            return dict(self._capacities)

    def get_registered_agents(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "agent_id": cap.agent_id,
                    "role": cap.role,
                    "max_capacity_hours": cap.max_capacity_hours,
                    "allocated_hours": cap.current_workload_hours,
                    "active_tasks": list(cap.assigned_task_ids),
                }
                for cap in self._capacities.values()
            ]

    def get_agent_workload(self, agent_id: str) -> Dict[str, Any]:
        with self._lock:
            cap = self._capacities.get(agent_id)
            if not cap:
                return {"allocated_hours": 0.0, "utilization_pct": 0.0, "active_tasks": []}
            return {
                "allocated_hours": cap.current_workload_hours,
                "utilization_pct": cap.utilization_pct,
                "active_tasks": list(cap.assigned_task_ids),
            }

    # ------------------------------------------------------------------
    # Task Management
    # ------------------------------------------------------------------

    def submit_task(self, task: Union[TaskAssignment, Dict[str, Any]]) -> TaskAssignment:
        """Register a task into the allocator store."""
        t_obj = task if isinstance(task, TaskAssignment) else TaskAssignment(**task)
        with self._lock:
            self._tasks[t_obj.task_id] = t_obj
        return t_obj

    def submit_tasks(self, tasks: List[Union[TaskAssignment, Dict[str, Any]]]) -> List[TaskAssignment]:
        """Register multiple tasks."""
        return [self.submit_task(t) for t in tasks]

    def get_task(self, task_id: str) -> Optional[TaskAssignment]:
        with self._lock:
            return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[TaskAssignment]:
        with self._lock:
            return list(self._tasks.values())

    # ------------------------------------------------------------------
    # Scoring & Allocation
    # ------------------------------------------------------------------

    def _score_agent_for_task(self, capacity: Optional[AgentCapacity], task: TaskAssignment) -> float:
        """Compute matching affinity score for an agent capacity and task."""
        if not capacity:
            return 0.0

        title = task.title.lower()
        desc = task.description.lower()
        req_skills = [s.lower() for s in task.required_skills]
        files = [f.lower() for f in task.estimated_files]
        combined = f"{title} {desc} {' '.join(req_skills)} {' '.join(files)}"

        patterns = ROLE_SKILL_PATTERNS.get(capacity.role, [])
        matches = 0
        for pat in patterns:
            if pat in combined:
                matches += 2

        for skill in req_skills:
            if any(pat in skill or skill in pat for pat in patterns):
                matches += 5

        # Direct role name match
        role_name = capacity.role.value.lower()
        if role_name in title or any(role_name in s for s in req_skills):
            matches += 5

        # Workload penalty (0 to -0.3)
        workload_ratio = capacity.current_workload_hours / max(1.0, capacity.max_capacity_hours)
        base_score = matches / 2.0
        return max(0.01, base_score - (workload_ratio * 0.2))

    def match_skills(self, task: Union[TaskAssignment, Dict[str, Any]]) -> Tuple[AgentRole, float]:
        """Determine the optimal AgentRole for a task."""
        t_obj = task if isinstance(task, TaskAssignment) else TaskAssignment(**task)
        best_role = AgentRole.BACKEND
        best_score = -1.0

        for aid, cap in self._capacities.items():
            score = self._score_agent_for_task(cap, t_obj)
            if score > best_score:
                best_score = score
                best_role = cap.role

        return best_role, round(max(0.1, best_score), 2)

    def allocate_task(
        self,
        task_or_id: Union[str, TaskAssignment, Dict[str, Any]],
        preferred_agent_id: Optional[str] = None,
    ) -> Optional[TaskAssignment]:
        """Assign a task to the best-matching agent."""
        with self._lock:
            if isinstance(task_or_id, str):
                task = self._tasks.get(task_or_id)
                if not task:
                    task = TaskAssignment(task_id=task_or_id, title=task_or_id)
                    self._tasks[task_or_id] = task
            elif isinstance(task_or_id, TaskAssignment):
                task = task_or_id
                self._tasks[task.task_id] = task
            else:
                task = TaskAssignment(**task_or_id)
                self._tasks[task.task_id] = task

            chosen_agent_id = preferred_agent_id
            chosen_role = None

            if chosen_agent_id and chosen_agent_id in self._capacities:
                chosen_role = self._capacities[chosen_agent_id].role
            else:
                best_score = -1.0
                best_agent_id = "BackendAgent"
                for aid, cap in self._capacities.items():
                    score = self._score_agent_for_task(cap, task)
                    if score > best_score:
                        best_score = score
                        best_agent_id = aid

                chosen_agent_id = best_agent_id
                chosen_role = self._capacities[chosen_agent_id].role

            # Update assignment
            task.assigned_agent = chosen_agent_id
            task.assigned_role = chosen_role
            task.status = TaskStatus.ASSIGNED

            # Update capacity
            cap = self._capacities[chosen_agent_id]
            if task.task_id not in cap.assigned_task_ids:
                cap.assigned_task_ids.append(task.task_id)
                cap.current_workload_hours += task.estimated_hours

            logger.info("Allocated task '%s' -> %s (%s)", task.task_id, chosen_agent_id, chosen_role.value if chosen_role else "general")
            return task

    def allocate_all(self) -> List[TaskAssignment]:
        """Sort tasks by priority and allocate all pending tasks."""
        with self._lock:
            # Sort critical/high priority first
            sorted_tasks = sorted(
                self._tasks.values(),
                key=lambda t: int(t.priority) if hasattr(t.priority, "value") else 2,
                reverse=True,
            )
            allocations = []
            for t in sorted_tasks:
                if t.status in (TaskStatus.PENDING, TaskStatus.ASSIGNED):
                    allocations.append(self.allocate_task(t))
            return allocations

    def reassign_task(self, task_id: str, target_agent_id: str) -> bool:
        """Reassign an active task from one agent to another."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or target_agent_id not in self._capacities:
                return False

            old_agent = task.assigned_agent
            if old_agent and old_agent in self._capacities:
                old_cap = self._capacities[old_agent]
                if task_id in old_cap.assigned_task_ids:
                    old_cap.assigned_task_ids.remove(task_id)
                    old_cap.current_workload_hours = max(0.0, old_cap.current_workload_hours - task.estimated_hours)

            new_cap = self._capacities[target_agent_id]
            if task_id not in new_cap.assigned_task_ids:
                new_cap.assigned_task_ids.append(task_id)
                new_cap.current_workload_hours += task.estimated_hours

            task.assigned_agent = target_agent_id
            task.assigned_role = new_cap.role
            task.status = TaskStatus.REASSIGNED
            return True

    def complete_task(self, task_id: str) -> bool:
        """Mark task as completed and free allocated agent workload hours."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            task.status = TaskStatus.COMPLETED
            self._completed_tasks.add(task_id)

            agent_id = task.assigned_agent
            if agent_id and agent_id in self._capacities:
                cap = self._capacities[agent_id]
                if task_id in cap.assigned_task_ids:
                    cap.assigned_task_ids.remove(task_id)
                    cap.current_workload_hours = max(0.0, cap.current_workload_hours - task.estimated_hours)

            return True

    def get_allocation_stats(self) -> Dict[str, Any]:
        """Aggregate allocation statistics."""
        with self._lock:
            assigned = [t for t in self._tasks.values() if t.status in (TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS, TaskStatus.REASSIGNED)]
            completed = list(self._completed_tasks)
            agent_util = {aid: cap.utilization_pct for aid, cap in self._capacities.items()}

            return {
                "total_tasks": len(self._tasks),
                "assigned_tasks": len(assigned),
                "completed_tasks": len(completed),
                "agent_utilization": agent_util,
            }
