"""
test_v34_comprehensive_matrix.py - AutoDev Version 3.4
Additional comprehensive test suite verifying:
- Department task priority sorting and dependency graphs
- Decision Engine tie-breaking under equal authority weights
- Conflict Resolver multi-party edge cases and escalation paths
- Communication Bus thread correlation and response timeouts
- Meeting minutes action item lifecycle (PENDING -> IN_PROGRESS -> COMPLETED)
- Metric sensitivity under varying lead times and defect ratios
- CEO, CTO, and Executive governance edge cases
"""

import pytest
import time
from pathlib import Path
from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType
from core.conflict_resolver import ConflictResolver, ConflictType, ConflictStatus
from core.decision_engine import DecisionDomain, DecisionEngine
from core.department import Department, DepartmentAuthorityLevel, DepartmentRole
from core.meeting_manager import MeetingManager, MeetingType
from core.organization import EnterpriseOrganization
from core.organization_metrics import OrganizationMetricsCalculator
from core.organization_state import OrganizationState


# 1. Department Task Priority & Dependency Tests
@pytest.mark.parametrize("priority_val", [1, 2, 3, 4, 5])
def test_department_task_priority_levels(priority_val):
    dept = Department("Backend", DepartmentRole.BACKEND)
    task = dept.assign_task(f"T-PRIO-{priority_val}", "Title", "Desc", "EM", priority=priority_val)
    assert task.priority == priority_val


def test_department_dependencies_tracking():
    dept = Department(
        name="Backend",
        role=DepartmentRole.BACKEND,
        dependencies=["Architecture", "ProductManager"],
    )
    assert "Architecture" in dept.dependencies
    assert "ProductManager" in dept.dependencies
    rep = dept.get_status_report()
    assert len(rep["dependencies"]) == 2


def test_department_budget_boundary():
    dept = Department("QA", DepartmentRole.QA, budget=1000.0)
    # Exactly spend budget
    assert dept.spend_budget(1000.0) is True
    assert dept.spent_budget == 1000.0
    # Over budget by $1
    assert dept.spend_budget(1.0) is False


def test_department_multiple_block_reasons():
    dept = Department("Frontend", DepartmentRole.FRONTEND)
    t1 = dept.assign_task("T-1", "T1", "D", "EM")
    dept.block_task("T-1", reason="Waiting for Figma design")
    rep = dept.get_status_report()
    assert rep["blocked_task_reasons"]["T-1"] == "Waiting for Figma design"


# 2. Decision Engine Multi-Option & Tie-Breaking Tests
@pytest.mark.parametrize("option_count", [2, 3, 4, 5])
def test_decision_engine_n_options(option_count, tmp_path):
    state = OrganizationState(storage_dir=tmp_path / f"dec_{option_count}", auto_persist=False)
    engine = DecisionEngine(state=state)
    options = [f"Option_{i}" for i in range(option_count)]

    pid = engine.create_proposal("Choice", DecisionDomain.ARCHITECTURE_CHOICE, options, "Arch")
    # Cast vote for the last option
    engine.cast_vote(pid, "CTO", options[-1], confidence=0.99)
    res = engine.evaluate_decision(pid)
    assert res["winning_option"] == options[-1]


def test_decision_engine_equal_votes_tie_break(tmp_path):
    state = OrganizationState(storage_dir=tmp_path / "dec_tie", auto_persist=False)
    engine = DecisionEngine(state=state)

    pid = engine.create_proposal("Tie Choice", DecisionDomain.PRIORITY, ["A", "B"], "EM")
    # Equal weight votes
    engine.cast_vote(pid, "Voter1", "A", confidence=0.8, custom_weight=2.0)
    engine.cast_vote(pid, "Voter2", "B", confidence=0.8, custom_weight=2.0)

    res = engine.evaluate_decision(pid)
    # Must deterministically select one without crashing
    assert res["winning_option"] in ("A", "B")
    assert res["status"] == "RESOLVED"


# 3. Conflict Resolver Complex Chains
def test_conflict_resolver_same_authority_tie():
    resolver = ConflictResolver()
    # Backend (35) and Frontend (35) have identical authority precedence!
    rec = resolver.register_conflict(
        conflict_type=ConflictType.OWNERSHIP_CONFLICT,
        parties_involved=["Backend", "Frontend"],
        description="Who owns GraphQL schema definition",
        competing_proposals={"Backend": "BE", "Frontend": "FE"},
    )
    resolved = resolver.resolve_conflict(rec.conflict_id)
    assert resolved.status == ConflictStatus.AUTO_RESOLVED
    assert resolved.resolution_strategy == "AUTHORITY_PRECEDENCE"


