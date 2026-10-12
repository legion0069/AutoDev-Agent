"""
test_worker_protocol.py - Tests for Distributed Worker Protocol Schemas & Serialization (v2.2)
"""

import pytest
from core.worker_protocol import (
    PROTOCOL_VERSION,
    TaskAssignmentPayload,
    TaskLeaseStatus,
    TaskResultPayload,
    WorkerCapabilities,
    WorkerHeartbeat,
    WorkerRegistrationRequest,
    WorkerRegistrationResponse,
    WorkerStatus,
    redact_payload_secrets,
)


def test_worker_capabilities_roundtrip():
    """Verifies WorkerCapabilities serialization and deserialization."""
    caps = WorkerCapabilities(
        supported_runtimes=["process", "container"],
        supported_operation_types=["CREATE_FILE", "MODIFY_FILE", "DELETE_FILE", "EXECUTE_TEST"],
        max_concurrency=4,
        has_container_support=True,
        container_engine="docker",
        tags=["gpu", "high-mem"],
    )
    d = caps.to_dict()
    restored = WorkerCapabilities.from_dict(d)

    assert restored.supported_runtimes == ["process", "container"]
    assert restored.max_concurrency == 4
    assert restored.has_container_support is True
    assert restored.container_engine == "docker"
    assert "gpu" in restored.tags


def test_worker_registration_request_and_response_roundtrip():
    """Verifies registration request and response schemas."""
    req = WorkerRegistrationRequest(
        worker_id="worker-001",
        worker_name="Worker Alpha",
        protocol_version=PROTOCOL_VERSION,
        capabilities=WorkerCapabilities(max_concurrency=2),
        hostname="node-1.cluster.local",
        auth_token="secret-token-12345",
    )
    req_dict = req.to_dict()
    assert req_dict["auth_token"] == "[REDACTED]"
    assert req_dict["worker_id"] == "worker-001"

    resp = WorkerRegistrationResponse(
        accepted=True,
        worker_id="worker-001",
        heartbeat_interval_seconds=5.0,
        lease_ttl_seconds=15.0,
    )
    resp_dict = resp.to_dict()
    assert resp_dict["accepted"] is True
    assert resp_dict["heartbeat_interval_seconds"] == 5.0


def test_worker_heartbeat_roundtrip():
    """Verifies WorkerHeartbeat serialization and status."""
    hb = WorkerHeartbeat(
        worker_id="worker-001",
        status=WorkerStatus.BUSY,
        current_load=2,
        active_task_ids=["task-1", "task-2"],
    )
    d = hb.to_dict()
    restored = WorkerHeartbeat.from_dict(d)

    assert restored.worker_id == "worker-001"
    assert restored.status == WorkerStatus.BUSY
    assert restored.current_load == 2
    assert len(restored.active_task_ids) == 2


def test_task_assignment_and_result_roundtrip():
    """Verifies TaskAssignmentPayload and TaskResultPayload serialization."""
    assignment = TaskAssignmentPayload(
        task_id="task-100",
        operation_id="OP-WRITE-01",
        transaction_id="tx-999",
        operation_type="CREATE_FILE",
        target_file="src/utils.py",
        target_content="def add(a, b): return a + b\n",
        lease_token="lease-tok-123",
        deadline_utc="2026-10-09T12:00:00Z",
        idempotency_key="idem-key-1",
        required_runtime="process",
        security_profile="restricted",
        metadata={"auth_token": "sk-secret1234567890abcdef1234"},
    )
    as_dict = assignment.to_dict()
    assert as_dict["metadata"]["auth_token"] == "[REDACTED]"

    restored_assign = TaskAssignmentPayload.from_dict(as_dict)
    assert restored_assign.task_id == "task-100"
    assert restored_assign.target_file == "src/utils.py"

    result = TaskResultPayload(
        task_id="task-100",
        operation_id="OP-WRITE-01",
        transaction_id="tx-999",
        worker_id="worker-001",
        lease_token="lease-tok-123",
        success=True,
        created_files=["src/utils.py"],
        duration_seconds=0.045,
    )
    res_dict = result.to_dict()
    restored_res = TaskResultPayload.from_dict(res_dict)

    assert restored_res.success is True
    assert restored_res.created_files == ["src/utils.py"]
    assert restored_res.duration_seconds == 0.045


def test_worker_registration_rejected_response():
    """Verifies rejected registration response serialization."""
    resp = WorkerRegistrationResponse(
        accepted=False,
        worker_id="unknown-worker",
        message="Protocol version mismatch: required 2.2.0, received 1.0.0",
    )
    d = resp.to_dict()
    assert d["accepted"] is False
    assert "Protocol version mismatch" in d["message"]


def test_task_lease_status_enum_values():
    """Verifies all task lease status lifecycle states."""
    expected_states = {"ACTIVE", "EXPIRED", "RELEASED", "REVOKED"}
    actual_states = {s.value for s in TaskLeaseStatus}
    assert expected_states == actual_states


def test_redact_payload_secrets_helper():
    """Verifies redact_payload_secrets scrubs sensitive nested dictionaries."""
    data = {
        "user": "alice",
        "api_key": "sk-1234567890abcdef1234567890",
        "nested": {
            "token": "secret-token-val",
            "count": 5,
        },
    }
    cleaned = redact_payload_secrets(data)
    assert cleaned["user"] == "alice"
    assert cleaned["api_key"] == "[REDACTED]"
    assert cleaned["nested"]["token"] == "[REDACTED]"
    assert cleaned["nested"]["count"] == 5


def test_worker_status_all_values():
    """Verifies all defined worker statuses exist."""
    expected = {"STARTING", "IDLE", "BUSY", "DEGRADED", "UNREACHABLE", "DRAINING", "STOPPED", "FAILED"}
    actual = {s.value for s in WorkerStatus}
    assert expected == actual


def test_task_result_payload_failure_serialization():
    """Verifies failed task result payload serialization and deserialization."""
    res = TaskResultPayload(
        task_id="t-fail",
        operation_id="OP-FAIL",
        transaction_id="tx-fail",
        worker_id="worker-err",
        lease_token="tok-err",
        success=False,
        error_type="SandboxSecurityError",
        error_message="Path escape violation",
    )
    d = res.to_dict()
    assert d["success"] is False
    assert d["error_type"] == "SandboxSecurityError"
    assert d["error_message"] == "Path escape violation"

    restored = TaskResultPayload.from_dict(d)
    assert restored.success is False
    assert restored.error_type == "SandboxSecurityError"


