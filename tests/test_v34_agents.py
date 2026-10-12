"""
test_v34_agents.py - AutoDev Version 3.4
Comprehensive unit test suite for the 17 specialized AI agents:
1. CEOAgent
2. CTOAgent
3. EngineeringManagerAgent
4. ArchitectAgent
5. BackendTeamAgent
6. FrontendTeamAgent
7. QAManagerAgent
8. SecurityManagerAgent
9. DevOpsManagerAgent
10. ReleaseManagerAgent
11. ProductManagerAgent
12. BusinessAnalystAgent
13. DocumentationManagerAgent
14. CustomerFeedbackManagerAgent
15. FinanceManagerAgent
16. ComplianceManagerAgent
17. OperationsManagerAgent
"""

from pathlib import Path
import pytest
from core.communication_bus import CommunicationBus
from core.organization_state import OrganizationState
from agents.ceo_agent import CEOAgent
from agents.cto_agent import CTOAgent
from agents.engineering_manager import EngineeringManagerAgent
from agents.architect_agent import ArchitectAgent
from agents.backend_team import BackendTeamAgent
from agents.frontend_team import FrontendTeamAgent
from agents.qa_manager import QAManagerAgent
from agents.security_manager import SecurityManagerAgent
from agents.devops_manager import DevOpsManagerAgent
from agents.release_manager import ReleaseManagerAgent
from agents.product_manager import ProductManagerAgent
from agents.business_analyst import BusinessAnalystAgent
from agents.documentation_manager import DocumentationManagerAgent
from agents.customer_feedback_manager import CustomerFeedbackManagerAgent
from agents.finance_manager import FinanceManagerAgent
from agents.compliance_manager import ComplianceManagerAgent
from agents.operations_manager import OperationsManagerAgent


@pytest.fixture
def bus_and_state(tmp_path: Path):
    bus = CommunicationBus()
    state = OrganizationState(storage_dir=tmp_path / "agents_test", auto_persist=True)
    return bus, state


# 1. CEO Agent Tests
def test_ceo_agent(bus_and_state):
    bus, state = bus_and_state
    ceo = CEOAgent(bus=bus, state=state)

    alignment = ceo.evaluate_strategic_alignment({"title": "AI Payments", "estimated_roi": 3.5})
    assert alignment["strategic_alignment"] is True

    bad_align = ceo.evaluate_strategic_alignment({"title": "Unfunded Research", "estimated_roi": 0.8})
    assert bad_align["strategic_alignment"] is False

    ok, msg = ceo.approve_budget(50000.0, "Backend")
    assert ok is True
    assert "approved $50,000.00" in msg.lower()

    # Exceeding executive cap
    ok_over, msg_over = ceo.approve_budget(500000.0, "Backend")
    assert ok_over is False

    esc = ceo.handle_escalation({"escalation_title": "Vendor dispute", "escalating_department": "Finance"})
    assert esc["status"] == "RESOLVED_BY_CEO"

    review = ceo.conduct_executive_review({"delivery_confidence": 0.96})
    assert review["executive_assessment"] == "HEALTHY"


# 2. CTO Agent Tests
def test_cto_agent(bus_and_state):
    bus, state = bus_and_state
    cto = CTOAgent(bus=bus, state=state)

    # Valid stack
    valid_res = cto.validate_technology_stack(["Python Standard Library", "SQLite"])
    assert valid_res["approved"] is True

    # Prohibited stack
    invalid_res = cto.validate_technology_stack(["LangGraph", "Celery", "Redis"])
    assert invalid_res["approved"] is False
    assert len(invalid_res["violations"]) == 3

    arch_res = cto.evaluate_architecture_proposal({"title": "Hexagonal Service", "decoupling_score": 95.0})
    assert arch_res["approved"] is True

    debt_res = cto.audit_technical_debt({"debt_items_count": 5, "estimated_hours": 45.0})
    assert debt_res["debt_level"] == "CRITICAL"

    dispute = cto.adjudicate_technical_dispute(
        "Protocol Choice",
        {"name": "Standard HTTP", "testability_score": 90.0, "external_deps": []},
        {"name": "Custom External Transport", "testability_score": 80.0, "external_deps": ["ExtLib"]},
    )
    assert dispute["winning_proposal"] == "Proposal A"


