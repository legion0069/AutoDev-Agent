"""
AutoDev Artifact Garbage Collector (Phase 4 - Differential Artifact Synchronization)
Scans content-addressed chunk storage, identifies orphan chunks not referenced by any
active artifact manifest or transaction, and safely reclaims unreferenced disk space.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from typing import Dict, List, Optional, Set, Any
import logging

from core.artifact_chunk_store import ArtifactChunkStore
from core.artifact_sync_protocol import ChunkManifest

logger = logging.getLogger(__name__)


@dataclass
class GCReport:
    """Report generated following a garbage collection cycle."""
    scanned_chunks: int
    referenced_chunks: int
    unreferenced_chunks: int
    reclaimed_bytes: int
    dry_run: bool
    deleted_digests: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ArtifactGarbageCollector:
    """
    Safely reclaims orphaned chunks from CAS.
    Preserves all chunks referenced by active manifests or transactions.
    """

    def __init__(self, chunk_store: ArtifactChunkStore) -> None:
        self.chunk_store = chunk_store

    def collect_orphans(
        self,
        active_manifests: List[ChunkManifest],
        protected_digests: Optional[Set[str]] = None,
        dry_run: bool = False,
    ) -> GCReport:
        """
        Scan chunk store, compute active references, and prune unreferenced chunks.
        """
        # Build set of referenced chunk digests
        referenced: Set[str] = set()
        for manifest in active_manifests:
            for chunk in manifest.chunks:
                referenced.add(chunk.digest.lower())

        if protected_digests:
            for d in protected_digests:
                referenced.add(d.lower())

        all_stored = self.chunk_store.list_chunks()
        unreferenced: List[str] = []
        reclaimed_bytes = 0
        deleted_digests: List[str] = []

        for digest in all_stored:
            if digest.lower() not in referenced:
                unreferenced.append(digest)
                # Query chunk size before deletion
                chunk_data = self.chunk_store.get_chunk(digest)
                chunk_size = len(chunk_data) if chunk_data else 0
                reclaimed_bytes += chunk_size

                if not dry_run:
                    success = self.chunk_store.delete_chunk(digest)
                    if success:
                        deleted_digests.append(digest)
                else:
                    deleted_digests.append(digest)

        return GCReport(
            scanned_chunks=len(all_stored),
            referenced_chunks=len(all_stored) - len(unreferenced),
            unreferenced_chunks=len(unreferenced),
            reclaimed_bytes=reclaimed_bytes,
            dry_run=dry_run,
            deleted_digests=deleted_digests,
        )
