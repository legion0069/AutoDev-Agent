"""
test_sprint_manager.py - Unit and Integration Tests for Sprint & Agile Management (v3.0)
"""

import pytest
from core.enterprise.enterprise_models import PriorityLevel, SprintState, UserStory
from core.enterprise.sprint_manager import SprintManager


@pytest.fixture
def sm():
    return SprintManager(default_velocity=15.0)


class TestSprintManager:
    def test_plan_sprint(self, sm: SprintManager):
        story1 = UserStory("US-1", "FEAT-1", "Task 1", "Dev", "code", "deliver", story_points=5, priority=PriorityLevel.HIGH)
        story2 = UserStory("US-2", "FEAT-1", "Task 2", "Dev", "test", "quality", story_points=8, priority=PriorityLevel.MEDIUM)

        sprint = sm.plan_sprint(
            sprint_id="SPRINT-01",
            sprint_number=1,
            goal="Deliver Core Ingestion Engine",
            candidate_stories=[story1, story2],
            capacity_points=40,
        )
        assert sprint.sprint_id == "SPRINT-01"
        assert sprint.sprint_number == 1
        assert sprint.committed_points == 13
        assert sprint.state == SprintState.PLANNING

    def test_start_sprint(self, sm: SprintManager):
        story = UserStory("US-1", "F-1", "Task", "U", "A", "B", story_points=5)
        sm.plan_sprint("SPRINT-02", 2, "Goal", [story], capacity_points=30)

        started = sm.start_sprint("SPRINT-02")
        assert started.state == SprintState.ACTIVE
        assert sm.get_active_sprint().sprint_id == "SPRINT-02"

    def test_cannot_start_two_active_sprints_simultaneously(self, sm: SprintManager):
        s1 = UserStory("US-1", "F-1", "T", "U", "A", "B", 3)
        sm.plan_sprint("S-1", 1, "G1", [s1])
        sm.plan_sprint("S-2", 2, "G2", [s1])

        sm.start_sprint("S-1")
        with pytest.raises(RuntimeError):
            sm.start_sprint("S-2")

    def test_daily_standup_simulation_and_burndown(self, sm: SprintManager):
        story = UserStory("US-1", "F-1", "Task", "U", "A", "B", story_points=8)
        sprint = sm.plan_sprint("SPRINT-03", 3, "Goal", [story], capacity_points=30)
        sm.start_sprint("SPRINT-03")

        standup1 = sm.conduct_daily_standup(day_index=1, blocked_story_ids=[])
        assert standup1["day_index"] == 1
        assert standup1["remaining_points"] == 8

        # Complete story
        sprint_ref = sm._sprints["SPRINT-03"]
        sprint_ref.stories[0].status = "DONE"

        standup2 = sm.conduct_daily_standup(day_index=2, blocked_story_ids=[])
        assert standup2["remaining_points"] == 0

        active_sprint = sm.get_active_sprint()
        assert len(active_sprint.daily_burndown) >= 2

    def test_complete_sprint_with_velocity_and_carryover(self, sm: SprintManager):
        done_story = UserStory("US-DONE", "F-1", "Done Task", "U", "A", "B", story_points=5, status="DONE")
        pending_story = UserStory("US-PEND", "F-1", "Pending Task", "U", "A", "B", story_points=8, status="IN_PROGRESS")

        sm.plan_sprint("SPRINT-04", 4, "Goal", [done_story, pending_story], capacity_points=30)
        sm.start_sprint("SPRINT-04")

        completed = sm.complete_sprint(
            sprint_id="SPRINT-04",
            retrospective_notes=["Great velocity on core modules", "Complex DB migrations carried over"],
        )
        assert completed.state == SprintState.COMPLETED
        assert completed.completed_points == 5
        assert completed.velocity == 5.0
        assert "US-PEND" in completed.carried_over_stories
        assert len(completed.retrospective_notes) == 2

    def test_average_velocity_calculation(self, sm: SprintManager):
        s1 = UserStory("U1", "F1", "T", "U", "A", "B", 10, status="DONE")
        sm.plan_sprint("S1", 1, "G", [s1])
        sm.start_sprint("S1")
        sm.complete_sprint("S1")

        s2 = UserStory("U2", "F1", "T", "U", "A", "B", 20, status="DONE")
        sm.plan_sprint("S2", 2, "G", [s2])
        sm.start_sprint("S2")
        sm.complete_sprint("S2")

        avg_vel = sm.get_average_velocity()
        assert avg_vel == 15.0
