"""
test_grpc_worker_server_client.py - Unit & Integration tests for GrpcWorkerServer & GrpcWorkerClient (v2.3)
"""

import time
from pathlib import Path
import pytest

from core.certificate_manager import CertificateManager
from core.grpc_worker_client import GrpcWorkerClient
from core.grpc_worker_server import GrpcWorkerServer
from core.task_lease_manager import TaskLeaseManager
from core.worker_protocol import (
    TaskAssignmentPayload,
    TaskResultPayload,
    WorkerCapabilities,
    WorkerHeartbeat,
    WorkerRegistrationRequest,
    WorkerStatus,
)
from core.worker_registry import WorkerRegistry


@pytest.fixture
def test_certs(tmp_path):
    cert_dir = tmp_path / "certs"
    cert_dir.mkdir(parents=True, exist_ok=True)
    cm = CertificateManager(cert_dir=cert_dir)
    server_info = cm.generate_server_certificate(common_name="127.0.0.1")
    client_info = cm.generate_client_certificate(worker_id="test-remote-worker")
    return cm, server_info, client_info


def test_grpc_server_client_lifecycle_plaintext(tmp_path):
    registry = WorkerRegistry()
    lease_manager = TaskLeaseManager()
    server = GrpcWorkerServer(
        host="127.0.0.1",
        port=0,
        registry=registry,
        lease_manager=lease_manager,
    )
    server.start()
    assigned_port = server.port

    try:
        client = GrpcWorkerClient(
            worker_id="worker-plaintext-1",
            coordinator_host="127.0.0.1",
            coordinator_port=assigned_port,
            workspace_root=tmp_path / "worker_ws",
        )
        # Register
        reg_resp = client.register()
        assert reg_resp.success
        assert "worker-plaintext-1" in registry.get_active_workers()

        # Send heartbeat
        hb_resp = client.send_heartbeat(status=WorkerStatus.IDLE)
        assert hb_resp.acknowledged

        # Submit task result
        res_payload = TaskResultPayload(
            task_id="test-task-01",
            lease_token="tok-123",
            worker_id="worker-plaintext-1",
            success=True,
            modified_files=["main.py"],
        )
        res_resp = client.submit_task_result(res_payload)
        assert res_resp.get("success")

    finally:
        server.stop()


def test_grpc_server_client_mtls(test_certs, tmp_path):
    cm, server_info, client_info = test_certs
    registry = WorkerRegistry()
    lease_manager = TaskLeaseManager()

    server = GrpcWorkerServer(
        host="127.0.0.1",
        port=0,
        registry=registry,
        lease_manager=lease_manager,
        certificate_manager=cm,
        server_cert_info=server_info,
        require_client_cert=True,
    )
    server.start()
    assigned_port = server.port

    try:
        client = GrpcWorkerClient(
            worker_id="test-remote-worker",
            coordinator_host="127.0.0.1",
            coordinator_port=assigned_port,
            workspace_root=tmp_path / "worker_ws",
            client_cert_info=client_info,
            certificate_manager=cm,
        )
        reg_resp = client.register()
        assert reg_resp.success
        assert "test-remote-worker" in registry.get_active_workers()

        hb_resp = client.send_heartbeat(status=WorkerStatus.BUSY, active_tasks=["task-mtls-1"])
        assert hb_resp.acknowledged

    finally:
        server.stop()


def test_task_polling_and_execution_over_rpc(tmp_path):
    registry = WorkerRegistry()
    lease_manager = TaskLeaseManager()
    server = GrpcWorkerServer(
        host="127.0.0.1",
        port=0,
        registry=registry,
        lease_manager=lease_manager,
    )
    server.start()
    assigned_port = server.port

    try:
        client = GrpcWorkerClient(
            worker_id="poll-worker-01",
            coordinator_host="127.0.0.1",
            coordinator_port=assigned_port,
            workspace_root=tmp_path / "worker_ws",
        )
        client.register()

        # Server queues a task
        task = TaskAssignmentPayload(
            task_id="task-rpc-exec-01",
            operation_id="op-rpc-01",
            transaction_id="tx-rpc-01",
            operation_type="CREATE_FILE",
            target_file="hello.py",
            target_content="print('Hello from RPC Worker')\n",
            lease_token="tok-999",
        )
        server.queue_task_for_worker("poll-worker-01", task)

        # Worker polls task
        polled_task = client.poll_task()
        assert polled_task is not None
        assert polled_task.task_id == "task-rpc-exec-01"

        # Worker executes task and submits result
        res = client.execute_and_submit(polled_task)
        assert res.success is True

        # Check server received result
        srv_res = server.get_result_for_task("task-rpc-exec-01")
        assert srv_res is not None
        assert srv_res.success is True
        assert "hello.py" in srv_res.created_files or "hello.py" in srv_res.modified_files

    finally:
        server.stop()


def test_multiple_concurrent_workers_over_rpc(tmp_path):
    registry = WorkerRegistry()
    server = GrpcWorkerServer(host="127.0.0.1", port=0, registry=registry)
    server.start()
    assigned_port = server.port

    try:
        clients = [
            GrpcWorkerClient(
                worker_id=f"concurrent-worker-{i}",
                coordinator_host="127.0.0.1",
                coordinator_port=assigned_port,
                workspace_root=tmp_path / f"worker_{i}",
            )
            for i in range(5)
        ]

        for c in clients:
            resp = c.register()
            assert resp.success is True

        active = registry.get_active_workers()
        assert len(active) == 5

        for c in clients:
            hb = c.send_heartbeat(status=WorkerStatus.IDLE)
            assert hb.acknowledged is True

    finally:
        server.stop()

