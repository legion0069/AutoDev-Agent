"""
grpc_worker_server.py - Coordinator-Side RPC/mTLS Server for Remote Workers (v2.3)

Listens for remote worker connections, enforces mutual TLS certificate validation,
manages worker registrations, dispatches task assignments, receives heartbeats,
and accepts task results and artifact submissions.
"""

from __future__ import annotations

import json
import logging
import queue
import socket
import ssl
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from core.certificate_manager import CertificateInfo, CertificateManager
from core.remote_worker_transport import TransportConfig, TransportError, TransportSecurityError
from core.task_lease_manager import TaskLeaseManager
from core.worker_auth import (
    AuthenticatedWorkerIdentity,
    WorkerAuthorizer,
    WorkerAuthenticationError,
    WorkerAuthorizationError,
)
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
from core.worker_registry import IncompatibleProtocolError, UnauthorizedWorkerError, WorkerRegistry

logger = logging.getLogger("AutoDev.GrpcWorkerServer")


class GrpcWorkerServer:
    """
    Coordinator-side RPC server handling remote worker connections over TLS/mTLS.
    """

    def __init__(
        self,
        registry: Optional[WorkerRegistry] = None,
        lease_manager: Optional[TaskLeaseManager] = None,
        config: Optional[TransportConfig] = None,
        authorizer: Optional[WorkerAuthorizer] = None,
        cert_manager: Optional[CertificateManager] = None,
        certificate_manager: Optional[CertificateManager] = None,
        server_cert_info: Optional[CertificateInfo] = None,
        host: str = "127.0.0.1",
        port: int = 50051,
        require_client_cert: bool = True,
        **kwargs: Any,
    ) -> None:
        self.registry = registry or WorkerRegistry()
        self.lease_manager = lease_manager or TaskLeaseManager()
        self.config = config or TransportConfig(host=host, port=port)
        if host != "127.0.0.1" or port != 50051:
            self.config.host = host
            self.config.port = port
        self.authorizer = authorizer or WorkerAuthorizer()
        self.cert_manager = certificate_manager or cert_manager or CertificateManager()
        self.server_cert_info = server_cert_info
        self.require_client_cert = require_client_cert

        self._server_sock: Optional[socket.socket] = None
        self._server_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._stopping = False
        self._lock = threading.RLock()

        # Task assignment queues per worker
        self._pending_tasks: Dict[str, queue.Queue[TaskAssignmentPayload]] = {}
        # Task results received
        self._results_received: Dict[str, TaskResultPayload] = {}
        # Authenticated identities per worker_id
        self._authenticated_identities: Dict[str, AuthenticatedWorkerIdentity] = {}

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def port(self) -> int:
        return self.config.port

    def start(self) -> None:
        """Starts the RPC/mTLS listener on a background thread."""
        if self._is_running:
            return

        self._stopping = False
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        raw_sock.bind((self.config.host, self.config.port))
        raw_sock.listen(128)

        self.config.port = raw_sock.getsockname()[1]
        self._server_sock = raw_sock

        self._server_thread = threading.Thread(
            target=self._listen_loop,
            name="AutoDev-WorkerServer",
            daemon=True,
        )
        self._server_thread.start()
        self._is_running = True
        logger.info("GrpcWorkerServer listening on %s:%d (mTLS=%s)", self.config.host, self.config.port, bool(self.server_cert_info))

    def stop(self) -> None:
        """Gracefully shuts down the RPC server."""
        if not self._is_running:
            return

        self._stopping = True
        self._is_running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=2.0)
        logger.info("GrpcWorkerServer stopped.")

    def queue_task_for_worker(self, worker_id: str, assignment: TaskAssignmentPayload) -> None:
        """Queues a task assignment for the specified worker to poll."""
        with self._lock:
            if worker_id not in self._pending_tasks:
                self._pending_tasks[worker_id] = queue.Queue()
            self._pending_tasks[worker_id].put(assignment)
            logger.info("Queued task %s for remote worker %s", assignment.task_id, worker_id)

    def get_result_for_task(self, task_id: str) -> Optional[TaskResultPayload]:
        """Returns received task result if available."""
        with self._lock:
            return self._results_received.get(task_id)

    def _listen_loop(self) -> None:
        """Accepts incoming TCP/TLS connections and spawns worker client handlers."""
        ssl_ctx: Optional[ssl.SSLContext] = None
        if self.server_cert_info:
            ssl_ctx = self.cert_manager.create_server_ssl_context(
                server_info_or_ca_path=self.server_cert_info,
                require_client_cert=self.require_client_cert,
            )
        elif self.config.use_tls and self.config.ca_cert_path and self.config.server_cert_path and self.config.server_key_path:
            ssl_ctx = self.cert_manager.create_server_ssl_context(
                server_info_or_ca_path=self.config.ca_cert_path,
                server_cert_path=self.config.server_cert_path,
                server_key_path=self.config.server_key_path,
                require_client_cert=self.require_client_cert,
            )

        while not self._stopping:
            try:
                client_sock, addr = self._server_sock.accept()
                if self._stopping:
                    client_sock.close()
                    break

                conn_sock = client_sock
                peer_cert: Optional[Dict[str, Any]] = None
                if ssl_ctx:
                    try:
                        conn_sock = ssl_ctx.wrap_socket(client_sock, server_side=True)
                        peer_cert = conn_sock.getpeercert()
                    except Exception as e:
                        logger.warning("mTLS Handshake failed from %s: %s", addr, e)
                        client_sock.close()
                        continue

                handler = threading.Thread(
                    target=self._handle_client_connection,
                    args=(conn_sock, addr, peer_cert),
                    daemon=True,
                )
                handler.start()

            except (socket.error, OSError):
                break

    def _handle_client_connection(
        self,
        sock: socket.socket,
        addr: Tuple[str, int],
        peer_cert: Optional[Dict[str, Any]],
    ) -> None:
        """Processes line-delimited JSON-RPC messages from a connected worker."""
        rfile = sock.makefile("r", encoding="utf-8")
        wfile = sock.makefile("w", encoding="utf-8")
        worker_id: Optional[str] = None

        try:
            for line in rfile:
                if self._stopping:
                    break
                line = line.strip()
                if not line:
                    continue

                try:
                    req = json.loads(line)
                except Exception as e:
                    self._send_rpc_response(wfile, {"error": f"Invalid JSON: {e}"})
                    continue

                method = req.get("method")
                params = req.get("params", {})
                req_id = req.get("id")

                resp_data: Dict[str, Any] = {"id": req_id}

                # 1. Register Worker
                if method == "RegisterWorker":
                    reg_req = WorkerRegistrationRequest.from_dict(params)
                    # Bind certificate identity
                    cert_cn = ""
                    cert_fp = ""
                    if peer_cert:
                        subject = dict(x[0] for x in peer_cert.get("subject", ()))
                        cert_cn = subject.get("commonName", "")

                    identity = AuthenticatedWorkerIdentity(
                        worker_id=reg_req.worker_id,
                        common_name=cert_cn or reg_req.worker_id,
                        certificate_fingerprint=cert_fp,
                        authenticated_via="mTLS" if peer_cert else "PLAINTEXT",
                    )
                    try:
                        self.authorizer.authorize_registration(identity)
                        reg_resp = self.registry.register_worker(reg_req)
                        with self._lock:
                            worker_id = reg_req.worker_id
                            self._authenticated_identities[worker_id] = identity
                            if worker_id not in self._pending_tasks:
                                self._pending_tasks[worker_id] = queue.Queue()
                        resp_data["result"] = reg_resp.to_dict()
                    except Exception as exc:
                        resp_data["error"] = str(exc)

                # 2. Heartbeat
                elif method == "Heartbeat":
                    hb = WorkerHeartbeat.from_dict(params)
                    try:
                        resp = self.registry.record_heartbeat(hb)
                        resp_data["result"] = resp.to_dict()
                    except Exception as exc:
                        resp_data["error"] = str(exc)

                # 3. Poll Assignment
                elif method == "PollTask":
                    w_id = params.get("worker_id", worker_id)
                    assignment: Optional[TaskAssignmentPayload] = None
                    with self._lock:
                        if w_id and w_id in self._pending_tasks:
                            try:
                                assignment = self._pending_tasks[w_id].get_nowait()
                            except queue.Empty:
                                assignment = None
                    resp_data["result"] = assignment.to_dict() if assignment else None

                # 4. Submit Task Result
                elif method == "SubmitTaskResult":
                    res_payload = TaskResultPayload.from_dict(params)
                    task_id = res_payload.task_id
                    with self._lock:
                        self._results_received[task_id] = res_payload
                    resp_data["result"] = {"success": True, "task_id": task_id}

                # Unknown method
                else:
                    resp_data["error"] = f"Unknown method '{method}'"

                self._send_rpc_response(wfile, resp_data)

        except (ConnectionResetError, BrokenPipeError, socket.error):
            pass
        finally:
            if worker_id:
                logger.info("Remote worker %s disconnected from %s", worker_id, addr)
            try:
                rfile.close()
                wfile.close()
                sock.close()
            except Exception:
                pass

    def _send_rpc_response(self, wfile: Any, response: Dict[str, Any]) -> None:
        try:
            wfile.write(json.dumps(response) + "\n")
            wfile.flush()
        except Exception:
            pass
