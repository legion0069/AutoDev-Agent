"""
test_task_lease_manager.py - Tests for Task Leases & Ownership Management (v2.2)
"""

import time
import pytest
from core.task_lease_manager import (
    DuplicateTaskExecutionError,
    LeaseError,
    LeaseOwnershipError,
    TaskLease,
    TaskLeaseManager,
)
from core.worker_protocol import TaskLeaseStatus


def test_acquire_and_validate_lease():
    """Verifies task lease acquisition and ownership token validation."""
    mgr = TaskLeaseManager(default_lease_ttl=10.0)
    lease = mgr.acquire_lease(
        task_id="task-100",
        operation_id="OP-01",
        transaction_id="tx-01",
        worker_id="worker-1",
    )

    assert isinstance(lease, TaskLease)
    assert lease.status == TaskLeaseStatus.ACTIVE
    assert lease.is_valid is True
    assert mgr.validate_ownership("task-100", lease.owner_token) is True
    assert mgr.validate_ownership("task-100", "invalid-token") is False


def test_renew_lease():
    """Verifies renewing an active lease extends expiration."""
    mgr = TaskLeaseManager(default_lease_ttl=2.0)
    lease = mgr.acquire_lease("t1", "op1", "tx1", "w1")
    initial_exp = lease.expires_timestamp

    time.sleep(0.05)
    res = mgr.renew_lease(lease.owner_token, ttl_seconds=5.0)

    assert res is True
    assert lease.expires_timestamp > initial_exp


def test_lease_expiration_detection():
    """Verifies that expired leases are marked EXPIRED and cannot be validated."""
    mgr = TaskLeaseManager(default_lease_ttl=0.1)
    lease = mgr.acquire_lease("t-expire", "op1", "tx1", "w1")

    time.sleep(0.15)
    expired = mgr.get_expired_leases()

    assert len(expired) == 1
    assert expired[0].task_id == "t-expire"
    assert lease.status == TaskLeaseStatus.EXPIRED
    assert mgr.validate_ownership("t-expire", lease.owner_token) is False


def test_duplicate_lease_acquisition_rejected():
    """Verifies that competing workers cannot acquire an active lease on the same task."""
    mgr = TaskLeaseManager(default_lease_ttl=10.0)
    mgr.acquire_lease("task-exclusive", "op1", "tx1", "worker-A")

    with pytest.raises(DuplicateTaskExecutionError) as exc_info:
        mgr.acquire_lease("task-exclusive", "op1", "tx1", "worker-B")
    assert "already has an active lease" in str(exc_info.value)


def test_release_and_revoke_lease():
    """Verifies release and revoke lifecycle operations."""
    mgr = TaskLeaseManager()
    lease1 = mgr.acquire_lease("t-rel", "op1", "tx1", "w1")
    assert mgr.release_lease(lease1.owner_token) is True
    assert lease1.status == TaskLeaseStatus.RELEASED

    lease2 = mgr.acquire_lease("t-rev", "op2", "tx1", "w2")
    assert mgr.revoke_lease("t-rev", reason="Worker crashed") is True
    assert lease2.status == TaskLeaseStatus.REVOKED


def test_list_active_leases_by_worker_and_transaction():
    """Verifies querying active leases by worker and transaction."""
    mgr = TaskLeaseManager(default_lease_ttl=10.0)
    mgr.acquire_lease("t-w1-a", "op1", "tx-alpha", "worker-1")
    mgr.acquire_lease("t-w1-b", "op2", "tx-alpha", "worker-1")
    mgr.acquire_lease("t-w2-a", "op3", "tx-beta", "worker-2")

    w1_leases = mgr.get_active_leases_for_worker("worker-1")
    assert len(w1_leases) == 2

    w2_leases = mgr.get_active_leases_for_worker("worker-2")
    assert len(w2_leases) == 1

    tx_alpha_leases = mgr.get_active_leases_for_transaction("tx-alpha")
    assert len(tx_alpha_leases) == 2


def test_renew_unknown_lease_token_returns_false():
    """Verifies renewing with nonexistent token returns False."""
    mgr = TaskLeaseManager()
    assert mgr.renew_lease("nonexistent-token-123") is False


def test_reentrant_lease_acquisition_same_worker():
    """Verifies that the same worker acquiring lease again extends TTL rather than throwing."""
    mgr = TaskLeaseManager(default_lease_ttl=2.0)
    lease1 = mgr.acquire_lease("t-reentrant", "op1", "tx1", "worker-same")
    exp1 = lease1.expires_timestamp

    time.sleep(0.05)
    lease2 = mgr.acquire_lease("t-reentrant", "op1", "tx1", "worker-same", ttl_seconds=10.0)

    assert lease1.lease_id == lease2.lease_id
    assert lease2.expires_timestamp > exp1


