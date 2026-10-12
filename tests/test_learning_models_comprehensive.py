"""
tests/test_learning_models_comprehensive.py - Comprehensive Unit Tests for Models, Aliases, Dataclasses & Enums in v3.1
"""

import time
import pytest

from core.learning.learning_models import (
    ArchitectureRecommendation,
    EngineeringPattern,
    EngineeringPlaybook,
    ImprovementArea,
    ImprovementRoadmapItem,
    LearningEvent,
    LearningEventType,
    LearningKnowledge,
    LearningSession,
    LearningSnapshot,
    PatternCategory,
    PerformanceEvolutionRecord,
    PlaybookArchetype,
    PromptOptimizationRecord,
    ReflectionReport,
    ReflectionScope,
    SelfImprovementPlan,
)


def test_learning_event_dual_properties():
    ev = LearningEvent(
        event_id="EV-100",
        timestamp=12345.67,
        project="demo",
        task_id="T-100",
        category=LearningEventType.BUG_FIXED,
        confidence=0.9,
        importance=85.0,
        summary="Fixed bug in parser",
        affected_files=["parser.py"],
        root_cause="NoneType error",
        solution="Guard clause",
        metrics={"duration": 1.5},
        tags=["bug", "parser"],
    )

    # Test aliases
    assert ev.id == "EV-100"
    assert ev.task == "T-100"
    assert ev.files == ["parser.py"]
    assert ev.key_metrics == {"duration": 1.5}

    # Test to_dict and from_dict
    d = ev.to_dict()
    assert d["event_id"] == "EV-100"
    assert d["id"] == "EV-100"
    assert d["task_id"] == "T-100"
    assert d["task"] == "T-100"

    rebuilt = LearningEvent.from_dict(d)
    assert rebuilt.event_id == "EV-100"
    assert rebuilt.category == LearningEventType.BUG_FIXED


def test_learning_session_dual_properties():
    sess = LearningSession(
        session_id="SESS-1",
        project_id="demo_proj",
        start_time=100.0,
        end_time=200.0,
        events=["EV-1", "EV-2"],
        summary="Session completed",
    )

    assert sess.id == "SESS-1"
    assert sess.project == "demo_proj"

    d = sess.to_dict()
    assert d["session_id"] == "SESS-1"
    assert d["id"] == "SESS-1"

    rebuilt = LearningSession.from_dict(d)
    assert rebuilt.session_id == "SESS-1"
    assert rebuilt.events == ["EV-1", "EV-2"]


def test_learning_snapshot_dual_properties():
    ev = LearningEvent(
        event_id="EV-1",
        timestamp=100.0,
        project="demo",
        task_id="T-1",
        category=LearningEventType.ARCHITECTURE_SUCCESS,
        confidence=0.9,
        importance=80.0,
        summary="Arch event",
    )
    snap = LearningSnapshot(
        snapshot_id="SNAP-1",
        timestamp=100.0,
        total_events=1,
        events_by_category={"ARCHITECTURE_SUCCESS": 1},
        events=[ev],
    )

    assert snap.id == "SNAP-1"
    d = snap.to_dict()
    assert d["snapshot_id"] == "SNAP-1"

    rebuilt = LearningSnapshot.from_dict(d)
    assert rebuilt.snapshot_id == "SNAP-1"
    assert len(rebuilt.events) == 1
    assert rebuilt.events[0].event_id == "EV-1"


def test_learning_knowledge_dual_properties():
    k = LearningKnowledge(
        knowledge_id="K-1",
        title="Testing Rule",
        content="Always write unit tests for public APIs",
        category="TESTING",
        confidence=0.95,
        utility_score=90.0,
        created_at=100.0,
        last_applied=105.0,
        usage_count=5,
        status="ACTIVE",
    )

    assert k.id == "K-1"
    d = k.to_dict()
    assert d["knowledge_id"] == "K-1"
    assert d["id"] == "K-1"

    rebuilt = LearningKnowledge.from_dict(d)
    assert rebuilt.knowledge_id == "K-1"
    assert rebuilt.status == "ACTIVE"


def test_engineering_pattern_dual_properties():
    p = EngineeringPattern(
        pattern_id="PAT-1",
        name="RepositoryPattern",
        category=PatternCategory.ARCHITECTURAL,
        description="Encapsulates data access",
        solution="Use repository interface and concrete DB adapter",
        usage_count=10,
        confidence=0.92,
        quality_score=95.0,
        success_rate=0.90,
    )

    assert p.id == "PAT-1"
    assert p.pattern_name == "RepositoryPattern"

    d = p.to_dict()
    assert d["pattern_id"] == "PAT-1"
    assert d["name"] == "RepositoryPattern"

    rebuilt = EngineeringPattern.from_dict(d)
    assert rebuilt.pattern_id == "PAT-1"
    assert rebuilt.category == PatternCategory.ARCHITECTURAL


