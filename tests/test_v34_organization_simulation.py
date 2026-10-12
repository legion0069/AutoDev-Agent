"""
test_v34_organization_simulation.py - AutoDev Version 3.4
End-to-End simulation tests for the entire Autonomous AI Software Company:
- Full 16-step company workflow: Customer -> BA -> PM -> CEO -> CTO -> EM -> Arch -> Backend -> Frontend -> QA -> Security -> DevOps -> Release -> Docs -> Feedback -> Ops
- Multi-meeting execution and minute broadcasting
- Multi-department dispute arbitration via Decision Engine
- Conflict resolution during corporate execution
- Orchestrator v3.4 integration methods
"""

from pathlib import Path
import pytest
from core.decision_engine import DecisionDomain
from core.organization import EnterpriseOrganization, Organization
from core.orchestrator import Orchestrator


@pytest.fixture
def org(tmp_path: Path):
    return EnterpriseOrganization(
        company_name="AutoDev Global Technologies Corp.",
        storage_dir=tmp_path / "company_sim",
        auto_persist=True,
    )


def test_enterprise_organization_initialization(org: EnterpriseOrganization):
    assert org.company_name == "AutoDev Global Technologies Corp."
    assert len(org.departments) >= 16
    assert "CEO" in org.departments
    assert "CTO" in org.departments
    assert "EngineeringManager" in org.departments
    assert "Architecture" in org.departments
    assert "Backend" in org.departments
    assert "Frontend" in org.departments
    assert "QA" in org.departments
    assert "Security" in org.departments
    assert "DevOps" in org.departments
    assert "ReleaseManager" in org.departments
    assert "Documentation" in org.departments
    assert "CustomerFeedback" in org.departments
    assert "BusinessAnalyst" in org.departments
    assert "ProductManager" in org.departments
    assert "Finance" in org.departments
    assert "Compliance" in org.departments
    assert "Operations" in org.departments


def test_full_company_simulation_workflow(org: EnterpriseOrganization):
    result = org.simulate_company_workflow(
        customer_request="Build an enterprise microservices user authentication service with JWT and rate limiting.",
        target_version="3.4.0",
    )

    assert result["simulation_status"] == "SUCCESS"
    assert result["target_version"] == "3.4.0"
    assert result["execution_duration_s"] > 0.0

    stages = result["stages"]
    assert "1_customer_ingestion" in stages
    assert "2_business_analysis" in stages
    assert "3_product_management" in stages
    assert "4_ceo_approval" in stages
    assert "5_cto_validation" in stages
    assert "6_engineering_allocation" in stages
    assert "7_architecture_design" in stages
    assert "8_backend_development" in stages
    assert "9_frontend_development" in stages
    assert "10_qa_verification" in stages
    assert "11_security_audit" in stages
    assert "12_devops_readiness" in stages
    assert "13_release_execution" in stages
    assert "14_documentation" in stages
    assert "15_customer_feedback" in stages
    assert "16_operations" in stages

    # Check key stage outputs
    assert stages["4_ceo_approval"]["approved"] is True
    assert stages["5_cto_validation"]["approved"] is True
    assert stages["10_qa_verification"]["quality_gate_status"] == "PASSED"
    assert stages["11_security_audit"]["security_gate_status"] == "APPROVED"
    assert stages["13_release_execution"]["release_status"] == "DEPLOYED_TO_PRODUCTION"

    # Check metrics dashboard
    dashboard = result["metrics_dashboard"]
    assert dashboard["velocity"] > 0.0
    assert dashboard["security_score"] >= 90.0
    assert dashboard["delivery_confidence"] >= 0.85


def test_conduct_all_corporate_meetings(org: EnterpriseOrganization):
    meetings = org.conduct_all_standard_meetings()
    assert len(meetings) == 8
    meeting_types = {m["meeting_type"] for m in meetings}
    assert "DAILY_STANDUP" in meeting_types
    assert "SPRINT_PLANNING" in meeting_types
    assert "ARCHITECTURE_REVIEW" in meeting_types
    assert "SECURITY_REVIEW" in meeting_types
    assert "RELEASE_MEETING" in meeting_types


def test_resolve_departmental_dispute(org: EnterpriseOrganization):
    dispute = org.resolve_departmental_dispute(
        title="Database Choice",
        domain=DecisionDomain.ARCHITECTURE_CHOICE,
        options=["PostgreSQL", "MongoDB"],
        voter_preferences={
            "CTO": "PostgreSQL",
            "Architecture": "PostgreSQL",
            "Backend": "PostgreSQL",
            "Frontend": "MongoDB",
        },
        evidence_dict={
            "CTO": ["Strict ACID transactions required"],
            "Architecture": ["Proven relational consistency"],
        },
    )
    assert dispute["winning_option"] == "PostgreSQL"
    assert dispute["status"] == "RESOLVED"
    assert dispute["confidence_score"] > 0.60


def test_organization_summary_and_dashboard(org: EnterpriseOrganization):
    summary = org.get_organization_summary()
    assert summary["company_name"] == org.company_name
    assert summary["total_headcount"] > 30
    assert summary["total_budget"] > 400000.0

    dash = org.get_organization_dashboard()
    assert "velocity" in dash
    assert "delivery_confidence" in dash
    assert "team_utilization_pct" in dash


def test_orchestrator_v34_integration(tmp_path: Path):
    orch = Orchestrator(
        project_root=tmp_path / "orch_ws",
        plan_path=tmp_path / "plan.json",
        state_path=tmp_path / "state.json",
        tasks_path=tmp_path / "tasks.json",
        log_dir=tmp_path / "logs",
    )

    # 1. Check property
    assert orch.enterprise_organization is not None
    assert isinstance(orch.enterprise_organization, EnterpriseOrganization)

    # 2. Run simulation
    sim_res = orch.simulate_organization(
        customer_request="Build high-performance real-time telemetry analytics platform.",
        target_version="3.4.0",
    )
    assert sim_res["simulation_status"] == "SUCCESS"
    assert len(sim_res["stages"]) == 16

    # 3. Query organization
    org_info = orch.query_organization()
    assert "departments" in org_info

    # 4. Conduct meetings
    meetings = orch.conduct_organization_meetings()
    assert len(meetings) == 8

    # 5. Resolve dispute
    dispute_res = orch.resolve_organization_dispute(
        title="Cache Layer Selection",
        domain="ARCHITECTURE_CHOICE",
        options=["In-Memory Local Dict", "Shared File MMap"],
        voter_preferences={"Architecture": "In-Memory Local Dict", "Backend": "In-Memory Local Dict"},
    )
    assert dispute_res["winning_option"] == "In-Memory Local Dict"


def test_organization_alias_compatibility():
    org = Organization(company_name="Alias Test")
    assert isinstance(org, EnterpriseOrganization)
    assert len(org.departments) >= 16
