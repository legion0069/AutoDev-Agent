"""
cluster_metrics.py - Cluster Telemetry, Observability & Diagram Generators for AutoDev (v2.9)

Aggregates real-time and historical cluster metrics (CPU/RAM, queue depth, throughput, latency,
worker utilization, parallel efficiency, scheduler metrics) and generates deterministic Mermaid diagrams.
"""

from __future__ import annotations

import copy
import logging
import math
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import NodeInfo, NodeRole, NodeStatus, TaskExecutionStatus, TaskSpec
from core.cluster.node_registry import NodeRegistry

logger = logging.getLogger("AutoDev.Cluster.Metrics")


@dataclass
class ClusterTelemetrySnapshot:
    """
    Point-in-time multi-dimensional telemetry snapshot of cluster health & performance.
    """
    timestamp: float
    total_nodes: int
    healthy_workers: int
    degraded_workers: int
    offline_nodes: int
    aggregate_cpu_utilization: float
    aggregate_memory_utilization: float
    avg_node_health_score: float
    avg_latency_ms: float
    queue_depth: int
    inflight_tasks: int
    completed_tasks: int
    failed_tasks: int
    dead_letter_tasks: int
    task_throughput_per_sec: float
    worker_utilization_ratio: float
    parallel_efficiency: float
    scheduler_efficiency: float


