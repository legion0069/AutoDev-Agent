"""
End-to-End acceptance test scenarios for AutoDev v2.6 Self-Healing Engine.
Covers Scenarios A, B, C, D, and E from Section 14.5 of the engineering specification.
"""

import os
import sys
import tempfile
import unittest

from core.diagnostic_models import FailureCategory
from core.patch_validator import PatchValidator
from core.repair_models import CandidatePatch, FilePatch, PatchStatus, RepairMode, RepairPolicy, ValidationGateStatus
from core.repair_recovery import RepairJournal, RepairRecoveryManager
from core.repair_transaction import RepairState, RepairTransaction
from core.self_healing_engine import SelfHealingEngine
from core.self_healing_orchestrator import SelfHealingOrchestrator
from core.test_execution_engine import PytestTestRunner, TestExecutionEngine
from core.test_result_models import FailureType, SingleTestResult, TestRunnerType, TestStatus


class TestV26EndToEndScenarios(unittest.TestCase):
    def test_scenario_a_successful_repair(self):
        """Scenario A: Successful end-to-end defect repair and verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Create project with defect
            math_py = os.path.join(tmpdir, "math_lib.py")
            with open(math_py, "w") as f:
                f.write("def compute_total(items):\n    return sum(items) - 1  # BUG\n")

            test_dir = os.path.join(tmpdir, "tests")
            os.makedirs(test_dir)
            test_math = os.path.join(test_dir, "test_math_lib.py")
            with open(test_math, "w") as f:
                f.write(
                    "import math_lib\n\n"
                    "def test_compute_total():\n"
                    "    assert math_lib.compute_total([10, 20]) == 30\n"
                )

            # 2. Run orchestrator to fix the bug
            orchestrator = SelfHealingOrchestrator(tmpdir)
            fixed_code = "def compute_total(items):\n    return sum(items)\n"

            summary = orchestrator.run_self_healing_workflow(
                failing_test_id="tests/test_math_lib.py",
                file_modifications={"math_lib.py": fixed_code},
            )

            # 3. Assertions
            self.assertTrue(summary.success)
            self.assertEqual(summary.final_state, RepairState.ACCEPTED.value)
            self.assertEqual(summary.validation_gates.get("gate_1_patch_validation"), ValidationGateStatus.PASSED.value)
            self.assertEqual(summary.validation_gates.get("gate_2_syntax_check"), ValidationGateStatus.PASSED.value)
            self.assertEqual(summary.validation_gates.get("gate_3_primary_test"), ValidationGateStatus.PASSED.value)

            with open(math_py, "r") as f:
                self.assertEqual(f.read(), fixed_code)

    def test_scenario_b_repair_rejected_and_rolled_back(self):
        """Scenario B: Candidate patch fails validation gate -> rollback to baseline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            math_py = os.path.join(tmpdir, "math_lib.py")
            orig_code = "def compute_total(items):\n    return sum(items) - 5\n"
            with open(math_py, "w") as f:
                f.write(orig_code)

            test_dir = os.path.join(tmpdir, "tests")
            os.makedirs(test_dir)
            test_math = os.path.join(test_dir, "test_math_lib.py")
            with open(test_math, "w") as f:
                f.write(
                    "import math_lib\n\n"
                    "def test_compute_total():\n"
                    "    assert math_lib.compute_total([10, 20]) == 30\n"
                )

            orchestrator = SelfHealingOrchestrator(tmpdir)
            # Candidate patch is also broken
            bad_fixed_code = "def compute_total(items):\n    return sum(items) + 999\n"

            summary = orchestrator.run_self_healing_workflow(
                failing_test_id="tests/test_math_lib.py",
                file_modifications={"math_lib.py": bad_fixed_code},
            )

            self.assertFalse(summary.success)
            self.assertEqual(summary.final_state, RepairState.ROLLED_BACK.value)
            self.assertTrue(summary.rollback_performed)

            # Verify file content is strictly restored to original code
            with open(math_py, "r") as f:
                self.assertEqual(f.read(), orig_code)

    def test_scenario_c_ambiguous_environmental_failure(self):
        """Scenario C: Environmental failure stops without code changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "db.py")
            orig_content = "# Database connection logic\n"
            with open(src_file, "w") as f:
                f.write(orig_content)

            orchestrator = SelfHealingOrchestrator(tmpdir)
            test_res = SingleTestResult(
                test_id="test_db_connect",
                test_name="test_db_connect",
                status=TestStatus.FAILED,
                failure_type=FailureType.NETWORK_DEPENDENCY_FAILURE,
                message="psycopg2.OperationalError: could not connect to server: Connection refused",
            )

            summary = orchestrator.run_self_healing_workflow(initial_test_result=test_res)
            self.assertFalse(summary.success)
            self.assertEqual(summary.final_state, RepairState.REJECTED.value)

            with open(src_file, "r") as f:
                self.assertEqual(f.read(), orig_content)

    def test_scenario_d_security_violation_rejection(self):
        """Scenario D: Patch attempting path traversal or test weakening is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = PatchValidator(tmpdir, RepairPolicy())
            # Malicious patch removing assertions from test
            fp = FilePatch(
                file_path="tests/test_auth.py",
                original_content="def test_auth(): assert check_token() is True\n",
                new_content="def test_auth(): pass\n",
            )
            patch = CandidatePatch(file_patches=[fp])
            val_res = validator.validate(patch)

            self.assertFalse(val_res.is_valid)
            self.assertFalse(val_res.anti_weakening_ok)

    def test_scenario_e_interrupted_recovery(self):
        """Scenario E: Crash recovery safely reconciles interrupted transactions on startup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "module.py")
            orig_code = "INITIAL_STATE = 1\n"
            with open(src_file, "w") as f:
                f.write(orig_code)

            journal_path = os.path.join(tmpdir, "repair_journal.jsonl")
            journal = RepairJournal(journal_path)

            # Record interrupted transaction
            tx = RepairTransaction(
                repair_id="rep_interrupted_99",
                state=RepairState.VERIFYING,
                file_snapshots={"module.py": orig_code},
            )
            journal.append_entry(tx)

            # Mutate file to dirty candidate state
            with open(src_file, "w") as f:
                f.write("INITIAL_STATE = 999_DIRTY\n")

            # Initialize orchestrator which triggers startup recovery
            orchestrator = SelfHealingOrchestrator(tmpdir, journal_path=journal_path)

            # Verify file was rolled back to initial state safely
            with open(src_file, "r") as f:
                self.assertEqual(f.read(), orig_code)


if __name__ == "__main__":
    unittest.main()
