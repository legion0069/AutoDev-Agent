"""
dashboard_server.py - Real-time Interactive Web Dashboard & Control Server for AutoDev (v2.3)

Provides an integrated HTTP/SSE server serving the glassmorphic dark-mode dashboard,
live system metrics, worker fleet states, execution timelines, and authenticated safe control actions.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import queue
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Callable, Dict, List, Optional, Set, Union
from urllib.parse import parse_qs, urlparse

from core.telemetry_models import TelemetryEvent, TelemetrySeverity
from core.telemetry_stream import TelemetryStream

logger = logging.getLogger("AutoDev.DashboardServer")

DASHBOARD_HTML_PATH = Path("dashboard/index.html")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server allowing concurrent SSE streams and REST requests."""
    daemon_threads = True
    allow_reuse_address = True


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler serving static dashboard assets, REST APIs, SSE telemetry,
    and authenticated control endpoints.
    """

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug(format, *args)

    @property
    def server_instance(self) -> DashboardServer:
        return self.server.dashboard_server  # type: ignore

    def _check_auth(self) -> bool:
        auth_token = self.server_instance.auth_token
        if not auth_token:
            return True
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            return token == auth_token
        # Check query param
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        token_param = qs.get("token", [""])[0]
        return token_param == auth_token

    def _send_json(self, data: Any, status_code: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_content: str, status_code: int = 200) -> None:
        body = html_content.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' data:; connect-src 'self';"
        )
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if not path:
            path = "/"

        # Public UI
        if path in ("/", "/dashboard"):
            html = self.server_instance.get_dashboard_html()
            self._send_html(html)
            return

        if not self._check_auth():
            self._send_json({"error": "Unauthorized: invalid or missing auth token"}, 401)
            return

        # 1. Health Probe
        if path == "/health":
            self._send_json({
                "status": "HEALTHY",
                "version": "2.3.0",
                "timestamp": time.time(),
            })
            return

        # 2. System Status & Summary Snapshot
        if path == "/status":
            snapshot = self.server_instance.get_status_snapshot()
            self._send_json(snapshot)
            return

        # 3. Worker Fleet
        if path == "/workers":
            workers = self.server_instance.get_workers()
            self._send_json(workers)
            return

        # 4. Transactions
        if path == "/transactions":
            txs = self.server_instance.get_transactions()
            self._send_json(txs)
            return

        # 5. Quality Intelligence Snapshot (v2.7)
        if path == "/quality":
            quality_data = self.server_instance.get_quality_snapshot()
            self._send_json(quality_data)
            return

        # 6. Live SSE Stream (/events)
        if path == "/events":
            self._handle_sse_stream(parsed)
            return

        # 6. Historical Transaction Report (/reports/<tx_id>)
        if path.startswith("/reports/"):
            tx_id = path[len("/reports/"):]
            report_data = self.server_instance.get_transaction_report(tx_id)
            if report_data:
                self._send_json(report_data)
            else:
                self._send_json({"error": f"Report for transaction '{tx_id}' not found."}, 404)
            return

        self._send_json({"error": f"Unknown endpoint '{path}'"}, 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if not self._check_auth():
            self._send_json({"error": "Unauthorized: invalid or missing auth token"}, 401)
            return

        # Read JSON body
        content_len = int(self.headers.get("Content-Length", 0))
        post_data = {}
        if content_len > 0:
            raw_body = self.rfile.read(content_len).decode("utf-8")
            try:
                post_data = json.loads(raw_body)
            except Exception as e:
                self._send_json({"error": f"Invalid JSON payload: {e}"}, 400)
                return

        # Terminal endpoints (v2.4)
        if path == "/terminal/message":
            if not self.server_instance.terminal_gateway:
                from core.terminal_gateway import TerminalGateway
                self.server_instance.terminal_gateway = TerminalGateway()
            
            resp = self.server_instance.terminal_gateway.handle_client_message(
                json.dumps(post_data),
                auth_token=self.server_instance.auth_token,
            )
            self._send_json(resp, status_code=200)
            return

        # Control endpoints
        if path.startswith("/control/"):
            action = path[len("/control/"):]
            result = self.server_instance.handle_control_action(action, post_data)
            status_code = 200 if result.get("success", True) else 400
            self._send_json(result, status_code=status_code)
            return

        self._send_json({"error": f"Unknown POST endpoint '{path}'"}, 404)

    def _handle_sse_stream(self, parsed: Any) -> None:
        qs = parse_qs(parsed.query)
        last_id = self.headers.get("Last-Event-ID") or qs.get("last_event_id", [None])[0]

        stream = self.server_instance.stream
        client_q, catchup_events = stream.subscribe(last_event_id=last_id)

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            for evt in catchup_events:
                sse_payload = TelemetryStream.format_sse(evt).encode("utf-8")
                self.wfile.write(sse_payload)
                self.wfile.flush()

            while not self.server_instance.is_stopping:
                try:
                    event = client_q.get(timeout=1.0)
                    if event is None:
                        break
                    sse_payload = TelemetryStream.format_sse(event).encode("utf-8")
                    self.wfile.write(sse_payload)
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
        except (ConnectionError, BrokenPipeError, OSError):
            logger.debug("SSE client disconnected.")
        finally:
            stream.unsubscribe(client_q)


class DashboardServer:
    """
    Lightweight, embedded real-time web dashboard server.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8088,
        stream: Optional[TelemetryStream] = None,
        report_dir: Optional[Union[str, Path]] = None,
        auth_token: Optional[str] = None,
        status_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        workers_provider: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        transactions_provider: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        quality_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        control_handler: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
        terminal_gateway: Optional[Any] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.stream = stream or TelemetryStream()
        self.report_dir = Path(report_dir).resolve() if report_dir else None
        self.auth_token = auth_token
        self.status_provider = status_provider
        self.workers_provider = workers_provider
        self.transactions_provider = transactions_provider
        self.quality_provider = quality_provider
        self.control_handler = control_handler
        self.terminal_gateway = terminal_gateway

        self._httpd: Optional[ThreadedHTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self.is_stopping = False
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> None:
        if self._is_running:
            return

        self.is_stopping = False
        self._httpd = ThreadedHTTPServer((self.host, self.port), DashboardRequestHandler)
        self._httpd.dashboard_server = self  # type: ignore

        self.port = self._httpd.server_address[1]

        self._server_thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="AutoDev-DashboardServer",
            daemon=True,
        )
        self._server_thread.start()
        self._is_running = True
        logger.info("DashboardServer listening on http://%s:%d", self.host, self.port)

    def stop(self) -> None:
        if not self._is_running or not self._httpd:
            return

        self.is_stopping = True
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=2.0)
        self._is_running = False
        logger.info("DashboardServer stopped.")

    def get_dashboard_html(self) -> str:
        """Loads dashboard HTML from disk or returns bundled fallback."""
        if DASHBOARD_HTML_PATH.exists():
            try:
                return DASHBOARD_HTML_PATH.read_text(encoding="utf-8")
            except Exception:
                pass
        return "<html><body><h1>AutoDev Dashboard v2.3.0</h1><p>Dashboard ready.</p></body></html>"

    def get_status_snapshot(self) -> Dict[str, Any]:
        if self.status_provider:
            return self.status_provider()
        return {
            "coordinator_health": "HEALTHY",
            "version": "2.3.0",
            "active_transactions": 0,
            "total_workers": 0,
            "running_tasks": 0,
            "recovery_events": 0,
            "policy_denials": 0,
            "buffered_events": self.stream.event_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_workers(self) -> List[Dict[str, Any]]:
        if self.workers_provider:
            return self.workers_provider()
        return []

    def get_transactions(self) -> List[Dict[str, Any]]:
        if self.transactions_provider:
            return self.transactions_provider()
        return []

    def get_quality_snapshot(self) -> Dict[str, Any]:
        if self.quality_provider:
            return self.quality_provider()
        from core.quality_dashboard import QualityDashboardProvider
        provider = QualityDashboardProvider()
        return provider.get_dashboard_payload()

    def handle_control_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # Record audit event
        self.stream.publish(
            TelemetryEvent(
                event_type=f"dashboard.control_action.{action}",
                source_component="DashboardServer",
                severity=TelemetrySeverity.INFO,
                payload={"action": action, "params": params},
            )
        )

        if self.control_handler:
            res = self.control_handler(action, params)
            if "action" not in res:
                res["action"] = action
            return res

        return {"success": True, "action": action, "message": f"Action '{action}' received and logged."}

    def get_transaction_report(self, tx_id: str) -> Optional[Dict[str, Any]]:
        if not self.report_dir or not self.report_dir.exists():
            return None
        report_file = self.report_dir / f"{tx_id}.json"
        if not report_file.exists():
            return None
        try:
            return json.loads(report_file.read_text(encoding="utf-8"))
        except Exception:
            return None
