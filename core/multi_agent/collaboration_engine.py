"""
AutoDev Collaboration Engine Subsystem.

Coordinates multi-agent workflows, task allocation, parallel execution, conflict resolution,
consensus ratification, inter-agent messaging, and telemetry aggregation.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.multi_agent.agent_bus import AgentMessageBus
from core.multi_agent.agent_registry import AgentDescriptor, AgentRegistry, AgentStatus
from core.multi_agent.conflict_resolver import ConflictResolver
from core.multi_agent.consensus_engine import ConsensusEngine
from core.multi_agent.conversation import ConversationEngine
from core.multi_agent.message import Message, MessagePriority, MessageType
from core.multi_agent.parallel_executor import ExecutionResult, ParallelExecutor
from core.multi_agent.resource_scheduler import ResourceScheduler
from core.multi_agent.shared_workspace import SharedWorkspace
from core.multi_agent.task_allocator import TaskAllocator
from core.multi_agent.work_queue import TaskPriority, WorkItem, WorkItemStatus, WorkQueue


@dataclass
class TelemetrySnapshot:
    """Aggregated organizational telemetry metrics."""
    agent_utilization: Dict[str, float] = field(default_factory=dict)
    queue_length: int = 0
    pending_tasks: int = 0
    in_progress_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    peak_parallelism: int = 0
    total_cpu_time: float = 0.0
    avg_execution_latency: float = 0.0
    min_execution_latency: float = 0.0
    max_execution_latency: float = 0.0
    communication_volume: int = 0
    collaboration_graph: Dict[str, Dict[str, int]] = field(default_factory=dict)
    idle_time: Dict[str, float] = field(default_factory=dict)
    conflict_count: int = 0
    conflict_rate: float = 0.0
    resolution_success_rate: float = 1.0


class CollaborationEngine:
    """
    Central coordinator orchestrating agents, message bus, conversations,
    work queues, resource reservations, parallel execution, and consensus.
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        bus: Optional[AgentMessageBus] = None,
        conversations: Optional[ConversationEngine] = None,
        work_queue: Optional[WorkQueue] = None,
        allocator: Optional[TaskAllocator] = None,
        scheduler: Optional[ResourceScheduler] = None,
        executor: Optional[ParallelExecutor] = None,
        resolver: Optional[ConflictResolver] = None,
        consensus: Optional[ConsensusEngine] = None,
        workspace: Optional[SharedWorkspace] = None,
    ) -> None:
        self.registry = registry or AgentRegistry()
        self.bus = bus or AgentMessageBus()
        self.conversations = conversations or ConversationEngine()
        self.work_queue = work_queue or WorkQueue()
        self.allocator = allocator or TaskAllocator()
        self.scheduler = scheduler or ResourceScheduler()
        self.executor = executor or ParallelExecutor(max_workers=8)
        self.resolver = resolver or ConflictResolver()
        self.consensus = consensus or ConsensusEngine()
        self.workspace = workspace or SharedWorkspace()

        self._lock = threading.RLock()
        self._latencies: List[float] = []
        self._agent_busy_time: Dict[str, float] = {}
        self._collaboration_matrix: Dict[str, Dict[str, int]] = {}
        self._started_at = time.time()

    def record_communication(self, sender: str, receiver: str) -> None:
        """Tracks inter-agent communication volume for the collaboration graph."""
        with self._lock:
            if sender not in self._collaboration_matrix:
                self._collaboration_matrix[sender] = {}
            self._collaboration_matrix[sender][receiver] = (
                self._collaboration_matrix[sender].get(receiver, 0) + 1
            )

    def submit_task(self, task: WorkItem) -> str:
        """Enqueues a task and announces it on the bus."""
        t_id = self.work_queue.enqueue(task)
        self.workspace.append_log(
            f"Enqueued task '{task.task_id}': {task.title}",
            level="INFO",
            source="collaboration_engine"
        )
        # Notify all agents on bus
        msg = Message(
            sender="collaboration_engine",
            receiver="*",
            msg_type=MessageType.BROADCAST,
            task_id=t_id,
            payload={"event": "TASK_ENQUEUED", "task": task.to_dict()},
        )
        self.bus.broadcast(msg)
        return t_id

    def execute_next_batch(
        self,
        default_runner_fn: Optional[Callable[[WorkItem, AgentDescriptor], Any]] = None,
        batch_size: int = 10,
    ) -> List[ExecutionResult]:
        """
        Allocates ready tasks from the work queue to best engineers, executes them
        in parallel under resource reservations, and records results and telemetry.
        """
        ready_tasks = self.work_queue.get_ready_tasks()
        if not ready_tasks:
            return []

        tasks_to_run = ready_tasks[:batch_size]
        critical_path = self.work_queue.get_critical_path()

        # Batch allocation
        assignments = self.allocator.allocate_batch(
            tasks_to_run,
            self.registry,
            critical_path=critical_path,
        )

        if not assignments:
            return []

        tasks_with_agents: List[Tuple[WorkItem, AgentDescriptor, Callable[[WorkItem, AgentDescriptor], Any]]] = []

        runner = default_runner_fn or self._default_task_runner

        for task in tasks_to_run:
            agent_id = assignments.get(task.task_id)
            if not agent_id:
                continue

            agent = self.registry.get_agent(agent_id)
            if not agent:
                continue

            # Mark task in progress & update agent workload
            self.work_queue.mark_in_progress(task.task_id, agent_id=agent_id)
            self.registry.update_workload(agent_id, delta=1)
            self.registry.set_status(agent_id, AgentStatus.BUSY)

            tasks_with_agents.append((task, agent, runner))

        if not tasks_with_agents:
            return []

        # Execute parallel batch
        results = self.executor.execute_batch(
            tasks_with_agents,
            scheduler=self.scheduler,
        )

        # Process completions
        for res in results:
            task = self.work_queue.get_task(res.task_id)
            agent = self.registry.get_agent(res.agent_id)

            with self._lock:
                self._latencies.append(res.duration)
                self._agent_busy_time[res.agent_id] = (
                    self._agent_busy_time.get(res.agent_id, 0.0) + res.duration
                )

            if res.success:
                self.work_queue.mark_completed(res.task_id, result=res.result)
                if agent:
                    self.registry.record_completion(
                        res.agent_id, success=True, duration=res.duration
                    )
                self.workspace.append_log(
                    f"Completed task '{res.task_id}' by {res.agent_id} in {res.duration:.3f}s",
                    level="INFO",
                )
            else:
                self.work_queue.mark_failed(res.task_id, error=res.error or "Unknown failure")
                if agent:
                    self.registry.record_completion(
                        res.agent_id, success=False, duration=res.duration
                    )
                self.workspace.append_log(
                    f"Task '{res.task_id}' failed under {res.agent_id}: {res.error}",
                    level="ERROR",
                )

            # Decrement agent workload
            self.registry.update_workload(res.agent_id, delta=-1)
            updated_agent = self.registry.get_agent(res.agent_id)
            if updated_agent and updated_agent.workload == 0:
                self.registry.set_status(res.agent_id, AgentStatus.IDLE)

        return results

    def _default_task_runner(self, task: WorkItem, agent: AgentDescriptor) -> Any:
        """Deterministic default runner function for simulating engineering execution."""
        # Yield deterministic result payload
        return {
            "status": "success",
            "task_id": task.task_id,
            "title": task.title,
            "executed_by": agent.agent_id,
            "role": agent.role.value,
        }

    def run_all_tasks(
        self,
        default_runner_fn: Optional[Callable[[WorkItem, AgentDescriptor], Any]] = None,
        max_cycles: int = 100,
    ) -> List[ExecutionResult]:
        """
        Executes ready tasks in cycles until queue is finished or max_cycles reached.
        """
        all_results: List[ExecutionResult] = []
        cycle = 0

        while not self.work_queue.is_finished() and cycle < max_cycles:
            cycle += 1
            batch_results = self.execute_next_batch(default_runner_fn=default_runner_fn)
            if not batch_results:
                # If no tasks could be scheduled (e.g. waiting or deadlocked), reclaim leases
                reclaimed = self.work_queue.reclaim_expired_leases()
                if not reclaimed:
                    break
            all_results.extend(batch_results)

        return all_results

    def get_telemetry(self) -> TelemetrySnapshot:
        """Computes and returns comprehensive organizational telemetry."""
        with self._lock:
            total_elapsed = max(0.001, time.time() - self._started_at)
            all_agents = self.registry.get_all_agents()

            utilization: Dict[str, float] = {}
            idle_time: Dict[str, float] = {}
            for ag in all_agents:
                busy = self._agent_busy_time.get(ag.agent_id, 0.0)
                util = min(1.0, busy / total_elapsed)
                utilization[ag.agent_id] = round(util, 4)
                idle_time[ag.agent_id] = round(max(0.0, total_elapsed - busy), 4)

            min_lat = min(self._latencies) if self._latencies else 0.0
            max_lat = max(self._latencies) if self._latencies else 0.0
            avg_lat = sum(self._latencies) / len(self._latencies) if self._latencies else 0.0

            total_messages = self.bus.count()

            # Add inter-agent communications logged in bus to collaboration graph
            graph: Dict[str, Dict[str, int]] = {}
            for s, r_dict in self._collaboration_matrix.items():
                graph[s] = dict(r_dict)

            for msg in self.bus.get_all_messages():
                s = msg.sender
                r = msg.receiver
                if s and r and r != "*":
                    if s not in graph:
                        graph[s] = {}
                    graph[s][r] = graph[s].get(r, 0) + 1

            conflict_count = self.resolver.total_conflicts
            res_rate = self.resolver.resolution_rate
            conflict_rate = (
                round(conflict_count / max(1, self.work_queue.size()), 4)
            )

            return TelemetrySnapshot(
                agent_utilization=utilization,
                queue_length=self.work_queue.size(),
                pending_tasks=self.work_queue.pending_count(),
                in_progress_tasks=self.work_queue.in_progress_count(),
                completed_tasks=self.work_queue.completed_count(),
                failed_tasks=self.work_queue.failed_count(),
                peak_parallelism=self.executor.peak_concurrency,
                total_cpu_time=round(self.executor.total_duration, 4),
                avg_execution_latency=round(avg_lat, 4),
                min_execution_latency=round(min_lat, 4),
                max_execution_latency=round(max_lat, 4),
                communication_volume=total_messages,
                collaboration_graph=graph,
                idle_time=idle_time,
                conflict_count=conflict_count,
                conflict_rate=conflict_rate,
                resolution_success_rate=res_rate,
            )

    def shutdown(self) -> None:
        """Gracefully shuts down executor and clears resources."""
        self.executor.shutdown(wait=True)
