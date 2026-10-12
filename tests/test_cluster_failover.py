"""
test_cluster_failover.py - Integration tests for worker crash recovery and master failover (v2.9)
"""

import pytest
import shutil
import tempfile
import time
from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_manager import ClusterManager
from core.cluster.cluster_state import NodeStatus, TaskExecutionStatus, TaskSpec


def test_worker_crash_and_task_recovery():
    temp_dir = tempfile.mkdtemp()
    try:
        config = ClusterConfig(
            storage_dir=temp_dir,
            heartbeat_interval=0.5,
            worker_timeout=1.5,
            queue_visibility_timeout=1.0,
        )
        cm = ClusterManager(config=config)
        cm.bootstrap_cluster(num_workers=3)

        # Worker 1 will be crashed
        worker1_id = "worker-node-01"

        # Simulate failure
        assert cm.simulate_worker_failure(worker1_id) is True

        node = cm.master.registry.get_node(worker1_id)
        assert node.status == NodeStatus.OFFLINE

        # Other healthy workers should remain active
        healthy_workers = cm.master.registry.get_healthy_workers()
        assert len(healthy_workers) == 2

        # Submitting a job should still succeed using remaining workers
        tasks = [
            TaskSpec(task_id="recover_task_01", title="Resilient Task 1"),
            TaskSpec(task_id="recover_task_02", title="Resilient Task 2"),
        ]
        job = cm.execute_job_sync(title="Failover Test Job", tasks=tasks, timeout=10.0)
        assert job.is_finished is True
        assert job.progress_percentage == 100.0

        cm.shutdown()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_master_failover_simulation():
    temp_dir = tempfile.mkdtemp()
    try:
        config = ClusterConfig(
            storage_dir=temp_dir,
            backup_masters=["backup-master-01", "backup-master-02"],
            split_brain_quorum_size=2,
        )
        cm = ClusterManager(config=config)
        cm.bootstrap_cluster(num_workers=2)

        initial_leader = cm.master.election.current_leader
        assert initial_leader == "master-node-01"

        # Simulate master failure
        new_leader = cm.simulate_master_failover()
        assert new_leader != initial_leader
        assert new_leader in ["backup-master-01", "backup-master-02"]

        cm.shutdown()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
