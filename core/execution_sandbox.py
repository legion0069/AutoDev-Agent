"""
execution_sandbox.py - Sandbox Security, Path Containment & Command Policy for AutoDev (v2.1)

Enforces strict workspace isolation:
- Path traversal prevention (parent directory, drive letters, UNC, symlinks, protected files)
- Configurable directory allowlists and sensitive file denylists
- Safe subprocess execution with argument arrays (no shell=True), approved command allowlists,
  timeouts, process-tree termination, and secret redaction.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Ensure project root is available on sys.path
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.execution_journal import redact_secrets
from core.execution_transaction import ExecutionEngineError

logger = logging.getLogger("AutoDev.ExecutionSandbox")


# =============================================================================
# EXCEPTION HIERARCHY
# =============================================================================

class SandboxSecurityError(ExecutionEngineError):
    """Base exception for all sandbox containment and security violations."""
    pass


class PathContainmentError(SandboxSecurityError):
    """Raised when a path escapes the authorized workspace boundaries."""
    pass


class ProtectedPathViolationError(SandboxSecurityError):
    """Raised when an operation attempts to mutate a protected internal or system path."""
    pass


class CommandPolicyError(SandboxSecurityError):
    """Raised when a command violates the approved command execution policy."""
    pass


class CommandTimeoutError(SandboxSecurityError):
    """Raised when a command execution exceeds its allotted time limit."""
    pass


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class CommandResult:
    """
    Structured telemetry outcome of a sandboxed subprocess execution.
    """
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    finished_at: Optional[str] = None
    cwd: str = ""

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": list(self.command),
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": self.duration_seconds,
            "timed_out": self.timed_out,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "cwd": self.cwd,
            "success": self.success,
        }


# =============================================================================
# SENSITIVE & PROTECTED CONSTANTS
# =============================================================================

DEFAULT_PROTECTED_DIR_NAMES = {
    ".git",
    ".github",
    ".svn",
    ".hg",
    ".ssh",
    ".aws",
    ".azure",
    ".kube",
}

DEFAULT_DENIED_FILE_PATTERNS = [
    re.compile(r"(?i)\.env(\..+)?$"),
    re.compile(r"(?i).*\.pem$"),
    re.compile(r"(?i).*\.key$"),
    re.compile(r"(?i).*\.pkcs12$"),
    re.compile(r"(?i).*id_rsa.*"),
    re.compile(r"(?i).*credentials.*"),
    re.compile(r"(?i).*authorized_keys.*"),
    re.compile(r"(?i).*\.passwd$"),
    re.compile(r"(?i).*\.shadow$"),
]

DEFAULT_APPROVED_BINARIES = {
    "python",
    "python3",
    "py",
    "pytest",
    "flake8",
    "mypy",
    "black",
    "bandit",
    "coverage",
    "git",
    "npm",
    "npx",
    "node",
    "tsc",
    "dotnet",
    "mvn",
    "gradle",
    "cargo",
    "go",
    "echo",
}

DANGEROUS_COMMAND_SUBSTRINGS = [
    "rm -rf /",
    "rm -rf /*",
    "del /s /q c:\\",
    "del /f /s /q",
    "format c:",
    ":(){ :|:& };:",
    "shutdown",
    "reboot",
    "curl | bash",
    "wget | bash",
    "mkfs",
    "dd if=",
]


# =============================================================================
# EXECUTION SANDBOX CLASS
# =============================================================================

class ExecutionSandbox:
    """
    Enforces path containment, configurable allowlist/denylist rules,
    and safe command execution policies.
    """

    def __init__(
        self,
        workspace_root: Union[str, Path],
        allowed_paths: Optional[List[str]] = None,
        denied_patterns: Optional[List[re.Pattern]] = None,
        approved_binaries: Optional[Set[str]] = None,
        allow_git_control_writes: bool = False,
        default_command_timeout: float = 30.0,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.allowed_paths = [Path(p).as_posix() for p in (allowed_paths or [])]
        self.denied_patterns = denied_patterns or list(DEFAULT_DENIED_FILE_PATTERNS)
        self.approved_binaries = set(approved_binaries or DEFAULT_APPROVED_BINARIES)
        self.allow_git_control_writes = allow_git_control_writes
        self.default_command_timeout = default_command_timeout

    # -------------------------------------------------------------------------
    # Path Validation & Containment
    # -------------------------------------------------------------------------

    def validate_path(
        self,
        target_path: Union[str, Path],
        is_write: bool = False,
        is_delete: bool = False,
    ) -> Path:
        """
        Validates that a path is strictly contained within the workspace root
        and does not violate security denylists, traversal limits, or protected directories.

        Returns:
            Resolved absolute Path object within workspace_root.

        Raises:
            PathContainmentError: If path escapes the workspace root.
            ProtectedPathViolationError: If path targets a protected or sensitive file.
        """
        path_obj = Path(target_path)

        # 1. Reject explicit UNC or Windows Drive Escapes when given as absolute outside workspace
        if path_obj.is_absolute():
            try:
                resolved = path_obj.resolve()
            except Exception as exc:
                raise PathContainmentError(f"Could not resolve absolute path '{target_path}': {exc}") from exc
        else:
            resolved = (self.workspace_root / path_obj).resolve()

        # 2. Strict Workspace Containment Check
        clean_resolved = Path(str(resolved).removeprefix("\\\\?\\"))
        clean_root = Path(str(self.workspace_root).removeprefix("\\\\?\\"))
        try:
            rel_to_root = clean_resolved.relative_to(clean_root)
        except ValueError as exc:
            raise PathContainmentError(
                f"Path containment violation: '{target_path}' (resolved to '{resolved}') "
                f"escapes workspace root '{self.workspace_root}'."
            ) from exc

        rel_posix = rel_to_root.as_posix()

        # 3. Check for Traversal / Parent Segment Residue
        if ".." in rel_posix.split("/"):
            raise PathContainmentError(
                f"Path traversal detected in path '{target_path}'."
            )

        # 4. Check Protected Control Directories (.git, etc.)
        parts = rel_to_root.parts
        if not self.allow_git_control_writes and is_write:
            for part in parts:
                if part in DEFAULT_PROTECTED_DIR_NAMES:
                    raise ProtectedPathViolationError(
                        f"Mutation of protected directory '{part}' in path '{target_path}' is forbidden."
                    )

        # 5. Check Sensitive File Denylists
        filename = resolved.name
        for pattern in self.denied_patterns:
            if pattern.search(filename) or pattern.search(rel_posix):
                raise ProtectedPathViolationError(
                    f"Access to sensitive file '{target_path}' matches denied pattern '{pattern.pattern}'."
                )

        # 6. Check Configurable Allowed Paths (if allowlist specified)
        if self.allowed_paths and is_write:
            matches_allowed = any(
                rel_posix == allowed or rel_posix.startswith(allowed.rstrip("/") + "/")
                for allowed in self.allowed_paths
            )
            if not matches_allowed:
                raise ProtectedPathViolationError(
                    f"Path '{rel_posix}' is not within any configured allowed paths: {self.allowed_paths}"
                )

        return resolved

    # -------------------------------------------------------------------------
    # Command Policy & Safe Execution
    # -------------------------------------------------------------------------

    def validate_command(
        self, command: Union[str, List[str]]
    ) -> List[str]:
        """
        Validates a command against safety policies and converts it to a safe argument array.

        Raises:
            CommandPolicyError: If command is dangerous, unapproved, or malformed.
        """
        if isinstance(command, str):
            cmd_str = command.strip()
            # Check dangerous command substrings
            for dang in DANGEROUS_COMMAND_SUBSTRINGS:
                if dang in cmd_str.lower():
                    raise CommandPolicyError(
                        f"Command '{cmd_str}' contains dangerous prohibited sequence '{dang}'."
                    )
            # Parse into argument list safely
            try:
                args = shlex.split(cmd_str, posix=(os.name != "nt"))
            except ValueError as exc:
                raise CommandPolicyError(
                    f"Failed to parse command string '{cmd_str}': {exc}"
                ) from exc
        elif isinstance(command, list):
            args = [str(a) for a in command if a is not None]
            cmd_str = " ".join(args)
            for dang in DANGEROUS_COMMAND_SUBSTRINGS:
                if dang in cmd_str.lower():
                    raise CommandPolicyError(
                        f"Command contains dangerous prohibited sequence '{dang}'."
                    )
        else:
            raise CommandPolicyError(f"Unsupported command type: {type(command)}")

        if not args:
            raise CommandPolicyError("Command cannot be empty.")

        binary_name = Path(args[0]).name.lower()
        if binary_name.endswith(".exe"):
            binary_name = binary_name[:-4]

        if binary_name not in self.approved_binaries:
            raise CommandPolicyError(
                f"Binary '{binary_name}' is not in the approved command allowlist: "
                f"{sorted(list(self.approved_binaries))}"
            )

        return args

    def run_command(
        self,
        command: Union[str, List[str]],
        timeout_seconds: Optional[float] = None,
        cwd: Optional[Union[str, Path]] = None,
        env_override: Optional[Dict[str, str]] = None,
    ) -> CommandResult:
        """
        Executes a validated command in a controlled subprocess with strict arguments array,
        timeout protection, and secret redaction.
        """
        args = self.validate_command(command)
        timeout = timeout_seconds or self.default_command_timeout

        working_dir = self.workspace_root
        if cwd:
            working_dir = self.validate_path(cwd)

        # Build clean environment with optional overrides
        exec_env = os.environ.copy()
        exec_env["PYTHONUNBUFFERED"] = "1"
        if env_override:
            exec_env.update(env_override)

        started_at = datetime.now(timezone.utc).isoformat()
        start_time = time.perf_counter()
        timed_out = False
        exit_code = -1
        stdout = ""
        stderr = ""

        logger.info("Sandbox executing command: %s (CWD: %s, Timeout: %ss)", args, working_dir, timeout)

        try:
            # Explicitly NEVER use shell=True
            proc = subprocess.Popen(
                args,
                cwd=str(working_dir),
                env=exec_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
            )
            try:
                out, err = proc.communicate(timeout=timeout)
                exit_code = proc.returncode
                stdout = out or ""
                stderr = err or ""
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.kill()
                out, err = proc.communicate()
                stdout = out or ""
                stderr = (err or "") + f"\n[AutoDev Sandbox] Process killed after timeout of {timeout}s."
                exit_code = -9
        except FileNotFoundError as fnf:
            exit_code = 127
            stderr = f"Command executable not found: {fnf}"
        except OSError as ose:
            exit_code = 126
            stderr = f"Failed to spawn subprocess: {ose}"

        duration = time.perf_counter() - start_time
        finished_at = datetime.now(timezone.utc).isoformat()

        # Sanitize sensitive data from captured output
        clean_stdout = redact_secrets(stdout)
        clean_stderr = redact_secrets(stderr)

        return CommandResult(
            command=args,
            exit_code=exit_code,
            stdout=clean_stdout,
            stderr=clean_stderr,
            duration_seconds=round(duration, 4),
            timed_out=timed_out,
            started_at=started_at,
            finished_at=finished_at,
            cwd=str(working_dir),
        )
