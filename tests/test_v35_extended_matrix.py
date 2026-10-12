"""
test_v35_extended_matrix.py - Extended Parameterized Test Matrix (AutoDev Version 3.5)
"""

import time
import pytest

from core.cross_company_scheduler import CrossCompanyScheduler, FederationTask
from core.enterprise_disaster_recovery import EnterpriseDisasterRecovery, OutageType
from core.enterprise_federation import EnterpriseFederation
from core.enterprise_governance import EnterpriseGovernanceManager
from core.enterprise_knowledge import EnterpriseKnowledgeGraph, KnowledgeCategory, RelationshipType
from core.enterprise_policy_engine import EnterprisePolicyEngine, PolicyAction, PolicyDomain, PolicyScope
from core.enterprise_registry import EnterpriseRegistry, OrganizationStatus
from core.enterprise_router import EnterpriseRouter
from core.enterprise_security import EnterpriseSecurityManager
from core.global_metrics import GlobalMetricsCalculator
from core.inter_company_bus import (
    FederationMessage,
    FederationMessagePriority,
    FederationMessageType,
    InterCompanyBus,
    MessageClassification,
)
from core.portfolio_manager import PortfolioManager, PortfolioProject, ProjectStatus
from core.resource_marketplace import OrderType, ResourceMarketplace, ResourceType
from core.shared_services import EnterpriseSharedServices


# =============================================================================
# 1. Baseline Companies Verification Matrix (8 Companies)
# =============================================================================

DEFAULT_COMPANIES = [
    ("COMP-A-BACKEND", "Apex Backend Platform Corp", "Backend Platform", 1500000.0),
    ("COMP-B-FRONTEND", "Vanguard Frontend Products Inc", "Frontend Products", 1200000.0),
    ("COMP-C-AI", "Cognitive AI Research Labs", "AI Research", 2000000.0),
    ("COMP-D-SECURITY", "Sentinel Enterprise Security Ltd", "Security & Defense", 1000000.0),
    ("COMP-E-CLOUD", "Stratus Cloud Infrastructure Systems", "Cloud Infrastructure", 1800000.0),
    ("COMP-F-QA", "Veritas Quality Assurance Services", "QA Services", 800000.0),
    ("COMP-G-DEVOPS", "Continuous DevOps Automation Corp", "DevOps & SRE", 900000.0),
    ("COMP-H-DOCS", "Lexicon Documentation Services", "Technical Documentation", 500000.0),
]


@pytest.mark.parametrize("cid, name, domain, budget", DEFAULT_COMPANIES)
def test_default_company_profiles_and_budgets(cid, name, domain, budget):
    fed = EnterpriseFederation()
    prof = fed.registry.get_company(cid)
    assert prof is not None
    assert prof.company_name == name
    assert prof.domain == domain
    assert prof.allocated_budget_usd == budget
    assert prof.status == OrganizationStatus.ACTIVE


# =============================================================================
# 2. Zero Trust Clearance Matrix (4 User Levels x 4 Resource Levels = 16 Tests)
# =============================================================================

CLEARANCE_LEVELS = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
CLEARANCE_RANKS = {"PUBLIC": 1, "INTERNAL": 2, "CONFIDENTIAL": 3, "RESTRICTED": 4}

@pytest.mark.parametrize("user_clearance", CLEARANCE_LEVELS)
@pytest.mark.parametrize("res_clearance", CLEARANCE_LEVELS)
def test_zero_trust_clearance_matrix(user_clearance, res_clearance):
    sec = EnterpriseSecurityManager()
    ident = sec.create_identity(
        company_id="COMP-A",
        department_id="ENG",
        role_name="User",
        clearance_level=user_clearance,
        permissions=["access:data"],
    )
    ok, reason = sec.authorize_action(
        token=ident.token,
        target_company_id="COMP-B",
        required_permission="access:data",
        resource_clearance=res_clearance,
    )
    expected_allow = CLEARANCE_RANKS[user_clearance] >= CLEARANCE_RANKS[res_clearance]
    assert ok is expected_allow
    if not expected_allow:
        assert "Clearance insufficient" in reason


# =============================================================================
# 3. Resource Marketplace Bid/Ask Order Placement Matrix (16 Tests)
# =============================================================================

@pytest.mark.parametrize("res_type", list(ResourceType))
@pytest.mark.parametrize("order_type", [OrderType.BID, OrderType.ASK])
def test_marketplace_order_creation_matrix(res_type, order_type):
    mkt = ResourceMarketplace()
    if order_type == OrderType.BID:
        order = mkt.place_bid("COMP-B", res_type, units=15.0, max_price_per_unit_usd=90.0)
    else:
        order = mkt.place_ask("COMP-A", res_type, units=15.0, price_per_unit_usd=110.0)
    assert order.order_id.startswith("ORD-")
    assert order.order_type == order_type
    assert order.resource_type == res_type
    assert order.status == "OPEN"


# =============================================================================
# 4. Knowledge Graph Tag Query Matrix
# =============================================================================

