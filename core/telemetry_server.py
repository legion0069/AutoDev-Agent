"""
telemetry_server.py - Lightweight Live Telemetry & SSE Streaming Server for AutoDev (v2.2)

Provides an embeddable HTTP server exposing live SSE event streaming, health probes,
worker status, and historical transaction reports on localhost.
"""

from __future__ import annotations

import json
import logging
import queue
import socket
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, Callable, Dict, List, Optional, Set, Union
from urllib.parse import parse_qs, urlparse

from core.telemetry_models import TelemetryEvent, TelemetrySnapshot
from core.telemetry_stream import TelemetryStream

logger = logging.getLogger("AutoDev.TelemetryServer")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server allowing concurrent SSE streams and REST requests."""
    daemon_threads = True
    allow_reuse_address = True


class TelemetryRequestHandler(BaseHTTPRequestHandler):
    """
    Handles telemetry REST queries and persistent SSE streaming connections.
    """

    def log_message(self, format: str, *args: Any) -> None:
        # Route to module logger rather than stderr
        logger.debug(format, *args)

    @property
    def server_instance(self) -> TelemetryServer:
        return self.server.telemetry_server  # type: ignore

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

    def _send_json_response(self, data: Dict[str, Any], status_code: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Processes GET requests for health, status, reports, and live SSE events."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if not path:
            path = "/"

        if not self._check_auth():
            self._send_json_response({"error": "Unauthorized: invalid or missing auth token"}, 401)
            return

        # 1. Health Probe
        if path == "/health":
            self._send_json_response({
                "status": "HEALTHY",
                "version": "2.2.0",
                "timestamp": time.time(),
            })
            return

        # 2. System Status & Summary Snapshot
        if path == "/status":
            snapshot = self.server_instance.get_status_snapshot()
            self._send_json_response(snapshot)
            return

        # 3. Live SSE Stream (/events)
        if path == "/events":
            self._handle_sse_stream(parsed)
            return

        # 4. Historical Transaction Report (/reports/<tx_id>)
        if path.startswith("/reports/"):
            tx_id = path[len("/reports/"):]
            report_data = self.server_instance.get_transaction_report(tx_id)
            if report_data:
                self._send_json_response(report_data)
            else:
                self._send_json_response({"error": f"Report for transaction '{tx_id}' not found."}, 404)
            return

        # Default Not Found
        self._send_json_response({"error": f"Unknown endpoint '{path}'"}, 404)

    def _handle_sse_stream(self, parsed: Any) -> None:
        """Streams Server-Sent Events to the client until disconnected."""
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
            # Replay catchup events
            for evt in catchup_events:
                sse_payload = TelemetryStream.format_sse(evt).encode("utf-8")
                self.wfile.write(sse_payload)
                self.wfile.flush()

            # Stream live events
            while not self.server_instance.is_stopping:
                try:
                    event = client_q.get(timeout=1.0)
                    if event is None:
                        break
                    sse_payload = TelemetryStream.format_sse(event).encode("utf-8")
                    self.wfile.write(sse_payload)
                    self.wfile.flush()
                except queue.Empty:
                    # Heartbeat comment to keep connection alive
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
        except (ConnectionError, BrokenPipeError, OSError):
            logger.debug("SSE client disconnected.")
        finally:
            stream.unsubscribe(client_q)


class TelemetryServer:
    """
    Lightweight, embedded HTTP server for streaming execution telemetry and metrics.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8088,
        stream: Optional[TelemetryStream] = None,
        report_dir: Optional[Union[str, Path]] = None,
        auth_token: Optional[str] = None,
        snapshot_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.stream = stream or TelemetryStream()
        self.report_dir = Path(report_dir).resolve() if report_dir else None
        self.auth_token = auth_token
        self.snapshot_provider = snapshot_provider

        self._httpd: Optional[ThreadedHTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self.is_stopping = False
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> None:
        """Starts the HTTP server on a background thread."""
        if self._is_running:
            return

        self.is_stopping = False
        self._httpd = ThreadedHTTPServer((self.host, self.port), TelemetryRequestHandler)
        self._httpd.telemetry_server = self  # type: ignore

        # Resolve assigned port if dynamic port 0 was passed
        self.port = self._httpd.server_address[1]

        self._server_thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="AutoDev-TelemetryServer",
            daemon=True,
        )
        self._server_thread.start()
        self._is_running = True
        logger.info("TelemetryServer listening on http://%s:%d", self.host, self.port)

    def stop(self) -> None:
        """Gracefully shuts down the HTTP server."""
        if not self._is_running or not self._httpd:
            return

        self.is_stopping = True
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=2.0)
        self._is_running = False
        logger.info("TelemetryServer stopped.")

    def get_status_snapshot(self) -> Dict[str, Any]:
        """Gathers aggregated system status."""
        if self.snapshot_provider:
            return self.snapshot_provider()
        return {
            "coordinator_status": "RUNNING",
            "buffered_events_count": self.stream.event_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_transaction_report(self, tx_id: str) -> Optional[Dict[str, Any]]:
        """Loads transaction report JSON from disk if available."""
        if not self.report_dir or not self.report_dir.exists():
            return None
        report_file = self.report_dir / f"{tx_id}.json"
        if not report_file.exists():
            return None
        try:
            return json.loads(report_file.read_text(encoding="utf-8"))
        except Exception:
            return None
