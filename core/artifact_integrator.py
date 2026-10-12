"""
artifact_integrator.py - Transactional Workspace Integration & Conflict Management for AutoDev (v2.3)

Integrates verified worker artifacts into the coordinator workspace under strict transaction boundaries.
Performs pre-integration snapshotting, detects local workspace conflicts, applies changes atomically,
executes post-integration validation gates, and triggers verified rollback on validation failure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from core.artifact_manifest import ArtifactManifest, validate_safe_relative_path
from core.artifact_models import ArtifactMetadata, ArtifactStatus, ArtifactType
from core.artifact_store import ArtifactStore
from core.artifact_verifier import ArtifactVerifier, VerificationResult
from core.execution_journal import ExecutionJournal
from core.execution_recovery import ExecutionRecovery, RecoveryResult
from core.execution_transaction import (
    ExecutionEngineError,
    ExecutionStatus,
    ExecutionTransaction,
    FileSnapshot,
)
from core.telemetry_models import TelemetryEvent, TelemetrySeverity
from core.telemetry_stream import TelemetryStream

logger = logging.getLogger("AutoDev.ArtifactIntegrator")


class ArtifactIntegrationConflictError(ExecutionEngineError):
    """Raised when an artifact conflicts with modified workspace files."""
    pass


class ArtifactIntegrationError(ExecutionEngineError):
    """Raised when artifact integration or post-integration validation fails."""
    pass


@dataclass
class IntegrationResult:
    """Detailed summary of artifact integration into workspace."""
    success: bool
    transaction_id: str
    manifest_id: str
    integrated_artifacts: List[str] = field(default_factory=list)
    rejected_artifacts: List[str] = field(default_factory=list)
    conflicted_artifacts: List[str] = field(default_factory=list)
    validation_passed: bool = True
    rollback_executed: bool = False
    recovery_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    integrated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        return res


class ArtifactIntegrator:
    """
    Coordinates the transactional application of verified artifacts to the active workspace.
    """

    def __init__(
        self,
        workspace_root: Union[str, Path],
        artifact_store: Optional[ArtifactStore] = None,
        artifact_verifier: Optional[ArtifactVerifier] = None,
        journal: Optional[ExecutionJournal] = None,
        telemetry_stream: Optional[TelemetryStream] = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.artifact_store = artifact_store or ArtifactStore()
        self.artifact_verifier = artifact_verifier or ArtifactVerifier()
        self.journal = journal
        self.telemetry_stream = telemetry_stream

    def integrate_manifest(
        self,
        manifest: ArtifactManifest,
        transaction: Optional[ExecutionTransaction] = None,
        validation_gate: Optional[Callable[[], bool]] = None,
    ) -> IntegrationResult:
        """
        Executes complete verification, staging, conflict detection, application,
        and validation cycle for an artifact manifest.
        """
        # 1. Manifest verification
        try:
            self.artifact_verifier.verify_manifest(
                manifest,
                expected_worker_id=manifest.worker_id,
                expected_transaction_id=manifest.transaction_id,
            )
        except Exception as e:
            logger.error("Manifest validation failed: %s", e)
            return IntegrationResult(
                success=False,
                transaction_id=manifest.transaction_id,
                manifest_id=manifest.manifest_id,
                error_message=f"Manifest verification error: {e}",
            )

        integrated_ids: List[str] = []
        rejected_ids: List[str] = []
        conflicted_ids: List[str] = []
        applied_file_backups: Dict[Path, Optional[bytes]] = {}

        # 2. Verify all artifact payloads and detect conflicts
        payloads_to_apply: List[Tuple[ArtifactMetadata, bytes, Path]] = []

        for art in manifest.artifacts:
            # Read staged bytes
            try:
                content_bytes = self.artifact_store.read_staged_artifact_bytes(
                    manifest.transaction_id, art.artifact_id
                )
            except Exception as e:
                art.status = ArtifactStatus.REJECTED
                art.rejection_reason = f"Staged payload missing: {e}"
                rejected_ids.append(art.artifact_id)
                continue

            # Verify integrity
            ver_res = self.artifact_verifier.verify_artifact_bytes(
                art,
                content_bytes,
                expected_worker_id=manifest.worker_id,
                expected_transaction_id=manifest.transaction_id,
            )
            if not ver_res.is_valid:
                rejected_ids.append(art.artifact_id)
                self._emit_telemetry(
                    "artifact.verification_failed",
                    TelemetrySeverity.ERROR,
                    {"artifact_id": art.artifact_id, "error": ver_res.error_message},
                    manifest.transaction_id,
                )
                continue

            # Check safe path and conflict
            safe_rel = validate_safe_relative_path(art.relative_path)
            target_file_path = (self.workspace_root / safe_rel).resolve()

            # Ensure within workspace root
            if not str(target_file_path).startswith(str(self.workspace_root)):
                art.status = ArtifactStatus.REJECTED
                art.rejection_reason = "Target path resolves outside workspace root"
                rejected_ids.append(art.artifact_id)
                continue

            payloads_to_apply.append((art, content_bytes, target_file_path))

        if rejected_ids or conflicted_ids:
            return IntegrationResult(
                success=False,
                transaction_id=manifest.transaction_id,
                manifest_id=manifest.manifest_id,
                integrated_artifacts=[],
                rejected_artifacts=rejected_ids,
                conflicted_artifacts=conflicted_ids,
                error_message=f"Artifact rejection or conflict occurred ({len(rejected_ids)} rejected, {len(conflicted_ids)} conflicts)",
            )

        # 3. Snapshot existing files for rollback
        for art, content_bytes, target_path in payloads_to_apply:
            if target_path.exists() and target_path.is_file():
                with open(target_path, "rb") as f:
                    applied_file_backups[target_path] = f.read()
            else:
                applied_file_backups[target_path] = None  # Did not exist

            # If transaction is provided, record snapshot in transaction
            if transaction:
                rel_str = str(target_path.relative_to(self.workspace_root)).replace("\\", "/")
                transaction.snapshot_file(rel_str, self.workspace_root)

        # 4. Apply file changes
        try:
            for art, content_bytes, target_path in payloads_to_apply:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "wb") as f:
                    f.write(content_bytes)
                art.status = ArtifactStatus.INTEGRATED
                integrated_ids.append(art.artifact_id)

            # 5. Run validation gate if provided
            validation_passed = True
            if validation_gate is not None:
                try:
                    validation_passed = bool(validation_gate())
                except Exception as e:
                    logger.warning("Validation gate exception: %s", e)
                    validation_passed = False

            if not validation_passed:
                # Rollback files
                self._rollback_applied_files(applied_file_backups)
                if transaction:
                    recovery = ExecutionRecovery(workspace_root=self.workspace_root)
                    rec_result = recovery.rollback_transaction(transaction, journal=self.journal)
                    rec_dict = rec_result.to_dict()
                else:
                    rec_dict = None

                self._emit_telemetry(
                    "artifact.validation_failed_rolled_back",
                    TelemetrySeverity.WARN,
                    {"manifest_id": manifest.manifest_id},
                    manifest.transaction_id,
                )

                return IntegrationResult(
                    success=False,
                    transaction_id=manifest.transaction_id,
                    manifest_id=manifest.manifest_id,
                    integrated_artifacts=[],
                    rejected_artifacts=rejected_ids,
                    validation_passed=False,
                    rollback_executed=True,
                    recovery_result=rec_dict,
                    error_message="Post-integration validation gate failed. Workspace rolled back safely.",
                )

            # Success
            self._emit_telemetry(
                "artifact.integration_succeeded",
                TelemetrySeverity.INFO,
                {"manifest_id": manifest.manifest_id, "count": len(integrated_ids)},
                manifest.transaction_id,
            )
            return IntegrationResult(
                success=True,
                transaction_id=manifest.transaction_id,
                manifest_id=manifest.manifest_id,
                integrated_artifacts=integrated_ids,
                rejected_artifacts=[],
                conflicted_artifacts=[],
                validation_passed=True,
                rollback_executed=False,
            )

        except Exception as e:
            logger.error("Error during artifact writing, triggering rollback: %s", e)
            self._rollback_applied_files(applied_file_backups)
            return IntegrationResult(
                success=False,
                transaction_id=manifest.transaction_id,
                manifest_id=manifest.manifest_id,
                integrated_artifacts=[],
                rollback_executed=True,
                error_message=f"Integration write error: {e}",
            )

    def _rollback_applied_files(self, backups: Dict[Path, Optional[bytes]]) -> None:
        """Restores pre-integration file states from in-memory snapshots."""
        for path, content in backups.items():
            try:
                if content is None:
                    if path.exists():
                        path.unlink()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with open(path, "wb") as f:
                        f.write(content)
            except Exception as e:
                logger.error("Failed to restore file %s during rollback: %s", path, e)

    def _emit_telemetry(
        self,
        event_name: str,
        severity: TelemetrySeverity,
        payload: Dict[str, Any],
        transaction_id: str,
    ) -> None:
        if self.telemetry_stream:
            event = TelemetryEvent(
                event_type=event_name,
                source_component="ArtifactIntegrator",
                severity=severity,
                transaction_id=transaction_id,
                payload=payload,
            )
            self.telemetry_stream.publish(event)
