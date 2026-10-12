"""
sprint_manager.py - Agile Sprint Execution, Velocity & Burndown for AutoDev (v3.0)

Coordinates 2-week sprint cycles, velocity metrics, capacity planning, daily standup simulation,
burndown tracking, retrospectives, and automated rollover of incomplete stories.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from core.enterprise.enterprise_models import (
    SprintPlan,
    SprintState,
    UserStory,
)

logger = logging.getLogger("AutoDev.Enterprise.Sprint")


class SprintManager:
    """
    Agile Sprint Coordinator managing sprint backlogs, velocity tracking,
    burndown charts, daily standups, and retrospective insights.
    """

    def __init__(self, default_velocity: float = 30.0) -> None:
        self._lock = threading.RLock()
        self._sprints: Dict[str, SprintPlan] = {}
        self._active_sprint_id: Optional[str] = None
        self._historical_velocities: List[float] = [default_velocity]
        self._standup_logs: Dict[str, List[Dict[str, Any]]] = {}

    def get_average_velocity(self) -> float:
        with self._lock:
            return round(sum(self._historical_velocities) / len(self._historical_velocities), 2)

    @property
    def average_velocity(self) -> float:
        return self.get_average_velocity()

    def plan_sprint(
        self,
        sprint_id: Optional[str] = None,
        sprint_number: Optional[int] = None,
        goal: str = "Deliver Planned Capabilities",
        candidate_stories: Optional[List[UserStory]] = None,
        capacity_points: Optional[int] = None,
        duration_days: int = 14,
    ) -> SprintPlan:
        """
        Plans a new sprint with target capacity and committed candidate stories.
        """
        with self._lock:
            now = time.time()
            s_num = sprint_number if sprint_number is not None else (len(self._sprints) + 1)
            s_id = sprint_id or f"sprint_{s_num:02d}"
            cap = capacity_points if capacity_points is not None else int(self.get_average_velocity() * 1.1)
            stories = copy.deepcopy(candidate_stories or [])
            committed = sum(s.story_points for s in stories)

            plan = SprintPlan(
                sprint_id=s_id,
                sprint_number=s_num,
                goal=goal,
                start_date=now,
                end_date=now + (duration_days * 86400),
                capacity_points=cap,
                committed_points=committed,
                stories=stories,
                state=SprintState.PLANNING,
                daily_burndown=[{
                    "day": 0,
                    "remaining_points": committed,
                    "completed_points": 0,
                    "timestamp": now,
                }],
            )

            self._sprints[s_id] = plan
            self._standup_logs[s_id] = []
            logger.info("Planned %s (#%d): '%s' with %d pt capacity, %d committed pts", s_id, s_num, goal, cap, committed)
            return copy.deepcopy(plan)

    create_sprint = plan_sprint

    def start_sprint(self, sprint_id: str) -> SprintPlan:
        """Starts an active sprint."""
        with self._lock:
            if self._active_sprint_id is not None and self._active_sprint_id != sprint_id:
                active_sprint = self._sprints.get(self._active_sprint_id)
                if active_sprint and active_sprint.state == SprintState.ACTIVE:
                    raise RuntimeError(f"Cannot start sprint {sprint_id}; sprint {self._active_sprint_id} is already ACTIVE.")

            sprint = self._sprints.get(sprint_id)
            if not sprint:
                raise KeyError(f"Sprint {sprint_id} not found")

            sprint.state = SprintState.ACTIVE
            self._active_sprint_id = sprint_id
            logger.info("Sprint %s is now ACTIVE", sprint_id)
            return copy.deepcopy(sprint)

    def get_active_sprint(self) -> Optional[SprintPlan]:
        """Retrieves currently active sprint."""
        with self._lock:
            if not self._active_sprint_id:
                return None
            return copy.deepcopy(self._sprints.get(self._active_sprint_id))

    def conduct_daily_standup(
        self,
        day_index: int = 1,
        blocked_story_ids: Optional[List[str]] = None,
        sprint_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Simulates and logs a daily standup for the active sprint."""
        with self._lock:
            sid = sprint_id or self._active_sprint_id
            if not sid or sid not in self._sprints:
                return {"status": "NO_ACTIVE_SPRINT", "day_index": day_index}

            sprint = self._sprints[sid]
            completed_pts = sum(s.story_points for s in sprint.stories if s.status == "DONE")
            sprint.completed_points = completed_pts
            rem_pts = max(0, sprint.committed_points - completed_pts)

            standup = {
                "sprint_id": sid,
                "day_index": day_index,
                "completed_points": completed_pts,
                "remaining_points": rem_pts,
                "blocked_stories": list(blocked_story_ids or []),
                "timestamp": time.time(),
            }

            sprint.daily_burndown.append({
                "day": day_index,
                "remaining_points": rem_pts,
                "completed_points": completed_pts,
                "timestamp": time.time(),
            })

            self._standup_logs.setdefault(sid, []).append(standup)
            return standup

    run_daily_standup = conduct_daily_standup

    def complete_sprint(
        self,
        sprint_id: Optional[str] = None,
        retrospective_notes: Optional[List[str]] = None,
    ) -> SprintPlan:
        """Completes an active sprint, updates velocity history, and records retrospective."""
        with self._lock:
            sid = sprint_id or self._active_sprint_id
            if not sid or sid not in self._sprints:
                raise KeyError(f"Sprint {sid} not found")

            sprint = self._sprints[sid]
            sprint.state = SprintState.COMPLETED
            
            # Calculate completed vs carried over
            completed_stories = [s for s in sprint.stories if s.status == "DONE"]
            carry_overs = [s.story_id for s in sprint.stories if s.status != "DONE"]
            
            sprint.completed_points = sum(s.story_points for s in completed_stories)
            sprint.carried_over_stories = carry_overs
            sprint.retrospective_notes = list(retrospective_notes or [])

            # Update historical velocity
            self._historical_velocities.append(float(sprint.completed_points))

            if self._active_sprint_id == sid:
                self._active_sprint_id = None

            logger.info("Sprint %s completed (Velocity: %.1f, Carried over: %d stories)",
                        sid, sprint.velocity, len(carry_overs))
            return copy.deepcopy(sprint)

    def get_sprint(self, sprint_id: str) -> Optional[SprintPlan]:
        with self._lock:
            return copy.deepcopy(self._sprints.get(sprint_id))

    def list_sprints(self) -> List[SprintPlan]:
        with self._lock:
            return [copy.deepcopy(s) for s in self._sprints.values()]
