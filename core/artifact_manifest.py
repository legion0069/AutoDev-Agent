"""
artifact_manifest.py - Manifest Validation & Quota Enforcement for AutoDev (v2.3)

Validates artifact manifests submitted by workers, enforces safe path boundaries
(rejecting traversal, absolute paths, drive letters, and UNC paths), and verifies quotas.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Any, Dict, List, Optional, Set, Union

from core.artifact_models import ArtifactMetadata, ArtifactStatus, ArtifactType

logger = logging.getLogger("AutoDev.ArtifactManifest")


class ArtifactManifestError(Exception):
    """Raised when an artifact manifest is invalid or violates constraints."""
    pass


MAX_MANIFEST_ARTIFACTS = 500
MAX_TOTAL_MANIFEST_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_SINGLE_ARTIFACT_BYTES = 50 * 1024 * 1024   # 50 MB


def validate_safe_relative_path(path_str: str) -> str:
    """
    Strictly validates that a path is a safe relative workspace path.
    Rejects:
    - Path traversal (..)
    - Absolute paths (/ or \\)
    - Windows drive prefixes (C:)
    - UNC paths (\\\\server\\share)
    - Null bytes or control characters
    """
    if not path_str or not isinstance(path_str, str):
        raise ArtifactManifestError("Artifact relative path cannot be empty")

    if "\0" in path_str:
        raise ArtifactManifestError("Artifact path contains null byte")

    # Normalize slashes
    normalized = path_str.replace("\\", "/")

    if normalized.startswith("/") or normalized.startswith("//"):
        raise ArtifactManifestError(f"Artifact path cannot be absolute: '{path_str}'")

    if re.match(r"^[a-zA-Z]:", path_str):
        raise ArtifactManifestError(f"Artifact path cannot contain Windows drive letter: '{path_str}'")

    parts = normalized.split("/")
    for part in parts:
        if part in ("..", "."):
            raise ArtifactManifestError(f"Artifact path cannot contain traversal elements ('{part}'): '{path_str}'")
        if not part and part != parts[-1]: # empty segments like a//b
            raise ArtifactManifestError(f"Artifact path contains redundant slashes: '{path_str}'")

    return normalized


@dataclass
class ArtifactManifest:
    """Validated manifest describing a set of artifacts submitted by a worker."""
    manifest_id: str
    transaction_id: str
    plan_id: str
    operation_id: str
    worker_id: str
    attempt_id: int
    artifacts: List[ArtifactMetadata] = field(default_factory=list)
    manifest_version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def total_size_bytes(self) -> int:
        return sum(a.file_size_bytes for a in self.artifacts)

    @property
    def total_artifacts(self) -> int:
        return len(self.artifacts)

    def validate(self) -> None:
        """
        Validates the schema, quotas, and path constraints of the manifest.
        Raises ArtifactManifestError if any constraint is violated.
        """
        if not self.manifest_id or not self.transaction_id or not self.operation_id or not self.worker_id:
            raise ArtifactManifestError("Manifest missing mandatory identity fields (manifest_id, transaction_id, operation_id, worker_id)")

        if len(self.artifacts) > MAX_MANIFEST_ARTIFACTS:
            raise ArtifactManifestError(
                f"Manifest exceeds maximum allowed artifact count ({len(self.artifacts)} > {MAX_MANIFEST_ARTIFACTS})"
            )

        total_bytes = 0
        seen_paths: Set[str] = set()
        seen_ids: Set[str] = set()

        for art in self.artifacts:
            # Identity consistency
            if art.transaction_id != self.transaction_id:
                raise ArtifactManifestError(
                    f"Artifact {art.artifact_id} transaction_id '{art.transaction_id}' does not match manifest transaction_id '{self.transaction_id}'"
                )
            if art.operation_id != self.operation_id:
                raise ArtifactManifestError(
                    f"Artifact {art.artifact_id} operation_id '{art.operation_id}' does not match manifest operation_id '{self.operation_id}'"
                )

            # Deduplication
            if art.artifact_id in seen_ids:
                raise ArtifactManifestError(f"Duplicate artifact ID in manifest: '{art.artifact_id}'")
            seen_ids.add(art.artifact_id)

            # Safe path
            safe_path = validate_safe_relative_path(art.relative_path)
            if safe_path in seen_paths:
                raise ArtifactManifestError(f"Duplicate target path in manifest: '{art.relative_path}'")
            seen_paths.add(safe_path)

            # Size limits
            if art.file_size_bytes < 0:
                raise ArtifactManifestError(f"Artifact {art.artifact_id} has negative file size: {art.file_size_bytes}")
            if art.file_size_bytes > MAX_SINGLE_ARTIFACT_BYTES:
                raise ArtifactManifestError(
                    f"Artifact {art.artifact_id} exceeds max single artifact size ({art.file_size_bytes} > {MAX_SINGLE_ARTIFACT_BYTES})"
                )
            total_bytes += art.file_size_bytes

            # SHA-256 validation
            if not art.sha256_digest or len(art.sha256_digest) != 64 or not all(c in "0123456789abcdefABCDEF" for c in art.sha256_digest):
                raise ArtifactManifestError(f"Artifact {art.artifact_id} has invalid SHA-256 digest: '{art.sha256_digest}'")

        if total_bytes > MAX_TOTAL_MANIFEST_BYTES:
            raise ArtifactManifestError(
                f"Manifest exceeds maximum total payload size ({total_bytes} > {MAX_TOTAL_MANIFEST_BYTES})"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "transaction_id": self.transaction_id,
            "plan_id": self.plan_id,
            "operation_id": self.operation_id,
            "worker_id": self.worker_id,
            "attempt_id": self.attempt_id,
            "manifest_version": self.manifest_version,
            "created_at": self.created_at,
            "total_artifacts": self.total_artifacts,
            "total_size_bytes": self.total_size_bytes,
            "artifacts": [a.to_dict() for a in self.artifacts],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArtifactManifest:
        artifacts = [ArtifactMetadata.from_dict(a) for a in data.get("artifacts", [])]
        return cls(
            manifest_id=data["manifest_id"],
            transaction_id=data["transaction_id"],
            plan_id=data.get("plan_id", ""),
            operation_id=data["operation_id"],
            worker_id=data["worker_id"],
            attempt_id=data.get("attempt_id", 1),
            artifacts=artifacts,
            manifest_version=data.get("manifest_version", "1.0"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )
