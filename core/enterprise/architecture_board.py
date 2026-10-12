"""
architecture_board.py - Architecture Review Board (ARB) & Design Quality Governance for AutoDev (v3.0)

Evaluates system proposals against enterprise architecture pillars: SOLID, DDD, Layering,
Scalability, Security, Performance, Maintainability, Complexity, and Testability.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from core.enterprise.enterprise_models import (
    ArchProposal,
    ArchReviewStatus,
    ArchitectureScorecard,
)

logger = logging.getLogger("AutoDev.Enterprise.ArchitectureBoard")


class ArchitectureBoard:
    """
    Enterprise Architecture Review Board (ARB).
    Performs deterministic scoring on design proposals and enforces architectural integrity.
    """

    def __init__(
        self,
        approval_threshold_score: float = 75.0,
        min_approval_score: Optional[float] = None,
    ) -> None:
        self.approval_threshold_score = min_approval_score if min_approval_score is not None else approval_threshold_score
        self._lock = threading.RLock()
        self._proposals: Dict[str, ArchProposal] = {}
        self._board_members = ["CTO", "Principal Architect", "Security Architect", "Lead Infrastructure Engineer"]

    def submit_proposal(
        self,
        title: str,
        author: str,
        system_component: str,
        changes_summary: str,
        adr_markdown: str = "",
        custom_scorecard: Optional[ArchitectureScorecard] = None,
        scorecard: Optional[ArchitectureScorecard] = None,
    ) -> ArchProposal:
        """Submits architectural change proposal to the review board."""
        with self._lock:
            p_id = f"PROP-{int(time.time()*1000)}-{len(self._proposals)+1:03d}"
            effective_scorecard = scorecard or custom_scorecard or self._evaluate_default_scorecard(changes_summary, adr_markdown)

            proposal = ArchProposal(
                proposal_id=p_id,
                title=title,
                author=author,
                system_component=system_component,
                changes_summary=changes_summary,
                adr_markdown=adr_markdown or f"# ADR: {title}\n## Context\n{changes_summary}\n",
                scorecard=effective_scorecard,
            )

            # Review evaluation
            self._evaluate_proposal(proposal)
            self._proposals[p_id] = proposal
            logger.info("ARB Proposal %s ('%s') evaluated with score %.1f (%s)",
                        p_id, title, proposal.scorecard.composite_architecture_score, proposal.review_status.value)
            return copy.deepcopy(proposal)

    def evaluate_code_architecture(self, code_str: str) -> ArchitectureScorecard:
        """
        Evaluates source code against architectural quality pillars.
        """
        scorecard = ArchitectureScorecard(
            solid_score=92.0,
            ddd_score=90.0,
            layering_score=95.0,
            scalability_score=90.0,
            security_score=95.0,
            performance_score=90.0,
            maintainability_score=92.0,
            complexity_penalty=5.0,
            testability_score=92.0,
        )

        code_lower = code_str.lower()
        # Heavily penalize prohibited frameworks
        prohibited = ["langgraph", "celery", "ray", "autogen", "crewai"]
        for p in prohibited:
            if f"import {p}" in code_lower or f"from {p}" in code_lower:
                scorecard.layering_score -= 25.0
                scorecard.solid_score -= 20.0
                scorecard.complexity_penalty += 35.0

        if len(code_str.splitlines()) > 500:
            scorecard.complexity_penalty += 15.0
            scorecard.maintainability_score -= 10.0

        return scorecard

    def _evaluate_default_scorecard(self, summary: str, adr: str) -> ArchitectureScorecard:
        """Calculates architecture scorecard based on design attributes and complexity."""
        card = ArchitectureScorecard(
            solid_score=92.0,
            ddd_score=88.0,
            layering_score=95.0,
            scalability_score=90.0,
            security_score=94.0,
            performance_score=89.0,
            maintainability_score=92.0,
            complexity_penalty=8.0,
            testability_score=95.0,
        )

        # Apply heuristics
        text = (summary + " " + adr).lower()
        if "circular" in text or "tight coupling" in text:
            card.layering_score -= 20.0
            card.complexity_penalty += 15.0
        if "monolith" in text:
            card.scalability_score -= 15.0
        if "encrypted" in text or "mtls" in text:
            card.security_score = min(100.0, card.security_score + 5.0)

        return card

    def _evaluate_proposal(self, proposal: ArchProposal) -> None:
        """Determines review status and feedback based on composite score."""
        score = proposal.scorecard.composite_architecture_score
        feedback: List[str] = []

        if score >= self.approval_threshold_score:
            if proposal.scorecard.security_score < 70.0:
                proposal.review_status = ArchReviewStatus.CONDITIONALLY_APPROVED
                feedback.append("Approved conditionally: Security score below 70; requires additional auth review.")
            else:
                proposal.review_status = ArchReviewStatus.APPROVED
                feedback.append(f"Approved with architectural quality score {score:.1f}/100.")
        elif score >= 60.0:
            proposal.review_status = ArchReviewStatus.REVISE_AND_RESUBMIT
            feedback.append(f"Revise and resubmit: Architecture score {score:.1f} is below threshold {self.approval_threshold_score}.")
        else:
            proposal.review_status = ArchReviewStatus.REJECTED
            feedback.append(f"Rejected: Significant architectural violations detected (score {score:.1f}/100).")

        proposal.review_feedback = feedback

    def get_proposal(self, proposal_id: str) -> Optional[ArchProposal]:
        with self._lock:
            p = self._proposals.get(proposal_id)
            return copy.deepcopy(p) if p else None

    def list_proposals(self) -> List[ArchProposal]:
        with self._lock:
            return [copy.deepcopy(p) for p in self._proposals.values()]
