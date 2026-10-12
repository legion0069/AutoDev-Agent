"""
test_remote_worker_cli.py - Unit tests for Remote Worker CLI Entrypoint (v2.3)
"""

import pytest
from core.remote_worker_cli import parse_args


def test_cli_parse_args_minimal():
    args = parse_args(["--worker-id", "cli-node-1"])
    assert args.worker_id == "cli-node-1"
    assert args.host == "127.0.0.1"
    assert args.port == 50051
    assert args.max_concurrency == 2
    assert args.use_tls is False


def test_cli_parse_args_full_options():
    args = parse_args([
        "--worker-id", "cli-node-secure",
        "--worker-name", "Secure Node",
        "--host", "10.0.0.5",
        "--port", "8443",
        "--workspace", "/tmp/ws",
        "--use-tls",
        "--ca-cert", "/path/ca.crt",
        "--client-cert", "/path/client.crt",
        "--client-key", "/path/client.key",
        "--auth-token", "tok-xyz",
        "--max-concurrency", "8",
        "--poll-interval", "0.5",
    ])
    assert args.worker_id == "cli-node-secure"
    assert args.worker_name == "Secure Node"
    assert args.host == "10.0.0.5"
    assert args.port == 8443
    assert args.workspace == "/tmp/ws"
    assert args.use_tls is True
    assert args.ca_cert == "/path/ca.crt"
    assert args.client_cert == "/path/client.crt"
    assert args.client_key == "/path/client.key"
    assert args.auth_token == "tok-xyz"
    assert args.max_concurrency == 8
    assert args.poll_interval == 0.5


def test_cli_parse_args_missing_mandatory_worker_id():
    with pytest.raises(SystemExit):
        parse_args([])
