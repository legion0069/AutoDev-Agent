"""
Tests for deterministic output across AutoDev v3.1 learning engines.
Validates that given identical inputs, all learning algorithms produce identical, repeatable outputs.
"""
import pytest
import os
import shutil
import tempfile
import json
from typing import List

from core.learning.learning_models import (
    LearningEvent,
    LearningEventType,
    PatternCategory,
    PlaybookArchetype,
    ReflectionScope,
    ImprovementArea,
)
from core.learning.learning_engine import LearningEngine
from core.learning.reflection_engine import ReflectionEngine
from core.learning.pattern_miner import PatternMiningEngine
from core.learning.prompt_optimizer import PromptOptimizationEngine
from core.learning.execution_analytics import ExecutionAnalyticsEngine
from core.learning.architecture_recommender import ArchitectureRecommendationEngine
from core.learning.playbook_engine import PlaybookEngine
from core.learning.self_improvement_planner import SelfImprovementPlanner
from core.learning.knowledge_evolution import KnowledgeEvolutionEngine
from core.learning.performance_evolution import PerformanceEvolutionEngine


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="autodev_test_det_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_learning_event_deterministic_serialization():
    evt1 = LearningEvent(
        id="EVT-1001",
        project="proj_alpha",
        task="task_det_1",
        category=LearningEventType.BUG_FIXED,
        confidence=0.92,
        importance=85.0,
        summary="Fixed race condition in connection pool",
        affected_files=["core/pool.py", "core/db.py"],
        root_cause="Missing mutex lock during acquire",
        solution="Wrapped acquire in threading.Lock",
        metrics={"duration_ms": 120, "retries": 1},
        tags=["concurrency", "bugfix"]
    )
    evt2 = LearningEvent(
        id="EVT-1001",
        project="proj_alpha",
        task="task_det_1",
        category=LearningEventType.BUG_FIXED,
        confidence=0.92,
        importance=85.0,
        summary="Fixed race condition in connection pool",
        affected_files=["core/pool.py", "core/db.py"],
        root_cause="Missing mutex lock during acquire",
        solution="Wrapped acquire in threading.Lock",
        metrics={"duration_ms": 120, "retries": 1},
        tags=["concurrency", "bugfix"]
    )
    
    d1 = json.dumps(evt1.to_dict(), sort_keys=True)
    d2 = json.dumps(evt2.to_dict(), sort_keys=True)
    assert d1 == d2


def test_prompt_optimizer_deterministic_compression(temp_dir):
    engine1 = PromptOptimizationEngine(storage_dir=os.path.join(temp_dir, "p1"))
    engine2 = PromptOptimizationEngine(storage_dir=os.path.join(temp_dir, "p2"))

    raw_prompt = """
    You are an expert Python engineer.
    Please write clean code.
    Please write clean code.
    Ensure test coverage is 100%.
    Follow PEP 8 guidelines.
    Follow PEP 8 guidelines.
    Never use deprecated libraries.
    """
    
    opt1 = engine1.optimize_prompt(raw_prompt, task_type="coding")
    opt2 = engine2.optimize_prompt(raw_prompt, task_type="coding")
    
    assert opt1.optimized_prompt == opt2.optimized_prompt
    assert opt1.token_count_before == opt2.token_count_before
    assert opt1.token_count_after == opt2.token_count_after
    assert opt1.compression_ratio == opt2.compression_ratio


def test_architecture_recommender_deterministic_output(temp_dir):
    engine1 = ArchitectureRecommendationEngine(storage_dir=os.path.join(temp_dir, "a1"))
    engine2 = ArchitectureRecommendationEngine(storage_dir=os.path.join(temp_dir, "a2"))

    req = "Build a high throughput RESTful API backend for customer user management with PostgreSQL and JWT auth"
    
    rec1 = engine1.recommend(req, project_name="user_service")
    rec2 = engine2.recommend(req, project_name="user_service")
    
    assert rec1.archetype == rec2.archetype
    assert rec1.database_choice == rec2.database_choice
    assert rec1.api_style == rec2.api_style
    assert rec1.design_patterns == rec2.design_patterns
    assert rec1.folder_structure == rec2.folder_structure


def test_playbook_deterministic_retrieval(temp_dir):
    engine1 = PlaybookEngine(storage_dir=os.path.join(temp_dir, "pb1"))
    engine2 = PlaybookEngine(storage_dir=os.path.join(temp_dir, "pb2"))

    pb1 = engine1.get_playbook(PlaybookArchetype.REST_API)
    pb2 = engine2.get_playbook(PlaybookArchetype.REST_API)

    assert pb1.archetype == pb2.archetype
    assert pb1.recommended_sequence == pb2.recommended_sequence
    assert pb1.best_practices == pb2.best_practices
    assert pb1.common_mistakes == pb2.common_mistakes


