"""
communication_bus.py - Enterprise Multi-Agent Communication Bus (AutoDev Version 3.4)

Provides an enterprise-grade, deterministic, thread-safe message bus supporting:
- Task Requests, Status Updates, Escalations, Approvals, Reviews
- Architecture Decisions, Incident Reports, Risk Alerts, Security Findings
- Meeting Minutes, Release Approvals
- Thread tracking, correlation IDs, priority queuing, direct messaging & broadcast
- Pub/Sub topics, acknowledgement tracking, and searchable audit logs
- 100% Python Standard Library (no external queuing or messaging brokers)
"""

from __future__ import annotations

import enum
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("AutoDev.Org.CommunicationBus")


class OrgMessageType(str, enum.Enum):
    """Enterprise organizational message types."""
    TASK_REQUEST = "TASK_REQUEST"
    STATUS_UPDATE = "STATUS_UPDATE"
    ESCALATION = "ESCALATION"
    APPROVAL = "APPROVAL"
    REVIEW = "REVIEW"
    ARCHITECTURE_DECISION = "ARCHITECTURE_DECISION"
    INCIDENT_REPORT = "INCIDENT_REPORT"
    RISK_ALERT = "RISK_ALERT"
    SECURITY_FINDING = "SECURITY_FINDING"
    MEETING_MINUTES = "MEETING_MINUTES"
    RELEASE_APPROVAL = "RELEASE_APPROVAL"
    NOTIFICATION = "NOTIFICATION"
    BROADCAST = "BROADCAST"


class MessagePriority(int, enum.Enum):
    """Priority levels for message routing."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


@dataclass
class OrgMessage:
    """
    Standard message envelope exchanged between departments and agents.
    """
    message_id: str = field(default_factory=lambda: f"MSG-{uuid.uuid4().hex[:10].upper()}")
    sender: str = "UNKNOWN"
    receiver: str = "ALL"  # Department name, Agent name, or 'ALL' for broadcast
    timestamp: float = field(default_factory=time.time)
    priority: MessagePriority = MessagePriority.NORMAL
    message_type: OrgMessageType = OrgMessageType.STATUS_UPDATE
    payload: Dict[str, Any] = field(default_factory=dict)
    thread_id: str = field(default_factory=lambda: f"THREAD-{uuid.uuid4().hex[:8].upper()}")
    correlation_id: Optional[str] = None
    response_required: bool = False
    acknowledged: bool = False
    status: str = "PENDING"  # PENDING, DELIVERED, ACKNOWLEDGED, ESCALATED
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes message to dictionary."""
        data = asdict(self)
        data["priority"] = int(self.priority.value if hasattr(self.priority, "value") else self.priority)
        data["message_type"] = str(self.message_type.value if hasattr(self.message_type, "value") else self.message_type)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OrgMessage:
        """Deserializes message from dictionary."""
        d = dict(data)
        if "priority" in d:
            if isinstance(d["priority"], int):
                try:
                    d["priority"] = MessagePriority(d["priority"])
                except ValueError:
                    d["priority"] = MessagePriority.NORMAL
            elif isinstance(d["priority"], str):
                d["priority"] = MessagePriority[d["priority"]]
        if "message_type" in d:
            if isinstance(d["message_type"], str):
                try:
                    d["message_type"] = OrgMessageType(d["message_type"])
                except ValueError:
                    d["message_type"] = OrgMessageType.STATUS_UPDATE
        return cls(**d)


