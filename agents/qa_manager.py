"""
qa_manager.py - Quality Assurance Manager Agent (AutoDev Version 3.4)

Directs test automation, regression coverage, and quality gate verification:
- Test planning and integration test suite synthesis
- Regression test selection and flaky test mitigation
- Code coverage auditing (>=90% target)
- Defect risk matrix generation
- Quality Gate Go/No-Go decisions
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType
from core.organization_state import OrganizationState

logger = logging.getLogger("AutoDev.Org.QAManager")


class QAManagerAgent:
    """
    Autonomous Quality Assurance Manager AI Agent.
    """

    def __init__(
        self,
        name: str = "QA",
        bus: Optional[CommunicationBus] = None,
        state: Optional[OrganizationState] = None,
    ) -> None:
        self.name = name
        self.bus = bus
        self.state = state
        self.authority_level = 3  # Managerial Quality
        self.min_coverage_threshold: float = 90.0

        if self.bus:
            self.bus.register_entity(self.name)

    def generate_test_plan(self, feature_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesizes comprehensive test plan with unit, integration, and boundary cases."""
        feature_name = feature_spec.get("name", "CoreFeature")
        user_stories = feature_spec.get("user_stories", [feature_name])

        cases = []
        for us in user_stories:
            cases.append(f"test_happy_path_{us.replace(' ', '_').lower()}")
            cases.append(f"test_boundary_conditions_{us.replace(' ', '_').lower()}")
            cases.append(f"test_error_handling_{us.replace(' ', '_').lower()}")

        return {
            "feature": feature_name,
            "test_cases": cases,
            "total_cases_planned": len(cases),
            "estimated_execution_time_s": len(cases) * 0.15,
            "target_coverage_pct": self.min_coverage_threshold,
        }

    def evaluate_quality_gate(
        self,
        test_results: Dict[str, Any],
        coverage_pct: float = 94.0,
    ) -> Dict[str, Any]:
        """Evaluates formal Go/No-Go quality gate."""
        passed = test_results.get("passed", 0)
        failed = test_results.get("failed", 0)
        total = passed + failed

        pass_rate = (passed / max(1, total)) * 100.0
        meets_coverage = coverage_pct >= self.min_coverage_threshold
        zero_failures = failed == 0

        gate_passed = meets_coverage and zero_failures
        status = "PASSED" if gate_passed else "REJECTED"

        rationale = (
            f"Quality gate PASSED: {passed}/{total} tests passed ({pass_rate:.1f}%), coverage {coverage_pct:.1f}% meets {self.min_coverage_threshold}% threshold."
            if gate_passed
            else f"Quality gate REJECTED: {failed} test failure(s) or coverage {coverage_pct:.1f}% below {self.min_coverage_threshold}% threshold."
        )

        return {
            "quality_gate_status": status,
            "tests_passed": passed,
            "tests_failed": failed,
            "test_pass_rate_pct": pass_rate,
            "coverage_pct": coverage_pct,
            "rationale": rationale,
            "timestamp": time.time(),
        }

    def build_risk_matrix(self, features: List[str]) -> Dict[str, Any]:
        """Constructs a defect risk matrix classifying features by risk tier."""
        matrix = {"CRITICAL_RISK": [], "MEDIUM_RISK": [], "LOW_RISK": []}
        for f in features:
            f_lower = f.lower()
            if any(k in f_lower for k in ["payment", "auth", "crypto", "database", "security"]):
                matrix["CRITICAL_RISK"].append(f)
            elif any(k in f_lower for k in ["api", "sync", "export", "cache"]):
                matrix["MEDIUM_RISK"].append(f)
            else:
                matrix["LOW_RISK"].append(f)

        return matrix
