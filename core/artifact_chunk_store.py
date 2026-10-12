"""
AutoDev Content-Addressed Artifact Chunk Store (Phase 4 - Differential Artifact Synchronization)
Provides immutable, content-addressed storage for artifact chunks with cryptographic
verification, deduplication, path-traversal prevention, and storage quota enforcement.
"""

from dataclasses import dataclass
import hashlib
import os
import re
from typing import Dict, List, Optional, Any


class ChunkStoreError(Exception):
    """Base exception for chunk store errors."""
    pass


class StorageQuotaExceededError(ChunkStoreError):
    """Raised when storing a chunk would exceed configured storage quota."""
    pass


class ChunkIntegrityError(ChunkStoreError):
    """Raised when chunk data does not match declared cryptographic digest."""
    pass


HEX_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class ArtifactChunkStore:
    """
    Content-Addressed Storage (CAS) for deduplicated binary chunks.
    Storage hierarchy: `<storage_root>/sha256/<prefix>/<digest>.chunk`
    """

    def __init__(
        self,
        storage_root: str = "memory/artifact_chunks",
        storage_quota_bytes: int = 10 * 1024 * 1024 * 1024,  # 10GB default
    ) -> None:
        self.storage_root = os.path.abspath(storage_root)
        self.storage_quota_bytes = storage_quota_bytes
        self.base_dir = os.path.join(self.storage_root, "sha256")
        os.makedirs(self.base_dir, exist_ok=True)

    def _validate_digest(self, digest: str) -> str:
        """Validate digest format to prevent directory traversal or malformed keys."""
        cleaned = digest.strip().lower()
        if not HEX_PATTERN.match(cleaned):
            raise ValueError(f"Invalid SHA-256 digest format: {digest}")
        return cleaned

    def _chunk_path(self, digest: str) -> str:
        cleaned = self._validate_digest(digest)
        prefix = cleaned[:2]
        return os.path.join(self.base_dir, prefix, f"{cleaned}.chunk")

    def has_chunk(self, digest: str) -> bool:
        """Check if chunk exists in CAS."""
        try:
            path = self._chunk_path(digest)
            return os.path.isfile(path)
        except ValueError:
            return False

    def put_chunk(self, digest: str, data: bytes) -> bool:
        """
        Verify cryptographic integrity of data against digest, check quotas,
        and store immutably. Deduplicates existing chunks.
        """
        cleaned = self._validate_digest(digest)
        actual_sha256 = hashlib.sha256(data).hexdigest().lower()
        if actual_sha256 != cleaned:
            raise ChunkIntegrityError(f"Chunk digest mismatch: declared {cleaned} != actual {actual_sha256}")

        path = self._chunk_path(cleaned)
        if os.path.isfile(path):
            # Already deduplicated and verified
            return True

        # Check quota
        current_usage = self.get_total_bytes()
        if current_usage + len(data) > self.storage_quota_bytes:
            raise StorageQuotaExceededError(
                f"Chunk store quota exceeded ({current_usage + len(data)} > {self.storage_quota_bytes} bytes)"
            )

        os.makedirs(os.path.dirname(path), exist_ok=True)
        temp_path = f"{path}.tmp.{os.getpid()}"
        try:
            with open(temp_path, "wb") as f:
                f.write(data)
            os.rename(temp_path, path)
            return True
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def get_chunk(self, digest: str) -> Optional[bytes]:
        """Retrieve chunk binary payload, verifying its integrity on read."""
        path = self._chunk_path(digest)
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as f:
            data = f.read()

        # Integrity verification
        actual_sha256 = hashlib.sha256(data).hexdigest().lower()
        cleaned = self._validate_digest(digest)
        if actual_sha256 != cleaned:
            raise ChunkIntegrityError(f"Corrupted chunk detected at {path}: expected {cleaned}, got {actual_sha256}")
        return data

    def delete_chunk(self, digest: str) -> bool:
        """Delete chunk from CAS."""
        try:
            path = self._chunk_path(digest)
            if os.path.isfile(path):
                os.remove(path)
                return True
            return False
        except (ValueError, OSError):
            return False

    def list_chunks(self) -> List[str]:
        """List all valid chunk digests stored in CAS."""
        digests: List[str] = []
        if not os.path.isdir(self.base_dir):
            return digests

        for prefix in os.listdir(self.base_dir):
            prefix_dir = os.path.join(self.base_dir, prefix)
            if os.path.isdir(prefix_dir):
                for filename in os.listdir(prefix_dir):
                    if filename.endswith(".chunk"):
                        digest = filename[:-6]
                        if HEX_PATTERN.match(digest):
                            digests.append(digest)
        return digests

    def get_total_bytes(self) -> int:
        """Calculate total storage consumed by chunks."""
        total = 0
        if not os.path.isdir(self.base_dir):
            return 0
        for root, _, files in os.walk(self.base_dir):
            for f in files:
                if f.endswith(".chunk"):
                    total += os.path.getsize(os.path.join(root, f))
        return total

    def get_stats(self) -> Dict[str, Any]:
        """Return storage metrics and quota consumption."""
        chunks = self.list_chunks()
        total_bytes = self.get_total_bytes()
        pct = (total_bytes / self.storage_quota_bytes * 100.0) if self.storage_quota_bytes > 0 else 0.0
        return {
            "chunk_count": len(chunks),
            "total_bytes": total_bytes,
            "storage_quota_bytes": self.storage_quota_bytes,
            "usage_percentage": round(pct, 2),
            "storage_root": self.storage_root,
        }
