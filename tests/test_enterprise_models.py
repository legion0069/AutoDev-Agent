"""
test_enterprise_models.py - Comprehensive Unit Tests for Enterprise Domain Models (v3.0)
"""

import pytest
from core.enterprise.enterprise_models import (
    AcceptanceCriteria,
    ArchProposal,
    ArchReviewStatus,
    ArchitectureScorecard,
    AuditLogRecord,
    CandidateProfile,
    ComplianceStandard,
    DecisionStatus,
    DepartmentType,
    EmployeeProfile,
    Epic,
    ExecutiveDecision,
    ExecutiveProfile,
    ExecutiveRole,
    ExpenseCategory,
    FinancialLedgerEntry,
    GovernancePolicy,
    JobPosting,
    KnowledgeCategory,
    KnowledgeItem,
    PriorityLevel,
    ProductFeature,
    ProductVision,
    QuarterlyBudget,
    ReleaseCandidate,
    ReleaseStage,
    SprintPlan,
    SprintState,
    StrategicGoal,
    SupportTicket,
    TeamType,
    TicketPriority,
    TicketType,
    UserStory,
)


class TestEnterpriseEnums:
    def test_executive_roles(self):
        roles = [r for r in ExecutiveRole]
        assert len(roles) == 15
        assert ExecutiveRole.CEO.value == "CEO"
        assert ExecutiveRole.CTO.value == "CTO"
        assert ExecutiveRole.VP_PRODUCT.value == "VP_PRODUCT"
        assert ExecutiveRole.VP_ENGINEERING.value == "VP_ENGINEERING"
        assert ExecutiveRole.DIRECTOR_QA.value == "DIRECTOR_QA"
        assert ExecutiveRole.DIRECTOR_SECURITY.value == "DIRECTOR_SECURITY"
        assert ExecutiveRole.LEGAL_COUNSEL.value == "LEGAL_COUNSEL"

    def test_department_types(self):
        depts = [d for d in DepartmentType]
        assert len(depts) >= 16
        assert DepartmentType.EXECUTIVE.value == "EXECUTIVE"
        assert DepartmentType.ENGINEERING.value == "ENGINEERING"
        assert DepartmentType.FINANCE.value == "FINANCE"
        assert DepartmentType.LEGAL.value == "LEGAL"

    def test_team_types(self):
        teams = [t for t in TeamType]
        assert len(teams) >= 8
        assert TeamType.BACKEND.value == "BACKEND"
        assert TeamType.AI_ML.value == "AI_ML"
        assert TeamType.QA_AUTOMATION.value == "QA_AUTOMATION"

    def test_decision_status(self):
        statuses = [s for s in DecisionStatus]
        assert DecisionStatus.PROPOSED.value == "PROPOSED"
        assert DecisionStatus.APPROVED.value == "APPROVED"
        assert DecisionStatus.VETOED.value == "VETOED"
        assert DecisionStatus.REJECTED.value == "REJECTED"


class TestExecutiveModels:
    def test_executive_profile_serialization(self):
        profile = ExecutiveProfile(
            role=ExecutiveRole.CEO,
            title="Chief Executive Officer",
            name="Elena Rostova",
            department=DepartmentType.EXECUTIVE,
            responsibilities=["Strategy", "Vision"],
            decision_authority=["ALL"],
            budget_authority_usd=5000000.0,
            risk_tolerance=0.7,
            strategic_priorities=["Scale AI Company"],
        )
        d = profile.to_dict()
        assert d["role"] == "CEO"
        assert d["department"] == "EXECUTIVE"
        assert d["budget_authority_usd"] == 5000000.0

        recovered = ExecutiveProfile.from_dict(d)
        assert recovered.role == ExecutiveRole.CEO
        assert recovered.name == "Elena Rostova"

    def test_executive_decision_serialization(self):
        dec = ExecutiveDecision(
            decision_id="DEC-001",
            title="Launch Version 3.0",
            description="Authorize production rollout",
            proposer_role=ExecutiveRole.CEO,
            required_signoffs=[ExecutiveRole.CTO, ExecutiveRole.VP_ENGINEERING],
            budget_impact_usd=100000.0,
        )
        d = dec.to_dict()
        assert d["decision_id"] == "DEC-001"
        assert d["proposer_role"] == "CEO"
        assert d["required_signoffs"] == ["CTO", "VP_ENGINEERING"]

        recovered = ExecutiveDecision.from_dict(d)
        assert recovered.decision_id == "DEC-001"
        assert recovered.proposer_role == ExecutiveRole.CEO
        assert recovered.required_signoffs == [ExecutiveRole.CTO, ExecutiveRole.VP_ENGINEERING]

    def test_strategic_goal_progress(self):
        goal = StrategicGoal(
            goal_id="GOAL-01",
            title="Achieve 10M ARR",
            description="Annual recurring revenue",
            target_quarter="Q4",
            target_metric="ARR_USD",
            target_value=10000000.0,
            current_value=7500000.0,
        )
        assert goal.progress_pct == 75.0
        d = goal.to_dict()
        assert d["progress_pct"] == 75.0


