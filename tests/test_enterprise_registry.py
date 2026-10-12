"""
test_enterprise_registry.py - Unit Tests for EnterpriseRegistry (AutoDev Version 3.5)
"""

import time
import pytest

from core.enterprise_registry import (
    CapabilityOffering,
    CompanyProfile,
    EnterpriseRegistry,
    OrganizationStatus,
)


def test_registry_initialization():
    reg = EnterpriseRegistry(enterprise_name="Acme Enterprise")
    summary = reg.get_registry_summary()
    assert summary["enterprise_name"] == "Acme Enterprise"
    assert summary["total_companies"] == 0
    assert summary["active_companies"] == 0


def test_register_company():
    reg = EnterpriseRegistry()
    prof = reg.register_company(
        company_id="COMP-01",
        company_name="Apex Backend Corp",
        domain="Backend Systems",
        business_unit="Core Tech",
        headcount=120,
        budget_usd=1500000.0,
    )
    assert prof.company_id == "COMP-01"
    assert prof.status == OrganizationStatus.ACTIVE
    assert reg.get_company("COMP-01") is prof


def test_add_and_find_capabilities():
    reg = EnterpriseRegistry()
    reg.register_company("COMP-01", "Backend Corp", "Backend")
    reg.register_company("COMP-02", "AI Corp", "AI")

    reg.add_capability("COMP-01", "HighThroughputAPI", "ENGINEERING", "Fast APIs", 100.0)
    reg.add_capability("COMP-02", "ModelTraining", "AI", "LLM Fine-tuning", 50.0)

    api_providers = reg.find_companies_by_capability("HighThroughputAPI")
    assert len(api_providers) == 1
    assert api_providers[0].company_id == "COMP-01"

    ai_providers = reg.find_companies_by_capability("ModelTraining")
    assert len(ai_providers) == 1
    assert ai_providers[0].company_id == "COMP-02"


def test_find_companies_by_domain():
    reg = EnterpriseRegistry()
    reg.register_company("C1", "Secure Systems", "Enterprise Cybersecurity")
    reg.register_company("C2", "Fast Frontend", "Consumer Frontend")

    sec_comps = reg.find_companies_by_domain("cybersecurity")
    assert len(sec_comps) == 1
    assert sec_comps[0].company_id == "C1"


def test_find_companies_by_business_unit():
    reg = EnterpriseRegistry()
    reg.register_company("C1", "Alpha", "DomainA", business_unit="CloudDivision")
    reg.register_company("C2", "Beta", "DomainB", business_unit="CloudDivision")
    reg.register_company("C3", "Gamma", "DomainC", business_unit="ConsumerDivision")

    cloud_comps = reg.find_companies_by_business_unit("CloudDivision")
    assert len(cloud_comps) == 2
    assert {c.company_id for c in cloud_comps} == {"C1", "C2"}


def test_update_company_status_and_health():
    reg = EnterpriseRegistry()
    reg.register_company("C1", "Alpha", "Domain")

    assert reg.update_company_status("C1", OrganizationStatus.DEGRADED, health_score=75.0) is True
    prof = reg.get_company("C1")
    assert prof.status == OrganizationStatus.DEGRADED
    assert prof.health_score == 75.0

    # Non-existent company
    assert reg.update_company_status("NON-EXISTENT", OrganizationStatus.OFFLINE) is False


def test_heartbeat_recording():
    reg = EnterpriseRegistry()
    reg.register_company("C1", "Alpha", "Domain")
    t0 = reg.get_company("C1").last_heartbeat
    time.sleep(0.01)

    assert reg.record_heartbeat("C1") is True
    assert reg.get_company("C1").last_heartbeat > t0
    assert reg.record_heartbeat("INVALID") is False


def test_list_companies_filtered():
    reg = EnterpriseRegistry()
    reg.register_company("C1", "Alpha", "Domain")
    reg.register_company("C2", "Beta", "Domain")
    reg.update_company_status("C2", OrganizationStatus.MAINTENANCE)

    all_comps = reg.list_companies()
    assert len(all_comps) == 2

    maint_comps = reg.list_companies(status=OrganizationStatus.MAINTENANCE)
    assert len(maint_comps) == 1
    assert maint_comps[0].company_id == "C2"


def test_registry_summary_aggregations():
    reg = EnterpriseRegistry()
    reg.register_company("C1", "Alpha", "Domain", budget_usd=1000000.0, headcount=50)
    reg.register_company("C2", "Beta", "Domain", budget_usd=2000000.0, headcount=150)
    reg.get_company("C1").spent_budget_usd = 200000.0
    reg.get_company("C2").spent_budget_usd = 800000.0

    summary = reg.get_registry_summary()
    assert summary["total_companies"] == 2
    assert summary["active_companies"] == 2
    assert summary["total_headcount"] == 200
    assert summary["total_budget_usd"] == 3000000.0
    assert summary["total_spent_usd"] == 1000000.0
