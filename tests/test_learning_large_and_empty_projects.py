"""
Tests for AutoDev v3.1 Learning Subsystem handling large-scale projects and empty/edge state projects.
"""
import pytest
import os
import shutil
import tempfile
import time
from typing import List

from core.learning.learning_models import (
    LearningEvent,
    LearningEventType,
    PatternCategory,
    PlaybookArchetype,
    ReflectionScope,
    ImprovementArea,
    LearningKnowledge
)
from core.learning.learning_engine import LearningEngine
from core.learning.reflection_engine import ReflectionEngine
from core.learning.pattern_miner import PatternMiningEngine
from core.learning.prompt_optimizer import PromptOptimizationEngine
from core.learning.execution_analytics import ExecutionAnalyticsEngine
from core.learning.architecture_recommender import ArchitectureRecommendationEngine
from core.learning.playbook_engine import PlaybookEngine
from core.learning.self_improvement_planner import SelfImprovementPlanner
from core.learning.knowledge_evolution import KnowledgeEvolutionEngine
from core.learning.performance_evolution import PerformanceEvolutionEngine


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="autodev_test_scale_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ===========================================================================
# 1. Empty Project & Zero State Tests
# ===========================================================================

def test_learning_engine_empty_project(temp_dir):
    engine = LearningEngine(storage_dir=temp_dir)
    
    events = engine.get_events_for_project("non_existent_project")
    assert events == []
    
    snapshot = engine.create_snapshot(project="empty_proj")
    assert snapshot.total_events == 0
    assert snapshot.average_confidence == 0.0
    assert snapshot.events_by_category == {}


def test_reflection_engine_empty_sprint_and_release(temp_dir):
    re = ReflectionEngine(storage_dir=temp_dir)
    
    rep_sprint = re.reflect_on_sprint(sprint_number=999, tasks_data=[])
    assert rep_sprint.scope == ReflectionScope.SPRINT
    assert rep_sprint.execution_success is True
    
    rep_release = re.reflect_on_release(release_version="v0.0.0", sprints_data=[])
    assert rep_release.scope == ReflectionScope.RELEASE
    assert rep_release.execution_success is True


def test_pattern_miner_empty_events(temp_dir):
    pm = PatternMiningEngine(storage_dir=temp_dir)
    pats = pm.mine_patterns([])
    assert pats == []


def test_prompt_optimizer_empty_and_whitespace(temp_dir):
    po = PromptOptimizationEngine(storage_dir=temp_dir)
    
    opt_empty = po.optimize_prompt("", task_type="coding")
    assert opt_empty.optimized_prompt == ""
    
    opt_ws = po.optimize_prompt("   \n\t   ", task_type="coding")
    assert opt_ws.optimized_prompt == ""


def test_architecture_recommender_empty_and_minimal_query(temp_dir):
    ar = ArchitectureRecommendationEngine(storage_dir=temp_dir)
    
    rec_empty = ar.recommend("", project_name="empty")
    assert rec_empty.archetype is not None
    assert rec_empty.api_style is not None
    
    rec_generic = ar.recommend("Make a project", project_name="generic")
    assert rec_generic.database_choice is not None


def test_execution_analytics_empty_stats(temp_dir):
    ea = ExecutionAnalyticsEngine(storage_dir=temp_dir)
    stats = ea.compute_aggregated_statistics()
    assert stats["total_projects"] == 0
    assert stats["avg_review_score"] == 0.0
    assert stats["avg_retry_count"] == 0.0


def test_knowledge_evolution_empty_state(temp_dir):
    ke = KnowledgeEvolutionEngine(storage_dir=temp_dir)
    merged = ke.evolve_knowledge([])
    assert merged == []
    
    promoted = ke.promote_proven_knowledge(min_utility=90.0)
    assert promoted == []


def test_performance_evolution_empty_report(temp_dir):
    pe = PerformanceEvolutionEngine(storage_dir=temp_dir)
    report = pe.generate_evolution_report()
    assert report["total_benchmarks"] == 0
    assert report["overall_speedup"] == 1.0


# ===========================================================================
# 2. Large Scale & High Volume Tests
# ===========================================================================

def test_learning_engine_large_scale_events(temp_dir):
    engine = LearningEngine(storage_dir=temp_dir)
    
    t0 = time.time()
    events = [
        LearningEvent(
            id=f"EVT-SCALE-{i}",
            project="large_enterprise_system",
            task=f"task_{i % 50}",
            category=LearningEventType.BUG_FIXED if i % 2 == 0 else LearningEventType.PATTERN_DISCOVERED,
            confidence=0.85 + (i % 15) * 0.01,
            importance=70.0 + (i % 30),
            summary=f"Automated event {i} description and optimization note",
            affected_files=[f"src/module_{i % 20}/component.py", f"tests/test_{i % 20}.py"],
            root_cause=f"Edge case error {i} in pipeline",
            solution=f"Patch {i} deployed successfully"
        )
        for i in range(500)
    ]
    
    for e in events:
        engine.record_event(e)
        
    duration = time.time() - t0
    assert duration < 5.0  # Processing 500 events within 5 seconds
    
    retrieved = engine.get_events_for_project("large_enterprise_system")
    assert len(retrieved) == 500
    
    snapshot = engine.create_snapshot(project="large_enterprise_system")
    assert snapshot.total_events == 500
    assert snapshot.average_confidence > 0.80


def test_pattern_mining_large_event_set(temp_dir):
    pm = PatternMiningEngine(storage_dir=temp_dir)
    
    events = [
        LearningEvent(
            id=f"EVT-{i}",
            category=LearningEventType.BUG_FIXED if i % 3 == 0 else LearningEventType.ARCHITECTURE_SUCCESS,
            summary=f"Database connection timeout on pool exhaustion variation {i % 10}",
            root_cause="Connection leak without context manager cleanup",
            solution="Ensure with db_session() as s: context manager usage"
        )
        for i in range(300)
    ]
    
    patterns = pm.mine_patterns(events)
    assert len(patterns) >= 1
    for p in patterns:
        assert p.usage_count >= 1
        assert p.confidence > 0.0


def test_knowledge_evolution_large_batch(temp_dir):
    ke = KnowledgeEvolutionEngine(storage_dir=temp_dir)
    
    items = [
        LearningKnowledge(
            id=f"KNW-{i}",
            domain="Security" if i % 2 == 0 else "Architecture",
            title=f"JWT Token validation best practice #{i % 5}",
            summary="Validate token signature and expiration timestamp before parsing claims",
            utility_score=60.0 + (i % 40)
        )
        for i in range(100)
    ]
    
    for it in items:
        ke.add_knowledge(it)
        
    evolved = ke.consolidate_and_deduplicate()
    assert len(evolved) < 100  # Duplicates merged
    
    promoted = ke.promote_proven_knowledge(min_utility=85.0)
    assert len(promoted) >= 1
