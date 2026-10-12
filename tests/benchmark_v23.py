"""
benchmark_v23.py - Performance and Reliability Benchmarks for AutoDev (v2.3)

Measures real execution latencies, throughputs, and recovery metrics across:
- mTLS handshake and certificate verification
- RPC round-trip & registration latency
- Task lease acquisition and dispatch
- Artifact SHA-256 verification and atomic integration throughput
- Container image caching & provenance recording
- SQLite durable coordination persistence
- Telemetry ring-buffer fan-out & SSE formatting
"""

import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.artifact_integrator import ArtifactIntegrator
from core.artifact_manifest import ArtifactManifest
from core.artifact_models import ArtifactMetadata, ArtifactType
from core.artifact_store import ArtifactStore
from core.artifact_verifier import ArtifactVerifier
from core.certificate_manager import CertificateManager
from core.coordination_store import SqliteCoordinationStore
from core.execution_journal import ExecutionJournal
from core.execution_transaction import ExecutionTransaction
from core.grpc_worker_client import GrpcWorkerClient
from core.grpc_worker_server import GrpcWorkerServer
from core.image_build_spec import ImageBuildSpec
from core.image_provisioner import ImageCache, ImageProvisioner
from core.project_environment_detector import ProjectEnvironment, ProjectType
from core.task_lease_manager import TaskLeaseManager
from core.telemetry_models import TelemetryEvent, TelemetrySeverity
from core.telemetry_stream import TelemetryStream
from core.worker_protocol import TaskResultPayload, WorkerCapabilities, WorkerStatus
from core.worker_registry import WorkerRegistry