class TestProductModels:
    def test_acceptance_criteria(self):
        crit = AcceptanceCriteria(
            criterion_id="AC-01",
            given="a validated cluster configuration",
            when="invoking orchestrator",
            then="all tasks complete without exceptions",
        )
        d = crit.to_dict()
        assert d["given"] == "a validated cluster configuration"
        assert not d["verified"]

    def test_user_story_serialization(self):
        crit = AcceptanceCriteria("AC-1", "A", "B", "C")
        story = UserStory(
            story_id="US-101",
            feature_id="FEAT-01",
            title="Implement C-Suite Governance",
            user_role="Executive",
            action="review and approve decisions",
            benefit="maintain strict corporate governance",
            story_points=5,
            priority=PriorityLevel.HIGH,
            acceptance_criteria=[crit],
        )
        d = story.to_dict()
        assert d["story_id"] == "US-101"
        assert d["priority"] == "HIGH"
        assert len(d["acceptance_criteria"]) == 1

    def test_feature_rice_score(self):
        feature = ProductFeature(
            feature_id="FEAT-01",
            epic_id="EPIC-01",
            name="Autonomous Architecture Review",
            description="Automated SOLID and DDD validation",
            reach=2000,
            impact=3.0,
            confidence=0.8,
            effort=4.0,
        )
        # RICE = (2000 * 3.0 * 0.8) / 4.0 = 4800 / 4.0 = 1200.0
        assert feature.rice_score == 1200.0
        d = feature.to_dict()
        assert d["rice_score"] == 1200.0

    def test_epic_serialization(self):
        epic = Epic(
            epic_id="EPIC-01",
            title="Autonomous Enterprise Platform",
            description="V3.0 release epics",
            strategic_theme="Scale",
            estimated_roi_multiplier=4.2,
        )
        d = epic.to_dict()
        assert d["epic_id"] == "EPIC-01"
        assert d["estimated_roi_multiplier"] == 4.2


class TestArchitectureModels:
    def test_architecture_scorecard_calculation(self):
        card = ArchitectureScorecard(
            solid_score=100.0,
            ddd_score=100.0,
            layering_score=100.0,
            scalability_score=100.0,
            security_score=100.0,
            performance_score=100.0,
            maintainability_score=100.0,
            testability_score=100.0,
            complexity_penalty=0.0,
        )
        assert card.composite_architecture_score == 100.0

        penalized = ArchitectureScorecard(
            solid_score=90.0,
            ddd_score=90.0,
            layering_score=90.0,
            scalability_score=90.0,
            security_score=90.0,
            performance_score=90.0,
            maintainability_score=90.0,
            testability_score=90.0,
            complexity_penalty=20.0,
        )
        # base = 90.0, penalty = 20.0 * 0.2 = 4.0 => 86.0
        assert penalized.composite_architecture_score == 86.0

    def test_arch_proposal_serialization(self):
        prop = ArchProposal(
            proposal_id="PROP-01",
            title="Clean Architecture Refactoring",
            author="Marcus Vance",
            system_component="CoreEngine",
            changes_summary="Decouple presentation and domain layers",
            adr_markdown="# ADR-001\nDecoupled architecture.",
            review_status=ArchReviewStatus.APPROVED,
        )
        d = prop.to_dict()
        assert d["proposal_id"] == "PROP-01"
        assert d["review_status"] == "APPROVED"
        assert "composite_architecture_score" in d["scorecard"]