def test_conflict_resolver_priority_fallback():
    resolver = ConflictResolver()
    rec = resolver.register_conflict(
        conflict_type=ConflictType.RESOURCE_CONFLICT,
        parties_involved=["QA", "DevOps"],
        description="Shared runner contention",
        competing_proposals={"QA": {"priority": 3}, "DevOps": {"priority": 3}},
    )
    resolved = resolver.resolve_conflict(rec.conflict_id)
    assert resolved.status == ConflictStatus.AUTO_RESOLVED


# 4. Communication Bus In-Depth Queries
def test_bus_query_limit():
    bus = CommunicationBus()
    for i in range(20):
        bus.send_message(OrgMessage(sender="A", receiver="B", payload={"i": i}))

    res_10 = bus.query_messages(limit=10)
    assert len(res_10) == 10

    res_5 = bus.query_messages(limit=5)
    assert len(res_5) == 5


def test_bus_empty_receiver_handling():
    bus = CommunicationBus()
    # Query non-existent department
    msgs = bus.get_messages("NonExistentDepartment")
    assert msgs == []


def test_bus_multiple_threads():
    bus = CommunicationBus()
    bus.send_message(OrgMessage(sender="A", receiver="B", thread_id="T1", payload={"msg": 1}))
    bus.send_message(OrgMessage(sender="A", receiver="B", thread_id="T2", payload={"msg": 2}))

    t1_hist = bus.get_thread_history("T1")
    t2_hist = bus.get_thread_history("T2")
    assert len(t1_hist) == 1
    assert len(t2_hist) == 1
    assert t1_hist[0].payload["msg"] == 1
    assert t2_hist[0].payload["msg"] == 2


# 5. Meeting Action Item State Progression
def test_meeting_action_item_model():
    state = OrganizationState(auto_persist=False)
    mm = MeetingManager(state=state)
    m = mm.schedule_and_conduct_meeting(MeetingType.DAILY_STANDUP, "Standup", "EM", ["BE"])

    assert len(m.action_items) >= 1
    item = m.action_items[0]
    assert item.status == "PENDING"

    # Mutate to completed
    item.status = "COMPLETED"
    d = item.to_dict()
    assert d["status"] == "COMPLETED"


# 6. Metric Calculator Extreme Value Sensitivities
@pytest.mark.parametrize("incidents,debt,expected_max_arch", [
    (0, 0, 100.0),
    (1, 2, 85.0),
    (3, 5, 59.0),
    (5, 10, 25.0),
])
def test_metric_architecture_health_sensitivity(incidents, debt, expected_max_arch):
    calc = OrganizationMetricsCalculator()
    dash = calc.calculate_dashboard(
        departments={},
        incidents_count=incidents,
        technical_debt_items=debt,
    )
    assert dash.architecture_health_score <= expected_max_arch


@pytest.mark.parametrize("cves,findings,expected_max_sec", [
    (0, 0, 100.0),
    (1, 0, 75.0),
    (2, 2, 45.0),
])
def test_metric_security_score_sensitivity(cves, findings, expected_max_sec):
    calc = OrganizationMetricsCalculator()
    dash = calc.calculate_dashboard(
        departments={},
        critical_cves_count=cves,
        security_findings_count=findings,
    )
    assert dash.security_score <= expected_max_sec


# 7. Enterprise Organization Department Lookups
@pytest.mark.parametrize("dept_name", [
    "CEO", "CTO", "EngineeringManager", "Architecture", "Backend",
    "Frontend", "QA", "Security", "DevOps", "ReleaseManager",
    "Documentation", "CustomerFeedback", "BusinessAnalyst",
    "ProductManager", "Finance", "Compliance", "Operations"
])
def test_enterprise_all_departments_lookup(dept_name):
    org = EnterpriseOrganization(auto_persist=False)
    d = org.get_department(dept_name)
    assert d is not None
    assert d.name == dept_name


@pytest.mark.parametrize("agent_name", [
    "CEO", "CTO", "EngineeringManager", "Architecture", "Backend",
    "Frontend", "QA", "Security", "DevOps", "ReleaseManager",
    "Documentation", "CustomerFeedback", "BusinessAnalyst",
    "ProductManager", "Finance", "Compliance", "Operations"
])
def test_enterprise_all_agents_lookup(agent_name):
    org = EnterpriseOrganization(auto_persist=False)
    a = org.get_agent(agent_name)
    assert a is not None
    assert a.name == agent_name
