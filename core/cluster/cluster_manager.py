"""
cluster_manager.py - High-Level Cluster Supervisor & Orchestrator for AutoDev (v2.9)

Provides the primary user-facing API for initializing, managing, submitting distributed workloads,
and simulating failover across the AutoDev distributed software engineering cluster.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import (
    ClusterJob,
    JobStatus,
    NodeInfo,
    NodeRole,
    NodeStatus,
    TaskExecutionStatus,
    TaskSpec,
)
from core.cluster.master_node import MasterNode
from core.cluster.worker_node import DEFAULT_ENGINEERING_CAPABILITIES, WorkerNode

logger = logging.getLogger("AutoDev.Cluster.Manager")


class ClusterManager:
    """
    Unified cluster manager supervising the AutoDev Distributed Cluster.
    Supports in-process fleet orchestration, multi-task parallel job dispatch,
    automatic worker failover, and comprehensive cluster telemetry reporting.
    """

    def __init__(self, config: Optional[ClusterConfig] = None, storage_dir: Optional[str] = None) -> None:
        self.config = config or ClusterConfig()
        if storage_dir:
            self.config.storage_dir = storage_dir
            self.config.checkpoint_storage_dir = f"{storage_dir}/checkpoints"

        self.master = MasterNode(
            node_id=self.config.master_id,
            hostname=self.config.master_host,
            ip="127.0.0.1",
            port=self.config.master_port,
            config=self.config,
        )

        self.workers: Dict[str, WorkerNode] = {}
        self.backup_masters: Dict[str, MasterNode] = {}
        self._lock = threading.RLock()
        self._initialized = False

    def bootstrap_cluster(self, num_workers: int = 4, custom_roles: Optional[List[List[str]]] = None) -> None:
        """
        Initializes and starts the master node and specified number of worker nodes.
        """
        with self._lock:
            if self._initialized:
                return

            # 1. Start Master Node
            self.master.start(auto_elect=True)

            # 2. Spawn and Register Backup Masters if configured
            for b_id in self.config.backup_masters:
                bm = MasterNode(node_id=b_id, config=self.config)
                bm.info.role = NodeRole.BACKUP_MASTER
                self.master.registry.register_node(bm.info)
                self.backup_masters[b_id] = bm

            # 3. Spawn and Register Worker Nodes
            role_definitions = custom_roles or [
                ["planning", "architecture", "general"],
                ["coding", "backend", "general"],
                ["testing", "qa", "general"],
                ["security", "audit", "general"],
                ["coding", "frontend", "general"],
                ["documentation", "general"],
                ["packaging", "release", "general"],
                ["performance", "optimization", "general"],
            ]

            for i in range(num_workers):
                w_id = f"worker-node-{i+1:02d}"
                caps = role_definitions[i % len(role_definitions)]
                self.add_worker(node_id=w_id, capabilities=caps)

            self._initialized = True
            logger.info(
                "Successfully bootstrapped cluster '%s' with 1 Master, %d Backup Masters, and %d Workers",
                self.config.cluster_name, len(self.backup_masters), len(self.workers)
            )

    def add_worker(
        self,
        node_id: str,
        capabilities: Optional[List[str]] = None,
        max_tasks: int = 4,
    ) -> WorkerNode:
        """
        Instantiates, registers, and starts a new cluster worker node.
        """
        with self._lock:
            caps = capabilities or list(DEFAULT_ENGINEERING_CAPABILITIES)
            worker = WorkerNode(
                node_id=node_id,
                capabilities=caps,
                max_tasks=max_tasks,
                config=self.config,
                queue=self.master.queue,
                lock_manager=self.master.lock_manager,
                artifact_sync=self.master.artifact_sync,
                memory=self.master.memory,
                heartbeat_callback=self._worker_heartbeat_dispatch,
            )

            # Register in master node registry
            self.master.registry.register_node(worker.info)
            worker.start()
            self.workers[node_id] = worker
            logger.info("Added worker %s with capabilities %s to cluster", node_id, caps)
            return worker

    def remove_worker(self, node_id: str) -> bool:
        """
        Stops and deregisters a worker node from the cluster.
        """
        with self._lock:
            worker = self.workers.pop(node_id, None)
            if worker:
                worker.stop()
                self.master.registry.deregister_node(node_id)
                logger.info("Removed worker %s from cluster", node_id)
                return True
            return False

    def _worker_heartbeat_dispatch(
        self,
        node_id: str,
        cpu_utilization: float,
        memory_utilization: float,
        active_tasks: int,
        latency_ms: float,
        metadata: Dict[str, Any],
    ) -> None:
        """Routes worker heartbeat to master HeartbeatManager."""
        self.master.heartbeat_manager.record_node_heartbeat(
            node_id=node_id,
            cpu_utilization=cpu_utilization,
            memory_utilization=memory_utilization,
            active_tasks=active_tasks,
            latency_ms=latency_ms,
            metadata=metadata,
        )

    # -------------------------------------------------------------------------
    # Workload Execution & Job Submission
    # -------------------------------------------------------------------------

    def submit_job(self, title: str, tasks: List[TaskSpec], description: str = "") -> str:
        """Submits multi-task job to cluster."""
        if not self._initialized:
            self.bootstrap_cluster()
        return self.master.submit_job(title=title, tasks=tasks, description=description)

    def execute_job_sync(self, title: str, tasks: List[TaskSpec], timeout: float = 30.0) -> ClusterJob:
        """Submits job and synchronously awaits its completion."""
        job_id = self.submit_job(title=title, tasks=tasks)
        return self.master.wait_for_job(job_id=job_id, timeout=timeout)

    def execute_cluster(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        num_tasks: int = 4,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        High-level cluster execution interface.
        Decomposes prompt/context into distributed engineering tasks across workers and executes them.
        """
        if not self._initialized:
            self.bootstrap_cluster()

        ctx = context or {}
        tasks: List[TaskSpec] = []
        now = time.time()

        task_defs = [
            ("PLAN", "System Architecture & Planning", ["planning", "architecture"], 10, []),
            ("CODE", "Core Backend & Frontend Implementation", ["coding", "backend"], 20, ["PLAN"]),
            ("TEST", "Automated Testing & QA Verification", ["testing", "qa"], 30, ["CODE"]),
            ("SEC", "Security Audit & Vulnerability Assessment", ["security", "audit"], 40, ["CODE"]),
        ]

        task_id_by_prefix: Dict[str, str] = {}
        for prefix, title, caps, prio, deps in task_defs[:num_tasks]:
            t_id = f"task_{prefix.lower()}_{int(now)}_{len(tasks)+1}"
            task_id_by_prefix[prefix] = t_id
            mapped_deps = [task_id_by_prefix[d] for d in deps if d in task_id_by_prefix]

            tasks.append(TaskSpec(
                task_id=t_id,
                title=f"{title}: {prompt[:40]}...",
                description=f"AutoDev Cluster execution for: {prompt}",
                required_capabilities=caps,
                priority=prio,
                dependencies=mapped_deps,
                payload={
                    "prompt": prompt,
                    "target_file": f"src/{prefix.lower()}_module.py",
                    "code_content": f"# AutoDev Cluster Module: {title}\n# Prompt: {prompt}\n\ndef execute():\n    return '{title} OK'\n",
                    "memory_updates": {f"cluster_task_{prefix.lower()}": "COMPLETED"},
                }
            ))

        job = self.execute_job_sync(title=f"Cluster Execution: {prompt[:30]}", tasks=tasks, timeout=timeout)
        telemetry = self.master.get_cluster_status()

        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "tasks_count": len(tasks),
            "progress_percentage": job.progress_percentage,
            "cluster_telemetry": telemetry,
            "mermaid_topology": self.master.metrics.generate_cluster_topology_diagram(leader_id=self.master.election.current_leader or self.config.master_id),
        }

    def execute_remote(self, task: TaskSpec, worker_id: str) -> Dict[str, Any]:
        """Directly dispatches a single task to a specific worker node."""
        if not self._initialized:
            self.bootstrap_cluster()

        worker = self.workers.get(worker_id)
        if not worker:
            raise ValueError(f"Worker {worker_id} is not registered in cluster")

        task.assigned_worker_id = worker_id
        task.status = TaskExecutionStatus.RUNNING
        return worker.execute_task(task)

    def query_cluster(self) -> Dict[str, Any]:
        """Returns comprehensive cluster health, topology, and performance report."""
        if not self._initialized:
            self.bootstrap_cluster()
        return self.master.get_cluster_status()

    # -------------------------------------------------------------------------
    # Fault Simulation & Failover
    # -------------------------------------------------------------------------

    def simulate_worker_failure(self, worker_id: str) -> bool:
        """Simulates worker node crash by stopping it and marking it OFFLINE."""
        with self._lock:
            worker = self.workers.get(worker_id)
            if not worker:
                return False
            worker.stop()
            self.master.heartbeat_manager.registry.update_node_status(worker_id, NodeStatus.OFFLINE)
            self.master._on_node_offline(worker_id, worker.info)
            logger.warning("Simulated worker failure for %s", worker_id)
            return True

    def simulate_master_failover(self) -> str:
        """
        Simulates master failure by stopping current master and triggering election among backup masters.
        """
        with self._lock:
            old_leader = self.master.election.current_leader or self.config.master_id
            logger.warning("Simulating master failover for leader %s", old_leader)
            
            # Step down or mark master offline in registry
            self.master.election.step_down(reason="simulated_failover")
            self.master.registry.update_node_status(old_leader, NodeStatus.OFFLINE)

            # Trigger election on backup master
            if self.backup_masters:
                first_backup = list(self.backup_masters.values())[0]
                # Sync registry state to backup master
                first_backup.registry.import_state(self.master.registry.export_state())
                new_leader = first_backup.election.start_election(reason="simulated_master_failover")
                first_backup.start(auto_elect=False)
                logger.info("Backup master %s promoted to LEADER", new_leader)
                return str(new_leader)
            else:
                new_leader = self.master.election.start_election(reason="simulated_failover_reelection")
                return str(new_leader)

    def shutdown(self) -> None:
        """Shuts down all workers, backup masters, and master node."""
        with self._lock:
            for w in self.workers.values():
                w.stop()
            for bm in self.backup_masters.values():
                bm.stop()
            self.master.stop()
            self._initialized = False
            logger.info("ClusterManager completely shutdown")

    def generate_full_cluster_report(self) -> str:
        """Produces comprehensive markdown cluster health & architectural report with all Mermaid diagrams."""
        status = self.query_cluster()
        tel = status.get("telemetry", {})

        report = f"""# AutoDev Distributed Cluster Execution Report (v2.9)
**Cluster Name**: `{self.config.cluster_name}`  
**Active Leader**: `{status.get('leader_id')}` (Epoch `{status.get('epoch')}`)  
**Total Nodes**: `{status.get('node_count')}` (`{status.get('healthy_workers')}` Healthy Workers)  
**Queue Depth**: `{status.get('queue_depth')}` | **In-Flight Tasks**: `{status.get('inflight_tasks')}`  

## 1. Cluster Operational Telemetry
- **CPU Aggregate Utilization**: `{tel.get('aggregate_cpu_utilization', 0.0)}%`
- **RAM Aggregate Utilization**: `{tel.get('aggregate_memory_utilization', 0.0)}%`
- **Average Node Health Score**: `{tel.get('avg_node_health_score', 100.0)} / 100.0`
- **Network Latency (Avg)**: `{tel.get('avg_latency_ms', 0.0)}ms`
- **Throughput**: `{tel.get('task_throughput_per_sec', 0.0)} tasks/sec`
- **Parallel Efficiency**: `{tel.get('parallel_efficiency', 1.0) * 100.0:.1f}%`
- **Scheduler Efficiency**: `{tel.get('scheduler_efficiency', 1.0) * 100.0:.1f}%`

## 2. Cluster Topology
{self.master.metrics.generate_cluster_topology_diagram(leader_id=status.get('leader_id', 'master-node-01'))}

## 3. Distributed Execution Lifecycle
{self.master.metrics.generate_execution_lifecycle_diagram()}

## 4. Leader Election & High Availability
{self.master.metrics.generate_leader_election_diagram()}

## 5. Heartbeat & Health State Transitions
{self.master.metrics.generate_heartbeat_flow_diagram()}

## 6. Distributed Task Scheduling Pipeline
{self.master.metrics.generate_task_scheduling_diagram()}

## 7. Artifact Synchronization & CAS
{self.master.metrics.generate_artifact_sync_diagram()}

## 8. Atomic Checkpoint Recovery
{self.master.metrics.generate_checkpoint_recovery_diagram()}
"""
        return report
