"""
dataclasses.py - Immutable Strongly-Typed Data Contracts for Autonomous AI Organization

All inter-agent communication, workflow routing, and organizational events
strictly utilize immutable frozen dataclasses. Dictionaries and raw JSON
are strictly disallowed for internal agent communication.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Union


class PriorityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class TaskStatus(str, Enum):
    BACKLOG = "BACKLOG"
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    CODE_REVIEW = "CODE_REVIEW"
    TESTING = "TESTING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"


class DecisionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DEPRECATED = "DEPRECATED"
    SUPERSEDED = "SUPERSEDED"


class ConflictType(str, Enum):
    MERGE_CONFLICT = "MERGE_CONFLICT"
    REQUIREMENT_CONFLICT = "REQUIREMENT_CONFLICT"
    ARCHITECTURE_CONFLICT = "ARCHITECTURE_CONFLICT"
    PRIORITY_CONFLICT = "PRIORITY_CONFLICT"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    DUPLICATE_IMPLEMENTATION = "DUPLICATE_IMPLEMENTATION"
    DEADLOCK = "DEADLOCK"


# ============================================================================
# Core Business & Product Dataclasses
# ============================================================================

@dataclass(frozen=True)
class WorkRequest:
    request_id: str
    title: str
    description: str
    requester: str
    priority: str = PriorityLevel.MEDIUM.value
    budget: float = 10000.0
    target_date: str = "2026-12-31"
    timestamp: float = field(default_factory=time.time)
    attributes: Tuple[Tuple[str, str], ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FeatureProposal:
    proposal_id: str
    title: str
    description: str
    target_audience: str
    business_value: float
    estimated_effort: float
    status: str = "PROPOSED"
    created_by: str = "ProductManager"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectRoadmap:
    roadmap_id: str
    project_name: str
    strategic_goals: Tuple[str, ...]
    milestones: Tuple[str, ...]
    start_date: str
    end_date: str
    approved_by: str
    version: str = "1.0.0"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Epic:
    epic_id: str
    title: str
    description: str
    priority: str = PriorityLevel.MEDIUM.value
    business_value: float = 100.0
    acceptance_criteria: Tuple[str, ...] = ()
    user_stories: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UserStory:
    story_id: str
    epic_id: str
    title: str
    as_a: str
    i_want: str
    so_that: str
    acceptance_criteria: Tuple[str, ...]
    points: int = 5
    status: str = TaskStatus.BACKLOG.value

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FunctionalRequirement:
    req_id: str
    source_id: str
    statement: str
    priority: str = PriorityLevel.HIGH.value
    domain: str = "CORE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TechnicalSpecification:
    spec_id: str
    req_id: str
    component: str
    spec_details: str
    interface_signature: str
    data_contract: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WireframeSpec:
    wireframe_id: str
    view_name: str
    components: Tuple[str, ...]
    layout: str
    accessibility_tags: Tuple[str, ...]
    user_flow_step: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# Engineering & Architecture Dataclasses
# ============================================================================

@dataclass(frozen=True)
class ArchitectureDecision:
    decision_id: str
    title: str
    status: str
    context: str
    decision: str
    consequences: Tuple[str, ...]
    author: str
    approved_by: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArchitectureReview:
    review_id: str
    decision_id: str
    reviewer: str
    approved: bool
    comments: Tuple[str, ...]
    recommendations: Tuple[str, ...]
    score: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EngineeringTask:
    task_id: str
    title: str
    description: str
    assigned_to: str
    task_type: str
    priority: str
    estimated_hours: float
    actual_hours: float = 0.0
    status: str = TaskStatus.PENDING.value
    dependencies: Tuple[str, ...] = ()
    artifacts: Tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewFeedback:
    feedback_id: str
    task_id: str
    reviewer: str
    status: str
    comments: Tuple[str, ...]
    score: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TechnicalDebtItem:
    item_id: str
    title: str
    description: str
    category: str
    estimated_remediation_hours: float
    priority: str
    status: str = TaskStatus.BACKLOG.value
    reported_by: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# Quality, Security, and Performance Dataclasses
# ============================================================================

@dataclass(frozen=True)
class BugTicket:
    ticket_id: str
    title: str
    description: str
    severity: str
    reporter: str
    assigned_to: Optional[str] = None
    status: str = "OPEN"
    reproduction_steps: Tuple[str, ...] = ()
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SecurityFinding:
    finding_id: str
    title: str
    severity: str
    cwe_or_owasp_id: str
    description: str
    remediation: str
    affected_component: str
    detected_by: str
    resolved: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PerformanceReport:
    report_id: str
    target_service: str
    cpu_utilization_pct: float
    memory_mb: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_rps: float
    bottlenecks: Tuple[str, ...]
    recommendations: Tuple[str, ...]
    status: str = "OPTIMAL"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# Release, Deployment & Risk Dataclasses
# ============================================================================

@dataclass(frozen=True)
class DeploymentPackage:
    package_id: str
    version: str
    environment: str
    artifacts: Tuple[str, ...]
    container_images: Tuple[str, ...]
    config_hashes: Tuple[str, ...]
    created_by: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReleaseApproval:
    approval_id: str
    package_id: str
    version: str
    approved_by: str
    approved: bool
    conditions: Tuple[str, ...]
    signatures: Tuple[str, ...]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RiskReport:
    report_id: str
    title: str
    risk_level: str
    probability: float
    impact: float
    mitigation_strategy: str
    owner: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# Sprint, Agile & Metrics Dataclasses
# ============================================================================

@dataclass(frozen=True)
class SprintPlan:
    sprint_id: str
    sprint_number: int
    goal: str
    capacity_hours: float
    task_ids: Tuple[str, ...]
    start_date: str
    end_date: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SprintReport:
    sprint_id: str
    sprint_name: str
    velocity_planned: float
    velocity_completed: float
    tasks_completed: int
    tasks_incomplete: int
    burndown_data: Tuple[float, ...]
    retrospective_positives: Tuple[str, ...]
    retrospective_negatives: Tuple[str, ...]
    action_items: Tuple[str, ...]
    start_time: float
    end_time: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EngineeringMetric:
    metric_id: str
    metric_name: str
    value: float
    unit: str
    category: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MeetingNote:
    meeting_id: str
    meeting_type: str
    attendees: Tuple[str, ...]
    notes: Tuple[str, ...]
    action_items: Tuple[str, ...]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# Conflict & Simulation Dataclasses
# ============================================================================

@dataclass(frozen=True)
class ConflictItem:
    conflict_id: str
    conflict_type: str
    parties: Tuple[str, ...]
    description: str
    resource_or_target: str
    severity: str = PriorityLevel.HIGH.value
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConflictResolutionReport:
    resolution_id: str
    conflict_id: str
    conflict_type: str
    strategy_applied: str
    winner_or_synthesis: str
    rationale: str
    resolved_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SimulationEvent:
    event_id: str
    timestamp: float
    event_type: str
    agent_id: str
    payload_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SimulationMetrics:
    total_events: int
    engineers_simulated: int
    total_tasks_processed: int
    average_turnaround_time: float
    throughput_tps: float
    utilization_pct: float = 85.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentMessage:
    message_id: str
    sender: str
    recipient: str
    message_type: str
    payload_id: str
    priority: str = PriorityLevel.MEDIUM.value
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutiveDashboardData:
    dashboard_type: str
    title: str
    metrics: Tuple[EngineeringMetric, ...]
    alerts: Tuple[str, ...]
    summary_markdown: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeveloperProfile:
    developer_id: str
    name: str
    role: str
    skills: Tuple[str, ...]
    current_capacity_hours: float = 40.0
    completed_tasks_count: int = 0
    code_quality_score: float = 95.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
