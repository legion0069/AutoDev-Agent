"""
Unit tests for AutoDev v2.6 RepairPlanner and PatchGenerator.
"""

import os
import tempfile
import unittest

from core.diagnostic_models import DiagnosticReport, FailureCategory, RootCauseHypothesis
from core.patch_generator import PatchGenerator
from core.repair_models import RepairPlan, RepairPolicy, RiskLevel
from core.repair_planner import RepairPlanner


class TestRepairPlannerGenerator(unittest.TestCase):
    def test_repair_plan_creation_low_risk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            planner = RepairPlanner(tmpdir)
            hypo = RootCauseHypothesis(
                summary="Fix arithmetic logic",
                failure_category=FailureCategory.LOGIC_ERROR,
                affected_files=["math_utils.py"],
                affected_symbols=["add"],
                confidence=0.85,
                estimated_risk="low",
            )
            report = DiagnosticReport(test_id="test_math", selected_hypothesis=hypo)
            plan = planner.create_repair_plan(report)
            self.assertIsNotNone(plan)
            self.assertEqual(plan.risk_level, RiskLevel.LOW)
            self.assertFalse(plan.requires_human_approval)

    def test_repair_plan_creation_security_high_risk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            planner = RepairPlanner(tmpdir)
            hypo = RootCauseHypothesis(
                summary="Fix token validation",
                failure_category=FailureCategory.LOGIC_ERROR,
                affected_files=["core/auth_token.py"],
                affected_symbols=["verify_token"],
                confidence=0.90,
            )
            report = DiagnosticReport(test_id="test_auth", selected_hypothesis=hypo)
            plan = planner.create_repair_plan(report)
            self.assertIsNotNone(plan)
            self.assertEqual(plan.risk_level, RiskLevel.HIGH)
            self.assertTrue(plan.requires_human_approval)

    def test_patch_generator_unified_diff(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "calc.py")
            with open(src_file, "w") as f:
                f.write("def add(a, b):\n    return a - b\n")

            generator = PatchGenerator(tmpdir)
            plan = RepairPlan(
                target_files=["calc.py"],
                rationale="Change minus to plus",
            )
            new_code = "def add(a, b):\n    return a + b\n"
            patch = generator.generate_patch(plan, file_modifications={"calc.py": new_code})
            self.assertIsNotNone(patch)
            self.assertEqual(len(patch.file_patches), 1)
            fp = patch.file_patches[0]
            self.assertEqual(fp.file_path, "calc.py")
            self.assertIn("-    return a - b", fp.diff_unified)
            self.assertIn("+    return a + b", fp.diff_unified)
            self.assertEqual(fp.lines_added, 1)
            self.assertEqual(fp.lines_removed, 1)


if __name__ == "__main__":
    unittest.main()
