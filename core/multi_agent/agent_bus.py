"""
AutoDev Distributed Agent Message Bus Subsystem.

Provides persistent message queuing, pub/sub topics, direct addressing,
broadcast/multicast routing, and synchronous request-response correlation.
"""

from __future__ import annotations

import copy
import logging
import queue
import threading
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Set, Union

from core.multi_agent.message import (
    Message,
    MessagePriority,
    MessageStatus,
    MessageType,
)

logger = logging.getLogger("AutoDev.MultiAgent.MessageBus")


class AgentMessageBus:
    """
    Central thread-safe message exchange and event bus for multi-agent collaboration.
    Guarantees in-order delivery per priority, historical message persistence,
    and request-response correlation.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # History store
        self._history: List[Message] = []
        self._messages_by_id: Dict[str, Message] = {}
        self._conversation_index: Dict[str, List[str]] = defaultdict(list)
        self._agent_inboxes: Dict[str, List[Message]] = defaultdict(list)

        # Active subscriptions and callbacks: agent_id -> list of callback handlers
        self._subscribers: Dict[str, List[Callable[[Message], None]]] = defaultdict(list)
        # Topic subscriptions: topic_name -> list of (agent_id_or_callback)
        self._topic_subscribers: Dict[str, List[Union[str, Callable[[Message], None]]]] = defaultdict(list)

        # Correlation response events: message_id -> (threading.Event, Optional[Message])
        self._pending_requests: Dict[str, Dict[str, Any]] = {}

    def register_inbox(self, agent_id: str) -> None:
        """Registers a named inbox on the message bus."""
        with self._lock:
            if agent_id not in self._agent_inboxes:
                self._agent_inboxes[agent_id] = []

    def get_inbox_size(self, agent_id: str) -> int:
        """Returns pending message count in agent inbox."""
        with self._lock:
            return len(self._agent_inboxes.get(agent_id, []))

    def publish(self, message: Message) -> bool:
        """
        Publishes a message onto the bus.
        Persists message into history and routes to target receiver(s).
        """
        with self._lock:
            # 1. Persist
            stored = copy.deepcopy(message)
            self._history.append(stored)
            self._messages_by_id[stored.message_id] = stored
            self._conversation_index[stored.conversation_id].append(stored.message_id)

            # 2. Check if this is a response to an active request
            if stored.correlation_id and stored.correlation_id in self._pending_requests:
                stored.status = MessageStatus.DELIVERED
                req_ctx = self._pending_requests[stored.correlation_id]
                req_ctx["response"] = copy.deepcopy(stored)
                req_ctx["event"].set()

            # 3. Route according to delivery pattern
            receivers: Set[str] = set()
            if stored.message_type == MessageType.BROADCAST or stored.receiver == "*":
                receivers = set(self._agent_inboxes.keys()) | set(self._subscribers.keys())
                receivers.add(stored.receiver)
            elif stored.message_type == MessageType.MULTICAST:
                multi = stored.payload.get("receivers") or [stored.receiver]
                receivers = set(multi)
            else:
                receivers = {stored.receiver}

            # Deposit into receiver inboxes
            for r in receivers:
                if r and r != "*":
                    self._agent_inboxes[r].append(copy.deepcopy(stored))

            # Mark delivered
            stored.status = MessageStatus.DELIVERED

            # 4. Trigger subscriber callbacks
            callbacks_to_invoke: List[Callable[[Message], None]] = []
            for r in receivers:
                callbacks_to_invoke.extend(self._subscribers.get(r, []))

            # Topic handlers
            topic = stored.payload.get("topic")
            if topic and topic in self._topic_subscribers:
                for sub in self._topic_subscribers[topic]:
                    if callable(sub):
                        callbacks_to_invoke.append(sub)
                    elif isinstance(sub, str):
                        self._agent_inboxes[sub].append(copy.deepcopy(stored))

        # Invoke callbacks outside lock to prevent deadlocks
        for cb in callbacks_to_invoke:
            try:
                cb(copy.deepcopy(stored))
            except Exception as e:
                logger.error("Error executing message bus subscriber callback: %s", e)

        return True

    def send(self, message: Message) -> bool:
        """Sends a message over the bus (alias for publish)."""
        return self.publish(message)

    def receive(
        self,
        agent_id: str,
        block: bool = False,
        timeout: Optional[float] = None
    ) -> Optional[Message]:
        """Pops and returns the next pending message from an agent's inbox."""
        deadline = time.time() + (timeout or 0.0) if timeout else 0.0
        while True:
            with self._lock:
                inbox = self._agent_inboxes.get(agent_id, [])
                if inbox:
                    msg = inbox.pop(0)
                    msg.status = MessageStatus.DELIVERED
                    return msg

            if not block:
                return None

            if timeout and time.time() >= deadline:
                return None
            time.sleep(0.01)

    def send_direct(
        self,
        sender: str,
        receiver: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        conversation_id: str = "default",
        task_id: Optional[str] = None,
    ) -> Message:
        """Convenience helper to send a point-to-point direct message."""
        msg = Message(
            sender=sender,
            receiver=receiver,
            payload=payload,
            message_type=MessageType.DIRECT,
            priority=priority,
            conversation_id=conversation_id,
            task_id=task_id,
        )
        self.publish(msg)
        return msg

    def broadcast(
        self,
        sender_or_msg: Union[str, Message],
        payload: Optional[Dict[str, Any]] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        conversation_id: str = "default",
    ) -> Message:
        """Broadcasts a message to all agents on the platform."""
        if isinstance(sender_or_msg, Message):
            msg = sender_or_msg
            msg.message_type = MessageType.BROADCAST
            self.publish(msg)
            return msg

        msg = Message(
            sender=sender_or_msg,
            receiver="*",
            payload=payload or {},
            message_type=MessageType.BROADCAST,
            priority=priority,
            conversation_id=conversation_id,
        )
        self.publish(msg)
        return msg

    def multicast(
        self,
        sender_or_msg: Union[str, Message],
        receivers_or_targets: Optional[List[str]] = None,
        payload: Optional[Dict[str, Any]] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        conversation_id: str = "default",
        target_agents: Optional[List[str]] = None,
    ) -> Message:
        """Sends a message to multiple specified recipient agents."""
        if isinstance(sender_or_msg, Message):
            msg = sender_or_msg
            targets = target_agents or receivers_or_targets or []
            msg.message_type = MessageType.MULTICAST
            msg.payload["receivers"] = list(targets)
            self.publish(msg)
            return msg

        targets = receivers_or_targets or target_agents or []
        p = copy.deepcopy(payload or {})
        p["receivers"] = list(targets)
        msg = Message(
            sender=sender_or_msg,
            receiver=",".join(targets),
            payload=p,
            message_type=MessageType.MULTICAST,
            priority=priority,
            conversation_id=conversation_id,
        )
        self.publish(msg)
        return msg

    def request(
        self,
        sender_or_msg: Union[str, Message],
        receiver: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 3.0,
        priority: MessagePriority = MessagePriority.HIGH,
        conversation_id: str = "default",
    ) -> Optional[Message]:
        """
        Issues a request and blocks until a correlated response arrives or timeout expires.
        """
        if isinstance(sender_or_msg, Message):
            msg = sender_or_msg
            msg.message_type = MessageType.REQUEST
            to = timeout if receiver is None else (payload if isinstance(payload, (int, float)) else timeout)
        else:
            msg = Message(
                sender=sender_or_msg,
                receiver=receiver or "",
                payload=payload or {},
                message_type=MessageType.REQUEST,
                priority=priority,
                conversation_id=conversation_id,
            )
            to = timeout

        event = threading.Event()
        with self._lock:
            self._pending_requests[msg.message_id] = {
                "event": event,
                "response": None,
                "created_at": time.time(),
            }

        self.publish(msg)

        completed = event.wait(timeout=to)

        with self._lock:
            ctx = self._pending_requests.pop(msg.message_id, None)
            if completed and ctx and ctx.get("response"):
                return ctx["response"]
            return None

    def respond(
        self,
        original_message: Optional[Message] = None,
        sender: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        original_request: Optional[Message] = None,
        responder: Optional[str] = None,
    ) -> Message:
        """Replies to a request message with correlation tracking."""
        orig = original_request or original_message
        if not orig:
            raise ValueError("original_message or original_request must be provided")
        resp_sender = responder or sender or "responder"
        resp = orig.create_response(sender=resp_sender, payload=payload or {})
        self.publish(resp)
        return resp

    def subscribe(self, agent_id: str, handler: Callable[[Message], None]) -> None:
        """Registers a callback handler for messages delivered to agent_id."""
        with self._lock:
            self._subscribers[agent_id].append(handler)

    def subscribe_topic(self, topic: str, handler: Union[str, Callable[[Message], None]]) -> None:
        """Registers a callback handler or agent_id for a topic."""
        with self._lock:
            self._topic_subscribers[topic].append(handler)

    def unsubscribe_topic(self, topic: str, handler: Union[str, Callable[[Message], None]]) -> None:
        """Removes a topic subscription."""
        with self._lock:
            if topic in self._topic_subscribers:
                self._topic_subscribers[topic] = [
                    h for h in self._topic_subscribers[topic] if h != handler
                ]

    def publish_topic(self, topic: str, message: Message) -> bool:
        """Publishes an event to a named topic."""
        with self._lock:
            msg = copy.deepcopy(message)
            msg.payload["topic"] = topic
            msg.message_type = MessageType.EVENT

            # Deliver to subscribers of this topic
            subs = list(self._topic_subscribers.get(topic, []))
            for sub in subs:
                if isinstance(sub, str):
                    self._agent_inboxes[sub].append(copy.deepcopy(msg))
                elif callable(sub):
                    try:
                        sub(copy.deepcopy(msg))
                    except Exception as e:
                        logger.error("Topic callback error: %s", e)

            # Persist
            self._history.append(msg)
            self._messages_by_id[msg.message_id] = msg
            return True

    def unsubscribe(self, agent_id: str) -> None:
        """Removes all subscriber callbacks for an agent."""
        with self._lock:
            if agent_id in self._subscribers:
                del self._subscribers[agent_id]

    def acknowledge(self, message_id: str, ack_by: str = "system", status_text: str = "OK") -> bool:
        """Marks a stored message as acknowledged."""
        with self._lock:
            msg = self._messages_by_id.get(message_id)
            if not msg:
                return False
            msg.acknowledge(ack_by=ack_by, status_text=status_text)
            return True

    def get_message(self, message_id: str) -> Optional[Message]:
        """Retrieves a message by message_id."""
        with self._lock:
            m = self._messages_by_id.get(message_id)
            return copy.deepcopy(m) if m else None

    def get_all_messages(self) -> List[Message]:
        """Returns all messages in chronological order."""
        with self._lock:
            return [copy.deepcopy(m) for m in self._history]

    def get_messages_for_agent(self, agent_id: str, clear_inbox: bool = False) -> List[Message]:
        """Retrieves and optionally clears pending messages from agent inbox."""
        with self._lock:
            msgs = [copy.deepcopy(m) for m in self._agent_inboxes.get(agent_id, [])]
            if clear_inbox:
                self._agent_inboxes[agent_id].clear()
            return msgs

    def get_conversation_messages(self, conversation_id: str) -> List[Message]:
        """Returns all messages belonging to a conversation thread."""
        with self._lock:
            mids = self._conversation_index.get(conversation_id, [])
            return [copy.deepcopy(self._messages_by_id[mid]) for mid in mids if mid in self._messages_by_id]

    def get_history(self, limit: int = 1000) -> List[Message]:
        """Returns chronological message history up to limit."""
        with self._lock:
            return [copy.deepcopy(m) for m in self._history[-limit:]]

    def count(self) -> int:
        """Returns total historical messages processed."""
        with self._lock:
            return len(self._history)

    def clear(self) -> None:
        """Resets all inboxes, subscriptions, and history."""
        with self._lock:
            self._history.clear()
            self._messages_by_id.clear()
            self._conversation_index.clear()
            self._agent_inboxes.clear()
            self._subscribers.clear()
            self._topic_subscribers.clear()
            self._pending_requests.clear()
