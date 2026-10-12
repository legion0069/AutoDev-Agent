"""
test_playbook_engine.py - AutoDev Version 3.1
Unit and integration tests for PlaybookEngine across 10 application archetypes,
best practices, common mistakes, and experience tracking.
"""

from pathlib import Path
import pytest
from core.learning.learning_models import EngineeringPlaybook, PlaybookArchetype
from core.learning.playbook_engine import PlaybookEngine


@pytest.fixture
def playbook_engine(tmp_path: Path):
    storage_dir = tmp_path / "playbooks"
    return PlaybookEngine(storage_dir=str(storage_dir), auto_persist=True)


def test_ten_default_playbooks_initialized(playbook_engine: PlaybookEngine):
    playbooks = playbook_engine.get_all_playbooks()
    assert len(playbooks) >= 10

    archetypes = {p.archetype for p in playbooks}
    expected = {
        PlaybookArchetype.REST_API,
        PlaybookArchetype.SPRING_BOOT,
        PlaybookArchetype.PYTHON_CLI,
        PlaybookArchetype.AI_AGENT,
        PlaybookArchetype.WEB_DASHBOARD,
        PlaybookArchetype.MICROSERVICES,
        PlaybookArchetype.AUTHENTICATION,
        PlaybookArchetype.CRUD_APPLICATION,
        PlaybookArchetype.EVENT_STREAMING,
        PlaybookArchetype.DISTRIBUTED_WORKER,
    }
    assert expected.issubset(archetypes)


def test_get_playbook_by_archetype(playbook_engine: PlaybookEngine):
    rest_pb = playbook_engine.get_playbook(PlaybookArchetype.REST_API)
    assert rest_pb is not None
    assert rest_pb.title == "REST API Service Playbook"
    assert len(rest_pb.recommended_sequence) >= 5
    assert len(rest_pb.best_practices) >= 3
    assert len(rest_pb.common_mistakes) >= 3
    assert rest_pb.quality_metrics["min_test_coverage_pct"] >= 90.0


def test_record_playbook_experience_success_and_failure(playbook_engine: PlaybookEngine):
    pb = playbook_engine.get_playbook(PlaybookArchetype.AI_AGENT)
    assert pb is not None
    initial_usage = pb.usage_count

    # Record 3 successes and 1 failure
    playbook_engine.record_playbook_experience(PlaybookArchetype.AI_AGENT, success=True, actual_effort_hours=4.0)
    playbook_engine.record_playbook_experience(PlaybookArchetype.AI_AGENT, success=True, actual_effort_hours=5.0)
    playbook_engine.record_playbook_experience(PlaybookArchetype.AI_AGENT, success=True, actual_effort_hours=4.5)
    updated = playbook_engine.record_playbook_experience(PlaybookArchetype.AI_AGENT, success=False, actual_effort_hours=6.0)

    assert updated is not None
    assert updated.usage_count == initial_usage + 4
    assert updated.success_rate == 0.75
    assert updated.estimated_effort_hours > 0.0


def test_custom_playbook_registration(playbook_engine: PlaybookEngine):
    custom_pb = EngineeringPlaybook(
        archetype=PlaybookArchetype.PYTHON_CLI,
        title="Custom Fast CLI Playbook",
        description="Optimized flow for single-binary Python CLI utilities.",
        recommended_sequence=["1. Argument parser", "2. Core runner", "3. Unit tests"],
        best_practices=["Zero startup latency", "Graceful SIGINT handling"],
        common_mistakes=["Heavy imports in global scope"],
        estimated_effort_hours=2.5,
    )

    registered = playbook_engine.register_playbook(custom_pb)
    assert registered.title == "Custom Fast CLI Playbook"

    fetched = playbook_engine.get_playbook(PlaybookArchetype.PYTHON_CLI)
    assert fetched is not None
    assert fetched.title == "Custom Fast CLI Playbook"
