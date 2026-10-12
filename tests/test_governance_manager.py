"""
test_governance_manager.py - Unit and Integration Tests for Corporate Governance & Compliance (v3.0)
"""

import pytest
from core.enterprise.enterprise_models import ComplianceStandard, DepartmentType, ExecutiveRole
from core.enterprise.governance_manager import GovernanceManager


@pytest.fixture
def gov():
    return GovernanceManager()


class TestGovernanceManager:
    def test_default_policies_initialized(self, gov: GovernanceManager):
        report = gov.generate_compliance_report()
        assert report["active_policies_count"] >= 3
        assert report["audit_integrity_valid"] is True

    def test_cryptographic_audit_trail_integrity(self, gov: GovernanceManager):
        # Log multiple events
        gov.log_audit_event(
            action="EXEC_APPROVE",
            actor="Elena Rostova",
            target_entity="Decision-01",
            department=DepartmentType.EXECUTIVE,
            details={"approved": True},
        )
        gov.log_audit_event(
            action="RELEASE_DEPLOY",
            actor="David Kim",
            target_entity="Release-3.0.0",
            department=DepartmentType.ENGINEERING,
            details={"version": "3.0.0"},
        )

        valid, error = gov.verify_audit_trail_integrity()
        assert valid is True
        assert error is None

    def test_tampered_audit_log_detected(self, gov: GovernanceManager):
        gov.log_audit_event("ACT1", "A1", "T1", DepartmentType.ENGINEERING, {"k": "v"})
        gov.log_audit_event("ACT2", "A2", "T2", DepartmentType.FINANCE, {"k": "v"})

        # Tamper with internal record
        gov._audit_trail[0].details = {"k": "TAMPERED_VALUE"}

        valid, error = gov.verify_audit_trail_integrity()
        assert valid is False
        assert "invalid hash signature" in error

    def test_codeowners_validation(self, gov: GovernanceManager):
        # core/security/* requires DIRECTOR_SECURITY
        valid, required = gov.validate_codeowners(
            file_path="core/security/auth.py",
            approving_roles=[ExecutiveRole.DIRECTOR_SECURITY],
        )
        assert valid is True
        assert ExecutiveRole.DIRECTOR_SECURITY in required

        # Missing approval
        invalid, required = gov.validate_codeowners(
            file_path="core/security/auth.py",
            approving_roles=[ExecutiveRole.DIRECTOR_QA],
        )
        assert invalid is False

    def test_branch_protection_rules(self, gov: GovernanceManager):
        # Force push rejected
        ok, msg = gov.validate_branch_push(branch="main", is_force_push=True, approvals_count=2)
        assert not ok
        assert "Force push rejected" in msg

        # Insufficient approvals rejected
        ok, msg = gov.validate_branch_push(branch="main", is_force_push=False, approvals_count=1)
        assert not ok
        assert "requires minimum 2 approvals" in msg

        # Passing
        ok, msg = gov.validate_branch_push(branch="main", is_force_push=False, approvals_count=2)
        assert ok
