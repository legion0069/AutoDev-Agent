"""
test_execution_lock.py - Comprehensive Tests for Workspace Locking & Concurrency Control (v2.1)
"""

import json
import os
import socket
import time
import pytest
from pathlib import Path

from core.execution_lock import (
    LockAcquisitionTimeoutError,
    LockMetadata,
    LockOwnershipError,
    ParallelOperationScheduler,
    WorkspaceLock,
    WorkspaceLockError,
)


# =============================================================================
# 1. WORKSPACE LOCK TESTS
# =============================================================================

def test_workspace_lock_acquire_and_release(tmp_path):
    """Verifies atomic acquisition and clean release of workspace lock."""
    lock = WorkspaceLock(workspace_root=tmp_path)
    assert lock.is_locked is False

    meta = lock.acquire(transaction_id="tx-lock-01", timeout_seconds=1.0)
    assert meta.transaction_id == "tx-lock-01"
    assert meta.pid == os.getpid()
    assert lock.is_locked is True
    assert (tmp_path / ".autodev.lock").exists()

    # Release
    released = lock.release(transaction_id="tx-lock-01")
    assert released is True
    assert lock.is_locked is False
    assert not (tmp_path / ".autodev.lock").exists()


def test_workspace_lock_reentrant_same_transaction(tmp_path):
    """Verifies that acquiring the lock twice with the same tx_id and PID succeeds."""
    lock = WorkspaceLock(workspace_root=tmp_path)
    meta1 = lock.acquire(transaction_id="tx-reenter-01", timeout_seconds=1.0)
    meta2 = lock.acquire(transaction_id="tx-reenter-01", timeout_seconds=1.0)

    assert meta1.owner_token == meta2.owner_token
    assert lock.is_locked is True
    lock.release(transaction_id="tx-reenter-01")


def test_workspace_lock_timeout_different_transaction(tmp_path):
    """Verifies that a competing transaction times out while waiting for the lock."""
    lock1 = WorkspaceLock(workspace_root=tmp_path)
    lock1.acquire(transaction_id="tx-first-01", timeout_seconds=1.0)

    lock2 = WorkspaceLock(workspace_root=tmp_path)
    with pytest.raises(LockAcquisitionTimeoutError) as exc_info:
        lock2.acquire(transaction_id="tx-competing-02", timeout_seconds=0.2)

    assert "Could not acquire workspace lock" in str(exc_info.value)
    lock1.release("tx-first-01")


def test_workspace_lock_release_ownership_verification(tmp_path):
    """Verifies that an unauthorized entity cannot release someone else's lock."""
    lock = WorkspaceLock(workspace_root=tmp_path)
    lock.acquire(transaction_id="tx-owner-01")

    with pytest.raises(LockOwnershipError) as exc_info:
        lock.release(transaction_id="tx-imposter-02")
    assert "Cannot release lock: owned by transaction" in str(exc_info.value)

    # Clean release with correct ID
    lock.release(transaction_id="tx-owner-01")


def test_workspace_lock_stale_lock_recovery(tmp_path):
    """Verifies that a stale lock from a dead PID is safely reclaimed."""
    lock_file = tmp_path / ".autodev.lock"
    # Write lock metadata with a dead PID (e.g. 999999)
    stale_meta = LockMetadata(
        owner_token="stale-token",
        transaction_id="tx-dead-pid",
        pid=999999,
        hostname=socket.gethostname(),
        ttl_seconds=300.0,
    )
    lock_file.write_text(json.dumps(stale_meta.to_dict()), encoding="utf-8")

    lock = WorkspaceLock(workspace_root=tmp_path)
    # Reclaiming stale lock must succeed
    meta = lock.acquire(transaction_id="tx-new-live-01", timeout_seconds=1.0)
    assert meta.transaction_id == "tx-new-live-01"
    assert lock.is_locked is True
    lock.release("tx-new-live-01")


# =============================================================================
# 2. PARALLEL OPERATION SCHEDULER TESTS
# =============================================================================

def test_parallel_scheduler_bounded_execution():
    """Verifies bounded parallel execution of operations across workers."""
    scheduler = ParallelOperationScheduler(max_workers=3)
    ops = [f"op_{i}" for i in range(6)]

    def _mock_work(op: str) -> str:
        time.sleep(0.01)
        return f"result_{op}"

    results = scheduler.execute_parallel_operations(ops, _mock_work)
    assert len(results) == 6
    assert results == [f"result_op_{i}" for i in range(6)]


def test_parallel_scheduler_single_or_empty():
    """Verifies parallel scheduler handles empty and single operation lists."""
    scheduler = ParallelOperationScheduler(max_workers=2)
    assert scheduler.execute_parallel_operations([], lambda x: x) == []

    single = scheduler.execute_parallel_operations(["op1"], lambda x: f"done_{x}")
    assert single == ["done_op1"]