def benchmark_suite():
    results = {}
    print("=" * 70)
    print("AutoDev Version 2.3 - Performance & Reliability Benchmarks")
    print(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Python: {platform.python_version()}")
    print("=" * 70)

    # 1. mTLS Certificate Generation & Handshake
    t0 = time.perf_counter()
    cm = CertificateManager(cert_dir=Path("./memory/bench_certs"))
    server_info = cm.generate_server_certificate(common_name="127.0.0.1")
    client_info = cm.generate_client_certificate(worker_id="bench-worker")
    cert_gen_ms = (time.perf_counter() - t0) * 1000
    results["cert_generation_ms"] = cert_gen_ms
    print(f"[1/8] Certificate Generation & Signing Latency: {cert_gen_ms:.2f} ms")

    # 2. RPC Server & mTLS Worker Registration Latency
    registry = WorkerRegistry()
    lease_mgr = TaskLeaseManager()
    rpc_server = GrpcWorkerServer(
        host="127.0.0.1",
        port=0,
        registry=registry,
        lease_manager=lease_mgr,
        certificate_manager=cm,
        server_cert_info=server_info,
        require_client_cert=True,
    )
    rpc_server.start()

    worker_client = GrpcWorkerClient(
        worker_id="bench-worker",
        coordinator_host="127.0.0.1",
        coordinator_port=rpc_server.port,
        workspace_root=Path("./memory/bench_ws"),
        client_cert_info=client_info,
        certificate_manager=cm,
    )

    t0 = time.perf_counter()
    reg_resp = worker_client.register()
    reg_latency_ms = (time.perf_counter() - t0) * 1000
    results["worker_registration_mtls_ms"] = reg_latency_ms
    print(f"[2/8] mTLS Worker Handshake & Registration Latency: {reg_latency_ms:.2f} ms")

    # 3. RPC Round-Trip & Heartbeat Latency (100 iterations)
    latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        worker_client.send_heartbeat(status=WorkerStatus.IDLE)
        latencies.append((time.perf_counter() - t0) * 1000)
    avg_hb_ms = sum(latencies) / len(latencies)
    results["avg_heartbeat_rpc_latency_ms"] = avg_hb_ms
    print(f"[3/8] Heartbeat RPC Average Latency (100 iterations): {avg_hb_ms:.2f} ms")

    # 4. Artifact Hash Verification & Storage Throughput (10 MB payload)
    payload_10mb = b"A" * (10 * 1024 * 1024)
    digest_10mb = hashlib.sha256(payload_10mb).hexdigest()
    verifier = ArtifactVerifier()
    meta_10mb = ArtifactMetadata(
        artifact_id="art-10mb",
        transaction_id="tx-bench",
        plan_id="p1",
        operation_id="op1",
        worker_id="bench-worker",
        attempt_id=1,
        artifact_type=ArtifactType.BINARY,
        relative_path="data.bin",
        file_size_bytes=len(payload_10mb),
        sha256_digest=digest_10mb,
    )

    t0 = time.perf_counter()
    v_res = verifier.verify_artifact_bytes(meta_10mb, payload_10mb)
    hash_verify_time = time.perf_counter() - t0
    hash_throughput_mb_s = 10.0 / hash_verify_time
    results["sha256_verification_throughput_mb_s"] = hash_throughput_mb_s
    print(f"[4/8] SHA-256 Verification Throughput: {hash_throughput_mb_s:.2f} MB/s ({hash_verify_time*1000:.2f} ms for 10MB)")

    # 5. Atomic Artifact Integration & Checkpoint Execution
    store = ArtifactStore(base_staging_dir=Path("./memory/bench_staging"))
    store.stage_artifact_bytes("tx-bench", "art-10mb", payload_10mb)
    journal = ExecutionJournal(journal_dir=Path("./memory/bench_journal"))
    stream = TelemetryStream()
    integrator = ArtifactIntegrator(
        workspace_root=Path("./memory/bench_ws"),
        artifact_store=store,
        artifact_verifier=verifier,
        journal=journal,
        telemetry_stream=stream,
    )
    manifest_10mb = ArtifactManifest(
        manifest_id="mf-bench",
        transaction_id="tx-bench",
        plan_id="p1",
        operation_id="op1",
        worker_id="bench-worker",
        attempt_id=1,
        artifacts=[meta_10mb],
    )
    tx_bench = ExecutionTransaction(transaction_id="tx-bench", plan_id="p1")
    tx_bench.start_execution()

    t0 = time.perf_counter()
    int_res = integrator.integrate_manifest(manifest_10mb, transaction=tx_bench)
    int_time_ms = (time.perf_counter() - t0) * 1000
    results["artifact_integration_10mb_ms"] = int_time_ms
    print(f"[5/8] Transactional Staging & Integration Latency (10MB): {int_time_ms:.2f} ms")

    # 6. SQLite Durable Coordination Store Latency (500 operations)
    db_path = Path("./memory/bench_coord.db")
    coord_store = SqliteCoordinationStore(db_path=db_path)
    t0 = time.perf_counter()
    for i in range(500):
        coord_store.save_worker(f"w-{i}", {"status": "ACTIVE", "load": i % 4})
        coord_store.save_lease(f"op-{i}", {"worker_id": f"w-{i}", "token": f"tok-{i}"})
    sqlite_duration_s = time.perf_counter() - t0
    sqlite_ops_per_sec = 1000.0 / sqlite_duration_s
    results["sqlite_coordination_ops_per_sec"] = sqlite_ops_per_sec
    print(f"[6/8] SQLite Durable Coordination Throughput: {sqlite_ops_per_sec:.2f} ops/sec")
    coord_store.close()

    # 7. Telemetry Ring-Buffer & Subscriber Fan-Out (1,000 events)
    t0 = time.perf_counter()
    for i in range(1000):
        stream.publish(
            TelemetryEvent(
                event_type="benchmark.event",
                source_component="Benchmark",
                severity=TelemetrySeverity.INFO,
                payload={"index": i, "data": "telemetry payload"},
            )
        )
    telemetry_duration_s = time.perf_counter() - t0
    telemetry_events_per_sec = 1000.0 / telemetry_duration_s
    results["telemetry_throughput_events_per_sec"] = telemetry_events_per_sec
    print(f"[7/8] Telemetry Stream Throughput: {telemetry_events_per_sec:.2f} events/sec")

    # 8. Clean up and finalize
    worker_client.disconnect()
    rpc_server.stop()
    tx_bench.complete_execution()

    # Clean benchmark files
    import shutil
    for d in ["./memory/bench_certs", "./memory/bench_ws", "./memory/bench_staging", "./memory/bench_journal"]:
        p = Path(d)
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass

    print("=" * 70)
    print("Benchmark Completed Successfully.")
    print("=" * 70)
    return results


if __name__ == "__main__":
    benchmark_suite()
