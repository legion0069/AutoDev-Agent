"""
AutoDev Communication Bus (v2.8)
================================
Thread-safe, deterministic inter-agent messaging protocol and collaboration event bus.
Enables structured communication, requests/responses, reviews, approvals, blocker tracking,
and topic pub/sub across specialized engineering agents.
"""

from __future__ import annotations

import collections
import logging
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from core.collaboration.collaboration_models import (
    AgentMessage,
    AgentRole,
    MessageStatus,
    MessageType,
)

logger = logging.getLogger("AutoDev.CommunicationBus")


class CommunicationBus:
    """
    Central deterministic communication bus connecting all specialized agents.
    Provides direct point-to-point messaging, broadcasts, request-response synchronization,
    blocker propagation, and historical audit logging.
    """

    def __init__(self, default_timeout: float = 30.0):
        self.default_timeout = default_timeout
        self._lock = threading.RLock()

        # Registered agents: agent_id -> {role, callback, direct_handler, queue}
        self._agents: Dict[str, Dict[str, Any]] = {}

        # Message storage: message_id -> AgentMessage
        self._messages: Dict[str, AgentMessage] = {}
        self._history: List[AgentMessage] = []

        # Mailboxes: agent_id -> list of unread message_ids
        self._mailboxes: Dict[str, List[str]] = collections.defaultdict(list)

        # Pending request-response events: correlation_id -> (threading.Event, response_holder)
        self._pending_requests: Dict[str, Tuple[threading.Event, List[AgentMessage]]] = {}

        # Direct handlers: agent_id -> Callable[[AgentMessage], Any]
        self._direct_handlers: Dict[str, Callable[[AgentMessage], Any]] = {}

        # Blocker registry: task_id -> {blocker_id, sender, description, timestamp, resolved}
        self._blockers: Dict[str, Dict[str, Any]] = {}

        # Topic subscriptions: topic -> set of callbacks
        self._topic_subscriptions: Dict[str, List[Callable[[AgentMessage], None]]] = collections.defaultdict(list)

    def register_agent(
        self,
        agent_id: str,
        role: Union[AgentRole, str] = AgentRole.GENERAL,
        callback: Optional[Callable[[AgentMessage], Optional[AgentMessage]]] = None,
    ) -> None:
        """Registers an agent with the bus and initializes its mailbox."""
        if isinstance(role, str):
            try:
                role = AgentRole(role)
            except ValueError:
                role = AgentRole.GENERAL

        with self._lock:
            self._agents[agent_id] = {
                "agent_id": agent_id,
                "role": role,
                "callback": callback,
                "registered_at": time.time(),
            }
            if agent_id not in self._mailboxes:
                self._mailboxes[agent_id] = []

    def unregister_agent(self, agent_id: str) -> None:
        """Removes an agent from active bus registration."""
        with self._lock:
            self._agents.pop(agent_id, None)
            self._mailboxes.pop(agent_id, None)
            self._direct_handlers.pop(agent_id, None)

    def register_direct_handler(self, agent_name: str, handler: Callable[[AgentMessage], Any]) -> None:
        """Registers a synchronous response handler for direct REQUEST calls."""
        with self._lock:
            self._direct_handlers[agent_name] = handler

    def is_agent_registered(self, agent_id: str) -> bool:
        with self._lock:
            return agent_id in self._agents

    def get_registered_agents(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "agent_id": aid,
                    "role": info["role"].value if hasattr(info["role"], "value") else str(info["role"]),
                    "registered_at": info["registered_at"],
                }
                for aid, info in self._agents.items()
            ]

    # ------------------------------------------------------------------
    # Message Routing & Publishing
    # ------------------------------------------------------------------

    def send_message(self, message: AgentMessage) -> AgentMessage:
        """Routes an AgentMessage to its recipient, mailbox, or broadcast pool."""
        with self._lock:
            message.timestamp = time.time() if not message.timestamp else message.timestamp
            self._messages[message.message_id] = message
            self._history.append(message)

            # Handle correlation for waiting request-response callers
            if (
                message.correlation_id
                and message.correlation_id in self._pending_requests
                and message.message_type != MessageType.REQUEST
            ):
                event, resp_list = self._pending_requests[message.correlation_id]
                resp_list.append(message)
                event.set()

            # Route to broadcast or specific agent
            if message.receiver.lower() in ("broadcast", "*", "all"):
                recipients = [aid for aid in self._agents.keys() if aid != message.sender]
                for recipient in recipients:
                    self._deliver_to_agent(recipient, message)
                message.status = MessageStatus.DELIVERED
            else:
                self._deliver_to_agent(message.receiver, message)

            # Notify topic subscribers if message specifies a topic in payload
            topic = message.payload.get("topic")
            if topic and topic in self._topic_subscriptions:
                for sub_cb in self._topic_subscriptions[topic]:
                    try:
                        sub_cb(message)
                    except Exception as e:
                        logger.error("Error in topic callback for %s: %s", topic, e)

            return message

    # Alias for publish
    publish = send_message

    def _deliver_to_agent(self, recipient_id: str, message: AgentMessage) -> None:
        """Delivers a message to an agent's mailbox and invokes its callback/direct handler."""
        self._mailboxes[recipient_id].append(message.message_id)
        message.status = MessageStatus.DELIVERED

        # Direct handler invocation if synchronous request
        if message.message_type == MessageType.REQUEST and recipient_id in self._direct_handlers:
            handler = self._direct_handlers[recipient_id]
            try:
                res_payload = handler(message)
                resp_dict = res_payload if isinstance(res_payload, dict) else {"result": res_payload}
                reply_msg = AgentMessage(
                    sender=recipient_id,
                    receiver=message.sender,
                    task_id=message.task_id,
                    message_type=MessageType.RESPONSE,
                    payload=resp_dict,
                    correlation_id=message.correlation_id,
                    reply_to=message.message_id,
                )
                self.send_message(reply_msg)
                return
            except Exception as e:
                logger.error("Error executing direct handler for %s: %s", recipient_id, e)

        # Immediate callback invocation
        agent_info = self._agents.get(recipient_id)
        if agent_info and agent_info.get("callback"):
            cb = agent_info["callback"]
            try:
                reply_msg = cb(message)
                if reply_msg and isinstance(reply_msg, AgentMessage):
                    self.send_message(reply_msg)
            except Exception as e:
                logger.error("Error executing callback for agent %s on message %s: %s", recipient_id, message.message_id, e)

    def send_request(
        self,
        sender: str,
        receiver: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
        timeout: Optional[float] = None,
        message_type: MessageType = MessageType.REQUEST,
    ) -> Optional[AgentMessage]:
        """Sends a synchronous request to an agent and waits for a matching response."""
        correlation_id = f"corr_{uuid.uuid4().hex[:10]}"
        event = threading.Event()
        resp_list: List[AgentMessage] = []

        with self._lock:
            self._pending_requests[correlation_id] = (event, resp_list)

        msg = AgentMessage(
            sender=sender,
            receiver=receiver,
            task_id=task_id,
            message_type=message_type,
            payload=payload,
            correlation_id=correlation_id,
        )
        self.send_message(msg)

        wait_time = timeout if timeout is not None else self.default_timeout
        signaled = event.wait(timeout=wait_time)

        with self._lock:
            self._pending_requests.pop(correlation_id, None)

        if signaled and resp_list:
            return resp_list[0]
        return None

    def reply(
        self,
        original_message: AgentMessage,
        payload: Dict[str, Any],
        sender: Optional[str] = None,
        message_type: MessageType = MessageType.RESPONSE,
    ) -> AgentMessage:
        """Constructs and routes a reply to an incoming message."""
        reply_msg = AgentMessage(
            sender=sender or original_message.receiver,
            receiver=original_message.sender,
            task_id=original_message.task_id,
            message_type=message_type,
            payload=payload,
            correlation_id=original_message.correlation_id,
            reply_to=original_message.message_id,
        )
        return self.send_message(reply_msg)

    def broadcast(
        self,
        sender: str,
        message_type: MessageType,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> AgentMessage:
        """Broadcasts a notification or event to all registered agents."""
        msg = AgentMessage(
            sender=sender,
            receiver="*",
            task_id=task_id,
            message_type=message_type,
            payload=payload,
        )
        return self.send_message(msg)

    # ------------------------------------------------------------------
    # Blockers
    # ------------------------------------------------------------------

    def report_blocker(
        self,
        sender: str,
        task_id: str,
        blocker_description: str,
        required_dependency: Optional[str] = None,
    ) -> AgentMessage:
        """Registers an active task blocker and broadcasts a BLOCKER message."""
        blocker_id = f"blk_{uuid.uuid4().hex[:8]}"
        with self._lock:
            self._blockers[task_id] = {
                "blocker_id": blocker_id,
                "task_id": task_id,
                "sender": sender,
                "description": blocker_description,
                "required_dependency": required_dependency,
                "timestamp": time.time(),
                "resolved": False,
            }

        payload = {
            "blocker_id": blocker_id,
            "task_id": task_id,
            "description": blocker_description,
            "required_dependency": required_dependency,
        }
        return self.broadcast(
            sender=sender,
            message_type=MessageType.BLOCKER,
            payload=payload,
            task_id=task_id,
        )

    def resolve_blocker(
        self,
        sender: str,
        task_id: str,
        resolution_notes: str = "",
    ) -> Optional[AgentMessage]:
        """Marks a blocker as resolved and notifies agents."""
        with self._lock:
            if task_id in self._blockers:
                self._blockers[task_id]["resolved"] = True
                self._blockers[task_id]["resolved_at"] = time.time()
                self._blockers[task_id]["resolved_by"] = sender
                self._blockers[task_id]["resolution_notes"] = resolution_notes

        payload = {
            "task_id": task_id,
            "resolved_by": sender,
            "resolution_notes": resolution_notes,
        }
        return self.broadcast(
            sender=sender,
            message_type=MessageType.NOTIFICATION,
            payload=payload,
            task_id=task_id,
        )

    def get_active_blockers(self) -> List[str]:
        """Returns list of task_ids with unresolved blockers."""
        with self._lock:
            return [tid for tid, b in self._blockers.items() if not b.get("resolved", False)]

    # ------------------------------------------------------------------
    # Mailbox & History Queries
    # ------------------------------------------------------------------

    def get_messages_for_agent(
        self,
        agent_id: str,
        unread_only: bool = True,
    ) -> List[AgentMessage]:
        with self._lock:
            msg_ids = self._mailboxes.get(agent_id, [])
            messages = [self._messages[mid] for mid in msg_ids if mid in self._messages]
            if unread_only:
                self._mailboxes[agent_id] = []
            return messages

    def get_mailbox(self, agent_id: str, filter_type: Optional[MessageType] = None) -> List[AgentMessage]:
        """Retrieve and drain unread messages for an agent with optional message_type filter."""
        with self._lock:
            msg_ids = list(self._mailboxes.get(agent_id, []))
            messages = [self._messages[mid] for mid in msg_ids if mid in self._messages]
            if filter_type:
                messages = [m for m in messages if m.message_type == filter_type]
            # Drain returned messages from mailbox
            drained_ids = {m.message_id for m in messages}
            self._mailboxes[agent_id] = [mid for mid in self._mailboxes.get(agent_id, []) if mid not in drained_ids]
            return messages

    def get_all_messages(self) -> List[AgentMessage]:
        with self._lock:
            return list(self._history)

    def get_history(
        self,
        task_id: Optional[str] = None,
        sender: Optional[str] = None,
        receiver: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        limit: int = 100,
    ) -> List[AgentMessage]:
        with self._lock:
            results = []
            for msg in reversed(self._history):
                if task_id and msg.task_id != task_id:
                    continue
                if sender and msg.sender != sender:
                    continue
                if receiver and msg.receiver not in (receiver, "broadcast", "*", "all"):
                    continue
                if message_type and msg.message_type != message_type:
                    continue
                results.append(msg)
                if len(results) >= limit:
                    break
            return list(reversed(results))

    def subscribe_topic(self, topic: str, callback: Callable[[AgentMessage], None]) -> None:
        with self._lock:
            self._topic_subscriptions[topic].append(callback)

    def clear(self) -> None:
        with self._lock:
            self._messages.clear()
            self._history.clear()
            self._mailboxes.clear()
            self._pending_requests.clear()
            self._direct_handlers.clear()
            self._blockers.clear()
            self._topic_subscriptions.clear()


# Alias for compatibility
CollaborationBus = CommunicationBus
