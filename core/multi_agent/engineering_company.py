"""
AutoDev Engineering Company Simulator Subsystem.

Simulates an entire autonomous software engineering organization comprising
Executive Management (CEO, CTO, Director), Architecture, Engineering Management,
Specialized Developers, QA, DevOps, Security, Documentation, and Release Management.

Includes automated standups, design reviews, code reviews, retrospectives, release meetings,
10 comprehensive Markdown engineering reports, and 6 Mermaid diagrams.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.multi_agent.agent_bus import AgentMessageBus
from core.multi_agent.agent_registry import AgentDescriptor, AgentRegistry, AgentRole, AgentStatus
from core.multi_agent.collaboration_engine import CollaborationEngine, TelemetrySnapshot
from core.multi_agent.conflict_resolver import ConflictRecord, ConflictResolver, ResolutionAction
from core.multi_agent.consensus_engine import ConsensusEngine, ConsensusProposal, ConsensusStrategy, ReviewVote, VoteDecision
from core.multi_agent.conversation import ConversationEngine, ConversationThread
from core.multi_agent.message import Message, MessagePriority, MessageType
from core.multi_agent.parallel_executor import ExecutionResult, ParallelExecutor
from core.multi_agent.resource_scheduler import LockType, ResourceScheduler
from core.multi_agent.shared_workspace import SharedWorkspace
from core.multi_agent.task_allocator import TaskAllocator
from core.multi_agent.work_queue import TaskPriority, WorkItem, WorkItemStatus, WorkQueue


class DistributedEngineeringCompany:
    """
    Autonomous distributed engineering organization simulating a full-lifecycle software enterprise.
    """

    def __init__(
        self,
        company_name: str = "AutoDev Autonomous Engineering Corp",
        deterministic_mode: bool = False,
        max_workers: int = 8,
    ) -> None:
        self.company_name = company_name
        self.deterministic_mode = deterministic_mode

        # Core collaboration engine & child subsystems
        self.registry = AgentRegistry()
        self.bus = AgentMessageBus()
        self.conversations = ConversationEngine()
        self.work_queue = WorkQueue()
        self.allocator = TaskAllocator()
        self.scheduler = ResourceScheduler()
        self.executor = ParallelExecutor(max_workers=max_workers, deterministic_mode=deterministic_mode)
        self.resolver = ConflictResolver()
        self.consensus = ConsensusEngine()
        self.workspace = SharedWorkspace()

        self.engine = CollaborationEngine(
            registry=self.registry,
            bus=self.bus,
            conversations=self.conversations,
            work_queue=self.work_queue,
            allocator=self.allocator,
            scheduler=self.scheduler,
            executor=self.executor,
            resolver=self.resolver,
            consensus=self.consensus,
            workspace=self.workspace,
        )

        self._standup_history: List[Dict[str, Any]] = []
        self._retrospective_history: List[Dict[str, Any]] = []
        self._release_history: List[Dict[str, Any]] = []
        self._execution_history: List[ExecutionResult] = []

        # Populate standard enterprise roster
        self._initialize_standard_roster()

    def _initialize_standard_roster(self) -> None:
        """Seeds the standard specialized corporate engineering roster."""
        standard_staff = [
            (AgentRole.CEO, "agent_ceo", "Chief Executive Officer", ["leadership", "strategy", "governance"], 100),
            (AgentRole.CTO, "agent_cto", "Chief Technology Officer", ["technical_strategy", "architecture_governance"], 95),
            (AgentRole.ENGINEERING_DIRECTOR, "agent_dir", "Engineering Director", ["management", "delivery", "org_scaling"], 90),
            (AgentRole.CHIEF_ARCHITECT, "agent_arch", "Chief Architect", ["system_design", "modularity", "standards"], 88),
            (AgentRole.ENGINEERING_MANAGER, "agent_em", "Engineering Manager", ["sprint_planning", "team_coordination"], 85),
            (AgentRole.TASK_SCHEDULER, "agent_sched", "Task Scheduler", ["queue_dispatch", "capacity_balancing"], 80),
            (AgentRole.BACKEND_ENGINEER, "agent_be", "Senior Backend Engineer", ["python", "api", "distributed_systems"], 75),
            (AgentRole.FRONTEND_ENGINEER, "agent_fe", "Senior Frontend Engineer", ["ui", "state_management", "css"], 75),
            (AgentRole.AI_ENGINEER, "agent_ai", "Lead AI Engineer", ["nlp", "agentic_workflows", "rag"], 80),
            (AgentRole.DATABASE_ENGINEER, "agent_db", "Principal Database Engineer", ["schemas", "indexing", "concurrency"], 75),
            (AgentRole.INFRASTRUCTURE_ENGINEER, "agent_infra", "Infrastructure Engineer", ["cloud", "storage", "networking"], 75),
            (AgentRole.DEVOPS_ENGINEER, "agent_devops", "DevOps Engineer", ["ci_cd", "automation", "containers"], 75),
            (AgentRole.QA_ENGINEER, "agent_qa", "Staff QA Engineer", ["testing", "validation", "regression"], 70),
            (AgentRole.SECURITY_ENGINEER, "agent_sec", "Principal Security Engineer", ["audit", "cryptography", "hardening"], 85),
            (AgentRole.DOCUMENTATION_ENGINEER, "agent_doc", "Technical Documentation Engineer", ["markdown", "apis", "specs"], 65),
            (AgentRole.RELEASE_MANAGER, "agent_rel", "Release Manager", ["versioning", "packaging", "deployment"], 80),
        ]

        for role, agent_id, name, caps, prio in standard_staff:
            desc = AgentDescriptor(
                agent_id=agent_id,
                name=name,
                role=role,
                capabilities=caps,
                priority=prio,
                workload=0,
                max_workload=5,
                status=AgentStatus.IDLE,
            )
            self.registry.register_agent(desc)

    # ------------------------------------------------------------------
    # Company Operations & Ceremonies
    # ------------------------------------------------------------------

    def simulate_daily_standup(self) -> Dict[str, Any]:
        """
        Conducts an autonomous engineering daily standup meeting.
        Every active engineer posts updates to the company message bus.
        """
        thread = self.conversations.create_thread(
            title=f"Daily Standup - {time.strftime('%Y-%m-%d %H:%M:%S')}",
            initiator="agent_em",
            tags=["standup", "daily_sync"],
        )

        updates: List[Dict[str, Any]] = []
        for agent in self.registry.get_all_agents():
            status_text = (
                f"Status: {agent.status.value.upper()}. "
                f"Workload: {agent.workload}/{agent.max_workload} tasks. "
                f"Completed to date: {agent.total_tasks_completed}."
            )
            thread.add_entry(
                author_id=agent.agent_id,
                message=status_text,
                entry_type="standup_update",
            )
            msg = Message(
                sender=agent.agent_id,
                receiver="agent_em",
                msg_type=MessageType.NOTIFICATION,
                conversation_id=thread.conversation_id,
                payload={"update": status_text, "workload": agent.workload},
            )
            self.bus.send(msg)
            self.engine.record_communication(agent.agent_id, "agent_em")
            updates.append({"agent_id": agent.agent_id, "role": agent.role.value, "update": status_text})

        standup_record = {
            "standup_id": f"standup_{uuid.uuid4().hex[:8]}",
            "timestamp": time.time(),
            "conversation_id": thread.conversation_id,
            "attendees_count": len(updates),
            "updates": updates,
        }
        self._standup_history.append(standup_record)
        self.workspace.append_log(f"Daily standup completed with {len(updates)} attendees.", level="INFO")
        return standup_record

    def simulate_handoff(
        self,
        from_agent_id: str,
        to_agent_id: str,
        task: WorkItem,
        notes: str = ""
    ) -> Message:
        """Simulates an explicit engineering handoff between two engineers."""
        payload = {
            "task_id": task.task_id,
            "task_title": task.title,
            "handoff_notes": notes,
            "resources": list(task.resources_required),
        }
        msg = Message(
            sender=from_agent_id,
            receiver=to_agent_id,
            msg_type=MessageType.DIRECT,
            priority=MessagePriority.HIGH,
            task_id=task.task_id,
            payload=payload,
        )
        self.bus.send(msg)
        self.engine.record_communication(from_agent_id, to_agent_id)
        self.workspace.add_note(
            topic=f"handoff_{task.task_id}",
            note=f"Handoff from {from_agent_id} to {to_agent_id}: {notes}",
            author_id=from_agent_id,
        )
        return msg

    def simulate_design_review(
        self,
        title: str,
        target_artifact: str,
        proposer_id: str = "agent_arch",
        strategy: ConsensusStrategy = ConsensusStrategy.WEIGHTED_MAJORITY,
    ) -> ConsensusProposal:
        """
        Runs an autonomous design review ceremony evaluating an architectural proposal.
        """
        prop_id = f"des_{uuid.uuid4().hex[:8]}"
        proposal = self.consensus.create_proposal(
            proposal_id=prop_id,
            title=title,
            description=f"Design review for artifact {target_artifact}",
            target_artifact=target_artifact,
            strategy=strategy,
            quality_threshold=80.0,
            confidence_threshold=0.75,
        )

        reviewers = [
            ("agent_arch", AgentRole.CHIEF_ARCHITECT, VoteDecision.APPROVE, 95.0, 0.95, "Architecturally sound."),
            ("agent_sec", AgentRole.SECURITY_ENGINEER, VoteDecision.APPROVE, 90.0, 0.90, "Passes security posture review."),
            ("agent_em", AgentRole.ENGINEERING_MANAGER, VoteDecision.APPROVE, 85.0, 0.85, "Feasible within sprint budget."),
            ("agent_qa", AgentRole.QA_ENGINEER, VoteDecision.APPROVE, 88.0, 0.88, "Test matrix specified."),
        ]

        for reviewer_id, role, decision, q_score, conf_score, rationale in reviewers:
            vote = ReviewVote(
                reviewer_id=reviewer_id,
                reviewer_role=role,
                decision=decision,
                quality_score=q_score,
                confidence_score=conf_score,
                rationale=rationale,
            )
            self.consensus.cast_vote(prop_id, vote)
            self.engine.record_communication(reviewer_id, proposer_id)

        self.consensus.evaluate_consensus(prop_id)
        self.workspace.record_design_decision(
            decision_id=prop_id,
            title=title,
            decision=proposal.status,
            author_id=proposer_id,
            rationale=proposal.decision_reason,
        )
        return proposal

    def simulate_code_review(
        self,
        task_id: str,
        code_diff: str = "",
        author_id: str = "agent_be",
    ) -> ConsensusProposal:
        """Runs a formal code review with QA, Security, and Engineering Manager."""
        prop_id = f"cr_{task_id}_{uuid.uuid4().hex[:6]}"
        proposal = self.consensus.create_proposal(
            proposal_id=prop_id,
            title=f"Code Review: Task {task_id}",
            description=f"Peer review of implementation by {author_id}",
            target_artifact=f"task_{task_id}",
            strategy=ConsensusStrategy.MAJORITY,
        )

        # Cast reviews
        self.consensus.cast_vote(
            prop_id,
            ReviewVote(
                reviewer_id="agent_qa",
                reviewer_role=AgentRole.QA_ENGINEER,
                decision=VoteDecision.APPROVE,
                quality_score=90.0,
                confidence_score=0.90,
                rationale="Automated test suite validates all assertions.",
            ),
        )
        self.consensus.cast_vote(
            prop_id,
            ReviewVote(
                reviewer_id="agent_sec",
                reviewer_role=AgentRole.SECURITY_ENGINEER,
                decision=VoteDecision.APPROVE,
                quality_score=92.0,
                confidence_score=0.95,
                rationale="No vulnerabilities detected in static analysis.",
            ),
        )

        self.consensus.evaluate_consensus(prop_id)
        self.workspace.add_review(
            review_id=prop_id,
            task_id=task_id,
            reviewer_id="peer_review_panel",
            status=proposal.status,
            comments=proposal.decision_reason,
        )
        return proposal

    def simulate_retrospective(self) -> Dict[str, Any]:
        """Runs sprint retrospective ceremony identifying achievements and improvements."""
        telemetry = self.engine.get_telemetry()
        retro = {
            "retro_id": f"retro_{uuid.uuid4().hex[:8]}",
            "timestamp": time.time(),
            "completed_tasks": telemetry.completed_tasks,
            "failed_tasks": telemetry.failed_tasks,
            "average_latency": telemetry.avg_execution_latency,
            "conflict_count": telemetry.conflict_count,
            "takeaways": [
                f"Organization completed {telemetry.completed_tasks} engineering tasks.",
                f"Peak parallelism reached {telemetry.peak_parallelism} concurrent agents.",
                f"Communication volume reached {telemetry.communication_volume} messages across bus.",
                "Deadlock prevention avoided 100% of circular wait conditions.",
            ],
        }
        self._retrospective_history.append(retro)
        return retro

    def simulate_release_meeting(self, version: str = "v3.3.0") -> Dict[str, Any]:
        """Conducts official release review with CEO, CTO, and Release Manager."""
        rel_prop = self.consensus.create_proposal(
            proposal_id=f"rel_{version}",
            title=f"Release Candidate Sign-off {version}",
            description="Production readiness and deployment sign-off",
            target_artifact=version,
            strategy=ConsensusStrategy.ARCHITECT_OVERRIDE,
        )
        self.consensus.cast_vote(
            f"rel_{version}",
            ReviewVote(
                reviewer_id="agent_arch",
                reviewer_role=AgentRole.CHIEF_ARCHITECT,
                decision=VoteDecision.APPROVE,
                quality_score=98.0,
                confidence_score=0.99,
                rationale="System integrity validated. All interfaces backward compatible.",
            ),
        )
        self.consensus.evaluate_consensus(f"rel_{version}")

        release_record = {
            "version": version,
            "timestamp": time.time(),
            "status": "APPROVED",
            "approved_by": "agent_arch",
            "release_manager": "agent_rel",
        }
        self._release_history.append(release_record)
        return release_record

    def submit_and_execute_tasks(
        self,
        tasks: List[WorkItem],
        custom_runner_fn: Optional[Callable[[WorkItem, AgentDescriptor], Any]] = None,
    ) -> List[ExecutionResult]:
        """Submits a batch of tasks to the company and runs them to completion."""
        for task in tasks:
            self.engine.submit_task(task)

        results = self.engine.run_all_tasks(default_runner_fn=custom_runner_fn)
        self._execution_history.extend(results)
        return results

    # ------------------------------------------------------------------
    # 10 Engineering Reports
    # ------------------------------------------------------------------

    def generate_company_report(self) -> str:
        """Report 1: Executive organizational overview."""
        telemetry = self.engine.get_telemetry()
        agents = self.registry.get_all_agents()
        return f"""# {self.company_name} - Executive Company Report

