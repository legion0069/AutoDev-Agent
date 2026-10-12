"""
test_image_provisioner.py - Unit tests for ImageProvisioner & ImageCache (v2.3)
"""

from pathlib import Path
import pytest

from core.container_runtime import MockContainerRuntimeAdapter
from core.image_build_spec import ImageBuildSpec
from core.image_provisioner import ImageCache, ImageProvisioner
from core.project_environment_detector import ProjectEnvironment, ProjectType


@pytest.fixture
def mock_runtime():
    return MockContainerRuntimeAdapter()


def test_image_cache_crud(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache = ImageCache(cache_file_path=cache_file)
    assert cache.get("key1") is None

    from core.image_build_spec import ImageProvenance
    prov = ImageProvenance(
        image_tag="test:tag",
        image_digest="sha256:1122334455667788",
        cache_key="key1",
        base_image="python:3.12-slim",
        built_at="2026-10-09T00:00:00Z",
        build_duration_seconds=1.2,
        manifest_hashes={},
    )
    cache.put("key1", prov)
    assert cache.get("key1") is not None
    assert cache.get("key1").image_tag == "test:tag"

    # Reload from file
    cache2 = ImageCache(cache_file_path=cache_file)
    assert cache2.get("key1") is not None

    # Invalidate
    cache.invalidate("key1")
    assert cache.get("key1") is None


def test_image_provisioner_build_and_cache(mock_runtime, tmp_path):
    cache_dir = tmp_path / "cache"
    provisioner = ImageProvisioner(runtime_adapter=mock_runtime, cache_dir=cache_dir)

    env = ProjectEnvironment(
        project_type=ProjectType.PYTHON,
        runtime_version="3.12",
        base_image="python:3.12-slim",
        dependency_manifests=["requirements.txt"],
        manifest_hashes={"requirements.txt": "sha-req-123"},
    )
    spec = provisioner.create_build_spec(env)
    assert spec.base_image == "python:3.12-slim"

    # 1. Build image (fresh)
    prov1 = provisioner.build_image(spec)
    assert prov1.image_digest.startswith("sha256:")
    assert not prov1.is_cached
    assert provisioner.verify_image(prov1)

    # 2. Build image again (cached hit)
    prov2 = provisioner.build_image(spec)
    assert prov2.is_cached
    assert prov2.cache_key == prov1.cache_key

    provisioner.cleanup_temporary_resources()


def test_image_provisioner_node_and_java_specs(mock_runtime, tmp_path):
    provisioner = ImageProvisioner(runtime_adapter=mock_runtime, cache_dir=tmp_path / "cache")

    # Node environment
    node_env = ProjectEnvironment(
        project_type=ProjectType.NODE,
        runtime_version="20",
        base_image="node:20-slim",
        dependency_manifests=["package.json", "package-lock.json"],
        lockfile_present=True,
    )
    node_spec = provisioner.create_build_spec(node_env)
    assert node_spec.base_image == "node:20-slim"
    assert any("npm ci" in inst for inst in node_spec.build_instructions)

    # Java Maven environment
    java_env = ProjectEnvironment(
        project_type=ProjectType.JAVA_MAVEN,
        runtime_version="17",
        base_image="maven:3.9-eclipse-temurin-17",
        dependency_manifests=["pom.xml"],
    )
    java_spec = provisioner.create_build_spec(java_env)
    assert java_spec.base_image == "maven:3.9-eclipse-temurin-17"


def test_image_provisioner_dockerfile_generation(mock_runtime, tmp_path):
    provisioner = ImageProvisioner(runtime_adapter=mock_runtime, cache_dir=tmp_path / "cache")
    spec = ImageBuildSpec(
        base_image="python:3.12-slim",
        target_tag="test:df",
        build_instructions=["RUN pip install pytest", "WORKDIR /workspace"],
    )
    df_content = provisioner.generate_dockerfile(spec)
    assert "FROM python:3.12-slim" in df_content
    assert "RUN pip install pytest" in df_content
    assert "WORKDIR /workspace" in df_content

