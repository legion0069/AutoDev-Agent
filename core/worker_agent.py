"""
worker_agent.py - Distributed Worker Execution Agent for AutoDev (v2.2)

Executes assigned change operations locally or in container sandboxes.
Captures generated artifacts, enforces path containment, and returns validated TaskResultPayloads.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.container_sandbox import ContainerSandbox, ExecutionBackend
from core.execution_sandbox import (
    ExecutionSandbox,
    PathContainmentError,
    ProtectedPathViolationError,
    SandboxSecurityError,
)
from core.worker_protocol import (
    TaskAssignmentPayload,
    TaskResultPayload,
    WorkerCapabilities,
    WorkerHeartbeat,
    WorkerRegistrationRequest,
    WorkerStatus,
)

logger = logging.getLogger("AutoDev.WorkerAgent")


class WorkerAgent:
    """
    Worker execution agent that processes TaskAssignmentPayloads securely within a sandbox.
    """

    def __init__(
        self,
        worker_id: str,
        workspace_root: Union[str, Path] = "projects",
        capabilities: Optional[WorkerCapabilities] = None,
        sandbox: Optional[ExecutionSandbox] = None,
    ) -> None:
        self.worker_id = worker_id
        self.workspace_root = Path(workspace_root).resolve()
        self.capabilities = capabilities or WorkerCapabilities()
        self.sandbox = sandbox or ExecutionSandbox(workspace_root=self.workspace_root)
        self.status = WorkerStatus.IDLE

    def create_registration_request(self, auth_token: Optional[str] = None) -> WorkerRegistrationRequest:
        """Constructs registration payload to connect to coordinator."""
        return WorkerRegistrationRequest(
            worker_id=self.worker_id,
            worker_name=f"AgentWorker-{self.worker_id}",
            capabilities=self.capabilities,
            auth_token=auth_token,
        )

    def generate_heartbeat(self, current_load: int = 0, active_tasks: Optional[List[str]] = None) -> WorkerHeartbeat:
        """Produces a periodic heartbeat payload."""
        return WorkerHeartbeat(
            worker_id=self.worker_id,
            status=self.status,
            current_load=current_load,
            active_tasks=active_tasks or [],
        )

    def execute_assignment(self, assignment: TaskAssignmentPayload) -> TaskResultPayload:
        """
        Executes a single assigned change operation within the sandbox.
        """
        start_time = time.perf_counter()
        self.status = WorkerStatus.BUSY

        modified_files: List[str] = []
        created_files: List[str] = []
        deleted_files: List[str] = []
        errors: List[str] = []
        artifacts: List[Dict[str, Any]] = []

        try:
            target_rel = assignment.target_file
            op_type = assignment.operation_type.upper()

            if op_type in {"CREATE", "CREATE_FILE"}:
                target_path = self.sandbox.validate_path(target_rel, is_write=True)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(assignment.target_content or "", encoding="utf-8")
                created_files.append(target_rel)

            elif op_type in {"MODIFY", "MODIFY_FILE"}:
                target_path = self.sandbox.validate_path(target_rel, is_write=True)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(assignment.target_content or "", encoding="utf-8")
                modified_files.append(target_rel)

            elif op_type in {"DELETE", "DELETE_FILE"}:
                target_path = self.sandbox.validate_path(target_rel, is_delete=True)
                if target_path.exists() and target_path.is_file():
                    target_path.unlink()
                    deleted_files.append(target_rel)

            else:
                raise ValueError(f"Unsupported operation type '{assignment.operation_type}'")

            success = True
            error_type = None
            error_message = None

        except (PathContainmentError, ProtectedPathViolationError, SandboxSecurityError) as p_err:
            success = False
            error_type = type(p_err).__name__
            error_message = str(p_err)
            errors.append(error_message)

        except Exception as exc:
            success = False
            error_type = type(exc).__name__
            error_message = str(exc)
            errors.append(error_message)

        finally:
            self.status = WorkerStatus.IDLE

        duration = time.perf_counter() - start_time
        return TaskResultPayload(
            task_id=assignment.task_id,
            operation_id=assignment.operation_id,
            transaction_id=assignment.transaction_id,
            worker_id=self.worker_id,
            lease_token=assignment.lease_token,
            success=success,
            modified_files=modified_files,
            created_files=created_files,
            deleted_files=deleted_files,
            artifacts=artifacts,
            duration_seconds=duration,
            error_type=error_type,
            error_message=error_message,
        )
