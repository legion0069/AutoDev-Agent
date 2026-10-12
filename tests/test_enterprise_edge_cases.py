"""
test_enterprise_edge_cases.py - Boundary Conditions & Resilience Tests for Enterprise Subsystems (v3.0)
"""

import pytest
from core.enterprise import (
    ArchitectureBoard,
    ArchitectureScorecard,
    BusinessAnalytics,
    CompanyBrain,
    ComplianceStandard,
    DecisionStatus,
    DepartmentType,
    EngineeringManager,
    ExecutiveDecisionEngine,
    ExecutiveRole,
    ExpenseCategory,
    FinanceManager,
    GovernanceManager,
    HiringManager,
    KnowledgeCategory,
    OrganizationGraph,
    PriorityLevel,
    ProductFeature,
    ProductManager,
    ReleaseCandidate,
    ReleaseStage,
    ReleaseTrain,
    SprintManager,
    SprintState,
    StrategicGoal,
    SupportCenter,
    SupportTicket,
    TeamType,
    TicketPriority,
    TicketType,
    UserStory,
)


class TestEnterpriseEdgeCases:
    def test_zero_budget_and_infinite_runway(self):
        fm = FinanceManager(initial_cash_reserve_usd=1000000.0)
        # 0 spend should yield inf runway
        runway = fm.calculate_runway_months(monthly_burn_usd=0.0)
        assert runway == float("inf")

    def test_negative_roi_calculation(self):
        fm = FinanceManager()
        # Invest $100k, return $50k => -50.0% ROI
        roi = fm.calculate_roi(invested_cost_usd=100000.0, expected_revenue_or_savings_usd=50000.0)
        assert roi == -50.0

        # Invest 0 => 0.0% ROI
        roi_zero = fm.calculate_roi(0.0, 1000.0)
        assert roi_zero == 0.0

    def test_rice_score_zero_or_low_effort(self):
        feat = ProductFeature(
            feature_id="F-EDGE",
            epic_id="E-EDGE",
            name="Instant Feat",
            description="Feat with 0 effort",
            reach=1000,
            impact=2.0,
            confidence=0.8,
            effort=0.0,  # Handled safely by max(0.1, effort)
        )
        assert feat.rice_score == 16000.0

    def test_strategic_goal_zero_target(self):
        goal = StrategicGoal(
            goal_id="G-ZERO",
            title="Zero Target Goal",
            description="Edge test",
            target_quarter="Q1",
            target_value=0.0,
        )
        assert goal.progress_pct == 100.0

    def test_unknown_ticket_resolution_raises(self):
        support = SupportCenter()
        with pytest.raises(KeyError):
            support.resolve_ticket("NON_EXISTENT_TICK", "Resolution notes")

        with pytest.raises(KeyError):
            support.record_csat("NON_EXISTENT_TICK", 5)

    def test_csat_clamping(self):
        support = SupportCenter()
        ticket = support.submit_ticket("c1", TicketType.INQUIRY, TicketPriority.P3_LOW, "Title", "Desc")
        support.resolve_ticket(ticket.ticket_id, "Res", csat_score=10)  # should clamp to 5
        updated = support.get_ticket(ticket.ticket_id)
        assert updated.csat_score == 5

        support.record_csat(ticket.ticket_id, -3)  # should clamp to 1
        updated2 = support.get_ticket(ticket.ticket_id)
        assert updated2.csat_score == 1

    def test_empty_knowledge_search(self):
        brain = CompanyBrain()
        res = brain.search_knowledge(query="NON_EXISTENT_QUERY_XYZ_123")
        assert len(res) == 0

    def test_empty_sprint_velocity(self):
        sm = SprintManager()
        sprint = sm.plan_sprint("S-EMPTY", 1, "Empty Goal", candidate_stories=[])
        sm.start_sprint("S-EMPTY")
        completed = sm.complete_sprint("S-EMPTY")
        assert completed.velocity == 0.0

    def test_nonexistent_employee_review_raises(self):
        hm = HiringManager()
        with pytest.raises(KeyError):
            hm.conduct_performance_review("EMP_NON_EXISTENT", 4.5)

        with pytest.raises(KeyError):
            hm.promote_employee("EMP_NON_EXISTENT", "CEO")

    def test_dora_tier_low_for_excessive_failure_rate(self):
        analytics = BusinessAnalytics()
        analytics.record_deployment(lead_time_hours=200.0, success=False)
        analytics.record_deployment(lead_time_hours=200.0, success=False)
        dora = analytics.get_dora_metrics()
        assert dora.change_failure_rate_pct == 100.0
        assert dora.dora_tier == "LOW"

    def test_codeowners_non_matching_path_allows_any(self):
        gov = GovernanceManager()
        # docs/readme.md is not in protected codeowners map
        valid, required = gov.validate_codeowners("docs/readme.md", approving_roles=[])
        assert valid is True
        assert len(required) == 0
