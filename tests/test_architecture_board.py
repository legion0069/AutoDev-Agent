"""
test_architecture_board.py - Unit and Integration Tests for Architecture Review Board (v3.0)
"""

import pytest
from core.enterprise.architecture_board import ArchitectureBoard
from core.enterprise.enterprise_models import ArchReviewStatus, ArchitectureScorecard


@pytest.fixture
def arb():
    return ArchitectureBoard(min_approval_score=80.0)


class TestArchitectureBoard:
    def test_submit_proposal_auto_approved(self, arb: ArchitectureBoard):
        prop = arb.submit_proposal(
            title="Clean Layered Architecture for Enterprise Orchestrator",
            author="Marcus Vance (CTO)",
            system_component="EnterpriseOrchestrator",
            changes_summary="Decoupled presentation, domain models, and corporate managers",
            adr_markdown="# ADR-001: Clean Enterprise Layering\n\nAdopts strict dependency inversion.",
            scorecard=ArchitectureScorecard(
                solid_score=95.0,
                ddd_score=90.0,
                layering_score=95.0,
                scalability_score=90.0,
                security_score=95.0,
                performance_score=90.0,
                maintainability_score=95.0,
                complexity_penalty=5.0,
                testability_score=95.0,
            ),
        )
        assert prop.proposal_id.startswith("PROP-")
        assert prop.scorecard.composite_architecture_score >= 90.0
        assert prop.review_status == ArchReviewStatus.APPROVED

    def test_submit_proposal_rejected_due_to_low_score(self, arb: ArchitectureBoard):
        low_scorecard = ArchitectureScorecard(
            solid_score=50.0,
            ddd_score=40.0,
            layering_score=50.0,
            scalability_score=50.0,
            security_score=50.0,
            performance_score=50.0,
            maintainability_score=50.0,
            complexity_penalty=40.0,
            testability_score=50.0,
        )
        prop = arb.submit_proposal(
            title="Monolithic God Object Implementation",
            author="Dev",
            system_component="Core",
            changes_summary="Single 10k line file",
            adr_markdown="# ADR: Monolith",
            scorecard=low_scorecard,
        )
        assert prop.scorecard.composite_architecture_score < 80.0
        assert prop.review_status == ArchReviewStatus.REJECTED
        assert len(prop.review_feedback) > 0

    def test_evaluate_code_architecture_heuristics(self, arb: ArchitectureBoard):
        clean_code = """
class EnterpriseService:
    def execute(self) -> None:
        pass
"""
        scorecard = arb.evaluate_code_architecture(clean_code)
        assert scorecard.solid_score >= 80.0
        assert scorecard.complexity_penalty <= 15.0
        assert scorecard.composite_architecture_score >= 80.0

    def test_evaluate_code_with_heavy_prohibited_frameworks(self, arb: ArchitectureBoard):
        prohibited_code = """
import langgraph
import celery
import ray
import autogen

def run():
    pass
"""
        scorecard = arb.evaluate_code_architecture(prohibited_code)
        # Should be heavily penalized for violating pure standard library mandate
        assert scorecard.layering_score < 50.0
        assert scorecard.complexity_penalty >= 30.0

    def test_list_proposals(self, arb: ArchitectureBoard):
        arb.submit_proposal("Prop 1", "Auth", "Comp1", "Summ", "ADR")
        arb.submit_proposal("Prop 2", "Auth", "Comp2", "Summ", "ADR")
        proposals = arb.list_proposals()
        assert len(proposals) >= 2
