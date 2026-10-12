"""
test_decision_engine.py - AutoDev Version 3.4
Unit and integration tests for Decision Engine:
- Proposal creation, options, and domains
- Multi-department voting with weights and evidence
- Weighted scoring and winning option selection
- Executive override / veto (CEO / CTO)
- Audit trail recording and ADR propagation
"""

from pathlib import Path
import pytest
from core.decision_engine import DecisionDomain, DecisionEngine
from core.organization_state import OrganizationState


@pytest.fixture
def decision_engine(tmp_path: Path):
    state = OrganizationState(storage_dir=tmp_path / "decisions", auto_persist=True)
    return DecisionEngine(state=state)


def test_create_proposal(decision_engine: DecisionEngine):
    pid = decision_engine.create_proposal(
        title="Database Choice for Transactional Ledger",
        domain=DecisionDomain.ARCHITECTURE_CHOICE,
        options=["PostgreSQL", "SQLite", "DynamoDB"],
        proposer="Backend",
        context={"project": "PaymentsAPI"},
    )
    assert pid.startswith("DEC-")

    prop = decision_engine.get_proposal(pid)
    assert prop is not None
    assert prop.title == "Database Choice for Transactional Ledger"
    assert prop.options == ["PostgreSQL", "SQLite", "DynamoDB"]
    assert prop.status == "OPEN"


def test_cast_vote_and_evaluate_decision(decision_engine: DecisionEngine):
    pid = decision_engine.create_proposal(
        title="API Style",
        domain=DecisionDomain.FRAMEWORK_SELECTION,
        options=["REST_JSON", "gRPC_Proto", "GraphQL"],
        proposer="Backend",
    )

    # Backend votes REST
    decision_engine.cast_vote(
        proposal_id=pid,
        voter="Backend",
        chosen_option="REST_JSON",
        confidence=0.9,
        evidence=["Ubiquitous standard across all HTTP clients"],
    )

    # Frontend votes REST
    decision_engine.cast_vote(
        proposal_id=pid,
        voter="Frontend",
        chosen_option="REST_JSON",
        confidence=0.95,
        evidence=["Native browser fetch API support"],
    )

    # DevOps votes gRPC
    decision_engine.cast_vote(
        proposal_id=pid,
        voter="DevOps",
        chosen_option="gRPC_Proto",
        confidence=0.8,
        evidence=["Higher binary serialization throughput"],
    )

    result = decision_engine.evaluate_decision(pid)
    assert result["winning_option"] == "REST_JSON"
    assert result["status"] == "RESOLVED"
    assert result["confidence_score"] > 0.60
    assert len(result["ranked_evidence"]) >= 1


def test_security_weight_boost(decision_engine: DecisionEngine):
    pid = decision_engine.create_proposal(
        title="Token Validation Policy",
        domain=DecisionDomain.SECURITY_FINDINGS,
        options=["Strict_Issuer_Verification", "Permissive_Local_Decode"],
        proposer="Backend",
    )

    # Backend votes Permissive (Weight 2.5)
    decision_engine.cast_vote(
        proposal_id=pid,
        voter="Backend",
        chosen_option="Permissive_Local_Decode",
        confidence=0.8,
        evidence=["Faster execution without network lookup"],
    )

    # Security votes Strict (Base weight 3.8 * 1.5 security domain boost = 5.7)
    decision_engine.cast_vote(
        proposal_id=pid,
        voter="Security",
        chosen_option="Strict_Issuer_Verification",
        confidence=0.99,
        evidence=["Prevents spoofed JWT token replay attacks"],
    )

    result = decision_engine.evaluate_decision(pid)
    # Security must decisively win!
    assert result["winning_option"] == "Strict_Issuer_Verification"


def test_executive_override_by_ceo(decision_engine: DecisionEngine):
    pid = decision_engine.create_proposal(
        title="Release Date",
        domain=DecisionDomain.RELEASE_TIMING,
        options=["Release_Today", "Delay_Two_Weeks"],
        proposer="ProductManager",
    )

    decision_engine.cast_vote(pid, "QA", "Delay_Two_Weeks", 0.9)
    decision_engine.cast_vote(pid, "Backend", "Delay_Two_Weeks", 0.85)

    decision_engine.evaluate_decision(pid)
    assert decision_engine.get_proposal(pid).winning_option == "Delay_Two_Weeks"

    # CEO exercises executive veto
    override_ok = decision_engine.override_decision(
        proposal_id=pid,
        overrider="CEO",
        chosen_option="Release_Today",
        rationale="Client contract penalty requires deployment today; hotfix minor defects in flight.",
    )
    assert override_ok is True
    prop = decision_engine.get_proposal(pid)
    assert prop.winning_option == "Release_Today"
    assert prop.status == "OVERRIDDEN"
    assert prop.overridden_by == "CEO"


def test_unauthorized_override_rejected(decision_engine: DecisionEngine):
    pid = decision_engine.create_proposal(
        title="Testing Framework",
        domain=DecisionDomain.FRAMEWORK_SELECTION,
        options=["Pytest", "Unittest"],
        proposer="QA",
    )
    # Individual contributor cannot override
    override_ok = decision_engine.override_decision(
        proposal_id=pid,
        overrider="JuniorEngineer",
        chosen_option="Unittest",
        rationale="I prefer unittest",
    )
    assert override_ok is False


def test_evaluate_decision_without_votes(decision_engine: DecisionEngine):
    pid = decision_engine.create_proposal(
        title="Fallback Choice",
        domain=DecisionDomain.PRIORITY,
        options=["Option_A", "Option_B"],
        proposer="PM",
    )
    result = decision_engine.evaluate_decision(pid)
    assert result["winning_option"] == "Option_A"
    assert result["status"] == "RESOLVED"
    assert "no votes cast" in result["decision_rationale"]


def test_list_proposals_by_domain(decision_engine: DecisionEngine):
    decision_engine.create_proposal("Arch 1", DecisionDomain.ARCHITECTURE_CHOICE, ["A", "B"], "Arch")
    decision_engine.create_proposal("Sec 1", DecisionDomain.SECURITY_FINDINGS, ["C", "D"], "Sec")

    all_props = decision_engine.list_proposals()
    assert len(all_props) == 2

    arch_props = decision_engine.list_proposals(domain=DecisionDomain.ARCHITECTURE_CHOICE)
    assert len(arch_props) == 1
    assert arch_props[0]["title"] == "Arch 1"
