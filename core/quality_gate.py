"""
AutoDev Quality Gate Engine (v2.7)
Evaluates code metrics, complexity bounds, risk probabilities, and architectural health
against configurable QualityGatePolicy thresholds to enforce pre-code-generation guardrails.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.quality_models import (
    ComplexityMetrics,
    DependencyHealthMetrics,
    PredictiveRiskScores,
    QualityGatePolicy,
    QualityGateResult,
    QualityGateStatus,
    QualityIssue,
    QualitySeverity,
)

logger = logging.getLogger(__name__)


class QualityGate:
    """Evaluates quality metrics against strict threshold policies."""

    def __init__(self, policy: Optional[QualityGatePolicy] = None):
        self.policy = policy or QualityGatePolicy()

    def evaluate(
        self,
        complexity: ComplexityMetrics,
        dependency_health: DependencyHealthMetrics,
        risk_scores: PredictiveRiskScores,
        issues: List[QualityIssue],
        duplication_percentage: float = 0.0,
    ) -> QualityGateResult:
        """
        Evaluates metrics against policy thresholds.
        Returns: QualityGateResult with status, rejection reasons, and refactoring suggestions.
        """
        rejection_reasons: List[str] = []
        warning_reasons: List[str] = []
        refactoring_suggestions: List[str] = []

        # 1. Cyclomatic Complexity Check
        if complexity.cyclomatic_complexity > self.policy.max_cyclomatic_complexity:
            rejection_reasons.append(
                f"Cyclomatic complexity ({complexity.cyclomatic_complexity}) exceeds maximum threshold ({self.policy.max_cyclomatic_complexity})."
            )
            refactoring_suggestions.append(
                "Extract sub-routines or use polymorphism / lookup tables to reduce decision points."
            )

        # 2. Cognitive Complexity Check
        if complexity.cognitive_complexity > self.policy.max_cognitive_complexity:
            rejection_reasons.append(
                f"Cognitive complexity ({complexity.cognitive_complexity}) exceeds maximum threshold ({self.policy.max_cognitive_complexity})."
            )
            refactoring_suggestions.append(
                "Flatten nested control structures and simplify compound boolean conditionals."
            )

        # 3. Maximum Nesting Depth Check
        if complexity.max_nesting_depth > self.policy.max_nesting_depth:
            rejection_reasons.append(
                f"Maximum nesting depth ({complexity.max_nesting_depth}) exceeds maximum limit ({self.policy.max_nesting_depth})."
            )
            refactoring_suggestions.append(
                "Use early guard-clause returns (`return early`) to flatten indentation levels."
            )

        # 4. Maintainability Index Check
        if complexity.maintainability_index < self.policy.min_maintainability_index:
            rejection_reasons.append(
                f"Maintainability index ({complexity.maintainability_index:.1f}) is below minimum threshold ({self.policy.min_maintainability_index:.1f})."
            )
            refactoring_suggestions.append(
                "Refactor monolithic functions into modular, single-responsibility units with docstrings."
            )

        # 5. Duplication Percentage Check
        if duplication_percentage > self.policy.max_duplication_percentage:
            rejection_reasons.append(
                f"Code duplication density ({duplication_percentage:.1f}%) exceeds maximum allowed ({self.policy.max_duplication_percentage:.1f}%)."
            )
            refactoring_suggestions.append(
                "Extract repeated code blocks into shared library utilities or abstract base classes."
            )

        # 6. Regression Probability Check
        if risk_scores.regression_probability > self.policy.max_regression_probability:
            rejection_reasons.append(
                f"Predicted regression probability ({risk_scores.regression_probability:.2f}) exceeds policy limit ({self.policy.max_regression_probability:.2f})."
            )
            refactoring_suggestions.append(
                "Narrow change blast radius or write targeted unit tests before applying modifications."
            )

        # 7. Security Confidence Check
        if risk_scores.security_confidence < self.policy.min_security_confidence:
            rejection_reasons.append(
                f"Security confidence ({risk_scores.security_confidence:.2f}) is below required minimum ({self.policy.min_security_confidence:.2f})."
            )
            refactoring_suggestions.append(
                "Perform security review and verify parameter sanitization / access control checks."
            )

        # 8. Circular Dependency Check
        if self.policy.disallow_circular_dependencies and dependency_health.has_circular_dependencies:
            rejection_reasons.append(
                f"Circular dependency detected in {dependency_health.circular_dependency_cycles}."
            )
            refactoring_suggestions.append(
                "Break circular imports using Dependency Inversion (interfaces) or extracting shared types."
            )

        # 9. God Object Check
        if self.policy.disallow_god_objects and dependency_health.is_god_object:
            rejection_reasons.append(
                f"Module exhibits God Object characteristics with excessive coupling (Ca={dependency_health.afferent_coupling}, Ce={dependency_health.efferent_coupling})."
            )
            refactoring_suggestions.append(
                "Split God class/module into decoupled service components."
            )

        # 10. Critical Issues Check
        critical_issues = [i for i in issues if i.severity == QualitySeverity.CRITICAL]
        if critical_issues:
            for ci in critical_issues:
                rejection_reasons.append(f"Critical Quality Rule Violation: {ci.description}")
                if ci.remediation_suggestion and ci.remediation_suggestion not in refactoring_suggestions:
                    refactoring_suggestions.append(ci.remediation_suggestion)

        # Determine Final Status
        if rejection_reasons:
            status = QualityGateStatus.REJECTED
            summary = f"Quality Gate REJECTED with {len(rejection_reasons)} blocking violation(s)."
        elif warning_reasons:
            status = QualityGateStatus.WARNING
            summary = f"Quality Gate PASSED with {len(warning_reasons)} warning(s)."
        else:
            status = QualityGateStatus.PASSED
            summary = "Quality Gate PASSED all policy threshold criteria."

        return QualityGateResult(
            status=status,
            rejection_reasons=rejection_reasons,
            warning_reasons=warning_reasons,
            refactoring_suggestions=list(dict.fromkeys(refactoring_suggestions)),
            evaluated_policy=self.policy,
            summary=summary,
        )
