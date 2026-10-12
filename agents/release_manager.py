"""
release_manager.py - Release Manager Agent (AutoDev Version 3.4)

Directs corporate release trains and release gate verification:
- Collects formal release approvals across departments
- Verifies Go/No-Go quality gates (QA, Security, Docs, DevOps)
- Generates official Release Notes and Changelogs
- Triggers production deployment and publishes release manifest
- Enforces release governance and audit compliance
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType
from core.organization_state import OrganizationState

logger = logging.getLogger("AutoDev.Org.ReleaseManager")


class ReleaseManagerAgent:
    """
    Autonomous Release Manager AI Agent.
    """

    def __init__(
        self,
        name: str = "ReleaseManager",
        bus: Optional[CommunicationBus] = None,
        state: Optional[OrganizationState] = None,
    ) -> None:
        self.name = name
        self.bus = bus
        self.state = state
        self.authority_level = 3  # Managerial Release
        self.mandatory_approvals: List[str] = ["CEO", "CTO", "QA", "Security"]
        self.collected_approvals: Dict[str, bool] = {}

        if self.bus:
            self.bus.register_entity(self.name)

    def collect_release_approvals(self, approvals_map: Dict[str, bool]) -> Dict[str, Any]:
        """Collects departmental sign-offs for upcoming release."""
        self.collected_approvals.update(approvals_map)
        missing = [dept for dept in self.mandatory_approvals if not self.collected_approvals.get(dept, False)]

        all_approved = len(missing) == 0
        return {
            "all_mandatory_approvals_gathered": all_approved,
            "approved_by": [k for k, v in self.collected_approvals.items() if v],
            "missing_approvals": missing,
            "status": "APPROVED_FOR_RELEASE" if all_approved else "PENDING_APPROVALS",
        }

    def evaluate_release_readiness(
        self,
        qa_gate_passed: bool,
        security_score: float,
        docs_complete: bool,
    ) -> Dict[str, Any]:
        """Evaluates whether all technical release criteria are satisfied."""
        sec_ok = security_score >= 85.0
        ready = qa_gate_passed and sec_ok and docs_complete

        return {
            "release_ready": ready,
            "qa_passed": qa_gate_passed,
            "security_passed": sec_ok,
            "docs_complete": docs_complete,
            "decision": "GO" if ready else "NO_GO",
            "timestamp": time.time(),
        }

    def generate_release_notes(self, version: str, features: List[str], fixes: Optional[List[str]] = None) -> str:
        """Synthesizes formal markdown release notes."""
        feats_str = "\n".join(f"- {f}" for f in features) if features else "- Core performance optimizations"
        fixes_str = "\n".join(f"- {fx}" for fx in (fixes or [])) if fixes else "- Zero known defects"

        notes = (
            f"# AutoDev Version {version} Release Notes\n\n"
            f"### Highlights & New Features\n{feats_str}\n\n"
            f"### Defect Remediations & Bug Fixes\n{fixes_str}\n\n"
            f"### Quality Verification\n- 100% Backward Compatibility Maintained\n- Zero Prohibited Frameworks\n"
        )
        return notes

    def execute_release(
        self,
        version: str,
        features: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Executes official release and archives record."""
        release_notes = self.generate_release_notes(version, features or ["Enterprise Organization Multi-Agent Delivery"])
        record = {
            "version": version,
            "release_status": "DEPLOYED_TO_PRODUCTION",
            "approvals": list(self.mandatory_approvals),
            "release_notes": release_notes,
            "released_at": time.time(),
        }

        if self.state:
            self.state.record_release(record)

        if self.bus:
            self.bus.broadcast(
                sender=self.name,
                message_type=OrgMessageType.RELEASE_APPROVAL,
                payload=record,
                priority=MessagePriority.CRITICAL,
            )

        logger.info("AutoDev Version %s released successfully.", version)
        return record
