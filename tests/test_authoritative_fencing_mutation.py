"""
Tests for authoritative fencing token verification at the mutation boundary in AutoDev v2.5.
"""

import time
import pytest
from core.consensus_protocol import FencingToken
from core.ha_coordinator import HACoordinator, LeaderFencingValidator, NotLeaderError, StaleLeaderError
from core.consensus_provider import MemoryConsensusProvider


def test_leader_fencing_validator_active_leader():
    coord = HACoordinator(coordinator_id="lead-1", lease_duration_seconds=5.0)
    coord.start()
    assert coord.is_leader is True

    validator = LeaderFencingValidator(coord)
    token = validator.assert_active_leader("assign_task")
    assert token.leader_id == "lead-1"
    assert token.is_expired is False

    coord.stop()


def test_leader_fencing_validator_non_leader_rejected():
    coord = HACoordinator(coordinator_id="follower-1", lease_duration_seconds=5.0)
    # Not started, role is STARTING
    validator = LeaderFencingValidator(coord)

    with pytest.raises(NotLeaderError):
        validator.assert_active_leader("grant_lease")


def test_leader_fencing_validator_expired_fencing_token():
    coord = HACoordinator(coordinator_id="lead-expired", lease_duration_seconds=0.01)
    coord.start()
    time.sleep(0.05)

    validator = LeaderFencingValidator(coord)
    with pytest.raises((StaleLeaderError, NotLeaderError)):
        validator.assert_active_leader("commit_checkpoint")

    coord.stop()


def test_ha_coordinator_with_consensus_provider_fencing():
    provider = MemoryConsensusProvider()
    coord = HACoordinator(
        coordinator_id="lead-consensus",
        consensus_provider=provider,
        lease_duration_seconds=5.0,
    )
    coord.start()

    assert coord.is_leader is True
    assert coord.fencing_token is not None
    assert coord.fencing_token.leader_id == "lead-consensus"

    # Reconcile failover
    report = coord.reconcile_failover()
    assert report["status"] == "reconciled"
    assert report["leader_id"] == "lead-consensus"

    coord.stop()
    assert coord.is_leader is False
