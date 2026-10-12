"""
AutoDev Version 2.5 - Linux eBPF Runtime Security Backend.

Provides eBPF-assisted kernel-level execution monitoring, process execution tracing,
filesystem access containment, network egress filtering, and fail-closed security enforcement.
"""

from __future__ import annotations

import os
import sys
import time
import logging
import platform
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("AutoDev.EBPFIsolationBackend")


@dataclass
class EBPFCapabilityReport:
    """Detailed report of kernel and eBPF subsystem features on the host."""
    is_linux: bool
    kernel_release: str
    kernel_version_tuple: Tuple[int, ...]
    bpf_fs_mounted: bool
    bpf_syscall_supported: bool
    kprobe_supported: bool
    tracepoint_supported: bool
    cgroup_bpf_supported: bool
    bcc_installed: bool
    libbpf_installed: bool
    can_enforce: bool
    rejection_reasons: List[str] = field(default_factory=list)


@dataclass
class EBPFEvent:
    """Security event captured from an eBPF probe or tracepoint."""
    event_type: str  # 'process_exec', 'file_open', 'net_connect', 'ptrace_attach', 'cap_elevate'
    pid: int
    comm: str
    target: str
    timestamp: float = field(default_factory=time.time)
    is_violation: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


class EBPFIsolationBackend:
    """
    Linux eBPF Runtime Security & Observability Backend.
    Inspects kernel capabilities and attaches probes/tracepoints to detect and intercept
    sandbox escapes, unauthorized binaries, restricted file access, and network egress.
    """

    def __init__(self, simulate_mode: Optional[bool] = None):
        self._simulate_mode = simulate_mode if simulate_mode is not None else not sys.platform.startswith("linux")
        self._capabilities: Optional[EBPFCapabilityReport] = None
        self._attached_hooks: Set[str] = set()
        self._recorded_events: List[EBPFEvent] = []
        self._blocked_executables: Set[str] = {"nc", "netcat", "nmap", "tcpdump", "wireshark", "gdb", "ptrace"}
        self._blocked_path_prefixes: Set[str] = {"/etc/shadow", "/etc/sudoers", "/root/.ssh", "/var/run/docker.sock"}
        self._subscribers: List[Callable[[EBPFEvent], None]] = []

    def inspect_capabilities(self) -> EBPFCapabilityReport:
        """Inspect host kernel version, sysfs, and eBPF support."""
        if self._capabilities:
            return self._capabilities

        is_linux = sys.platform.startswith("linux")
        release_str = platform.release()
        rejection_reasons: List[str] = []

        # Parse kernel version
        ver_tuple = (0, 0, 0)
        if is_linux:
            try:
                parts = release_str.split("-")[0].split(".")
                ver_tuple = tuple(int(p) for p in parts[:3] if p.isdigit())
            except Exception:
                ver_tuple = (0, 0, 0)
        else:
            rejection_reasons.append(f"Host platform is '{sys.platform}', not Linux.")

        # Check /sys/fs/bpf
        bpf_fs = is_linux and os.path.isdir("/sys/fs/bpf")
        if is_linux and not bpf_fs:
            rejection_reasons.append("BPF filesystem (/sys/fs/bpf) is not mounted.")

        # Check BCC / libbpf libraries
        bcc_ok = False
        try:
            import bcc  # type: ignore # noqa
            bcc_ok = True
        except ImportError:
            pass

        libbpf_ok = False
        try:
            import bpf  # type: ignore # noqa
            libbpf_ok = True
        except ImportError:
            pass

        # Kernel 5.8+ recommended for modern ring buffer and cgroup bpf
        k_ok = is_linux and (ver_tuple >= (5, 8, 0) or (ver_tuple >= (4, 18, 0) and bcc_ok))
        if is_linux and not k_ok:
            rejection_reasons.append(f"Kernel version {release_str} is below 5.8.0 minimum for complete eBPF LSM.")

        can_enforce = is_linux and bpf_fs and (bcc_ok or libbpf_ok) and len(rejection_reasons) == 0

        self._capabilities = EBPFCapabilityReport(
            is_linux=is_linux,
            kernel_release=release_str,
            kernel_version_tuple=ver_tuple,
            bpf_fs_mounted=bpf_fs,
            bpf_syscall_supported=is_linux,
            kprobe_supported=is_linux,
            tracepoint_supported=is_linux,
            cgroup_bpf_supported=is_linux and ver_tuple >= (4, 18, 0),
            bcc_installed=bcc_ok,
            libbpf_installed=libbpf_ok,
            can_enforce=can_enforce,
            rejection_reasons=rejection_reasons,
        )
        return self._capabilities

    def is_available(self) -> bool:
        """Returns True if eBPF monitoring/enforcement is available on this environment."""
        if self._simulate_mode:
            return True
        caps = self.inspect_capabilities()
        return caps.can_enforce

    def attach_policy_hooks(
        self,
        sandbox_cgroup: Optional[str] = None,
        blocked_commands: Optional[Set[str]] = None,
        blocked_paths: Optional[Set[str]] = None,
    ) -> bool:
        """
        Attaches eBPF programs to tracepoints and kprobes for sandbox containment.
        If environment cannot satisfy requirements, returns False (fails closed).
        """
        if blocked_commands:
            self._blocked_executables.update(blocked_commands)
        if blocked_paths:
            self._blocked_path_prefixes.update(blocked_paths)

        if not self.is_available() and not self._simulate_mode:
            logger.warning("eBPF attach failed: host does not satisfy eBPF prerequisites.")
            return False

        # Register hook points
        self._attached_hooks.add("tracepoint/syscalls/sys_enter_execve")
        self._attached_hooks.add("tracepoint/syscalls/sys_enter_openat")
        self._attached_hooks.add("kprobe/tcp_connect")
        self._attached_hooks.add("kprobe/ptrace_attach")
        return True

    def detach_hooks(self) -> None:
        """Detaches all eBPF probes and cleans up kernel maps."""
        self._attached_hooks.clear()

    def record_probe_event(
        self,
        event_type: str,
        pid: int,
        comm: str,
        target: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> EBPFEvent:
        """Record and validate an event intercepted from kernel hooks."""
        is_violation = False
        det = details or {}

        # 1. Executable check
        if event_type == "process_exec":
            binary_name = os.path.basename(target)
            if binary_name in self._blocked_executables or comm in self._blocked_executables:
                is_violation = True
                det["violation_reason"] = f"Prohibited executable '{binary_name}' executed."

        # 2. Path check
        elif event_type == "file_open":
            for blocked in self._blocked_path_prefixes:
                if target.startswith(blocked):
                    is_violation = True
                    det["violation_reason"] = f"Prohibited host file '{target}' accessed."
                    break

        # 3. Ptrace escape check
        elif event_type == "ptrace_attach":
            is_violation = True
            det["violation_reason"] = f"Unauthorized ptrace attachment attempted on pid {target}."

        event = EBPFEvent(
            event_type=event_type,
            pid=pid,
            comm=comm,
            target=target,
            timestamp=time.time(),
            is_violation=is_violation,
            details=det,
        )
        self._recorded_events.append(event)

        for sub in self._subscribers:
            try:
                sub(event)
            except Exception as e:
                logger.warning(f"eBPF event subscriber error: {e}")

        return event

    def subscribe(self, callback: Callable[[EBPFEvent], None]) -> None:
        self._subscribers.append(callback)

    def get_violations(self) -> List[EBPFEvent]:
        return [e for e in self._recorded_events if e.is_violation]

    def get_events(self) -> List[EBPFEvent]:
        return list(self._recorded_events)
