"""
test_enterprise_governance.py - Unit Tests for EnterpriseGovernance & PolicyEngine (AutoDev Version 3.5)
"""

import pytest

from core.enterprise_governance import (
    EnterpriseGovernanceManager,
    GovernanceAuditReport,
)
from core.enterprise_policy_engine import (
    EnterprisePolicyEngine,
    PolicyAction,
    PolicyDomain,
    PolicyEvaluationResult,
    PolicyRule,
    PolicyScope,
)


def test_policy_engine_registration_and_evaluation():
    pe = EnterprisePolicyEngine()
    rule = pe.register_rule(
        name="No Root Access",
        domain=PolicyDomain.SECURITY,
        scope=PolicyScope.ENTERPRISE,
        condition=lambda ctx: ctx.get("is_root", False) is True,
        action=PolicyAction.DENY,
        severity="CRITICAL",
        description="Root access forbidden",
    )
    assert rule.rule_id.startswith("POL-")

    # Evaluation on compliant context
    res_compliant = pe.evaluate(PolicyDomain.SECURITY, {"is_root": False})
    assert res_compliant.is_compliant is True
    assert res_compliant.action == PolicyAction.ALLOW

    # Evaluation on non-compliant context
    res_violated = pe.evaluate(PolicyDomain.SECURITY, {"is_root": True})
    assert res_violated.is_compliant is False
    assert res_violated.action == PolicyAction.DENY
    assert len(res_violated.violations) == 1


def test_policy_scoping_inheritance():
    pe = EnterprisePolicyEngine()
    # Company specific rule for COMP-A
    pe.register_rule(
        name="COMP-A Strict Rate Limit",
        domain=PolicyDomain.ARCHITECTURE,
        scope=PolicyScope.COMPANY,
        target_id="COMP-A",
        condition=lambda ctx: ctx.get("rate_limit", 100) > 50,
        action=PolicyAction.DENY,
    )

    # Context with rate_limit=80 evaluated for COMP-A -> should violate
    res_a = pe.evaluate(PolicyDomain.ARCHITECTURE, {"rate_limit": 80}, company_id="COMP-A")
    assert res_a.is_compliant is False

    # Same context evaluated for COMP-B -> should pass because rule target is COMP-A
    res_b = pe.evaluate(PolicyDomain.ARCHITECTURE, {"rate_limit": 80}, company_id="COMP-B")
    assert res_b.is_compliant is True


def test_standard_governance_rules_clean_audit():
    gov = EnterpriseGovernanceManager()

    # Clean context complying with all standards
    clean_ctx = {
        "budget_spent": 50000,
        "budget_allocated": 100000,
        "dependencies": ["python-std-lib", "urllib"],
        "has_eval_or_exec": False,
        "critical_cves_count": 0,
        "unmasked_pii_detected": False,
        "api_endpoints_count": 5,
        "has_api_docs": True,
        "qa_pass_rate_pct": 99.5,
    }

    report = gov.audit_target("COMP-A", "COMPANY", clean_ctx)
    assert report.is_compliant is True
    assert report.overall_compliance_score == 100.0
    assert len(report.violations) == 0


def test_standard_governance_detects_violations():
    gov = EnterpriseGovernanceManager()

    # Context violating security (critical CVE) and architecture (langgraph dependency)
    violation_ctx = {
        "critical_cves_count": 2,
        "dependencies": ["langgraph"],
        "has_eval_or_exec": True,
        "qa_pass_rate_pct": 80.0,
    }

    report = gov.audit_target("COMP-BAD", "COMPANY", violation_ctx)
    assert report.is_compliant is False
    assert report.overall_compliance_score <= 80.0
    assert len(report.violations) >= 3

    # Ensure CVE and external framework violations appear
    viol_str = " ".join(report.violations)
    assert "Zero Critical CVE Gate" in viol_str
    assert "Zero External Orchestration Rule" in viol_str
    assert "Unsafe Dynamic Execution Ban" in viol_str


def test_verify_release_gate():
    gov = EnterpriseGovernanceManager()

    # Release context with 100% QA pass and 0 CVEs
    good_release = {
        "critical_cves_count": 0,
        "qa_pass_rate_pct": 98.0,
        "api_endpoints_count": 0,
        "has_api_docs": True,
    }
    can_release, viol = gov.verify_release_gate(good_release)
    assert can_release is True
    assert len(viol) == 0

    # Failing release: low QA pass rate
    bad_release = {
        "critical_cves_count": 0,
        "qa_pass_rate_pct": 88.0,
        "api_endpoints_count": 0,
    }
    can_rel_bad, viol_bad = gov.verify_release_gate(bad_release)
    assert can_rel_bad is False
    assert len(viol_bad) > 0
