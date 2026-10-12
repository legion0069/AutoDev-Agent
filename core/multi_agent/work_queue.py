"""
AutoDev Multi-Agent Work Queue Subsystem.

Provides thread-safe priority work queue with dependency tracking, lease management,
and critical path computation using only Python standard library.
"""

from __future__ import annotations

import heapq
import itertools
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from core.multi_agent.agent_registry import AgentRole


class WorkItemStatus(str, Enum):
    """Lifecycle status of a WorkItem."""
    PENDING = "pending"
    READY = "ready"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class TaskPriority(int, Enum):
    """Standardized task priority values (higher values mean higher priority)."""
    LOW = 10
    NORMAL = 50
    HIGH = 80
    CRITICAL = 100


@dataclass
class WorkItem:
    """Represents an engineering task in the multi-agent organization."""
    task_id: str
    title: str
    description: str = ""
    required_role: Optional[AgentRole] = None
    required_capabilities: List[str] = field(default_factory=list)
    priority: int = TaskPriority.NORMAL
    estimated_duration: float = 1.0  # seconds or abstract work units
    dependencies: Set[str] = field(default_factory=set)
    status: WorkItemStatus = WorkItemStatus.PENDING
    assigned_agent_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    result: Any = None
    error: Optional[str] = None
    resources_required: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    lease_expiration: Optional[float] = None

    def is_ready(self, completed_tasks: Set[str]) -> bool:
        """Determines if all prerequisites have completed successfully."""
        return self.dependencies.issubset(completed_tasks) and self.status in (
            WorkItemStatus.PENDING,
            WorkItemStatus.READY,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the work item to a JSON-compatible dictionary."""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "required_role": self.required_role.value if self.required_role else None,
            "required_capabilities": list(self.required_capabilities),
            "priority": self.priority,
            "estimated_duration": self.estimated_duration,
            "dependencies": sorted(list(self.dependencies)),
            "status": self.status.value,
            "assigned_agent_id": self.assigned_agent_id,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "result": self.result,
            "error": self.error,
            "resources_required": list(self.resources_required),
            "metadata": dict(self.metadata),
            "lease_expiration": self.lease_expiration,
        }


class WorkQueue:
    """
    Thread-safe work queue with priority dispatch, dependency resolution,
    lease timeouts, and topological critical-path determination.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tasks: Dict[str, WorkItem] = {}
        self._completed_task_ids: Set[str] = set()
        self._failed_task_ids: Set[str] = set()
        self._counter = itertools.count()  # Tie breaker for deterministic heapq

    def enqueue(self, task: WorkItem) -> str:
        """Enqueues a new work item into the organization queue."""
        with self._lock:
            if task.task_id in self._tasks:
                existing = self._tasks[task.task_id]
                if existing.status in (WorkItemStatus.COMPLETED, WorkItemStatus.FAILED):
                    self._completed_task_ids.discard(task.task_id)
                    self._failed_task_ids.discard(task.task_id)
                else:
                    raise ValueError(f"Task with ID '{task.task_id}' already exists in work queue.")
            
            # Check if initially ready
            if task.is_ready(self._completed_task_ids):
                task.status = WorkItemStatus.READY
            else:
                task.status = WorkItemStatus.PENDING

            self._tasks[task.task_id] = task
            return task.task_id

    def get_task(self, task_id: str) -> Optional[WorkItem]:
        """Retrieves a work item by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[WorkItem]:
        """Returns all work items sorted deterministically by task_id."""
        with self._lock:
            return sorted(list(self._tasks.values()), key=lambda t: t.task_id)

    def get_ready_tasks(self) -> List[WorkItem]:
        """
        Returns all tasks whose dependencies are satisfied and are ready for assignment.
        Sorted deterministically by (-priority, created_at, task_id).
        """
        with self._lock:
            ready: List[WorkItem] = []
            for task in self._tasks.values():
                if task.status in (WorkItemStatus.PENDING, WorkItemStatus.READY):
                    if task.dependencies.issubset(self._completed_task_ids):
                        task.status = WorkItemStatus.READY
                        ready.append(task)
                    else:
                        task.status = WorkItemStatus.PENDING

            ready.sort(key=lambda t: (-t.priority, t.created_at, t.task_id))
            return ready

    def mark_in_progress(
        self,
        task_id: str,
        agent_id: str,
        lease_duration: float = 60.0
    ) -> bool:
        """Marks a task as actively running under a specific agent with an expiration lease."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.status = WorkItemStatus.IN_PROGRESS
            task.assigned_agent_id = agent_id
            task.started_at = time.time()
            task.lease_expiration = task.started_at + lease_duration
            return True

    def mark_completed(self, task_id: str, result: Any = None) -> bool:
        """Marks a task as completed and updates dependent readiness."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.status = WorkItemStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()
            task.lease_expiration = None
            self._completed_task_ids.add(task_id)
            return True

    def mark_failed(self, task_id: str, error: str = "", allow_retry: bool = True) -> bool:
        """Marks a task as failed, triggering automatic retries if within quota."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.error = error
            task.lease_expiration = None
            
            if allow_retry and task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = WorkItemStatus.READY
                task.assigned_agent_id = None
            else:
                task.status = WorkItemStatus.FAILED
                self._failed_task_ids.add(task_id)
            return True

    def renew_lease(self, task_id: str, lease_duration: float = 60.0) -> bool:
        """Renews an active task execution lease."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status != WorkItemStatus.IN_PROGRESS:
                return False
            task.lease_expiration = time.time() + lease_duration
            return True

    def reclaim_expired_leases(self, now: Optional[float] = None) -> List[str]:
        """
        Identifies and reclaims tasks whose leases have expired, resetting them to READY.
        """
        with self._lock:
            current_time = now if now is not None else time.time()
            reclaimed: List[str] = []
            for task in self._tasks.values():
                if (
                    task.status == WorkItemStatus.IN_PROGRESS
                    and task.lease_expiration is not None
                    and task.lease_expiration < current_time
                ):
                    task.status = WorkItemStatus.READY
                    task.assigned_agent_id = None
                    task.lease_expiration = None
                    reclaimed.append(task.task_id)
            return reclaimed

    def get_critical_path(self) -> List[str]:
        """
        Computes the critical path (longest dependency chain by duration) through the task graph.
        Returns ordered task_ids along the critical path.
        """
        with self._lock:
            if not self._tasks:
                return []

            # Build in-degree and adjacency
            adj: Dict[str, List[str]] = {t_id: [] for t_id in self._tasks}
            in_degree: Dict[str, int] = {t_id: 0 for t_id in self._tasks}

            for t_id, task in self._tasks.items():
                for dep in task.dependencies:
                    if dep in adj:
                        adj[dep].append(t_id)
                        in_degree[t_id] += 1

            # Topological sort via Kahn's algorithm
            zero_in: List[str] = [t for t, deg in in_degree.items() if deg == 0]
            zero_in.sort()
            topo_order: List[str] = []

            q = list(zero_in)
            while q:
                curr = q.pop(0)
                topo_order.append(curr)
                for nxt in sorted(adj[curr]):
                    in_degree[nxt] -= 1
                    if in_degree[nxt] == 0:
                        q.append(nxt)

            # Earliest completion times and predecessors
            dist: Dict[str, float] = {t: self._tasks[t].estimated_duration for t in self._tasks}
            pred: Dict[str, Optional[str]] = {t: None for t in self._tasks}

            for u in topo_order:
                for v in adj[u]:
                    new_dist = dist[u] + self._tasks[v].estimated_duration
                    if new_dist > dist[v]:
                        dist[v] = new_dist
                        pred[v] = u

            if not dist:
                return []

            # Find endpoint with maximum cumulative duration
            end_task = max(dist.keys(), key=lambda k: (dist[k], k))
            
            # Reconstruct path
            path: List[str] = []
            curr: Optional[str] = end_task
            while curr is not None:
                path.append(curr)
                curr = pred[curr]
            path.reverse()
            return path

    def is_finished(self) -> bool:
        """Returns True if every queued task has completed or irrevocably failed."""
        with self._lock:
            return all(
                t.status in (WorkItemStatus.COMPLETED, WorkItemStatus.FAILED)
                for t in self._tasks.values()
            )

    def size(self) -> int:
        """Returns total number of tasks in the queue."""
        with self._lock:
            return len(self._tasks)

    def pending_count(self) -> int:
        """Returns count of tasks that are still PENDING or READY."""
        with self._lock:
            return sum(
                1 for t in self._tasks.values()
                if t.status in (WorkItemStatus.PENDING, WorkItemStatus.READY)
            )

    def in_progress_count(self) -> int:
        """Returns count of actively executing tasks."""
        with self._lock:
            return sum(1 for t in self._tasks.values() if t.status == WorkItemStatus.IN_PROGRESS)

    def completed_count(self) -> int:
        """Returns count of completed tasks."""
        with self._lock:
            return len(self._completed_task_ids)

    def failed_count(self) -> int:
        """Returns count of failed tasks."""
        with self._lock:
            return len(self._failed_task_ids)
