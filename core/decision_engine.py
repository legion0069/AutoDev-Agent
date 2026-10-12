"""
decision_engine.py - Organizational Decision Engine (AutoDev Version 3.4)

When departments disagree on:
- Architecture choice
- Framework selection
- Priority & Roadmaps
- Deadline & Scope
- Bug severity & Hotfixes
- Release timing (Go / No-Go)
- Security findings & CVE risk acceptance

The Decision Engine:
1. Collects departmental votes & authority weights
2. Calculates weighted confidence scores
3. Ranks supporting evidence strings
4. Selects optimal decision deterministically
5. Stores comprehensive rationale & audit trail
6. Supports executive override / veto (CEO / CTO)
"""

from __future__ import annotations

import enum
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.organization_state import OrganizationState

logger = logging.getLogger("AutoDev.Org.DecisionEngine")


class DecisionDomain(str, enum.Enum):
    """Categorization of departmental decisions."""
    ARCHITECTURE_CHOICE = "ARCHITECTURE_CHOICE"
    FRAMEWORK_SELECTION = "FRAMEWORK_SELECTION"
    PRIORITY = "PRIORITY"
    DEADLINE = "DEADLINE"
    BUG_SEVERITY = "BUG_SEVERITY"
    RELEASE_TIMING = "RELEASE_TIMING"
    SECURITY_FINDINGS = "SECURITY_FINDINGS"
    RESOURCE_ALLOCATION = "RESOURCE_ALLOCATION"


@dataclass
class VoteRecord:
    """Individual department or agent vote."""
    voter: str
    chosen_option: str
    confidence: float  # 0.0 to 1.0
    evidence: List[str] = field(default_factory=list)
    weight: float = 1.0
    rationale: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionProposal:
    """Formal proposal submitted for organizational decision."""
    proposal_id: str
    title: str
    domain: DecisionDomain
    options: List[str]
    proposer: str
    context: Dict[str, Any] = field(default_factory=dict)
    votes: List[VoteRecord] = field(default_factory=list)
    status: str = "OPEN"  # OPEN, RESOLVED, OVERRIDDEN, REJECTED
    winning_option: Optional[str] = None
    confidence_score: float = 0.0
    decision_rationale: str = ""
    ranked_evidence: List[str] = field(default_factory=list)
    overridden_by: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["domain"] = self.domain.value if hasattr(self.domain, "value") else str(self.domain)
        return d


