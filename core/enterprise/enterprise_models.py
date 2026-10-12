"""
enterprise_models.py - Enterprise Domain Models & Data Contracts for AutoDev (v3.0)

Defines data contracts, enumerations, DTOs, and schemas across all corporate departments
including Executive, Product, Sprint, Architecture, Engineering, HR, Finance, Support,
Analytics, Release Train, Governance, Company Brain, and Simulation.
"""

from __future__ import annotations

import copy
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# 1. Executive & Governance Enums
# ---------------------------------------------------------------------------

class ExecutiveRole(str, Enum):
    CEO = "CEO"
    CTO = "CTO"
    VP_ENGINEERING = "VP_ENGINEERING"
    VP_PRODUCT = "VP_PRODUCT"
    DIRECTOR_ENGINEERING = "DIRECTOR_ENGINEERING"
    DIRECTOR_QA = "DIRECTOR_QA"
    DIRECTOR_SECURITY = "DIRECTOR_SECURITY"
    DIRECTOR_PLATFORM = "DIRECTOR_PLATFORM"
    DIRECTOR_DEVOPS = "DIRECTOR_DEVOPS"
    DIRECTOR_DOCUMENTATION = "DIRECTOR_DOCUMENTATION"
    DIRECTOR_CUSTOMER_SUCCESS = "DIRECTOR_CUSTOMER_SUCCESS"
    DIRECTOR_ANALYTICS = "DIRECTOR_ANALYTICS"
    DIRECTOR_FINANCE = "DIRECTOR_FINANCE"
    DIRECTOR_HR = "DIRECTOR_HR"
    LEGAL_COUNSEL = "LEGAL_COUNSEL"


class DecisionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    CONDITIONALLY_APPROVED = "CONDITIONALLY_APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    VETOED = "VETOED"
    EXECUTED = "EXECUTED"


class DepartmentType(str, Enum):
    EXECUTIVE = "EXECUTIVE"
    PRODUCT = "PRODUCT"
    ENGINEERING = "ENGINEERING"
    QA = "QA"
    DEVOPS = "DEVOPS"
    SECURITY = "SECURITY"
    ARCHITECTURE = "ARCHITECTURE"
    DESIGN = "DESIGN"
    DOCUMENTATION = "DOCUMENTATION"
    MARKETING = "MARKETING"
    SALES_ENGINEERING = "SALES_ENGINEERING"
    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    FINANCE = "FINANCE"
    ANALYTICS = "ANALYTICS"
    HR = "HR"
    LEGAL = "LEGAL"


class TeamType(str, Enum):
    BACKEND = "BACKEND"
    FRONTEND = "FRONTEND"
    MOBILE = "MOBILE"
    AI_ML = "AI_ML"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    DATABASE = "DATABASE"
    QA_AUTOMATION = "QA_AUTOMATION"
    PLATFORM = "PLATFORM"
    PRODUCT_OPS = "PRODUCT_OPS"
    SECURITY_OPS = "SECURITY_OPS"
    CORE_SERVICES = "CORE_SERVICES"


# ---------------------------------------------------------------------------
# 2. Executive Decision Engine Models
# ---------------------------------------------------------------------------

@dataclass
class ExecutiveProfile:
    role: ExecutiveRole
    title: str
    name: str
    department: DepartmentType
    responsibilities: List[str]
    decision_authority: List[str]
    budget_authority_usd: float
    risk_tolerance: float  # 0.0 (Risk Averse) - 1.0 (Aggressive)
    strategic_priorities: List[str]
    kpis: Dict[str, float] = field(default_factory=dict)
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["role"] = self.role.value
        d["department"] = self.department.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutiveProfile:
        d = dict(data)
        d["role"] = ExecutiveRole(d["role"]) if isinstance(d["role"], str) else d["role"]
        d["department"] = DepartmentType(d["department"]) if isinstance(d["department"], str) else d["department"]
        return cls(**d)


@dataclass
class ExecutiveDecision:
    decision_id: str
    title: str
    description: str
    proposer_role: ExecutiveRole
    required_signoffs: List[ExecutiveRole]
    signoffs_received: Dict[str, bool] = field(default_factory=dict)  # role -> approved
    veto_role: Optional[ExecutiveRole] = None
    status: DecisionStatus = DecisionStatus.PROPOSED
    budget_impact_usd: float = 0.0
    strategic_alignment_score: float = 100.0  # 0-100
    risk_score: float = 10.0                 # 0-100
    rationale: str = ""
    created_at: float = field(default_factory=time.time)
    decided_at: Optional[float] = None
    conditions: List[str] = field(default_factory=list)
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["proposer_role"] = self.proposer_role.value
        d["required_signoffs"] = [r.value for r in self.required_signoffs]
        d["veto_role"] = self.veto_role.value if self.veto_role else None
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutiveDecision:
        d = dict(data)
        d["proposer_role"] = ExecutiveRole(d["proposer_role"]) if isinstance(d["proposer_role"], str) else d["proposer_role"]
        d["required_signoffs"] = [ExecutiveRole(r) if isinstance(r, str) else r for r in d.get("required_signoffs", [])]
        d["veto_role"] = ExecutiveRole(d["veto_role"]) if d.get("veto_role") else None
        d["status"] = DecisionStatus(d["status"]) if isinstance(d["status"], str) else d["status"]
        return cls(**d)


