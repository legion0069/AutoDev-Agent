"""
Unit tests for AutoDev v2.6 SelfHealingEngine, RepairTransaction,
RepairJournal, and RepairRecoveryManager.
"""

import os
import tempfile
import unittest

from core.patch_validator import PatchValidator
from core.repair_models import CandidatePatch, FilePatch, PatchStatus, RepairPlan, RepairPolicy
from core.repair_recovery import RepairJournal, RepairRecoveryManager
from core.repair_transaction import RepairState, RepairTransaction
from core.self_healing_engine import SelfHealingEngine
from core.test_execution_engine import GenericCommandTestRunner, TestExecutionEngine
from core.test_result_models import TestRunnerType


class TestSelfHealingEngineRecovery(unittest.TestCase):
    def test_transaction_state_transitions(self):
        tx = RepairTransaction(repair_id="rep_test_01")
        self.assertEqual(tx.state, RepairState.CREATED)

        self.assertTrue(tx.transition_to(RepairState.DIAGNOSING, "Starting diagnosis"))
        self.assertEqual(tx.state, RepairState.DIAGNOSING)
        self.assertEqual(len(tx.state_history), 1)

        # Invalid transition
        self.assertFalse(tx.transition_to(RepairState.ACCEPTED, "Direct jump"))
        self.assertEqual(tx.state, RepairState.DIAGNOSING)

    def test_engine_verified_rollback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "app.py")
            orig_code = "def get_val(): return 100\n"
            with open(src_file, "w") as f:
                f.write(orig_code)

            engine = SelfHealingEngine(tmpdir)
            tx = RepairTransaction(repair_id="tx_rollback")
            tx.record_file_snapshot("app.py", orig_code)

            # Mutate file
            with open(src_file, "w") as f:
                f.write("def get_val(): return 999\n")

            tx.transition_to(RepairState.DIAGNOSING)
            tx.transition_to(RepairState.PLANNED)
            tx.transition_to(RepairState.PATCH_GENERATED)
            tx.transition_to(RepairState.PATCH_VALIDATED)
            tx.transition_to(RepairState.APPLIED_IN_CANDIDATE)
            tx.transition_to(RepairState.VERIFYING)
            tx.transition_to(RepairState.VERIFICATION_FAILED)

            rollback_ok = engine.rollback_transaction(tx)
            self.assertTrue(rollback_ok)
            self.assertEqual(tx.state, RepairState.ROLLED_BACK)

            with open(src_file, "r") as f:
                restored = f.read()
            self.assertEqual(restored, orig_code)

    def test_journal_and_restart_recovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "service.py")
            orig_code = "SECRET = 'original'\n"
            with open(src_file, "w") as f:
                f.write(orig_code)

            journal_file = os.path.join(tmpdir, "journal.jsonl")
            journal = RepairJournal(journal_file)

            # Simulate an uncommitted transaction in APPLIED_IN_CANDIDATE
            tx = RepairTransaction(
                repair_id="rep_crashed_1",
                state=RepairState.APPLIED_IN_CANDIDATE,
                file_snapshots={"service.py": orig_code},
            )
            journal.append_entry(tx)

            # File was left modified on disk
            with open(src_file, "w") as f:
                f.write("SECRET = 'corrupted_candidate'\n")

            # Restart recovery manager
            recovery_mgr = RepairRecoveryManager(tmpdir, journal)
            recovered = recovery_mgr.reconcile_on_startup()

            self.assertIn("rep_crashed_1", recovered)
            with open(src_file, "r") as f:
                restored = f.read()
            self.assertEqual(restored, orig_code)


if __name__ == "__main__":
    unittest.main()
