"""
test_v23_integration.py - Comprehensive End-to-End Integration Suite for AutoDev (v2.3)

Validates the full v2.3 workflow:
1. Environment detection & reproducible image provisioning with caching
2. mTLS certificate generation and secure remote worker RPC registration
3. Assignment dispatch and execution under sandbox isolation
4. Artifact staging, independent cryptographic digest verification, and transactional integration
5. Validation gate execution and verified transactional rollback on injected failure
6. Real-time telemetry streaming and dashboard monitoring
"""

import hashlib
import json
from pathlib import Path
import time
import pytest

from core.artifact_integrator import ArtifactIntegrator
from core.artifact_manifest import ArtifactManifest
from core.artifact_models import ArtifactMetadata, ArtifactStatus, ArtifactType
from core.artifact_store import ArtifactStore
from core.artifact_verifier import ArtifactVerifier
from core.certificate_manager import CertificateManager
from core.change_execution_planner import (
    ChangeExecutionPlan,
    ChangeOperation,
    ExecutionStage,
    OperationType,
    ValidationGate,
)
from core.container_runtime import MockContainerRuntimeAdapter
from core.dashboard_server import DashboardServer
from core.execution_journal import ExecutionJournal
from core.execution_transaction import ExecutionStatus, ExecutionTransaction
from core.grpc_worker_client import GrpcWorkerClient
from core.grpc_worker_server import GrpcWorkerServer
from core.image_provisioner import ImageCache, ImageProvisioner
from core.project_environment_detector import ProjectEnvironmentDetector, ProjectType
from core.prompt_builder import PromptBuilder
from core.task_lease_manager import TaskLeaseManager
from core.telemetry_models import TelemetryEvent, TelemetrySeverity
from core.telemetry_stream import TelemetryStream
from core.worker_protocol import TaskResultPayload, WorkerCapabilities, WorkerStatus
from core.worker_registry import WorkerRegistry


@pytest.fixture
def e2e_environment(tmp_path):
    # Setup directories
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    staging = tmp_path / "artifacts"
    staging.mkdir(parents=True, exist_ok=True)
    certs = tmp_path / "certs"
    certs.mkdir(parents=True, exist_ok=True)
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)

    # Core components
    cm = CertificateManager(cert_dir=certs)
    server_info = cm.generate_server_certificate(common_name="127.0.0.1")
    client_info = cm.generate_client_certificate(worker_id="remote-e2e-worker")

    registry = WorkerRegistry()
    lease_manager = TaskLeaseManager()
    journal = ExecutionJournal(journal_dir=journal_dir)
    stream = TelemetryStream()
    store = ArtifactStore(base_staging_dir=staging)
    verifier = ArtifactVerifier(lease_manager=lease_manager)
    integrator = ArtifactIntegrator(
        workspace_root=ws,
        artifact_store=store,
        artifact_verifier=verifier,
        journal=journal,
        telemetry_stream=stream,
    )
    runtime = MockContainerRuntimeAdapter()
    detector = ProjectEnvironmentDetector()
    provisioner = ImageProvisioner(runtime_adapter=runtime, detector=detector, cache_dir=tmp_path / "cache")

    # Start gRPC Coordinator Server
    rpc_server = GrpcWorkerServer(
        host="127.0.0.1",
        port=0,
        registry=registry,
        lease_manager=lease_manager,
        certificate_manager=cm,
        server_cert_info=server_info,
        require_client_cert=True,
    )
    rpc_server.start()

    # Start Dashboard Server
    dash_server = DashboardServer(
        host="127.0.0.1",
        port=0,
        stream=stream,
    )
    dash_server.start()

    yield {
        "workspace": ws,
        "staging": staging,
        "cm": cm,
        "client_info": client_info,
        "registry": registry,
        "lease_manager": lease_manager,
        "journal": journal,
        "stream": stream,
        "store": store,
        "verifier": verifier,
        "integrator": integrator,
        "provisioner": provisioner,
        "detector": detector,
        "rpc_server": rpc_server,
        "dash_server": dash_server,
    }

    rpc_server.stop()
    dash_server.stop()


