"""
AutoDev Interactive Session Manager (Phase 5 - Secure Interactive Debugging)
Manages lifecycle of interactive debugging sessions, enforces concurrency limits,
idle timeouts, lifetime ceilings, and audits session lifecycle events.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import time
from typing import Dict, List, Optional, Any
import uuid
import logging

from core.pty_adapter import BasePTYAdapter, SubprocessPTYAdapter
from core.terminal_authorization import TerminalAuthorizer, TerminalSecurityPolicy

logger = logging.getLogger(__name__)


class DebugSessionStatus(str, Enum):
    ACTIVE = "active"
    TERMINATED = "terminated"
    EXPIRED = "expired"
    IDLE_TIMEOUT = "idle_timeout"


@dataclass
class InteractiveDebugSession:
    session_id: str
    principal_id: str
    transaction_id: str
    sandbox_id: str
    worker_id: Optional[str]
    pty_adapter: BasePTYAdapter
    status: DebugSessionStatus = DebugSessionStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)
    duration_limit_seconds: float = 3600.0
    idle_timeout_seconds: float = 600.0

    @property
    def remaining_seconds(self) -> float:
        elapsed = time.time() - self.created_at
        return max(0.0, self.duration_limit_seconds - elapsed)

    @property
    def idle_seconds(self) -> float:
        return max(0.0, time.time() - self.last_activity_at)

    def is_expired(self) -> bool:
        return time.time() - self.created_at >= self.duration_limit_seconds

    def is_idle_timed_out(self) -> bool:
        return time.time() - self.last_activity_at >= self.idle_timeout_seconds

    def touch(self) -> None:
        self.last_activity_at = time.time()


class InteractiveSessionManager:
    """
    Coordinates creation, I/O routing, lifetime management, and termination
    of interactive debugging sessions attached to authorized sandboxes.
    """

    def __init__(
        self,
        authorizer: Optional[TerminalAuthorizer] = None,
        max_concurrent_sessions: int = 5,
        default_session_lifetime_sec: float = 3600.0,
        default_idle_timeout_sec: float = 600.0,
    ) -> None:
        self.authorizer = authorizer or TerminalAuthorizer()
        self.max_concurrent_sessions = max_concurrent_sessions
        self.default_session_lifetime_sec = default_session_lifetime_sec
        self.default_idle_timeout_sec = default_idle_timeout_sec
        self.sessions: Dict[str, InteractiveDebugSession] = {}
        self.session_audit_log: List[Dict[str, Any]] = []

    def create_session(
        self,
        principal_id: str,
        transaction_id: str,
        sandbox_id: str,
        worker_id: Optional[str] = None,
        command: Optional[List[str]] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        is_coordinator_host: bool = False,
    ) -> InteractiveDebugSession:
        """
        Authorize and instantiate an interactive debug session attached to a sandbox.
        """
        # Cleanup expired sessions first
        self.reap_stale_sessions()

        # Check concurrency limits
        active_count = sum(1 for s in self.sessions.values() if s.status == DebugSessionStatus.ACTIVE)
        if active_count >= self.max_concurrent_sessions:
            raise RuntimeError(f"Concurrent terminal session limit reached ({self.max_concurrent_sessions})")

        # Authorize session
        self.authorizer.authorize_session(
            principal_id=principal_id,
            transaction_id=transaction_id,
            sandbox_id=sandbox_id,
            worker_id=worker_id,
            is_coordinator_host=is_coordinator_host,
        )

        session_id = f"debug-{uuid.uuid4().hex[:8]}"
        adapter = SubprocessPTYAdapter(command=command, cwd=cwd, env=env)
        adapter.start()

        session = InteractiveDebugSession(
            session_id=session_id,
            principal_id=principal_id,
            transaction_id=transaction_id,
            sandbox_id=sandbox_id,
            worker_id=worker_id,
            pty_adapter=adapter,
            duration_limit_seconds=self.default_session_lifetime_sec,
            idle_timeout_seconds=self.default_idle_timeout_sec,
        )

        self.sessions[session_id] = session
        self._record_audit(session_id, "session_created", {"principal_id": principal_id, "sandbox_id": sandbox_id})
        return session

    def get_session(self, session_id: str) -> Optional[InteractiveDebugSession]:
        session = self.sessions.get(session_id)
        if session and session.status == DebugSessionStatus.ACTIVE:
            if session.is_expired():
                self.terminate_session(session_id, reason=DebugSessionStatus.EXPIRED)
            elif session.is_idle_timed_out():
                self.terminate_session(session_id, reason=DebugSessionStatus.IDLE_TIMEOUT)
            elif not session.pty_adapter.is_alive():
                self.terminate_session(session_id, reason=DebugSessionStatus.TERMINATED)
        return self.sessions.get(session_id)

    def write_input(self, session_id: str, data: str) -> bool:
        session = self.get_session(session_id)
        if not session or session.status != DebugSessionStatus.ACTIVE:
            return False
        session.touch()
        session.pty_adapter.write(data)
        return True

    def read_output(self, session_id: str, timeout_ms: int = 100) -> str:
        session = self.get_session(session_id)
        if not session or session.status != DebugSessionStatus.ACTIVE:
            return ""
        output = session.pty_adapter.read(timeout_ms=timeout_ms)
        if output:
            session.touch()
        return output

    def resize_session(self, session_id: str, cols: int, rows: int) -> bool:
        session = self.get_session(session_id)
        if not session or session.status != DebugSessionStatus.ACTIVE:
            return False
        session.pty_adapter.resize(cols, rows)
        return True

    def terminate_session(self, session_id: str, reason: DebugSessionStatus = DebugSessionStatus.TERMINATED) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False
        session.status = reason
        session.pty_adapter.terminate()
        self._record_audit(session_id, "session_terminated", {"reason": reason.value})
        return True

    def reap_stale_sessions(self) -> int:
        """Scan and terminate all expired or timed out sessions."""
        reaped = 0
        for sid, session in list(self.sessions.items()):
            if session.status == DebugSessionStatus.ACTIVE:
                if session.is_expired():
                    self.terminate_session(sid, DebugSessionStatus.EXPIRED)
                    reaped += 1
                elif session.is_idle_timed_out():
                    self.terminate_session(sid, DebugSessionStatus.IDLE_TIMEOUT)
                    reaped += 1
                elif not session.pty_adapter.is_alive():
                    self.terminate_session(sid, DebugSessionStatus.TERMINATED)
                    reaped += 1
        return reaped

    def _record_audit(self, session_id: str, event_type: str, details: Dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "event_type": event_type,
            "details": details,
        }
        self.session_audit_log.append(record)
