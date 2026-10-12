"""
cross_company_scheduler.py - Global Multi-Company Enterprise Scheduler (AutoDev Version 3.5)

Orchestrates cross-company dependencies and execution scheduling:
- Multi-company dependency DAG representation with cycle detection
- Critical Path Method (CPM) calculation: ES, EF, LS, LF, Float/Slack, and Critical Path
- Priority-weighted scheduling and company resource load balancing
- Deadline optimization and cross-company blocker/conflict detection
- 100% Python Standard Library.
"""

from __future__ import annotations

import collections
import enum
import logging
import threading
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("AutoDev.Federation.Scheduler")


@dataclass
class FederationTask:
    """A task spanning cross-company workflows."""
    task_id: str
    company_id: str
    title: str
    duration_hours: float
    priority: int = 3  # 1 (lowest) to 5 (highest)
    dependencies: List[str] = field(default_factory=list)  # task_ids this task depends on
    deadline_hours: Optional[float] = None
    status: str = "PENDING"  # PENDING, READY, IN_PROGRESS, COMPLETED, BLOCKED
    # CPM calculation attributes
    earliest_start: float = 0.0
    earliest_finish: float = 0.0
    latest_start: float = 0.0
    latest_finish: float = 0.0
    slack: float = 0.0
    is_critical: bool = False
    assigned_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CrossCompanyScheduler:
    """
    Global scheduler coordinating complex multi-company projects,
    identifying critical paths, and balancing cross-organization dependencies.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tasks: Dict[str, FederationTask] = {}
        # Adjacency: task_id -> list of successor task_ids
        self._successors: Dict[str, List[str]] = collections.defaultdict(list)

    def add_task(
        self,
        task_id: str,
        company_id: str,
        title: str,
        duration_hours: float,
        dependencies: Optional[List[str]] = None,
        priority: int = 3,
        deadline_hours: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FederationTask:
        """Registers a task in the cross-company scheduler."""
        with self._lock:
            task = FederationTask(
                task_id=task_id,
                company_id=company_id,
                title=title,
                duration_hours=max(0.1, float(duration_hours)),
                dependencies=list(dependencies or []),
                priority=max(1, min(5, int(priority))),
                deadline_hours=deadline_hours,
                metadata=metadata or {},
            )
            self._tasks[task_id] = task

            # Update successor graph
            for dep_id in task.dependencies:
                self._successors[dep_id].append(task_id)

            return task

    def detect_cycles(self) -> Tuple[bool, List[str]]:
        """
        Detects if circular dependencies exist in the cross-company task graph using DFS.
        Returns (has_cycle, cycle_path).
        """
        with self._lock:
            visited = {}  # 0: unvisited, 1: visiting, 2: visited
            parent = {}

            for tid in self._tasks:
                visited[tid] = 0

            cycle_nodes = []

            def dfs(node: str) -> bool:
                visited[node] = 1
                for succ in self._successors.get(node, []):
                    if succ not in visited:
                        continue
                    if visited[succ] == 1:
                        # Cycle found!
                        cycle_nodes.append(succ)
                        cycle_nodes.append(node)
                        return True
                    if visited[succ] == 0:
                        parent[succ] = node
                        if dfs(succ):
                            return True
                visited[node] = 2
                return False

            for tid in self._tasks:
                if visited[tid] == 0:
                    if dfs(tid):
                        return True, cycle_nodes

            return False, []

    def compute_critical_path(self) -> Dict[str, Any]:
        """
        Executes the Critical Path Method (CPM):
        1. Forward pass: computes Earliest Start (ES) and Earliest Finish (EF).
        2. Backward pass: computes Latest Finish (LF) and Latest Start (LS).
        3. Identifies Slack (Float) = LS - ES. Tasks with Slack == 0 are Critical.
        """
        with self._lock:
            has_cycle, cycle = self.detect_cycles()
            if has_cycle:
                raise ValueError(f"Cannot compute CPM on cyclic graph: {cycle}")

            # Topological Sort (Kahn's algorithm)
            in_degree = {tid: len([d for d in t.dependencies if d in self._tasks]) for tid, t in self._tasks.items()}
            queue = collections.deque([tid for tid, deg in in_degree.items() if deg == 0])
            topo_order = []

            while queue:
                curr = queue.popleft()
                topo_order.append(curr)
                for succ in self._successors.get(curr, []):
                    if succ in in_degree:
                        in_degree[succ] -= 1
                        if in_degree[succ] == 0:
                            queue.append(succ)

            # 1. Forward Pass
            for tid in topo_order:
                task = self._tasks[tid]
                if not task.dependencies:
                    task.earliest_start = 0.0
                else:
                    task.earliest_start = max(
                        (self._tasks[dep].earliest_finish for dep in task.dependencies if dep in self._tasks),
                        default=0.0,
                    )
                task.earliest_finish = task.earliest_start + task.duration_hours

            max_project_duration = max((t.earliest_finish for t in self._tasks.values()), default=0.0)

            # 2. Backward Pass
            # Reverse topological order
            for tid in reversed(topo_order):
                task = self._tasks[tid]
                succs = self._successors.get(tid, [])
                if not succs:
                    # End node
                    task.latest_finish = task.deadline_hours if task.deadline_hours is not None else max_project_duration
                else:
                    task.latest_finish = min(
                        (self._tasks[s].latest_start for s in succs if s in self._tasks),
                        default=max_project_duration,
                    )
                task.latest_start = task.latest_finish - task.duration_hours
                task.slack = round(task.latest_start - task.earliest_start, 2)
                task.is_critical = abs(task.slack) <= 0.001

            critical_path_tasks = [t.task_id for t in self._tasks.values() if t.is_critical]

            return {
                "total_project_duration_hours": max_project_duration,
                "critical_path_tasks": critical_path_tasks,
                "critical_path_count": len(critical_path_tasks),
                "total_tasks_scheduled": len(self._tasks),
            }

    def get_ready_tasks(self) -> List[FederationTask]:
        """
        Returns all tasks whose dependencies are 100% completed,
        sorted by priority descending, then is_critical (critical path first).
        """
        with self._lock:
            ready = []
            for t in self._tasks.values():
                if t.status in ("PENDING", "READY"):
                    deps_satisfied = all(
                        self._tasks[d].status == "COMPLETED"
                        for d in t.dependencies
                        if d in self._tasks
                    )
                    if deps_satisfied:
                        t.status = "READY"
                        ready.append(t)

            # Sort: Priority descending, then is_critical (True before False), then duration ascending
            ready.sort(key=lambda t: (-t.priority, -int(t.is_critical), t.duration_hours))
            return ready

    def complete_task(self, task_id: str) -> bool:
        """Marks a task as completed."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.status = "COMPLETED"
            return True

    def detect_conflicts_and_bottlenecks(self, company_capacity_hours: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Identifies resource allocation bottlenecks where scheduled tasks
        exceed a company's available capacity.
        """
        with self._lock:
            bottlenecks = []
            company_demand: Dict[str, float] = collections.defaultdict(float)

            for t in self._tasks.values():
                if t.status in ("READY", "IN_PROGRESS", "PENDING"):
                    company_demand[t.company_id] += t.duration_hours

            for company_id, demand in company_demand.items():
                cap = company_capacity_hours.get(company_id, 40.0)
                if demand > cap:
                    bottlenecks.append({
                        "company_id": company_id,
                        "required_hours": demand,
                        "available_capacity_hours": cap,
                        "overage_hours": demand - cap,
                        "severity": "CRITICAL" if (demand / max(1.0, cap)) > 1.5 else "WARNING",
                    })

            return bottlenecks
