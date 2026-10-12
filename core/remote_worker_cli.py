"""
remote_worker_cli.py - Standalone CLI Entrypoint for AutoDev Remote Worker Node (v2.3)

Allows starting and running an authenticated remote worker process:
    python -m core.remote_worker_cli --worker-id node-01 --host 127.0.0.1 --port 50051
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import sys
import time

from core.remote_worker_transport import TransportConfig
from core.grpc_worker_client import GrpcWorkerClient
from core.worker_protocol import WorkerCapabilities

logger = logging.getLogger("AutoDev.RemoteWorkerCLI")


def parse_args(args=None):
    parser = argparse.ArgumentParser(description="AutoDev Version 2.3 Remote Worker Node")
    parser.add_argument("--worker-id", type=str, required=True, help="Unique worker identifier")
    parser.add_argument("--worker-name", type=str, default=None, help="Human-readable worker name")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Coordinator host address")
    parser.add_argument("--port", type=int, default=50051, help="Coordinator port")
    parser.add_argument("--workspace", type=str, default="./remote_workspace", help="Local worker workspace root")
    parser.add_argument("--use-tls", action="store_true", help="Enable mutual TLS")
    parser.add_argument("--ca-cert", type=str, default=None, help="Root CA certificate path")
    parser.add_argument("--client-cert", type=str, default=None, help="Worker client certificate path")
    parser.add_argument("--client-key", type=str, default=None, help="Worker client private key path")
    parser.add_argument("--auth-token", type=str, default=None, help="Bearer authentication token")
    parser.add_argument("--max-concurrency", type=int, default=2, help="Max concurrent operations")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Task polling interval in seconds")
    return parser.parse_args(args)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    args = parse_args()

    cfg = TransportConfig(
        host=args.host,
        port=args.port,
        use_tls=args.use_tls,
        ca_cert_path=args.ca_cert,
        client_cert_path=args.client_cert,
        client_key_path=args.client_key,
        auth_token=args.auth_token,
    )

    caps = WorkerCapabilities(
        max_concurrency=args.max_concurrency,
        supported_runtimes=["process", "container"],
    )

    client = GrpcWorkerClient(
        worker_id=args.worker_id,
        worker_name=args.worker_name or f"RemoteWorker-{args.worker_id}",
        workspace_root=args.workspace,
        config=cfg,
        capabilities=caps,
    )

    logger.info("Connecting remote worker '%s' to %s:%d...", args.worker_id, args.host, args.port)
    try:
        client.connect()
        logger.info("Worker '%s' connected and listening for tasks...", args.worker_id)
        while True:
            client.poll_and_execute_task()
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        logger.info("Shutting down worker...")
        client.disconnect()
    except Exception as exc:
        logger.error("Worker encountered fatal error: %s", exc)
        client.disconnect()
        sys.exit(1)


if __name__ == "__main__":
    main()
