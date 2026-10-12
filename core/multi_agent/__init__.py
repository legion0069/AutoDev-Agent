"""
AutoDev Version 3.3 - Distributed Multi-Agent Collaboration Platform Subsystem.

Provides an enterprise-scale autonomous software engineering organization
operating deterministically via standard library concurrency primitives.
"""

from core.multi_agent.agent_bus import AgentMessageBus
from core.multi_agent.agent_registry import (
    AgentDescriptor,
    AgentRegistry,
    AgentRole,
    AgentStatus,
)
from core.multi_agent.collaboration_engine import (
    CollaborationEngine,
    TelemetrySnapshot,
)
from core.multi_agent.conflict_resolver import (
    ConflictRecord,
    ConflictResolver,
    ConflictType,
    ResolutionAction,
)
from core.multi_agent.consensus_engine import (
    ROLE_SENIORITY_WEIGHTS,
    ConsensusEngine,
    ConsensusProposal,
    ConsensusStrategy,
    ReviewVote,
    VoteDecision,
)
from core.multi_agent.conversation import (
    ConversationDecision,
    ConversationEngine,
    ConversationEntry,
    ConversationStatus,
    ConversationThread,
)
from core.multi_agent.engineering_company import DistributedEngineeringCompany
from core.multi_agent.message import (
    Message,
    MessagePriority,
    MessageStatus,
    MessageType,
)
from core.multi_agent.parallel_executor import (
    ExecutionResult,
    ParallelExecutor,
)
from core.multi_agent.resource_scheduler import (
    LockType,
    ResourceLock,
    ResourceReservation,
    ResourceScheduler,
)
from core.multi_agent.shared_workspace import SharedWorkspace
from core.multi_agent.task_allocator import TaskAllocator
from core.multi_agent.work_queue import (
    TaskPriority,
    WorkItem,
    WorkItemStatus,
    WorkQueue,
)

__all__ = [
    # Message Bus & Messaging
    "Message",
    "MessageType",
    "MessagePriority",
    "MessageStatus",
    "AgentMessageBus",
    # Agent Registry
    "AgentRole",
    "AgentStatus",
    "AgentDescriptor",
    "AgentRegistry",
    # Conversations
    "ConversationEntry",
    "ConversationStatus",
    "ConversationDecision",
    "ConversationThread",
    "ConversationEngine",
    # Work Queue & Scheduling
    "WorkItemStatus",
    "TaskPriority",
    "WorkItem",
    "WorkQueue",
    "TaskAllocator",
    # Resource Locks & Parallel Execution
    "LockType",
    "ResourceLock",
    "ResourceReservation",
    "ResourceScheduler",
    "ExecutionResult",
    "ParallelExecutor",
    # Conflict Resolution & Consensus
    "ConflictType",
    "ResolutionAction",
    "ConflictRecord",
    "ConflictResolver",
    "ConsensusStrategy",
    "VoteDecision",
    "ROLE_SENIORITY_WEIGHTS",
    "ReviewVote",
    "ConsensusProposal",
    "ConsensusEngine",
    # Shared Workspace & Collaboration
    "SharedWorkspace",
    "TelemetrySnapshot",
    "CollaborationEngine",
    "DistributedEngineeringCompany",
]
