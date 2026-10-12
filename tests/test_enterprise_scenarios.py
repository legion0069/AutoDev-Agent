"""
test_enterprise_scenarios.py - Real-World Corporate Operational Scenarios (v3.0)
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
    EnterpriseCompany,
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
    SupportCenter,
    SupportTicket,
    TeamType,
    TicketPriority,
    TicketType,
    UserStory,
)


class TestEnterpriseScenarios:
    def test_emergency_security_hotfix_scenario(self):
        """
        Scenario: A critical CVE is discovered in the authentication token parser.
        Workflow:
        1. Support Center receives P0_CRITICAL ticket
        2. Auto-converts to Security Ops engineering task
        3. Security Director proposes emergency hotfix decision
        4. Architecture Board evaluates security scorecard
        5. Release Train creates HOTFIX candidate, passes gates, gathers CTO/CSO signoffs, and deploys.
        """
        company = EnterpriseCompany()

        # 1. Ingest P0 ticket
        ticket = company.support_center.submit_ticket(
            customer_id="enterprise_sec_team",
            ticket_type=TicketType.INCIDENT,
            priority=TicketPriority.P0_CRITICAL,
            title="CVE-2026-999: Auth Token Buffer Overrun",
            description="Buffer overrun in ECDSA signature parser requires immediate patch.",
            assigned_team=TeamType.SECURITY_OPS,
        )
        assert ticket.status == "IN_ENGINEERING"
        assert ticket.linked_engineering_task_id is not None

        # 2. Executive emergency decision
        dec = company.executive_engine.propose_decision(
            title="Authorize Emergency Hotfix Release 3.0.1",
            description="Immediate security deployment to patch CVE-2026-999",
            proposer_role=ExecutiveRole.DIRECTOR_SECURITY,
            required_signoffs=[ExecutiveRole.CTO, ExecutiveRole.DIRECTOR_SECURITY],
            risk_score=5.0,
        )
        company.executive_engine.signoff_decision(dec.decision_id, ExecutiveRole.CTO, approved=True)
        company.executive_engine.signoff_decision(dec.decision_id, ExecutiveRole.DIRECTOR_SECURITY, approved=True)

        # 3. Release Train hotfix
        hotfix_rc = company.release_train.create_release_candidate(
            target_version="3.0.1",
            stage=ReleaseStage.HOTFIX,
            bugs=["CVE-2026-999"],
        )
        company.release_train.set_gate_status(hotfix_rc.release_id, "security_scan_clean", True)
        company.release_train.signoff_release(hotfix_rc.release_id, ExecutiveRole.CTO)
        company.release_train.signoff_release(hotfix_rc.release_id, ExecutiveRole.DIRECTOR_SECURITY)

        deployed_hotfix = company.release_train.promote_to_general_availability(hotfix_rc.release_id)
        assert deployed_hotfix.version == "3.0.1"
        assert company.release_train.get_current_version() == "3.0.1"

        # 4. Resolve incident ticket
        company.support_center.resolve_ticket(
            ticket.ticket_id,
            resolution_notes="Hotfix 3.0.1 deployed to production cluster.",
            rca="Bounds checking flaw in signature parsing subroutine.",
            csat_score=5,
        )
        updated_ticket = company.support_center.get_ticket(ticket.ticket_id)
        assert updated_ticket.status == "RESOLVED"

    def test_quarterly_budget_burn_and_cost_optimization_scenario(self):
        """
        Scenario: High cloud and LLM spending threatens quarterly budget.
        Workflow:
        1. Record multiple operational expenses
        2. Finance Manager detects high cloud & LLM spend
        3. Generates automated cost optimization recommendations
        4. Director of Finance tracks ROI on optimization initiative.
        """
        finance = FinanceManager(initial_cash_reserve_usd=5000000.0)

        # Record heavy compute and LLM token expenses
        for m in range(3):
            finance.record_expense(ExpenseCategory.INFRASTRUCTURE_CLOUD, 80000.0, f"Month {m+1} Cloud", DepartmentType.DEVOPS)
            finance.record_expense(ExpenseCategory.LLM_API_TOKENS, 40000.0, f"Month {m+1} Tokens", DepartmentType.ENGINEERING)

        recs = finance.generate_cost_optimization_recommendations()
        assert len(recs) >= 2
        categories = [r["category"] for r in recs]
        assert ExpenseCategory.INFRASTRUCTURE_CLOUD.value in categories

        # Calculate ROI of optimization initiative (invest $10k in spot node automation, save $60k/quarter)
        roi = finance.calculate_roi(invested_cost_usd=10000.0, expected_revenue_or_savings_usd=60000.0)
        assert roi == 500.0

    def test_postmortem_and_institutional_knowledge_scenario(self):
        """
        Scenario: Production incident resolution generates an ADR and Postmortem in Company Brain.
        Workflow:
        1. Store postmortem in CompanyBrain
        2. Store updated architectural ADR
        3. Link ADR and Postmortem bidirectionally
        4. Verify cross-searchability.
        """
        brain = CompanyBrain()

        postmortem = brain.store_knowledge(
            title="Postmortem: High Memory Pressure on Master Node",
            category=KnowledgeCategory.POSTMORTEM,
            content="Task queue grew excessively due to slow worker heartbeats. Resolution: implemented task queue backpressure.",
            tags=["postmortem", "memory", "master_node", "backpressure"],
            author="Rachel Green (DevOps)",
            department=DepartmentType.DEVOPS,
        )

        adr = brain.store_knowledge(
            title="ADR-004: Adaptive Queue Backpressure & Rate Limiting",
            category=KnowledgeCategory.ARCHITECTURE_ADR,
            content="Master node rejects task submissions when memory exceeds 85% threshold.",
            tags=["adr", "architecture", "backpressure", "rate_limiting"],
            author="Marcus Vance (CTO)",
            department=DepartmentType.ARCHITECTURE,
        )

        brain.link_knowledge(postmortem.knowledge_id, adr.knowledge_id)

        related_to_pm = brain.get_related_knowledge(postmortem.knowledge_id)
        assert len(related_to_pm) == 1
        assert related_to_pm[0].title == adr.title

        related_to_adr = brain.get_related_knowledge(adr.knowledge_id)
        assert len(related_to_adr) == 1
        assert related_to_adr[0].title == postmortem.title
