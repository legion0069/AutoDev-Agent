"""
artifact_verifier.py - Cryptographic Digest & Path Integrity Verification for AutoDev (v2.3)

Performs mandatory, independent verification of received worker artifacts:
recomputes SHA-256 digests over raw bytes, validates exact byte lengths,
enforces transaction and lease ownership boundaries, and records rejection telemetry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple

from core.artifact_manifest import ArtifactManifest, validate_safe_relative_path
from core.artifact_models import ArtifactMetadata, ArtifactStatus, ArtifactType
from core.task_lease_manager import TaskLeaseManager

logger = logging.getLogger("AutoDev.ArtifactVerifier")


class ArtifactVerificationError(Exception):
    """Raised when artifact integrity or authenticity verification fails."""
    pass


@dataclass
class VerificationResult:
    """Result of an artifact verification operation."""
    is_valid: bool
    artifact_id: str
    recomputed_digest: str
    declared_digest: str
    recomputed_size_bytes: int
    declared_size_bytes: int
    error_message: Optional[str] = None
    verified_at: str = ""

    def __post_init__(self) -> None:
        if not self.verified_at:
            self.verified_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "artifact_id": self.artifact_id,
            "recomputed_digest": self.recomputed_digest,
            "declared_digest": self.declared_digest,
            "recomputed_size_bytes": self.recomputed_size_bytes,
            "declared_size_bytes": self.declared_size_bytes,
            "error_message": self.error_message,
            "verified_at": self.verified_at,
        }


class ArtifactVerifier:
    """
    Independent verification gate for worker-submitted artifacts before staging and integration.
    """

    def __init__(self, lease_manager: Optional[TaskLeaseManager] = None) -> None:
        self.lease_manager = lease_manager

    def verify_artifact_bytes(
        self,
        metadata: ArtifactMetadata,
        content_bytes: bytes,
        expected_worker_id: Optional[str] = None,
        expected_transaction_id: Optional[str] = None,
    ) -> VerificationResult:
        """
        Verifies that actual received bytes match declared metadata.
        Never trusts worker-supplied hashes or sizes without independent computation.
        """
        recomputed_size = len(content_bytes)
        recomputed_digest = hashlib.sha256(content_bytes).hexdigest()

        # 1. Size match
        if recomputed_size != metadata.file_size_bytes:
            err = f"Size mismatch for artifact {metadata.artifact_id}: declared {metadata.file_size_bytes}B, received {recomputed_size}B"
            metadata.status = ArtifactStatus.REJECTED
            metadata.rejection_reason = err
            return VerificationResult(
                is_valid=False,
                artifact_id=metadata.artifact_id,
                recomputed_digest=recomputed_digest,
                declared_digest=metadata.sha256_digest,
                recomputed_size_bytes=recomputed_size,
                declared_size_bytes=metadata.file_size_bytes,
                error_message=err,
            )

        # 2. SHA-256 Digest match
        if recomputed_digest.lower() != metadata.sha256_digest.lower():
            err = f"SHA-256 digest mismatch for artifact {metadata.artifact_id}: declared {metadata.sha256_digest}, recomputed {recomputed_digest}"
            metadata.status = ArtifactStatus.REJECTED
            metadata.rejection_reason = err
            return VerificationResult(
                is_valid=False,
                artifact_id=metadata.artifact_id,
                recomputed_digest=recomputed_digest,
                declared_digest=metadata.sha256_digest,
                recomputed_size_bytes=recomputed_size,
                declared_size_bytes=metadata.file_size_bytes,
                error_message=err,
            )

        # 3. Path safety check
        try:
            validate_safe_relative_path(metadata.relative_path)
        except Exception as e:
            err = f"Path safety violation in artifact {metadata.artifact_id}: {e}"
            metadata.status = ArtifactStatus.REJECTED
            metadata.rejection_reason = err
            return VerificationResult(
                is_valid=False,
                artifact_id=metadata.artifact_id,
                recomputed_digest=recomputed_digest,
                declared_digest=metadata.sha256_digest,
                recomputed_size_bytes=recomputed_size,
                declared_size_bytes=metadata.file_size_bytes,
                error_message=err,
            )

        # 4. Identity & Transaction ownership checks
        if expected_worker_id and metadata.worker_id != expected_worker_id:
            err = f"Worker ID mismatch for artifact {metadata.artifact_id}: expected '{expected_worker_id}', got '{metadata.worker_id}'"
            metadata.status = ArtifactStatus.REJECTED
            metadata.rejection_reason = err
            return VerificationResult(
                is_valid=False,
                artifact_id=metadata.artifact_id,
                recomputed_digest=recomputed_digest,
                declared_digest=metadata.sha256_digest,
                recomputed_size_bytes=recomputed_size,
                declared_size_bytes=metadata.file_size_bytes,
                error_message=err,
            )

        if expected_transaction_id and metadata.transaction_id != expected_transaction_id:
            err = f"Transaction ID mismatch for artifact {metadata.artifact_id}: expected '{expected_transaction_id}', got '{metadata.transaction_id}'"
            metadata.status = ArtifactStatus.REJECTED
            metadata.rejection_reason = err
            return VerificationResult(
                is_valid=False,
                artifact_id=metadata.artifact_id,
                recomputed_digest=recomputed_digest,
                declared_digest=metadata.sha256_digest,
                recomputed_size_bytes=recomputed_size,
                declared_size_bytes=metadata.file_size_bytes,
                error_message=err,
            )

        # 5. Lease validation if lease_manager present
        if self.lease_manager:
            lease = self.lease_manager.get_lease(metadata.operation_id)
            if lease and lease.worker_id != metadata.worker_id:
                err = f"Lease ownership violation: operation {metadata.operation_id} held by {lease.worker_id}, artifact submitted by {metadata.worker_id}"
                metadata.status = ArtifactStatus.REJECTED
                metadata.rejection_reason = err
                return VerificationResult(
                    is_valid=False,
                    artifact_id=metadata.artifact_id,
                    recomputed_digest=recomputed_digest,
                    declared_digest=metadata.sha256_digest,
                    recomputed_size_bytes=recomputed_size,
                    declared_size_bytes=metadata.file_size_bytes,
                    error_message=err,
                )

        metadata.status = ArtifactStatus.VERIFIED
        return VerificationResult(
            is_valid=True,
            artifact_id=metadata.artifact_id,
            recomputed_digest=recomputed_digest,
            declared_digest=metadata.sha256_digest,
            recomputed_size_bytes=recomputed_size,
            declared_size_bytes=metadata.file_size_bytes,
        )

    def verify_manifest(
        self,
        manifest: ArtifactManifest,
        expected_worker_id: Optional[str] = None,
        expected_transaction_id: Optional[str] = None,
    ) -> None:
        """
        Validates the overall manifest structure and ownership bounds.
        Raises ArtifactVerificationError on failure.
        """
        try:
            manifest.validate()
        except Exception as e:
            raise ArtifactVerificationError(f"Manifest schema validation failed: {e}") from e

        if expected_worker_id and manifest.worker_id != expected_worker_id:
            raise ArtifactVerificationError(
                f"Manifest worker ID mismatch: expected '{expected_worker_id}', got '{manifest.worker_id}'"
            )

        if expected_transaction_id and manifest.transaction_id != expected_transaction_id:
            raise ArtifactVerificationError(
                f"Manifest transaction ID mismatch: expected '{expected_transaction_id}', got '{manifest.transaction_id}'"
            )
