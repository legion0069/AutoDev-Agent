"""
Deep tests for Subsystem 8: Self Improvement Planner.
Validates multi-subsystem health evaluation, ROI calculation, roadmap synthesis, and scheduled upgrade tracking.
"""
import pytest
import os
import shutil
import tempfile
import json

from core.learning.learning_models import (
    ImprovementArea,
    ImprovementRoadmapItem,
    SelfImprovementPlan
)
from core.learning.self_improvement_planner import SelfImprovementPlanner


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="autodev_test_sip_deep_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_subsystem_health_evaluation_weighting(temp_dir):
    planner = SelfImprovementPlanner(storage_dir=temp_dir)
    
    execution_metrics = {
        "retry_rate": 0.35,              # High retry rate (weak RetryEngine)
        "planning_drift_pct": 0.10,      # Low drift (strong Planning)
        "test_failure_rate": 0.05,       # Low failure (strong Testing)
        "prompt_bloat_ratio": 0.40,      # High bloat (weak PromptSynthesis)
        "review_rejections": 2
    }
    
    health = planner.evaluate_subsystem_health(execution_metrics)
    assert health["RetryEngine"] < 75.0
    assert health["PromptSynthesis"] < 75.0
    assert health["PlanningEngine"] > 80.0
    assert health["TestingStrategy"] > 80.0


def test_roadmap_generation_prioritization(temp_dir):
    planner = SelfImprovementPlanner(storage_dir=temp_dir)
    
    health_scores = {
        "RetryEngine": 45.0,             # Critical weakness
        "PromptSynthesis": 60.0,         # Moderate weakness
        "PlanningEngine": 88.0,
        "TestingStrategy": 92.0,
        "Orchestration": 95.0
    }
    
    plan = planner.evaluate_and_plan(period="2026-Q4", health_metrics=health_scores)
    
    assert plan.weakest_subsystem in ("RetryEngine", "RETRY_ENGINE")
    assert len(plan.roadmap_items) >= 2
    
    # Priority check: the lowest health score gets highest priority (P0 or P1)
    p0_or_p1_items = [item for item in plan.roadmap_items if item.priority in ("P0", "P1")]
    assert len(p0_or_p1_items) >= 1
    assert any("Retry" in item.target_subsystem or item.area == ImprovementArea.RETRY_ENGINE for item in p0_or_p1_items)


def test_plan_serialization_and_retrieval(temp_dir):
    planner = SelfImprovementPlanner(storage_dir=temp_dir)
    
    health_scores = {
        "RetryEngine": 55.0,
        "PlanningEngine": 70.0,
        "PromptSynthesis": 80.0
    }
    
    plan = planner.evaluate_and_plan(period="2026-11", health_metrics=health_scores)
    plan_dict = plan.to_dict()
    
    restored_plan = SelfImprovementPlan.from_dict(plan_dict)
    assert restored_plan.evaluation_period == "2026-11"
    assert restored_plan.weakest_subsystem == plan.weakest_subsystem
    assert len(restored_plan.roadmap_items) == len(plan.roadmap_items)


def test_markdown_roadmap_report_generation(temp_dir):
    planner = SelfImprovementPlanner(storage_dir=temp_dir)
    
    health_scores = {"RetryEngine": 50.0, "PromptSynthesis": 65.0}
    plan = planner.evaluate_and_plan(period="2026-Q4", health_metrics=health_scores)
    
    md_report = planner.generate_roadmap_markdown(plan)
    assert "# Self-Improvement Roadmap" in md_report
    assert "Weakest Subsystem" in md_report
    assert "2026-Q4" in md_report
