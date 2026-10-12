"""
enterprise_governance.py - Global Enterprise Governance & Compliance (AutoDev Version 3.5)

Enforces enterprise-wide standards across all 7 corporate pillars:
1. Budget limits & financial controls
2. Architecture standards & ADR compliance
3. Coding standards & static analysis gates
4. Security standards & vulnerability thresholds
5. Regulatory compliance standards (SOC2, GDPR, HIPAA, PCI-DSS)
6. Documentation standards & API reference completeness
7. Release standards & quality verification gates

100% Python Standard Library.
"""

from __future__ import annotations

import collections
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.enterprise_policy_engine import (
    EnterprisePolicyEngine,
    PolicyAction,
    PolicyDomain,
    PolicyEvaluationResult,
    PolicyScope,
)

logger = logging.getLogger("AutoDev.Federation.Governance")


@dataclass
class GovernanceAuditReport:
    """Consolidated audit report for a company or project."""
    audit_id: str
    target_id: str  # company_id or project_id
    target_type: str  # COMPANY or PROJECT
    timestamp: float
    overall_compliance_score: float  # 0.0 to 100.0
    is_compliant: bool
    domain_scores: Dict[str, float] = field(default_factory=dict)
    violations: List[str] = field(default_factory=list)
    remediation_actions: List[str] = field(default_factory=list)


