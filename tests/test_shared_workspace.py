"""
Tests for SharedWorkspace blackboard and memory architecture in AutoDev v3.3.
"""

import pytest
from core.multi_agent.shared_workspace import SharedWorkspace


def test_shared_workspace_state_and_branches():
    workspace = SharedWorkspace(initial_branch="main")
    assert workspace.get_branch() == "main"

    workspace.set_branch("feature/distributed-agents")
    assert workspace.get_branch() == "feature/distributed-agents"

    workspace.set_state("project_version", "3.3.0")
    workspace.set_state("feature_flags", {"multi_agent": True, "p2p": False})

    assert workspace.get_state("project_version") == "3.3.0"
    assert workspace.get_state("feature_flags")["multi_agent"] is True
    assert workspace.get_state("non_existent", default=None) is None


def test_artifact_management():
    workspace = SharedWorkspace()
    workspace.store_artifact(
        artifact_id="arch_spec",
        content="# Architecture Specification\nMulti-agent framework details.",
        metadata={"author": "agent_arch", "version": 1},
    )

    art = workspace.get_artifact("arch_spec")
    assert art is not None
    assert art["artifact_id"] == "arch_spec"
    assert "Multi-agent" in art["content"]
    assert art["metadata"]["author"] == "agent_arch"
    assert workspace.list_artifacts() == ["arch_spec"]


def test_notes_and_design_decisions():
    workspace = SharedWorkspace()
    workspace.add_note(topic="performance", note="Consider lock pooling", author_id="agent_be")
    workspace.add_note(topic="security", note="Audit headers", author_id="agent_sec")

    perf_notes = workspace.get_notes(topic="performance")
    assert len(perf_notes) == 1
    assert perf_notes[0]["author_id"] == "agent_be"

    workspace.record_design_decision(
        decision_id="ADR-001",
        title="Python Standard Library Concurrency",
        decision="Use ThreadPoolExecutor and queue.Queue",
        author_id="agent_arch",
        rationale="Eliminates external daemon dependencies.",
    )

    adrs = workspace.get_design_decisions()
    assert len(adrs) == 1
    assert adrs[0]["decision_id"] == "ADR-001"


def test_bug_tracking_and_reviews():
    workspace = SharedWorkspace()
    workspace.report_bug(
        bug_id="BUG-101",
        title="Race condition on queue pop",
        severity="HIGH",
        reported_by="agent_qa",
    )

    active_bugs = workspace.get_active_bugs()
    assert len(active_bugs) == 1
    assert active_bugs[0]["status"] == "OPEN"

    # Resolve bug
    assert workspace.resolve_bug("BUG-101", resolved_by="agent_be", fix_notes="Added RLock") is True
    assert len(workspace.get_active_bugs()) == 0
    assert len(workspace.get_active_bugs(include_resolved=True)) == 1

    # Reviews
    workspace.add_review("CR-1", "task_auth", "agent_sec", "APPROVED")
    reviews = workspace.get_active_reviews()
    assert len(reviews) == 1
    assert reviews[0]["reviewer_id"] == "agent_sec"


def test_snapshot_export_and_load():
    ws1 = SharedWorkspace(initial_branch="dev")
    ws1.set_state("key", "val")
    ws1.add_note("sync", "test note", "agent_1")
    snapshot = ws1.export_snapshot()

    ws2 = SharedWorkspace()
    ws2.load_snapshot(snapshot)
    assert ws2.get_branch() == "dev"
    assert ws2.get_state("key") == "val"
    assert len(ws2.get_notes()) == 1
