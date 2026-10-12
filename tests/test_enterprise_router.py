"""
test_enterprise_router.py - Unit Tests for EnterpriseRouter (AutoDev Version 3.5)
"""

import pytest

from core.enterprise_registry import EnterpriseRegistry, OrganizationStatus
from core.enterprise_router import EnterpriseRouter, RoutingRule
from core.inter_company_bus import (
    FederationMessage,
    FederationMessagePriority,
    FederationMessageType,
    InterCompanyBus,
    MessageClassification,
)


@pytest.fixture
def router_setup():
    bus = InterCompanyBus()
    reg = EnterpriseRegistry()
    router = EnterpriseRouter(bus=bus, registry=reg)

    reg.register_company("COMP-A", "Alpha Corp", "Backend")
    reg.register_company("COMP-B", "Beta Corp", "Frontend")
    reg.register_company("COMP-C", "Gamma Corp", "AI")
    bus.register_company("COMP-A")
    bus.register_company("COMP-B")
    bus.register_company("COMP-C")

    return bus, reg, router


def test_unrestricted_routing(router_setup):
    bus, reg, router = router_setup
    router.allow_all_traffic("COMP-A")

    msg = FederationMessage(
        company_id="COMP-A",
        target_company_id="COMP-B",
        payload={"data": "hello"},
    )
    assert router.route_message(msg) is True
    assert msg.status == "DELIVERED"
    stats = router.get_router_stats()
    assert stats["total_routed"] == 1


def test_acl_blocking_unauthorized_cross_traffic(router_setup):
    bus, reg, router = router_setup
    # Explicitly configure ACL for COMP-A to only allow COMP-C
    router.allow_cross_company_traffic("COMP-A", "COMP-C")

    # Dispatch to COMP-B should be blocked by ACL
    msg = FederationMessage(
        company_id="COMP-A",
        target_company_id="COMP-B",
        payload={"secret": "not_allowed"},
    )
    assert router.route_message(msg) is False
    assert msg.status == "FAILED"
    assert "ACL denied" in msg.error_reason

    stats = router.get_router_stats()
    assert stats["total_blocked"] == 1


def test_classification_limit_enforcement(router_setup):
    bus, reg, router = router_setup
    router.allow_all_traffic("COMP-A")
    # Set max classification for COMP-A to INTERNAL
    router.set_company_classification_limit("COMP-A", MessageClassification.INTERNAL)

    # Attempt to send RESTRICTED message
    msg = FederationMessage(
        company_id="COMP-A",
        target_company_id="COMP-B",
        classification=MessageClassification.RESTRICTED,
        payload={"top_secret": "classified"},
    )
    assert router.route_message(msg) is False
    assert msg.status == "FAILED"
    assert "exceeds sender clearance" in msg.error_reason


def test_dynamic_routing_rule_override(router_setup):
    bus, reg, router = router_setup
    router.allow_all_traffic("COMP-A")

    # Add rule: If message payload has 'urgent_bug', escalate priority to EMERGENCY
    rule = RoutingRule(
        rule_id="R-URGENT",
        name="Escalate Urgent Bugs",
        condition=lambda m: m.payload.get("is_urgent_bug") is True,
        priority_override=FederationMessagePriority.EMERGENCY,
    )
    router.add_routing_rule(rule)

    msg = FederationMessage(
        company_id="COMP-A",
        target_company_id="COMP-B",
        priority=FederationMessagePriority.NORMAL,
        payload={"is_urgent_bug": True},
    )
    assert router.route_message(msg) is True
    assert msg.priority == FederationMessagePriority.EMERGENCY


def test_automatic_rerouting_when_target_is_offline(router_setup):
    bus, reg, router = router_setup
    router.allow_all_traffic("COMP-A")

    # Add capability to both COMP-B and COMP-C
    reg.add_capability("COMP-B", "HeavyCompute", "INFRA", "Compute node")
    reg.add_capability("COMP-C", "HeavyCompute", "INFRA", "Backup compute node")

    # Mark COMP-B as OFFLINE
    reg.update_company_status("COMP-B", OrganizationStatus.OFFLINE)

    msg = FederationMessage(
        company_id="COMP-A",
        target_company_id="COMP-B",
        payload={"required_capability": "HeavyCompute", "job": "SimulatePhysics"},
    )
    assert router.route_message(msg) is True
    # Message should be automatically rerouted to COMP-C!
    assert msg.target_company_id == "COMP-C"
    stats = router.get_router_stats()
    assert stats["total_rerouted"] == 1
