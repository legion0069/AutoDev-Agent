"""
test_leader_election.py - Unit tests for deterministic leader election and failover (v2.9)
"""

import pytest
import time
from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import NodeInfo, NodeRole, NodeStatus
from core.cluster.leader_election import ElectionState, LeaderElection
from core.cluster.node_registry import NodeRegistry


def test_deterministic_leader_election():
    reg = NodeRegistry()
    config = ClusterConfig(split_brain_quorum_size=2)

    master1 = NodeInfo(node_id="master-01", role=NodeRole.MASTER, health_score=95.0, uptime=100.0)
    backup1 = NodeInfo(node_id="master-02", role=NodeRole.BACKUP_MASTER, health_score=98.0, uptime=50.0)
    worker1 = NodeInfo(node_id="worker-01", role=NodeRole.WORKER, health_score=99.0, uptime=200.0)

    reg.register_node(master1)
    reg.register_node(backup1)
    reg.register_node(worker1)

    election = LeaderElection(local_node_id="master-01", registry=reg, config=config)

    # 1. Master-01 should win because MASTER role precedence (rank 3) > BACKUP_MASTER (rank 2)
    leader = election.start_election(reason="initial_election")
    assert leader == "master-01"
    assert election.is_leader("master-01") is True
    assert election.state == ElectionState.LEADER
    assert election.current_epoch == 2


def test_backup_master_promotion():
    reg = NodeRegistry()
    config = ClusterConfig(split_brain_quorum_size=2)

    master1 = NodeInfo(node_id="master-01", role=NodeRole.MASTER, status=NodeStatus.OFFLINE)
    backup1 = NodeInfo(node_id="master-02", role=NodeRole.BACKUP_MASTER, status=NodeStatus.HEALTHY, health_score=90.0)
    worker1 = NodeInfo(node_id="worker-01", role=NodeRole.WORKER, status=NodeStatus.HEALTHY, health_score=95.0)

    reg.register_node(master1)
    reg.register_node(backup1)
    reg.register_node(worker1)

    election = LeaderElection(local_node_id="master-02", registry=reg, config=config)

    # Master-01 is OFFLINE, so backup master-02 should be elected
    new_leader = election.handle_leader_failure("master-01")
    assert new_leader == "master-02"
    assert election.is_leader("master-02") is True
    assert election.state == ElectionState.LEADER


def test_split_brain_quorum_prevention():
    reg = NodeRegistry()
    config = ClusterConfig(split_brain_quorum_size=3)

    master1 = NodeInfo(node_id="master-01", role=NodeRole.MASTER, status=NodeStatus.HEALTHY)
    reg.register_node(master1)

    election = LeaderElection(local_node_id="master-01", registry=reg, config=config)

    # Active nodes = 1 < quorum 3 -> election should abort
    leader = election.start_election(reason="test_quorum")
    assert leader is None
