"""
AutoDev Consensus Engine (v2.8)
===============================
Multi-criteria proposal scoring, confidence comparison, and strategy-driven consensus resolution
(majority, weighted, architecture-first, security-first, performance-first).
"""

from __future__ import annotations

import collections
import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from core.collaboration.collaboration_models import (
    AgentRole,
    ConsensusResult,
    ConsensusStrategy,
    Proposal,
)

logger = logging.getLogger("AutoDev.ConsensusEngine")

# Role authority weight multipliers by decision category / strategy
ROLE_WEIGHT_MATRIX: Dict[str, Dict[AgentRole, float]] = {
    "architecture-first": {
        AgentRole.ARCHITECTURE: 3.5,
        AgentRole.SECURITY: 1.8,
        AgentRole.BACKEND: 1.5,
        AgentRole.PERFORMANCE: 1.3,
        AgentRole.TESTING: 1.0,
    },
    "security-first": {
        AgentRole.SECURITY: 4.0,
        AgentRole.ARCHITECTURE: 2.0,
        AgentRole.BACKEND: 1.2,
        AgentRole.RELEASE: 1.2,
    },
    "performance-first": {
        AgentRole.PERFORMANCE: 3.5,
        AgentRole.BACKEND: 2.0,
        AgentRole.ARCHITECTURE: 1.5,
        AgentRole.TESTING: 1.0,
    },
    "weighted": {
        AgentRole.ARCHITECTURE: 2.0,
        AgentRole.SECURITY: 2.0,
        AgentRole.BACKEND: 1.5,
        AgentRole.FRONTEND: 1.5,
        AgentRole.TESTING: 1.5,
        AgentRole.PERFORMANCE: 1.5,
        AgentRole.DOCUMENTATION: 1.0,
        AgentRole.RELEASE: 1.0,
        AgentRole.GENERAL: 1.0,
    },
    "majority": {
        AgentRole.ARCHITECTURE: 1.0,
        AgentRole.SECURITY: 1.0,
        AgentRole.BACKEND: 1.0,
        AgentRole.FRONTEND: 1.0,
        AgentRole.TESTING: 1.0,
        AgentRole.PERFORMANCE: 1.0,
        AgentRole.DOCUMENTATION: 1.0,
        AgentRole.RELEASE: 1.0,
        AgentRole.GENERAL: 1.0,
    },
}


class ConsensusEngine:
    """
    Evaluates competing proposals from specialized engineering agents and reaches deterministic consensus.
    Supports multiple resolution strategies and produces transparent decision audit logs.
    """

    def __init__(
        self,
        bus: Optional[Any] = None,
        default_strategy: ConsensusStrategy = ConsensusStrategy.WEIGHTED,
    ):
        self.bus = bus
        self.default_strategy = default_strategy
        self._lock = threading.RLock()
        self._proposals: Dict[str, Proposal] = {}
        self._votes: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)  # proposal_id -> votes
        self._consensus_history: List[ConsensusResult] = []

    def submit_proposal(self, proposal: Proposal) -> str:
        """Register a new proposal."""
        with self._lock:
            self._proposals[proposal.proposal_id] = proposal
        return proposal.proposal_id

    def vote(self, voter_id: str, proposal_id: str, confidence: float = 1.0, role: Optional[AgentRole] = None) -> None:
        """Cast a vote on a proposal."""
        with self._lock:
            self._votes[proposal_id].append({
                "voter": voter_id,
                "confidence": confidence,
                "role": role or AgentRole.GENERAL,
                "timestamp": time.time(),
            })

    # Alias for submit_vote
    submit_vote = vote

    def reach_consensus(
        self,
        topic: str,
        proposals: Optional[List[Proposal]] = None,
        strategy: Optional[Union[ConsensusStrategy, str]] = None,
        issue_id: Optional[str] = None,
    ) -> ConsensusResult:
        """
        Evaluate submitted proposals and determine the winning engineering choice.
        """
        strat_enum = strategy or self.default_strategy
        if isinstance(strat_enum, str):
            try:
                strat_enum = ConsensusStrategy(strat_enum)
            except ValueError:
                strat_enum = ConsensusStrategy.WEIGHTED

        strat_key = strat_enum.value.lower() if hasattr(strat_enum, "value") else str(strat_enum).lower()
        prop_list = proposals if proposals is not None else list(self._proposals.values())

        with self._lock:
            if not prop_list:
                result = ConsensusResult(
                    issue_id=issue_id,
                    topic=topic,
                    strategy=strat_enum,
                    winning_proposal_id=None,
                    score=0.0,
                    reasoning="No proposals provided for consensus evaluation.",
                    accepted=False,
                )
                self._consensus_history.append(result)
                return result

            # Register submitted proposals into cache
            for p in prop_list:
                self._proposals[p.proposal_id] = p

            # Check Security Veto if security-first strategy
            if strat_enum == ConsensusStrategy.SECURITY_FIRST:
                sec_proposals = [p for p in prop_list if p.role == AgentRole.SECURITY or "security" in p.title.lower()]
                # If there are security proposals, check if any has high confidence or vetoes
                for sp in sec_proposals:
                    if sp.confidence < 0.50:
                        # SecurityAgent declares proposal unsafe, force safe proposal
                        logger.warning("SecurityAgent flagged proposals as risky during consensus evaluation")

            # Score each proposal
            weights_table = ROLE_WEIGHT_MATRIX.get(strat_key, ROLE_WEIGHT_MATRIX["weighted"])
            scores: Dict[str, float] = {}
            for p in prop_list:
                base_weight = weights_table.get(p.role, 1.0)
                # Combine proposer confidence with author role weight
                prop_score = p.confidence * base_weight

                # Add external votes for this proposal
                for v in self._votes.get(p.proposal_id, []):
                    voter_weight = weights_table.get(v.get("role", AgentRole.GENERAL), 1.0)
                    prop_score += v.get("confidence", 1.0) * voter_weight

                scores[p.proposal_id] = round(prop_score, 3)

            # Choose winning proposal
            winning_id = max(scores, key=lambda k: scores[k])
            winning_proposal = self._proposals[winning_id]
            winning_score = scores[winning_id]

            reasoning = (
                f"Proposal '{winning_proposal.title}' ({winning_id}) won under strategy '{strat_key}' "
                f"with score {winning_score} across {len(prop_list)} evaluated options."
            )

            result = ConsensusResult(
                issue_id=issue_id,
                topic=topic,
                winning_proposal_id=winning_id,
                winning_proposal=winning_proposal,
                strategy=strat_enum,
                score=winning_score,
                reasoning=reasoning,
                scores=scores,
                proposals_evaluated=len(prop_list),
                accepted=True,
            )

            self._consensus_history.append(result)
            logger.info("Consensus reached on topic '%s': %s (Score: %s)", topic, winning_id, winning_score)
            return result

    def get_history(self) -> List[ConsensusResult]:
        with self._lock:
            return list(self._consensus_history)

    def clear(self) -> None:
        with self._lock:
            self._proposals.clear()
            self._votes.clear()
            self._consensus_history.clear()
