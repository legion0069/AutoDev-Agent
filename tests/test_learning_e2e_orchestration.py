"""
tests/test_learning_e2e_orchestration.py - Comprehensive E2E Orchestration & Lifecycle Tests for AutoDev v3.1
"""

import json
import shutil
import tempfile
import time
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
from core.orchestrator import Orchestrator


@pytest.fixture
def temp_learning_dir():
    temp_dir = tempfile.mkdtemp(prefix="autodev_learning_e2e_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_e2e_master_engine_initialization(temp_learning_dir):
    engine = SelfEvolvingEngine(storage_dir=temp_learning_dir)
    assert engine is not None
    assert engine.learning_engine is not None
    assert engine.reflection_engine is not None
    assert engine.pattern_miner is not None
    assert engine.prompt_optimizer is not None
    assert engine.analytics_engine is not None
    assert engine.recommender is not None
    assert engine.playbook_engine is not None
    assert engine.planner is not None
    assert engine.knowledge_evolution is not None
    assert engine.performance_evolution is not None


def test_e2e_task_completion_lifecycle(temp_learning_dir):
    engine = SelfEvolvingEngine(storage_dir=temp_learning_dir)
    res = engine.on_task_completed(
        task_id="TASK-101",
        task_title="Build User Authentication Module",
        project_id="auth_service",
        execution_success=True,
        retries_count=1,
        tests_passed=15,
        tests_failed=0,
        prompt_text="Implement OAuth2 JWT Token Handler with Refresh Token rotation",
        duration_seconds=1.45,
        review_score=94.5,
        affected_files=["auth/jwt.py", "auth/service.py", "tests/test_jwt.py"],
        root_cause="",
        solution="Generated secure HMAC-SHA256 signing and expiration verification",
    )

    assert res["task_id"] == "TASK-101"
    assert res["project_id"] == "auth_service"
    assert res["learning_event_id"] is not None
    assert res["event_category"] == LearningEventType.BUG_FIXED.value
    assert res["prompt_efficiency_score"] >= 0.0

    # Verify event persisted
    events = engine.learning_engine.list_events()
    assert len(events) == 1
    assert events[0].task_id == "TASK-101"

    # Verify reflection generated
    reflections = engine.reflection_engine.list_reflections()
    assert len(reflections) == 1
    assert reflections[0].task_id == "TASK-101"
    assert reflections[0].execution_success is True


def test_e2e_task_failure_lifecycle(temp_learning_dir):
    engine = SelfEvolvingEngine(storage_dir=temp_learning_dir)
    res = engine.on_task_completed(
        task_id="TASK-102",
        task_title="Implement Redis Distributed Lock",
        project_id="core_cache",
        execution_success=False,
        retries_count=3,
        tests_passed=2,
        tests_failed=5,
        prompt_text="Write distributed lock using Redis SETNX",
        duration_seconds=3.2,
        review_score=45.0,
        affected_files=["cache/lock.py"],
        error_logs=["ConnectionTimeoutError: Failed connecting to redis host"],
        root_cause="Missing mock server in testing environment",
        solution="Need local in-memory fallback",
    )

    assert res["task_id"] == "TASK-102"
    assert res["event_category"] == LearningEventType.REVIEW_FAILURE.value

    # Verify reflection detected excessive retries
    reflections = engine.reflection_engine.list_reflections()
    assert any(r.excessive_retries is True for r in reflections)


def test_e2e_sprint_reflection_lifecycle(temp_learning_dir):
    engine = SelfEvolvingEngine(storage_dir=temp_learning_dir)
    refl = engine.on_sprint_completed(
        sprint_number=3,
        committed_points=40,
        completed_points=36,
        velocity_points=36,
        blockers_count=1,
        carryover_stories=1,
    )

    assert refl is not None
    assert refl.sprint_number == 3
    assert refl.planning_accuracy >= 0.8
    assert len(refl.key_takeaways) > 0

    events = engine.learning_engine.list_events()
    assert any("Sprint-3" in e.task_id for e in events)


def test_e2e_release_reflection_lifecycle(temp_learning_dir):
    engine = SelfEvolvingEngine(storage_dir=temp_learning_dir)
    refl = engine.on_release_completed(
        version="3.1.0",
        quality_gates_passed=8,
        quality_gates_total=8,
        lead_time_hours=4.5,
        postmortem_count=0,
    )

    assert refl is not None
    assert refl.release_version == "3.1.0"
    assert refl.gate_pass_rate == 100.0
    assert refl.execution_success is True

    events = engine.learning_engine.list_events()
    assert any("Release-3.1.0" in e.task_id for e in events)


def test_e2e_recommend_for_new_project_pipeline(temp_learning_dir):
    engine = SelfEvolvingEngine(storage_dir=temp_learning_dir)
    rec_bundle = engine.recommend_for_new_project(
        project_name="OrderManagementService",
        requirements="High performance REST API service with Postgres database and JWT authentication",
        domain_tags=["fintech", "ecommerce", "orders"],
    )

    assert rec_bundle["project_name"] == "OrderManagementService"
    rec = rec_bundle["recommendation"]
    assert rec["archetype"] in (
        PlaybookArchetype.REST_API.value,
        PlaybookArchetype.CRUD.value,
        PlaybookArchetype.AUTHENTICATION.value,
    )
    assert len(rec["recommended_patterns"]) > 0
    assert rec_bundle["matched_playbook"] is not None
    assert len(rec_bundle["recommended_patterns"]) > 0


def test_e2e_monthly_evolution_cycle(temp_learning_dir):
    engine = SelfEvolvingEngine(storage_dir=temp_learning_dir)

    # Seed some events
    for i in range(5):
        engine.on_task_completed(
            task_id=f"T-MONTH-{i}",
            task_title=f"Task Component {i}",
            project_id="monthly_test_proj",
            execution_success=(i != 2),
            retries_count=0 if i != 2 else 2,
            tests_passed=10,
            tests_failed=0 if i != 2 else 3,
            duration_seconds=1.0 + i * 0.2,
            review_score=95.0 if i != 2 else 60.0,
            affected_files=[f"module_{i}.py"],
        )

    cycle_res = engine.run_monthly_evolution_cycle(month_label="2026-10")

    assert cycle_res["month_label"] == "2026-10"
    assert "monthly_reflection" in cycle_res
    assert "knowledge_evolution" in cycle_res
    assert "self_improvement_plan" in cycle_res
    assert "performance_evolution" in cycle_res
    assert cycle_res["cycle_duration_ms"] >= 0.0


def test_e2e_all_eight_reports_generation(temp_learning_dir):
    engine = SelfEvolvingEngine(storage_dir=temp_learning_dir)

    # Trigger baseline activity
    engine.on_task_completed(
        task_id="T-REP-1",
        task_title="Report verification task",
        project_id="reporting_suite",
        execution_success=True,
    )

    report_bundle = engine.generate_comprehensive_learning_report()

    expected_reports = [
        "learning_report",
        "reflection_report",
        "evolution_report",
        "performance_report",
        "architecture_report",
        "prompt_improvement_report",
        "pattern_discovery_report",
        "self_improvement_roadmap",
    ]

    for rep in expected_reports:
        assert rep in report_bundle, f"Missing report: {rep}"
        assert isinstance(report_bundle[rep], dict), f"Report {rep} must be a dictionary"


def test_e2e_learning_dashboard_and_query_state(temp_learning_dir):
    engine = SelfEvolvingEngine(storage_dir=temp_learning_dir)
    engine.on_task_completed(
        task_id="T-DASH-1",
        task_title="Dashboard task test",
        project_id="dashboard_proj",
        execution_success=True,
    )

    dash = engine.get_learning_dashboard()
    assert dash["total_events"] >= 1
    assert dash["total_reflections"] >= 1
    assert dash["discovered_patterns_count"] >= 1
    assert dash["playbooks_count"] == 10
    assert "kpi_metrics" in dash
    assert len(dash["recent_events"]) >= 1


def test_e2e_prompt_optimization_integration(temp_learning_dir):
    engine = SelfEvolvingEngine(storage_dir=temp_learning_dir)
    raw_prompt = """
    Please write a clean Python module.
    Please write a clean Python module.
    Make sure to write tests.
    Make sure to write tests.
    Ensure 100% test coverage.
    """
    opt = engine.optimize_prompt(raw_prompt=raw_prompt, task_type="coding", target_tokens=500)
    assert opt.compression_ratio > 1.0 or opt.token_count_after <= opt.token_count_before
    assert len(opt.patterns_applied) >= 0


def test_e2e_orchestrator_learning_methods_integration(temp_learning_dir):
    # Verify Orchestrator proxy methods to evolving_engine
    engine = SelfEvolvingEngine(storage_dir=temp_learning_dir)
    orch = Orchestrator(evolving_engine=engine)

    # 1. recommend_architecture
    arch = orch.recommend_architecture(
        requirement="Build high-throughput REST API for financial transactions",
        domain="fintech",
    )
    assert arch["archetype"] is not None

    # 2. run_learning_cycle (task)
    task_res = orch.run_learning_cycle(
        timeframe="task",
        task_id="T-ORCH-1",
        task_title="Orchestrated Task",
        success=True,
        quality_score=92.0,
    )
    assert task_res["task_id"] == "T-ORCH-1"

    # 3. run_learning_cycle (sprint)
    sprint_res = orch.run_learning_cycle(
        timeframe="sprint",
        sprint_id="SPRINT-10",
        task_records=[],
    )
    assert sprint_res["sprint_number"] == 10

    # 4. run_learning_cycle (release)
    rel_res = orch.run_learning_cycle(
        timeframe="release",
        version="3.1.0",
        notes="GA Release",
    )
    assert rel_res["release_version"] == "3.1.0"

    # 5. get_learning_report
    rep = orch.get_learning_report()
    assert "learning_report" in rep

    # 6. query_learning_state
    q_state = orch.query_learning_state()
    assert q_state["total_events"] >= 1

    # 7. optimize_prompt
    p_opt = orch.optimize_prompt("Duplicate prompt line\nDuplicate prompt line")
    assert "optimized_prompt" in p_opt
