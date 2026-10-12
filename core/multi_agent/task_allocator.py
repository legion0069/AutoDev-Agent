"""
AutoDev Task Allocator Subsystem.

Provides deterministic multi-agent task allocation based on agent specialization,
current workload, historical success, task criticality, and capacity limits.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from core.multi_agent.agent_registry import AgentDescriptor, AgentRegistry, AgentStatus
from core.multi_agent.work_queue import WorkItem


class TaskAllocator:
    """
    Deterministic task allocation engine.
    Matches engineering tasks to the most suitable available agents
    using multi-factor objective scoring and strict tie-breaking.
    """

    def __init__(
        self,
        weight_specialization: float = 0.40,
        weight_workload: float = 0.25,
        weight_success: float = 0.25,
        weight_priority: float = 0.10,
    ) -> None:
        self.w_spec = weight_specialization
        self.w_work = weight_workload
        self.w_succ = weight_success
        self.w_prio = weight_priority

    def score_agent(
        self,
        agent: AgentDescriptor,
        task: WorkItem,
        is_critical: bool = False
    ) -> float:
        """
        Computes a deterministic matching score in [0.0, 100.0] for an agent and task.
        Returns -1.0 if the agent is strictly ineligible (e.g. offline or max workload exceeded).
        """
        # Ineligibility checks
        if agent.status in (AgentStatus.OFFLINE, AgentStatus.FAILED):
            return -1.0
        if agent.workload >= agent.max_workload:
            return -1.0

        # 1. Specialization Match (0.0 to 1.0)
        spec_score = 0.0
        if task.required_role is not None:
            if agent.role == task.required_role:
                spec_score += 0.6
            else:
                # Role mismatch penalty, but allow cross-functional if no strict requirement
                spec_score += 0.0
        else:
            spec_score += 0.5  # Generalist task

        # Capability coverage
        if task.required_capabilities:
            matched_caps = set(task.required_capabilities).intersection(agent.capabilities)
            cap_ratio = len(matched_caps) / len(task.required_capabilities)
            spec_score += 0.4 * cap_ratio
        else:
            spec_score += 0.4

        spec_score = min(1.0, max(0.0, spec_score))

        # 2. Workload Availability Score (0.0 to 1.0, higher means more available)
        availability = 1.0 - (agent.workload / max(1, agent.max_workload))
        availability = min(1.0, max(0.0, availability))

        # 3. Historical Success Score (0.0 to 1.0)
        success_score = agent.success_rate

        # 4. Agent Priority Tier Score (0.0 to 1.0)
        priority_score = min(1.0, max(0.0, agent.priority / 100.0))

        # Weighted aggregate
        base_score = (
            (self.w_spec * spec_score)
            + (self.w_work * availability)
            + (self.w_succ * success_score)
            + (self.w_prio * priority_score)
        ) * 100.0

        # Critical path boost: Give higher weight to success and priority for critical items
        if is_critical:
            critical_bonus = (success_score * 15.0) + (priority_score * 10.0)
            base_score += critical_bonus

        return round(base_score, 4)

    def allocate(
        self,
        task: WorkItem,
        registry: AgentRegistry,
        critical_path: Optional[List[str]] = None
    ) -> Optional[AgentDescriptor]:
        """
        Allocates the single best agent for a task deterministically.
        Returns the chosen AgentDescriptor, or None if no eligible agent exists.
        """
        is_critical = bool(critical_path and task.task_id in critical_path)
        all_agents = registry.get_all_agents()

        scored_candidates: List[tuple[float, int, float, str, AgentDescriptor]] = []

        for agent in all_agents:
            score = self.score_agent(agent, task, is_critical=is_critical)
            if score >= 0.0:
                # Deterministic sorting key:
                # (-score, agent.workload, -agent.success_rate, agent.agent_id)
                scored_candidates.append(
                    (-score, agent.workload, -agent.success_rate, agent.agent_id, agent)
                )

        if not scored_candidates:
            return None

        scored_candidates.sort()
        best_agent = scored_candidates[0][4]
        return best_agent

    def allocate_batch(
        self,
        tasks: List[WorkItem],
        registry: AgentRegistry,
        critical_path: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Allocates a batch of tasks deterministically to registered agents.
        Temporarily models workload changes during assignment to prevent over-allocation.
        Returns mapping of task_id -> agent_id.
        """
        assignments: Dict[str, str] = {}
        # Track simulated workload locally during batch planning
        virtual_workload: Dict[str, int] = {
            a.agent_id: a.workload for a in registry.get_all_agents()
        }

        # Sort tasks by priority descending, then critical path membership, then task_id
        crit_set: Set[str] = set(critical_path or [])
        sorted_tasks = sorted(
            tasks,
            key=lambda t: (-t.priority, 0 if t.task_id in crit_set else 1, t.task_id),
        )

        for task in sorted_tasks:
            candidates: List[tuple[float, int, str, AgentDescriptor]] = []
            for agent in registry.get_all_agents():
                # Temporarily set workload in virtual copy
                current_v_workload = virtual_workload.get(agent.agent_id, agent.workload)
                if current_v_workload >= agent.max_workload:
                    continue
                if agent.status in (AgentStatus.OFFLINE, AgentStatus.FAILED):
                    continue

                # Temporary descriptor with virtual workload
                temp_agent = AgentDescriptor(
                    agent_id=agent.agent_id,
                    name=agent.name,
                    role=agent.role,
                    capabilities=agent.capabilities,
                    priority=agent.priority,
                    workload=current_v_workload,
                    max_workload=agent.max_workload,
                    status=agent.status,
                    total_tasks_completed=agent.total_tasks_completed,
                    total_tasks_failed=agent.total_tasks_failed,
                    historical_durations=agent.historical_durations,
                )
                score = self.score_agent(temp_agent, task, is_critical=(task.task_id in crit_set))
                if score >= 0.0:
                    candidates.append((-score, current_v_workload, agent.agent_id, agent))

            if candidates:
                candidates.sort()
                chosen = candidates[0][3]
                assignments[task.task_id] = chosen.agent_id
                virtual_workload[chosen.agent_id] = virtual_workload.get(chosen.agent_id, 0) + 1

        return assignments
