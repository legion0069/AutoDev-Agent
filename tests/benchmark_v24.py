"""
AutoDev Version 2.4 Performance Benchmark Suite (Phase 9)
Measures throughput, latency, and resource metrics for:
1. HA Leader Election & Failover Latency
2. Kubernetes Worker Pool Reconciliation Duration
3. FastCDC Artifact Chunking & Hashing Throughput (MB/s)
4. Differential Artifact Synchronization & Cache Deduplication
5. Terminal Gateway Frame Streaming Latency
"""

import os
import sys
import time
import json
import hashlib
import platform
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.consensus_protocol import CoordinatorRole, FencingToken
from core.ha_coordinator import HACoordinator, LeaderFencingValidator
from core.coordination_store import MemoryCoordinationStore
from core.worker_scaling_policy import WorkerScalingPolicy
from core.kubernetes_worker_provider import FakeKubernetesClient, KubernetesWorkerProvider
from core.kubernetes_worker_controller import KubernetesWorkerController
from core.artifact_chunker import ArtifactChunker
from core.artifact_chunk_store import ArtifactChunkStore
from core.artifact_sync_protocol import ChunkTransferMessage
from core.artifact_transfer_manager import ArtifactTransferManager
from core.terminal_authorization import TerminalAuthorizer, TerminalSecurityPolicy
from core.interactive_session_manager import InteractiveSessionManager
from core.terminal_gateway import TerminalGateway


def benchmark_ha_coordination(iterations: int = 100):
    store = MemoryCoordinationStore()
    peers = [f"node-{i}" for i in range(5)]
    coordinators = [HACoordinator(coordinator_id=p, peer_ids=peers, store=store) for p in peers]

    start = time.perf_counter()
    for i in range(iterations):
        leader = coordinators[i % len(coordinators)]
        leader.start_election()
    duration = time.perf_counter() - start
    avg_ms = (duration / iterations) * 1000.0

    return {
        "benchmark": "HA Leader Election & Term Advance",
        "iterations": iterations,
        "total_duration_sec": round(duration, 4),
        "avg_election_latency_ms": round(avg_ms, 3),
        "ops_per_sec": round(iterations / duration, 1),
    }


def benchmark_k8s_reconciliation(iterations: int = 200):
    client = FakeKubernetesClient()
    provider = KubernetesWorkerProvider(client)
    controller = KubernetesWorkerController(client, provider)

    crd = {
        "apiVersion": "autodev.io/v1alpha1",
        "kind": "AutoDevWorkerPool",
        "metadata": {"name": "bench-pool", "namespace": "autodev-system"},
        "spec": {
            "replicas": 5,
            "minReplicas": 1,
            "maxReplicas": 20,
            "image": "autodev/worker:v2.4.0",
            "scalingPolicy": {"enabled": True, "queueDepthThreshold": 5, "cooldownSeconds": 0},
        }
    }
    client.create_custom_resource("autodev.io", "v1alpha1", "autodevworkerpools", crd, "autodev-system")

    start = time.perf_counter()
    for i in range(iterations):
        controller.reconcile_pool("bench-pool", "autodev-system", queue_depth=i % 15, busy_workers=i % 5)
    duration = time.perf_counter() - start
    avg_ms = (duration / iterations) * 1000.0

    return {
        "benchmark": "Kubernetes Pool Reconciliation Loop",
        "iterations": iterations,
        "total_duration_sec": round(duration, 4),
        "avg_reconcile_latency_ms": round(avg_ms, 3),
        "reconciles_per_sec": round(iterations / duration, 1),
    }


