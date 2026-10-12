"""
test_execution_recovery.py - Comprehensive Tests for Verified Transactional Recovery & Rollback (v2.1)
"""

import pytest
from pathlib import Path

from core.execution_journal import ExecutionJournal
from core.execution_recovery import (
    ExecutionRecovery,
    RecoveryError,
    RecoveryResult,
    RestorationVerificationError,
)
from core.execution_transaction import (
    ExecutionStatus,
    ExecutionTransaction,
    FileSnapshot,
)


# =============================================================================
# 1. TRANSACTION RECOVERY & ROLLBACK TESTS
# =============================================================================

def test_rollback_modified_files(tmp_path):
    """Verifies that modified files are cleanly restored to pre-mutation content."""
    mod_file = tmp_path / "src" / "service.py"
    mod_file.parent.mkdir(parents=True)
    mod_file.write_text("def original_function(): pass\n", encoding="utf-8")

    tx = ExecutionTransaction(
        transaction_id="tx-rec-01",
        plan_id="p1",
        task_id="t1",
        workspace_root=tmp_path,
    )
    # Capture snapshot before mutation
    tx.capture_file_snapshot("src/service.py")

    # Simulate mutation by agent
    mod_file.write_text("def broken_mutated_function(): raise Exception()\n", encoding="utf-8")
    tx.record_change("src/service.py", "MODIFY")

    recovery = ExecutionRecovery(workspace_root=tmp_path)
    res: RecoveryResult = recovery.rollback_transaction(transaction=tx)

    assert res.success is True
    assert res.verification_passed is True
    assert "src/service.py" in res.files_reverted
    assert mod_file.read_text(encoding="utf-8") == "def original_function(): pass\n"
    assert tx.status == ExecutionStatus.ROLLED_BACK


def test_rollback_created_files(tmp_path):
    """Verifies that files created during the transaction are deleted upon rollback."""
    new_file = tmp_path / "src" / "new_handler.py"

    tx = ExecutionTransaction(
        transaction_id="tx-rec-02",
        plan_id="p1",
        task_id="t1",
        workspace_root=tmp_path,
    )
    # Capture snapshot of non-existent file
    tx.capture_file_snapshot("src/new_handler.py")

    # Simulate creation
    new_file.parent.mkdir(parents=True, exist_ok=True)
    new_file.write_text("class NewHandler: pass\n", encoding="utf-8")
    tx.record_change("src/new_handler.py", "CREATE")
    assert new_file.exists()

    recovery = ExecutionRecovery(workspace_root=tmp_path)
    res: RecoveryResult = recovery.rollback_transaction(transaction=tx)

    assert res.success is True
    assert res.verification_passed is True
    assert "src/new_handler.py" in res.files_deleted
    assert not new_file.exists()


def test_rollback_deleted_files(tmp_path):
    """Verifies that files deleted during transaction are restored upon rollback."""
    del_file = tmp_path / "docs" / "api.md"
    del_file.parent.mkdir(parents=True)
    del_file.write_text("# API Reference\nInitial docs content.\n", encoding="utf-8")

    tx = ExecutionTransaction(
        transaction_id="tx-rec-03",
        plan_id="p1",
        task_id="t1",
        workspace_root=tmp_path,
    )
    tx.capture_file_snapshot("docs/api.md")

    # Simulate deletion
    del_file.unlink()
    tx.record_change("docs/api.md", "DELETE")
    assert not del_file.exists()

    recovery = ExecutionRecovery(workspace_root=tmp_path)
    res: RecoveryResult = recovery.rollback_transaction(transaction=tx)

    assert res.success is True
    assert res.verification_passed is True
    assert "docs/api.md" in res.files_restored
    assert del_file.exists()
    assert del_file.read_text(encoding="utf-8") == "# API Reference\nInitial docs content.\n"


def test_rollback_idempotent_execution(tmp_path):
    """Verifies that executing rollback repeatedly is safe and idempotent."""
    target_file = tmp_path / "app.py"
    target_file.write_text("BASE_STATE = True\n", encoding="utf-8")

    tx = ExecutionTransaction(
        transaction_id="tx-rec-04",
        plan_id="p1",
        task_id="t1",
        workspace_root=tmp_path,
    )
    tx.capture_file_snapshot("app.py")
    target_file.write_text("BASE_STATE = False\n", encoding="utf-8")
    tx.record_change("app.py", "MODIFY")

    recovery = ExecutionRecovery(workspace_root=tmp_path)

    # First rollback
    res1 = recovery.rollback_transaction(transaction=tx)
    assert res1.success is True
    assert target_file.read_text(encoding="utf-8") == "BASE_STATE = True\n"

    # Second rollback
    res2 = recovery.rollback_transaction(transaction=tx)
    assert res2.success is True
    assert res2.verification_passed is True
    assert target_file.read_text(encoding="utf-8") == "BASE_STATE = True\n"


def test_rollback_with_execution_journal_logging(tmp_path):
    """Verifies that rollback operations append audit events to the ExecutionJournal."""
    journal_dir = tmp_path / "journal"
    journal = ExecutionJournal("tx-journal-rec-05", journal_root=journal_dir)

    target_file = tmp_path / "file.py"
    target_file.write_text("ORIGINAL", encoding="utf-8")

    tx = ExecutionTransaction(
        transaction_id="tx-journal-rec-05",
        plan_id="p1",
        task_id="t1",
        workspace_root=tmp_path,
    )
    tx.capture_file_snapshot("file.py")
    target_file.write_text("MUTATED", encoding="utf-8")
    tx.record_change("file.py", "MODIFY")

    recovery = ExecutionRecovery(workspace_root=tmp_path)
    res = recovery.rollback_transaction(transaction=tx, journal=journal)

    assert res.success is True
    events = journal.load_events(verify_integrity=True)
    event_types = [e.event_type for e in events]
    assert "ROLLBACK_STARTED" in event_types
    assert "FILE_REVERTED" in event_types
    assert "ROLLBACK_COMPLETED" in event_types
