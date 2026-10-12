"""
distributed_checkpoint.py - Persistent Cluster Checkpointing & Disaster Recovery for AutoDev (v2.9)

Saves atomic snapshots of cluster state, node registry, distributed queue, replicated memory,
active locks, and scheduler allocations with SHA-256 integrity validation and automatic crash recovery.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import ClusterState, DistributedClusterMemory
from core.cluster.distributed_lock_manager import DistributedLockManager
from core.cluster.distributed_queue import DistributedQueue
from core.cluster.node_registry import NodeRegistry

logger = logging.getLogger("AutoDev.Cluster.Checkpoint")


@dataclass
class CheckpointMetadata:
    checkpoint_id: str
    created_at: float
    epoch: int
    leader_id: str
    sha256: str
    file_path: str
    size_bytes: int
    node_count: int
    task_count: int


class DistributedCheckpointManager:
    """
    Manages persistent atomic checkpointing, verification, and recovery for the AutoDev Cluster.
    """

    def __init__(
        self,
        storage_dir: Optional[Path | str] = None,
        config: Optional[ClusterConfig] = None,
    ) -> None:
        self.config = config or ClusterConfig()
        self.storage_dir = Path(storage_dir or self.config.checkpoint_storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def create_checkpoint(
        self,
        epoch: int,
        leader_id: str,
        registry: NodeRegistry,
        queue: DistributedQueue,
        memory: DistributedClusterMemory,
        lock_manager: DistributedLockManager,
        scheduler_stats: Optional[Dict[str, Any]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Atomically snapshots the entire cluster state to disk with SHA-256 integrity verification.
        Returns the unique checkpoint ID.
        """
        with self._lock:
            now = time.time()
            chk_id = f"chk_{int(now * 1000)}_{epoch}"
            filename = f"{chk_id}.json"
            tmp_path = self.storage_dir / f"{filename}.tmp"
            final_path = self.storage_dir / filename

            payload = {
                "checkpoint_id": chk_id,
                "timestamp": now,
                "epoch": epoch,
                "leader_id": leader_id,
                "registry": registry.export_state(),
                "queue": queue.export_state(),
                "memory": memory.dump_snapshot(),
                "locks": lock_manager.export_state(),
                "scheduler": scheduler_stats or {},
                "custom_metadata": custom_metadata or {},
            }

            raw_bytes = json.dumps(payload, indent=2).encode("utf-8")
            digest = hashlib.sha256(raw_bytes).hexdigest()

            # Envelope containing payload and checksum
            envelope = {
                "checkpoint_id": chk_id,
                "epoch": epoch,
                "leader_id": leader_id,
                "created_at": now,
                "sha256": digest,
                "payload": payload,
            }

            envelope_bytes = json.dumps(envelope, indent=2).encode("utf-8")

            # Atomic write to .tmp then rename
            with open(tmp_path, "wb") as f:
                f.write(envelope_bytes)
                f.flush()
                os.fsync(f.fileno())

            if final_path.exists():
                final_path.unlink()
            tmp_path.rename(final_path)

            logger.info("Created atomic cluster checkpoint %s (epoch=%d, sha=%s[:8], size=%d bytes)", chk_id, epoch, digest, len(envelope_bytes))

            # Prune old checkpoints
            self.prune_old_checkpoints(self.config.max_checkpoints_retained)

            return chk_id

    def load_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Finds and loads the latest valid verified checkpoint.
        """
        with self._lock:
            checkpoints = self.list_checkpoints()
            if not checkpoints:
                return None

            latest = checkpoints[0]
            return self.load_checkpoint(latest.checkpoint_id)

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Loads and validates SHA-256 checksum for a specific checkpoint.
        """
        with self._lock:
            chk_path = self.storage_dir / f"{checkpoint_id}.json"
            if not chk_path.exists():
                logger.error("Checkpoint file %s does not exist", chk_path)
                return None

            try:
                with open(chk_path, "rb") as f:
                    envelope_bytes = f.read()

                envelope = json.loads(envelope_bytes.decode("utf-8"))
                payload = envelope.get("payload", {})
                expected_sha = envelope.get("sha256", "")

                # Verify payload digest
                payload_raw = json.dumps(payload, indent=2).encode("utf-8")
                computed_sha = hashlib.sha256(payload_raw).hexdigest()

                if computed_sha != expected_sha:
                    logger.error("Checkpoint %s checksum verification failed! Expected: %s, Computed: %s", checkpoint_id, expected_sha, computed_sha)
                    return None

                logger.info("Successfully loaded and verified checkpoint %s (epoch=%d)", checkpoint_id, envelope.get("epoch", 1))
                return payload

            except Exception as e:
                logger.error("Failed to load checkpoint %s: %s", checkpoint_id, e)
                return None

    def restore_into_subsystems(
        self,
        checkpoint_data: Dict[str, Any],
        registry: NodeRegistry,
        queue: DistributedQueue,
        memory: DistributedClusterMemory,
        lock_manager: DistributedLockManager,
    ) -> bool:
        """
        Restores cluster subsystems from deserialized checkpoint payload.
        """
        with self._lock:
            try:
                if "registry" in checkpoint_data:
                    registry.import_state(checkpoint_data["registry"])
                if "queue" in checkpoint_data:
                    queue.import_state(checkpoint_data["queue"])
                if "memory" in checkpoint_data:
                    memory.load_snapshot(checkpoint_data["memory"])
                if "locks" in checkpoint_data:
                    lock_manager.import_state(checkpoint_data["locks"])
                logger.info("Restored cluster state from checkpoint %s", checkpoint_data.get("checkpoint_id"))
                return True
            except Exception as e:
                logger.error("Failed to restore state into cluster subsystems: %s", e)
                return False

    def list_checkpoints(self) -> List[CheckpointMetadata]:
        """
        Returns list of all available checkpoints sorted descending by creation timestamp.
        """
        with self._lock:
            records: List[CheckpointMetadata] = []
            for file_path in self.storage_dir.glob("chk_*.json"):
                try:
                    with open(file_path, "rb") as f:
                        envelope = json.load(f)
                    payload = envelope.get("payload", {})
                    reg = payload.get("registry", {})
                    q = payload.get("queue", {})
                    node_cnt = len(reg.get("nodes", {}))
                    task_cnt = len(q.get("inflight", {})) + len(q.get("ready", []))

                    records.append(CheckpointMetadata(
                        checkpoint_id=envelope["checkpoint_id"],
                        created_at=envelope.get("created_at", 0.0),
                        epoch=envelope.get("epoch", 1),
                        leader_id=envelope.get("leader_id", "unknown"),
                        sha256=envelope.get("sha256", ""),
                        file_path=str(file_path),
                        size_bytes=file_path.stat().st_size,
                        node_count=node_cnt,
                        task_count=task_cnt,
                    ))
                except Exception:
                    continue

            records.sort(key=lambda r: r.created_at, reverse=True)
            return records

    def prune_old_checkpoints(self, max_retained: int) -> int:
        """
        Prunes old checkpoint files exceeding max_retained limit.
        """
        with self._lock:
            checkpoints = self.list_checkpoints()
            if len(checkpoints) <= max_retained:
                return 0

            pruned_count = 0
            to_remove = checkpoints[max_retained:]
            for r in to_remove:
                p = Path(r.file_path)
                if p.exists():
                    try:
                        p.unlink()
                        pruned_count += 1
                        logger.debug("Pruned old checkpoint file: %s", p.name)
                    except Exception as e:
                        logger.error("Failed to prune checkpoint file %s: %s", p, e)
            return pruned_count
