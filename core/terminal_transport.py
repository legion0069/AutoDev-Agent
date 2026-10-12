"""
AutoDev Version 2.5 - Terminal Transport Abstraction & Capabilities.

Defines the pluggable transport layer for interactive remote debugging sessions,
supporting both WebRTC low-latency data channels and resilient WebSocket fallback.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class TerminalTransportCapabilities:
    """Declared capabilities of a terminal transport implementation."""
    transport_name: str  # 'webrtc', 'websocket'
    supports_binary_stream: bool = True
    supports_backpressure: bool = True
    is_peer_to_peer: bool = False
    typical_latency_ms: float = 10.0


@dataclass
class TerminalConnectionMetrics:
    """Real-time observability metrics for an active terminal streaming connection."""
    session_id: str
    transport_type: str
    connection_state: str  # 'connecting', 'connected', 'degraded', 'closed', 'failed'
    bytes_sent: int = 0
    bytes_received: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    dropped_messages: int = 0
    round_trip_latency_ms: float = 0.0
    reconnect_attempts: int = 0
    connected_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)


class TerminalTransport(abc.ABC):
    """Abstract base class for terminal I/O transports."""

    @abc.abstractmethod
    def get_capabilities(self) -> TerminalTransportCapabilities:
        """Return the transport capabilities."""
        pass

    @abc.abstractmethod
    def send_input(self, data: str) -> None:
        """Send user keystrokes / terminal input to the remote PTY."""
        pass

    @abc.abstractmethod
    def send_output(self, data: str) -> None:
        """Send PTY output stream to the attached client."""
        pass

    @abc.abstractmethod
    def send_resize(self, cols: int, rows: int) -> None:
        """Send terminal window resize event (SIGWINCH)."""
        pass

    @abc.abstractmethod
    def on_input(self, callback: Callable[[str], None]) -> None:
        """Register callback for received user input."""
        pass

    @abc.abstractmethod
    def on_output(self, callback: Callable[[str], None]) -> None:
        """Register callback for terminal output stream."""
        pass

    @abc.abstractmethod
    def get_metrics(self) -> TerminalConnectionMetrics:
        """Retrieve connection metrics."""
        pass

    @abc.abstractmethod
    def close(self, reason: str = "") -> None:
        """Gracefully terminate transport session."""
        pass


class WebSocketTerminalTransport(TerminalTransport):
    """
    Standard WebSocket/HTTP bidirectional transport for terminal streaming.
    Default resilient fallback across all browser and proxy environments.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._metrics = TerminalConnectionMetrics(
            session_id=session_id,
            transport_type="websocket",
            connection_state="connected",
        )
        self._input_callbacks: List[Callable[[str], None]] = []
        self._output_callbacks: List[Callable[[str], None]] = []
        self._is_closed = False

    def get_capabilities(self) -> TerminalTransportCapabilities:
        return TerminalTransportCapabilities(
            transport_name="websocket",
            supports_binary_stream=True,
            supports_backpressure=True,
            is_peer_to_peer=False,
            typical_latency_ms=25.0,
        )

    def send_input(self, data: str) -> None:
        if self._is_closed:
            return
        self._metrics.bytes_received += len(data.encode())
        self._metrics.messages_received += 1
        self._metrics.last_activity_at = time.time()
        for cb in self._input_callbacks:
            cb(data)

    def send_output(self, data: str) -> None:
        if self._is_closed:
            return
        self._metrics.bytes_sent += len(data.encode())
        self._metrics.messages_sent += 1
        self._metrics.last_activity_at = time.time()
        for cb in self._output_callbacks:
            cb(data)

    def send_resize(self, cols: int, rows: int) -> None:
        self._metrics.last_activity_at = time.time()

    def on_input(self, callback: Callable[[str], None]) -> None:
        self._input_callbacks.append(callback)

    def on_output(self, callback: Callable[[str], None]) -> None:
        self._output_callbacks.append(callback)

    def get_metrics(self) -> TerminalConnectionMetrics:
        return self._metrics

    def close(self, reason: str = "") -> None:
        self._is_closed = True
        self._metrics.connection_state = "closed"
