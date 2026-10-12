"""
test_coordination_store.py - Unit tests for Memory & SQLite CoordinationStore Backends (v2.3)
"""

from pathlib import Path
import pytest

from core.coordination_store import (
    CoordinationStore,
    MemoryCoordinationStore,
    SqliteCoordinationStore,
)


@pytest.mark.parametrize("store_factory", [
    lambda tmp_path: MemoryCoordinationStore(),
    lambda tmp_path: SqliteCoordinationStore(db_path=tmp_path / "coord.db"),
])
def test_coordination_store_operations(store_factory, tmp_path):
    store = store_factory(tmp_path)

    # 1. Worker CRUD
    store.save_worker("worker-01", {"worker_id": "worker-01", "status": "ACTIVE", "concurrency": 4})
    w = store.get_worker("worker-01")
    assert w is not None
    assert w["status"] == "ACTIVE"
    assert len(store.list_workers()) == 1

    store.delete_worker("worker-01")
    assert store.get_worker("worker-01") is None
    assert len(store.list_workers()) == 0

    # 2. Lease CRUD
    store.save_lease("op-100", {"operation_id": "op-100", "worker_id": "worker-02", "token": "tok-1"})
    lease = store.get_lease("op-100")
    assert lease is not None
    assert lease["token"] == "tok-1"
    assert len(store.list_leases()) == 1

    store.delete_lease("op-100")
    assert store.get_lease("op-100") is None

    # 3. Idempotency Records
    store.save_idempotency_record("idem-key-1", {"result": "success", "val": 42})
    record = store.get_idempotency_record("idem-key-1")
    assert record is not None
    assert record["val"] == 42

    store.close()


def test_sqlite_persistence_across_restarts(tmp_path):
    db_file = tmp_path / "persistent.db"
    store1 = SqliteCoordinationStore(db_path=db_file)
    store1.save_worker("worker-restart", {"worker_id": "worker-restart", "concurrency": 8})
    store1.save_lease("op-restart", {"operation_id": "op-restart", "token": "tok-persist"})
    store1.save_idempotency_record("key-restart", {"status": "persisted"})
    store1.close()

    # Reopen same database file
    store2 = SqliteCoordinationStore(db_path=db_file)
    assert store2.get_worker("worker-restart") is not None
    assert store2.get_worker("worker-restart")["concurrency"] == 8
    assert store2.get_lease("op-restart")["token"] == "tok-persist"
    assert store2.get_idempotency_record("key-restart")["status"] == "persisted"
    store2.close()


def test_sqlite_multithreaded_access(tmp_path):
    import threading
    db_file = tmp_path / "concurrent.db"
    store = SqliteCoordinationStore(db_path=db_file)

    def worker_job(worker_idx: int):
        for i in range(10):
            store.save_worker(f"w-{worker_idx}-{i}", {"idx": worker_idx, "i": i})
            store.save_idempotency_record(f"idem-{worker_idx}-{i}", {"val": i})

    threads = [threading.Thread(target=worker_job, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    workers = store.list_workers()
    assert len(workers) == 50
    store.close()

