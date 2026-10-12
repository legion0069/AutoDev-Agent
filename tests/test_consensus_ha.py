"""
Unit and Integration Tests for High Availability Coordination, Consensus & Fencing (Phase 2 & Phase 8.1)
"""

import time
import pytest

from core.consensus_protocol import (
    CoordinatorRole,
    FencingToken,
    CoordinatorNode,
    VoteRequest,
    VoteResponse,
    ConsensusHeartbeat,
)
from core.ha_coordinator import (
    HACoordinator,
    LeaderFencingValidator,
    HAError,
    NotLeaderError,
    StaleLeaderError,
    FencingViolationError,
    QuorumLostError,
)
from core.coordination_store import MemoryCoordinationStore


class TestConsensusProtocolModels:
    def test_fencing_token_monotonic_and_expiry(self):
        token = FencingToken(term=1, leader_id="coord-1", fencing_generation=1, expires_at_timestamp=time.time() + 10.0)
        assert not token.is_expired
        assert token.is_valid_for(expected_term=1, expected_generation=1)
        assert not token.is_valid_for(expected_term=2, expected_generation=1)

        # Expired token
        expired_token = FencingToken(term=1, leader_id="coord-1", fencing_generation=1, expires_at_timestamp=time.time() - 1.0)
        assert expired_token.is_expired
        assert not expired_token.is_valid_for(expected_term=1, expected_generation=1)

    def test_fencing_token_serialization(self):
        token = FencingToken(term=3, leader_id="coord-alpha", fencing_generation=7)
        data = token.to_dict()
        assert data["term"] == 3
        assert data["leader_id"] == "coord-alpha"
        assert data["fencing_generation"] == 7

        recovered = FencingToken.from_dict(data)
        assert recovered.term == 3
        assert recovered.leader_id == "coord-alpha"
        assert recovered.fencing_generation == 7

    def test_coordinator_node_liveness(self):
        node = CoordinatorNode(coordinator_id="node-1", role=CoordinatorRole.FOLLOWER, last_heartbeat_timestamp=time.time())
        assert node.is_alive
        node.last_heartbeat_timestamp = time.time() - 20.0
        assert not node.is_alive

    def test_coordinator_node_serialization(self):
        node = CoordinatorNode(coordinator_id="node-xyz", role=CoordinatorRole.LEADER, current_term=4)
        d = node.to_dict()
        assert d["coordinator_id"] == "node-xyz"
        assert d["role"] == "LEADER"
        assert d["current_term"] == 4


