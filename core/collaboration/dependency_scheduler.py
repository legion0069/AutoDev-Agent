"""
AutoDev Dependency Scheduler (v2.8)
===================================
DAG-based dependency resolution, parallel execution batching, critical path calculation,
and topological concurrency optimization for multi-agent workflows.
"""

from __future__ import annotations

import collections
import logging
import threading
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from core.collaboration.collaboration_models import TaskAssignment, TaskStatus

logger = logging.getLogger("AutoDev.DependencyScheduler")


class CyclicDependencyError(Exception):
    """Raised when a circular dependency is detected in the task graph."""
    pass


class DependencyScheduler:
    """
    Constructs and evaluates Directed Acyclic Graphs (DAGs) of tasks to maximize parallel execution.
    Calculates execution batches, identifies critical paths, and tracks readiness barriers.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._tasks: Dict[str, TaskAssignment] = {}
        self._completed_task_ids: Set[str] = set()

    # ------------------------------------------------------------------
    # Task Registration
    # ------------------------------------------------------------------

    def add_task(self, task: Union[TaskAssignment, Dict[str, Any]]) -> TaskAssignment:
        """Register a task for DAG dependency tracking."""
        t_obj = task if isinstance(task, TaskAssignment) else TaskAssignment(**task)
        with self._lock:
            self._tasks[t_obj.task_id] = t_obj
        return t_obj

    def add_tasks(self, tasks: List[Union[TaskAssignment, Dict[str, Any]]]) -> List[TaskAssignment]:
        """Register multiple tasks."""
        return [self.add_task(t) for t in tasks]

    def get_task(self, task_id: str) -> Optional[TaskAssignment]:
        with self._lock:
            return self._tasks.get(task_id)

    def get_all_tasks(self) -> Dict[str, TaskAssignment]:
        with self._lock:
            return dict(self._tasks)

    def mark_completed(self, task_id: str) -> None:
        """Mark a task as completed to unblock downstream dependent tasks."""
        with self._lock:
            self._completed_task_ids.add(task_id)
            if task_id in self._tasks:
                self._tasks[task_id].status = TaskStatus.COMPLETED

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()
            self._completed_task_ids.clear()

    # ------------------------------------------------------------------
    # Filtering & Readiness
    # ------------------------------------------------------------------

    def get_ready_tasks(self) -> List[TaskAssignment]:
        """Returns all uncompleted tasks whose dependencies are fully satisfied."""
        with self._lock:
            ready = []
            for tid, t in self._tasks.items():
                if tid not in self._completed_task_ids and t.status != TaskStatus.COMPLETED:
                    if all(dep in self._completed_task_ids for dep in t.dependencies):
                        ready.append(t)
            return ready

    def get_blocked_tasks(self) -> List[TaskAssignment]:
        """Returns all uncompleted tasks waiting on at least one incomplete dependency."""
        with self._lock:
            blocked = []
            for tid, t in self._tasks.items():
                if tid not in self._completed_task_ids and t.status != TaskStatus.COMPLETED:
                    if any(dep not in self._completed_task_ids for dep in t.dependencies):
                        blocked.append(t)
            return blocked

    # ------------------------------------------------------------------
    # DAG Construction & Analysis
    # ------------------------------------------------------------------

    def _normalize_tasks(
        self,
        tasks: Optional[List[Union[Any, Dict[str, Any]]]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Extracts normalized dictionary representation of tasks keyed by task ID."""
        task_list = tasks if tasks is not None else list(self._tasks.values())
        task_map = {}
        for t in task_list:
            t_dict = t.to_dict() if hasattr(t, "to_dict") else dict(t)
            tid = str(t_dict.get("id", t_dict.get("task_id", "task_0")))
            task_map[tid] = {
                "id": tid,
                "title": t_dict.get("title", ""),
                "dependencies": list(t_dict.get("dependencies", [])),
                "estimated_hours": float(t_dict.get("estimated_hours", 1.0)),
                "priority": int(t_dict.get("priority", 1)) if isinstance(t_dict.get("priority"), (int, float)) else 2,
                "status": t_dict.get("status", "pending"),
            }
        return task_map

    def build_graph(
        self,
        tasks: Optional[List[Union[Any, Dict[str, Any]]]] = None,
    ) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
        """
        Constructs forward dependency graph (task -> dependencies) and reverse graph (dependency -> dependents).
        Returns: (adj_in, adj_out)
        """
        task_map = self._normalize_tasks(tasks)
        adj_in: Dict[str, Set[str]] = {tid: set() for tid in task_map}
        adj_out: Dict[str, Set[str]] = {tid: set() for tid in task_map}

        for tid, tinfo in task_map.items():
            for dep in tinfo["dependencies"]:
                if dep in task_map:
                    adj_in[tid].add(dep)
                    adj_out[dep].add(tid)

        return adj_in, adj_out

    def detect_cycles(self, tasks: Optional[List[Union[Any, Dict[str, Any]]]] = None) -> List[List[str]]:
        """Checks for cycles in the task DAG using Tarjan's strongly connected components algorithm."""
        adj_in, adj_out = self.build_graph(tasks)
        nodes = list(adj_out.keys())
        index = 0
        indices: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        stack: List[str] = []
        on_stack: Set[str] = set()
        sccs: List[List[str]] = []

        def strongconnect(node: str):
            nonlocal index
            indices[node] = index
            lowlinks[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)

            for neighbor in adj_out.get(node, set()):
                if neighbor not in indices:
                    strongconnect(neighbor)
                    lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
                elif neighbor in on_stack:
                    lowlinks[node] = min(lowlinks[node], indices[neighbor])

            if lowlinks[node] == indices[node]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == node:
                        break
                if len(scc) > 1:
                    sccs.append(scc)

        for n in nodes:
            if n not in indices:
                strongconnect(n)

        return sccs

    def get_parallel_batches(
        self,
        tasks: Optional[List[Union[Any, Dict[str, Any]]]] = None,
    ) -> List[List[str]]:
        """
        Calculates topological parallel execution batches using Kahn's algorithm.
        All tasks within a batch can be safely executed concurrently by different agents.
        """
        task_map = self._normalize_tasks(tasks)
        if not task_map:
            return []

        # in-degree: number of unresolved incoming dependencies
        in_degree: Dict[str, int] = {}
        adj_out: Dict[str, Set[str]] = collections.defaultdict(set)

        for tid, tinfo in task_map.items():
            valid_deps = [dep for dep in tinfo["dependencies"] if dep in task_map]
            in_degree[tid] = len(valid_deps)
            for dep in valid_deps:
                adj_out[dep].add(tid)

        batches: List[List[str]] = []
        # Current ready queue (in-degree == 0)
        current_batch = [tid for tid, deg in in_degree.items() if deg == 0]

        visited_count = 0
        while current_batch:
            batches.append(sorted(current_batch))
            visited_count += len(current_batch)
            next_batch = []

            for tid in current_batch:
                for dependent in adj_out[tid]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_batch.append(dependent)

            current_batch = next_batch

        # Handle remaining tasks if there was a cycle
        if visited_count < len(task_map):
            remaining = [tid for tid, deg in in_degree.items() if deg > 0]
            if remaining:
                batches.append(remaining)

        return batches

    def get_critical_path(
        self,
        tasks: Optional[List[Union[Any, Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        Calculates the longest path through the DAG (critical path) based on task estimated hours.
        Returns: {'critical_path': List[str], 'total_hours': float}
        """
        task_map = self._normalize_tasks(tasks)
        if not task_map:
            return {"critical_path": [], "total_hours": 0.0}

        batches = self.get_parallel_batches(tasks)
        earliest_finish: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {tid: None for tid in task_map}

        for batch in batches:
            for tid in batch:
                tinfo = task_map[tid]
                hours = tinfo["estimated_hours"]
                valid_deps = [dep for dep in tinfo["dependencies"] if dep in earliest_finish]

                if not valid_deps:
                    earliest_finish[tid] = hours
                else:
                    max_dep = max(valid_deps, key=lambda d: earliest_finish[d])
                    earliest_finish[tid] = earliest_finish[max_dep] + hours
                    predecessor[tid] = max_dep

        # Find terminal task with the maximum cumulative duration
        if not earliest_finish:
            return {"critical_path": [], "total_hours": 0.0}

        end_node = max(earliest_finish, key=lambda k: earliest_finish[k])
        max_duration = earliest_finish[end_node]

        # Reconstruct path backwards
        cpath = []
        curr: Optional[str] = end_node
        while curr is not None:
            cpath.append(curr)
            curr = predecessor.get(curr)

        cpath.reverse()
        return {
            "critical_path": cpath,
            "total_hours": round(max_duration, 2),
        }
