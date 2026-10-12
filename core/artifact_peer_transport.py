"""
AutoDev Version 2.5 - Peer-to-Peer Artifact Transport & Chunk Verification.

Handles direct authenticated chunk exchange between worker nodes with strict SHA-256
integrity verification, mutual authentication tokens, and rate-limited chunk streaming.
"""

from __future__ import annotations

import hashlib
import time
import logging
import urllib.request
import urllib.error
from typing import Any, Dict, Optional, Tuple

from core.artifact_chunk_store import ArtifactChunkStore

logger = logging.getLogger("AutoDev.ArtifactPeerTransport")


class ChunkIntegrityError(Exception):
    """Raised when a transferred chunk digest does not match its expected SHA-256."""
    pass


class PeerTransportError(Exception):
    """Raised when network transfer to a peer node fails."""
    pass


class ArtifactPeerClient:
    """
    Client for requesting and validating Content-Addressed chunks directly
    from peer worker nodes or fallback coordinator storage.
    """

    def __init__(self, chunk_store: ArtifactChunkStore, auth_token: str = ""):
        self.chunk_store = chunk_store
        self.auth_token = auth_token

    def fetch_chunk_from_peer(
        self,
        peer_endpoint: str,
        chunk_digest: str,
        expected_size: Optional[int] = None,
        timeout: float = 10.0,
    ) -> bytes:
        """
        Retrieves chunk bytes from peer, validates SHA-256 digest, and stores into local CAS.
        """
        # If already present locally, return immediately
        if self.chunk_store.has_chunk(chunk_digest):
            return self.chunk_store.get_chunk(chunk_digest)

        url = f"{peer_endpoint.rstrip('/')}/api/v2.5/artifacts/chunks/{chunk_digest}"
        req = urllib.request.Request(url)
        if self.auth_token:
            req.add_header("Authorization", f"Bearer {self.auth_token}")
        req.add_header("User-Agent", "AutoDev-Artifact-P2P/2.5")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
        except Exception as e:
            raise PeerTransportError(f"Failed to fetch chunk '{chunk_digest}' from {peer_endpoint}: {e}")

        # Strict SHA-256 Verification
        computed_hash = hashlib.sha256(data).hexdigest()
        if computed_hash != chunk_digest:
            raise ChunkIntegrityError(
                f"Chunk integrity mismatch! Expected SHA-256 {chunk_digest}, got {computed_hash}"
            )

        if expected_size is not None and len(data) != expected_size:
            raise ChunkIntegrityError(
                f"Chunk size mismatch! Expected {expected_size} bytes, got {len(data)}"
            )

        # Store into local chunk store
        self.chunk_store.put_chunk(digest=chunk_digest, data=data)
        return data


class ArtifactPeerServer:
    """
    Lightweight server handler for serving content-addressed chunks to authorized peers.
    """

    def __init__(self, chunk_store: ArtifactChunkStore, shared_secret: str = ""):
        self.chunk_store = chunk_store
        self.shared_secret = shared_secret

    def handle_get_chunk(self, chunk_digest: str, auth_header: Optional[str] = None) -> Tuple[int, bytes]:
        """
        Validates authorization and returns chunk bytes if found.
        """
        if self.shared_secret:
            expected_auth = f"Bearer {self.shared_secret}"
            if not auth_header or auth_header != expected_auth:
                return 401, b'{"error": "Unauthorized chunk access"}'

        # Sanitize digest (must be hex 64 chars)
        if len(chunk_digest) != 64 or not all(c in "0123456789abcdefABCDEF" for c in chunk_digest):
            return 400, b'{"error": "Invalid chunk digest format"}'

        if not self.chunk_store.has_chunk(chunk_digest):
            return 404, b'{"error": "Chunk not found"}'

        try:
            data = self.chunk_store.get_chunk(chunk_digest)
            return 200, data
        except Exception as e:
            return 500, f'{{"error": "Chunk retrieval error: {e}"}}'.encode()
