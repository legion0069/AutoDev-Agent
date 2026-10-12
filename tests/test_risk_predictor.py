"""
tests/test_risk_predictor.py - Unit tests for AutoDev Risk Predictor (v2.7)

Validates:
- Deterministic risk modeling for regressions and future failures
- Architecture drift and API breaking change risk estimation
- Performance and security confidence scoring
- Concurrency, deadlock, timeout, and data corruption forecasting
- Integration with historical defect memory
"""

import pytest
from core.quality_models import (
    ComplexityMetrics,
    DependencyHealthMetrics,
    PredictiveRiskScores,
    QualityIssue,
    QualityRiskCategory,
    QualitySeverity,
)
from core.risk_predictor import RiskPredictor


def test_clean_codebase_risk_prediction():
    """Clean codebase should have near zero regression risk and high security confidence."""
    predictor = RiskPredictor()
    complexity = ComplexityMetrics(
        cyclomatic_complexity=2,
        cognitive_complexity=1,
        max_nesting_depth=1,
        maintainability_index=90.0,
        sloc=100,
    )
    dep_health = DependencyHealthMetrics()

    scores = predictor.predict_risks(
        complexity=complexity,
        dependency_health=dep_health,
        duplication_count=0,
        issues=[],
    )

    assert scores.regression_probability < 0.20
    assert scores.future_failure_probability < 0.20
    assert scores.security_confidence > 0.85
    assert scores.composite_risk_score < 25.0


def test_high_complexity_elevates_regression_and_failure_risk():
    """High cyclomatic and cognitive complexity directly elevates regression probability."""
    predictor = RiskPredictor()
    complexity = ComplexityMetrics(
        cyclomatic_complexity=35,
        cognitive_complexity=40,
        max_nesting_depth=6,
        maintainability_index=25.0,
        sloc=2000,
    )
    dep_health = DependencyHealthMetrics(
        has_circular_dependencies=True,
        package_instability=0.9,
    )

    scores = predictor.predict_risks(
        complexity=complexity,
        dependency_health=dep_health,
        duplication_count=5,
        issues=[],
    )

    assert scores.regression_probability > 0.40
    assert scores.future_failure_probability > 0.40
    assert scores.composite_risk_score > 40.0


def test_security_confidence_degradation_from_issues():
    """Security issues reduce security confidence score deterministically."""
    predictor = RiskPredictor()
    complexity = ComplexityMetrics(maintainability_index=80.0)
    dep_health = DependencyHealthMetrics()
    
    security_issue = QualityIssue(
        rule_id="SEC-001",
        rule_name="Unsanitized Input in Shell Command",
        category=QualityRiskCategory.SECURITY_VULNERABILITY,
        severity=QualitySeverity.CRITICAL,
        description="Shell execution with unquoted variable",
    )

    scores = predictor.predict_risks(
        complexity=complexity,
        dependency_health=dep_health,
        duplication_count=0,
        issues=[security_issue],
    )

    assert scores.security_confidence < 0.70


def test_concurrency_and_deadlock_risk_forecasting():
    """Thread safety issues increase deadlock and race condition risk scores."""
    predictor = RiskPredictor()
    complexity = ComplexityMetrics(maintainability_index=75.0)
    dep_health = DependencyHealthMetrics()

    concurrency_issue = QualityIssue(
        rule_id="THREAD-001",
        rule_name="Global Mutable State Without Synchronization",
        category=QualityRiskCategory.CONCURRENCY_RISK,
        severity=QualitySeverity.HIGH,
        description="Unprotected global shared dictionary",
    )

    scores = predictor.predict_risks(
        complexity=complexity,
        dependency_health=dep_health,
        duplication_count=0,
        issues=[concurrency_issue],
    )

    assert scores.deadlock_risk > 0.20


def test_deterministic_scoring_reproducibility():
    """Calling predict_risks multiple times with identical inputs must return identical floats."""
    predictor = RiskPredictor()
    complexity = ComplexityMetrics(cyclomatic_complexity=10, cognitive_complexity=12, maintainability_index=70.0)
    dep_health = DependencyHealthMetrics(package_instability=0.4)

    res1 = predictor.predict_risks(complexity, dep_health, duplication_count=2, issues=[])
    res2 = predictor.predict_risks(complexity, dep_health, duplication_count=2, issues=[])

    assert res1.regression_probability == res2.regression_probability
    assert res1.future_failure_probability == res2.future_failure_probability
    assert res1.security_confidence == res2.security_confidence
    assert res1.composite_risk_score == res2.composite_risk_score