@dataclass
class StrategicGoal:
    goal_id: str
    title: str
    description: str
    target_quarter: str  # e.g. "Q1", "Q2", "Q3", "Q4"
    target_year: int = 2026
    owner_role: ExecutiveRole = ExecutiveRole.CEO
    target_metric: str = "ARR_USD"
    target_value: float = 1000000.0
    current_value: float = 0.0
    status: str = "IN_PROGRESS"

    @property
    def progress_pct(self) -> float:
        if self.target_value == 0:
            return 100.0
        return min(100.0, max(0.0, (self.current_value / self.target_value) * 100.0))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["owner_role"] = self.owner_role.value
        d["progress_pct"] = round(self.progress_pct, 2)
        return d


# ---------------------------------------------------------------------------
# 3. Product Management Models
# ---------------------------------------------------------------------------

class PriorityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class AcceptanceCriteria:
    criterion_id: str
    given: str
    when: str
    then: str
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UserStory:
    story_id: str
    feature_id: str
    title: str
    user_role: str        # "As a <role>"
    action: str           # "I want to <action>"
    benefit: str          # "So that <benefit>"
    story_points: int = 3
    priority: PriorityLevel = PriorityLevel.MEDIUM
    acceptance_criteria: List[AcceptanceCriteria] = field(default_factory=list)
    engineering_tasks: List[str] = field(default_factory=list)
    status: str = "BACKLOG"  # BACKLOG, SPRINT_BACKLOG, IN_PROGRESS, IN_REVIEW, DONE

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["priority"] = self.priority.value
        d["acceptance_criteria"] = [c.to_dict() for c in self.acceptance_criteria]
        return d


@dataclass
class ProductFeature:
    feature_id: str
    epic_id: str
    name: str
    description: str
    business_value: float = 100.0
    reach: int = 1000          # RICE Reach
    impact: float = 2.0        # RICE Impact (0.5 to 3.0)
    confidence: float = 0.8    # RICE Confidence (0.0 to 1.0)
    effort: float = 5.0        # RICE Effort (story points or weeks)
    user_stories: List[UserStory] = field(default_factory=list)
    target_release: str = "v1.0.0"
    dependencies: List[str] = field(default_factory=list)
    status: str = "PLANNED"

    @property
    def rice_score(self) -> float:
        eff = max(0.1, self.effort)
        return (self.reach * self.impact * self.confidence) / eff

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["rice_score"] = round(self.rice_score, 2)
        d["user_stories"] = [s.to_dict() for s in self.user_stories]
        return d


@dataclass
class Epic:
    epic_id: str
    title: str
    description: str
    strategic_theme: str
    target_quarter: str = "Q1"
    features: List[ProductFeature] = field(default_factory=list)
    estimated_roi_multiplier: float = 3.5
    status: str = "IN_PROGRESS"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["features"] = [f.to_dict() for f in self.features]
        return d


@dataclass
class ProductVision:
    vision_statement: str
    target_market: str
    value_proposition: str
    key_differentiators: List[str]
    success_metrics: Dict[str, str] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 4. Sprint & Agile Management Models
# ---------------------------------------------------------------------------

