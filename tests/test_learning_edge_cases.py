"""
tests/test_learning_edge_cases.py - Boundary, Edge Case, and Malformed Input Tests for AutoDev v3.1
"""

import json
import shutil
import tempfile
from pathlib import Path
import pytest

from core.learning import (
    ArchitectureRecommendationEngine,
    ExecutionAnalyticsEngine,
    KnowledgeEvolutionEngine,
    LearningEngine,
    LearningEventType,
    PatternCategory,
    PatternMiningEngine,
    PerformanceEvolutionEngine,
    PlaybookArchetype,
    PlaybookEngine,
    PromptOptimizationEngine,
    ReflectionEngine,
    SelfEvolvingEngine,
    SelfImprovementPlanner,
)
from core.learning.learning_models import (
    ArchitectureRecommendation,
    EngineeringPattern,
    EngineeringPlaybook,
    LearningEvent,
    LearningKnowledge,
    LearningSession,
    LearningSnapshot,
    ReflectionReport,
    SelfImprovementPlan,
)


@pytest.fixture
def temp_edge_dir():
    temp_dir = tempfile.mkdtemp(prefix="autodev_learning_edge_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_empty_learning_engine_queries(temp_edge_dir):
    engine = LearningEngine(storage_dir=temp_edge_dir)
    assert engine.list_events() == []
    assert engine.get_event("non_existent_id") is None
    assert engine.list_knowledge() == []
    assert engine.get_knowledge("non_existent_id") is None
    assert engine.get_events_by_category(LearningEventType.BUG_FIXED) == []
    assert engine.get_events_by_project("non_existent_project") == []

    snapshot = engine.create_snapshot()
    assert snapshot.total_events == 0
    assert snapshot.events == []


def test_empty_reflection_engine_queries(temp_edge_dir):
    engine = ReflectionEngine(storage_dir=temp_edge_dir)
    assert engine.list_reflections() == []
    assert engine.get_reflection("non_existent_id") is None

    # Reflection on task with 0 tests
    refl = engine.reflect_on_task(
        task_id="T-ZERO",
        task_title="Zero Tests Task",
        execution_success=True,
        retries_count=0,
        tests_passed=0,
        tests_failed=0,
        prompt_length_chars=0,
        duration_seconds=0.0,
        review_score=100.0,
    )
    assert refl.test_sufficiency == "LOW" or refl.tests_sufficient is False


def test_empty_pattern_miner_operations(temp_edge_dir):
    miner = PatternMiningEngine(storage_dir=temp_edge_dir)
    # Filter for non-existent category
    res = miner.query_patterns(category="UNKNOWN_CATEGORY")
    assert res == []

    # Mine from empty event list
    mined = miner.mine_patterns_from_events([])
    assert mined == []

    # Record usage for non-existent pattern
    assert miner.record_pattern_usage("non_existent_id", True) is None or miner.record_pattern_usage("non_existent_id", True) is False


def test_prompt_optimizer_extreme_inputs(temp_edge_dir):
    optimizer = PromptOptimizationEngine(storage_dir=temp_edge_dir)

    # Empty prompt
    res_empty = optimizer.optimize_prompt("", task_type="coding", target_tokens=100)
    assert res_empty.token_count_before == 0
    assert res_empty.token_count_after == 0

    # Whitespace only
    res_ws = optimizer.optimize_prompt("   \n\n\t   ", task_type="coding", target_tokens=100)
    assert res_ws.token_count_after == 0

    # Extremely short target tokens (e.g. 5)
    long_prompt = "Line of text. " * 100
    res_short = optimizer.optimize_prompt(long_prompt, task_type="coding", target_tokens=5)
    assert res_short.token_count_after <= res_short.token_count_before

    # Huge target tokens (e.g. 100,000)
    res_huge = optimizer.optimize_prompt(long_prompt, task_type="coding", target_tokens=100000)
    assert res_huge.optimized_prompt != ""


def test_execution_analytics_empty_and_zero_values(temp_edge_dir):
    analytics = ExecutionAnalyticsEngine(storage_dir=temp_edge_dir)
    # Compute metrics with zero recorded runs
    kpis = analytics.compute_aggregate_kpis()
    assert kpis["total_runs"] == 0
    assert kpis["average_review_score"] == 0.0
    assert kpis["average_retry_count"] == 0.0

    # Query trends for non-existent project
    trends = analytics.generate_trend_series("no_such_project")
    assert trends["review_scores"] == []
    assert trends["retry_counts"] == []


def test_architecture_recommender_ambiguous_and_empty_prompts(temp_edge_dir):
    recommender = ArchitectureRecommendationEngine(storage_dir=temp_edge_dir)

    # Empty requirements
    rec_empty = recommender.recommend_architecture("EmptyProj", "")
    assert rec_empty is not None
    assert rec_empty.project_name == "EmptyProj"
    assert rec_empty.folder_structure != {}

    # Gibberish requirements
    rec_gibberish = recommender.recommend_architecture("GibberishProj", "xyz123abc 456qwe !! ??")
    assert rec_gibberish is not None
    assert rec_gibberish.archetype in [a.value for a in PlaybookArchetype]


def test_knowledge_evolution_similarity_edge_cases(temp_edge_dir):
    evo = KnowledgeEvolutionEngine(storage_dir=temp_edge_dir)

    # Both empty strings
    sim_empty = evo.calculate_text_similarity("", "")
    assert sim_empty == 1.0

    # One empty string
    sim_one = evo.calculate_text_similarity("some text", "")
    assert sim_one == 0.0

    # Identical strings
    sim_same = evo.calculate_text_similarity("identical content here", "identical content here")
    assert sim_same == 1.0

    # Unicode and special characters
    sim_unicode = evo.calculate_text_similarity("Python 🚀 async/await pattern", "Python 🚀 async/await pattern")
    assert sim_unicode == 1.0


def test_performance_evolution_zero_division_guard(temp_edge_dir):
    perf = PerformanceEvolutionEngine(storage_dir=temp_edge_dir)

    # No records
    report = perf.generate_performance_report()
    assert report["total_runs"] == 0
    assert report["latest_run"] is None

    # Single record (no previous generation to divide against)
    perf.record_run(
        version_tag="v3.1",
        stage="task_execution",
        duration_ms=100.0,
        memory_kb=2048.0,
        throughput_ops_sec=10.0,
    )
    report_single = perf.generate_performance_report()
    assert report_single["total_runs"] == 1


def test_self_improvement_planner_zero_kpi_evaluation(temp_edge_dir):
    planner = SelfImprovementPlanner(storage_dir=temp_edge_dir)

    # Evaluate with empty metrics
    plan = planner.evaluate_subsystems(
        execution_kpis={},
        reflection_reports=[],
        failure_events=[],
    )

    assert plan is not None
    assert len(plan.subsystem_health_scores) > 0
    assert plan.weakest_subsystem != ""
    assert len(plan.roadmap) > 0


def test_corrupted_json_recovery(temp_edge_dir):
    events_file = Path(temp_edge_dir) / "events.json"
    events_file.write_text("{ this is corrupted json", encoding="utf-8")

    # LearningEngine should handle corrupted JSON without crashing
    engine = LearningEngine(storage_dir=temp_edge_dir)
    assert engine.list_events() == []

    # Can now record new events safely
    ev = engine.record_event(
        category=LearningEventType.BUG_FIXED,
        summary="Recovery test event",
        project="recovery_proj",
        task_id="T-REC",
    )
    assert ev is not None
    assert len(engine.list_events()) == 1
