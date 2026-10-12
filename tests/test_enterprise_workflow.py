"""
test_enterprise_workflow.py - End-to-End Autonomous Enterprise Lifecycle Integration Tests (v3.0)
"""

import pytest
from core.enterprise import (
    EnterpriseCompany,
    ExecutiveRole,
    TeamType,
)
from core.orchestrator import Orchestrator


@pytest.fixture
def company():
    return EnterpriseCompany()


class TestEnterpriseWorkflow:
    def test_complete_autonomous_lifecycle_execution(self, company: EnterpriseCompany):
        result = company.run_enterprise_lifecycle(
            strategic_goal="Deliver Complete Autonomous AI Software Company v3.0",
            target_version="3.0.0",
            budget_usd=500000.0,
        )

        assert result["status"] == "SUCCESS"
        assert result["deployed_version"] == "3.0.0"
        assert len(result["lifecycle_log"]) >= 9
        assert result["architecture_score"] >= 80.0
        assert result["dora_tier"] == "ELITE"
        assert result["csat_average"] >= 4.5
        assert result["cash_reserve_usd"] > 0

    def test_company_overview_telemetry(self, company: EnterpriseCompany):
        overview = company.get_company_overview()
        assert overview["company_name"] == "AutoDev Autonomous Technologies Inc."
        assert overview["executives_count"] == 15
        assert overview["employees_count"] >= 4
        assert overview["compliance_valid"] is True
        assert overview["dora_metrics"]["dora_tier"] == "ELITE"

    def test_orchestrator_enterprise_integration(self):
        orchestrator = Orchestrator()
        assert hasattr(orchestrator, "enterprise_company")
        assert hasattr(orchestrator, "execute_enterprise")
        assert hasattr(orchestrator, "simulate_company")
        assert hasattr(orchestrator, "query_company")

        # Query enterprise state
        state = orchestrator.query_company()
        assert state["executives_count"] == 15

        # Execute enterprise lifecycle via Orchestrator
        res = orchestrator.execute_enterprise(
            strategic_goal="Autonomous Cluster Scaling",
            target_version="3.1.0",
            budget_usd=100000.0,
        )
        assert res["status"] == "SUCCESS"
        assert res["deployed_version"] == "3.1.0"

        # Simulate workday via Orchestrator
        day_sim = orchestrator.simulate_company(timeframe="workday", day_index=5)
        assert day_sim["day_index"] == 5

        # Simulate sprint via Orchestrator
        sprint_sim = orchestrator.simulate_company(timeframe="sprint", sprint_number=2, duration_days=2)
        assert sprint_sim["sprint_number"] == 2
