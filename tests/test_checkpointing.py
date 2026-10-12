"""
test_checkpointing.py - Unit tests for persistent DistributedCheckpointManager (v2.9)
"""

import pytest
import shutil
import tempfile
from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import DistributedClusterMemory, NodeInfo, NodeRole, TaskSpec
from core.cluster.distributed_checkpoint import DistributedCheckpointManager
from core.cluster.distributed_lock_manager import DistributedLockManager
from core.cluster.distributed_queue import DistributedQueue
from core.cluster.node_registry import NodeRegistry


def test_atomic_checkpoint_creation_and_recovery():
    temp_dir = tempfile.mkdtemp()
    try:
        config = ClusterConfig(checkpoint_storage_dir=temp_dir, max_checkpoints_retained=5)
        chk_mgr = DistributedCheckpointManager(storage_dir=temp_dir, config=config)

        # 1. Setup sample subsystem states
        reg = NodeRegistry()
        reg.register_node(NodeInfo(node_id="worker-01", role=NodeRole.WORKER))
        reg.register_node(NodeInfo(node_id="master-01", role=NodeRole.MASTER))

        q = DistributedQueue(config=config)
        q.enqueue(TaskSpec(task_id="task_100", title="Test Task"))

        mem = DistributedClusterMemory(node_id="master-01")
        mem.set("app_version", "2.9.0")

        locks = DistributedLockManager(config=config)
        locks.acquire("res:config", owner_id="master-01")

        # 2. Create checkpoint
        chk_id = chk_mgr.create_checkpoint(
            epoch=1,
            leader_id="master-01",
            registry=reg,
            queue=q,
            memory=mem,
            lock_manager=locks,
        )

        assert chk_id.startswith("chk_")
        checkpoints = chk_mgr.list_checkpoints()
        assert len(checkpoints) == 1
        assert checkpoints[0].checkpoint_id == chk_id

        # 3. Restore into fresh subsystems
        new_reg = NodeRegistry()
        new_q = DistributedQueue(config=config)
        new_mem = DistributedClusterMemory(node_id="master-02")
        new_locks = DistributedLockManager(config=config)

        payload = chk_mgr.load_checkpoint(chk_id)
        assert payload is not None

        success = chk_mgr.restore_into_subsystems(
            checkpoint_data=payload,
            registry=new_reg,
            queue=new_q,
            memory=new_mem,
            lock_manager=new_locks,
        )
        assert success is True

        # Verify restored values
        assert new_reg.get_node("worker-01") is not None
        assert new_q.get_queue_depth() == 1
        assert new_mem.get("app_version") == "2.9.0"
        assert new_locks.is_locked("res:config") is True

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
