"""
test_master_node.py - Unit tests for MasterNode coordination and job execution (v2.9)
"""

import pytest
import shutil
import tempfile
import time
from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import JobStatus, NodeInfo, NodeRole, TaskSpec
from core.cluster.master_node import MasterNode
from core.cluster.worker_node import WorkerNode


def test_master_node_job_lifecycle():
    temp_dir = tempfile.mkdtemp()
    try:
        config = ClusterConfig(storage_dir=temp_dir, heartbeat_interval=0.5, checkpoint_interval=5.0)
        master = MasterNode(node_id="master-01", config=config)
        master.start(auto_elect=True)

        # Register and start worker
        worker = WorkerNode(
            node_id="worker-01",
            capabilities=["planning", "coding", "general"],
            config=config,
            queue=master.queue,
            lock_manager=master.lock_manager,
            artifact_sync=master.artifact_sync,
            memory=master.memory,
            heartbeat_callback=lambda nid, cpu, mem, active, lat, meta: master.heartbeat_manager.record_node_heartbeat(nid, cpu, mem, active, lat, meta),
        )
        master.registry.register_node(worker.info)
        worker.start()

        # Submit job
        tasks = [
            TaskSpec(task_id="T1", title="Plan Architecture", required_capabilities=["planning"]),
            TaskSpec(task_id="T2", title="Implement Code", required_capabilities=["coding"], dependencies=["T1"]),
        ]

        job_id = master.submit_job(title="Test Job", tasks=tasks)
        assert job_id.startswith("job_")

        # Wait for job completion
        job = master.wait_for_job(job_id=job_id, timeout=10.0)
        assert job.status == JobStatus.COMPLETED
        assert job.progress_percentage == 100.0

        status = master.get_cluster_status()
        assert status["completed_jobs"] == 1
        assert status["queue_depth"] == 0

        worker.stop()
        master.stop()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