def benchmark_fastcdc_chunking(payload_mb: int = 10):
    chunker = ArtifactChunker(min_size=4096, target_size=16384, max_size=65536)
    # Generate random-like entropy payload
    block = b"AutoDevFastCDCBlockHeader\x01\x02\x03\x04\x05" + (b"DataStreamPayloadBlock" * 40)
    data = block * (payload_mb * 1024 * 1024 // len(block))

    start = time.perf_counter()
    chunks = chunker.chunk_bytes(data, include_data=True)
    duration = time.perf_counter() - start

    mb_size = len(data) / (1024 * 1024)
    throughput_mb_s = mb_size / duration

    return {
        "benchmark": "FastCDC Chunking & Hashing Throughput",
        "payload_mb": round(mb_size, 2),
        "chunk_count": len(chunks),
        "avg_chunk_size_bytes": round(len(data) / len(chunks), 1),
        "duration_sec": round(duration, 4),
        "throughput_mb_sec": round(throughput_mb_s, 2),
    }


def benchmark_differential_sync(tmp_dir: Path):
    sender_cas = ArtifactChunkStore(storage_root=str(tmp_dir / "sender_cas"))
    receiver_cas = ArtifactChunkStore(storage_root=str(tmp_dir / "receiver_cas"))
    chunker = ArtifactChunker(min_size=4096, target_size=16384, max_size=65536)

    sender_mgr = ArtifactTransferManager(chunk_store=sender_cas, chunker=chunker)
    receiver_mgr = ArtifactTransferManager(chunk_store=receiver_cas, chunker=chunker, staging_dir=str(tmp_dir / "staging"))

    # Initial 5MB file
    f1 = tmp_dir / "file_v1.bin"
    base_data = (b"ArtifactInitialSegmentDataBlock\n" * 100) * 1500
    f1.write_bytes(base_data)

    m1, _ = sender_mgr.create_manifest_for_file(str(f1), artifact_id="art-v1")
    neg1 = receiver_mgr.negotiate_incoming_transfer(m1)

    # Initial transfer
    t0 = time.perf_counter()
    for d in neg1.missing_chunk_digests:
        data = sender_cas.get_chunk(d)
        receiver_mgr.receive_chunk(ChunkTransferMessage.from_bytes("art-v1", d, 0, data))
    dest1 = tmp_dir / "reconstructed_v1.bin"
    receiver_mgr.reconstruct_artifact("art-v1", str(dest1))
    t_initial = time.perf_counter() - t0

    # 1% modified v2 file (appended tail)
    f2 = tmp_dir / "file_v2.bin"
    v2_data = base_data + (b"NEW_PATCH_DATA_BLOCK\n" * 50)
    f2.write_bytes(v2_data)

    m2, _ = sender_mgr.create_manifest_for_file(str(f2), artifact_id="art-v2")
    neg2 = receiver_mgr.negotiate_incoming_transfer(m2)

    # Differential transfer
    t1 = time.perf_counter()
    for d in neg2.missing_chunk_digests:
        data = sender_cas.get_chunk(d)
        receiver_mgr.receive_chunk(ChunkTransferMessage.from_bytes("art-v2", d, 0, data))
    dest2 = tmp_dir / "reconstructed_v2.bin"
    receiver_mgr.reconstruct_artifact("art-v2", str(dest2))
    t_diff = time.perf_counter() - t1

    dedup_ratio = (1.0 - (len(neg2.missing_chunk_digests) / len(m2.chunks))) * 100.0

    return {
        "benchmark": "Differential Artifact Transfer & CAS Deduplication",
        "initial_transfer_time_sec": round(t_initial, 4),
        "differential_transfer_time_sec": round(t_diff, 4),
        "speedup_factor": round(t_initial / max(0.0001, t_diff), 2),
        "total_chunks_v2": len(m2.chunks),
        "missing_chunks_transferred": len(neg2.missing_chunk_digests),
        "cache_deduplication_pct": round(dedup_ratio, 2),
    }


def benchmark_terminal_gateway_latency(iterations: int = 100):
    auth = TerminalAuthorizer(TerminalSecurityPolicy(allowed_principals={"benchmarker"}))
    mgr = InteractiveSessionManager(authorizer=auth)
    gateway = TerminalGateway(session_manager=mgr)

    # Create session
    create_msg = json.dumps({
        "action": "create",
        "principal_id": "benchmarker",
        "transaction_id": "tx-bench",
        "sandbox_id": "sbx-bench",
        "is_coordinator_host": False,
    })
    resp = gateway.handle_client_message(create_msg)
    sid = resp["session_id"]

    start = time.perf_counter()
    for i in range(iterations):
        in_msg = json.dumps({"action": "input", "session_id": sid, "data": f"echo {i}\n"})
        gateway.handle_client_message(in_msg)
        read_msg = json.dumps({"action": "read", "session_id": sid, "timeout_ms": 1})
        gateway.handle_client_message(read_msg)
    duration = time.perf_counter() - start

    mgr.terminate_session(sid)
    avg_latency_ms = (duration / (iterations * 2)) * 1000.0

    return {
        "benchmark": "Terminal Gateway Frame Dispatch Latency",
        "iterations": iterations,
        "total_duration_sec": round(duration, 4),
        "avg_frame_latency_ms": round(avg_latency_ms, 3),
        "frames_per_sec": round((iterations * 2) / duration, 1),
    }


def run_all_benchmarks():
    print("=" * 70)
    print("AutoDev Version 2.4 — Performance Benchmark Suite")
    print(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Python: {platform.python_version()}")
    print("=" * 70)

    results = []

    # 1. HA Coordination
    print("\n[1/5] Benchmarking HA Leader Election & Fencing...")
    r1 = benchmark_ha_coordination(iterations=200)
    print(json.dumps(r1, indent=2))
    results.append(r1)

    # 2. Kubernetes Controller
    print("\n[2/5] Benchmarking Kubernetes Worker Pool Reconciliation...")
    r2 = benchmark_k8s_reconciliation(iterations=300)
    print(json.dumps(r2, indent=2))
    results.append(r2)

    # 3. FastCDC Chunking
    print("\n[3/5] Benchmarking FastCDC Chunking Throughput (10 MB)...")
    r3 = benchmark_fastcdc_chunking(payload_mb=10)
    print(json.dumps(r3, indent=2))
    results.append(r3)

    # 4. Differential Sync
    print("\n[4/5] Benchmarking Differential Artifact Transfer & CAS Deduplication...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        r4 = benchmark_differential_sync(Path(tmp_dir))
    print(json.dumps(r4, indent=2))
    results.append(r4)

    # 5. Terminal Gateway
    print("\n[5/5] Benchmarking Terminal Gateway Frame Streaming...")
    r5 = benchmark_terminal_gateway_latency(iterations=100)
    print(json.dumps(r5, indent=2))
    results.append(r5)

    print("\n" + "=" * 70)
    print("Benchmark Suite Execution Complete.")
    print("=" * 70)

    return results


if __name__ == "__main__":
    run_all_benchmarks()
