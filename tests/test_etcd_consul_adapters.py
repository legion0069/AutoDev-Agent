"""
Unit and Integration tests for etcd v3 and Consul external consensus adapters.
"""

import pytest
from core.consensus_provider import (
    ConsensusConfiguration,
    ConsensusConfigurationError,
    FencingTokenRejectedError,
    LeadershipLostError,
    LeadershipToken,
    QuorumUnavailableError,
)
from core.etcd_consensus_adapter import EtcdConsensusAdapter
from core.consul_consensus_adapter import ConsulConsensusAdapter


def test_etcd_adapter_config_validation():
    # Empty endpoints
    with pytest.raises(ConsensusConfigurationError):
        EtcdConsensusAdapter(ConsensusConfiguration(endpoints=[]))

    # Invalid timeout
    with pytest.raises(ConsensusConfigurationError):
        EtcdConsensusAdapter(ConsensusConfiguration(timeout_seconds=0))


def test_etcd_adapter_lifecycle_and_fencing():
    config = ConsensusConfiguration(
        provider_type="etcd",
        endpoints=["127.0.0.1:2379"],
        prefix="/autodev/test",
        lease_ttl_seconds=5.0,
    )
    adapter = EtcdConsensusAdapter(config)

    lease = adapter.acquire_leadership("coordinator-etcd-1", term=1, ttl_seconds=5.0)
    assert lease.leader_id == "coordinator-etcd-1"
    assert lease.term == 1
    assert adapter.verify_leadership(lease) is True

    # Renew lease
    renewed = adapter.renew_leadership(lease, ttl_seconds=5.0)
    assert renewed.generation > lease.generation
    assert adapter.verify_leadership(renewed) is True

    # Conditional write with valid fencing token
    token = adapter.get_fencing_token()
    assert adapter.conditional_put("/autodev/test/state", "ok", expected_version=0, fencing_token=token) is True

    # Stale token write must be rejected
    stale = LeadershipToken(leader_id="coordinator-etcd-1", term=0, generation=0)
    with pytest.raises(FencingTokenRejectedError):
        adapter.conditional_put("/autodev/test/state", "bad", expected_version=1, fencing_token=stale)

    # Simulated partition fails closed
    adapter.set_partitioned(True)
    with pytest.raises(QuorumUnavailableError):
        adapter.acquire_leadership("coordinator-etcd-2", term=2)

    adapter.set_partitioned(False)
    adapter.release_leadership(renewed)
    adapter.close()


def test_consul_adapter_lifecycle_and_fencing():
    config = ConsensusConfiguration(
        provider_type="consul",
        endpoints=["127.0.0.1:8500"],
        prefix="autodev/consul_test",
        lease_ttl_seconds=5.0,
    )
    adapter = ConsulConsensusAdapter(config)

    lease = adapter.acquire_leadership("coordinator-consul-1", term=1, ttl_seconds=5.0)
    assert lease.leader_id == "coordinator-consul-1"
    assert lease.term == 1
    assert adapter.verify_leadership(lease) is True

    # Renew lease
    renewed = adapter.renew_leadership(lease, ttl_seconds=5.0)
    assert renewed.generation > lease.generation
    assert adapter.verify_leadership(renewed) is True

    # Conditional write with valid token
    token = adapter.get_fencing_token()
    assert adapter.conditional_put("autodev/consul_test/key1", "val1", expected_version=0, fencing_token=token) is True

    # Stale token write rejected
    stale = LeadershipToken(leader_id="coordinator-consul-1", term=0, generation=0)
    with pytest.raises(FencingTokenRejectedError):
        adapter.conditional_put("autodev/consul_test/key1", "val2", expected_version=1, fencing_token=stale)

    # Release leadership
    adapter.release_leadership(renewed)
    adapter.close()