class TestFinanceModels:
    def test_quarterly_budget_spent_and_remaining(self):
        budget = QuarterlyBudget(
            quarter="Q1",
            year=2026,
            total_allocated_usd=1000000.0,
            category_limits_usd={"ENGINEERING_SALARIES": 600000.0, "INFRASTRUCTURE_CLOUD": 400000.0},
            actual_spent_usd={"ENGINEERING_SALARIES": 200000.0, "INFRASTRUCTURE_CLOUD": 150000.0},
        )
        assert budget.total_spent_usd == 350000.0
        assert budget.remaining_budget_usd == 650000.0
        d = budget.to_dict()
        assert d["total_spent_usd"] == 350000.0
        assert d["remaining_budget_usd"] == 650000.0

    def test_financial_ledger_entry(self):
        entry = FinancialLedgerEntry(
            entry_id="TX-01",
            category=ExpenseCategory.LLM_API_TOKENS,
            amount_usd=1500.50,
            description="OpenAI API token consumption",
            department=DepartmentType.ENGINEERING,
        )
        d = entry.to_dict()
        assert d["category"] == "LLM_API_TOKENS"
        assert d["department"] == "ENGINEERING"


class TestSupportModels:
    def test_support_ticket_serialization(self):
        ticket = SupportTicket(
            ticket_id="TICK-001",
            customer_id="cust_99",
            ticket_type=TicketType.BUG_REPORT,
            priority=TicketPriority.P1_HIGH,
            title="Login timeout on mobile",
            description="Users experiencing 504 gateway timeout",
            assigned_team=TeamType.MOBILE,
        )
        d = ticket.to_dict()
        assert d["ticket_type"] == "BUG_REPORT"
        assert d["priority"] == "P1_HIGH"
        assert d["assigned_team"] == "MOBILE"


class TestReleaseModels:
    def test_release_candidate_approval(self):
        rc = ReleaseCandidate(
            release_id="REL-3.0.0",
            version="3.0.0",
            stage=ReleaseStage.RELEASE_CANDIDATE,
            checklist_gates={
                "unit_tests_pass": True,
                "integration_tests_pass": True,
                "security_scan_clean": True,
                "performance_sla_met": True,
                "docs_updated": True,
                "executive_signoff": True,
            },
            approved_by=[ExecutiveRole.CTO, ExecutiveRole.VP_ENGINEERING],
        )
        assert rc.is_approved_for_ga is True

        # Incomplete gate
        rc.checklist_gates["unit_tests_pass"] = False
        assert rc.is_approved_for_ga is False

    def test_release_candidate_insufficient_signoffs(self):
        rc = ReleaseCandidate(
            release_id="REL-3.0.1",
            version="3.0.1",
            stage=ReleaseStage.RELEASE_CANDIDATE,
            approved_by=[ExecutiveRole.CTO],  # Needs at least 2
        )
        assert rc.is_approved_for_ga is False


class TestGovernanceModels:
    def test_governance_policy(self):
        pol = GovernancePolicy(
            policy_id="POL-SOC2",
            name="SOC2 Policy",
            standard=ComplianceStandard.SOC2_TYPE_II,
            rule_description="Two approvals required",
            mandatory_approvers=[ExecutiveRole.CTO, ExecutiveRole.DIRECTOR_SECURITY],
        )
        d = pol.to_dict()
        assert d["standard"] == "SOC2_TYPE_II"
        assert d["mandatory_approvers"] == ["CTO", "DIRECTOR_SECURITY"]

    def test_audit_log_record(self):
        rec = AuditLogRecord(
            record_id="AUD-01",
            action="DEPLOY_PRODUCTION",
            actor="Marcus Vance",
            target_entity="Release 3.0.0",
            department=DepartmentType.ARCHITECTURE,
            details={"version": "3.0.0"},
            sha256_hash="abc123hash",
        )
        d = rec.to_dict()
        assert d["department"] == "ARCHITECTURE"
        assert d["action"] == "DEPLOY_PRODUCTION"


class TestKnowledgeModels:
    def test_knowledge_item_serialization(self):
        item = KnowledgeItem(
            knowledge_id="KB-001",
            title="Cluster Architecture Specs",
            category=KnowledgeCategory.ARCHITECTURE_ADR,
            content="Detailed distributed cluster specification.",
            tags=["cluster", "distributed", "v2.9"],
            author="David Kim",
            source_department=DepartmentType.ENGINEERING,
        )
        d = item.to_dict()
        assert d["category"] == "ARCHITECTURE_ADR"
        assert d["source_department"] == "ENGINEERING"
        assert "cluster" in d["tags"]
