"""
inter_company_bus.py - Federation Message Bus (AutoDev Version 3.5)

Provides enterprise-wide inter-company communication:
- Cross-company task delegation, knowledge requests, architecture reviews,
  security alerts, incident broadcasts, shared services, budget requests, executive approvals.
- High-integrity message envelope with company_id, department_id, sender, receiver,
  priority, classification, trace_id, thread_id, response_required, digital_signature.
- Deterministic cryptographic HMAC-SHA256 signatures for zero-trust message integrity.
- Thread-safe pub/sub topic routing, direct routing, dead-letter handling, and trace tracking.
- 100% Python Standard Library.
"""

from __future__ import annotations

import enum
import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("AutoDev.Federation.Bus")


class MessageClassification(str, enum.Enum):
    """Information security classification tiers across enterprise federation."""
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class FederationMessagePriority(int, enum.Enum):
    """Priority levels for inter-company routing."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


class FederationMessageType(str, enum.Enum):
    """Categorized federation message types."""
    TASK_DELEGATION = "TASK_DELEGATION"
    KNOWLEDGE_REQUEST = "KNOWLEDGE_REQUEST"
    KNOWLEDGE_RESPONSE = "KNOWLEDGE_RESPONSE"
    ARCHITECTURE_REVIEW = "ARCHITECTURE_REVIEW"
    SECURITY_ALERT = "SECURITY_ALERT"
    INCIDENT_BROADCAST = "INCIDENT_BROADCAST"
    SHARED_SERVICE_REQUEST = "SHARED_SERVICE_REQUEST"
    SHARED_SERVICE_RESPONSE = "SHARED_SERVICE_RESPONSE"
    BUDGET_REQUEST = "BUDGET_REQUEST"
    EXECUTIVE_APPROVAL = "EXECUTIVE_APPROVAL"
    RESOURCE_TRADE_OFFER = "RESOURCE_TRADE_OFFER"
    RESOURCE_TRADE_ACCEPT = "RESOURCE_TRADE_ACCEPT"
    GOVERNANCE_POLICY_UPDATE = "GOVERNANCE_POLICY_UPDATE"
    DISASTER_ALERT = "DISASTER_ALERT"
    HEARTBEAT = "HEARTBEAT"
    GENERAL = "GENERAL"


@dataclass
class FederationMessage:
    """
    Standard federation message envelope connecting companies, departments, and agents.
    """
    message_id: str = field(default_factory=lambda: f"FEDMSG-{uuid.uuid4().hex[:12].upper()}")
    company_id: str = "GLOBAL_ENTERPRISE"
    target_company_id: str = "ALL"  # 'ALL' for federation-wide broadcast or specific company_id
    department_id: str = "EXECUTIVE"
    target_department_id: str = "ALL"
    sender: str = "SYSTEM"
    receiver: str = "ALL"
    priority: FederationMessagePriority = FederationMessagePriority.NORMAL
    classification: MessageClassification = MessageClassification.INTERNAL
    message_type: FederationMessageType = FederationMessageType.GENERAL
    trace_id: str = field(default_factory=lambda: f"TRACE-{uuid.uuid4().hex[:12].upper()}")
    thread_id: str = field(default_factory=lambda: f"THREAD-{uuid.uuid4().hex[:8].upper()}")
    response_required: bool = False
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
    digital_signature: str = ""
    status: str = "CREATED"  # CREATED, DISPATCHED, DELIVERED, ACKNOWLEDGED, FAILED
    acknowledged: bool = False
    correlation_id: Optional[str] = None
    error_reason: Optional[str] = None

    def sign(self, secret_key: str = "FEDERATION_SECRET_SALT") -> str:
        """Computes deterministic HMAC-SHA256 signature for message envelope integrity."""
        signature_material = (
            f"{self.message_id}:{self.company_id}:{self.target_company_id}:"
            f"{self.sender}:{self.receiver}:{self.priority.value if hasattr(self.priority, 'value') else self.priority}:"
            f"{self.classification.value if hasattr(self.classification, 'value') else self.classification}:"
            f"{self.trace_id}:{self.thread_id}:{json.dumps(self.payload, sort_keys=True)}"
        )
        sig = hmac.new(
            secret_key.encode("utf-8"),
            signature_material.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        self.digital_signature = sig
        return sig

    def verify_signature(self, secret_key: str = "FEDERATION_SECRET_SALT") -> bool:
        """Verifies message authenticity and tamper-resistance."""
        if not self.digital_signature:
            return False
        expected_material = (
            f"{self.message_id}:{self.company_id}:{self.target_company_id}:"
            f"{self.sender}:{self.receiver}:{self.priority.value if hasattr(self.priority, 'value') else self.priority}:"
            f"{self.classification.value if hasattr(self.classification, 'value') else self.classification}:"
            f"{self.trace_id}:{self.thread_id}:{json.dumps(self.payload, sort_keys=True)}"
        )
        expected_sig = hmac.new(
            secret_key.encode("utf-8"),
            expected_material.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(self.digital_signature, expected_sig)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes message to dictionary."""
        d = asdict(self)
        d["priority"] = self.priority.value if hasattr(self.priority, "value") else self.priority
        d["classification"] = self.classification.value if hasattr(self.classification, "value") else self.classification
        d["message_type"] = self.message_type.value if hasattr(self.message_type, "value") else self.message_type
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FederationMessage:
        """Constructs FederationMessage from dictionary."""
        d = dict(data)
        if "priority" in d and not isinstance(d["priority"], FederationMessagePriority):
            d["priority"] = FederationMessagePriority(int(d["priority"]))
        if "classification" in d and not isinstance(d["classification"], MessageClassification):
            d["classification"] = MessageClassification(str(d["classification"]))
        if "message_type" in d and not isinstance(d["message_type"], FederationMessageType):
            d["message_type"] = FederationMessageType(str(d["message_type"]))
        return cls(**d)


