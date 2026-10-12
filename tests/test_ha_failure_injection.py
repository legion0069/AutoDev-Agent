"""
High Availability & Consensus Failure Injection Tests (Phase 8.1)
Exercises split-brain partitions, stale leader fencing, loss of quorum,
mid-operation token expiry, and durable store crash recovery.
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
from core.coordination_store import MemoryCoordinationStore, SqliteCoordinationStore


class TestHAFailureInjection:
    def test_stale_leader_attempting_mutation_fails_closed(self):
        c1 = HACoordinator(coordinator_id="node-1")
        c1.start_election()
        validator = LeaderFencingValidator(c1)

        # Active leader succeeds
        token = validator.assert_active_leader("assign_task")
        assert token.term == 1

        # Simulate leader being deposed by higher term
        c1.step_down("Deposed by higher term from peer")
        with pytest.raises(NotLeaderError, match="not the active leader"):
            validator.assert_active_leader("assign_task")

    def test_fencing_token_expired_fails_closed(self):
        c1 = HACoordinator(coordinator_id="node-1", lease_duration_seconds=0.05)
        c1.start_election()
        validator = LeaderFencingValidator(c1)

        # Wait for lease to expire
        time.sleep(0.1)
        with pytest.raises((StaleLeaderError, NotLeaderError)):
            validator.assert_active_leader("commit_checkpoint")

    def test_loss_of_quorum_broadcast_triggers_degraded_mode(self):
        # 3 node cluster where no peers respond
        peers = ["node-1", "node-2", "node-3"]
        c1 = HACoordinator(
            coordinator_id="node-1",
            peer_ids=peers,
            transport_call=lambda p, m, d: None,  # No responses
        )
        c1.role = CoordinatorRole.LEADER
        c1.current_term = 1
        c1.fencing_token = FencingToken(term=1, leader_id="node-1", fencing_generation=1)

        # Heartbeat broadcast should detect loss of quorum (1/2 acked)
        c1._broadcast_heartbeat()
        assert c1.role == CoordinatorRole.DEGRADED
        assert c1.fencing_token is None

    def test_reentrant_election_increments_term_and_generation(self):
        c1 = HACoordinator(coordinator_id="node-1")
        c1.start_election()
        assert c1.current_term == 1
        gen1 = c1.current_generation

        c1.start_election()
        assert c1.current_term == 2
        assert c1.current_generation > gen1
        assert c1.fencing_token.term == 2

    def test_vote_response_with_higher_term_forces_stepdown(self):
        c1 = HACoordinator(
            coordinator_id="node-1",
            peer_ids=["node-1", "node-2"],
            transport_call=lambda p, m, d: {"term": 10, "vote_granted": False, "voter_id": "node-2"},
        )
        won = c1.start_election()
        assert won is False
        assert c1.current_term == 10
        assert c1.role in (CoordinatorRole.FOLLOWER, CoordinatorRole.UNAVAILABLE)

    def test_sqlite_coordination_store_coordinator_records(self, tmp_path):
        db_path = tmp_path / "coord.db"
        store = SqliteCoordinationStore(db_path=db_path)

        store.save_coordinator("coord-1", {"role": "LEADER", "term": 5})
        store.save_coordinator("coord-2", {"role": "FOLLOWER", "term": 5})

        c1_data = store.get_coordinator("coord-1")
        assert c1_data is not None
        assert c1_data["role"] == "LEADER"

        all_coords = store.list_coordinators()
        assert len(all_coords) == 2

        store.save_leadership(5, "coord-1", 3, time.time() + 30.0)
        leader_info = store.get_leadership()
        assert leader_info is not None
        assert leader_info["leader_id"] == "coord-1"
        assert leader_info["term"] == 5

    def test_outdated_heartbeat_rejected_by_follower(self):
        c = HACoordinator(coordinator_id="follower-node")
        c.current_term = 4

        # Stale heartbeat with term 2
        hb = ConsensusHeartbeat(term=2, leader_id="old-leader", fencing_generation=1)
        res = c.receive_heartbeat(hb)
        assert res["success"] is False
        assert "outdated" in res["reason"]
