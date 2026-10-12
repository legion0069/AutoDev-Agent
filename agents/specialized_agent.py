"""
AutoDev Collaboration Framework - Base Specialized Engineering Agent (v2.8)
============================================================================
Abstract base foundation for all specialized engineering agents in the
collaborative multi-agent software engineering organization.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from core.collaboration.collaboration_models import (
    AgentMessage,
    AgentRole,
    MessageType,
    Proposal,
    TaskAssignment,
)

logger = logging.getLogger("autodev.agents.specialized")


class SpecializedAgent(ABC):
    """
    Base autonomous engineering agent with full multi-agent collaboration,
    messaging, workspace locking, code staging, review, and consensus capabilities.
    """

    def __init__(
        self,
        name: str,
        role: AgentRole,
        llm_client: Optional[Any] = None,
        bus: Optional[Any] = None,
        workspace: Optional[Any] = None,
    ):
        self.name = name
        self.role = role
        self.llm_client = llm_client
        self.bus = bus
        self.workspace = workspace
        self.collaboration_manager: Optional[Any] = None
        self._assigned_tasks: List[TaskAssignment] = []
        self._completed_tasks: List[TaskAssignment] = []

    def bind_collaboration_manager(self, manager: Any) -> None:
        """Connect this agent to the central CollaborationManager."""
        self.collaboration_manager = manager
        if hasattr(manager, "bus"):
            self.bus = manager.bus
        if hasattr(manager, "workspace"):
            self.workspace = manager.workspace

    # ------------------------------------------------------------------
    # Inter-Agent Messaging Protocols
    # ------------------------------------------------------------------

    def send_message(
        self,
        receiver: str,
        message_type: MessageType,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> AgentMessage:
        """Send a structured collaboration message across the bus."""
        if not self.bus:
            raise RuntimeError(f"Agent '{self.name}' has no communication bus bound.")

        msg = AgentMessage(
            sender=self.name,
            receiver=receiver,
            message_type=message_type,
            payload=payload,
            task_id=task_id,
        )
        return self.bus.publish(msg)

    def request(
        self,
        receiver: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
        timeout: float = 10.0,
    ) -> Optional[AgentMessage]:
        """Send a synchronous direct REQUEST and wait for RESPONSE."""
        if not self.bus:
            raise RuntimeError(f"Agent '{self.name}' has no communication bus bound.")
        return self.bus.send_request(
            sender=self.name,
            receiver=receiver,
            payload=payload,
            task_id=task_id,
            timeout=timeout,
        )

    def receive_messages(self, filter_type: Optional[MessageType] = None) -> List[AgentMessage]:
        """Fetch all pending messages from this agent's mailbox."""
        if not self.bus:
            return []
        return self.bus.get_mailbox(self.name, filter_type=filter_type)

    def report_blocker(self, task_id: str, reason: str) -> None:
        """Broadcast a task blocker to the entire organization."""
        if self.bus:
            self.bus.report_blocker(self.name, task_id, reason)

    def resolve_blocker(self, task_id: str, resolution_notes: str) -> None:
        """Resolve a previously declared blocker."""
        if self.bus:
            self.bus.resolve_blocker(self.name, task_id, resolution_notes)

    # ------------------------------------------------------------------
    # Workspace & Lock Management
    # ------------------------------------------------------------------

    def acquire_lock(self, file_path: str, is_exclusive: bool = True, ttl: float = 60.0) -> bool:
        """Acquire an atomic read/write lock on a file in shared workspace."""
        if not self.workspace:
            return True
        lock = self.workspace.acquire_lock(
            file_path=file_path,
            holder=self.name,
            role=self.role,
            is_exclusive=is_exclusive,
            ttl=ttl,
        )
        return lock is not None

    def release_lock(self, file_path: str) -> bool:
        """Release a held lock on a workspace file."""
        if not self.workspace:
            return True
        return self.workspace.release_lock(file_path=file_path, holder=self.name)

    def stage_code(self, file_path: str, content: str, commit_message: str = "") -> None:
        """Stage modified or generated file content into shared workspace memory."""
        if self.workspace:
            self.workspace.stage_change(
                file_path=file_path,
                author_id=self.name,
                role=self.role,
                content=content,
                commit_message=commit_message,
            )

    def submit_review(
        self,
        file_path: str,
        comment: str,
        is_approved: bool = True,
        severity: str = "INFO",
    ) -> None:
        """Submit a formal review or approval for a staged change."""
        if self.workspace:
            self.workspace.add_review_comment(
                file_path=file_path,
                author_id=self.name,
                role=self.role,
                comment=comment,
                severity=severity,
                is_blocking=not is_approved,
            )
            if is_approved:
                self.workspace.approve_staged_change(file_path, reviewer_id=self.name)
            else:
                self.workspace.reject_staged_change(file_path, reviewer_id=self.name, reason=comment)

    # ------------------------------------------------------------------
    # Proposals & Consensus
    # ------------------------------------------------------------------

    def create_proposal(
        self,
        title: str,
        description: str,
        confidence: float = 0.90,
        tradeoffs: Optional[List[str]] = None,
        spec: Optional[Dict[str, Any]] = None,
    ) -> Proposal:
        """Create a structured engineering proposal for consensus voting."""
        return Proposal(
            proposer=self.name,
            role=self.role,
            title=title,
            description=description,
            confidence=confidence,
            tradeoffs=tradeoffs or [],
            spec=spec or {},
        )

    # ------------------------------------------------------------------
    # Task Execution Interface
    # ------------------------------------------------------------------

    @abstractmethod
    def execute_task(
        self,
        task: TaskAssignment,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute domain-specific engineering task.
        Must return execution summary dictionary with actions, artifacts, and staged files.
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}' role='{self.role.value}'>"
