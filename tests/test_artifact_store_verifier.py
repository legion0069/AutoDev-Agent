"""
test_artifact_store_verifier.py - Unit tests for ArtifactStore & ArtifactVerifier (v2.3)
"""

import hashlib
import io
from pathlib import Path
import zipfile
import pytest

from core.artifact_manifest import ArtifactManifest
from core.artifact_models import ArtifactMetadata, ArtifactStatus, ArtifactType
from core.artifact_store import ArtifactStore, ArtifactStoreError
from core.artifact_verifier import ArtifactVerifier


def test_artifact_store_atomic_staging(tmp_path):
    store = ArtifactStore(base_staging_dir=tmp_path / "staging")
    data = b"print('hello world')\n"
    path = store.stage_artifact_bytes("tx-999", "art-1", data)

    assert path.exists()
    assert store.read_staged_artifact_bytes("tx-999", "art-1") == data

    # Cleanup
    store.cleanup_transaction("tx-999")
    assert not (tmp_path / "staging" / "tx-999").exists()


def test_artifact_store_safe_zip_extraction(tmp_path):
    store = ArtifactStore(base_staging_dir=tmp_path / "staging")

    # Create safe zip in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("module/utils.py", "def foo(): pass\n")
    zip_bytes = buf.getvalue()

    out_dir = tmp_path / "extracted"
    extracted = store.extract_safe_archive(zip_bytes, out_dir, is_zip=True)
    assert len(extracted) == 1
    assert (out_dir / "module" / "utils.py").exists()


def test_artifact_store_zip_slip_rejection(tmp_path):
    store = ArtifactStore(base_staging_dir=tmp_path / "staging")

    # Create malicious zip with traversal
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../escape.txt", "malicious content")
    bad_zip_bytes = buf.getvalue()

    out_dir = tmp_path / "extracted_bad"
    with pytest.raises(Exception):
        store.extract_safe_archive(bad_zip_bytes, out_dir, is_zip=True)


def test_artifact_verifier_digest_and_size_checks():
    verifier = ArtifactVerifier()
    content = b"def test_app(): assert True\n"
    digest = hashlib.sha256(content).hexdigest()
    size = len(content)

    meta_valid = ArtifactMetadata(
        artifact_id="art-valid",
        transaction_id="tx-1",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="tests/test_app.py",
        file_size_bytes=size,
        sha256_digest=digest,
    )

    # 1. Valid
    res = verifier.verify_artifact_bytes(meta_valid, content, expected_worker_id="w1", expected_transaction_id="tx-1")
    assert res.is_valid
    assert meta_valid.status == ArtifactStatus.VERIFIED

    # 2. Corrupted content / hash mismatch
    meta_corrupt = ArtifactMetadata(
        artifact_id="art-corrupt",
        transaction_id="tx-1",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="tests/test_app.py",
        file_size_bytes=size,
        sha256_digest="0" * 64,
    )
    res2 = verifier.verify_artifact_bytes(meta_corrupt, content)
    assert not res2.is_valid
    assert meta_corrupt.status == ArtifactStatus.REJECTED
    assert "SHA-256 digest mismatch" in res2.error_message


def test_artifact_verifier_size_mismatch():
    verifier = ArtifactVerifier()
    content = b"sample content"
    digest = hashlib.sha256(content).hexdigest()

    meta = ArtifactMetadata(
        artifact_id="art-size-bad",
        transaction_id="tx-1",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="sample.txt",
        file_size_bytes=9999,  # Incorrect size
        sha256_digest=digest,
    )
    res = verifier.verify_artifact_bytes(meta, content)
    assert not res.is_valid
    assert "Size mismatch" in res.error_message


def test_artifact_verifier_worker_and_transaction_mismatch():
    verifier = ArtifactVerifier()
    content = b"sample content"
    digest = hashlib.sha256(content).hexdigest()

    meta = ArtifactMetadata(
        artifact_id="art-w-bad",
        transaction_id="tx-actual",
        plan_id="p1",
        operation_id="op1",
        worker_id="w-actual",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="sample.txt",
        file_size_bytes=len(content),
        sha256_digest=digest,
    )

    # Worker mismatch
    res_w = verifier.verify_artifact_bytes(meta, content, expected_worker_id="w-other")
    assert not res_w.is_valid
    assert "Worker ID mismatch" in res_w.error_message

    # Transaction mismatch
    res_tx = verifier.verify_artifact_bytes(meta, content, expected_transaction_id="tx-other")
    assert not res_tx.is_valid
    assert "Transaction ID mismatch" in res_tx.error_message

