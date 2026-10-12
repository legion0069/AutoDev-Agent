"""
test_pattern_miner.py - AutoDev Version 3.1
Unit and integration tests for PatternMiningEngine, clustering of bug fixes,
layout discovery, pattern registration, confidence scoring, and usage tracking.
"""

from pathlib import Path
import pytest
from core.learning.learning_models import (
    EngineeringPattern,
    LearningEvent,
    LearningEventType,
    PatternCategory,
)
from core.learning.pattern_miner import PatternMiningEngine


@pytest.fixture
def pattern_miner(tmp_path: Path):
    storage_dir = tmp_path / "patterns"
    return PatternMiningEngine(storage_dir=str(storage_dir), auto_persist=True)


def test_register_and_query_pattern(pattern_miner: PatternMiningEngine):
    pat = pattern_miner.register_pattern(
        name="Outbox Pattern for Reliable Messaging",
        category=PatternCategory.ARCHITECTURE,
        description="Persist events in SQL table before asynchronous publish.",
        structure_template={"models": "domain/outbox.py", "publisher": "infra/outbox_publisher.py"},
        applicable_scenarios=["Event-Driven Microservices"],
        confidence=0.95,
        quality_score=94.0,
        tags=["outbox", "messaging"],
    )

    assert pat.id.startswith("PAT-")
    assert pat.category == PatternCategory.ARCHITECTURE

    found = pattern_miner.query_patterns(category=PatternCategory.ARCHITECTURE)
    assert len(found) >= 1
    assert any(p.name == "Outbox Pattern for Reliable Messaging" for p in found)


def test_mine_patterns_from_bug_fix_events(pattern_miner: PatternMiningEngine):
    events = [
        LearningEvent(
            category=LearningEventType.BUG_FIXED,
            summary="Fixed connection leak by using context manager",
            root_cause="Open connection unclosed on error",
            solution="Wrap cursor in 'with connection:' block",
            affected_files=["db/repo.py"],
            confidence=0.92,
        ),
        LearningEvent(
            category=LearningEventType.BUG_FIXED,
            summary="Fixed file descriptor leak with with-block",
            root_cause="File handle left open after exception",
            solution="Wrap file open in with-statement context manager",
            affected_files=["io/reader.py"],
            confidence=0.90,
        ),
    ]

    mined = pattern_miner.mine_patterns_from_events(events)
    assert len(mined) > 0
    assert any(p.category == PatternCategory.BUG_FIX for p in mined)


def test_mine_file_layout_patterns(pattern_miner: PatternMiningEngine):
    sample_files = [
        "core/services/auth_service.py",
        "core/repositories/user_repo.py",
        "core/models/user.py",
        "api/controllers/auth_controller.py",
        "tests/unit/test_auth_service.py",
    ]

    pattern = pattern_miner.mine_file_layout_patterns("Clean Architecture Layout", sample_files)
    assert pattern is not None
    assert pattern.category == PatternCategory.FILE_LAYOUT
    assert "core" in pattern.structure_template
    assert "tests" in pattern.structure_template


def test_record_pattern_usage_and_success_rate(pattern_miner: PatternMiningEngine):
    pat = pattern_miner.register_pattern(
        name="Retry with Exponential Backoff",
        category=PatternCategory.API_DESIGN,
        description="Retry transient network failures with jittered backoff.",
        confidence=0.80,
    )

    # Record 3 successful uses and 1 failure
    pattern_miner.record_pattern_usage(pat.id, success=True)
    pattern_miner.record_pattern_usage(pat.id, success=True)
    pattern_miner.record_pattern_usage(pat.id, success=True)
    updated = pattern_miner.record_pattern_usage(pat.id, success=False)

    assert updated is not None
    assert updated.usage_count == 4
    assert updated.success_rate == 0.75
    assert updated.confidence > 0.80  # Increased due to usage frequency


def test_query_patterns_filtering(pattern_miner: PatternMiningEngine):
    pattern_miner.register_pattern(
        name="High Quality Arch",
        category=PatternCategory.ARCHITECTURE,
        description="P1",
        confidence=0.95,
        quality_score=98.0,
        tags=["enterprise"],
    )
    pattern_miner.register_pattern(
        name="Low Quality Draft",
        category=PatternCategory.ARCHITECTURE,
        description="P2",
        confidence=0.50,
        quality_score=60.0,
        tags=["draft"],
    )

    results = pattern_miner.query_patterns(
        category=PatternCategory.ARCHITECTURE,
        min_confidence=0.90,
        min_quality=90.0,
        tags=["enterprise"],
    )
    assert len(results) == 1
    assert results[0].name == "High Quality Arch"


def test_default_patterns_preloaded(pattern_miner: PatternMiningEngine):
    all_patterns = pattern_miner.get_all_patterns()
    # Ensure default patterns exist
    assert len(all_patterns) >= 3
    categories = {p.category for p in all_patterns}
    assert PatternCategory.ARCHITECTURE in categories
    assert PatternCategory.API_DESIGN in categories