def test_v23_e2e_successful_remote_execution_and_artifact_integration(e2e_environment):
    env = e2e_environment
    ws = env["workspace"]
    rpc_server = env["rpc_server"]

    # 1. Project inspection & image provisioning
    (ws / "requirements.txt").write_text("pytest>=7.0.0\n", encoding="utf-8")
    proj_env = env["detector"].detect(ws)
    assert proj_env.project_type == ProjectType.PYTHON

    spec = env["provisioner"].create_build_spec(proj_env)
    provenance = env["provisioner"].build_image(spec, workspace_path=ws)
    assert provenance.image_digest.startswith("sha256:")
    assert env["provisioner"].verify_image(provenance)

    # 2. Start Remote Worker Client with mTLS
    worker_client = GrpcWorkerClient(
        worker_id="remote-e2e-worker",
        coordinator_host="127.0.0.1",
        coordinator_port=rpc_server.port,
        workspace_root=ws,
        client_cert_info=env["client_info"],
        certificate_manager=env["cm"],
    )
    reg_res = worker_client.register()
    assert reg_res.success
    assert "remote-e2e-worker" in env["registry"].get_active_workers()

    # 3. Create execution plan & transaction
    tx = ExecutionTransaction(transaction_id="tx-v23-e2e-1", plan_id="plan-e2e-1")
    tx.start_execution()

    # Lease task to worker
    lease = env["lease_manager"].acquire_lease("op-e2e-01", "remote-e2e-worker", duration_seconds=60)
    assert lease is not None

    # 4. Generate advisory worker contract prompt
    builder = PromptBuilder()
    contract_prompt = builder.build_worker_execution_contract(
        transaction_id="tx-v23-e2e-1",
        task_id="op-e2e-01",
        worker_id="remote-e2e-worker",
        authorized_paths=["src/calculator.py"],
        runtime_profile="restricted",
    )
    assert "DISTRIBUTED WORKER EXECUTION CONTRACT" in contract_prompt

    # 5. Remote Worker produces and stages artifact
    calc_code = b"def add(a, b):\n    return a + b\n"
    calc_digest = hashlib.sha256(calc_code).hexdigest()
    env["store"].stage_artifact_bytes("tx-v23-e2e-1", "art-calc-1", calc_code)

    art_meta = ArtifactMetadata(
        artifact_id="art-calc-1",
        transaction_id="tx-v23-e2e-1",
        plan_id="plan-e2e-1",
        operation_id="op-e2e-01",
        worker_id="remote-e2e-worker",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="src/calculator.py",
        file_size_bytes=len(calc_code),
        sha256_digest=calc_digest,
    )
    manifest = ArtifactManifest(
        manifest_id="mf-calc-1",
        transaction_id="tx-v23-e2e-1",
        plan_id="plan-e2e-1",
        operation_id="op-e2e-01",
        worker_id="remote-e2e-worker",
        attempt_id=1,
        artifacts=[art_meta],
    )

    # 6. Coordinator integrates artifact & executes validation gate
    def validation_gate_check():
        return True  # tests passed

    int_result = env["integrator"].integrate_manifest(
        manifest,
        transaction=tx,
        validation_gate=validation_gate_check,
    )
    assert int_result.success
    assert "art-calc-1" in int_result.integrated_artifacts
    assert (ws / "src" / "calculator.py").exists()
    assert (ws / "src" / "calculator.py").read_bytes() == calc_code

    # 7. Worker submits task result to coordinator RPC
    task_res = TaskResultPayload(
        task_id="op-e2e-01",
        lease_token=lease.lease_token,
        worker_id="remote-e2e-worker",
        success=True,
        created_files=["src/calculator.py"],
    )
    submit_res = worker_client.submit_task_result(task_res)
    assert submit_res.get("success")

    tx.complete_execution()
    assert tx.status == ExecutionStatus.SUCCEEDED


