"""
Tests for AgentMessageBus and Message models in AutoDev v3.3.
"""

import time
import pytest
from core.multi_agent.agent_bus import AgentMessageBus
from core.multi_agent.message import (
    Message,
    MessagePriority,
    MessageStatus,
    MessageType,
)


def test_message_creation_and_serialization():
    msg = Message(
        sender="agent_a",
        receiver="agent_b",
        msg_type=MessageType.DIRECT,
        priority=MessagePriority.HIGH,
        payload={"action": "review_pr", "pr_id": 42},
        attachments=["diff.patch"],
    )
    assert msg.sender == "agent_a"
    assert msg.receiver == "agent_b"
    assert msg.priority == MessagePriority.HIGH
    assert msg.status == MessageStatus.PENDING

    data = msg.to_dict()
    restored = Message.from_dict(data)
    assert restored.message_id == msg.message_id
    assert restored.payload == msg.payload
    assert restored.attachments == ["diff.patch"]

    # Priority comparison (higher priority value < lower priority value for min-heap/priority queue)
    msg_crit = Message(sender="a", receiver="b", priority=MessagePriority.CRITICAL)
    assert msg_crit < msg


def test_direct_messaging_and_inbox():
    bus = AgentMessageBus()
    msg = Message(
        sender="sender_1",
        receiver="receiver_1",
        msg_type=MessageType.DIRECT,
        payload={"data": 123},
    )
    bus.send(msg)

    assert bus.get_inbox_size("receiver_1") == 1
    assert bus.get_inbox_size("sender_1") == 0

    popped = bus.receive("receiver_1", block=False)
    assert popped is not None
    assert popped.message_id == msg.message_id
    assert popped.status == MessageStatus.DELIVERED
    assert bus.get_inbox_size("receiver_1") == 0


def test_broadcast_and_multicast():
    bus = AgentMessageBus()
    # Register receivers
    bus.register_inbox("agent_1")
    bus.register_inbox("agent_2")
    bus.register_inbox("agent_3")

    # Broadcast
    bmsg = Message(
        sender="lead",
        receiver="*",
        msg_type=MessageType.BROADCAST,
        payload={"announcement": "standup now"},
    )
    bus.broadcast(bmsg)
    assert bus.get_inbox_size("agent_1") == 1
    assert bus.get_inbox_size("agent_2") == 1
    assert bus.get_inbox_size("agent_3") == 1

    # Multicast
    mmsg = Message(
        sender="lead",
        receiver="",
        msg_type=MessageType.MULTICAST,
        payload={"urgent": True},
    )
    bus.multicast(mmsg, target_agents=["agent_1", "agent_3"])
    assert bus.get_inbox_size("agent_1") == 2
    assert bus.get_inbox_size("agent_2") == 1
    assert bus.get_inbox_size("agent_3") == 2


def test_topic_pub_sub():
    bus = AgentMessageBus()
    bus.subscribe_topic("deployments", "devops_agent")
    bus.subscribe_topic("deployments", "qa_agent")

    event = Message(
        sender="ci_cd",
        receiver="",
        msg_type=MessageType.EVENT,
        payload={"artifact": "v3.3.0", "status": "deployed"},
    )
    bus.publish_topic("deployments", event)

    assert bus.get_inbox_size("devops_agent") == 1
    assert bus.get_inbox_size("qa_agent") == 1

    bus.unsubscribe_topic("deployments", "qa_agent")
    bus.publish_topic("deployments", event)
    assert bus.get_inbox_size("devops_agent") == 2
    assert bus.get_inbox_size("qa_agent") == 1


def test_correlated_request_response():
    bus = AgentMessageBus()
    req = Message(
        sender="client_agent",
        receiver="server_agent",
        msg_type=MessageType.REQUEST,
        payload={"calc": "2+2"},
    )

    # In a background response simulation
    def respond_later():
        time.sleep(0.05)
        bus.respond(
            original_request=req,
            responder="server_agent",
            payload={"result": 4},
        )

    import threading
    t = threading.Thread(target=respond_later)
    t.start()

    resp = bus.request(req, timeout=2.0)
    t.join()

    assert resp is not None
    assert resp.correlation_id == req.message_id
    assert resp.payload == {"result": 4}
    assert resp.status == MessageStatus.DELIVERED


def test_acknowledgement_and_history():
    bus = AgentMessageBus()
    msg = Message(
        sender="a",
        receiver="b",
        msg_type=MessageType.DIRECT,
        payload={"step": 1},
    )
    bus.send(msg)
    assert bus.acknowledge(msg.message_id) is True
    assert bus.get_message(msg.message_id).status == MessageStatus.ACKNOWLEDGED
    assert bus.count() == 1
    assert len(bus.get_conversation_messages(msg.conversation_id)) == 1
