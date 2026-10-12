"""
End-to-End Integration Tests for AutoDev Version 2.4 (Phase 8.5)
Exercises HA coordination, Kubernetes worker provisioning, FastCDC differential artifact sync,
and secure interactive debugging in a unified lifecycle workflow.
"""

import os
import json
import time
import tempfile
import pytest
from pathlib import Path

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
from core.orchestrator import Orchestrator


class TestAutoDevV24EndToEndIntegration:
    def test_full_v24_lifecycle(self, tmp_path):
        # 1. HA Coordination: 3-node cluster leader election
        store = MemoryCoordinationStore()
        peers = ["coord-alpha", "coord-beta", "coord-gamma"]
        cluster_map = {}

        def cluster_transport(peer_id, method, payload):
            target = cluster_map.get(peer_id)
            if not target:
                return None
            if method == "RequestVote":
                from core.consensus_protocol import VoteRequest
                req = VoteRequest.from_dict(payload)
                resp = target.receive_vote_request(req)
                return resp.to_dict()
            elif method == "Heartbeat":
                from core.consensus_protocol import ConsensusHeartbeat
                hb = ConsensusHeartbeat.from_dict(payload)
                return target.receive_heartbeat(hb)
            return None

        c_alpha = HACoordinator(coordinator_id="coord-alpha", peer_ids=peers, store=store, transport_call=cluster_transport)
        c_beta = HACoordinator(coordinator_id="coord-beta", peer_ids=peers, store=store, transport_call=cluster_transport)
        c_gamma = HACoordinator(coordinator_id="coord-gamma", peer_ids=peers, store=store, transport_call=cluster_transport)

        cluster_map["coord-alpha"] = c_alpha
        cluster_map["coord-beta"] = c_beta
        cluster_map["coord-gamma"] = c_gamma

        won = c_alpha.start_election()
        assert won is True
        assert c_alpha.role == CoordinatorRole.LEADER

        validator = LeaderFencingValidator(c_alpha)
        validator.assert_active_leader()
        token = c_alpha.fencing_token
        assert token is not None
        assert token.term == 1

        # 2. Kubernetes Worker Orchestration: Reconcile WorkerPool CRD
        k8s_client = FakeKubernetesClient()
        k8s_provider = KubernetesWorkerProvider(k8s_client)
        k8s_controller = KubernetesWorkerController(k8s_client, k8s_provider)

        crd = {
            "apiVersion": "autodev.io/v1alpha1",
            "kind": "AutoDevWorkerPool",
            "metadata": {"name": "ci-workers", "namespace": "autodev-system"},
            "spec": {
                "replicas": 2,
                "minReplicas": 1,
                "maxReplicas": 10,
                "image": "autodev/worker:v2.4.0",
                "scalingPolicy": {"enabled": True, "queueDepthThreshold": 2, "cooldownSeconds": 0},
            }
        }
        k8s_client.create_custom_resource("autodev.io", "v1alpha1", "autodevworkerpools", crd, "autodev-system")
        rec_res = k8s_controller.reconcile_pool("ci-workers", "autodev-system", queue_depth=6, busy_workers=2)
        assert rec_res.status == "Success"
        assert rec_res.desired_replicas > 2

        # 3. Differential Artifact Synchronization: Sender chunks file, Receiver negotiates & reconstructs
        sender_cas = ArtifactChunkStore(storage_root=str(tmp_path / "sender_cas"))
        receiver_cas = ArtifactChunkStore(storage_root=str(tmp_path / "receiver_cas"))
        chunker = ArtifactChunker(min_size=1024, target_size=2048, max_size=4096)

        sender_tm = ArtifactTransferManager(chunk_store=sender_cas, chunker=chunker)
        receiver_tm = ArtifactTransferManager(chunk_store=receiver_cas, chunker=chunker, staging_dir=str(tmp_path / "staging"))

        src_file = tmp_path / "build_output.tar"
        data_payload = b"TAR-CONTAINER-HEADER\n" + (b"BYTE-STREAM-CHUNK-DIFF-DATA-BLOCK\n" * 200)
        src_file.write_bytes(data_payload)

        manifest, _ = sender_tm.create_manifest_for_file(str(src_file), artifact_id="build-artifact-v1", transaction_id="tx-e2e-01")
        neg = receiver_tm.negotiate_incoming_transfer(manifest)

        # Transmit missing chunks
        for d in neg.missing_chunk_digests:
            chunk_bytes = sender_cas.get_chunk(d)
            receiver_tm.receive_chunk(ChunkTransferMessage.from_bytes(
                artifact_id="build-artifact-v1",
                chunk_digest=d,
                chunk_index=0,
                data=chunk_bytes,
            ))

        assert receiver_tm.is_transfer_ready("build-artifact-v1") is True
        target_reconstructed = tmp_path / "final_build_output.tar"
        ack = receiver_tm.reconstruct_artifact("build-artifact-v1", str(target_reconstructed))
        assert ack.status == "completed"
        assert ack.whole_sha256_verified is True
        assert target_reconstructed.read_bytes() == data_payload

        # 4. Secure Interactive Debugging: Authorize session & route frames
        auth = TerminalAuthorizer(TerminalSecurityPolicy(allowed_principals={"developer"}))
        sess_mgr = InteractiveSessionManager(authorizer=auth)
        gateway = TerminalGateway(session_manager=sess_mgr)

        # Authorized session creation
        create_resp = gateway.handle_client_message(json.dumps({
            "action": "create",
            "principal_id": "developer",
            "transaction_id": "tx-e2e-01",
            "sandbox_id": "sandbox-k8s-pod-01",
            "is_coordinator_host": False,
        }))
        assert create_resp["type"] == "created"
        debug_sid = create_resp["session_id"]

        # Terminal IO
        gateway.handle_client_message(json.dumps({
            "action": "input",
            "session_id": debug_sid,
            "data": "echo Debugging Complete\n"
        }))
        gateway.handle_client_message(json.dumps({
            "action": "terminate",
            "session_id": debug_sid,
        }))

        # 5. Coordinator Failover Simulation: Alpha crashes, Beta takes over
        c_alpha.role = CoordinatorRole.UNAVAILABLE
        c_beta.start_election()
        assert c_beta.role == CoordinatorRole.LEADER
        assert c_beta.current_term == 2
        beta_token = c_beta.fencing_token
        assert beta_token is not None
        assert beta_token.term == 2

        # Verify old leader Alpha cannot make protected mutations
        validator_alpha = LeaderFencingValidator(c_alpha)
        with pytest.raises(Exception):
            validator_alpha.assert_active_leader()

        # Beta reconciles failover
        reconcile_summary = c_beta.reconcile_failover()
        assert reconcile_summary["status"] == "reconciled"
        assert reconcile_summary["current_term"] == 2
