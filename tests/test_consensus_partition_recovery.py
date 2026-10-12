"""
Tests for consensus partition recovery, quorum loss fail-closed behavior, and transaction adoption.
"""

import time
import pytest
from core.consensus_provider import (
    MemoryConsensusProvider,
    LeadershipLease,
    LeadershipToken,
    QuorumUnavailableError,
    LeadershipLostError,
)
from core.ha_coordinator import HACoordinator, LeaderFencingValidator


def test_consensus_partition_and_recovery_flow():
    provider = MemoryConsensusProvider()
    coord1 = HACoordinator("coord-1", consensus_provider=provider, lease_duration_seconds=5.0)
    coord1.start()
    assert coord1.is_leader is True
    t1 = coord1.fencing_token
    assert t1 is not None

    # Simulate network partition
    provider.set_partitioned(True)

    # Protected mutation during partition must fail closed
    with pytest.raises(QuorumUnavailableError):
        provider.conditional_put("state_key", "value_1", expected_version=0, fencing_token=provider.get_fencing_token())

    # Heal network partition
    provider.set_partitioned(False)

    # After recovery, leadership can be renewed and writes succeed
    assert coord1.renew_leader_lease() is True
    token_recovered = provider.get_fencing_token()
    assert provider.conditional_put("state_key", "value_1", expected_version=0, fencing_token=token_recovered) is True

    coord1.stop()


def test_consensus_failover_reconciliation_with_in_flight_transactions():
    provider = MemoryConsensusProvider()
    coord_primary = HACoordinator("coord-primary", consensus_provider=provider, lease_duration_seconds=5.0)
    coord_primary.start()

    # Create mock transaction and lease manager
    class MockTx:
        def __init__(self, tx_id):
            self.transaction_id = tx_id
            self.status = "STAGE_RUNNING"

    class MockLeaseManager:
        def prune_expired_leases(self):
            return ["lease_orphaned_1", "lease_orphaned_2"]

    class MockJournal:
        def __init__(self):
            self.events = []
        def append_event(self, event_type, transaction_id, payload):
            self.events.append((event_type, transaction_id, payload))

    journal = MockJournal()
    tx1 = MockTx("tx-in-flight-1")
    tx2 = MockTx("tx-in-flight-2")

    report = coord_primary.reconcile_failover(
        active_transactions=[tx1, tx2],
        lease_manager=MockLeaseManager(),
        journal=journal,
    )

    assert report["status"] == "reconciled"
    assert report["reconciled_transactions"] == 2
    assert report["orphaned_leases_revoked"] == 2
    assert len(journal.events) == 2
    assert journal.events[0][0] == "ha.transaction_adopted"

    coord_primary.stop()
