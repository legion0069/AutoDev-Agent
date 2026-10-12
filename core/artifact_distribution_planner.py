"""
AutoDev Version 2.5 - Fleet-Scale Peer-to-Peer Artifact Distribution Planner.

Plans multi-source chunk downloads, schedules differential transfers from optimal peers,
manages replication policies, and protects active transfers from premature garbage collection.
"""

from __future__ import annotations

import time
import hashlib
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.artifact_chunk_store import ArtifactChunkStore
from core.artifact_manifest import ArtifactManifest
from core.artifact_peer_registry import ArtifactPeerRegistry, PeerInfo
from core.artifact_peer_transport import ArtifactPeerClient, ChunkIntegrityError

logger = logging.getLogger("AutoDev.ArtifactDistributionPlanner")


@dataclass
class ArtifactReplicationPolicy:
    """Policy dictating how widely critical build and test artifacts are distributed."""
    min_replication_factor: int = 2
    max_concurrent_downloads: int = 4
    prefer_local_rack: bool = True
    retry_attempts_per_chunk: int = 3
    fallback_to_coordinator: bool = True


@dataclass
class ChunkTransferTask:
    """Represents a planned transfer for an individual missing chunk."""
    chunk_digest: str
    chunk_index: int
    size_bytes: int
    eligible_peer_endpoints: List[str]
    selected_endpoint: Optional[str] = None
    is_cached_locally: bool = False
    status: str = "pending"  # 'pending', 'downloading', 'completed', 'failed'
    bytes_transferred: int = 0
    duration_seconds: float = 0.0


@dataclass
class ArtifactFetchPlan:
    """Comprehensive multi-source execution plan for reconstructing an artifact."""
    artifact_id: str
    manifest_digest: str
    total_chunks: int
    total_size_bytes: int
    missing_chunks: List[ChunkTransferTask]
    cached_chunks_count: int
    missing_chunks_count: int
    estimated_network_bytes: int
    created_at: float = field(default_factory=time.time)


