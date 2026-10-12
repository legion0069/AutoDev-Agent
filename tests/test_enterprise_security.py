"""
test_enterprise_security.py - Unit Tests for EnterpriseSecurityManager (AutoDev Version 3.5)
"""

import time
import pytest

from core.enterprise_security import (
    EnterpriseCertificate,
    EnterpriseSecurityManager,
    FederatedIdentity,
    SecurityAuditEntry,
)


def test_security_manager_initialization():
    sec = EnterpriseSecurityManager(master_secret="TEST_ROOT_SECRET")
    dash = sec.get_security_dashboard()
    assert dash["active_identities_count"] == 0
    assert dash["stored_secrets_count"] == 0
    assert dash["audit_chain_valid"] is True


def test_federated_identity_and_token():
    sec = EnterpriseSecurityManager()
    ident = sec.create_identity(
        company_id="COMP-A",
        department_id="SECURITY",
        role_name="SecEngineer",
        clearance_level="CONFIDENTIAL",
        permissions=["read:audit", "write:firewall"],
    )
    assert ident.identity_id.startswith("ID-")
    assert ident.token is not None
    assert ident.has_permission("read:audit") is True
    assert ident.has_permission("admin:root") is False

    validated = sec.validate_token(ident.token)
    assert validated is not None
    assert validated.identity_id == ident.identity_id


def test_token_revocation():
    sec = EnterpriseSecurityManager()
    ident = sec.create_identity("COMP-A", "ENG", "Dev")
    assert sec.validate_token(ident.token) is not None

    assert sec.revoke_token(ident.token, reason="Compromised session") is True
    assert sec.validate_token(ident.token) is None


def test_zero_trust_authorization_success():
    sec = EnterpriseSecurityManager()
    ident = sec.create_identity(
        company_id="COMP-A",
        department_id="ENG",
        role_name="Architect",
        clearance_level="CONFIDENTIAL",
        permissions=["deploy:staging"],
    )
    ok, reason = sec.authorize_action(
        token=ident.token,
        target_company_id="COMP-B",
        required_permission="deploy:staging",
        resource_clearance="INTERNAL",
    )
    assert ok is True
    assert reason == "Authorized"


def test_zero_trust_authorization_insufficient_clearance():
    sec = EnterpriseSecurityManager()
    ident = sec.create_identity(
        company_id="COMP-A",
        department_id="ENG",
        role_name="Intern",
        clearance_level="INTERNAL",
        permissions=["read:all"],
    )
    ok, reason = sec.authorize_action(
        token=ident.token,
        target_company_id="COMP-B",
        required_permission="read:all",
        resource_clearance="RESTRICTED",  # Higher than INTERNAL
    )
    assert ok is False
    assert "Clearance insufficient" in reason


def test_zero_trust_authorization_missing_permission():
    sec = EnterpriseSecurityManager()
    ident = sec.create_identity(
        company_id="COMP-A",
        department_id="ENG",
        role_name="Dev",
        clearance_level="CONFIDENTIAL",
        permissions=["read:logs"],
    )
    ok, reason = sec.authorize_action(
        token=ident.token,
        target_company_id="COMP-B",
        required_permission="delete:database",
        resource_clearance="CONFIDENTIAL",
    )
    assert ok is False
    assert "Missing 'delete:database'" in reason


def test_certificate_issuance_and_verification():
    sec = EnterpriseSecurityManager()
    cert = sec.issue_certificate("COMP-A", validity_days=30)
    assert cert.cert_id.startswith("CERT-")
    assert cert.subject_company == "COMP-A"
    assert sec.verify_certificate(cert.cert_id) is True

    # Revoke certificate
    assert sec.revoke_certificate(cert.cert_id, reason="Certificate renewal") is True
    assert sec.verify_certificate(cert.cert_id) is False


def test_secrets_vault_encryption_and_retrieval():
    sec = EnterpriseSecurityManager()
    ident = sec.create_identity("COMP-A", "ENG", "Dev", clearance_level="CONFIDENTIAL", permissions=["secrets:read"])

    assert sec.store_secret("DB_PROD_PASSWORD", "SuperSecurePass_2026!", "COMP-A", "CONFIDENTIAL") is True

    # Authorized retrieval
    retrieved = sec.retrieve_secret("DB_PROD_PASSWORD", ident.token)
    assert retrieved == "SuperSecurePass_2026!"

    # Unauthorized retrieval (low clearance)
    ident_low = sec.create_identity("COMP-B", "ENG", "Junior", clearance_level="PUBLIC", permissions=["secrets:read"])
    assert sec.retrieve_secret("DB_PROD_PASSWORD", ident_low.token) is None


def test_threat_propagation_and_quarantine():
    sec = EnterpriseSecurityManager()
    ident_a = sec.create_identity("COMP-MALICIOUS", "CORE", "AgentA")
    ident_b = sec.create_identity("COMP-SAFE", "CORE", "AgentB")

    # Propagate threat
    event = sec.propagate_threat(
        compromised_company_id="COMP-MALICIOUS",
        threat_type="EXFILTRATION_ACTIVITY",
        indicators_of_compromise=["192.168.1.100", "payload.bin"],
    )
    assert event["action_taken"] == "QUARANTINE_COMPANY"
    assert event["revoked_tokens_count"] == 1

    # Malicious company identity should now be rejected
    assert sec.validate_token(ident_a.token) is None

    # Safe company identity should still be valid
    assert sec.validate_token(ident_b.token) is not None

    # Lift quarantine
    assert sec.lift_quarantine("COMP-MALICIOUS") is True


def test_cryptographic_audit_chain_tamper_evidence():
    sec = EnterpriseSecurityManager()
    for i in range(5):
        sec.create_identity("COMP-A", "DEPT", f"Role{i}")

    assert sec.verify_audit_chain_integrity() is True

    # Simulate adversarial tampering with block 2
    sec._audit_chain[2].actor = "ADVERSARY_HACKER"
    # Tampered block must fail cryptographic verification
    assert sec.verify_audit_chain_integrity() is False
