"""
test_project_environment_detector.py - Unit tests for Project Stack & Environment Detection (v2.3)
"""

from pathlib import Path
import pytest
from core.project_environment_detector import (
    ProjectEnvironment,
    ProjectEnvironmentDetector,
    ProjectType,
)


def test_detect_python_requirements_txt(tmp_path):
    (tmp_path / "requirements.txt").write_text("pytest>=7.0.0\nrequests==2.31.0\n", encoding="utf-8")
    detector = ProjectEnvironmentDetector()
    env = detector.detect(tmp_path)

    assert env.project_type == ProjectType.PYTHON
    assert env.runtime_version == "3.12"
    assert env.base_image == "python:3.12-slim"
    assert "requirements.txt" in env.dependency_manifests
    assert "pytest" in env.test_command


def test_detect_python_pyproject_toml(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nrequires-python = ">=3.11"\n', encoding="utf-8")
    detector = ProjectEnvironmentDetector()
    env = detector.detect(tmp_path)

    assert env.project_type == ProjectType.PYTHON
    assert env.runtime_version == "3.11"
    assert "pyproject.toml" in env.dependency_manifests


def test_detect_node_project(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "demo-node", "scripts": {"test": "jest"}}\n', encoding="utf-8")
    (tmp_path / "package-lock.json").write_text('{"lockfileVersion": 3}\n', encoding="utf-8")
    detector = ProjectEnvironmentDetector()
    env = detector.detect(tmp_path)

    assert env.project_type == ProjectType.NODE
    assert env.lockfile_present is True
    assert env.base_image == "node:20-slim"
    assert "package.json" in env.dependency_manifests
    assert "package-lock.json" in env.dependency_manifests


def test_detect_java_maven_project(tmp_path):
    (tmp_path / "pom.xml").write_text("<project><modelVersion>4.0.0</modelVersion></project>\n", encoding="utf-8")
    detector = ProjectEnvironmentDetector()
    env = detector.detect(tmp_path)

    assert env.project_type == ProjectType.JAVA_MAVEN
    assert env.base_image == "maven:3.9-eclipse-temurin-17"
    assert "mvn test" in env.test_command


def test_detect_java_gradle_project(tmp_path):
    (tmp_path / "build.gradle").write_text('plugins { id "java" }\n', encoding="utf-8")
    detector = ProjectEnvironmentDetector()
    env = detector.detect(tmp_path)

    assert env.project_type == ProjectType.JAVA_GRADLE
    assert env.base_image == "gradle:8.5-jdk17"


def test_detect_static_web_project(tmp_path):
    (tmp_path / "index.html").write_text("<!DOCTYPE html><html><body>Demo</body></html>", encoding="utf-8")
    detector = ProjectEnvironmentDetector()
    env = detector.detect(tmp_path)

    assert env.project_type == ProjectType.STATIC_WEB
    assert env.base_image == "alpine:3.19"


def test_detect_unknown_project(tmp_path):
    (tmp_path / "notes.txt").write_text("Just some text files without manifest", encoding="utf-8")
    detector = ProjectEnvironmentDetector()
    env = detector.detect(tmp_path)

    assert env.project_type == ProjectType.UNKNOWN
    assert env.confidence == 0.0


def test_detect_python_fastapi_and_flask(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="api"\ndependencies=["fastapi>=0.100.0", "uvicorn"]\n',
        encoding="utf-8",
    )
    detector = ProjectEnvironmentDetector()
    env = detector.detect(tmp_path)

    assert env.project_type == ProjectType.PYTHON
    assert "FastAPI" in env.frameworks


def test_detect_node_yarn_lock(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "yarn-app"}', encoding="utf-8")
    (tmp_path / "yarn.lock").write_text("# yarn lockfile v1\n", encoding="utf-8")
    detector = ProjectEnvironmentDetector()
    env = detector.detect(tmp_path)

    assert env.project_type == ProjectType.NODE
    assert env.lockfile_present is True
    assert "yarn.lock" in env.dependency_manifests


def test_detect_node_pnpm_lock(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "pnpm-app"}', encoding="utf-8")
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '6.0'\n", encoding="utf-8")
    detector = ProjectEnvironmentDetector()
    env = detector.detect(tmp_path)

    assert env.project_type == ProjectType.NODE
    assert env.lockfile_present is True
    assert "pnpm-lock.yaml" in env.dependency_manifests


def test_detect_nonexistent_workspace(tmp_path):
    missing_dir = tmp_path / "does_not_exist"
    detector = ProjectEnvironmentDetector()
    env = detector.detect(missing_dir)

    assert env.project_type == ProjectType.UNKNOWN
    assert env.confidence == 0.0

