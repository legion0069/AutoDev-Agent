"""
core.enterprise - Autonomous Enterprise Organization & Corporate Governance Package (AutoDev v3.0)

Exports all corporate subsystems:
- Executive Decision Engine (C-Suite Governance)
- Organization Graph (Hierarchy & Routing)
- Product Management Engine (Vision, Epics, Features, User Stories, RICE)
- Sprint & Agile Management (Sprints, Burndown, Retros, Standups)
- Architecture Review Board (SOLID, DDD, Scalability, Architecture Scorecard)
- Engineering Department (8 Specialized Teams, Workload Balancing)
- HR & Talent Engine (Headcount, Candidate Scoring, Offers, Performance Reviews)
- Financial Operations (Budgets, Ledgers, Runway, ROI, Cost Optimization)
- Customer Support Center (P0-P3 Tickets, SLAs, RCA, CSAT, Auto Bug Tasks)
- Business & DORA Analytics (Deployment Frequency, Lead Time, MTTR, Change Failure Rate)
- Executive Business Intelligence Dashboard (Daily, Weekly, QBR Scorecards)
- Release Train (Alpha, Beta, RC, GA, Hotfix, SemVer, Quality Gates)
- Corporate Governance & Compliance (SOC2, GDPR, ISO27001, SHA-256 Audit Trail)
- Company Knowledge Brain (10 Institutional Knowledge Categories)
- Company Simulation Engine (Workday, Sprint, Release, Quarter, Year)
- Enterprise Company Master Orchestrator
"""

from core.enterprise.architecture_board import ArchitectureBoard
from core.enterprise.business_analytics import BusinessAnalytics, DoraMetrics, ProductUsageMetrics
from core.enterprise.company_brain import CompanyBrain
from core.enterprise.company_simulator import CompanySimulator
from core.enterprise.engineering_manager import EngineeringManager, EngineeringTeam
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
from core.enterprise.enterprise_orchestrator import EnterpriseCompany
from core.enterprise.executive_dashboard import ExecutiveDashboard
from core.enterprise.executive_engine import ExecutiveDecisionEngine
from core.enterprise.finance_manager import FinanceManager
from core.enterprise.governance_manager import GovernanceManager
from core.enterprise.hiring_manager import HiringManager
from core.enterprise.organization_graph import EdgeRelation, OrgEdge, OrganizationGraph, OrgNode
from core.enterprise.product_manager import ProductManager
from core.enterprise.release_train import ReleaseTrain
from core.enterprise.sprint_manager import SprintManager
from core.enterprise.support_center import SupportCenter

__all__ = [
    # Master Orchestrator & Simulator
    "EnterpriseCompany",
    "CompanySimulator",
    # Subsystems
    "ExecutiveDecisionEngine",
    "OrganizationGraph",
    "ProductManager",
    "SprintManager",
    "ArchitectureBoard",
    "EngineeringManager",
    "EngineeringTeam",
    "HiringManager",
    "FinanceManager",
    "SupportCenter",
    "BusinessAnalytics",
    "DoraMetrics",
    "ProductUsageMetrics",
    "ExecutiveDashboard",
    "ReleaseTrain",
    "GovernanceManager",
    "CompanyBrain",
    # Graph & Node structures
    "OrgNode",
    "OrgEdge",
    "EdgeRelation",
    # Enums
    "ExecutiveRole",
    "DecisionStatus",
    "DepartmentType",
    "TeamType",
    "PriorityLevel",
    "SprintState",
    "ArchReviewStatus",
    "ExpenseCategory",
    "TicketPriority",
    "TicketType",
    "ReleaseStage",
    "ComplianceStandard",
    "KnowledgeCategory",
    # Data Models
    "ExecutiveProfile",
    "ExecutiveDecision",
    "StrategicGoal",
    "ProductVision",
    "Epic",
    "ProductFeature",
    "UserStory",
    "AcceptanceCriteria",
    "SprintPlan",
    "ArchitectureScorecard",
    "ArchProposal",
    "JobPosting",
    "CandidateProfile",
    "EmployeeProfile",
    "FinancialLedgerEntry",
    "QuarterlyBudget",
    "SupportTicket",
    "ReleaseCandidate",
    "GovernancePolicy",
    "AuditLogRecord",
    "KnowledgeItem",
]
