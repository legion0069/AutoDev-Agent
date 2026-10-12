"""
conflict_resolver.py - Organizational Conflict Resolution Engine (AutoDev Version 3.4)

Detects and resolves inter-departmental conflicts:
- Resource conflicts (CPU, developers, shared queues)
- Task conflicts (duplicated tasks, priority inversions)
- Architecture conflicts (divergent patterns, incompatible schemas)
- Merge conflicts (conflicting source changes)
- Priority conflicts (conflicting sprint deliverables)
- Ownership conflicts (boundary ambiguity between teams)
- Security conflicts (security findings blocking deployment)

Resolves automatically whenever rule-based or authority-based criteria apply;
escalates to Engineering Manager -> CTO -> CEO otherwise.
"""

from __future__ import annotations

import difflib
import enum
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType

logger = logging.getLogger("AutoDev.Org.ConflictResolver")


class ConflictType(str, enum.Enum):
    """Types of inter-departmental conflicts."""
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    TASK_CONFLICT = "TASK_CONFLICT"
    ARCHITECTURE_CONFLICT = "ARCHITECTURE_CONFLICT"
    MERGE_CONFLICT = "MERGE_CONFLICT"
    PRIORITY_CONFLICT = "PRIORITY_CONFLICT"
    OWNERSHIP_CONFLICT = "OWNERSHIP_CONFLICT"
    SECURITY_CONFLICT = "SECURITY_CONFLICT"


class ConflictStatus(str, enum.Enum):
    """Lifecycle status of a conflict."""
    DETECTED = "DETECTED"
    AUTO_RESOLVED = "AUTO_RESOLVED"
    ESCALATED = "ESCALATED"
    RESOLVED_BY_ESCALATION = "RESOLVED_BY_ESCALATION"
    CLOSED = "CLOSED"


@dataclass
class ConflictRecord:
    """Detailed record of an organizational conflict."""
    conflict_id: str
    conflict_type: ConflictType
    parties_involved: List[str]
    description: str
    competing_proposals: Dict[str, Any]
    status: ConflictStatus = ConflictStatus.DETECTED
    resolution_strategy: Optional[str] = None
    resolution_details: str = ""
    escalated_to: Optional[str] = None
    detected_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["conflict_type"] = self.conflict_type.value if hasattr(self.conflict_type, "value") else str(self.conflict_type)
        d["status"] = self.status.value if hasattr(self.status, "value") else str(self.status)
        return d


