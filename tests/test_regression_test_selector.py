"""
Unit tests for AutoDev v2.6 RegressionTestSelector across validation tiers.
"""

import os
import tempfile
import unittest

from core.regression_test_selector import RegressionTestSelector
from core.repair_models import CandidatePatch, FilePatch


class TestRegressionTestSelector(unittest.TestCase):
    def test_targeted_level_selection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = os.path.join(tmpdir, "tests")
            os.makedirs(tests_dir)
            with open(os.path.join(tests_dir, "test_calculator.py"), "w") as f:
                f.write("def test_add(): pass\n")
            with open(os.path.join(tests_dir, "test_unrelated.py"), "w") as f:
                f.write("def test_other(): pass\n")

            selector = RegressionTestSelector(tmpdir)
            patch = CandidatePatch(
                file_patches=[FilePatch(file_path="calculator.py", new_content="")]
            )

            res = selector.select_tests(patch, validation_level="targeted")
            self.assertEqual(res.validation_level, "targeted")
            self.assertTrue(any("test_calculator.py" in t for t in res.selected_tests))
            self.assertFalse(any("test_unrelated.py" in t for t in res.selected_tests))

    def test_standard_level_import_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = os.path.join(tmpdir, "tests")
            os.makedirs(tests_dir)
            with open(os.path.join(tests_dir, "test_calculator.py"), "w") as f:
                f.write("def test_add(): pass\n")
            with open(os.path.join(tests_dir, "test_service.py"), "w") as f:
                f.write("import calculator\ndef test_service(): pass\n")

            selector = RegressionTestSelector(tmpdir)
            patch = CandidatePatch(
                file_patches=[FilePatch(file_path="calculator.py", new_content="")]
            )

            res = selector.select_tests(patch, validation_level="standard")
            self.assertEqual(res.validation_level, "standard")
            self.assertTrue(any("test_calculator.py" in t for t in res.selected_tests))
            self.assertTrue(any("test_service.py" in t for t in res.selected_tests))

    def test_security_escalation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = os.path.join(tmpdir, "tests")
            os.makedirs(tests_dir)
            with open(os.path.join(tests_dir, "test_auth.py"), "w") as f:
                f.write("def test_auth(): pass\n")
            with open(os.path.join(tests_dir, "test_auth_integration.py"), "w") as f:
                f.write("def test_auth_int(): pass\n")

            selector = RegressionTestSelector(tmpdir)
            patch = CandidatePatch(
                file_patches=[FilePatch(file_path="core/auth_manager.py", new_content="")]
            )

            res = selector.select_tests(patch, validation_level="targeted")
            self.assertTrue(res.escalated)
            self.assertEqual(res.validation_level, "comprehensive")


if __name__ == "__main__":
    unittest.main()
