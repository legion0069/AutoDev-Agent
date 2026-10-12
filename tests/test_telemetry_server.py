"""
test_telemetry_server.py - Tests for Embedded Telemetry HTTP & SSE Server (v2.2)
"""

import json
import time
import urllib.request
import urllib.error
import pytest
from core.telemetry_models import TelemetryEvent, TelemetrySeverity
from core.telemetry_server import TelemetryServer
from core.telemetry_stream import TelemetryStream


def test_telemetry_server_health_and_status(tmp_path):
    """Verifies /health and /status endpoints on localhost."""
    stream = TelemetryStream()
    stream.publish_event("SYS_INIT", "System initialized")

    server = TelemetryServer(host="127.0.0.1", port=0, stream=stream, report_dir=tmp_path)
    server.start()

    try:
        base_url = f"http://127.0.0.1:{server.port}"

        # 1. Health Probe
        with urllib.request.urlopen(f"{base_url}/health", timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "HEALTHY"
            assert data["version"] == "2.2.0"

        # 2. Status Endpoint
        with urllib.request.urlopen(f"{base_url}/status", timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["buffered_events_count"] == 1

    finally:
        server.stop()


def test_telemetry_server_auth_token_enforcement():
    """Verifies token authentication on telemetry server endpoints."""
    server = TelemetryServer(
        host="127.0.0.1",
        port=0,
        auth_token="secret-telemetry-key",
    )
    server.start()

    try:
        base_url = f"http://127.0.0.1:{server.port}"

        # Request without token -> 401
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{base_url}/health", timeout=3)
        assert exc_info.value.code == 401

        # Request with Bearer header -> 200
        req = urllib.request.Request(
            f"{base_url}/health",
            headers={"Authorization": "Bearer secret-telemetry-key"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200

        # Request with query token -> 200
        with urllib.request.urlopen(f"{base_url}/health?token=secret-telemetry-key", timeout=3) as resp:
            assert resp.status == 200

    finally:
        server.stop()


def test_telemetry_server_transaction_report_retrieval(tmp_path):
    """Verifies /reports/<tx_id> endpoint serves saved transaction JSON."""
    report_file = tmp_path / "tx-999.json"
    report_file.write_text(json.dumps({"transaction_id": "tx-999", "overall_success": True}), encoding="utf-8")

    server = TelemetryServer(host="127.0.0.1", port=0, report_dir=tmp_path)
    server.start()

    try:
        base_url = f"http://127.0.0.1:{server.port}"

        # Existing report
        with urllib.request.urlopen(f"{base_url}/reports/tx-999", timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["transaction_id"] == "tx-999"
            assert data["overall_success"] is True

        # Non-existent report -> 404
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{base_url}/reports/non-existent-tx", timeout=3)
        assert exc_info.value.code == 404

    finally:
        server.stop()


def test_telemetry_server_custom_snapshot_provider():
    """Verifies custom snapshot provider returns custom status payload."""
    def custom_provider():
        return {"custom_metric": 42, "workers_active": 3}

    server = TelemetryServer(host="127.0.0.1", port=0, snapshot_provider=custom_provider)
    server.start()

    try:
        base_url = f"http://127.0.0.1:{server.port}"
        with urllib.request.urlopen(f"{base_url}/status", timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["custom_metric"] == 42
            assert data["workers_active"] == 3
    finally:
        server.stop()


def test_telemetry_server_unknown_endpoint_returns_404():
    """Verifies unmapped endpoints return 404."""
    server = TelemetryServer(host="127.0.0.1", port=0)
    server.start()

    try:
        base_url = f"http://127.0.0.1:{server.port}"
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{base_url}/unmapped_api", timeout=3)
        assert exc_info.value.code == 404
    finally:
        server.stop()

