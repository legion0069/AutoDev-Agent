"""
test_enterprise_extended_validation.py - Extended Autonomous Enterprise Validation Matrix (v3.0)
"""

import time
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


class TestExecutiveEscalationChains:
    @pytest.mark.parametrize("start_node,expected_ultimate_parent", [
        ("lead_backend", "emp_ceo"),
        ("lead_frontend", "emp_ceo"),
        ("lead_ai", "emp_ceo"),
        ("lead_sec", "emp_ceo"),
        ("emp_dirqa", "emp_ceo"),
        ("emp_dirdevops", "emp_ceo"),
        ("emp_cso", "emp_ceo"),
    ])
    def test_reporting_chain_up_to_ceo(self, start_node: str, expected_ultimate_parent: str):
        org = OrganizationGraph()
        chain = org.get_reporting_chain(start_node)
        assert len(chain) >= 2
        assert chain[0] == start_node
        assert chain[-1] == expected_ultimate_parent


class TestFinancialMultiQuarterLedger:
    def test_budget_creation_and_balance_tracking(self):
        fm = FinanceManager(initial_cash_reserve_usd=10000000.0)
        
        # Create Q1, Q2, Q3, Q4 budgets
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            budget = fm.create_quarterly_budget(
                quarter=q,
                year=2026,
                category_limits_usd={
                    ExpenseCategory.ENGINEERING_SALARIES.value: 1000000.0,
                    ExpenseCategory.INFRASTRUCTURE_CLOUD.value: 200000.0,
                    ExpenseCategory.LLM_API_TOKENS.value: 100000.0,
                },
            )
            assert budget.quarter == q
            assert budget.total_allocated_usd == 1300000.0

        # Spend in Q2
        fm.record_expense(
            category=ExpenseCategory.INFRASTRUCTURE_CLOUD,
            amount_usd=50000.0,
            description="Q2 Cloud Spend",
            department=DepartmentType.DEVOPS,
            quarter_key="2026-Q2",
        )
        q2_budget = fm.get_budget("2026-Q2")
        assert q2_budget.actual_spent_usd[ExpenseCategory.INFRASTRUCTURE_CLOUD.value] == 50000.0
        assert q2_budget.remaining_budget_usd == 1250000.0


class TestIncidentRCAWorkflow:
    @pytest.mark.parametrize("p_level", [TicketPriority.P0_CRITICAL, TicketPriority.P1_HIGH, TicketPriority.P2_MEDIUM])
    def test_incident_resolution_and_rca(self, p_level: TicketPriority):
        sc = SupportCenter()
        brain = CompanyBrain()

        ticket = sc.submit_ticket(
            customer_id="cust_incident_01",
            ticket_type=TicketType.INCIDENT,
            priority=p_level,
            title=f"Service degradation ({p_level.value})",
            description="Latency increased on authentication endpoint.",
        )
        assert ticket.status == "IN_ENGINEERING"

        # Resolve ticket with RCA
        resolved = sc.resolve_ticket(
            ticket.ticket_id,
            resolution_notes="Increased worker pool and enabled response caching",
            rca="Connection pool exhaustion under burst traffic",
            csat_score=5,
        )
        assert resolved.status == "RESOLVED"
        assert resolved.csat_score == 5

        # Store Postmortem in Brain
        postmortem = brain.store_knowledge(
            title=f"Postmortem: {ticket.ticket_id} {p_level.value}",
            category=KnowledgeCategory.POSTMORTEM,
            content=f"RCA: Connection pool exhaustion. Resolution: {resolved.description}",
            tags=["postmortem", p_level.value.lower(), "rca"],
            author="DevOps Lead",
            department=DepartmentType.DEVOPS,
        )
        assert postmortem.knowledge_id.startswith("KB-")


class TestCodeownersHierarchyValidation:
    @pytest.mark.parametrize("path,approver,should_pass", [
        ("core/enterprise/executive_engine.py", ExecutiveRole.CEO, True),
        ("core/enterprise/executive_engine.py", ExecutiveRole.CTO, True),
        ("core/enterprise/executive_engine.py", ExecutiveRole.DIRECTOR_QA, False),
        ("core/security/crypto.py", ExecutiveRole.DIRECTOR_SECURITY, True),
        ("core/security/crypto.py", ExecutiveRole.DIRECTOR_HR, False),
        ("core/finance/ledger.py", ExecutiveRole.DIRECTOR_FINANCE, True),
        ("core/finance/ledger.py", ExecutiveRole.DIRECTOR_DOCUMENTATION, False),
        ("core/cluster/worker.py", ExecutiveRole.DIRECTOR_PLATFORM, True),
        ("core/cluster/worker.py", ExecutiveRole.DIRECTOR_DEVOPS, True),
    ])
    def test_codeowners_policy_enforcement(self, path: str, approver: ExecutiveRole, should_pass: bool):
        gov = GovernanceManager()
        valid, _ = gov.validate_codeowners(file_path=path, approving_roles=[approver])
        assert valid == should_pass


class TestFullQuarterlyProgressionSimulation:
    def test_full_annual_progression(self):
        company = EnterpriseCompany(company_name="AutoDev Global Autonomous Corporation")
        res = company.simulator.simulate_year(2026)
        assert res["simulation_year"] == 2026
        assert len(res["quarters"]) == 4
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            assert q in res["quarters"]
            assert res["quarters"][q]["release"]["stage"] == "GENERAL_AVAILABILITY"

        overview = company.get_company_overview()
        assert overview["company_name"] == "AutoDev Global Autonomous Corporation"
        assert overview["total_spending_usd"] > 0
        assert overview["compliance_valid"] is True
