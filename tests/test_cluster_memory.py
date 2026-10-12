"""
test_cluster_memory.py - Unit tests for DistributedClusterMemory (v2.9)
"""

import pytest
import time
from core.cluster.cluster_state import DistributedClusterMemory, MemoryEntry


def test_cluster_memory_set_get_delete():
    mem = DistributedClusterMemory(node_id="node-01")
    
    # 1. Set key
    entry = mem.set("database_url", "postgresql://localhost:5432/autodev", source_node="node-01")
    assert entry.key == "database_url"
    assert entry.version == 1
    assert entry.value == "postgresql://localhost:5432/autodev"
    assert mem.contains("database_url") is True

    # 2. Update key
    entry2 = mem.set("database_url", "postgresql://localhost:5433/autodev", source_node="node-02")
    assert entry2.version == 2
    assert entry2.updated_by == "node-02"
    assert mem.get("database_url") == "postgresql://localhost:5433/autodev"

    # 3. List keys
    assert "database_url" in mem.keys()

    # 4. Delete key
    assert mem.delete("database_url", source_node="node-01") is True
    assert mem.contains("database_url") is False
    assert mem.get("database_url") is None
    assert mem.get("database_url", default="fallback") == "fallback"


def test_cluster_memory_replication_merge():
    mem_local = DistributedClusterMemory(node_id="master-01")
    mem_remote = DistributedClusterMemory(node_id="worker-02")

    mem_local.set("config_a", "val_a_v1")
    time.sleep(0.01)
    mem_remote.set("config_a", "val_a_v2")
    mem_remote.set("config_b", "val_b_v1")

    # Snapshot remote and merge into local
    remote_snap = mem_remote.dump_snapshot()
    updated_count = mem_local.merge_replication(remote_snap)
    assert updated_count == 2
    assert mem_local.get("config_a") == "val_a_v2"
    assert mem_local.get("config_b") == "val_b_v1"


def test_cluster_memory_snapshot_load():
    mem1 = DistributedClusterMemory(node_id="master-01")
    mem1.set("key1", {"nested": 123})
    mem1.set("key2", [1, 2, 3])

    snap = mem1.dump_snapshot()
    
    mem2 = DistributedClusterMemory(node_id="master-02")
    mem2.load_snapshot(snap)

    assert mem2.get("key1") == {"nested": 123}
    assert mem2.get("key2") == [1, 2, 3]
