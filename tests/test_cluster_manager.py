"""
test_cluster_manager.py - Unit and integration tests for high-level ClusterManager (v2.9)
"""

import pytest
import shutil
import tempfile
from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_manager import ClusterManager
from core.cluster.cluster_state import JobStatus, TaskSpec


def test_cluster_manager_bootstrap_and_execution():
    temp_dir = tempfile.mkdtemp()
    try:
        config = ClusterConfig(
            cluster_name="autodev-test-cluster",
            storage_dir=temp_dir,
            checkpoint_storage_dir=f"{temp_dir}/checkpoints",
            heartbeat_interval=0.5,
        )
        cm = ClusterManager(config=config)
        cm.bootstrap_cluster(num_workers=4)

        status = cm.query_cluster()
        assert status["cluster_name"] == "autodev-test-cluster"
        assert status["healthy_workers"] == 4

        # Execute high-level cluster prompt
        result = cm.execute_cluster(
            prompt="Build high-performance distributed microservice",
            num_tasks=3,
            timeout=15.0,
        )

        assert result["status"] == JobStatus.COMPLETED.value
        assert result["tasks_count"] == 3
        assert result["progress_percentage"] == 100.0
        assert "mermaid_topology" in result

        # Verify full cluster report generation
        report = cm.generate_full_cluster_report()
        assert "# AutoDev Distributed Cluster Execution Report" in report
        assert "Cluster Operational Telemetry" in report

        cm.shutdown()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
