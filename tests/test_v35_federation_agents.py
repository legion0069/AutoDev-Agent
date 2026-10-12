"""
test_v35_federation_agents.py - Unit Tests for Specialized Federation AI Agents (AutoDev Version 3.5)
"""

import pytest

from agents.chief_financial_officer import ChiefFinancialOfficer, ChiefFinancialOfficerAgent
from agents.cross_company_coordinator import CrossCompanyCoordinator, CrossCompanyCoordinatorAgent
from agents.enterprise_auditor import EnterpriseAuditor, EnterpriseAuditorAgent
from agents.enterprise_risk_officer import EnterpriseRiskOfficer, EnterpriseRiskOfficerAgent
from agents.enterprise_security_officer import EnterpriseSecurityOfficer, EnterpriseSecurityOfficerAgent
from agents.federation_ceo import FederationCEO, FederationCEOAgent
from agents.federation_cto import FederationCTO, FederationCTOAgent
from agents.global_architect import GlobalArchitect, GlobalArchitectAgent
from agents.global_operations_director import GlobalOperationsDirector, GlobalOperationsDirectorAgent
from agents.portfolio_director import PortfolioDirector, PortfolioDirectorAgent


def test_federation_ceo_strategic_evaluation():
    ceo = FederationCEOAgent(name="Victoria Sterling")
    assert ceo.authority_level == 5

    # High ROI & strategic alignment -> approved
    res = ceo.evaluate_strategic_initiative(
        initiative_title="Autonomous Cloud Federation",
        proposing_company_id="COMP-A",
        estimated_capital_usd=500000.0,
        expected_roi=3.8,
        strategic_alignment_score=92.0,
    )
    assert res["is_approved"] is True
    assert res["allocated_capital_usd"] == 500000.0

    # Low ROI -> rejected
    res_bad = ceo.evaluate_strategic_initiative("Pet Project", "COMP-B", 200000.0, 1.2, 50.0)
    assert res_bad["is_approved"] is False


def test_federation_ceo_dispute_and_directive():
    ceo = FederationCEO()
    disp = ceo.resolve_inter_company_dispute("DISP-1", "COMP-A", "COMP-B", "API contract", "Adopt Schema v2")
    assert disp["binding"] is True

    directive = ceo.issue_executive_directive("Mandatory Zero-Trust", "All companies adopt TLS 1.3", ["ALL"])
    assert directive["priority"] == "CRITICAL"


def test_federation_cto_technology_validation():
    cto = FederationCTOAgent()
    assert cto.authority_level == 5

    # Standard clean stack -> approved
    res_clean = cto.validate_technology_proposal("Modular Core", "COMP-A", ["Python", "SQLite"], ["python-std-lib"])
    assert res_clean["is_approved"] is True
    assert res_clean["veto_exercised"] is False

    # External orchestration framework -> vetoed!
    res_banned = cto.validate_technology_proposal("LangGraph Wrapper", "COMP-B", ["Python"], ["langgraph"])
    assert res_banned["is_approved"] is False
    assert res_banned["veto_exercised"] is True


def test_federation_cto_architecture_mandate():
    cto = FederationCTO()
    mandate = cto.mandate_architecture_standard("Enterprise Zero-Copy Bus", "Protocol v3.5 Specification")
    assert mandate["binding"] is True


def test_portfolio_director_initiative_scoring():
    pd = PortfolioDirectorAgent()
    assert pd.authority_level == 4

    scored = pd.score_initiative("Core Rewrite", business_value=90.0, strategic_alignment=95.0, estimated_roi=4.0, risk_score=15.0)
    assert scored["composite_score"] >= 65.0
    assert scored["recommended_priority"] == "P1_HIGH"


def test_portfolio_director_portfolio_health():
    pd = PortfolioDirector()
    projects = [
        {"title": "P1", "delivery_confidence": 0.95},
        {"title": "P2", "delivery_confidence": 0.40},  # At risk
    ]
    health = pd.evaluate_portfolio_health(projects)
    assert health["projects_at_risk"] == 1
    assert health["status"] == "REQUIRES_ATTENTION"


def test_global_architect_adr_review():
    arch = GlobalArchitectAgent()
    assert arch.authority_level == 4

    adr_res = arch.review_cross_company_adr(
        adr_title="Event Federation",
        proposing_company="COMP-A",
        impacted_companies=["COMP-B", "COMP-C"],
        architecture_pattern="Event-Driven Federation",
        protocols=["JSON", "HMAC"],
    )
    assert adr_res["is_ratified"] is True
    assert adr_res["architecture_health_impact"] == 5.0


