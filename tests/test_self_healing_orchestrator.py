"""
Unit tests for AutoDev v2.6 SelfHealingOrchestrator, operational modes,
and human approval controls.
"""

import os
import tempfile
import unittest

from core.repair_models import RepairMode, RepairPolicy
from core.repair_transaction import RepairState
from core.self_healing_orchestrator import SelfHealingOrchestrator
from core.test_result_models import FailureType, SingleTestResult, TestStatus


class TestSelfHealingOrchestrator(unittest.TestCase):
    def test_observe_only_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "app.py")
            orig_code = "def get_code(): return 404\n"
            with open(src_file, "w") as f:
                f.write(orig_code)

            policy = RepairPolicy(mode=RepairMode.OBSERVE_ONLY)
            orchestrator = SelfHealingOrchestrator(tmpdir, policy)

            test_res = SingleTestResult(
                test_id="test_app",
                test_name="test_app",
                test_file="app.py",
                status=TestStatus.FAILED,
                failure_type=FailureType.ASSERTION_FAILURE,
                message="AssertionError: assert 404 == 200",
                stack_trace=f'File "{src_file}", line 1, in get_code\nAssertionError: assert 404 == 200',
            )

            new_code = "def get_code(): return 200\n"
            summary = orchestrator.run_self_healing_workflow(
                initial_test_result=test_res,
                file_modifications={"app.py": new_code},
            )

            self.assertTrue(summary.success)
            self.assertIn("Observe-Only Mode", summary.summary_markdown)
            # File on disk was NOT modified in observe only
            with open(src_file, "r") as f:
                self.assertEqual(f.read(), orig_code)

    def test_assisted_mode_human_rejection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "app.py")
            orig_code = "def calc(): return 0\n"
            with open(src_file, "w") as f:
                f.write(orig_code)

            policy = RepairPolicy(mode=RepairMode.ASSISTED)
            orchestrator = SelfHealingOrchestrator(tmpdir, policy)

            test_res = SingleTestResult(
                test_id="test_calc",
                test_name="test_calc",
                test_file="app.py",
                status=TestStatus.FAILED,
                failure_type=FailureType.ASSERTION_FAILURE,
                message="AssertionError: assert 0 == 1",
            )

            # Human reviewer callback returns False (rejected)
            summary = orchestrator.run_self_healing_workflow(
                initial_test_result=test_res,
                file_modifications={"app.py": "def calc(): return 1\n"},
                human_approval_callback=lambda plan, patch: False,
            )

            self.assertFalse(summary.success)
            self.assertTrue(summary.human_approval_required)
            self.assertEqual(summary.final_state, RepairState.REJECTED.value)

    def test_environmental_failure_skip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = SelfHealingOrchestrator(tmpdir)
            test_res = SingleTestResult(
                test_id="test_redis",
                test_name="test_redis",
                status=TestStatus.FAILED,
                failure_type=FailureType.NETWORK_DEPENDENCY_FAILURE,
                message="ConnectionRefusedError: Redis service unreachable",
            )

            summary = orchestrator.run_self_healing_workflow(initial_test_result=test_res)
            self.assertFalse(summary.success)
            self.assertIn("Environmental Failure", summary.summary_markdown)


if __name__ == "__main__":
    unittest.main()
