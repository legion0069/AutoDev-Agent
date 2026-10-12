"""
conversation.py - Persistent Multi-Agent Engineering Discussions (v3.3)

Provides threaded discussions, branching exploration, decision tracking,
resolution summaries, and complete conversation replay.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from core.multi_agent.message import Message

logger = logging.getLogger("AutoDev.MultiAgent.Conversation")


class ConversationStatus(str, Enum):
    """Lifecycle state of an engineering discussion."""
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    ARCHIVED = "ARCHIVED"


@dataclass
class ConversationDecision:
    """A formal engineering decision ratified during a conversation."""
    decision_id: str
    decision: str
    decided_by: str
    rationale: str
    timestamp: float = field(default_factory=time.time)
    consensus_ratio: float = 1.0
    affected_components: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConversationEntry:
    """A discrete recorded discussion entry or message in a conversation thread."""
    entry_id: str
    author_id: str
    message: str
    entry_type: str = "message"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConversationThread:
    """
    Persistent engineering discussion supporting linear history,
    named branches (for alternative proposals), and formal decision tracking.
    """

    def __init__(
        self,
        conversation_id: str,
        title: str,
        topic: str = "engineering",
        participants: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        self.conversation_id = conversation_id
        self.title = title
        self.topic = topic
        self.tags = list(tags or [])
        self.participants: Set[str] = set(participants or [])
        self.status = ConversationStatus.OPEN
        self.created_at = time.time()
        self.updated_at = self.created_at
        self.summary: str = ""

        # Main timeline messages and entries
        self.messages: List[Message] = []
        self.entries: List[ConversationEntry] = []
        # Branches: branch_name -> list of Messages
        self.branches: Dict[str, List[Message]] = {}
        # Formal decisions ratified
        self.decisions: List[ConversationDecision] = []

    def add_entry(
        self,
        author_id: str,
        message: str,
        entry_type: str = "message",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationEntry:
        """Adds a text entry or standup update to the conversation."""
        self.participants.add(author_id)
        self.updated_at = time.time()
        entry = ConversationEntry(
            entry_id=f"entry-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}",
            author_id=author_id,
            message=message,
            entry_type=entry_type,
            metadata=metadata or {},
        )
        self.entries.append(entry)
        return entry

    def add_message(self, message: Message, branch: Optional[str] = None) -> None:
        """Appends a message to the conversation main thread or named branch."""
        self.participants.add(message.sender)
        self.updated_at = time.time()
        msg_copy = copy.deepcopy(message)

        if branch:
            if branch not in self.branches:
                self.branches[branch] = []
            self.branches[branch].append(msg_copy)
        else:
            self.messages.append(msg_copy)

    def branch(self, branch_name: str, parent_branch: Optional[str] = None) -> str:
        """Creates a new proposal branch initialized from existing thread."""
        if branch_name in self.branches:
            return branch_name

        if parent_branch and parent_branch in self.branches:
            initial = [copy.deepcopy(m) for m in self.branches[parent_branch]]
        else:
            initial = [copy.deepcopy(m) for m in self.messages]

        self.branches[branch_name] = initial
        return branch_name

    def record_decision(
        self,
        decision: str,
        decided_by: str,
        rationale: str = "",
        consensus_ratio: float = 1.0,
        affected_components: Optional[List[str]] = None,
    ) -> ConversationDecision:
        """Records a ratified architectural or implementation decision."""
        dec = ConversationDecision(
            decision_id=f"dec-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}",
            decision=decision,
            decided_by=decided_by,
            rationale=rationale,
            consensus_ratio=consensus_ratio,
            affected_components=affected_components or [],
        )
        self.decisions.append(dec)
        self.updated_at = time.time()
        return dec

    def resolve(self, summary: str) -> None:
        """Marks conversation as resolved with an official closing summary."""
        self.status = ConversationStatus.RESOLVED
        self.summary = summary
        self.updated_at = time.time()

    def summarize(self) -> str:
        """Generates a text summary of the conversation and ratified decisions."""
        if self.summary:
            return self.summary

        lines = [
            f"Topic: {self.title} ({self.topic})",
            f"Participants: {', '.join(sorted(self.participants))}",
            f"Messages: {len(self.messages)} in main thread, {len(self.branches)} branches",
            f"Status: {self.status.value}",
        ]
        if self.decisions:
            lines.append("Decisions Ratified:")
            for d in self.decisions:
                lines.append(f" - [{d.decided_by}] {d.decision} (Rationale: {d.rationale})")
        return "\n".join(lines)

    def replay(self) -> List[Dict[str, Any]]:
        """Returns chronological replay events across the discussion."""
        events: List[Dict[str, Any]] = []
        for m in self.messages:
            events.append({
                "type": "MESSAGE",
                "timestamp": m.timestamp,
                "sender": m.sender,
                "receiver": m.receiver,
                "content": m.payload.get("content", str(m.payload)),
                "message_id": m.message_id,
            })
        for d in self.decisions:
            events.append({
                "type": "DECISION",
                "timestamp": d.timestamp,
                "decided_by": d.decided_by,
                "decision": d.decision,
                "rationale": d.rationale,
                "decision_id": d.decision_id,
            })
        events.sort(key=lambda e: e["timestamp"])
        return events

    def to_dict(self) -> Dict[str, Any]:
        """Serializes conversation state."""
        return {
            "conversation_id": self.conversation_id,
            "title": self.title,
            "topic": self.topic,
            "participants": sorted(list(self.participants)),
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "summary": self.summary,
            "messages_count": len(self.messages),
            "branches_count": len(self.branches),
            "decisions": [d.to_dict() for d in self.decisions],
            "branches": {k: [m.to_dict() for m in v] for k, v in self.branches.items()},
        }


class ConversationEngine:
    """
    Manager and repository for all collaborative engineering conversations.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._conversations: Dict[str, ConversationThread] = {}

    def create_conversation(
        self,
        title: str,
        topic: str = "engineering",
        participants: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
    ) -> ConversationThread:
        """Instantiates and registers a new conversation thread."""
        cid = conversation_id or f"conv-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"
        thread = ConversationThread(
            conversation_id=cid,
            title=title,
            topic=topic,
            participants=participants or [],
        )
        with self._lock:
            self._conversations[cid] = thread
        return thread

    def create_thread(
        self,
        title: str,
        initiator: str = "",
        tags: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
    ) -> ConversationThread:
        """Convenience method to create and register an engineering discussion thread."""
        cid = conversation_id or f"conv-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"
        thread = ConversationThread(
            conversation_id=cid,
            title=title,
            topic=tags[0] if tags else "engineering",
            participants=[initiator] if initiator else [],
            tags=tags or [],
        )
        with self._lock:
            self._conversations[cid] = thread
        return thread

    def get_conversation(self, conversation_id: str) -> Optional[ConversationThread]:
        """Retrieves an active conversation thread."""
        with self._lock:
            return self._conversations.get(conversation_id)

    def list_conversations(self, status: Optional[ConversationStatus] = None) -> List[ConversationThread]:
        """Lists discussions, optionally filtered by status."""
        with self._lock:
            if status is None:
                return list(self._conversations.values())
            return [c for c in self._conversations.values() if c.status == status]

    def count(self) -> int:
        """Returns total conversations tracked."""
        with self._lock:
            return len(self._conversations)

    def clear(self) -> None:
        """Clears all conversations."""
        with self._lock:
            self._conversations.clear()
