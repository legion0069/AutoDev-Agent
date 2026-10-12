"""
execution_transaction.py - Transaction Boundaries, Lifecycle & State Models for AutoDev (v2.1)

Manages transactional execution states, pre-mutation workspace snapshots,
state transitions, and aggregated telemetry for change execution plans.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Ensure project root is available on sys.path
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger("AutoDev.ExecutionTransaction")


# =============================================================================
# EXCEPTION HIERARCHY
# =============================================================================

class ExecutionEngineError(Exception):
    """Base exception for all execution engine and transaction errors."""
    pass


class InvalidStateTransitionError(ExecutionEngineError):
    """Raised when an invalid state transition is attempted on a transaction or operation."""
    pass


class TransactionError(ExecutionEngineError):
    """Raised when a transactional boundary or consistency check fails."""
    pass


class WorkspaceSafetyError(ExecutionEngineError):
    """Raised when workspace safety checks detect dangerous or dirty conditions."""
    pass


class ExecutionAuthorizationError(ExecutionEngineError):
    """Raised when an operation or plan is not authorized for execution."""
    pass


# =============================================================================
# ENUMS & STATE TRANSITIONS
# =============================================================================

class ExecutionStatus(str, Enum):
    """Lifecycle states for transactions, stages, and operations."""
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    PAUSED = "PAUSED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


# Explicit valid state transition graph
VALID_STATE_TRANSITIONS: Dict[ExecutionStatus, Set[ExecutionStatus]] = {
    ExecutionStatus.PENDING: {
        ExecutionStatus.VALIDATING,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.WAITING_FOR_APPROVAL,
        ExecutionStatus.ROLLING_BACK,
        ExecutionStatus.FAILED,
    },
    ExecutionStatus.VALIDATING: {
        ExecutionStatus.READY,
        ExecutionStatus.WAITING_FOR_APPROVAL,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.ROLLING_BACK,
    },
    ExecutionStatus.WAITING_FOR_APPROVAL: {
        ExecutionStatus.READY,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.FAILED,
        ExecutionStatus.ROLLING_BACK,
    },
    ExecutionStatus.READY: {
        ExecutionStatus.RUNNING,
        ExecutionStatus.PAUSED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.ROLLING_BACK,
        ExecutionStatus.FAILED,
    },
    ExecutionStatus.RUNNING: {
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.PAUSED,
        ExecutionStatus.ROLLING_BACK,
        ExecutionStatus.INTERRUPTED,
        ExecutionStatus.CANCELLED,
    },
    ExecutionStatus.PAUSED: {
        ExecutionStatus.RUNNING,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.INTERRUPTED,
        ExecutionStatus.ROLLING_BACK,
        ExecutionStatus.FAILED,
    },
    ExecutionStatus.ROLLING_BACK: {
        ExecutionStatus.ROLLED_BACK,
        ExecutionStatus.RECOVERY_REQUIRED,
        ExecutionStatus.FAILED,
    },
    ExecutionStatus.ROLLED_BACK: {
        ExecutionStatus.ROLLED_BACK,
        ExecutionStatus.FAILED,
        ExecutionStatus.RECOVERY_REQUIRED,
    },
    ExecutionStatus.RECOVERY_REQUIRED: {
        ExecutionStatus.ROLLING_BACK,
        ExecutionStatus.ROLLED_BACK,
        ExecutionStatus.FAILED,
    },
    ExecutionStatus.INTERRUPTED: {
        ExecutionStatus.READY,
        ExecutionStatus.RUNNING,
        ExecutionStatus.ROLLING_BACK,
        ExecutionStatus.RECOVERY_REQUIRED,
        ExecutionStatus.FAILED,
    },
    ExecutionStatus.SUCCEEDED: set(),  # Terminal state
    ExecutionStatus.FAILED: {
        ExecutionStatus.ROLLING_BACK,
        ExecutionStatus.RECOVERY_REQUIRED,
        ExecutionStatus.ROLLED_BACK,
    },
    ExecutionStatus.CANCELLED: {
        ExecutionStatus.ROLLING_BACK,
        ExecutionStatus.ROLLED_BACK,
    },
}


def validate_state_transition(
    current_state: ExecutionStatus,
    target_state: ExecutionStatus,
    entity_name: str = "Transaction",
) -> None:
    """
    Validates whether a state transition is permitted.
    
    Raises:
        InvalidStateTransitionError: If the transition is illegal.
    """
    if current_state == target_state:
        return
    allowed = VALID_STATE_TRANSITIONS.get(current_state, set())
    if target_state not in allowed:
        raise InvalidStateTransitionError(
            f"Illegal {entity_name} state transition: cannot transition from "
            f"'{current_state.value}' to '{target_state.value}'. "
            f"Allowed target states: {[s.value for s in allowed]}"
        )


# =============================================================================
# DATA MODELS & TELEMETRY
# =============================================================================

@dataclass
class FileSnapshot:
    """
    Immutable representation of a file's state captured before mutation.
    """
    relative_path: str
    absolute_path: str
    exists_before: bool
    content_hash_before: Optional[str] = None
    size_bytes_before: int = 0
    is_binary: bool = False
    captured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    backup_path: Optional[str] = None
    content_backup: Optional[Union[str, bytes]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Returns JSON-serializable dictionary representation."""
        return {
            "relative_path": self.relative_path,
            "absolute_path": self.absolute_path,
            "exists_before": self.exists_before,
            "content_hash_before": self.content_hash_before,
            "size_bytes_before": self.size_bytes_before,
            "is_binary": self.is_binary,
            "captured_at": self.captured_at,
            "backup_path": self.backup_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FileSnapshot:
        """Constructs FileSnapshot from dictionary representation."""
        return cls(
            relative_path=data.get("relative_path", ""),
            absolute_path=data.get("absolute_path", ""),
            exists_before=bool(data.get("exists_before", False)),
            content_hash_before=data.get("content_hash_before"),
            size_bytes_before=int(data.get("size_bytes_before", 0)),
            is_binary=bool(data.get("is_binary", False)),
            captured_at=data.get(
                "captured_at", datetime.now(timezone.utc).isoformat()
            ),
            backup_path=data.get("backup_path"),
        )


@dataclass
class OperationExecutionResult:
    """
    Detailed telemetry result of an individual change operation execution.
    """
    operation_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: float = 0.0
    modified_files: List[str] = field(default_factory=list)
    created_files: List[str] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)
    validation_results: Dict[str, Any] = field(default_factory=dict)
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    recovery_status: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "status": self.status.value if isinstance(self.status, ExecutionStatus) else str(self.status),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "modified_files": list(self.modified_files),
            "created_files": list(self.created_files),
            "deleted_files": list(self.deleted_files),
            "validation_results": dict(self.validation_results),
            "error_type": self.error_type,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "recovery_status": self.recovery_status,
            "artifacts": list(self.artifacts),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OperationExecutionResult:
        raw_status = data.get("status", "PENDING")
        try:
            status = ExecutionStatus(raw_status)
        except ValueError:
            status = ExecutionStatus.PENDING

        return cls(
            operation_id=str(data.get("operation_id", "")),
            status=status,
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            modified_files=list(data.get("modified_files", [])),
            created_files=list(data.get("created_files", [])),
            deleted_files=list(data.get("deleted_files", [])),
            validation_results=dict(data.get("validation_results", {})),
            error_type=data.get("error_type"),
            error_message=data.get("error_message"),
            retry_count=int(data.get("retry_count", 0)),
            recovery_status=data.get("recovery_status"),
            artifacts=list(data.get("artifacts", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class StageExecutionResult:
    """
    Detailed telemetry result of an execution stage containing multiple operations.
    """
    stage_number: int
    status: ExecutionStatus = ExecutionStatus.PENDING
    operation_results: List[OperationExecutionResult] = field(default_factory=list)
    validation_results: Dict[str, Any] = field(default_factory=dict)
    checkpoint_id: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: float = 0.0
    failure_reason: Optional[str] = None
    recovery_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_number": self.stage_number,
            "status": self.status.value if isinstance(self.status, ExecutionStatus) else str(self.status),
            "operation_results": [r.to_dict() for r in self.operation_results],
            "validation_results": dict(self.validation_results),
            "checkpoint_id": self.checkpoint_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "failure_reason": self.failure_reason,
            "recovery_result": self.recovery_result,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StageExecutionResult:
        raw_status = data.get("status", "PENDING")
        try:
            status = ExecutionStatus(raw_status)
        except ValueError:
            status = ExecutionStatus.PENDING

        op_results = [
            OperationExecutionResult.from_dict(o)
            for o in data.get("operation_results", [])
        ]

        return cls(
            stage_number=int(data.get("stage_number", 1)),
            status=status,
            operation_results=op_results,
            validation_results=dict(data.get("validation_results", {})),
            checkpoint_id=data.get("checkpoint_id"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            failure_reason=data.get("failure_reason"),
            recovery_result=data.get("recovery_result"),
        )


@dataclass
class ExecutionReport:
    """
    Comprehensive structured audit report summarizing an entire execution transaction.
    """
    transaction_id: str
    overall_success: bool
    status: ExecutionStatus
    stages_completed: int = 0
    stages_failed: int = 0
    operations_completed: int = 0
    operations_failed: int = 0
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)
    validation_summary: Dict[str, Any] = field(default_factory=dict)
    rollback_summary: Optional[Dict[str, Any]] = None
    duration_seconds: float = 0.0
    recovery_required: bool = False
    workspace_clean: bool = True
    initial_git_head: Optional[str] = None
    final_git_head: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    finished_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "overall_success": self.overall_success,
            "status": self.status.value if isinstance(self.status, ExecutionStatus) else str(self.status),
            "stages_completed": self.stages_completed,
            "stages_failed": self.stages_failed,
            "operations_completed": self.operations_completed,
            "operations_failed": self.operations_failed,
            "files_created": list(self.files_created),
            "files_modified": list(self.files_modified),
            "files_deleted": list(self.files_deleted),
            "validation_summary": dict(self.validation_summary),
            "rollback_summary": self.rollback_summary,
            "duration_seconds": self.duration_seconds,
            "recovery_required": self.recovery_required,
            "workspace_clean": self.workspace_clean,
            "initial_git_head": self.initial_git_head,
            "final_git_head": self.final_git_head,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "artifacts": list(self.artifacts),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionReport:
        raw_status = data.get("status", "FAILED")
        try:
            status = ExecutionStatus(raw_status)
        except ValueError:
            status = ExecutionStatus.FAILED

        return cls(
            transaction_id=str(data.get("transaction_id", "")),
            overall_success=bool(data.get("overall_success", False)),
            status=status,
            stages_completed=int(data.get("stages_completed", 0)),
            stages_failed=int(data.get("stages_failed", 0)),
            operations_completed=int(data.get("operations_completed", 0)),
            operations_failed=int(data.get("operations_failed", 0)),
            files_created=list(data.get("files_created", [])),
            files_modified=list(data.get("files_modified", [])),
            files_deleted=list(data.get("files_deleted", [])),
            validation_summary=dict(data.get("validation_summary", {})),
            rollback_summary=data.get("rollback_summary"),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            recovery_required=bool(data.get("recovery_required", False)),
            workspace_clean=bool(data.get("workspace_clean", True)),
            initial_git_head=data.get("initial_git_head"),
            final_git_head=data.get("final_git_head"),
            warnings=list(data.get("warnings", [])),
            errors=list(data.get("errors", [])),
            artifacts=list(data.get("artifacts", [])),
            started_at=data.get("started_at", datetime.now(timezone.utc).isoformat()),
            finished_at=data.get("finished_at"),
        )


# =============================================================================
# EXECUTION TRANSACTION CLASS
# =============================================================================

class ExecutionTransaction:
    """
    Encapsulates the transactional state and lifecycle of a ChangeExecutionPlan execution.
    
    Tracks initial workspace fingerprints, pre-existing user modifications,
    stage checkpoints, file snapshots, and state transitions.
    """

    def __init__(
        self,
        transaction_id: str,
        plan_id: str = "plan-default",
        task_id: str = "task-default",
        workspace_root: Union[str, Path] = "projects",
        initial_git_head: Optional[str] = None,
        journal_path: Optional[Union[str, Path]] = None,
        mode: str = "apply",
    ) -> None:
        self.transaction_id = transaction_id
        self.plan_id = plan_id
        self.task_id = task_id
        self.workspace_root = Path(workspace_root).resolve()
        self.initial_git_head = initial_git_head
        self.journal_path = Path(journal_path).resolve() if journal_path else None
        self.mode = mode.lower()

        self.status = ExecutionStatus.PENDING
        self.started_at: str = datetime.now(timezone.utc).isoformat()
        self.updated_at: str = self.started_at
        self.completed_at: Optional[str] = None

        # Workspace fingerprinting
        self.initial_workspace_fingerprint: Dict[str, str] = {}
        self.pre_existing_modifications: Set[str] = set()
        self.pre_existing_untracked: Set[str] = set()

        # Mutation tracking
        self.snapshots: Dict[str, FileSnapshot] = {}
        self.modified_files: Set[str] = set()
        self.created_files: Set[str] = set()
        self.deleted_files: Set[str] = set()

        # Stage and checkpoint tracking
        self.completed_stages: List[StageExecutionResult] = []
        self.active_stage: Optional[int] = None
        self.checkpoint_ids: List[str] = []

        # Error and recovery
        self.failure_details: Optional[Dict[str, Any]] = None
        self.recovery_attempts: int = 0
        self.final_verification: Optional[Dict[str, Any]] = None

    def transition_to(self, target_state: ExecutionStatus) -> None:
        """Transitions transaction state with strict transition validation."""
        validate_state_transition(
            self.status, target_state, f"Transaction({self.transaction_id})"
        )
        old_state = self.status
        self.status = target_state
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if target_state in {
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.ROLLED_BACK,
            ExecutionStatus.CANCELLED,
        }:
            self.completed_at = self.updated_at
        logger.info(
            "Transaction %s state transition: %s -> %s",
            self.transaction_id,
            old_state.value,
            target_state.value,
        )

    def start_execution(self) -> None:
        """Helper to transition transaction to RUNNING via valid state graph."""
        if self.status == ExecutionStatus.PENDING:
            self.transition_to(ExecutionStatus.VALIDATING)
        if self.status == ExecutionStatus.VALIDATING:
            self.transition_to(ExecutionStatus.READY)
        if self.status in (ExecutionStatus.READY, ExecutionStatus.PAUSED):
            self.transition_to(ExecutionStatus.RUNNING)


    def complete_execution(self) -> None:
        """Helper to transition transaction to SUCCEEDED."""
        if self.status == ExecutionStatus.RUNNING:
            self.transition_to(ExecutionStatus.SUCCEEDED)

    def snapshot_file(self, relative_path: str, base_dir: Optional[Path] = None) -> FileSnapshot:
        """Alias for capture_file_snapshot."""
        return self.capture_file_snapshot(relative_path, base_dir=base_dir)

    def capture_file_snapshot(
        self, relative_path: str, base_dir: Optional[Path] = None
    ) -> FileSnapshot:
        """
        Captures a pre-mutation snapshot of a file before any write or delete occurs.
        If already captured in this transaction, returns existing snapshot to preserve initial baseline.
        """
        norm_rel = Path(relative_path).as_posix()
        if norm_rel in self.snapshots:
            return self.snapshots[norm_rel]

        root = (base_dir or self.workspace_root).resolve()
        target_path = (root / norm_rel).resolve()

        exists = target_path.exists()
        content_hash = None
        size_bytes = 0
        is_binary = False
        content_backup: Optional[Union[str, bytes]] = None

        if exists and target_path.is_file():
            try:
                raw_bytes = target_path.read_bytes()
                size_bytes = len(raw_bytes)
                content_hash = hashlib.sha256(raw_bytes).hexdigest()
                try:
                    content_backup = raw_bytes.decode("utf-8")
                    is_binary = False
                except UnicodeDecodeError:
                    content_backup = raw_bytes
                    is_binary = True
            except OSError as exc:
                logger.warning(
                    "Failed to read file for snapshot '%s': %s", target_path, exc
                )

        snapshot = FileSnapshot(
            relative_path=norm_rel,
            absolute_path=str(target_path),
            exists_before=exists,
            content_hash_before=content_hash,
            size_bytes_before=size_bytes,
            is_binary=is_binary,
            content_backup=content_backup,
        )
        self.snapshots[norm_rel] = snapshot
        return snapshot

    def record_change(
        self, relative_path: str, change_type: str
    ) -> None:
        """
        Records a file mutation performed under this transaction.
        """
        norm_rel = Path(relative_path).as_posix()
        change_upper = change_type.upper()

        if change_upper in {"CREATE", "CREATE_FILE"}:
            self.created_files.add(norm_rel)
            self.modified_files.discard(norm_rel)
            self.deleted_files.discard(norm_rel)
        elif change_upper in {"MODIFY", "MODIFY_FILE"}:
            if norm_rel not in self.created_files:
                self.modified_files.add(norm_rel)
            self.deleted_files.discard(norm_rel)
        elif change_upper in {"DELETE", "DELETE_FILE"}:
            self.deleted_files.add(norm_rel)
            self.modified_files.discard(norm_rel)
            self.created_files.discard(norm_rel)

        self.updated_at = datetime.now(timezone.utc).isoformat()

    def create_checkpoint(self, checkpoint_id: str) -> None:
        """Records a new progress checkpoint ID."""
        if checkpoint_id not in self.checkpoint_ids:
            self.checkpoint_ids.append(checkpoint_id)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serializes full transaction state."""
        return {
            "transaction_id": self.transaction_id,
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "workspace_root": str(self.workspace_root),
            "initial_git_head": self.initial_git_head,
            "journal_path": str(self.journal_path) if self.journal_path else None,
            "mode": self.mode,
            "status": self.status.value,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "initial_workspace_fingerprint": self.initial_workspace_fingerprint,
            "pre_existing_modifications": list(self.pre_existing_modifications),
            "pre_existing_untracked": list(self.pre_existing_untracked),
            "snapshots": {k: v.to_dict() for k, v in self.snapshots.items()},
            "modified_files": list(self.modified_files),
            "created_files": list(self.created_files),
            "deleted_files": list(self.deleted_files),
            "completed_stages": [s.to_dict() for s in self.completed_stages],
            "active_stage": self.active_stage,
            "checkpoint_ids": list(self.checkpoint_ids),
            "failure_details": self.failure_details,
            "recovery_attempts": self.recovery_attempts,
            "final_verification": self.final_verification,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionTransaction:
        """Deserializes transaction from dictionary representation."""
        tx = cls(
            transaction_id=str(data.get("transaction_id", "")),
            plan_id=str(data.get("plan_id", "")),
            task_id=str(data.get("task_id", "")),
            workspace_root=Path(data.get("workspace_root", ".")),
            initial_git_head=data.get("initial_git_head"),
            journal_path=Path(data["journal_path"]) if data.get("journal_path") else None,
            mode=str(data.get("mode", "apply")),
        )
        raw_status = data.get("status", "PENDING")
        try:
            tx.status = ExecutionStatus(raw_status)
        except ValueError:
            tx.status = ExecutionStatus.PENDING

        tx.started_at = data.get("started_at", tx.started_at)
        tx.updated_at = data.get("updated_at", tx.updated_at)
        tx.completed_at = data.get("completed_at")
        tx.initial_workspace_fingerprint = dict(
            data.get("initial_workspace_fingerprint", {})
        )
        tx.pre_existing_modifications = set(
            data.get("pre_existing_modifications", [])
        )
        tx.pre_existing_untracked = set(data.get("pre_existing_untracked", []))
        tx.snapshots = {
            k: FileSnapshot.from_dict(v)
            for k, v in data.get("snapshots", {}).items()
        }
        tx.modified_files = set(data.get("modified_files", []))
        tx.created_files = set(data.get("created_files", []))
        tx.deleted_files = set(data.get("deleted_files", []))
        tx.completed_stages = [
            StageExecutionResult.from_dict(s)
            for s in data.get("completed_stages", [])
        ]
        tx.active_stage = data.get("active_stage")
        tx.checkpoint_ids = list(data.get("checkpoint_ids", []))
        tx.failure_details = data.get("failure_details")
        tx.recovery_attempts = int(data.get("recovery_attempts", 0))
        tx.final_verification = data.get("final_verification")
        return tx
