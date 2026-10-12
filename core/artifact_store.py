"""
artifact_store.py - Isolated Staging Store & Safe Archive Extraction for AutoDev (v2.3)

Provides isolated transactional staging for incoming worker artifacts under memory/artifacts/<tx_id>/,
atomic file writes, path sanitization, quota management, and hardened archive handling.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
import shutil
import tarfile
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import zipfile

from core.artifact_manifest import validate_safe_relative_path
from core.artifact_models import ArtifactMetadata, ArtifactStatus, ArtifactType

logger = logging.getLogger("AutoDev.ArtifactStore")


class ArtifactStoreError(Exception):
    """Raised when artifact staging or retrieval fails."""
    pass


MAX_ARCHIVE_ENTRIES = 1000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 100 * 1024 * 1024  # 100 MB


class ArtifactStore:
    """
    Manages isolated filesystem staging for artifacts pending verification and integration.
    Default storage root: memory/artifacts/<tx_id>/<artifact_id>/
    """

    def __init__(self, base_staging_dir: Optional[Union[str, Path]] = None) -> None:
        self.base_staging_dir = Path(base_staging_dir or "memory/artifacts").resolve()
        self.base_staging_dir.mkdir(parents=True, exist_ok=True)

    def get_transaction_staging_dir(self, transaction_id: str) -> Path:
        """Returns the isolated directory for a specific transaction."""
        safe_tx = "".join(c for c in transaction_id if c.isalnum() or c in ("-", "_"))
        if not safe_tx:
            raise ArtifactStoreError("Invalid transaction_id for staging directory")
        tx_dir = self.base_staging_dir / safe_tx
        tx_dir.mkdir(parents=True, exist_ok=True)
        return tx_dir

    def get_artifact_staging_path(self, transaction_id: str, artifact_id: str) -> Path:
        """Returns the target staging path for an individual artifact payload."""
        tx_dir = self.get_transaction_staging_dir(transaction_id)
        safe_art = "".join(c for c in artifact_id if c.isalnum() or c in ("-", "_"))
        if not safe_art:
            raise ArtifactStoreError("Invalid artifact_id for staging path")
        art_dir = tx_dir / safe_art
        art_dir.mkdir(parents=True, exist_ok=True)
        return art_dir / "payload.bin"

    def stage_artifact_bytes(
        self,
        transaction_id: str,
        artifact_id: str,
        content_bytes: bytes,
    ) -> Path:
        """
        Atomically writes raw artifact bytes to the isolated staging area.
        """
        target_path = self.get_artifact_staging_path(transaction_id, artifact_id)
        tmp_path = target_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "wb") as f:
                f.write(content_bytes)
            # Atomic rename / replace
            if target_path.exists():
                target_path.unlink()
            tmp_path.rename(target_path)
            logger.debug("Staged %d bytes for artifact %s in tx %s", len(content_bytes), artifact_id, transaction_id)
            return target_path
        except Exception as e:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            raise ArtifactStoreError(f"Failed to stage artifact {artifact_id}: {e}") from e

    def read_staged_artifact_bytes(self, transaction_id: str, artifact_id: str) -> bytes:
        """Reads stored bytes for a staged artifact."""
        target_path = self.get_artifact_staging_path(transaction_id, artifact_id)
        if not target_path.exists():
            raise ArtifactStoreError(f"Staged artifact payload not found at {target_path}")
        with open(target_path, "rb") as f:
            return f.read()

    def cleanup_transaction(self, transaction_id: str) -> None:
        """Removes the entire staging directory for a completed or aborted transaction."""
        try:
            tx_dir = self.get_transaction_staging_dir(transaction_id)
            if tx_dir.exists():
                shutil.rmtree(tx_dir, ignore_errors=True)
                logger.debug("Cleaned up staging directory for transaction %s", transaction_id)
        except Exception as e:
            logger.warning("Failed to clean up staging directory for tx %s: %s", transaction_id, e)

    def extract_safe_archive(
        self,
        archive_bytes: bytes,
        target_dir: Path,
        is_zip: bool = True,
    ) -> List[Path]:
        """
        Safely extracts an in-memory zip or tar archive into target_dir with
        Zip Slip prevention, decompression bomb limits, and symlink protection.
        """
        extracted_paths: List[Path] = []
        target_dir = target_dir.resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        if is_zip:
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
                infolist = zf.infolist()
                if len(infolist) > MAX_ARCHIVE_ENTRIES:
                    raise ArtifactStoreError(f"Archive entry count exceeds limit ({len(infolist)} > {MAX_ARCHIVE_ENTRIES})")

                total_uncompressed = sum(info.file_size for info in infolist)
                if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise ArtifactStoreError(
                        f"Archive uncompressed size exceeds limit ({total_uncompressed} > {MAX_ARCHIVE_UNCOMPRESSED_BYTES})"
                    )

                for member in infolist:
                    # Traversal check
                    safe_rel = validate_safe_relative_path(member.filename.replace("\\", "/"))
                    dest_path = (target_dir / safe_rel).resolve()
                    if not str(dest_path).startswith(str(target_dir)):
                        raise ArtifactStoreError(f"Zip Slip path traversal detected: {member.filename}")

                    if member.is_dir():
                        dest_path.mkdir(parents=True, exist_ok=True)
                    else:
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(dest_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        extracted_paths.append(dest_path)
        else:
            # Safe Tar extraction
            with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:*") as tf:
                members = tf.getmembers()
                if len(members) > MAX_ARCHIVE_ENTRIES:
                    raise ArtifactStoreError(f"Tar archive entry count exceeds limit ({len(members)} > {MAX_ARCHIVE_ENTRIES})")

                total_uncompressed = sum(m.size for m in members)
                if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise ArtifactStoreError(
                        f"Tar uncompressed size exceeds limit ({total_uncompressed} > {MAX_ARCHIVE_UNCOMPRESSED_BYTES})"
                    )

                for member in members:
                    if member.issym() or member.islnk():
                        raise ArtifactStoreError(f"Symlink or hardlink in archive rejected: {member.name}")
                    safe_rel = validate_safe_relative_path(member.name.replace("\\", "/"))
                    dest_path = (target_dir / safe_rel).resolve()
                    if not str(dest_path).startswith(str(target_dir)):
                        raise ArtifactStoreError(f"Tar path traversal detected: {member.name}")

                    if member.isdir():
                        dest_path.mkdir(parents=True, exist_ok=True)
                    else:
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        f = tf.extractfile(member)
                        if f is not None:
                            with open(dest_path, "wb") as dst:
                                shutil.copyfileobj(f, dst)
                            extracted_paths.append(dest_path)

        return extracted_paths