class ArtifactDistributionPlanner:
    """
    Schedules differential P2P chunk transfers across worker fleet.
    Integrates with ArtifactPeerRegistry and ArtifactChunkStore to minimize coordinator bandwidth.
    """

    def __init__(
        self,
        peer_registry: ArtifactPeerRegistry,
        policy: Optional[ArtifactReplicationPolicy] = None,
    ):
        self.peer_registry = peer_registry
        self.policy = policy or ArtifactReplicationPolicy()
        self._lock = threading.RLock()
        self._active_transfer_chunks: Set[str] = set()

    def lock_chunks_for_transfer(self, chunk_digests: List[str]) -> None:
        """Lock chunk hashes to prevent concurrent Garbage Collection from pruning them."""
        with self._lock:
            for c in chunk_digests:
                self._active_transfer_chunks.add(c)

    def unlock_chunks(self, chunk_digests: List[str]) -> None:
        """Unlock chunk hashes after transfer completes."""
        with self._lock:
            for c in chunk_digests:
                self._active_transfer_chunks.discard(c)

    def is_chunk_in_active_transfer(self, chunk_digest: str) -> bool:
        """Called by Garbage Collector to protect in-flight chunks."""
        with self._lock:
            return chunk_digest in self._active_transfer_chunks

    def plan_fetch(
        self,
        manifest: Any,
        local_chunk_store: ArtifactChunkStore,
    ) -> ArtifactFetchPlan:
        """
        Inspects local chunk cache and creates an optimal P2P download plan.
        Supports ChunkManifest, ArtifactManifest, or custom manifest models.
        """
        active_peers = {p.peer_id: p for p in self.peer_registry.list_active_peers()}
        missing_tasks: List[ChunkTransferTask] = []
        cached_count = 0
        missing_bytes = 0

        chunks = getattr(manifest, "chunks", [])
        if isinstance(chunks, dict):
            chunks = list(chunks.values())

        for idx, chunk_entry in enumerate(chunks):
            if hasattr(chunk_entry, "digest"):
                digest = chunk_entry.digest
                size = getattr(chunk_entry, "size_bytes", 0)
            elif isinstance(chunk_entry, dict):
                digest = chunk_entry.get("chunk_hash") or chunk_entry.get("digest") or ""
                size = chunk_entry.get("size") or chunk_entry.get("size_bytes") or 0
            else:
                digest = str(chunk_entry)
                size = 0

            if local_chunk_store.has_chunk(digest):
                cached_count += 1
            else:
                # Find candidate peers who have this chunk
                peer_ids = self.peer_registry.availability_index.find_peers_for_chunk(digest)
                endpoints: List[str] = []
                for pid in peer_ids:
                    pinfo = active_peers.get(pid)
                    if pinfo and pinfo.has_capacity:
                        endpoints.append(pinfo.endpoint)

                # Fallback to coordinator if no active peer has it
                if not endpoints and self.policy.fallback_to_coordinator:
                    endpoints.append(self.peer_registry.coordinator_endpoint)

                selected = endpoints[0] if endpoints else None
                missing_tasks.append(ChunkTransferTask(
                    chunk_digest=digest,
                    chunk_index=idx,
                    size_bytes=size,
                    eligible_peer_endpoints=endpoints,
                    selected_endpoint=selected,
                    is_cached_locally=False,
                ))
                missing_bytes += size

        art_id = getattr(manifest, "artifact_id", getattr(manifest, "manifest_id", "unknown_artifact"))
        root_digest = getattr(manifest, "whole_sha256", getattr(manifest, "root_digest", ""))
        tot_size = getattr(manifest, "total_size_bytes", getattr(manifest, "total_size", missing_bytes))

        return ArtifactFetchPlan(
            artifact_id=art_id,
            manifest_digest=root_digest,
            total_chunks=len(chunks),
            total_size_bytes=tot_size,
            missing_chunks=missing_tasks,
            cached_chunks_count=cached_count,
            missing_chunks_count=len(missing_tasks),
            estimated_network_bytes=missing_bytes,
        )

    def execute_fetch_plan(
        self,
        plan: ArtifactFetchPlan,
        peer_client: ArtifactPeerClient,
        local_chunk_store: ArtifactChunkStore,
        transport_mock: Optional[Callable[[str, str], bytes]] = None,
    ) -> Dict[str, Any]:
        """
        Executes the fetch plan, downloads missing chunks, and verifies the reconstructed artifact.
        """
        start_t = time.time()
        chunk_digests = [task.chunk_digest for task in plan.missing_chunks]
        self.lock_chunks_for_transfer(chunk_digests)

        transferred_bytes = 0
        failed_chunks = []

        try:
            for task in plan.missing_chunks:
                task_start = time.time()
                success = False

                # Try eligible peer endpoints in order
                for endpoint in task.eligible_peer_endpoints:
                    try:
                        if transport_mock:
                            data = transport_mock(endpoint, task.chunk_digest)
                            # Verify SHA-256
                            calc = hashlib.sha256(data).hexdigest()
                            if calc != task.chunk_digest:
                                raise ChunkIntegrityError("Corrupt chunk in mock transport")
                            local_chunk_store.put_chunk(digest=task.chunk_digest, data=data)
                        else:
                            data = peer_client.fetch_chunk_from_peer(
                                peer_endpoint=endpoint,
                                chunk_digest=task.chunk_digest,
                                expected_size=task.size_bytes if task.size_bytes > 0 else None,
                            )

                        task.status = "completed"
                        task.bytes_transferred = len(data)
                        task.duration_seconds = time.time() - task_start
                        transferred_bytes += len(data)
                        success = True
                        break
                    except Exception as e:
                        logger.warning(f"Failed to fetch chunk {task.chunk_digest} from {endpoint}: {e}")

                if not success:
                    task.status = "failed"
                    failed_chunks.append(task.chunk_digest)

            # Reconstruct and verify total digest if all chunks acquired
            total_duration = time.time() - start_t
            if failed_chunks:
                return {
                    "success": False,
                    "artifact_id": plan.artifact_id,
                    "failed_chunks": failed_chunks,
                    "duration_seconds": total_duration,
                    "bytes_transferred": transferred_bytes,
                }

            return {
                "success": True,
                "artifact_id": plan.artifact_id,
                "total_chunks": plan.total_chunks,
                "cached_chunks_used": plan.cached_chunks_count,
                "p2p_chunks_downloaded": len(plan.missing_chunks),
                "bytes_transferred": transferred_bytes,
                "duration_seconds": total_duration,
            }

        finally:
            self.unlock_chunks(chunk_digests)
