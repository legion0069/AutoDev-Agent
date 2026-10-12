"""
AutoDev Terminal Gateway (Phase 5 - Secure Interactive Debugging)
WebSocket/JSON streaming gateway bridging browser dashboard terminals
with authorized interactive debugging sessions.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Dict, Optional, Any, Callable
import logging

from core.interactive_session_manager import (
    InteractiveSessionManager,
    InteractiveDebugSession,
    DebugSessionStatus,
)
from core.terminal_authorization import (
    TerminalSecurityError,
    UnauthorizedSessionError,
    HostExecutionProhibitedError,
)

logger = logging.getLogger(__name__)


class TerminalGateway:
    """
    Message router and protocol handler for interactive WebSocket terminal sessions.
    """

    def __init__(
        self,
        session_manager: Optional[InteractiveSessionManager] = None,
        auth_token_validator: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self.session_manager = session_manager or InteractiveSessionManager()
        self.auth_token_validator = auth_token_validator or (lambda token: bool(token and token.strip()))

    def handle_client_message(self, raw_message: str, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a single JSON message frame from client terminal.
        """
        # Validate auth token if provided
        if auth_token and not self.auth_token_validator(auth_token):
            return {"type": "error", "message": "Invalid or expired authentication token"}

        try:
            payload = json.loads(raw_message)
        except Exception as e:
            return {"type": "error", "message": f"Malformed JSON frame: {e}"}

        action = payload.get("action", "")

        try:
            if action == "create":
                principal_id = payload.get("principal_id", "anonymous")
                transaction_id = payload.get("transaction_id", "")
                sandbox_id = payload.get("sandbox_id", "")
                worker_id = payload.get("worker_id")
                is_coordinator_host = payload.get("is_coordinator_host", False)

                session = self.session_manager.create_session(
                    principal_id=principal_id,
                    transaction_id=transaction_id,
                    sandbox_id=sandbox_id,
                    worker_id=worker_id,
                    is_coordinator_host=is_coordinator_host,
                )
                return {
                    "type": "created",
                    "session_id": session.session_id,
                    "transaction_id": session.transaction_id,
                    "sandbox_id": session.sandbox_id,
                    "remaining_seconds": session.remaining_seconds,
                    "status": session.status.value,
                }

            elif action == "input":
                session_id = payload.get("session_id", "")
                data = payload.get("data", "")
                success = self.session_manager.write_input(session_id, data)
                if not success:
                    return {"type": "error", "session_id": session_id, "message": "Failed to write input to session"}
                return {"type": "input_ack", "session_id": session_id}

            elif action == "read":
                session_id = payload.get("session_id", "")
                timeout_ms = payload.get("timeout_ms", 100)
                output = self.session_manager.read_output(session_id, timeout_ms=timeout_ms)
                session = self.session_manager.get_session(session_id)
                status = session.status.value if session else "terminated"
                return {
                    "type": "output",
                    "session_id": session_id,
                    "data": output,
                    "status": status,
                    "remaining_seconds": session.remaining_seconds if session else 0.0,
                }

            elif action == "resize":
                session_id = payload.get("session_id", "")
                cols = int(payload.get("cols", 80))
                rows = int(payload.get("rows", 24))
                success = self.session_manager.resize_session(session_id, cols, rows)
                return {"type": "resize_ack", "session_id": session_id, "success": success}

            elif action == "terminate":
                session_id = payload.get("session_id", "")
                success = self.session_manager.terminate_session(session_id)
                return {"type": "terminated", "session_id": session_id, "success": success}

            elif action == "status":
                session_id = payload.get("session_id", "")
                session = self.session_manager.get_session(session_id)
                if not session:
                    return {"type": "status", "session_id": session_id, "status": "not_found"}
                return {
                    "type": "status",
                    "session_id": session_id,
                    "status": session.status.value,
                    "remaining_seconds": session.remaining_seconds,
                    "idle_seconds": session.idle_seconds,
                }

            else:
                return {"type": "error", "message": f"Unknown terminal action: {action}"}

        except TerminalSecurityError as tse:
            return {"type": "security_violation", "message": str(tse)}
        except Exception as ex:
            logger.exception("Unexpected error handling terminal gateway message: %s", ex)
            return {"type": "error", "message": f"Internal gateway error: {ex}"}
