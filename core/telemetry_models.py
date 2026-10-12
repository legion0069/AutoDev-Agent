"""
telemetry_models.py - Structured Telemetry Models & Severity Enums for AutoDev (v2.2)

Defines versioned telemetry events, severity levels, snapshot metrics,
and JSON serialization formats for live execution monitoring.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AutoDev.TelemetryModels")


class TelemetrySeverity(str, Enum):
    """Severity levels for telemetry events."""
    INFO = "INFO"
    WARNING = "WARNING"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class TelemetryEventType:
    """Standardized event type strings for AutoDev v2.0 - v2.4."""
    # HA & Consensus (v2.4)
    HA_COORDINATOR_REGISTERED = "ha.coordinator.registered"
    HA_ELECTION_STARTED = "ha.election.started"
    HA_LEADERSHIP_ELECTED = "ha.leadership.elected"
    HA_LEADERSHIP_LOST = "ha.leadership.lost"
    HA_FENCING_VIOLATION = "ha.fencing.violation"
    HA_QUORUM_LOST = "ha.quorum.lost"
    HA_FAILOVER_RECONCILED = "ha.failover.reconciled"

    # Kubernetes Worker Orchestration (v2.4)
    K8S_POOL_RECONCILED = "k8s.pool.reconciled"
    K8S_WORKER_SCALED = "k8s.worker.scaled"
    K8S_PROVISIONING_ERROR = "k8s.provisioning.error"

    # Differential Artifact Synchronization (v2.4)
    ARTIFACT_CHUNK_STORED = "artifact.chunk.stored"
    ARTIFACT_SYNC_NEGOTIATED = "artifact.sync.negotiated"
    ARTIFACT_CHUNK_TRANSFERRED = "artifact.chunk.transferred"
    ARTIFACT_RECONSTRUCTED = "artifact.reconstructed"
    ARTIFACT_GC_COMPLETED = "artifact.gc.completed"

    # Interactive Debugging Terminal (v2.4)
    DEBUG_SESSION_CREATED = "debug.session.created"
    DEBUG_SESSION_TERMINATED = "debug.session.terminated"
    TERMINAL_SECURITY_DENIAL = "terminal.security.denial"

    # External Consensus & Fencing (v2.5)
    CONSENSUS_PROVIDER_ELECTED = "consensus.provider.elected"
    CONSENSUS_LEASE_RENEWED = "consensus.lease.renewed"
    CONSENSUS_LEASE_EXPIRED = "consensus.lease.expired"
    CONSENSUS_PARTITION_DETECTED = "consensus.partition.detected"
    CONSENSUS_FENCING_REJECTED = "consensus.fencing.rejected"

    # Runtime Isolation & eBPF Security (v2.5)
    ISOLATION_SANDBOX_CREATED = "isolation.sandbox.created"
    ISOLATION_VIOLATION_DETECTED = "isolation.violation.detected"
    ISOLATION_PROCESS_DENIED = "isolation.process.denied"
    EBPF_PROBE_ATTACHED = "ebpf.probe.attached"
    EBPF_VIOLATION_TRIGGERED = "ebpf.violation.triggered"

    # Fleet-Scale P2P Artifact Distribution (v2.5)
    ARTIFACT_PEER_REGISTERED = "artifact.peer.registered"
    ARTIFACT_PEER_EXPIRED = "artifact.peer.expired"
    ARTIFACT_P2P_TRANSFER_STARTED = "artifact.p2p.transfer.started"
    ARTIFACT_P2P_TRANSFER_COMPLETED = "artifact.p2p.transfer.completed"
    ARTIFACT_REPLICATION_EXECUTED = "artifact.replication.executed"

    # WebRTC Remote Debugging Transport (v2.5)
    WEBRTC_SESSION_SIGNALED = "webrtc.session.signaled"
    WEBRTC_DATA_CHANNEL_OPENED = "webrtc.data_channel.opened"
    WEBRTC_DATA_CHANNEL_CLOSED = "webrtc.data_channel.closed"
    WEBRTC_FALLBACK_TRIGGERED = "webrtc.fallback.triggered"

    # Autonomous Self-Healing & Test Intelligence (v2.6)
    TEST_EXECUTION_STARTED = "test.execution.started"
    TEST_EXECUTION_COMPLETED = "test.execution.completed"
    FAILURE_CLASSIFIED = "failure.classified"
    ROOT_CAUSE_HYPOTHESIS_GENERATED = "root_cause.hypothesis.generated"
    REPAIR_PLAN_GENERATED = "repair.plan.generated"
    CANDIDATE_PATCH_GENERATED = "candidate.patch.generated"
    PATCH_VALIDATED = "patch.validated"
    PATCH_REJECTED = "patch.rejected"
    CANDIDATE_VERIFICATION_STARTED = "candidate.verification.started"
    CANDIDATE_VERIFICATION_FAILED = "candidate.verification.failed"
    REPAIR_ACCEPTED = "repair.accepted"
    ROLLBACK_STARTED = "rollback.started"
    ROLLBACK_COMPLETED = "rollback.completed"
    ROLLBACK_FAILED = "rollback.failed"
    HUMAN_APPROVAL_REQUESTED = "human.approval.requested"
    HUMAN_APPROVAL_GRANTED = "human.approval.granted"
    HUMAN_APPROVAL_DENIED = "human.approval.denied"
    REPAIR_BUDGET_EXHAUSTED = "repair.budget.exhausted"

    # Predictive Failure Prevention & Quality Intelligence (v2.7)
    QUALITY_ASSESSMENT_STARTED = "quality.assessment.started"
    QUALITY_ASSESSMENT_COMPLETED = "quality.assessment.completed"
    QUALITY_GATE_PASSED = "quality.gate.passed"
    QUALITY_GATE_REJECTED = "quality.gate.rejected"
    QUALITY_RISK_PREDICTED = "quality.risk.predicted"
    QUALITY_TREND_UPDATED = "quality.trend.updated"


# Secret redaction helper
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|auth|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"),
    re.compile(r"(?i)sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"(?i)AIza[0-9A-Za-z\-_]{35}"),
    re.compile(r"(?i)Bearer\s+[a-zA-Z0-9_\-\.]{20,}"),
]

def redact_telemetry_payload(data: Any) -> Any:
    """Recursively redacts API keys and secrets from telemetry payloads."""
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if any(term in k.lower() for term in ["key", "secret", "token", "password", "auth"]):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_telemetry_payload(v)
        return redacted
    elif isinstance(data, list):
        return [redact_telemetry_payload(x) for x in data]
    elif isinstance(data, str):
        res = SECRET_PATTERNS[0].sub(r"\1: [REDACTED]", data)
        for pat in SECRET_PATTERNS[1:]:
            res = pat.sub("[REDACTED]", res)
        return res
    return data


@dataclass
class TelemetryEvent:
    """Individual real-time event published during plan execution or worker lifecycle."""
    event_type: str = "EVENT"
    event_id: str = ""
    source_component: str = "AutoDev"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    transaction_id: Optional[str] = None
    plan_id: Optional[str] = None
    stage_id: Optional[int] = None
    operation_id: Optional[str] = None
    worker_id: Optional[str] = None
    container_id: Optional[str] = None
    severity: TelemetrySeverity = TelemetrySeverity.INFO
    status: Optional[str] = None
    duration_ms: Optional[float] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    payload: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.payload is not None and not self.metadata:
            self.metadata = self.payload
        elif self.metadata and self.payload is None:
            self.payload = self.metadata
        if isinstance(self.severity, str):
            try:
                self.severity = TelemetrySeverity(self.severity)
            except ValueError:
                self.severity = TelemetrySeverity.INFO


    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "transaction_id": self.transaction_id,
            "plan_id": self.plan_id,
            "stage_id": self.stage_id,
            "operation_id": self.operation_id,
            "worker_id": self.worker_id,
            "container_id": self.container_id,
            "severity": self.severity.value,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "message": redact_telemetry_payload(self.message),
            "metadata": redact_telemetry_payload(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TelemetryEvent:
        sev_val = data.get("severity", TelemetrySeverity.INFO.value)
        try:
            sev = TelemetrySeverity(sev_val)
        except ValueError:
            sev = TelemetrySeverity.INFO

        return cls(
            event_id=str(data["event_id"]),
            event_type=str(data["event_type"]),
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
            transaction_id=data.get("transaction_id"),
            plan_id=data.get("plan_id"),
            stage_id=data.get("stage_id"),
            operation_id=data.get("operation_id"),
            worker_id=data.get("worker_id"),
            container_id=data.get("container_id"),
            severity=sev,
            status=data.get("status"),
            duration_ms=data.get("duration_ms"),
            message=str(data.get("message", "")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class TelemetrySnapshot:
    """Aggregated real-time metrics snapshot across the coordinator and active workers."""
    coordinator_status: str = "HEALTHY"
    active_transactions_count: int = 0
    registered_workers_count: int = 0
    idle_workers_count: int = 0
    busy_workers_count: int = 0
    unreachable_workers_count: int = 0
    queued_operations_count: int = 0
    completed_operations_count: int = 0
    failed_operations_count: int = 0
    last_event_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
