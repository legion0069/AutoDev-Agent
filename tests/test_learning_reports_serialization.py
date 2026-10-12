"""
tests/test_learning_reports_serialization.py - Deterministic Output, Schema Validation & Serialization Tests for AutoDev v3.1 Reports
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
    ImprovementRoadmapItem,
    LearningEvent,
    LearningKnowledge,
    LearningSession,
    LearningSnapshot,
    PerformanceEvolutionRecord,
    PromptOptimizationRecord,
    ReflectionReport,
    SelfImprovementPlan,
)


@pytest.fixture
def temp_report_dir():
    temp_dir = tempfile.mkdtemp(prefix="autodev_learning_reports_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_learning_report_schema_and_serialization(temp_report_dir):
    engine = LearningEngine(storage_dir=temp_report_dir)
    engine.record_event(
        category=LearningEventType.ARCHITECTURE_SUCCESS,
        summary="Architecture modularization success",
        project="alpha",
        task_id="T-1",
        confidence=0.95,
        importance=90.0,
    )
    snapshot = engine.create_snapshot()
    data = snapshot.to_dict()

    assert "snapshot_id" in data
    assert "total_events" in data
    assert "events_by_category" in data
    assert "events" in data
    assert isinstance(data["events"], list)
    assert len(data["events"]) == 1

    # Verify JSON serializability
    json_str = json.dumps(data)
    assert len(json_str) > 0


def test_reflection_report_schema_and_serialization(temp_report_dir):
    refl_engine = ReflectionEngine(storage_dir=temp_report_dir)
    refl = refl_engine.reflect_on_task(
        task_id="T-2",
        task_title="Review reflection schema test",
        execution_success=True,
        retries_count=0,
        tests_passed=5,
        tests_failed=0,
        prompt_length_chars=800,
        duration_seconds=1.2,
        review_score=92.0,
    )
    data = refl.to_dict()

    assert "reflection_id" in data
    assert "task_id" in data
    assert "execution_success" in data
    assert "what_worked" in data
    assert "what_failed" in data
    assert "why_analysis" in data
    assert "improvement_actions" in data
    assert isinstance(data["what_worked"], list)


def test_evolution_report_schema_and_serialization(temp_report_dir):
    evo = KnowledgeEvolutionEngine(storage_dir=temp_report_dir)
    items = [
        LearningKnowledge(
            knowledge_id="K-1",
            title="JWT token standard",
            content="Always validate exp and aud claims in JWT tokens",
            category="SECURITY",
            utility_score=95.0,
        ),
        LearningKnowledge(
            knowledge_id="K-2",
            title="JWT token verification",
            content="Always validate expiration and audience claims in JWT tokens",
            category="SECURITY",
            utility_score=80.0,
        ),
    ]

    res = evo.evolve_knowledge_base(items)
    assert "merged_count" in res
    assert "archived_count" in res
    assert "promoted_count" in res
    assert "remaining_knowledge_count" in res

    data = evo.to_dict()
    assert "total_merged" in data
    assert "total_archived" in data
    assert "total_promoted" in data


def test_performance_report_schema_and_serialization(temp_report_dir):
    perf = PerformanceEvolutionEngine(storage_dir=temp_report_dir)
    perf.record_run(
        version_tag="v3.0",
        stage="planning",
        duration_ms=250.0,
        memory_kb=4096.0,
        throughput_ops_sec=4.0,
    )
    perf.record_run(
        version_tag="v3.1",
        stage="planning",
        duration_ms=180.0,
        memory_kb=3500.0,
        throughput_ops_sec=5.5,
    )

    report = perf.generate_performance_report()
    assert "total_runs" in report
    assert "latest_run" in report
    assert "generational_speedup" in report
    assert "memory_delta_pct" in report


def test_architecture_report_schema_and_serialization(temp_report_dir):
    arch_engine = ArchitectureRecommendationEngine(storage_dir=temp_report_dir)
    rec = arch_engine.recommend_architecture(
        project_name="DataPipeline",
        requirements="ETL event-driven pipeline processing kafka messages with sqlite checkpointing",
        domain_tags=["data", "events", "etl"],
    )
    data = rec.to_dict()

    assert "recommendation_id" in data
    assert "project_name" in data
    assert "archetype" in data
    assert "folder_structure" in data
    assert "design_patterns" in data
    assert "database_recommendation" in data
    assert "api_style" in data
    assert "testing_strategy" in data
    assert "security_model" in data


def test_prompt_improvement_report_schema_and_serialization(temp_report_dir):
    opt_engine = PromptOptimizationEngine(storage_dir=temp_report_dir)
    opt_engine.optimize_prompt("Test prompt\nTest prompt\nInstructions", task_type="coding")
    report = opt_engine.generate_prompt_report()

    assert "total_prompts_optimized" in report
    assert "average_compression_ratio" in report
    assert "average_tokens_saved" in report
    assert "available_templates" in report


def test_pattern_discovery_report_schema_and_serialization(temp_report_dir):
    miner = PatternMiningEngine(storage_dir=temp_report_dir)
    patterns = miner.get_all_patterns()
    data = miner.to_dict()

    assert "total_patterns" in data
    assert "patterns_by_category" in data
    assert "patterns" in data
    assert len(data["patterns"]) >= 1


def test_self_improvement_roadmap_schema_and_serialization(temp_report_dir):
    planner = SelfImprovementPlanner(storage_dir=temp_report_dir)
    plan = planner.evaluate_subsystems(
        execution_kpis={"average_retry_count": 2.5, "average_review_score": 70.0},
        reflection_reports=[],
        failure_events=[],
    )
    report = planner.generate_roadmap_report()

    assert "total_plans" in report
    assert "latest_plan" in report
    assert "active_roadmap_items" in report
    assert "subsystem_health_scores" in report["latest_plan"]


def test_deterministic_json_output_consistency(temp_report_dir):
    # Running identical deterministic recommendation produces consistent serialized results
    arch1 = ArchitectureRecommendationEngine(storage_dir=temp_report_dir)
    rec1 = arch1.recommend_architecture(
        project_name="DeterministicTest",
        requirements="REST API with JWT Authentication and PostgreSQL database",
    )

    arch2 = ArchitectureRecommendationEngine(storage_dir=temp_report_dir)
    rec2 = arch2.recommend_architecture(
        project_name="DeterministicTest",
        requirements="REST API with JWT Authentication and PostgreSQL database",
    )

    assert rec1.archetype == rec2.archetype
    assert rec1.database_recommendation == rec2.database_recommendation
    assert rec1.api_style == rec2.api_style
    assert rec1.design_patterns == rec2.design_patterns
