"""
AutoDev Repair Transaction (v2.6)
Manages the strict state machine and durable lifecycle for autonomous repair operations.
"""

from __future__ import annotations

import enum
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

from core.repair_models import CandidatePatch, RepairPlan

logger = logging.getLogger(__name__)


class RepairState(str, enum.Enum):
    """Formal states in a self-healing repair transaction lifecycle."""
    CREATED = "created"
    DIAGNOSING = "diagnosing"
    PLANNED = "planned"
    PATCH_GENERATED = "patch_generated"
    PATCH_VALIDATED = "patch_validated"
    APPLIED_IN_CANDIDATE = "applied_in_candidate"
    VERIFYING = "verifying"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    VERIFICATION_FAILED = "verification_failed"
    ROLLBACK_PENDING = "rollback_pending"
    ROLLED_BACK = "rolled_back"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    CANCELLED = "cancelled"
    RECOVERY_REQUIRED = "recovery_required"


# Allowed state transitions for verification safety
VALID_TRANSITIONS: Dict[RepairState, Set[RepairState]] = {
    RepairState.CREATED: {RepairState.DIAGNOSING, RepairState.CANCELLED},
    RepairState.DIAGNOSING: {RepairState.PLANNED, RepairState.REJECTED, RepairState.NEEDS_HUMAN_REVIEW, RepairState.CANCELLED},
    RepairState.PLANNED: {RepairState.PATCH_GENERATED, RepairState.REJECTED, RepairState.NEEDS_HUMAN_REVIEW, RepairState.CANCELLED},
    RepairState.PATCH_GENERATED: {RepairState.PATCH_VALIDATED, RepairState.NEEDS_HUMAN_REVIEW, RepairState.REJECTED, RepairState.CANCELLED},
    RepairState.PATCH_VALIDATED: {RepairState.APPLIED_IN_CANDIDATE, RepairState.REJECTED, RepairState.NEEDS_HUMAN_REVIEW, RepairState.CANCELLED},
    RepairState.APPLIED_IN_CANDIDATE: {RepairState.VERIFYING, RepairState.ROLLBACK_PENDING, RepairState.RECOVERY_REQUIRED},
    RepairState.VERIFYING: {RepairState.ACCEPTED, RepairState.VERIFICATION_FAILED, RepairState.ROLLBACK_PENDING, RepairState.NEEDS_HUMAN_REVIEW},
    RepairState.VERIFICATION_FAILED: {RepairState.ROLLBACK_PENDING, RepairState.ROLLED_BACK, RepairState.REJECTED, RepairState.RECOVERY_REQUIRED},
    RepairState.ROLLBACK_PENDING: {RepairState.ROLLED_BACK, RepairState.RECOVERY_REQUIRED},
    RepairState.NEEDS_HUMAN_REVIEW: {RepairState.APPLIED_IN_CANDIDATE, RepairState.PATCH_VALIDATED, RepairState.VERIFYING, RepairState.ACCEPTED, RepairState.REJECTED, RepairState.CANCELLED},
    RepairState.ROLLED_BACK: {RepairState.REJECTED, RepairState.CREATED, RepairState.VERIFICATION_FAILED},
    RepairState.ACCEPTED: set(),
    RepairState.REJECTED: set(),
    RepairState.CANCELLED: set(),
    RepairState.RECOVERY_REQUIRED: {RepairState.ROLLED_BACK, RepairState.REJECTED},
}


@dataclass
class StateTransitionRecord:
    """Record of a single state transition."""
    from_state: str
    to_state: str
    timestamp: float = field(default_factory=time.time)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RepairTransaction:
    """Durable unit of work for diagnosing, applying, and verifying a code repair."""
    repair_id: str = field(default_factory=lambda: f"rep_{uuid.uuid4().hex[:8]}")
    project_id: str = "default_project"
    transaction_id: Optional[str] = None
    state: RepairState = RepairState.CREATED
    plan: Optional[RepairPlan] = None
    patch: Optional[CandidatePatch] = None
    file_snapshots: Dict[str, str] = field(default_factory=dict)  # rel_path -> original content
    validation_gate_results: Dict[str, Any] = field(default_factory=dict)
    state_history: List[StateTransitionRecord] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error_message: Optional[str] = None

    def can_transition_to(self, new_state: RepairState) -> bool:
        """Checks if moving to new_state is allowed from current state."""
        return new_state in VALID_TRANSITIONS.get(self.state, set())

    def transition_to(self, new_state: RepairState, reason: str = "") -> bool:
        """Applies state transition if valid, recording audit history."""
        if not self.can_transition_to(new_state):
            logger.error(f"Invalid repair transition from {self.state.value} to {new_state.value}")
            return False

        record = StateTransitionRecord(
            from_state=self.state.value,
            to_state=new_state.value,
            reason=reason,
        )
        self.state_history.append(record)
        self.state = new_state
        self.updated_at = time.time()
        logger.info(f"RepairTransaction {self.repair_id}: {record.from_state} -> {record.to_state} ({reason})")
        return True

    def record_file_snapshot(self, rel_path: str, content: str):
        """Records baseline file content prior to candidate application."""
        if rel_path not in self.file_snapshots:
            self.file_snapshots[rel_path] = content

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repair_id": self.repair_id,
            "project_id": self.project_id,
            "transaction_id": self.transaction_id,
            "state": self.state.value,
            "plan": self.plan.to_dict() if self.plan else None,
            "patch": self.patch.to_dict() if self.patch else None,
            "file_snapshots": self.file_snapshots,
            "file_snapshots_count": len(self.file_snapshots),
            "validation_gate_results": self.validation_gate_results,
            "state_history": [r.to_dict() for r in self.state_history],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error_message": self.error_message,
        }