class InterCompanyBus:
    """
    Federated Enterprise Communication Bus connecting unlimited autonomous companies.
    Thread-safe, priority-queued, topic pub/sub with delivery tracking and audit traces.
    """

    def __init__(self, secret_key: str = "FEDERATION_SECRET_SALT") -> None:
        self._lock = threading.RLock()
        self.secret_key = secret_key
        # Inboxes indexed by company_id -> list of FederationMessage
        self._company_inboxes: Dict[str, List[FederationMessage]] = {}
        # Inboxes indexed by f"{company_id}:{department_id}" -> list of FederationMessage
        self._department_inboxes: Dict[str, List[FederationMessage]] = {}
        # Topic subscribers: topic -> list of callback functions
        self._topic_subscribers: Dict[str, List[Callable[[FederationMessage], None]]] = {}
        # Message type subscribers: type_str -> list of callback functions
        self._type_subscribers: Dict[str, List[Callable[[FederationMessage], None]]] = {}
        # Traces: trace_id -> list of message_ids
        self._traces: Dict[str, List[str]] = {}
        # Threads: thread_id -> list of message_ids
        self._threads: Dict[str, List[str]] = {}
        # Pending response requests: message_id -> FederationMessage
        self._pending_requests: Dict[str, FederationMessage] = {}
        # Message store: message_id -> FederationMessage
        self._messages: Dict[str, FederationMessage] = {}
        # Dead-letter queue
        self._dead_letter_queue: List[FederationMessage] = []
        # Total messages routed
        self._total_routed = 0

    def register_company(self, company_id: str) -> None:
        """Registers a company with an inbox in the federation bus."""
        with self._lock:
            if company_id not in self._company_inboxes:
                self._company_inboxes[company_id] = []
                logger.debug("Registered company '%s' to InterCompanyBus", company_id)

    def register_department(self, company_id: str, department_id: str) -> None:
        """Registers a department inbox under a company."""
        with self._lock:
            key = f"{company_id}:{department_id}"
            if key not in self._department_inboxes:
                self._department_inboxes[key] = []
            self.register_company(company_id)

    def subscribe_topic(self, topic: str, callback: Callable[[FederationMessage], None]) -> None:
        """Subscribes callback to a named federation topic."""
        with self._lock:
            if topic not in self._topic_subscribers:
                self._topic_subscribers[topic] = []
            self._topic_subscribers[topic].append(callback)

    def subscribe_type(
        self,
        msg_type: FederationMessageType | str,
        callback: Callable[[FederationMessage], None],
    ) -> None:
        """Subscribes callback to a federation message type."""
        with self._lock:
            key = msg_type.value if hasattr(msg_type, "value") else str(msg_type)
            if key not in self._type_subscribers:
                self._type_subscribers[key] = []
            self._type_subscribers[key].append(callback)

    def send_message(self, message: FederationMessage) -> bool:
        """
        Dispatches message across the enterprise federation.
        Automatically signs message if not signed, verifies signature,
        routes to inboxes, triggers subscribers, and tracks thread/trace.
        """
        with self._lock:
            if not message.digital_signature:
                message.sign(self.secret_key)
            elif not message.verify_signature(self.secret_key):
                message.status = "FAILED"
                message.error_reason = "Signature verification failed"
                self._dead_letter_queue.append(message)
                logger.error("Message %s failed signature check on InterCompanyBus", message.message_id)
                return False

            self._messages[message.message_id] = message
            self._total_routed += 1

            # Track trace and thread
            if message.trace_id not in self._traces:
                self._traces[message.trace_id] = []
            self._traces[message.trace_id].append(message.message_id)

            if message.thread_id not in self._threads:
                self._threads[message.thread_id] = []
            self._threads[message.thread_id].append(message.message_id)

            if message.response_required:
                self._pending_requests[message.message_id] = message

            # Deliver to target company/department inboxes
            target_co = message.target_company_id
            target_dept = message.target_department_id

            delivered = False

            if target_co in ("ALL", "*"):
                # Broadcast across all companies
                for cid, inbox in self._company_inboxes.items():
                    if cid != message.company_id:
                        inbox.append(message)
                        delivered = True
            else:
                if target_co in self._company_inboxes:
                    self._company_inboxes[target_co].append(message)
                    delivered = True
                else:
                    self.register_company(target_co)
                    self._company_inboxes[target_co].append(message)
                    delivered = True

            # If specific department target
            if target_dept not in ("ALL", "*") and target_co not in ("ALL", "*"):
                dept_key = f"{target_co}:{target_dept}"
                if dept_key in self._department_inboxes:
                    self._department_inboxes[dept_key].append(message)
                else:
                    self.register_department(target_co, target_dept)
                    self._department_inboxes[dept_key].append(message)

            message.status = "DELIVERED" if delivered else "DISPATCHED"

            # Check if correlation response
            if message.correlation_id and message.correlation_id in self._pending_requests:
                self._pending_requests[message.correlation_id].acknowledged = True

            # Trigger type subscribers
            type_key = message.message_type.value if hasattr(message.message_type, "value") else str(message.message_type)
            if type_key in self._type_subscribers:
                for cb in self._type_subscribers[type_key]:
                    try:
                        cb(message)
                    except Exception as e:
                        logger.error("Error in InterCompanyBus type subscriber: %s", e)

            # Trigger topic if provided in payload
            topic = message.payload.get("topic")
            if topic and topic in self._topic_subscribers:
                for cb in self._topic_subscribers[topic]:
                    try:
                        cb(message)
                    except Exception as e:
                        logger.error("Error in InterCompanyBus topic subscriber: %s", e)

            return True

    def get_company_messages(
        self,
        company_id: str,
        drain: bool = False,
        limit: Optional[int] = None,
    ) -> List[FederationMessage]:
        """Retrieves and optionally drains messages for a company."""
        with self._lock:
            inbox = self._company_inboxes.get(company_id, [])
            # Sort by priority descending, then timestamp ascending
            sorted_msgs = sorted(
                inbox,
                key=lambda m: (-int(m.priority.value if hasattr(m.priority, "value") else m.priority), m.timestamp),
            )
            if limit:
                result = sorted_msgs[:limit]
            else:
                result = list(sorted_msgs)

            if drain:
                if limit:
                    self._company_inboxes[company_id] = sorted_msgs[limit:]
                else:
                    self._company_inboxes[company_id] = []

            return result

    def get_department_messages(
        self,
        company_id: str,
        department_id: str,
        drain: bool = False,
    ) -> List[FederationMessage]:
        """Retrieves messages for a specific company department."""
        with self._lock:
            key = f"{company_id}:{department_id}"
            inbox = self._department_inboxes.get(key, [])
            sorted_msgs = sorted(
                inbox,
                key=lambda m: (-int(m.priority.value if hasattr(m.priority, "value") else m.priority), m.timestamp),
            )
            if drain:
                self._department_inboxes[key] = []
            return sorted_msgs

    def broadcast_security_alert(
        self,
        source_company_id: str,
        threat_level: str,
        threat_details: Dict[str, Any],
    ) -> FederationMessage:
        """Convenience method to broadcast an urgent security alert to all companies."""
        msg = FederationMessage(
            company_id=source_company_id,
            target_company_id="ALL",
            sender=f"{source_company_id}:Security",
            receiver="ALL",
            priority=FederationMessagePriority.EMERGENCY,
            classification=MessageClassification.RESTRICTED,
            message_type=FederationMessageType.SECURITY_ALERT,
            payload={
                "threat_level": threat_level,
                "threat_details": threat_details,
                "action_required": "IMMEDIATE_QUARANTINE_OR_PATCH",
            },
        )
        self.send_message(msg)
        return msg

    def broadcast_incident(
        self,
        source_company_id: str,
        severity: str,
        service_affected: str,
        root_cause: str,
    ) -> FederationMessage:
        """Broadcasts a high-severity incident across the federation."""
        msg = FederationMessage(
            company_id=source_company_id,
            target_company_id="ALL",
            sender=f"{source_company_id}:Operations",
            receiver="ALL",
            priority=FederationMessagePriority.CRITICAL,
            classification=MessageClassification.INTERNAL,
            message_type=FederationMessageType.INCIDENT_BROADCAST,
            payload={
                "severity": severity,
                "service": service_affected,
                "root_cause": root_cause,
            },
        )
        self.send_message(msg)
        return msg

    def get_trace(self, trace_id: str) -> List[FederationMessage]:
        """Returns ordered list of messages in a trace."""
        with self._lock:
            msg_ids = self._traces.get(trace_id, [])
            return [self._messages[mid] for mid in msg_ids if mid in self._messages]

    def get_thread(self, thread_id: str) -> List[FederationMessage]:
        """Returns ordered list of messages in a conversation thread."""
        with self._lock:
            msg_ids = self._threads.get(thread_id, [])
            return [self._messages[mid] for mid in msg_ids if mid in self._messages]

    def get_dead_letters(self) -> List[FederationMessage]:
        """Returns list of rejected / failed dead-letter messages."""
        with self._lock:
            return list(self._dead_letter_queue)

    def get_bus_telemetry(self) -> Dict[str, Any]:
        """Returns real-time telemetry metrics of the federation bus."""
        with self._lock:
            total_inbox_messages = sum(len(ib) for ib in self._company_inboxes.values())
            return {
                "registered_companies": len(self._company_inboxes),
                "registered_departments": len(self._department_inboxes),
                "total_routed_messages": self._total_routed,
                "total_inbox_backlog": total_inbox_messages,
                "dead_letter_count": len(self._dead_letter_queue),
                "active_traces_count": len(self._traces),
                "active_threads_count": len(self._threads),
                "pending_requests_count": len(self._pending_requests),
            }
