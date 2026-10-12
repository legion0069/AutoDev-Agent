"""
test_container_sandbox.py - Tests for Containerized Execution Sandbox & Fail-Closed Routing (v2.2)
"""

import pytest
from pathlib import Path

from core.container_runtime import (
    ContainerRuntimeUnavailableError,
    ContainerSecurityProfile,
    MockContainerRuntime,
)
from core.container_sandbox import ContainerSandbox, ExecutionBackend
from core.execution_sandbox import CommandResult


def test_container_sandbox_process_fallback(tmp_path):
    """Verifies ContainerSandbox uses host process execution when backend is PROCESS."""
    sandbox = ContainerSandbox(workspace_root=tmp_path, backend=ExecutionBackend.PROCESS)
    res: CommandResult = sandbox.execute_in_sandbox(["python", "-c", "print('process-ok')"])

    assert res.success is True
    assert "process-ok" in res.stdout


def test_container_sandbox_mock_container_backend(tmp_path):
    """Verifies ContainerSandbox delegates to container runtime when backend is CONTAINER."""
    mock_rt = MockContainerRuntime(
        should_succeed=True,
        mock_stdout="container-output-verified",
    )
    sandbox = ContainerSandbox(
        workspace_root=tmp_path,
        backend=ExecutionBackend.CONTAINER,
        container_runtime=mock_rt,
    )
    res = sandbox.execute_in_sandbox(["python", "-c", "print('hello')"])

    assert res.success is True
    assert "container-output-verified" in res.stdout
    assert len(mock_rt.execution_history) == 1


def test_container_sandbox_fails_closed_when_container_required_and_unavailable(tmp_path):
    """Verifies that require_container=True strictly fails closed if runtime is not usable."""
    mock_rt = MockContainerRuntime(is_available=False, is_daemon_running=False)
    sandbox = ContainerSandbox(
        workspace_root=tmp_path,
        backend=ExecutionBackend.AUTO,
        container_runtime=mock_rt,
    )

    with pytest.raises(ContainerRuntimeUnavailableError) as exc_info:
        sandbox.execute_in_sandbox(
            ["python", "test.py"],
            require_container=True,
        )
    assert "Container isolation was required for this operation" in str(exc_info.value)


def test_container_sandbox_passes_environment_variables(tmp_path):
    """Verifies environment variables are passed to container config."""
    mock_rt = MockContainerRuntime(should_succeed=True)
    sandbox = ContainerSandbox(
        workspace_root=tmp_path,
        backend=ExecutionBackend.CONTAINER,
        container_runtime=mock_rt,
    )
    sandbox.execute_in_sandbox(
        ["pytest"],
        env={"TEST_ENV": "active", "RUN_ID": "123"},
    )
    assert len(mock_rt.execution_history) == 1
    cfg = mock_rt.execution_history[0]
    assert cfg.environment.get("TEST_ENV") == "active"
    assert cfg.environment.get("RUN_ID") == "123"


def test_container_sandbox_read_only_workspace_mount(tmp_path):
    """Verifies read_only_workspace flag marks mount as read-only."""
    mock_rt = MockContainerRuntime(should_succeed=True)
    sandbox = ContainerSandbox(
        workspace_root=tmp_path,
        backend=ExecutionBackend.CONTAINER,
        container_runtime=mock_rt,
    )
    sandbox.execute_in_sandbox(
        ["python", "analyze.py"],
        read_only_workspace=True,
    )
    cfg = mock_rt.execution_history[0]
    assert len(cfg.mounts) == 1
    assert cfg.mounts[0].read_only is True


def test_container_sandbox_custom_image_setting(tmp_path):
    """Verifies custom default_image is propagated to container execution config."""
    mock_rt = MockContainerRuntime(should_succeed=True)
    sandbox = ContainerSandbox(
        workspace_root=tmp_path,
        backend=ExecutionBackend.CONTAINER,
        container_runtime=mock_rt,
        default_image="python:3.12-alpine",
    )
    sandbox.execute_in_sandbox(["python", "--version"])
    assert mock_rt.execution_history[0].image == "python:3.12-alpine"


def test_container_sandbox_backend_enum_values():
    """Verifies all defined ExecutionBackend enum options."""
    expected = {"process", "container", "auto"}
    actual = {b.value for b in ExecutionBackend}
    assert expected == actual


def test_container_sandbox_auto_mode_uses_container_when_available(tmp_path):
    """Verifies AUTO mode routes to container when healthy container runtime is present."""
    mock_rt = MockContainerRuntime(should_succeed=True, is_available=True, is_daemon_running=True)
    sandbox = ContainerSandbox(
        workspace_root=tmp_path,
        backend=ExecutionBackend.AUTO,
        container_runtime=mock_rt,
    )
    res = sandbox.execute_in_sandbox(["echo", "auto-test"])
    assert res.success is True
    assert len(mock_rt.execution_history) == 1


