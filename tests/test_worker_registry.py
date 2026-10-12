"""
test_worker_registry.py - Tests for Worker Registry & Health Tracking (v2.2)
"""

import time
import pytest
from core.worker_protocol import (
    PROTOCOL_VERSION,
    WorkerCapabilities,
    WorkerHeartbeat,
    WorkerRegistrationRequest,
    WorkerStatus,
)
from core.worker_registry import (
    IncompatibleProtocolError,
    UnauthorizedWorkerError,
    WorkerInfo,
    WorkerRegistry,
)


def test_worker_registration_success():
    """Verifies registering a valid worker."""
    registry = WorkerRegistry(heartbeat_timeout_seconds=10.0)
    req = WorkerRegistrationRequest(
        worker_id="worker-node-1",
        worker_name="Node 1",
        capabilities=WorkerCapabilities(max_concurrency=3),
    )
    resp = registry.register_worker(req)

    assert resp.accepted is True
    assert resp.worker_id == "worker-node-1"

    worker = registry.get_worker("worker-node-1")
    assert worker is not None
    assert worker.status == WorkerStatus.IDLE
    assert worker.is_available is True
    assert worker.capabilities.max_concurrency == 3


def test_worker_registration_incompatible_protocol_rejected():
    """Verifies protocol version mismatch is rejected."""
    registry = WorkerRegistry()
    req = WorkerRegistrationRequest(
        worker_id="worker-old",
        worker_name="Old Node",
        protocol_version="1.0.0",
    )
    with pytest.raises(IncompatibleProtocolError) as exc_info:
        registry.register_worker(req)
    assert "incompatible" in str(exc_info.value)


def test_worker_registration_auth_token_enforcement():
    """Verifies authentication token checking on worker registration."""
    registry = WorkerRegistry(expected_auth_tokens={"valid-secret-token"})

    # Missing / invalid token
    req_bad = WorkerRegistrationRequest(
        worker_id="worker-imposter",
        worker_name="Imposter",
        auth_token="wrong-token",
    )
    with pytest.raises(UnauthorizedWorkerError):
        registry.register_worker(req_bad)

    # Valid token
    req_good = WorkerRegistrationRequest(
        worker_id="worker-auth",
        worker_name="Auth Worker",
        auth_token="valid-secret-token",
    )
    resp = registry.register_worker(req_good)
    assert resp.accepted is True


def test_worker_heartbeat_processing():
    """Verifies heartbeat updates worker load, active tasks, and status."""
    registry = WorkerRegistry(heartbeat_timeout_seconds=10.0)
    req = WorkerRegistrationRequest(worker_id="worker-hb", worker_name="HB Worker")
    registry.register_worker(req)

    hb = WorkerHeartbeat(
        worker_id="worker-hb",
        status=WorkerStatus.BUSY,
        current_load=2,
        active_task_ids=["t1", "t2"],
    )
    res = registry.process_heartbeat(hb)
    assert res is True

    w = registry.get_worker("worker-hb")
    assert w is not None
    assert w.status == WorkerStatus.BUSY
    assert w.current_load == 2
    assert "t1" in w.active_task_ids


def test_stale_worker_pruning():
    """Verifies that workers with expired heartbeats are marked UNREACHABLE."""
    registry = WorkerRegistry(heartbeat_timeout_seconds=0.1)
    req = WorkerRegistrationRequest(worker_id="worker-stale", worker_name="Stale Worker")
    registry.register_worker(req)

    time.sleep(0.15)
    stale_ids = registry.prune_stale_workers()

    assert "worker-stale" in stale_ids
    w = registry.get_worker("worker-stale")
    assert w is not None
    assert w.status == WorkerStatus.UNREACHABLE
    assert w.is_available is False


def test_find_eligible_workers_by_capability_and_load():
    """Verifies worker capability routing and load-based ordering."""
    registry = WorkerRegistry()

    # Worker 1: process only, load 0
    w1_req = WorkerRegistrationRequest(
        worker_id="w1",
        worker_name="Worker 1",
        capabilities=WorkerCapabilities(supported_operation_types=["CREATE_FILE"], max_concurrency=2),
    )
    registry.register_worker(w1_req)

    # Worker 2: container support, load 1
    w2_req = WorkerRegistrationRequest(
        worker_id="w2",
        worker_name="Worker 2",
        capabilities=WorkerCapabilities(
            supported_operation_types=["CREATE_FILE", "EXECUTE_TEST"],
            supported_runtimes=["process", "container"],
            has_container_support=True,
            max_concurrency=2,
        ),
    )
    registry.register_worker(w2_req)
    registry.assign_task_to_worker("w2", "existing-task")

    # Query process operation
    proc_workers = registry.find_eligible_workers(operation_type="CREATE_FILE")
    assert len(proc_workers) == 2
    assert proc_workers[0].worker_id == "w1"  # least loaded first

    # Query container operation
    cont_workers = registry.find_eligible_workers(
        operation_type="EXECUTE_TEST",
        require_container=True,
    )
    assert len(cont_workers) == 1
    assert cont_workers[0].worker_id == "w2"


def test_worker_deregistration():
    """Verifies deregistering a worker removes it from the registry."""
    registry = WorkerRegistry()
    req = WorkerRegistrationRequest(worker_id="w-leave", worker_name="Leaving Worker")
    registry.register_worker(req)

    res = registry.deregister_worker("w-leave")
    assert res is True
    assert registry.get_worker("w-leave") is None


def test_worker_task_assignment_and_completion_load():
    """Verifies load tracking as tasks are assigned and completed."""
    registry = WorkerRegistry()
    req = WorkerRegistrationRequest(worker_id="w-load", worker_name="Load Worker", capabilities=WorkerCapabilities(max_concurrency=3))
    registry.register_worker(req)

    w = registry.get_worker("w-load")
    assert w.current_load == 0

    registry.assign_task_to_worker("w-load", "task-a")
    assert w.current_load == 1
    assert "task-a" in w.active_task_ids

    registry.assign_task_to_worker("w-load", "task-b")
    assert w.current_load == 2

    registry.complete_task_for_worker("w-load", "task-a")
    assert w.current_load == 1
    assert "task-a" not in w.active_task_ids
    assert "task-b" in w.active_task_ids


