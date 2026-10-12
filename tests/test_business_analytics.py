"""
test_business_analytics.py - Unit and Integration Tests for DORA Metrics & Business Analytics (v3.0)
"""

import pytest
from core.enterprise.business_analytics import BusinessAnalytics, DoraMetrics, ProductUsageMetrics


@pytest.fixture
def analytics():
    return BusinessAnalytics()


class TestBusinessAnalytics:
    def test_default_dora_tier_elite(self, analytics: BusinessAnalytics):
        dora = analytics.get_dora_metrics()
        assert dora.dora_tier == "ELITE"
        assert dora.deployment_frequency_per_day >= 1.0
        assert dora.lead_time_for_changes_hours <= 24.0
        assert dora.mean_time_to_recovery_minutes <= 60.0
        assert dora.change_failure_rate_pct <= 5.0

    def test_record_deployment_metrics_calculation(self, analytics: BusinessAnalytics):
        analytics.record_deployment(lead_time_hours=1.5, success=True)
        analytics.record_deployment(lead_time_hours=2.5, success=True)
        analytics.record_deployment(lead_time_hours=2.0, success=False)

        dora = analytics.get_dora_metrics()
        assert dora.lead_time_for_changes_hours == 2.0
        # 1 failure out of 3 = 33.33%
        assert dora.change_failure_rate_pct == 33.33

    def test_record_incident_recovery(self, analytics: BusinessAnalytics):
        analytics.record_incident_recovery(duration_minutes=10.0)
        analytics.record_incident_recovery(duration_minutes=20.0)
        dora = analytics.get_dora_metrics()
        assert dora.mean_time_to_recovery_minutes == 15.0

    def test_feature_usage_and_sprint_velocity(self, analytics: BusinessAnalytics):
        analytics.record_feature_usage("AutonomousCodeReview", count=50)
        analytics.record_feature_usage("AutonomousCodeReview", count=25)
        usage = analytics.get_usage_metrics()
        assert usage.feature_invocations["AutonomousCodeReview"] == 75

        analytics.record_sprint_velocity(sprint_id="S-01", points_completed=38, cycle_time_hours=16.4)
        summary = analytics.to_dict()
        assert len(summary["velocity_history"]) == 1
        assert summary["velocity_history"][0]["points_completed"] == 38

    def test_analytics_recommendations(self, analytics: BusinessAnalytics):
        # Force high failure rate
        analytics.record_deployment(lead_time_hours=5.0, success=False)
        recs = analytics.generate_recommendations()
        assert len(recs) > 0
        assert any(r["metric"] == "Change Failure Rate" for r in recs)
