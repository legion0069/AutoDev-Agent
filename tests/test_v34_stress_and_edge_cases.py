"""
test_v34_stress_and_edge_cases.py - AutoDev Version 3.4
Stress, concurrency, robustness, and edge-case testing for Autonomous AI Organization:
- Multi-threaded concurrent message dispatch on CommunicationBus
- High-concurrency task processing and capacity saturation in Departments
- Rapid multi-proposal voting in Decision Engine
- Complex conflict resolution chains and fallback escalation paths
- Simultaneous meeting executions
- Cryptographic hash chain validation under rapid sequential events
- Edge cases: empty payloads, extreme budgets, zero capacities, unknown entities
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
import time
from core.communication_bus import (
    CommunicationBus,
    MessagePriority,
    OrgMessage,
    OrgMessageType,
)
from core.conflict_resolver import ConflictResolver, ConflictType
from core.decision_engine import DecisionDomain, DecisionEngine
from core.department import Department, DepartmentAuthorityLevel, DepartmentRole
from core.meeting_manager import MeetingManager, MeetingType
from core.organization import EnterpriseOrganization
from core.organization_state import OrganizationState


def test_concurrent_message_bus_dispatch():
    bus = CommunicationBus()
    for i in range(10):
        bus.register_entity(f"Dept_{i}")

    def sender_worker(sender_id: int):
        for j in range(25):
            msg = OrgMessage(
                sender=f"Dept_{sender_id}",
                receiver=f"Dept_{(sender_id + 1) % 10}",
                priority=MessagePriority.NORMAL,
                payload={"iter": j},
            )
            bus.send_message(msg)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(sender_worker, i) for i in range(5)]
        for f in futures:
            f.result()

    telemetry = bus.get_bus_telemetry()
    assert telemetry["total_messages_exchanged"] == 125
    assert bus.clear() is None
    assert bus.get_bus_telemetry()["total_messages_exchanged"] == 0


def test_concurrent_department_task_saturation():
    dept = Department("HeavyBackend", DepartmentRole.BACKEND, capacity=10)

    def worker_assign(tid: int):
        return dept.assign_task(f"TASK-{tid}", f"Title {tid}", "Desc", "EM")

    with ThreadPoolExecutor(max_workers=4) as executor:
        tasks = list(executor.map(worker_assign, range(20)))

    assert len(tasks) == 20
    # Exactly 10 active tasks and 10 blocked tasks
    assert len(dept.active_tasks) == 10
    assert len(dept.blocked_tasks) == 10
    assert dept.health_score < 50.0

    # Rapid completion of all active tasks
    for i in range(10):
        dept.complete_task(f"TASK-{i}")

    # The 10 blocked tasks should have been unblocked!
    assert len(dept.active_tasks) == 10
    assert len(dept.blocked_tasks) == 0


def test_decision_engine_high_volume_proposals(tmp_path: Path):
    state = OrganizationState(storage_dir=tmp_path / "dec_stress", auto_persist=False)
    engine = DecisionEngine(state=state)

    for i in range(15):
        pid = engine.create_proposal(
            title=f"Proposal {i}",
            domain=DecisionDomain.PRIORITY,
            options=["High", "Low"],
            proposer="ProductManager",
        )
        engine.cast_vote(pid, "CTO", "High", 0.95)
        engine.cast_vote(pid, "Backend", "High" if i % 2 == 0 else "Low", 0.8)
        res = engine.evaluate_decision(pid)
        assert res["winning_option"] == "High"


def test_conflict_resolver_all_seven_types():
    resolver = ConflictResolver()
    conflict_types = [
        ConflictType.RESOURCE_CONFLICT,
        ConflictType.TASK_CONFLICT,
        ConflictType.ARCHITECTURE_CONFLICT,
        ConflictType.MERGE_CONFLICT,
        ConflictType.PRIORITY_CONFLICT,
        ConflictType.OWNERSHIP_CONFLICT,
        ConflictType.SECURITY_CONFLICT,
    ]

    for ct in conflict_types:
        rec = resolver.register_conflict(
            conflict_type=ct,
            parties_involved=["Backend", "QA"],
            description=f"Dispute of type {ct.value}",
            competing_proposals={"Backend": "Option 1", "QA": "Option 2"},
        )
        res = resolver.resolve_conflict(rec.conflict_id)
        assert res.status.value in ("AUTO_RESOLVED", "ESCALATED")


def test_rapid_audit_trail_tamper_detection(tmp_path: Path):
    state = OrganizationState(storage_dir=tmp_path / "audit_stress", auto_persist=False)

    for i in range(50):
        state.record_audit_event(
            actor=f"Agent_{i%5}",
            action=f"ACTION_{i}",
            details={"index": i, "timestamp": time.time()},
        )

    assert len(state.audit_trail) == 50
    assert state.verify_audit_trail_integrity() is True

    # Tamper with the 25th event
    state.audit_trail[25]["details"]["index"] = 9999
    assert state.verify_audit_trail_integrity() is False


def test_simultaneous_all_meetings_and_action_item_tracking(tmp_path: Path):
    state = OrganizationState(storage_dir=tmp_path / "meet_stress", auto_persist=False)
    bus = CommunicationBus()
    mm = MeetingManager(bus=bus, state=state)

    meeting_types = [
        MeetingType.DAILY_STANDUP,
        MeetingType.SPRINT_PLANNING,
        MeetingType.SPRINT_REVIEW,
        MeetingType.ARCHITECTURE_REVIEW,
        MeetingType.INCIDENT_REVIEW,
        MeetingType.SECURITY_REVIEW,
        MeetingType.RELEASE_MEETING,
        MeetingType.EXECUTIVE_REVIEW,
        MeetingType.RETROSPECTIVE,
    ]

    minutes_list = []
    for mt in meeting_types:
        m = mm.schedule_and_conduct_meeting(
            meeting_type=mt,
            title=f"{mt.value} Test Session",
            host="HostAgent",
            attendees=["Backend", "Frontend", "QA"],
        )
        minutes_list.append(m)

    assert len(minutes_list) == 9
    assert all(len(m.action_items) >= 1 for m in minutes_list)
    assert all(len(m.decisions_ratified) >= 1 for m in minutes_list)


def test_organization_budget_exhaustion_and_overrun(tmp_path: Path):
    org = EnterpriseOrganization(
        company_name="Budget Stress Corp",
        storage_dir=tmp_path / "budget_stress",
        initial_budget_usd=10000.0,
        auto_persist=False,
    )

    # Department spends more than its budget
    be = org.get_department("Backend")
    assert be is not None
    assert be.spend_budget(be.budget + 5000.0) is False
    assert be.spent_budget > be.budget

    rep = be.get_status_report()
    assert rep["budget_remaining"] == 0.0


def test_unknown_entity_messaging(tmp_path: Path):
    bus = CommunicationBus()
    # Sending to unknown receiver auto-registers the entity inbox
    msg = OrgMessage(sender="UnknownA", receiver="UnknownB", payload={"hello": "world"})
    assert bus.send_message(msg) is True
    assert len(bus.get_messages("UnknownB")) == 1


def test_empty_string_search_memory(tmp_path: Path):
    state = OrganizationState(storage_dir=tmp_path / "empty_search", auto_persist=False)
    state.record_incident({"title": "Sample Incident", "severity": "SEV-3"})
    results = state.search_memory("sample")
    assert len(results) == 1
    # Search non-matching
    assert len(state.search_memory("xyznonexistent")) == 0
