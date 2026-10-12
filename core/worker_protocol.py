"""
worker_protocol.py - Distributed Worker Communication Protocol & Message Schemas for AutoDev (v2.2)

Defines protocol versioning, typed message payloads, worker lifecycle states,
task assignments, task completion results, and serialization schemas.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger("AutoDev.WorkerProtocol")

PROTOCOL_VERSION = "2.2.0"


class WorkerStatus(str, Enum):
    """Lifecycle states of an AutoDev distributed worker agent."""
    STARTING = "STARTING"
    IDLE = "IDLE"
    BUSY = "BUSY"
    DEGRADED = "DEGRADED"
    UNREACHABLE = "UNREACHABLE"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class TaskLeaseStatus(str, Enum):
    """State of an assigned task lease."""
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    RELEASED = "RELEASED"
    REVOKED = "REVOKED"


# Secret redaction helper
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|auth|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"),
    re.compile(r"(?i)sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"(?i)AIza[0-9A-Za-z\-_]{35}"),
    re.compile(r"(?i)Bearer\s+[a-zA-Z0-9_\-\.]{20,}"),
]

def redact_payload_secrets(data: Any) -> Any:
    """Recursively redacts secrets from dictionary or string payloads."""
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if any(term in k.lower() for term in ["key", "secret", "token", "password", "auth"]):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_payload_secrets(v)
        return redacted
    elif isinstance(data, list):
        return [redact_payload_secrets(x) for x in data]
    elif isinstance(data, str):
        res = SECRET_PATTERNS[0].sub(r"\1: [REDACTED]", data)
        for pat in SECRET_PATTERNS[1:]:
            res = pat.sub("[REDACTED]", res)
        return res
    return data


# =============================================================================
# TYPED PROTOCOL PAYLOADS
# =============================================================================

@dataclass
class WorkerCapabilities:
    """Declared capabilities of an AutoDev worker agent."""
    supported_runtimes: List[str] = field(default_factory=lambda: ["process"])
    supported_operation_types: List[str] = field(default_factory=lambda: ["CREATE_FILE", "MODIFY_FILE", "DELETE_FILE"])
    max_concurrency: int = 2
    has_container_support: bool = False
    container_engine: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkerCapabilities:
        return cls(
            supported_runtimes=list(data.get("supported_runtimes", ["process"])),
            supported_operation_types=list(data.get("supported_operation_types", ["CREATE_FILE", "MODIFY_FILE", "DELETE_FILE"])),
            max_concurrency=int(data.get("max_concurrency", 2)),
            has_container_support=bool(data.get("has_container_support", False)),
            container_engine=data.get("container_engine"),
            tags=list(data.get("tags", [])),
        )


@dataclass
class WorkerRegistrationRequest:
    """Registration payload sent by a worker connecting to the coordinator."""
    worker_id: str
    worker_name: str
    protocol_version: str = PROTOCOL_VERSION
    capabilities: WorkerCapabilities = field(default_factory=WorkerCapabilities)
    hostname: str = "localhost"
    auth_token: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "worker_name": self.worker_name,
            "protocol_version": self.protocol_version,
            "capabilities": self.capabilities.to_dict(),
            "hostname": self.hostname,
            "auth_token": "[REDACTED]" if self.auth_token else None,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkerRegistrationRequest:
        return cls(
            worker_id=str(data["worker_id"]),
            worker_name=str(data.get("worker_name", data["worker_id"])),
            protocol_version=str(data.get("protocol_version", PROTOCOL_VERSION)),
            capabilities=WorkerCapabilities.from_dict(data.get("capabilities", {})),
            hostname=str(data.get("hostname", "localhost")),
            auth_token=data.get("auth_token"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class WorkerRegistrationResponse:
    """Response returned by coordinator upon worker registration."""
    accepted: bool
    worker_id: str
    coordinator_version: str = PROTOCOL_VERSION
    heartbeat_interval_seconds: float = 5.0
    lease_ttl_seconds: float = 15.0
    message: str = "Registration accepted"

    @property
    def success(self) -> bool:
        return self.accepted

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["success"] = self.accepted
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkerRegistrationResponse:
        accepted = bool(data.get("accepted", data.get("success", False)))
        return cls(
            accepted=accepted,
            worker_id=str(data.get("worker_id", "")),
            coordinator_version=str(data.get("coordinator_version", PROTOCOL_VERSION)),
            heartbeat_interval_seconds=float(data.get("heartbeat_interval_seconds", 5.0)),
            lease_ttl_seconds=float(data.get("lease_ttl_seconds", 15.0)),
            message=str(data.get("message", "Registration accepted")),
        )



@dataclass
class WorkerHeartbeat:
    """Heartbeat signal sent by an active worker."""
    worker_id: str
    status: WorkerStatus = WorkerStatus.IDLE
    current_load: int = 0
    concurrency_used: Optional[int] = None
    active_task_ids: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.concurrency_used is not None and self.current_load == 0:
            self.current_load = self.concurrency_used
        elif self.current_load != 0 and self.concurrency_used is None:
            self.concurrency_used = self.current_load

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "status": self.status.value if isinstance(self.status, WorkerStatus) else str(self.status),
            "current_load": self.current_load,
            "concurrency_used": self.current_load,
            "active_task_ids": self.active_task_ids,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkerHeartbeat:
        raw_status = data.get("status", WorkerStatus.IDLE.value)
        try:
            status = WorkerStatus(raw_status)
        except ValueError:
            status = WorkerStatus.IDLE
        load = int(data.get("current_load", data.get("concurrency_used", 0)))
        return cls(
            worker_id=str(data["worker_id"]),
            status=status,
            current_load=load,
            concurrency_used=load,
            active_task_ids=list(data.get("active_task_ids", [])),
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
        )


@dataclass
class WorkerHeartbeatResponse:
    """Response returned by coordinator for worker heartbeat."""
    acknowledged: bool
    worker_id: str
    rebalance_required: bool = False
    message: str = "Heartbeat acknowledged"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkerHeartbeatResponse:
        return cls(
            acknowledged=bool(data.get("acknowledged", True)),
            worker_id=str(data.get("worker_id", "")),
            rebalance_required=bool(data.get("rebalance_required", False)),
            message=str(data.get("message", "Heartbeat acknowledged")),
        )




@dataclass
class TaskAssignmentPayload:
    """Payload assigning a change operation or stage to a worker."""
    task_id: str
    operation_id: str
    transaction_id: str
    operation_type: str
    target_file: str
    target_content: Optional[str] = None
    lease_token: str = ""
    deadline_utc: str = ""
    idempotency_key: str = ""
    required_runtime: str = "process"
    security_profile: str = "restricted"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "operation_id": self.operation_id,
            "transaction_id": self.transaction_id,
            "operation_type": self.operation_type,
            "target_file": self.target_file,
            "target_content": self.target_content,
            "lease_token": self.lease_token,
            "deadline_utc": self.deadline_utc,
            "idempotency_key": self.idempotency_key,
            "required_runtime": self.required_runtime,
            "security_profile": self.security_profile,
            "metadata": redact_payload_secrets(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskAssignmentPayload:
        return cls(
            task_id=str(data["task_id"]),
            operation_id=str(data["operation_id"]),
            transaction_id=str(data["transaction_id"]),
            operation_type=str(data.get("operation_type", "MODIFY_FILE")),
            target_file=str(data["target_file"]),
            target_content=data.get("target_content"),
            lease_token=str(data.get("lease_token", "")),
            deadline_utc=str(data.get("deadline_utc", "")),
            idempotency_key=str(data.get("idempotency_key", "")),
            required_runtime=str(data.get("required_runtime", "process")),
            security_profile=str(data.get("security_profile", "restricted")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class TaskResultPayload:
    """Result report returned by a worker after completing an assigned task."""
    task_id: str
    operation_id: str = ""
    transaction_id: str = ""
    worker_id: str = ""
    lease_token: str = ""
    success: bool = True
    modified_files: List[str] = field(default_factory=list)
    created_files: List[str] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    validation_results: List[Dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.operation_id:
            self.operation_id = self.task_id
        if not self.transaction_id:
            self.transaction_id = "default_tx"


    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "operation_id": self.operation_id,
            "transaction_id": self.transaction_id,
            "worker_id": self.worker_id,
            "lease_token": self.lease_token,
            "success": self.success,
            "modified_files": self.modified_files,
            "created_files": self.created_files,
            "deleted_files": self.deleted_files,
            "artifacts": self.artifacts,
            "validation_results": self.validation_results,
            "duration_seconds": self.duration_seconds,
            "error_type": self.error_type,
            "error_message": redact_payload_secrets(self.error_message) if self.error_message else None,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskResultPayload:
        return cls(
            task_id=str(data["task_id"]),
            operation_id=str(data["operation_id"]),
            transaction_id=str(data["transaction_id"]),
            worker_id=str(data["worker_id"]),
            lease_token=str(data["lease_token"]),
            success=bool(data["success"]),
            modified_files=list(data.get("modified_files", [])),
            created_files=list(data.get("created_files", [])),
            deleted_files=list(data.get("deleted_files", [])),
            artifacts=list(data.get("artifacts", [])),
            validation_results=list(data.get("validation_results", [])),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            error_type=data.get("error_type"),
            error_message=data.get("error_message"),
            completed_at=data.get("completed_at", datetime.now(timezone.utc).isoformat()),
        )
