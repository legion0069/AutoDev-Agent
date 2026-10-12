"""
worker_node.py - Autonomous Distributed Worker Node Engine for AutoDev (v2.9)

Executes specialized distributed engineering tasks (Planning, Coding, Review, Testing,
Security, Documentation, Packaging), manages task visibility leases, reports execution telemetry,
synchronizes distributed memory/artifacts, and sends periodic heartbeats to the cluster master.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from core.cluster.artifact_sync import ArtifactSyncManager
from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import (
    DistributedClusterMemory,
    LockType,
    NodeInfo,
    NodeRole,
    NodeStatus,
    TaskExecutionStatus,
    TaskSpec,
)
from core.cluster.distributed_lock_manager import DistributedLockManager
from core.cluster.distributed_queue import DistributedQueue

logger = logging.getLogger("AutoDev.Cluster.Worker")

# Default engineering capabilities supported by AutoDev workers
DEFAULT_ENGINEERING_CAPABILITIES = [
    "planning",
    "coding",
    "review",
    "testing",
    "security",
    "documentation",
    "packaging",
    "architecture",
    "performance",
    "general",
]


class WorkerNode:
    """
    Autonomous distributed cluster worker.
    Continuously pulls assigned or capability-matched tasks from the distributed queue,
    executes them safely, maintains heartbeat telemetry, and reports artifacts/results to the master.
    """

    def __init__(
        self,
        node_id: str,
        hostname: str = "localhost",
        ip: str = "127.0.0.1",
        port: int = 9500,
        capabilities: Optional[List[str]] = None,
        max_tasks: int = 4,
        config: Optional[ClusterConfig] = None,
        queue: Optional[DistributedQueue] = None,
        lock_manager: Optional[DistributedLockManager] = None,
        artifact_sync: Optional[ArtifactSyncManager] = None,
        memory: Optional[DistributedClusterMemory] = None,
        heartbeat_callback: Optional[Callable[[str, float, float, int, float, Dict[str, Any]], None]] = None,
        task_handlers: Optional[Dict[str, Callable[[TaskSpec, WorkerNode], Dict[str, Any]]]] = None,
    ) -> None:
        self.node_id = node_id
        self.hostname = hostname
        self.ip = ip
        self.port = port
        self.capabilities = capabilities or list(DEFAULT_ENGINEERING_CAPABILITIES)
        self.max_tasks = max_tasks
        self.config = config or ClusterConfig()

        self.queue = queue
        self.lock_manager = lock_manager
        self.artifact_sync = artifact_sync or ArtifactSyncManager(node_id=node_id, config=self.config)
        self.memory = memory or DistributedClusterMemory(node_id=node_id)
        self.heartbeat_callback = heartbeat_callback
        self.task_handlers = task_handlers or {}

        # Worker Node Info
        self.info = NodeInfo(
            node_id=self.node_id,
            hostname=self.hostname,
            ip=self.ip,
            port=self.port,
            role=NodeRole.WORKER,
            status=NodeStatus.HEALTHY,
            capabilities=list(self.capabilities),
            max_tasks=self.max_tasks,
            active_tasks=0,
            uptime=0.0,
            health_score=100.0,
        )

        self._running = False
        self._execution_threads: List[threading.Thread] = []
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._active_tasks_map: Dict[str, TaskSpec] = {}
        self._logs: List[str] = []
        self._start_time = time.time()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def active_task_count(self) -> int:
        with self._lock:
            return len(self._active_tasks_map)

    def register_handler(self, capability: str, handler: Callable[[TaskSpec, WorkerNode], Dict[str, Any]]) -> None:
        """Registers custom execution handler for specific capability."""
        with self._lock:
            self.task_handlers[capability.lower()] = handler

    def send_heartbeat(self) -> None:
        """Sends heartbeat telemetry to master / coordinator."""
        with self._lock:
            now = time.time()
            self.info.uptime = now - self._start_time
            self.info.active_tasks = len(self._active_tasks_map)
            
            # Estimate simulated/runtime CPU and memory usage
            active_ratio = (self.info.active_tasks / self.max_tasks) if self.max_tasks > 0 else 0.0
            self.info.cpu_utilization = min(95.0, round(10.0 + (active_ratio * 40.0), 2))
            self.info.memory_utilization = min(90.0, round(15.0 + (active_ratio * 30.0), 2))

            if self.heartbeat_callback:
                try:
                    self.heartbeat_callback(
                        self.node_id,
                        self.info.cpu_utilization,
                        self.info.memory_utilization,
                        self.info.active_tasks,
                        self.info.latency_ms,
                        {"capabilities": self.capabilities, "uptime": self.info.uptime},
                    )
                except Exception as e:
                    logger.warning("Worker %s heartbeat send failed: %s", self.node_id, e)

    def execute_task(self, task: TaskSpec) -> Dict[str, Any]:
        """
        Executes a single task synchronously, recording logs, metrics, generated artifacts, and results.
        """
        start_time = time.time()
        task_id = task.task_id
        logs: List[str] = [f"[{self.node_id}] Started execution of task {task_id}: {task.title}"]
        logger.info("Worker %s executing task %s (%s)", self.node_id, task_id, task.title)

        with self._lock:
            self._active_tasks_map[task_id] = task
            self.info.active_tasks = len(self._active_tasks_map)

        result_payload: Dict[str, Any] = {}
        generated_artifacts: List[str] = []
        success = True
        error_msg: Optional[str] = None

        try:
            # 1. Determine execution capability
            caps = task.required_capabilities or ["general"]
            primary_cap = caps[0].lower() if caps else "general"

            # 2. Check if a custom handler is registered
            handler = self.task_handlers.get(primary_cap) or self.task_handlers.get("general")
            if handler:
                logs.append(f"Dispatching to registered handler for capability '{primary_cap}'")
                result_payload = handler(task, self)
            else:
                # 3. Default autonomous engineering execution
                result_payload = self._default_task_execution(task, logs, generated_artifacts)

            logs.append(f"[{self.node_id}] Task {task_id} completed successfully in {(time.time() - start_time)*1000.0:.2f}ms")

        except Exception as e:
            success = False
            error_msg = f"{type(e).__name__}: {str(e)}"
            tb = traceback.format_exc()
            logs.append(f"[{self.node_id}] Task {task_id} failed with error: {error_msg}\n{tb}")
            logger.error("Worker %s failed task %s: %s", self.node_id, task_id, error_msg)

        finally:
            with self._lock:
                self._active_tasks_map.pop(task_id, None)
                self.info.active_tasks = len(self._active_tasks_map)
                if success:
                    self.info.total_tasks_completed += 1
                else:
                    self.info.total_tasks_failed += 1

            duration = time.time() - start_time
            task.logs.extend(logs)

            # 4. Report back to queue
            if self.queue:
                if success:
                    self.queue.ack(task_id=task_id, result=result_payload, artifacts=generated_artifacts)
                else:
                    self.queue.nack(task_id=task_id, error=error_msg or "Unknown error", retry=True)

        return {
            "task_id": task_id,
            "worker_id": self.node_id,
            "success": success,
            "duration": duration,
            "result": result_payload,
            "artifacts": generated_artifacts,
            "error_message": error_msg,
            "logs": logs,
        }

    def _default_task_execution(
        self,
        task: TaskSpec,
        logs: List[str],
        generated_artifacts: List[str],
    ) -> Dict[str, Any]:
        """
        Built-in execution engine for standard distributed engineering tasks.
        """
        payload = task.payload or {}
        task_type = payload.get("task_type", "engineering")

        # Simulate or perform file generation / modification
        file_path = payload.get("target_file", f"src/{task.task_id.lower()}.py")
        code_content = payload.get("code_content", f"# Auto-generated by {self.node_id}\n# Task: {task.title}\n")

        # Store generated artifact in CAS
        art_id = f"art_{task.task_id}"
        self.artifact_sync.store_artifact(
            artifact_id=art_id,
            relative_path=file_path,
            content=code_content,
            content_type="text/x-python",
            metadata={"task_id": task.task_id, "worker_id": self.node_id},
        )
        generated_artifacts.append(art_id)
        logs.append(f"Generated and stored artifact '{art_id}' at path '{file_path}'")

        # Update distributed memory if keys are specified
        if "memory_updates" in payload:
            for k, v in payload["memory_updates"].items():
                self.memory.set(k, v, source_node=self.node_id)
                logs.append(f"Updated cluster memory key '{k}'")

        return {
            "status": "COMPLETED",
            "output_file": file_path,
            "bytes_written": len(code_content.encode("utf-8")),
            "worker_role": self.info.role.value,
        }

    def start(self) -> None:
        """Starts worker processing threads and heartbeat sender loop."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._start_time = time.time()

            # Heartbeat thread
            self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True, name=f"HB-{self.node_id}")
            self._heartbeat_thread.start()

            # Worker execution polling threads
            for i in range(max(1, self.max_tasks)):
                t = threading.Thread(target=self._worker_loop, daemon=True, name=f"Exec-{self.node_id}-{i}")
                t.start()
                self._execution_threads.append(t)

            logger.info("Started WorkerNode %s (capabilities: %s, max_tasks: %d)", self.node_id, self.capabilities, self.max_tasks)

    def stop(self) -> None:
        """Stops worker execution and terminates polling loops."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self.info.status = NodeStatus.OFFLINE
            logger.info("Stopping WorkerNode %s", self.node_id)

    def _heartbeat_loop(self) -> None:
        while self._running:
            try:
                self.send_heartbeat()
            except Exception as e:
                logger.error("Worker %s heartbeat loop error: %s", self.node_id, e)
            time.sleep(self.config.heartbeat_interval)

    def _worker_loop(self) -> None:
        while self._running:
            if not self.queue:
                time.sleep(0.1)
                continue

            try:
                # Poll queue for matching task
                task = self.queue.dequeue(
                    worker_id=self.node_id,
                    capabilities=self.capabilities,
                    timeout=0.2,
                )
                if task:
                    self.execute_task(task)
            except Exception as e:
                if self._running:
                    logger.error("Worker %s loop execution error: %s", self.node_id, e)
                time.sleep(0.1)
