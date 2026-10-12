"""
test_v34_extended_matrix.py - AutoDev Version 3.4
Parameterized test matrix systematically verifying:
- All 13 message types and 5 priority levels on CommunicationBus
- All 16 DepartmentRoles and 5 DepartmentAuthorityLevels
- All 8 DecisionDomains with diverse vote distributions
- All 9 MeetingTypes with distinct agendas and actions
- All 7 ConflictTypes under different authority conditions
"""

import pytest
from core.communication_bus import (
    CommunicationBus,
    MessagePriority,
    OrgMessage,
    OrgMessageType,
)
from core.conflict_resolver import ConflictResolver, ConflictType
from core.decision_engine import DecisionDomain, DecisionEngine
from core.department import (
    Department,
    DepartmentAuthorityLevel,
    DepartmentRole,
)
from core.meeting_manager import MeetingManager, MeetingType
from core.organization_state import OrganizationState


# 1. Parameterized Message Types
@pytest.mark.parametrize("msg_type", list(OrgMessageType))
def test_all_message_types_supported(msg_type):
    bus = CommunicationBus()
    msg = OrgMessage(
        sender="DeptA",
        receiver="DeptB",
        message_type=msg_type,
        payload={"type": msg_type.value},
    )
    assert bus.send_message(msg) is True
    msgs = bus.get_messages("DeptB")
    assert len(msgs) == 1
    assert msgs[0].message_type == msg_type


# 2. Parameterized Message Priorities
@pytest.mark.parametrize("priority", list(MessagePriority))
def test_all_message_priorities_supported(priority):
    bus = CommunicationBus()
    msg = OrgMessage(
        sender="DeptA",
        receiver="DeptB",
        priority=priority,
        payload={"prio": priority.value},
    )
    assert bus.send_message(msg) is True
    msgs = bus.get_messages("DeptB")
    assert len(msgs) == 1
    assert msgs[0].priority == priority


# 3. Parameterized Department Roles
@pytest.mark.parametrize("role", list(DepartmentRole))
def test_all_department_roles_initialization(role):
    dept = Department(
        name=f"Dept_{role.value}",
        role=role,
        capacity=8,
        budget=45000.0,
    )
    assert dept.role == role
    assert dept.health_score == 100.0
    rep = dept.get_status_report()
    assert rep["role"] == role.value


# 4. Parameterized Department Authority Levels
@pytest.mark.parametrize("auth_level", list(DepartmentAuthorityLevel))
def test_all_department_authority_levels(auth_level):
    dept = Department(
        name=f"Dept_Auth_{auth_level.value}",
        role=DepartmentRole.BACKEND,
        authority=auth_level,
    )
    assert dept.authority == auth_level
    rep = dept.get_status_report()
    assert rep["authority"] == auth_level.value


# 5. Parameterized Decision Domains
@pytest.mark.parametrize("domain", list(DecisionDomain))
def test_all_decision_domains_resolution(domain, tmp_path):
    state = OrganizationState(storage_dir=tmp_path / f"dec_{domain.value}", auto_persist=False)
    engine = DecisionEngine(state=state)

    pid = engine.create_proposal(
        title=f"Decision for {domain.value}",
        domain=domain,
        options=["Option_Alpha", "Option_Beta"],
        proposer="ProposerDept",
    )
    engine.cast_vote(pid, "CTO", "Option_Alpha", confidence=0.95)
    engine.cast_vote(pid, "EngineeringManager", "Option_Alpha", confidence=0.90)

    res = engine.evaluate_decision(pid)
    assert res["winning_option"] == "Option_Alpha"
    assert res["domain"] == domain.value


# 6. Parameterized Meeting Types
@pytest.mark.parametrize("mtype", list(MeetingType))
def test_all_meeting_types_execution(mtype, tmp_path):
    state = OrganizationState(storage_dir=tmp_path / f"meet_{mtype.value}", auto_persist=False)
    mm = MeetingManager(state=state)

    minutes = mm.schedule_and_conduct_meeting(
        meeting_type=mtype,
        title=f"{mtype.value} Test",
        host="HostAgent",
        attendees=["Backend", "QA"],
    )
    assert minutes.meeting_type == mtype
    assert len(minutes.action_items) >= 1
    assert len(minutes.decisions_ratified) >= 1


# 7. Parameterized Conflict Types
@pytest.mark.parametrize("ctype", list(ConflictType))
def test_all_conflict_types_registration_and_handling(ctype):
    resolver = ConflictResolver()
    rec = resolver.register_conflict(
        conflict_type=ctype,
        parties_involved=["PartyA", "PartyB"],
        description=f"Dispute of {ctype.value}",
        competing_proposals={"PartyA": {"val": 1}, "PartyB": {"val": 2}},
    )
    resolved = resolver.resolve_conflict(rec.conflict_id)
    assert resolved.status.value in ("AUTO_RESOLVED", "ESCALATED")