class CommunicationBus:
    """
    Central, thread-safe communication bus for the entire AI organization.
    Handles point-to-point messaging, broadcasts, prioritized inboxes,
    escalation paths, correlation linking, and conversation thread tracking.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._inboxes: Dict[str, List[OrgMessage]] = {}
        self._message_history: List[OrgMessage] = []
        self._threads: Dict[str, List[str]] = {}  # thread_id -> list of message_ids
        self._subscribers: Dict[str, List[Callable[[OrgMessage], None]]] = {}  # topic/type -> callbacks
        self._pending_requests: Dict[str, OrgMessage] = {}  # message_id -> request message
        self._responses: Dict[str, OrgMessage] = {}  # correlation_id -> response message
        self._escalation_listeners: List[Callable[[OrgMessage], None]] = []

    def register_entity(self, entity_name: str) -> None:
        """Registers a department or agent inbox on the bus."""
        with self._lock:
            if entity_name not in self._inboxes:
                self._inboxes[entity_name] = []
                logger.debug("Entity '%s' registered on CommunicationBus.", entity_name)

    def send_message(self, message: OrgMessage) -> bool:
        """
        Sends a message to a specific receiver or broadcasts to all registered entities.
        """
        with self._lock:
            # Register sender and receiver if missing
            self.register_entity(message.sender)
            if message.receiver not in ("ALL", "*"):
                self.register_entity(message.receiver)

            # Record in global history & threads
            self._message_history.append(message)
            if message.thread_id not in self._threads:
                self._threads[message.thread_id] = []
            self._threads[message.thread_id].append(message.message_id)

            if message.response_required:
                self._pending_requests[message.message_id] = message

            # Deliver to inbox(es)
            if message.receiver in ("ALL", "*"):
                delivered_count = 0
                for entity, inbox in self._inboxes.items():
                    if entity != message.sender:
                        inbox.append(message)
                        delivered_count += 1
                message.status = "DELIVERED"
            else:
                self._inboxes[message.receiver].append(message)
                message.status = "DELIVERED"

            # Sort inbox by priority descending
            if message.receiver in self._inboxes:
                self._inboxes[message.receiver].sort(
                    key=lambda m: (-int(m.priority.value if hasattr(m.priority, "value") else m.priority), m.timestamp)
                )

            # Check if correlation response
            if message.correlation_id:
                self._responses[message.correlation_id] = message
                if message.correlation_id in self._pending_requests:
                    self._pending_requests[message.correlation_id].acknowledged = True

            # Trigger type-based subscribers
            msg_type_str = str(message.message_type.value if hasattr(message.message_type, "value") else message.message_type)
            if msg_type_str in self._subscribers:
                for callback in self._subscribers[msg_type_str]:
                    try:
                        callback(message)
                    except Exception as e:
                        logger.error("Error in subscriber callback for %s: %s", msg_type_str, e)

            # Trigger escalation handlers if escalation message
            if message.message_type == OrgMessageType.ESCALATION or message.priority >= MessagePriority.CRITICAL:
                message.status = "ESCALATED"
                for listener in self._escalation_listeners:
                    try:
                        listener(message)
                    except Exception as e:
                        logger.error("Error triggering escalation listener: %s", e)

            return True

    def broadcast(
        self,
        sender: str,
        message_type: OrgMessageType,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        thread_id: Optional[str] = None,
    ) -> OrgMessage:
        """Broadcasts a message to all registered departments and agents."""
        msg = OrgMessage(
            sender=sender,
            receiver="ALL",
            priority=priority,
            message_type=message_type,
            payload=payload,
            thread_id=thread_id or f"THREAD-BCAST-{uuid.uuid4().hex[:6].upper()}",
        )
        self.send_message(msg)
        return msg

    def respond(
        self,
        original_message: OrgMessage,
        sender: str,
        payload: Dict[str, Any],
        message_type: Optional[OrgMessageType] = None,
        priority: Optional[MessagePriority] = None,
    ) -> OrgMessage:
        """Constructs and sends a correlated response to an original message."""
        resp = OrgMessage(
            sender=sender,
            receiver=original_message.sender,
            priority=priority or original_message.priority,
            message_type=message_type or OrgMessageType.STATUS_UPDATE,
            payload=payload,
            thread_id=original_message.thread_id,
            correlation_id=original_message.message_id,
            response_required=False,
        )
        self.send_message(resp)
        self.acknowledge_message(original_message.message_id)
        return resp

    def get_messages(self, receiver: str, unread_only: bool = True) -> List[OrgMessage]:
        """Retrieves and optionally removes messages from an entity's inbox."""
        with self._lock:
            if receiver not in self._inboxes:
                return []
            if unread_only:
                msgs = list(self._inboxes[receiver])
                self._inboxes[receiver].clear()
                for m in msgs:
                    m.acknowledged = True
                    m.status = "ACKNOWLEDGED"
                return msgs
            else:
                return list(self._inboxes[receiver])

    def peek_messages(self, receiver: str) -> List[OrgMessage]:
        """Views messages in inbox without clearing or acknowledging them."""
        with self._lock:
            return list(self._inboxes.get(receiver, []))

    def acknowledge_message(self, message_id: str) -> bool:
        """Marks a message as acknowledged."""
        with self._lock:
            for msg in self._message_history:
                if msg.message_id == message_id:
                    msg.acknowledged = True
                    msg.status = "ACKNOWLEDGED"
                    return True
            return False

    def subscribe(self, message_type: OrgMessageType | str, callback: Callable[[OrgMessage], None]) -> None:
        """Registers a callback for a specific message type."""
        with self._lock:
            key = message_type.value if hasattr(message_type, "value") else str(message_type)
            if key not in self._subscribers:
                self._subscribers[key] = []
            self._subscribers[key].append(callback)

    def register_escalation_listener(self, listener: Callable[[OrgMessage], None]) -> None:
        """Registers a handler specifically for escalations and emergency alerts."""
        with self._lock:
            self._escalation_listeners.append(listener)

    def get_thread_history(self, thread_id: str) -> List[OrgMessage]:
        """Retrieves chronological messages belonging to a conversation thread."""
        with self._lock:
            msg_ids = set(self._threads.get(thread_id, []))
            return [m for m in self._message_history if m.message_id in msg_ids]

    def query_messages(
        self,
        sender: Optional[str] = None,
        receiver: Optional[str] = None,
        message_type: Optional[OrgMessageType | str] = None,
        thread_id: Optional[str] = None,
        min_priority: Optional[MessagePriority] = None,
        limit: int = 100,
    ) -> List[OrgMessage]:
        """Searches message history using multi-dimensional filters."""
        with self._lock:
            results = []
            type_val = (
                message_type.value
                if hasattr(message_type, "value")
                else str(message_type) if message_type else None
            )
            min_prio_val = (
                min_priority.value
                if hasattr(min_priority, "value")
                else int(min_priority) if min_priority else 1
            )

            for m in reversed(self._message_history):
                if sender and m.sender != sender:
                    continue
                if receiver and m.receiver != receiver and m.receiver not in ("ALL", "*"):
                    continue
                if type_val and (m.message_type.value if hasattr(m.message_type, "value") else str(m.message_type)) != type_val:
                    continue
                if thread_id and m.thread_id != thread_id:
                    continue
                m_prio = m.priority.value if hasattr(m.priority, "value") else int(m.priority)
                if m_prio < min_prio_val:
                    continue
                results.append(m)
                if len(results) >= limit:
                    break
            return results

    def get_bus_telemetry(self) -> Dict[str, Any]:
        """Returns diagnostic metrics and queue depths across all inboxes."""
        with self._lock:
            queue_depths = {k: len(v) for k, v in self._inboxes.items()}
            return {
                "total_messages_exchanged": len(self._message_history),
                "active_threads_count": len(self._threads),
                "registered_entities": list(self._inboxes.keys()),
                "pending_requests_count": len([m for m in self._pending_requests.values() if not m.acknowledged]),
                "queue_depths": queue_depths,
            }

    def clear(self) -> None:
        """Resets message queues and history."""
        with self._lock:
            self._inboxes.clear()
            self._message_history.clear()
            self._threads.clear()
            self._pending_requests.clear()
            self._responses.clear()
