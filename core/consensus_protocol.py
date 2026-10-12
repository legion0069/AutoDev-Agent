"""
consensus_protocol.py - Consensus Wire Protocol & Fencing Models for AutoDev (v2.4)

Defines coordinator lifecycle states, monotonically increasing fencing tokens,
peer node descriptors, election messages, and consensus protocol schemas.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import time
from typing import Any, Dict, List, Optional, Set


class CoordinatorRole(str, Enum):
    """Lifecycle role of a coordinator instance in an HA cluster."""
    STARTING = "STARTING"
    FOLLOWER = "FOLLOWER"
    CANDIDATE = "CANDIDATE"
    LEADER = "LEADER"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    STOPPING = "STOPPING"


@dataclass
class FencingToken:
    """
    Monotonically increasing fencing generation token ensuring single-writer
    safety across leader failovers. Stale leaders with outdated generation numbers
    are rejected by workers and storage layers.
    """
    term: int
    leader_id: str
    fencing_generation: int
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at_timestamp: float = field(default_factory=lambda: time.time() + 15.0)

    @property
    def is_expired(self) -> bool:
        """Returns True if the fencing token has exceeded its lease duration."""
        return time.time() > self.expires_at_timestamp

    def is_valid_for(self, expected_term: int, expected_generation: int) -> bool:
        """Validates that this token matches or exceeds the required term and generation."""
        if self.is_expired:
            return False
        return self.term >= expected_term and self.fencing_generation >= expected_generation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "term": self.term,
            "leader_id": self.leader_id,
            "fencing_generation": self.fencing_generation,
            "issued_at": self.issued_at,
            "expires_at_timestamp": self.expires_at_timestamp,
            "is_expired": self.is_expired,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FencingToken:
        return cls(
            term=int(data["term"]),
            leader_id=str(data["leader_id"]),
            fencing_generation=int(data["fencing_generation"]),
            issued_at=str(data.get("issued_at", datetime.now(timezone.utc).isoformat())),
            expires_at_timestamp=float(data.get("expires_at_timestamp", time.time() + 15.0)),
        )


@dataclass
class CoordinatorNode:
    """Operational state and connection metadata for a coordinator node."""
    coordinator_id: str
    host: str = "127.0.0.1"
    port: int = 50051
    role: CoordinatorRole = CoordinatorRole.STARTING
    current_term: int = 0
    last_heartbeat_timestamp: float = field(default_factory=time.time)
    last_heartbeat_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_alive(self) -> bool:
        return self.is_active and (time.time() - self.last_heartbeat_timestamp) < 15.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coordinator_id": self.coordinator_id,
            "host": self.host,
            "port": self.port,
            "role": self.role.value if isinstance(self.role, CoordinatorRole) else str(self.role),
            "current_term": self.current_term,
            "last_heartbeat_timestamp": self.last_heartbeat_timestamp,
            "last_heartbeat_at": self.last_heartbeat_at,
            "is_active": self.is_active,
            "is_alive": self.is_alive,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CoordinatorNode:
        role_raw = data.get("role", "STARTING")
        try:
            role = CoordinatorRole(role_raw)
        except ValueError:
            role = CoordinatorRole.STARTING
        return cls(
            coordinator_id=str(data["coordinator_id"]),
            host=str(data.get("host", "127.0.0.1")),
            port=int(data.get("port", 50051)),
            role=role,
            current_term=int(data.get("current_term", 0)),
            last_heartbeat_timestamp=float(data.get("last_heartbeat_timestamp", time.time())),
            last_heartbeat_at=str(data.get("last_heartbeat_at", datetime.now(timezone.utc).isoformat())),
            is_active=bool(data.get("is_active", True)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class VoteRequest:
    """Message sent by candidate coordinator requesting peer votes."""
    term: int
    candidate_id: str
    last_log_index: int = 0
    last_log_term: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VoteRequest:
        return cls(
            term=int(data["term"]),
            candidate_id=str(data["candidate_id"]),
            last_log_index=int(data.get("last_log_index", 0)),
            last_log_term=int(data.get("last_log_term", 0)),
        )


@dataclass
class VoteResponse:
    """Message returned by peer node in response to VoteRequest."""
    term: int
    vote_granted: bool
    voter_id: str
    fencing_token: Optional[FencingToken] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["fencing_token"] = self.fencing_token.to_dict() if self.fencing_token else None
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VoteResponse:
        f_tok = None
        if data.get("fencing_token"):
            f_tok = FencingToken.from_dict(data["fencing_token"])
        return cls(
            term=int(data["term"]),
            vote_granted=bool(data["vote_granted"]),
            voter_id=str(data["voter_id"]),
            fencing_token=f_tok,
            reason=data.get("reason"),
        )


@dataclass
class ConsensusHeartbeat:
    """Periodic heartbeat broadcasted by leader coordinator to maintain quorum."""
    term: int
    leader_id: str
    fencing_generation: int
    lease_ttl_seconds: float = 5.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConsensusHeartbeat:
        return cls(
            term=int(data["term"]),
            leader_id=str(data["leader_id"]),
            fencing_generation=int(data["fencing_generation"]),
            lease_ttl_seconds=float(data.get("lease_ttl_seconds", 5.0)),
            timestamp=float(data.get("timestamp", time.time())),
        )
