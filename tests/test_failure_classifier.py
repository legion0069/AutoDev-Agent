"""
Unit tests for AutoDev v2.6 FailureClassifier and FlakyTestDetector.
"""

import unittest

from core.failure_classifier import FailureClassifier, FlakyTestDetector
from core.test_result_models import FailureType, SingleTestResult, TestStatus


class TestFailureClassifier(unittest.TestCase):
    def test_classify_assertion_failure(self):
        msg = "AssertionError: Expected 42, but got 41"
        ftype, conf, _ = FailureClassifier.classify(message=msg)
        self.assertEqual(ftype, FailureType.ASSERTION_FAILURE)
        self.assertGreaterEqual(conf, 0.8)

    def test_classify_syntax_error(self):
        msg = "SyntaxError: invalid syntax (main.py, line 12)"
        ftype, conf, _ = FailureClassifier.classify(message=msg)
        self.assertEqual(ftype, FailureType.SYNTAX_ERROR)
        self.assertGreaterEqual(conf, 0.9)

    def test_classify_import_error(self):
        msg = "ModuleNotFoundError: No module named 'nonexistent_package'"
        ftype, conf, _ = FailureClassifier.classify(message=msg)
        self.assertEqual(ftype, FailureType.IMPORT_FAILURE)
        self.assertGreaterEqual(conf, 0.9)

    def test_classify_network_dependency(self):
        msg = "ConnectionRefusedError: [Errno 111] Connection refused on 127.0.0.1:5432"
        ftype, conf, _ = FailureClassifier.classify(message=msg)
        self.assertEqual(ftype, FailureType.NETWORK_DEPENDENCY_FAILURE)
        self.assertTrue(FailureClassifier.is_environmental(ftype))

    def test_classify_timeout(self):
        ftype, conf, _ = FailureClassifier.classify(message="Timeout", exit_code=124)
        self.assertEqual(ftype, FailureType.TEST_TIMEOUT)

    def test_classify_type_error(self):
        msg = "TypeError: unsupported operand type(s) for +: 'int' and 'str'"
        ftype, conf, _ = FailureClassifier.classify(message=msg)
        self.assertEqual(ftype, FailureType.TYPE_CHECKING_FAILURE)

    def test_classify_test_result_enrichment(self):
        test = SingleTestResult(
            test_id="test_mod",
            test_name="test_fn",
            status=TestStatus.FAILED,
            message="AssertionError: assert False",
        )
        enriched = FailureClassifier.classify_test_result(test)
        self.assertEqual(enriched.failure_type, FailureType.ASSERTION_FAILURE)


class TestFlakyTestDetector(unittest.TestCase):
    def test_flaky_detection_true(self):
        detector = FlakyTestDetector(max_retries=3)
        calls = [True, False, True]
        idx = 0

        def runner():
            nonlocal idx
            res = calls[idx % len(calls)]
            idx += 1
            return res

        is_flaky, pass_rate, _ = detector.evaluate_test(runner, "test_flaky_1")
        self.assertTrue(is_flaky)
        self.assertGreater(pass_rate, 0.0)
        self.assertLess(pass_rate, 1.0)

    def test_flaky_detection_false_consistent_pass(self):
        detector = FlakyTestDetector(max_retries=3)
        is_flaky, pass_rate, _ = detector.evaluate_test(lambda: True, "test_pass_1")
        self.assertFalse(is_flaky)
        self.assertEqual(pass_rate, 1.0)

    def test_flaky_detection_false_consistent_fail(self):
        detector = FlakyTestDetector(max_retries=3)
        is_flaky, pass_rate, _ = detector.evaluate_test(lambda: False, "test_fail_1")
        self.assertFalse(is_flaky)
        self.assertEqual(pass_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
