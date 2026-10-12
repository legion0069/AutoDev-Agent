"""
AutoDev Repair Planner (v2.6)
Synthesizes diagnostic hypotheses into structured, actionable repair plans
with risk classification and targeted test definitions.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Set

from core.diagnostic_models import DiagnosticReport, RootCauseHypothesis
from core.repair_models import RepairPlan, RepairPolicy, RiskLevel

logger = logging.getLogger(__name__)

# Security-sensitive keywords and module paths
SECURITY_SENSITIVE_PATHS = {
    "auth", "security", "consensus", "isolation", "crypto",
    "token", "certificate", "secret", "ebpf", "sandbox", "fencing"
}


class RepairPlanner:
    """Plans minimal-risk, evidence-supported repair actions from diagnostic findings."""

    def __init__(self, workspace_path: str, policy: Optional[RepairPolicy] = None):
        self.workspace_path = os.path.realpath(os.path.abspath(workspace_path))
        self.policy = policy or RepairPolicy()

    def create_repair_plan(
        self,
        diagnostic_report: DiagnosticReport,
        hypothesis: Optional[RootCauseHypothesis] = None,
    ) -> Optional[RepairPlan]:
        """Creates a RepairPlan from a diagnostic report and selected hypothesis."""
        target_hypo = hypothesis or diagnostic_report.selected_hypothesis
        if not target_hypo:
            logger.warning("No hypothesis available to generate repair plan.")
            return None

        # Determine risk and approval requirement
        risk_level, requires_approval = self._evaluate_risk(target_hypo)

        # Assemble targeted tests
        targeted_tests = [diagnostic_report.test_id] if diagnostic_report.test_id else []

        plan = RepairPlan(
            hypothesis_id=target_hypo.hypothesis_id,
            test_id=diagnostic_report.test_id,
            failing_behavior=diagnostic_report.evidence.failure_message if diagnostic_report.evidence else "Test failure",
            expected_behavior=target_hypo.suggested_fix_description or "Test passes and expected logic holds",
            target_files=list(target_hypo.affected_files),
            target_symbols=list(target_hypo.affected_symbols),
            targeted_tests=targeted_tests,
            rationale=target_hypo.summary,
            risk_level=risk_level,
            requires_human_approval=requires_approval or self.policy.require_human_approval,
        )
        return plan

    def _evaluate_risk(self, hypo: RootCauseHypothesis) -> tuple[RiskLevel, bool]:
        """Assesses change blast radius and security sensitivity."""
        # Check security sensitivity in affected files
        for f in hypo.affected_files:
            f_lower = f.lower()
            if any(k in f_lower for k in SECURITY_SENSITIVE_PATHS):
                return RiskLevel.HIGH, True

        # Check estimated risk from hypothesis
        if hypo.estimated_risk == "critical":
            return RiskLevel.CRITICAL, True
        elif hypo.estimated_risk == "high":
            return RiskLevel.HIGH, True
        elif len(hypo.affected_files) > 2:
            return RiskLevel.MEDIUM, False

        return RiskLevel.LOW, False
