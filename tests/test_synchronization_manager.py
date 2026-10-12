"""
Tests for AutoDev Synchronization Manager (v2.8)
================================================
Verifies synchronization checkpoints (PRE_MERGE, PRE_RELEASE, POST_ARCHITECTURE),
barrier synchronization, automated quality gate evaluations, and blocker detection.
"""

import threading
import time
import pytest
from core.collaboration.collaboration_models import SyncCheckpointType
from core.collaboration.synchronization_manager import SynchronizationManager


def test_checkpoint_creation_and_recording():
    sync = SynchronizationManager()
    cp = sync.create_checkpoint(
        SyncCheckpointType.PRE_MERGE,
        name="TestPreMerge",
        required_validations=["tests", "security"],
    )
    assert cp.passed is False

    # Record tests pass
    sync.record_validation(cp.checkpoint_id, "TestingAgent", "tests", passed=True)
    passed, issues = sync.evaluate_checkpoint(cp.checkpoint_id)
    assert passed is False
    assert any("security" in i for i in issues)

    # Record security pass
    sync.record_validation(cp.checkpoint_id, "SecurityAgent", "security", passed=True)
    passed_final, issues_final = sync.evaluate_checkpoint(cp.checkpoint_id)
    assert passed_final is True
    assert len(issues_final) == 0


def test_checkpoint_blocker_recording():
    sync = SynchronizationManager()
    cp = sync.create_checkpoint(
        SyncCheckpointType.PRE_RELEASE,
        name="TestPreRelease",
        required_validations=["tests", "security"],
    )

    # Record test failure
    sync.record_validation(
        cp.checkpoint_id,
        "TestingAgent",
        "tests",
        passed=False,
        details={"reason": "2 integration tests failed"},
    )
    passed, issues = sync.evaluate_checkpoint(cp.checkpoint_id)
    assert passed is False
    assert len(cp.blockers) > 0


def test_barrier_waiting_concurrent():
    sync = SynchronizationManager()
    cp = sync.create_checkpoint(
        SyncCheckpointType.POST_ARCHITECTURE,
        name="ArchBarrier",
        required_validations=["interface_compatibility"],
    )

    def release_barrier_after_delay():
        time.sleep(0.1)
        sync.record_validation(cp.checkpoint_id, "ArchitectureAgent", "interface_compatibility", passed=True)

    t = threading.Thread(target=release_barrier_after_delay)
    t.start()

    cleared = sync.wait_for_barrier(cp.checkpoint_id, timeout_seconds=2.0)
    t.join()
    assert cleared is True


def test_automated_gate_checks():
    sync = SynchronizationManager()
    cp = sync.create_checkpoint(
        SyncCheckpointType.PRE_MERGE,
        name="AutoGate",
        required_validations=["tests", "security", "documentation"],
    )

    results = sync.run_automated_gate_checks(
        checkpoint_id=cp.checkpoint_id,
        test_runner_func=lambda: True,
        security_scanner_func=lambda: True,
        doc_validator_func=lambda: True,
    )
    assert results["tests"] is True
    assert results["security"] is True
    assert results["documentation"] is True

    passed, _ = sync.evaluate_checkpoint(cp.checkpoint_id)
    assert passed is True
