"""
test_artifact_manifest.py - Unit tests for ArtifactManifest & Path Sanitization (v2.3)
"""

import pytest
from core.artifact_manifest import (
    ArtifactManifest,
    ArtifactManifestError,
    validate_safe_relative_path,
)
from core.artifact_models import ArtifactMetadata, ArtifactType


def test_validate_safe_relative_path():
    assert validate_safe_relative_path("src/core/utils.py") == "src/core/utils.py"
    assert validate_safe_relative_path("README.md") == "README.md"
    assert validate_safe_relative_path("tests\\sub\\test_x.py") == "tests/sub/test_x.py"

    # Traversal rejection
    with pytest.raises(ArtifactManifestError, match="traversal elements"):
        validate_safe_relative_path("../secret.txt")

    with pytest.raises(ArtifactManifestError, match="traversal elements"):
        validate_safe_relative_path("src/../../secret.txt")

    # Absolute path rejection
    with pytest.raises(ArtifactManifestError, match="cannot be absolute"):
        validate_safe_relative_path("/etc/passwd")

    # Windows drive letter rejection
    with pytest.raises(ArtifactManifestError, match="Windows drive letter"):
        validate_safe_relative_path("C:\\Windows\\System32")


def test_artifact_manifest_validation_success():
    art = ArtifactMetadata(
        artifact_id="art-001",
        transaction_id="tx-100",
        plan_id="plan-1",
        operation_id="op-1",
        worker_id="worker-1",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="src/main.py",
        file_size_bytes=100,
        sha256_digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    manifest = ArtifactManifest(
        manifest_id="mf-001",
        transaction_id="tx-100",
        plan_id="plan-1",
        operation_id="op-1",
        worker_id="worker-1",
        attempt_id=1,
        artifacts=[art],
    )
    manifest.validate()
    assert manifest.total_artifacts == 1
    assert manifest.total_size_bytes == 100


def test_artifact_manifest_validation_failures():
    # Duplicate artifact ID
    art1 = ArtifactMetadata(
        artifact_id="dup-id",
        transaction_id="tx-100",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="file1.py",
        file_size_bytes=10,
        sha256_digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    art2 = ArtifactMetadata(
        artifact_id="dup-id",
        transaction_id="tx-100",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="file2.py",
        file_size_bytes=10,
        sha256_digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    manifest = ArtifactManifest(
        manifest_id="mf-dup",
        transaction_id="tx-100",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifacts=[art1, art2],
    )
    with pytest.raises(ArtifactManifestError, match="Duplicate artifact ID"):
        manifest.validate()


def test_validate_null_byte_rejection():
    with pytest.raises(ArtifactManifestError, match="null byte"):
        validate_safe_relative_path("src/app\0.py")


def test_manifest_max_single_artifact_quota():
    from core.artifact_manifest import MAX_SINGLE_ARTIFACT_BYTES
    art = ArtifactMetadata(
        artifact_id="art-huge",
        transaction_id="tx-1",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifact_type=ArtifactType.BINARY,
        relative_path="huge.bin",
        file_size_bytes=MAX_SINGLE_ARTIFACT_BYTES + 1,
        sha256_digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    manifest = ArtifactManifest(
        manifest_id="mf-huge",
        transaction_id="tx-1",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifacts=[art],
    )
    with pytest.raises(ArtifactManifestError, match="exceeds max single artifact size"):
        manifest.validate()


def test_manifest_invalid_sha256_rejection():
    art = ArtifactMetadata(
        artifact_id="art-bad-sha",
        transaction_id="tx-1",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifact_type=ArtifactType.SOURCE_CODE,
        relative_path="file.py",
        file_size_bytes=10,
        sha256_digest="not-a-valid-sha-digest",
    )
    manifest = ArtifactManifest(
        manifest_id="mf-bad-sha",
        transaction_id="tx-1",
        plan_id="p1",
        operation_id="op1",
        worker_id="w1",
        attempt_id=1,
        artifacts=[art],
    )
    with pytest.raises(ArtifactManifestError, match="invalid SHA-256"):
        manifest.validate()

