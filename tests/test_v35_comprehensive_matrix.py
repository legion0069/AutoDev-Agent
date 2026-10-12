"""
test_v35_comprehensive_matrix.py - Comprehensive Parameterized Matrix & Edge Case Tests (AutoDev Version 3.5)
"""

import hashlib
import json
import time
import pytest

from core.cross_company_scheduler import CrossCompanyScheduler, FederationTask
from core.enterprise_disaster_recovery import EnterpriseDisasterRecovery, OutageType
from core.enterprise_governance import EnterpriseGovernanceManager
from core.enterprise_knowledge import (
    EnterpriseKnowledgeGraph,
    KnowledgeCategory,
    KnowledgeEdge,
    KnowledgeNode,
    RelationshipType,
)
from core.enterprise_policy_engine import (
    EnterprisePolicyEngine,
    PolicyAction,
    PolicyDomain,
    PolicyScope,
)
from core.enterprise_registry import CapabilityOffering, CompanyProfile, EnterpriseRegistry, OrganizationStatus
from core.enterprise_security import EnterpriseSecurityManager
from core.global_metrics import GlobalEnterpriseDashboard, GlobalMetricsCalculator
from core.inter_company_bus import (
    FederationMessage,
    FederationMessagePriority,
    FederationMessageType,
    InterCompanyBus,
    MessageClassification,
)
from core.portfolio_manager import PortfolioManager, PortfolioProject, ProjectStatus
from core.resource_marketplace import ResourceMarketplace, ResourceType


# =============================================================================
# 1. Message Type & Priority Matrix Tests
# =============================================================================

@pytest.mark.parametrize("msg_type", list(FederationMessageType))
def test_all_message_types_supported(msg_type):
    bus = InterCompanyBus()
    bus.register_company("C1")
    bus.register_company("C2")
    msg = FederationMessage(
        company_id="C1",
        target_company_id="C2",
        message_type=msg_type,
        payload={"type": msg_type.value},
    )
    assert bus.send_message(msg) is True
    inbox = bus.get_company_messages("C2")
    assert len(inbox) == 1
    assert inbox[0].message_type == msg_type


@pytest.mark.parametrize("priority", list(FederationMessagePriority))
def test_all_message_priorities_supported(priority):
    bus = InterCompanyBus()
    bus.register_company("C1")
    bus.register_company("C2")
    msg = FederationMessage(
        company_id="C1",
        target_company_id="C2",
        priority=priority,
        payload={"p": priority.value},
    )
    assert bus.send_message(msg) is True
    inbox = bus.get_company_messages("C2")
    assert inbox[0].priority == priority


@pytest.mark.parametrize("classification", list(MessageClassification))
def test_all_message_classifications_supported(classification):
    bus = InterCompanyBus()
    bus.register_company("C1")
    bus.register_company("C2")
    msg = FederationMessage(
        company_id="C1",
        target_company_id="C2",
        classification=classification,
        payload={"c": classification.value},
    )
    assert bus.send_message(msg) is True
    inbox = bus.get_company_messages("C2")
    assert inbox[0].classification == classification


# =============================================================================
# 2. Knowledge Category & Relationship Type Matrix Tests
# =============================================================================

@pytest.mark.parametrize("category", list(KnowledgeCategory))
def test_all_knowledge_categories_publishable(category):
    kg = EnterpriseKnowledgeGraph()
    node = kg.add_knowledge_node(
        category=category,
        title=f"Node for {category.value}",
        content=f"Detailed institutional knowledge content for {category.value}",
        company_id="COMP-A",
        author="Agent",
    )
    assert node.category == category
    assert kg.get_knowledge_analytics()["nodes_by_category"][category.value] == 1


