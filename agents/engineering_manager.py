"""
engineering_manager.py - Engineering Manager Agent (AutoDev Version 3.4)

Directs sprint execution and team coordination:
- Sprint capacity planning and velocity tracking
- Task allocation across Backend, Frontend, and QA teams
- Real-time blocker remediation and workload balancing
- Team health supervision and burnout prevention
- Presides over Daily Standups and Sprint Retrospectives
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType
from core.organization_state import OrganizationState

logger = logging.getLogger("AutoDev.Org.EngineeringManager")


class EngineeringManagerAgent:
    """
    Autonomous Engineering Manager AI Agent.
    """

    def __init__(
        self,
        name: str = "EngineeringManager",
        bus: Optional[CommunicationBus] = None,
        state: Optional[OrganizationState] = None,
    ) -> None:
        self.name = name
        self.bus = bus
        self.state = state
        self.authority_level = 3  # Managerial
        self.velocity_history: List[float] = [20.0, 24.0, 22.5]
        self.active_sprint_id: Optional[str] = "SPRINT-42"

        if self.bus:
            self.bus.register_entity(self.name)

    def plan_sprint_allocation(
        self,
        user_stories: List[str],
        available_teams: List[str],
        team_capacities: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Decomposes user stories into atomic engineering tasks and assigns to teams."""
        capacities = team_capacities or {"Backend": 15, "Frontend": 10, "QA": 12}
        allocated_tasks: Dict[str, Dict[str, Any]] = {}
        idx = 1

        for story in user_stories:
            # Backend task
            be_id = f"TASK-BE-{idx:02d}"
            allocated_tasks[be_id] = {
                "team": "Backend",
                "title": f"Implement backend service for: {story}",
                "estimated_hours": 6.0,
                "story": story,
            }

            # Frontend task (if user-facing)
            if any(k in story.lower() for k in ["ui", "endpoint", "gateway", "modal", "view", "dashboard"]):
                fe_id = f"TASK-FE-{idx:02d}"
                allocated_tasks[fe_id] = {
                    "team": "Frontend",
                    "title": f"Implement UI interface for: {story}",
                    "estimated_hours": 5.0,
                    "story": story,
                }

            # QA verification task
            qa_id = f"TASK-QA-{idx:02d}"
            allocated_tasks[qa_id] = {
                "team": "QA",
                "title": f"Automated test coverage for: {story}",
                "estimated_hours": 4.0,
                "story": story,
            }
            idx += 1

        total_workload = len(allocated_tasks)
        total_capacity = sum(capacities.values())
        healthy = total_workload <= total_capacity

        result = {
            "sprint_id": self.active_sprint_id,
            "allocated_tasks": allocated_tasks,
            "total_tasks_count": total_workload,
            "team_capacity_healthy": healthy,
            "target_velocity": statistics_mean(self.velocity_history) if self.velocity_history else 22.0,
        }

        if self.state:
            self.state.record_audit_event(
                actor=self.name,
                action="PLAN_SPRINT_ALLOCATION",
                details={"tasks_count": total_workload, "healthy": healthy},
            )

        logger.info("Sprint allocation planned: %d tasks assigned.", total_workload)
        return result

    def balance_workloads(self, department_reports: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Detects workload imbalances across teams and triggers rebalancing."""
        overloaded = []
        underutilized = []

        for dept, rep in department_reports.items():
            util = rep.get("utilization_rate", 0.5)
            if util > 1.0:
                overloaded.append(dept)
            elif util < 0.4:
                underutilized.append(dept)

        actions = []
        if overloaded and underutilized:
            actions.append(f"Shift non-critical testing from {overloaded[0]} to {underutilized[0]}")

        return {
            "overloaded_teams": overloaded,
            "underutilized_teams": underutilized,
            "rebalance_actions": actions,
            "balanced": len(overloaded) == 0,
        }

    def unblock_task(self, task_id: str, reason: str, solution: str) -> Dict[str, Any]:
        """Resolves task blocker and unblocks assigned engineer."""
        logger.info("EM unblocking task '%s': %s -> %s", task_id, reason, solution)
        return {
            "task_id": task_id,
            "status": "UNBLOCKED",
            "resolution": solution,
            "timestamp": time.time(),
        }


def statistics_mean(numbers: List[float]) -> float:
    return round(sum(numbers) / max(1, len(numbers)), 2)
