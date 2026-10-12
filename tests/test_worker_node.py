"""
test_worker_node.py - Unit tests for autonomous WorkerNode execution (v2.9)
"""

import pytest
import shutil
import tempfile
from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import TaskSpec
from core.cluster.distributed_queue import DistributedQueue
from core.cluster.worker_node import WorkerNode


def test_worker_node_task_execution():
    temp_dir = tempfile.mkdtemp()
    try:
        config = ClusterConfig(storage_dir=temp_dir)
        q = DistributedQueue(config=config)
        worker = WorkerNode(
            node_id="worker-01",
            capabilities=["coding", "backend"],
            config=config,
            queue=q,
        )

        task = TaskSpec(
            task_id="task_backend_api",
            title="Implement User API",
            required_capabilities=["coding"],
            payload={
                "target_file": "src/user_api.py",
                "code_content": "def get_user(): return {'id': 1}",
                "memory_updates": {"api_status": "READY"},
            }
        )

        result = worker.execute_task(task)

        assert result["success"] is True
        assert result["task_id"] == "task_backend_api"
        assert len(result["artifacts"]) > 0
        assert worker.memory.get("api_status") == "READY"
        assert worker.info.total_tasks_completed == 1

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_worker_custom_handler():
    worker = WorkerNode(node_id="worker-custom", capabilities=["custom_skill"])

    def custom_handler(task, w_node):
        return {"result_data": f"Executed by {w_node.node_id} for {task.task_id}"}

    worker.register_handler("custom_skill", custom_handler)

    task = TaskSpec(task_id="custom_task_01", required_capabilities=["custom_skill"])
    res = worker.execute_task(task)

    assert res["success"] is True
    assert res["result"]["result_data"] == "Executed by worker-custom for custom_task_01"
