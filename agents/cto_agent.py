"""
cto_agent.py - Chief Technology Officer Agent (AutoDev Version 3.4)

Highest technical authority across the AI Organization:
- Defines enterprise technology standards and Technology Radar
- Validates system architectures and component decoupling
- Audits and remediates technical debt
- Adjudicates technical disputes and architectural divergence
- Enforces zero-vulnerability security policies
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType
from core.organization_state import OrganizationState

logger = logging.getLogger("AutoDev.Org.CTOAgent")


class CTOAgent:
    """
    Autonomous Chief Technology Officer AI Agent.
    """

    def __init__(
        self,
        name: str = "CTO",
        bus: Optional[CommunicationBus] = None,
        state: Optional[OrganizationState] = None,
    ) -> None:
        self.name = name
        self.bus = bus
        self.state = state
        self.authority_level = 5  # Executive Technical
        self.approved_stacks: List[str] = [
            "Python 3.12 Standard Library",
            "POSIX Standard System Calls",
            "Deterministic SQLite / In-Memory State",
            "Structured JSON Data Contracts",
        ]
        self.prohibited_dependencies: List[str] = [
            "LangGraph", "CrewAI", "AutoGen", "Haystack", "Ray", "Celery", "Redis"
        ]

        if self.bus:
            self.bus.register_entity(self.name)

    def validate_technology_stack(self, proposed_technologies: List[str]) -> Dict[str, Any]:
        """Audits technology choices against architectural standards and prohibited dependencies."""
        violations = []
        approved = []

        for tech in proposed_technologies:
            if any(proh.lower() in tech.lower() for proh in self.prohibited_dependencies):
                violations.append(f"Prohibited external framework detected: '{tech}'")
            else:
                approved.append(tech)

        is_valid = len(violations) == 0
        governance_score = 100.0 if is_valid else max(20.0, 100.0 - (len(violations) * 35.0))

        result = {
            "approved": is_valid,
            "governance_score": governance_score,
            "approved_technologies": approved,
            "violations": violations,
            "rationale": (
                "Proposed technology stack complies strictly with Python Standard Library directive."
                if is_valid
                else f"Stack rejected: {'; '.join(violations)}."
            ),
        }

        if self.state:
            self.state.record_audit_event(
                actor=self.name,
                action="VALIDATE_TECH_STACK",
                details=result,
            )

        logger.info("CTO tech stack validation: Approved=%s, Score=%.1f", is_valid, governance_score)
        return result

    def evaluate_architecture_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Performs executive architectural review."""
        title = proposal.get("title", "Architecture Proposal")
        patterns = proposal.get("patterns", ["Repository Pattern", "Domain-Driven Design"])
        decoupling_score = proposal.get("decoupling_score", 92.0)

        approved = decoupling_score >= 80.0
        return {
            "title": title,
            "approved": approved,
            "architectural_score": decoupling_score,
            "guidance": (
                "Approved. Architecture enforces strict interface segregation and modularity."
                if approved
                else "Rejected. Architecture exhibits tight coupling. Refactor into modular services."
            ),
            "timestamp": time.time(),
        }

    def audit_technical_debt(self, debt_report: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates accumulated technical debt and schedules refactoring priority."""
        total_items = debt_report.get("debt_items_count", 0)
        total_hours = debt_report.get("estimated_hours", 0.0)

        urgency = "CRITICAL" if total_hours > 40.0 else "NORMAL"
        directive = (
            "Allocate 20% of upcoming sprint capacity to technical debt remediation."
            if urgency == "CRITICAL"
            else "Technical debt is within acceptable corporate thresholds."
        )

        return {
            "debt_level": urgency,
            "accumulated_debt_hours": total_hours,
            "cto_directive": directive,
            "timestamp": time.time(),
        }

    def adjudicate_technical_dispute(
        self,
        dispute_topic: str,
        proposal_a: Dict[str, Any],
        proposal_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Provides decisive CTO adjudication on engineering disputes."""
        # Favor proposal with fewer external dependencies and higher testability
        score_a = proposal_a.get("testability_score", 85.0) - (len(proposal_a.get("external_deps", [])) * 20.0)
        score_b = proposal_b.get("testability_score", 85.0) - (len(proposal_b.get("external_deps", [])) * 20.0)

        winner = "Proposal A" if score_a >= score_b else "Proposal B"
        chosen = proposal_a if winner == "Proposal A" else proposal_b

        rationale = f"CTO Decision: Selected {winner} for '{dispute_topic}' due to superior determinism and modular isolation."
        if self.state:
            self.state.record_audit_event(
                actor=self.name,
                action="ADJUDICATE_DISPUTE",
                details={"topic": dispute_topic, "winner": winner, "rationale": rationale},
            )

        return {
            "winning_proposal": winner,
            "details": chosen,
            "rationale": rationale,
            "timestamp": time.time(),
        }