def test_reflection_report_dual_properties():
    r = ReflectionReport(
        reflection_id="REFL-1",
        scope=ReflectionScope.TASK,
        timestamp=100.0,
        task_id="T-1",
        task_title="Task 1",
        execution_success=True,
        what_worked=["Fast execution", "High test coverage"],
        what_failed=[],
        why_analysis="Clean architecture and clear prompt",
        improvement_actions=["Continue using modular design"],
        retries_count=0,
        excessive_retries=False,
        planning_accuracy=1.0,
        tests_sufficient=True,
        prompt_bloated=False,
    )

    assert r.id == "REFL-1"
    assert r.task == "T-1"
    assert r.success is True

    d = r.to_dict()
    assert d["reflection_id"] == "REFL-1"
    assert d["scope"] == ReflectionScope.TASK.value

    rebuilt = ReflectionReport.from_dict(d)
    assert rebuilt.reflection_id == "REFL-1"
    assert rebuilt.scope == ReflectionScope.TASK


def test_architecture_recommendation_dual_properties():
    rec = ArchitectureRecommendation(
        recommendation_id="REC-1",
        project_name="OrderService",
        archetype=PlaybookArchetype.REST_API.value,
        folder_structure={"src": ["api", "models", "services"]},
        design_patterns=["Repository Pattern", "Dependency Injection"],
        database_recommendation="PostgreSQL",
        api_style="RESTful JSON",
        testing_strategy="Pytest with unit and integration fixtures",
        security_model="JWT Bearer Token with RBAC",
        confidence=0.94,
    )

    assert rec.id == "REC-1"
    assert rec.structure == {"src": ["api", "models", "services"]}

    d = rec.to_dict()
    assert d["recommendation_id"] == "REC-1"
    assert d["project_name"] == "OrderService"

    rebuilt = ArchitectureRecommendation.from_dict(d)
    assert rebuilt.recommendation_id == "REC-1"
    assert rebuilt.database_recommendation == "PostgreSQL"


def test_engineering_playbook_dual_properties():
    pb = EngineeringPlaybook(
        playbook_id="PB-1",
        archetype=PlaybookArchetype.CRUD,
        name="CRUD Application Playbook",
        description="Standard CRUD patterns",
        recommended_sequence=["Define schema", "Build repository", "Add endpoints", "Write tests"],
        best_practices=["Validate input", "Use transactions"],
        common_mistakes=["Missing pagination", "N+1 query issue"],
        estimated_effort_hours=4.0,
        quality_threshold=85.0,
    )

    assert pb.id == "PB-1"
    d = pb.to_dict()
    assert d["playbook_id"] == "PB-1"
    assert d["archetype"] == PlaybookArchetype.CRUD.value

    rebuilt = EngineeringPlaybook.from_dict(d)
    assert rebuilt.playbook_id == "PB-1"
    assert rebuilt.archetype == PlaybookArchetype.CRUD


def test_self_improvement_plan_dual_properties():
    item = ImprovementRoadmapItem(
        item_id="ROAD-1",
        area=ImprovementArea.TESTING,
        title="Enhance Mock Coverage",
        description="Increase unit test coverage on external APIs",
        priority="HIGH",
        estimated_roi=0.85,
        target_subsystem="TesterAgent",
        status="PLANNED",
    )
    plan = SelfImprovementPlan(
        plan_id="PLAN-1",
        timestamp=100.0,
        evaluation_period="2026-10",
        weakest_subsystem="Testing",
        subsystem_health_scores={"Testing": 65.0, "Orchestration": 95.0},
        roadmap=[item],
        improvement_summary="Focusing on test coverage",
    )

    assert plan.id == "PLAN-1"
    d = plan.to_dict()
    assert d["plan_id"] == "PLAN-1"
    assert len(d["roadmap"]) == 1
    assert d["roadmap"][0]["item_id"] == "ROAD-1"

    rebuilt = SelfImprovementPlan.from_dict(d)
    assert rebuilt.plan_id == "PLAN-1"
    assert len(rebuilt.roadmap) == 1
    assert rebuilt.roadmap[0].area == ImprovementArea.TESTING


def test_performance_evolution_record_dual_properties():
    rec = PerformanceEvolutionRecord(
        record_id="PERF-1",
        timestamp=100.0,
        version_tag="v3.1",
        stage="task_execution",
        duration_ms=45.2,
        memory_kb=1024.0,
        throughput_ops_sec=22.1,
        planning_latency_ms=12.0,
        review_latency_ms=15.0,
        generation_latency_ms=18.2,
    )

    assert rec.id == "PERF-1"
    d = rec.to_dict()
    assert d["record_id"] == "PERF-1"
    assert d["version_tag"] == "v3.1"

    rebuilt = PerformanceEvolutionRecord.from_dict(d)
    assert rebuilt.record_id == "PERF-1"
    assert rebuilt.duration_ms == 45.2