## Organizational Overview
- **Active Staff Count**: {len(agents)} specialized agents
- **Total Work Items Processed**: {self.work_queue.size()}
- **Completed Deliverables**: {telemetry.completed_tasks}
- **Peak Organizational Parallelism**: {telemetry.peak_parallelism} concurrent workers
- **Total Inter-Agent Messages**: {telemetry.communication_volume}
- **Resolution Success Rate**: {telemetry.resolution_success_rate * 100:.1f}%

## Leadership Summary
- **CEO**: agent_ceo (Autonomous Governance)
- **CTO**: agent_cto (Technical Architecture Strategy)
- **Engineering Director**: agent_dir (Execution & Scaling)
- **Chief Architect**: agent_arch (Consensus & System Modularity)
"""

    def generate_engineering_report(self) -> str:
        """Report 2: Engineering subsystem health and delivery."""
        telemetry = self.engine.get_telemetry()
        crit_path = self.work_queue.get_critical_path()
        return f"""# Engineering Subsystem Report

## Execution Metrics
- **Completed Tasks**: {telemetry.completed_tasks}
- **Pending / In-Progress**: {telemetry.pending_tasks} / {telemetry.in_progress_tasks}
- **Failed Tasks**: {telemetry.failed_tasks}
- **Average Execution Latency**: {telemetry.avg_execution_latency:.3f}s
- **Total CPU Runtime**: {telemetry.total_cpu_time:.3f}s

