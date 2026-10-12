"""
Tests for AutoDev v2.5 Runtime Isolation Provider and Security Profiles.
"""

import os
import sys
import tempfile
import pytest
from core.isolation_provider import (
    IsolationCapabilities,
    IsolationPolicy,
    IsolationProfile,
    IsolationUnavailableError,
    IsolationViolationError,
    LocalProcessIsolationProvider,
    PROFILE_DEVELOPMENT,
    PROFILE_STANDARD,
    PROFILE_STRICT,
    PROFILE_UNTRUSTED_CODE,
)


def test_isolation_capabilities_inspection():
    provider = LocalProcessIsolationProvider()
    caps = provider.get_capabilities()

    assert caps.backend_name == "local_process"
    assert caps.platform_os == sys.platform
    assert isinstance(caps.kernel_version, str)
    assert isinstance(caps.supports_ebpf, bool)


def test_isolation_sandbox_execution_success(tmp_path):
    provider = LocalProcessIsolationProvider()
    handle = provider.create_sandbox(
        workspace_dir=str(tmp_path),
        profile=PROFILE_DEVELOPMENT,
    )

    # Simple echo command
    result = provider.execute_in_sandbox(
        handle=handle,
        command=[sys.executable, "-c", "print('hello_sandbox')"],
    )

    assert result.exit_code == 0
    assert "hello_sandbox" in result.stdout
    assert len(result.violations) == 0
    assert result.is_success is True

    provider.destroy_sandbox(handle)
    assert handle.is_active is False


def test_isolation_prohibited_command_denial(tmp_path):
    provider = LocalProcessIsolationProvider()
    handle = provider.create_sandbox(
        workspace_dir=str(tmp_path),
        profile=PROFILE_STRICT,
        policy=IsolationPolicy(
            prohibited_commands=["reboot", "shutdown", "format"],
        ),
    )

    with pytest.raises(IsolationViolationError) as exc_info:
        provider.execute_in_sandbox(
            handle=handle,
            command=["shutdown", "-r", "now"],
        )

    assert "prohibited directive" in str(exc_info.value)
    audits = provider.get_audit_trail()
    assert len(audits) >= 1
    assert audits[-1].action_taken == "denied"


def test_isolation_prohibited_host_path_denial(tmp_path):
    provider = LocalProcessIsolationProvider()
    handle = provider.create_sandbox(
        workspace_dir=str(tmp_path),
        profile=PROFILE_STANDARD,
        policy=IsolationPolicy(
            prohibited_host_paths=["/etc/shadow", "~/.ssh", "C:\\Windows\\System32\\config"],
        ),
    )

    with pytest.raises(IsolationViolationError):
        provider.execute_in_sandbox(
            handle=handle,
            command=["cat", "/etc/shadow"],
        )


def test_isolation_timeout_enforcement(tmp_path):
    provider = LocalProcessIsolationProvider()
    handle = provider.create_sandbox(
        workspace_dir=str(tmp_path),
        profile=PROFILE_STRICT,
    )

    # Run sleep for 2s with a 0.2s timeout
    result = provider.execute_in_sandbox(
        handle=handle,
        command=[sys.executable, "-c", "import time; time.sleep(2.0)"],
        timeout=0.2,
    )

    assert result.exit_code == 124
    assert result.is_fail_closed is True
    assert len(result.violations) == 1
    assert result.violations[0].violation_type == "resource_exhaustion"


def test_isolation_fail_closed_on_unsupported_ebpf(tmp_path):
    provider = LocalProcessIsolationProvider(eBPF_backend=None)
    # Policy mandates eBPF monitoring on platform where it's unavailable
    policy = IsolationPolicy(
        require_ebpf_monitoring=True,
        fail_closed_on_unsupported=True,
    )

    # If capabilities.supports_ebpf is False, creating sandbox must fail closed
    caps = provider.get_capabilities()
    if not caps.supports_ebpf:
        with pytest.raises(IsolationUnavailableError):
            provider.create_sandbox(str(tmp_path), policy=policy)
