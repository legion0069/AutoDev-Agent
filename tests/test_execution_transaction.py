"""
test_execution_transaction.py - Comprehensive Tests for Transaction Models & Lifecycle (v2.1)
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

from core.execution_transaction import (
    ExecutionAuthorizationError,
    ExecutionEngineError,
    ExecutionReport,
    ExecutionStatus,
    ExecutionTransaction,
    FileSnapshot,
    InvalidStateTransitionError,
    OperationExecutionResult,
    StageExecutionResult,
    TransactionError,
    WorkspaceSafetyError,
    validate_state_transition,
)


# =============================================================================
# 1. STATE TRANSITION TESTS
# =============================================================================

def test_valid_state_transitions():
    """Verifies that all standard legal lifecycle transitions succeed."""
    # PENDING -> VALIDATING -> READY -> RUNNING -> SUCCEEDED
    validate_state_transition(ExecutionStatus.PENDING, ExecutionStatus.VALIDATING)
    validate_state_transition(ExecutionStatus.VALIDATING, ExecutionStatus.READY)
    validate_state_transition(ExecutionStatus.READY, ExecutionStatus.RUNNING)
    validate_state_transition(ExecutionStatus.RUNNING, ExecutionStatus.SUCCEEDED)

    # RUNNING -> ROLLING_BACK -> ROLLED_BACK
    validate_state_transition(ExecutionStatus.RUNNING, ExecutionStatus.ROLLING_BACK)
    validate_state_transition(ExecutionStatus.ROLLING_BACK, ExecutionStatus.ROLLED_BACK)

    # Self-transition is a no-op
    validate_state_transition(ExecutionStatus.RUNNING, ExecutionStatus.RUNNING)


def test_invalid_state_transitions_raise_error():
    """Verifies that illegal state transitions raise InvalidStateTransitionError."""
    # Cannot jump directly from PENDING to SUCCEEDED
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        validate_state_transition(ExecutionStatus.PENDING, ExecutionStatus.SUCCEEDED)
    assert "cannot transition" in str(exc_info.value)

    # Cannot transition from terminal SUCCEEDED to RUNNING
    with pytest.raises(InvalidStateTransitionError):
        validate_state_transition(ExecutionStatus.SUCCEEDED, ExecutionStatus.RUNNING)

    # Cannot transition from CANCELLED to READY
    with pytest.raises(InvalidStateTransitionError):
        validate_state_transition(ExecutionStatus.CANCELLED, ExecutionStatus.READY)


def test_transition_to_updates_transaction_lifecycle():
    """Verifies that ExecutionTransaction.transition_to updates timestamps and status."""
    tx = ExecutionTransaction(
        transaction_id="tx-test-01",
        plan_id="plan-01",
        task_id="task-01",
        workspace_root="/workspace",
    )
    assert tx.status == ExecutionStatus.PENDING
    assert tx.completed_at is None

    tx.transition_to(ExecutionStatus.VALIDATING)
    assert tx.status == ExecutionStatus.VALIDATING

    tx.transition_to(ExecutionStatus.READY)
    assert tx.status == ExecutionStatus.READY

    tx.transition_to(ExecutionStatus.RUNNING)
    assert tx.status == ExecutionStatus.RUNNING

    tx.transition_to(ExecutionStatus.SUCCEEDED)
    assert tx.status == ExecutionStatus.SUCCEEDED
    assert tx.completed_at is not None


# =============================================================================
# 2. FILE SNAPSHOT TESTS
# =============================================================================

def test_file_snapshot_capture_existing_text(tmp_path):
    """Verifies FileSnapshot captures existing text file content, size, and SHA256 hash."""
    file_path = tmp_path / "src" / "sample.py"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("print('hello world')", encoding="utf-8")

    tx = ExecutionTransaction(
        transaction_id="tx-snap-01",
        plan_id="plan-01",
        task_id="task-01",
        workspace_root=tmp_path,
    )

    snapshot = tx.capture_file_snapshot("src/sample.py")
    assert snapshot.exists_before is True
    assert snapshot.relative_path == "src/sample.py"
    assert snapshot.size_bytes_before > 0
    assert snapshot.content_hash_before is not None
    assert snapshot.is_binary is False
    assert snapshot.content_backup == "print('hello world')"


def test_file_snapshot_capture_nonexistent_file(tmp_path):
    """Verifies FileSnapshot captures non-existent file cleanly."""
    tx = ExecutionTransaction(
        transaction_id="tx-snap-02",
        plan_id="plan-01",
        task_id="task-01",
        workspace_root=tmp_path,
    )

    snapshot = tx.capture_file_snapshot("src/new_module.py")
    assert snapshot.exists_before is False
    assert snapshot.content_hash_before is None
    assert snapshot.size_bytes_before == 0
    assert snapshot.content_backup is None


def test_file_snapshot_capture_idempotent_preserves_initial_baseline(tmp_path):
    """Verifies that calling capture_file_snapshot twice preserves the original baseline."""
    file_path = tmp_path / "data.txt"
    file_path.write_text("Initial Content", encoding="utf-8")

    tx = ExecutionTransaction(
        transaction_id="tx-snap-03",
        plan_id="plan-01",
        task_id="task-01",
        workspace_root=tmp_path,
    )

    snap1 = tx.capture_file_snapshot("data.txt")
    assert snap1.content_backup == "Initial Content"

    # Mutate file on disk
    file_path.write_text("Mutated Content", encoding="utf-8")

    # Second capture must return original snapshot
    snap2 = tx.capture_file_snapshot("data.txt")
    assert snap2.content_backup == "Initial Content"
    assert snap1 is snap2


def test_file_snapshot_to_dict_and_from_dict():
    """Verifies FileSnapshot serialization roundtrip."""
    snap = FileSnapshot(
        relative_path="core/utils.py",
        absolute_path="/workspace/core/utils.py",
        exists_before=True,
        content_hash_before="abc123sha",
        size_bytes_before=150,
        is_binary=False,
    )
    data = snap.to_dict()
    restored = FileSnapshot.from_dict(data)
    assert restored.relative_path == snap.relative_path
    assert restored.content_hash_before == snap.content_hash_before
    assert restored.exists_before is True


# =============================================================================
# 3. OPERATION & STAGE RESULT TESTS
# =============================================================================

def test_operation_execution_result_roundtrip():
    """Verifies OperationExecutionResult serialization and schema defaults."""
    op_res = OperationExecutionResult(
        operation_id="OP-001",
        status=ExecutionStatus.SUCCEEDED,
        started_at="2026-10-09T00:00:00Z",
        finished_at="2026-10-09T00:00:02Z",
        duration_seconds=2.0,
        modified_files=["core/module.py"],
        created_files=["tests/test_module.py"],
        deleted_files=[],
    )
    d = op_res.to_dict()
    restored = OperationExecutionResult.from_dict(d)
    assert restored.operation_id == "OP-001"
    assert restored.status == ExecutionStatus.SUCCEEDED
    assert restored.modified_files == ["core/module.py"]
    assert restored.duration_seconds == 2.0


def test_stage_execution_result_roundtrip():
    """Verifies StageExecutionResult serialization with child operation results."""
    stage_res = StageExecutionResult(
        stage_number=1,
        status=ExecutionStatus.SUCCEEDED,
        operation_results=[
            OperationExecutionResult(
                operation_id="OP-001",
                status=ExecutionStatus.SUCCEEDED,
                duration_seconds=1.5,
            )
        ],
        validation_results={"gate-lint": {"passed": True}},
        checkpoint_id="chk-01",
        duration_seconds=1.5,
    )
    d = stage_res.to_dict()
    restored = StageExecutionResult.from_dict(d)
    assert restored.stage_number == 1
    assert restored.status == ExecutionStatus.SUCCEEDED
    assert len(restored.operation_results) == 1
    assert restored.checkpoint_id == "chk-01"


# =============================================================================
# 4. EXECUTION TRANSACTION MUTATION TRACKING
# =============================================================================

def test_execution_transaction_record_changes(tmp_path):
    """Verifies record_change tracks created, modified, and deleted files cleanly."""
    tx = ExecutionTransaction(
        transaction_id="tx-mut-01",
        plan_id="plan-01",
        task_id="task-01",
        workspace_root=tmp_path,
    )

    tx.record_change("src/a.py", "CREATE")
    assert "src/a.py" in tx.created_files
    assert "src/a.py" not in tx.modified_files

    tx.record_change("src/b.py", "MODIFY")
    assert "src/b.py" in tx.modified_files

    tx.record_change("src/c.py", "DELETE")
    assert "src/c.py" in tx.deleted_files

    # Modifying a created file stays in created_files
    tx.record_change("src/a.py", "MODIFY")
    assert "src/a.py" in tx.created_files
    assert "src/a.py" not in tx.modified_files


def test_execution_transaction_checkpoints():
    """Verifies checkpoint ID registration in transaction."""
    tx = ExecutionTransaction(
        transaction_id="tx-chk-01",
        plan_id="plan-01",
        task_id="task-01",
        workspace_root="/workspace",
    )
    tx.create_checkpoint("chk-stage-1")
    tx.create_checkpoint("chk-stage-2")
    assert tx.checkpoint_ids == ["chk-stage-1", "chk-stage-2"]


def test_execution_transaction_to_dict_and_from_dict(tmp_path):
    """Verifies full ExecutionTransaction serialization and restoration."""
    tx = ExecutionTransaction(
        transaction_id="tx-full-01",
        plan_id="plan-01",
        task_id="task-01",
        workspace_root=tmp_path,
        initial_git_head="commit-sha-1234",
    )
    tx.record_change("src/main.py", "MODIFY")
    tx.create_checkpoint("chk-01")

    data = tx.to_dict()
    restored = ExecutionTransaction.from_dict(data)

    assert restored.transaction_id == "tx-full-01"
    assert restored.initial_git_head == "commit-sha-1234"
    assert "src/main.py" in restored.modified_files
    assert "chk-01" in restored.checkpoint_ids


# =============================================================================
# 5. EXECUTION REPORT TESTS
# =============================================================================

def test_execution_report_serialization():
    """Verifies ExecutionReport serialization, JSON formatting, and deserialization."""
    report = ExecutionReport(
        transaction_id="tx-rep-01",
        overall_success=True,
        status=ExecutionStatus.SUCCEEDED,
        stages_completed=3,
        stages_failed=0,
        operations_completed=5,
        operations_failed=0,
        files_created=["src/new.py"],
        files_modified=["src/old.py"],
        files_deleted=[],
        duration_seconds=12.4,
    )

    json_str = report.to_json()
    assert '"overall_success": true' in json_str
    assert '"stages_completed": 3' in json_str

    parsed = json.loads(json_str)
    restored = ExecutionReport.from_dict(parsed)
    assert restored.transaction_id == "tx-rep-01"
    assert restored.overall_success is True
    assert restored.status == ExecutionStatus.SUCCEEDED
    assert restored.files_created == ["src/new.py"]