## Critical Path Analysis
- **Critical Path Length**: {len(crit_path)} stages
- **Path Sequence**: {' -> '.join(crit_path) if crit_path else 'None (Empty or independent)'}
"""

    def generate_agent_performance_report(self) -> str:
        """Report 3: Individual agent performance and efficiency scorecard."""
        telemetry = self.engine.get_telemetry()
        lines = [
            "# Agent Performance & Efficiency Scorecard\n",
            "| Agent ID | Role | Completed | Failed | Success Rate | Workload | Utilization |",
            "|---|---|---|---|---|---|---|",
        ]
        for ag in self.registry.get_all_agents():
            util = telemetry.agent_utilization.get(ag.agent_id, 0.0)
            lines.append(
                f"| `{ag.agent_id}` | {ag.role.value} | {ag.total_tasks_completed} | "
                f"{ag.total_tasks_failed} | {ag.success_rate * 100:.1f}% | "
                f"{ag.workload}/{ag.max_workload} | {util * 100:.1f}% |"
            )
        return "\n".join(lines)

    def generate_communication_graph_report(self) -> str:
        """Report 4: Inter-agent messaging matrix."""
        telemetry = self.engine.get_telemetry()
        lines = [
            "# Inter-Agent Communication Matrix\n",
            f"- **Total Messages Transmitted**: {telemetry.communication_volume}\n",
            "| Sender | Receiver | Message Count |",
            "|---|---|---|",
        ]
        for sender, receivers in sorted(telemetry.collaboration_graph.items()):
            for receiver, count in sorted(receivers.items()):
                lines.append(f"| `{sender}` | `{receiver}` | {count} |")
        return "\n".join(lines)

    def generate_task_timeline_report(self) -> str:
        """Report 5: Task lifecycle and completion chronology."""
        tasks = self.work_queue.get_all_tasks()
        lines = [
            "# Task Timeline & Lifecycle Report\n",
            "| Task ID | Title | Status | Assigned Agent | Priority | Runtime |",
            "|---|---|---|---|---|---|",
        ]
        for t in tasks:
            runtime = f"{(t.completed_at - t.started_at):.3f}s" if (t.completed_at and t.started_at) else "N/A"
            lines.append(
                f"| `{t.task_id}` | {t.title} | {t.status.value.upper()} | "
                f"`{t.assigned_agent_id or 'unassigned'}` | {t.priority} | {runtime} |"
            )
        return "\n".join(lines)

    def generate_parallel_execution_timeline_report(self) -> str:
        """Report 6: Parallel worker concurrency and execution records."""
        telemetry = self.engine.get_telemetry()
        lines = [
            "# Parallel Execution Timeline\n",
            f"- **Configured Max Workers**: {self.executor.max_workers}",
            f"- **Peak Observed Concurrency**: {telemetry.peak_parallelism}",
            f"- **Total Concurrent Tasks Executed**: {self.executor.total_executed}\n",
            "| Task ID | Agent ID | Status | Duration | Resources Locked |",
            "|---|---|---|---|---|",
        ]
        for res in self._execution_history:
            status = "SUCCESS" if res.success else f"FAIL ({res.error})"
            res_str = ", ".join(res.resources_used) if res.resources_used else "None"
            lines.append(
                f"| `{res.task_id}` | `{res.agent_id}` | {status} | {res.duration:.3f}s | {res_str} |"
            )
        return "\n".join(lines)

    def generate_consensus_report(self) -> str:
        """Report 7: Code reviews and design consensus decisions."""
        summary = self.consensus.get_consensus_summary()
        proposals = self.consensus.get_all_proposals()
        lines = [
            "# Engineering Consensus & Ratification Report\n",
            f"- **Total Proposals / Reviews**: {summary['total_proposals']}",
            f"- **Ratified & Approved**: {summary['approved_count']}",
            f"- **Rejected**: {summary['rejected_count']}",
            f"- **Ratification Rate**: {summary['ratification_rate'] * 100:.1f}%\n",
            "| Proposal ID | Title | Strategy | Status | Total Votes | Decision Reason |",
            "|---|---|---|---|---|---|",
        ]
        for p in proposals:
            lines.append(
                f"| `{p.proposal_id}` | {p.title} | {p.strategy.value} | {p.status} | "
                f"{len(p.votes)} | {p.decision_reason} |"
            )
        return "\n".join(lines)

    def generate_conflict_resolution_report(self) -> str:
        """Report 8: Conflict detection and resolution audit."""
        conflicts = self.resolver.get_all_conflicts()
        lines = [
            "# Conflict Resolution Audit\n",
            f"- **Total Detected Conflicts**: {len(conflicts)}",
            f"- **Successfully Remediated**: {self.resolver.resolved_count}",
            f"- **Resolution Success Rate**: {self.resolver.resolution_rate * 100:.1f}%\n",
            "| Conflict ID | Type | Involved Agents | Resources | Action | Winner |",
            "|---|---|---|---|---|---|",
        ]
        for c in conflicts:
            action = c.resolution_action.value if c.resolution_action else "PENDING"
            lines.append(
                f"| `{c.conflict_id}` | {c.conflict_type.value} | {', '.join(c.involved_agents)} | "
                f"{', '.join(c.involved_resources)} | {action} | `{c.winning_agent_id or 'none'}` |"
            )
        return "\n".join(lines)

    def generate_resource_utilization_report(self) -> str:
        """Report 9: Distributed resource locking and file safety audit."""
        locks = self.scheduler.get_active_locks()
        lines = [
            "# Distributed Resource & Lock Utilization Report\n",
            f"- **Active Locks Held**: {len(locks)}\n",
            "| Resource ID | Holder Agent | Lock Mode | Acquired Time |",
            "|---|---|---|---|",
        ]
        for lk in locks:
            lines.append(
                f"| `{lk['resource_id']}` | `{lk['holder_id']}` | {lk['lock_type']} | {lk['acquired_at']} |"
            )
        if not locks:
            lines.append("| *All resources cleanly unlocked* | - | - | - |")
        return "\n".join(lines)

    def generate_daily_engineering_report(self) -> str:
        """Report 10: Consolidated daily engineering organization journal."""
        telemetry = self.engine.get_telemetry()
        return f"""# Daily Engineering Standup & Organizational Journal

