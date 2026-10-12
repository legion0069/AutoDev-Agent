"""
AutoDev Workload Balancer (v2.8)
===============================
Real-time utilization monitoring, queue variance tracking, and dynamic task rebalancing across AI agents.
"""

from __future__ import annotations

import logging
import statistics
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from core.collaboration.collaboration_models import AgentRole, TaskAssignment
from core.collaboration.task_allocator import TaskAllocator

logger = logging.getLogger("AutoDev.WorkloadBalancer")


class WorkloadBalancer:
    """
    Monitors agent capacity, logical CPU utilization, and task queues.
    Triggers dynamic work-stealing and task rebalancing when workload imbalance exceeds thresholds.
    """

    def __init__(
        self,
        allocator: Optional[TaskAllocator] = None,
        imbalance_threshold: float = 0.35,  # 35% disparity triggers rebalance
        min_task_rebalance_threshold: int = 1,
    ):
        self.allocator = allocator
        self.imbalance_threshold = imbalance_threshold
        self.min_task_rebalance_threshold = min_task_rebalance_threshold
        self._balancing_history: List[Dict[str, Any]] = []

    def compute_metrics(
        self,
        allocator: Optional[TaskAllocator] = None,
    ) -> Dict[str, Any]:
        """
        Computes system-wide workload statistics across all registered agents.
        """
        alloc = allocator or self.allocator
        if not alloc:
            return {
                "agent_count": 0,
                "total_hours": 0.0,
                "total_workload_hours": 0.0,
                "max_workload_hours": 0.0,
                "avg_utilization_pct": 0.0,
                "max_utilization_pct": 0.0,
                "min_utilization_pct": 0.0,
                "imbalance_score": 0.0,
                "agent_metrics": {},
            }

        capacities = alloc.get_capacities()
        if not capacities:
            return {
                "agent_count": 0,
                "total_hours": 0.0,
                "total_workload_hours": 0.0,
                "max_workload_hours": 0.0,
                "avg_utilization_pct": 0.0,
                "max_utilization_pct": 0.0,
                "min_utilization_pct": 0.0,
                "imbalance_score": 0.0,
                "agent_metrics": {},
            }

        agent_metrics: Dict[str, Dict[str, Any]] = {}
        utilizations: List[float] = []
        workload_hours: List[float] = []

        for aid, cap in capacities.items():
            wl = {
                "allocated_hours": cap.current_workload_hours,
                "utilization_pct": cap.utilization_pct,
                "active_tasks": list(cap.assigned_task_ids),
            }
            agent_metrics[aid] = wl
            utilizations.append(cap.utilization_pct)
            workload_hours.append(cap.current_workload_hours)

        total_hours = sum(workload_hours)
        max_hours = max(workload_hours) if workload_hours else 0.0
        avg_util = statistics.mean(utilizations) if utilizations else 0.0
        max_util = max(utilizations) if utilizations else 0.0
        min_util = min(utilizations) if utilizations else 0.0
        stdev_util = statistics.stdev(utilizations) if len(utilizations) > 1 else 0.0

        # Normalized disparity
        imbalance_score = round((max_util - min_util) / 100.0, 3)

        return {
            "agent_count": len(capacities),
            "total_hours": round(total_hours, 2),
            "total_workload_hours": round(total_hours, 2),
            "max_workload_hours": round(max_hours, 2),
            "avg_utilization_pct": round(avg_util, 1),
            "max_utilization_pct": round(max_util, 1),
            "min_utilization_pct": round(min_util, 1),
            "stdev_utilization": round(stdev_util, 2),
            "imbalance_score": imbalance_score,
            "agent_metrics": agent_metrics,
        }

    # Alias for test suite
    compute_workload_metrics = compute_metrics

    def detect_imbalance(self, allocator: Optional[TaskAllocator] = None) -> bool:
        """Determines whether workload disparity exceeds threshold."""
        metrics = self.compute_metrics(allocator)
        if metrics["agent_count"] <= 1:
            return False
        return metrics["imbalance_score"] >= self.imbalance_threshold

    def balance_workload(
        self,
        allocator: Optional[TaskAllocator] = None,
        threshold_hours: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes dynamic work-stealing from overloaded agents to underutilized agents.
        """
        alloc = allocator or self.allocator
        if not alloc:
            return []

        capacities = alloc.get_capacities()
        if len(capacities) < 2:
            return []

        rebalancing_actions = []
        limit_hours = threshold_hours if threshold_hours is not None else 3.0

        # Sort agents by workload descending
        sorted_agents = sorted(
            capacities.values(),
            key=lambda c: c.current_workload_hours,
            reverse=True,
        )

        most_busy = sorted_agents[0]
        least_busy = sorted_agents[-1]

        while (most_busy.current_workload_hours - least_busy.current_workload_hours) > limit_hours and len(most_busy.assigned_task_ids) > 1:
            task_to_steal_id = most_busy.assigned_task_ids[-1]
            task = alloc.get_task(task_to_steal_id)
            if not task:
                break

            success = alloc.reassign_task(task_to_steal_id, least_busy.agent_id)
            if success:
                action = {
                    "task_id": task_to_steal_id,
                    "from_agent": most_busy.agent_id,
                    "to_agent": least_busy.agent_id,
                    "hours": task.estimated_hours,
                    "timestamp": time.time(),
                }
                rebalancing_actions.append(action)
                self._balancing_history.append(action)
                logger.info("Balanced task '%s' from %s to %s (%sh)", task_to_steal_id, most_busy.agent_id, least_busy.agent_id, task.estimated_hours)

            # Re-sort agents
            sorted_agents = sorted(
                capacities.values(),
                key=lambda c: c.current_workload_hours,
                reverse=True,
            )
            most_busy = sorted_agents[0]
            least_busy = sorted_agents[-1]

        return rebalancing_actions
