"""
tests/test_quality_report.py - Unit tests for AutoDev Quality Report Generator (v2.7)

Validates:
- Multi-format report generation (Markdown, HTML, JSON)
- Executive summary and Engineering breakdown rendering
- Risk matrix and heatmap data serialization
- Proactive refactoring suggestions rendering
"""

import json
import pytest
from core.quality_models import (
    ComplexityMetrics,
    DependencyHealthMetrics,
    PredictiveRiskScores,
    QualityAssessmentResult,
    QualityGateResult,
    QualityGateStatus,
    QualityIssue,
    QualityRiskCategory,
    QualitySeverity,
)
from core.quality_report import QualityReportGenerator


@pytest.fixture
def sample_assessment():
    """Constructs a sample QualityAssessmentResult fixture."""
    complexity = ComplexityMetrics(
        cyclomatic_complexity=6,
        cognitive_complexity=8,
        max_nesting_depth=3,
        maintainability_index=78.5,
        loc=450,
        sloc=380,
    )
    dep_health = DependencyHealthMetrics(
        instability=0.35,
        abstractness=0.20,
        distance_main_sequence=0.45,
    )
    risk_scores = PredictiveRiskScores(
        future_failure_probability=0.12,
        regression_probability=0.15,
        security_confidence=0.92,
        overall_risk_score=0.185,
    )
    gate_result = QualityGateResult(
        status=QualityGateStatus.PASSED,
        score=85.0,
        reasons=[],
        refactoring_suggestions=["Consider extracting helper functions for complex loops."],
    )
    issues = [
        QualityIssue(
            rule_id="QUAL-001",
            rule_name="Cognitive Complexity Warning",
            category=QualityRiskCategory.COMPLEXITY_EXPLOSION,
            severity=QualitySeverity.MEDIUM,
            description="Method process_data has cognitive complexity 8",
            remediation_suggestion="Extract inner processing block into a dedicated function.",
        )
    ]

    return QualityAssessmentResult(
        project_id="test_suite_project",
        task_id="task-001",
        aggregate_complexity=complexity,
        dependency_health=dep_health,
        risk_scores=risk_scores,
        gate_result=gate_result,
        issues=issues,
        recommendations=["Maintain modular architecture patterns."],
        remediation_suggestions=["Extract helper functions for complex loops."],
    )


def test_markdown_report_generation(sample_assessment):
    """Generates complete Markdown quality report containing key sections."""
    generator = QualityReportGenerator()
    md_content = generator.generate_markdown(sample_assessment)

    assert "# AutoDev Predictive Quality & Failure Prevention Report" in md_content
    assert "Maintainability Index" in md_content
    assert "78.5/100" in md_content
    assert "Quality Gate Status" in md_content
    assert "PASSED" in md_content
    assert "QUAL-001" in md_content


def test_html_report_generation(sample_assessment):
    """Generates styled HTML report."""
    generator = QualityReportGenerator()
    html_content = generator.generate_html(sample_assessment)

    assert "<!DOCTYPE html>" in html_content
    assert "AutoDev Quality Intelligence Report" in html_content
    assert "78.5" in html_content
    assert "PASSED" in html_content
    assert "Cognitive Complexity Warning" in html_content


def test_json_report_generation(sample_assessment):
    """Generates valid JSON machine-readable report."""
    generator = QualityReportGenerator()
    json_str = generator.generate_json(sample_assessment)

    data = json.loads(json_str)
    assert data["project_id"] == "test_suite_project"
    assert data["gate_result"]["status"] == "PASSED"
    assert data["aggregate_complexity"]["maintainability_index"] == 78.5
    assert len(data["issues"]) == 1
    assert data["issues"][0]["rule_id"] == "QUAL-001"


def test_save_all_formats_to_disk(sample_assessment, tmp_path):
    """Saves Markdown, HTML, and JSON reports to disk simultaneously."""
    generator = QualityReportGenerator()
    out_dir = tmp_path / "reports"
    files = generator.export_all(sample_assessment, output_dir=str(out_dir), base_name="quality_summary")

    assert (out_dir / "quality_summary.md").exists()
    assert (out_dir / "quality_summary.html").exists()
    assert (out_dir / "quality_summary.json").exists()
