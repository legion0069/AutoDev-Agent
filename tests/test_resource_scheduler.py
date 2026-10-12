"""
Tests for ResourceScheduler, LockType, and deadlock prevention in AutoDev v3.3.
"""

import time
import pytest
from core.multi_agent.resource_scheduler import (
    LockType,
    ResourceLock,
    ResourceReservation,
    ResourceScheduler,
)


def test_read_and_write_locks():
    scheduler = ResourceScheduler()

    # Multiple readers allowed
    assert scheduler.acquire_lock("doc.md", "reader_1", lock_type=LockType.READ) is True
    assert scheduler.acquire_lock("doc.md", "reader_2", lock_type=LockType.READ) is True
    assert set(scheduler.get_lock_holders("doc.md")) == {"reader_1", "reader_2"}

    # Writer blocked while readers exist
    assert scheduler.acquire_lock("doc.md", "writer_1", lock_type=LockType.WRITE, timeout=0.1) is False

    # Release readers
    assert scheduler.release_lock("doc.md", "reader_1") is True
    assert scheduler.release_lock("doc.md", "reader_2") is True
    assert scheduler.is_locked("doc.md") is False

    # Writer can now acquire exclusive lock
    assert scheduler.acquire_lock("doc.md", "writer_1", lock_type=LockType.WRITE) is True
    assert scheduler.get_lock_holders("doc.md") == ["writer_1"]

    # Reader blocked while writer holds lock
    assert scheduler.acquire_lock("doc.md", "reader_1", lock_type=LockType.READ, timeout=0.1) is False
    assert scheduler.release_lock("doc.md", "writer_1") is True


def test_deadlock_prevention_canonical_sorting():
    scheduler = ResourceScheduler()

    # Agent 1 asks for [res_b, res_a] -> canonical sorted to [res_a, res_b]
    assert scheduler.acquire_multi(["res_b", "res_a"], "agent_1") is True
    assert scheduler.is_locked("res_a") is True
    assert scheduler.is_locked("res_b") is True

    # Agent 2 attempts competing acquisition on overlapping resources
    assert scheduler.acquire_multi(["res_a", "res_c"], "agent_2", timeout=0.1) is False
    # If agent_2 failed, any partial locks (e.g. res_c) must be rolled back
    assert scheduler.is_locked("res_c") is False

    # Clean release
    scheduler.release_lock("res_a", "agent_1")
    scheduler.release_lock("res_b", "agent_1")
    assert scheduler.is_locked("res_a") is False
    assert scheduler.is_locked("res_b") is False


def test_resource_reservations():
    scheduler = ResourceScheduler()
    res_id = scheduler.reserve_resources(
        agent_id="agent_txn",
        resource_ids=["file_x.py", "file_y.py"],
        lock_type=LockType.WRITE,
    )
    assert res_id is not None
    assert scheduler.is_locked("file_x.py") is True
    assert scheduler.is_locked("file_y.py") is True

    # Release reservation
    assert scheduler.release_reservation(res_id) is True
    assert scheduler.is_locked("file_x.py") is False
    assert scheduler.is_locked("file_y.py") is False
    # Duplicate release is safe
    assert scheduler.release_reservation(res_id) is False


def test_lease_expiration_and_cleanup():
    scheduler = ResourceScheduler(default_lease_duration=0.1)

    assert scheduler.acquire_lock("temp.txt", "agent_slow", lease_duration=0.05) is True
    assert scheduler.is_locked("temp.txt") is True

    time.sleep(0.1)
    # Lock is expired
    freed = scheduler.clean_expired_leases()
    assert "temp.txt" in freed
    assert scheduler.is_locked("temp.txt") is False