class TestHACoordinatorElectionAndFencing:
    def test_single_coordinator_self_election(self):
        store = MemoryCoordinationStore()
        coord = HACoordinator(coordinator_id="coord-1", peer_ids=["coord-1"], store=store)
        assert coord.role == CoordinatorRole.STARTING

        won = coord.start_election()
        assert won is True
        assert coord.role == CoordinatorRole.LEADER
        assert coord.is_leader is True
        assert coord.current_term == 1
        assert coord.leader_id == "coord-1"

        token = coord.fencing_token
        assert token is not None
        assert token.term == 1
        assert token.leader_id == "coord-1"

    def test_three_node_cluster_election_quorum(self):
        store = MemoryCoordinationStore()
        peers = ["node-1", "node-2", "node-3"]
        c1 = HACoordinator(coordinator_id="node-1", peer_ids=peers, store=store)
        c2 = HACoordinator(coordinator_id="node-2", peer_ids=peers, store=store)
        c3 = HACoordinator(coordinator_id="node-3", peer_ids=peers, store=store)

        # Node 1 starts election
        req = VoteRequest(term=1, candidate_id="node-1", last_log_index=0, last_log_term=0)
        resp2 = c2.receive_vote_request(req)
        resp3 = c3.receive_vote_request(req)

        assert resp2.vote_granted is True
        assert resp3.vote_granted is True

        # Candidate node 1 becomes leader
        c1.role = CoordinatorRole.LEADER
        c1.current_term = 1
        c1.leader_id = "node-1"
        c1.current_generation += 1
        c1.fencing_token = FencingToken(term=1, leader_id="node-1", fencing_generation=c1.current_generation)

        # Node 1 sends heartbeat to followers
        hb = ConsensusHeartbeat(term=1, leader_id="node-1", fencing_generation=c1.current_generation)
        hb_resp2 = c2.receive_heartbeat(hb)
        hb_resp3 = c3.receive_heartbeat(hb)

        assert hb_resp2["success"] is True
        assert hb_resp3["success"] is True
        assert c2.leader_id == "node-1"
        assert c3.leader_id == "node-1"
        assert c2.role == CoordinatorRole.FOLLOWER
        assert c3.role == CoordinatorRole.FOLLOWER

    def test_candidate_rejects_lower_term_vote(self):
        store = MemoryCoordinationStore()
        c = HACoordinator(coordinator_id="node-1", peer_ids=["node-1", "node-2"], store=store)
        c.current_term = 5
        req = VoteRequest(term=4, candidate_id="node-2", last_log_index=0, last_log_term=0)
        resp = c.receive_vote_request(req)
        assert resp.vote_granted is False
        assert resp.term == 5

    def test_candidate_rejects_duplicate_vote_in_same_term(self):
        store = MemoryCoordinationStore()
        c = HACoordinator(coordinator_id="node-voter", peer_ids=["node-voter", "c1", "c2"], store=store)
        c.current_term = 2
        # First candidate gets vote
        req1 = VoteRequest(term=2, candidate_id="c1")
        resp1 = c.receive_vote_request(req1)
        assert resp1.vote_granted is True

        # Second candidate in same term is rejected
        req2 = VoteRequest(term=2, candidate_id="c2")
        resp2 = c.receive_vote_request(req2)
        assert resp2.vote_granted is False

    def test_peer_registration_and_deregistration(self):
        coord = HACoordinator(coordinator_id="master-node")
        assert coord.total_cluster_size == 1
        assert coord.quorum_size == 1

        peer = CoordinatorNode(coordinator_id="worker-node-1")
        coord.register_peer(peer)
        assert coord.total_cluster_size == 2
        assert coord.quorum_size == 2

        coord.deregister_peer("worker-node-1")
        assert coord.total_cluster_size == 1

    def test_role_change_callback_triggered(self):
        coord = HACoordinator(coordinator_id="cb-node")
        observed_roles = []
        coord.on_role_change(lambda role: observed_roles.append(role))

        coord.start_election()
        assert CoordinatorRole.CANDIDATE in observed_roles
        assert CoordinatorRole.LEADER in observed_roles

    def test_leader_lease_renewal(self):
        coord = HACoordinator(coordinator_id="renew-node", lease_duration_seconds=5.0)
        coord.start_election()
        assert coord.is_leader is True
        orig_expiry = coord.fencing_token.expires_at_timestamp

        time.sleep(0.1)
        renewed = coord.renew_leader_lease()
        assert renewed is True
        assert coord.fencing_token.expires_at_timestamp > orig_expiry

    def test_leader_fencing_validator_protects_mutations(self):
        store = MemoryCoordinationStore()
        c = HACoordinator(coordinator_id="node-1", peer_ids=["node-1"], store=store)
        validator = LeaderFencingValidator(c)

        # Should fail closed when not leader
        with pytest.raises(NotLeaderError):
            validator.assert_active_leader()

        # Elect leader
        c.start_election()
        # Now passes
        token = validator.assert_active_leader()
        assert token.term == 1

        # Step down
        c.step_down(reason="Stepping down for test")
        with pytest.raises(NotLeaderError):
            validator.assert_active_leader()

    def test_stale_leader_fencing_token_rejection(self):
        store = MemoryCoordinationStore()
        c = HACoordinator(coordinator_id="node-1", peer_ids=["node-1"], store=store)
        c.start_election()

        token1 = c.fencing_token
        validator = LeaderFencingValidator(c)

        # Token 1 is initially valid
        assert validator.validate_fencing_token(token1, minimum_generation=1) is True

        # Expired token is rejected
        expired_token = FencingToken(term=1, leader_id="node-1", fencing_generation=1, expires_at_timestamp=time.time() - 1.0)
        assert validator.validate_fencing_token(expired_token) is False

        # Higher generation requirement rejects outdated token
        assert validator.validate_fencing_token(token1, minimum_generation=999) is False

    def test_failover_reconciliation_safely_adopts_state(self):
        store = MemoryCoordinationStore()
        # Simulate previous leader registering state in durable store
        store.save_coordinator("old-leader", {"coordinator_id": "old-leader", "role": "LEADER", "current_term": 1})
        store.save_leadership(1, "old-leader", 1, time.time() + 10.0)

        # New coordinator elected in term 2
        new_coord = HACoordinator(coordinator_id="new-leader", peer_ids=["new-leader"], store=store)
        new_coord.start_election()
        assert new_coord.current_term == 1

        # Run failover reconciliation
        summary = new_coord.reconcile_failover()
        assert summary["status"] == "reconciled"
        assert summary["reconciled_by"] == "new-leader"
