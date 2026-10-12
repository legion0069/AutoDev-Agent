"""
test_inter_company_bus.py - Unit & Integration Tests for InterCompanyBus (AutoDev Version 3.5)
"""

import threading
import time
import pytest

from core.inter_company_bus import (
    FederationMessage,
    FederationMessagePriority,
    FederationMessageType,
    InterCompanyBus,
    MessageClassification,
)


def test_bus_initialization():
    bus = InterCompanyBus(secret_key="TEST_KEY")
    stats = bus.get_bus_telemetry()
    assert stats["registered_companies"] == 0
    assert stats["total_routed_messages"] == 0
    assert stats["dead_letter_count"] == 0


def test_company_registration_and_inbox():
    bus = InterCompanyBus()
    bus.register_company("COMP-A")
    bus.register_company("COMP-B")
    stats = bus.get_bus_telemetry()
    assert stats["registered_companies"] == 2


def test_message_signing_and_verification():
    msg = FederationMessage(
        company_id="COMP-A",
        target_company_id="COMP-B",
        sender="Agent1",
        receiver="Agent2",
        payload={"task": "DataAnalysis"},
    )
    sig = msg.sign(secret_key="SECRET_123")
    assert sig is not None and len(sig) == 64
    assert msg.verify_signature(secret_key="SECRET_123") is True
    assert msg.verify_signature(secret_key="WRONG_SECRET") is False


def test_invalid_signature_routes_to_dead_letter():
    bus = InterCompanyBus(secret_key="CORRECT_KEY")
    msg = FederationMessage(
        company_id="COMP-A",
        target_company_id="COMP-B",
        sender="Agent1",
        receiver="Agent2",
        payload={"task": "Malicious"},
    )
    msg.sign(secret_key="WRONG_KEY")  # Signed with wrong secret
    success = bus.send_message(msg)
    assert success is False
    assert msg.status == "FAILED"
    dead_letters = bus.get_dead_letters()
    assert len(dead_letters) == 1
    assert dead_letters[0].message_id == msg.message_id


def test_point_to_point_message_delivery():
    bus = InterCompanyBus()
    bus.register_company("COMP-A")
    bus.register_company("COMP-B")

    msg = FederationMessage(
        company_id="COMP-A",
        target_company_id="COMP-B",
        sender="AgentA",
        receiver="AgentB",
        priority=FederationMessagePriority.HIGH,
        payload={"query": "SystemStatus"},
    )
    assert bus.send_message(msg) is True

    inbox_b = bus.get_company_messages("COMP-B")
    assert len(inbox_b) == 1
    assert inbox_b[0].message_id == msg.message_id
    assert inbox_b[0].status == "DELIVERED"

    # Inbox A should not have received it
    assert len(bus.get_company_messages("COMP-A")) == 0


def test_inbox_drain():
    bus = InterCompanyBus()
    bus.register_company("COMP-A")
    bus.register_company("COMP-B")

    for i in range(5):
        bus.send_message(FederationMessage(
            company_id="COMP-A",
            target_company_id="COMP-B",
            payload={"item": i},
        ))

    msgs = bus.get_company_messages("COMP-B", drain=True)
    assert len(msgs) == 5
    # Inbox should now be empty after drain
    assert len(bus.get_company_messages("COMP-B")) == 0


def test_priority_sorting_in_inbox():
    bus = InterCompanyBus()
    bus.register_company("COMP-B")

    msg_low = FederationMessage(company_id="COMP-A", target_company_id="COMP-B", priority=FederationMessagePriority.LOW, payload={"p": "low"})
    msg_emerg = FederationMessage(company_id="COMP-A", target_company_id="COMP-B", priority=FederationMessagePriority.EMERGENCY, payload={"p": "emerg"})
    msg_normal = FederationMessage(company_id="COMP-A", target_company_id="COMP-B", priority=FederationMessagePriority.NORMAL, payload={"p": "norm"})

    bus.send_message(msg_low)
    bus.send_message(msg_emerg)
    bus.send_message(msg_normal)

    sorted_msgs = bus.get_company_messages("COMP-B")
    assert sorted_msgs[0].priority == FederationMessagePriority.EMERGENCY
    assert sorted_msgs[1].priority == FederationMessagePriority.NORMAL
    assert sorted_msgs[2].priority == FederationMessagePriority.LOW


