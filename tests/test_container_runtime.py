"""
test_container_runtime.py - Comprehensive Tests for Container Runtime Abstraction & Security Profiles (v2.2)
"""

import pytest
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
    redact_container_output,
)


# =============================================================================
# 1. RUNTIME DETECTOR & DATA MODEL TESTS
# =============================================================================

def test_container_runtime_detector_probes():
    """Verifies ContainerRuntimeDetector inspects docker/podman and falls back to NONE gracefully."""
    detector = ContainerRuntimeDetector()
    info = detector.detect()

    assert isinstance(info, ContainerRuntimeInfo)
    assert info.runtime_type in {ContainerRuntimeType.DOCKER, ContainerRuntimeType.PODMAN, ContainerRuntimeType.NONE}
    assert isinstance(info.capabilities, dict)
    assert "read_only_root" in info.capabilities
    assert info.last_checked_at is not None


def test_container_runtime_info_serialization():
    """Verifies ContainerRuntimeInfo round-trip serialization."""
    info = ContainerRuntimeInfo(
        runtime_type=ContainerRuntimeType.DOCKER,
        is_available=True,
        executable_path="/usr/bin/docker",
        version="Docker version 25.0.0",
        is_daemon_running=True,
    )
    data = info.to_dict()
    assert data["runtime_type"] == "docker"
    assert data["is_available"] is True
    assert data["executable_path"] == "/usr/bin/docker"
    assert data["is_daemon_running"] is True


def test_container_execution_config_serialization():
    """Verifies ContainerExecutionConfig serialization with secret redaction."""
    cfg = ContainerExecutionConfig(
        image="python:3.12-alpine",
        command=["python", "-c", "print('ok')"],
        environment={"API_KEY": "sk-1234567890abcdef1234567890", "PORT": "8080"},
        mounts=[ContainerMount(host_path="/host/app", container_path="/workspace", read_only=True)],
        security_profile=ContainerSecurityProfile.RESTRICTED,
    )
    data = cfg.to_dict()
    assert data["image"] == "python:3.12-alpine"
    assert data["environment"]["API_KEY"] == "[REDACTED]"
    assert data["environment"]["PORT"] == "8080"
    assert data["security_profile"] == "restricted"
    assert len(data["mounts"]) == 1
    assert data["mounts"][0]["read_only"] is True


# =============================================================================
# 2. SECRET REDACTION TESTS
# =============================================================================

def test_redact_container_output_scrubs_tokens():
    """Verifies secrets in stdout/stderr are stripped."""
    raw = "Token received: Bearer sk-1234567890abcdef1234567890 and AIzaSyD9876543210abcdefghijklmnopq"
    clean = redact_container_output(raw)
    assert "sk-1234567890abcdef1234567890" not in clean
    assert "AIzaSyD9876543210abcdefghijklmnopq" not in clean
    assert "[REDACTED]" in clean


# =============================================================================
# 3. MOCK RUNTIME EXECUTION & ERROR HANDLING
# =============================================================================

def test_mock_container_runtime_success():
    """Verifies successful container execution via mock runtime."""
    runtime = MockContainerRuntime(
        should_succeed=True,
        exit_code=0,
        mock_stdout="Compilation successful",
    )
    cfg = ContainerExecutionConfig(
        command=["python", "-m", "py_compile", "app.py"],
        timeout_seconds=10.0,
    )
    res: ContainerExecutionResult = runtime.execute(cfg)

    assert res.success is True
    assert res.exit_code == 0
    assert "Compilation successful" in res.stdout
    assert res.timed_out is False
    assert res.runtime_type == ContainerRuntimeType.DOCKER


def test_mock_container_runtime_failure():
    """Verifies container failure reporting."""
    runtime = MockContainerRuntime(
        should_succeed=False,
        exit_code=2,
        mock_stderr="SyntaxError: invalid syntax",
    )
    cfg = ContainerExecutionConfig(command=["python", "broken.py"])
    res = runtime.execute(cfg)

    assert res.success is False
    assert res.exit_code == 2
    assert "SyntaxError" in res.stderr


def test_mock_container_runtime_timeout():
    """Verifies container timeout detection."""
    runtime = MockContainerRuntime(should_timeout=True)
    cfg = ContainerExecutionConfig(command=["sleep", "100"], timeout_seconds=2.0)
    res = runtime.execute(cfg)

    assert res.success is False
    assert res.timed_out is True
    assert res.exit_code == 124


