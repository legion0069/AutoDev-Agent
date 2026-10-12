"""
test_distributed_scheduler.py - Unit tests for multi-strategy scheduler and DAG waves (v2.9)
"""

import pytest
from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import NodeInfo, NodeRole, NodeStatus, TaskSpec
from core.cluster.distributed_scheduler import DistributedScheduler
from core.cluster.node_registry import NodeRegistry


def test_least_loaded_and_round_robin_scheduling():
    reg = NodeRegistry()
    w1 = NodeInfo(node_id="worker-01", role=NodeRole.WORKER, max_tasks=4, cpu_utilization=10.0, health_score=95.0)
    w2 = NodeInfo(node_id="worker-02", role=NodeRole.WORKER, max_tasks=4, cpu_utilization=80.0, health_score=80.0)
    reg.register_node(w1)
    reg.register_node(w2)

    scheduler = DistributedScheduler(registry=reg)

    t1 = TaskSpec(task_id="t1", title="Task 1")
    t2 = TaskSpec(task_id="t2", title="Task 2")

    # Least loaded should pick w1 (lowest CPU and load)
    selected = scheduler.select_worker(t1, strategy="least_loaded")
    assert selected == "worker-01"

    # Assign to w1
    scheduler.assign_task(t1, "worker-01")

    # Round robin
    rr1 = scheduler.select_worker(t2, strategy="round_robin")
    rr2 = scheduler.select_worker(t2, strategy="round_robin")
    assert rr1 != rr2 or len(reg.get_healthy_workers()) == 1


def test_capability_based_scheduling():
    reg = NodeRegistry()
    w_sec = NodeInfo(node_id="worker-sec", role=NodeRole.WORKER, capabilities=["security", "audit"])
    w_qa = NodeInfo(node_id="worker-qa", role=NodeRole.WORKER, capabilities=["testing", "qa"])
    reg.register_node(w_sec)
    reg.register_node(w_qa)

    scheduler = DistributedScheduler(registry=reg)

    task_audit = TaskSpec(task_id="t_sec", title="Security Audit", required_capabilities=["security"])
    selected = scheduler.select_worker(task_audit, strategy="capability_based")
    assert selected == "worker-sec"


def test_dependency_dag_kahn_waves():
    scheduler = DistributedScheduler(registry=NodeRegistry())

    # DAG: A -> B, A -> C, B -> D, C -> D
    tA = TaskSpec(task_id="A")
    tB = TaskSpec(task_id="B", dependencies=["A"])
    tC = TaskSpec(task_id="C", dependencies=["A"])
    tD = TaskSpec(task_id="D", dependencies=["B", "C"])

    adj, waves = scheduler.build_dependency_dag([tA, tB, tC, tD])

    assert len(waves) == 3
    assert waves[0] == ["A"]
    assert waves[1] == ["B", "C"]
    assert waves[2] == ["D"]


def test_dependency_dag_cycle_detection():
    scheduler = DistributedScheduler(registry=NodeRegistry())

    t1 = TaskSpec(task_id="T1", dependencies=["T2"])
    t2 = TaskSpec(task_id="T2", dependencies=["T1"])

    with pytest.raises(ValueError, match="Cycle detected"):
        scheduler.build_dependency_dag([t1, t2])
