"""
AutoDev Quality Report Generator (v2.7)
Generates comprehensive Markdown, HTML, and JSON reports from QualityAssessmentResult,
including Executive Summaries, Risk Matrices, Heatmaps, and Trend analysis.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from core.quality_models import QualityAssessmentResult, QualityGateStatus, QualitySeverity


class QualityReportGenerator:
    """Generates multi-format quality assessment documentation."""

    @classmethod
    def generate_markdown(cls, assessment: QualityAssessmentResult) -> str:
        """Renders comprehensive Markdown quality intelligence report."""
        status_icon = "✅" if assessment.gate_result.is_passed else "❌"
        status_text = assessment.gate_result.status.value

        md_lines = [
            f"# AutoDev Predictive Quality & Failure Prevention Report",
            f"",
            f"**Assessment ID:** `{assessment.assessment_id}`  ",
            f"**Timestamp:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(assessment.timestamp))}  ",
            f"**Quality Gate Status:** {status_icon} **{status_text}**  ",
            f"",
            f"---",
            f"",
            f"## 1. Executive Summary",
            f"",
            f"- **Overall Maintainability Index:** `{assessment.overall_maintainability_index:.1f}/100`",
            f"- **Total Estimated Technical Debt:** `{assessment.total_technical_debt_minutes} minutes` (`{assessment.total_technical_debt_minutes / 60.0:.1f} hours`)",
            f"- **Predicted Regression Probability:** `{assessment.risk_scores.regression_probability * 100.0:.1f}%`",
            f"- **Overall Risk Score:** `{assessment.risk_scores.overall_risk_score:.2f} / 1.00`",
            f"- **Code Duplication Density:** `{assessment.duplication_percentage:.1f}%`",
            f"",
            f"---",
            f"",
            f"## 2. Engineering Metrics Breakdown",
            f"",
            f"| Metric | Measured Value | Standard Target | Status |",
            f"| :--- | :--- | :--- | :--- |",
            f"| **Cyclomatic Complexity** | {assessment.complexity_summary.cyclomatic_complexity} | ≤ 15 | {'🟢 OK' if assessment.complexity_summary.cyclomatic_complexity <= 15 else '🔴 High'} |",
            f"| **Cognitive Complexity** | {assessment.complexity_summary.cognitive_complexity} | ≤ 20 | {'🟢 OK' if assessment.complexity_summary.cognitive_complexity <= 20 else '🔴 High'} |",
            f"| **Max Nesting Depth** | {assessment.complexity_summary.max_nesting_depth} | ≤ 4 | {'🟢 OK' if assessment.complexity_summary.max_nesting_depth <= 4 else '🔴 Deep'} |",
            f"| **Maintainability Index (MI)** | {assessment.overall_maintainability_index:.1f} | ≥ 40.0 | {'🟢 Healthy' if assessment.overall_maintainability_index >= 40.0 else '🔴 Degraded'} |",
            f"| **Package Instability (I)** | {assessment.dependency_health.instability:.2f} | ≤ 0.85 | {'🟢 Stable' if assessment.dependency_health.instability <= 0.85 else '🟡 Unstable'} |",
            f"| **Distance from Main Seq (D)** | {assessment.dependency_health.distance_main_sequence:.2f} | ≤ 0.50 | {'🟢 Balanced' if assessment.dependency_health.distance_main_sequence <= 0.50 else '🟡 Skewed'} |",
            f"| **Circular Dependencies** | {len(assessment.dependency_health.circular_dependency_cycles)} | 0 | {'🟢 None' if not assessment.dependency_health.has_circular_dependencies else '🔴 Detected'} |",
            f"",
            f"---",
            f"",
            f"## 3. Predictive Risk Matrix",
            f"",
            f"| Risk Dimension | Predicted Probability / Score | Risk Category |",
            f"| :--- | :--- | :--- |",
            f"| **Regression Probability** | `{assessment.risk_scores.regression_probability:.2f}` | {'🔴 High' if assessment.risk_scores.regression_probability > 0.4 else '🟢 Low'} |",
            f"| **Future Failure Probability** | `{assessment.risk_scores.future_failure_probability:.2f}` | {'🔴 High' if assessment.risk_scores.future_failure_probability > 0.4 else '🟢 Low'} |",
            f"| **Architecture Drift Risk** | `{assessment.risk_scores.architecture_drift_risk:.2f}` | {'🟡 Moderate' if assessment.risk_scores.architecture_drift_risk > 0.3 else '🟢 Low'} |",
            f"| **API Breaking Risk** | `{assessment.risk_scores.api_breaking_risk:.2f}` | {'🔴 High' if assessment.risk_scores.api_breaking_risk > 0.5 else '🟢 Low'} |",
            f"| **Performance Regression Risk** | `{assessment.risk_scores.performance_regression_risk:.2f}` | {'🟡 Moderate' if assessment.risk_scores.performance_regression_risk > 0.4 else '🟢 Low'} |",
            f"| **Security Risk** | `{assessment.risk_scores.security_risk:.2f}` | {'🔴 High' if assessment.risk_scores.security_risk > 0.5 else '🟢 Low'} |",
            f"",
            f"---",
            f"",
            f"## 4. Quality Gate Violations & Findings",
            f"",
        ]

        if not assessment.issues:
            md_lines.append("🎉 **No quality issues or rule violations identified.**")
        else:
            for idx, issue in enumerate(assessment.issues, 1):
                sev_badge = "🔴" if issue.severity == QualitySeverity.CRITICAL else "🟠" if issue.severity == QualitySeverity.HIGH else "🟡"
                loc_str = f"`{issue.location.file_path}:L{issue.location.start_line}`" if issue.location else "Workspace"
                md_lines.extend([
                    f"### {idx}. {sev_badge} [{issue.rule_id}] {issue.rule_name}",
                    f"- **Location:** {loc_str}",
                    f"- **Severity:** `{issue.severity.value}`",
                    f"- **Description:** {issue.description}",
                    f"- **Remediation:** {issue.remediation_suggestion}",
                    f"- **Technical Debt:** `{issue.technical_debt_minutes} min`",
                    f"",
                ])

        if assessment.gate_result.refactoring_suggestions:
            md_lines.extend([
                f"## 5. Actionable Refactoring Roadmap",
                f"",
            ])
            for sug in assessment.gate_result.refactoring_suggestions:
                md_lines.append(f"- 💡 {sug}")

        return "\n".join(md_lines)

    @classmethod
    def generate_html(cls, assessment: QualityAssessmentResult) -> str:
        """Renders styled HTML dashboard report for UI and artifact embedding."""
        status_color = "#10b981" if assessment.gate_result.is_passed else "#ef4444"
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>AutoDev Quality Intelligence Report - {assessment.assessment_id}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0f19; color: #f3f4f6; padding: 2rem; }}
    .card {{ background: rgba(18, 24, 38, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem; backdrop-filter: blur(12px); }}
    .badge {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-weight: 600; font-size: 0.85rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
    .metric-val {{ font-size: 1.5rem; font-weight: bold; color: #06b6d4; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
    th, td {{ text-align: left; padding: 0.75rem; border-bottom: 1px solid rgba(255, 255, 255, 0.08); }}
    th {{ color: #9ca3af; font-size: 0.85rem; text-transform: uppercase; }}
  </style>
</head>
<body>
  <h1>AutoDev Quality Intelligence Report</h1>
  <div class="card">
    <h2>Quality Gate Status: <span class="badge" style="background: {status_color}22; color: {status_color}; border: 1px solid {status_color};">{assessment.gate_result.status.value}</span></h2>
    <p style="color: #9ca3af;">Assessment ID: <code>{assessment.assessment_id}</code> | Project: <code>{assessment.project_id}</code></p>
  </div>

  <div class="grid">
    <div class="card">
      <div style="color: #9ca3af; font-size: 0.8rem;">Maintainability Index</div>
      <div class="metric-val">{assessment.overall_maintainability_index:.1f}/100</div>
    </div>
    <div class="card">
      <div style="color: #9ca3af; font-size: 0.8rem;">Technical Debt</div>
      <div class="metric-val" style="color: #f59e0b;">{assessment.total_technical_debt_minutes} min</div>
    </div>
    <div class="card">
      <div style="color: #9ca3af; font-size: 0.8rem;">Regression Probability</div>
      <div class="metric-val" style="color: #ef4444;">{assessment.risk_scores.regression_probability * 100.0:.1f}%</div>
    </div>
    <div class="card">
      <div style="color: #9ca3af; font-size: 0.8rem;">Duplication Density</div>
      <div class="metric-val" style="color: #8b5cf6;">{assessment.duplication_percentage:.1f}%</div>
    </div>
  </div>

  <div class="card">
    <h2>Quality Gate Findings ({len(assessment.issues)})</h2>
    <table>
      <thead>
        <tr><th>Rule ID</th><th>Rule Name</th><th>Severity</th><th>Description</th><th>Debt</th></tr>
      </thead>
      <tbody>
        {''.join(f'<tr><td><code>{i.rule_id}</code></td><td>{i.rule_name}</td><td>{i.severity.value}</td><td>{i.description}</td><td>{i.technical_debt_minutes}m</td></tr>' for i in assessment.issues)}
      </tbody>
    </table>
  </div>
</body>
</html>"""

    @classmethod
    def generate_json(cls, assessment: QualityAssessmentResult) -> str:
        """Returns normalized machine-readable JSON schema string."""
        return json.dumps(assessment.to_dict(), indent=2)

    @classmethod
    def export_all(cls, assessment: QualityAssessmentResult, output_dir: str = ".", base_name: str = "quality_report") -> Dict[str, str]:
        """Saves Markdown, HTML, and JSON reports to disk simultaneously."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        md_path = os.path.join(output_dir, f"{base_name}.md")
        html_path = os.path.join(output_dir, f"{base_name}.html")
        json_path = os.path.join(output_dir, f"{base_name}.json")

        md_content = cls.generate_markdown(assessment)
        html_content = cls.generate_html(assessment)
        json_content = cls.generate_json(assessment)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(json_content)

        return {
            "markdown": md_path,
            "html": html_path,
            "json": json_path,
            "md": md_path,
        }
