"""
AutoDev Version 2.5 - Runtime Execution Isolation Provider Abstraction.

Defines pluggable isolation backends, security profiles (development, standard, strict, untrusted_code),
OS-enforced sandbox policies, capability inspection, and fail-closed isolation violations.
"""

from __future__ import annotations

import abc
import os
import sys
import time
import uuid
import logging
import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("AutoDev.IsolationProvider")


# =====================================================================
# Isolation Exceptions
# =====================================================================

class IsolationError(Exception):
    """Base exception for runtime isolation errors."""
    pass


class IsolationUnavailableError(IsolationError):
    """Raised when a requested isolation backend or required security feature is unavailable."""
    pass


class IsolationViolationError(IsolationError):
    """Raised when a sandbox process violates runtime security policy (e.g. prohibited path/command)."""
    pass


class IsolationCapabilityMismatchError(IsolationError):
    """Raised when the host platform cannot satisfy the required security capabilities."""
    pass


# =====================================================================
# Isolation Data Contracts & Profiles
# =====================================================================

@dataclass
class IsolationCapabilities:
    """Explicitly inspectable host runtime isolation capabilities."""
    backend_name: str
    platform_os: str
    kernel_version: str
    supports_ebpf: bool = False
    supports_seccomp: bool = False
    supports_apparmor: bool = False
    supports_cgroups: bool = False
    supports_network_isolation: bool = False
    supports_readonly_root: bool = False
    supports_user_namespaces: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IsolationViolation:
    """Record of a detected isolation or policy violation."""
    violation_type: str  # 'unauthorized_path', 'prohibited_command', 'network_egress', 'resource_exhaustion', 'privilege_escalation'
    details: str
    severity: str = "HIGH"  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    detected_at: float = field(default_factory=time.time)


@dataclass
class IsolationAuditEvent:
    """Structured audit trail for every sandboxed execution."""
    event_id: str
    timestamp: float
    sandbox_id: str
    profile_name: str
    command: List[str]
    effective_policy: Dict[str, Any]
    violations: List[IsolationViolation]
    action_taken: str  # 'allowed', 'denied', 'terminated', 'completed'
    duration_seconds: float = 0.0
    exit_code: Optional[int] = None
    sanitized_env_keys: List[str] = field(default_factory=list)


@dataclass
class IsolationProfile:
    """Named security profile specifying resource and OS-level confinement."""
    name: str  # 'development', 'standard', 'strict', 'untrusted_code'
    description: str
    non_root: bool = True
    drop_capabilities: List[str] = field(default_factory=lambda: ["ALL"])
    seccomp_profile: Optional[str] = "runtime/default"
    read_only_rootfs: bool = False
    egress_blocked: bool = False
    max_memory_mb: int = 2048
    max_cpu_cores: float = 2.0
    max_processes: int = 128
    timeout_seconds: float = 300.0


@dataclass
class IsolationPolicy:
    """Fine-grained execution policy enforced at runtime boundaries."""
    allowed_workspace_paths: List[str] = field(default_factory=list)
    prohibited_host_paths: List[str] = field(default_factory=lambda: [
        "/etc/shadow", "/etc/passwd", "/root", "C:\\Windows\\System32\\config",
        "~/.ssh", "~/.aws", "~/.gemini", "~/.kube",
    ])
    prohibited_commands: List[str] = field(default_factory=lambda: [
        "shutdown", "reboot", "mkfs", "dd", "format", "iptables", "userdel", "visudo"
    ])
    allow_network_egress: bool = True
    require_ebpf_monitoring: bool = False
    fail_closed_on_unsupported: bool = True


@dataclass
class IsolationSandboxHandle:
    """Handle identifying an active isolation container or subprocess sandbox."""
    sandbox_id: str
    profile: IsolationProfile
    policy: IsolationPolicy
    workspace_dir: str
    created_at: float = field(default_factory=time.time)
    container_id: Optional[str] = None
    pid: Optional[int] = None
    is_active: bool = True


@dataclass
class IsolationExecutionResult:
    """Result of sandboxed command execution with security audit metadata."""
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    violations: List[IsolationViolation] = field(default_factory=list)
    audit_event: Optional[IsolationAuditEvent] = None
    is_fail_closed: bool = False

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0 and len(self.violations) == 0


# Pre-defined Named Profiles
PROFILE_DEVELOPMENT = IsolationProfile(
    name="development",
    description="Permissive local profile for rapid testing and low-overhead local tasks.",
    non_root=False,
    read_only_rootfs=False,
    egress_blocked=False,
    max_memory_mb=4096,
    max_cpu_cores=4.0,
    max_processes=256,
    timeout_seconds=600.0,
)

PROFILE_STANDARD = IsolationProfile(
    name="standard",
    description="Standard container isolation with non-root execution and resource limits.",
    non_root=True,
    drop_capabilities=["SYS_ADMIN", "NET_ADMIN", "SYS_PTRACE"],
    read_only_rootfs=False,
    egress_blocked=False,
    max_memory_mb=2048,
    max_cpu_cores=2.0,
    max_processes=128,
    timeout_seconds=300.0,
)

