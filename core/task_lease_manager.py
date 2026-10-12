"""
task_lease_manager.py - Task Lease & Ownership Management for Distributed AutoDev (v2.2)

Provides atomic task lease acquisition, heartbeat renewal, TTL-based expiration,
ownership verification tokens, duplicate execution prevention, and stale worker recovery.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from core.worker_protocol import TaskLeaseStatus

logger = logging.getLogger("AutoDev.TaskLeaseManager")


class LeaseError(Exception):
    """Base exception for task lease operations."""
    pass


class LeaseOwnershipError(LeaseError):
    """Raised when an operation is attempted with an invalid or expired lease token."""
    pass


class DuplicateTaskExecutionError(LeaseError):
    """Raised when a task with an active lease is attempted to be reassigned concurrently."""
    pass


@dataclass
class TaskLease:
    """Represents an active or expired ownership lease over an assigned task."""
    lease_id: str
    task_id: str
    operation_id: str
    transaction_id: str
    worker_id: str
    owner_token: str
    attempt_number: int = 1
    idempotency_key: str = ""
    acquired_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_renewed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = ""
    expires_timestamp: float = 0.0
    status: TaskLeaseStatus = TaskLeaseStatus.ACTIVE

    @property
    def lease_token(self) -> str:
        """Alias for owner_token."""
        return self.owner_token

    @property
    def is_valid(self) -> bool:
        """Returns True if lease is in ACTIVE state and has not passed its expiration timestamp."""
        return self.status == TaskLeaseStatus.ACTIVE and time.time() < self.expires_timestamp


    def to_dict(self) -> Dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "task_id": self.task_id,
            "operation_id": self.operation_id,
            "transaction_id": self.transaction_id,
            "worker_id": self.worker_id,
            "owner_token": self.owner_token,
            "attempt_number": self.attempt_number,
            "idempotency_key": self.idempotency_key,
            "acquired_at": self.acquired_at,
            "last_renewed_at": self.last_renewed_at,
            "expires_at": self.expires_at,
            "status": self.status.value,
            "is_valid": self.is_valid,
        }


class TaskLeaseManager:
    """
    Thread-safe coordinator for distributed task ownership leases and heartbeat renewals.
    """

    def __init__(self, default_lease_ttl: float = 15.0) -> None:
        self.default_lease_ttl = default_lease_ttl
        self._leases: Dict[str, TaskLease] = {}             # lease_id -> TaskLease
        self._task_to_lease: Dict[str, str] = {}           # task_id -> lease_id
        self._token_to_lease: Dict[str, str] = {}          # owner_token -> lease_id
        self._completed_tasks: Set[str] = set()
        self._lock = threading.RLock()

    def acquire_lease(
        self,
        task_id: str,
        operation_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        ttl_seconds: Optional[float] = None,
        idempotency_key: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> TaskLease:
        """
        Atomically grants a task ownership lease to a worker.
        """
        with self._lock:
            # Handle 2-arg call (task_id, worker_id)
            if transaction_id is None and worker_id is None and operation_id is not None:
                worker_id = operation_id
                operation_id = task_id
                transaction_id = "default_tx"
            else:
                operation_id = operation_id or task_id
                transaction_id = transaction_id or "default_tx"
                worker_id = worker_id or "default_worker"

            actual_ttl = duration_seconds if duration_seconds is not None else (
                ttl_seconds if ttl_seconds is not None else self.default_lease_ttl
            )
            now_ts = time.time()
            exp_ts = now_ts + actual_ttl

            # Check if existing active lease exists
            existing_lease_id = self._task_to_lease.get(task_id)
            if existing_lease_id:
                existing = self._leases.get(existing_lease_id)
                if existing and existing.is_valid:
                    if existing.worker_id == worker_id:
                        # Re-entrant renewal by same worker
                        existing.expires_timestamp = exp_ts
                        existing.last_renewed_at = datetime.now(timezone.utc).isoformat()
                        return existing
                    raise DuplicateTaskExecutionError(
                        f"Task '{task_id}' already has an active lease held by worker '{existing.worker_id}'."
                    )

            lease_id = f"lease-{uuid.uuid4().hex[:10]}"
            owner_token = f"tok-{uuid.uuid4().hex}"
            now_iso = datetime.now(timezone.utc).isoformat()
            exp_iso = datetime.fromtimestamp(exp_ts, tz=timezone.utc).isoformat()

            lease = TaskLease(
                lease_id=lease_id,
                task_id=task_id,
                operation_id=operation_id,
                transaction_id=transaction_id,
                worker_id=worker_id,
                owner_token=owner_token,
                idempotency_key=idempotency_key or f"idem-{task_id}-{operation_id}",
                acquired_at=now_iso,
                last_renewed_at=now_iso,
                expires_at=exp_iso,
                expires_timestamp=exp_ts,
                status=TaskLeaseStatus.ACTIVE,
            )
            self._leases[lease_id] = lease
            self._task_to_lease[task_id] = lease_id
            self._token_to_lease[owner_token] = lease_id
            logger.info("Granted lease %s on task %s to worker %s (TTL: %.1fs)", lease_id, task_id, worker_id, actual_ttl)
            return lease

    def get_lease(self, task_or_op_id: str) -> Optional[TaskLease]:
        """Looks up active lease by task_id or operation_id."""
        with self._lock:
            lease_id = self._task_to_lease.get(task_or_op_id)
            if lease_id and lease_id in self._leases:
                return self._leases[lease_id]
            for lease in self._leases.values():
                if lease.operation_id == task_or_op_id or lease.task_id == task_or_op_id:
                    return lease
            return None


    def renew_lease(self, owner_token: str, ttl_seconds: Optional[float] = None) -> bool:
        """
        Renews an active task lease using its ownership token.
        """
        with self._lock:
            lease_id = self._token_to_lease.get(owner_token)
            if not lease_id:
                return False
            lease = self._leases.get(lease_id)
            if not lease or lease.status != TaskLeaseStatus.ACTIVE:
                return False

            ttl = ttl_seconds if ttl_seconds is not None else self.default_lease_ttl
            lease.expires_timestamp = time.time() + ttl
            lease.expires_at = datetime.fromtimestamp(lease.expires_timestamp, tz=timezone.utc).isoformat()
            lease.last_renewed_at = datetime.now(timezone.utc).isoformat()
            return True

    def validate_ownership(self, task_id: str, owner_token: str) -> bool:
        """
        Strictly verifies that owner_token holds a valid, unexpired lease for the specified task.
        """
        with self._lock:
            lease_id = self._task_to_lease.get(task_id)
            if not lease_id:
                return False
            lease = self._leases.get(lease_id)
            if not lease:
                return False
            if lease.owner_token != owner_token:
                return False
            return lease.is_valid

    def release_lease(self, owner_token: str, mark_completed: bool = True) -> bool:
        """
        Releases task lease upon successful execution.
        """
        with self._lock:
            lease_id = self._token_to_lease.get(owner_token)
            if not lease_id:
                return False
            lease = self._leases.get(lease_id)
            if not lease:
                return False

            lease.status = TaskLeaseStatus.RELEASED
            if mark_completed:
                self._completed_tasks.add(lease.task_id)
            logger.info("Released lease %s for task %s", lease_id, lease.task_id)
            return True

    def revoke_lease(self, task_id: str, reason: str = "Revoked by coordinator") -> bool:
        """
        Revokes a lease due to worker failure, timeout, or cancellation.
        """
        with self._lock:
            lease_id = self._task_to_lease.get(task_id)
            if not lease_id:
                return False
            lease = self._leases.get(lease_id)
            if not lease:
                return False

            lease.status = TaskLeaseStatus.REVOKED
            logger.warning("Revoked lease %s on task %s: %s", lease_id, task_id, reason)
            return True

    def get_expired_leases(self) -> List[TaskLease]:
        """
        Returns all leases whose TTL has expired and updates their status to EXPIRED.
        """
        with self._lock:
            now_ts = time.time()
            expired: List[TaskLease] = []
            for lease in self._leases.values():
                if lease.status == TaskLeaseStatus.ACTIVE and now_ts >= lease.expires_timestamp:
                    lease.status = TaskLeaseStatus.EXPIRED
                    expired.append(lease)
                    logger.warning("Task lease %s for task %s has expired.", lease.lease_id, lease.task_id)
            return expired

    def get_active_leases_for_worker(self, worker_id: str) -> List[TaskLease]:
        """Returns all currently valid active leases held by the given worker."""
        with self._lock:
            return [
                lease for lease in self._leases.values()
                if lease.worker_id == worker_id and lease.is_valid
            ]

    def get_active_leases_for_transaction(self, transaction_id: str) -> List[TaskLease]:
        """Returns all currently valid active leases associated with the given transaction."""
        with self._lock:
            return [
                lease for lease in self._leases.values()
                if lease.transaction_id == transaction_id and lease.is_valid
            ]

