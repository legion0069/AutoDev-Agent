"""
message.py - Structured Inter-Agent Communication Protocol (v3.3)

Provides deterministic, thread-safe, and serializable messaging structures
supporting point-to-point, multicast, broadcast, and request-response patterns.
"""

from __future__ import annotations

import copy
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MessageType(str, Enum):
    """Classification of multi-agent message delivery patterns."""
    DIRECT = "DIRECT"
    BROADCAST = "BROADCAST"
    MULTICAST = "MULTICAST"
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    EVENT = "EVENT"
    NOTIFICATION = "NOTIFICATION"


class MessagePriority(int, Enum):
    """Deterministic message priority ranking for work queues."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class MessageStatus(str, Enum):
    """Delivery and acknowledgement lifecycle status."""
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FAILED = "FAILED"


@dataclass
class Message:
    """
    Structured message payload for inter-agent communication.
    Supports priority comparison for deterministic min/max priority queues.
    """
    sender: str
    receiver: str
    payload: Dict[str, Any] = field(default_factory=dict)
    message_type: MessageType = MessageType.DIRECT
    priority: MessagePriority = MessagePriority.NORMAL
    conversation_id: str = "default"
    task_id: Optional[str] = None
    message_id: str = field(default_factory=lambda: f"msg-{int(time.time()*1000)}-{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)
    attachments: List[Any] = field(default_factory=list)
    status: MessageStatus = MessageStatus.PENDING
    correlation_id: Optional[str] = None
    acknowledgement: Optional[Dict[str, Any]] = None
    msg_type: Optional[MessageType] = None

    def __post_init__(self) -> None:
        if self.msg_type is not None:
            self.message_type = self.msg_type
        if isinstance(self.message_type, str):
            self.message_type = MessageType(self.message_type)
        if isinstance(self.priority, int) and not isinstance(self.priority, MessagePriority):
            self.priority = MessagePriority(self.priority)
        if isinstance(self.status, str):
            self.status = MessageStatus(self.status)

    def acknowledge(self, ack_by: str, status_text: str = "OK", metadata: Optional[Dict[str, Any]] = None) -> None:
        """Marks message as acknowledged by a receiver."""
        self.status = MessageStatus.ACKNOWLEDGED
        self.acknowledgement = {
            "ack_by": ack_by,
            "status": status_text,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }

    def create_response(self, sender: str, payload: Dict[str, Any], priority: Optional[MessagePriority] = None) -> Message:
        """Constructs a deterministic response message correlated to this message."""
        return Message(
            sender=sender,
            receiver=self.sender,
            payload=payload,
            message_type=MessageType.RESPONSE,
            priority=priority or self.priority,
            conversation_id=self.conversation_id,
            task_id=self.task_id,
            correlation_id=self.message_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes message into a clean dictionary."""
        d = asdict(self)
        d["message_type"] = self.message_type.value if isinstance(self.message_type, Enum) else str(self.message_type)
        d["priority"] = self.priority.value if isinstance(self.priority, Enum) else int(self.priority)
        d["status"] = self.status.value if isinstance(self.status, Enum) else str(self.status)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Message:
        """Reconstructs message from serialized dictionary."""
        d = copy.deepcopy(data)
        if "message_type" in d:
            d["message_type"] = MessageType(d["message_type"])
        if "priority" in d:
            d["priority"] = MessagePriority(d["priority"])
        if "status" in d:
            d["status"] = MessageStatus(d["status"])
        return cls(**d)

    def to_json(self) -> str:
        """Returns JSON string representation."""
        return json.dumps(self.to_dict(), default=str)

    def __lt__(self, other: Any) -> bool:
        """Priority queue ordering: higher priority ranks first, then earlier timestamp."""
        if not isinstance(other, Message):
            return NotImplemented
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value
        return self.timestamp < other.timestamp
