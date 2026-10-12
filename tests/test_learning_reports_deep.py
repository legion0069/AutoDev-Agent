"""
Comprehensive test suite validating all 8 required reporting modules in AutoDev v3.1:
1. Learning Report
2. Reflection Report
3. Evolution Report
4. Performance Report
5. Architecture Report
6. Prompt Improvement Report
7. Pattern Discovery Report
8. Self Improvement Roadmap
"""
import pytest
import os
import shutil
import tempfile
import json

from core.learning.learning_coordinator import LearningCoordinator
from core.learning.learning_models import (
    LearningEvent,
    LearningEventType,
    LearningKnowledge,
    PlaybookArchetype,
    ReflectionScope,
    ImprovementArea
)


@pytest.fixture
def coordinator():
    d = tempfile.mkdtemp(prefix="autodev_reports_deep_")
    coord = LearningCoordinator(storage_dir=d)
    yield coord
    shutil.rmtree(d, ignore_errors=True)


def test_generate_learning_report(coordinator):
    coordinator.learning_engine.record_event(LearningEvent(
        id="EVT-RPT-1",
        project="proj_report",
        task="task_1",
        category=LearningEventType.BUG_FIXED,
        summary="Fixed race condition",
        root_cause="Unsynchronized dictionary access",
        solution="Added lock guard"
    ))
    
    report = coordinator.generate_learning_report()
    assert report is not None
    assert "total_events" in report or "events_count" in report or "summary" in report
    assert report.get("total_events", 0) >= 1 or len(report.get("events", [])) >= 1


def test_generate_reflection_report(coordinator):
    task_res = {
        "task_id": "T-REF-1",
        "title": "Build caching layer",
        "success": True,
        "retries": 1,
        "review_score": 90.0,
        "tests_passed": True
    }
    
    ref = coordinator.reflection_engine.reflect_on_task(task_res)
    assert ref is not None
    assert ref.execution_success is True
    assert len(ref.what_worked) >= 1


def test_generate_evolution_report(coordinator):
    coordinator.knowledge_evolution.add_knowledge(
        LearningKnowledge(
            id="KNW-EVO-1",
            title="Async worker pool scaling",
            summary="Keep worker concurrency tied to os.cpu_count()",
            utility_score=88.0
        )
    )
    
    rep = coordinator.generate_evolution_report()
    assert rep is not None
    assert "institutional_knowledge" in rep or "total_knowledge_items" in rep or "knowledge" in rep


def test_generate_performance_report(coordinator):
    coordinator.performance_evolution.record_metric(
        stage="planning",
        execution_time_seconds=0.8,
        memory_usage_mb=45.0
    )
    
    rep = coordinator.generate_performance_report()
    assert rep is not None
    assert "version" in rep or "stage_summaries" in rep or "benchmarks" in rep


def test_generate_architecture_report(coordinator):
    rec = coordinator.architecture_recommender.recommend(
        requirement="Build an event-driven message queue processor with RabbitMQ and Python workers",
        project_name="worker_service"
    )
    
    rep = coordinator.generate_architecture_report(rec)
    assert rep is not None
    assert "archetype" in rep
    assert "database_choice" in rep or "database_recommendation" in rep


def test_generate_prompt_improvement_report(coordinator):
    coordinator.prompt_optimizer.optimize_prompt(
        "Generate a CRUD router in FastAPI. Generate a CRUD router in FastAPI.",
        task_type="coding"
    )
    
    rep = coordinator.generate_prompt_improvement_report()
    assert rep is not None
    assert "records" in rep or "total_templates" in rep or "average_compression_ratio" in rep


def test_generate_pattern_discovery_report(coordinator):
    coordinator.pattern_miner.mine_patterns([
        LearningEvent(
            id="EVT-PAT-1",
            category=LearningEventType.PATTERN_DISCOVERED,
            summary="Factory method pattern for provider instantiation",
            solution="Create get_provider() dispatch function"
        )
    ])
    
    rep = coordinator.generate_pattern_discovery_report()
    assert rep is not None
    assert "patterns" in rep or "total_patterns" in rep


def test_generate_self_improvement_roadmap_report(coordinator):
    plan = coordinator.self_improvement_planner.evaluate_and_plan(
        period="2026-Q4",
        health_metrics={"RetryEngine": 55.0, "PlanningEngine": 85.0}
    )
    
    rep = coordinator.generate_self_improvement_roadmap_report(plan)
    assert rep is not None
    assert "roadmap" in rep or "weakest_subsystem" in rep or "executive_summary" in rep
