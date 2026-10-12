"""
AutoDev Risk Predictor (v2.7)
Deterministic predictive risk modeling: regression probability, future failure probability,
architecture drift, API breaking risk, performance regressions, security risks,
and multi-dimensional engineering confidence scores.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from core.quality_metrics import calculate_composite_risk_score
from core.quality_models import (
    ComplexityMetrics,
    DependencyHealthMetrics,
    PredictiveRiskScores,
    QualityIssue,
    QualityRiskCategory,
    QualitySeverity,
)

logger = logging.getLogger(__name__)

SECURITY_KEYWORDS = {"auth", "crypto", "token", "secret", "certificate", "sandbox", "ebpf", "fencing", "isolation"}


class RiskPredictor:
    """Predicts pre-execution risks, failure probabilities, and quality confidence scores."""

    def predict_risks(
        self,
        complexity: ComplexityMetrics,
        dependency_health: DependencyHealthMetrics,
        issues: Optional[List[QualityIssue] | int] = None,
        impact_summary: Optional[Dict[str, Any]] = None,
        historical_defects_count: int = 0,
        modified_files: Optional[List[str]] = None,
        duplication_count: int = 0,
        *args: Any,
        **kwargs: Any,
    ) -> PredictiveRiskScores:
        """
        Computes deterministic probabilistic risk scores and confidence levels.
        """
        if isinstance(issues, (int, float)):
            duplication_count = int(issues)
            issues_val = kwargs.get("issues")
            if issues_val is None and len(args) > 0 and isinstance(args[0], list):
                issues_val = args[0]
            issues = issues_val or []
        else:
            issues = issues or []

        impact = impact_summary or {}
        mod_files = modified_files or []

        # 1. Complexity Risk Factor
        comp_risk = 0.0
        if complexity.cyclomatic_complexity > 20 or complexity.cognitive_complexity > 25:
            comp_risk = 0.8
        elif complexity.cyclomatic_complexity > 10 or complexity.cognitive_complexity > 15:
            comp_risk = 0.4
        elif complexity.max_nesting_depth >= 4:
            comp_risk = 0.5

        # 2. Instability & Architecture Risk
        instability_risk = dependency_health.instability
        arch_drift = dependency_health.distance_main_sequence
        if dependency_health.has_circular_dependencies:
            arch_drift = min(1.0, arch_drift + 0.4)
        if dependency_health.is_god_object:
            arch_drift = min(1.0, arch_drift + 0.3)

        # 3. Blast Radius & Regression Probability
        affected_callers = impact.get("affected_callers_count", 0)
        affected_tests = impact.get("affected_tests_count", 0)
        blast_factor = min(1.0, (affected_callers * 0.1) + (len(mod_files) * 0.15))

        hist_risk = min(1.0, historical_defects_count * 0.25)
        base_risk = 0.05
        if dependency_health.has_circular_dependencies:
            base_risk += 0.15
        if duplication_count > 0:
            base_risk += min(0.15, duplication_count * 0.03)

        reg_prob = min(
            1.0,
            base_risk
            + (0.35 * blast_factor)
            + (0.30 * comp_risk)
            + (0.25 * instability_risk)
            + (0.20 * hist_risk),
        )

        # 4. Specific Failure Category Predictions
        future_failure_prob = 0.1
        if complexity.maintainability_index < 40.0:
            future_failure_prob += 0.4
        if any(i.severity == QualitySeverity.CRITICAL for i in issues):
            future_failure_prob += 0.3
        future_failure_prob = min(1.0, round(future_failure_prob, 4))

        # API Breaking Change Risk
        api_breaking = 0.0
        if impact.get("public_api_changed", False) or any(
            i.category == QualityRiskCategory.API_CONTRACT_VIOLATION for i in issues
        ):
            api_breaking = 0.85
        elif any("api" in f.lower() or "interface" in f.lower() for f in mod_files):
            api_breaking = 0.45

        # Performance Regression Risk
        perf_risk = 0.0
        if complexity.max_nesting_depth >= 4 or complexity.longest_call_chain >= 4:
            perf_risk = 0.65
        elif complexity.cognitive_complexity > 20:
            perf_risk = 0.45

        # Security Risk
        sec_risk = 0.0
        for f in mod_files:
            if any(k in f.lower() for k in SECURITY_KEYWORDS):
                sec_risk = 0.75
                break
        for i in issues:
            cat = getattr(i, "category", "")
            cat_val = cat.value if hasattr(cat, "value") else str(cat)
            if cat_val in (QualityRiskCategory.SECURITY_VULNERABILITY.value, "security_vulnerability", "SECURITY_VULNERABILITY") or "sec" in getattr(i, "rule_id", "").lower():
                sec_risk = max(sec_risk, 0.70 if getattr(i, "severity", None) == QualitySeverity.CRITICAL else 0.45)

        # Concurrency & Deadlock Risk
        concurrency_risk = 0.0
        for i in issues:
            cat = getattr(i, "category", "")
            cat_val = cat.value if hasattr(cat, "value") else str(cat)
            if cat_val in (QualityRiskCategory.THREAD_SAFETY_RACE.value, QualityRiskCategory.CONCURRENCY_RISK.value, "concurrency_risk", "thread_safety_race", "THREAD_SAFETY_RACE", "CONCURRENCY_RISK") or "thread" in getattr(i, "rule_id", "").lower():
                concurrency_risk = 0.80

        # Timeout & Resource Leak Risk
        leak_risk = 0.0
        for i in issues:
            cat = getattr(i, "category", "")
            cat_val = cat.value if hasattr(cat, "value") else str(cat)
            if cat_val in (QualityRiskCategory.RESOURCE_MEMORY_LEAK.value, "resource_memory_leak", "RESOURCE_MEMORY_LEAK") or "resource" in getattr(i, "rule_id", "").lower() or "leak" in getattr(i, "rule_id", "").lower():
                leak_risk = 0.70

        # Confidence Levels
        review_conf = max(0.2, min(1.0, 1.0 - (comp_risk * 0.5 + arch_drift * 0.3)))
        sec_conf = max(0.2, min(1.0, 1.0 - sec_risk))
        test_conf = max(0.2, min(1.0, 0.4 + (0.6 if affected_tests > 0 else 0.0) - (reg_prob * 0.3)))

        # Composite Overall Risk Score
        overall_risk = calculate_composite_risk_score(
            regression_prob=reg_prob,
            complexity_risk=comp_risk,
            instability_risk=instability_risk,
            security_risk=sec_risk,
            historical_defect_risk=hist_risk,
        )

        return PredictiveRiskScores(
            overall_risk_score=overall_risk,
            regression_probability=round(reg_prob, 4),
            future_failure_probability=future_failure_prob,
            architecture_drift_risk=round(arch_drift, 4),
            api_breaking_risk=round(api_breaking, 4),
            performance_regression_risk=round(perf_risk, 4),
            security_risk=round(sec_risk, 4),
            concurrency_race_risk=round(concurrency_risk, 4),
            timeout_leak_risk=round(leak_risk, 4),
            review_confidence=round(review_conf, 4),
            security_confidence=round(sec_conf, 4),
            testing_confidence=round(test_conf, 4),
            public_exposure_score=round(api_breaking, 4),
            mutation_risk=round(reg_prob * 0.8 + comp_risk * 0.2, 4),
        )