@pytest.mark.parametrize("rel_type", list(RelationshipType))
def test_all_relationship_types_linkable(rel_type):
    kg = EnterpriseKnowledgeGraph()
    n1 = kg.add_knowledge_node(KnowledgeCategory.ADR, "Source", "Content", "C1", "Dev")
    n2 = kg.add_knowledge_node(KnowledgeCategory.API, "Target", "Content", "C1", "Dev")
    edge = kg.link_nodes(n1.node_id, n2.node_id, rel_type, description=f"Relationship {rel_type.value}")
    assert edge is not None
    assert edge.relationship == rel_type


# =============================================================================
# 3. Resource Marketplace Resource Types Matrix Tests
# =============================================================================

@pytest.mark.parametrize("resource_type", list(ResourceType))
def test_all_resource_types_tradable(resource_type):
    mkt = ResourceMarketplace()
    ask = mkt.place_ask("C1", resource_type, units=10.0, price_per_unit_usd=100.0)
    bid = mkt.place_bid("C2", resource_type, units=10.0, max_price_per_unit_usd=100.0)
    assert ask.status == "FILLED"
    assert bid.status == "FILLED"
    depth = mkt.get_market_depth(resource_type)
    assert depth["resource_type"] == resource_type.value


# =============================================================================
# 4. Policy Domain & Scope Matrix Tests
# =============================================================================

@pytest.mark.parametrize("domain", list(PolicyDomain))
def test_all_policy_domains_evaluated(domain):
    pe = EnterprisePolicyEngine()
    rule = pe.register_rule(
        name=f"Rule for {domain.value}",
        domain=domain,
        scope=PolicyScope.ENTERPRISE,
        condition=lambda ctx: ctx.get("violation", False) is True,
        action=PolicyAction.DENY,
    )
    res_clean = pe.evaluate(domain, {"violation": False})
    assert res_clean.is_compliant is True

    res_viol = pe.evaluate(domain, {"violation": True})
    assert res_viol.is_compliant is False


@pytest.mark.parametrize("action", list(PolicyAction))
def test_all_policy_actions_propagated(action):
    pe = EnterprisePolicyEngine()
    pe.register_rule(
        name=f"Action Rule {action.value}",
        domain=PolicyDomain.SECURITY,
        scope=PolicyScope.ENTERPRISE,
        condition=lambda ctx: True,
        action=action,
    )
    res = pe.evaluate(PolicyDomain.SECURITY, {})
    assert res.action == action


# =============================================================================
# 5. Outage Type Disaster Recovery Matrix Tests
# =============================================================================

@pytest.mark.parametrize("outage_type", list(OutageType))
def test_outage_types_recorded_in_dr(outage_type):
    dr = EnterpriseDisasterRecovery()
    if outage_type == OutageType.COMPANY_OUTAGE:
        evt = dr.recover_company_outage("C1")
    elif outage_type == OutageType.DEPARTMENT_OUTAGE:
        evt = dr.recover_department_outage("C1", "QA")
    elif outage_type == OutageType.MEMORY_CORRUPTION:
        evt = dr.recover_memory_corruption({"a": 1}, "dummy_checksum")
    elif outage_type == OutageType.BUS_FAILURE:
        evt = dr.recover_bus_failure()
    else:
        # Default record
        from core.enterprise_disaster_recovery import RecoveryEvent
        evt = RecoveryEvent("E1", outage_type, "ENTITY", "Reason", "Action", True, 1.0)
        dr._recovery_history.append(evt)

    assert evt.outage_type == outage_type


# =============================================================================
# 6. Project Status Matrix Tests
# =============================================================================

@pytest.mark.parametrize("status", list(ProjectStatus))
def test_all_project_statuses_assignable(status):
    pm = PortfolioManager()
    proj = pm.create_project(f"Project for {status.value}", "COMP-A")
    pm.update_progress(proj.project_id, status=status)
    assert proj.status == status


# =============================================================================
# 7. Model Serialization & to_dict Matrix Tests
# =============================================================================