def test_broadcast_message_delivery():
    bus = InterCompanyBus()
    bus.register_company("COMP-A")
    bus.register_company("COMP-B")
    bus.register_company("COMP-C")

    broadcast_msg = FederationMessage(
        company_id="COMP-A",
        target_company_id="ALL",
        message_type=FederationMessageType.INCIDENT_BROADCAST,
        payload={"incident": "GlobalLatencySpike"},
    )
    bus.send_message(broadcast_msg)

    # Receiver companies should have received it, but not sender
    assert len(bus.get_company_messages("COMP-B")) == 1
    assert len(bus.get_company_messages("COMP-C")) == 1
    assert len(bus.get_company_messages("COMP-A")) == 0


def test_department_inbox_routing():
    bus = InterCompanyBus()
    bus.register_department("COMP-A", "QA")

    msg = FederationMessage(
        company_id="COMP-B",
        target_company_id="COMP-A",
        target_department_id="QA",
        payload={"action": "RunSmokeTest"},
    )
    bus.send_message(msg)

    dept_msgs = bus.get_department_messages("COMP-A", "QA")
    assert len(dept_msgs) == 1
    assert dept_msgs[0].payload["action"] == "RunSmokeTest"


def test_topic_subscription():
    bus = InterCompanyBus()
    received = []

    def topic_cb(msg: FederationMessage):
        received.append(msg.message_id)

    bus.subscribe_topic("security.alerts", topic_cb)

    msg = FederationMessage(
        company_id="COMP-SEC",
        target_company_id="ALL",
        payload={"topic": "security.alerts", "alert": "CVE-2026-001"},
    )
    bus.send_message(msg)

    assert len(received) == 1
    assert received[0] == msg.message_id


def test_type_subscription():
    bus = InterCompanyBus()
    received_types = []

    bus.subscribe_type(
        FederationMessageType.BUDGET_REQUEST,
        lambda msg: received_types.append(msg.message_id),
    )

    msg = FederationMessage(
        company_id="COMP-A",
        target_company_id="COMP-FIN",
        message_type=FederationMessageType.BUDGET_REQUEST,
        payload={"requested_amount": 50000},
    )
    bus.send_message(msg)

    assert len(received_types) == 1


def test_trace_and_thread_tracking():
    bus = InterCompanyBus()
    trace_id = "TRACE-ALPHA"
    thread_id = "THREAD-BETA"

    msg1 = FederationMessage(company_id="COMP-A", target_company_id="COMP-B", trace_id=trace_id, thread_id=thread_id)
    msg2 = FederationMessage(company_id="COMP-B", target_company_id="COMP-A", trace_id=trace_id, thread_id=thread_id, correlation_id=msg1.message_id)

    bus.send_message(msg1)
    bus.send_message(msg2)

    trace = bus.get_trace(trace_id)
    assert len(trace) == 2
    assert trace[0].message_id == msg1.message_id
    assert trace[1].message_id == msg2.message_id

    thread = bus.get_thread(thread_id)
    assert len(thread) == 2


def test_convenience_broadcasts():
    bus = InterCompanyBus()
    bus.register_company("COMP-A")
    bus.register_company("COMP-B")

    sec_alert = bus.broadcast_security_alert("COMP-SEC", "CRITICAL", {"details": "ZeroDay"})
    assert sec_alert.priority == FederationMessagePriority.EMERGENCY
    assert sec_alert.classification == MessageClassification.RESTRICTED

    inc_msg = bus.broadcast_incident("COMP-OPS", "SEV-1", "AuthenticationGateway", "NetworkSplit")
    assert inc_msg.priority == FederationMessagePriority.CRITICAL

    assert len(bus.get_company_messages("COMP-A")) == 2
    assert len(bus.get_company_messages("COMP-B")) == 2
