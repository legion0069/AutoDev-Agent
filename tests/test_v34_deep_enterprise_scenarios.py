"""
test_v34_deep_enterprise_scenarios.py - AutoDev Version 3.4
Enterprise lifecycle, real-world corporate scenarios, and end-to-end integration tests:
- Feature intake to release train
- Security vulnerability remediation & release blocking
- Resource starvation & automated workload rebalancing
- Architectural divergence & ADR enforcement
- Blameless incident postmortem & SLA restoration
- Financial budget reallocation & variance audits
- Regulatory compliance certification & audit proof
- Customer feedback loop & CSAT roadmap generation
"""

from pathlib import Path
import pytest
import time
from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType
from core.conflict_resolver import ConflictResolver, ConflictType
from core.decision_engine import DecisionDomain, DecisionEngine
from core.department import Department, DepartmentAuthorityLevel, DepartmentRole
from core.meeting_manager import MeetingManager, MeetingType
from core.organization import EnterpriseOrganization
from core.organization_metrics import OrganizationMetricsCalculator
from core.organization_state import OrganizationState
from agents.ceo_agent import CEOAgent
from agents.cto_agent import CTOAgent
from agents.security_manager import SecurityManagerAgent
from agents.qa_manager import QAManagerAgent
from agents.devops_manager import DevOpsManagerAgent
from agents.release_manager import ReleaseManagerAgent
from agents.finance_manager import FinanceManagerAgent
from agents.compliance_manager import ComplianceManagerAgent
from agents.operations_manager import OperationsManagerAgent


@pytest.fixture
def enterprise_org(tmp_path: Path):
    return EnterpriseOrganization(
        company_name="Apex Software Technologies",
        storage_dir=tmp_path / "enterprise_scenarios",
        initial_budget_usd=1000000.0,
        auto_persist=False,
    )


# Scenario 1: Security finding blocks release until remediation verified
def test_scenario_security_blocks_release(enterprise_org: EnterpriseOrganization):
    sec = enterprise_org.get_agent("Security")
    rel = enterprise_org.get_agent("ReleaseManager")

    # Security audits code containing dangerous eval()
    audit_res = sec.audit_code_security(["result = eval(untrusted_payload)"])
    assert audit_res["security_gate_status"] == "BLOCKED"
    assert audit_res["vulnerabilities_found"] == 1

    # Release manager evaluates readiness -> must be NO_GO
    readiness = rel.evaluate_release_readiness(
        qa_gate_passed=True,
        security_score=audit_res["security_score"],
        docs_complete=True,
    )
    assert readiness["decision"] == "NO_GO"

    # Remediation applied: remove eval()
    clean_audit = sec.audit_code_security(["result = json.loads(untrusted_payload)"])
    assert clean_audit["security_gate_status"] == "APPROVED"

    # Now release is approved -> GO
    readiness_post = rel.evaluate_release_readiness(
        qa_gate_passed=True,
        security_score=clean_audit["security_score"],
        docs_complete=True,
    )
    assert readiness_post["decision"] == "GO"


# Scenario 2: Resource starvation triggers workload rebalancing
def test_scenario_workload_rebalancing(enterprise_org: EnterpriseOrganization):
    em = enterprise_org.get_agent("EngineeringManager")
    be = enterprise_org.get_department("Backend")
    fe = enterprise_org.get_department("Frontend")

    # Backend capacity is 20; fill it with 22 tasks -> overload!
    for i in range(22):
        be.assign_task(f"T-BE-{i}", f"Task {i}", "Desc", "EM")

    reports = {
        "Backend": be.get_status_report(),
        "Frontend": fe.get_status_report(),
    }
    balance = em.balance_workloads(reports)
    assert "Backend" in balance["overloaded_teams"]
    assert len(balance["rebalance_actions"]) > 0


# Scenario 3: Architectural dispute escalated to CTO
def test_scenario_architecture_dispute_resolved_by_cto(enterprise_org: EnterpriseOrganization):
    cto = enterprise_org.get_agent("CTO")
    dispute = cto.adjudicate_technical_dispute(
        dispute_topic="State Store",
        proposal_a={"name": "In-Memory Dictionary with Mutex", "testability_score": 95.0, "external_deps": []},
        proposal_b={"name": "Redis External Cluster", "testability_score": 75.0, "external_deps": ["RedisLib"]},
    )
    assert dispute["winning_proposal"] == "Proposal A"
    assert "In-Memory" in dispute["details"]["name"]


