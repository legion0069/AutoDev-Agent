"""
test_communication_bus.py - AutoDev Version 3.4
Unit and integration tests for Enterprise Communication Bus:
- Priority routing, direct delivery, and broadcasts
- Thread tracking and correlation linking
- Inbox management, acknowledgements, and search queries
- Pub/Sub type subscribers and escalation handlers
"""

import pytest
import time
from core.communication_bus import (
    CommunicationBus,
    MessagePriority,
    OrgMessage,
    OrgMessageType,
)


@pytest.fixture
def bus():
    b = CommunicationBus()
    b.register_entity("Backend")
    b.register_entity("Frontend")
    b.register_entity("QA")
    b.register_entity("Security")
    b.register_entity("EngineeringManager")
    return b


def test_register_entity(bus: CommunicationBus):
    bus.register_entity("DevOps")
    telemetry = bus.get_bus_telemetry()
    assert "DevOps" in telemetry["registered_entities"]


def test_send_direct_message(bus: CommunicationBus):
    msg = OrgMessage(
        sender="Backend",
        receiver="QA",
        priority=MessagePriority.NORMAL,
        message_type=OrgMessageType.TASK_REQUEST,
        payload={"task_id": "T-101", "details": "Verify payment endpoint"},
    )
    assert bus.send_message(msg) is True
    assert msg.status == "DELIVERED"

    unread = bus.get_messages("QA", unread_only=True)
    assert len(unread) == 1
    assert unread[0].message_id == msg.message_id
    assert unread[0].acknowledged is True
    assert unread[0].status == "ACKNOWLEDGED"

    # Subsequent fetch should be empty
    assert len(bus.get_messages("QA", unread_only=True)) == 0


def test_peek_messages_does_not_clear(bus: CommunicationBus):
    msg = OrgMessage(
        sender="Backend",
        receiver="QA",
        priority=MessagePriority.NORMAL,
        message_type=OrgMessageType.TASK_REQUEST,
        payload={"task": "Inspect logs"},
    )
    bus.send_message(msg)

    peeked = bus.peek_messages("QA")
    assert len(peeked) == 1
    # Unread messages should still be present
    unread = bus.get_messages("QA", unread_only=True)
    assert len(unread) == 1


def test_broadcast_message(bus: CommunicationBus):
    bcast = bus.broadcast(
        sender="EngineeringManager",
        message_type=OrgMessageType.STATUS_UPDATE,
        payload={"announcement": "Sprint 42 kickoff at 10:00 AM"},
        priority=MessagePriority.HIGH,
    )
    assert bcast.receiver == "ALL"

    for dept in ["Backend", "Frontend", "QA", "Security"]:
        msgs = bus.get_messages(dept)
        assert len(msgs) == 1
        assert msgs[0].message_id == bcast.message_id

    # Sender should not receive its own broadcast in inbox
    assert len(bus.get_messages("EngineeringManager")) == 0


def test_inbox_priority_sorting(bus: CommunicationBus):
    msg_low = OrgMessage(sender="Backend", receiver="QA", priority=MessagePriority.LOW, payload={"id": "low"})
    msg_crit = OrgMessage(sender="Security", receiver="QA", priority=MessagePriority.CRITICAL, payload={"id": "crit"})
    msg_norm = OrgMessage(sender="Frontend", receiver="QA", priority=MessagePriority.NORMAL, payload={"id": "norm"})

    bus.send_message(msg_low)
    bus.send_message(msg_crit)
    bus.send_message(msg_norm)

    qa_msgs = bus.get_messages("QA", unread_only=True)
    assert len(qa_msgs) == 3
    # Top message must be CRITICAL
    assert qa_msgs[0].priority == MessagePriority.CRITICAL
    assert qa_msgs[0].payload["id"] == "crit"
    assert qa_msgs[1].priority == MessagePriority.NORMAL
    assert qa_msgs[2].priority == MessagePriority.LOW


def test_correlated_response(bus: CommunicationBus):
    req = OrgMessage(
        sender="Backend",
        receiver="Security",
        priority=MessagePriority.HIGH,
        message_type=OrgMessageType.REVIEW,
        payload={"code": "def auth(): pass"},
        response_required=True,
    )
    bus.send_message(req)

    # Respond back
    resp = bus.respond(
        original_message=req,
        sender="Security",
        payload={"review": "Approved, no vulnerabilities"},
        message_type=OrgMessageType.APPROVAL,
    )

    assert resp.correlation_id == req.message_id
    assert resp.thread_id == req.thread_id
    assert resp.receiver == "Backend"

    be_msgs = bus.get_messages("Backend")
    assert len(be_msgs) == 1
    assert be_msgs[0].payload["review"] == "Approved, no vulnerabilities"


