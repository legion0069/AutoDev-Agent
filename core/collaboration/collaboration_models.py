"""
AutoDev Collaboration Framework - Models & Data Structures (v2.8)
=================================================================
Unified data models, message schemas, role definitions, consensus contracts,
conflict descriptors, file lock primitives, and synchronization checkpoints.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# ----------------------------------------------------------------------
# 1. Agent Roles & Communication Types
# ----------------------------------------------------------------------

class AgentRole(str, enum.Enum):
    """Specialized roles within an autonomous AI engineering organization."""
    ARCHITECTURE = "architecture"
    BACKEND = "backend"
    FRONTEND = "frontend"
    TESTING = "testing"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    RELEASE = "release"
    COORDINATOR = "coordinator"
    REVIEWER = "reviewer"
    GENERAL = "general"


class MessageType(str, enum.Enum):
    """Supported communication message types on the Collaboration Bus."""
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    QUESTION = "QUESTION"
    ANSWER = "ANSWER"
    REVIEW = "REVIEW"
    APPROVAL = "APPROVAL"
    BLOCKER = "BLOCKER"
    DEPENDENCY = "DEPENDENCY"
    NOTIFICATION = "NOTIFICATION"
    PROPOSAL = "PROPOSAL"
    VOTE = "VOTE"
    SYNC = "SYNC"


class MessageStatus(str, enum.Enum):
    """Delivery and handling status of an AgentMessage."""
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


@dataclass
class AgentMessage:
    """Message envelope exchanged across the Collaboration Bus."""
    message_id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:10]}")
    sender: str = "anonymous"
    receiver: str = "broadcast"  # Agent name, "*" or "broadcast"
    timestamp: float = field(default_factory=time.time)
    task_id: Optional[str] = None
    message_type: MessageType = MessageType.NOTIFICATION
    payload: Dict[str, Any] = field(default_factory=dict)
    status: MessageStatus = MessageStatus.SENT
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "message_type": self.message_type.value if hasattr(self.message_type, "value") else str(self.message_type),
            "payload": self.payload,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentMessage:
        msg_type = data.get("message_type", MessageType.NOTIFICATION)
        if isinstance(msg_type, str):
            try:
                msg_type = MessageType(msg_type)
            except ValueError:
                msg_type = MessageType.NOTIFICATION
        status = data.get("status", MessageStatus.SENT)
        if isinstance(status, str):
            try:
                status = MessageStatus(status)
            except ValueError:
                status = MessageStatus.SENT
        return cls(
            message_id=data.get("message_id", f"msg_{uuid.uuid4().hex[:10]}"),
            sender=data.get("sender", "anonymous"),
            receiver=data.get("receiver", "broadcast"),
            timestamp=data.get("timestamp", time.time()),
            task_id=data.get("task_id"),
            message_type=msg_type,
            payload=data.get("payload", {}),
            status=status,
            correlation_id=data.get("correlation_id"),
            reply_to=data.get("reply_to"),
        )


# ----------------------------------------------------------------------
# 2. Task Models & Allocation Structures
# ----------------------------------------------------------------------

class TaskPriority(enum.IntEnum):
    """Task execution priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class TaskStatus(str, enum.Enum):
    """Lifecycle status of a task assignment."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    REASSIGNED = "reassigned"


@dataclass
class TaskAssignment:
    """Intelligent task assignment descriptor with skills, hours, and dependencies."""
    task_id: str
    title: str = ""
    description: str = ""
    assigned_agent: Optional[str] = None
    assigned_role: Optional[AgentRole] = None
    required_skills: List[str] = field(default_factory=list)
    estimated_hours: float = 1.0
    priority: TaskPriority = TaskPriority.MEDIUM
    dependencies: List[str] = field(default_factory=list)
    complexity: str = "medium"  # "low", "medium", "high", "critical"
    ownership: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    estimated_files: List[str] = field(default_factory=list)
    assigned_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    @property
    def agent_id(self) -> Optional[str]:
        return self.assigned_agent

    @agent_id.setter
    def agent_id(self, value: Optional[str]):
        self.assigned_agent = value

    @property
    def agent_role(self) -> Optional[AgentRole]:
        return self.assigned_role

    @agent_role.setter
    def agent_role(self, value: Optional[AgentRole]):
        self.assigned_role = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "assigned_agent": self.assigned_agent,
            "assigned_role": self.assigned_role.value if hasattr(self.assigned_role, "value") else str(self.assigned_role),
            "required_skills": self.required_skills,
            "estimated_hours": self.estimated_hours,
            "priority": self.priority.name if hasattr(self.priority, "name") else str(self.priority),
            "dependencies": self.dependencies,
            "complexity": self.complexity,
            "ownership": self.ownership,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "estimated_files": self.estimated_files,
            "assigned_at": self.assigned_at,
            "completed_at": self.completed_at,
        }


# ----------------------------------------------------------------------
# 3. Consensus Engine Models
# ----------------------------------------------------------------------

class ConsensusStrategy(str, enum.Enum):
    """Consensus strategies for resolving technical and architectural disputes."""
    MAJORITY = "majority"
    WEIGHTED = "weighted"
    ARCHITECTURE_FIRST = "architecture-first"
    SECURITY_FIRST = "security-first"
    PERFORMANCE_FIRST = "performance-first"


@dataclass
class Proposal:
    """An engineering solution proposal submitted by a specialized agent."""
    proposal_id: str = field(default_factory=lambda: f"prop_{uuid.uuid4().hex[:8]}")
    proposer: str = ""
    role: AgentRole = AgentRole.GENERAL
    title: str = ""
    description: str = ""
    confidence: float = 0.80
    tradeoffs: List[str] = field(default_factory=list)
    spec: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "proposer": self.proposer,
            "role": self.role.value if hasattr(self.role, "value") else str(self.role),
            "title": self.title,
            "description": self.description,
            "confidence": self.confidence,
            "tradeoffs": self.tradeoffs,
            "spec": self.spec,
            "timestamp": self.timestamp,
        }


@dataclass
class ConsensusResult:
    """Outcome of multi-agent proposal scoring and consensus determination."""
    consensus_id: str = field(default_factory=lambda: f"cons_{uuid.uuid4().hex[:8]}")
    issue_id: Optional[str] = None
    topic: str = ""
    winning_proposal_id: Optional[str] = None
    strategy: ConsensusStrategy = ConsensusStrategy.WEIGHTED
    score: float = 0.0
    reasoning: str = ""
    scores: Dict[str, float] = field(default_factory=dict)
    participating_agents: List[str] = field(default_factory=list)
    proposals_evaluated: int = 0
    accepted: bool = True
    timestamp: float = field(default_factory=time.time)
    winning_proposal: Optional[Proposal] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consensus_id": self.consensus_id,
            "issue_id": self.issue_id,
            "topic": self.topic,
            "winning_proposal_id": self.winning_proposal_id,
            "strategy": self.strategy.value if hasattr(self.strategy, "value") else str(self.strategy),
            "score": self.score,
            "reasoning": self.reasoning,
            "scores": self.scores,
            "participating_agents": self.participating_agents,
            "proposals_evaluated": self.proposals_evaluated,
            "accepted": self.accepted,
            "timestamp": self.timestamp,
            "winning_proposal": self.winning_proposal.to_dict() if self.winning_proposal else None,
        }


# ----------------------------------------------------------------------
# 4. Conflict Resolution Models
# ----------------------------------------------------------------------

class ConflictType(str, enum.Enum):
    """Categorization of inter-agent engineering conflicts."""
    CONCURRENT_EDIT = "CONCURRENT_EDIT"
    FILE_WRITE_COLLISION = "FILE_WRITE_COLLISION"
    API_MISMATCH = "API_MISMATCH"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    DEPENDENCY_CONFLICT = "DEPENDENCY_CONFLICT"
    INTERFACE_BREAK = "INTERFACE_BREAK"
    MERGE_CONFLICT = "MERGE_CONFLICT"


@dataclass
class Conflict:
    """An identified conflict between two or more agents or code components."""
    conflict_id: str = field(default_factory=lambda: f"conf_{uuid.uuid4().hex[:8]}")
    conflict_type: ConflictType = ConflictType.CONCURRENT_EDIT
    file_path: Optional[str] = None
    involved_agents: List[str] = field(default_factory=list)
    description: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_decision: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value if hasattr(self.conflict_type, "value") else str(self.conflict_type),
            "file_path": self.file_path,
            "involved_agents": self.involved_agents,
            "description": self.description,
            "context": self.context,
            "resolved": self.resolved,
            "resolution_decision": self.resolution_decision,
            "timestamp": self.timestamp,
        }


@dataclass
class ResolutionDecision:
    """Resolution decision for an identified conflict with verification records."""
    decision_id: str = field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:8]}")
    conflict_id: str = ""
    strategy: str = "three_way_merge"
    resolution_patch: Dict[str, Any] = field(default_factory=dict)
    resolved_content: Optional[str] = None
    explanation: str = ""
    applied_by: str = "ConflictResolver"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "conflict_id": self.conflict_id,
            "strategy": self.strategy,
            "resolution_patch": self.resolution_patch,
            "resolved_content": self.resolved_content,
            "explanation": self.explanation,
            "applied_by": self.applied_by,
            "timestamp": self.timestamp,
        }


# ----------------------------------------------------------------------
# 5. Shared Workspace & Locking Models
# ----------------------------------------------------------------------

@dataclass
class FileLock:
    """Fine-grained atomic read/write lock on a workspace file."""
    file_path: str
    holder: str
    role: AgentRole = AgentRole.GENERAL
    is_exclusive: bool = True
    acquired_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 60.0)
    task_id: Optional[str] = None
    lock_id: str = field(default_factory=lambda: f"lock_{uuid.uuid4().hex[:8]}")

    @property
    def owner_agent_id(self) -> str:
        return self.holder

    @property
    def lock_type(self) -> str:
        return "exclusive" if self.is_exclusive else "shared"

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lock_id": self.lock_id,
            "file_path": self.file_path,
            "holder": self.holder,
            "role": self.role.value if hasattr(self.role, "value") else str(self.role),
            "is_exclusive": self.is_exclusive,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "task_id": self.task_id,
            "is_expired": self.is_expired,
        }


@dataclass
class ReviewComment:
    """Review comment on a staged file modification."""
    comment_id: str = field(default_factory=lambda: f"rc_{uuid.uuid4().hex[:8]}")
    file_path: str = ""
    author_id: str = ""
    role: AgentRole = AgentRole.GENERAL
    comment: str = ""
    line_number: Optional[int] = None
    severity: str = "INFO"  # "INFO", "WARNING", "ERROR", "BLOCKER"
    is_blocking: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "file_path": self.file_path,
            "author_id": self.author_id,
            "role": self.role.value if hasattr(self.role, "value") else str(self.role),
            "comment": self.comment,
            "line_number": self.line_number,
            "severity": self.severity,
            "is_blocking": self.is_blocking,
            "timestamp": self.timestamp,
        }


@dataclass
class StagedChange:
    """In-memory staged file modification awaiting multi-agent review."""
    change_id: str = field(default_factory=lambda: f"sc_{uuid.uuid4().hex[:8]}")
    file_path: str = ""
    author_id: str = ""
    role: AgentRole = AgentRole.GENERAL
    content: str = ""
    diff: Optional[str] = None
    commit_message: str = ""
    is_approved: bool = False
    reviewers: List[str] = field(default_factory=list)
    comments: List[ReviewComment] = field(default_factory=list)
    staged_at: float = field(default_factory=time.time)
    approved_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id,
            "file_path": self.file_path,
            "author_id": self.author_id,
            "role": self.role.value if hasattr(self.role, "value") else str(self.role),
            "content": self.content,
            "diff": self.diff,
            "commit_message": self.commit_message,
            "is_approved": self.is_approved,
            "reviewers": self.reviewers,
            "comments": [c.to_dict() for c in self.comments],
            "staged_at": self.staged_at,
            "approved_at": self.approved_at,
        }


# ----------------------------------------------------------------------
# 6. Synchronization Checkpoint Models
# ----------------------------------------------------------------------

class SyncCheckpointType(str, enum.Enum):
    """Synchronization barrier checkpoints across the multi-agent organization."""
    PRE_MERGE = "PRE_MERGE"
    PRE_RELEASE = "PRE_RELEASE"
    POST_ARCHITECTURE = "POST_ARCHITECTURE"
    PRE_DEPLOYMENT = "PRE_DEPLOYMENT"


@dataclass
class SyncCheckpoint:
    """Barrier state and validation outcome at an organization checkpoint."""
    checkpoint_id: str = field(default_factory=lambda: f"sync_{uuid.uuid4().hex[:8]}")
    checkpoint_type: SyncCheckpointType = SyncCheckpointType.PRE_MERGE
    name: str = ""
    required_validations: List[str] = field(default_factory=list)
    validation_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    passed: bool = False
    blockers: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "checkpoint_type": self.checkpoint_type.value if hasattr(self.checkpoint_type, "value") else str(self.checkpoint_type),
            "name": self.name,
            "required_validations": self.required_validations,
            "validation_results": self.validation_results,
            "passed": self.passed,
            "blockers": self.blockers,
            "created_at": self.created_at,
            "context": self.context,
        }


# ----------------------------------------------------------------------
# 7. Collaboration Configuration
# ----------------------------------------------------------------------

@dataclass
class CollaborationConfig:
    """Master configuration for the Multi-Agent Collaboration Framework."""
    max_parallel_agents: int = 8
    consensus_strategy: ConsensusStrategy = ConsensusStrategy.WEIGHTED
    workload_balancing: bool = True
    communication_timeout: float = 15.0
    retry_policy: Dict[str, Any] = field(default_factory=lambda: {"max_retries": 3, "backoff_factor": 1.5})
    review_depth: str = "deep"
    imbalance_threshold_hours: float = 3.0
    auto_resolve_conflicts: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_parallel_agents": self.max_parallel_agents,
            "consensus_strategy": self.consensus_strategy.value if hasattr(self.consensus_strategy, "value") else str(self.consensus_strategy),
            "workload_balancing": self.workload_balancing,
            "communication_timeout": self.communication_timeout,
            "retry_policy": self.retry_policy,
            "review_depth": self.review_depth,
            "imbalance_threshold_hours": self.imbalance_threshold_hours,
            "auto_resolve_conflicts": self.auto_resolve_conflicts,
        }
