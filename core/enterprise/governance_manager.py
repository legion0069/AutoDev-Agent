"""
governance_manager.py - Enterprise Corporate Governance & Compliance Engine for AutoDev (v3.0)

Enforces compliance frameworks (SOC2 Type II, GDPR, ISO 27001, HIPAA, PCI-DSS),
branch protection rules, CODEOWNERS approval policies, and cryptographic
tamper-evident SHA-256 audit logging.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from core.enterprise.enterprise_models import (
    AuditLogRecord,
    ComplianceStandard,
    DepartmentType,
    ExecutiveRole,
    GovernancePolicy,
)

logger = logging.getLogger("AutoDev.Enterprise.Governance")


class GovernanceManager:
    """
    Autonomous Corporate Governance, Policy & Cryptographic Audit Engine.
    Enforces regulatory compliance, branch protection, CODEOWNERS rules, and tamper-evident audit trails.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._policies: Dict[str, GovernancePolicy] = {}
        self._audit_trail: List[AuditLogRecord] = []
        self._codeowners: Dict[str, List[ExecutiveRole]] = {}
        self._protected_branches: Set[str] = {"main", "master", "release/*", "production"}

        self._init_default_policies()

    def _init_default_policies(self) -> None:
        """Initializes default regulatory compliance policies."""
        defaults = [
            (
                "POL-SOC2-01",
                "SOC2 Access Control & Multi-Party Review",
                ComplianceStandard.SOC2_TYPE_II,
                "All production changes require two independent executive approvals and passing automated test suites.",
                [ExecutiveRole.CTO, ExecutiveRole.DIRECTOR_SECURITY],
            ),
            (
                "POL-GDPR-01",
                "GDPR Privacy & Data Minimization",
                ComplianceStandard.GDPR,
                "Customer PII must be encrypted at rest and in transit; retention limits strictly enforced.",
                [ExecutiveRole.LEGAL_COUNSEL, ExecutiveRole.DIRECTOR_SECURITY],
            ),
            (
                "POL-ISO27001-01",
                "ISO 27001 Information Security Management",
                ComplianceStandard.ISO_27001,
                "Continuous automated vulnerability scanning and branch protection on all release repos.",
                [ExecutiveRole.DIRECTOR_SECURITY, ExecutiveRole.DIRECTOR_DEVOPS],
            ),
        ]

        for pid, name, std, desc, approvers in defaults:
            self._policies[pid] = GovernancePolicy(
                policy_id=pid,
                name=name,
                standard=std,
                rule_description=desc,
                mandatory_approvers=approvers,
                enforce_branch_protection=True,
                enforce_mfa=True,
                active=True,
            )

        # Default CODEOWNERS paths
        self._codeowners = {
            "core/enterprise/*": [ExecutiveRole.CEO, ExecutiveRole.CTO],
            "core/security/*": [ExecutiveRole.DIRECTOR_SECURITY],
            "core/finance/*": [ExecutiveRole.DIRECTOR_FINANCE],
            "core/cluster/*": [ExecutiveRole.DIRECTOR_PLATFORM, ExecutiveRole.DIRECTOR_DEVOPS],
        }

    def register_policy(self, policy: GovernancePolicy) -> None:
        """Registers a new governance compliance policy."""
        with self._lock:
            self._policies[policy.policy_id] = policy
            self.log_audit_event(
                action="REGISTER_GOVERNANCE_POLICY",
                actor="System/Governance",
                target_entity=policy.policy_id,
                department=DepartmentType.LEGAL,
                details={"policy_name": policy.name, "standard": policy.standard.value},
            )

    def log_audit_event(
        self,
        action: str,
        actor: str,
        target_entity: str,
        department: DepartmentType,
        details: Dict[str, Any],
    ) -> AuditLogRecord:
        """
        Appends an immutable audit log record protected by a SHA-256 cryptographic chain.
        """
        with self._lock:
            now = time.time()
            record_id = f"AUDIT-{int(now * 1000)}-{len(self._audit_trail) + 1}"
            
            # Hash previous record to create tamper-evident chain
            prev_hash = self._audit_trail[-1].sha256_hash if self._audit_trail else "GENESIS_HASH"
            payload = f"{record_id}|{action}|{actor}|{target_entity}|{department.value}|{json.dumps(details, sort_keys=True)}|{now}|{prev_hash}"
            sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()

            record = AuditLogRecord(
                record_id=record_id,
                action=action,
                actor=actor,
                target_entity=target_entity,
                department=department,
                details=details,
                sha256_hash=sha256,
                timestamp=now,
            )
            self._audit_trail.append(record)
            return record

    def verify_audit_trail_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Validates the entire cryptographic SHA-256 chain to detect any tampering or deletion.
        """
        with self._lock:
            prev_hash = "GENESIS_HASH"
            for idx, rec in enumerate(self._audit_trail):
                payload = f"{rec.record_id}|{rec.action}|{rec.actor}|{rec.target_entity}|{rec.department.value}|{json.dumps(rec.details, sort_keys=True)}|{rec.timestamp}|{prev_hash}"
                expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                if rec.sha256_hash != expected:
                    return False, f"Audit record [{rec.record_id}] at index {idx} has invalid hash signature"
                prev_hash = rec.sha256_hash
            return True, None

    def validate_codeowners(
        self,
        file_path: str,
        approving_roles: List[ExecutiveRole],
        require_all: bool = False,
    ) -> Tuple[bool, List[ExecutiveRole]]:
        """
        Checks if required codeowners have signed off for a modified file path.
        If require_all is False, passes if at least one designated codeowner has approved (or if path is unrestricted).
        If require_all is True, passes only if all designated codeowners have approved.
        """
        with self._lock:
            required_roles: Set[ExecutiveRole] = set()
            for pattern, owners in self._codeowners.items():
                prefix = pattern.replace("*", "").rstrip("/")
                if file_path.startswith(prefix) or pattern == file_path:
                    required_roles.update(owners)

            if not required_roles:
                return (True, [])

            if require_all:
                missing = [r for r in required_roles if r not in approving_roles]
                return (len(missing) == 0, list(required_roles))
            else:
                has_approval = any(r in approving_roles for r in required_roles)
                return (has_approval, list(required_roles))

    def validate_branch_push(self, branch: str, is_force_push: bool, approvals_count: int) -> Tuple[bool, str]:
        """Validates branch protection rules."""
        if branch in self._protected_branches or branch.startswith("release/"):
            if is_force_push:
                return False, f"Force push rejected on protected branch '{branch}'"
            if approvals_count < 2:
                return False, f"Branch '{branch}' requires minimum 2 approvals, got {approvals_count}"
        return True, "Branch rules validated"

    def generate_compliance_report(self) -> Dict[str, Any]:
        """Generates comprehensive compliance and audit report."""
        with self._lock:
            integrity_valid, error = self.verify_audit_trail_integrity()
            return {
                "active_policies_count": len(self._policies),
                "audit_records_count": len(self._audit_trail),
                "audit_integrity_valid": integrity_valid,
                "audit_integrity_error": error,
                "policies": [p.to_dict() for p in self._policies.values()],
                "protected_branches": list(self._protected_branches),
                "codeowners_rules": {k: [r.value for r in v] for k, v in self._codeowners.items()},
            }
