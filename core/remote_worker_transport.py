"""
remote_worker_transport.py - Remote Worker Transport Abstraction for AutoDev (v2.3)

Provides an extensible transport abstraction supporting local, remote (mTLS/RPC),
and hybrid worker coordination. Allows AutoDev to run without mandatory gRPC
dependencies while enabling authenticated multi-machine execution when configured.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from core.worker_protocol import (
    PROTOCOL_VERSION,
    TaskAssignmentPayload,
    TaskResultPayload,
    WorkerCapabilities,
    WorkerHeartbeat,
    WorkerRegistrationRequest,
    WorkerRegistrationResponse,
    WorkerStatus,
)

logger = logging.getLogger("AutoDev.RemoteWorkerTransport")


class RemoteTransportMode(str, Enum):
    """Supported deployment modes for worker execution."""
    LOCAL = "local"      # Local worker threads/processes
    REMOTE = "remote"    # Authenticated remote workers over mTLS/RPC
    HYBRID = "hybrid"    # Both local and remote workers coordinated concurrently


class TransportError(Exception):
    """Base exception for remote worker transport operations."""
    pass


class TransportConnectionError(TransportError):
    """Raised when connection to coordinator or worker fails."""
    pass


class TransportSecurityError(TransportError):
    """Raised when TLS or authentication verification fails."""
    pass


@dataclass
class TransportConfig:
    """Configuration options for worker transport."""
    mode: RemoteTransportMode = RemoteTransportMode.LOCAL
    host: str = "127.0.0.1"
    port: int = 50051
    coordinator_endpoint: str = "127.0.0.1:50051"
    use_tls: bool = True
    use_mtls: bool = True
    ca_cert_path: Optional[str] = None
    server_cert_path: Optional[str] = None
    server_key_path: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None
    auth_token: Optional[str] = None
    request_timeout_seconds: float = 30.0
    heartbeat_interval_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.coordinator_endpoint and ":" in self.coordinator_endpoint:
            parts = self.coordinator_endpoint.split(":")
            self.host = parts[0]
            try:
                self.port = int(parts[1])
            except ValueError:
                pass
        elif self.host and self.port:
            self.coordinator_endpoint = f"{self.host}:{self.port}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value if isinstance(self.mode, RemoteTransportMode) else str(self.mode),
            "coordinator_endpoint": self.coordinator_endpoint,
            "host": self.host,
            "port": self.port,
            "use_tls": self.use_tls,
            "use_mtls": self.use_mtls,
            "ca_cert_path": self.ca_cert_path,
            "server_cert_path": self.server_cert_path,
            "client_cert_path": self.client_cert_path,
            "auth_token": "[REDACTED]" if self.auth_token else None,
            "request_timeout_seconds": self.request_timeout_seconds,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
        }


class RemoteWorkerTransport:
    """
    Base transport implementation supporting local and remote channels.
    """

    def __init__(self, config: Optional[TransportConfig] = None) -> None:
        self.config = config or TransportConfig()
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def connect(self) -> None:
        """Establishes transport connection."""
        self._is_connected = True
        logger.debug("RemoteWorkerTransport connected (mode: %s)", self.config.mode)

    def disconnect(self) -> None:
        """Closes transport connection."""
        self._is_connected = False
        logger.debug("RemoteWorkerTransport disconnected.")

    def start(self) -> None:
        self.connect()

    def stop(self) -> None:
        self.disconnect()
