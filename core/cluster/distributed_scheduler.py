"""
distributed_scheduler.py - Distributed Task Scheduler & Rebalancer for AutoDev Cluster (v2.9)

Implements multi-strategy distributed scheduling (Round-Robin, Least-Loaded, Capability-Based,
Priority-Aware, Data-Locality, Dependency-Aware DAG execution), continuous rebalancing,
and dynamic work-stealing across heterogeneous cluster workers.
"""

from __future__ import annotations

import collections
import copy
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import NodeInfo, NodeRole, NodeStatus, TaskExecutionStatus, TaskSpec
from core.cluster.node_registry import NodeRegistry

logger = logging.getLogger("AutoDev.Cluster.Scheduler")


class DistributedScheduler:
    """
    Intelligent distributed scheduler for cluster task allocation and rebalancing.
    """

    def __init__(self, registry: NodeRegistry, config: Optional[ClusterConfig] = None) -> None:
        self.registry = registry
        self.config = config or ClusterConfig()
        self._lock = threading.RLock()
        self._rr_index: int = 0
        self._task_assignments: Dict[str, str] = {}  # task_id -> worker_id
        self._worker_active_counts: Dict[str, int] = collections.defaultdict(int)

        # Telemetry metrics
        self._total_scheduled = 0
        self._total_rebalanced = 0
        self._strategy_distribution: Dict[str, int] = collections.defaultdict(int)

    def select_worker(
        self,
        task: TaskSpec,
        strategy: Optional[str] = None,
        cached_node_artifacts: Optional[Dict[str, Set[str]]] = None,
    ) -> Optional[str]:
        """
        Selects the optimal worker ID for a task according to the selected strategy.
        """
        strat = (strategy or self.config.scheduler_strategy).lower()
        self._strategy_distribution[strat] += 1

        with self._lock:
            # 1. Candidate selection: must be worker, healthy/degraded, and have capacity
            candidates = self._get_eligible_candidates(task)
            if not candidates:
                logger.debug("No eligible workers available for task %s (caps: %s)", task.task_id, task.required_capabilities)
                return None

            if strat == "round_robin":
                return self._schedule_round_robin(candidates)
            elif strat == "least_loaded":
                return self._schedule_least_loaded(candidates)
            elif strat == "capability_based":
                return self._schedule_capability_based(candidates, task)
            elif strat == "priority_aware":
                return self._schedule_priority_aware(candidates, task)
            elif strat == "data_locality":
                return self._schedule_data_locality(candidates, task, cached_node_artifacts)
            elif strat == "dependency_aware":
                return self._schedule_least_loaded(candidates)
            else:
                return self._schedule_least_loaded(candidates)

    def _get_eligible_candidates(self, task: TaskSpec) -> List[NodeInfo]:
        all_workers = [
            n for n in self.registry.get_all_nodes()
            if n.role == NodeRole.WORKER
            and n.status in (NodeStatus.HEALTHY, NodeStatus.DEGRADED)
        ]

        eligible: List[NodeInfo] = []
        for w in all_workers:
            # Capacity check
            active = self._worker_active_counts[w.node_id]
            if active >= w.max_tasks:
                continue

            # Capability check
            if task.required_capabilities:
                w_caps = set(w.capabilities)
                if "general" not in w_caps and not all(c in w_caps for c in task.required_capabilities):
                    continue

            eligible.append(w)
        return eligible

    def _schedule_round_robin(self, candidates: List[NodeInfo]) -> str:
        idx = self._rr_index % len(candidates)
        self._rr_index += 1
        return candidates[idx].node_id

    def _schedule_least_loaded(self, candidates: List[NodeInfo]) -> str:
        # Sort by: (current active / max_tasks, cpu_utilization, -health_score)
        def load_score(n: NodeInfo) -> Tuple[float, float, float]:
            active = self._worker_active_counts[n.node_id]
            ratio = (active / n.max_tasks) if n.max_tasks > 0 else 1.0
            return (ratio, n.cpu_utilization, -n.health_score)

        sorted_cands = sorted(candidates, key=load_score)
        return sorted_cands[0].node_id

    def _schedule_capability_based(self, candidates: List[NodeInfo], task: TaskSpec) -> str:
        # Prioritize worker with exact matching capability count and lowest load
        def cap_score(n: NodeInfo) -> Tuple[int, float]:
            exact_matches = len(set(task.required_capabilities).intersection(set(n.capabilities)))
            active = self._worker_active_counts[n.node_id]
            return (-exact_matches, active)

        sorted_cands = sorted(candidates, key=cap_score)
        return sorted_cands[0].node_id

    def _schedule_priority_aware(self, candidates: List[NodeInfo], task: TaskSpec) -> str:
        # High priority tasks (lower task.priority number) routed to lowest CPU and highest health score
        def prio_cand_score(n: NodeInfo) -> Tuple[float, float]:
            active = self._worker_active_counts[n.node_id]
            return (n.cpu_utilization + (active * 10.0), -n.health_score)

        sorted_cands = sorted(candidates, key=prio_cand_score)
        return sorted_cands[0].node_id

    def _schedule_data_locality(
        self,
        candidates: List[NodeInfo],
        task: TaskSpec,
        cached_node_artifacts: Optional[Dict[str, Set[str]]] = None,
    ) -> str:
        locality_hints = set(task.locality_hints)
        if not locality_hints or not cached_node_artifacts:
            return self._schedule_least_loaded(candidates)

        # Worker with most locality hints cached
        def locality_score(n: NodeInfo) -> Tuple[int, float]:
            node_cached = cached_node_artifacts.get(n.node_id, set())
            overlap = len(locality_hints.intersection(node_cached))
            active = self._worker_active_counts[n.node_id]
            return (-overlap, active)

        sorted_cands = sorted(candidates, key=locality_score)
        return sorted_cands[0].node_id

    def assign_task(self, task: TaskSpec, worker_id: str) -> None:
        """Records task allocation in scheduler tracking."""
        with self._lock:
            self._task_assignments[task.task_id] = worker_id
            self._worker_active_counts[worker_id] += 1
            self._total_scheduled += 1
            task.assigned_worker_id = worker_id
            task.status = TaskExecutionStatus.SCHEDULED
            logger.debug("Scheduler assigned task %s to worker %s", task.task_id, worker_id)

    def release_task(self, task_id: str) -> None:
        """Frees worker capacity when task completes or fails."""
        with self._lock:
            worker_id = self._task_assignments.pop(task_id, None)
            if worker_id and self._worker_active_counts[worker_id] > 0:
                self._worker_active_counts[worker_id] -= 1

    def build_dependency_dag(self, tasks: List[TaskSpec]) -> Tuple[Dict[str, Set[str]], List[List[str]]]:
        """
        Builds DAG adjacency representation and Kahn's topological parallel execution waves.
        Raises ValueError if circular dependency is detected.
        """
        task_map = {t.task_id: t for t in tasks}
        in_degree: Dict[str, int] = {t.task_id: 0 for t in tasks}
        adj_graph: Dict[str, Set[str]] = {t.task_id: set() for t in tasks}

        for t in tasks:
            for dep in t.dependencies:
                if dep in task_map:
                    adj_graph[dep].add(t.task_id)
                    in_degree[t.task_id] += 1

        waves: List[List[str]] = []
        current_wave = [t_id for t_id, deg in in_degree.items() if deg == 0]

        visited_count = 0
        while current_wave:
            waves.append(sorted(current_wave))
            next_wave: List[str] = []
            for node in current_wave:
                visited_count += 1
                for neighbor in adj_graph[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_wave.append(neighbor)
            current_wave = next_wave

        if visited_count < len(tasks):
            raise ValueError("Cycle detected in task dependencies; cannot form topological DAG")

        return adj_graph, waves

    def rebalance_cluster(self, queued_tasks: Dict[str, TaskSpec]) -> List[Tuple[str, str, str]]:
        """
        Continuous work-stealing and load rebalancing.
        If utilization variance across workers exceeds threshold, migrates tasks from overloaded to underutilized workers.
        Returns list of (task_id, source_worker, target_worker).
        """
        if not self.config.enable_work_stealing:
            return []

        with self._lock:
            workers = [
                n for n in self.registry.get_all_nodes()
                if n.role == NodeRole.WORKER and n.status == NodeStatus.HEALTHY
            ]
            if len(workers) < 2:
                return []

            # Compute load for each worker
            worker_loads: Dict[str, int] = {w.node_id: self._worker_active_counts[w.node_id] for w in workers}
            min_worker = min(workers, key=lambda w: worker_loads[w.node_id])
            max_worker = max(workers, key=lambda w: worker_loads[w.node_id])

            min_load = worker_loads[min_worker.node_id]
            max_load = worker_loads[max_worker.node_id]

            reassignments: List[Tuple[str, str, str]] = []

            if max_load >= 2 and (min_load == 0 or (max_load / max(1, min_load)) >= self.config.work_stealing_threshold_ratio):
                # Find queued tasks currently scheduled to max_worker
                for t_id, task in queued_tasks.items():
                    if task.status == TaskExecutionStatus.SCHEDULED and self._task_assignments.get(t_id) == max_worker.node_id:
                        # Check if min_worker satisfies task capabilities
                        if not task.required_capabilities or set(task.required_capabilities).issubset(set(min_worker.capabilities)) or "general" in min_worker.capabilities:
                            # Migrate task
                            self._task_assignments[t_id] = min_worker.node_id
                            self._worker_active_counts[max_worker.node_id] -= 1
                            self._worker_active_counts[min_worker.node_id] += 1
                            task.assigned_worker_id = min_worker.node_id
                            reassignments.append((t_id, max_worker.node_id, min_worker.node_id))
                            self._total_rebalanced += 1
                            logger.info("Work-stealing rebalanced task %s: %s -> %s", t_id, max_worker.node_id, min_worker.node_id)
                            break

            return reassignments

    def get_scheduler_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_scheduled": self._total_scheduled,
                "total_rebalanced": self._total_rebalanced,
                "strategy_distribution": dict(self._strategy_distribution),
                "worker_active_counts": dict(self._worker_active_counts),
            }
