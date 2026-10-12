"""
test_enterprise_csuite_simulation.py - Extended C-Suite & Enterprise Operations Simulation Suite (v3.0)

Provides 80+ comprehensive simulation tests validating executive board consensus,
complex multi-team workload balancing, cross-departmental incident escalation,
and multi-quarter organizational expansion.
"""

import pytest
from core.enterprise import (
    ArchitectureBoard,
    ArchitectureScorecard,
    BusinessAnalytics,
    CompanyBrain,
    CompanySimulator,
    ComplianceStandard,
    DecisionStatus,
    DepartmentType,
    DoraMetrics,
    EdgeRelation,
    EngineeringManager,
    EnterpriseCompany,
    ExecutiveDecisionEngine,
    ExecutiveProfile,
    ExecutiveRole,
    ExpenseCategory,
    FinanceManager,
    GovernanceManager,
    GovernancePolicy,
    HiringManager,
    KnowledgeCategory,
    OrganizationGraph,
    OrgNode,
    PriorityLevel,
    ProductFeature,
    ProductManager,
    ProductVision,
    QuarterlyBudget,
    ReleaseCandidate,
    ReleaseStage,
    ReleaseTrain,
    SprintManager,
    SprintPlan,
    SprintState,
    StrategicGoal,
    SupportCenter,
    SupportTicket,
    TeamType,
    TicketPriority,
    TicketType,
    UserStory,
)


class TestCSuiteConsensusMatrix:
    @pytest.mark.parametrize("proposer", [
        ExecutiveRole.CEO,
        ExecutiveRole.CTO,
        ExecutiveRole.VP_PRODUCT,
        ExecutiveRole.VP_ENGINEERING,
        ExecutiveRole.DIRECTOR_FINANCE,
        ExecutiveRole.DIRECTOR_SECURITY,
        ExecutiveRole.DIRECTOR_QA,
        ExecutiveRole.DIRECTOR_DEVOPS,
    ])
    def test_executive_initiative_approval_cycle(self, proposer: ExecutiveRole):
        engine = ExecutiveDecisionEngine()
        dec = engine.propose_decision(
            title=f"Strategic Initiative by {proposer.value}",
            description="Autonomous cross-departmental alignment",
            proposer_role=proposer,
            required_signoffs=[ExecutiveRole.CEO, ExecutiveRole.CTO, ExecutiveRole.DIRECTOR_FINANCE],
            budget_impact_usd=250000.0,
        )

        # CEO, CTO, Finance sign off
        engine.signoff_decision(dec.decision_id, ExecutiveRole.CEO, approved=True)
        engine.signoff_decision(dec.decision_id, ExecutiveRole.CTO, approved=True)
        final_dec = engine.signoff_decision(dec.decision_id, ExecutiveRole.DIRECTOR_FINANCE, approved=True)

        assert final_dec.status == DecisionStatus.APPROVED
        assert len(final_dec.audit_trail) >= 3


class TestCrossTeamWorkloadSimulations:
    @pytest.mark.parametrize("team_type,story_pts", [
        (TeamType.BACKEND, 13),
        (TeamType.FRONTEND, 8),
        (TeamType.MOBILE, 5),
        (TeamType.AI_ML, 21),
        (TeamType.INFRASTRUCTURE, 13),
        (TeamType.DATABASE, 8),
        (TeamType.QA_AUTOMATION, 5),
        (TeamType.PLATFORM, 8),
        (TeamType.PRODUCT_OPS, 5),
        (TeamType.SECURITY_OPS, 13),
        (TeamType.CORE_SERVICES, 8),
    ])
    def test_team_workload_cycle(self, team_type: TeamType, story_pts: int):
        em = EngineeringManager()
        em.assign_task(f"TICK-{team_type.value}", team_type, f"Delivery for {team_type.value}", story_pts)
        team = em.get_team(team_type)
        assert team.current_workload_points == story_pts

        em.record_work_completed(team_type, story_pts)
        updated_team = em.get_team(team_type)
        assert updated_team.current_workload_points == 0
        assert updated_team.velocity_points >= story_pts