PROFILE_STRICT = IsolationProfile(
    name="strict",
    description="Hardened isolation with dropped capabilities, readonly root, and egress controls.",
    non_root=True,
    drop_capabilities=["ALL"],
    seccomp_profile="strict",
    read_only_rootfs=True,
    egress_blocked=True,
    max_memory_mb=1024,
    max_cpu_cores=1.0,
    max_processes=64,
    timeout_seconds=120.0,
)

PROFILE_UNTRUSTED_CODE = IsolationProfile(
    name="untrusted_code",
    description="Maximum lockdown for evaluating untrusted dependencies or PR code.",
    non_root=True,
    drop_capabilities=["ALL"],
    seccomp_profile="untrusted",
    read_only_rootfs=True,
    egress_blocked=True,
    max_memory_mb=512,
    max_cpu_cores=1.0,
    max_processes=32,
    timeout_seconds=60.0,
)


# =====================================================================
# Isolation Provider Interface
# =====================================================================

class IsolationProvider(abc.ABC):
    """Abstract provider for runtime execution isolation backends."""

    @abc.abstractmethod
    def get_capabilities(self) -> IsolationCapabilities:
        """Inspect and return the runtime security capabilities of this backend."""
        pass

    @abc.abstractmethod
    def create_sandbox(
        self,
        workspace_dir: str,
        profile: Optional[IsolationProfile] = None,
        policy: Optional[IsolationPolicy] = None,
    ) -> IsolationSandboxHandle:
        """Provision an isolated sandbox container or runtime boundary."""
        pass

    @abc.abstractmethod
    def execute_in_sandbox(
        self,
        handle: IsolationSandboxHandle,
        command: List[str],
        cwd: Optional[str] = None,
        timeout: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> IsolationExecutionResult:
        """Execute a command strictly inside the sandbox boundary."""
        pass

    @abc.abstractmethod
    def destroy_sandbox(self, handle: IsolationSandboxHandle) -> None:
        """Tear down the sandbox, release mounts, and cleanup resources."""
        pass

    @abc.abstractmethod
    def get_audit_trail(self) -> List[IsolationAuditEvent]:
        """Return structured audit events recorded across all executions."""
        pass


# =====================================================================
# Local Process Isolation Provider (Default Local / Host Backend)
# =====================================================================

class LocalProcessIsolationProvider(IsolationProvider):
    """
    Subprocess-level isolation provider with strict path containment, command filtering,
    environment scrubbing, and explicit capability disclosure.
    """

    def __init__(self, eBPF_backend: Optional[Any] = None):
        self.ebpf_backend = eBPF_backend
        self._audit_trail: List[IsolationAuditEvent] = []
        self._sandboxes: Dict[str, IsolationSandboxHandle] = {}

    def get_capabilities(self) -> IsolationCapabilities:
        is_linux = sys.platform.startswith("linux")
        return IsolationCapabilities(
            backend_name="local_process",
            platform_os=sys.platform,
            kernel_version=platform.release(),
            supports_ebpf=bool(self.ebpf_backend and self.ebpf_backend.is_available()),
            supports_seccomp=is_linux,
            supports_apparmor=is_linux and os.path.exists("/sys/kernel/security/apparmor"),
            supports_cgroups=is_linux and os.path.exists("/sys/fs/cgroup"),
            supports_network_isolation=False,
            supports_readonly_root=False,
            supports_user_namespaces=is_linux,
            details={"mode": "local_process_containment"},
        )

    def create_sandbox(
        self,
        workspace_dir: str,
        profile: Optional[IsolationProfile] = None,
        policy: Optional[IsolationPolicy] = None,
    ) -> IsolationSandboxHandle:
        prof = profile or PROFILE_STANDARD
        pol = policy or IsolationPolicy(allowed_workspace_paths=[workspace_dir])

        # Validate mandatory eBPF requirement
        if pol.require_ebpf_monitoring:
            caps = self.get_capabilities()
            if not caps.supports_ebpf:
                if pol.fail_closed_on_unsupported:
                    raise IsolationUnavailableError(
                        "eBPF monitoring required by policy, but not supported on current runtime/platform."
                    )

        sb_id = f"sandbox-{uuid.uuid4().hex[:10]}"
        handle = IsolationSandboxHandle(
            sandbox_id=sb_id,
            profile=prof,
            policy=pol,
            workspace_dir=os.path.abspath(workspace_dir),
            created_at=time.time(),
        )
        self._sandboxes[sb_id] = handle
        return handle

    def execute_in_sandbox(
        self,
        handle: IsolationSandboxHandle,
        command: List[str],
        cwd: Optional[str] = None,
        timeout: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> IsolationExecutionResult:
        start_t = time.time()
        violations: List[IsolationViolation] = []
        target_cwd = cwd or handle.workspace_dir
        cmd_str = " ".join(command)

        # 1. Prohibited Command Validation
        for prohibited in handle.policy.prohibited_commands:
            if any(prohibited == arg or prohibited in arg.split() for arg in command):
                violations.append(IsolationViolation(
                    violation_type="prohibited_command",
                    details=f"Command '{cmd_str}' matches prohibited directive '{prohibited}'.",
                    severity="CRITICAL",
                ))

        # 2. Path Traversal & Prohibited Host Path Validation
        for prohibited_path in handle.policy.prohibited_host_paths:
            expanded = os.path.expanduser(prohibited_path)
            for arg in command:
                if expanded in arg or prohibited_path in arg:
                    violations.append(IsolationViolation(
                        violation_type="unauthorized_path",
                        details=f"Argument '{arg}' references prohibited host path '{prohibited_path}'.",
                        severity="HIGH",
                    ))

        # 3. Workspace Path Containment Check
        abs_target_cwd = os.path.abspath(target_cwd)
        abs_ws = os.path.abspath(handle.workspace_dir)
        if not abs_target_cwd.startswith(abs_ws):
            violations.append(IsolationViolation(
                violation_type="unauthorized_path",
                details=f"Target working directory '{abs_target_cwd}' escapes workspace boundary '{abs_ws}'.",
                severity="HIGH",
            ))

        # 4. If critical violations found, fail closed immediately
        if violations:
            audit = IsolationAuditEvent(
                event_id=f"audit-{uuid.uuid4().hex[:8]}",
                timestamp=time.time(),
                sandbox_id=handle.sandbox_id,
                profile_name=handle.profile.name,
                command=command,
                effective_policy={"profile": handle.profile.name, "egress_blocked": handle.profile.egress_blocked},
                violations=violations,
                action_taken="denied",
                duration_seconds=time.time() - start_t,
                exit_code=126,
            )
            self._audit_trail.append(audit)
            raise IsolationViolationError(
                f"Sandbox execution denied due to {len(violations)} security violation(s): {[v.details for v in violations]}"
            )

        # 5. Environment Scrubbing (remove sensitive host tokens)
        scrubbed_env = dict(os.environ)
        sensitive_keys = [k for k in scrubbed_env if any(s in k.upper() for s in ["KEY", "SECRET", "TOKEN", "PASSWORD", "AUTH"])]
        for k in sensitive_keys:
            scrubbed_env.pop(k, None)
        if env:
            scrubbed_env.update(env)

        exec_timeout = timeout or handle.profile.timeout_seconds

        # 6. Run process with timeout
        try:
            proc = subprocess.run(
                command,
                cwd=abs_target_cwd,
                capture_output=True,
                text=True,
                timeout=exec_timeout,
                env=scrubbed_env,
            )
            duration = time.time() - start_t
            audit = IsolationAuditEvent(
                event_id=f"audit-{uuid.uuid4().hex[:8]}",
                timestamp=time.time(),
                sandbox_id=handle.sandbox_id,
                profile_name=handle.profile.name,
                command=command,
                effective_policy={"profile": handle.profile.name},
                violations=violations,
                action_taken="completed",
                duration_seconds=duration,
                exit_code=proc.returncode,
                sanitized_env_keys=sensitive_keys,
            )
            self._audit_trail.append(audit)
            return IsolationExecutionResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_seconds=duration,
                violations=violations,
                audit_event=audit,
            )
        except subprocess.TimeoutExpired as te:
            duration = time.time() - start_t
            violations.append(IsolationViolation(
                violation_type="resource_exhaustion",
                details=f"Execution exceeded timeout limit of {exec_timeout}s.",
                severity="MEDIUM",
            ))
            audit = IsolationAuditEvent(
                event_id=f"audit-{uuid.uuid4().hex[:8]}",
                timestamp=time.time(),
                sandbox_id=handle.sandbox_id,
                profile_name=handle.profile.name,
                command=command,
                effective_policy={"profile": handle.profile.name},
                violations=violations,
                action_taken="terminated",
                duration_seconds=duration,
                exit_code=124,
            )
            self._audit_trail.append(audit)
            return IsolationExecutionResult(
                exit_code=124,
                stdout=te.stdout or "" if isinstance(te.stdout, str) else "",
                stderr=f"TimeoutExpired: execution killed after {exec_timeout}s",
                duration_seconds=duration,
                violations=violations,
                audit_event=audit,
                is_fail_closed=True,
            )
        except Exception as e:
            duration = time.time() - start_t
            audit = IsolationAuditEvent(
                event_id=f"audit-{uuid.uuid4().hex[:8]}",
                timestamp=time.time(),
                sandbox_id=handle.sandbox_id,
                profile_name=handle.profile.name,
                command=command,
                effective_policy={"profile": handle.profile.name},
                violations=violations,
                action_taken="terminated",
                duration_seconds=duration,
                exit_code=1,
            )
            self._audit_trail.append(audit)
            return IsolationExecutionResult(
                exit_code=1,
                stdout="",
                stderr=f"Execution failed: {e}",
                duration_seconds=duration,
                violations=violations,
                audit_event=audit,
            )

    def destroy_sandbox(self, handle: IsolationSandboxHandle) -> None:
        handle.is_active = False
        self._sandboxes.pop(handle.sandbox_id, None)

    def get_audit_trail(self) -> List[IsolationAuditEvent]:
        return list(self._audit_trail)
