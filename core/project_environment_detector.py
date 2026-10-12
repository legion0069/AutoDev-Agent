"""
project_environment_detector.py - Dynamic Project Environment & Stack Detector for AutoDev (v2.3)

Inspects project repository files and dependency manifests (Python, Node.js, Java/Maven/Gradle, Static Web)
to infer the language, runtime versions, build tools, base images, and test suites with zero LLM hallucinations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("AutoDev.ProjectEnvironmentDetector")


class ProjectType(str, Enum):
    """Identified project technology stack type."""
    PYTHON = "PYTHON"
    NODE = "NODE"
    JAVA_MAVEN = "JAVA_MAVEN"
    JAVA_GRADLE = "JAVA_GRADLE"
    STATIC_WEB = "STATIC_WEB"
    UNKNOWN = "UNKNOWN"


@dataclass
class ProjectEnvironment:
    """Inferred environment, runtime requirements, and build configuration for a project."""
    project_type: ProjectType = ProjectType.PYTHON
    primary_language: str = "python"
    runtime_version: str = "3.12"
    base_image: str = "python:3.12-slim"
    dependency_manifests: List[str] = field(default_factory=list)
    manifest_hashes: Dict[str, str] = field(default_factory=dict)
    detected_languages: List[str] = field(default_factory=list)
    is_version_explicit: bool = False
    frameworks: List[str] = field(default_factory=list)
    lockfile_present: bool = False
    lockfile_path: Optional[str] = None
    build_tools: List[str] = field(default_factory=list)
    test_command: str = "pytest"
    build_command: Optional[str] = None
    confidence: float = 1.0
    assumptions: List[str] = field(default_factory=list)
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["project_type"] = self.project_type.value
        return res


ProjectEnvironmentSpec = ProjectEnvironment


class ProjectEnvironmentDetector:
    """
    Scans project directory manifests to detect technology stack and build requirements.
    """

    def __init__(self, workspace_root: Optional[Union[str, Path]] = None) -> None:
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path(".").resolve()

    def detect(self, workspace_path: Optional[Union[str, Path]] = None) -> ProjectEnvironment:
        """
        Inspects project manifests and returns a structured ProjectEnvironment.
        """
        ws = Path(workspace_path).resolve() if workspace_path else self.workspace_root
        detected_languages: Set[str] = set()
        manifests: List[str] = []
        manifest_hashes: Dict[str, str] = {}
        frameworks: Set[str] = set()
        build_tools: Set[str] = set()
        runtime_version: Optional[str] = None
        is_version_explicit = False
        has_lockfile = False
        lockfile_path: Optional[str] = None
        suggested_test_cmd = "pytest"
        suggested_build_cmd: Optional[str] = None
        assumptions: List[str] = []

        if not ws.exists():
            return ProjectEnvironment(
                project_type=ProjectType.UNKNOWN,
                primary_language="unknown",
                runtime_version="unknown",
                base_image="alpine:3.19",
                assumptions=["Workspace directory does not exist."],
                confidence=0.0,
            )

        def _hash_file(p: Path) -> str:
            try:
                return hashlib.sha256(p.read_bytes()).hexdigest()
            except Exception:
                return ""

        # 1. Check Python Manifests
        py_req = ws / "requirements.txt"
        py_proj = ws / "pyproject.toml"
        py_setup = ws / "setup.py"
        py_pipfile_lock = ws / "Pipfile.lock"

        if py_req.exists() or py_proj.exists() or py_setup.exists() or list(ws.glob("*.py")):
            detected_languages.add("python")
            if py_req.exists():
                manifests.append("requirements.txt")
                manifest_hashes["requirements.txt"] = _hash_file(py_req)
            if py_proj.exists():
                manifests.append("pyproject.toml")
                manifest_hashes["pyproject.toml"] = _hash_file(py_proj)
                try:
                    content = py_proj.read_text(encoding="utf-8")
                    if "fastapi" in content.lower():
                        frameworks.add("FastAPI")
                    if "django" in content.lower():
                        frameworks.add("Django")
                    if "flask" in content.lower():
                        frameworks.add("Flask")
                    match = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        v_str = match.group(1).replace(">=", "").replace("==", "").replace("~=", "").strip()
                        runtime_version = v_str[:4] if len(v_str) >= 4 else v_str
                        is_version_explicit = True
                except Exception:
                    pass
            if py_pipfile_lock.exists():
                has_lockfile = True
                lockfile_path = "Pipfile.lock"
                manifest_hashes["Pipfile.lock"] = _hash_file(py_pipfile_lock)

            build_tools.add("pip")
            suggested_test_cmd = "pytest tests/ -v"

        # 2. Check Node.js / TypeScript Manifests
        pkg_json = ws / "package.json"
        pkg_lock = ws / "package-lock.json"
        yarn_lock = ws / "yarn.lock"
        pnpm_lock = ws / "pnpm-lock.yaml"
        nvmrc = ws / ".nvmrc"

        if pkg_json.exists() or list(ws.glob("*.js")) or list(ws.glob("*.ts")):
            detected_languages.add("javascript")
            if (ws / "tsconfig.json").exists() or list(ws.glob("*.ts")):
                detected_languages.add("typescript")

            if pkg_json.exists():
                manifests.append("package.json")
                manifest_hashes["package.json"] = _hash_file(pkg_json)
                try:
                    data = json.loads(pkg_json.read_text(encoding="utf-8"))
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    if "react" in deps:
                        frameworks.add("React")
                    if "next" in deps:
                        frameworks.add("Next.js")
                    if "express" in deps:
                        frameworks.add("Express")
                    if "vue" in deps:
                        frameworks.add("Vue")
                    if "jest" in deps or "mocha" in deps:
                        suggested_test_cmd = "npm test"
                except Exception:
                    pass

            if pkg_lock.exists():
                has_lockfile = True
                lockfile_path = "package-lock.json"
                manifests.append("package-lock.json")
                manifest_hashes["package-lock.json"] = _hash_file(pkg_lock)
                build_tools.add("npm")
            elif yarn_lock.exists():
                has_lockfile = True
                lockfile_path = "yarn.lock"
                manifests.append("yarn.lock")
                manifest_hashes["yarn.lock"] = _hash_file(yarn_lock)
                build_tools.add("yarn")
            elif pnpm_lock.exists():
                has_lockfile = True
                lockfile_path = "pnpm-lock.yaml"
                manifests.append("pnpm-lock.yaml")
                manifest_hashes["pnpm-lock.yaml"] = _hash_file(pnpm_lock)
                build_tools.add("pnpm")
            else:
                build_tools.add("npm")

            if nvmrc.exists():
                runtime_version = nvmrc.read_text(encoding="utf-8").strip()
                is_version_explicit = True
            suggested_build_cmd = "npm run build" if pkg_json.exists() else None

        # 3. Check Java / Maven / Gradle
        pom_xml = ws / "pom.xml"
        build_gradle = ws / "build.gradle"
        build_gradle_kts = ws / "build.gradle.kts"

        if pom_xml.exists() or build_gradle.exists() or build_gradle_kts.exists() or list(ws.glob("*.java")):
            detected_languages.add("java")
            if pom_xml.exists():
                manifests.append("pom.xml")
                manifest_hashes["pom.xml"] = _hash_file(pom_xml)
                build_tools.add("maven")
                suggested_test_cmd = "mvn test"
                suggested_build_cmd = "mvn clean package"
            if build_gradle.exists() or build_gradle_kts.exists():
                g_file = "build.gradle" if build_gradle.exists() else "build.gradle.kts"
                manifests.append(g_file)
                manifest_hashes[g_file] = _hash_file(ws / g_file)
                build_tools.add("gradle")
                suggested_test_cmd = "gradle test"
                suggested_build_cmd = "gradle build"

        # 4. Check Static HTML / Web
        if (ws / "index.html").exists() and not detected_languages:
            detected_languages.add("html/css/javascript")
            manifests.append("index.html")
            manifest_hashes["index.html"] = _hash_file(ws / "index.html")
            suggested_test_cmd = "echo 'Static web assets verified'"

        # Project Type Resolution
        proj_type = ProjectType.UNKNOWN
        primary = "unknown"
        base_img = "alpine:3.19"

        if "python" in detected_languages:
            proj_type = ProjectType.PYTHON
            primary = "python"
            if not runtime_version:
                runtime_version = "3.12"
                assumptions.append("Defaulted Python runtime version to 3.12")
            base_img = f"python:{runtime_version}-slim"
        elif "typescript" in detected_languages or "javascript" in detected_languages:
            proj_type = ProjectType.NODE
            primary = "typescript" if "typescript" in detected_languages else "javascript"
            if not runtime_version:
                runtime_version = "20"
                assumptions.append("Defaulted Node.js runtime version to 20")
            base_img = f"node:{runtime_version}-slim"
        elif "java" in detected_languages:
            if "maven" in build_tools or pom_xml.exists():
                proj_type = ProjectType.JAVA_MAVEN
                base_img = "maven:3.9-eclipse-temurin-17"
            else:
                proj_type = ProjectType.JAVA_GRADLE
                base_img = "gradle:8.5-jdk17"
            primary = "java"
            if not runtime_version:
                runtime_version = "17"
                assumptions.append("Defaulted Java runtime version to 17")
        elif "html/css/javascript" in detected_languages:
            proj_type = ProjectType.STATIC_WEB
            primary = "html/css/javascript"
            runtime_version = "static"
            base_img = "alpine:3.19"
        else:
            runtime_version = "unknown"

        confidence = 0.95 if manifests else (0.7 if detected_languages else 0.0)

        return ProjectEnvironment(
            project_type=proj_type,
            primary_language=primary,
            runtime_version=runtime_version,
            base_image=base_img,
            dependency_manifests=manifests,
            manifest_hashes=manifest_hashes,
            detected_languages=sorted(list(detected_languages)),
            is_version_explicit=is_version_explicit,
            frameworks=sorted(list(frameworks)),
            lockfile_present=has_lockfile,
            lockfile_path=lockfile_path,
            build_tools=sorted(list(build_tools)),
            test_command=suggested_test_cmd,
            build_command=suggested_build_cmd,
            confidence=confidence,
            assumptions=assumptions,
        )
