"""
test_lock_manager.py - Unit tests for DistributedLockManager (v2.9)
"""

import pytest
import time
from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import LockType
from core.cluster.distributed_lock_manager import (
    DistributedLockManager,
    LockAcquisitionError,
)


def test_exclusive_and_shared_locking():
    mgr = DistributedLockManager()

    # 1. Exclusive Lock
    assert mgr.acquire("file:main.py", owner_id="worker-01", lock_type=LockType.EXCLUSIVE) is True
    assert mgr.is_locked("file:main.py") is True
    
    # Another worker cannot acquire exclusive or shared lock
    assert mgr.acquire("file:main.py", owner_id="worker-02", lock_type=LockType.EXCLUSIVE, timeout=0.0) is False
    assert mgr.acquire("file:main.py", owner_id="worker-02", lock_type=LockType.SHARED, timeout=0.0) is False

    # Release
    assert mgr.release("file:main.py", owner_id="worker-01") is True
    assert mgr.is_locked("file:main.py") is False

    # 2. Shared Locks
    assert mgr.acquire("file:shared.py", owner_id="worker-01", lock_type=LockType.SHARED) is True
    assert mgr.acquire("file:shared.py", owner_id="worker-02", lock_type=LockType.SHARED) is True

    # Exclusive requester blocked
    assert mgr.acquire("file:shared.py", owner_id="worker-03", lock_type=LockType.EXCLUSIVE, timeout=0.0) is False

    # Release shared
    mgr.release("file:shared.py", owner_id="worker-01")
    mgr.release("file:shared.py", owner_id="worker-02")
    assert mgr.is_locked("file:shared.py") is False


def test_lease_ttl_and_sweeping():
    mgr = DistributedLockManager()

    # Acquire with 0.5s TTL
    mgr.acquire("task:T1", owner_id="worker-01", ttl_seconds=0.5)
    assert mgr.is_locked("task:T1") is True

    # Sweeping immediately does not expire
    assert mgr.sweep_expired_leases() == []

    # Advance time simulated
    now = time.time()
    expired = mgr.sweep_expired_leases(current_time=now + 1.0)
    assert "task:T1" in expired
    assert mgr.is_locked("task:T1") is False


def test_lock_context_manager():
    mgr = DistributedLockManager()

    with mgr.lock_context("resource:db", owner_id="worker-01") as locked:
        assert locked is True
        assert mgr.is_locked("resource:db") is True

    assert mgr.is_locked("resource:db") is False