# Scenario 4: Production SEV-1 Incident triage to blameless postmortem
def test_scenario_incident_to_postmortem(enterprise_org: EnterpriseOrganization):
    ops = enterprise_org.get_agent("Operations")

    # 1. Incident triggered
    inc = ops.handle_incident(
        incident_title="Memory leak in worker pool",
        severity="SEV-1",
        affected_service="WorkerFleet",
        root_cause_hypothesis="Circular references in task objects",
    )
    assert inc["status"] == "TRIAGED"
    assert len(ops.active_incidents) == 1

    # 2. Postmortem conducted
    pm = ops.conduct_postmortem(
        incident_id=inc["incident_id"],
        timeline=["Detection: 00:00", "Mitigated: 00:05", "Resolved: 00:15"],
        root_cause="Circular references preventing garbage collection",
        preventive_actions=["Break reference cycle via weakref", "Add automated memory regression test"],
    )
    assert len(pm["five_whys"]) == 5
    assert len(ops.active_incidents) == 0


# Scenario 5: Financial budget variance audit
def test_scenario_financial_budget_variance(enterprise_org: EnterpriseOrganization):
    fin = enterprise_org.get_agent("Finance")

    dept_reports = {
        "Backend": {"budget_spent": 35000.0},
        "Frontend": {"budget_spent": 20000.0},
        "QA": {"budget_spent": 15000.0},
    }
    burn = fin.calculate_monthly_burn(dept_reports)
    assert burn["total_monthly_burn_usd"] == 70000.0

    rep = fin.generate_financial_report(total_spent=70000.0, total_budget=100000.0)
    assert rep["financial_health"] == "ON_BUDGET"
    assert rep["remaining_budget_usd"] == 30000.0


# Scenario 6: Regulatory compliance certification
def test_scenario_compliance_certification(enterprise_org: EnterpriseOrganization):
    comp = enterprise_org.get_agent("Compliance")

    audit = comp.audit_compliance({"data_retention_policy_active": True})
    assert audit["compliant"] is True

    cert = comp.generate_compliance_certificate()
    assert cert["status"] == "ATTESTED"
    assert "SOC2_TYPE_II" in cert["frameworks"]


# Scenario 7: Customer feedback loop into product backlog
def test_scenario_customer_feedback_loop(enterprise_org: EnterpriseOrganization):
    cf = enterprise_org.get_agent("CustomerFeedback")
    pm = enterprise_org.get_agent("ProductManager")

    cf.ingest_feedback({"csat_score": 90.0, "feedback": "Fast API response"})
    cf.ingest_feedback({"csat_score": 70.0, "feedback": "Add batch upload capability"})

    recs = cf.export_recommendations_to_pm()
    assert len(recs["top_pain_points"]) >= 1

    features = [
        {"title": "Batch Upload Feature", "reach": 15.0, "impact": 4.0, "confidence": 0.85, "effort_days": 3.0},
    ]
    ranked = pm.prioritize_backlog(features)
    assert ranked[0]["title"] == "Batch Upload Feature"


# Scenario 8: High-frequency message thread interaction
def test_scenario_multi_message_thread_flow(enterprise_org: EnterpriseOrganization):
    bus = enterprise_org.bus

    thread_id = "THREAD-COLLAB-99"
    m1 = OrgMessage(sender="BA", receiver="PM", thread_id=thread_id, payload={"step": "story_ready"})
    m2 = OrgMessage(sender="PM", receiver="Arch", thread_id=thread_id, payload={"step": "design_ready"})
    m3 = OrgMessage(sender="Arch", receiver="Backend", thread_id=thread_id, payload={"step": "adr_ratified"})

    bus.send_message(m1)
    bus.send_message(m2)
    bus.send_message(m3)

    history = bus.get_thread_history(thread_id)
    assert len(history) == 3
    assert [m.payload["step"] for m in history] == ["story_ready", "design_ready", "adr_ratified"]


# Scenario 9: Full meeting cycle with minutes verification
def test_scenario_meeting_cycle(enterprise_org: EnterpriseOrganization):
    standup = enterprise_org.conduct_corporate_meeting(MeetingType.DAILY_STANDUP)
    assert standup["meeting_type"] == "DAILY_STANDUP"
    assert len(standup["decisions_ratified"]) >= 1

    release_mtg = enterprise_org.conduct_corporate_meeting(MeetingType.RELEASE_MEETING)
    assert release_mtg["meeting_type"] == "RELEASE_MEETING"
    assert len(release_mtg["decisions_ratified"]) >= 1


# Scenario 10: Organization metrics dashboard reflection
def test_scenario_metrics_dashboard_reflection(enterprise_org: EnterpriseOrganization):
    dash = enterprise_org.get_organization_dashboard()
    assert dash["architecture_health_score"] >= 80.0
    assert dash["security_score"] >= 90.0
    assert dash["delivery_confidence"] > 0.80
    assert "summary" in dash
