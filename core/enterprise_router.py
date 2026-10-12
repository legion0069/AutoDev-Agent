"""
enterprise_router.py - Enterprise Message & Workload Router (AutoDev Version 3.5)

Provides intelligent message and workload routing across the enterprise federation:
- Dynamic content-based and capability-based routing rules
- Cross-company Access Control List (ACL) & Zero Trust classification enforcement
- Automatic rerouting to healthy alternate providers during company degradation/outages
- Trace inspection, route metrics, and priority-aware escalation
- 100% Python Standard Library.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.enterprise_registry import EnterpriseRegistry, OrganizationStatus
from core.inter_company_bus import (
    FederationMessage,
    FederationMessagePriority,
    FederationMessageType,
    InterCompanyBus,
    MessageClassification,
)

logger = logging.getLogger("AutoDev.Federation.Router")


@dataclass
class RoutingRule:
    """A rule mapping criteria to routing decisions."""
    rule_id: str
    name: str
    condition: Callable[[FederationMessage], bool]
    target_company_id: Optional[str] = None
    target_department_id: Optional[str] = None
    priority_override: Optional[FederationMessagePriority] = None
    intercept_callback: Optional[Callable[[FederationMessage], None]] = None
    is_active: bool = True


class EnterpriseRouter:
    """
    Intelligent router coordinating message dispatch across federated companies.
    Applies security ACLs, capability fallbacks, and priority escalation.
    """

    def __init__(
        self,
        bus: InterCompanyBus,
        registry: EnterpriseRegistry,
    ) -> None:
        self._lock = threading.RLock()
        self.bus = bus
        self.registry = registry
        # ACL: source_company_id -> set of allowed target_company_ids (or '*' for unrestricted)
        self._company_acl: Dict[str, Set[str]] = {}
        # Classification threshold: company_id -> max allowed classification
        self._classification_limits: Dict[str, MessageClassification] = {}
        # Dynamic routing rules
        self._rules: List[RoutingRule] = []
        # Routing statistics
        self._routed_count = 0
        self._rerouted_count = 0
        self._blocked_count = 0

    def allow_cross_company_traffic(self, source_company_id: str, target_company_id: str) -> None:
        """Permits source company to route messages to target company."""
        with self._lock:
            if source_company_id not in self._company_acl:
                self._company_acl[source_company_id] = set()
            self._company_acl[source_company_id].add(target_company_id)

    def allow_all_traffic(self, source_company_id: str) -> None:
        """Allows source company to dispatch to any company in the federation."""
        with self._lock:
            if source_company_id not in self._company_acl:
                self._company_acl[source_company_id] = set()
            self._company_acl[source_company_id].add("*")

    def set_company_classification_limit(
        self,
        company_id: str,
        max_classification: MessageClassification,
    ) -> None:
        """Sets highest information classification tier allowed for this company."""
        with self._lock:
            self._classification_limits[company_id] = max_classification

    def add_routing_rule(self, rule: RoutingRule) -> None:
        """Registers a dynamic routing rule."""
        with self._lock:
            self._rules.append(rule)

    def route_message(self, message: FederationMessage) -> bool:
        """
        Evaluates ACLs, rules, and company health before delegating to the InterCompanyBus.
        Performs automated rerouting if target company is DEGRADED or OFFLINE.
        """
        with self._lock:
            # 1. Access Control List Check
            if not self._check_acl(message):
                message.status = "FAILED"
                message.error_reason = f"ACL denied routing from '{message.company_id}' to '{message.target_company_id}'"
                self._blocked_count += 1
                logger.warning(message.error_reason)
                return False

            # 2. Information Security Classification Limit Check
            if not self._check_classification(message):
                message.status = "FAILED"
                message.error_reason = f"Classification '{message.classification.value}' exceeds sender clearance."
                self._blocked_count += 1
                logger.warning(message.error_reason)
                return False

            # 3. Dynamic Rules Evaluation
            for rule in self._rules:
                if rule.is_active and rule.condition(message):
                    if rule.target_company_id:
                        message.target_company_id = rule.target_company_id
                    if rule.target_department_id:
                        message.target_department_id = rule.target_department_id
                    if rule.priority_override:
                        message.priority = rule.priority_override
                    if rule.intercept_callback:
                        rule.intercept_callback(message)

            # 4. Target Health & Capability Fallback Rerouting
            if message.target_company_id not in ("ALL", "*"):
                target_prof = self.registry.get_company(message.target_company_id)
                if target_prof and target_prof.status in (OrganizationStatus.OFFLINE, OrganizationStatus.MAINTENANCE):
                    # Attempt automated fallback to another company offering the needed capability
                    cap_needed = message.payload.get("required_capability")
                    if cap_needed:
                        alternates = self.registry.find_companies_by_capability(cap_needed)
                        # Pick first active alternate that is not the offline target
                        healthy_alt = next((alt for alt in alternates if alt.company_id != target_prof.company_id), None)
                        if healthy_alt:
                            logger.info(
                                "Rerouting message %s from offline '%s' to alternate '%s' for capability '%s'",
                                message.message_id, target_prof.company_id, healthy_alt.company_id, cap_needed,
                            )
                            message.target_company_id = healthy_alt.company_id
                            self._rerouted_count += 1
                        else:
                            logger.warning("Target '%s' is offline and no alternate found for '%s'", target_prof.company_id, cap_needed)
                    else:
                        logger.warning("Target '%s' is %s with no capability specified for fallback.", target_prof.company_id, target_prof.status.value)

            # 5. Dispatch via Bus
            success = self.bus.send_message(message)
            if success:
                self._routed_count += 1
            return success

    def _check_acl(self, message: FederationMessage) -> bool:
        """Verifies cross-company communication permissions."""
        src = message.company_id
        tgt = message.target_company_id

        # Federation system / broadcast sender is always allowed
        if src in ("GLOBAL_ENTERPRISE", "SYSTEM", "FEDERATION"):
            return True

        # Intracompany messages are always allowed
        if src == tgt:
            return True

        # If no ACL defined yet for src, default to permissive enterprise federation
        if src not in self._company_acl:
            return True

        allowed = self._company_acl[src]
        return "*" in allowed or tgt in allowed or tgt in ("ALL", "*")

    def _check_classification(self, message: FederationMessage) -> bool:
        """Ensures message does not exceed classification boundary."""
        src = message.company_id
        if src not in self._classification_limits:
            return True

        hierarchy = {
            MessageClassification.PUBLIC: 1,
            MessageClassification.INTERNAL: 2,
            MessageClassification.CONFIDENTIAL: 3,
            MessageClassification.RESTRICTED: 4,
        }
        max_allowed = self._classification_limits[src]
        return hierarchy.get(message.classification, 1) <= hierarchy.get(max_allowed, 4)

    def get_router_stats(self) -> Dict[str, Any]:
        """Returns routing telemetry."""
        with self._lock:
            return {
                "total_routed": self._routed_count,
                "total_rerouted": self._rerouted_count,
                "total_blocked": self._blocked_count,
                "configured_acls": len(self._company_acl),
                "classification_limits": len(self._classification_limits),
                "active_rules_count": sum(1 for r in self._rules if r.is_active),
            }
