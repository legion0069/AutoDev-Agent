"""
AutoDev Consensus Engine Subsystem.

Provides distributed peer review and ratification mechanisms across specialized agents
using majority, weighted majority, architect override, engineering manager override,
quality thresholds, and confidence thresholds.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from core.multi_agent.agent_registry import AgentRole


class ConsensusStrategy(str, Enum):
    """Supported consensus evaluation policies."""
    MAJORITY = "majority"
    WEIGHTED_MAJORITY = "weighted_majority"
    ARCHITECT_OVERRIDE = "architect_override"
    ENGINEERING_MANAGER_OVERRIDE = "engineering_manager_override"
    QUALITY_THRESHOLD = "quality_threshold"
    CONFIDENCE_THRESHOLD = "confidence_threshold"


class VoteDecision(str, Enum):
    """Individual reviewer decision."""
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


# Standardized seniority weights for weighted majority evaluation
ROLE_SENIORITY_WEIGHTS: Dict[AgentRole, float] = {
    AgentRole.CHIEF_ARCHITECT: 3.0,
    AgentRole.ENGINEERING_MANAGER: 2.0,
    AgentRole.ENGINEERING_DIRECTOR: 3.5,
    AgentRole.CTO: 4.0,
    AgentRole.CEO: 4.0,
    AgentRole.SECURITY_ENGINEER: 2.5,
    AgentRole.QA_ENGINEER: 1.5,
    AgentRole.RELEASE_MANAGER: 2.0,
}


@dataclass
class ReviewVote:
    """Individual agent vote on an engineering proposal or code review."""
    reviewer_id: str
    reviewer_role: AgentRole
    decision: VoteDecision
    quality_score: float = 80.0       # 0.0 to 100.0
    confidence_score: float = 0.85    # 0.0 to 1.0
    rationale: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the vote."""
        return {
            "reviewer_id": self.reviewer_id,
            "reviewer_role": self.reviewer_role.value,
            "decision": self.decision.value,
            "quality_score": self.quality_score,
            "confidence_score": self.confidence_score,
            "rationale": self.rationale,
            "timestamp": self.timestamp,
        }


