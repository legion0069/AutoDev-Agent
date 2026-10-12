"""
test_dashboard_server.py - Unit & Integration tests for DashboardServer & Safe Control Actions (v2.3)
"""

import json
import time
import urllib.request
import urllib.error
import pytest

from core.dashboard_server import DashboardServer
from core.telemetry_models import TelemetryEvent, TelemetrySeverity
from core.telemetry_stream import TelemetryStream


@pytest.fixture
def dashboard_server():
    stream = TelemetryStream()
    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        stream=stream,
        status_provider=lambda: {
            "coordinator_health": "HEALTHY",
            "active_transactions": 1,
            "total_workers": 3,
            "running_tasks": 2,
            "recovery_events": 0,
            "policy_denials": 0,
        },
        workers_provider=lambda: [
            {"worker_id": "worker-1", "is_remote": True, "state": "BUSY", "capabilities": ["python"]}
        ],
        transactions_provider=lambda: [
            {"transaction_id": "tx-dash-1", "status": "RUNNING", "completed_stages": 1, "total_stages": 3}
        ],
    )
    server.start()
    yield server
    server.stop()


def test_dashboard_ui_html(dashboard_server):
    port = dashboard_server.port
    req = urllib.request.Request(f"http://127.0.0.1:{port}/")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "AutoDev Dashboard" in content


def test_dashboard_status_and_workers_api(dashboard_server):
    port = dashboard_server.port

    # /status
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/status") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert data["coordinator_health"] == "HEALTHY"
        assert data["total_workers"] == 3

    # /workers
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/workers") as resp:
        workers = json.loads(resp.read().decode("utf-8"))
        assert len(workers) == 1
        assert workers[0]["worker_id"] == "worker-1"

    # /transactions
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/transactions") as resp:
        txs = json.loads(resp.read().decode("utf-8"))
        assert len(txs) == 1
        assert txs[0]["transaction_id"] == "tx-dash-1"


def test_dashboard_control_actions(dashboard_server):
    port = dashboard_server.port

    # Post control action
    action_url = f"http://127.0.0.1:{port}/control/pause"
    req_body = json.dumps({"transaction_id": "tx-dash-1"}).encode("utf-8")
    req = urllib.request.Request(
        action_url,
        data=req_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        assert res_data.get("success") is True


def test_dashboard_auth_enforcement():
    stream = TelemetryStream()
    auth_server = DashboardServer(
        host="127.0.0.1",
        port=0,
        stream=stream,
        auth_token="secret-token-123",
    )
    auth_server.start()
    port = auth_server.port

    try:
        # Request without auth should be 401
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/status")
        assert excinfo.value.code == 401

        # Request with valid Bearer token
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/status",
            headers={"Authorization": "Bearer secret-token-123"},
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200

    finally:
        auth_server.stop()


def test_dashboard_security_headers(dashboard_server):
    port = dashboard_server.port
    req = urllib.request.Request(f"http://127.0.0.1:{port}/")
    with urllib.request.urlopen(req) as resp:
        headers = dict(resp.headers)
        assert "X-Frame-Options" in headers or "x-frame-options" in headers
        assert "X-Content-Type-Options" in headers or "x-content-type-options" in headers


def test_dashboard_all_control_actions(dashboard_server):
    port = dashboard_server.port
    actions = ["resume", "cancel", "approve", "drain_worker"]

    for act in actions:
        url = f"http://127.0.0.1:{port}/control/{act}"
        body = json.dumps({"target_id": "test-target"}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("success") is True
            assert data.get("action") == act

