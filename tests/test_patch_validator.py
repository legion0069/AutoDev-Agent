"""
Unit tests for AutoDev v2.6 PatchValidator, anti-weakening rules,
AST syntax verification, and containment checks.
"""

import os
import tempfile
import unittest

from core.patch_validator import PatchValidator
from core.repair_models import CandidatePatch, FilePatch, RepairPolicy, RiskLevel


class TestPatchValidator(unittest.TestCase):
    def test_valid_patch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = PatchValidator(tmpdir)
            fp = FilePatch(
                file_path="service.py",
                original_content="def process(): return 0\n",
                new_content="def process(): return 1\n",
            )
            patch = CandidatePatch(file_patches=[fp])
            res = validator.validate(patch)
            self.assertTrue(res.is_valid)
            self.assertTrue(res.syntax_ok)
            self.assertTrue(res.containment_ok)

    def test_reject_syntax_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = PatchValidator(tmpdir)
            fp = FilePatch(
                file_path="service.py",
                original_content="def process(): return 0\n",
                new_content="def process(): return (\n",
            )
            patch = CandidatePatch(file_patches=[fp])
            res = validator.validate(patch)
            self.assertFalse(res.is_valid)
            self.assertFalse(res.syntax_ok)
            self.assertTrue(any("Syntax validation failed" in r for r in res.rejection_reasons))

    def test_reject_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = PatchValidator(tmpdir)
            fp = FilePatch(
                file_path="../outside.py",
                original_content="",
                new_content="import os\n",
            )
            patch = CandidatePatch(file_patches=[fp])
            res = validator.validate(patch)
            self.assertFalse(res.is_valid)
            self.assertFalse(res.containment_ok)
            self.assertTrue(any("traversal" in r for r in res.rejection_reasons))

    def test_reject_silent_exception_suppression(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = PatchValidator(tmpdir)
            fp = FilePatch(
                file_path="service.py",
                original_content="def calc(): return 1/0\n",
                new_content="def calc():\n    try:\n        return 1/0\n    except:\n        pass\n",
            )
            patch = CandidatePatch(file_patches=[fp])
            res = validator.validate(patch)
            self.assertFalse(res.is_valid)
            self.assertFalse(res.anti_weakening_ok)
            self.assertTrue(any("silent exception" in r for r in res.rejection_reasons))

    def test_reject_test_weakening_assert_deletion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = PatchValidator(tmpdir)
            fp = FilePatch(
                file_path="tests/test_service.py",
                original_content="def test_foo():\n    assert service.calc() == 42\n",
                new_content="def test_foo():\n    pass\n",
            )
            patch = CandidatePatch(file_patches=[fp])
            res = validator.validate(patch)
            self.assertFalse(res.is_valid)
            self.assertFalse(res.anti_weakening_ok)
            self.assertTrue(any("weakening" in r for r in res.rejection_reasons))

    def test_security_sensitive_flagging(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = RepairPolicy(allow_security_sensitive_changes=False)
            validator = PatchValidator(tmpdir, policy)
            fp = FilePatch(
                file_path="core/auth_manager.py",
                original_content="def verify(): return False\n",
                new_content="def verify(): return True\n",
            )
            patch = CandidatePatch(file_patches=[fp])
            res = validator.validate(patch)
            self.assertTrue(res.is_valid)
            self.assertTrue(fp.is_security_sensitive)
            self.assertEqual(patch.risk_level, RiskLevel.HIGH)
            self.assertTrue(len(res.warnings) > 0)


if __name__ == "__main__":
    unittest.main()
