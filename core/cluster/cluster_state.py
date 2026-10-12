"""
cluster_state.py - Cluster Topology Models, Distributed State & Memory for AutoDev (v2.9)

Provides data contracts, enumerations, state containers, and replicated distributed memory
for multi-node cluster operation, node tracking, task execution states, and consensus data.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("AutoDev.Cluster.State")


class NodeRole(str, Enum):
    MASTER = "MASTER"
    WORKER = "WORKER"
    OBSERVER = "OBSERVER"
    BACKUP_MASTER = "BACKUP_MASTER"


class NodeStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    RECOVERING = "RECOVERING"
    DEREGISTERED = "DEREGISTERED"


class TaskExecutionStatus(str, Enum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"
    DEAD_LETTER = "DEAD_LETTER"


class JobStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class LockType(str, Enum):
    EXCLUSIVE = "EXCLUSIVE"
    SHARED = "SHARED"
    FILE = "FILE"
    TASK = "TASK"
    MEMORY = "MEMORY"
    ARTIFACT = "ARTIFACT"


class SyncStatus(str, Enum):
    SYNCED = "SYNCED"
    OUT_OF_SYNC = "OUT_OF_SYNC"
    SYNCING = "SYNCING"
    CONFLICT = "CONFLICT"


@dataclass
class NodeInfo:
    """
    Metadata and telemetry representing an active or registered cluster node.
    """
    node_id: str
    hostname: str = "localhost"
    ip: str = "127.0.0.1"
    port: int = 9500
    role: NodeRole = NodeRole.WORKER
    status: NodeStatus = NodeStatus.HEALTHY
    capabilities: List[str] = field(default_factory=lambda: ["general"])
    cpu_utilization: float = 0.0      # 0.0 - 100.0%
    memory_utilization: float = 0.0   # 0.0 - 100.0%
    active_tasks: int = 0
    max_tasks: int = 4
    uptime: float = 0.0
    health_score: float = 100.0       # 0.0 - 100.0
    latency_ms: float = 0.5
    last_heartbeat: float = field(default_factory=time.time)
    registered_at: float = field(default_factory=time.time)
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["role"] = self.role.value if isinstance(self.role, NodeRole) else str(self.role)
        d["status"] = self.status.value if isinstance(self.status, NodeStatus) else str(self.status)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NodeInfo:
        d = dict(data)
        if "role" in d and isinstance(d["role"], str):
            try:
                d["role"] = NodeRole(d["role"])
            except ValueError:
                d["role"] = NodeRole.WORKER
        if "status" in d and isinstance(d["status"], str):
            try:
                d["status"] = NodeStatus(d["status"])
            except ValueError:
                d["status"] = NodeStatus.HEALTHY
        return cls(**d)

    @property
    def is_available(self) -> bool:
        """Returns True if worker can accept new tasks."""
        return (
            self.role == NodeRole.WORKER
            and self.status in (NodeStatus.HEALTHY, NodeStatus.DEGRADED)
            and self.active_tasks < self.max_tasks
        )

    @property
    def utilization_ratio(self) -> float:
        """Normalized workload ratio [0.0 - 1.0]."""
        if self.max_tasks <= 0:
            return 1.0
        return min(1.0, self.active_tasks / self.max_tasks)


@dataclass
class TaskSpec:
    """
    Specification and execution state of a distributed task.
    """
    task_id: str
    job_id: str = "default_job"
    title: str = ""
    description: str = ""
    required_capabilities: List[str] = field(default_factory=list)
    priority: int = 50  # Lower number = higher priority (0-100)
    dependencies: List[str] = field(default_factory=list)
    estimated_duration: float = 1.0
    payload: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    assigned_worker_id: Optional[str] = None
    status: TaskExecutionStatus = TaskExecutionStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    artifacts: List[str] = field(default_factory=list)
    locality_hints: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    visibility_deadline: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, TaskExecutionStatus) else str(self.status)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskSpec:
        d = dict(data)
        if "status" in d and isinstance(d["status"], str):
            try:
                d["status"] = TaskExecutionStatus(d["status"])
            except ValueError:
                d["status"] = TaskExecutionStatus.PENDING
        return cls(**d)


@dataclass
class ClusterJob:
    """
    Represents an end-to-end distributed job composed of multiple dependent or parallel tasks.
    """
    job_id: str
    title: str
    description: str = ""
    status: JobStatus = JobStatus.SUBMITTED
    tasks: Dict[str, TaskSpec] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "job_id": self.job_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, JobStatus) else str(self.status),
            "tasks": {k: t.to_dict() for k, t in self.tasks.items()},
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "metadata": self.metadata,
            "error_message": self.error_message,
        }
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ClusterJob:
        d = dict(data)
        if "status" in d and isinstance(d["status"], str):
            try:
                d["status"] = JobStatus(d["status"])
            except ValueError:
                d["status"] = JobStatus.SUBMITTED
        if "tasks" in d and isinstance(d["tasks"], dict):
            d["tasks"] = {k: TaskSpec.from_dict(v) for k, v in d["tasks"].items()}
        return cls(**d)

    @property
    def is_finished(self) -> bool:
        return self.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)

    @property
    def progress_percentage(self) -> float:
        if not self.tasks:
            return 100.0 if self.is_finished else 0.0
        completed = sum(1 for t in self.tasks.values() if t.status == TaskExecutionStatus.COMPLETED)
        return (completed / len(self.tasks)) * 100.0


@dataclass
class LockLease:
    """
    Cluster distributed lock lease descriptor.
    """
    resource_id: str
    lock_type: LockType
    owner_id: str
    acquired_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    renewed_count: int = 0
    waiters: List[str] = field(default_factory=list)

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return now >= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["lock_type"] = self.lock_type.value if isinstance(self.lock_type, LockType) else str(self.lock_type)
        return d


@dataclass
class MemoryEntry:
    """
    Versioned distributed memory record with vector clock and metadata.
    """
    key: str
    value: Any
    version: int = 1
    vector_clock: Dict[str, int] = field(default_factory=dict)
    updated_by: str = "cluster"
    updated_at: float = field(default_factory=time.time)
    deleted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryEntry:
        return cls(**data)


class DistributedClusterMemory:
    """
    Replicated in-memory key-value store for distributed cluster sharing.
    Supports atomic updates, version vectors, transactional batch mutations,
    and conflict resolution strategies.
    """

    def __init__(self, node_id: str = "master-node-01") -> None:
        self.node_id = node_id
        self._store: Dict[str, MemoryEntry] = {}
        self._lock = threading.RLock()
        self._change_log: List[Dict[str, Any]] = []

    def set(self, key: str, value: Any, source_node: Optional[str] = None) -> MemoryEntry:
        """Sets or updates a key in cluster memory with monotonic version increments."""
        with self._lock:
            now = time.time()
            node = source_node or self.node_id
            existing = self._store.get(key)
            if existing:
                new_version = existing.version + 1
                new_clock = dict(existing.vector_clock)
                new_clock[node] = new_clock.get(node, 0) + 1
            else:
                new_version = 1
                new_clock = {node: 1}

            entry = MemoryEntry(
                key=key,
                value=copy.deepcopy(value),
                version=new_version,
                vector_clock=new_clock,
                updated_by=node,
                updated_at=now,
                deleted=False,
            )
            self._store[key] = entry
            self._change_log.append({
                "op": "set",
                "key": key,
                "version": new_version,
                "node": node,
                "timestamp": now,
            })
            return entry

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves value for key if not deleted."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None or entry.deleted:
                return default
            return copy.deepcopy(entry.value)

    def get_entry(self, key: str) -> Optional[MemoryEntry]:
        """Retrieves full MemoryEntry descriptor."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None or entry.deleted:
                return None
            return copy.deepcopy(entry)

    def delete(self, key: str, source_node: Optional[str] = None) -> bool:
        """Marks key as deleted (tombstone) with version increment."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None or entry.deleted:
                return False
            now = time.time()
            node = source_node or self.node_id
            entry.deleted = True
            entry.version += 1
            entry.vector_clock[node] = entry.vector_clock.get(node, 0) + 1
            entry.updated_at = now
            entry.updated_by = node
            self._change_log.append({
                "op": "delete",
                "key": key,
                "version": entry.version,
                "node": node,
                "timestamp": now,
            })
            return True

    def contains(self, key: str) -> bool:
        """Checks whether an active non-deleted key exists."""
        with self._lock:
            entry = self._store.get(key)
            return entry is not None and not entry.deleted

    def keys(self) -> List[str]:
        """Returns all non-deleted keys."""
        with self._lock:
            return [k for k, v in self._store.items() if not v.deleted]

    def dump_snapshot(self) -> Dict[str, Any]:
        """Returns serializable snapshot of all memory entries."""
        with self._lock:
            return {k: v.to_dict() for k, v in self._store.items()}

    def load_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Loads snapshot into cluster memory."""
        with self._lock:
            self._store.clear()
            for k, v in snapshot.items():
                self._store[k] = MemoryEntry.from_dict(v)

    def merge_replication(self, remote_entries: Dict[str, Any]) -> int:
        """
        Merges remote memory entries using Last-Write-Wins (LWW) and version comparison.
        Returns the number of updated keys.
        """
        with self._lock:
            updated = 0
            for k, val in remote_entries.items():
                remote_entry = MemoryEntry.from_dict(val) if isinstance(val, dict) else val
                local_entry = self._store.get(k)
                if local_entry is None:
                    self._store[k] = copy.deepcopy(remote_entry)
                    updated += 1
                else:
                    # Resolve conflict: highest version, or latest timestamp if tied
                    if remote_entry.version > local_entry.version or (
                        remote_entry.version == local_entry.version and remote_entry.updated_at > local_entry.updated_at
                    ):
                        self._store[k] = copy.deepcopy(remote_entry)
                        updated += 1
            return updated


@dataclass
class ClusterState:
    """
    Comprehensive snapshot container representing the complete cluster state at an instant.
    """
    cluster_name: str = "autodev-cluster"
    epoch: int = 1
    leader_id: str = "master-node-01"
    nodes: Dict[str, NodeInfo] = field(default_factory=dict)
    jobs: Dict[str, ClusterJob] = field(default_factory=dict)
    active_tasks: Dict[str, TaskSpec] = field(default_factory=dict)
    locks: Dict[str, LockLease] = field(default_factory=dict)
    memory_snapshot: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_name": self.cluster_name,
            "epoch": self.epoch,
            "leader_id": self.leader_id,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "jobs": {k: v.to_dict() for k, v in self.jobs.items()},
            "active_tasks": {k: v.to_dict() for k, v in self.active_tasks.items()},
            "locks": {k: v.to_dict() for k, v in self.locks.items()},
            "memory_snapshot": self.memory_snapshot,
            "timestamp": self.timestamp,
        }
