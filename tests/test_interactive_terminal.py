"""
Unit and Integration Tests for Secure Interactive Debugging Terminal (Phase 5 & Phase 8.4)
"""

import json
import time
import pytest

from core.terminal_authorization import (
    TerminalSecurityPolicy,
    TerminalAuthorizer,
    TerminalSecurityError,
    UnauthorizedSessionError,
    HostExecutionProhibitedError,
)
from core.pty_adapter import SubprocessPTYAdapter
from core.interactive_session_manager import (
    DebugSessionStatus,
    InteractiveDebugSession,
    InteractiveSessionManager,
)
from core.terminal_gateway import TerminalGateway


class TestTerminalAuthorization:
    def test_coordinator_host_execution_strictly_prohibited(self):
        policy = TerminalSecurityPolicy(allow_coordinator_host_execution=False)
        auth = TerminalAuthorizer(policy)

        # Attempt to run on coordinator host must fail closed
        with pytest.raises(HostExecutionProhibitedError):
            auth.authorize_session(
                principal_id="developer",
                transaction_id="tx-1",
                sandbox_id="sandbox-1",
                is_coordinator_host=True,
            )

    def test_unauthorized_principal_denied(self):
        policy = TerminalSecurityPolicy(allowed_principals={"admin", "lead"})
        auth = TerminalAuthorizer(policy)

        with pytest.raises(UnauthorizedSessionError):
            auth.authorize_session(
                principal_id="untrusted-user",
                transaction_id="tx-1",
                sandbox_id="sandbox-1",
                is_coordinator_host=False,
            )

    def test_missing_sandbox_id_denied(self):
        policy = TerminalSecurityPolicy(require_isolated_sandbox=True)
        auth = TerminalAuthorizer(policy)

        with pytest.raises(UnauthorizedSessionError):
            auth.authorize_session(
                principal_id="developer",
                transaction_id="tx-1",
                sandbox_id=None,
                is_coordinator_host=False,
            )

    def test_authorized_sandbox_session_granted(self):
        policy = TerminalSecurityPolicy(allowed_principals={"developer"})
        auth = TerminalAuthorizer(policy)

        authorized = auth.authorize_session(
            principal_id="developer",
            transaction_id="tx-100",
            sandbox_id="container-sandbox-99",
            worker_id="worker-node-1",
            is_coordinator_host=False,
        )
        assert authorized is True
        assert len(auth.audit_log) == 1
        assert auth.audit_log[0]["event"] == "terminal_authorization_granted"


class TestInteractiveSessionManagerAndGateway:
    def test_session_lifecycle_and_io(self):
        authorizer = TerminalAuthorizer()
        mgr = InteractiveSessionManager(authorizer=authorizer)

        session = mgr.create_session(
            principal_id="developer",
            transaction_id="tx-123",
            sandbox_id="sandbox-test-1",
        )
        assert session.session_id.startswith("debug-")
        assert session.status == DebugSessionStatus.ACTIVE
        assert session.remaining_seconds > 0

        # Send input
        mgr.write_input(session.session_id, "echo AutoDevTest\n")
        time.sleep(0.3)

        # Read output
        output = mgr.read_output(session.session_id, timeout_ms=300)
        assert len(output) >= 0

        # Terminate
        terminated = mgr.terminate_session(session.session_id)
        assert terminated is True
        assert mgr.get_session(session.session_id).status == DebugSessionStatus.TERMINATED

    def test_session_concurrency_limit_enforced(self):
        authorizer = TerminalAuthorizer()
        mgr = InteractiveSessionManager(authorizer=authorizer, max_concurrent_sessions=2)

        s1 = mgr.create_session("developer", "tx-1", "sbx-1")
        s2 = mgr.create_session("developer", "tx-2", "sbx-2")

        with pytest.raises(RuntimeError, match="limit reached"):
            mgr.create_session("developer", "tx-3", "sbx-3")

        mgr.terminate_session(s1.session_id)
        mgr.terminate_session(s2.session_id)

    def test_session_resizing(self):
        authorizer = TerminalAuthorizer()
        mgr = InteractiveSessionManager(authorizer=authorizer)
        s = mgr.create_session("developer", "tx-1", "sbx-1")
        resized = mgr.resize_session(s.session_id, cols=120, rows=40)
        assert resized is True
        mgr.terminate_session(s.session_id)

    def test_terminal_gateway_frame_protocol(self):
        authorizer = TerminalAuthorizer()
        mgr = InteractiveSessionManager(authorizer=authorizer)
        gateway = TerminalGateway(session_manager=mgr)

        # Create session frame
        create_msg = json.dumps({
            "action": "create",
            "principal_id": "developer",
            "transaction_id": "tx-gw-1",
            "sandbox_id": "sbx-gw-1",
            "is_coordinator_host": False,
        })
        resp = gateway.handle_client_message(create_msg)
        assert resp["type"] == "created"
        sid = resp["session_id"]

        # Input frame
        input_msg = json.dumps({
            "action": "input",
            "session_id": sid,
            "data": "help\n",
        })
        input_resp = gateway.handle_client_message(input_msg)
        assert input_resp["type"] == "input_ack"

        # Status frame
        status_msg = json.dumps({"action": "status", "session_id": sid})
        status_resp = gateway.handle_client_message(status_msg)
        assert status_resp["type"] == "status"
        assert status_resp["status"] == "active"

        # Resize frame
        resize_msg = json.dumps({"action": "resize", "session_id": sid, "cols": 100, "rows": 30})
        resize_resp = gateway.handle_client_message(resize_msg)
        assert resize_resp["type"] == "resize_ack"

        # Terminate frame
        term_msg = json.dumps({"action": "terminate", "session_id": sid})
        term_resp = gateway.handle_client_message(term_msg)
        assert term_resp["type"] == "terminated"

    def test_gateway_blocks_host_execution(self):
        gateway = TerminalGateway()
        host_msg = json.dumps({
            "action": "create",
            "principal_id": "developer",
            "transaction_id": "tx-attack",
            "sandbox_id": "none",
            "is_coordinator_host": True,
        })
        resp = gateway.handle_client_message(host_msg)
        assert resp["type"] == "security_violation"
        assert "strictly prohibited" in resp["message"]

    def test_gateway_malformed_json_handling(self):
        gateway = TerminalGateway()
        resp = gateway.handle_client_message("NOT_JSON_DATA{{{")
        assert resp["type"] == "error"
        assert "Malformed JSON" in resp["message"]

    def test_gateway_auth_token_validator(self):
        gateway = TerminalGateway(auth_token_validator=lambda tok: tok == "valid-secret-token")
        msg = json.dumps({"action": "status", "session_id": "s1"})

        # Bad token
        resp_bad = gateway.handle_client_message(msg, auth_token="wrong-token")
        assert resp_bad["type"] == "error"
        assert "Invalid or expired" in resp_bad["message"]
