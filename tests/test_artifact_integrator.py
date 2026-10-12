"""
test_artifact_integrator.py - Unit & Integration tests for ArtifactIntegrator & Rollbacks (v2.3)
"""

import hashlib
from pathlib import Path
import pytest

from core.artifact_integrator import ArtifactIntegrator
from core.artifact_manifest import ArtifactManifest
from core.artifact_models import ArtifactMetadata, ArtifactStatus, ArtifactType
from core.artifact_store import ArtifactStore
from core.artifact_verifier import ArtifactVerifier
from core.execution_journal import ExecutionJournal
from core.execution_transaction import ExecutionTransaction
from core.telemetry_stream import TelemetryStream


@pytest.fixture
def test_setup(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    staging = tmp_path / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    store = ArtifactStore(base_staging_dir=staging)
    verifier = ArtifactVerifier()
    journal = ExecutionJournal(journal_dir=tmp_path / "journal")
    stream = TelemetryStream()
    integrator = ArtifactIntegrator(
        workspace_root=ws,
        artifact_store=store,
        artifact_verifier=verifier,
        journal=journal,
        telemetry_stream=stream,
    )
    return ws, store, integrator


def test_artifact_integrator_success(test_setup):
    ws, store, integrator = test_setup

    content = b"print('version 2.3 active')\n"
    digest = hashlib.sha256(content).hexdigest()
    size = len(content)

    store.stage_artifact_bytes("tx-int-1", "art-01", content)

    art = ArtifactMetadata(
        artifact_id="art-01",
        transaction_id="tx-int-1",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="src/app.py",
        file_size_bytes=size,
        sha256_digest=digest,
    )
    manifest = ArtifactManifest(
        manifest_id="mf-int-1",
        transaction_id="tx-int-1",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifacts=[art],
    )

    tx = ExecutionTransaction(transaction_id="tx-int-1", plan_id="p1")
    result = integrator.integrate_manifest(manifest, transaction=tx, validation_gate=lambda: True)

    assert result.success
    assert "art-01" in result.integrated_artifacts
    assert (ws / "src" / "app.py").exists()
    assert (ws / "src" / "app.py").read_bytes() == content


def test_artifact_integrator_validation_failure_and_rollback(test_setup):
    ws, store, integrator = test_setup

    # Pre-existing file
    target_file = ws / "config.json"
    target_file.write_text('{"env": "production"}', encoding="utf-8")
    original_bytes = target_file.read_bytes()

    # Worker attempts to overwrite config.json
    new_content = b'{"env": "broken_test"}'
    store.stage_artifact_bytes("tx-int-2", "art-02", new_content)

    art = ArtifactMetadata(
        artifact_id="art-02",
        transaction_id="tx-int-2",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="config.json",
        file_size_bytes=len(new_content),
        sha256_digest=hashlib.sha256(new_content).hexdigest(),
    )
    manifest = ArtifactManifest(
        manifest_id="mf-int-2",
        transaction_id="tx-int-2",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifacts=[art],
    )

    tx = ExecutionTransaction(transaction_id="tx-int-2", plan_id="p1")

    # Validation gate returns False (simulating failing unit test suite)
    result = integrator.integrate_manifest(manifest, transaction=tx, validation_gate=lambda: False)

    assert not result.success
    assert result.rollback_executed
    assert not result.validation_passed

    # Verify original file content restored
    assert target_file.read_bytes() == original_bytes


def test_artifact_integrator_multiple_files_atomic(test_setup):
    ws, store, integrator = test_setup

    c1 = b"def f1(): return 1\n"
    c2 = b"def f2(): return 2\n"

    store.stage_artifact_bytes("tx-multi", "art-1", c1)
    store.stage_artifact_bytes("tx-multi", "art-2", c2)

    art1 = ArtifactMetadata(
        artifact_id="art-1",
        transaction_id="tx-multi",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="pkg/f1.py",
        file_size_bytes=len(c1),
        sha256_digest=hashlib.sha256(c1).hexdigest(),
    )
    art2 = ArtifactMetadata(
        artifact_id="art-2",
        transaction_id="tx-multi",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="pkg/f2.py",
        file_size_bytes=len(c2),
        sha256_digest=hashlib.sha256(c2).hexdigest(),
    )
    manifest = ArtifactManifest(
        manifest_id="mf-multi",
        transaction_id="tx-multi",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifacts=[art1, art2],
    )

    tx = ExecutionTransaction(transaction_id="tx-multi", plan_id="p1")
    result = integrator.integrate_manifest(manifest, transaction=tx)

    assert result.success
    assert len(result.integrated_artifacts) == 2
    assert (ws / "pkg" / "f1.py").read_bytes() == c1
    assert (ws / "pkg" / "f2.py").read_bytes() == c2


def test_artifact_integrator_corrupted_staged_artifact(test_setup):
    ws, store, integrator = test_setup

    # Stage content that doesn't match manifest digest
    staged_content = b"actual content"
    store.stage_artifact_bytes("tx-corrupt", "art-bad", staged_content)

    art = ArtifactMetadata(
        artifact_id="art-bad",
        transaction_id="tx-corrupt",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="bad.py",
        file_size_bytes=len(staged_content),
        sha256_digest="f" * 64,  # mismatched hash
    )
    manifest = ArtifactManifest(
        manifest_id="mf-corrupt",
        transaction_id="tx-corrupt",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifacts=[art],
    )

    tx = ExecutionTransaction(transaction_id="tx-corrupt", plan_id="p1")
    result = integrator.integrate_manifest(manifest, transaction=tx)

    assert not result.success
    assert not (ws / "bad.py").exists()

