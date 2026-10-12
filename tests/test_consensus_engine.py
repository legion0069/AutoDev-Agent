"""
Tests for ConsensusEngine and review ratification in AutoDev v3.3.
"""

import pytest
from core.multi_agent.agent_registry import AgentRole
from core.multi_agent.consensus_engine import (
    ConsensusEngine,
    ConsensusProposal,
    ConsensusStrategy,
    ReviewVote,
    VoteDecision,
)


def test_majority_consensus_strategy():
    engine = ConsensusEngine()
    prop = engine.create_proposal(
        proposal_id="pr_1",
        title="Refactor Auth",
        description="Switch to OAuth2",
        strategy=ConsensusStrategy.MAJORITY,
    )

    engine.cast_vote(
        "pr_1",
        ReviewVote("dev_1", AgentRole.BACKEND_ENGINEER, VoteDecision.APPROVE),
    )
    engine.cast_vote(
        "pr_1",
        ReviewVote("dev_2", AgentRole.FRONTEND_ENGINEER, VoteDecision.APPROVE),
    )
    engine.cast_vote(
        "pr_1",
        ReviewVote("dev_3", AgentRole.QA_ENGINEER, VoteDecision.REJECT),
    )

    approved, reason, metrics = engine.evaluate_consensus("pr_1")
    assert approved is True
    assert metrics["approvals_count"] == 2
    assert metrics["rejections_count"] == 1
    assert prop.status == "APPROVED"


def test_weighted_majority_consensus_strategy():
    engine = ConsensusEngine()
    prop = engine.create_proposal(
        proposal_id="pr_2",
        title="Deploy to Prod",
        description="Production release candidate",
        strategy=ConsensusStrategy.WEIGHTED_MAJORITY,
    )

    # Chief Architect (weight 3.0) approves
    engine.cast_vote(
        "pr_2",
        ReviewVote("arch_1", AgentRole.CHIEF_ARCHITECT, VoteDecision.APPROVE),
    )
    # Two junior engineers (weight 1.0 each = 2.0 total) reject
    engine.cast_vote(
        "pr_2",
        ReviewVote("dev_1", AgentRole.BACKEND_ENGINEER, VoteDecision.REJECT),
    )
    engine.cast_vote(
        "pr_2",
        ReviewVote("dev_2", AgentRole.FRONTEND_ENGINEER, VoteDecision.REJECT),
    )

    approved, reason, metrics = engine.evaluate_consensus("pr_2")
    # Architect's 3.0 outweighs 2.0
    assert approved is True
    assert metrics["approve_weight"] == 3.0
    assert metrics["reject_weight"] == 2.0


def test_architect_override_strategy():
    engine = ConsensusEngine()
    prop = engine.create_proposal(
        proposal_id="pr_3",
        title="Change Tech Stack",
        description="Adopt Elixir",
        strategy=ConsensusStrategy.ARCHITECT_OVERRIDE,
    )

    # 4 developers approve
    for i in range(4):
        engine.cast_vote(
            "pr_3",
            ReviewVote(f"dev_{i}", AgentRole.BACKEND_ENGINEER, VoteDecision.APPROVE),
        )

    # Architect rejects
    engine.cast_vote(
        "pr_3",
        ReviewVote("arch_1", AgentRole.CHIEF_ARCHITECT, VoteDecision.REJECT),
    )

    approved, reason, metrics = engine.evaluate_consensus("pr_3")
    assert approved is False
    assert "Chief Architect arch_1 override: reject" in reason
    assert prop.status == "REJECTED"


def test_quality_and_confidence_threshold_strategies():
    engine = ConsensusEngine()

    # Quality threshold
    prop_q = engine.create_proposal(
        proposal_id="pr_q",
        title="Quality Gate",
        description="Verify quality metric",
        strategy=ConsensusStrategy.QUALITY_THRESHOLD,
        quality_threshold=85.0,
    )
    # Average quality 80.0 < 85.0
    engine.cast_vote(
        "pr_q",
        ReviewVote("qa_1", AgentRole.QA_ENGINEER, VoteDecision.APPROVE, quality_score=80.0),
    )
    approved, _, _ = engine.evaluate_consensus("pr_q")
    assert approved is False

    # Confidence threshold
    prop_c = engine.create_proposal(
        proposal_id="pr_c",
        title="Confidence Gate",
        description="Verify model confidence",
        strategy=ConsensusStrategy.CONFIDENCE_THRESHOLD,
        confidence_threshold=0.80,
    )
    engine.cast_vote(
        "pr_c",
        ReviewVote("ai_1", AgentRole.AI_ENGINEER, VoteDecision.APPROVE, confidence_score=0.95),
    )
    approved, _, _ = engine.evaluate_consensus("pr_c")
    assert approved is True


def test_consensus_summary():
    engine = ConsensusEngine()
    engine.create_proposal("p1", "P1", "Desc")
    engine.cast_vote("p1", ReviewVote("a1", AgentRole.CHIEF_ARCHITECT, VoteDecision.APPROVE))
    engine.evaluate_consensus("p1")

    summary = engine.get_consensus_summary()
    assert summary["total_proposals"] == 1
    assert summary["approved_count"] == 1
    assert summary["ratification_rate"] == 1.0
