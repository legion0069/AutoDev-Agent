"""
artifact_models.py - Artifact Types, Metadata & Status Models for AutoDev (v2.3)

Defines strongly-typed data structures for distributed worker artifact tracking,
cryptographic verification, and transactional workspace integration.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class ArtifactType(str, Enum):
    """Classification of artifacts produced by remote or local workers."""
    SOURCE_CODE = "source_code"
    TEST_RESULTS = "test_results"
    BUILD_OUTPUT = "build_output"
    LOG_OUTPUT = "log_output"
    DIFF_PATCH = "diff_patch"
    REPORT = "report"
    BINARY = "binary"


class ArtifactStatus(str, Enum):
    """Lifecycle status of a received artifact."""
    STAGED = "staged"
    VERIFIED = "verified"
    INTEGRATED = "integrated"
    REJECTED = "rejected"
    CONFLICT = "conflict"


@dataclass
class ArtifactMetadata:
    """Detailed metadata for a single worker-produced artifact."""
    artifact_id: str
    transaction_id: str
    plan_id: str
    operation_id: str
    worker_id: str
    attempt_id: int
    artifact_type: ArtifactType
    relative_path: str
    file_size_bytes: int
    sha256_digest: str
    media_type: str = "text/plain"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    producer_identity: Optional[str] = None
    manifest_version: str = "1.0"
    status: ArtifactStatus = ArtifactStatus.STAGED
    rejection_reason: Optional[str] = None
    signature: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["artifact_type"] = self.artifact_type.value
        res["status"] = self.status.value
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArtifactMetadata:
        data_copy = dict(data)
        if isinstance(data_copy.get("artifact_type"), str):
            data_copy["artifact_type"] = ArtifactType(data_copy["artifact_type"])
        if isinstance(data_copy.get("status"), str):
            data_copy["status"] = ArtifactStatus(data_copy["status"])
        return cls(**data_copy)
