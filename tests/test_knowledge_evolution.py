"""
test_knowledge_evolution.py - AutoDev Version 3.1
Unit and integration tests for KnowledgeEvolutionEngine, Jaccard similarity,
memory merging, stale archiving, and standard promotion.
"""

from pathlib import Path
import pytest
from core.learning.knowledge_evolution import KnowledgeEvolutionEngine
from core.learning.learning_models import LearningKnowledge


@pytest.fixture
def evolution_engine(tmp_path: Path):
    storage_dir = tmp_path / "knowledge_evolution"
    return KnowledgeEvolutionEngine(storage_dir=str(storage_dir), auto_persist=True)


def test_jaccard_similarity_calculation(evolution_engine: KnowledgeEvolutionEngine):
    t1 = "Always sanitize user inputs to prevent SQL injection."
    t2 = "Always sanitize user inputs to prevent SQL injection."
    assert evolution_engine.calculate_text_similarity(t1, t2) == pytest.approx(1.0, 0.01)

    t3 = "Always sanitize user inputs before executing SQL database queries."
    sim = evolution_engine.calculate_text_similarity(t1, t3)
    assert sim >= 0.60

    t4 = "Completely different text about graphical user interface CSS colors."
    assert evolution_engine.calculate_text_similarity(t1, t4) < 0.15


def test_merge_duplicate_knowledge_items(evolution_engine: KnowledgeEvolutionEngine):
    k1 = LearningKnowledge(
        knowledge_id="KN-01",
        domain="Database",
        topic="Connection Pooling",
        summary="Always configure min and max connection pool limits for database sockets.",
        details="Prevents resource starvation on database cluster.",
        evidence_events=["EVT-01"],
        confidence=0.85,
        utility_score=75.0,
    )
    k2 = LearningKnowledge(
        knowledge_id="KN-02",
        domain="Database",
        topic="Connection Pool Configuration",
        summary="Always configure min and max connection pool limits for database connection sockets.",
        details="Avoids connection exhaustion under high traffic load.",
        evidence_events=["EVT-02"],
        confidence=0.90,
        utility_score=80.0,
    )

    merged_list = evolution_engine.merge_similar_knowledge([k1, k2], similarity_threshold=0.60)
    assert len(merged_list) == 1

    merged = merged_list[0]
    assert set(merged.evidence_events) == {"EVT-01", "EVT-02"}
    assert merged.confidence >= 0.90
    assert merged.utility_score >= 80.0


def test_archive_obsolete_knowledge(evolution_engine: KnowledgeEvolutionEngine):
    stale_item = LearningKnowledge(
        knowledge_id="KN-OLD",
        domain="Legacy",
        topic="Python 2 compatibility",
        summary="Use unicode literals for python 2 string compatibility.",
        confidence=0.40,
        utility_score=25.0,
    )
    fresh_item = LearningKnowledge(
        knowledge_id="KN-NEW",
        domain="Async",
        topic="AsyncIO Gather",
        summary="Use asyncio.TaskGroup in Python 3.11+ for structured concurrency.",
        confidence=0.95,
        utility_score=90.0,
    )

    active, archived = evolution_engine.archive_obsolete_knowledge(
        [stale_item, fresh_item],
        utility_threshold=40.0,
        confidence_threshold=0.50,
    )

    assert len(active) == 1
    assert active[0].knowledge_id == "KN-NEW"
    assert len(archived) == 1
    assert archived[0].knowledge_id == "KN-OLD"


def test_promote_high_utility_standards(evolution_engine: KnowledgeEvolutionEngine):
    item1 = LearningKnowledge(
        knowledge_id="KN-STD-01",
        domain="Architecture",
        topic="SOLID Principles",
        summary="Strict dependency inversion via interfaces.",
        confidence=0.98,
        utility_score=95.0,
        promoted=False,
    )
    item2 = LearningKnowledge(
        knowledge_id="KN-DRAFT-01",
        domain="Architecture",
        topic="Draft note",
        summary="Experimental caching spike.",
        confidence=0.70,
        utility_score=60.0,
        promoted=False,
    )

    promoted = evolution_engine.promote_high_utility_standards([item1, item2], min_utility=90.0, min_confidence=0.95)
    assert len(promoted) == 1
    assert promoted[0].knowledge_id == "KN-STD-01"
    assert promoted[0].promoted is True


def test_full_knowledge_evolution_cycle(evolution_engine: KnowledgeEvolutionEngine):
    items = [
        LearningKnowledge(
            knowledge_id="KN-1",
            domain="Security",
            topic="Password Hashing",
            summary="Always use bcrypt or argon2 with unique salt for password hashing.",
            confidence=0.96,
            utility_score=95.0,
        ),
        LearningKnowledge(
            knowledge_id="KN-2",
            domain="Security",
            topic="Password Hashing Standard",
            summary="Always use bcrypt or argon2 with unique salt for password storage hashing.",
            confidence=0.92,
            utility_score=90.0,
        ),
        LearningKnowledge(
            knowledge_id="KN-3",
            domain="Misc",
            topic="Obsolete workarounds",
            summary="Old workaround for defunct library.",
            confidence=0.30,
            utility_score=20.0,
        ),
    ]

    report = evolution_engine.run_knowledge_evolution_cycle(items)
    assert report["initial_count"] == 3
    assert report["merged_count"] >= 1
    assert report["archived_count"] >= 1
    assert report["promoted_count"] >= 1
    assert report["final_active_count"] >= 1
