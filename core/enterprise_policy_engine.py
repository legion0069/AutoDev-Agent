"""
enterprise_policy_engine.py - Enterprise Declarative Policy Engine (AutoDev Version 3.5)

Evaluates hierarchical policies across the enterprise federation:
- Multi-tier policy scoping: ENTERPRISE > BUSINESS_UNIT > COMPANY > DEPARTMENT.
- Declarative condition matching across payloads, contexts, and transactions.
- Policy actions: ALLOW, DENY, REQUIRE_APPROVAL, AUDIT_FLAG, QUARANTINE.
- Cascading rule inheritance and priority overrides.
- 100% Python Standard Library.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("AutoDev.Federation.PolicyEngine")


class PolicyScope(str, enum.Enum):
    """Scope tier where a policy applies."""
    ENTERPRISE = "ENTERPRISE"
    BUSINESS_UNIT = "BUSINESS_UNIT"
    COMPANY = "COMPANY"
    DEPARTMENT = "DEPARTMENT"


class PolicyDomain(str, enum.Enum):
    """Domain categorization for policies."""
    BUDGET = "BUDGET"
    ARCHITECTURE = "ARCHITECTURE"
    CODING = "CODING"
    SECURITY = "SECURITY"
    COMPLIANCE = "COMPLIANCE"
    DOCUMENTATION = "DOCUMENTATION"
    RELEASE = "RELEASE"


class PolicyAction(str, enum.Enum):
    """Action to take upon policy evaluation."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    AUDIT_FLAG = "AUDIT_FLAG"
    QUARANTINE = "QUARANTINE"


@dataclass
class PolicyRule:
    """A policy rule defining conditions and actions."""
    rule_id: str
    name: str
    domain: PolicyDomain
    scope: PolicyScope
    target_id: str = "*"  # '*' for all targets within scope, or specific company/dept id
    severity: str = "HIGH"  # LOW, MEDIUM, HIGH, CRITICAL
    action: PolicyAction = PolicyAction.DENY
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    description: str = ""
    is_active: bool = True
    created_at: float = field(default_factory=time.time)

    def evaluate(self, context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Evaluates condition on context dictionary.
        Returns (is_violated, reason).
        """
        if not self.is_active:
            return False, "Rule is inactive"
        if self.condition is None:
            return False, "No condition defined"

        try:
            violated = bool(self.condition(context))
            reason = f"Policy '{self.name}' ({self.rule_id}) violated" if violated else "Policy satisfied"
            return violated, reason
        except Exception as e:
            logger.error("Error evaluating policy %s: %s", self.rule_id, e)
            return True, f"Policy evaluation error: {e}"


@dataclass
class PolicyEvaluationResult:
    """Outcome of evaluating one or more policies against a context."""
    is_compliant: bool
    action: PolicyAction
    violations: List[str] = field(default_factory=list)
    remediation_required: List[str] = field(default_factory=list)
    evaluated_rules_count: int = 0


class EnterprisePolicyEngine:
    """
    Hierarchical policy evaluator enforcing enterprise-wide and company-specific rules.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._rules: Dict[str, PolicyRule] = {}
        # Domain index
        self._domain_rules: Dict[PolicyDomain, List[str]] = {d: [] for d in PolicyDomain}
        # Scope index
        self._scope_rules: Dict[PolicyScope, List[str]] = {s: [] for s in PolicyScope}

    def register_rule(
        self,
        name: str,
        domain: PolicyDomain | str,
        scope: PolicyScope | str,
        condition: Callable[[Dict[str, Any]], bool],
        action: PolicyAction | str = PolicyAction.DENY,
        target_id: str = "*",
        severity: str = "HIGH",
        description: str = "",
    ) -> PolicyRule:
        """Registers a new declarative policy rule."""
        with self._lock:
            rid = f"POL-{uuid.uuid4().hex[:8].upper()}"
            dom = PolicyDomain(domain) if isinstance(domain, str) else domain
            scp = PolicyScope(scope) if isinstance(scope, str) else scope
            act = PolicyAction(action) if isinstance(action, str) else action

            rule = PolicyRule(
                rule_id=rid,
                name=name,
                domain=dom,
                scope=scp,
                target_id=target_id,
                severity=severity,
                action=act,
                condition=condition,
                description=description,
            )
            self._rules[rid] = rule
            self._domain_rules[dom].append(rid)
            self._scope_rules[scp].append(rid)
            logger.info("Registered policy '%s' (%s) in domain %s", name, rid, dom.value)
            return rule

    def evaluate(
        self,
        domain: PolicyDomain | str,
        context: Dict[str, Any],
        company_id: Optional[str] = None,
        department_id: Optional[str] = None,
    ) -> PolicyEvaluationResult:
        """
        Evaluates active rules in a domain against the given context.
        Applies hierarchical inheritance (ENTERPRISE rules first, then COMPANY, then DEPARTMENT).
        """
        with self._lock:
            dom = PolicyDomain(domain) if isinstance(domain, str) else domain
            candidate_rule_ids = self._domain_rules.get(dom, [])

            violations = []
            remediations = []
            highest_action = PolicyAction.ALLOW
            evaluated_count = 0

            # Priority of actions: QUARANTINE > DENY > REQUIRE_APPROVAL > AUDIT_FLAG > ALLOW
            action_severity = {
                PolicyAction.ALLOW: 1,
                PolicyAction.AUDIT_FLAG: 2,
                PolicyAction.REQUIRE_APPROVAL: 3,
                PolicyAction.DENY: 4,
                PolicyAction.QUARANTINE: 5,
            }

            for rid in candidate_rule_ids:
                rule = self._rules[rid]
                if not rule.is_active:
                    continue

                # Scope matching
                if rule.scope == PolicyScope.ENTERPRISE:
                    # Enterprise applies to all
                    pass
                elif rule.scope == PolicyScope.COMPANY:
                    if rule.target_id not in ("*", company_id):
                        continue
                elif rule.scope == PolicyScope.DEPARTMENT:
                    if rule.target_id not in ("*", department_id):
                        continue

                evaluated_count += 1
                violated, reason = rule.evaluate(context)
                if violated:
                    violations.append(f"[{rule.severity}] {reason}")
                    remediations.append(f"Remediate {rule.name}: {rule.description}")
                    if action_severity[rule.action] > action_severity[highest_action]:
                        highest_action = rule.action

            is_compliant = len(violations) == 0
            return PolicyEvaluationResult(
                is_compliant=is_compliant,
                action=highest_action,
                violations=violations,
                remediation_required=remediations,
                evaluated_rules_count=evaluated_count,
            )

    def deactivate_rule(self, rule_id: str) -> bool:
        """Disables a policy rule."""
        with self._lock:
            if rule_id in self._rules:
                self._rules[rule_id].is_active = False
                return True
            return False

    def list_rules(self, domain: Optional[PolicyDomain] = None) -> List[PolicyRule]:
        """Lists active policy rules."""
        with self._lock:
            if domain:
                return [self._rules[rid] for rid in self._domain_rules.get(domain, [])]
            return list(self._rules.values())
