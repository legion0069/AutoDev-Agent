"""
Deep tests for Knowledge Evolution Engine (token similarity, deduplication, utility ranking, promotion, and archiving).
"""
import pytest
import os
import shutil
import tempfile
import time
from typing import List

from core.learning.learning_models import LearningKnowledge
from core.learning.knowledge_evolution import KnowledgeEvolutionEngine


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="autodev_test_knw_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_similarity_calculation_variations(temp_dir):
    ke = KnowledgeEvolutionEngine(storage_dir=temp_dir)
    
    # Identical
    assert ke.calculate_similarity("Use FastAPI with Pydantic models", "Use FastAPI with Pydantic models") == 1.0
    
    # High similarity
    sim_high = ke.calculate_similarity(
        "Always use FastAPI routers with Pydantic schemas for request validation",
        "Use FastAPI routers and Pydantic schemas for input request validation"
    )
    assert sim_high > 0.60
    
    # Low similarity
    sim_low = ke.calculate_similarity(
        "Deploy PostgreSQL on Kubernetes cluster",
        "Configure CSS flexbox responsive layout"
    )
    assert sim_low < 0.20


def test_merge_two_similar_knowledge_items(temp_dir):
    ke = KnowledgeEvolutionEngine(storage_dir=temp_dir)
    
    k1 = LearningKnowledge(
        id="KNW-1",
        domain="Database",
        title="PostgreSQL Index Optimization",
        summary="Add B-Tree indices on frequently queried foreign keys to reduce seq scans",
        evidence_events=["EVT-101", "EVT-102"],
        utility_score=60.0,
        usage_count=3
    )
    k2 = LearningKnowledge(
        id="KNW-2",
        domain="Database",
        title="PostgreSQL Query Indexing Strategy",
        summary="Create B-Tree indexes on foreign keys to eliminate sequential scans on joins",
        evidence_events=["EVT-103", "EVT-104"],
        utility_score=75.0,
        usage_count=5
    )
    
    ke.add_knowledge(k1)
    ke.add_knowledge(k2)
    
    merged_list = ke.consolidate_and_deduplicate()
    assert len(merged_list) == 1
    
    merged = merged_list[0]
    assert "EVT-101" in merged.evidence_events or "EVT-101" in merged.source_events
    assert "EVT-103" in merged.evidence_events or "EVT-103" in merged.source_events
    assert merged.usage_count >= 8
    assert merged.utility_score >= 70.0


def test_promote_high_utility_knowledge(temp_dir):
    ke = KnowledgeEvolutionEngine(storage_dir=temp_dir)
    
    k_normal = LearningKnowledge(
        id="KNW-NORM",
        domain="API",
        title="Standard REST Error Response",
        summary="Return 404 for missing entities",
        utility_score=50.0,
        usage_count=2
    )
    k_star = LearningKnowledge(
        id="KNW-STAR",
        domain="Architecture",
        title="Hexagonal Architecture Port Adapter Pattern",
        summary="Isolate domain entities from external framework adapters",
        utility_score=95.0,
        usage_count=15
    )
    
    ke.add_knowledge(k_normal)
    ke.add_knowledge(k_star)
    
    promoted = ke.promote_proven_knowledge(min_utility=90.0)
    assert len(promoted) == 1
    assert promoted[0].id == "KNW-STAR"
    assert promoted[0].promoted is True


def test_archive_obsolete_knowledge(temp_dir):
    ke = KnowledgeEvolutionEngine(storage_dir=temp_dir)
    
    k_active = LearningKnowledge(
        id="KNW-ACT",
        title="Modern Python Type Hints",
        summary="Use built-in generics list[str] in Python 3.9+",
        utility_score=80.0,
        last_accessed=time.time()
    )
    k_obsolete = LearningKnowledge(
        id="KNW-OBS",
        title="Python 2.7 Compatibility Workaround",
        summary="Use from __future__ import unicode_literals",
        utility_score=10.0,
        last_accessed=time.time() - (365 * 86400)  # 1 year old
    )
    
    ke.add_knowledge(k_active)
    ke.add_knowledge(k_obsolete)
    
    archived = ke.archive_stale_knowledge(max_idle_days=180)
    assert len(archived) == 1
    assert archived[0].id == "KNW-OBS"
    assert archived[0].status == "ARCHIVED"


def test_query_top_knowledge(temp_dir):
    ke = KnowledgeEvolutionEngine(storage_dir=temp_dir)
    
    for i in range(10):
        ke.add_knowledge(LearningKnowledge(
            id=f"KNW-{i}",
            domain="Security" if i % 2 == 0 else "DevOps",
            title=f"Knowledge topic {i}",
            summary=f"Summary description about {'OAuth2 security tokens' if i % 2 == 0 else 'Docker multistage build'}",
            utility_score=50.0 + i * 5
        ))
        
    results = ke.query_knowledge("security tokens", top_k=3)
    assert len(results) <= 3
    for r in results:
        assert "Security" in r.domain or "OAuth2" in r.summary or "tokens" in r.summary
