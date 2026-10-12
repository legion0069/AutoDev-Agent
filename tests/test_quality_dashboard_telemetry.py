"""
tests/test_quality_dashboard_telemetry.py - Unit tests for Quality Dashboard and Telemetry (v2.7)

Validates:
- QualityDashboardProvider payload generation and KPI metrics serialization
- DashboardServer /quality REST API endpoint response
- Quality telemetry event streaming and schema conformance
"""

import json
import time
import urllib.request
import pytest
from core.dashboard_server import DashboardServer
from core.quality_dashboard import QualityDashboardProvider
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
from core.telemetry_models import TelemetryEvent, TelemetrySeverity
from core.telemetry_stream import TelemetryStream


def test_quality_dashboard_provider_payload():
    """Generates structured dashboard UI payload."""
    assessment = QualityAssessmentResult(
        project_id="proj_1",
        aggregate_complexity=ComplexityMetrics(
            cyclomatic_complexity=3,
            cognitive_complexity=4,
            maintainability_index=88.5,
        ),
        dependency_health=DependencyHealthMetrics(package_instability=0.25),
        risk_scores=PredictiveRiskScores(regression_probability=0.05, security_confidence=0.98),
        gate_result=QualityGateResult(status=QualityGateStatus.PASSED, score=92.0),
    )

    provider = QualityDashboardProvider(latest_assessment=assessment)
    payload = provider.get_dashboard_payload()

    assert "kpis" in payload
    assert payload["kpis"]["maintainability_index"] == 88.5
    assert payload["kpis"]["cyclomatic_complexity"] == 3.0
    assert payload["quality_gate"]["status"] == "PASSED"
    assert payload["risks"]["regression_probability"] == 0.05


def test_dashboard_server_quality_endpoint():
    """DashboardServer serves /quality endpoint with valid JSON."""
    assessment = QualityAssessmentResult(
        project_id="web_app",
        aggregate_complexity=ComplexityMetrics(maintainability_index=91.0),
        gate_result=QualityGateResult(status=QualityGateStatus.PASSED),
    )
    provider = QualityDashboardProvider(latest_assessment=assessment)

    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        quality_provider=provider.get_dashboard_payload,
    )
    server.start()
    try:
        url = f"http://127.0.0.1:{server.port}/quality"
        req = urllib.request.urlopen(url, timeout=3)
        assert req.status == 200
        data = json.loads(req.read().decode("utf-8"))
        assert data["kpis"]["maintainability_index"] == 91.0
        assert data["quality_gate"]["status"] == "PASSED"
    finally:
        server.stop()


def test_quality_telemetry_events():
    """Telemetry stream properly records and broadcasts quality events."""
    stream = TelemetryStream(max_events=100)
    
    evt = TelemetryEvent(
        event_type="QUALITY_ASSESSMENT_COMPLETED",
        source_component="PredictiveQualityEngine",
        severity=TelemetrySeverity.INFO,
        payload={"maintainability_index": 85.0, "status": "PASSED"},
    )
    stream.publish(evt)

    assert stream.event_count >= 1
    events = stream.get_recent_events(limit=5)
    assert events[0].event_type == "QUALITY_ASSESSMENT_COMPLETED"
    assert events[0].payload["maintainability_index"] == 85.0
