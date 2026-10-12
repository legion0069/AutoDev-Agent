"""
AutoDev Version 2.5 - Fleet-Scale Artifact Peer Registry & Availability Index.

Maintains peer worker registrations, content-addressed chunk availability indices,
peer health heartbeats, and storage quotas for decentralized peer-to-peer distribution.
"""

from __future__ import annotations

import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("AutoDev.ArtifactPeerRegistry")


@dataclass
class PeerInfo:
    """Information regarding an authorized worker peer eligible for artifact exchange."""
    peer_id: str
    endpoint: str  # e.g. "http://10.0.1.5:8090" or "grpc://10.0.1.5:50055"
    role: str = "worker"
    public_key_fingerprint: str = ""
    max_concurrent_transfers: int = 8
    active_transfers: int = 0
    storage_quota_bytes: int = 10 * 1024 * 1024 * 1024  # 10 GB
    storage_used_bytes: int = 0
    last_heartbeat: float = field(default_factory=time.time)
    heartbeat_ttl_seconds: float = 30.0
    is_authorized: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_alive(self) -> bool:
        return (time.time() - self.last_heartbeat) < self.heartbeat_ttl_seconds and self.is_authorized

    @property
    def has_capacity(self) -> bool:
        return self.is_alive and self.active_transfers < self.max_concurrent_transfers


class ArtifactAvailabilityIndex:
    """
    Thread-safe inverted index mapping Content-Addressed chunk hashes to the
    set of active peer IDs that possess verified copies of each chunk.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._chunk_to_peers: Dict[str, Set[str]] = {}  # chunk_digest -> set(peer_id)
        self._peer_to_chunks: Dict[str, Set[str]] = {}  # peer_id -> set(chunk_digest)

    def register_chunks(self, peer_id: str, chunk_digests: List[str]) -> None:
        """Register that a peer possesses a list of verified chunk digests."""
        with self._lock:
            if peer_id not in self._peer_to_chunks:
                self._peer_to_chunks[peer_id] = set()

            for digest in chunk_digests:
                if digest not in self._chunk_to_peers:
                    self._chunk_to_peers[digest] = set()
                self._chunk_to_peers[digest].add(peer_id)
                self._peer_to_chunks[peer_id].add(digest)

    def unregister_peer(self, peer_id: str) -> None:
        """Remove all chunk associations for an expired or disconnected peer."""
        with self._lock:
            chunks = self._peer_to_chunks.pop(peer_id, set())
            for digest in chunks:
                peers = self._chunk_to_peers.get(digest)
                if peers:
                    peers.discard(peer_id)
                    if not peers:
                        del self._chunk_to_peers[digest]

    def find_peers_for_chunk(self, chunk_digest: str) -> List[str]:
        """Return list of peer IDs that possess the specified chunk."""
        with self._lock:
            peers = self._chunk_to_peers.get(chunk_digest, set())
            return list(peers)

    def get_chunk_replication_count(self, chunk_digest: str) -> int:
        with self._lock:
            return len(self._chunk_to_peers.get(chunk_digest, set()))

    def total_indexed_chunks(self) -> int:
        with self._lock:
            return len(self._chunk_to_peers)


class ArtifactPeerRegistry:
    """
    Fleet-scale peer discovery and authorization registry.
    Coordinates worker peer registrations, liveness heartbeats, and content availability.
    """

    def __init__(self, coordinator_endpoint: Optional[str] = None):
        self.coordinator_endpoint = coordinator_endpoint or "http://127.0.0.1:8080"
        self._lock = threading.RLock()
        self._peers: Dict[str, PeerInfo] = {}
        self.availability_index = ArtifactAvailabilityIndex()

    def register_peer(
        self,
        peer_id: str,
        endpoint: str,
        role: str = "worker",
        public_key_fingerprint: str = "",
        max_concurrent_transfers: int = 8,
        storage_quota_bytes: int = 10 * 1024 * 1024 * 1024,
    ) -> PeerInfo:
        """Register or update an authorized peer worker node."""
        with self._lock:
            peer = PeerInfo(
                peer_id=peer_id,
                endpoint=endpoint,
                role=role,
                public_key_fingerprint=public_key_fingerprint,
                max_concurrent_transfers=max_concurrent_transfers,
                storage_quota_bytes=storage_quota_bytes,
                last_heartbeat=time.time(),
                is_authorized=True,
            )
            self._peers[peer_id] = peer
            logger.info(f"Registered artifact peer '{peer_id}' at {endpoint}")
            return peer

    def heartbeat(
        self,
        peer_id: str,
        active_transfers: Optional[int] = None,
        storage_used_bytes: Optional[int] = None,
        possessed_chunks: Optional[List[str]] = None,
    ) -> bool:
        """Record heartbeat and update advertised chunk availability from peer."""
        with self._lock:
            peer = self._peers.get(peer_id)
            if not peer or not peer.is_authorized:
                return False

            peer.last_heartbeat = time.time()
            if active_transfers is not None:
                peer.active_transfers = active_transfers
            if storage_used_bytes is not None:
                peer.storage_used_bytes = storage_used_bytes

            if possessed_chunks:
                self.availability_index.register_chunks(peer_id, possessed_chunks)

            return True

    def get_peer(self, peer_id: str) -> Optional[PeerInfo]:
        with self._lock:
            return self._peers.get(peer_id)

    def list_active_peers(self) -> List[PeerInfo]:
        """Return all peers that have sent a heartbeat within TTL."""
        with self._lock:
            self._prune_stale_peers()
            return [p for p in self._peers.values() if p.is_alive]

    def _prune_stale_peers(self) -> None:
        """Remove peers that have timed out and unregister their chunks."""
        now = time.time()
        stale_ids = [
            pid for pid, p in self._peers.items()
            if (now - p.last_heartbeat) >= p.heartbeat_ttl_seconds
        ]
        for pid in stale_ids:
            logger.info(f"Pruning stale artifact peer '{pid}'")
            self._peers.pop(pid, None)
            self.availability_index.unregister_peer(pid)

    def deregister_peer(self, peer_id: str) -> None:
        with self._lock:
            self._peers.pop(peer_id, None)
            self.availability_index.unregister_peer(peer_id)
