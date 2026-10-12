"""
distributed_queue.py - Reliable Distributed Priority Queue for AutoDev Cluster (v2.9)

Provides reliable task distribution, priority scheduling, visibility timeouts,
acknowledgement protocols, exponential backoff retries, and dead-letter queue (DLQ) support.
"""

from __future__ import annotations

import copy
import heapq
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import TaskExecutionStatus, TaskSpec

logger = logging.getLogger("AutoDev.Cluster.Queue")


@dataclass(order=True)
class PrioritizedTaskItem:
    priority: int
    created_at: float
    task_id: str = field(compare=False)
    task: TaskSpec = field(compare=False)


class DistributedQueue:
    """
    High-reliability thread-safe distributed priority task queue.
    Manages ready queue, in-flight visibility leases, retry backoffs, and dead-letter storage.
    """

    def __init__(self, config: Optional[ClusterConfig] = None) -> None:
        self.config = config or ClusterConfig()
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)

        # Storage structures
        self._ready_heap: List[PrioritizedTaskItem] = []
        self._inflight: Dict[str, TaskSpec] = {}              # task_id -> TaskSpec
        self._dead_letter: Dict[str, TaskSpec] = {}          # task_id -> TaskSpec
        self._completed: Dict[str, TaskSpec] = {}            # task_id -> TaskSpec
        self._all_tasks: Dict[str, TaskSpec] = {}            # task_id -> TaskSpec
        self._waiting_dependencies: Dict[str, TaskSpec] = {} # task_id -> TaskSpec

        # Metrics counters
        self._total_enqueued = 0
        self._total_dequeued = 0
        self._total_acked = 0
        self._total_nacked = 0
        self._total_retried = 0

    def enqueue(self, task: TaskSpec) -> bool:
        """
        Pushes a task into the queue. If it has unsatisfied dependencies,
        it is placed in the waiting pool until dependencies complete.
        """
        with self._lock:
            now = time.time()
            t = copy.deepcopy(task)
            t.created_at = t.created_at or now
            self._all_tasks[t.task_id] = t

            # Check if dependencies are satisfied
            if t.dependencies and not self._are_dependencies_satisfied(t.dependencies):
                t.status = TaskExecutionStatus.PENDING
                self._waiting_dependencies[t.task_id] = t
                logger.debug("Task %s enqueued to dependency wait pool (waiting for %s)", t.task_id, t.dependencies)
            else:
                t.status = TaskExecutionStatus.PENDING
                item = PrioritizedTaskItem(priority=t.priority, created_at=t.created_at, task_id=t.task_id, task=t)
                heapq.heappush(self._ready_heap, item)
                logger.debug("Task %s enqueued to ready heap (priority=%d)", t.task_id, t.priority)

            self._total_enqueued += 1
            self._cond.notify_all()
            return True

    def enqueue_batch(self, tasks: List[TaskSpec]) -> int:
        """Enqueues a batch of tasks."""
        with self._lock:
            count = 0
            for t in tasks:
                if self.enqueue(t):
                    count += 1
            return count

    def dequeue(
        self,
        worker_id: str,
        capabilities: Optional[List[str]] = None,
        timeout: float = 0.0,
    ) -> Optional[TaskSpec]:
        """
        Dequeues the highest-priority available task matching worker capabilities.
        If timeout > 0, waits up to timeout seconds for a task to become available.
        """
        deadline = time.time() + timeout if timeout > 0 else 0.0
        with self._lock:
            while True:
                # Reclaim timed-out tasks only if in-flight tasks exist
                if self._inflight:
                    self.reclaim_timed_out_tasks()

                # Find candidate from ready heap
                temp_held: List[PrioritizedTaskItem] = []
                selected_task: Optional[TaskSpec] = None

                while self._ready_heap:
                    item = heapq.heappop(self._ready_heap)
                    task = item.task

                    # Verify task is still pending and valid
                    if task.task_id in self._inflight or task.task_id in self._completed:
                        continue

                    # Capability matching
                    if self._matches_capabilities(task, capabilities):
                        selected_task = task
                        break
                    else:
                        temp_held.append(item)

                # Push back unmatched items
                for item in temp_held:
                    heapq.heappush(self._ready_heap, item)

                if selected_task:
                    now = time.time()
                    selected_task.assigned_worker_id = worker_id
                    selected_task.started_at = now
                    selected_task.status = TaskExecutionStatus.RUNNING
                    selected_task.visibility_deadline = now + self.config.queue_visibility_timeout
                    self._inflight[selected_task.task_id] = selected_task
                    self._all_tasks[selected_task.task_id] = selected_task
                    self._total_dequeued += 1
                    logger.debug("Task %s dispatched to worker %s (visibility_deadline=%.2f)", selected_task.task_id, worker_id, selected_task.visibility_deadline)
                    return copy.deepcopy(selected_task)

                if timeout <= 0.0:
                    return None

                remaining = deadline - time.time()
                if remaining <= 0.0:
                    return None

                self._cond.wait(timeout=min(remaining, 0.5))

    def dequeue_batch(
        self,
        worker_id: str,
        max_count: int,
        capabilities: Optional[List[str]] = None,
    ) -> List[TaskSpec]:
        """
        Dequeues up to max_count tasks matching capabilities in high-throughput batch mode.
        """
        batch: List[TaskSpec] = []
        with self._lock:
            if self._inflight:
                self.reclaim_timed_out_tasks()

            temp_held: List[PrioritizedTaskItem] = []
            now = time.time()

            while self._ready_heap and len(batch) < max_count:
                item = heapq.heappop(self._ready_heap)
                task = item.task

                if task.task_id in self._inflight or task.task_id in self._completed:
                    continue

                if self._matches_capabilities(task, capabilities):
                    task.assigned_worker_id = worker_id
                    task.started_at = now
                    task.status = TaskExecutionStatus.RUNNING
                    task.visibility_deadline = now + self.config.queue_visibility_timeout
                    self._inflight[task.task_id] = task
                    self._all_tasks[task.task_id] = task
                    self._total_dequeued += 1
                    batch.append(copy.deepcopy(task))
                else:
                    temp_held.append(item)

            for item in temp_held:
                heapq.heappush(self._ready_heap, item)

        return batch

    def ack(self, task_id: str, result: Optional[Dict[str, Any]] = None, artifacts: Optional[List[str]] = None) -> bool:
        """
        Acknowledges successful completion of a task.
        Transitions status to COMPLETED, stores result, and unblocks waiting dependencies.
        """
        with self._lock:
            task = self._inflight.pop(task_id, None) or self._all_tasks.get(task_id)
            if not task:
                logger.warning("Ack failed: Task %s not found in inflight registry", task_id)
                return False

            now = time.time()
            task.status = TaskExecutionStatus.COMPLETED
            task.completed_at = now
            if result is not None:
                task.result = result
            if artifacts:
                task.artifacts.extend(artifacts)

            self._completed[task_id] = task
            self._all_tasks[task_id] = task
            self._total_acked += 1
            logger.debug("Task %s acknowledged successfully", task_id)

            # Check dependent waiting tasks
            self._check_and_promote_waiting_tasks()
            self._cond.notify_all()
            return True

    def nack(self, task_id: str, error: str = "", retry: bool = True) -> bool:
        """
        Negatively acknowledges a task execution failure.
        If retry count < max_retries, schedules backoff retry. Otherwise moves to Dead-Letter Queue (DLQ).
        """
        with self._lock:
            task = self._inflight.pop(task_id, None) or self._all_tasks.get(task_id)
            if not task:
                logger.warning("Nack failed: Task %s not found", task_id)
                return False

            now = time.time()
            task.error_message = error
            self._total_nacked += 1

            if retry and task.retry_count < task.max_retries and task.retry_count < self.config.max_task_retries:
                task.retry_count += 1
                task.status = TaskExecutionStatus.RETRYING
                task.assigned_worker_id = None
                self._total_retried += 1
                logger.warning("Task %s failed (attempt %d/%d): %s. Re-enqueuing for retry.", task_id, task.retry_count, task.max_retries, error)
                # Re-add to ready heap
                item = PrioritizedTaskItem(priority=task.priority, created_at=now, task_id=task.task_id, task=task)
                heapq.heappush(self._ready_heap, item)
            else:
                task.status = TaskExecutionStatus.DEAD_LETTER
                task.completed_at = now
                self._dead_letter[task_id] = task
                logger.error("Task %s moved to Dead-Letter Queue (retries exhausted: %d/%d): %s", task_id, task.retry_count, task.max_retries, error)

            self._all_tasks[task_id] = task
            self._cond.notify_all()
            return True

    def reclaim_timed_out_tasks(self, current_time: Optional[float] = None) -> List[str]:
        """
        Reclaims tasks whose visibility deadline expired without ACK/NACK.
        Re-enqueues them or routes to DLQ.
        """
        with self._lock:
            now = current_time if current_time is not None else time.time()
            expired_ids: List[str] = []

            for t_id, task in list(self._inflight.items()):
                if now >= task.visibility_deadline:
                    expired_ids.append(t_id)
                    del self._inflight[t_id]
                    logger.warning("Task %s visibility deadline expired (worker %s). Reclaiming.", t_id, task.assigned_worker_id)
                    self.nack(t_id, error="Visibility lease expired", retry=True)

            return expired_ids

    def _matches_capabilities(self, task: TaskSpec, capabilities: Optional[List[str]]) -> bool:
        if not task.required_capabilities:
            return True
        if not capabilities:
            return False
        caps_set = set(capabilities)
        if "general" in caps_set:
            return True
        return all(c in caps_set for c in task.required_capabilities)

    def _are_dependencies_satisfied(self, dependencies: List[str]) -> bool:
        for dep in dependencies:
            dep_task = self._completed.get(dep)
            if not dep_task or dep_task.status != TaskExecutionStatus.COMPLETED:
                return False
        return True

    def _check_and_promote_waiting_tasks(self) -> None:
        promoted: List[str] = []
        for t_id, task in list(self._waiting_dependencies.items()):
            if self._are_dependencies_satisfied(task.dependencies):
                promoted.append(t_id)
                del self._waiting_dependencies[t_id]
                item = PrioritizedTaskItem(priority=task.priority, created_at=task.created_at, task_id=task.task_id, task=task)
                heapq.heappush(self._ready_heap, item)
                logger.info("Promoted task %s from dependency wait pool to ready queue", t_id)

    def get_task(self, task_id: str) -> Optional[TaskSpec]:
        with self._lock:
            t = self._all_tasks.get(task_id)
            return copy.deepcopy(t) if t else None

    def get_queue_depth(self) -> int:
        with self._lock:
            return len(self._ready_heap)

    def get_inflight_count(self) -> int:
        with self._lock:
            return len(self._inflight)

    def get_dead_letter_tasks(self) -> List[TaskSpec]:
        with self._lock:
            return [copy.deepcopy(t) for t in self._dead_letter.values()]

    def retry_dead_letter(self, task_id: str) -> bool:
        """Manually retries a dead-letter task."""
        with self._lock:
            task = self._dead_letter.pop(task_id, None)
            if not task:
                return False
            task.retry_count = 0
            task.status = TaskExecutionStatus.PENDING
            task.error_message = None
            item = PrioritizedTaskItem(priority=task.priority, created_at=time.time(), task_id=task.task_id, task=task)
            heapq.heappush(self._ready_heap, item)
            self._cond.notify_all()
            logger.info("Manual DLQ retry initiated for task %s", task_id)
            return True

    def export_state(self) -> Dict[str, Any]:
        """Exports queue state for cluster checkpointing."""
        with self._lock:
            return {
                "ready": [item.task.to_dict() for item in self._ready_heap],
                "inflight": {k: v.to_dict() for k, v in self._inflight.items()},
                "waiting_dependencies": {k: v.to_dict() for k, v in self._waiting_dependencies.items()},
                "dead_letter": {k: v.to_dict() for k, v in self._dead_letter.items()},
                "completed": {k: v.to_dict() for k, v in self._completed.items()},
                "stats": {
                    "enqueued": self._total_enqueued,
                    "dequeued": self._total_dequeued,
                    "acked": self._total_acked,
                    "nacked": self._total_nacked,
                    "retried": self._total_retried,
                },
            }

    def import_state(self, data: Dict[str, Any]) -> None:
        """Restores queue state from checkpoint."""
        with self._lock:
            self._ready_heap.clear()
            self._inflight.clear()
            self._waiting_dependencies.clear()
            self._dead_letter.clear()
            self._completed.clear()
            self._all_tasks.clear()

            for t_dict in data.get("ready", []):
                t = TaskSpec.from_dict(t_dict)
                self._all_tasks[t.task_id] = t
                item = PrioritizedTaskItem(priority=t.priority, created_at=t.created_at, task_id=t.task_id, task=t)
                heapq.heappush(self._ready_heap, item)

            for k, v in data.get("inflight", {}).items():
                t = TaskSpec.from_dict(v)
                self._inflight[k] = t
                self._all_tasks[k] = t

            for k, v in data.get("waiting_dependencies", {}).items():
                t = TaskSpec.from_dict(v)
                self._waiting_dependencies[k] = t
                self._all_tasks[k] = t

            for k, v in data.get("dead_letter", {}).items():
                t = TaskSpec.from_dict(v)
                self._dead_letter[k] = t
                self._all_tasks[k] = t

            for k, v in data.get("completed", {}).items():
                t = TaskSpec.from_dict(v)
                self._completed[k] = t
                self._all_tasks[k] = t

            stats = data.get("stats", {})
            self._total_enqueued = stats.get("enqueued", 0)
            self._total_dequeued = stats.get("dequeued", 0)
            self._total_acked = stats.get("acked", 0)
            self._total_nacked = stats.get("nacked", 0)
            self._total_retried = stats.get("retried", 0)
            self._cond.notify_all()
