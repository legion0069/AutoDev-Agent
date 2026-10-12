"""
tests/test_learning_pattern_mining_deep.py - In-depth Pattern Clustering, Confidence & Category Tests for AutoDev v3.1
"""

import shutil
import tempfile
from pathlib import Path
import pytest

from core.learning import (
    LearningEventType,
    PatternCategory,
    PatternMiningEngine,
)
from core.learning.learning_models import EngineeringPattern, LearningEvent


@pytest.fixture
def temp_miner_dir():
    temp_dir = tempfile.mkdtemp(prefix="autodev_pattern_mining_deep_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_deep_bug_fix_pattern_clustering(temp_miner_dir):
    miner = PatternMiningEngine(storage_dir=temp_miner_dir)

    # 3 similar bug events regarding null pointer in token parser
    events = [
        LearningEvent(
            event_id="EV-1",
            timestamp=1000.0,
            project="auth_proj",
            task_id="T-1",
            category=LearningEventType.BUG_FIXED,
            confidence=0.9,
            importance=80.0,
            summary="Fixed AttributeError: 'NoneType' object has no attribute 'decode' in token parser",
            root_cause="Null token header passed into decoder",
            solution="Added null check guard before decoding token header",
            affected_files=["auth/parser.py"],
        ),
        LearningEvent(
            event_id="EV-2",
            timestamp=1001.0,
            project="gateway_proj",
            task_id="T-2",
            category=LearningEventType.BUG_FIXED,
            confidence=0.95,
            importance=85.0,
            summary="Fixed AttributeError: 'NoneType' object has no attribute 'decode' in auth middleware",
            root_cause="Null token header passed into decoder",
            solution="Added null check guard before decoding token header",
            affected_files=["middleware/auth.py"],
        ),
    ]

    mined = miner.mine_patterns_from_events(events)
    assert len(mined) >= 1
    p = mined[0]
    assert p.category in (PatternCategory.BUG_FIX, PatternCategory.CODING_CONVENTION)
    assert "null check guard" in p.solution.lower() or "token" in p.name.lower()


def test_deep_file_layout_pattern_extraction(temp_miner_dir):
    miner = PatternMiningEngine(storage_dir=temp_miner_dir)

    file_sets = [
        ["src/core/models.py", "src/core/services.py", "src/api/routes.py", "tests/test_api.py"],
        ["src/core/models.py", "src/core/services.py", "src/api/routes.py", "tests/test_routes.py"],
        ["src/core/models.py", "src/core/services.py", "src/api/routes.py", "tests/test_service.py"],
    ]

    patterns = miner.mine_file_layout_patterns(file_sets)
    assert len(patterns) >= 1
    assert any("src/core" in p.description or "layout" in p.name.lower() for p in patterns)


def test_pattern_confidence_decay_and_reinforcement(temp_miner_dir):
    miner = PatternMiningEngine(storage_dir=temp_miner_dir)

    pat = miner.register_pattern(
        name="ReinforcementPattern",
        category=PatternCategory.PERFORMANCE,
        description="Thread-local memory pool pattern",
        solution="Reuse pre-allocated buffers across worker threads",
    )

    # Reinforce with 4 consecutive successes
    for _ in range(4):
        miner.record_pattern_usage(pat.pattern_id, success=True)

    p_updated = miner.get_pattern(pat.pattern_id)
    assert p_updated.usage_count == 4
    assert p_updated.success_rate == 1.0

    # Introduce 1 failure
    miner.record_pattern_usage(pat.pattern_id, success=False)
    p_updated = miner.get_pattern(pat.pattern_id)
    assert p_updated.usage_count == 5
    assert p_updated.success_rate == 0.80


def test_pattern_category_coverage(temp_miner_dir):
    miner = PatternMiningEngine(storage_dir=temp_miner_dir)

    categories = list(PatternCategory)
    for cat in categories:
        pat = miner.register_pattern(
            name=f"Pattern_{cat.name}",
            category=cat,
            description=f"Pattern for {cat.value}",
            solution=f"Standard solution for {cat.value}",
        )
        assert pat.category == cat

    all_pats = miner.get_all_patterns()
    assert len(all_pats) >= len(categories)


def test_top_patterns_ranking_algorithm(temp_miner_dir):
    miner = PatternMiningEngine(storage_dir=temp_miner_dir)

    p1 = miner.register_pattern("P_HighQuality", PatternCategory.ARCHITECTURAL, "High qual", "Sol")
    p2 = miner.register_pattern("P_LowQuality", PatternCategory.ARCHITECTURAL, "Low qual", "Sol")

    # Give P1 10 successes
    for _ in range(10):
        miner.record_pattern_usage(p1.pattern_id, True)

    # Give P2 10 failures
    for _ in range(10):
        miner.record_pattern_usage(p2.pattern_id, False)

    top = miner.get_top_patterns(limit=5)
    top_ids = [p.pattern_id for p in top]

    assert p1.pattern_id in top_ids
    # P1 should rank higher than P2
    if p2.pattern_id in top_ids:
        assert top_ids.index(p1.pattern_id) < top_ids.index(p2.pattern_id)
