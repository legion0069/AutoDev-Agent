"""
container_sandbox.py - Containerized Execution Sandbox for AutoDev (v2.2)

Integrates container runtime isolation with Version 2.1 ExecutionSandbox.
Enforces fail-closed isolation policies, workspace mounts, and backend routing.
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from core.container_runtime import (
    ContainerExecutionConfig,
    ContainerExecutionResult,
    ContainerMount,
    ContainerRuntimeDetector,
    ContainerRuntimeError,
    ContainerRuntimeInfo,
    ContainerRuntimeType,
    ContainerRuntimeUnavailableError,
    ContainerSecurityProfile,
    ContainerSecurityViolationError,
    ContainerSubprocessAdapter,
    MockContainerRuntime,
)
from core.execution_sandbox import (
    CommandResult,
    ExecutionSandbox,
    PathContainmentError,
    ProtectedPathViolationError,
    SandboxSecurityError,
)

logger = logging.getLogger("AutoDev.ContainerSandbox")


class ExecutionBackend(str, Enum):
    """Execution backend options for operations and validation commands."""
    PROCESS = "process"        # Host process-level sandbox
    CONTAINER = "container"    # Docker or Podman container sandbox
    AUTO = "auto"              # Uses container if available, falls back to process unless container required


class ContainerSandbox(ExecutionSandbox):
    """
    Extends ExecutionSandbox with container isolation and backend management.
    """

    def __init__(
        self,
        workspace_root: Union[str, Path] = "projects",
        backend: ExecutionBackend = ExecutionBackend.AUTO,
        security_profile: ContainerSecurityProfile = ContainerSecurityProfile.RESTRICTED,
        container_runtime: Optional[ContainerSubprocessAdapter] = None,
        default_image: str = "python:3.12-slim",
    ) -> None:
        super().__init__(workspace_root=workspace_root)
        self.backend = backend
        self.security_profile = security_profile
        self.default_image = default_image
        self.runtime_adapter = container_runtime or ContainerSubprocessAdapter()
        self.detector = ContainerRuntimeDetector()

    @property
    def is_container_available(self) -> bool:
        """Returns True if a responsive Docker or Podman daemon is available."""
        info = self.runtime_adapter.runtime_info
        return bool(info and info.is_available and info.is_daemon_running)

    def execute_in_sandbox(
        self,
        args: List[str],
        cwd: Optional[Union[str, Path]] = None,
        timeout: float = 30.0,
        env: Optional[Dict[str, str]] = None,
        require_container: bool = False,
        read_only_workspace: bool = False,
    ) -> CommandResult:
        """
        Executes a command within either a container sandbox or local process sandbox
        based on configured backend and required isolation.
        """
        # Determine actual backend
        use_container = False
        if self.backend == ExecutionBackend.CONTAINER or require_container:
            if not self.is_container_available:
                raise ContainerRuntimeUnavailableError(
                    "Container isolation was required for this operation, but no healthy Docker/Podman runtime was detected. Failing closed."
                )
            use_container = True
        elif self.backend == ExecutionBackend.AUTO:
            use_container = self.is_container_available

        if use_container:
            return self._run_in_container(
                args=args,
                cwd=cwd,
                timeout=timeout,
                env=env,
                read_only_workspace=read_only_workspace,
            )
        else:
            return self.run_command(
                command=args,
                cwd=cwd,
                timeout_seconds=timeout,
                env_override=env,
            )

    def _run_in_container(
        self,
        args: List[str],
        cwd: Optional[Union[str, Path]] = None,
        timeout: float = 30.0,
        env: Optional[Dict[str, str]] = None,
        read_only_workspace: bool = False,
    ) -> CommandResult:
        """Runs the command inside a container sandbox."""
        work_dir_host = (cwd or self.workspace_root)
        try:
            work_dir_resolved = self.validate_path(str(work_dir_host), is_write=not read_only_workspace)
        except Exception:
            work_dir_resolved = Path(work_dir_host).resolve()

        mount = ContainerMount(
            host_path=str(self.workspace_root),
            container_path="/workspace",
            read_only=read_only_workspace,
        )

        config = ContainerExecutionConfig(
            image=self.default_image,
            command=args,
            environment=env or {},
            mounts=[mount],
            working_dir="/workspace",
            security_profile=self.security_profile,
            network_mode="none" if self.security_profile == ContainerSecurityProfile.RESTRICTED else "bridge",
            timeout_seconds=timeout,
        )

        result: ContainerExecutionResult = self.runtime_adapter.execute(config)

        return CommandResult(
            command=args,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_seconds=result.duration_seconds,
            timed_out=result.timed_out,
        )
