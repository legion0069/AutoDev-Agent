"""
distributed_scheduler.py - Dependency-Aware Distributed Operation Scheduler for AutoDev (v2.2)

Coordinates execution of ChangeExecutionPlan stages across distributed workers.
Enforces stage dependencies, disjoint file boundaries, bounded concurrency,
and fail-closed isolation policies.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.change_execution_planner import ChangeExecutionPlan, ChangeOperation, ExecutionStage
from core.task_lease_manager import LeaseOwnershipError, TaskLease, TaskLeaseManager
from core.worker_protocol import (
    TaskAssignmentPayload,
    TaskResultPayload,
    WorkerCapabilities,
    WorkerStatus,
)
from core.worker_registry import WorkerInfo, WorkerRegistry

logger = logging.getLogger("AutoDev.DistributedScheduler")


class DistributedSchedulerError(Exception):
    """Base exception for distributed scheduler errors."""
    pass


class WorkerUnavailableError(DistributedSchedulerError):
    """Raised when no worker satisfying required capabilities is available."""
    pass


class ConflictingOperationError(DistributedSchedulerError):
    """Raised when conflicting file mutations are scheduled concurrently."""
    pass


@dataclass
class SchedulerConfig:
    """Configuration for distributed operation scheduling."""
    max_global_concurrency: int = 8
    max_worker_concurrency: int = 2
    task_timeout_seconds: float = 60.0
    lease_ttl_seconds: float = 15.0
    require_container_isolation: bool = False
    preferred_runtime: str = "process"
    enforce_disjoint_batches: bool = True


class DistributedScheduler:
    """
    Coordinates distributed operation execution across registered workers.
    """

    def __init__(
        self,
        registry: WorkerRegistry,
        lease_manager: TaskLeaseManager,
        config: Optional[SchedulerConfig] = None,
    ) -> None:
        self.registry = registry
        self.lease_manager = lease_manager
        self.config = config or SchedulerConfig()
        self._lock = threading.RLock()
        self._active_file_locks: Set[str] = set()

    def partition_disjoint_batches(self, operations: List[ChangeOperation]) -> List[List[ChangeOperation]]:
        """
        Partitions operations into sequential batches where each batch contains
        strictly disjoint file target sets for safe parallel dispatch.
        """
        batches: List[List[ChangeOperation]] = []
        current_batch: List[ChangeOperation] = []
        current_files: Set[str] = set()

        for op in operations:
            target_norm = Path(op.file).as_posix().lower() if op.file else ""
            if target_norm and target_norm in current_files:
                # File conflict detected in current batch -> start new batch
                if current_batch:
                    batches.append(current_batch)
                current_batch = [op]
                current_files = {target_norm}
            else:
                current_batch.append(op)
                if target_norm:
                    current_files.add(target_norm)

        if current_batch:
            batches.append(current_batch)

        return batches

    def create_assignment(
        self,
        operation: ChangeOperation,
        transaction_id: str,
        worker_id: str,
    ) -> Tuple[TaskAssignmentPayload, TaskLease]:
        """
        Acquires a task lease and creates a TaskAssignmentPayload for an operation.
        """
        with self._lock:
            target_norm = Path(operation.file).as_posix() if operation.file else ""
            task_id = f"task-{operation.operation_id}"

            lease = self.lease_manager.acquire_lease(
                task_id=task_id,
                operation_id=operation.operation_id,
                transaction_id=transaction_id,
                worker_id=worker_id,
                ttl_seconds=self.config.lease_ttl_seconds,
            )

            req_runtime = "container" if self.config.require_container_isolation else self.config.preferred_runtime

            payload = TaskAssignmentPayload(
                task_id=task_id,
                operation_id=operation.operation_id,
                transaction_id=transaction_id,
                operation_type=operation.operation_type,
                target_file=target_norm,
                target_content=operation.target_content,
                lease_token=lease.owner_token,
                deadline_utc=lease.expires_at,
                idempotency_key=lease.idempotency_key,
                required_runtime=req_runtime,
                security_profile="restricted",
                metadata={"reason": operation.reason},
            )

            self.registry.assign_task_to_worker(worker_id, task_id)
            if target_norm:
                self._active_file_locks.add(target_norm.lower())

            return payload, lease

    def release_operation(self, worker_id: str, task_id: str, lease_token: str, target_file: Optional[str] = None) -> None:
        """
        Releases task lease, worker load, and active file lock.
        """
        with self._lock:
            self.lease_manager.release_lease(lease_token)
            self.registry.complete_task_for_worker(worker_id, task_id)
            if target_file:
                self._active_file_locks.discard(Path(target_file).as_posix().lower())

    def cancel_transaction(self, transaction_id: str) -> None:
        """Revokes all active task leases associated with the given transaction."""
        with self._lock:
            active_leases = self.lease_manager.get_active_leases_for_transaction(transaction_id)
            for lease in active_leases:
                self.lease_manager.revoke_lease(lease.task_id, reason=f"Transaction {transaction_id} cancelled")
                self.registry.complete_task_for_worker(lease.worker_id, lease.task_id)

    def find_worker_for_operation(
        self,
        operation: ChangeOperation,
        require_container: Optional[bool] = None,
    ) -> WorkerInfo:
        """
        Selects an eligible worker for the specified change operation.
        """
        with self._lock:
            req_container = require_container if require_container is not None else self.config.require_container_isolation
            req_runtime = "container" if req_container else self.config.preferred_runtime
            eligible = self.registry.find_eligible_workers(
                operation_type=operation.operation_type,
                required_runtime=req_runtime,
                require_container=req_container,
            )
            if not eligible:
                raise WorkerUnavailableError(
                    f"No available workers found satisfying operation '{operation.operation_type}' and runtime requirements."
                )
            return eligible[0]
