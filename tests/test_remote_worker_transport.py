"""
test_remote_worker_transport.py - Unit tests for Remote Worker Transport Abstraction (v2.3)
"""

import pytest
from core.remote_worker_transport import (
    RemoteTransportMode,
    RemoteWorkerTransport,
    TransportConfig,
    TransportError,
)


def test_transport_mode_resolution():
    assert RemoteTransportMode.LOCAL == "local"
    assert RemoteTransportMode.REMOTE == "remote"
    assert RemoteTransportMode.HYBRID == "hybrid"


def test_transport_config_defaults():
    cfg = TransportConfig()
    assert cfg.mode == RemoteTransportMode.LOCAL
    assert cfg.coordinator_endpoint == "127.0.0.1:50051"
    assert cfg.use_mtls is True


def test_transport_base_lifecycle():
    cfg = TransportConfig(mode=RemoteTransportMode.LOCAL)
    transport = RemoteWorkerTransport(cfg)
    assert not transport.is_connected

    transport.connect()
    assert transport.is_connected

    transport.disconnect()
    assert not transport.is_connected

    # start/stop aliases
    transport.start()
    assert transport.is_connected
    transport.stop()
    assert not transport.is_connected


def test_transport_config_custom_endpoint():
    cfg = TransportConfig(coordinator_endpoint="192.168.1.100:8443", mode=RemoteTransportMode.REMOTE)
    assert cfg.host == "192.168.1.100"
    assert cfg.port == 8443
    assert cfg.mode == RemoteTransportMode.REMOTE


def test_transport_config_secret_redaction():
    cfg = TransportConfig(auth_token="super-secret-token-12345")
    d = cfg.to_dict()
    assert d["auth_token"] == "[REDACTED]"
    assert "super-secret-token-12345" not in str(d)


def test_transport_error_hierarchy():
    from core.remote_worker_transport import TransportConnectionError, TransportSecurityError
    assert issubclass(TransportConnectionError, TransportError)
    assert issubclass(TransportSecurityError, TransportError)