# 3. Engineering Manager Agent Tests
def test_engineering_manager_agent(bus_and_state):
    bus, state = bus_and_state
    em = EngineeringManagerAgent(bus=bus, state=state)

    alloc = em.plan_sprint_allocation(
        user_stories=["US-1 Payment Gateway", "US-2 Audit Trail"],
        available_teams=["Backend", "Frontend", "QA"],
    )
    assert alloc["total_tasks_count"] >= 4
    assert alloc["team_capacity_healthy"] is True

    reports = {
        "Backend": {"utilization_rate": 1.2},
        "Frontend": {"utilization_rate": 0.3},
    }
    balance = em.balance_workloads(reports)
    assert len(balance["overloaded_teams"]) == 1
    assert len(balance["underutilized_teams"]) == 1

    unblock = em.unblock_task("TASK-01", "Missing auth token", "Generated mock token")
    assert unblock["status"] == "UNBLOCKED"


# 4. Architect Agent Tests
def test_architect_agent(bus_and_state):
    bus, state = bus_and_state
    arch = ArchitectAgent(bus=bus, state=state)

    sys_design = arch.design_system("High throughput event streaming payment ledger")
    assert "Repository Pattern" in sys_design["recommended_patterns"]
    assert "Transactional Outbox" in sys_design["recommended_patterns"]
    assert "core/domain" in sys_design["folder_structure"]

    adr = arch.generate_adr("Strict Layering", "Need modular decoupling", "Adopt DDD", "Clean separation")
    assert adr["status"] == "ACCEPTED"

    # Cycle check
    clean_graph = {"A": ["B"], "B": ["C"], "C": []}
    assert arch.validate_component_boundaries(clean_graph)["is_clean"] is True

    cyclic_graph = {"A": ["B"], "B": ["C"], "C": ["A"]}
    assert arch.validate_component_boundaries(cyclic_graph)["is_clean"] is False


# 5. Backend Team Agent Tests
def test_backend_team_agent(bus_and_state):
    bus, state = bus_and_state
    be = BackendTeamAgent(bus=bus, state=state)

    ep = be.develop_endpoint({"path": "/v1/orders", "methods": ["POST"]})
    assert ep["status"] == "DEVELOPMENT_COMPLETE"
    assert "POST /v1/orders" in be.endpoints_implemented

    model = be.create_domain_model("UserEntity", {"id": "str", "email": "str"})
    assert model["status"] == "MODEL_GENERATED"
    assert "UserEntity" in model["model_code"]

    rev_bad = be.review_backend_code("cursor.execute('SELECT * FROM users WHERE id = %s' % user_id)")
    assert rev_bad["clean"] is False

    rev_good = be.review_backend_code("cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))")
    assert rev_good["clean"] is True


# 6. Frontend Team Agent Tests
def test_frontend_team_agent(bus_and_state):
    bus, state = bus_and_state
    fe = FrontendTeamAgent(bus=bus, state=state)

    comp = fe.develop_component({"name": "LedgerTable", "props": ["items", "onSelect"]})
    assert comp["status"] == "UI_DEVELOPMENT_COMPLETE"
    assert "LedgerTable" in fe.components_created

    acc_good = fe.develop_component({"name": "Button", "props": []})
    assert fe.validate_accessibility("<img src='x.png' alt='logo'>")["compliant"] is True
    assert fe.validate_accessibility("<img src='x.png'>")["compliant"] is False


