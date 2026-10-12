"""
Comprehensive End-to-End Integration Test for AutoDev Version 2.5:
- External consensus & leader fencing
- OS/runtime isolation with eBPF security monitoring
- Fleet-scale differential P2P artifact distribution
- WebRTC interactive remote debugging
"""

import os
import sys
import time
import hashlib
import tempfile
from pathlib import Path
import pytest

from core.consensus_provider import MemoryConsensusProvider
from core.ha_coordinator import HACoordinator, LeaderFencingValidator
from core.isolation_provider import (
    LocalProcessIsolationProvider,
    PROFILE_STANDARD,
    IsolationPolicy,
)
from core.ebpf_isolation_backend import EBPFIsolationBackend
from core.artifact_chunk_store import ArtifactChunkStore
from core.artifact_sync_protocol import ChunkManifest, ChunkMetadata
from core.artifact_manifest import ArtifactManifest
from core.artifact_peer_registry import ArtifactPeerRegistry
from core.artifact_peer_transport import ArtifactPeerClient
from core.artifact_distribution_planner import ArtifactDistributionPlanner
from core.terminal_transport import WebSocketTerminalTransport
from core.webrtc_terminal_transport import WebRTCTerminalTransport
from core.prompt_builder import PromptBuilder
from core.telemetry_models import TelemetryEvent, TelemetryEventType, TelemetrySeverity