def test_global_architect_interface_contract():
    arch = GlobalArchitect()
    contract = arch.generate_interface_contract("PaymentGateway", "COMP-A", ["COMP-B"], ["/charge", "/refund"])
    assert contract["sla_availability_pct"] == 99.95


def test_cross_company_coordinator_delegation_and_blockers():
    coord = CrossCompanyCoordinatorAgent()
    assert coord.authority_level == 3

    delegation = coord.coordinate_task_delegation("Build UI Form", "COMP-A", "COMP-B", 12.0)
    assert delegation["status"] == "COORDINATED"

    blocker = coord.triage_inter_company_blocker("Waiting for DB Schema", "COMP-B", "COMP-A", impact_hours=25.0)
    assert blocker["urgency"] == "HIGH"


def test_enterprise_security_officer_readiness_audit():
    ciso = EnterpriseSecurityOfficerAgent()
    assert ciso.authority_level == 4

    # Posture with 0 CVEs and MFA -> cleared
    audit_clean = ciso.audit_security_readiness("COMP-A", critical_cves=0, high_severity_findings=1, secrets_detected=0, mfa_enabled=True)
    assert audit_clean["is_cleared"] is True
    assert audit_clean["security_veto_exercised"] is False
    assert audit_clean["security_score"] == 95.0

    # Posture with critical CVE -> vetoed!
    audit_vuln = ciso.audit_security_readiness("COMP-BAD", critical_cves=2, high_severity_findings=0, secrets_detected=1, mfa_enabled=False)
    assert audit_vuln["is_cleared"] is False
    assert audit_vuln["security_veto_exercised"] is True
    assert len(audit_vuln["blocking_reasons"]) == 3


def test_enterprise_security_officer_threat_advisory():
    ciso = EnterpriseSecurityOfficer()
    adv = ciso.issue_threat_advisory("CVE-2026-9999", ["AuthService"], "IMMEDIATE_HOTFIX")
    assert adv["severity"] == "CRITICAL"


def test_chief_financial_officer_capital_allocation():
    cfo = ChiefFinancialOfficerAgent()
    assert cfo.authority_level == 5

    # High projected return -> full approval
    res_high = cfo.allocate_capital("COMP-A", 100000.0, 200000.0, "High growth market")
    assert res_high["is_fully_approved"] is True
    assert res_high["allocated_budget_usd"] == 100000.0

    # Low return -> trimmed allocation
    res_low = cfo.allocate_capital("COMP-B", 100000.0, 80000.0, "Low return")
    assert res_low["is_fully_approved"] is False
    assert res_low["allocated_budget_usd"] == 60000.0


def test_chief_financial_officer_runway():
    cfo = ChiefFinancialOfficer()
    runway = cfo.assess_financial_runway(total_treasury_usd=2400000.0, monthly_burn_rate_usd=100000.0)
    assert runway["runway_months"] == 24.0
    assert runway["financial_health"] == "HEALTHY"


def test_enterprise_risk_officer():
    ero = EnterpriseRiskOfficerAgent()
    assert ero.authority_level == 4

    risk_eval = ero.assess_enterprise_risk(company_count=8, quarantined_count=0, projects_at_risk_count=1, critical_cves_total=0)
    assert risk_eval["risk_tier"] == "LOW"
    assert risk_eval["mitigation_required"] is False

    mitigation = ero.prescribe_mitigation("SupplyChain", "Single source vendor")
    assert "automated canary" in mitigation["mitigation_plan"]


def test_enterprise_auditor():
    auditor = EnterpriseAuditorAgent()
    assert auditor.authority_level == 4

    # Forensic audit
    audit_res = auditor.conduct_integrity_audit(audit_chain_valid=True, audit_event_count=50, unauthorized_mutations_count=0)
    assert audit_res["audit_opinion"] == "UNQUALIFIED_CLEAN"

    # SOC2 verification
    soc2 = auditor.verify_soc2_compliance(security_score=95.0, zero_trust_enforced=True, audit_trail_immutable=True)
    assert soc2["certified"] is True


def test_global_operations_director():
    ops = GlobalOperationsDirectorAgent()
    assert ops.authority_level == 4

    vitality = ops.assess_ecosystem_vitality(active_companies_pct=95.0, average_latency_ms=25.0, open_incidents_count=0)
    assert vitality["is_healthy"] is True
    assert vitality["status"] == "NOMINAL"

    dr_run = ops.initiate_disaster_recovery("INC-01", "COMP-A", "FAILOVER", "HOT_STANDBY_RESTORE")
    assert dr_run["recovery_status"] == "IN_PROGRESS_AUTOMATED"