class ClusterMetricsManager:
    """
    Cluster observability and telemetry engine.
    Maintains historical time-series window and generates architectural Mermaid diagrams.
    """

    def __init__(self, registry: NodeRegistry, config: Optional[ClusterConfig] = None) -> None:
        self.registry = registry
        self.config = config or ClusterConfig()
        self._lock = threading.RLock()
        self._history: List[ClusterTelemetrySnapshot] = []
        self._task_completion_times: List[float] = []
        self._heartbeat_failures_count: int = 0

    def record_heartbeat_failure(self) -> None:
        with self._lock:
            self._heartbeat_failures_count += 1

    def record_task_completed(self) -> None:
        with self._lock:
            self._task_completion_times.append(time.time())
            if len(self._task_completion_times) > 1000:
                self._task_completion_times = self._task_completion_times[-1000:]

    def capture_snapshot(
        self,
        queue_depth: int = 0,
        inflight_tasks: int = 0,
        dead_letter_tasks: int = 0,
    ) -> ClusterTelemetrySnapshot:
        """
        Gathers current metrics across registered nodes and generates a telemetry snapshot.
        """
        with self._lock:
            now = time.time()
            all_nodes = self.registry.get_all_nodes()
            workers = [n for n in all_nodes if n.role == NodeRole.WORKER]

            total_nodes = len(all_nodes)
            healthy_workers = sum(1 for n in workers if n.status == NodeStatus.HEALTHY)
            degraded_workers = sum(1 for n in workers if n.status == NodeStatus.DEGRADED)
            offline_nodes = sum(1 for n in all_nodes if n.status == NodeStatus.OFFLINE)

            total_cpu = sum(n.cpu_utilization for n in all_nodes)
            total_mem = sum(n.memory_utilization for n in all_nodes)
            total_health = sum(n.health_score for n in all_nodes)
            total_lat = sum(n.latency_ms for n in all_nodes)
            total_completed = sum(n.total_tasks_completed for n in all_nodes)
            total_failed = sum(n.total_tasks_failed for n in all_nodes)

            avg_cpu = (total_cpu / total_nodes) if total_nodes > 0 else 0.0
            avg_mem = (total_mem / total_nodes) if total_nodes > 0 else 0.0
            avg_health = (total_health / total_nodes) if total_nodes > 0 else 100.0
            avg_lat = (total_lat / total_nodes) if total_nodes > 0 else 0.0

            # Compute throughput over past 10 seconds
            cutoff = now - 10.0
            recent_completions = sum(1 for t in self._task_completion_times if t >= cutoff)
            throughput = recent_completions / 10.0

            # Worker utilization & parallel efficiency
            total_capacity = sum(w.max_tasks for w in workers)
            total_active = sum(w.active_tasks for w in workers)
            utilization = (total_active / total_capacity) if total_capacity > 0 else 0.0

            # Parallel efficiency: ratio of active workers executing simultaneously
            active_worker_count = sum(1 for w in workers if w.active_tasks > 0)
            parallel_eff = (active_worker_count / len(workers)) if workers else 1.0

            # Scheduler efficiency: penalty if tasks waiting while healthy capacity exists
            sched_eff = 1.0
            if queue_depth > 0 and (total_capacity - total_active) > 0:
                sched_eff = max(0.5, 1.0 - (queue_depth / (total_capacity + 1.0)))

            snap = ClusterTelemetrySnapshot(
                timestamp=now,
                total_nodes=total_nodes,
                healthy_workers=healthy_workers,
                degraded_workers=degraded_workers,
                offline_nodes=offline_nodes,
                aggregate_cpu_utilization=round(avg_cpu, 2),
                aggregate_memory_utilization=round(avg_mem, 2),
                avg_node_health_score=round(avg_health, 2),
                avg_latency_ms=round(avg_lat, 2),
                queue_depth=queue_depth,
                inflight_tasks=inflight_tasks,
                completed_tasks=total_completed,
                failed_tasks=total_failed,
                dead_letter_tasks=dead_letter_tasks,
                task_throughput_per_sec=round(throughput, 2),
                worker_utilization_ratio=round(utilization, 3),
                parallel_efficiency=round(parallel_eff, 3),
                scheduler_efficiency=round(sched_eff, 3),
            )

            self._history.append(snap)
            # Retain sliding window
            if len(self._history) > 600:
                self._history = self._history[-600:]

            return snap

    def get_latest_metrics(self) -> Dict[str, Any]:
        with self._lock:
            if not self._history:
                self.capture_snapshot()
            return asdict(self._history[-1])

    def get_summary_report(self) -> Dict[str, Any]:
        with self._lock:
            latest = self.get_latest_metrics()
            all_nodes = self.registry.get_all_nodes()
            return {
                "cluster_name": self.config.cluster_name,
                "latest_snapshot": latest,
                "node_count": len(all_nodes),
                "nodes": [n.to_dict() for n in all_nodes],
                "heartbeat_failures": self._heartbeat_failures_count,
            }

    # -------------------------------------------------------------------------
    # Deterministic Mermaid Diagram Generators
    # -------------------------------------------------------------------------

    def generate_cluster_topology_diagram(self, leader_id: str = "master-node-01") -> str:
        """Generates Mermaid diagram representing live cluster topology."""
        nodes = self.registry.get_all_nodes()
        lines = [
            "```mermaid",
            "graph TD",
            "    subgraph Control_Plane [Control Plane & High Availability]",
        ]

        masters = [n for n in nodes if n.role in (NodeRole.MASTER, NodeRole.BACKUP_MASTER)]
        workers = [n for n in nodes if n.role == NodeRole.WORKER]
        observers = [n for n in nodes if n.role == NodeRole.OBSERVER]

        for m in masters:
            is_active = (m.node_id == leader_id)
            tag = "Active Leader" if is_active else "Backup Master"
            style_class = "style " + m.node_id.replace("-", "_") + " fill:#059669,stroke:#10b981,color:#fff,stroke-width:2px" if is_active else "style " + m.node_id.replace("-", "_") + " fill:#1e293b,stroke:#64748b,color:#cbd5e1"
            lines.append(f"        {m.node_id.replace('-', '_')}[\"{m.node_id}<br/>({tag})<br/>Health: {m.health_score}%\"]")
            lines.append(f"        {style_class}")

        lines.append("    end")
        lines.append("    subgraph Worker_Fleet [Distributed Worker Fleet]")

        for w in workers:
            st = w.status.value
            fill = "#0f766e" if st == "HEALTHY" else ("#b45309" if st == "DEGRADED" else "#b91c1c")
            lines.append(f"        {w.node_id.replace('-', '_')}[\"{w.node_id}<br/>Caps: {', '.join(w.capabilities[:2])}<br/>Load: {w.active_tasks}/{w.max_tasks}\"]")
            lines.append(f"        style {w.node_id.replace('-', '_')} fill:{fill},stroke:#cbd5e1,color:#fff")

        lines.append("    end")

        # Connect leader to workers
        lead_clean = leader_id.replace("-", "_")
        for w in workers:
            w_clean = w.node_id.replace("-", "_")
            lines.append(f"    {lead_clean} -->|Dispatch & Heartbeat| {w_clean}")

        lines.append("```")
        return "\n".join(lines)

    def generate_leader_election_diagram(self) -> str:
        """Generates Mermaid sequence diagram of deterministic leader election & backup failover."""
        return """```mermaid
sequenceDiagram
    autonumber
    participant Master1 as Master Node 01 (Leader)
    participant HB as Heartbeat Manager
    participant Backup as Backup Master (Candidate)
    participant Registry as Node Registry
    participant Cluster as Worker Fleet

    Note over Master1: Master Node 01 Crashes / Network Timeout
    HB->>Master1: Periodic Probe (Ping)
    Master1--xHB: Timeout (No ACK > worker_timeout)
    HB->>Registry: Mark Node 01 OFFLINE
    HB->>Backup: Trigger Leader Failure Event
    Note over Backup: Start Deterministic Election (Term/Epoch N+1)
    Backup->>Registry: Query Active Eligible Nodes
    Registry-->>Backup: Return Nodes & Health Scores
    Note over Backup: Quorum Check >= QuorumSize: PASSED
    Note over Backup: Score Ranking: Backup Master #1 Wins
    Backup->>Backup: State Transition -> LEADER
    Backup->>Cluster: Broadcast New Leader Announcement (Epoch N+1)
    Cluster-->>Backup: Register & Send Heartbeats to New Leader
```"""

    def generate_heartbeat_flow_diagram(self) -> str:
        """Generates Mermaid state diagram of heartbeat node lifecycle."""
        return """```mermaid
stateDiagram-v2
    [*] --> REGISTERED : Node Registration
    REGISTERED --> HEALTHY : Initial Heartbeat Received
    
    HEALTHY --> DEGRADED : High Load (>90%) OR Missed Heartbeat (1x)
    DEGRADED --> HEALTHY : Heartbeat Latency Normal & Load < 80%
    
    HEALTHY --> OFFLINE : Missed Heartbeats > worker_timeout
    DEGRADED --> OFFLINE : Missed Heartbeats > worker_timeout
    
    OFFLINE --> RECOVERING : Node Reconnects & Sends Heartbeat
    RECOVERING --> HEALTHY : Verification & State Resync Complete
    
    HEALTHY --> DEREGISTERED : Graceful Node Shutdown
    OFFLINE --> DEREGISTERED : Manual Deregister
    DEREGISTERED --> [*]
```"""

    def generate_task_scheduling_diagram(self) -> str:
        """Generates Mermaid flowchart of the distributed scheduler decision pipeline."""
        return """```mermaid
flowchart TD
    A[Cluster Job Submitted] --> B[Decompose into TaskSpecs]
    B --> C[Build DAG & Kahn Dependency Waves]
    C --> D{Dependencies Completed?}
    D -- No --> E[Hold in Dependency Wait Pool]
    D -- Yes --> F[Push into Distributed Priority Queue]
    
    F --> G[Scheduler Evaluation Loop]
    G --> H{Scheduling Strategy}
    H -- Least Loaded --> I1[Select Min Load Ratio & CPU]
    H -- Capability Based --> I2[Match Skills & Role Affinity]
    H -- Priority Aware --> I3[Route High Priority to Top Health Nodes]
    H -- Data Locality --> I4[Match Cached Artifacts & Memory]
    H -- Round Robin --> I5[Deterministic Sequential Worker Selection]
    
    I1 --> J[Dispatch Task with Visibility Lease]
    I2 --> J
    I3 --> J
    I4 --> J
    I5 --> J
    
    J --> K[Worker Executes Task]
    K --> L{Execution Status}
    L -- Success --> M[ACK Task & Store Artifacts & Unlock Dependencies]
    L -- Failure --> N{Retries < Max?}
    N -- Yes --> O[NACK with Exponential Backoff Retry]
    N -- No --> P[Move to Dead-Letter Queue (DLQ)]
    O --> F
```"""

    def generate_artifact_sync_diagram(self) -> str:
        """Generates Mermaid diagram of Content-Addressable Artifact Synchronization."""
        return """```mermaid
sequenceDiagram
    autonumber
    participant W as Worker Node (Producer)
    participant M as Master Artifact CAS
    participant W2 as Peer Worker (Consumer)

    W->>W: Generate Source Code & Diff Artifacts
    W->>W: Compute SHA-256 Checksums
    W->>M: Register Artifact Manifest (IDs, Paths, SHA-256)
    M-->>W: Acknowledge Registration
    Note over M: Store In-Memory & Persist to Storage Root
    
    W2->>M: Query Sync Manifest & Compute Delta
    M-->>W2: Return Delta Artifact List (Missing / Higher Version)
    W2->>M: Request Blobs for Delta Artifacts
    M-->>W2: Stream Chunked Content & Checksums
    W2->>W2: Verify SHA-256 & Store in Local Workspace
```"""

    def generate_checkpoint_recovery_diagram(self) -> str:
        """Generates Mermaid diagram of atomic checkpoint creation & disaster recovery."""
        return """```mermaid
sequenceDiagram
    autonumber
    participant Master as Master Node
    participant Disk as Persistent Disk Storage
    participant NewMaster as New Master (Post-Failover)

    rect rgb(20, 50, 40)
    Note over Master,Disk: Periodic Atomic Checkpoint Creation
    Master->>Master: Aggregate State (Registry, Queue, Memory, Locks)
    Master->>Master: Compute SHA-256 Checksum Envelope
    Master->>Disk: Write Atomic Checkpoint Payload to .tmp File
    Master->>Disk: Atomic Rename .tmp -> chk_timestamp_epoch.json
    Master->>Disk: Prune Old Checkpoints (> max_retained)
    end

    rect rgb(50, 20, 30)
    Note over NewMaster,Disk: Automated Disaster Recovery Flow
    NewMaster->>Disk: Discover Latest Checkpoint File
    Disk-->>NewMaster: Return Latest Verified Envelope
    NewMaster->>NewMaster: Validate SHA-256 Envelope Hash
    NewMaster->>NewMaster: Restore Node Registry, Queue, Distributed Memory, Locks
    NewMaster->>NewMaster: Resume In-Flight Task Leases & DAG Execution
    end
```"""

    def generate_execution_lifecycle_diagram(self) -> str:
        """Generates Mermaid flowchart of distributed multi-stage execution."""
        return """```mermaid
flowchart LR
    subgraph Master_Node [Master Node Coordination]
        Sub[Submit Job] --> Plan[Planning & DAG Build]
        Plan --> Sch[Distributed Scheduler]
        Sch --> Q[Priority Queue]
        Rec[Heartbeat & Failure Monitor] -.-> Sch
    end
    
    subgraph Worker_Nodes [Distributed Autonomous Workers]
        Q -->|Task Lease| W1[Worker: Coding]
        Q -->|Task Lease| W2[Worker: Testing]
        Q -->|Task Lease| W3[Worker: Security]
        Q -->|Task Lease| W4[Worker: Review]
    end
    
    subgraph Storage [Shared Distributed Storage]
        W1 -->|Artifact CAS| AS[Artifact Sync]
        W2 -->|Artifact CAS| AS
        W3 -->|Memory Set| DM[Distributed Memory]
        W4 -->|Atomic Lock| LM[Lock Manager]
    end
    
    W1 -->|ACK Task| Sch
    W2 -->|ACK Task| Sch
    W3 -->|ACK Task| Sch
    W4 -->|ACK Task| Sch
```"""