class ConflictResolver:
    """
    Automated conflict detection and resolution engine.
    Ensures that inter-departmental disputes never halt corporate delivery.
    """

    # Department authority precedence for tie-breaking
    AUTHORITY_PRECEDENCE: Dict[str, int] = {
        "CEO": 100,
        "CTO": 90,
        "ChiefArchitect": 80,
        "Security": 75,       # Security has high veto authority
        "EngineeringManager": 70,
        "ReleaseManager": 65,
        "Compliance": 60,
        "ProductManager": 55,
        "Finance": 50,
        "DevOps": 45,
        "QAManager": 40,
        "Backend": 35,
        "Frontend": 35,
        "Operations": 30,
        "Documentation": 25,
        "BusinessAnalyst": 20,
        "CustomerFeedback": 15,
    }

    def __init__(self, bus: Optional[CommunicationBus] = None) -> None:
        self._lock = threading.RLock()
        self.bus = bus
        self._conflicts: Dict[str, ConflictRecord] = {}

    def register_conflict(
        self,
        conflict_type: ConflictType | str,
        parties_involved: List[str],
        description: str,
        competing_proposals: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConflictRecord:
        """Registers a newly detected dispute between departments."""
        with self._lock:
            cid = f"CONF-{uuid.uuid4().hex[:8].upper()}"
            ctype = ConflictType(conflict_type) if isinstance(conflict_type, str) else conflict_type
            rec = ConflictRecord(
                conflict_id=cid,
                conflict_type=ctype,
                parties_involved=parties_involved,
                description=description,
                competing_proposals=competing_proposals,
                metadata=metadata or {},
            )
            self._conflicts[cid] = rec
            logger.info("Conflict '%s' [%s] registered between %s", cid, ctype.value, parties_involved)
            return rec

    def resolve_conflict(self, conflict_id: str) -> ConflictRecord:
        """
        Attempts automated resolution based on conflict type and precedence rules.
        If cannot be resolved automatically, escalates up the hierarchy.
        """
        with self._lock:
            rec = self._conflicts.get(conflict_id)
            if not rec:
                raise ValueError(f"Conflict '{conflict_id}' not found.")

            # 1. Security Conflict: Security policy ALWAYS trumps feature convenience
            if rec.conflict_type == ConflictType.SECURITY_CONFLICT:
                rec.resolution_strategy = "SECURITY_AUTHORITY_TRUMP"
                rec.resolution_details = (
                    "Security finding strictly enforced. Vulnerability remediation is mandatory "
                    "before feature deployment. Security team proposal adopted."
                )
                rec.status = ConflictStatus.AUTO_RESOLVED
                rec.resolved_at = time.time()
                self._notify_parties(rec)
                return rec

            # 2. Ownership Conflict: Precedence-based tie-breaking
            if rec.conflict_type == ConflictType.OWNERSHIP_CONFLICT:
                winner = max(
                    rec.parties_involved,
                    key=lambda p: self.AUTHORITY_PRECEDENCE.get(p, 10),
                )
                rec.resolution_strategy = "AUTHORITY_PRECEDENCE"
                rec.resolution_details = (
                    f"Ownership assigned to '{winner}' based on organizational authority hierarchy."
                )
                rec.status = ConflictStatus.AUTO_RESOLVED
                rec.resolved_at = time.time()
                self._notify_parties(rec)
                return rec

            # 3. Merge Conflict: Automated 3-way or unified diff resolution
            if rec.conflict_type == ConflictType.MERGE_CONFLICT:
                resolved_text, success = self._attempt_merge_resolution(rec.competing_proposals)
                if success:
                    rec.resolution_strategy = "THREE_WAY_MERGE_SYNTHESIS"
                    rec.resolution_details = "Successfully synthesized non-overlapping modifications."
                    rec.metadata["resolved_content"] = resolved_text
                    rec.status = ConflictStatus.AUTO_RESOLVED
                    rec.resolved_at = time.time()
                    self._notify_parties(rec)
                    return rec
                else:
                    return self.escalate_conflict(conflict_id, escalate_to="ChiefArchitect", reason="Overlapping code block collision")

            # 4. Resource / Priority Conflict: Fair allocation or priority ranking
            if rec.conflict_type in (ConflictType.RESOURCE_CONFLICT, ConflictType.PRIORITY_CONFLICT, ConflictType.TASK_CONFLICT):
                # Rank proposals by priority / customer value score if provided
                proposals = rec.competing_proposals

                def _extract_priority(party: str) -> int:
                    val = proposals.get(party)
                    if isinstance(val, dict):
                        return val.get("priority", 1)
                    return 1

                sorted_parties = sorted(
                    rec.parties_involved,
                    key=lambda p: (
                        _extract_priority(p),
                        self.AUTHORITY_PRECEDENCE.get(p, 10),
                    ),
                    reverse=True,
                )
                winner = sorted_parties[0]
                rec.resolution_strategy = "PRIORITY_RESOURCE_ALLOCATION"
                rec.resolution_details = (
                    f"Allocated critical resource/priority quota to '{winner}' based on authority precedence and task ROI."
                )
                rec.status = ConflictStatus.AUTO_RESOLVED
                rec.resolved_at = time.time()
                self._notify_parties(rec)
                return rec

            # 5. Architecture Conflict: Check if ChiefArchitect or CTO involved
            if rec.conflict_type == ConflictType.ARCHITECTURE_CONFLICT:
                for party in rec.parties_involved:
                    if party in ("ChiefArchitect", "CTO"):
                        rec.resolution_strategy = "ARCHITECT_DECISIVE_DECISION"
                        rec.resolution_details = f"Architectural standard ratified by '{party}'."
                        rec.status = ConflictStatus.AUTO_RESOLVED
                        rec.resolved_at = time.time()
                        self._notify_parties(rec)
                        return rec
                return self.escalate_conflict(conflict_id, escalate_to="ChiefArchitect", reason="Divergent architectural proposals")

            # Default: Escalate to EngineeringManager
            return self.escalate_conflict(
                conflict_id,
                escalate_to="EngineeringManager",
                reason=f"Automated heuristic exhausted for {rec.conflict_type.value}",
            )

    def escalate_conflict(self, conflict_id: str, escalate_to: str, reason: str) -> ConflictRecord:
        """Escalates an unresolved conflict to designated leadership."""
        with self._lock:
            rec = self._conflicts.get(conflict_id)
            if not rec:
                raise ValueError(f"Conflict '{conflict_id}' not found.")

            rec.status = ConflictStatus.ESCALATED
            rec.escalated_to = escalate_to
            rec.resolution_details = f"Escalated to {escalate_to}: {reason}"

            # Dispatch notification if bus attached
            if self.bus:
                msg = OrgMessage(
                    sender="ConflictResolver",
                    receiver=escalate_to,
                    priority=MessagePriority.CRITICAL,
                    message_type=OrgMessageType.ESCALATION,
                    payload={
                        "conflict_id": conflict_id,
                        "conflict_type": rec.conflict_type.value,
                        "parties": rec.parties_involved,
                        "reason": reason,
                        "competing_proposals": rec.competing_proposals,
                    },
                    response_required=True,
                )
                self.bus.send_message(msg)

            logger.warning("Conflict '%s' ESCALATED to %s: %s", conflict_id, escalate_to, reason)
            return rec

    def resolve_escalated_conflict(
        self,
        conflict_id: str,
        adjudicator: str,
        chosen_resolution: str,
        rationale: str,
    ) -> ConflictRecord:
        """Records an authoritative resolution delivered by an executive adjudicator."""
        with self._lock:
            rec = self._conflicts.get(conflict_id)
            if not rec:
                raise ValueError(f"Conflict '{conflict_id}' not found.")

            rec.status = ConflictStatus.RESOLVED_BY_ESCALATION
            rec.resolution_strategy = f"EXECUTIVE_ADJUDICATION_{adjudicator}"
            rec.resolution_details = f"Resolved by {adjudicator}: {chosen_resolution}. Rationale: {rationale}"
            rec.resolved_at = time.time()
            self._notify_parties(rec)

            logger.info("Escalated conflict '%s' resolved by %s: %s", conflict_id, adjudicator, chosen_resolution)
            return rec

    def _attempt_merge_resolution(self, proposals: Dict[str, Any]) -> Tuple[str, bool]:
        """Simple non-overlapping merge synthesizer using difflib."""
        try:
            base = proposals.get("base", "")
            prop_a = proposals.get("proposal_a")
            prop_b = proposals.get("proposal_b")

            if prop_a is None or prop_b is None:
                keys = list(proposals.keys())
                if len(keys) >= 2:
                    prop_a = str(proposals[keys[0]])
                    prop_b = str(proposals[keys[1]])
                else:
                    return "", False

            # If identical, easy resolve
            if prop_a == prop_b:
                return prop_a, True

            # If one is unchanged from base, pick the other
            if base:
                if prop_a == base and prop_b != base:
                    return prop_b, True
                if prop_b == base and prop_a != base:
                    return prop_a, True

            # Check if disjoint line sets
            lines_a = set(prop_a.splitlines())
            lines_b = set(prop_b.splitlines())
            base_lines = set(base.splitlines()) if base else set()

            # Overlapping modifications: if both changed or removed base lines
            if base_lines:
                removed_a = base_lines - lines_a
                removed_b = base_lines - lines_b
                if (removed_a & removed_b) and prop_a != prop_b:
                    return "", False

            # If base was empty and proposals are different, collision
            if not base and prop_a != prop_b:
                return "", False

            added_a = lines_a - base_lines
            added_b = lines_b - base_lines

            # If no intersection in added lines, we can safely combine
            if not (added_a & added_b):
                combined = prop_a + "\n" + "\n".join(added_b)
                return combined, True

            return "", False
        except Exception:
            return "", False

    def _notify_parties(self, rec: ConflictRecord) -> None:
        """Broadcasts conflict resolution back to involved parties."""
        if not self.bus:
            return
        for party in rec.parties_involved:
            self.bus.send_message(
                OrgMessage(
                    sender="ConflictResolver",
                    receiver=party,
                    priority=MessagePriority.HIGH,
                    message_type=OrgMessageType.NOTIFICATION,
                    payload={
                        "conflict_id": rec.conflict_id,
                        "status": rec.status.value,
                        "resolution_strategy": rec.resolution_strategy,
                        "details": rec.resolution_details,
                    },
                )
            )

    def get_conflict(self, conflict_id: str) -> Optional[ConflictRecord]:
        """Retrieves conflict record by ID."""
        with self._lock:
            return self._conflicts.get(conflict_id)

    def list_conflicts(self, status: Optional[ConflictStatus | str] = None) -> List[Dict[str, Any]]:
        """Lists conflicts, optionally filtered by status."""
        with self._lock:
            st_val = status.value if hasattr(status, "value") else str(status) if status else None
            results = []
            for c in self._conflicts.values():
                c_st = c.status.value if hasattr(c.status, "value") else str(c.status)
                if st_val and c_st != st_val:
                    continue
                results.append(c.to_dict())
            return results
