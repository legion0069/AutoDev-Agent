"""
test_learning_engine.py - AutoDev Version 3.1
Unit and integration tests for LearningEngine, event indexing, session tracking,
snapshot generation, and JSON persistence.
"""

from pathlib import Path
import pytest
from core.learning.learning_engine import LearningEngine
from core.learning.learning_models import (
    LearningEvent,
    LearningEventType,
    LearningKnowledge,
)


@pytest.fixture
def temp_learning_engine(tmp_path: Path):
    storage_dir = tmp_path / "learning"
    engine = LearningEngine(storage_dir=str(storage_dir), auto_persist=True)
    return engine


def test_record_single_event(temp_learning_engine: LearningEngine):
    event = temp_learning_engine.record_event(
        category=LearningEventType.BUG_FIXED,
        summary="Fixed race condition in connection pool",
        project="PaymentService",
        task_id="TASK-01",
        confidence=0.95,
        importance=85.0,
        affected_files=["db/pool.py"],
        root_cause="Unsynchronized access",
        solution="Added lock lease",
        metrics={"latency_reduction_pct": 18.5},
        tags=["db", "concurrency"],
    )

    assert event.id.startswith("EVT-")
    assert event.category == LearningEventType.BUG_FIXED
    assert event.project == "PaymentService"

    events = temp_learning_engine.get_all_events()
    assert len(events) == 1
    assert events[0].id == event.id


def test_query_events_by_category(temp_learning_engine: LearningEngine):
    temp_learning_engine.record_event(
        category=LearningEventType.BUG_FIXED,
        summary="Bug 1",
        project="ProjA",
    )
    temp_learning_engine.record_event(
        category=LearningEventType.ARCHITECTURE_SUCCESS,
        summary="Arch 1",
        project="ProjA",
    )
    temp_learning_engine.record_event(
        category=LearningEventType.BUG_FIXED,
        summary="Bug 2",
        project="ProjB",
    )

    bug_events = temp_learning_engine.query_events(category=LearningEventType.BUG_FIXED)
    assert len(bug_events) == 2

    arch_events = temp_learning_engine.query_events(category=LearningEventType.ARCHITECTURE_SUCCESS)
    assert len(arch_events) == 1


def test_query_events_by_project_and_filters(temp_learning_engine: LearningEngine):
    temp_learning_engine.record_event(
        category=LearningEventType.PATTERN_DISCOVERED,
        summary="High importance pattern",
        project="CoreEngine",
        confidence=0.95,
        importance=90.0,
        tags=["pattern", "core"],
    )
    temp_learning_engine.record_event(
        category=LearningEventType.PATTERN_DISCOVERED,
        summary="Low importance pattern",
        project="CoreEngine",
        confidence=0.60,
        importance=40.0,
        tags=["experimental"],
    )

    filtered = temp_learning_engine.query_events(
        project="CoreEngine",
        min_importance=80.0,
        min_confidence=0.90,
    )
    assert len(filtered) == 1
    assert filtered[0].summary == "High importance pattern"

    tag_filtered = temp_learning_engine.query_events(tags=["core"])
    assert len(tag_filtered) == 1


def test_learning_session_lifecycle(temp_learning_engine: LearningEngine):
    session = temp_learning_engine.start_session(project="AuthService")
    assert session.session_id.startswith("SESS-")
    assert session.project == "AuthService"

    evt1 = temp_learning_engine.record_event(
        category=LearningEventType.TEST_STRATEGY,
        summary="Added parameterized mock tests",
        project="AuthService",
    )
    temp_learning_engine.add_event_to_session(session.session_id, evt1)

    closed_session = temp_learning_engine.close_session(session.session_id)
    assert closed_session is not None
    assert len(closed_session.events) == 1
    assert closed_session.metrics["events_count"] == 1


def test_learning_snapshot_creation(temp_learning_engine: LearningEngine):
    temp_learning_engine.record_event(
        category=LearningEventType.BUG_FIXED,
        summary="Fixed off-by-one error",
        project="Inventory",
        confidence=0.90,
    )
    temp_learning_engine.record_event(
        category=LearningEventType.PERFORMANCE_IMPROVEMENT,
        summary="Optimized hash lookup",
        project="Inventory",
        confidence=0.94,
    )

    snapshot = temp_learning_engine.create_snapshot(project="Inventory")
    assert snapshot.project == "Inventory"
    assert snapshot.total_events == 2
    assert snapshot.categories_count["BUG_FIXED"] == 1
    assert snapshot.categories_count["PERFORMANCE_IMPROVEMENT"] == 1
    assert snapshot.average_confidence == 0.92

    latest = temp_learning_engine.get_latest_snapshot("Inventory")
    assert latest is not None
    assert latest.snapshot_id == snapshot.snapshot_id


def test_knowledge_recording_and_retrieval(temp_learning_engine: LearningEngine):
    k = temp_learning_engine.record_knowledge(
        domain="Security",
        topic="JWT Validation",
        summary="Always enforce issuer and audience verification in JWT middleware.",
        details="Prevents token spoofing across different microservices sharing keys.",
        evidence_events=["EVT-SEC-01"],
        confidence=0.99,
        utility_score=95.0,
        promoted=True,
    )

    assert k.knowledge_id.startswith("KN-")
    assert k.promoted is True

    queried = temp_learning_engine.query_knowledge(domain="Security", min_utility=90.0)
    assert len(queried) == 1
    assert queried[0].topic == "JWT Validation"


def test_persistence_reload(tmp_path: Path):
    storage_dir = tmp_path / "persist_learning"
    engine1 = LearningEngine(storage_dir=str(storage_dir), auto_persist=True)
    engine1.record_event(
        category=LearningEventType.REFACTOR_SUCCESS,
        summary="Extracted domain entities",
        project="Billing",
        task_id="T-BILL-10",
    )
    engine1.record_knowledge(
        domain="Refactoring",
        topic="Domain Isolation",
        summary="Keep business entities free of framework imports.",
    )

    # Re-instantiate from same storage directory
    engine2 = LearningEngine(storage_dir=str(storage_dir), auto_persist=True)
    events = engine2.get_all_events()
    assert len(events) == 1
    assert events[0].summary == "Extracted domain entities"
    assert events[0].project == "Billing"

    knowledge_list = engine2.get_all_knowledge()
    assert len(knowledge_list) == 1
    assert knowledge_list[0].topic == "Domain Isolation"


def test_summary_and_stats(temp_learning_engine: LearningEngine):
    temp_learning_engine.record_event(
        category=LearningEventType.BUG_FIXED,
        summary="Bug fix",
        project="P1",
    )
    summary = temp_learning_engine.get_learning_summary()
    assert summary["total_events"] == 1
    assert summary["categories"]["BUG_FIXED"] == 1
