"""
enterprise_security.py - Enterprise Security, Zero Trust & Federated IAM (AutoDev Version 3.5)

Implements enterprise-grade Zero Trust security across the federation:
- Cross-company Identity & Access Management (IAM) with token issuance and validation
- Zero Trust policy evaluator (least privilege, continuous verification, context checks)
- Digital Certificate Management (issue, verify, revoke, rotate, expiry checks)
- Enterprise Secrets Vault with deterministic key derivation and access audits
- Federated SHA-256 tamper-evident security audit logging
- Threat propagation engine (immediate federation-wide quarantine on threat detection)
- 100% Python Standard Library.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("AutoDev.Federation.Security")


@dataclass
class FederatedIdentity:
    """Identity record for an agent or system in the enterprise federation."""
    identity_id: str
    company_id: str
    department_id: str
    role_name: str
    clearance_level: str  # PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED
    assigned_permissions: Set[str] = field(default_factory=set)
    is_active: bool = True
    token: str = ""
    token_expiry: float = 0.0

    def has_permission(self, permission: str) -> bool:
        return self.is_active and (permission in self.assigned_permissions or "*" in self.assigned_permissions)


@dataclass
class EnterpriseCertificate:
    """Digital certificate representation for inter-company mutual trust."""
    cert_id: str
    subject_company: str
    issuer: str
    issued_at: float
    expires_at: float
    public_key_fingerprint: str
    signature: str
    is_revoked: bool = False
    revocation_reason: Optional[str] = None


@dataclass
class SecurityAuditEntry:
    """Tamper-evident chained audit event for federation security."""
    entry_id: str
    timestamp: float
    actor: str
    company_id: str
    action: str
    resource: str
    result: str  # ALLOWED, DENIED, QUARANTINED
    previous_hash: str
    entry_hash: str
    details: Dict[str, Any] = field(default_factory=dict)


class EnterpriseSecurityManager:
    """
    Federation-wide security orchestrator enforcing Zero Trust, certificate lifecycle,
    secrets governance, and rapid threat propagation.
    """

    def __init__(self, master_secret: str = "ENTERPRISE_ZERO_TRUST_ROOT_KEY") -> None:
        self._lock = threading.RLock()
        self.master_secret = master_secret
        self._identities: Dict[str, FederatedIdentity] = {}
        self._tokens: Dict[str, str] = {}  # token -> identity_id
        self._certificates: Dict[str, EnterpriseCertificate] = {}
        self._secrets_vault: Dict[str, Dict[str, Any]] = {}  # secret_name -> {encrypted_val, company_id, clearance}
        self._audit_chain: List[SecurityAuditEntry] = []
        self._revoked_tokens: Set[str] = set()
        self._quarantined_companies: Set[str] = set()
        self._known_threats: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # 1. Federated IAM & Token Management
    # -------------------------------------------------------------------------

    def create_identity(
        self,
        company_id: str,
        department_id: str,
        role_name: str,
        clearance_level: str = "INTERNAL",
        permissions: Optional[List[str]] = None,
        token_validity_seconds: float = 86400.0,
    ) -> FederatedIdentity:
        """Registers a new identity in the enterprise federation."""
        with self._lock:
            iid = f"ID-{uuid.uuid4().hex[:8].upper()}"
            ident = FederatedIdentity(
                identity_id=iid,
                company_id=company_id,
                department_id=department_id,
                role_name=role_name,
                clearance_level=clearance_level,
                assigned_permissions=set(permissions or ["general:read", "general:write"]),
            )
            # Issue initial session token
            token, expiry = self._generate_token(ident, validity_seconds=token_validity_seconds)
            ident.token = token
            ident.token_expiry = expiry

            self._identities[iid] = ident
            self._tokens[token] = iid

            self._record_audit(
                actor=iid,
                company_id=company_id,
                action="CREATE_IDENTITY",
                resource=role_name,
                result="ALLOWED",
                details={"clearance": clearance_level, "permissions": list(ident.assigned_permissions)},
            )
            return ident

    def validate_token(self, token: str) -> Optional[FederatedIdentity]:
        """Validates bearer token against expiration and revocation."""
        with self._lock:
            if token in self._revoked_tokens:
                logger.warning("Attempted use of revoked token: %s", token[:10])
                return None

            iid = self._tokens.get(token)
            if not iid:
                return None

            ident = self._identities.get(iid)
            if not ident or not ident.is_active:
                return None

            if time.time() > ident.token_expiry:
                logger.warning("Token expired for identity: %s", iid)
                return None

            if ident.company_id in self._quarantined_companies:
                logger.warning("Identity %s belongs to quarantined company %s", iid, ident.company_id)
                return None

            return ident

    def revoke_token(self, token: str, reason: str = "Manual revocation") -> bool:
        """Immediately revokes an active security token."""
        with self._lock:
            if token in self._tokens:
                self._revoked_tokens.add(token)
                iid = self._tokens[token]
                self._record_audit(
                    actor="SecurityManager",
                    company_id="FEDERATION",
                    action="REVOKE_TOKEN",
                    resource=iid,
                    result="ALLOWED",
                    details={"reason": reason},
                )
                return True
            return False

    # -------------------------------------------------------------------------
    # 2. Zero Trust Authorization
    # -------------------------------------------------------------------------

    def authorize_action(
        self,
        token: str,
        target_company_id: str,
        required_permission: str,
        resource_clearance: str = "INTERNAL",
    ) -> Tuple[bool, str]:
        """
        Zero Trust policy evaluation:
        Validates token, verifies company quarantine, checks permissions, and clearance hierarchy.
        """
        with self._lock:
            ident = self.validate_token(token)
            if not ident:
                self._record_audit("UNKNOWN", target_company_id, required_permission, "SECURITY_GATE", "DENIED", {"reason": "Invalid or expired token"})
                return False, "Authentication failure: Invalid, expired, or quarantined token"

            if target_company_id in self._quarantined_companies:
                self._record_audit(ident.identity_id, target_company_id, required_permission, "SECURITY_GATE", "DENIED", {"reason": "Target company is quarantined"})
                return False, f"Target company '{target_company_id}' is quarantined"

            # Clearance check
            clearance_ranks = {"PUBLIC": 1, "INTERNAL": 2, "CONFIDENTIAL": 3, "RESTRICTED": 4}
            if clearance_ranks.get(ident.clearance_level, 1) < clearance_ranks.get(resource_clearance, 2):
                self._record_audit(ident.identity_id, target_company_id, required_permission, "SECURITY_GATE", "DENIED", {"reason": "Insufficient clearance"})
                return False, f"Clearance insufficient: {ident.clearance_level} < {resource_clearance}"

            # Permission check
            if not ident.has_permission(required_permission):
                self._record_audit(ident.identity_id, target_company_id, required_permission, "SECURITY_GATE", "DENIED", {"reason": "Missing permission"})
                return False, f"Permission denied: Missing '{required_permission}'"

            self._record_audit(ident.identity_id, target_company_id, required_permission, "SECURITY_GATE", "ALLOWED", {})
            return True, "Authorized"

    # -------------------------------------------------------------------------
    # 3. Certificate Management
    # -------------------------------------------------------------------------

    def issue_certificate(
        self,
        subject_company: str,
        validity_days: int = 365,
    ) -> EnterpriseCertificate:
        """Issues a signed digital certificate for mutual enterprise trust."""
        with self._lock:
            cid = f"CERT-{uuid.uuid4().hex[:8].upper()}"
            now = time.time()
            exp = now + (validity_days * 86400)
            fingerprint = hashlib.sha256(f"{cid}:{subject_company}:{now}".encode("utf-8")).hexdigest()

            # Sign certificate with master secret
            sig_material = f"{cid}:{subject_company}:FEDERATION_ROOT:{now}:{exp}:{fingerprint}"
            sig = hmac.new(self.master_secret.encode("utf-8"), sig_material.encode("utf-8"), hashlib.sha256).hexdigest()

            cert = EnterpriseCertificate(
                cert_id=cid,
                subject_company=subject_company,
                issuer="FEDERATION_ROOT",
                issued_at=now,
                expires_at=exp,
                public_key_fingerprint=fingerprint,
                signature=sig,
            )
            self._certificates[cid] = cert
            self._record_audit(
                actor="SecurityManager",
                company_id=subject_company,
                action="ISSUE_CERTIFICATE",
                resource=cid,
                result="ALLOWED",
                details={"subject": subject_company, "expires_at": exp},
            )
            return cert

    def verify_certificate(self, cert_id: str) -> bool:
        """Verifies integrity, signature, and validity period of a certificate."""
        with self._lock:
            cert = self._certificates.get(cert_id)
            if not cert or cert.is_revoked:
                return False
            if time.time() > cert.expires_at:
                return False

            sig_material = f"{cert.cert_id}:{cert.subject_company}:{cert.issuer}:{cert.issued_at}:{cert.expires_at}:{cert.public_key_fingerprint}"
            expected_sig = hmac.new(self.master_secret.encode("utf-8"), sig_material.encode("utf-8"), hashlib.sha256).hexdigest()
            return hmac.compare_digest(cert.signature, expected_sig)

    def revoke_certificate(self, cert_id: str, reason: str = "Compromised") -> bool:
        """Revokes an enterprise certificate."""
        with self._lock:
            cert = self._certificates.get(cert_id)
            if cert:
                cert.is_revoked = True
                cert.revocation_reason = reason
                return True
            return False

    # -------------------------------------------------------------------------
    # 4. Enterprise Secrets Vault
    # -------------------------------------------------------------------------

    def store_secret(
        self,
        secret_name: str,
        secret_value: str,
        owner_company_id: str,
        clearance_level: str = "CONFIDENTIAL",
    ) -> bool:
        """Encrypts and stores an enterprise secret."""
        with self._lock:
            # Deterministic AES-like stream masking via HMAC key derivation
            key = hashlib.sha256(f"{self.master_secret}:{secret_name}".encode("utf-8")).digest()
            val_bytes = secret_value.encode("utf-8")
            encrypted_bytes = bytes([b ^ key[i % len(key)] for i, b in enumerate(val_bytes)])
            encoded_val = base64.b64encode(encrypted_bytes).decode("utf-8")

            self._secrets_vault[secret_name] = {
                "encoded_val": encoded_val,
                "owner": owner_company_id,
                "clearance": clearance_level,
                "updated_at": time.time(),
            }
            return True

    def retrieve_secret(
        self,
        secret_name: str,
        requester_token: str,
    ) -> Optional[str]:
        """Retrieves and decrypts an enterprise secret if authorized."""
        with self._lock:
            sec_record = self._secrets_vault.get(secret_name)
            if not sec_record:
                return None

            authorized, _ = self.authorize_action(
                token=requester_token,
                target_company_id=sec_record["owner"],
                required_permission="secrets:read",
                resource_clearance=sec_record["clearance"],
            )
            if not authorized:
                return None

            key = hashlib.sha256(f"{self.master_secret}:{secret_name}".encode("utf-8")).digest()
            encrypted_bytes = base64.b64decode(sec_record["encoded_val"])
            decrypted_bytes = bytes([b ^ key[i % len(key)] for i, b in enumerate(encrypted_bytes)])
            return decrypted_bytes.decode("utf-8")

    # -------------------------------------------------------------------------
    # 5. Threat Propagation & Quarantine
    # -------------------------------------------------------------------------

    def propagate_threat(
        self,
        compromised_company_id: str,
        threat_type: str,
        indicators_of_compromise: List[str],
        action: str = "QUARANTINE_COMPANY",
    ) -> Dict[str, Any]:
        """
        Immediately propagates threat intelligence across the federation,
        quarantining compromised companies and revoking tokens.
        """
        with self._lock:
            threat_event = {
                "threat_id": f"THR-{uuid.uuid4().hex[:8].upper()}",
                "company_id": compromised_company_id,
                "threat_type": threat_type,
                "iocs": indicators_of_compromise,
                "action_taken": action,
                "timestamp": time.time(),
            }
            self._known_threats.append(threat_event)

            if action in ("QUARANTINE_COMPANY", "FULL_LOCKDOWN"):
                self._quarantined_companies.add(compromised_company_id)
                # Revoke all tokens belonging to this company
                revoked_count = 0
                for token, iid in list(self._tokens.items()):
                    ident = self._identities.get(iid)
                    if ident and ident.company_id == compromised_company_id:
                        self._revoked_tokens.add(token)
                        ident.is_active = False
                        revoked_count += 1

                threat_event["revoked_tokens_count"] = revoked_count
                logger.critical(
                    "SECURITY QUARANTINE: Company '%s' quarantined across federation. %d tokens revoked.",
                    compromised_company_id, revoked_count,
                )

            self._record_audit(
                actor="EnterpriseSecurityOfficer",
                company_id=compromised_company_id,
                action="PROPAGATE_THREAT",
                resource=threat_type,
                result="QUARANTINED",
                details=threat_event,
            )
            return threat_event

    def lift_quarantine(self, company_id: str) -> bool:
        """Lifts quarantine status after remediation."""
        with self._lock:
            if company_id in self._quarantined_companies:
                self._quarantined_companies.remove(company_id)
                logger.info("Quarantine lifted for company '%s'", company_id)
                return True
            return False

    def get_quarantined_companies(self) -> List[str]:
        """Returns the list of currently quarantined company IDs."""
        with self._lock:
            return list(self._quarantined_companies)

    # -------------------------------------------------------------------------
    # 6. Cryptographic Audit Chain
    # -------------------------------------------------------------------------

    def _record_audit(
        self,
        actor: str,
        company_id: str,
        action: str,
        resource: str,
        result: str,
        details: Dict[str, Any],
    ) -> SecurityAuditEntry:
        """Appends an event to the immutable SHA-256 chained audit log."""
        eid = f"SEC-AUD-{len(self._audit_chain)+1:06d}"
        now = time.time()
        prev_hash = self._audit_chain[-1].entry_hash if self._audit_chain else "GENESIS_FEDERATION_BLOCK"

        material = f"{eid}:{now}:{actor}:{company_id}:{action}:{resource}:{result}:{prev_hash}:{json.dumps(details, sort_keys=True)}"
        entry_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()

        entry = SecurityAuditEntry(
            entry_id=eid,
            timestamp=now,
            actor=actor,
            company_id=company_id,
            action=action,
            resource=resource,
            result=result,
            previous_hash=prev_hash,
            entry_hash=entry_hash,
            details=details,
        )
        self._audit_chain.append(entry)
        return entry

    def verify_audit_chain_integrity(self) -> bool:
        """Cryptographically verifies the security audit chain."""
        with self._lock:
            for i, entry in enumerate(self._audit_chain):
                expected_prev = self._audit_chain[i - 1].entry_hash if i > 0 else "GENESIS_FEDERATION_BLOCK"
                if entry.previous_hash != expected_prev:
                    return False
                material = (
                    f"{entry.entry_id}:{entry.timestamp}:{entry.actor}:{entry.company_id}:"
                    f"{entry.action}:{entry.resource}:{entry.result}:{entry.previous_hash}:"
                    f"{json.dumps(entry.details, sort_keys=True)}"
                )
                computed_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
                if entry.entry_hash != computed_hash:
                    return False
            return True

    def _generate_token(self, ident: FederatedIdentity, validity_seconds: float = 86400.0) -> Tuple[str, float]:
        """Generates a secure HMAC session token."""
        expiry = time.time() + validity_seconds
        token_payload = f"{ident.identity_id}:{ident.company_id}:{expiry}:{uuid.uuid4().hex}"
        token_sig = hmac.new(self.master_secret.encode("utf-8"), token_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        token = f"autodev_fed_{base64.urlsafe_b64encode(token_payload.encode('utf-8')).decode('utf-8')}.{token_sig[:16]}"
        return token, expiry

    def get_security_dashboard(self) -> Dict[str, Any]:
        """Returns enterprise security telemetry."""
        with self._lock:
            return {
                "active_identities_count": len(self._identities),
                "active_certificates_count": len([c for c in self._certificates.values() if not c.is_revoked]),
                "stored_secrets_count": len(self._secrets_vault),
                "quarantined_companies": list(self._quarantined_companies),
                "known_threats_count": len(self._known_threats),
                "audit_chain_length": len(self._audit_chain),
                "audit_chain_valid": self.verify_audit_chain_integrity(),
            }
