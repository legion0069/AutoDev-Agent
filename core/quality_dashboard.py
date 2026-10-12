"""
AutoDev Quality Dashboard Provider (v2.7)
Prepares serialized JSON and UI view models for the Quality Intelligence dashboard panel.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from core.quality_models import QualityAssessmentResult, QualityGateStatus, QualitySeverity


class QualityDashboardProvider:
    """Formats QualityAssessmentResult for frontend dashboard consumption."""

    def __init__(
        self,
        assessment: Optional[QualityAssessmentResult] = None,
        latest_assessment: Optional[QualityAssessmentResult] = None,
    ):
        self.assessment = assessment or latest_assessment or QualityAssessmentResult()

    def get_dashboard_payload(self) -> Dict[str, Any]:
        """Returns structured payload consumed by dashboard JavaScript."""
        gate_status = (
            self.assessment.gate_result.status.value
            if hasattr(self.assessment.gate_result.status, "value")
            else str(self.assessment.gate_result.status)
        )
        return {
            "assessment_id": self.assessment.assessment_id,
            "project_id": self.assessment.project_id,
            "timestamp": self.assessment.timestamp,
            "kpis": {
                "maintainability_index": self.assessment.overall_maintainability_index,
                "cyclomatic_complexity": float(self.assessment.complexity_summary.cyclomatic_complexity),
                "cognitive_complexity": float(self.assessment.complexity_summary.cognitive_complexity),
                "technical_debt_minutes": self.assessment.total_technical_debt_minutes,
                "technical_debt_hours": round(self.assessment.total_technical_debt_minutes / 60.0, 1),
                "regression_probability_pct": round(self.assessment.risk_scores.regression_probability * 100.0, 1),
                "duplication_pct": self.assessment.duplication_percentage,
                "duplication_percentage": self.assessment.duplication_percentage,
                "gate_status": gate_status,
                "gate_passed": self.assessment.gate_result.is_passed,
            },
            "quality_gate": {
                "status": gate_status,
                "is_passed": self.assessment.gate_result.is_passed,
                "reasons": self.assessment.gate_result.reasons or self.assessment.gate_result.rejection_reasons,
                "suggestions": self.assessment.gate_result.refactoring_suggestions,
            },
            "complexity": {
                "maintainability_index": self.assessment.overall_maintainability_index,
                "cyclomatic_complexity": self.assessment.complexity_summary.cyclomatic_complexity,
                "cognitive_complexity": self.assessment.complexity_summary.cognitive_complexity,
                "cyclomatic": self.assessment.complexity_summary.cyclomatic_complexity,
                "cognitive": self.assessment.complexity_summary.cognitive_complexity,
                "max_nesting": self.assessment.complexity_summary.max_nesting_depth,
                "longest_call_chain": self.assessment.complexity_summary.longest_call_chain,
                "sloc": self.assessment.total_sloc,
                "loc": self.assessment.total_loc,
            },
            "dependency_health": {
                "instability": self.assessment.dependency_health.instability,
                "package_instability": self.assessment.dependency_health.instability,
                "abstractness": self.assessment.dependency_health.abstractness,
                "distance": self.assessment.dependency_health.distance_main_sequence,
                "distance_from_main_sequence": self.assessment.dependency_health.distance_main_sequence,
                "circular_cycles": self.assessment.dependency_health.circular_dependency_cycles,
                "is_god_object": self.assessment.dependency_health.is_god_object,
            },
            "risks": self.assessment.risk_scores.to_dict() if hasattr(self.assessment.risk_scores, "to_dict") else self.assessment.risk_scores,
            "risk_scores": self.assessment.risk_scores.to_dict() if hasattr(self.assessment.risk_scores, "to_dict") else self.assessment.risk_scores,
            "issues": [i.to_dict() if hasattr(i, "to_dict") else i for i in self.assessment.issues],
            "issues_count_by_severity": {
                "CRITICAL": sum(1 for i in self.assessment.issues if getattr(i, "severity", None) == QualitySeverity.CRITICAL),
                "HIGH": sum(1 for i in self.assessment.issues if getattr(i, "severity", None) == QualitySeverity.HIGH),
                "MEDIUM": sum(1 for i in self.assessment.issues if getattr(i, "severity", None) == QualitySeverity.MEDIUM),
                "LOW": sum(1 for i in self.assessment.issues if getattr(i, "severity", None) == QualitySeverity.LOW),
            },
            "heatmap": self.assessment.heatmap_data,
            "refactoring_roadmap": self.assessment.gate_result.refactoring_suggestions,
            "gate_rejections": self.assessment.gate_result.rejection_reasons,
        }
