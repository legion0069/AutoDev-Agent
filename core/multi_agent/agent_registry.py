"""
AutoDev Agent Registry Subsystem.

Provides thread-safe agent registration, capability discovery, health monitoring,
heartbeat tracking, and operational metrics.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("AutoDev.MultiAgent.Registry")


class AgentRole(str, Enum):
    """Specialized engineering and leadership roles across the organization."""
    CEO = "CEO"
    CTO = "CTO"
    ENGINEERING_DIRECTOR = "Engineering Director"
    CHIEF_ARCHITECT = "Chief Architect"
    ENGINEERING_MANAGER = "Engineering Manager"
    TASK_SCHEDULER = "Task Scheduler"
    BACKEND_ENGINEER = "Backend Engineer"
    FRONTEND_ENGINEER = "Frontend Engineer"
    AI_ENGINEER = "AI Engineer"
    DATABASE_ENGINEER = "Database Engineer"
    INFRASTRUCTURE_ENGINEER = "Infrastructure Engineer"
    DEVOPS_ENGINEER = "DevOps Engineer"
    QA_ENGINEER = "QA Engineer"
    SECURITY_ENGINEER = "Security Engineer"
    DOCUMENTATION_ENGINEER = "Documentation Engineer"
    RELEASE_MANAGER = "Release Manager"


class AgentStatus(str, Enum):
    """Operational status of a registered agent."""
    IDLE = "IDLE"
    BUSY = "BUSY"
    ACTIVE = "ACTIVE"
    OFFLINE = "OFFLINE"
    FAILED = "FAILED"


@dataclass
class AgentDescriptor:
    """
    Metadata, operational metrics, and capability profile for a specialized agent.
    """
    agent_id: str
    name: str
    role: AgentRole
    capabilities: List[str] = field(default_factory=list)
    priority: int = 50  # 1 (lowest) to 100 (highest)
    workload: int = 0  # Active in-flight tasks
    max_workload: int = 5
    status: AgentStatus = AgentStatus.IDLE
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_heartbeat: float = field(default_factory=time.time)
    registered_at: float = field(default_factory=time.time)
    completed_tasks_count: int = 0
    failed_tasks_count: int = 0
    total_execution_time: float = 0.0
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    historical_durations: List[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.role, str):
            self.role = AgentRole(self.role)
        if isinstance(self.status, str):
            self.status = AgentStatus(self.status)
        if self.completed_tasks_count and not self.total_tasks_completed:
            self.total_tasks_completed = self.completed_tasks_count
        if self.total_tasks_completed and not self.completed_tasks_count:
            self.completed_tasks_count = self.total_tasks_completed
        if self.failed_tasks_count and not self.total_tasks_failed:
            self.total_tasks_failed = self.failed_tasks_count
        if self.total_tasks_failed and not self.failed_tasks_count:
            self.failed_tasks_count = self.total_tasks_failed

    @property
    def historical_success_rate(self) -> float:
        """Returns success ratio between 0.0 and 1.0 (defaults to 1.0 if no tasks run)."""
        total = self.total_tasks_completed + self.total_tasks_failed
        if total == 0:
            return 1.0
        return round(self.total_tasks_completed / float(total), 4)

    @property
    def success_rate(self) -> float:
        """Alias for historical_success_rate."""
        return self.historical_success_rate

    @property
    def average_duration(self) -> float:
        """Returns average task execution duration in seconds."""
        total = self.total_tasks_completed + self.total_tasks_failed
        if total == 0:
            return 0.0
        return round(self.total_execution_time / float(total), 4)

    @property
    def is_available(self) -> bool:
        """Checks whether the agent can accept additional tasks."""
        return (
            self.status not in (AgentStatus.OFFLINE, AgentStatus.FAILED)
            and self.workload < self.max_workload
        )

    def record_task_completion(
        self,
        arg1: Union[float, bool] = 0.0,
        arg2: Union[float, bool] = True,
        success: Optional[bool] = None,
        duration: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """Updates internal telemetry metrics upon task finish."""
        if success is not None:
            is_success = bool(success)
        elif isinstance(arg1, bool):
            is_success = arg1
        elif isinstance(arg2, bool):
            is_success = arg2
        else:
            is_success = True

        if duration is not None:
            dur = float(duration)
        elif isinstance(arg1, (int, float)) and not isinstance(arg1, bool):
            dur = float(arg1)
        elif isinstance(arg2, (int, float)) and not isinstance(arg2, bool):
            dur = float(arg2)
        else:
            dur = 0.0

        if is_success:
            self.completed_tasks_count += 1
            self.total_tasks_completed += 1
        else:
            self.failed_tasks_count += 1
            self.total_tasks_failed += 1

        self.total_execution_time += max(0.0, dur)
        self.historical_durations.append(dur)
        self.workload = max(0, self.workload - 1)
        if self.workload == 0 and self.status == AgentStatus.BUSY:
            self.status = AgentStatus.IDLE

    def to_dict(self) -> Dict[str, Any]:
        """Converts descriptor to serializable dictionary."""
        d = asdict(self)
        d["role"] = self.role.value if isinstance(self.role, Enum) else str(self.role)
        d["status"] = self.status.value if isinstance(self.status, Enum) else str(self.status)
        d["historical_success_rate"] = self.historical_success_rate
        d["success_rate"] = self.success_rate
        d["average_duration"] = self.average_duration
        return d


class _CountableInt(int):
    """Integer that can also be called as a method for dual property/method compatibility."""
    def __call__(self) -> int:
        return int(self)


class AgentRegistry:
    """
    Central thread-safe registry and health supervisor for all collaborating agents.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._agents: Dict[str, AgentDescriptor] = {}

    @property
    def count(self) -> _CountableInt:
        """Returns total registered agent count as countable int."""
        with self._lock:
            return _CountableInt(len(self._agents))

    def register_agent(self, descriptor: AgentDescriptor) -> bool:
        """Registers a new agent descriptor. Raises ValueError if already registered."""
        with self._lock:
            if descriptor.agent_id in self._agents:
                raise ValueError(f"Agent '{descriptor.agent_id}' already registered.")
            self._agents[descriptor.agent_id] = copy.deepcopy(descriptor)
            logger.debug("Registered agent: %s (%s)", descriptor.agent_id, descriptor.role.value)
            return True

    def remove_agent(self, agent_id: str) -> bool:
        """Unregisters an agent from the platform."""
        with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                return True
            return False

    def get_agent(self, agent_id: str) -> Optional[AgentDescriptor]:
        """Retrieves a deepcopy of an agent descriptor by ID."""
        with self._lock:
            agent = self._agents.get(agent_id)
            return copy.deepcopy(agent) if agent else None

    def discover_agents(
        self,
        role: Optional[AgentRole] = None,
        capability: Optional[str] = None,
        required_capabilities: Optional[List[str]] = None,
        available_only: bool = False,
    ) -> List[AgentDescriptor]:
        """
        Discovers agents filtered by role, capability keyword(s), and availability.
        Returns sorted list by descending priority and ascending current workload.
        """
        with self._lock:
            matches: List[AgentDescriptor] = []
            for agent in self._agents.values():
                if role is not None and agent.role != role:
                    continue
                if capability is not None:
                    cap_clean = capability.lower()
                    if not any(cap_clean in c.lower() for c in agent.capabilities):
                        continue
                if required_capabilities:
                    agent_caps = {c.lower() for c in agent.capabilities}
                    if not all(rc.lower() in agent_caps for rc in required_capabilities):
                        continue
                if available_only and not agent.is_available:
                    continue
                matches.append(copy.deepcopy(agent))

            # Deterministic sort: higher priority first, lower workload first, then agent_id
            matches.sort(key=lambda a: (-a.priority, a.workload, a.agent_id))
            return matches

    def agent_capabilities(self, agent_id: str) -> List[str]:
        """Returns listed capabilities for the specified agent."""
        with self._lock:
            agent = self._agents.get(agent_id)
            return list(agent.capabilities) if agent else []

    def heartbeat(self, agent_id: str, status: Optional[AgentStatus] = None) -> bool:
        """Records agent heartbeat signal and updates status."""
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return False
            agent.last_heartbeat = time.time()
            if status is not None:
                agent.status = status
            elif agent.status == AgentStatus.OFFLINE:
                agent.status = AgentStatus.IDLE
            return True

    def set_status(self, agent_id: str, status: AgentStatus) -> bool:
        """Sets status of a registered agent."""
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return False
            agent.status = status
            return True

    def update_workload(self, agent_id: str, delta: int) -> int:
        """Adjusts active workload count for an agent and returns new workload."""
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return 0
            agent.workload = max(0, agent.workload + delta)
            if agent.workload >= agent.max_workload:
                agent.status = AgentStatus.BUSY
            elif agent.workload == 0 and agent.status == AgentStatus.BUSY:
                agent.status = AgentStatus.IDLE
            return agent.workload

    def record_completion(
        self,
        agent_id: str,
        success: bool = True,
        duration: float = 0.0
    ) -> None:
        """Records task finish on an agent descriptor."""
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent:
                agent.record_task_completion(duration=duration, success=success)

    def check_health(
        self,
        stale_timeout_seconds: Optional[float] = None,
        timeout_seconds: float = 60.0,
    ) -> List[AgentDescriptor]:
        """
        Inspects agent heartbeats. Marks agents past timeout as OFFLINE.
        Returns list of unhealthy (offline) agents.
        """
        now = time.time()
        stale_limit = stale_timeout_seconds if stale_timeout_seconds is not None else timeout_seconds
        with self._lock:
            unhealthy: List[AgentDescriptor] = []
            for agent in self._agents.values():
                if (now - agent.last_heartbeat) > stale_limit:
                    agent.status = AgentStatus.OFFLINE
                    unhealthy.append(copy.deepcopy(agent))
            return unhealthy

    def get_all_agents(self) -> List[AgentDescriptor]:
        """Returns all registered agent descriptors."""
        with self._lock:
            return [copy.deepcopy(a) for a in self._agents.values()]

    def clear(self) -> None:
        """Clears all registered agents."""
        with self._lock:
            self._agents.clear()