def test_thread_tracking(bus: CommunicationBus):
    tid = "THREAD-SPRINT-01"
    m1 = OrgMessage(sender="Backend", receiver="Frontend", thread_id=tid, payload={"step": 1})
    m2 = OrgMessage(sender="Frontend", receiver="Backend", thread_id=tid, payload={"step": 2})
    m3 = OrgMessage(sender="QA", receiver="Backend", thread_id=tid, payload={"step": 3})

    bus.send_message(m1)
    bus.send_message(m2)
    bus.send_message(m3)

    thread_msgs = bus.get_thread_history(tid)
    assert len(thread_msgs) == 3
    assert [m.payload["step"] for m in thread_msgs] == [1, 2, 3]


def test_pubsub_subscriber(bus: CommunicationBus):
    received_incidents = []

    def on_incident(msg: OrgMessage):
        received_incidents.append(msg)

    bus.subscribe(OrgMessageType.INCIDENT_REPORT, on_incident)

    inc_msg = OrgMessage(
        sender="DevOps",
        receiver="ALL",
        message_type=OrgMessageType.INCIDENT_REPORT,
        payload={"severity": "SEV-1", "title": "Database connection pool timeout"},
    )
    bus.send_message(inc_msg)

    assert len(received_incidents) == 1
    assert received_incidents[0].payload["severity"] == "SEV-1"


def test_escalation_listener(bus: CommunicationBus):
    escalations = []

    def on_escalation(msg: OrgMessage):
        escalations.append(msg)

    bus.register_escalation_listener(on_escalation)

    esc_msg = OrgMessage(
        sender="QA",
        receiver="EngineeringManager",
        message_type=OrgMessageType.ESCALATION,
        priority=MessagePriority.CRITICAL,
        payload={"blocker": "Environment offline"},
    )
    bus.send_message(esc_msg)

    assert len(escalations) == 1
    assert escalations[0].status == "ESCALATED"


def test_query_messages_filters(bus: CommunicationBus):
    for i in range(10):
        bus.send_message(
            OrgMessage(
                sender="Backend" if i % 2 == 0 else "Frontend",
                receiver="QA",
                message_type=OrgMessageType.TASK_REQUEST if i < 5 else OrgMessageType.STATUS_UPDATE,
                priority=MessagePriority.HIGH if i == 0 else MessagePriority.NORMAL,
                payload={"index": i},
            )
        )

    # Filter by sender
    be_msgs = bus.query_messages(sender="Backend")
    assert len(be_msgs) == 5

    # Filter by type
    status_msgs = bus.query_messages(message_type=OrgMessageType.STATUS_UPDATE)
    assert len(status_msgs) == 5

    # Filter by min priority
    high_msgs = bus.query_messages(min_priority=MessagePriority.HIGH)
    assert len(high_msgs) == 1


def test_message_serialization_roundtrip():
    msg = OrgMessage(
        sender="Architecture",
        receiver="Backend",
        priority=MessagePriority.CRITICAL,
        message_type=OrgMessageType.ARCHITECTURE_DECISION,
        payload={"adr": "ADR-01", "decision": "Hexagonal Architecture"},
        metadata={"author": "ChiefArchitect"},
    )
    d = msg.to_dict()
    assert d["priority"] == 4
    assert d["message_type"] == "ARCHITECTURE_DECISION"

    restored = OrgMessage.from_dict(d)
    assert restored.message_id == msg.message_id
    assert restored.priority == MessagePriority.CRITICAL
    assert restored.message_type == OrgMessageType.ARCHITECTURE_DECISION
    assert restored.payload["adr"] == "ADR-01"


def test_clear_bus(bus: CommunicationBus):
    bus.send_message(OrgMessage(sender="Backend", receiver="QA", payload={"x": 1}))
    bus.clear()
    telemetry = bus.get_bus_telemetry()
    assert telemetry["total_messages_exchanged"] == 0
    assert len(telemetry["registered_entities"]) == 0
