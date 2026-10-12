"""
test_heartbeat_manager.py - Unit tests for HeartbeatManager and health scoring (v2.9)
"""

import pytest
import time
from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import NodeInfo, NodeRole, NodeStatus
from core.cluster.heartbeat_manager import HeartbeatManager
from core.cluster.node_registry import NodeRegistry


def test_health_score_calculation():
    reg = NodeRegistry()
    hb = HeartbeatManager(registry=reg)

    # Ideal state: 0% CPU, 0% Memory, 0 tasks, 0.5ms latency -> 100.0 score
    score_ideal = hb.calculate_health_score(cpu_utilization=0.0, memory_utilization=0.0, active_tasks=0, max_tasks=4, latency_ms=0.5)
    assert score_ideal >= 99.0

    # Stressed state: 90% CPU, 80% Memory, 4/4 tasks, 150ms latency
    score_stressed = hb.calculate_health_score(cpu_utilization=90.0, memory_utilization=80.0, active_tasks=4, max_tasks=4, latency_ms=150.0)
    assert score_stressed < 40.0


def test_heartbeat_status_transitions():
    reg = NodeRegistry()
    config = ClusterConfig(heartbeat_interval=0.5, worker_timeout=1.5, degraded_threshold_heartbeats=1)
    
    offline_called = []
    degraded_called = []
    recovered_called = []

    hb = HeartbeatManager(
        registry=reg,
        config=config,
        on_node_offline=lambda nid, n: offline_called.append(nid),
        on_node_degraded=lambda nid, n: degraded_called.append(nid),
        on_node_recovered=lambda nid, n: recovered_called.append(nid),
    )

    worker = NodeInfo(node_id="worker-01", role=NodeRole.WORKER, max_tasks=4)
    reg.register_node(worker)

    # 1. Normal heartbeat
    hb.record_node_heartbeat("worker-01", cpu_utilization=20.0, memory_utilization=30.0, active_tasks=1)
    node = reg.get_node("worker-01")
    assert node.status == NodeStatus.HEALTHY
    assert node.health_score > 70.0

    # 2. Simulated time advance -> DEGRADED
    now = time.time()
    status_map = hb.check_heartbeats(current_time=now + 0.8)
    assert status_map["worker-01"] == NodeStatus.DEGRADED
    assert "worker-01" in degraded_called

    # 3. Simulated time advance -> OFFLINE
    status_map_offline = hb.check_heartbeats(current_time=now + 2.0)
    assert status_map_offline["worker-01"] == NodeStatus.OFFLINE
    assert "worker-01" in offline_called

    # 4. Worker returns -> RECOVERING
    hb.record_node_heartbeat("worker-01", cpu_utilization=10.0, memory_utilization=20.0, active_tasks=0)
    node_rec = reg.get_node("worker-01")
    assert node_rec.status == NodeStatus.RECOVERING
    assert "worker-01" in recovered_called
