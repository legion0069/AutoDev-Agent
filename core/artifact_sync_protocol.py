"""
AutoDev Artifact Differential Sync Protocol (Phase 4 - Differential Artifact Synchronization)
Defines protocol messages and versioned chunk manifests for differential artifact transfer.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import base64
import json


@dataclass
class ChunkMetadata:
    """Metadata describing a single chunk within a chunked artifact."""
    digest: str
    size_bytes: int
    offset: int
    index: int


@dataclass
class ChunkManifest:
    """
    Versioned manifest describing all chunks and reconstruction properties of an artifact.
    """
    artifact_id: str
    total_size_bytes: int
    whole_sha256: str
    chunks: List[ChunkMetadata]
    manifest_version: str = "2.4"
    chunk_algorithm: str = "fastcdc"
    min_size: int = 4096
    target_size: int = 16384
    max_size: int = 65536
    producer_id: str = "coordinator"
    transaction_id: Optional[str] = None
    operation_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "manifest_version": self.manifest_version,
            "total_size_bytes": self.total_size_bytes,
            "whole_sha256": self.whole_sha256,
            "chunk_algorithm": self.chunk_algorithm,
            "min_size": self.min_size,
            "target_size": self.target_size,
            "max_size": self.max_size,
            "producer_id": self.producer_id,
            "transaction_id": self.transaction_id,
            "operation_id": self.operation_id,
            "created_at": self.created_at,
            "chunks": [asdict(c) for c in self.chunks],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkManifest":
        chunks_raw = data.get("chunks", [])
        chunks = [
            ChunkMetadata(
                digest=c["digest"],
                size_bytes=c["size_bytes"],
                offset=c["offset"],
                index=c["index"],
            )
            for c in chunks_raw
        ]
        return cls(
            artifact_id=data["artifact_id"],
            manifest_version=data.get("manifest_version", "2.4"),
            total_size_bytes=data["total_size_bytes"],
            whole_sha256=data["whole_sha256"],
            chunks=chunks,
            chunk_algorithm=data.get("chunk_algorithm", "fastcdc"),
            min_size=data.get("min_size", 4096),
            target_size=data.get("target_size", 16384),
            max_size=data.get("max_size", 65536),
            producer_id=data.get("producer_id", "coordinator"),
            transaction_id=data.get("transaction_id"),
            operation_id=data.get("operation_id"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class ChunkSyncNegotiationRequest:
    manifest: ChunkManifest


@dataclass
class ChunkSyncNegotiationResponse:
    artifact_id: str
    missing_chunk_digests: List[str]
    existing_chunk_count: int
    total_chunk_count: int


@dataclass
class ChunkTransferMessage:
    artifact_id: str
    chunk_digest: str
    chunk_index: int
    chunk_data_b64: str  # Base64 encoded payload for JSON/gRPC transport

    @classmethod
    def from_bytes(cls, artifact_id: str, chunk_digest: str, chunk_index: int, data: bytes) -> "ChunkTransferMessage":
        return cls(
            artifact_id=artifact_id,
            chunk_digest=chunk_digest,
            chunk_index=chunk_index,
            chunk_data_b64=base64.b64encode(data).decode("ascii"),
        )

    def get_data(self) -> bytes:
        return base64.b64decode(self.chunk_data_b64.encode("ascii"))


@dataclass
class ChunkSyncAck:
    artifact_id: str
    verified_chunk_count: int
    whole_sha256_verified: bool
    status: str  # "completed", "in_progress", "failed"
    error: Optional[str] = None
