"""
test_enterprise_deep_suites.py - Deep Parameterized Enterprise Test Matrix for AutoDev (v3.0)

Extends enterprise test coverage across all 15 executive roles, 16 departments, 8 engineering teams,
10 knowledge categories, 10 financial categories, RICE scoring matrix, architecture sensitivity analysis,
and compliance policy checks.
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
    DoraMetrics,
    EdgeRelation,
    EngineeringManager,
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


class TestExecutiveRoleAuthorityMatrix:
    @pytest.mark.parametrize("role", list(ExecutiveRole))
    def test_executive_role_registration_and_retrieval(self, role: ExecutiveRole):
        engine = ExecutiveDecisionEngine()
        exec_profile = engine.get_executive(role)
        assert exec_profile is not None
        assert exec_profile.role == role
        assert exec_profile.budget_authority_usd > 0
        assert 0.0 <= exec_profile.risk_tolerance <= 1.0
        assert len(exec_profile.responsibilities) > 0


class TestDepartmentMatrix:
    @pytest.mark.parametrize("dept", list(DepartmentType))
    def test_department_expense_accounting(self, dept: DepartmentType):
        fm = FinanceManager()
        entry = fm.record_expense(
            category=ExpenseCategory.GENERAL_ADMIN,
            amount_usd=1500.0,
            description=f"Operational admin for {dept.value}",
            department=dept,
        )
        assert entry.department == dept
        dept_spending = fm.get_spending_by_department()
        assert dept_spending[dept.value] >= 1500.0


class TestEngineeringTeamsMatrix:
    @pytest.mark.parametrize("team_type", list(TeamType))
    def test_team_task_allocation_and_capacity(self, team_type: TeamType):
        em = EngineeringManager()
        t = em.get_team(team_type)
        assert t is not None
        assert t.team_type == team_type

        # Assign task
        task = em.assign_task(f"TASK-{team_type.value}", team_type, f"Core work for {team_type.value}", story_points=5)
        assert task["team"] == team_type.value
        updated_t = em.get_team(team_type)
        assert updated_t.current_workload_points == 5


class TestKnowledgeCategoriesMatrix:
    @pytest.mark.parametrize("category", list(KnowledgeCategory))
    def test_knowledge_category_storage_and_filter(self, category: KnowledgeCategory):
        brain = CompanyBrain()
        item = brain.store_knowledge(
            title=f"Standard Doc for {category.value}",
            category=category,
            content=f"Comprehensive documentation and details for {category.value}.",
            tags=["matrix_test", category.value.lower()],
            author="System Test Runner",
            department=DepartmentType.EXECUTIVE,
        )
        assert item.category == category

        results = brain.search_knowledge(category=category)
        assert len(results) >= 1
        assert any(r.knowledge_id == item.knowledge_id for r in results)


class TestFinancialExpenseCategoriesMatrix:
    @pytest.mark.parametrize("cat", list(ExpenseCategory))
    def test_expense_category_ledger_recording(self, cat: ExpenseCategory):
        fm = FinanceManager()
        entry = fm.record_expense(
            category=cat,
            amount_usd=2500.0,
            description=f"Ledger entry for {cat.value}",
            department=DepartmentType.ENGINEERING,
        )
        assert entry.category == cat
        cat_spending = fm.get_spending_by_category()
        assert cat_spending[cat.value] >= 2500.0


class TestTicketPrioritiesAndSLAs:
    @pytest.mark.parametrize("priority,expected_sla_hours", [
        (TicketPriority.P0_CRITICAL, 1),
        (TicketPriority.P1_HIGH, 4),
        (TicketPriority.P2_MEDIUM, 24),
        (TicketPriority.P3_LOW, 72),
    ])
    def test_ticket_priority_sla_duration(self, priority: TicketPriority, expected_sla_hours: int):
        support = SupportCenter()
        ticket = support.submit_ticket(
            customer_id="cust_sla",
            ticket_type=TicketType.BUG_REPORT,
            priority=priority,
            title="SLA Test",
            description="Testing SLA durations",
        )
        expected_seconds = expected_sla_hours * 3600
        actual_duration = ticket.sla_deadline - ticket.created_at
        assert abs(actual_duration - expected_seconds) < 5.0


class TestReleaseStagesMatrix:
    @pytest.mark.parametrize("stage", list(ReleaseStage))
    def test_release_stage_creation(self, stage: ReleaseStage):
        rt = ReleaseTrain()
        rc = rt.create_release_candidate(f"3.0.{list(ReleaseStage).index(stage)}", stage=stage)
        assert rc.stage == stage
        assert rc.status == "STAGED"


class TestComplianceStandardsMatrix:
    @pytest.mark.parametrize("standard", list(ComplianceStandard))
    def test_compliance_standard_policy_registration(self, standard: ComplianceStandard):
        gov = GovernanceManager()
        policy = GovernancePolicy(
            policy_id=f"POL-{standard.value}",
            name=f"Policy for {standard.value}",
            standard=standard,
            rule_description="Strict compliance mandate",
            mandatory_approvers=[ExecutiveRole.CTO, ExecutiveRole.DIRECTOR_SECURITY],
        )
        gov.register_policy(policy)
        report = gov.generate_compliance_report()
        assert any(p["standard"] == standard.value for p in report["policies"])


class TestRiceScoringVariations:
    @pytest.mark.parametrize("reach,impact,confidence,effort,expected_rice", [
        (1000, 3.0, 1.0, 5.0, 600.0),
        (5000, 2.0, 0.8, 10.0, 800.0),
        (10000, 1.0, 0.5, 2.0, 2500.0),
        (500, 0.5, 0.9, 1.0, 225.0),
        (20000, 3.0, 0.95, 4.0, 14250.0),
        (100, 1.0, 1.0, 10.0, 10.0),
        (50000, 2.5, 0.7, 8.0, 10937.5),
        (300, 3.0, 0.6, 3.0, 180.0),
    ])
    def test_rice_formula_precision(self, reach, impact, confidence, effort, expected_rice):
        feat = ProductFeature(
            feature_id="F-RICE",
            epic_id="E-RICE",
            name="RICE Test Feat",
            description="Testing RICE mathematical precision",
            reach=reach,
            impact=impact,
            confidence=confidence,
            effort=effort,
        )
        assert abs(feat.rice_score - expected_rice) < 0.01


class TestArchitectureScorecardSensitivity:
    @pytest.mark.parametrize("solid,ddd,layering,scalability,security,penalty,min_expected", [
        (100, 100, 100, 100, 100, 0, 100.0),
        (90, 90, 90, 90, 90, 0, 90.0),
        (90, 90, 90, 90, 90, 20, 86.0),
        (80, 80, 80, 80, 80, 0, 80.0),
        (70, 70, 70, 70, 70, 10, 68.0),
        (95, 90, 95, 90, 95, 5, 90.0),
        (60, 60, 60, 60, 60, 0, 60.0),
    ])
    def test_scorecard_sensitivity(self, solid, ddd, layering, scalability, security, penalty, min_expected):
        card = ArchitectureScorecard(
            solid_score=float(solid),
            ddd_score=float(ddd),
            layering_score=float(layering),
            scalability_score=float(scalability),
            security_score=float(security),
            performance_score=float(solid),
            maintainability_score=float(solid),
            complexity_penalty=float(penalty),
            testability_score=float(solid),
        )
        assert card.composite_architecture_score >= min_expected - 0.1


class TestDoraTierPermutations:
    @pytest.mark.parametrize("freq,lead_h,mttr_m,cfr_pct,expected_tier", [
        (5.0, 2.0, 15.0, 2.0, "ELITE"),
        (1.5, 12.0, 45.0, 4.5, "ELITE"),
        (0.5, 48.0, 120.0, 10.0, "HIGH"),
        (0.1, 200.0, 500.0, 25.0, "MEDIUM"),
        (0.01, 500.0, 2000.0, 50.0, "LOW"),
    ])
    def test_dora_tier_classification(self, freq, lead_h, mttr_m, cfr_pct, expected_tier):
        dora = DoraMetrics(
            deployment_frequency_per_day=freq,
            lead_time_for_changes_hours=lead_h,
            mean_time_to_recovery_minutes=mttr_m,
            change_failure_rate_pct=cfr_pct,
        )
        assert dora.dora_tier == expected_tier
