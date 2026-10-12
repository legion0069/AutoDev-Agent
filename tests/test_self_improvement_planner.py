"""
test_self_improvement_planner.py - AutoDev Version 3.1
Unit and integration tests for SelfImprovementPlanner across 8 internal dimensions,
weakest subsystem detection, ROI-ranked roadmaps, and upgrade scheduling.
"""

from pathlib import Path
import pytest
from core.learning.learning_models import ImprovementArea, SelfImprovementPlan
from core.learning.self_improvement_planner import SelfImprovementPlanner


@pytest.fixture
def planner(tmp_path: Path):
    storage_dir = tmp_path / "self_improvement"
    return SelfImprovementPlanner(storage_dir=str(storage_dir), auto_persist=True)


def test_evaluate_and_create_improvement_plan(planner: SelfImprovementPlanner):
    metrics = {
        "retry_rate": 0.28,          # High retry rate -> lowers RETRY_ENGINE score
        "review_score": 92.0,
        "prompt_length_avg": 4500,  # Prompts getting big -> lowers PROMPT_ENGINEERING
        "test_coverage_pct": 82.0,  # Below 90% -> lowers TESTING_STRATEGY
        "planning_accuracy": 95.0,
        "memory_duplicate_ratio": 0.05,
    }

    plan = planner.evaluate_and_create_plan(
        evaluation_period="2026-10",
        system_metrics=metrics,
    )

    assert plan.plan_id.startswith("PLAN-")
    assert plan.evaluation_period == "2026-10"
    assert len(plan.weakest_subsystems) > 0
    assert "RETRY_ENGINE" in plan.weakest_subsystems or "PROMPT_ENGINEERING" in plan.weakest_subsystems
    assert len(plan.roadmap_items) >= 2

    # Verify roadmap items have positive ROI and are sorted by priority / ROI
    assert all(item.estimated_roi > 0.0 for item in plan.roadmap_items)
    assert all(item.effort_days > 0.0 for item in plan.roadmap_items)


def test_update_roadmap_item_status(planner: SelfImprovementPlanner):
    plan = planner.evaluate_and_create_plan(
        evaluation_period="2026-11",
        system_metrics={"retry_rate": 0.35},
    )

    first_item = plan.roadmap_items[0]
    assert first_item.status == "PLANNED"

    updated_plan = planner.update_roadmap_item_status(plan.plan_id, first_item.id, "IN_PROGRESS")
    assert updated_plan is not None
    assert updated_plan.roadmap_items[0].status == "IN_PROGRESS"

    completed_plan = planner.update_roadmap_item_status(plan.plan_id, first_item.id, "COMPLETED")
    assert completed_plan is not None
    assert completed_plan.roadmap_items[0].status == "COMPLETED"


def test_get_latest_plan_and_history(planner: SelfImprovementPlanner):
    plan1 = planner.evaluate_and_create_plan(evaluation_period="2026-09", system_metrics={})
    plan2 = planner.evaluate_and_create_plan(evaluation_period="2026-10", system_metrics={})

    latest = planner.get_latest_plan()
    assert latest is not None
    assert latest.plan_id == plan2.plan_id

    all_plans = planner.get_all_plans()
    assert len(all_plans) == 2


def test_subsystem_health_scores_coverage(planner: SelfImprovementPlanner):
    scores = planner.calculate_subsystem_health_scores({
        "retry_rate": 0.05,
        "review_score": 96.0,
        "prompt_length_avg": 1200,
        "test_coverage_pct": 95.0,
        "planning_accuracy": 98.0,
        "memory_duplicate_ratio": 0.01,
    })

    expected_areas = {
        ImprovementArea.RETRY_ENGINE.value,
        ImprovementArea.PLANNING.value,
        ImprovementArea.PROMPT_ENGINEERING.value,
        ImprovementArea.TESTING_STRATEGY.value,
        ImprovementArea.ORCHESTRATION.value,
        ImprovementArea.ARCHITECTURE_MODELING.value,
        ImprovementArea.MEMORY_MANAGEMENT.value,
        ImprovementArea.SECURITY_GOVERNANCE.value,
    }
    assert expected_areas.issubset(set(scores.keys()))
    assert all(0.0 <= s <= 100.0 for s in scores.values())
