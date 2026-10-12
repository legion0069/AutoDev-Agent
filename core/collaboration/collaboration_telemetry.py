"""
AutoDev Collaboration Framework - Collaboration Telemetry & Visualizer (v2.8)
=============================================================================
Calculates multi-agent collaboration performance metrics, tracking efficiency,
utilization, communication density, conflict frequency, review coverage,
and generates rich deterministic Mermaid diagrams for the multi-agent system.
"""

from __future__ import annotations

import json
import logging
import statistics
import time
from typing import Any, Dict, List, Optional, Set

from .collaboration_models import AgentRole

logger = logging.getLogger("autodev.collaboration.telemetry")


class CollaborationTelemetry:
    """
    Collects, calculates, and exports multi-agent collaboration metrics and
    architectural Mermaid visual diagrams.
    """

    def __init__(self):
        self._start_time = time.time()
        self._events: List[Dict[str, Any]] = []

    def log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Record a telemetry event."""
        self._events.append({
            "timestamp": time.time(),
            "event_type": event_type,
            "details": details,
        })

    # ------------------------------------------------------------------
    # Metrics Aggregation
    # ------------------------------------------------------------------

    def compute_metrics(
        self,
        allocator=None,
        bus=None,
        consensus_engine=None,
        conflict_resolver=None,
        workspace=None,
        scheduler=None,
    ) -> Dict[str, Any]:
        """
        Aggregate multi-dimensional collaboration metrics across all subsystem components.
        """
        now = time.time()
        duration = max(0.001, now - self._start_time)

        # 1. Agent Utilization & Workload
        agent_utilization = {}
        total_tasks = 0
        assigned_tasks = 0
        completed_tasks = 0
        if allocator:
            alloc_stats = allocator.get_allocation_stats()
            total_tasks = alloc_stats.get("total_tasks", 0)
            assigned_tasks = alloc_stats.get("assigned_tasks", 0)
            completed_tasks = alloc_stats.get("completed_tasks", 0)
            agent_utilization = alloc_stats.get("agent_utilization", {})

        # 2. Parallelism Metric (Max & Mean concurrent active tasks)
        parallelism = 1.0
        critical_path_hours = 0.0
        if scheduler:
            batches = scheduler.get_parallel_batches()
            if batches:
                batch_sizes = [len(b) for b in batches]
                parallelism = sum(batch_sizes) / max(1, len(batch_sizes))
            cpath = scheduler.get_critical_path()
            critical_path_hours = cpath.get("total_hours", 0.0)

        # 3. Communication Density
        communication_count = 0
        message_types_breakdown = {}
        if bus:
            messages = bus.get_all_messages()
            communication_count = len(messages)
            for m in messages:
                mtype = m.message_type.value if hasattr(m.message_type, "value") else str(m.message_type)
                message_types_breakdown[mtype] = message_types_breakdown.get(mtype, 0) + 1

        # 4. Consensus & Conflict Metrics
        consensus_count = len(consensus_engine.get_history()) if consensus_engine else 0
        conflict_count = len(conflict_resolver.get_history()) if conflict_resolver else 0

        # 5. Review Coverage & Approval Metrics
        review_coverage_pct = 0.0
        avg_approval_time_sec = 0.0
        if workspace:
            staged = workspace.get_staged_changes()
            if staged:
                approved_count = sum(1 for c in staged.values() if c.is_approved)
                review_coverage_pct = (approved_count / max(1, len(staged))) * 100.0
                approval_durations = [
                    c.approved_at - c.staged_at
                    for c in staged.values()
                    if c.is_approved and c.approved_at and c.staged_at
                ]
                if approval_durations:
                    avg_approval_time_sec = statistics.mean(approval_durations)

        # 6. Collaboration Efficiency
        progress_ratio = ((assigned_tasks + completed_tasks) / max(1, total_tasks))
        collaboration_efficiency = min(
            1.0,
            max(0.1, progress_ratio * (1.0 - min(0.5, conflict_count * 0.05))),
        )

        return {
            "duration_seconds": round(duration, 2),
            "total_tasks": total_tasks,
            "assigned_tasks": assigned_tasks,
            "completed_tasks": completed_tasks,
            "agent_utilization": agent_utilization,
            "average_parallelism": round(parallelism, 2),
            "critical_path_hours": round(critical_path_hours, 2),
            "collaboration_efficiency": round(collaboration_efficiency, 3),
            "communication_count": communication_count,
            "message_types_breakdown": message_types_breakdown,
            "conflict_count": conflict_count,
            "consensus_count": consensus_count,
            "review_coverage_pct": round(review_coverage_pct, 1),
            "average_approval_time_sec": round(avg_approval_time_sec, 2),
        }

    # ------------------------------------------------------------------
    # Mermaid Diagram Generators
    # ------------------------------------------------------------------

    def generate_collaboration_graph(self, bus=None, allocator=None) -> str:
        """
        Generate Mermaid diagram showing Agent collaboration topology and message links.
        """
        diagram = ["```mermaid", "graph TD", "    %% AutoDev v2.8 Multi-Agent Collaboration Graph"]

        agents = set()
        edges: Dict[Tuple[str, str], int] = {}

        if bus:
            for msg in bus.get_all_messages():
                if msg.sender and msg.receiver and msg.receiver != "*":
                    agents.add(msg.sender)
                    agents.add(msg.receiver)
                    pair = (msg.sender, msg.receiver)
                    edges[pair] = edges.get(pair, 0) + 1

        if not agents:
            agents = {
                "ArchitectureAgent",
                "BackendAgent",
                "FrontendAgent",
                "TestingAgent",
                "SecurityAgent",
                "PerformanceAgent",
                "DocumentationAgent",
                "ReleaseAgent",
            }
            # Default collaboration topologies
            edges[("ArchitectureAgent", "BackendAgent")] = 3
            edges[("ArchitectureAgent", "FrontendAgent")] = 2
            edges[("BackendAgent", "FrontendAgent")] = 5
            edges[("TestingAgent", "BackendAgent")] = 4
            edges[("SecurityAgent", "BackendAgent")] = 2
            edges[("PerformanceAgent", "BackendAgent")] = 2
            edges[("DocumentationAgent", "ReleaseAgent")] = 2
            edges[("ReleaseAgent", "ArchitectureAgent")] = 1

        for ag in sorted(agents):
            diagram.append(f'    {ag}["fa:fa-robot {ag}"]')

        for (src, dst), count in edges.items():
            diagram.append(f"    {src} -->|{count} msgs| {dst}")

        diagram.append("```")
        return "\n".join(diagram)

    def generate_task_allocation_graph(self, allocator) -> str:
        """
        Generate Mermaid diagram mapping tasks to assigned specialized agents.
        """
        diagram = ["```mermaid", "graph LR", "    %% AutoDev v2.8 Task Allocation Map"]
        if not allocator:
            diagram.append("    Orchestrator --> Tasks")
            diagram.append("```")
            return "\n".join(diagram)

        tasks = allocator.get_all_tasks()
        agents_seen = set()

        for t in tasks:
            task_node = f'T_{t.task_id[:6]}["{t.title} ({t.priority.name})"]'
            agent_name = t.assigned_agent or "Unassigned"
            agents_seen.add(agent_name)
            diagram.append(f"    {task_node} --> {agent_name}")

        for ag in sorted(agents_seen):
            diagram.append(f'    style {ag} fill:#2d3748,stroke:#4299e1,stroke-width:2px,color:#fff')

        diagram.append("```")
        return "\n".join(diagram)

    def generate_communication_graph(self, bus) -> str:
        """
        Generate Mermaid Sequence Diagram of inter-agent message flows.
        """
        diagram = ["```mermaid", "sequenceDiagram", "    autonumber", "    %% AutoDev v2.8 Inter-Agent Protocol Flow"]
        if not bus or not bus.get_all_messages():
            diagram.append("    ArchitectureAgent->>BackendAgent: REQUEST (API Contract)")
            diagram.append("    BackendAgent-->>ArchitectureAgent: RESPONSE (Schemas)")
            diagram.append("    BackendAgent->>TestingAgent: REVIEW (Endpoints)")
            diagram.append("    TestingAgent-->>BackendAgent: APPROVAL (All 100% Passed)")
            diagram.append("```")
            return "\n".join(diagram)

        messages = bus.get_all_messages()[:15]  # Limit to first 15 for clean diagram
        for msg in messages:
            sender = msg.sender or "Agent"
            receiver = msg.receiver if msg.receiver != "*" else "AllAgents"
            mtype = msg.message_type.value
            arrow = "-->>" if mtype in ("RESPONSE", "APPROVAL", "ANSWER") else "->>"
            diagram.append(f"    {sender}{arrow}{receiver}: {mtype} [{msg.task_id or 'General'}]")

        diagram.append("```")
        return "\n".join(diagram)

    def generate_consensus_flow(self, consensus_engine) -> str:
        """
        Generate Mermaid flowchart of consensus voting and resolution.
        """
        diagram = ["```mermaid", "graph TD", "    %% AutoDev v2.8 Consensus Engine Flow",
                   "    A[Dispute / Proposal Submission] --> B[Collect Agent Proposals]",
                   "    B --> C[Compute Role Authority Weights]",
                   "    C --> D{Strategy Evaluation}",
                   "    D -->|Security-First| E[Security Veto Check & Score]",
                   "    D -->|Architecture-First| F[Architectural Boundary Scoring]",
                   "    D -->|Weighted / Majority| G[Normalized Score Comparison]",
                   "    E --> H[Select Winning Proposal]",
                   "    F --> H",
                   "    G --> H",
                   "    H --> I[Log Immutable Consensus Record]",
                   "    I --> J[Broadcast Decision to Bus]",
                   "```"]
        return "\n".join(diagram)

    def generate_dependency_scheduling_graph(self, scheduler) -> str:
        """
        Generate Mermaid graph of DAG task dependencies and parallel execution batches.
        """
        diagram = ["```mermaid", "graph TD", "    %% AutoDev v2.8 Task Dependency DAG & Critical Path"]
        if not scheduler:
            diagram.append("    T1 --> T2")
            diagram.append("```")
            return "\n".join(diagram)

        tasks = scheduler.get_all_tasks()
        cpath = scheduler.get_critical_path()
        cpath_set = set(cpath.get("critical_path", []))

        for tid, t in tasks.items():
            node_label = f'{tid}["{t.title}"]'
            if tid in cpath_set:
                diagram.append(f"    {node_label}")
                diagram.append(f"    style {tid} fill:#9b2c2c,stroke:#feb2b2,stroke-width:2px,color:#fff")
            else:
                diagram.append(f"    {node_label}")

            for dep_id in t.dependencies:
                if dep_id in tasks:
                    diagram.append(f"    {dep_id} --> {tid}")

        diagram.append("```")
        return "\n".join(diagram)
