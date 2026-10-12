"""
test_company_simulator.py - Unit and Integration Tests for Discrete-Event Company Simulator (v3.0)
"""

import pytest
from core.enterprise.company_simulator import CompanySimulator


@pytest.fixture
def simulator():
    return CompanySimulator()


class TestCompanySimulator:
    def test_simulate_workday(self, simulator: CompanySimulator):
        result = simulator.simulate_workday(day_index=1)
        assert result["day_index"] == 1
        assert result["events_count"] >= 3
        assert "briefing" in result
        assert result["briefing"]["report_type"] == "DAILY_EXECUTIVE_BRIEFING"

    def test_simulate_sprint(self, simulator: CompanySimulator):
        result = simulator.simulate_sprint(sprint_number=1, duration_days=3)
        assert result["sprint_id"] == "SPRINT-001"
        assert result["velocity_achieved"] >= 0
        assert result["architecture_score"] >= 80.0
        assert result["daily_summaries_count"] == 3

    def test_simulate_release(self, simulator: CompanySimulator):
        result = simulator.simulate_release(target_version="3.0.0")
        assert result["version"] == "3.0.0"
        assert result["stage"] == "GENERAL_AVAILABILITY"
        assert result["status"] == "DEPLOYED"
        assert len(result["approvers"]) >= 2

    def test_simulate_quarter(self, simulator: CompanySimulator):
        result = simulator.simulate_quarter(quarter="Q1", year=2026)
        assert result["quarter"] == "Q1"
        assert result["year"] == 2026
        assert len(result["hired_employees"]) >= 1
        assert result["sprints_completed"] >= 1
        assert result["qbr"]["report_type"] == "QUARTERLY_BUSINESS_REVIEW"

    def test_simulate_year(self, simulator: CompanySimulator):
        result = simulator.simulate_year(year=2026)
        assert result["simulation_year"] == 2026
        assert "Q1" in result["quarters"]
        assert "Q2" in result["quarters"]
        assert "Q3" in result["quarters"]
        assert "Q4" in result["quarters"]
        assert result["final_cash_reserve_usd"] > 0
        assert result["final_headcount"] >= 4