class DecisionEngine:
    """
    Consensus, dispute arbitration and decision engine for AI organizations.
    Uses multi-criteria weighted scoring and evidence synthesis.
    """

    # Department authority weights for decision scoring
    AUTHORITY_WEIGHTS: Dict[str, float] = {
        "CEO": 5.0,
        "CTO": 4.5,
        "ChiefArchitect": 4.0,
        "Architecture": 4.0,
        "EngineeringManager": 3.5,
        "Security": 3.8,  # High weight on security matters
        "ReleaseManager": 3.5,
        "QAManager": 3.0,
        "DevOps": 3.0,
        "Backend": 2.5,
        "Frontend": 2.5,
        "ProductManager": 3.5,
        "BusinessAnalyst": 2.5,
        "Finance": 3.0,
        "Compliance": 3.5,
        "Operations": 3.0,
    }

    def __init__(self, state: Optional[OrganizationState] = None) -> None:
        self._lock = threading.RLock()
        self.state = state
        self._proposals: Dict[str, DecisionProposal] = {}

    def create_proposal(
        self,
        title: str,
        domain: DecisionDomain | str,
        options: List[str],
        proposer: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Opens a new decision proposal across departments."""
        with self._lock:
            pid = f"DEC-{uuid.uuid4().hex[:8].upper()}"
            dom = DecisionDomain(domain) if isinstance(domain, str) else domain
            prop = DecisionProposal(
                proposal_id=pid,
                title=title,
                domain=dom,
                options=options,
                proposer=proposer,
                context=context or {},
            )
            self._proposals[pid] = prop

            if self.state:
                self.state.record_audit_event(
                    actor=proposer,
                    action="CREATE_DECISION_PROPOSAL",
                    details={"proposal_id": pid, "title": title, "domain": dom.value, "options": options},
                )

            logger.info("Decision proposal '%s' created for '%s'.", pid, title)
            return pid

    def cast_vote(
        self,
        proposal_id: str,
        voter: str,
        chosen_option: str,
        confidence: float = 0.9,
        evidence: Optional[List[str]] = None,
        rationale: str = "",
        custom_weight: Optional[float] = None,
    ) -> bool:
        """Registers a department or executive vote."""
        with self._lock:
            prop = self._proposals.get(proposal_id)
            if not prop or prop.status != "OPEN":
                logger.warning("Cannot cast vote on proposal '%s' (Status: %s).", proposal_id, getattr(prop, "status", "UNKNOWN"))
                return False

            if chosen_option not in prop.options:
                logger.warning("Option '%s' not among allowed options %s.", chosen_option, prop.options)
                return False

            # Assign authority weight
            weight = custom_weight or self.AUTHORITY_WEIGHTS.get(voter, 2.0)

            # Security domain boosts Security department weight
            if prop.domain == DecisionDomain.SECURITY_FINDINGS and "Security" in voter:
                weight *= 1.5

            vote = VoteRecord(
                voter=voter,
                chosen_option=chosen_option,
                confidence=max(0.1, min(1.0, float(confidence))),
                evidence=evidence or [],
                weight=weight,
                rationale=rationale,
            )
            prop.votes.append(vote)
            return True

    def evaluate_decision(self, proposal_id: str) -> Dict[str, Any]:
        """
        Calculates weighted vote totals, ranks evidence, and selects best decision.
        """
        with self._lock:
            prop = self._proposals.get(proposal_id)
            if not prop:
                return {"error": f"Proposal '{proposal_id}' not found"}

            if not prop.votes:
                # Default to first option with baseline confidence if no votes cast
                prop.winning_option = prop.options[0] if prop.options else "DEFAULT"
                prop.confidence_score = 0.5
                prop.decision_rationale = "Adopted default option (no votes cast)."
                prop.status = "RESOLVED"
                prop.resolved_at = time.time()
                return prop.to_dict()

            # Tally weighted scores per option
            option_scores: Dict[str, float] = {opt: 0.0 for opt in prop.options}
            option_evidence: Dict[str, List[Tuple[float, str]]] = {opt: [] for opt in prop.options}
            total_weight = 0.0

            for v in prop.votes:
                effective_score = v.weight * v.confidence
                option_scores[v.chosen_option] = option_scores.get(v.chosen_option, 0.0) + effective_score
                total_weight += v.weight
                for ev in v.evidence:
                    option_evidence[v.chosen_option].append((effective_score, ev))

            # Select winner with highest weighted score
            best_option = max(option_scores.keys(), key=lambda k: option_scores[k])
            best_score = option_scores[best_option]
            winning_votes = [v for v in prop.votes if v.chosen_option == best_option]
            winning_weight = sum(v.weight for v in winning_votes)
            calculated_confidence = min(0.99, max(0.40, round(best_score / max(0.001, winning_weight), 3)))

            # Rank evidence strings
            winner_ev_tuples = sorted(option_evidence[best_option], key=lambda x: -x[0])
            ranked_ev = [ev_str for _, ev_str in winner_ev_tuples]

            # Construct comprehensive rationale
            supporting_voters = [v.voter for v in prop.votes if v.chosen_option == best_option]
            voters_str = ", ".join(supporting_voters) if supporting_voters else "Consensus algorithm"
            rationale = (
                f"Selected '{best_option}' with weighted score of {best_score:.2f}/{total_weight:.2f} "
                f"({calculated_confidence*100:.1f}% confidence). Supported by: {voters_str}."
            )

            prop.winning_option = best_option
            prop.confidence_score = calculated_confidence
            prop.decision_rationale = rationale
            prop.ranked_evidence = ranked_ev[:5]
            prop.status = "RESOLVED"
            prop.resolved_at = time.time()

            # Record in organization state & audit
            if self.state:
                self.state.record_audit_event(
                    actor="DecisionEngine",
                    action="RESOLVE_DECISION",
                    details={
                        "proposal_id": proposal_id,
                        "winning_option": best_option,
                        "confidence": calculated_confidence,
                        "domain": prop.domain.value,
                    },
                )
                if prop.domain == DecisionDomain.ARCHITECTURE_CHOICE:
                    self.state.record_architecture_decision({
                        "decision_id": f"ADR-{proposal_id}",
                        "title": prop.title,
                        "decision": best_option,
                        "author": voters_str,
                        "status": "ACCEPTED",
                        "rationale": rationale,
                    })

            logger.info("Proposal '%s' resolved -> '%s' (Confidence: %.2f)", proposal_id, best_option, calculated_confidence)
            return prop.to_dict()

    def override_decision(
        self,
        proposal_id: str,
        overrider: str,
        chosen_option: str,
        rationale: str,
    ) -> bool:
        """
        Allows executive authority (CEO / CTO) to override or veto any decision.
        """
        with self._lock:
            prop = self._proposals.get(proposal_id)
            if not prop:
                return False

            if overrider not in ("CEO", "CTO", "ExecutiveManagement"):
                logger.warning("Overrider '%s' lacks executive authority to override decisions.", overrider)
                return False

            prop.winning_option = chosen_option
            prop.status = "OVERRIDDEN"
            prop.overridden_by = overrider
            prop.decision_rationale = f"Executive override by {overrider}: {rationale}"
            prop.confidence_score = 0.99
            prop.resolved_at = time.time()

            if self.state:
                self.state.record_audit_event(
                    actor=overrider,
                    action="EXECUTIVE_OVERRIDE",
                    details={"proposal_id": proposal_id, "option": chosen_option, "rationale": rationale},
                )

            logger.warning("Proposal '%s' OVERRIDDEN by %s -> '%s'", proposal_id, overrider, chosen_option)
            return True

    def get_proposal(self, proposal_id: str) -> Optional[DecisionProposal]:
        """Retrieves proposal by ID."""
        with self._lock:
            return self._proposals.get(proposal_id)

    def list_proposals(self, domain: Optional[DecisionDomain | str] = None) -> List[Dict[str, Any]]:
        """Lists all decision proposals."""
        with self._lock:
            dom_val = domain.value if hasattr(domain, "value") else str(domain) if domain else None
            results = []
            for p in self._proposals.values():
                p_dom = p.domain.value if hasattr(p.domain, "value") else str(p.domain)
                if dom_val and p_dom != dom_val:
                    continue
                results.append(p.to_dict())
            return results
