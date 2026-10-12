"""
test_organization_state.py - AutoDev Version 3.4
Unit and integration tests for Organization State & Memory:
- Department history snapshots and chronological records
- Meetings, ADRs, Releases, Incidents, Postmortems
- Customer requests and Financial reports
- Cryptographic SHA-256 tamper-evident audit log & tamper verification
- Keyword search across collections
- JSON persistence and reloading
"""

from pathlib import Path
import pytest
from core.organization_state import OrganizationState


@pytest.fixture
def org_state(tmp_path: Path):
    storage_dir = tmp_path / "org_state"
    return OrganizationState(storage_dir=storage_dir, auto_persist=True)


def test_audit_trail_cryptographic_verification(org_state: OrganizationState):
    # Record multiple audit events
    id1 = org_state.record_audit_event("CEO", "APPROVE_PLAN", {"version": "3.4"})
    id2 = org_state.record_audit_event("CTO", "VALIDATE_TECH", {"status": "PASSED"})
    id3 = org_state.record_audit_event("ReleaseManager", "RELEASE_GA", {"version": "3.4.0"})

    assert len(org_state.audit_trail) == 3
    assert org_state.verify_audit_trail_integrity() is True

    # Tamper with an event in the chain and verify integrity fails!
    org_state.audit_trail[1]["action"] = "TAMPERED_ACTION"
    assert org_state.verify_audit_trail_integrity() is False


def test_record_and_retrieve_meetings(org_state: OrganizationState):
    mid = org_state.record_meeting({
        "type": "DAILY_STANDUP",
        "title": "Engineering Standup",
        "host": "EngineeringManager",
        "attendees": ["Backend", "Frontend", "QA"],
        "decisions": ["Deploy staging build"],
    })
    assert mid.startswith("MEET-")
    assert len(org_state.meeting_history) == 1
    assert org_state.meeting_history[0]["title"] == "Engineering Standup"


def test_record_and_retrieve_architecture_decisions(org_state: OrganizationState):
    adr_id = org_state.record_architecture_decision({
        "title": "Use Hexagonal Layering",
        "decision": "Isolate core domain models from IO adapters",
        "author": "ChiefArchitect",
        "status": "ACCEPTED",
    })
    assert adr_id.startswith("ADR-")
    assert len(org_state.architecture_decisions) == 1
    assert org_state.architecture_decisions[0]["decision"] == "Isolate core domain models from IO adapters"


def test_record_and_resolve_incidents(org_state: OrganizationState):
    inc_id = org_state.record_incident({
        "title": "Database connection pool exhaustion",
        "severity": "SEV-2",
        "reporter": "DevOps",
    })
    assert inc_id.startswith("INC-")
    assert len(org_state.incidents) == 1
    assert org_state.incidents[0]["status"] == "ACTIVE"

    # Resolve incident
    res = org_state.resolve_incident(
        incident_id=inc_id,
        resolution="Increased pool max_connections to 50",
        root_cause="Spike in parallel worker threads",
    )
    assert res is True
    assert org_state.incidents[0]["status"] == "RESOLVED"
    assert org_state.incidents[0]["resolution"] == "Increased pool max_connections to 50"


def test_record_postmortem(org_state: OrganizationState):
    pm_id = org_state.record_postmortem({
        "incident_id": "INC-01",
        "root_cause": "Unbounded task queue",
        "lessons_learned": "Enforce bounded backpressure queues",
    })
    assert pm_id.startswith("PM-")
    assert len(org_state.postmortems) == 1
    assert org_state.postmortems[0]["lessons_learned"] == "Enforce bounded backpressure queues"


def test_record_customer_request_and_financials(org_state: OrganizationState):
    req_id = org_state.record_customer_request({
        "title": "Support Stripe Webhooks",
        "description": "Need automated webhook handling for subscription renewals",
    })
    assert req_id.startswith("REQ-")
    assert len(org_state.customer_requests) == 1

    fin_id = org_state.record_financial_report({
        "monthly_burn_rate": 45000.0,
        "token_expenditure_usd": 120.50,
    })
    assert fin_id.startswith("FIN-")
    assert len(org_state.financial_reports) == 1


def test_roadmap_updates(org_state: OrganizationState):
    milestones = [
        {"title": "M1: Alpha Launch", "due_date": "2026-11-01"},
        {"title": "M2: Enterprise GA", "due_date": "2026-12-15"},
    ]
    org_state.update_roadmap(quarter="Q4-2026", milestones=milestones)

    assert "Q4-2026" in org_state.roadmaps["quarters"]
    assert len(org_state.roadmaps["quarters"]["Q4-2026"]) == 2
    assert len(org_state.roadmaps["milestones"]) == 2


def test_search_memory_across_domains(org_state: OrganizationState):
    org_state.record_architecture_decision({"title": "Event-Driven Microservices", "decision": "Kafka streaming"})
    org_state.record_meeting({"title": "Kafka architecture review", "decisions": ["Approved event schema"]})
    org_state.record_incident({"title": "Kafka partition rebalance lag", "root_cause": "Consumer group stalled"})

    # Search for 'Kafka' across all domains
    results = org_state.search_memory("Kafka")
    assert len(results) == 3

    domains = {r["domain"] for r in results}
    assert "architecture_decisions" in domains
    assert "meeting_history" in domains
    assert "incidents" in domains

    # Targeted domain search
    adr_only = org_state.search_memory("Kafka", domain="adr")
    assert len(adr_only) == 1
    assert adr_only[0]["domain"] == "architecture_decisions"


def test_persistence_save_and_reload(tmp_path: Path):
    storage_dir = tmp_path / "persist_test"
    state1 = OrganizationState(storage_dir=storage_dir, auto_persist=True)
    state1.record_architecture_decision({"title": "ADR 1", "decision": "Use SQLite"})
    state1.record_incident({"title": "Incident 1", "severity": "SEV-3"})

    # Reload from same disk location
    state2 = OrganizationState(storage_dir=storage_dir, auto_persist=True)
    assert len(state2.architecture_decisions) == 1
    assert state2.architecture_decisions[0]["title"] == "ADR 1"
    assert len(state2.incidents) == 1
    assert state2.incidents[0]["title"] == "Incident 1"
    assert state2.verify_audit_trail_integrity() is True
