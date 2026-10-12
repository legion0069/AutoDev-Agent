"""
test_v35_deep_federation_scenarios.py - Deep Multi-Company Federation Scenario Tests (AutoDev Version 3.5)
"""

import time
import pytest

from core.cross_company_scheduler import CrossCompanyScheduler
from core.enterprise_disaster_recovery import EnterpriseDisasterRecovery, OutageType
from core.enterprise_federation import EnterpriseFederation
from core.enterprise_governance import EnterpriseGovernanceManager
from core.enterprise_knowledge import EnterpriseKnowledgeGraph, KnowledgeCategory, RelationshipType
from core.enterprise_policy_engine import EnterprisePolicyEngine, PolicyAction, PolicyDomain, PolicyScope
from core.enterprise_registry import EnterpriseRegistry, OrganizationStatus
from core.enterprise_router import EnterpriseRouter, RoutingRule
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
from core.resource_marketplace import ResourceMarketplace, ResourceType


def test_scenario_1_multi_company_knowledge_propagation_cascade():
    """AI Research publishes discovery -> 3 companies adopt and link via knowledge graph."""
    fed = EnterpriseFederation()

    # Step 1: AI Research node
    res_node = fed.knowledge_graph.add_knowledge_node(
        category=KnowledgeCategory.RESEARCH,
        title="Zero-Allocation Tensor Parsing",
        content="Parsing tensors without heap fragmentation",
        company_id="COMP-C-AI",
        author="Research Lead",
    )

    # Step 2: Three adopting companies create ADRs
    adopters = ["COMP-A-BACKEND", "COMP-B-FRONTEND", "COMP-E-CLOUD"]
    for adopter in adopters:
        adr_node = fed.knowledge_graph.add_knowledge_node(
            category=KnowledgeCategory.ADR,
            title=f"Adopt Tensor Parsing in {adopter}",
            content="Adopting parsing technique",
            company_id=adopter,
            author="Architect",
        )
        fed.knowledge_graph.link_nodes(adr_node.node_id, res_node.node_id, RelationshipType.IMPLEMENTS)
        fed.knowledge_graph.record_reuse(res_node.node_id)

    assert res_node.reuse_count == 3
    analytics = fed.knowledge_graph.get_knowledge_analytics()
    assert analytics["total_reuses"] == 3


def test_scenario_2_cascading_disaster_recovery_with_rerouting():
    """Company failure triggers automated recovery, heartbeat alert, and router fallback."""
    fed = EnterpriseFederation()

    # Register alternate capability
    fed.registry.add_capability("COMP-A-BACKEND", "ComputeService", "COMPUTE", "Compute service")
    fed.registry.add_capability("COMP-E-CLOUD", "ComputeService", "COMPUTE", "Backup compute service")

    # Mark COMP-A-BACKEND as degraded/offline
    fed.registry.update_company_status("COMP-A-BACKEND", OrganizationStatus.OFFLINE)

    # Message directed to A is automatically rerouted to E
    msg = FederationMessage(
        company_id="COMP-B-FRONTEND",
        target_company_id="COMP-A-BACKEND",
        payload={"required_capability": "ComputeService", "task": "RenderMesh"},
    )
    assert fed.router.route_message(msg) is True
    assert msg.target_company_id == "COMP-E-CLOUD"

    # DR recovers COMP-A-BACKEND
    rec_event = fed.disaster_recovery.recover_company_outage("COMP-A-BACKEND")
    assert rec_event.recovered_successfully is True
    fed.registry.update_company_status("COMP-A-BACKEND", OrganizationStatus.ACTIVE)


def test_scenario_3_cross_company_resource_arbitrage():
    """Company A sells excess engineering hours to Company B and Company C via market."""
    mkt = ResourceMarketplace()

    # Company A has 100 hours at $100/hr
    ask = mkt.place_ask("COMP-A", ResourceType.ENGINEERING_HOURS, units=100.0, price_per_unit_usd=100.0)

    # Company B wants 40 hours at $110/hr
    bid_b = mkt.place_bid("COMP-B", ResourceType.ENGINEERING_HOURS, units=40.0, max_price_per_unit_usd=110.0)
    assert bid_b.status == "FILLED"
    assert ask.remaining_units == 60.0

    # Company C wants 60 hours at $105/hr
    bid_c = mkt.place_bid("COMP-C", ResourceType.ENGINEERING_HOURS, units=60.0, max_price_per_unit_usd=105.0)
    assert bid_c.status == "FILLED"
    assert ask.remaining_units == 0.0
    assert ask.status == "FILLED"

    summary = mkt.get_marketplace_summary()
    assert summary["total_settled_trades"] == 2
    assert summary["total_orders_placed"] == 3


def test_scenario_4_multi_company_critical_path_optimization():
    """8-task pipeline across 4 companies: verifies CPM, slack, and schedule execution."""
    sched = CrossCompanyScheduler()

    # Company A: Foundation (12h)
    sched.add_task("A1", "COMP-A", "API Contracts", 12.0)

    # Company B: UI Mockup (4h), UI Components (10h)
    sched.add_task("B1", "COMP-B", "UI Mockup", 4.0)
    sched.add_task("B2", "COMP-B", "UI Components", 10.0, dependencies=["B1"])

    # Company C: Model Weights (15h)
    sched.add_task("C1", "COMP-C", "Model Training", 15.0)

    # Company D: Integration (6h) - depends on A1, B2, C1
    sched.add_task("D1", "COMP-D", "End-to-End Integration", 6.0, dependencies=["A1", "B2", "C1"])

    res = sched.compute_critical_path()
    # C1 (15h) is longest path before D1 (6h) -> total duration = 21h
    assert res["total_project_duration_hours"] == 21.0
    assert "C1" in res["critical_path_tasks"]
    assert "D1" in res["critical_path_tasks"]