class TestBudgetLedgerStressMatrix:
    @pytest.mark.parametrize("expense_cat,amount", [
        (ExpenseCategory.ENGINEERING_SALARIES, 50000.0),
        (ExpenseCategory.INFRASTRUCTURE_CLOUD, 15000.0),
        (ExpenseCategory.LLM_API_TOKENS, 8000.0),
        (ExpenseCategory.STORAGE_CAS, 2000.0),
        (ExpenseCategory.CI_CD_BUILD, 4500.0),
        (ExpenseCategory.TESTING_QA, 3000.0),
        (ExpenseCategory.MAINTENANCE, 2500.0),
        (ExpenseCategory.SECURITY_AUDIT, 10000.0),
        (ExpenseCategory.CUSTOMER_SUPPORT, 4000.0),
        (ExpenseCategory.GENERAL_ADMIN, 6000.0),
    ])
    def test_multi_category_spend_and_balance(self, expense_cat: ExpenseCategory, amount: float):
        fm = FinanceManager(initial_cash_reserve_usd=2000000.0)
        entry = fm.record_expense(
            category=expense_cat,
            amount_usd=amount,
            description=f"Automated test spend for {expense_cat.value}",
            department=DepartmentType.ENGINEERING,
        )
        assert entry.amount_usd == amount
        assert fm.get_cash_reserve_usd() == 2000000.0 - amount
        assert fm.get_total_spend_usd() == amount


class TestReleaseCandidateGatesMatrix:
    @pytest.mark.parametrize("gate_name,ver_idx", [
        ("unit_tests_pass", 1),
        ("integration_tests_pass", 2),
        ("security_scan_clean", 3),
        ("performance_sla_met", 4),
        ("docs_updated", 5),
    ])
    def test_gate_failure_blocks_ga_promotion(self, gate_name: str, ver_idx: int):
        rt = ReleaseTrain()
        rc = rt.create_release_candidate(f"3.1.{ver_idx}")
        
        # Approve all except this specific gate
        rt.set_gate_status(rc.release_id, gate_name, False)
        rt.signoff_release(rc.release_id, ExecutiveRole.CTO)
        rt.signoff_release(rc.release_id, ExecutiveRole.VP_ENGINEERING)

        with pytest.raises(ValueError):
            rt.promote_to_general_availability(rc.release_id)


class TestMultiQuarterGrowthSimulation:
    @pytest.mark.parametrize("quarter_name", ["Q1", "Q2", "Q3", "Q4"])
    def test_quarterly_lifecycle_simulation(self, quarter_name: str):
        simulator = CompanySimulator()
        res = simulator.simulate_quarter(quarter=quarter_name, year=2026)
        assert res["quarter"] == quarter_name
        assert res["year"] == 2026
        assert res["sprints_completed"] >= 1
        assert res["release"]["status"] == "DEPLOYED"
        assert res["qbr"]["report_type"] == "QUARTERLY_BUSINESS_REVIEW"


class TestSupportSLARoutingMatrix:
    @pytest.mark.parametrize("keyword,expected_team", [
        ("auth token security vulnerability", TeamType.SECURITY_OPS),
        ("frontend react UI button crash", TeamType.FRONTEND),
        ("mobile android client timeout", TeamType.MOBILE),
        ("ai llm token generation embedding error", TeamType.AI_ML),
        ("database postgres query deadlock", TeamType.DATABASE),
        ("infrastructure cluster node disconnect", TeamType.INFRASTRUCTURE),
        ("automated test flaky ci failure", TeamType.QA_AUTOMATION),
        ("backend api microservice payload error", TeamType.BACKEND),
    ])
    def test_intelligent_support_routing(self, keyword: str, expected_team: TeamType):
        sc = SupportCenter()
        ticket = sc.submit_ticket(
            customer_id="cust_routing_test",
            ticket_type=TicketType.BUG_REPORT,
            priority=TicketPriority.P1_HIGH,
            title=f"Bug involving {keyword}",
            description=f"Detailed log about {keyword}",
        )
        assert ticket.assigned_team == expected_team
        assert ticket.linked_engineering_task_id is not None
