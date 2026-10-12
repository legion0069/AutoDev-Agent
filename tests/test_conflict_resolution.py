"""
Tests for ConflictResolver and conflict detection in AutoDev v3.3.
"""

import pytest
from core.multi_agent.conflict_resolver import (
    ConflictRecord,
    ConflictResolver,
    ConflictType,
    ResolutionAction,
)
from core.multi_agent.work_queue import WorkItem


def test_merge_conflict_detection_and_resolution():
    resolver = ConflictResolver()
    base = "def add(a, b):\n    return a + b\n"
    prop_1 = "def add(a, b):\n    # Fast add\n    return a + b\n"
    prop_2 = "def add(a, b):\n    # Robust add with type checks\n    assert isinstance(a, int)\n    return a + b\n"

    conflict = resolver.detect_merge_conflict(
        resource_id="math_util.py",
        base_content=base,
        proposals={"agent_be_1": prop_1, "agent_be_2": prop_2},
    )
    assert conflict is not None
    assert conflict.conflict_type == ConflictType.MERGE
    assert conflict.resolved is False

    # Resolve with CHOOSE_BEST
    resolved = resolver.resolve_conflict(conflict, preferred_action=ResolutionAction.CHOOSE_BEST)
    assert resolved.resolved is True
    assert resolved.winning_agent_id in ("agent_be_1", "agent_be_2")
    assert resolver.resolved_count == 1
    assert resolver.resolution_rate == 1.0


def test_duplicate_implementation_detection():
    resolver = ConflictResolver()
    tasks = [
        WorkItem(task_id="t1", title="Build User Authentication", assigned_agent_id="agent_1"),
        WorkItem(task_id="t2", title="Build user authentication", assigned_agent_id="agent_2"),
        WorkItem(task_id="t3", title="Design Database Schema", assigned_agent_id="agent_3"),
    ]

    conflicts = resolver.detect_duplicate_implementations(tasks)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.conflict_type == ConflictType.DUPLICATE_IMPLEMENTATION
    assert set(c.involved_agents) == {"agent_1", "agent_2"}


def test_architecture_conflict_detection():
    resolver = ConflictResolver()
    proposals = {
        "agent_arch": {"database": "PostgreSQL", "protocol": "gRPC"},
        "agent_be": {"database": "MongoDB", "protocol": "gRPC"},
    }

    conflict = resolver.detect_architecture_conflict(proposals)
    assert conflict is not None
    assert conflict.conflict_type == ConflictType.ARCHITECTURE
    assert "database" in conflict.involved_resources

    # Architect override resolution
    resolved = resolver.resolve_conflict(conflict, preferred_action=ResolutionAction.ARCHITECT_OVERRIDE)
    assert resolved.resolved is True
    assert resolved.winning_agent_id == "agent_arch"


def test_dependency_conflict_detection():
    resolver = ConflictResolver()
    agent_deps = {
        "agent_be": {"fastapi": "0.109.0", "pydantic": "2.6.0"},
        "agent_ai": {"fastapi": "0.100.0", "pydantic": "2.6.0"},
    }

    conflict = resolver.detect_dependency_conflict(agent_deps)
    assert conflict is not None
    assert conflict.conflict_type == ConflictType.DEPENDENCY
    assert "fastapi" in conflict.involved_resources
    assert "pydantic" not in conflict.involved_resources