def test_v25_complete_autonomous_lifecycle(tmp_path):
    # =========================================================================
    # 1. Consensus & Leader Election with Authoritative Fencing
    # =========================================================================
    consensus = MemoryConsensusProvider()
    coord = HACoordinator(
        coordinator_id="coord-primary-v25",
        consensus_provider=consensus,
        lease_duration_seconds=10.0,
    )
    coord.start()
    assert coord.is_leader is True

    validator = LeaderFencingValidator(coord)
    token = validator.assert_active_leader("plan_execution")
    assert token.leader_id == "coord-primary-v25"
    assert token.term >= 0
    assert token.fencing_generation >= 1

    # =========================================================================
    # 2. Worker Execution Contract Prompt Synthesis
    # =========================================================================
    prompt_builder = PromptBuilder()
    contract_prompt = prompt_builder.synthesize_worker_execution_contract(
        transaction_id="tx-v25-001",
        task_id="TASK-V25-ORCH",
        worker_id="worker-agent-42",
        runtime_profile="standard",
        authorized_paths=[str(tmp_path / "src"), str(tmp_path / "tests")],
        expected_artifacts=["dist/bundle.js", "reports/test_results.xml"],
        validation_gates=["pytest", "flake8", "manifest_sha256"],
        fencing_term=token.term,
        fencing_generation=token.fencing_generation,
        chunk_sync_enabled=True,
        debug_session_id="dbg-session-99",
        p2p_distribution_enabled=True,
        ebpf_monitoring_active=True,
    )

    assert "DISTRIBUTED WORKER EXECUTION CONTRACT (AutoDev v2.5)" in contract_prompt
    assert "Generation `1`" in contract_prompt or "Generation `" in contract_prompt
    assert "P2P Fleet Artifact Exchange" in contract_prompt

    # =========================================================================
    # 3. Runtime Isolation & eBPF Security Monitoring
    # =========================================================================
    ebpf_backend = EBPFIsolationBackend(simulate_mode=True)
    ebpf_backend.attach_policy_hooks()

    isolation_provider = LocalProcessIsolationProvider(eBPF_backend=ebpf_backend)
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    sandbox_handle = isolation_provider.create_sandbox(
        workspace_dir=str(workspace_dir),
        profile=PROFILE_STANDARD,
        policy=IsolationPolicy(
            allowed_workspace_paths=[str(workspace_dir)],
            prohibited_commands=["visudo", "reboot"],
        ),
    )
    assert sandbox_handle.is_active is True

    # Execute safe worker command inside sandbox
    exec_result = isolation_provider.execute_in_sandbox(
        handle=sandbox_handle,
        command=[sys.executable, "-c", "print('AutoDev v2.5 Execution Successful')"],
    )
    assert exec_result.exit_code == 0
    assert "AutoDev v2.5 Execution Successful" in exec_result.stdout

    # Record eBPF probe observation
    ebpf_event = ebpf_backend.record_probe_event("process_exec", pid=1001, comm="python", target=sys.executable)
    assert ebpf_event.is_violation is False

    # =========================================================================
    # 4. Peer-to-Peer Artifact Distribution & Differential Verification
    # =========================================================================
    worker_store_dir = tmp_path / "worker_store"
    coordinator_store_dir = tmp_path / "coord_store"
    worker_store = ArtifactChunkStore(storage_root=str(worker_store_dir))
    coord_store = ArtifactChunkStore(storage_root=str(coordinator_store_dir))

    # Produce artifact chunks
    block_a = b"function computeMetrics() { return 42; }\n"
    block_b = b"export default computeMetrics;\n"
    hash_a = hashlib.sha256(block_a).hexdigest()
    hash_b = hashlib.sha256(block_b).hexdigest()

    coord_store.put_chunk(digest=hash_a, data=block_a)
    coord_store.put_chunk(digest=hash_b, data=block_b)

    # Peer registry
    peer_registry = ArtifactPeerRegistry()
    peer_registry.register_peer("peer-node-alpha", endpoint="http://10.20.1.1:8090")
    peer_registry.heartbeat("peer-node-alpha", possessed_chunks=[hash_a, hash_b])

    # Artifact manifest
    manifest = ChunkManifest(
        artifact_id="art-bundle-001",
        whole_sha256=hashlib.sha256(block_a + block_b).hexdigest(),
        total_size_bytes=len(block_a) + len(block_b),
        chunks=[
            ChunkMetadata(digest=hash_a, size_bytes=len(block_a), offset=0, index=0),
            ChunkMetadata(digest=hash_b, size_bytes=len(block_b), offset=len(block_a), index=1),
        ],
    )

    p2p_planner = ArtifactDistributionPlanner(peer_registry=peer_registry)
    plan = p2p_planner.plan_fetch(manifest, worker_store)
    assert plan.missing_chunks_count == 2

    # Execute fetch plan
    def p2p_mock_transport(endpoint: str, digest: str) -> bytes:
        if digest == hash_a:
            return block_a
        elif digest == hash_b:
            return block_b
        raise ValueError(f"Unknown chunk {digest}")

    peer_client = ArtifactPeerClient(chunk_store=worker_store)
    fetch_result = p2p_planner.execute_fetch_plan(
        plan=plan,
        peer_client=peer_client,
        local_chunk_store=worker_store,
        transport_mock=p2p_mock_transport,
    )
    assert fetch_result["success"] is True
    assert fetch_result["p2p_chunks_downloaded"] == 2
    assert worker_store.has_chunk(hash_a) is True
    assert worker_store.has_chunk(hash_b) is True

    # =========================================================================
    # 5. WebRTC Remote Debugging Transport Verification
    # =========================================================================
    webrtc_transport = WebRTCTerminalTransport(
        session_id="dbg-session-99",
        sandbox_id=sandbox_handle.sandbox_id,
        auth_principal="developer-alice",
        is_container_sandbox=True,
    )
    answer = webrtc_transport.process_sdp_offer("v=0\r\no=alice 100 0 IN IP4 0.0.0.0\r\ns=dbg\r\n")
    assert answer["type"] == "answer"

    terminal_logs = []
    webrtc_transport.on_output(lambda msg: terminal_logs.append(msg))
    webrtc_transport.send_output("[v2.5] worker container ready.\n")
    assert "[v2.5] worker container ready.\n" in terminal_logs

    # Clean teardown
    webrtc_transport.close()
    isolation_provider.destroy_sandbox(sandbox_handle)
    coord.stop()