## Organization: {self.company_name}
- **Date / Cycle**: Standup Sessions Completed: {len(self._standup_history)}
- **Tasks Finished**: {telemetry.completed_tasks} / {self.work_queue.size()}
- **Parallel Speedup**: Peak parallelism = {telemetry.peak_parallelism}x
- **Total Bus Messages**: {telemetry.communication_volume}
- **Conflict Rate**: {telemetry.conflict_rate * 100:.1f}%

## Recent Standup Highlights
{self._standup_history[-1]['updates'][0]['update'] if self._standup_history else 'No standups recorded yet.'}
"""

    # ------------------------------------------------------------------
    # 6 Mermaid Diagrams
    # ------------------------------------------------------------------

    def generate_company_hierarchy_diagram(self) -> str:
        """Diagram 1: Corporate command and reporting hierarchy."""
        return """```mermaid
graph TD
    CEO["CEO (agent_ceo)"] --> CTO["CTO (agent_cto)"]
    CTO --> DIR["Engineering Director (agent_dir)"]
    DIR --> ARCH["Chief Architect (agent_arch)"]
    DIR --> EM["Engineering Manager (agent_em)"]
    DIR --> REL["Release Manager (agent_rel)"]
    ARCH --> BE["Backend Engineer (agent_be)"]
    ARCH --> FE["Frontend Engineer (agent_fe)"]
    ARCH --> AI["AI Engineer (agent_ai)"]
    ARCH --> DB["Database Engineer (agent_db)"]
    EM --> QA["QA Engineer (agent_qa)"]
    EM --> SEC["Security Engineer (agent_sec)"]
    EM --> DOC["Doc Engineer (agent_doc)"]
    CTO --> INFRA["Infrastructure (agent_infra)"]
    CTO --> DEVOPS["DevOps (agent_devops)"]
```"""

    def generate_message_bus_diagram(self) -> str:
        """Diagram 2: Message bus routing architecture."""
        return """```mermaid
graph LR
    Agents["Specialized Agents"] -->|Direct / Request| BUS["AgentMessageBus (Thread-Safe Router)"]
    BUS -->|Broadcast| All["All Subscribed Agents"]
    BUS -->|Topic Pub/Sub| Subscribers["Topic Subscribers"]
    BUS -->|Persistent Journal| Store["In-Memory Message Store"]
    BUS -->|Correlated Response| Requester["Originating Agent"]
```"""

    def generate_parallel_execution_diagram(self) -> str:
        """Diagram 3: Parallel work dispatch and lock acquisition."""
        return """```mermaid
graph TD
    WQ["WorkQueue (Prioritized Tasks)"] --> ALLOC["TaskAllocator (Scoring Engine)"]
    ALLOC --> POOL["ParallelExecutor (ThreadPoolExecutor)"]
    POOL --> RES["ResourceScheduler (Deadlock-Free Locks)"]
    RES --> WORKER1["Worker 1 (agent_be)"]
    RES --> WORKER2["Worker 2 (agent_fe)"]
    RES --> WORKER3["Worker 3 (agent_ai)"]
    WORKER1 --> COMP["Completion & Telemetry"]
    WORKER2 --> COMP
    WORKER3 --> COMP
```"""

    def generate_resource_scheduling_diagram(self) -> str:
        """Diagram 4: Canonical sorting deadlock prevention."""
        return """```mermaid
sequenceDiagram
    participant Agent as Agent (Worker)
    participant Scheduler as ResourceScheduler
    participant LockTable as Canonical Lock Table

    Agent->>Scheduler: reserve_resources([file_B, file_A])
    Note over Scheduler: Sort resources canonically: [file_A, file_B]
    Scheduler->>LockTable: Acquire lock for file_A
    LockTable-->>Scheduler: file_A Granted
    Scheduler->>LockTable: Acquire lock for file_B
    LockTable-->>Scheduler: file_B Granted
    Scheduler-->>Agent: reservation_id (Success)
    Note over Agent: Execute task safely
    Agent->>Scheduler: release_reservation(reservation_id)
    Scheduler->>LockTable: Release file_A & file_B
```"""

    def generate_consensus_workflow_diagram(self) -> str:
        """Diagram 5: Peer review consensus flow."""
        return """```mermaid
stateDiagram-v2
    [*] --> ProposalCreated
    ProposalCreated --> Voting: Dispatch Review Votes
    Voting --> ArchitectCheck: Chief Architect Override?
    ArchitectCheck --> Approved: Architect Approves
    ArchitectCheck --> WeightedCheck: Fallback to Weighted Majority
    WeightedCheck --> Approved: Approve Weight > Reject Weight
    WeightedCheck --> Rejected: Reject Weight >= Approve Weight
    Approved --> [*]
    Rejected --> [*]
```"""

    def generate_communication_graph_diagram(self) -> str:
        """Diagram 6: Top dynamic inter-agent communication channels."""
        telemetry = self.engine.get_telemetry()
        lines = ["```mermaid", "graph TD"]
        count = 0
        for s, recvs in telemetry.collaboration_graph.items():
            for r, c in recvs.items():
                if count < 15:
                    lines.append(f'    {s.replace("-", "_")} -->|"{c} msgs"| {r.replace("-", "_")}')
                    count += 1
        if count == 0:
            lines.append("    agent_arch -->|Standup & Reviews| agent_em")
            lines.append("    agent_em -->|Tasks| agent_be")
            lines.append("    agent_be -->|PR| agent_qa")
        lines.append("```")
        return "\n".join(lines)

    def shutdown(self) -> None:
        """Cleans up background threads and executor resources."""
        self.engine.shutdown()
