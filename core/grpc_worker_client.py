"""
grpc_worker_client.py - Remote Worker Client Channel & Execution Agent for AutoDev (v2.3)

Connects to the AutoDev coordinator over mTLS, handles registration, maintains
heartbeat liveness, polls assigned operations, executes them inside sandboxes,
and submits verified task results and artifact metadata.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import socket
import ssl
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from core.certificate_manager import CertificateInfo, CertificateManager
from core.container_runtime import ContainerRuntimeDetector, ContainerRuntimeInfo, ContainerRuntimeType
from core.container_sandbox import ContainerSandbox, ExecutionBackend
from core.remote_worker_transport import TransportConfig, TransportConnectionError, TransportSecurityError
from core.worker_agent import WorkerAgent
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

logger = logging.getLogger("AutoDev.GrpcWorkerClient")


class GrpcWorkerClient:
    """
    Remote worker agent client communicating with coordinator over mTLS.
    """

    def __init__(
        self,
        worker_id: str,
        worker_name: Optional[str] = None,
        workspace_root: Optional[Union[str, Path]] = None,
        coordinator_host: str = "127.0.0.1",
        coordinator_port: int = 50051,
        config: Optional[TransportConfig] = None,
        capabilities: Optional[WorkerCapabilities] = None,
        cert_manager: Optional[CertificateManager] = None,
        certificate_manager: Optional[CertificateManager] = None,
        client_cert_info: Optional[CertificateInfo] = None,
        **kwargs: Any,
    ) -> None:
        self.worker_id = worker_id
        self.worker_name = worker_name or worker_id
        self.workspace_root = Path(workspace_root or "projects").resolve()
        self.config = config or TransportConfig(host=coordinator_host, port=coordinator_port)
        if coordinator_host != "127.0.0.1" or coordinator_port != 50051:
            self.config.host = coordinator_host
            self.config.port = coordinator_port
        self.capabilities = capabilities or WorkerCapabilities()
        self.cert_manager = certificate_manager or cert_manager or CertificateManager()
        self.client_cert_info = client_cert_info

        self._sock: Optional[socket.socket] = None
        self._rfile: Optional[Any] = None
        self._wfile: Optional[Any] = None
        self._req_id = 0
        self._lock = threading.RLock()
        self._is_connected = False
        self._is_running = False
        self._heartbeat_thread: Optional[threading.Thread] = None

        # Sandbox agent for local task execution
        self.worker_agent = WorkerAgent(
            worker_id=self.worker_id,
            workspace_root=self.workspace_root,
        )

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def connect(self) -> bool:
        """Establishes TCP/mTLS connection with coordinator and registers worker."""
        with self._lock:
            if self._is_connected:
                return True

            try:
                raw_sock = socket.create_connection(
                    (self.config.host, self.config.port),
                    timeout=self.config.request_timeout_seconds,
                )

                if self.client_cert_info:
                    ssl_ctx = self.cert_manager.create_client_ssl_context(self.client_cert_info)
                    self._sock = ssl_ctx.wrap_socket(raw_sock, server_hostname="localhost")
                elif self.config.use_tls and self.config.ca_cert_path and self.config.client_cert_path and self.config.client_key_path:
                    ssl_ctx = self.cert_manager.create_client_ssl_context(
                        ca_cert_path=self.config.ca_cert_path,
                        client_cert_path=self.config.client_cert_path,
                        client_key_path=self.config.client_key_path,
                    )
                    self._sock = ssl_ctx.wrap_socket(raw_sock, server_hostname="localhost")
                else:
                    self._sock = raw_sock

                self._rfile = self._sock.makefile("r", encoding="utf-8")
                self._wfile = self._sock.makefile("w", encoding="utf-8")
                self._is_connected = True
                logger.info("Connected to coordinator at %s:%d (mTLS=%s)", self.config.host, self.config.port, bool(self.client_cert_info))
                return True

            except Exception as e:
                logger.error("Failed to connect to coordinator at %s:%d: %s", self.config.host, self.config.port, e)
                self._is_connected = False
                return False

    def disconnect(self) -> None:
        """Closes RPC connection and stops background heartbeat loop."""
        with self._lock:
            self._is_running = False
            self._is_connected = False
            try:
                if self._rfile:
                    self._rfile.close()
                if self._wfile:
                    self._wfile.close()
                if self._sock:
                    self._sock.close()
            except Exception:
                pass
            logger.info("Disconnected from coordinator.")

    def _call_rpc(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sends line-delimited JSON-RPC call and receives response."""
        with self._lock:
            if not self._is_connected and not self.connect():
                raise TransportConnectionError("Not connected to coordinator.")

            self._req_id += 1
            payload = {
                "id": self._req_id,
                "method": method,
                "params": params,
            }

            try:
                self._wfile.write(json.dumps(payload) + "\n")
                self._wfile.flush()

                line = self._rfile.readline()
                if not line:
                    raise TransportConnectionError("Coordinator closed connection.")

                resp = json.loads(line.strip())
                if "error" in resp and resp["error"]:
                    raise TransportSecurityError(resp["error"])
                return resp.get("result", {})

            except Exception as e:
                self.disconnect()
                raise TransportConnectionError(f"RPC call '{method}' failed: {e}") from e

    def register(self) -> WorkerRegistrationResponse:
        """Registers this worker with the coordinator."""
        req = WorkerRegistrationRequest(
            worker_id=self.worker_id,
            worker_name=self.worker_name,
            protocol_version=PROTOCOL_VERSION,
            capabilities=self.capabilities,
        )
        res_data = self._call_rpc("RegisterWorker", req.to_dict())
        return WorkerRegistrationResponse.from_dict(res_data)

    def send_heartbeat(
        self,
        status: WorkerStatus = WorkerStatus.IDLE,
        active_tasks: Optional[List[str]] = None,
    ) -> Any:
        """Sends heartbeat update to coordinator."""
        hb = WorkerHeartbeat(
            worker_id=self.worker_id,
            status=status,
            active_task_ids=active_tasks or [],
            concurrency_used=len(active_tasks or []),
        )
        res_data = self._call_rpc("Heartbeat", hb.to_dict())
        from core.worker_protocol import WorkerHeartbeatResponse
        return WorkerHeartbeatResponse.from_dict(res_data)

    def poll_task(self) -> Optional[TaskAssignmentPayload]:
        """Polls coordinator for assigned tasks."""
        res_data = self._call_rpc("PollTask", {"worker_id": self.worker_id})
        if res_data:
            return TaskAssignmentPayload.from_dict(res_data)
        return None

    def submit_task_result(self, result: TaskResultPayload) -> Dict[str, Any]:
        """Submits executed task result to coordinator."""
        return self._call_rpc("SubmitTaskResult", result.to_dict())

    def execute_and_submit(self, task: TaskAssignmentPayload) -> TaskResultPayload:
        """Executes assigned task using local sandbox worker agent and submits result to coordinator."""
        res_payload = self.worker_agent.execute_assignment(task)
        self.submit_task_result(res_payload)
        return res_payload

    def poll_and_execute_task(self) -> Optional[TaskResultPayload]:
        """Polls for an assigned task, executes it, and submits result if present."""
        task = self.poll_task()
        if task:
            return self.execute_and_submit(task)
        else:
            self.send_heartbeat(status=WorkerStatus.IDLE)
            return None

    def run_worker_loop(self, poll_interval_seconds: float = 1.0) -> None:
        """Main worker daemon polling loop."""
        self._is_running = True
        logger.info("Starting remote worker poll loop for %s", self.worker_id)

        while self._is_running:
            try:
                task = self.poll_task()
                if task:
                    logger.info("Worker %s received task assignment: %s", self.worker_id, task.task_id)
                    # Execute locally via sandbox agent
                    res_payload = self.worker_agent.execute_assignment(task)
                    # Submit results
                    self.submit_task_result(res_payload)
                else:
                    self.send_heartbeat(status=WorkerStatus.IDLE)

                time.sleep(poll_interval_seconds)

            except Exception as e:
                logger.error("Error in worker loop: %s", e)
                time.sleep(poll_interval_seconds * 2)
