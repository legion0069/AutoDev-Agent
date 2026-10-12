"""
test_enterprise_disaster_recovery.py - Unit Tests for EnterpriseDisasterRecovery (AutoDev Version 3.5)
"""

import time
import pytest

from core.enterprise_disaster_recovery import (
    EnterpriseDisasterRecovery,
    EnterpriseSnapshot,
    OutageType,
    RecoveryEvent,
)


def test_disaster_recovery_initialization():
    dr = EnterpriseDisasterRecovery()
    metrics = dr.get_recovery_metrics()
    assert metrics["total_recoveries"] == 0
    assert metrics["recovery_success_rate"] == 1.0
    assert metrics["snapshots_stored"] == 0


def test_snapshot_capture_and_validation():
    dr = EnterpriseDisasterRecovery()
    state = {"company_count": 8, "active_projects": ["P1", "P2"], "balance": 500000}
    snap = dr.capture_snapshot(state)

    assert snap.snapshot_id.startswith("SNAP-")
    assert len(snap.checksum_sha256) == 64

    latest = dr.get_latest_valid_snapshot()
    assert latest is not None
    assert latest.snapshot_id == snap.snapshot_id
    assert latest.state_payload["company_count"] == 8


def test_heartbeat_outage_detection():
    dr = EnterpriseDisasterRecovery(heartbeat_timeout_seconds=0.05)
    dr.record_heartbeat("COMP-A")
    dr.record_heartbeat("COMP-B")

    # Initially no outage
    assert len(dr.check_for_outages()) == 0

    # Wait for timeout
    time.sleep(0.06)
    outages = dr.check_for_outages()
    assert len(outages) == 2
    entities = [ent for ent, elapsed in outages]
    assert "COMP-A" in entities
    assert "COMP-B" in entities


def test_company_outage_recovery():
    dr = EnterpriseDisasterRecovery()
    restarted = []

    def mock_restart(cid: str) -> bool:
        restarted.append(cid)
        return True

    rec_event = dr.recover_company_outage("COMP-A", restart_callback=mock_restart)
    assert rec_event.outage_type == OutageType.COMPANY_OUTAGE
    assert rec_event.affected_entity == "COMP-A"
    assert rec_event.recovered_successfully is True
    assert "COMP-A" in restarted


def test_department_outage_recovery():
    dr = EnterpriseDisasterRecovery()

    def mock_reassign() -> int:
        return 7  # 7 tasks redistributed

    rec_event = dr.recover_department_outage("COMP-A", "Backend", reassign_tasks_callback=mock_reassign)
    assert rec_event.outage_type == OutageType.DEPARTMENT_OUTAGE
    assert rec_event.recovered_successfully is True
    assert "redistributed 7 in-flight tasks" in rec_event.action_taken


def test_memory_corruption_recovery_and_rollback():
    dr = EnterpriseDisasterRecovery()
    original_state = {"healthy_data": [1, 2, 3]}
    snap = dr.capture_snapshot(original_state)

    restored_state = []

    def mock_rollback(data: dict) -> bool:
        restored_state.append(data)
        return True

    # Simulate corrupted state
    corrupt_state = {"healthy_data": [1, 2, 999999]}
    event = dr.recover_memory_corruption(
        current_state=corrupt_state,
        expected_checksum=snap.checksum_sha256,
        apply_rollback_callback=mock_rollback,
    )
    assert event.recovered_successfully is True
    assert "Rolled back state to snapshot" in event.action_taken
    assert len(restored_state) == 1
    assert restored_state[0] == original_state


def test_bus_failure_recovery():
    dr = EnterpriseDisasterRecovery()
    event = dr.recover_bus_failure(reinit_bus_callback=lambda: True)
    assert event.outage_type == OutageType.BUS_FAILURE
    assert event.recovered_successfully is True


def test_recovery_metrics_calculation():
    dr = EnterpriseDisasterRecovery()
    dr.recover_company_outage("C1")
    dr.recover_company_outage("C2")

    metrics = dr.get_recovery_metrics()
    assert metrics["total_recoveries"] == 2
    assert metrics["recovery_success_rate"] == 1.0
    assert len(metrics["recent_recoveries"]) == 2