class EnterpriseGovernanceManager:
    """
    Automated governance and standards enforcement across the entire enterprise federation.
    """

    def __init__(self, policy_engine: Optional[EnterprisePolicyEngine] = None) -> None:
        self._lock = threading.RLock()
        self.policy_engine = policy_engine or EnterprisePolicyEngine()
        self._audit_reports: List[GovernanceAuditReport] = []
        self._bootstrap_standard_policies()

    def _bootstrap_standard_policies(self) -> None:
        """Installs baseline enterprise policies across all 7 pillars."""
        # 1. Budget: Prevent unapproved expenditures > $500,000 without Executive board signoff
        self.policy_engine.register_rule(
            name="Executive Budget Ceiling",
            domain=PolicyDomain.BUDGET,
            scope=PolicyScope.ENTERPRISE,
            condition=lambda ctx: ctx.get("budget_spent", 0) > ctx.get("budget_allocated", 100000) * 1.2,
            action=PolicyAction.REQUIRE_APPROVAL,
            severity="HIGH",
            description="Spending exceeds 120% of allocated budget. Executive CFO signoff required.",
        )

        # 2. Architecture: Zero external orchestrators (LangGraph/CrewAI/etc) and mandatory standard lib
        self.policy_engine.register_rule(
            name="Zero External Orchestration Rule",
            domain=PolicyDomain.ARCHITECTURE,
            scope=PolicyScope.ENTERPRISE,
            condition=lambda ctx: any(dep in ctx.get("dependencies", []) for dep in ["langgraph", "crewai", "autogen", "haystack"]),
            action=PolicyAction.DENY,
            severity="CRITICAL",
            description="External AI orchestration frameworks are prohibited by enterprise policy.",
        )

        # 3. Coding: Disallow unsafe eval/exec constructs
        self.policy_engine.register_rule(
            name="Unsafe Dynamic Execution Ban",
            domain=PolicyDomain.CODING,
            scope=PolicyScope.ENTERPRISE,
            condition=lambda ctx: ctx.get("has_eval_or_exec", False) is True,
            action=PolicyAction.DENY,
            severity="CRITICAL",
            description="Use of eval() or exec() violates enterprise secure coding standards.",
        )

        # 4. Security: Zero critical CVEs accepted into production releases
        self.policy_engine.register_rule(
            name="Zero Critical CVE Gate",
            domain=PolicyDomain.SECURITY,
            scope=PolicyScope.ENTERPRISE,
            condition=lambda ctx: ctx.get("critical_cves_count", 0) > 0,
            action=PolicyAction.DENY,
            severity="CRITICAL",
            description="Production promotion blocked due to active critical CVEs.",
        )

        # 5. Compliance: Data privacy compliance (GDPR/PII masking)
        self.policy_engine.register_rule(
            name="Mandatory PII Masking",
            domain=PolicyDomain.COMPLIANCE,
            scope=PolicyScope.ENTERPRISE,
            condition=lambda ctx: ctx.get("unmasked_pii_detected", False) is True,
            action=PolicyAction.DENY,
            severity="HIGH",
            description="Unmasked personally identifiable information (PII) detected in data stream.",
        )

        # 6. Documentation: Mandatory API reference documentation
        self.policy_engine.register_rule(
            name="API Documentation Completeness",
            domain=PolicyDomain.DOCUMENTATION,
            scope=PolicyScope.ENTERPRISE,
            condition=lambda ctx: ctx.get("api_endpoints_count", 0) > 0 and not ctx.get("has_api_docs", True),
            action=PolicyAction.AUDIT_FLAG,
            severity="MEDIUM",
            description="Public API endpoints missing accompanying interface documentation.",
        )

        # 7. Release: Minimum 95% QA pass rate required for release promotion
        self.policy_engine.register_rule(
            name="Release Quality Gate",
            domain=PolicyDomain.RELEASE,
            scope=PolicyScope.ENTERPRISE,
            condition=lambda ctx: ctx.get("qa_pass_rate_pct", 100.0) < 95.0,
            action=PolicyAction.DENY,
            severity="HIGH",
            description="QA regression pass rate below 95% threshold.",
        )

    def audit_target(
        self,
        target_id: str,
        target_type: str,
        context: Dict[str, Any],
    ) -> GovernanceAuditReport:
        """
        Executes a comprehensive governance audit across all 7 domains for a target company or project.
        Calculates compliance scores and generates remediation steps.
        """
        with self._lock:
            domain_scores: Dict[str, float] = {}
            all_violations: List[str] = []
            all_remediations: List[str] = []

            for domain in PolicyDomain:
                res = self.policy_engine.evaluate(domain=domain, context=context)
                score = 100.0 if res.is_compliant else max(20.0, 100.0 - (len(res.violations) * 35.0))
                domain_scores[domain.value] = score
                all_violations.extend(res.violations)
                all_remediations.extend(res.remediation_required)

            overall_score = round(sum(domain_scores.values()) / max(1, len(domain_scores)), 1)
            is_compliant = overall_score >= 85.0 and len(all_violations) == 0

            aid = f"GOV-AUD-{uuid.uuid4().hex[:8].upper()}"
            report = GovernanceAuditReport(
                audit_id=aid,
                target_id=target_id,
                target_type=target_type,
                timestamp=time.time(),
                overall_compliance_score=overall_score,
                is_compliant=is_compliant,
                domain_scores=domain_scores,
                violations=all_violations,
                remediation_actions=all_remediations,
            )
            self._audit_reports.append(report)
            logger.info("Conducted governance audit %s for %s (%s). Score: %.1f", aid, target_id, target_type, overall_score)
            return report

    def verify_release_gate(self, release_context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Convenience method checking Security, Quality, and Documentation gates for a release."""
        sec_res = self.policy_engine.evaluate(PolicyDomain.SECURITY, release_context)
        rel_res = self.policy_engine.evaluate(PolicyDomain.RELEASE, release_context)
        doc_res = self.policy_engine.evaluate(PolicyDomain.DOCUMENTATION, release_context)

        violations = sec_res.violations + rel_res.violations + doc_res.violations
        can_release = len(violations) == 0
        return can_release, violations

    def get_governance_summary(self) -> Dict[str, Any]:
        """Returns macro compliance summary."""
        with self._lock:
            if not self._audit_reports:
                return {"total_audits": 0, "average_compliance_score": 100.0, "compliant_rate": 1.0}

            avg_score = sum(r.overall_compliance_score for r in self._audit_reports) / len(self._audit_reports)
            compliant_count = sum(1 for r in self._audit_reports if r.is_compliant)

            return {
                "total_audits_conducted": len(self._audit_reports),
                "average_compliance_score": round(avg_score, 1),
                "compliance_pass_rate": round(compliant_count / len(self._audit_reports), 2),
                "recent_violations_count": sum(len(r.violations) for r in self._audit_reports[-5:]),
            }