# 7. QA Manager Agent Tests
def test_qa_manager_agent(bus_and_state):
    bus, state = bus_and_state
    qa = QAManagerAgent(bus=bus, state=state)

    plan = qa.generate_test_plan({"name": "Payments", "user_stories": ["US-1 Checkout", "US-2 Refund"]})
    assert plan["total_cases_planned"] == 6

    gate_pass = qa.evaluate_quality_gate({"passed": 20, "failed": 0}, coverage_pct=95.0)
    assert gate_pass["quality_gate_status"] == "PASSED"

    gate_fail = qa.evaluate_quality_gate({"passed": 20, "failed": 1}, coverage_pct=95.0)
    assert gate_fail["quality_gate_status"] == "REJECTED"

    matrix = qa.build_risk_matrix(["Payment Processing", "UI Colors", "Report Export"])
    assert "Payment Processing" in matrix["CRITICAL_RISK"]
    assert "UI Colors" in matrix["LOW_RISK"]


# 8. Security Manager Agent Tests
def test_security_manager_agent(bus_and_state):
    bus, state = bus_and_state
    sec = SecurityManagerAgent(bus=bus, state=state)

    audit_bad = sec.audit_code_security(["result = eval(user_input)"])
    assert audit_bad["vulnerabilities_found"] == 1
    assert audit_bad["security_gate_status"] == "BLOCKED"

    audit_good = sec.audit_code_security(["result = int(user_input)"])
    assert audit_good["vulnerabilities_found"] == 0
    assert audit_good["security_gate_status"] == "APPROVED"

    deps = sec.scan_dependencies(["vulnerable-legacy-crypto", "json"])
    assert deps["clean"] is False

    score = sec.calculate_security_score(findings_count=1, critical_cves=0)
    assert score == 90.0


# 9. DevOps Manager Agent Tests
def test_devops_manager_agent(bus_and_state):
    bus, state = bus_and_state
    devops = DevOpsManagerAgent(bus=bus, state=state)

    plan = devops.generate_deployment_plan({"service": "PaymentsAPI", "version": "3.4.0"})
    assert plan["status"] == "READY_FOR_DEPLOYMENT"
    assert len(plan["execution_steps"]) == 7

    rollback = devops.generate_rollback_plan(plan)
    assert rollback["rollback_ready"] is True

    env = devops.validate_environment({"env": "production"})
    assert env["status"] == "ENVIRONMENT_HEALTHY"


# 10. Release Manager Agent Tests
def test_release_manager_agent(bus_and_state):
    bus, state = bus_and_state
    rel = ReleaseManagerAgent(bus=bus, state=state)

    approvals = rel.collect_release_approvals({"CEO": True, "CTO": True, "QA": True, "Security": True})
    assert approvals["all_mandatory_approvals_gathered"] is True
    assert approvals["status"] == "APPROVED_FOR_RELEASE"

    readiness = rel.evaluate_release_readiness(qa_gate_passed=True, security_score=95.0, docs_complete=True)
    assert readiness["decision"] == "GO"

    rel_record = rel.execute_release("3.4.0", ["Enterprise Organization Engine"])
    assert rel_record["release_status"] == "DEPLOYED_TO_PRODUCTION"


# 11. Product Manager Agent Tests
def test_product_manager_agent(bus_and_state):
    bus, state = bus_and_state
    pm = ProductManagerAgent(bus=bus, state=state)

    features = [
        {"title": "Feature Low", "reach": 5.0, "impact": 1.0, "confidence": 0.5, "effort_days": 5.0},
        {"title": "Feature High", "reach": 10.0, "impact": 5.0, "confidence": 0.9, "effort_days": 2.0},
    ]
    ranked = pm.prioritize_backlog(features)
    assert ranked[0]["title"] == "Feature High"
    assert ranked[0]["customer_value_score"] > ranked[1]["customer_value_score"]

    goal = pm.define_sprint_goal(["Payment API", "Audit Ledger"])
    assert "Payment API" in goal["sprint_goal"]

    roadmap = pm.update_roadmap("Q4-2026", [{"title": "Milestone A"}])
    assert roadmap["status"] == "ROADMAP_UPDATED"


