"""
Tests for WebRTC remote debugging terminal security boundaries, backpressure, and cross-session isolation.
"""

import pytest
from core.webrtc_terminal_transport import (
    WebRTCSignalingError,
    WebRTCTerminalTransport,
    WebRTCUnauthorizedError,
)


def test_webrtc_empty_sdp_offer_rejected():
    transport = WebRTCTerminalTransport(
        session_id="session-sec-1",
        sandbox_id="container-sb-01",
        auth_principal="authorized_dev",
        is_container_sandbox=True,
    )

    with pytest.raises(WebRTCSignalingError):
        transport.process_sdp_offer("")

    with pytest.raises(WebRTCSignalingError):
        transport.process_sdp_offer(None)

    transport.close()


def test_webrtc_oversized_input_frame_dropped_with_metrics():
    transport = WebRTCTerminalTransport(
        session_id="session-sec-2",
        sandbox_id="container-sb-02",
        auth_principal="authorized_dev",
        is_container_sandbox=True,
        max_buffer_bytes=1024,  # 1 KB buffer limit
    )
    transport.process_sdp_offer("v=0\r\no=dev 0 0 IN IP4 0.0.0.0\r\ns=test\r\n")

    received = []
    transport.on_input(lambda d: received.append(d))

    # 1. Normal frame (10 bytes)
    transport.send_input("ls -la\n")
    assert len(received) == 1

    # 2. Oversized frame (2 KB)
    oversized = "A" * 2048
    transport.send_input(oversized)

    assert len(received) == 1  # Oversized frame must be dropped
    metrics = transport.get_metrics()
    assert metrics.dropped_messages == 1

    transport.close()


def test_webrtc_cross_session_isolation():
    t1 = WebRTCTerminalTransport("session-1", "sb-1", "alice", is_container_sandbox=True)
    t2 = WebRTCTerminalTransport("session-2", "sb-2", "bob", is_container_sandbox=True)

    t1.process_sdp_offer("v=0\r\no=alice 0 0 IN IP4 0.0.0.0\r\ns=t1\r\n")
    t2.process_sdp_offer("v=0\r\no=bob 0 0 IN IP4 0.0.0.0\r\ns=t2\r\n")

    t1_out = []
    t2_out = []
    t1.on_output(lambda d: t1_out.append(d))
    t2.on_output(lambda d: t2_out.append(d))

    t1.send_output("alice_private_data\n")
    t2.send_output("bob_private_data\n")

    assert t1_out == ["alice_private_data\n"]
    assert t2_out == ["bob_private_data\n"]
    assert "bob" not in t1_out[0]
    assert "alice" not in t2_out[0]

    t1.close()
    t2.close()
