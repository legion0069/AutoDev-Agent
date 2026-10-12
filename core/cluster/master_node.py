"""
master_node.py - Authoritative Cluster Master & Coordination Engine for AutoDev (v2.9)

Supervises the distributed cluster, manages node membership, runs the leader election protocol,
schedules and dispatches DAG tasks, handles worker failover, coordinates distributed locking
and memory, drives periodic atomic checkpointing, and produces cluster telemetry.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

from core.cluster.artifact_sync import ArtifactSyncManager
from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_metrics import ClusterMetricsManager
from core.cluster.cluster_state import (
    ClusterJob,
    ClusterState,
    DistributedClusterMemory,
    JobStatus,
    NodeInfo,
    NodeRole,
    NodeStatus,
    TaskExecutionStatus,
    TaskSpec,
)
from core.cluster.distributed_checkpoint import DistributedCheckpointManager
from core.cluster.distributed_lock_manager import DistributedLockManager
from core.cluster.distributed_queue import DistributedQueue
from core.cluster.distributed_scheduler import DistributedScheduler
from core.cluster.heartbeat_manager import HeartbeatManager
from core.cluster.leader_election import LeaderElection
from core.cluster.node_registry import NodeRegistry

logger = logging.getLogger("AutoDev.Cluster.Master")


class MasterNode:
    """
    Authoritative coordinator for the AutoDev distributed cluster.
    """

    def __init__(
        self,
        node_id: str = "master-node-01",
        hostname: str = "localhost",
        ip: str = "127.0.0.1",
        port: int = 9500,
        config: Optional[ClusterConfig] = None,
    ) -> None:
        self.node_id = node_id
        self.hostname = hostname
        self.ip = ip
        self.port = port
        self.config = config or ClusterConfig()

        # Core Cluster Subsystems
        self.registry = NodeRegistry()
        self.queue = DistributedQueue(config=self.config)
        self.lock_manager = DistributedLockManager(config=self.config)
        self.artifact_sync = ArtifactSyncManager(node_id=node_id, config=self.config)
        self.memory = DistributedClusterMemory(node_id=node_id)
        self.scheduler = DistributedScheduler(registry=self.registry, config=self.config)
        self.metrics = ClusterMetricsManager(registry=self.registry, config=self.config)
        self.checkpoint_manager = DistributedCheckpointManager(config=self.config)

        # High Availability & Election
        self.election = LeaderElection(
            local_node_id=self.node_id,
            registry=self.registry,
            config=self.config,
            on_leader_changed=self._on_leader_changed,
        )

        # Heartbeat Failure Detector
        self.heartbeat_manager = HeartbeatManager(
            registry=self.registry,
            config=self.config,
            on_node_offline=self._on_node_offline,
            on_node_degraded=self._on_node_degraded,
            on_node_recovered=self._on_node_recovered,
        )

        # Register Self in Node Registry
        self.info = NodeInfo(
            node_id=self.node_id,
            hostname=self.hostname,
            ip=self.ip,
            port=self.port,
            role=NodeRole.MASTER,
            status=NodeStatus.HEALTHY,
            capabilities=["coordination", "scheduling", "consensus", "general"],
            max_tasks=0,
            active_tasks=0,
            health_score=100.0,
        )
        self.registry.register_node(self.info)

        # Master Jobs Repository
        self._jobs: Dict[str, ClusterJob] = {}
        self._lock = threading.RLock()
        self._running = False
        self._coordination_thread: Optional[threading.Thread] = None
        self._checkpoint_thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def is_leader(self) -> bool:
        return self.election.is_leader(self.node_id)

    def start(self, auto_elect: bool = True) -> None:
        """
        Starts master coordination loops, election, and heartbeat supervisor.
        """
        with self._lock:
            if self._running:
                return
            self._running = True

            # Attempt to auto-restore from previous checkpoint if configured
            if self.config.enable_auto_recovery:
                latest_chk = self.checkpoint_manager.load_latest_checkpoint()
                if latest_chk:
                    self.checkpoint_manager.restore_into_subsystems(
                        checkpoint_data=latest_chk,
                        registry=self.registry,
                        queue=self.queue,
                        memory=self.memory,
                        lock_manager=self.lock_manager,
                    )
                    logger.info("Restored master %s from checkpoint", self.node_id)

            # Ensure master node info registered
            self.registry.register_node(self.info)

            # Run initial election if requested
            if auto_elect:
                self.election.start_election(reason="master_startup")

            # Start Heartbeat manager
            self.heartbeat_manager.start()

            # Start Coordination & Rebalancing loop
            self._coordination_thread = threading.Thread(target=self._coordination_loop, daemon=True, name=f"MasterCoord-{self.node_id}")
            self._coordination_thread.start()

            # Start Periodic Checkpointing loop
            self._checkpoint_thread = threading.Thread(target=self._checkpoint_loop, daemon=True, name=f"MasterChk-{self.node_id}")
            self._checkpoint_thread.start()

            logger.info("MasterNode %s started successfully (Leader: %s, Epoch: %d)", self.node_id, self.election.current_leader, self.election.current_epoch)

    def stop(self) -> None:
        """
        Stops all master coordination threads and services.
        """
        with self._lock:
            if not self._running:
                return
            self._running = False
            self.heartbeat_manager.stop()
            self.info.status = NodeStatus.OFFLINE
            logger.info("MasterNode %s stopped", self.node_id)

    # -------------------------------------------------------------------------
    # Job Management API
    # -------------------------------------------------------------------------

    def submit_job(
        self,
        title: str,
        tasks: List[TaskSpec],
        description: str = "",
        job_id: Optional[str] = None,
    ) -> str:
        """
        Submits a distributed multi-task job, builds dependency DAG, and enqueues initial ready tasks.
        """
        with self._lock:
            j_id = job_id or f"job_{int(time.time()*1000)}_{len(self._jobs)+1}"
            task_dict: Dict[str, TaskSpec] = {}

            for t in tasks:
                t.job_id = j_id
                task_dict[t.task_id] = copy.deepcopy(t)

            job = ClusterJob(
                job_id=j_id,
                title=title,
                description=description,
                status=JobStatus.RUNNING,
                tasks=task_dict,
                created_at=time.time(),
            )
            self._jobs[j_id] = job

            # Build dependency DAG to validate for cycles
            try:
                self.scheduler.build_dependency_dag(tasks)
            except ValueError as e:
                job.status = JobStatus.FAILED
                job.error_message = f"Invalid job DAG: {str(e)}"
                logger.error("Job %s submission rejected: %s", j_id, e)
                return j_id

            # Enqueue tasks into reliable distributed queue
            self.queue.enqueue_batch(tasks)
            logger.info("Submitted cluster job %s ('%s') with %d tasks", j_id, title, len(tasks))
            return j_id

    def cancel_job(self, job_id: str) -> bool:
        """Cancels an active job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.is_finished:
                return False
            job.status = JobStatus.CANCELLED
            job.completed_at = time.time()
            logger.info("Cancelled cluster job %s", job_id)
            return True

    def get_job(self, job_id: str) -> Optional[ClusterJob]:
        """Retrieves snapshot of job status and task execution progress."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            
            # Sync task statuses from queue
            for t_id, t in list(job.tasks.items()):
                latest_task = self.queue.get_task(t_id)
                if latest_task:
                    job.tasks[t_id] = latest_task

            # Check if all tasks finished
            if not job.is_finished and job.tasks:
                all_completed = all(t.status == TaskExecutionStatus.COMPLETED for t in job.tasks.values())
                any_failed = any(t.status in (TaskExecutionStatus.FAILED, TaskExecutionStatus.DEAD_LETTER) for t in job.tasks.values())

                if all_completed:
                    job.status = JobStatus.COMPLETED
                    job.completed_at = time.time()
                    self.metrics.record_task_completed()
                elif any_failed:
                    # If any task in DLQ, mark job failed
                    if any(t.status == TaskExecutionStatus.DEAD_LETTER for t in job.tasks.values()):
                        job.status = JobStatus.FAILED
                        job.completed_at = time.time()

            return copy.deepcopy(job)

    def wait_for_job(self, job_id: str, timeout: float = 30.0, poll_interval: float = 0.1) -> ClusterJob:
        """
        Synchronously blocks until job reaches terminal state or timeout occurs.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self.get_job(job_id)
            if job and job.is_finished:
                return job
            time.sleep(poll_interval)

        job = self.get_job(job_id)
        if job:
            return job
        raise TimeoutError(f"Job {job_id} timed out after {timeout} seconds")

    # -------------------------------------------------------------------------
    # Failover and Health Event Handlers
    # -------------------------------------------------------------------------

    def _on_node_offline(self, node_id: str, node: NodeInfo) -> None:
        """
        Handles worker failure by reclaiming and reassigning in-flight tasks.
        """
        logger.warning("Node %s went OFFLINE. Triggering task failover.", node_id)
        self.metrics.record_heartbeat_failure()

        # Check if leader failed
        if self.election.current_leader == node_id:
            self.election.handle_leader_failure(node_id)

        # Sweep and reclaim in-flight tasks from queue
        reclaimed = self.queue.reclaim_timed_out_tasks()
        logger.info("Reclaimed %d tasks due to node failure", len(reclaimed))

    def _on_node_degraded(self, node_id: str, node: NodeInfo) -> None:
        logger.info("Node %s is DEGRADED (Health: %.1f%%)", node_id, node.health_score)

    def _on_node_recovered(self, node_id: str, node: NodeInfo) -> None:
        logger.info("Node %s RECOVERED back to cluster", node_id)

    def _on_leader_changed(self, new_leader: str, epoch: int) -> None:
        logger.info("Leader changed to %s for Epoch %d", new_leader, epoch)

    # -------------------------------------------------------------------------
    # Background Coordination & Checkpointing
    # -------------------------------------------------------------------------

    def _coordination_loop(self) -> None:
        while self._running:
            try:
                # 0. Refresh Master's own heartbeat
                self.heartbeat_manager.record_node_heartbeat(
                    node_id=self.node_id,
                    cpu_utilization=5.0,
                    memory_utilization=10.0,
                    active_tasks=0,
                )

                # 1. Capture Telemetry Snapshot
                self.metrics.capture_snapshot(
                    queue_depth=self.queue.get_queue_depth(),
                    inflight_tasks=self.queue.get_inflight_count(),
                    dead_letter_tasks=len(self.queue.get_dead_letter_tasks()),
                )

                # 2. Sweep expired locks
                self.lock_manager.sweep_expired_leases()

                # 3. Sweep expired queue leases
                self.queue.reclaim_timed_out_tasks()

                # 4. Continuous Rebalancing / Work-stealing
                inflight_map = {t.task_id: t for t in self.queue.get_dead_letter_tasks()}
                self.scheduler.rebalance_cluster(inflight_map)

            except Exception as e:
                if self._running:
                    logger.error("Error in master coordination loop: %s", e)

            time.sleep(1.0)

    def _checkpoint_loop(self) -> None:
        while self._running:
            time.sleep(self.config.checkpoint_interval)
            if not self._running:
                break
            try:
                self.checkpoint_manager.create_checkpoint(
                    epoch=self.election.current_epoch,
                    leader_id=self.election.current_leader or self.node_id,
                    registry=self.registry,
                    queue=self.queue,
                    memory=self.memory,
                    lock_manager=self.lock_manager,
                    scheduler_stats=self.scheduler.get_scheduler_stats(),
                )
            except Exception as e:
                logger.error("Periodic checkpoint creation error: %s", e)

    def get_cluster_status(self) -> Dict[str, Any]:
        """Returns comprehensive cluster health and operational status summary."""
        with self._lock:
            all_nodes = self.registry.get_all_nodes()
            return {
                "cluster_name": self.config.cluster_name,
                "leader_id": self.election.current_leader,
                "epoch": self.election.current_epoch,
                "is_leader": self.is_leader,
                "node_count": len(all_nodes),
                "healthy_workers": len(self.registry.get_healthy_workers()),
                "queue_depth": self.queue.get_queue_depth(),
                "inflight_tasks": self.queue.get_inflight_count(),
                "active_jobs": len([j for j in self._jobs.values() if not j.is_finished]),
                "completed_jobs": len([j for j in self._jobs.values() if j.status == JobStatus.COMPLETED]),
                "telemetry": self.metrics.get_latest_metrics(),
            }
