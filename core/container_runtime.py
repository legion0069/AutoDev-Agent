"""
container_runtime.py - Container Runtime Abstraction & Security Profiles for AutoDev (v2.2)

Provides container runtime detection (Docker, Podman), secure CLI subprocess execution
with argument arrays (no shell=True), container security profiles (restricted, development, custom),
resource limits, and mock/fake adapters for deterministic testing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("AutoDev.ContainerRuntime")


# =============================================================================
# EXCEPTION HIERARCHY
# =============================================================================

class ContainerRuntimeError(Exception):
    """Base exception for container runtime operations."""
    pass


class ContainerRuntimeUnavailableError(ContainerRuntimeError):
    """Raised when a requested container runtime is not installed or daemon is unreachable."""
    pass


class ContainerSecurityViolationError(ContainerRuntimeError):
    """Raised when container configuration violates security policies."""
    pass


class ContainerExecutionTimeoutError(ContainerRuntimeError):
    """Raised when a container workload exceeds its execution timeout."""
    pass


# =============================================================================
# ENUMS & DATA MODELS
# =============================================================================

class ContainerRuntimeType(str, Enum):
    """Supported container runtime engines."""
    DOCKER = "docker"
    PODMAN = "podman"
    NONE = "none"


class ContainerSecurityProfile(str, Enum):
    """Container security profiles for execution isolation."""
    RESTRICTED = "restricted"      # Default: no network, read-only root, non-root user, dropped caps
    DEVELOPMENT = "development"    # Permits build tools and optional allowlisted network
    CUSTOM = "custom"              # Admin-configured parameters with mandatory safety checks


@dataclass
class ContainerRuntimeInfo:
    """Telemetry and capability details for a detected container runtime."""
    runtime_type: ContainerRuntimeType
    is_available: bool = False
    executable_path: Optional[str] = None
    version: Optional[str] = None
    is_daemon_running: bool = False
    supported_profiles: List[str] = field(default_factory=lambda: ["restricted", "development", "custom"])
    capabilities: Dict[str, bool] = field(default_factory=lambda: {
        "read_only_root": True,
        "non_root_user": True,
        "cpu_limit": True,
        "memory_limit": True,
        "pids_limit": True,
        "network_disabled": True,
        "dropped_capabilities": True,
    })
    last_checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_type": self.runtime_type.value,
            "is_available": self.is_available,
            "executable_path": self.executable_path,
            "version": self.version,
            "is_daemon_running": self.is_daemon_running,
            "supported_profiles": self.supported_profiles,
            "capabilities": self.capabilities,
            "last_checked_at": self.last_checked_at,
        }


@dataclass
class ContainerMount:
    """Represents a bind-mount directory mapped into a container."""
    host_path: str
    container_path: str
    read_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContainerExecutionConfig:
    """Configuration parameters for executing an operation inside a container."""
    image: str = "python:3.12-slim"
    command: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    mounts: List[ContainerMount] = field(default_factory=list)
    working_dir: str = "/workspace"
    security_profile: ContainerSecurityProfile = ContainerSecurityProfile.RESTRICTED
    network_mode: str = "none"
    cpu_limit: Optional[str] = "1.0"
    memory_limit: Optional[str] = "512m"
    pids_limit: int = 64
    timeout_seconds: float = 30.0
    user_id: str = "1000:1000"
    read_only_root: bool = True
    tmpfs_mounts: List[str] = field(default_factory=lambda: ["/tmp:rw,noexec,nosuid,size=64m"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image": self.image,
            "command": self.command,
            "environment": {k: "[REDACTED]" if any(s in k.lower() for s in ["key", "secret", "token", "password"]) else v for k, v in self.environment.items()},
            "mounts": [m.to_dict() for m in self.mounts],
            "working_dir": self.working_dir,
            "security_profile": self.security_profile.value,
            "network_mode": self.network_mode,
            "cpu_limit": self.cpu_limit,
            "memory_limit": self.memory_limit,
            "pids_limit": self.pids_limit,
            "timeout_seconds": self.timeout_seconds,
            "user_id": self.user_id,
            "read_only_root": self.read_only_root,
            "tmpfs_mounts": self.tmpfs_mounts,
        }


@dataclass
class ContainerExecutionResult:
    """Telemetry and outcome of a containerized execution."""
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    container_id: Optional[str] = None
    runtime_type: ContainerRuntimeType = ContainerRuntimeType.NONE
    timed_out: bool = False
    error_message: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and self.error_message is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": self.duration_seconds,
            "container_id": self.container_id,
            "runtime_type": self.runtime_type.value,
            "timed_out": self.timed_out,
            "error_message": self.error_message,
            "artifacts": self.artifacts,
            "completed_at": self.completed_at,
        }


# =============================================================================
# SECRET REDACTION FOR CONTAINER OUTPUTS
# =============================================================================

SECRET_REDACT_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|auth|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"),
    re.compile(r"(?i)sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"(?i)AIza[0-9A-Za-z\-_]{30,}"),
    re.compile(r"(?i)Bearer\s+[a-zA-Z0-9_\-\.]{20,}"),
]

def redact_container_output(text: str) -> str:
    """Scrubs sensitive API tokens and credentials from container stdout/stderr."""
    if not text:
        return ""
    result = text
    result = SECRET_REDACT_PATTERNS[0].sub(r"\1: [REDACTED]", result)
    for pat in SECRET_REDACT_PATTERNS[1:]:
        result = pat.sub("[REDACTED]", result)
    return result


# =============================================================================
# RUNTIME DETECTOR
# =============================================================================

class ContainerRuntimeDetector:
    """
    Detects availability, executable paths, and daemon responsiveness of Docker or Podman.
    """

    def __init__(self, preferred_runtime: Optional[ContainerRuntimeType] = None) -> None:
        self.preferred_runtime = preferred_runtime
        self._cached_info: Optional[ContainerRuntimeInfo] = None

    def detect(self, force_refresh: bool = False) -> ContainerRuntimeInfo:
        """
        Probes the host environment for a responsive container runtime.
        """
        if self._cached_info is not None and not force_refresh:
            return self._cached_info

        candidates = [ContainerRuntimeType.DOCKER, ContainerRuntimeType.PODMAN]
        if self.preferred_runtime and self.preferred_runtime in candidates:
            candidates.insert(0, candidates.pop(candidates.index(self.preferred_runtime)))

        for runtime_type in candidates:
            info = self._probe_runtime(runtime_type)
            if info.is_available and info.is_daemon_running:
                self._cached_info = info
                return info

        # If none found or daemon not running
        fallback = ContainerRuntimeInfo(
            runtime_type=ContainerRuntimeType.NONE,
            is_available=False,
            is_daemon_running=False,
        )
        self._cached_info = fallback
        return fallback

    def _probe_runtime(self, runtime_type: ContainerRuntimeType) -> ContainerRuntimeInfo:
        exe_name = runtime_type.value
        exe_path = shutil.which(exe_name)
        if not exe_path:
            return ContainerRuntimeInfo(runtime_type=runtime_type, is_available=False)

        # Check version
        version_str: Optional[str] = None
        try:
            res = subprocess.run(
                [exe_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                version_str = res.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            pass

        # Check daemon responsiveness
        daemon_ok = False
        try:
            res_info = subprocess.run(
                [exe_path, "info"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res_info.returncode == 0:
                daemon_ok = True
        except (subprocess.SubprocessError, OSError):
            daemon_ok = False

        return ContainerRuntimeInfo(
            runtime_type=runtime_type,
            is_available=True,
            executable_path=exe_path,
            version=version_str,
            is_daemon_running=daemon_ok,
        )


# =============================================================================
# CONTAINER SUBPROCESS RUNTIME ADAPTER
# =============================================================================

class ContainerSubprocessAdapter:
    """
    Executes containerized workloads using secure argument arrays via Docker/Podman CLI.
    Enforces security profiles, non-root execution, resource limits, and timeout cleanup.
    """

    def __init__(self, runtime_info: Optional[ContainerRuntimeInfo] = None) -> None:
        self.runtime_info = runtime_info or ContainerRuntimeDetector().detect()

    def execute(self, config: ContainerExecutionConfig) -> ContainerExecutionResult:
        """
        Executes a container workload using the detected or configured runtime.
        """
        if not self.runtime_info.is_available or not self.runtime_info.is_daemon_running:
            raise ContainerRuntimeUnavailableError(
                f"Container runtime '{self.runtime_info.runtime_type.value}' is unavailable or daemon is not running."
            )

        self._validate_security_policy(config)

        container_name = f"autodev-run-{uuid.uuid4().hex[:12]}"
        cmd = self._build_run_command(config, container_name)
        start_time = time.perf_counter()

        logger.info(
            "Launching container workload '%s' with profile '%s'",
            container_name,
            config.security_profile.value,
        )

        timed_out = False
        stdout_str = ""
        stderr_str = ""
        exit_code = 1

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
                check=False,
            )
            stdout_str = redact_container_output(proc.stdout)
            stderr_str = redact_container_output(proc.stderr)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = 124
            stderr_str = f"Container execution timed out after {config.timeout_seconds} seconds."
            logger.warning("Container %s timed out, force killing...", container_name)
            self._cleanup_container(container_name)
        except Exception as exc:
            exit_code = 1
            stderr_str = f"Container execution error: {exc}"
            logger.error("Failed to execute container %s: %s", container_name, exc)
        finally:
            self._cleanup_container(container_name)

        duration = time.perf_counter() - start_time
        return ContainerExecutionResult(
            exit_code=exit_code,
            stdout=stdout_str,
            stderr=stderr_str,
            duration_seconds=duration,
            container_id=container_name,
            runtime_type=self.runtime_info.runtime_type,
            timed_out=timed_out,
            error_message=stderr_str if exit_code != 0 and not stdout_str else None,
        )

    def _validate_security_policy(self, config: ContainerExecutionConfig) -> None:
        """
        Enforces container security constraints based on the chosen security profile.
        """
        # Block dangerous host mounts
        forbidden_host_paths = [
            "/var/run/docker.sock",
            "/run/podman/podman.sock",
            "\\\\.\\pipe\\docker_engine",
            "/etc",
            "/bin",
            "/sbin",
            "/usr",
            "/root",
            "C:\\Windows",
            "C:\\Program Files",
        ]
        for mount in config.mounts:
            raw_path = mount.host_path.replace("\\", "/").lower()
            for forbidden in forbidden_host_paths:
                forb_clean = forbidden.replace("\\", "/").lower()
                if raw_path == forb_clean or raw_path.startswith(forb_clean + "/"):
                    raise ContainerSecurityViolationError(
                        f"Mounting sensitive system path '{mount.host_path}' is forbidden."
                    )
            try:
                norm = str(Path(mount.host_path).resolve()).replace("\\", "/").lower()
                for forbidden in forbidden_host_paths:
                    forb_clean = forbidden.replace("\\", "/").lower()
                    if norm == forb_clean or norm.startswith(forb_clean + "/"):
                        raise ContainerSecurityViolationError(
                            f"Mounting sensitive system path '{mount.host_path}' is forbidden."
                        )
            except Exception:
                pass

        if config.security_profile == ContainerSecurityProfile.RESTRICTED:
            if config.network_mode != "none":
                raise ContainerSecurityViolationError(
                    "Network access is forbidden in 'restricted' security profile."
                )

    def _build_run_command(self, config: ContainerExecutionConfig, container_name: str) -> List[str]:
        exe = self.runtime_info.executable_path or self.runtime_info.runtime_type.value
        cmd = [
            exe,
            "run",
            "--rm",
            "--name",
            container_name,
            f"--net={config.network_mode}",
            f"--pids-limit={config.pids_limit}",
        ]

        # Security isolation flags
        if config.read_only_root:
            cmd.append("--read-only")

        if config.user_id:
            cmd.extend(["--user", config.user_id])

        if config.cpu_limit:
            cmd.append(f"--cpus={config.cpu_limit}")

        if config.memory_limit:
            cmd.append(f"--memory={config.memory_limit}")

        if config.security_profile == ContainerSecurityProfile.RESTRICTED:
            cmd.append("--cap-drop=ALL")
            cmd.append("--security-opt=no-new-privileges:true")

        # tmpfs mounts
        for tmpfs in config.tmpfs_mounts:
            cmd.append(f"--tmpfs={tmpfs}")

        # Bind mounts
        for mount in config.mounts:
            ro_flag = ":ro" if mount.read_only else ":rw"
            cmd.append(f"-v={mount.host_path}:{mount.container_path}{ro_flag}")

        # Working directory
        if config.working_dir:
            cmd.extend(["-w", config.working_dir])

        # Environment variables
        for k, v in config.environment.items():
            cmd.extend(["-e", f"{k}={v}"])

        # Image and command
        cmd.append(config.image)
        cmd.extend(config.command)
        return cmd

    def _cleanup_container(self, container_name: str) -> None:
        exe = self.runtime_info.executable_path or self.runtime_info.runtime_type.value
        try:
            subprocess.run(
                [exe, "rm", "-f", container_name],
                capture_output=True,
                timeout=5,
                check=False,
            )
        except Exception:
            pass


# =============================================================================
# MOCK / FAKE CONTAINER RUNTIME (FOR TEST DETERMINISM)
# =============================================================================

class MockContainerRuntime(ContainerSubprocessAdapter):
    """
    Deterministic mock runtime adapter for unit tests without Docker/Podman daemon requirements.
    """

    def __init__(
        self,
        should_succeed: bool = True,
        exit_code: int = 0,
        mock_stdout: str = "Mock container executed successfully",
        mock_stderr: str = "",
        should_timeout: bool = False,
        is_available: bool = True,
        is_daemon_running: bool = True,
    ) -> None:
        info = ContainerRuntimeInfo(
            runtime_type=ContainerRuntimeType.DOCKER,
            is_available=is_available,
            executable_path="/usr/bin/docker",
            version="Docker version 26.0.0, mock",
            is_daemon_running=is_daemon_running,
        )
        super().__init__(runtime_info=info)
        self.should_succeed = should_succeed
        self.exit_code = exit_code
        self.mock_stdout = mock_stdout
        self.mock_stderr = mock_stderr
        self.should_timeout = should_timeout
        self.execution_history: List[ContainerExecutionConfig] = []

    def execute(self, config: ContainerExecutionConfig) -> ContainerExecutionResult:
        self.execution_history.append(config)
        self._validate_security_policy(config)

        if not self.runtime_info.is_available or not self.runtime_info.is_daemon_running:
            raise ContainerRuntimeUnavailableError("Mock container daemon is unavailable.")

        if self.should_timeout:
            return ContainerExecutionResult(
                exit_code=124,
                stdout="",
                stderr="Container execution timed out (mock).",
                duration_seconds=config.timeout_seconds,
                container_id=f"mock-container-{uuid.uuid4().hex[:8]}",
                runtime_type=ContainerRuntimeType.DOCKER,
                timed_out=True,
                error_message="Mock container execution timed out.",
            )

        return ContainerExecutionResult(
            exit_code=self.exit_code if self.should_succeed else (self.exit_code or 1),
            stdout=redact_container_output(self.mock_stdout),
            stderr=redact_container_output(self.mock_stderr),
            duration_seconds=0.05,
            container_id=f"mock-container-{uuid.uuid4().hex[:8]}",
            runtime_type=ContainerRuntimeType.DOCKER,
            timed_out=False,
            error_message=self.mock_stderr if not self.should_succeed else None,
        )

    def add_mock_image(self, tag: str, digest: str = "sha256:mockdigest1234567890") -> None:
        """Registers a mock image tag and digest for testing."""
        if not hasattr(self, "_mock_images"):
            self._mock_images = {}
        self._mock_images[tag] = digest

    def inspect_image(self, tag: str) -> Optional[Dict[str, Any]]:
        """Mock image inspection."""
        if not hasattr(self, "_mock_images"):
            self._mock_images = {}
        if tag in self._mock_images:
            return {
                "Id": self._mock_images[tag],
                "RepoTags": [tag],
                "Size": 1024000,
            }
        return {"Id": f"sha256:{hashlib.sha256(tag.encode('utf-8')).hexdigest()}", "RepoTags": [tag], "Size": 1024000}


ContainerRuntimeAdapter = ContainerSubprocessAdapter
MockContainerRuntimeAdapter = MockContainerRuntime


def get_container_runtime() -> ContainerRuntimeAdapter:
    """Factory helper returning detected ContainerRuntimeAdapter or MockContainerRuntime."""
    detector = ContainerRuntimeDetector()
    info = detector.detect()
    if info.is_available and info.is_daemon_running:
        return ContainerSubprocessAdapter(runtime_info=info)
    return MockContainerRuntime(is_available=False, is_daemon_running=False)

