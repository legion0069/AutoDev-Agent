"""
artifact_sync.py - Distributed Artifact Synchronization & Incremental CAS for AutoDev Cluster (v2.9)

Coordinates cluster-wide synchronization of generated files, source diffs, execution reports,
documentation, memory snapshots, and git metadata with SHA-256 checksums, delta transfers,
and automated conflict resolution.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import SyncStatus

logger = logging.getLogger("AutoDev.Cluster.ArtifactSync")


@dataclass
class ArtifactManifestEntry:
    """
    Metadata record for an artifact in the distributed cluster registry.
    """
    artifact_id: str
    relative_path: str
    size_bytes: int
    sha256: str
    version: int = 1
    content_type: str = "text/plain"
    author_node_id: str = "cluster"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    sync_status: SyncStatus = SyncStatus.SYNCED

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["sync_status"] = self.sync_status.value if isinstance(self.sync_status, SyncStatus) else str(self.sync_status)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArtifactManifestEntry:
        d = dict(data)
        if "sync_status" in d and isinstance(d["sync_status"], str):
            try:
                d["sync_status"] = SyncStatus(d["sync_status"])
            except ValueError:
                d["sync_status"] = SyncStatus.SYNCED
        return cls(**d)


@dataclass
class SyncReport:
    """
    Summary result of an artifact synchronization operation between nodes.
    """
    source_node_id: str
    target_node_id: str
    synced_count: int = 0
    bytes_transferred: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    duration_ms: float = 0.0
    synced_artifacts: List[str] = field(default_factory=list)
    conflict_artifacts: List[str] = field(default_factory=list)


class ArtifactSyncManager:
    """
    Distributed Content-Addressable & Incremental Artifact Synchronization Engine.
    """

    def __init__(self, node_id: str, storage_root: Optional[Path | str] = None, config: Optional[ClusterConfig] = None) -> None:
        self.node_id = node_id
        self.config = config or ClusterConfig()
        self.storage_root = Path(storage_root or (Path(self.config.storage_dir) / "artifacts" / node_id)).resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)

        self._manifest: Dict[str, ArtifactManifestEntry] = {}
        self._in_memory_blobs: Dict[str, bytes] = {}
        self._lock = threading.RLock()

    @staticmethod
    def compute_sha256(content: str | bytes) -> str:
        """Computes SHA-256 hexadecimal hash string."""
        data = content.encode("utf-8") if isinstance(content, str) else content
        return hashlib.sha256(data).hexdigest()

    def store_artifact(
        self,
        artifact_id: str,
        relative_path: str,
        content: str | bytes,
        content_type: str = "text/plain",
        metadata: Optional[Dict[str, Any]] = None,
        persist_to_disk: bool = True,
    ) -> ArtifactManifestEntry:
        """
        Stores artifact blob, computes digest, updates version and manifest entry.
        """
        data = content.encode("utf-8") if isinstance(content, str) else content
        digest = self.compute_sha256(data)
        now = time.time()

        with self._lock:
            existing = self._manifest.get(artifact_id)
            version = (existing.version + 1) if (existing and existing.sha256 != digest) else (existing.version if existing else 1)

            entry = ArtifactManifestEntry(
                artifact_id=artifact_id,
                relative_path=relative_path,
                size_bytes=len(data),
                sha256=digest,
                version=version,
                content_type=content_type,
                author_node_id=self.node_id,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                metadata=metadata or {},
                sync_status=SyncStatus.SYNCED,
            )

            self._manifest[artifact_id] = entry
            self._in_memory_blobs[artifact_id] = data

            if persist_to_disk:
                target_path = self.storage_root / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "wb") as f:
                    f.write(data)

            logger.debug("Stored artifact %s (%s, %d bytes, sha=%s[:8])", artifact_id, relative_path, len(data), digest)
            return entry

    def get_artifact_content(self, artifact_id: str) -> Optional[bytes]:
        """
        Retrieves binary artifact payload from cache or disk.
        """
        with self._lock:
            if artifact_id in self._in_memory_blobs:
                return self._in_memory_blobs[artifact_id]

            entry = self._manifest.get(artifact_id)
            if not entry:
                return None

            disk_path = self.storage_root / entry.relative_path
            if disk_path.exists():
                try:
                    with open(disk_path, "rb") as f:
                        data = f.read()
                    self._in_memory_blobs[artifact_id] = data
                    return data
                except Exception as e:
                    logger.error("Failed to read artifact %s from disk: %s", artifact_id, e)
            return None

    def get_artifact_text(self, artifact_id: str) -> Optional[str]:
        """Retrieves artifact content as UTF-8 string."""
        raw = self.get_artifact_content(artifact_id)
        if raw is None:
            return None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="replace")

    def get_manifest(self) -> Dict[str, ArtifactManifestEntry]:
        """Returns snapshot of current artifact manifest."""
        with self._lock:
            return copy.deepcopy(self._manifest)

    def compute_sync_delta(self, remote_manifest: Dict[str, Dict[str, Any]]) -> List[str]:
        """
        Calculates list of artifact IDs that need to be fetched from remote
        because they are missing locally or have different SHA-256 / higher versions.
        """
        with self._lock:
            delta: List[str] = []
            for art_id, r_dict in remote_manifest.items():
                remote_sha = r_dict.get("sha256")
                remote_version = r_dict.get("version", 1)
                local = self._manifest.get(art_id)

                if local is None or local.sha256 != remote_sha or remote_version > local.version:
                    delta.append(art_id)
            return delta

    def sync_from_remote(
        self,
        remote_node_id: str,
        remote_manifest: Dict[str, Dict[str, Any]],
        fetch_blob_callback: Any,
        conflict_strategy: str = "last_write_wins",
    ) -> SyncReport:
        """
        Synchronizes artifacts from remote node by requesting blobs for delta items.
        """
        start_time = time.time()
        delta_ids = self.compute_sync_delta(remote_manifest)
        report = SyncReport(
            source_node_id=remote_node_id,
            target_node_id=self.node_id,
        )

        for art_id in delta_ids:
            r_entry_dict = remote_manifest[art_id]
            r_entry = ArtifactManifestEntry.from_dict(r_entry_dict)
            local_entry = self._manifest.get(art_id)

            # Conflict check: both modified differently
            if local_entry and local_entry.sha256 != r_entry.sha256:
                report.conflicts_detected += 1
                report.conflict_artifacts.append(art_id)
                # Conflict resolution
                if conflict_strategy == "last_write_wins":
                    if r_entry.updated_at < local_entry.updated_at:
                        logger.info("Conflict on %s: Local is newer. Retaining local.", art_id)
                        report.conflicts_resolved += 1
                        continue
                    logger.info("Conflict on %s: Remote is newer. Overwriting local.", art_id)
                elif conflict_strategy == "master_authoritative":
                    pass

            # Fetch blob
            blob = fetch_blob_callback(art_id)
            if blob is not None:
                self.store_artifact(
                    artifact_id=art_id,
                    relative_path=r_entry.relative_path,
                    content=blob,
                    content_type=r_entry.content_type,
                    metadata=r_entry.metadata,
                )
                report.synced_count += 1
                report.bytes_transferred += len(blob)
                report.synced_artifacts.append(art_id)
                if art_id in report.conflict_artifacts:
                    report.conflicts_resolved += 1

        report.duration_ms = (time.time() - start_time) * 1000.0
        logger.info(
            "Completed artifact sync from %s: %d synced, %d bytes, %d conflicts in %.2fms",
            remote_node_id, report.synced_count, report.bytes_transferred, report.conflicts_detected, report.duration_ms
        )
        return report

    def export_manifest_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {k: v.to_dict() for k, v in self._manifest.items()}

    def import_manifest_dict(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self._manifest.clear()
            for k, v in data.items():
                self._manifest[k] = ArtifactManifestEntry.from_dict(v)
