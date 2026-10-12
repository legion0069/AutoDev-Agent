"""
AutoDev Collaboration Framework (v2.8)
======================================
Deterministic multi-agent collaboration, communication, consensus,
conflict resolution, task allocation, dependency scheduling, and synchronization.
"""

from .collaboration_models import (
    AgentMessage,
    AgentRole,
    CollaborationConfig,
    Conflict,
    ConflictType,
    ConsensusResult,
    ConsensusStrategy,
    FileLock,
    MessageStatus,
    MessageType,
    Proposal,
    ResolutionDecision,
    ReviewComment,
    StagedChange,
    SyncCheckpoint,
    SyncCheckpointType,
    TaskAssignment,
    TaskPriority,
    TaskStatus,
)
from .communication_bus import CollaborationBus, CommunicationBus
from .consensus_engine import ConsensusEngine
from .conflict_resolver import ConflictResolver
from .dependency_scheduler import DependencyScheduler
from .shared_workspace import SharedWorkspace
from .synchronization_manager import SynchronizationManager
from .task_allocator import TaskAllocator
from .workload_balancer import WorkloadBalancer
from .collaboration_telemetry import CollaborationTelemetry
from .collaboration_manager import CollaborationManager

__all__ = [
    "AgentMessage",
    "AgentRole",
    "CollaborationBus",
    "CollaborationConfig",
    "CollaborationManager",
    "CollaborationTelemetry",
    "CommunicationBus",
    "Conflict",
    "ConflictResolver",
    "ConflictType",
    "ConsensusEngine",
    "ConsensusResult",
    "ConsensusStrategy",
    "DependencyScheduler",
    "FileLock",
    "MessageStatus",
    "MessageType",
    "Proposal",
    "ResolutionDecision",
    "ReviewComment",
    "SharedWorkspace",
    "StagedChange",
    "SyncCheckpoint",
    "SyncCheckpointType",
    "SynchronizationManager",
    "TaskAllocator",
    "TaskAssignment",
    "TaskPriority",
    "TaskStatus",
    "WorkloadBalancer",
]
