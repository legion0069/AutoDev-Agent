"""
Secure Interactive Debugging Terminal Edge Case Tests (Phase 8.4)
Exercises environment variable secret sanitization, session idle timeouts,
ring buffer capacity limits, and WebSocket gateway frame validation.
"""

import os
import time
import json
import pytest

from core.pty_adapter import SubprocessPTYAdapter
from core.terminal_authorization import TerminalAuthorizer, TerminalSecurityPolicy
from core.interactive_session_manager import (
    InteractiveSessionManager,
    InteractiveDebugSession,
    DebugSessionStatus,
)
from core.terminal_gateway import TerminalGateway


class TestInteractiveTerminalEdgeCases:
    def test_environment_sanitization_strips_secrets(self):
        dirty_env = {
            "OPENAI_API_KEY": "sk-secret1234567890",
            "DATABASE_PASSWORD": "supersecretpassword",
            "COORDINATOR_AUTH_TOKEN": "bearer-token-val",
            "BENIGN_VAR": "harmless_value",
        }
        adapter = SubprocessPTYAdapter(env=dirty_env)
        sanitized = adapter.env

        assert "OPENAI_API_KEY" not in sanitized
        assert "DATABASE_PASSWORD" not in sanitized
        assert "COORDINATOR_AUTH_TOKEN" not in sanitized
        assert sanitized.get("BENIGN_VAR") == "harmless_value"
        assert sanitized.get("AUTODEV_DEBUG_SESSION") == "1"

    def test_session_idle_timeout_reaping(self):
        auth = TerminalAuthorizer(TerminalSecurityPolicy(allowed_principals={"tester"}))
        mgr = InteractiveSessionManager(
            authorizer=auth,
            default_session_lifetime_sec=100.0,
            default_idle_timeout_sec=0.1,  # 100ms idle timeout
        )
        session = mgr.create_session("tester", "tx-idle", "sbx-idle")
        assert session.status == DebugSessionStatus.ACTIVE

        # Sleep past idle timeout
        time.sleep(0.2)
        reaped = mgr.reap_stale_sessions()
        assert reaped == 1

        checked_session = mgr.get_session(session.session_id)
        assert checked_session.status == DebugSessionStatus.IDLE_TIMEOUT

    def test_session_lifetime_expiry(self):
        auth = TerminalAuthorizer(TerminalSecurityPolicy(allowed_principals={"tester"}))
        mgr = InteractiveSessionManager(
            authorizer=auth,
            default_session_lifetime_sec=0.1,  # 100ms lifetime
            default_idle_timeout_sec=100.0,
        )
        session = mgr.create_session("tester", "tx-exp", "sbx-exp")

        time.sleep(0.2)
        reaped = mgr.reap_stale_sessions()
        assert reaped == 1
        assert mgr.get_session(session.session_id).status == DebugSessionStatus.EXPIRED

    def test_gateway_invalid_action_returns_error(self):
        gateway = TerminalGateway()
        resp = gateway.handle_client_message(json.dumps({"action": "unsupported_action"}))
        assert resp["type"] == "error"
        assert "Unknown terminal action" in resp["message"]

    def test_gateway_read_nonexistent_session(self):
        gateway = TerminalGateway()
        resp = gateway.handle_client_message(json.dumps({"action": "read", "session_id": "nonexistent"}))
        assert resp["type"] == "output"
        assert resp["data"] == ""
        assert resp["status"] == "terminated"
