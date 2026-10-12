"""
test_meeting_manager.py - AutoDev Version 3.4
Unit and integration tests for Autonomous Meeting Manager:
- 9 Corporate meeting types: Standup, Planning, Review, Architecture, Incident, Security, Release, Executive, Retro
- Blocker extraction from department telemetry
- Action item synthesis and assignment
- Decision ratification and broadcast
- Meeting minutes archiving and queries
"""

from pathlib import Path
import pytest
from core.communication_bus import CommunicationBus, OrgMessageType
from core.meeting_manager import MeetingManager, MeetingType
from core.organization_state import OrganizationState


@pytest.fixture
def bus():
    return CommunicationBus()


@pytest.fixture
def meeting_manager(tmp_path: Path, bus: CommunicationBus):
    state = OrganizationState(storage_dir=tmp_path / "meetings", auto_persist=True)
    return MeetingManager(bus=bus, state=state)


def test_conduct_daily_standup(meeting_manager: MeetingManager):
    reports = {
        "Backend": {"active_tasks_count": 3, "blocked_tasks_count": 1, "blocked_task_reasons": {"T-1": "Waiting on schema"}},
        "Frontend": {"active_tasks_count": 2, "blocked_tasks_count": 0, "blocked_task_reasons": {}},
    }
    minutes = meeting_manager.schedule_and_conduct_meeting(
        meeting_type=MeetingType.DAILY_STANDUP,
        title="Engineering Daily Standup",
        host="EngineeringManager",
        attendees=["Backend", "Frontend", "QA"],
        department_reports=reports,
    )
    assert minutes.meeting_id.startswith("MEET-DAIL-")
    assert minutes.meeting_type == MeetingType.DAILY_STANDUP
    assert len(minutes.blockers_identified) == 1
    assert "Waiting on schema" in minutes.blockers_identified[0]
    assert len(minutes.action_items) >= 1
    assert minutes.action_items[0].assignee == "EngineeringManager"
    assert len(minutes.decisions_ratified) >= 1


def test_conduct_sprint_planning(meeting_manager: MeetingManager):
    minutes = meeting_manager.schedule_and_conduct_meeting(
        meeting_type=MeetingType.SPRINT_PLANNING,
        title="Sprint 43 Planning",
        host="ProductManager",
        attendees=["EngineeringManager", "Backend", "Frontend", "QA"],
        agenda=["Review backlog", "Estimate capacity", "Commit sprint goal"],
    )
    assert minutes.meeting_type == MeetingType.SPRINT_PLANNING
    assert any("Sprint backlog committed" in d for d in minutes.decisions_ratified)
    assert any("Decompose committed epics" in a.description for a in minutes.action_items)


def test_conduct_architecture_review(meeting_manager: MeetingManager):
    minutes = meeting_manager.schedule_and_conduct_meeting(
        meeting_type=MeetingType.ARCHITECTURE_REVIEW,
        title="Core Ledger ADR Review",
        host="ChiefArchitect",
        attendees=["ChiefArchitect", "Backend", "Security", "DevOps"],
    )
    assert minutes.meeting_type == MeetingType.ARCHITECTURE_REVIEW
    assert any("Architectural Decision Record" in d for d in minutes.decisions_ratified)
    assert any("Architecture" == a.assignee for a in minutes.action_items)


def test_conduct_security_review(meeting_manager: MeetingManager):
    minutes = meeting_manager.schedule_and_conduct_meeting(
        meeting_type=MeetingType.SECURITY_REVIEW,
        title="Sprint Security Audit",
        host="Security",
        attendees=["Security", "Backend", "DevOps", "Compliance"],
    )
    assert minutes.meeting_type == MeetingType.SECURITY_REVIEW
    assert any("Zero critical CVEs" in d for d in minutes.decisions_ratified)
    assert minutes.action_items[0].priority == "CRITICAL"


def test_conduct_release_meeting(meeting_manager: MeetingManager):
    minutes = meeting_manager.schedule_and_conduct_meeting(
        meeting_type=MeetingType.RELEASE_MEETING,
        title="Version 3.4.0 Release Go/No-Go",
        host="ReleaseManager",
        attendees=["ReleaseManager", "QA", "Security", "DevOps", "CEO", "CTO"],
    )
    assert minutes.meeting_type == MeetingType.RELEASE_MEETING
    assert any("Release gate checklist PASSED" in d for d in minutes.decisions_ratified)


def test_conduct_incident_review(meeting_manager: MeetingManager):
    minutes = meeting_manager.schedule_and_conduct_meeting(
        meeting_type=MeetingType.INCIDENT_REVIEW,
        title="INC-101 Post-Triage Review",
        host="Operations",
        attendees=["Operations", "DevOps", "Backend"],
    )
    assert minutes.meeting_type == MeetingType.INCIDENT_REVIEW
    assert any("Incident classified and mitigated" in d for d in minutes.decisions_ratified)


def test_conduct_executive_review(meeting_manager: MeetingManager):
    minutes = meeting_manager.schedule_and_conduct_meeting(
        meeting_type=MeetingType.EXECUTIVE_REVIEW,
        title="Q4 Executive Operations Review",
        host="CEO",
        attendees=["CEO", "CTO", "Finance", "ProductManager"],
    )
    assert minutes.meeting_type == MeetingType.EXECUTIVE_REVIEW
    assert any("burn rate" in d.lower() for d in minutes.decisions_ratified)


def test_conduct_retrospective(meeting_manager: MeetingManager):
    minutes = meeting_manager.schedule_and_conduct_meeting(
        meeting_type=MeetingType.RETROSPECTIVE,
        title="Sprint 42 Retrospective",
        host="EngineeringManager",
        attendees=["Backend", "Frontend", "QA", "DevOps"],
    )
    assert minutes.meeting_type == MeetingType.RETROSPECTIVE
    assert len(minutes.action_items) >= 1


def test_minutes_broadcast_on_bus(meeting_manager: MeetingManager, bus: CommunicationBus):
    received = []
    bus.subscribe(OrgMessageType.MEETING_MINUTES, lambda m: received.append(m))

    meeting_manager.schedule_and_conduct_meeting(
        meeting_type=MeetingType.DAILY_STANDUP,
        title="Test Standup",
        host="EM",
        attendees=["Backend"],
    )
    assert len(received) == 1
    assert received[0].payload["title"] == "Test Standup"


def test_list_and_get_minutes(meeting_manager: MeetingManager):
    m1 = meeting_manager.schedule_and_conduct_meeting(MeetingType.DAILY_STANDUP, "S1", "EM", ["A"])
    m2 = meeting_manager.schedule_and_conduct_meeting(MeetingType.RETROSPECTIVE, "R1", "EM", ["A"])

    all_m = meeting_manager.list_meetings()
    assert len(all_m) == 2

    standups = meeting_manager.list_meetings(meeting_type=MeetingType.DAILY_STANDUP)
    assert len(standups) == 1
    assert standups[0]["title"] == "S1"

    fetched = meeting_manager.get_meeting_minutes(m1.meeting_id)
    assert fetched is not None
    assert fetched.meeting_id == m1.meeting_id
