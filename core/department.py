"""
department.py - Autonomous AI Department Models & Foundation (AutoDev Version 3.4)

Defines the core Department architecture:
- Roles, Authority levels, Budgets, Priorities, Capacities
- Health Scores, Performance Scores, Workloads, Blocked Tasks, Dependencies
- Department inbox processing, task lifecycle, and inter-department collaboration
- 100% Python Standard Library
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType

logger = logging.getLogger("AutoDev.Org.Department")


class DepartmentRole(str, enum.Enum):
    """Department functional roles across the enterprise."""
    EXECUTIVE = "EXECUTIVE"
    ENGINEERING_MANAGEMENT = "ENGINEERING_MANAGEMENT"
    ARCHITECTURE = "ARCHITECTURE"
    BACKEND = "BACKEND"
    FRONTEND = "FRONTEND"
    QA = "QA"
    SECURITY = "SECURITY"
    DEVOPS = "DEVOPS"
    RELEASE_MANAGEMENT = "RELEASE_MANAGEMENT"
    PRODUCT_MANAGEMENT = "PRODUCT_MANAGEMENT"
    BUSINESS_ANALYSIS = "BUSINESS_ANALYSIS"
    DOCUMENTATION = "DOCUMENTATION"
    CUSTOMER_FEEDBACK = "CUSTOMER_FEEDBACK"
    FINANCE = "FINANCE"
    COMPLIANCE = "COMPLIANCE"
    OPERATIONS = "OPERATIONS"


class DepartmentAuthorityLevel(int, enum.Enum):
    """Hierarchical decision authority levels."""
    OPERATIONAL = 1      # Individual contributors / basic actions
    SPECIALIST = 2       # Domain expert recommendations
    MANAGERIAL = 3       # Team allocation & scheduling
    DIRECTOR = 4         # Cross-department governance & technical sign-off
    EXECUTIVE = 5        # Final veto, company budget & strategic approval


@dataclass
class DepartmentTask:
    """Task assigned to a department."""
    task_id: str
    title: str
    description: str
    assigned_by: str
    priority: int = 1  # 1 (low) to 5 (critical)
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, BLOCKED, FAILED
    blocker_reason: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Department:
    """
    Autonomous AI Department unit.
    Operates with defined responsibilities, resource constraints,
    communication channels, and authority levels.
    """

    def __init__(
        self,
        name: str,
        role: DepartmentRole,
        authority: DepartmentAuthorityLevel = DepartmentAuthorityLevel.SPECIALIST,
        bus: Optional[CommunicationBus] = None,
        budget: float = 100000.0,
        priority: int = 5,
        capacity: int = 10,
        headcount: int = 3,
        dependencies: Optional[List[str]] = None,
        description: str = "",
    ) -> None:
        self._lock = threading.RLock()
        self.name = name
        self.role = role
        self.authority = authority
        self.bus = bus
        self.budget = float(budget)
        self.spent_budget = 0.0
        self.priority = priority
        self.capacity = capacity
        self.headcount = headcount
        self.dependencies = dependencies or []
        self.description = description or f"Autonomous {name} Department"

        # Operational state
        self.active_tasks: Dict[str, DepartmentTask] = {}
        self.completed_tasks: List[DepartmentTask] = []
        self.failed_tasks: List[DepartmentTask] = []
        self.blocked_tasks: Dict[str, DepartmentTask] = {}

        # Telemetry & Scores
        self.health_score: float = 100.0
        self.performance_score: float = 100.0
        self.confidence: float = 0.95
        self.total_processed_messages: int = 0
        self.last_active_timestamp: float = time.time()

        # Connect to communication bus
        if self.bus:
            self.bus.register_entity(self.name)

        logger.debug("Department '%s' [%s] initialized.", self.name, self.role.value)

    @property
    def current_workload(self) -> int:
        """Returns the number of tasks currently in progress or blocked."""
        with self._lock:
            return len(self.active_tasks) + len(self.blocked_tasks)

    @property
    def utilization_rate(self) -> float:
        """Workload relative to maximum capacity (0.0 to 1.0+)."""
        with self._lock:
            return self.current_workload / max(1, self.capacity)

    def set_bus(self, bus: CommunicationBus) -> None:
        """Attaches communication bus."""
        with self._lock:
            self.bus = bus
            self.bus.register_entity(self.name)

    def assign_task(
        self,
        task_id: str,
        title: str,
        description: str,
        assigned_by: str,
        priority: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DepartmentTask:
        """Assigns a new task to this department."""
        with self._lock:
            task = DepartmentTask(
                task_id=task_id,
                title=title,
                description=description,
                assigned_by=assigned_by,
                priority=priority,
                status="IN_PROGRESS" if self.current_workload < self.capacity else "BLOCKED",
                blocker_reason="Department at maximum capacity" if self.current_workload >= self.capacity else None,
                metadata=metadata or {},
            )
            if task.status == "IN_PROGRESS":
                self.active_tasks[task_id] = task
            else:
                self.blocked_tasks[task_id] = task

            self._update_scores()
            logger.info("Task '%s' assigned to department '%s' (Status: %s).", task_id, self.name, task.status)
            return task

    def complete_task(self, task_id: str, artifacts: Optional[List[str]] = None, cost: float = 0.0) -> Optional[DepartmentTask]:
        """Marks an active or blocked task as completed."""
        with self._lock:
            task = self.active_tasks.pop(task_id, None) or self.blocked_tasks.pop(task_id, None)
            if not task:
                return None

            task.status = "COMPLETED"
            task.completed_at = time.time()
            if artifacts:
                task.artifacts.extend(artifacts)
            self.completed_tasks.append(task)
            self.spend_budget(cost)

            # Try to unblock pending tasks
            self._rebalance_workload()
            self._update_scores()
            self.last_active_timestamp = time.time()

            logger.info("Department '%s' completed task '%s'.", self.name, task_id)
            return task

    def fail_task(self, task_id: str, reason: str) -> Optional[DepartmentTask]:
        """Marks a task as failed."""
        with self._lock:
            task = self.active_tasks.pop(task_id, None) or self.blocked_tasks.pop(task_id, None)
            if not task:
                return None

            task.status = "FAILED"
            task.blocker_reason = reason
            task.completed_at = time.time()
            self.failed_tasks.append(task)

            self._rebalance_workload()
            self._update_scores()
            self.last_active_timestamp = time.time()

            logger.warning("Department '%s' failed task '%s': %s", self.name, task_id, reason)
            return task

    def block_task(self, task_id: str, reason: str) -> Optional[DepartmentTask]:
        """Marks an active task as blocked."""
        with self._lock:
            task = self.active_tasks.pop(task_id, None)
            if not task:
                return None

            task.status = "BLOCKED"
            task.blocker_reason = reason
            self.blocked_tasks[task_id] = task
            self._update_scores()
            logger.warning("Department '%s' task '%s' BLOCKED: %s", self.name, task_id, reason)
            return task

    def unblock_task(self, task_id: str) -> Optional[DepartmentTask]:
        """Unblocks a blocked task."""
        with self._lock:
            task = self.blocked_tasks.pop(task_id, None)
            if not task:
                return None

            task.status = "IN_PROGRESS"
            task.blocker_reason = None
            self.active_tasks[task_id] = task
            self._update_scores()
            logger.info("Department '%s' unblocked task '%s'.", self.name, task_id)
            return task

    def spend_budget(self, amount: float) -> bool:
        """Deducts expenses from the department budget."""
        with self._lock:
            self.spent_budget += max(0.0, amount)
            return self.spent_budget <= self.budget

    def allocate_budget(self, additional_amount: float) -> float:
        """Increases department budget."""
        with self._lock:
            self.budget += max(0.0, additional_amount)
            return self.budget

    def send_message(
        self,
        receiver: str,
        message_type: OrgMessageType,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        thread_id: Optional[str] = None,
        response_required: bool = False,
    ) -> Optional[OrgMessage]:
        """Dispatches an outbound message over the bus."""
        if not self.bus:
            logger.warning("Department '%s' has no bus attached.", self.name)
            return None

        msg = OrgMessage(
            sender=self.name,
            receiver=receiver,
            priority=priority,
            message_type=message_type,
            payload=payload,
            thread_id=thread_id or f"THREAD-{self.name[:4]}-{int(time.time()*1000)%100000}",
            response_required=response_required,
        )
        self.bus.send_message(msg)
        self.last_active_timestamp = time.time()
        return msg

    def process_inbox(self) -> List[OrgMessage]:
        """Fetches and processes unread messages from communication bus inbox."""
        if not self.bus:
            return []

        messages = self.bus.get_messages(self.name, unread_only=True)
        with self._lock:
            self.total_processed_messages += len(messages)
            if messages:
                self.last_active_timestamp = time.time()
        return messages

    def escalate_issue(
        self,
        escalate_to: str,
        issue_title: str,
        details: Dict[str, Any],
        urgency: MessagePriority = MessagePriority.CRITICAL,
    ) -> Optional[OrgMessage]:
        """Escalates a blocker or conflict to executive management."""
        payload = {
            "escalation_title": issue_title,
            "escalating_department": self.name,
            "authority_level": int(self.authority.value),
            "details": details,
            "timestamp": time.time(),
        }
        return self.send_message(
            receiver=escalate_to,
            message_type=OrgMessageType.ESCALATION,
            payload=payload,
            priority=urgency,
            response_required=True,
        )

    def _rebalance_workload(self) -> None:
        """Pulls eligible blocked tasks back to active if capacity allows."""
        while len(self.active_tasks) < self.capacity and self.blocked_tasks:
            # Pick first blocked task that was blocked by capacity
            capacity_blocked_id = None
            for tid, t in self.blocked_tasks.items():
                if t.blocker_reason == "Department at maximum capacity":
                    capacity_blocked_id = tid
                    break
            if capacity_blocked_id:
                self.unblock_task(capacity_blocked_id)
            else:
                break

    def _update_scores(self) -> None:
        """Re-evaluates health, performance, and confidence metrics."""
        # Health Score: starts at 100, penalized by blocked tasks and overload
        overload = max(0, self.current_workload - self.capacity)
        blocked_penalty = len(self.blocked_tasks) * 12.0
        overload_penalty = overload * 15.0
        self.health_score = max(5.0, min(100.0, 100.0 - blocked_penalty - overload_penalty))

        # Performance Score: based on task success vs failure ratio
        total_finished = len(self.completed_tasks) + len(self.failed_tasks)
        if total_finished > 0:
            success_ratio = len(self.completed_tasks) / total_finished
            self.performance_score = max(10.0, round(success_ratio * 100.0, 1))
        else:
            self.performance_score = 100.0

        # Confidence: weighted blend of health and performance
        self.confidence = round(max(0.2, (self.health_score * 0.5 + self.performance_score * 0.5) / 100.0), 3)

    def get_status_report(self) -> Dict[str, Any]:
        """Generates comprehensive status telemetry for dashboards and meetings."""
        with self._lock:
            return {
                "name": self.name,
                "role": self.role.value,
                "authority": self.authority.value,
                "budget_total": self.budget,
                "budget_spent": self.spent_budget,
                "budget_remaining": max(0.0, self.budget - self.spent_budget),
                "priority": self.priority,
                "capacity": self.capacity,
                "current_workload": self.current_workload,
                "utilization_rate": round(self.utilization_rate, 2),
                "active_tasks_count": len(self.active_tasks),
                "blocked_tasks_count": len(self.blocked_tasks),
                "completed_tasks_count": len(self.completed_tasks),
                "failed_tasks_count": len(self.failed_tasks),
                "health_score": round(self.health_score, 1),
                "performance_score": round(self.performance_score, 1),
                "confidence": self.confidence,
                "dependencies": list(self.dependencies),
                "headcount": self.headcount,
                "blocked_task_reasons": {tid: t.blocker_reason for tid, t in self.blocked_tasks.items()},
                "last_active": self.last_active_timestamp,
            }