def test_mock_container_runtime_unavailable_raises_error():
    """Verifies error raised when daemon is unreachable."""
    runtime = MockContainerRuntime(is_available=False, is_daemon_running=False)
    cfg = ContainerExecutionConfig(command=["echo", "hello"])

    with pytest.raises(ContainerRuntimeUnavailableError) as exc_info:
        runtime.execute(cfg)
    assert "daemon is unavailable" in str(exc_info.value)


# =============================================================================
# 4. CONTAINER SECURITY POLICY VIOLATIONS
# =============================================================================

def test_container_security_policy_forbids_docker_socket_mount():
    """Verifies mounting the host docker.sock is strictly forbidden."""
    runtime = MockContainerRuntime()
    cfg = ContainerExecutionConfig(
        mounts=[ContainerMount(host_path="/var/run/docker.sock", container_path="/docker.sock", read_only=False)]
    )
    with pytest.raises(ContainerSecurityViolationError) as exc_info:
        runtime.execute(cfg)
    assert "Mounting sensitive system path" in str(exc_info.value)


def test_container_security_policy_forbids_network_in_restricted_profile():
    """Verifies network_mode='bridge' is forbidden in restricted profile."""
    runtime = MockContainerRuntime()
    cfg = ContainerExecutionConfig(
        security_profile=ContainerSecurityProfile.RESTRICTED,
        network_mode="bridge",
    )
    with pytest.raises(ContainerSecurityViolationError) as exc_info:
        runtime.execute(cfg)
    assert "Network access is forbidden in 'restricted' security profile" in str(exc_info.value)


def test_container_security_policy_allows_network_in_development_profile():
    """Verifies network_mode='bridge' is allowed when development profile is specified."""
    runtime = MockContainerRuntime(should_succeed=True, exit_code=0)
    cfg = ContainerExecutionConfig(
        security_profile=ContainerSecurityProfile.DEVELOPMENT,
        network_mode="bridge",
        command=["pip", "install", "requests"],
    )
    res = runtime.execute(cfg)
    assert res.success is True


def test_container_security_policy_blocks_etc_and_root_mounts():
    """Verifies mounting /etc, /root, or /bin is strictly rejected."""
    runtime = MockContainerRuntime()
    for forbidden_path in ["/etc", "/root", "/bin", "/sbin"]:
        cfg = ContainerExecutionConfig(
            mounts=[ContainerMount(host_path=forbidden_path, container_path="/data")]
        )
        with pytest.raises(ContainerSecurityViolationError):
            runtime.execute(cfg)


def test_container_command_builder_flags():
    """Verifies generated CLI command contains security hardening flags."""
    runtime = MockContainerRuntime()
    cfg = ContainerExecutionConfig(
        image="python:3.12-slim",
        command=["pytest"],
        security_profile=ContainerSecurityProfile.RESTRICTED,
        read_only_root=True,
        user_id="1001:1001",
        cpu_limit="2.0",
        memory_limit="1g",
        pids_limit=128,
        tmpfs_mounts=["/tmp:rw,size=32m"],
    )
    cmd = runtime._build_run_command(cfg, "test-container")
    assert "--rm" in cmd
    assert "--read-only" in cmd
    assert "--user" in cmd
    assert "1001:1001" in cmd
    assert "--cpus=2.0" in cmd
    assert "--memory=1g" in cmd
    assert "--pids-limit=128" in cmd
    assert "--cap-drop=ALL" in cmd
    assert "--security-opt=no-new-privileges:true" in cmd


def test_container_runtime_info_custom_capabilities():
    """Verifies custom capability mapping in ContainerRuntimeInfo."""
    info = ContainerRuntimeInfo(
        runtime_type=ContainerRuntimeType.PODMAN,
        is_available=True,
        capabilities={"custom_cap": True, "read_only_root": False},
    )
    d = info.to_dict()
    assert d["runtime_type"] == "podman"
    assert d["capabilities"]["custom_cap"] is True
    assert d["capabilities"]["read_only_root"] is False


def test_redact_container_output_empty_and_no_secrets():
    """Verifies edge cases when text is empty or contains no sensitive patterns."""
    assert redact_container_output("") == ""
    normal_text = "Standard log line: system operational on port 8080."
    assert redact_container_output(normal_text) == normal_text


