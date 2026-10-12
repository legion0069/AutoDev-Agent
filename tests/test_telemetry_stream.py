"""
test_telemetry_stream.py - Tests for Real-Time Telemetry Ring Buffer & SSE Formatting (v2.2)
"""

import json
import pytest
from core.telemetry_models import TelemetryEvent, TelemetrySeverity
from core.telemetry_stream import TelemetryStream


def test_publish_and_buffer_events():
    """Verifies publishing events to ring buffer with secret redaction."""
    stream = TelemetryStream(max_buffer_size=10)

    evt1 = stream.publish_event(
        event_type="TRANSACTION_STARTED",
        message="Starting transaction tx-100 with key sk-1234567890abcdef1234567890",
        transaction_id="tx-100",
        metadata={"token": "Bearer secret-auth-token-12345"},
    )

    assert stream.event_count == 1
    assert evt1.event_id == "evt-000001"
    assert "[REDACTED]" in evt1.message
    assert evt1.metadata["token"] == "[REDACTED]"


def test_ring_buffer_bounded_capacity():
    """Verifies ring buffer evicts oldest events when max_buffer_size is exceeded."""
    stream = TelemetryStream(max_buffer_size=3)

    for i in range(5):
        stream.publish_event(event_type=f"EVENT_{i}", message=f"Message {i}")

    assert stream.event_count == 3
    recent = stream.get_recent_events()
    assert len(recent) == 3
    assert recent[0].event_type == "EVENT_2"
    assert recent[2].event_type == "EVENT_4"


def test_subscribe_and_receive_events():
    """Verifies subscriber queues receive broadcast events."""
    stream = TelemetryStream()
    client_q, catchup = stream.subscribe()

    assert len(catchup) == 0

    stream.publish_event(event_type="STAGE_COMPLETED", message="Stage 1 complete")
    evt = client_q.get(timeout=1.0)

    assert evt is not None
    assert evt.event_type == "STAGE_COMPLETED"
    stream.unsubscribe(client_q)


def test_subscribe_catchup_by_last_event_id():
    """Verifies reconnecting with last_event_id replays missed events."""
    stream = TelemetryStream()
    stream.publish_event("E1")
    e2 = stream.publish_event("E2")
    stream.publish_event("E3")
    stream.publish_event("E4")

    # Reconnect after E2
    client_q, catchup = stream.subscribe(last_event_id=e2.event_id)

    assert len(catchup) == 2
    assert catchup[0].event_type == "E3"
    assert catchup[1].event_type == "E4"
    stream.unsubscribe(client_q)


def test_format_sse_wire_protocol():
    """Verifies standard Server-Sent Events wire format output."""
    evt = TelemetryEvent(
        event_id="evt-000099",
        event_type="WORKER_HEARTBEAT",
        message="Worker alive",
        severity=TelemetrySeverity.INFO,
    )
    sse_text = TelemetryStream.format_sse(evt)

    assert sse_text.startswith("id: evt-000099\n")
    assert "event: WORKER_HEARTBEAT\n" in sse_text
    assert "data: {" in sse_text
    assert sse_text.endswith("\n\n")


def test_telemetry_filter_by_transaction_id():
    """Verifies filtering buffered events by transaction_id."""
    stream = TelemetryStream()
    stream.publish_event("E1", transaction_id="tx-A")
    stream.publish_event("E2", transaction_id="tx-B")
    stream.publish_event("E3", transaction_id="tx-A")

    tx_a_events = stream.get_recent_events(transaction_id="tx-A")
    assert len(tx_a_events) == 2
    assert all(e.transaction_id == "tx-A" for e in tx_a_events)


def test_telemetry_multi_subscriber_fanout():
    """Verifies that events are broadcast to all active subscribers."""
    stream = TelemetryStream()
    q1, _ = stream.subscribe()
    q2, _ = stream.subscribe()

    stream.publish_event("BROADCAST_TEST", message="Hello Subscribers")

    e1 = q1.get(timeout=1.0)
    e2 = q2.get(timeout=1.0)

    assert e1.event_type == "BROADCAST_TEST"
    assert e2.event_type == "BROADCAST_TEST"

    stream.unsubscribe(q1)
    stream.unsubscribe(q2)


def test_telemetry_snapshot_model_serialization():
    """Verifies TelemetrySnapshot roundtrip serialization."""
    from core.telemetry_models import TelemetrySnapshot
    snap = TelemetrySnapshot(
        coordinator_status="HEALTHY",
        registered_workers_count=4,
        idle_workers_count=3,
        busy_workers_count=1,
        active_transactions_count=1,
    )
    d = snap.to_dict()
    assert d["coordinator_status"] == "HEALTHY"
    assert d["registered_workers_count"] == 4
    assert d["idle_workers_count"] == 3
    assert d["busy_workers_count"] == 1


def test_telemetry_stream_empty_get_recent_events():
    """Verifies querying an empty stream returns empty list."""
    stream = TelemetryStream()
    assert stream.get_recent_events() == []


