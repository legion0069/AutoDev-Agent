"""
Tests for AutoDev v2.5 Linux eBPF Security Monitoring & Inspection Backend.
"""

import sys
import pytest
from core.ebpf_isolation_backend import (
    EBPFCapabilityReport,
    EBPFEvent,
    EBPFIsolationBackend,
)


def test_ebpf_capability_inspection():
    backend = EBPFIsolationBackend(simulate_mode=False)
    caps = backend.inspect_capabilities()

    assert isinstance(caps.is_linux, bool)
    assert isinstance(caps.kernel_release, str)
    assert isinstance(caps.rejection_reasons, list)

    if not sys.platform.startswith("linux"):
        assert caps.can_enforce is False
        assert any("not Linux" in r for r in caps.rejection_reasons)


def test_ebpf_simulation_hooks_and_violations():
    backend = EBPFIsolationBackend(simulate_mode=True)
    assert backend.is_available() is True

    # Attach hooks
    attached = backend.attach_policy_hooks(
        blocked_commands={"nmap", "nc"},
        blocked_paths={"/etc/shadow", "/root/.ssh"},
    )
    assert attached is True

    # Normal event
    e1 = backend.record_probe_event("process_exec", pid=101, comm="python", target="/usr/bin/python")
    assert e1.is_violation is False

    # Blocked executable event
    e2 = backend.record_probe_event("process_exec", pid=102, comm="nc", target="/usr/bin/nc")
    assert e2.is_violation is True
    assert "Prohibited executable" in e2.details["violation_reason"]

    # Blocked file access event
    e3 = backend.record_probe_event("file_open", pid=103, comm="cat", target="/etc/shadow")
    assert e3.is_violation is True
    assert "Prohibited host file" in e3.details["violation_reason"]

    # Ptrace escape event
    e4 = backend.record_probe_event("ptrace_attach", pid=104, comm="gdb", target="1")
    assert e4.is_violation is True

    violations = backend.get_violations()
    assert len(violations) == 3

    backend.detach_hooks()
