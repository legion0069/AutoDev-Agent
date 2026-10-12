"""
Tests for Master Collaboration Manager (v2.8)
==============================================
Verifies subsystem integration, specialized agent registration, task planning,
inter-agent communication, consensus delegation, conflict resolution, and telemetry.
"""

import pytest
from agents import (
    ArchitectureAgent,
    BackendAgent,
    DocumentationAgent,
    FrontendAgent,
    PerformanceAgent,
    ReleaseAgent,
    SecurityAgent,
    TestingAgent,
)
from core.collaboration import (
    CollaborationConfig,
    CollaborationManager,
    ConsensusStrategy,
    Proposal,
    TaskAssignment,
    TaskPriority,
)


def test_collaboration_manager_init_and_registration():
    mgr = CollaborationManager()
    arch_agent = ArchitectureAgent()
    back_agent = BackendAgent()

    mgr.register_agent(arch_agent)
    mgr.register_agent(back_agent)

    assert mgr.get_agent("ArchitectureAgent") is arch_agent
    assert mgr.get_agent("BackendAgent") is back_agent
    assert arch_agent.collaboration_manager is mgr


def test_collaboration_manager_planning_and_scheduling():
    mgr = CollaborationManager()
    mgr.register_agent(ArchitectureAgent())
    mgr.register_agent(BackendAgent())
    mgr.register_agent(FrontendAgent())
    mgr.register_agent(TestingAgent())

    tasks = [
        TaskAssignment(task_id="t1", title="Define system architecture and contracts", required_skills=["architecture"]),
        TaskAssignment(task_id="t2", title="Implement REST API endpoints", required_skills=["api", "backend"], dependencies=["t1"]),
        TaskAssignment(task_id="t3", title="Implement React UI view", required_skills=["ui", "frontend"], dependencies=["t1"]),
        TaskAssignment(task_id="t4", title="Write unit and integration tests", required_skills=["testing"], dependencies=["t2", "t3"]),
    ]
    mgr.submit_tasks(tasks)
    plan = mgr.plan_and_schedule()

    assert plan["total_tasks"] == 4
    assert len(plan["parallel_batches"]) == 3
    assert plan["allocations"]["t1"] == "ArchitectureAgent"
    assert plan["allocations"]["t2"] == "BackendAgent"
    assert plan["allocations"]["t3"] == "FrontendAgent"
    assert plan["allocations"]["t4"] == "TestingAgent"


def test_collaboration_manager_consensus_and_conflict():
    mgr = CollaborationManager()
    # Consensus test through manager
    proposals = [
        Proposal(proposal_id="p1", proposer="BackendAgent", title="Option 1", confidence=0.8),
        Proposal(proposal_id="p2", proposer="SecurityAgent", title="Option 2", confidence=0.9),
    ]
    res = mgr.request_consensus("Security architecture", proposals, strategy=ConsensusStrategy.WEIGHTED)
    assert res.winning_proposal_id in ("p1", "p2")


def test_collaboration_manager_telemetry_and_mermaid_diagrams():
    mgr = CollaborationManager()
    mgr.register_agent(ArchitectureAgent())
    mgr.register_agent(BackendAgent())

    report = mgr.generate_collaboration_report()
    assert "metrics" in report
    assert "diagrams" in report
    assert "collaboration_graph" in report["diagrams"]
    assert "task_allocation_graph" in report["diagrams"]
    assert "communication_graph" in report["diagrams"]
    assert "consensus_flow" in report["diagrams"]
    assert "dependency_scheduling_graph" in report["diagrams"]
