"""
dependency_scanner.py - Multi-Ecosystem Dependency Scanner & Parser (v3.2)

Parses requirements.txt, package.json, pom.xml, build.gradle, Cargo.toml, go.mod, and composer.json
into standardized DependencyNode and PackageVersion structures using strictly Python Standard Library.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.ecosystem.ecosystem_models import (
    DependencyEcosystem,
    DependencyNode,
    PackageVersion,
)

logger = logging.getLogger("AutoDev.DependencyIntelligence.Scanner")


class DependencyScanner:
    """
    Parses manifest files across all major programming language ecosystems:
    - Python (requirements.txt, setup.py, pyproject.toml)
    - JavaScript / TypeScript (package.json)
    - Java / Kotlin (pom.xml, build.gradle)
    - Rust (Cargo.toml)
    - Go (go.mod)
    - PHP (composer.json)
    """

    def scan_directory(self, root_dir: str) -> List[DependencyNode]:
        """Scans a project directory and extracts all manifest dependencies."""
        nodes: List[DependencyNode] = []
        path = Path(root_dir)
        if not path.exists():
            return nodes

        # Check for each manifest
        req_file = path / "requirements.txt"
        if req_file.exists():
            nodes.extend(self.parse_requirements_txt(req_file.read_text(encoding="utf-8", errors="ignore")))

        pkg_json = path / "package.json"
        if pkg_json.exists():
            nodes.extend(self.parse_package_json(pkg_json.read_text(encoding="utf-8", errors="ignore")))

        pom_xml = path / "pom.xml"
        if pom_xml.exists():
            nodes.extend(self.parse_pom_xml(pom_xml.read_text(encoding="utf-8", errors="ignore")))

        gradle_file = path / "build.gradle"
        if gradle_file.exists():
            nodes.extend(self.parse_build_gradle(gradle_file.read_text(encoding="utf-8", errors="ignore")))

        cargo_file = path / "Cargo.toml"
        if cargo_file.exists():
            nodes.extend(self.parse_cargo_toml(cargo_file.read_text(encoding="utf-8", errors="ignore")))

        go_file = path / "go.mod"
        if go_file.exists():
            nodes.extend(self.parse_go_mod(go_file.read_text(encoding="utf-8", errors="ignore")))

        composer_file = path / "composer.json"
        if composer_file.exists():
            nodes.extend(self.parse_composer_json(composer_file.read_text(encoding="utf-8", errors="ignore")))

        return nodes

    def scan_manifest(self, file_path: str) -> List[DependencyNode]:
        """Parses a specific manifest file by inspecting filename and extension."""
        path = Path(file_path)
        if not path.is_file():
            return []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            name = path.name.lower()
            if "requirements" in name or name.endswith(".txt"):
                return self.parse_requirements_txt(content)
            elif name == "package.json":
                return self.parse_package_json(content)
            elif name == "pom.xml":
                return self.parse_pom_xml(content)
            elif name == "build.gradle" or name.endswith(".gradle"):
                return self.parse_build_gradle(content)
            elif name == "cargo.toml":
                return self.parse_cargo_toml(content)
            elif name == "go.mod":
                return self.parse_go_mod(content)
            elif name == "composer.json":
                return self.parse_composer_json(content)
            return []
        except Exception as e:
            logger.warning(f"Failed to scan manifest {file_path}: {e}")
            return []

    def scan_project_dependencies(self, root_dir: str) -> List[DependencyNode]:
        """Alias for scan_directory."""
        return self.scan_directory(root_dir)

    def parse_requirements_txt(self, content: str) -> List[DependencyNode]:
        """Parses Python requirements.txt."""
        nodes: List[DependencyNode] = []
        for line in content.splitlines():
            # Strip inline comments
            clean = line.split("#")[0].strip()
            if not clean or clean.startswith("-"):
                continue

            # e.g., fastapi==0.115.0 or uvicorn[standard]>=0.30.0
            match = re.match(r"^([a-zA-Z0-9_\-\.]+)(?:\[[^\]]*\])?\s*([=><~!^].*)?$", clean)
            if match:
                pkg = match.group(1).strip()
                spec = match.group(2).strip() if match.group(2) else "latest"
                ver = re.sub(r"^[=><~!^ ]+", "", spec) if spec != "latest" else "0.0.0"
                nodes.append(DependencyNode(
                    name=pkg,
                    version_spec=spec,
                    current_version=ver,
                    ecosystem=DependencyEcosystem.PYTHON,
                    is_direct=True,
                    scope="runtime",
                ))
        return nodes

    def parse_package_json(self, content: str) -> List[DependencyNode]:
        """Parses Node.js package.json."""
        nodes: List[DependencyNode] = []
        try:
            data = json.loads(content)
        except Exception as e:
            logger.warning("Failed to parse package.json: %s", e)
            return nodes

        deps = data.get("dependencies", {})
        for name, spec in deps.items():
            ver = re.sub(r"^[\^~>=< ]+", "", str(spec))
            nodes.append(DependencyNode(
                name=name,
                version_spec=str(spec),
                current_version=ver,
                ecosystem=DependencyEcosystem.NPM,
                is_direct=True,
                scope="runtime",
            ))

        dev_deps = data.get("devDependencies", {})
        for name, spec in dev_deps.items():
            ver = re.sub(r"^[\^~>=< ]+", "", str(spec))
            nodes.append(DependencyNode(
                name=name,
                version_spec=str(spec),
                current_version=ver,
                ecosystem=DependencyEcosystem.NPM,
                is_direct=True,
                scope="dev",
            ))

        peer_deps = data.get("peerDependencies", {})
        for name, spec in peer_deps.items():
            ver = re.sub(r"^[\^~>=< ]+", "", str(spec))
            nodes.append(DependencyNode(
                name=name,
                version_spec=str(spec),
                current_version=ver,
                ecosystem=DependencyEcosystem.NPM,
                is_direct=True,
                scope="peer",
            ))
        return nodes

    def parse_pom_xml(self, content: str) -> List[DependencyNode]:
        """Parses Maven pom.xml using standard regex (zero external XML parsers)."""
        nodes: List[DependencyNode] = []
        # Find all <dependency> ... </dependency> blocks
        dep_blocks = re.findall(r"<dependency>(.*?)</dependency>", content, re.DOTALL)
        for block in dep_blocks:
            g_match = re.search(r"<groupId>(.*?)</groupId>", block)
            a_match = re.search(r"<artifactId>(.*?)</artifactId>", block)
            v_match = re.search(r"<version>(.*?)</version>", block)
            s_match = re.search(r"<scope>(.*?)</scope>", block)

            if g_match and a_match:
                name = f"{g_match.group(1).strip()}:{a_match.group(1).strip()}"
                ver = v_match.group(1).strip() if v_match else "1.0.0"
                scope = s_match.group(1).strip() if s_match else "runtime"
                nodes.append(DependencyNode(
                    name=name,
                    version_spec=ver,
                    current_version=ver,
                    ecosystem=DependencyEcosystem.MAVEN,
                    is_direct=True,
                    scope=scope,
                ))
        return nodes

    def parse_build_gradle(self, content: str) -> List[DependencyNode]:
        """Parses Gradle build.gradle dependencies."""
        nodes: List[DependencyNode] = []
        # Match implementation 'org.springframework.boot:spring-boot-starter-web:3.1.2' or implementation("com.example:pkg:1.0")
        pattern = r"(implementation|testImplementation|api|compileOnly)\s*(?:\(\s*)?['\"]([^'\"]+)['\"](?:\s*\))?"
        for scope, full_spec in re.findall(pattern, content):
            parts = full_spec.split(":")
            if len(parts) >= 2:
                name = f"{parts[0]}:{parts[1]}"
                ver = parts[2] if len(parts) > 2 else "1.0.0"
                nodes.append(DependencyNode(
                    name=name,
                    version_spec=ver,
                    current_version=ver,
                    ecosystem=DependencyEcosystem.GRADLE,
                    is_direct=True,
                    scope="test" if "test" in scope.lower() else "runtime",
                ))
        return nodes

    def parse_cargo_toml(self, content: str) -> List[DependencyNode]:
        """Parses Rust Cargo.toml dependencies."""
        nodes: List[DependencyNode] = []
        in_deps = False
        in_dev_deps = False

        for line in content.splitlines():
            clean = line.strip()
            if clean == "[dependencies]":
                in_deps = True
                in_dev_deps = False
                continue
            elif clean == "[dev-dependencies]":
                in_deps = False
                in_dev_deps = True
                continue
            elif clean.startswith("["):
                in_deps = False
                in_dev_deps = False
                continue

            if in_deps or in_dev_deps:
                # Match serde = "1.0.193" or tokio = { version = "1.35", features = [...] }
                match = re.match(r"^([a-zA-Z0-9_\-]+)\s*=\s*(.*)$", clean)
                if match:
                    pkg = match.group(1)
                    val = match.group(2)
                    ver = "0.1.0"
                    if '"' in val:
                        ver_match = re.search(r'"([^"]+)"', val)
                        if ver_match:
                            ver = ver_match.group(1)
                    nodes.append(DependencyNode(
                        name=pkg,
                        version_spec=ver,
                        current_version=ver,
                        ecosystem=DependencyEcosystem.CARGO,
                        is_direct=True,
                        scope="dev" if in_dev_deps else "runtime",
                    ))
        return nodes

    def parse_go_mod(self, content: str) -> List[DependencyNode]:
        """Parses Go go.mod requirements."""
        nodes: List[DependencyNode] = []
        in_require = False
        for line in content.splitlines():
            clean = line.strip()
            is_indirect = "// indirect" in clean
            clean_no_comment = clean.split("//")[0].strip()

            if clean_no_comment.startswith("require ("):
                in_require = True
                continue
            elif clean_no_comment == ")" and in_require:
                in_require = False
                continue
            elif clean_no_comment.startswith("require "):
                parts = clean_no_comment.split()
                if len(parts) >= 3:
                    nodes.append(DependencyNode(
                        name=parts[1],
                        version_spec=parts[2],
                        current_version=parts[2].lstrip("v"),
                        ecosystem=DependencyEcosystem.GOMOD,
                        is_direct=not is_indirect,
                        scope="runtime",
                    ))
            elif in_require and clean_no_comment:
                parts = clean_no_comment.split()
                if len(parts) >= 2:
                    nodes.append(DependencyNode(
                        name=parts[0],
                        version_spec=parts[1],
                        current_version=parts[1].lstrip("v"),
                        ecosystem=DependencyEcosystem.GOMOD,
                        is_direct=not is_indirect,
                        scope="runtime",
                    ))
        return nodes

    def parse_composer_json(self, content: str) -> List[DependencyNode]:
        """Parses PHP composer.json."""
        nodes: List[DependencyNode] = []
        try:
            data = json.loads(content)
        except Exception:
            return nodes

        for name, spec in data.get("require", {}).items():
            if name == "php":
                continue
            ver = re.sub(r"^[\^~>=< ]+", "", str(spec))
            nodes.append(DependencyNode(
                name=name,
                version_spec=str(spec),
                current_version=ver,
                ecosystem=DependencyEcosystem.COMPOSER,
                is_direct=True,
                scope="runtime",
            ))

        for name, spec in data.get("require-dev", {}).items():
            ver = re.sub(r"^[\^~>=< ]+", "", str(spec))
            nodes.append(DependencyNode(
                name=name,
                version_spec=str(spec),
                current_version=ver,
                ecosystem=DependencyEcosystem.COMPOSER,
                is_direct=True,
                scope="dev",
            ))
        return nodes
