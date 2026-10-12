"""
Unit tests for AutoDev v2.6 TestExecutionEngine, SafeSubprocessExecutor,
secret redaction, log bounding, and test runner adapters.
"""

import os
import sys
import tempfile
import unittest

from core.test_execution_engine import (
    GenericCommandTestRunner,
    PytestTestRunner,
    SafeSubprocessExecutor,
    TestExecutionEngine,
    UnittestTestRunner,
    is_path_contained,
)
from core.test_result_models import (
    FailureType,
    SingleTestResult,
    TestExecutionFingerprint,
    TestRunnerType,
    TestStatus,
    TestSuiteResult,
    bound_log_text,
    redact_secrets,
)


class TestTestResultModels(unittest.TestCase):
    def test_secret_redaction(self):
        raw = "Error on API_KEY='sk-1234567890abcdef12345678' with Bearer 12345678901234567890"
        redacted = redact_secrets(raw)
        self.assertNotIn("sk-1234567890abcdef12345678", redacted)
        self.assertIn("[REDACTED_SECRET]", redacted)

    def test_log_bounding(self):
        large = "A" * 100000
        bounded = bound_log_text(large, max_bytes=1000)
        self.assertLessEqual(len(bounded.encode("utf-8")), 2000)
        self.assertIn("LOG TRUNCATED", bounded)

    def test_fingerprint_generation(self):
        fp = TestExecutionFingerprint(working_directory="/test/dir", changed_files=["a.py"])
        d = fp.to_dict()
        self.assertEqual(d["working_directory"], "/test/dir")
        self.assertTrue(len(fp.env_hash) > 0)

    def test_single_and_suite_result_serialization(self):
        single = SingleTestResult(
            test_id="test_foo",
            test_name="test_foo",
            status=TestStatus.FAILED,
            failure_type=FailureType.ASSERTION_FAILURE,
            message="assert 1 == 2",
        )
        suite = TestSuiteResult(
            run_id="run_1",
            tests=[single],
        )
        self.assertEqual(suite.total_count, 1)
        self.assertEqual(suite.failed_count, 1)
        self.assertFalse(suite.success)
        d = suite.to_dict()
        self.assertEqual(d["run_id"], "run_1")
        restored = TestSuiteResult.from_dict(d)
        self.assertEqual(restored.failed_count, 1)


class TestSafeSubprocessExecutor(unittest.TestCase):
    def test_path_containment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inside = os.path.join(tmpdir, "child", "file.py")
            outside = os.path.join(tmpdir, "..", "outside.py")
            self.assertTrue(is_path_contained(inside, tmpdir))
            self.assertFalse(is_path_contained(outside, tmpdir))

    def test_safe_execution_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code, stdout, stderr, dur = SafeSubprocessExecutor.run_command(
                cmd=[sys.executable, "-c", "print('Hello AutoDev')"],
                cwd=tmpdir,
                timeout_seconds=10,
            )
            self.assertEqual(exit_code, 0)
            self.assertIn("Hello AutoDev", stdout)
            self.assertGreater(dur, 0.0)

    def test_safe_execution_timeout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code, stdout, stderr, dur = SafeSubprocessExecutor.run_command(
                cmd=[sys.executable, "-c", "import time; time.sleep(5)"],
                cwd=tmpdir,
                timeout_seconds=1,
            )
            self.assertEqual(exit_code, 124)
            self.assertIn("timed out", stderr)


class TestTestExecutionEngine(unittest.TestCase):
    def test_engine_runner_registration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TestExecutionEngine(tmpdir)
            runner = engine.get_runner(TestRunnerType.PYTEST)
            self.assertIsInstance(runner, PytestTestRunner)

            generic = GenericCommandTestRunner([sys.executable, "-V"], TestRunnerType.GENERIC)
            engine.register_runner(generic)
            self.assertEqual(engine.get_runner(TestRunnerType.GENERIC), generic)

    def test_generic_runner_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TestExecutionEngine(tmpdir)
            generic = GenericCommandTestRunner([sys.executable, "-c", "print('OK')"])
            engine.register_runner(generic)
            res = engine.execute_test_suite(runner_type=TestRunnerType.GENERIC)
            self.assertTrue(res.success)
            self.assertEqual(res.passed_count, 1)


if __name__ == "__main__":
    unittest.main()