class SprintState(str, Enum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass
class SprintPlan:
    sprint_id: str
    sprint_number: int
    goal: str
    start_date: float
    end_date: float
    capacity_points: int = 40
    committed_points: int = 0
    completed_points: int = 0
    state: SprintState = SprintState.PLANNING
    stories: List[UserStory] = field(default_factory=list)
    carried_over_stories: List[str] = field(default_factory=list)
    daily_burndown: List[Dict[str, Any]] = field(default_factory=list)
    retrospective_notes: List[str] = field(default_factory=list)

    @property
    def velocity(self) -> float:
        return float(self.completed_points)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        d["stories"] = [s.to_dict() for s in self.stories]
        d["velocity"] = self.velocity
        return d


# ---------------------------------------------------------------------------
# 5. Architecture Board Models
# ---------------------------------------------------------------------------

class ArchReviewStatus(str, Enum):
    APPROVED = "APPROVED"
    CONDITIONALLY_APPROVED = "CONDITIONALLY_APPROVED"
    REJECTED = "REJECTED"
    REVISE_AND_RESUBMIT = "REVISE_AND_RESUBMIT"


@dataclass
class ArchitectureScorecard:
    solid_score: float = 90.0        # 0-100
    ddd_score: float = 85.0          # 0-100
    layering_score: float = 95.0     # 0-100
    scalability_score: float = 90.0  # 0-100
    security_score: float = 95.0     # 0-100
    performance_score: float = 88.0  # 0-100
    maintainability_score: float = 92.0 # 0-100
    complexity_penalty: float = 10.0 # 0-100
    testability_score: float = 90.0  # 0-100

    @property
    def composite_architecture_score(self) -> float:
        base = (
            self.solid_score * 0.15 +
            self.ddd_score * 0.10 +
            self.layering_score * 0.15 +
            self.scalability_score * 0.15 +
            self.security_score * 0.15 +
            self.performance_score * 0.10 +
            self.maintainability_score * 0.10 +
            self.testability_score * 0.10
        )
        final_score = max(0.0, min(100.0, base - (self.complexity_penalty * 0.2)))
        return round(final_score, 2)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["composite_architecture_score"] = self.composite_architecture_score
        return d


@dataclass
class ArchProposal:
    proposal_id: str
    title: str
    author: str
    system_component: str
    changes_summary: str
    adr_markdown: str
    scorecard: ArchitectureScorecard = field(default_factory=ArchitectureScorecard)
    review_status: ArchReviewStatus = ArchReviewStatus.APPROVED
    review_feedback: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["scorecard"] = self.scorecard.to_dict()
        d["review_status"] = self.review_status.value
        return d


# ---------------------------------------------------------------------------
# 6. HR & Hiring Models
# ---------------------------------------------------------------------------

@dataclass
class JobPosting:
    job_id: str
    title: str
    department: DepartmentType
    team: TeamType
    required_skills: List[str]
    salary_range_usd: Tuple[float, float]
    headcount: int = 1
    filled: int = 0
    status: str = "OPEN"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["department"] = self.department.value
        d["team"] = self.team.value
        return d


@dataclass
class CandidateProfile:
    candidate_id: str
    job_id: str
    name: str
    skills: List[str]
    experience_years: float
    interview_score: float = 85.0  # 0-100
    cultural_fit_score: float = 90.0
    status: str = "APPLIED"  # APPLIED, INTERVIEWED, OFFER_EXTENDED, HIRED, REJECTED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EmployeeProfile:
    employee_id: str
    name: str
    role_title: str
    department: DepartmentType
    team: TeamType
    manager_id: Optional[str]
    skills: List[str]
    performance_rating: float = 4.2  # 1.0 - 5.0
    salary_usd: float = 140000.0
    hired_at: float = field(default_factory=time.time)
    promotion_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["department"] = self.department.value
        d["team"] = self.team.value
        return d


# ---------------------------------------------------------------------------
# 7. Finance & Budget Models
# ---------------------------------------------------------------------------

class ExpenseCategory(str, Enum):
    ENGINEERING_SALARIES = "ENGINEERING_SALARIES"
    INFRASTRUCTURE_CLOUD = "INFRASTRUCTURE_CLOUD"
    LLM_API_TOKENS = "LLM_API_TOKENS"
    STORAGE_CAS = "STORAGE_CAS"
    CI_CD_BUILD = "CI_CD_BUILD"
    TESTING_QA = "TESTING_QA"
    MAINTENANCE = "MAINTENANCE"
    SECURITY_AUDIT = "SECURITY_AUDIT"
    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    GENERAL_ADMIN = "GENERAL_ADMIN"


@dataclass
class FinancialLedgerEntry:
    entry_id: str
    category: ExpenseCategory
    amount_usd: float
    description: str
    department: DepartmentType
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["department"] = self.department.value
        return d


@dataclass
class QuarterlyBudget:
    quarter: str
    year: int
    total_allocated_usd: float
    category_limits_usd: Dict[str, float] = field(default_factory=dict)
    actual_spent_usd: Dict[str, float] = field(default_factory=dict)

    @property
    def total_spent_usd(self) -> float:
        return sum(self.actual_spent_usd.values())

    @property
    def remaining_budget_usd(self) -> float:
        return self.total_allocated_usd - self.total_spent_usd

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["total_spent_usd"] = round(self.total_spent_usd, 2)
        d["remaining_budget_usd"] = round(self.remaining_budget_usd, 2)
        return d


# ---------------------------------------------------------------------------
# 8. Customer Support & Incident Models
# ---------------------------------------------------------------------------

class TicketPriority(str, Enum):
    P0_CRITICAL = "P0_CRITICAL"
    P1_HIGH = "P1_HIGH"
    P2_MEDIUM = "P2_MEDIUM"
    P3_LOW = "P3_LOW"


class TicketType(str, Enum):
    BUG_REPORT = "BUG_REPORT"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    INCIDENT = "INCIDENT"
    INQUIRY = "INQUIRY"


@dataclass
class SupportTicket:
    ticket_id: str
    customer_id: str
    ticket_type: TicketType
    priority: TicketPriority
    title: str
    description: str
    status: str = "OPEN"  # OPEN, TRIAGED, IN_ENGINEERING, RESOLVED, CLOSED
    assigned_team: TeamType = TeamType.CORE_SERVICES
    linked_engineering_task_id: Optional[str] = None
    sla_deadline: float = field(default_factory=lambda: time.time() + 86400)
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    csat_score: Optional[int] = None  # 1 to 5

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["ticket_type"] = self.ticket_type.value
        d["priority"] = self.priority.value
        d["assigned_team"] = self.assigned_team.value
        return d


# ---------------------------------------------------------------------------
# 9. Release Train & Deployment Models
# ---------------------------------------------------------------------------

class ReleaseStage(str, Enum):
    ALPHA = "ALPHA"
    BETA = "BETA"
    RELEASE_CANDIDATE = "RELEASE_CANDIDATE"
    GENERAL_AVAILABILITY = "GENERAL_AVAILABILITY"
    HOTFIX = "HOTFIX"
    PATCH = "PATCH"
    LTS = "LTS"
    ROLLBACK = "ROLLBACK"


@dataclass
class ReleaseCandidate:
    release_id: str
    version: str  # e.g., "3.0.0"
    stage: ReleaseStage = ReleaseStage.RELEASE_CANDIDATE
    epics_included: List[str] = field(default_factory=list)
    features_included: List[str] = field(default_factory=list)
    bugs_fixed: List[str] = field(default_factory=list)
    checklist_gates: Dict[str, bool] = field(default_factory=lambda: {
        "unit_tests_pass": True,
        "integration_tests_pass": True,
        "security_scan_clean": True,
        "performance_sla_met": True,
        "docs_updated": True,
        "executive_signoff": True,
    })
    approved_by: List[ExecutiveRole] = field(default_factory=list)
    status: str = "STAGED"
    created_at: float = field(default_factory=time.time)
    deployed_at: Optional[float] = None

    @property
    def is_approved_for_ga(self) -> bool:
        return all(self.checklist_gates.values()) and len(self.approved_by) >= 2

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["stage"] = self.stage.value
        d["approved_by"] = [r.value for r in self.approved_by]
        d["is_approved_for_ga"] = self.is_approved_for_ga
        return d


# ---------------------------------------------------------------------------
# 10. Governance & Compliance Models
# ---------------------------------------------------------------------------

class ComplianceStandard(str, Enum):
    SOC2_TYPE_II = "SOC2_TYPE_II"
    GDPR = "GDPR"
    ISO_27001 = "ISO_27001"
    HIPAA = "HIPAA"
    PCI_DSS = "PCI_DSS"


@dataclass
class GovernancePolicy:
    policy_id: str
    name: str
    standard: ComplianceStandard
    rule_description: str
    mandatory_approvers: List[ExecutiveRole]
    enforce_branch_protection: bool = True
    enforce_mfa: bool = True
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["standard"] = self.standard.value
        d["mandatory_approvers"] = [r.value for r in self.mandatory_approvers]
        return d


@dataclass
class AuditLogRecord:
    record_id: str
    action: str
    actor: str
    target_entity: str
    department: DepartmentType
    details: Dict[str, Any]
    sha256_hash: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["department"] = self.department.value
        return d


# ---------------------------------------------------------------------------
# 11. Company Brain & Knowledge Models
# ---------------------------------------------------------------------------

class KnowledgeCategory(str, Enum):
    BUSINESS_VISION = "BUSINESS_VISION"
    ARCHITECTURE_ADR = "ARCHITECTURE_ADR"
    CUSTOMER_INSIGHTS = "CUSTOMER_INSIGHTS"
    PRODUCT_ROADMAP = "PRODUCT_ROADMAP"
    ENGINEERING_STANDARDS = "ENGINEERING_STANDARDS"
    FINANCE_METRICS = "FINANCE_METRICS"
    LEGAL_COMPLIANCE = "LEGAL_COMPLIANCE"
    SUPPORT_KNOWLEDGE = "SUPPORT_KNOWLEDGE"
    MEETING_NOTES = "MEETING_NOTES"
    POSTMORTEM = "POSTMORTEM"


@dataclass
class KnowledgeItem:
    knowledge_id: str
    title: str
    category: KnowledgeCategory
    content: str
    tags: List[str]
    author: str
    source_department: DepartmentType
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["source_department"] = self.source_department.value
        return d
