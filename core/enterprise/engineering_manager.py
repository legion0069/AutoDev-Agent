"""
engineering_manager.py - Engineering Department & Cross-Team Workload Allocation for AutoDev (v3.0)

Supervises specialized engineering teams (Backend, Frontend, Mobile, AI/ML, Infrastructure, Database,
QA Automation, Platform), allocates user stories, and tracks team productivity metrics.
"""

from __future__ import annotations

import copy
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from core.enterprise.enterprise_models import (
    EmployeeProfile,
    TeamType,
    UserStory,
)

logger = logging.getLogger("AutoDev.Enterprise.Engineering")


@dataclass
class EngineeringTeam:
    team_type: TeamType
    name: str
    lead_id: str
    members: List[str] = field(default_factory=list)  # employee_ids
    assigned_tasks: List[str] = field(default_factory=list)
    active_stories: List[str] = field(default_factory=list)
    current_workload_points: int = 0
    capacity_points: int = 40
    velocity_points: float = 35.0
    defect_density_per_kloc: float = 0.5

    @property
    def is_overloaded(self) -> bool:
        return self.current_workload_points > self.capacity_points

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_type": self.team_type.value,
            "name": self.name,
            "lead_id": self.lead_id,
            "members": self.members,
            "assigned_tasks": self.assigned_tasks,
            "current_workload_points": self.current_workload_points,
            "capacity_points": self.capacity_points,
            "velocity_points": self.velocity_points,
            "is_overloaded": self.is_overloaded,
        }


class EngineeringManager:
    """
    Engineering Department Management Engine.
    Coordinates specialized engineering teams, balances sprint workloads, and tracks team output.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._teams: Dict[TeamType, EngineeringTeam] = {}
        self._story_assignments: Dict[str, TeamType] = {}
        self._tasks: Dict[str, Dict[str, Any]] = {}

        self._init_default_teams()

    def _init_default_teams(self) -> None:
        """Constructs standard engineering team matrix."""
        team_specs = [
            (TeamType.BACKEND, "Core Backend & Distributed Systems", "lead_backend", ["emp_b1", "emp_b2", "emp_b3"]),
            (TeamType.FRONTEND, "Web & Client Interfaces", "lead_frontend", ["emp_f1", "emp_f2"]),
            (TeamType.MOBILE, "Mobile Client Applications", "lead_mobile", ["emp_m1"]),
            (TeamType.AI_ML, "AI Agent Synthesis & ML Systems", "lead_ai", ["emp_ai1", "emp_ai2"]),
            (TeamType.INFRASTRUCTURE, "Cloud Infra & Cluster Fabric", "lead_infra", ["emp_i1", "emp_i2"]),
            (TeamType.DATABASE, "Storage & Data Architectures", "lead_db", ["emp_db1"]),
            (TeamType.QA_AUTOMATION, "Test Automation & Quality Gates", "lead_qa", ["emp_qa1", "emp_qa2"]),
            (TeamType.PLATFORM, "Developer Platform & CI/CD Tooling", "lead_plat", ["emp_p1"]),
            (TeamType.PRODUCT_OPS, "Product Operations & Release QA", "lead_prodops", ["emp_po1"]),
            (TeamType.SECURITY_OPS, "Security Operations & Vulnerability Response", "lead_sec", ["emp_sec1"]),
            (TeamType.CORE_SERVICES, "Core Shared Services & Messaging Bus", "lead_core", ["emp_cs1"]),
        ]

        for tt, name, lead, members in team_specs:
            self._teams[tt] = EngineeringTeam(
                team_type=tt,
                name=name,
                lead_id=lead,
                members=members,
            )

    def assign_task(
        self,
        task_id: str,
        team: TeamType,
        title: str,
        story_points: int = 3,
    ) -> Dict[str, Any]:
        """Assigns an engineering task to a team."""
        with self._lock:
            if team not in self._teams:
                team = TeamType.BACKEND

            t_obj = self._teams[team]
            t_obj.assigned_tasks.append(task_id)
            t_obj.current_workload_points += story_points

            task_rec = {
                "task_id": task_id,
                "team": team.value,
                "title": title,
                "story_points": story_points,
                "status": "ASSIGNED",
            }
            self._tasks[task_id] = task_rec
            logger.info("Assigned task %s ('%s', %d pts) to team %s", task_id, title, story_points, team.value)
            return task_rec

    def record_work_completed(self, team: TeamType, points: int) -> None:
        """Records completed engineering story points for a team."""
        with self._lock:
            if team in self._teams:
                t_obj = self._teams[team]
                t_obj.current_workload_points = max(0, t_obj.current_workload_points - points)
                t_obj.velocity_points += float(points)

    def get_overloaded_teams(self) -> List[EngineeringTeam]:
        """Returns teams where active workload exceeds capacity."""
        with self._lock:
            return [copy.deepcopy(t) for t in self._teams.values() if t.is_overloaded]

    def allocate_story_to_team(self, story: UserStory, target_team: Optional[TeamType] = None) -> TeamType:
        """
        Allocates a user story to the optimal engineering team based on skills or explicit team target.
        """
        with self._lock:
            if target_team and target_team in self._teams:
                team_type = target_team
            else:
                title_lower = (story.title + " " + story.action).lower()
                if "front" in title_lower or "ui" in title_lower or "dashboard" in title_lower:
                    team_type = TeamType.FRONTEND
                elif "ai" in title_lower or "llm" in title_lower or "model" in title_lower:
                    team_type = TeamType.AI_ML
                elif "qa" in title_lower or "test" in title_lower or "verify" in title_lower:
                    team_type = TeamType.QA_AUTOMATION
                elif "infra" in title_lower or "cluster" in title_lower or "cloud" in title_lower:
                    team_type = TeamType.INFRASTRUCTURE
                elif "db" in title_lower or "database" in title_lower or "storage" in title_lower:
                    team_type = TeamType.DATABASE
                else:
                    team_type = TeamType.BACKEND

            team = self._teams[team_type]
            team.active_stories.append(story.story_id)
            team.current_workload_points += story.story_points
            self._story_assignments[story.story_id] = team_type
            logger.debug("Allocated story %s ('%s') to %s", story.story_id, story.title, team_type.value)
            return team_type

    def get_team(self, team_type: TeamType) -> Optional[EngineeringTeam]:
        with self._lock:
            t = self._teams.get(team_type)
            return copy.deepcopy(t) if t else None

    def list_teams(self) -> List[EngineeringTeam]:
        with self._lock:
            return [copy.deepcopy(t) for t in self._teams.values()]

    def get_metrics(self) -> Dict[str, Any]:
        """Calculates aggregate engineering department metrics."""
        with self._lock:
            total_engineers = sum(len(t.members) + 1 for t in self._teams.values())
            total_active_workload = sum(t.current_workload_points for t in self._teams.values())
            total_velocity = sum(t.velocity_points for t in self._teams.values())

            return {
                "total_teams": len(self._teams),
                "total_headcount": total_engineers,
                "total_active_workload_points": total_active_workload,
                "total_velocity_points": round(total_velocity, 2),
                "teams": {t.team_type.value: t.to_dict() for t in self._teams.values()}
            }

    get_engineering_metrics = get_metrics
