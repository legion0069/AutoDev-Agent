"""
worker_registry.py - Worker Registry & Health Management for AutoDev (v2.2)

Maintains active worker registrations, tracks heartbeat liveness, handles capability negotiation,
detects stale/dead workers, and provides thread-safe routing queries.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from core.worker_protocol import (
    PROTOCOL_VERSION,
    WorkerCapabilities,
    WorkerHeartbeat,
    WorkerRegistrationRequest,
    WorkerRegistrationResponse,
    WorkerStatus,
)

logger = logging.getLogger("AutoDev.WorkerRegistry")


class WorkerRegistryError(Exception):
    """Base exception for worker registry operations."""
    pass


class IncompatibleProtocolError(WorkerRegistryError):
    """Raised when a worker connects with an incompatible protocol version."""
    pass


class UnauthorizedWorkerError(WorkerRegistryError):
    """Raised when worker authentication fails."""
    pass


@dataclass
class WorkerInfo:
    """Full operational state and metadata for a registered worker."""
    worker_id: str
    worker_name: str
    protocol_version: str
    capabilities: WorkerCapabilities
    hostname: str = "localhost"
    status: WorkerStatus = WorkerStatus.IDLE
    current_load: int = 0
    active_task_ids: Set[str] = field(default_factory=set)
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_heartbeat_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_heartbeat_timestamp: float = field(default_factory=time.time)
    auth_token_hash: Optional[str] = None
    last_error: Optional[str] = None

    @property
    def is_available(self) -> bool:
        """Returns True if worker is in a ready state to accept tasks."""
        return (
            self.status in {WorkerStatus.IDLE, WorkerStatus.BUSY}
            and self.current_load < self.capabilities.max_concurrency
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "worker_name": self.worker_name,
            "protocol_version": self.protocol_version,
            "capabilities": self.capabilities.to_dict(),
            "hostname": self.hostname,
            "status": self.status.value,
            "current_load": self.current_load,
            "active_task_ids": list(self.active_task_ids),
            "registered_at": self.registered_at,
            "last_heartbeat_at": self.last_heartbeat_at,
            "is_available": self.is_available,
            "last_error": self.last_error,
        }


class WorkerRegistry:
    """
    Thread-safe registry of active, idle, and degraded distributed workers.
    """

    def __init__(
        self,
        heartbeat_timeout_seconds: float = 15.0,
        expected_auth_tokens: Optional[Set[str]] = None,
    ) -> None:
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self.expected_auth_tokens = expected_auth_tokens or set()
        self._workers: Dict[str, WorkerInfo] = {}
        self._lock = threading.RLock()

    def register_worker(self, request: WorkerRegistrationRequest) -> WorkerRegistrationResponse:
        """
        Registers or updates a worker after validating protocol version and auth tokens.
        """
        with self._lock:
            # Protocol check
            if request.protocol_version.split(".")[0] != PROTOCOL_VERSION.split(".")[0]:
                raise IncompatibleProtocolError(
                    f"Worker protocol version '{request.protocol_version}' is incompatible with coordinator '{PROTOCOL_VERSION}'."
                )

            # Auth token verification
            if self.expected_auth_tokens and (not request.auth_token or request.auth_token not in self.expected_auth_tokens):
                raise UnauthorizedWorkerError(f"Worker '{request.worker_id}' failed authentication.")

            now_iso = datetime.now(timezone.utc).isoformat()
            now_ts = time.time()

            info = WorkerInfo(
                worker_id=request.worker_id,
                worker_name=request.worker_name,
                protocol_version=request.protocol_version,
                capabilities=request.capabilities,
                hostname=request.hostname,
                status=WorkerStatus.IDLE,
                registered_at=now_iso,
                last_heartbeat_at=now_iso,
                last_heartbeat_timestamp=now_ts,
            )
            self._workers[request.worker_id] = info

            logger.info("Worker '%s' (%s) registered successfully.", request.worker_id, request.worker_name)
            return WorkerRegistrationResponse(
                accepted=True,
                worker_id=request.worker_id,
                heartbeat_interval_seconds=max(2.0, self.heartbeat_timeout_seconds / 3.0),
                lease_ttl_seconds=self.heartbeat_timeout_seconds,
            )

    def process_heartbeat(self, heartbeat: WorkerHeartbeat) -> bool:
        """
        Updates heartbeat timestamp, load, and status for a registered worker.
        """
        with self._lock:
            worker = self._workers.get(heartbeat.worker_id)
            if not worker:
                logger.warning("Received heartbeat from unknown worker '%s'", heartbeat.worker_id)
                return False

            worker.last_heartbeat_at = datetime.now(timezone.utc).isoformat()
            worker.last_heartbeat_timestamp = time.time()
            worker.status = heartbeat.status
            worker.current_load = heartbeat.current_load
            worker.active_task_ids = set(heartbeat.active_task_ids)
            return True

    def deregister_worker(self, worker_id: str, reason: str = "Graceful shutdown") -> bool:
        """
        Marks worker as STOPPED and removes it from active routing.
        """
        with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.status = WorkerStatus.STOPPED
                worker.last_error = reason
                del self._workers[worker_id]
                logger.info("Worker '%s' deregistered: %s", worker_id, reason)
                return True
            return False

    def record_heartbeat(self, heartbeat: WorkerHeartbeat) -> WorkerHeartbeatResponse:
        """Records a heartbeat and returns a response object."""
        success = self.process_heartbeat(heartbeat)
        from core.worker_protocol import WorkerHeartbeatResponse
        return WorkerHeartbeatResponse(
            acknowledged=success,
            worker_id=heartbeat.worker_id,
        )

    def get_worker(self, worker_id: str) -> Optional[WorkerInfo]:
        """Returns the worker info by ID, or None if not found."""
        with self._lock:
            return self._workers.get(worker_id)

    def get_active_workers(self) -> List[str]:
        """Returns list of active worker IDs."""
        with self._lock:
            self.prune_stale_workers()
            return [w.worker_id for w in self._workers.values() if w.status in {WorkerStatus.IDLE, WorkerStatus.BUSY}]

    def list_workers(self, include_unhealthy: bool = False) -> List[WorkerInfo]:
        """Returns all registered workers."""
        with self._lock:
            self.prune_stale_workers()
            if include_unhealthy:
                return list(self._workers.values())
            return [w for w in self._workers.values() if w.status != WorkerStatus.UNREACHABLE]

    def find_eligible_workers(
        self,
        operation_type: str,
        required_runtime: str = "process",
        require_container: bool = False,
    ) -> List[WorkerInfo]:
        """
        Returns eligible, available workers matching task runtime and capability requirements.
        """
        with self._lock:
            self.prune_stale_workers()
            eligible: List[WorkerInfo] = []
            for w in self._workers.values():
                if not w.is_available:
                    continue
                if operation_type not in w.capabilities.supported_operation_types:
                    continue
                if require_container and not w.capabilities.has_container_support:
                    continue
                if required_runtime not in w.capabilities.supported_runtimes:
                    continue
                eligible.append(w)

            # Sort by least loaded first
            eligible.sort(key=lambda w: (w.current_load, len(w.active_task_ids)))
            return eligible

    def prune_stale_workers(self) -> List[str]:
        """
        Detects and flags workers that have missed their heartbeat window as UNREACHABLE.
        """
        with self._lock:
            now_ts = time.time()
            stale_ids: List[str] = []
            for w_id, w in self._workers.items():
                if w.status in {WorkerStatus.STOPPED, WorkerStatus.UNREACHABLE}:
                    continue
                age = now_ts - w.last_heartbeat_timestamp
                if age > self.heartbeat_timeout_seconds:
                    logger.warning("Worker '%s' heartbeat timed out (age %.1fs > %.1fs). Marking UNREACHABLE.", w_id, age, self.heartbeat_timeout_seconds)
                    w.status = WorkerStatus.UNREACHABLE
                    w.last_error = f"Heartbeat timed out after {age:.1f}s"
                    stale_ids.append(w_id)
            return stale_ids

    def assign_task_to_worker(self, worker_id: str, task_id: str) -> bool:
        """Increments worker load and tracks task assignment."""
        with self._lock:
            worker = self._workers.get(worker_id)
            if worker and worker.is_available:
                worker.active_task_ids.add(task_id)
                worker.current_load = len(worker.active_task_ids)
                if worker.current_load >= worker.capabilities.max_concurrency:
                    worker.status = WorkerStatus.BUSY
                return True
            return False

    def complete_task_for_worker(self, worker_id: str, task_id: str) -> None:
        """Removes task from worker load."""
        with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.active_task_ids.discard(task_id)
                worker.current_load = len(worker.active_task_ids)
                if worker.current_load < worker.capabilities.max_concurrency and worker.status == WorkerStatus.BUSY:
                    worker.status = WorkerStatus.IDLE
