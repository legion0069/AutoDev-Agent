"""
cluster_config.py - Distributed Cluster Configuration for AutoDev (v2.9)

Defines production-grade configuration models, validation, serialization,
and default profiles for master, worker, and observer nodes in an AutoDev cluster.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ClusterConfig:
    """
    Master configuration schema for the AutoDev Distributed Cluster Engine (v2.9).
    Supports JSON serialization, disk persistence, and environment variable overrides.
    """
    cluster_name: str = "autodev-cluster-01"
    master_id: str = "master-node-01"
    master_host: str = "127.0.0.1"
    master_port: int = 9500
    backup_masters: List[str] = field(default_factory=lambda: ["master-node-02", "master-node-03"])
    
    # Timing and Health Probes (seconds)
    heartbeat_interval: float = 1.0
    worker_timeout: float = 3.0
    degraded_threshold_heartbeats: int = 2
    offline_threshold_heartbeats: int = 3
    health_score_threshold_degraded: float = 60.0
    
    # Scheduling & Distribution
    scheduler_strategy: str = "least_loaded"  # round_robin, least_loaded, capability_based, priority_aware, data_locality, dependency_aware
    max_workers: int = 64
    default_worker_capacity: int = 4
    enable_work_stealing: bool = True
    work_stealing_threshold_ratio: float = 2.0
    
    # Distributed Queue & Retries
    queue_visibility_timeout: float = 5.0
    max_task_retries: int = 3
    retry_backoff_factor: float = 1.5
    dead_letter_threshold: int = 3
    batch_dispatch_size: int = 10
    
    # Distributed Locking & Consensus
    lease_ttl_seconds: float = 10.0
    lock_renewal_interval: float = 3.0
    enable_deadlock_detection: bool = True
    deadlock_check_interval: float = 5.0
    leader_election_timeout: float = 2.0
    split_brain_quorum_size: int = 1
    
    # Artifact Sync & Memory
    artifact_sync_interval: float = 2.0
    enable_incremental_sync: bool = True
    chunk_size_bytes: int = 65536  # 64 KB chunks
    memory_replication_factor: int = 2
    memory_consistency_model: str = "eventual"  # eventual, strong, causal
    
    # Checkpointing & Persistence
    checkpoint_interval: float = 5.0
    checkpoint_storage_dir: str = "memory/cluster/checkpoints"
    max_checkpoints_retained: int = 10
    enable_auto_recovery: bool = True
    
    # Storage & Telemetry
    storage_dir: str = "memory/cluster"
    telemetry_window_seconds: int = 300
    log_level: str = "INFO"
    
    def __post_init__(self) -> None:
        self._apply_env_overrides()

    def _apply_env_overrides(self) -> None:
        """Applies environment variable overrides if present."""
        if "AUTODEV_CLUSTER_NAME" in os.environ:
            self.cluster_name = os.environ["AUTODEV_CLUSTER_NAME"]
        if "AUTODEV_MASTER_ID" in os.environ:
            self.master_id = os.environ["AUTODEV_MASTER_ID"]
        if "AUTODEV_MASTER_HOST" in os.environ:
            self.master_host = os.environ["AUTODEV_MASTER_HOST"]
        if "AUTODEV_MASTER_PORT" in os.environ:
            try:
                self.master_port = int(os.environ["AUTODEV_MASTER_PORT"])
            except ValueError:
                pass
        if "AUTODEV_HEARTBEAT_INTERVAL" in os.environ:
            try:
                self.heartbeat_interval = float(os.environ["AUTODEV_HEARTBEAT_INTERVAL"])
            except ValueError:
                pass
        if "AUTODEV_WORKER_TIMEOUT" in os.environ:
            try:
                self.worker_timeout = float(os.environ["AUTODEV_WORKER_TIMEOUT"])
            except ValueError:
                pass
        if "AUTODEV_SCHEDULER_STRATEGY" in os.environ:
            self.scheduler_strategy = os.environ["AUTODEV_SCHEDULER_STRATEGY"]
        if "AUTODEV_MAX_WORKERS" in os.environ:
            try:
                self.max_workers = int(os.environ["AUTODEV_MAX_WORKERS"])
            except ValueError:
                pass

    def to_dict(self) -> Dict[str, Any]:
        """Converts configuration to dictionary representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ClusterConfig:
        """Constructs ClusterConfig from dictionary, ignoring unexpected fields."""
        valid_keys = cls.__dataclass_fields__.keys()  # type: ignore
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    def save_json(self, file_path: str | Path) -> None:
        """Persists cluster configuration to a JSON file."""
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_json(cls, file_path: str | Path) -> ClusterConfig:
        """Loads cluster configuration from a JSON file, falling back to defaults if not found."""
        p = Path(file_path)
        if not p.exists():
            return cls()
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception:
            return cls()
