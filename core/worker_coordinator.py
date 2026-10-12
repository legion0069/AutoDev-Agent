"""
worker_coordinator.py - Distributed Worker Coordinator for AutoDev (v2.2)

Coordinates distributed workers, manages local/remote worker pools, dispatches
stages with disjoint-batch concurrency, validates worker results, and integrates
with Version 2.1 transactional recovery and journal logging.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from core.change_execution_planner import ChangeOperation, ExecutionStage, ValidationGate
from core.distributed_scheduler import DistributedScheduler, SchedulerConfig
from core.execution_journal import ExecutionJournal
from core.execution_recovery import ExecutionRecovery
from core.execution_transaction import (
    ExecutionReport,
    ExecutionStatus,
    ExecutionTransaction,
    OperationExecutionResult,
    StageExecutionResult,
)
from core.task_lease_manager import TaskLeaseManager
from core.worker_agent import WorkerAgent
from core.worker_protocol import (
    TaskAssignmentPayload,
    TaskResultPayload,
    WorkerCapabilities,
    WorkerHeartbeat,
    WorkerRegistrationRequest,
    WorkerStatus,
)
from core.worker_registry import WorkerInfo, WorkerRegistry

logger = logging.getLogger("AutoDev.WorkerCoordinator")


class WorkerCoordinator:
    """
    Central coordinator managing distributed worker pools, task assignments, and stage execution.
    """

    def __init__(
        self,
        workspace_root: Union[str, Path] = "projects",
        registry: Optional[WorkerRegistry] = None,
        lease_manager: Optional[TaskLeaseManager] = None,
        scheduler_config: Optional[SchedulerConfig] = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.registry = registry or WorkerRegistry()
        self.lease_manager = lease_manager or TaskLeaseManager()
        self.scheduler = DistributedScheduler(
            registry=self.registry,
            lease_manager=self.lease_manager,
            config=scheduler_config,
        )
        self.local_workers: Dict[str, WorkerAgent] = {}
        self._lock = threading.RLock()

    def spawn_local_workers(self, count: int = 2) -> List[WorkerAgent]:
        """
        Spawns a local pool of in-process WorkerAgents and registers them with the coordinator.
        """
        with self._lock:
            spawned: List[WorkerAgent] = []
            for idx in range(count):
                worker_id = f"local-worker-{idx + 1}"
                agent = WorkerAgent(
                    worker_id=worker_id,
                    workspace_root=self.workspace_root,
                    capabilities=WorkerCapabilities(max_concurrency=2),
                )
                self.local_workers[worker_id] = agent

                # Register with coordinator
                req = agent.create_registration_request()
                self.registry.register_worker(req)
                spawned.append(agent)

            logger.info("Spawned and registered %d local worker agents.", count)
            return spawned

    def execute_stage_distributed(
        self,
        transaction: ExecutionTransaction,
        stage: ExecutionStage,
        journal: Optional[ExecutionJournal] = None,
    ) -> StageExecutionResult:
        """
        Executes an ExecutionStage across registered distributed workers.
        Enforces disjoint file batching, pre-mutation snapshots, and result validation.
        """
        start_time = time.perf_counter()
        transaction.active_stage = stage.stage_number

        if journal:
            journal.append_event(
                "STAGE_DISTRIBUTED_STARTED",
                {"stage_number": stage.stage_number, "operations_count": len(stage.operations)},
            )

        operation_results: List[OperationExecutionResult] = []
        stage_status = ExecutionStatus.SUCCEEDED
        failure_reason: Optional[str] = None

        # 1. Partition operations into disjoint file batches
        batches = self.scheduler.partition_disjoint_batches(stage.operations)

        for batch_idx, batch in enumerate(batches):
            logger.info("Executing disjoint operation batch %d/%d (ops: %d)", batch_idx + 1, len(batches), len(batch))

            # Capture pre-mutation snapshots on coordinator
            for op in batch:
                if op.file:
                    transaction.capture_file_snapshot(op.file)

            # Dispatch batch in parallel across eligible workers
            with ThreadPoolExecutor(max_workers=min(len(batch), self.scheduler.config.max_global_concurrency)) as executor:
                futures = {}
                for op in batch:
                    # Route to worker
                    worker = self.scheduler.find_worker_for_operation(op)
                    payload, lease = self.scheduler.create_assignment(op, transaction.transaction_id, worker.worker_id)

                    # Get local worker agent or execute via dispatch
                    worker_agent = self.local_workers.get(worker.worker_id)
                    if not worker_agent:
                        # Fallback create worker agent
                        worker_agent = WorkerAgent(worker.worker_id, workspace_root=self.workspace_root)

                    fut = executor.submit(worker_agent.execute_assignment, payload)
                    futures[fut] = (op, payload, lease, worker.worker_id)

                for fut in as_completed(futures):
                    op, payload, lease, worker_id = futures[fut]
                    try:
                        result_payload: TaskResultPayload = fut.result()

                        # Validate ownership
                        if not self.lease_manager.validate_ownership(payload.task_id, payload.lease_token):
                            raise ValueError(f"Task result rejected: invalid or expired lease token for {payload.task_id}")

                        # Record transaction changes
                        for c_file in result_payload.created_files:
                            transaction.record_change(c_file, "CREATE")
                        for m_file in result_payload.modified_files:
                            transaction.record_change(m_file, "MODIFY")
                        for d_file in result_payload.deleted_files:
                            transaction.record_change(d_file, "DELETE")

                        op_res = OperationExecutionResult(
                            operation_id=op.operation_id,
                            status=ExecutionStatus.SUCCEEDED if result_payload.success else ExecutionStatus.FAILED,
                            duration_seconds=result_payload.duration_seconds,
                            modified_files=result_payload.modified_files,
                            created_files=result_payload.created_files,
                            deleted_files=result_payload.deleted_files,
                            error_type=result_payload.error_type,
                            error_message=result_payload.error_message,
                        )
                        operation_results.append(op_res)

                        if not result_payload.success:
                            stage_status = ExecutionStatus.FAILED
                            failure_reason = f"Operation '{op.operation_id}' failed: {result_payload.error_message}"

                    except Exception as exc:
                        stage_status = ExecutionStatus.FAILED
                        failure_reason = f"Operation '{op.operation_id}' execution exception: {exc}"
                        operation_results.append(
                            OperationExecutionResult(
                                operation_id=op.operation_id,
                                status=ExecutionStatus.FAILED,
                                error_type=type(exc).__name__,
                                error_message=str(exc),
                            )
                        )
                    finally:
                        self.scheduler.release_operation(worker_id, payload.task_id, payload.lease_token, op.file)

            if stage_status == ExecutionStatus.FAILED:
                # Stop subsequent batches
                break

        duration = time.perf_counter() - start_time
        return StageExecutionResult(
            stage_number=stage.stage_number,
            status=stage_status,
            operation_results=operation_results,
            duration_seconds=duration,
            failure_reason=failure_reason,
        )