# 12. Business Analyst Agent Tests
def test_business_analyst_agent(bus_and_state):
    bus, state = bus_and_state
    ba = BusinessAnalystAgent(bus=bus, state=state)

    analysis = ba.analyze_customer_request("Build an automated transaction ledger with webhook notifications.")
    assert "Epic:" in analysis["epic"]
    assert len(analysis["user_stories"]) >= 3
    assert len(analysis["acceptance_criteria"]) >= 2
    assert analysis["estimated_roi"] >= 2.0

    roi = ba.calculate_roi(development_cost_usd=10000.0, estimated_benefit_usd=40000.0)
    assert roi == 4.0


# 13. Documentation Manager Agent Tests
def test_documentation_manager_agent(bus_and_state):
    bus, state = bus_and_state
    doc = DocumentationManagerAgent(bus=bus, state=state)

    api_docs = doc.generate_api_documentation(["POST /v1/orders", "GET /v1/orders"])
    assert api_docs["status"] == "DOCS_GENERATED"
    assert api_docs["endpoints_documented"] == 2

    runbook = doc.generate_runbook("PaymentService")
    assert "Operational Runbook: PaymentService" in runbook

    cl = doc.update_changelog("3.4.0", ["Added Autonomous AI Organization"])
    assert "[3.4.0]" in cl


# 14. Customer Feedback Manager Agent Tests
def test_customer_feedback_manager_agent(bus_and_state):
    bus, state = bus_and_state
    cf = CustomerFeedbackManagerAgent(bus=bus, state=state)

    cf.ingest_feedback({"csat_score": 95.0, "feedback": "Fast and smooth"})
    cf.ingest_feedback({"csat_score": 60.0, "feedback": "Error 500 when payload is empty"})

    csat = cf.analyze_csat()
    assert csat == 77.5

    pains = cf.identify_pain_points()
    assert len(pains) == 1
    assert "Error 500" in pains[0]

    recs = cf.export_recommendations_to_pm()
    assert recs["total_feedback_count"] == 2


# 15. Finance Manager Agent Tests
def test_finance_manager_agent(bus_and_state):
    bus, state = bus_and_state
    fin = FinanceManagerAgent(bus=bus, state=state)

    cost = fin.estimate_project_cost(engineer_hours=20.0, tokens_consumed=1_000_000)
    assert cost["developer_labor_cost_usd"] == 1300.0
    assert cost["ai_token_cost_usd"] == 2.50
    assert cost["total_estimated_cost_usd"] > 1300.0

    burn = fin.calculate_monthly_burn({"Backend": {"budget_spent": 12000.0}, "Frontend": {"budget_spent": 8000.0}})
    assert burn["total_monthly_burn_usd"] == 20000.0

    rep = fin.generate_financial_report(total_spent=50000.0, total_budget=100000.0)
    assert rep["financial_health"] == "ON_BUDGET"
    assert rep["remaining_budget_usd"] == 50000.0


# 16. Compliance Manager Agent Tests
def test_compliance_manager_agent(bus_and_state):
    bus, state = bus_and_state
    comp = ComplianceManagerAgent(bus=bus, state=state)

    audit = comp.audit_compliance({"data_retention_policy_active": True})
    assert audit["compliant"] is True
    assert audit["compliance_score"] == 100.0

    cert = comp.generate_compliance_certificate()
    assert cert["status"] == "ATTESTED"


# 17. Operations Manager Agent Tests
def test_operations_manager_agent(bus_and_state):
    bus, state = bus_and_state
    ops = OperationsManagerAgent(bus=bus, state=state)

    sla = ops.monitor_slas({"uptime_pct": 99.99, "latency_p95_ms": 35.0})
    assert sla["sla_met"] is True
    assert sla["sla_status"] == "COMPLIANT"

    inc = ops.handle_incident("Memory leak in worker loop", severity="SEV-2")
    assert inc["status"] == "TRIAGED"
    assert len(ops.active_incidents) == 1

    pm = ops.conduct_postmortem(inc["incident_id"], root_cause="Unbounded queue buffer")
    assert len(pm["five_whys"]) == 5
    assert len(ops.active_incidents) == 0  # Resolved and removed
