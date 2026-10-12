"""
test_engineering_manager.py - Unit and Integration Tests for Engineering Department (v3.0)
"""

import pytest
from core.enterprise.engineering_manager import EngineeringManager
from core.enterprise.enterprise_models import TeamType


@pytest.fixture
def eng_mgr():
    return EngineeringManager()


class TestEngineeringManager:
    def test_default_teams_initialized(self, eng_mgr: EngineeringManager):
        teams = eng_mgr.list_teams()
        assert len(teams) >= 8
        team_types = {t.team_type for t in teams}
        assert TeamType.BACKEND in team_types
        assert TeamType.FRONTEND in team_types
        assert TeamType.MOBILE in team_types
        assert TeamType.AI_ML in team_types
        assert TeamType.INFRASTRUCTURE in team_types
        assert TeamType.DATABASE in team_types
        assert TeamType.QA_AUTOMATION in team_types
        assert TeamType.PLATFORM in team_types

    def test_assign_task_to_team(self, eng_mgr: EngineeringManager):
        task = eng_mgr.assign_task(
            task_id="ENG-101",
            team=TeamType.BACKEND,
            title="Implement Distributed Lock Lease Manager",
            story_points=5,
        )
        assert task["task_id"] == "ENG-101"
        team = eng_mgr.get_team(TeamType.BACKEND)
        assert "ENG-101" in team.assigned_tasks
        assert team.current_workload_points == 5

    def test_record_work_completed(self, eng_mgr: EngineeringManager):
        eng_mgr.assign_task("ENG-102", TeamType.AI_ML, "Train Router", story_points=8)
        eng_mgr.record_work_completed(TeamType.AI_ML, points=8)

        team = eng_mgr.get_team(TeamType.AI_ML)
        assert team.current_workload_points == 0
        assert team.velocity_points >= 8.0

    def test_workload_balancing_and_overload_detection(self, eng_mgr: EngineeringManager):
        # Capacity is 40. Assign 45 points.
        eng_mgr.assign_task("ENG-T1", TeamType.DATABASE, "Task 1", story_points=25)
        eng_mgr.assign_task("ENG-T2", TeamType.DATABASE, "Task 2", story_points=20)

        team = eng_mgr.get_team(TeamType.DATABASE)
        assert team.is_overloaded is True

        overloaded_teams = eng_mgr.get_overloaded_teams()
        assert TeamType.DATABASE in [t.team_type for t in overloaded_teams]

    def test_get_engineering_metrics(self, eng_mgr: EngineeringManager):
        eng_mgr.assign_task("E1", TeamType.FRONTEND, "UI", 10)
        eng_mgr.record_work_completed(TeamType.FRONTEND, 10)

        metrics = eng_mgr.get_metrics()
        assert metrics["total_teams"] >= 8
        assert metrics["total_active_workload_points"] == 0
        assert metrics["total_velocity_points"] >= 10.0
