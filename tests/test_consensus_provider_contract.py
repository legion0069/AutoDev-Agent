"""
Unit and Contract tests for AutoDev v2.5 ConsensusProvider interface and MemoryConsensusProvider.
"""

import time
import pytest
from core.consensus_provider import (
    ConsensusConfiguration,
    ConsensusHealth,
    ConsensusUnavailableError,
    FencingTokenRejectedError,
    LeadershipLease,
    LeadershipLostError,
    LeadershipToken,
    MemoryConsensusProvider,
    QuorumUnavailableError,
)


def test_consensus_provider_single_leader_election():
    provider = MemoryConsensusProvider()
    lease = provider.acquire_leadership("coord-1", term=1, ttl_seconds=5.0)

    assert lease.leader_id == "coord-1"
    assert lease.term == 1
    assert lease.generation == 1
    assert lease.is_active is True
    assert lease.is_expired is False
    assert provider.verify_leadership(lease) is True

    # Second coordinator attempting to acquire same term must be rejected
    with pytest.raises(LeadershipLostError):
        provider.acquire_leadership("coord-2", term=1, ttl_seconds=5.0)


def test_consensus_provider_lease_renewal():
    provider = MemoryConsensusProvider()
    lease = provider.acquire_leadership("coord-1", term=1, ttl_seconds=1.0)
    original_gen = lease.generation

    time.sleep(0.05)
    renewed = provider.renew_leadership(lease, ttl_seconds=2.0)

    assert renewed.leader_id == "coord-1"
    assert renewed.term == 1
    assert renewed.generation > original_gen
    assert renewed.expires_at > lease.expires_at
    assert provider.verify_leadership(renewed) is True


def test_consensus_provider_fencing_token_monotonic():
    provider = MemoryConsensusProvider()
    lease1 = provider.acquire_leadership("coord-1", term=1, ttl_seconds=5.0)
    token1 = provider.get_fencing_token()

    assert token1.leader_id == "coord-1"
    assert token1.term == 1
    assert token1.generation == 1

    # Release and elect coord-2 in term 2
    provider.release_leadership(lease1)
    lease2 = provider.acquire_leadership("coord-2", term=2, ttl_seconds=5.0)
    token2 = provider.get_fencing_token()

    assert token2.is_newer_than(token1) is True
    assert token1.is_stale_compared_to(token2.term, token2.generation) is True


def test_consensus_provider_conditional_put_and_delete():
    provider = MemoryConsensusProvider()
    lease = provider.acquire_leadership("coord-1", term=1, ttl_seconds=5.0)
    token = lease.fencing_token

    # Initial write with expected_version=0
    assert provider.conditional_put("key1", "val1", expected_version=0, fencing_token=token) is True
    val, ver = provider.get("key1")
    assert val == "val1"
    assert ver == 1

    # Conflict on outdated expected_version
    assert provider.conditional_put("key1", "val2", expected_version=0, fencing_token=token) is False

    # Successful update with correct expected_version=1
    assert provider.conditional_put("key1", "val2", expected_version=1, fencing_token=token) is True
    val2, ver2 = provider.get("key1")
    assert val2 == "val2"
    assert ver2 == 2

    # Conditional delete
    assert provider.conditional_delete("key1", expected_version=2, fencing_token=token) is True
    assert provider.get("key1") is None


def test_consensus_provider_stale_fencing_token_rejected():
    provider = MemoryConsensusProvider()
    lease = provider.acquire_leadership("coord-1", term=1, ttl_seconds=5.0)
    stale_token = LeadershipToken(leader_id="coord-1", term=0, generation=0)

    with pytest.raises(FencingTokenRejectedError):
        provider.conditional_put("key_fenced", "value", expected_version=0, fencing_token=stale_token)


def test_consensus_provider_network_partition_simulation():
    provider = MemoryConsensusProvider()
    provider.acquire_leadership("coord-1", term=1, ttl_seconds=5.0)

    # Inject network partition
    provider.set_partitioned(True)

    with pytest.raises(QuorumUnavailableError):
        provider.get("some_key")

    with pytest.raises(QuorumUnavailableError):
        provider.conditional_put("key", "val")

    health = provider.get_health()
    assert health.is_healthy is False

    # Heal partition
    provider.set_partitioned(False)
    assert provider.get_health().is_healthy is True
