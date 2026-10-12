"""
Tests for fail-closed runtime isolation enforcement, unauthorized host mounts, and traversal defense.
"""

import os
import sys
import tempfile
import pytest
from core.isolation_provider import (
    LocalProcessIsolationProvider,
    PROFILE_STRICT,
    PROFILE_UNTRUSTED_CODE,
    IsolationPolicy,
    IsolationViolationError,
)


def test_isolation_workspace_escape_denied(tmp_path):
    ws_dir = tmp_path / "authorized_workspace"
    ws_dir.mkdir()
    outside_dir = tmp_path / "forbidden_outside"
    outside_dir.mkdir()

    provider = LocalProcessIsolationProvider()
    handle = provider.create_sandbox(
        workspace_dir=str(ws_dir),
        profile=PROFILE_STRICT,
        policy=IsolationPolicy(allowed_workspace_paths=[str(ws_dir)]),
    )

    # Attempting to execute with target cwd outside workspace must fail closed
    with pytest.raises(IsolationViolationError) as exc_info:
        provider.execute_in_sandbox(
            handle=handle,
            command=[sys.executable, "-c", "print('escaped')"],
            cwd=str(outside_dir),
        )

    assert "escapes workspace boundary" in str(exc_info.value)
    provider.destroy_sandbox(handle)


def test_isolation_environment_token_scrubbing(tmp_path):
    provider = LocalProcessIsolationProvider()
    handle = provider.create_sandbox(
        workspace_dir=str(tmp_path),
        profile=PROFILE_UNTRUSTED_CODE,
    )

    # Set dummy sensitive environment variables in parent process
    os.environ["AUTODEV_SECRET_KEY"] = "super_secret_12345"
    os.environ["API_TOKEN"] = "token_xyz_987"

    # Command that prints environment
    script = "import os; print('SECRET_PRESENT=' + str('AUTODEV_SECRET_KEY' in os.environ))"
    result = provider.execute_in_sandbox(
        handle=handle,
        command=[sys.executable, "-c", script],
    )

    assert result.exit_code == 0
    assert "SECRET_PRESENT=False" in result.stdout
    assert "AUTODEV_SECRET_KEY" in result.audit_event.sanitized_env_keys

    # Clean up
    os.environ.pop("AUTODEV_SECRET_KEY", None)
    os.environ.pop("API_TOKEN", None)
    provider.destroy_sandbox(handle)