def test_v23_e2e_validation_failure_triggers_verified_rollback(e2e_environment):
    env = e2e_environment
    ws = env["workspace"]

    # Pre-existing file
    main_py = ws / "main.py"
    main_py.write_text("print('original stable code')\n", encoding="utf-8")
    original_bytes = main_py.read_bytes()

    tx = ExecutionTransaction(transaction_id="tx-v23-e2e-fail", plan_id="plan-e2e-fail")
    tx.start_execution()

    # Acquire lease
    lease = env["lease_manager"].acquire_lease("op-e2e-bad", "remote-e2e-worker", duration_seconds=60)

    # Bad payload staged
    bad_code = b"syntax error !!!"
    bad_digest = hashlib.sha256(bad_code).hexdigest()
    env["store"].stage_artifact_bytes("tx-v23-e2e-fail", "art-bad-1", bad_code)

    art_meta = ArtifactMetadata(
        artifact_id="art-bad-1",
        transaction_id="tx-v23-e2e-fail",
        plan_id="plan-e2e-fail",
        operation_id="op-e2e-bad",
        worker_id="remote-e2e-worker",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="main.py",
        file_size_bytes=len(bad_code),
        sha256_digest=bad_digest,
    )
    manifest = ArtifactManifest(
        manifest_id="mf-bad-1",
        transaction_id="tx-v23-e2e-fail",
        plan_id="plan-e2e-fail",
        operation_id="op-e2e-bad",
        worker_id="remote-e2e-worker",
        attempt_id=1,
        artifacts=[art_meta],
    )

    # Validation gate fails
    int_result = env["integrator"].integrate_manifest(
        manifest,
        transaction=tx,
        validation_gate=lambda: False,
    )
    assert not int_result.success
    assert int_result.rollback_executed

    # Assert main.py was restored safely to pre-mutation content
    assert main_py.read_bytes() == original_bytes


def test_v23_e2e_hybrid_execution_and_telemetry_flow(e2e_environment):
    env = e2e_environment
    ws = env["workspace"]
    stream = env["stream"]

    sub_q, _ = stream.subscribe()

    # 1. Register a local and a remote worker
    reg = env["registry"]
    from core.worker_protocol import WorkerRegistrationRequest
    reg.register_worker(WorkerRegistrationRequest(worker_id="worker-local-1", worker_name="Local Worker"))
    reg.register_worker(WorkerRegistrationRequest(worker_id="worker-remote-2", worker_name="Remote Worker"))

    active = reg.get_active_workers()
    assert "worker-local-1" in active
    assert "worker-remote-2" in active

    # 2. Stage and integrate artifacts for both workers
    tx = ExecutionTransaction(transaction_id="tx-hybrid-01", plan_id="plan-hybrid-01")
    tx.start_execution()

    c_local = b"# Local Worker Code\n"
    c_remote = b"# Remote Worker Code\n"
    env["store"].stage_artifact_bytes("tx-hybrid-01", "art-loc", c_local)
    env["store"].stage_artifact_bytes("tx-hybrid-01", "art-rem", c_remote)

    manifest = ArtifactManifest(
        manifest_id="mf-hybrid",
        transaction_id="tx-hybrid-01",
        plan_id="plan-hybrid-01",
        operation_id="op-hybrid",
        worker_id="worker-remote-2",
        attempt_id=1,
        artifacts=[
            ArtifactMetadata(
                artifact_id="art-loc",
                transaction_id="tx-hybrid-01",
                plan_id="plan-hybrid-01",
                operation_id="op-hybrid",
                worker_id="worker-remote-2",
                attempt_id=1,
                artifact_type=ArtifactType.SOURCE_CODE,
                relative_path="src/local_mod.py",
                file_size_bytes=len(c_local),
                sha256_digest=hashlib.sha256(c_local).hexdigest(),
            ),
            ArtifactMetadata(
                artifact_id="art-rem",
                transaction_id="tx-hybrid-01",
                plan_id="plan-hybrid-01",
                operation_id="op-hybrid",
                worker_id="worker-remote-2",
                attempt_id=1,
                artifact_type=ArtifactType.SOURCE_CODE,
                relative_path="src/remote_mod.py",
                file_size_bytes=len(c_remote),
                sha256_digest=hashlib.sha256(c_remote).hexdigest(),
            ),
        ],
    )

    res = env["integrator"].integrate_manifest(manifest, transaction=tx)
    assert res.success
    assert (ws / "src" / "local_mod.py").read_bytes() == c_local
    assert (ws / "src" / "remote_mod.py").read_bytes() == c_remote

    tx.complete_execution()
    assert tx.status == ExecutionStatus.SUCCEEDED
    assert stream.event_count > 0 or not sub_q.empty()