TAG_TEST_DATA = [
    ("python", ["python", "standard-library", "core"]),
    ("security", ["security", "zero-trust", "ciso"]),
    ("cloud", ["cloud", "infrastructure", "kubernetes"]),
    ("ai", ["ai", "machine-learning", "attention"]),
    ("database", ["database", "sqlite", "relational"]),
]

@pytest.mark.parametrize("search_tag, node_tags", TAG_TEST_DATA)
def test_knowledge_graph_tag_matching_matrix(search_tag, node_tags):
    kg = EnterpriseKnowledgeGraph()
    n = kg.add_knowledge_node(
        category=KnowledgeCategory.LIBRARY,
        title=f"Node tagged {search_tag}",
        content=f"Content for {search_tag}",
        company_id="COMP-A",
        author="Agent",
        tags=node_tags,
    )
    results = kg.search(search_tag)
    matched_ids = [node.node_id for node, score in results]
    assert n.node_id in matched_ids


# =============================================================================
# 5. Shared Services Subsystem Matrix (8 Subsystems)
# =============================================================================

@pytest.mark.parametrize("service_name", [
    "artifacts", "models", "prompts", "packages", "licenses", "monitoring", "logging", "notifications"
])
def test_shared_services_subsystems_mounted(service_name):
    services = EnterpriseSharedServices()
    assert hasattr(services, service_name)
    sub = getattr(services, service_name)
    assert sub is not None


# =============================================================================
# 6. Policy Engine Severity Propagation Matrix
# =============================================================================

@pytest.mark.parametrize("severity", ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
def test_policy_severity_levels(severity):
    pe = EnterprisePolicyEngine()
    pe.register_rule(
        name=f"Rule {severity}",
        domain=PolicyDomain.SECURITY,
        scope=PolicyScope.ENTERPRISE,
        condition=lambda ctx: True,
        action=PolicyAction.DENY,
        severity=severity,
    )
    res = pe.evaluate(PolicyDomain.SECURITY, {})
    assert not res.is_compliant
    assert f"[{severity}]" in res.violations[0]


# =============================================================================
# 7. Portfolio ROI Calculation Matrix
# =============================================================================

ROI_TEST_CASES = [
    (100000.0, 2.0, 200000.0),
    (250000.0, 3.5, 875000.0),
    (500000.0, 1.2, 600000.0),
    (1000000.0, 4.0, 4000000.0),
]

@pytest.mark.parametrize("budget, roi, expected_return", ROI_TEST_CASES)
def test_portfolio_roi_return_calculations(budget, roi, expected_return):
    pm = PortfolioManager()
    proj = pm.create_project("ROI Test Project", "COMP-A", budget_usd=budget, estimated_roi=roi)
    assert proj.allocated_budget_usd == budget
    assert proj.estimated_roi == roi
    dash = pm.get_portfolio_dashboard()
    assert dash["expected_portfolio_return_usd"] == expected_return


# =============================================================================
# 8. Scheduler CPM Slack Values Matrix
# =============================================================================

SLACK_CASES = [
    (5.0, 10.0, 5.0),
    (12.0, 20.0, 8.0),
    (15.0, 15.0, 0.0),
]

@pytest.mark.parametrize("t1_dur, t2_dur, expected_slack", SLACK_CASES)
def test_scheduler_slack_calculations(t1_dur, t2_dur, expected_slack):
    sched = CrossCompanyScheduler()
    # Branch 1: T1
    sched.add_task("T1", "COMP-A", "Task 1", t1_dur)
    # Branch 2: T2
    sched.add_task("T2", "COMP-B", "Task 2", t2_dur)
    # End merges both
    sched.add_task("END", "COMP-C", "End", 1.0, dependencies=["T1", "T2"])

    sched.compute_critical_path()
    assert sched._tasks["T1"].slack == expected_slack
    assert sched._tasks["T2"].slack == 0.0  # T2 is on critical path (longer duration)


# =============================================================================
# 9. Priority Queue Reordering Matrix
# =============================================================================

@pytest.mark.parametrize("priorities", [
    [FederationMessagePriority.LOW, FederationMessagePriority.CRITICAL],
    [FederationMessagePriority.NORMAL, FederationMessagePriority.EMERGENCY],
    [FederationMessagePriority.LOW, FederationMessagePriority.NORMAL, FederationMessagePriority.HIGH],
])
def test_priority_inbox_reordering(priorities):
    bus = InterCompanyBus()
    bus.register_company("RECEIVER")

    for p in priorities:
        bus.send_message(FederationMessage(
            company_id="SENDER",
            target_company_id="RECEIVER",
            priority=p,
            payload={"p": p.value},
        ))

    inbox = bus.get_company_messages("RECEIVER")
    assert len(inbox) == len(priorities)
    # Verify strict descending sort by priority rank
    rank_map = {
        FederationMessagePriority.LOW: 1,
        FederationMessagePriority.NORMAL: 2,
        FederationMessagePriority.HIGH: 3,
        FederationMessagePriority.CRITICAL: 4,
        FederationMessagePriority.EMERGENCY: 5,
    }
    for i in range(len(inbox) - 1):
        assert rank_map[inbox[i].priority] >= rank_map[inbox[i + 1].priority]