def test_execution_analytics_deterministic_stats(temp_dir):
    engine = ExecutionAnalyticsEngine(storage_dir=temp_dir)
    
    metrics_list = [
        {"review_score": 85.0, "retry_count": 1, "duration_seconds": 12.0, "coverage_pct": 88.0, "tests_passed": 10},
        {"review_score": 90.0, "retry_count": 0, "duration_seconds": 8.0, "coverage_pct": 92.0, "tests_passed": 15},
        {"review_score": 95.0, "retry_count": 2, "duration_seconds": 16.0, "coverage_pct": 94.0, "tests_passed": 20},
    ]
    
    for i, m in enumerate(metrics_list):
        engine.record_project_run(f"proj_{i}", m)
        
    stats1 = engine.compute_aggregated_statistics()
    stats2 = engine.compute_aggregated_statistics()
    
    assert stats1["avg_review_score"] == stats2["avg_review_score"]
    assert stats1["avg_retry_count"] == stats2["avg_retry_count"]
    assert stats1["avg_duration_seconds"] == stats2["avg_duration_seconds"]
    assert stats1["avg_coverage_pct"] == stats2["avg_coverage_pct"]


def test_pattern_miner_deterministic_clustering(temp_dir):
    engine1 = PatternMiningEngine(storage_dir=os.path.join(temp_dir, "pm1"))
    engine2 = PatternMiningEngine(storage_dir=os.path.join(temp_dir, "pm2"))

    events = [
        LearningEvent(
            id=f"EVT-{i}",
            category=LearningEventType.BUG_FIXED,
            summary="Null pointer dereference on uninitialized session token",
            root_cause="Missing session validation before header read",
            solution="Add token guard validator middleware"
        )
        for i in range(5)
    ]

    pats1 = engine1.mine_patterns(events)
    pats2 = engine2.mine_patterns(events)

    assert len(pats1) == len(pats2)
    if pats1 and pats2:
        assert pats1[0].name == pats2[0].name
        assert pats1[0].category == pats2[0].category


def test_reflection_engine_deterministic_evaluation(temp_dir):
    re1 = ReflectionEngine(storage_dir=os.path.join(temp_dir, "re1"))
    re2 = ReflectionEngine(storage_dir=os.path.join(temp_dir, "re2"))

    task_data = {
        "task_id": "T-100",
        "title": "Implement auth middleware",
        "success": True,
        "retries": 0,
        "review_score": 95.0,
        "tests_passed": True,
        "prompt_length": 450,
        "metrics": {"duration_ms": 2500}
    }

    rep1 = re1.reflect_on_task(task_data)
    rep2 = re2.reflect_on_task(task_data)

    assert rep1.execution_success == rep2.execution_success
    assert rep1.excessive_retries == rep2.excessive_retries
    assert rep1.planning_accurate == rep2.planning_accurate
    assert rep1.tests_sufficient == rep2.tests_sufficient
    assert rep1.what_worked == rep2.what_worked


def test_self_improvement_planner_deterministic_ranking(temp_dir):
    sip1 = SelfImprovementPlanner(storage_dir=os.path.join(temp_dir, "sip1"))
    sip2 = SelfImprovementPlanner(storage_dir=os.path.join(temp_dir, "sip2"))

    health_metrics = {
        "RetryEngine": 60.0,
        "PlanningEngine": 85.0,
        "PromptSynthesis": 70.0,
        "TestingStrategy": 90.0,
        "Orchestration": 95.0
    }

    plan1 = sip1.evaluate_and_plan("2026-10", health_metrics=health_metrics)
    plan2 = sip2.evaluate_and_plan("2026-10", health_metrics=health_metrics)

    assert plan1.weakest_subsystem == plan2.weakest_subsystem
    assert len(plan1.roadmap_items) == len(plan2.roadmap_items)
    for r1, r2 in zip(plan1.roadmap_items, plan2.roadmap_items):
        assert r1.target_subsystem == r2.target_subsystem
        assert r1.priority == r2.priority
        assert r1.estimated_roi == r2.estimated_roi


def test_knowledge_evolution_deterministic_similarity(temp_dir):
    ke = KnowledgeEvolutionEngine(storage_dir=temp_dir)
    
    sim1 = ke.calculate_similarity(
        "Implement repository pattern with SQLAlchemy ORM",
        "Implement repository pattern with database ORM layer"
    )
    sim2 = ke.calculate_similarity(
        "Implement repository pattern with SQLAlchemy ORM",
        "Implement repository pattern with database ORM layer"
    )
    
    assert sim1 == sim2
    assert 0.0 <= sim1 <= 1.0


def test_performance_evolution_deterministic_speedup_calculation(temp_dir):
    pe = PerformanceEvolutionEngine(storage_dir=temp_dir)
    
    rec = pe.record_metric(
        stage="planning",
        execution_time_seconds=1.5,
        memory_usage_mb=64.0,
        planning_latency_ms=150.0,
        benchmark_name="planning_bench"
    )
    
    assert rec.execution_time_seconds == 1.5
    assert rec.memory_usage_mb == 64.0
    assert rec.planning_latency_ms == 150.0
    assert rec.duration_ms == 1500.0
    assert rec.memory_kb == 64.0 * 1024.0