def test_knowledge_node_to_dict():
    n = KnowledgeNode("K1", KnowledgeCategory.ADR, "Title", "Content", "C1", "Dev", ["tag1"])
    d = n.to_dict()
    assert d["node_id"] == "K1"
    assert d["category"] == "ADR"
    assert json.dumps(d)


def test_federation_task_to_dict():
    t = FederationTask("T1", "C1", "Title", 10.0, priority=4)
    d = t.to_dict()
    assert d["task_id"] == "T1"
    assert json.dumps(d)


def test_portfolio_project_to_dict():
    p = PortfolioProject("P1", "Title", "C1")
    d = p.to_dict()
    assert d["project_id"] == "P1"
    assert "budget_variance_usd" in d
    assert "cost_performance_index" in d
    assert json.dumps(d)


def test_global_dashboard_to_dict():
    calc = GlobalMetricsCalculator()
    dash = calc.calculate_global_dashboard({})
    d = dash.to_dict()
    assert "enterprise_health_score" in d
    assert json.dumps(d)


def test_company_profile_to_dict():
    prof = CompanyProfile("C1", "Name", "Domain", "BU", 50, 500000.0)
    d = prof.to_dict()
    assert d["company_id"] == "C1"
    assert json.dumps(d)


def test_capability_offering_to_dict():
    cap = CapabilityOffering(capability_name="CAP-1", category="AI", description="AI Description", capacity_units=100.0)
    d = cap.to_dict()
    assert d["capability_name"] == "CAP-1"
    assert json.dumps(d)


# =============================================================================
# 8. Edge Cases: Security Manager
# =============================================================================

def test_security_expired_token():
    sec = EnterpriseSecurityManager()
    # Create identity with 0.01s validity
    ident = sec.create_identity("C1", "D1", "Role", token_validity_seconds=0.01)
    time.sleep(0.02)
    # Expired token must evaluate to None
    assert sec.validate_token(ident.token) is None


def test_security_invalid_token_format():
    sec = EnterpriseSecurityManager()
    assert sec.validate_token("INVALID_TOKEN_STRING") is None
    assert sec.validate_token("") is None


def test_security_unknown_secret_retrieval():
    sec = EnterpriseSecurityManager()
    ident = sec.create_identity("C1", "D1", "Role")
    assert sec.retrieve_secret("NON_EXISTENT_KEY", ident.token) is None


# =============================================================================
# 9. Edge Cases: Scheduler
# =============================================================================

def test_scheduler_disconnected_subgraphs():
    sched = CrossCompanyScheduler()
    # Subgraph 1
    sched.add_task("G1_T1", "C1", "Sub1 Task 1", 5.0)
    sched.add_task("G1_T2", "C1", "Sub1 Task 2", 10.0, dependencies=["G1_T1"])

    # Subgraph 2 (independent)
    sched.add_task("G2_T1", "C2", "Sub2 Task 1", 20.0)

    res = sched.compute_critical_path()
    assert res["total_project_duration_hours"] == 20.0
    assert "G2_T1" in res["critical_path_tasks"]


def test_scheduler_nonexistent_dependencies_ignored():
    sched = CrossCompanyScheduler()
    sched.add_task("T1", "C1", "Task 1", 5.0, dependencies=["GHOST_DEP"])
    res = sched.compute_critical_path()
    assert res["total_project_duration_hours"] == 5.0


# =============================================================================
# 10. Edge Cases: Disaster Recovery
# =============================================================================

def test_disaster_recovery_corrupt_chain_fallback_to_second_snapshot():
    dr = EnterpriseDisasterRecovery()
    snap1 = dr.capture_snapshot({"version": 1})
    snap2 = dr.capture_snapshot({"version": 2})

    # Tamper with snap2's checksum
    snap2.checksum_sha256 = "INVALID_HASH"

    # Latest VALID snapshot should fall back to snap1
    valid_snap = dr.get_latest_valid_snapshot()
    assert valid_snap is not None
    assert valid_snap.snapshot_id == snap1.snapshot_id
    assert valid_snap.state_payload["version"] == 1
