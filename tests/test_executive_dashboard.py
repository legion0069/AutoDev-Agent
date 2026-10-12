"""
test_executive_dashboard.py - Unit and Integration Tests for C-Suite BI Executive Dashboard (v3.0)
"""

import pytest
from core.enterprise.executive_dashboard import ExecutiveDashboard


@pytest.fixture
def dashboard():
    return ExecutiveDashboard()


class TestExecutiveDashboard:
    def test_generate_daily_briefing(self, dashboard: ExecutiveDashboard):
        briefing = dashboard.generate_daily_briefing(
            engineering_kpis={"active_sprints": 1, "deployments_today": 4, "open_bugs": 1, "dora_tier": "ELITE"},
            finance_kpis={"cash_reserve_usd": 5000000.0, "daily_burn_usd": 12000.0, "runway_months": 36.0},
            support_kpis={"open_tickets": 2, "avg_csat": 4.9, "sla_compliance_pct": 99.0},
            security_kpis={"open_cves": 0, "compliance_score": 100.0, "branch_protection_enforced": True},
        )
        assert briefing["report_type"] == "DAILY_EXECUTIVE_BRIEFING"
        assert briefing["engineering"]["deployments_today"] == 4
        assert briefing["finance"]["runway_months"] == 36.0
        assert len(briefing["risks"]) > 0

    def test_generate_weekly_report(self, dashboard: ExecutiveDashboard):
        weekly = dashboard.generate_weekly_report(
            engineering_kpis={"points_delivered": 42, "pr_reviews_completed": 35, "lead_time_hours": 2.1},
            finance_kpis={"weekly_spend_usd": 75000.0, "quarter_budget_used_pct": 22.0},
            support_kpis={"open_tickets": 3},
            product_kpis={"active_epics": 2, "features_completed": 6},
        )
        assert weekly["report_type"] == "WEEKLY_OPERATIONAL_REVIEW"
        assert weekly["engineering_velocity"]["points_delivered"] == 42
        assert weekly["product_progress"]["features_completed"] == 6

    def test_generate_quarterly_business_review(self, dashboard: ExecutiveDashboard):
        qbr = dashboard.generate_quarterly_business_review(
            strategic_goals_progress=[{"goal_id": "GOAL-01", "progress_pct": 100.0}],
            finance_summary={"total_spent_usd": 950000.0},
            product_summary={"total_features": 12},
            dora_summary={"dora_tier": "ELITE"},
        )
        assert qbr["report_type"] == "QUARTERLY_BUSINESS_REVIEW"
        assert len(qbr["strategic_goals"]) == 1
        assert qbr["dora_scorecard"]["dora_tier"] == "ELITE"

    def test_cached_report_retrieval(self, dashboard: ExecutiveDashboard):
        dashboard.generate_daily_briefing({}, {}, {}, {})
        cached = dashboard.get_latest_report("daily")
        assert cached is not None
        assert cached["report_type"] == "DAILY_EXECUTIVE_BRIEFING"
