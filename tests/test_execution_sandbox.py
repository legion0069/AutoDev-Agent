"""
test_execution_sandbox.py - Comprehensive Tests for Sandbox Containment & Command Policy (v2.1)
"""

import os
import sys
import pytest
from pathlib import Path

from core.execution_sandbox import (
    CommandPolicyError,
    CommandResult,
    CommandTimeoutError,
    ExecutionSandbox,
    PathContainmentError,
    ProtectedPathViolationError,
    SandboxSecurityError,
)


# =============================================================================
# 1. PATH CONTAINMENT & TRAVERSAL TESTS
# =============================================================================

def test_sandbox_valid_relative_path(tmp_path):
    """Verifies that legitimate relative paths resolve cleanly within workspace."""
    sandbox = ExecutionSandbox(workspace_root=tmp_path)
    res = sandbox.validate_path("src/core/utils.py")
    assert res == (tmp_path / "src" / "core" / "utils.py").resolve()
    assert res.is_relative_to(tmp_path)


def test_sandbox_parent_traversal_rejected(tmp_path):
    """Verifies that parent traversal attempts (../) outside root raise PathContainmentError."""
    sandbox = ExecutionSandbox(workspace_root=tmp_path)
    with pytest.raises(PathContainmentError) as exc_info:
        sandbox.validate_path("../../etc/passwd")
    assert "escapes workspace root" in str(exc_info.value).lower() or "containment violation" in str(exc_info.value).lower()


def test_sandbox_absolute_path_outside_workspace_rejected(tmp_path):
    """Verifies that absolute paths outside workspace root raise PathContainmentError."""
    sandbox = ExecutionSandbox(workspace_root=tmp_path)
    # Outside path
    outside = Path(tmp_path.parent / "other_dir" / "secret.txt")
    with pytest.raises(PathContainmentError):
        sandbox.validate_path(str(outside))


def test_sandbox_windows_drive_or_system_escape_rejected(tmp_path):
    r"""Verifies that absolute OS paths (e.g. C:\Windows or /etc) raise PathContainmentError."""
    sandbox = ExecutionSandbox(workspace_root=tmp_path)
    target = "C:\\Windows\\System32\\calc.exe" if os.name == "nt" else "/etc/shadow"
    with pytest.raises(PathContainmentError):
        sandbox.validate_path(target)


# =============================================================================
# 2. PROTECTED & SENSITIVE PATH TESTS
# =============================================================================

def test_sandbox_git_directory_mutation_forbidden(tmp_path):
    """Verifies that writing to .git control directory is prohibited."""
    sandbox = ExecutionSandbox(workspace_root=tmp_path, allow_git_control_writes=False)
    with pytest.raises(ProtectedPathViolationError) as exc_info:
        sandbox.validate_path(".git/config", is_write=True)
    assert "protected directory '.git'" in str(exc_info.value).lower()


def test_sandbox_sensitive_denied_patterns(tmp_path):
    """Verifies that credentials and secret keys (.env, id_rsa, .pem) are blocked."""
    sandbox = ExecutionSandbox(workspace_root=tmp_path)

    with pytest.raises(ProtectedPathViolationError):
        sandbox.validate_path(".env")

    with pytest.raises(ProtectedPathViolationError):
        sandbox.validate_path("config/production.env")

    with pytest.raises(ProtectedPathViolationError):
        sandbox.validate_path("id_rsa")

    with pytest.raises(ProtectedPathViolationError):
        sandbox.validate_path("certs/server.pem")


def test_sandbox_custom_allowed_paths(tmp_path):
    """Verifies that configured allowed_paths blocks writes to non-whitelisted paths."""
    sandbox = ExecutionSandbox(
        workspace_root=tmp_path,
        allowed_paths=["src", "tests", "docs"],
    )

    # Allowed paths succeed
    sandbox.validate_path("src/module.py", is_write=True)
    sandbox.validate_path("tests/test_mod.py", is_write=True)

    # Non-allowed path is rejected
    with pytest.raises(ProtectedPathViolationError) as exc_info:
        sandbox.validate_path("scripts/deploy.sh", is_write=True)
    assert "not within any configured allowed paths" in str(exc_info.value)


# =============================================================================
# 3. COMMAND POLICY TESTS
# =============================================================================

def test_sandbox_validate_command_approved_binary(tmp_path):
    """Verifies that approved command binaries are parsed into safe argument arrays."""
    sandbox = ExecutionSandbox(workspace_root=tmp_path)
    args = sandbox.validate_command("python -m py_compile src/app.py")
    assert args == ["python", "-m", "py_compile", "src/app.py"]


def test_sandbox_validate_command_unapproved_binary_rejected(tmp_path):
    """Verifies that unapproved binaries raise CommandPolicyError."""
    sandbox = ExecutionSandbox(workspace_root=tmp_path)
    with pytest.raises(CommandPolicyError) as exc_info:
        sandbox.validate_command("curl http://example.com")
    assert "not in the approved command allowlist" in str(exc_info.value)


def test_sandbox_dangerous_command_substrings_rejected(tmp_path):
    """Verifies that destructive shell commands are blocked."""
    sandbox = ExecutionSandbox(workspace_root=tmp_path)
    with pytest.raises(CommandPolicyError) as exc_info:
        sandbox.validate_command("python -c 'import os; os.system(\"rm -rf /\")'")
    assert "prohibited sequence" in str(exc_info.value).lower()


# =============================================================================
# 4. SUBPROCESS EXECUTION TESTS
# =============================================================================

def test_sandbox_run_command_success(tmp_path):
    """Verifies running a safe subprocess in the sandbox."""
    sandbox = ExecutionSandbox(workspace_root=tmp_path)
    cmd = [sys.executable, "-c", "print('sandbox execution successful')"]
    res: CommandResult = sandbox.run_command(cmd)

    assert res.success is True
    assert res.exit_code == 0
    assert "sandbox execution successful" in res.stdout
    assert res.duration_seconds >= 0.0


def test_sandbox_run_command_timeout(tmp_path):
    """Verifies that long-running commands are terminated after timeout."""
    sandbox = ExecutionSandbox(workspace_root=tmp_path)
    # Run sleep for 5 seconds with 0.5s timeout
    cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    res: CommandResult = sandbox.run_command(cmd, timeout_seconds=0.5)

    assert res.timed_out is True
    assert res.success is False
    assert "timeout" in res.stderr.lower()


def test_sandbox_run_command_redacts_secrets(tmp_path):
    """Verifies that captured stdout/stderr redacts sensitive keys."""
    sandbox = ExecutionSandbox(workspace_root=tmp_path)
    cmd = [sys.executable, "-c", "print('API_KEY: sk-1234567890123456789012345')"]
    res: CommandResult = sandbox.run_command(cmd)

    assert "sk-1234567890123456789012345" not in res.stdout
    assert "[REDACTED]" in res.stdout
