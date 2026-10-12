"""
ceo_agent.py - Chief Executive Officer Agent (AutoDev Version 3.4)

Highest executive authority across the AI Organization:
- Sets strategic corporate vision and quarterly targets
- Approves enterprise capital expenditures and departmental budgets
- Resolves high-priority executive escalations
- Presides over Executive Reviews and All-Hands meetings
- Holds final corporate veto authority
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType
from core.organization_state import OrganizationState

logger = logging.getLogger("AutoDev.Org.CEOAgent")


class CEOAgent:
    """
    Autonomous Chief Executive Officer AI Agent.
    """

    def __init__(
        self,
        name: str = "CEO",
        bus: Optional[CommunicationBus] = None,
        state: Optional[OrganizationState] = None,
    ) -> None:
        self.name = name
        self.bus = bus
        self.state = state
        self.authority_level = 5  # Executive
        self.approved_budgets: Dict[str, float] = {}
        self.strategic_goals: List[str] = [
            "Deliver zero-defect autonomous software systems",
            "Maintain elite DORA metrics across all releases",
            "Optimize operational token efficiency and unit margins",
            "Enforce strict SOC2 and ISO 27001 corporate compliance",
        ]

        if self.bus:
            self.bus.register_entity(self.name)

    def evaluate_strategic_alignment(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates whether an initiative aligns with corporate vision."""
        title = proposal.get("title", "")
        roi = proposal.get("estimated_roi", 1.0)
        risk = proposal.get("risk_level", "MEDIUM")

        is_aligned = roi >= 1.5 and risk != "EXTREME"
        rationale = (
            f"Proposal '{title}' exhibits strong ROI ({roi:.1f}x) and acceptable corporate risk."
            if is_aligned
            else f"Proposal '{title}' deferred: insufficient ROI ({roi:.1f}x) or excessive risk."
        )

        return {
            "proposal_title": title,
            "strategic_alignment": is_aligned,
            "executive_score": 95.0 if is_aligned else 40.0,
            "rationale": rationale,
        }

    def approve_budget(self, amount: float, requesting_department: str) -> Tuple[bool, str]:
        """Reviews and authoritatively approves/rejects departmental budget requests."""
        if amount <= 0:
            return False, "Budget amount must be positive."

        if amount > 250000.0:
            return False, f"Requested ${amount:,.2f} exceeds single-initiative executive cap of $250,000."

        self.approved_budgets[requesting_department] = (
            self.approved_budgets.get(requesting_department, 0.0) + amount
        )

        rationale = f"CEO approved ${amount:,.2f} allocation for {requesting_department}."
        if self.state:
            self.state.record_audit_event(
                actor=self.name,
                action="APPROVE_BUDGET",
                details={"department": requesting_department, "amount": amount},
            )

        logger.info(rationale)
        return True, rationale

    def handle_escalation(self, escalation: Dict[str, Any]) -> Dict[str, Any]:
        """Authoritatively resolves executive escalations."""
        title = escalation.get("escalation_title", "General Issue")
        dept = escalation.get("escalating_department", "Unknown")

        resolution = f"CEO Executive Directive: Resolved issue '{title}' for {dept}. Proceed with highest priority delivery."
        if self.state:
            self.state.record_audit_event(
                actor=self.name,
                action="RESOLVE_EXECUTIVE_ESCALATION",
                details={"title": title, "department": dept, "resolution": resolution},
            )

        return {
            "status": "RESOLVED_BY_CEO",
            "resolution": resolution,
            "timestamp": time.time(),
        }

    def conduct_executive_review(self, company_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Conducts top-level corporate health evaluation."""
        confidence = company_metrics.get("delivery_confidence", 0.95)
        burn = company_metrics.get("monthly_burn_rate_usd", 0.0)

        health = "HEALTHY" if confidence >= 0.85 else "NEEDS_ATTENTION"
        guidance = (
            "Execution is on track. Continue standard sprint cadence."
            if health == "HEALTHY"
            else "Elevated defect risk detected. Directing CTO and QA to strengthen quality gates."
        )

        return {
            "executive_assessment": health,
            "delivery_confidence": confidence,
            "monthly_burn_rate_usd": burn,
            "strategic_guidance": guidance,
            "timestamp": time.time(),
        }
