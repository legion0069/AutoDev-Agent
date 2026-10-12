"""
test_v35_policy_and_governance_matrix.py - Deep Policy & Governance Matrix Tests (AutoDev Version 3.5)
"""

import pytest

from core.enterprise_governance import EnterpriseGovernanceManager
from core.enterprise_policy_engine import (
    EnterprisePolicyEngine,
    PolicyAction,
    PolicyDomain,
    PolicyEvaluationResult,
    PolicyRule,
    PolicyScope,
)
from core.shared_services import LicenseManager


# =============================================================================
# 1. License Permissiveness Matrix (10 SPDX Licenses)
# =============================================================================

LICENSE_TEST_CASES = [
    ("MIT", True),
    ("Apache-2.0", True),
    ("BSD-3-Clause", True),
    ("BSD-2-Clause", True),
    ("ISC", True),
    ("Unlicense", True),
    ("CC0-1.0", True),
    ("GPL-2.0", False),
    ("GPL-3.0", False),
    ("AGPL-3.0", False),
]

@pytest.mark.parametrize("spdx_id, expected_allowed", LICENSE_TEST_CASES)
def test_spdx_license_matrix(spdx_id, expected_allowed):
    lm = LicenseManager()
    allowed, reason = lm.check_license("test-library", spdx_id)
    assert allowed is expected_allowed
    if not expected_allowed:
        assert "copyleft" in reason


# =============================================================================
# 2. Budget Ceiling Escalation Matrix (6 Budget Tiers)
# =============================================================================

BUDGET_OVERRUN_CASES = [
    (100000.0, 50000.0, True),    # 50% spent -> compliant
    (100000.0, 100000.0, True),   # 100% spent -> compliant
    (100000.0, 115000.0, True),   # 115% spent -> compliant (< 120%)
    (100000.0, 125000.0, False),  # 125% spent -> violates 120% rule
    (500000.0, 650000.0, False),  # 130% spent -> violates 120% rule
    (1000000.0, 950000.0, True),  # 95% spent -> compliant
]

@pytest.mark.parametrize("budget_alloc, budget_spent, expected_compliant", BUDGET_OVERRUN_CASES)
def test_budget_overrun_matrix(budget_alloc, budget_spent, expected_compliant):
    gov = EnterpriseGovernanceManager()
    res = gov.policy_engine.evaluate(
        domain=PolicyDomain.BUDGET,
        context={"budget_allocated": budget_alloc, "budget_spent": budget_spent},
    )
    assert res.is_compliant is expected_compliant


# =============================================================================
# 3. QA Release Quality Gate Threshold Matrix (6 Pass Rates)
# =============================================================================

QA_PASS_RATES = [
    (100.0, True),
    (98.5, True),
    (95.0, True),
    (94.9, False),
    (90.0, False),
    (75.0, False),
]

@pytest.mark.parametrize("pass_rate, expected_release_ok", QA_PASS_RATES)
def test_qa_quality_gate_matrix(pass_rate, expected_release_ok):
    gov = EnterpriseGovernanceManager()
    res = gov.policy_engine.evaluate(
        domain=PolicyDomain.RELEASE,
        context={"qa_pass_rate_pct": pass_rate},
    )
    assert res.is_compliant is expected_release_ok


# =============================================================================
# 4. Critical CVE Blockers Matrix (5 CVE counts)
# =============================================================================

CVE_CASES = [
    (0, True),
    (1, False),
    (3, False),
    (5, False),
    (10, False),
]

@pytest.mark.parametrize("cve_count, expected_clean", CVE_CASES)
def test_cve_blocker_matrix(cve_count, expected_clean):
    gov = EnterpriseGovernanceManager()
    res = gov.policy_engine.evaluate(
        domain=PolicyDomain.SECURITY,
        context={"critical_cves_count": cve_count},
    )
    assert res.is_compliant is expected_clean


# =============================================================================
# 5. External Orchestration Framework Ban Matrix (8 Frameworks)
# =============================================================================

FRAMEWORK_CASES = [
    (["python-std-lib", "dataclasses", "unittest"], True),
    (["langgraph"], False),
    (["crewai"], False),
    (["autogen"], False),
    (["haystack"], False),
    (["fastapi", "crewai"], False),
    (["sqlite3", "json", "urllib"], True),
]

@pytest.mark.parametrize("dependencies, expected_allowed", FRAMEWORK_CASES)
def test_external_orchestrator_ban_matrix(dependencies, expected_allowed):
    gov = EnterpriseGovernanceManager()
    res = gov.policy_engine.evaluate(
        domain=PolicyDomain.ARCHITECTURE,
        context={"dependencies": dependencies},
    )
    assert res.is_compliant is expected_allowed
