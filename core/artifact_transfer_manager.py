"""
AutoDev Artifact Transfer Manager (Phase 4 - Differential Artifact Synchronization)
Coordinates differential artifact synchronization, manifest negotiation, resumable
transfers, content-addressed staging, and whole-artifact integrity verification.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import os
from typing import Dict, List, Optional, Set, Tuple, Any
import logging

from core.artifact_chunker import ArtifactChunker, ChunkInfo
from core.artifact_chunk_store import ArtifactChunkStore, ChunkIntegrityError
from core.artifact_sync_protocol import (
    ChunkMetadata,
    ChunkManifest,
    ChunkSyncNegotiationRequest,
    ChunkSyncNegotiationResponse,
    ChunkTransferMessage,
    ChunkSyncAck,
)

logger = logging.getLogger(__name__)


@dataclass
class TransferSession:
    """Tracks state of an active or resumable artifact transfer."""
    artifact_id: str
    manifest: ChunkManifest
    staging_path: str
    received_chunk_digests: Set[str] = field(default_factory=set)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_activity_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed: bool = False
    verified_sha256: Optional[str] = None


class ArtifactTransferManager:
    """
    Manages client/server differential artifact synchronization.
    Reduces network bandwidth by transmitting only missing content-addressed chunks.
    """

    def __init__(
        self,
        chunk_store: Optional[ArtifactChunkStore] = None,
        chunker: Optional[ArtifactChunker] = None,
        staging_dir: str = "memory/staging/artifacts",
    ) -> None:
        self.chunk_store = chunk_store or ArtifactChunkStore()
        self.chunker = chunker or ArtifactChunker()
        self.staging_dir = os.path.abspath(staging_dir)
        os.makedirs(self.staging_dir, exist_ok=True)
        self.active_sessions: Dict[str, TransferSession] = {}

    def create_manifest_for_file(
        self,
        file_path: str,
        artifact_id: str,
        transaction_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        producer_id: str = "sender",
    ) -> Tuple[ChunkManifest, List[ChunkInfo]]:
        """
        Inspect a local file, chunk it using FastCDC, store chunks into local CAS,
        and generate a versioned ChunkManifest.
        """
        chunk_infos = self.chunker.chunk_file(file_path, include_data=True)
        total_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        whole_sha256 = hasher.hexdigest()

        # Store chunks in local chunk store
        manifest_chunks: List[ChunkMetadata] = []
        for c in chunk_infos:
            if c.data is not None:
                self.chunk_store.put_chunk(c.digest, c.data)
            manifest_chunks.append(
                ChunkMetadata(
                    digest=c.digest,
                    size_bytes=c.size_bytes,
                    offset=c.offset,
                    index=c.index,
                )
            )

        manifest = ChunkManifest(
            artifact_id=artifact_id,
            manifest_version="2.4",
            total_size_bytes=total_size,
            whole_sha256=whole_sha256,
            chunk_algorithm="fastcdc",
            min_size=self.chunker.min_size,
            target_size=self.chunker.target_size,
            max_size=self.chunker.max_size,
            chunks=manifest_chunks,
            producer_id=producer_id,
            transaction_id=transaction_id,
            operation_id=operation_id,
        )
        return manifest, chunk_infos

    def negotiate_incoming_transfer(self, manifest: ChunkManifest) -> ChunkSyncNegotiationResponse:
        """
        Receiver side: check which chunks in the manifest are already present in CAS.
        Initialize a TransferSession for resumable transfer.
        """
        missing: List[str] = []
        existing_count = 0

        session_staging = os.path.join(self.staging_dir, f"{manifest.artifact_id}.stage")
        session = TransferSession(
            artifact_id=manifest.artifact_id,
            manifest=manifest,
            staging_path=session_staging,
        )

        for chunk_meta in manifest.chunks:
            if self.chunk_store.has_chunk(chunk_meta.digest):
                existing_count += 1
                session.received_chunk_digests.add(chunk_meta.digest)
            else:
                missing.append(chunk_meta.digest)

        self.active_sessions[manifest.artifact_id] = session

        return ChunkSyncNegotiationResponse(
            artifact_id=manifest.artifact_id,
            missing_chunk_digests=missing,
            existing_chunk_count=existing_count,
            total_chunk_count=len(manifest.chunks),
        )

    def receive_chunk(self, message: ChunkTransferMessage) -> bool:
        """
        Receiver side: ingest, cryptographically verify, and persist an incoming chunk.
        """
        session = self.active_sessions.get(message.artifact_id)
        if not session:
            raise ValueError(f"No active transfer session for artifact {message.artifact_id}")

        chunk_data = message.get_data()
        self.chunk_store.put_chunk(message.chunk_digest, chunk_data)
        session.received_chunk_digests.add(message.chunk_digest)
        session.last_activity_at = datetime.now(timezone.utc).isoformat()
        return True

    def is_transfer_ready(self, artifact_id: str) -> bool:
        """Check if all chunks for an artifact are present in CAS."""
        session = self.active_sessions.get(artifact_id)
        if not session:
            return False
        required_digests = {c.digest for c in session.manifest.chunks}
        return required_digests.issubset(session.received_chunk_digests)

    def reconstruct_artifact(self, artifact_id: str, destination_path: str) -> ChunkSyncAck:
        """
        Receiver side: assemble verified chunks from CAS into destination file
        and verify whole-artifact SHA-256 against manifest.
        """
        session = self.active_sessions.get(artifact_id)
        if not session:
            raise ValueError(f"Transfer session for {artifact_id} not found")

        # Verify all chunks exist in CAS
        chunks_data: List[bytes] = []
        for c in session.manifest.chunks:
            data = self.chunk_store.get_chunk(c.digest)
            if data is None:
                raise ChunkIntegrityError(f"Missing required chunk {c.digest} during reconstruction")
            chunks_data.append(data)

        # Reconstruct in staging area first
        staged_file = session.staging_path
        verified_sha256 = ArtifactChunker.reconstruct_file(
            chunks_data=chunks_data,
            output_path=staged_file,
            expected_sha256=session.manifest.whole_sha256,
        )

        # Move to final destination
        os.makedirs(os.path.dirname(os.path.abspath(destination_path)), exist_ok=True)
        if os.path.exists(destination_path):
            os.remove(destination_path)
        os.rename(staged_file, destination_path)

        session.completed = True
        session.verified_sha256 = verified_sha256

        return ChunkSyncAck(
            artifact_id=artifact_id,
            verified_chunk_count=len(session.manifest.chunks),
            whole_sha256_verified=True,
            status="completed",
        )
