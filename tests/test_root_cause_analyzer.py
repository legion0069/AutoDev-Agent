"""
Unit tests for AutoDev v2.6 RootCauseAnalyzer and FailureEvidenceCollector.
"""

import os
import tempfile
import unittest

from core.diagnostic_models import ConfidenceLevel, FailureCategory
from core.failure_evidence import FailureEvidenceCollector
from core.root_cause_analyzer import RootCauseAnalyzer
from core.test_result_models import FailureType, SingleTestResult, TestStatus


class MockLLM:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def generate(self, prompt: str) -> str:
        return self.response_text


class TestRootCauseAnalyzer(unittest.TestCase):
    def test_evidence_collector_stack_parsing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "calculator.py")
            with open(src_file, "w") as f:
                f.write("def add(a, b):\n    return a - b\n")

            collector = FailureEvidenceCollector(tmpdir)
            stack_text = (
                f'Traceback (most recent call last):\n'
                f'  File "{src_file}", line 2, in add\n'
                f'    return a - b\n'
                f'AssertionError: assert 4 == 0\n'
            )
            frames = collector.parse_stack_trace(stack_text)
            self.assertEqual(len(frames), 1)
            self.assertEqual(frames[0].function_name, "add")
            self.assertEqual(frames[0].line_number, 2)
            self.assertTrue(frames[0].is_in_workspace)

            symbols = collector.extract_affected_symbols("calculator.py", 2)
            self.assertTrue(any("add" in s for s in symbols))

    def test_deterministic_syntax_diagnosis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = RootCauseAnalyzer(tmpdir)
            test_res = SingleTestResult(
                test_id="test_syntax",
                test_name="test_syntax",
                status=TestStatus.ERROR,
                failure_type=FailureType.SYNTAX_ERROR,
                message="SyntaxError: invalid syntax",
                stack_trace='File "calc.py", line 4\n  if True\n         ^\nSyntaxError: invalid syntax',
            )
            report = analyzer.analyze(test_res)
            self.assertIsNotNone(report.selected_hypothesis)
            self.assertEqual(report.selected_hypothesis.failure_category, FailureCategory.SYNTAX_ERROR)
            self.assertGreaterEqual(report.selected_hypothesis.confidence, 0.95)

    def test_deterministic_environmental_diagnosis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = RootCauseAnalyzer(tmpdir)
            test_res = SingleTestResult(
                test_id="test_db",
                test_name="test_db",
                status=TestStatus.FAILED,
                failure_type=FailureType.NETWORK_DEPENDENCY_FAILURE,
                message="ConnectionRefusedError: [Errno 111] Connection refused",
            )
            report = analyzer.analyze(test_res)
            self.assertIsNotNone(report.selected_hypothesis)
            self.assertTrue(report.selected_hypothesis.is_environmental)
            self.assertEqual(report.selected_hypothesis.failure_category, FailureCategory.ENVIRONMENTAL)

    def test_llm_assisted_diagnosis(self):
        llm_json = """
        {
          "hypotheses": [
            {
              "summary": "Off-by-one error in loop upper bound",
              "failure_category": "off_by_one",
              "affected_files": ["calc.py"],
              "affected_symbols": ["range_calc"],
              "supporting_evidence": ["Expected 10 items, got 9"],
              "confidence": 0.88,
              "estimated_risk": "low",
              "suggested_fix_description": "Change range(n) to range(n + 1)"
            }
          ]
        }
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = RootCauseAnalyzer(tmpdir, llm_client=MockLLM(llm_json))
            test_res = SingleTestResult(
                test_id="test_range",
                test_name="test_range",
                status=TestStatus.FAILED,
                failure_type=FailureType.RUNTIME_EXCEPTION,
                message="IndexError: list index out of range",
            )
            report = analyzer.analyze(test_res)
            self.assertTrue(report.llm_enhanced)
            self.assertIsNotNone(report.selected_hypothesis)
            self.assertEqual(report.selected_hypothesis.failure_category, FailureCategory.OFF_BY_ONE)


if __name__ == "__main__":
    unittest.main()
