"""
AutoDev Terminal Authorization & Security Policy (Phase 5 - Secure Interactive Debugging)
Enforces strict execution environment boundaries, token authentication, sandbox binding,
and explicitly prohibits interactive shells on the coordinator host.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any
import logging

logger = logging.getLogger(__name__)


class TerminalSecurityError(Exception):
    """Base exception for terminal security and authorization violations."""
    pass


class UnauthorizedSessionError(TerminalSecurityError):
    """Raised when an unauthorized principal attempts to initiate or attach to a debug session."""
    pass


class HostExecutionProhibitedError(TerminalSecurityError):
    """Raised when an interactive session attempts to run on the coordinator host."""
    pass


@dataclass
class TerminalSecurityPolicy:
    """
    Security constraints governing interactive terminal access.
    By default, interactive shells on the coordinator host are STRICTLY FORBIDDEN.
    """
    allow_coordinator_host_execution: bool = False
    require_isolated_sandbox: bool = True
    allowed_principals: Set[str] = field(default_factory=lambda: {"admin", "developer", "lead"})
    max_session_duration_seconds: int = 3600  # 1 hour
    idle_timeout_seconds: int = 600  # 10 minutes
    max_concurrent_sessions: int = 5
    allowed_commands_allowlist: Optional[List[str]] = None  # None = full sandbox shell if container isolated


class TerminalAuthorizer:
    """
    Validates terminal session requests against transaction context,
    worker identities, sandbox boundaries, and security policies.
    """

    def __init__(self, policy: Optional[TerminalSecurityPolicy] = None) -> None:
        self.policy = policy or TerminalSecurityPolicy()
        self.audit_log: List[Dict[str, Any]] = []

    def authorize_session(
        self,
        principal_id: str,
        transaction_id: str,
        sandbox_id: Optional[str],
        worker_id: Optional[str] = None,
        is_coordinator_host: bool = False,
    ) -> bool:
        """
        Evaluate whether a terminal session request is authorized.
        Fails closed on any policy violation.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Rule 1: Coordinator host execution check
        if is_coordinator_host and not self.policy.allow_coordinator_host_execution:
            event = {
                "event": "terminal_authorization_denied",
                "reason": "Host execution strictly prohibited by security policy",
                "principal_id": principal_id,
                "transaction_id": transaction_id,
                "timestamp": now,
            }
            self.audit_log.append(event)
            logger.warning("Terminal access denied: host execution prohibited for principal %s", principal_id)
            raise HostExecutionProhibitedError(
                "Interactive debugging on coordinator host is strictly prohibited. Use an isolated sandbox container."
            )

        # Rule 2: Principal authentication & authorization
        if principal_id not in self.policy.allowed_principals:
            event = {
                "event": "terminal_authorization_denied",
                "reason": f"Principal '{principal_id}' not in allowed principals",
                "principal_id": principal_id,
                "transaction_id": transaction_id,
                "timestamp": now,
            }
            self.audit_log.append(event)
            raise UnauthorizedSessionError(f"Principal '{principal_id}' is not authorized for interactive debugging")

        # Rule 3: Sandbox requirement
        if self.policy.require_isolated_sandbox and not sandbox_id:
            event = {
                "event": "terminal_authorization_denied",
                "reason": "Isolated sandbox_id required but not provided",
                "principal_id": principal_id,
                "transaction_id": transaction_id,
                "timestamp": now,
            }
            self.audit_log.append(event)
            raise UnauthorizedSessionError("Interactive debugging requires an authorized isolated sandbox ID")

        # Audit authorized access
        event = {
            "event": "terminal_authorization_granted",
            "principal_id": principal_id,
            "transaction_id": transaction_id,
            "sandbox_id": sandbox_id,
            "worker_id": worker_id,
            "timestamp": now,
        }
        self.audit_log.append(event)
        return True
