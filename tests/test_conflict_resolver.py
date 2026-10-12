"""
test_conflict_resolver.py - AutoDev Version 3.4
Unit and integration tests for Conflict Resolution Engine:
- Conflict types: Resource, Task, Architecture, Merge, Priority, Ownership, Security
- Automated resolution via security authority, precedence, and diff synthesis
- Escalation workflows to Engineering Manager -> CTO -> CEO
- Executive adjudication of escalated disputes
"""

import pytest
from core.communication_bus import CommunicationBus
from core.conflict_resolver import (
    ConflictRecord,
    ConflictResolver,
    ConflictStatus,
    ConflictType,
)


@pytest.fixture
def bus():
    return CommunicationBus()


@pytest.fixture
def resolver(bus: CommunicationBus):
    return ConflictResolver(bus=bus)


def test_register_conflict(resolver: ConflictResolver):
    rec = resolver.register_conflict(
        conflict_type=ConflictType.RESOURCE_CONFLICT,
        parties_involved=["Backend", "QA"],
        description="Contention over shared staging database",
        competing_proposals={"Backend": {"priority": 3}, "QA": {"priority": 2}},
    )
    assert rec.conflict_id.startswith("CONF-")
    assert rec.conflict_type == ConflictType.RESOURCE_CONFLICT
    assert rec.status == ConflictStatus.DETECTED


def test_resolve_security_conflict_strictly_enforced(resolver: ConflictResolver):
    rec = resolver.register_conflict(
        conflict_type=ConflictType.SECURITY_CONFLICT,
        parties_involved=["Backend", "Security"],
        description="Feature release blocked by unencrypted secret in configuration",
        competing_proposals={"Backend": "Deploy now, patch next week", "Security": "Block deployment"},
    )
    resolved = resolver.resolve_conflict(rec.conflict_id)
    assert resolved.status == ConflictStatus.AUTO_RESOLVED
    assert resolved.resolution_strategy == "SECURITY_AUTHORITY_TRUMP"
    assert "Security finding strictly enforced" in resolved.resolution_details


def test_resolve_ownership_conflict_by_authority(resolver: ConflictResolver):
    rec = resolver.register_conflict(
        conflict_type=ConflictType.OWNERSHIP_CONFLICT,
        parties_involved=["Frontend", "ChiefArchitect"],
        description="Dispute over who dictates shared component design system",
        competing_proposals={"Frontend": "UI team owns components", "ChiefArchitect": "Architecture owns design tokens"},
    )
    resolved = resolver.resolve_conflict(rec.conflict_id)
    assert resolved.status == ConflictStatus.AUTO_RESOLVED
    assert resolved.resolution_strategy == "AUTHORITY_PRECEDENCE"
    # ChiefArchitect has authority 80 vs Frontend 35
    assert "ChiefArchitect" in resolved.resolution_details


def test_resolve_merge_conflict_non_overlapping(resolver: ConflictResolver):
    base_code = "def start():\n    return True\n"
    prop_a = "def start():\n    return True\ndef feature_a():\n    return 'A'\n"
    prop_b = "def start():\n    return True\ndef feature_b():\n    return 'B'\n"

    rec = resolver.register_conflict(
        conflict_type=ConflictType.MERGE_CONFLICT,
        parties_involved=["Backend-Dev1", "Backend-Dev2"],
        description="Simultaneous non-overlapping additions to service module",
        competing_proposals={"base": base_code, "proposal_a": prop_a, "proposal_b": prop_b},
    )
    resolved = resolver.resolve_conflict(rec.conflict_id)
    assert resolved.status == ConflictStatus.AUTO_RESOLVED
    assert resolved.resolution_strategy == "THREE_WAY_MERGE_SYNTHESIS"
    assert "feature_a" in resolved.metadata["resolved_content"]
    assert "feature_b" in resolved.metadata["resolved_content"]


def test_resolve_merge_conflict_overlapping_escalates(resolver: ConflictResolver):
    base_code = "x = 1"
    prop_a = "x = 2"
    prop_b = "x = 3"

    rec = resolver.register_conflict(
        conflict_type=ConflictType.MERGE_CONFLICT,
        parties_involved=["Backend-Dev1", "Backend-Dev2"],
        description="Direct collision on variable assignment",
        competing_proposals={"base": base_code, "proposal_a": prop_a, "proposal_b": prop_b},
    )
    resolved = resolver.resolve_conflict(rec.conflict_id)
    # Direct collision must escalate to ChiefArchitect!
    assert resolved.status == ConflictStatus.ESCALATED
    assert resolved.escalated_to == "ChiefArchitect"


def test_resolve_resource_conflict_by_priority(resolver: ConflictResolver):
    rec = resolver.register_conflict(
        conflict_type=ConflictType.RESOURCE_CONFLICT,
        parties_involved=["Frontend", "Backend"],
        description="Contention for compute quota",
        competing_proposals={
            "Frontend": {"priority": 1},
            "Backend": {"priority": 5},
        },
    )
    resolved = resolver.resolve_conflict(rec.conflict_id)
    assert resolved.status == ConflictStatus.AUTO_RESOLVED
    assert resolved.resolution_strategy == "PRIORITY_RESOURCE_ALLOCATION"
    assert "Backend" in resolved.resolution_details


def test_resolve_architecture_conflict_with_cto(resolver: ConflictResolver):
    rec = resolver.register_conflict(
        conflict_type=ConflictType.ARCHITECTURE_CONFLICT,
        parties_involved=["Backend", "CTO"],
        description="Choice of messaging protocol",
        competing_proposals={"Backend": "ZeroMQ", "CTO": "Standard Library Queue"},
    )
    resolved = resolver.resolve_conflict(rec.conflict_id)
    assert resolved.status == ConflictStatus.AUTO_RESOLVED
    assert resolved.resolution_strategy == "ARCHITECT_DECISIVE_DECISION"
    assert "CTO" in resolved.resolution_details


def test_adjudicate_escalated_conflict(resolver: ConflictResolver):
    rec = resolver.register_conflict(
        conflict_type=ConflictType.PRIORITY_CONFLICT,
        parties_involved=["TeamA", "TeamB"],
        description="Disputed sprint goal priority",
        competing_proposals={"TeamA": "Feature X", "TeamB": "Feature Y"},
    )
    escalated = resolver.escalate_conflict(rec.conflict_id, escalate_to="CEO", reason="Deadlock between department heads")
    assert escalated.status == ConflictStatus.ESCALATED

    # CEO adjudicates
    adjudicated = resolver.resolve_escalated_conflict(
        conflict_id=rec.conflict_id,
        adjudicator="CEO",
        chosen_resolution="Execute Feature X first; sequence Feature Y into follow-up sprint",
        rationale="Feature X unlocks immediate contract milestone",
    )
    assert adjudicated.status == ConflictStatus.RESOLVED_BY_ESCALATION
    assert "CEO" in adjudicated.resolution_strategy


def test_list_conflicts_filtering(resolver: ConflictResolver):
    c1 = resolver.register_conflict(ConflictType.SECURITY_CONFLICT, ["A", "B"], "C1", {})
    c2 = resolver.register_conflict(ConflictType.RESOURCE_CONFLICT, ["C", "D"], "C2", {})
    resolver.resolve_conflict(c1.conflict_id)

    all_confs = resolver.list_conflicts()
    assert len(all_confs) == 2

    auto_resolved = resolver.list_conflicts(status=ConflictStatus.AUTO_RESOLVED)
    assert len(auto_resolved) == 1
    assert auto_resolved[0]["conflict_id"] == c1.conflict_id
