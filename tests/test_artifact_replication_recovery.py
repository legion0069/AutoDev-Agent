"""
Tests for artifact replication policies, peer failure recovery, and corruption detection.
"""

import hashlib
import pytest
from core.artifact_chunk_store import ArtifactChunkStore
from core.artifact_sync_protocol import ChunkManifest, ChunkMetadata
from core.artifact_peer_registry import ArtifactPeerRegistry
from core.artifact_peer_transport import ArtifactPeerClient, ChunkIntegrityError
from core.artifact_distribution_planner import ArtifactDistributionPlanner, ArtifactReplicationPolicy


def test_artifact_fetch_failover_to_secondary_peer(tmp_path):
    store = ArtifactChunkStore(storage_root=str(tmp_path / "store"))
    chunk_data = b"replication_failover_test_block"
    chunk_hash = hashlib.sha256(chunk_data).hexdigest()

    manifest = ChunkManifest(
        artifact_id="art-failover-01",
        whole_sha256=chunk_hash,
        total_size_bytes=len(chunk_data),
        chunks=[ChunkMetadata(digest=chunk_hash, size_bytes=len(chunk_data), offset=0, index=0)],
    )

    registry = ArtifactPeerRegistry(coordinator_endpoint="http://10.0.0.1:8080")
    # Peer 1 (failing) and Peer 2 (healthy)
    registry.register_peer("peer-failing", endpoint="http://10.0.1.1:8090")
    registry.register_peer("peer-healthy", endpoint="http://10.0.1.2:8090")

    registry.heartbeat("peer-failing", possessed_chunks=[chunk_hash])
    registry.heartbeat("peer-healthy", possessed_chunks=[chunk_hash])

    planner = ArtifactDistributionPlanner(peer_registry=registry)
    plan = planner.plan_fetch(manifest, store)

    # Mock transport where peer 1 fails and peer 2 succeeds
    def mock_transport(endpoint: str, digest: str) -> bytes:
        if endpoint == "http://10.0.1.1:8090":
            raise ConnectionRefusedError("Simulated peer node down")
        if endpoint == "http://10.0.1.2:8090":
            return chunk_data
        raise ValueError("Unknown endpoint")

    peer_client = ArtifactPeerClient(chunk_store=store)
    result = planner.execute_fetch_plan(
        plan=plan,
        peer_client=peer_client,
        local_chunk_store=store,
        transport_mock=mock_transport,
    )

    assert result["success"] is True
    assert store.has_chunk(chunk_hash) is True


def test_corrupted_chunk_rejected_and_reported(tmp_path):
    store = ArtifactChunkStore(storage_root=str(tmp_path / "store"))
    chunk_data = b"correct_chunk_payload"
    chunk_hash = hashlib.sha256(chunk_data).hexdigest()

    manifest = ChunkManifest(
        artifact_id="art-corrupt-01",
        whole_sha256=chunk_hash,
        total_size_bytes=len(chunk_data),
        chunks=[ChunkMetadata(digest=chunk_hash, size_bytes=len(chunk_data), offset=0, index=0)],
    )

    registry = ArtifactPeerRegistry()
    registry.register_peer("peer-corrupt", endpoint="http://10.0.1.9:8090")
    registry.heartbeat("peer-corrupt", possessed_chunks=[chunk_hash])

    planner = ArtifactDistributionPlanner(peer_registry=registry)
    plan = planner.plan_fetch(manifest, store)

    # Mock transport returns corrupt data
    def corrupt_transport(endpoint: str, digest: str) -> bytes:
        return b"tampered_chunk_corrupt_data"

    peer_client = ArtifactPeerClient(chunk_store=store)
    result = planner.execute_fetch_plan(
        plan=plan,
        peer_client=peer_client,
        local_chunk_store=store,
        transport_mock=corrupt_transport,
    )

    assert result["success"] is False
    assert chunk_hash in result["failed_chunks"]
    assert store.has_chunk(chunk_hash) is False
