"""
AutoDev Parallel Executor Subsystem.

Provides concurrent task execution across distributed agents using ThreadPoolExecutor,
coordinated resource locking, deadlock prevention, and execution telemetry.
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.multi_agent.agent_registry import AgentDescriptor
from core.multi_agent.resource_scheduler import LockType, ResourceScheduler
from core.multi_agent.work_queue import WorkItem, WorkItemStatus


@dataclass
class ExecutionResult:
    """Record of an executed task run."""
    task_id: str
    agent_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    resources_used: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the execution result."""
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "resources_used": list(self.resources_used),
        }


class ParallelExecutor:
    """
    Manages concurrent multi-agent task execution with bounded thread workers,
    integrated resource reservation, and performance telemetry.
    """

    def __init__(
        self,
        max_workers: int = 8,
        deterministic_mode: bool = False,
    ) -> None:
        self.max_workers = max(1, max_workers)
        self.deterministic_mode = deterministic_mode
        self._pool = (
            concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
            if not deterministic_mode
            else None
        )
        self._lock = threading.RLock()
        self._active_tasks = 0
        self._peak_concurrency = 0
        self._total_executed = 0
        self._total_duration = 0.0
        self._is_shutdown = False

    @property
    def peak_concurrency(self) -> int:
        """Peak simultaneous tasks observed."""
        with self._lock:
            return self._peak_concurrency

    @property
    def total_executed(self) -> int:
        """Total tasks processed by executor."""
        with self._lock:
            return self._total_executed

    @property
    def total_duration(self) -> float:
        """Sum of all task runtimes."""
        with self._lock:
            return self._total_duration

    def _track_start(self) -> None:
        with self._lock:
            self._active_tasks += 1
            if self._active_tasks > self._peak_concurrency:
                self._peak_concurrency = self._active_tasks

    def _track_end(self, duration: float) -> None:
        with self._lock:
            self._active_tasks -= 1
            self._total_executed += 1
            self._total_duration += duration

    def _run_single(
        self,
        task: WorkItem,
        agent: AgentDescriptor,
        runner_fn: Callable[[WorkItem, AgentDescriptor], Any],
        scheduler: Optional[ResourceScheduler] = None,
    ) -> ExecutionResult:
        """Internal worker function that executes a single task under resource locks."""
        self._track_start()
        start_time = time.time()
        resources_to_lock = list(task.resources_required)
        reservation_id: Optional[str] = None
        success = False
        res_output = None
        err_msg = None

        try:
            # 1. Acquire resource locks if resources specified
            if scheduler and resources_to_lock:
                reservation_id = scheduler.reserve_resources(
                    agent_id=agent.agent_id,
                    resource_ids=resources_to_lock,
                    lock_type=LockType.WRITE,
                    timeout=10.0,
                )
                if not reservation_id:
                    raise TimeoutError(
                        f"Failed to acquire resources {resources_to_lock} for task {task.task_id}"
                    )

            # 2. Invoke runner function
            res_output = runner_fn(task, agent)
            success = True

        except Exception as ex:
            success = False
            err_msg = str(ex)
        finally:
            # 3. Always release resource reservation
            if scheduler and reservation_id:
                scheduler.release_reservation(reservation_id)

            end_time = time.time()
            duration = end_time - start_time
            self._track_end(duration)

        return ExecutionResult(
            task_id=task.task_id,
            agent_id=agent.agent_id,
            success=success,
            result=res_output,
            error=err_msg,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            resources_used=resources_to_lock,
        )

    def execute_task(
        self,
        task: WorkItem,
        agent: AgentDescriptor,
        runner_fn: Callable[[WorkItem, AgentDescriptor], Any],
        scheduler: Optional[ResourceScheduler] = None,
    ) -> ExecutionResult:
        """Synchronously executes a task or runs directly."""
        return self._run_single(task, agent, runner_fn, scheduler)

    def execute_batch(
        self,
        tasks_with_agents: List[Tuple[WorkItem, AgentDescriptor, Callable[[WorkItem, AgentDescriptor], Any]]],
        scheduler: Optional[ResourceScheduler] = None,
    ) -> List[ExecutionResult]:
        """
        Executes a batch of assigned tasks simultaneously using the thread pool.
        In deterministic_mode, executes them sequentially in canonical task order.
        """
        if not tasks_with_agents:
            return []

        if self.deterministic_mode or self._pool is None:
            # Deterministic sequential execution
            results: List[ExecutionResult] = []
            for task, agent, runner_fn in tasks_with_agents:
                res = self._run_single(task, agent, runner_fn, scheduler)
                results.append(res)
            return results

        # Concurrent parallel execution
        futures: List[concurrent.futures.Future[ExecutionResult]] = []
        for task, agent, runner_fn in tasks_with_agents:
            f = self._pool.submit(self._run_single, task, agent, runner_fn, scheduler)
            futures.append(f)

        results = []
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

        # Sort results deterministically by task_id for reproducible reporting
        results.sort(key=lambda r: r.task_id)
        return results

    def shutdown(self, wait: bool = True) -> None:
        """Shuts down the internal thread pool."""
        with self._lock:
            if not self._is_shutdown and self._pool is not None:
                self._pool.shutdown(wait=wait)
                self._is_shutdown = True
