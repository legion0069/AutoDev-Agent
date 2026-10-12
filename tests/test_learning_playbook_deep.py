"""
tests/test_learning_playbook_deep.py - In-depth Verification for All 10 Engineering Playbooks (v3.1)
"""

import shutil
import tempfile
from pathlib import Path
import pytest

from core.learning import PlaybookArchetype, PlaybookEngine
from core.learning.learning_models import EngineeringPlaybook


@pytest.fixture
def temp_playbook_dir():
    temp_dir = tempfile.mkdtemp(prefix="autodev_playbook_deep_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_all_ten_archetypes_present_and_valid(temp_playbook_dir):
    engine = PlaybookEngine(storage_dir=temp_playbook_dir)
    playbooks = engine.list_playbooks()
    assert len(playbooks) == 10

    archetype_set = {p.archetype for p in playbooks}
    expected_archetypes = {
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

    assert archetype_set == expected_archetypes


def test_playbook_structure_and_content_quality(temp_playbook_dir):
    engine = PlaybookEngine(storage_dir=temp_playbook_dir)
    playbooks = engine.list_playbooks()

    for pb in playbooks:
        assert pb.name != ""
        assert pb.description != ""
        assert len(pb.recommended_sequence) >= 3, f"Playbook {pb.name} lacks steps in sequence"
        assert len(pb.best_practices) >= 2, f"Playbook {pb.name} lacks best practices"
        assert len(pb.common_mistakes) >= 2, f"Playbook {pb.name} lacks common mistakes"
        assert pb.estimated_effort_hours > 0.0
        assert pb.quality_threshold >= 75.0


def test_rest_api_playbook_details(temp_playbook_dir):
    engine = PlaybookEngine(storage_dir=temp_playbook_dir)
    pb = engine.get_playbook(PlaybookArchetype.REST_API)
    assert pb is not None
    assert any("route" in step.lower() or "schema" in step.lower() or "model" in step.lower() for step in pb.recommended_sequence)
    assert any("pydantic" in bp.lower() or "validation" in bp.lower() for bp in pb.best_practices)


def test_ai_agent_playbook_details(temp_playbook_dir):
    engine = PlaybookEngine(storage_dir=temp_playbook_dir)
    pb = engine.get_playbook(PlaybookArchetype.AI_AGENT)
    assert pb is not None
    assert any("tool" in step.lower() or "prompt" in step.lower() for step in pb.recommended_sequence)
    assert any("deterministic" in bp.lower() or "guardrail" in bp.lower() or "timeout" in bp.lower() for bp in pb.best_practices)


def test_microservices_playbook_details(temp_playbook_dir):
    engine = PlaybookEngine(storage_dir=temp_playbook_dir)
    pb = engine.get_playbook(PlaybookArchetype.MICROSERVICES)
    assert pb is not None
    assert any("isolation" in bp.lower() or "contract" in bp.lower() or "correlation" in bp.lower() or "idempotent" in bp.lower() for bp in pb.best_practices)


def test_playbook_experience_accumulation(temp_playbook_dir):
    engine = PlaybookEngine(storage_dir=temp_playbook_dir)
    pb = engine.get_playbook(PlaybookArchetype.WEB_DASHBOARD)
    initial_usage = pb.usage_count

    # Simulate 3 successful project executions
    engine.record_playbook_experience(
        archetype=PlaybookArchetype.WEB_DASHBOARD,
        success=True,
        duration_minutes=25.0,
        review_score=95.0,
    )
    engine.record_playbook_experience(
        archetype=PlaybookArchetype.WEB_DASHBOARD,
        success=True,
        duration_minutes=20.0,
        review_score=92.0,
    )
    engine.record_playbook_experience(
        archetype=PlaybookArchetype.WEB_DASHBOARD,
        success=False,
        duration_minutes=35.0,
        review_score=60.0,
    )

    updated_pb = engine.get_playbook(PlaybookArchetype.WEB_DASHBOARD)
    assert updated_pb.usage_count == initial_usage + 3
    assert updated_pb.success_rate == pytest.approx(2.0 / 3.0, rel=1e-2)