@dataclass
class ConsensusProposal:
    """Represents a proposal, change, or review subjected to consensus."""
    proposal_id: str
    title: str
    description: str
    target_artifact: str
    strategy: ConsensusStrategy = ConsensusStrategy.WEIGHTED_MAJORITY
    quality_threshold: float = 75.0
    confidence_threshold: float = 0.70
    votes: List[ReviewVote] = field(default_factory=list)
    status: str = "OPEN"  # OPEN, APPROVED, REJECTED
    ratified_at: Optional[float] = None
    decision_reason: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the proposal and consensus result."""
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "description": self.description,
            "target_artifact": self.target_artifact,
            "strategy": self.strategy.value,
            "quality_threshold": self.quality_threshold,
            "confidence_threshold": self.confidence_threshold,
            "votes": [v.to_dict() for v in self.votes],
            "status": self.status,
            "ratified_at": self.ratified_at,
            "decision_reason": self.decision_reason,
            "metrics": self.metrics,
        }


class ConsensusEngine:
    """
    Subsystem managing multi-agent consensus, code reviews, and architectural ratifications.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._proposals: Dict[str, ConsensusProposal] = {}

    def create_proposal(
        self,
        proposal_id: str,
        title: str,
        description: str,
        target_artifact: str = "",
        strategy: ConsensusStrategy = ConsensusStrategy.WEIGHTED_MAJORITY,
        quality_threshold: float = 75.0,
        confidence_threshold: float = 0.70,
    ) -> ConsensusProposal:
        """Registers a new proposal for multi-agent evaluation."""
        with self._lock:
            if proposal_id in self._proposals:
                raise ValueError(f"Proposal with ID '{proposal_id}' already exists.")
            proposal = ConsensusProposal(
                proposal_id=proposal_id,
                title=title,
                description=description,
                target_artifact=target_artifact,
                strategy=strategy,
                quality_threshold=quality_threshold,
                confidence_threshold=confidence_threshold,
            )
            self._proposals[proposal_id] = proposal
            return proposal

    def cast_vote(self, proposal_id: str, vote: ReviewVote) -> bool:
        """Records an agent's vote on the specified proposal."""
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal or proposal.status != "OPEN":
                return False

            # Replace previous vote from same reviewer if present
            existing_idx = next(
                (i for i, v in enumerate(proposal.votes) if v.reviewer_id == vote.reviewer_id),
                None
            )
            if existing_idx is not None:
                proposal.votes[existing_idx] = vote
            else:
                proposal.votes.append(vote)
            return True

    def evaluate_consensus(self, proposal_id: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates current votes according to proposal's configured strategy.
        Updates proposal status and returns (approved, reason, metrics).
        """
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                return False, "Proposal not found", {}

            active_votes = [v for v in proposal.votes if v.decision != VoteDecision.ABSTAIN]
            if not active_votes:
                return False, "No active votes recorded", {"total_votes": len(proposal.votes)}

            approvals = [v for v in active_votes if v.decision == VoteDecision.APPROVE]
            rejections = [v for v in active_votes if v.decision == VoteDecision.REJECT]

            avg_quality = sum(v.quality_score for v in active_votes) / len(active_votes)
            avg_confidence = sum(v.confidence_score for v in active_votes) / len(active_votes)

            metrics = {
                "total_votes": len(proposal.votes),
                "active_votes": len(active_votes),
                "approvals_count": len(approvals),
                "rejections_count": len(rejections),
                "avg_quality": round(avg_quality, 2),
                "avg_confidence": round(avg_confidence, 3),
            }

            approved = False
            reason = ""

            # Strategy evaluation
            if proposal.strategy == ConsensusStrategy.MAJORITY:
                approved = len(approvals) > len(rejections)
                reason = (
                    f"Majority decision: {len(approvals)} approvals vs {len(rejections)} rejections."
                )

            elif proposal.strategy == ConsensusStrategy.WEIGHTED_MAJORITY:
                approve_weight = sum(
                    ROLE_SENIORITY_WEIGHTS.get(v.reviewer_role, 1.0) for v in approvals
                )
                reject_weight = sum(
                    ROLE_SENIORITY_WEIGHTS.get(v.reviewer_role, 1.0) for v in rejections
                )
                metrics["approve_weight"] = round(approve_weight, 2)
                metrics["reject_weight"] = round(reject_weight, 2)
                approved = approve_weight > reject_weight
                reason = (
                    f"Weighted majority: {approve_weight:.1f} approve weight vs {reject_weight:.1f} reject weight."
                )

            elif proposal.strategy == ConsensusStrategy.ARCHITECT_OVERRIDE:
                arch_vote = next(
                    (v for v in active_votes if v.reviewer_role == AgentRole.CHIEF_ARCHITECT),
                    None
                )
                if arch_vote:
                    approved = arch_vote.decision == VoteDecision.APPROVE
                    reason = f"Chief Architect {arch_vote.reviewer_id} override: {arch_vote.decision.value}."
                else:
                    # Fallback to simple majority if architect has not voted
                    approved = len(approvals) > len(rejections)
                    reason = f"No Architect vote; fallback to majority ({len(approvals)} to {len(rejections)})."

            elif proposal.strategy == ConsensusStrategy.ENGINEERING_MANAGER_OVERRIDE:
                em_vote = next(
                    (v for v in active_votes if v.reviewer_role == AgentRole.ENGINEERING_MANAGER),
                    None
                )
                if em_vote:
                    approved = em_vote.decision == VoteDecision.APPROVE
                    reason = f"Engineering Manager {em_vote.reviewer_id} override: {em_vote.decision.value}."
                else:
                    approved = len(approvals) > len(rejections)
                    reason = f"No Manager vote; fallback to majority ({len(approvals)} to {len(rejections)})."

            elif proposal.strategy == ConsensusStrategy.QUALITY_THRESHOLD:
                meets_quality = avg_quality >= proposal.quality_threshold
                has_plurality = len(approvals) >= len(rejections)
                approved = meets_quality and has_plurality
                reason = (
                    f"Quality threshold check: avg quality {avg_quality:.1f}/{proposal.quality_threshold:.1f}, "
                    f"approvals {len(approvals)}/{len(active_votes)}."
                )

            elif proposal.strategy == ConsensusStrategy.CONFIDENCE_THRESHOLD:
                meets_confidence = avg_confidence >= proposal.confidence_threshold
                has_plurality = len(approvals) >= len(rejections)
                approved = meets_confidence and has_plurality
                reason = (
                    f"Confidence threshold check: avg confidence {avg_confidence:.2f}/{proposal.confidence_threshold:.2f}, "
                    f"approvals {len(approvals)}/{len(active_votes)}."
                )

            proposal.status = "APPROVED" if approved else "REJECTED"
            proposal.ratified_at = time.time()
            proposal.decision_reason = reason
            proposal.metrics = metrics
            return approved, reason, metrics

    def get_proposal(self, proposal_id: str) -> Optional[ConsensusProposal]:
        """Retrieves a proposal by ID."""
        with self._lock:
            return self._proposals.get(proposal_id)

    def get_all_proposals(self) -> List[ConsensusProposal]:
        """Returns all recorded proposals."""
        with self._lock:
            return list(self._proposals.values())

    def get_consensus_summary(self) -> Dict[str, Any]:
        """Summarizes consensus outcomes across the organization."""
        with self._lock:
            total = len(self._proposals)
            approved = sum(1 for p in self._proposals.values() if p.status == "APPROVED")
            rejected = sum(1 for p in self._proposals.values() if p.status == "REJECTED")
            open_props = sum(1 for p in self._proposals.values() if p.status == "OPEN")

            return {
                "total_proposals": total,
                "approved_count": approved,
                "rejected_count": rejected,
                "open_count": open_props,
                "ratification_rate": round(approved / max(1, total), 4),
            }
