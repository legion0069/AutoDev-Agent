"""
Tests for AutoDev v2.5 WebRTC Remote Debugging Transport and strict security boundaries.
"""

import pytest
from core.terminal_transport import WebSocketTerminalTransport
from core.webrtc_terminal_transport import (
    WebRTCSignalingError,
    WebRTCTerminalTransport,
    WebRTCUnauthorizedError,
)


def test_webrtc_transport_host_execution_prohibited():
    # Attempting to attach WebRTC terminal to coordinator host must be strictly forbidden
    with pytest.raises(WebRTCUnauthorizedError) as exc_info:
        WebRTCTerminalTransport(
            session_id="session-unsafe",
            sandbox_id="host-coord-01",
            auth_principal="admin",
            is_container_sandbox=False,  # Target is coordinator host
        )

    assert "strictly prohibited" in str(exc_info.value)


def test_webrtc_transport_sdp_signaling_and_streaming():
    transport = WebRTCTerminalTransport(
        session_id="session-debug-1",
        sandbox_id="container-sb-01",
        auth_principal="dev_user",
        is_container_sandbox=True,
    )

    caps = transport.get_capabilities()
    assert caps.transport_name == "webrtc"
    assert caps.is_peer_to_peer is True

    # Process client SDP offer
    offer_sdp = "v=0\r\no=Client 12345 0 IN IP4 0.0.0.0\r\ns=Test\r\n"
    answer = transport.process_sdp_offer(offer_sdp)

    assert answer["type"] == "answer"
    assert "v=0" in answer["sdp"]
    assert answer["session_id"] == "session-debug-1"

    # Add ICE candidate
    candidate_added = transport.add_ice_candidate({"candidate": "candidate:1 1 UDP 2130706431 127.0.0.1 50000 typ host"})
    assert candidate_added is True

    # Test I/O streaming
    received_output = []
    transport.on_output(lambda data: received_output.append(data))

    transport.send_output("root@container:/# ls -la\n")
    assert "root@container:/# ls -la\n" in received_output

    metrics = transport.get_metrics()
    assert metrics.messages_sent == 1
    assert metrics.bytes_sent > 0
    assert metrics.connection_state == "connected"

    transport.close("Debug session finished")
    assert transport.get_metrics().connection_state == "closed"


def test_websocket_terminal_transport_fallback():
    ws_transport = WebSocketTerminalTransport(session_id="session-fallback-1")
    caps = ws_transport.get_capabilities()

    assert caps.transport_name == "websocket"
    assert caps.typical_latency_ms == 25.0

    in_data = []
    ws_transport.on_input(lambda d: in_data.append(d))
    ws_transport.send_input("pwd\n")

    assert in_data == ["pwd\n"]
    assert ws_transport.get_metrics().messages_received == 1

    ws_transport.close()
    assert ws_transport.get_metrics().connection_state == "closed"