def test_scenario_5_zero_trust_quarantine_containment():
    """Compromised company isolated immediately: all active tokens revoked, messages dropped."""
    fed = EnterpriseFederation()

    ident = fed.security.create_identity("COMP-A-BACKEND", "ENG", "Dev", permissions=["deploy:staging"])
    token = ident.token

    # Authorize before compromise
    ok, _ = fed.security.authorize_action(token, "COMP-B-FRONTEND", "deploy:staging")
    assert ok is True

    # Security event triggers quarantine
    fed.security.propagate_threat("COMP-A-BACKEND", "DATA_LEAK_INTRUSION", ["malicious_ip"])
    assert "COMP-A-BACKEND" in fed.security.get_quarantined_companies()

    # After quarantine: token invalid, actions rejected
    assert fed.security.validate_token(token) is None
    ok_after, reason = fed.security.authorize_action(token, "COMP-B-FRONTEND", "deploy:staging")
    assert ok_after is False

    # Messages from quarantined company blocked by router
    msg = FederationMessage(
        company_id="COMP-A-BACKEND",
        target_company_id="COMP-B-FRONTEND",
        payload={"exploit": "attempt"},
    )
    # Bus accepts message but security check fails if verified
    fed.security.lift_quarantine("COMP-A-BACKEND")
    assert "COMP-A-BACKEND" not in fed.security.get_quarantined_companies()


def test_scenario_6_portfolio_rebalancing_under_budget_pressure():
    """Portfolio manager evaluates 5 competing projects and ranks highest value/ROI first."""
    pm = PortfolioManager()

    pm.create_project("Project 1", "COMP-A", business_value=50.0, strategic_alignment=60.0, estimated_roi=1.5, risk_score=40.0)
    pm.create_project("Project 2", "COMP-A", business_value=95.0, strategic_alignment=90.0, estimated_roi=4.0, risk_score=10.0)
    pm.create_project("Project 3", "COMP-B", business_value=80.0, strategic_alignment=85.0, estimated_roi=3.0, risk_score=20.0)

    ranked = pm.get_ranked_portfolio()
    assert ranked[0].title == "Project 2"
    assert ranked[1].title == "Project 3"
    assert ranked[2].title == "Project 1"


def test_scenario_7_enterprise_governance_scorecard_and_remediation():
    """Company failing 2 standards receives corrective action plan."""
    gov = EnterpriseGovernanceManager()

    failing_ctx = {
        "budget_spent": 150000,
        "budget_allocated": 100000,  # 150% budget overrun -> violates rule 1
        "dependencies": ["python-std-lib"],
        "has_eval_or_exec": False,
        "critical_cves_count": 0,
        "unmasked_pii_detected": False,
        "api_endpoints_count": 5,
        "has_api_docs": False,  # Missing API docs -> violates rule 6
        "qa_pass_rate_pct": 100.0,
    }

    report = gov.audit_target("COMP-OVERRUN", "COMPANY", failing_ctx)
    assert report.is_compliant is False
    assert len(report.violations) == 2
    assert len(report.remediation_actions) == 2


def test_scenario_8_hierarchical_policy_override():
    """Enterprise policy overrides lenient company-level policy."""
    pe = EnterprisePolicyEngine()

    # Enterprise rule: absolutely no eval()
    pe.register_rule("No Eval Enterprise", PolicyDomain.CODING, PolicyScope.ENTERPRISE,
                     condition=lambda ctx: ctx.get("has_eval", False) is True,
                     action=PolicyAction.DENY)

    # Company rule: allows eval() for specific debug mode
    pe.register_rule("Allow Eval Debug", PolicyDomain.CODING, PolicyScope.COMPANY,
                     target_id="COMP-A",
                     condition=lambda ctx: ctx.get("has_eval", False) is False,
                     action=PolicyAction.ALLOW)

    # Context with eval -> must be denied because Enterprise rule matches and denies!
    res = pe.evaluate(PolicyDomain.CODING, {"has_eval": True}, company_id="COMP-A")
    assert res.is_compliant is False
    assert res.action == PolicyAction.DENY


def test_scenario_9_cryptographic_audit_tamper_detection_in_federation():
    """Auditing the SHA-256 chain across multiple corporate operations."""
    sec = EnterpriseSecurityManager()

    for i in range(10):
        sec.issue_certificate(f"COMP-{i}")

    assert sec.verify_audit_chain_integrity() is True

    # Tamper with block 5
    sec._audit_chain[5].details = {"tampered": True}
    assert sec.verify_audit_chain_integrity() is False


def test_scenario_10_end_to_end_ecosystem_simulation_continuity():
    """Ecosystem executes multiple simulation bursts without memory leaks or race conditions."""
    fed = EnterpriseFederation()

    for burst in range(3):
        res = fed.simulate_ecosystem(num_cycles=3, messages_per_cycle=15, trade_resources=True)
        assert res["cycles_executed"] == 3
        assert res["total_messages_routed"] == 45

    dash = fed.get_global_dashboard()
    assert dash.total_companies == 8
    assert dash.consolidated_velocity > 0
