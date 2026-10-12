"""
test_executive_engine.py - Unit and Integration Tests for Executive Decision Engine (v3.0)
"""

import pytest
from core.enterprise.enterprise_models import (
    DecisionStatus,
    DepartmentType,
    ExecutiveDecision,
    ExecutiveProfile,
    ExecutiveRole,
    StrategicGoal,
)
from core.enterprise.executive_engine import ExecutiveDecisionEngine


@pytest.fixture
def engine():
    return ExecutiveDecisionEngine()


class TestExecutiveDecisionEngine:
    def test_default_c_suite_initialized(self, engine: ExecutiveDecisionEngine):
        execs = engine.list_executives()
        assert len(execs) == 15
        roles = {e.role for e in execs}
        assert ExecutiveRole.CEO in roles
        assert ExecutiveRole.CTO in roles
        assert ExecutiveRole.VP_PRODUCT in roles
        assert ExecutiveRole.VP_ENGINEERING in roles
        assert ExecutiveRole.DIRECTOR_FINANCE in roles
        assert ExecutiveRole.DIRECTOR_SECURITY in roles
        assert ExecutiveRole.LEGAL_COUNSEL in roles

    def test_get_executive(self, engine: ExecutiveDecisionEngine):
        ceo = engine.get_executive(ExecutiveRole.CEO)
        assert ceo is not None
        assert ceo.role == ExecutiveRole.CEO
        assert ceo.title == "Chief Executive Officer"
        assert ceo.budget_authority_usd >= 5000000.0

    def test_update_kpis(self, engine: ExecutiveDecisionEngine):
        engine.update_executive_kpis(ExecutiveRole.CTO, {"architecture_health": 98.5})
        cto = engine.get_executive(ExecutiveRole.CTO)
        assert cto.kpis["architecture_health"] == 98.5

    def test_propose_decision(self, engine: ExecutiveDecisionEngine):
        dec = engine.propose_decision(
            title="Adopt Rust for Core Gateway",
            description="Upgrade core routing engine to high-performance Rust service",
            proposer_role=ExecutiveRole.CTO,
            required_signoffs=[ExecutiveRole.VP_ENGINEERING, ExecutiveRole.DIRECTOR_SECURITY],
            budget_impact_usd=150000.0,
            strategic_alignment_score=92.0,
            risk_score=20.0,
        )
        assert dec.decision_id.startswith("DEC-")
        assert dec.status == DecisionStatus.PROPOSED
        assert len(dec.required_signoffs) >= 2

    def test_decision_approval_flow(self, engine: ExecutiveDecisionEngine):
        dec = engine.propose_decision(
            title="Expand AI Infrastructure Cluster",
            description="Add 32 GPU nodes for local training",
            proposer_role=ExecutiveRole.VP_ENGINEERING,
            required_signoffs=[ExecutiveRole.CTO, ExecutiveRole.DIRECTOR_FINANCE],
            budget_impact_usd=300000.0,
        )

        # First signoff
        res1 = engine.signoff_decision(dec.decision_id, ExecutiveRole.CTO, approved=True, notes="Tech stack verified")
        assert res1.status == DecisionStatus.IN_REVIEW
        assert res1.signoffs_received["CTO"] is True

        # Second signoff completes approval
        res2 = engine.signoff_decision(dec.decision_id, ExecutiveRole.DIRECTOR_FINANCE, approved=True, notes="Budget allocated")
        assert res2.status == DecisionStatus.APPROVED
        assert res2.decided_at is not None

    def test_decision_rejection_flow(self, engine: ExecutiveDecisionEngine):
        dec = engine.propose_decision(
            title="Acquire Third-Party Logging Service",
            description="Purchase enterprise vendor license",
            proposer_role=ExecutiveRole.DIRECTOR_DEVOPS,
            required_signoffs=[ExecutiveRole.VP_ENGINEERING],
            budget_impact_usd=50000.0,
        )
        res = engine.signoff_decision(dec.decision_id, ExecutiveRole.VP_ENGINEERING, approved=False, notes="Cost exceeds target")
        assert res.status == DecisionStatus.REJECTED

    def test_executive_veto(self, engine: ExecutiveDecisionEngine):
        dec = engine.propose_decision(
            title="Disable MFA for Automated Load Tests",
            description="Bypass security for performance benchmarking",
            proposer_role=ExecutiveRole.DIRECTOR_QA,
            required_signoffs=[ExecutiveRole.VP_ENGINEERING],
        )
        vetoed = engine.veto_decision(
            dec.decision_id,
            veto_role=ExecutiveRole.DIRECTOR_SECURITY,
            reason="Violates SOC2 compliance and zero-trust policy",
        )
        assert vetoed.status == DecisionStatus.VETOED
        assert vetoed.veto_role == ExecutiveRole.DIRECTOR_SECURITY

    def test_budget_exceeded_auto_escalation(self, engine: ExecutiveDecisionEngine):
        # Director of Documentation authority is $150,000. Proposing $500,000 decision.
        dec = engine.propose_decision(
            title="Global Translation Retainer",
            description="Contract multi-language documentation agency",
            proposer_role=ExecutiveRole.DIRECTOR_DOCUMENTATION,
            required_signoffs=[ExecutiveRole.VP_PRODUCT],
            budget_impact_usd=500000.0,
        )
        # Required signoffs should auto-include CEO and DIRECTOR_FINANCE
        assert ExecutiveRole.CEO in dec.required_signoffs
        assert ExecutiveRole.DIRECTOR_FINANCE in dec.required_signoffs

    def test_strategic_goals_management(self, engine: ExecutiveDecisionEngine):
        goal = engine.create_strategic_goal(
            goal_id="GOAL-Q1-2026-01",
            title="Autonomous Enterprise Delivery",
            description="Deliver AutoDev Version 3.0",
            target_quarter="Q1",
            target_year=2026,
            owner_role=ExecutiveRole.CEO,
            target_metric="DORA_DEPLOY_PER_DAY",
            target_value=5.0,
        )
        assert goal.goal_id == "GOAL-Q1-2026-01"
        assert goal.progress_pct == 0.0

        engine.update_strategic_goal_progress("GOAL-Q1-2026-01", current_value=4.0)
        updated = engine.get_strategic_goal("GOAL-Q1-2026-01")
        assert updated.progress_pct == 80.0

    def test_list_decisions_by_status(self, engine: ExecutiveDecisionEngine):
        d1 = engine.propose_decision("D1", "Desc", ExecutiveRole.CEO, [ExecutiveRole.CTO])
        d2 = engine.propose_decision("D2", "Desc", ExecutiveRole.CEO, [ExecutiveRole.CTO])
        engine.signoff_decision(d1.decision_id, ExecutiveRole.CTO, approved=True)

        approved_list = engine.list_decisions(status=DecisionStatus.APPROVED)
        assert any(d.decision_id == d1.decision_id for d in approved_list)
        assert not any(d.decision_id == d2.decision_id for d in approved_list)
