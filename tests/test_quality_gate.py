"""
tests/test_quality_gate.py - Unit tests for AutoDev Quality Gate (v2.7)

Validates:
- Quality gate threshold policy enforcement (PASSED, WARNING, REJECTED)
- Fail-closed rejections for critical complexity, security confidence, and regression risk
- Rejection diagnosis with root cause, evidence metrics, and refactoring suggestions
"""

import pytest
from core.quality_gate import QualityGate
from core.quality_models import (
    ComplexityMetrics,
    DependencyHealthMetrics,
    PredictiveRiskScores,
    QualityGatePolicy,
    QualityGateStatus,
    QualityIssue,
    QualityRiskCategory,
    QualitySeverity,
)


def test_quality_gate_passed_for_healthy_metrics():
    """All healthy metrics below policy thresholds pass the quality gate cleanly."""
    policy = QualityGatePolicy(
        max_cyclomatic_complexity=15,
        min_maintainability_index=60.0,
        max_regression_probability=0.35,
        min_security_confidence=0.80,
    )
    gate = QualityGate(policy=policy)

    complexity = ComplexityMetrics(
        cyclomatic_complexity=4,
        maintainability_index=85.0,
    )
    dep_health = DependencyHealthMetrics()
    risks = PredictiveRiskScores(
        regression_probability=0.10,
        security_confidence=0.95,
        future_failure_probability=0.08,
    )

    result = gate.evaluate(
        complexity=complexity,
        dependency_health=dep_health,
        risk_scores=risks,
        issues=[],
    )

    assert result.status == QualityGateStatus.PASSED
    assert len(result.reasons) == 0
    assert result.score > 80.0


def test_quality_gate_rejection_due_to_extreme_complexity():
    """Exceeding max cyclomatic complexity triggers a gate rejection with actionable suggestions."""
    policy = QualityGatePolicy(max_cyclomatic_complexity=15)
    gate = QualityGate(policy=policy)

    complexity = ComplexityMetrics(
        cyclomatic_complexity=28,  # > 15
        maintainability_index=45.0,
    )
    dep_health = DependencyHealthMetrics()
    risks = PredictiveRiskScores(regression_probability=0.20, security_confidence=0.90)

    result = gate.evaluate(
        complexity=complexity,
        dependency_health=dep_health,
        risk_scores=risks,
        issues=[],
    )

    assert result.status == QualityGateStatus.REJECTED
    assert any("Cyclomatic complexity" in r for r in result.reasons)
    assert len(result.refactoring_suggestions) >= 1


def test_quality_gate_rejection_due_to_security_confidence():
    """Security confidence below minimum threshold triggers rejection."""
    policy = QualityGatePolicy(min_security_confidence=0.80)
    gate = QualityGate(policy=policy)

    complexity = ComplexityMetrics(cyclomatic_complexity=5, maintainability_index=80.0)
    dep_health = DependencyHealthMetrics()
    risks = PredictiveRiskScores(security_confidence=0.60)  # < 0.80

    result = gate.evaluate(
        complexity=complexity,
        dependency_health=dep_health,
        risk_scores=risks,
        issues=[],
    )

    assert result.status == QualityGateStatus.REJECTED
    assert any("Security confidence" in r for r in result.reasons)


def test_quality_gate_rejection_due_to_circular_dependencies():
    """Circular imports trigger gate rejection when policy blocks cycles."""
    policy = QualityGatePolicy(allow_circular_dependencies=False)
    gate = QualityGate(policy=policy)

    complexity = ComplexityMetrics(cyclomatic_complexity=3, maintainability_index=85.0)
    dep_health = DependencyHealthMetrics(
        has_circular_dependencies=True,
        circular_dependency_cycles=[["pkg/a.py", "pkg/b.py", "pkg/a.py"]],
    )
    risks = PredictiveRiskScores(security_confidence=0.90, regression_probability=0.10)

    result = gate.evaluate(
        complexity=complexity,
        dependency_health=dep_health,
        risk_scores=risks,
        issues=[],
    )

    assert result.status == QualityGateStatus.REJECTED
    assert any("Circular dependency" in r for r in result.reasons)


def test_quality_gate_warning_mode():
    """Minor issues create a WARNING status instead of REJECTED when non-blocking."""
    policy = QualityGatePolicy(
        max_cyclomatic_complexity=20,
        min_maintainability_index=60.0,
    )
    gate = QualityGate(policy=policy)

    complexity = ComplexityMetrics(
        cyclomatic_complexity=12,
        maintainability_index=65.0,
    )
    dep_health = DependencyHealthMetrics()
    risks = PredictiveRiskScores(regression_probability=0.25, security_confidence=0.85)

    minor_issue = QualityIssue(
        rule_id="WARN-001",
        rule_name="Unused Import",
        category=QualityRiskCategory.DEAD_CODE,
        severity=QualitySeverity.LOW,
        description="Unused import os",
    )

    result = gate.evaluate(
        complexity=complexity,
        dependency_health=dep_health,
        risk_scores=risks,
        issues=[minor_issue],
    )

    assert result.status in (QualityGateStatus.PASSED, QualityGateStatus.WARNING)
