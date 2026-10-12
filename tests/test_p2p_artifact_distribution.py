"""
Tests for AutoDev v2.5 Fleet-Scale Peer-to-Peer Artifact Distribution.
"""

import hashlib
import tempfile
from pathlib import Path
import pytest

from core.artifact_chunk_store import ArtifactChunkStore
from core.artifact_sync_protocol import ChunkManifest, ChunkMetadata
from core.artifact_manifest import ArtifactManifest
from core.artifact_peer_registry import ArtifactPeerRegistry
from core.artifact_peer_transport import ArtifactPeerClient, ArtifactPeerServer
from core.artifact_distribution_planner import ArtifactDistributionPlanner, ArtifactReplicationPolicy


def test_peer_registry_and_availability_index():
    registry = ArtifactPeerRegistry(coordinator_endpoint="http://10.0.0.1:8080")

    p1 = registry.register_peer("worker-node-1", endpoint="http://10.0.1.1:8090")
    p2 = registry.register_peer("worker-node-2", endpoint="http://10.0.1.2:8090")

    assert p1.is_alive is True
    assert len(registry.list_active_peers()) == 2

    # Register chunk availability
    chunk_a = hashlib.sha256(b"chunk_alpha").hexdigest()
    chunk_b = hashlib.sha256(b"chunk_beta").hexdigest()

    registry.heartbeat("worker-node-1", possessed_chunks=[chunk_a])
    registry.heartbeat("worker-node-2", possessed_chunks=[chunk_a, chunk_b])

    assert registry.availability_index.find_peers_for_chunk(chunk_a) == ["worker-node-1", "worker-node-2"] or \
           set(registry.availability_index.find_peers_for_chunk(chunk_a)) == {"worker-node-1", "worker-node-2"}
    assert registry.availability_index.find_peers_for_chunk(chunk_b) == ["worker-node-2"]

    # Deregister peer 1
    registry.deregister_peer("worker-node-1")
    assert registry.availability_index.find_peers_for_chunk(chunk_a) == ["worker-node-2"]


def test_p2p_artifact_distribution_plan_and_execution(tmp_path):
    # Setup two stores: peer1 store and local worker store
    peer1_store_dir = tmp_path / "peer1_store"
    local_store_dir = tmp_path / "local_store"
    peer1_store = ArtifactChunkStore(storage_root=str(peer1_store_dir))
    local_store = ArtifactChunkStore(storage_root=str(local_store_dir))

    # Chunk data
    c1_bytes = b"alpha_content_block_1"
    c2_bytes = b"beta_content_block_2"
    c1_hash = hashlib.sha256(c1_bytes).hexdigest()
    c2_hash = hashlib.sha256(c2_bytes).hexdigest()

    # Pre-populate peer1 store
    peer1_store.put_chunk(digest=c1_hash, data=c1_bytes)
    peer1_store.put_chunk(digest=c2_hash, data=c2_bytes)

    # Pre-populate local store with only c1 (so c2 is missing)
    local_store.put_chunk(digest=c1_hash, data=c1_bytes)

    # Registry
    registry = ArtifactPeerRegistry()
    registry.register_peer("peer-1", endpoint="http://10.0.1.1:8090")
    registry.heartbeat("peer-1", possessed_chunks=[c1_hash, c2_hash])

    # Artifact manifest referencing c1 and c2
    manifest = ChunkManifest(
        artifact_id="art-test-01",
        whole_sha256="root-digest-01",
        total_size_bytes=len(c1_bytes) + len(c2_bytes),
        chunks=[
            ChunkMetadata(digest=c1_hash, size_bytes=len(c1_bytes), offset=0, index=0),
            ChunkMetadata(digest=c2_hash, size_bytes=len(c2_bytes), offset=len(c1_bytes), index=1),
        ],
    )

    planner = ArtifactDistributionPlanner(peer_registry=registry)
    plan = planner.plan_fetch(manifest, local_store)

    assert plan.total_chunks == 2
    assert plan.cached_chunks_count == 1
    assert plan.missing_chunks_count == 1
    assert plan.missing_chunks[0].chunk_digest == c2_hash
    assert "http://10.0.1.1:8090" in plan.missing_chunks[0].eligible_peer_endpoints

    # Execute fetch with transport mock
    def mock_transport(endpoint: str, digest: str) -> bytes:
        if digest == c2_hash:
            return c2_bytes
        raise ValueError("Unknown chunk")

    peer_client = ArtifactPeerClient(chunk_store=local_store)
    result = planner.execute_fetch_plan(
        plan=plan,
        peer_client=peer_client,
        local_chunk_store=local_store,
        transport_mock=mock_transport,
    )

    assert result["success"] is True
    assert result["p2p_chunks_downloaded"] == 1
    assert local_store.has_chunk(c2_hash) is True
