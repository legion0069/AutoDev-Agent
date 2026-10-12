"""
dependency_analyzer.py - Comprehensive Dependency Analyzer & Recommendation Engine (v3.2)

Detects:
- Unused packages (AST and grep matching against codebase)
- Duplicate dependencies
- Version conflicts
- Deprecated libraries
- Outdated packages
- Transitive dependency chains
- License conflicts (GPL vs MIT/Apache-2.0)

Recommends:
- Safe version upgrades
- Direct drop-in package replacements
- Security patches
"""

from __future__ import annotations

import copy
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.dependency_intelligence.dependency_graph import DependencyGraph
from core.dependency_intelligence.dependency_scanner import DependencyScanner
from core.ecosystem.ecosystem_models import (
    DependencyConflict,
    DependencyEcosystem,
    DependencyNode,
    DependencyRecommendation,
    PackageVersion,
)

logger = logging.getLogger("AutoDev.DependencyIntelligence.Analyzer")


class DependencyAnalyzer:
    """
    Analyzes project dependencies against ecosystem rules, known deprecations,
    and actual codebase import usage.
    """

    # Comprehensive built-in catalog of deprecated packages and their modern replacements
    DEPRECATED_PACKAGES: Dict[str, Dict[str, Any]] = {
        # Python
        "pycrypto": {
            "replacement": "cryptography",
            "reason": "Unmaintained since 2013, contains numerous unpatched vulnerabilities.",
            "safe_version": "42.0.0",
        },
        "urllib3_mock": {
            "replacement": "responses",
            "reason": "Deprecated mock framework, use responses or pytest-mock.",
            "safe_version": "0.25.0",
        },
        "optparse": {
            "replacement": "argparse",
            "reason": "Deprecated in Python Standard Library since 3.2.",
            "safe_version": "built-in",
        },
        "nose": {
            "replacement": "pytest",
            "reason": "Nose is completely unmaintained, migrate to pytest.",
            "safe_version": "8.3.0",
        },
        "fabric": {
            "replacement": "invoke",
            "reason": "Fabric 1.x is obsolete on Python 3.",
            "safe_version": "3.2.0",
        },
        # NPM
        "request": {
            "replacement": "axios",
            "reason": "Deprecated since February 2020. Use axios, node-fetch, or undici.",
            "safe_version": "1.7.0",
        },
        "moment": {
            "replacement": "date-fns",
            "reason": "Moment.js is in maintenance mode; prefer date-fns, dayjs, or Luxon.",
            "safe_version": "3.3.0",
        },
        "left-pad": {
            "replacement": "built-in String.prototype.padStart",
            "reason": "Obsolete micro-package.",
            "safe_version": "ES2017",
        },
        "babel-eslint": {
            "replacement": "@babel/eslint-parser",
            "reason": "Deprecated parser, use @babel/eslint-parser.",
            "safe_version": "7.22.0",
        },
        # Java / Maven
        "log4j:log4j": {
            "replacement": "org.apache.logging.log4j:log4j-core",
            "reason": "Log4j 1.x reached end of life and contains severe CVEs.",
            "safe_version": "2.23.1",
        },
        "junit:junit": {
            "replacement": "org.junit.jupiter:junit-jupiter",
            "reason": "JUnit 4 is legacy; modernize to JUnit 5 (Jupiter).",
            "safe_version": "5.10.2",
        },
    }

    # High-risk / Viral licenses that conflict with commercial/proprietary code
    RESTRICTIVE_LICENSES: Set[str] = {"GPL-2.0", "GPL-3.0", "AGPL-3.0", "SSPL"}

    # Latest stable reference versions for popular frameworks
    LATEST_STABLE_ECOSYSTEM: Dict[str, str] = {
        "fastapi": "0.115.0",
        "pydantic": "2.9.2",
        "pytest": "8.3.3",
        "requests": "2.32.3",
        "flask": "3.0.3",
        "django": "5.1.1",
        "react": "18.3.1",
        "vue": "3.5.10",
        "next": "14.2.13",
        "axios": "1.7.7",
        "typescript": "5.6.2",
        "express": "4.21.0",
        "tokio": "1.40.0",
        "serde": "1.0.210",
    }

    def __init__(self, scanner: Optional[DependencyScanner] = None) -> None:
        self.scanner = scanner or DependencyScanner()

    def analyze_dependencies(
        self,
        nodes: List[DependencyNode],
        source_code_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Runs comprehensive inspection on a list of dependencies.
        Returns metrics, conflicts, unused dependencies, and recommendations.
        """
        graph = DependencyGraph()
        for node in nodes:
            graph.add_dependency(node)

        # 1. Detect duplicates across manifests
        duplicates: List[Dict[str, Any]] = []
        name_counts: Dict[str, List[DependencyNode]] = {}
        for n in nodes:
            name_counts.setdefault(n.name.lower(), []).append(n)

        for name, node_list in name_counts.items():
            if len(node_list) > 1:
                duplicates.append({
                    "package": name,
                    "count": len(node_list),
                    "versions": [n.current_version for n in node_list],
                    "ecosystems": [n.ecosystem.value for n in node_list],
                })

        # 2. Detect deprecated packages
        deprecated: List[Dict[str, Any]] = []
        recommendations: List[DependencyRecommendation] = []

        for n in nodes:
            base_name = n.name.lower()
            if base_name in self.DEPRECATED_PACKAGES:
                info = self.DEPRECATED_PACKAGES[base_name]
                deprecated.append({
                    "package": n.name,
                    "current_version": n.current_version,
                    "replacement": info["replacement"],
                    "reason": info["reason"],
                })
                recommendations.append(DependencyRecommendation(
                    package_name=n.name,
                    current_version=n.current_version,
                    recommended_version=info.get("safe_version", "latest"),
                    recommendation_type="REPLACEMENT",
                    rationale=info["reason"],
                    breaking_change_risk="MEDIUM",
                    ecosystem=n.ecosystem,
                    replacement_package=info["replacement"],
                    migration_notes=[f"Replace import {n.name} with {info['replacement']}."],
                ))

        # 3. Detect outdated packages vs latest stable
        outdated: List[Dict[str, Any]] = []
        for n in nodes:
            base_name = n.name.lower()
            if base_name in self.LATEST_STABLE_ECOSYSTEM:
                latest_str = self.LATEST_STABLE_ECOSYSTEM[base_name]
                cur_v = PackageVersion(n.current_version)
                lat_v = PackageVersion(latest_str)
                if cur_v < lat_v:
                    diff_type = "MAJOR" if cur_v.major < lat_v.major else ("MINOR" if cur_v.minor < lat_v.minor else "PATCH")
                    outdated.append({
                        "package": n.name,
                        "current_version": n.current_version,
                        "latest_version": latest_str,
                        "update_type": diff_type,
                    })
                    recommendations.append(DependencyRecommendation(
                        package_name=n.name,
                        current_version=n.current_version,
                        recommended_version=latest_str,
                        recommendation_type="UPGRADE",
                        rationale=f"Newer {diff_type.lower()} release available ({n.current_version} -> {latest_str}).",
                        breaking_change_risk="HIGH" if diff_type == "MAJOR" else "LOW",
                        ecosystem=n.ecosystem,
                    ))

        # 4. Detect unused packages if source code content is provided
        unused: List[str] = []
        if source_code_files:
            combined_code = " ".join(source_code_files.values())
            for n in nodes:
                if n.is_direct and n.scope == "runtime":
                    pkg_clean = n.name.replace("-", "_").lower()
                    # Check import patterns
                    patterns = [
                        rf"\bimport\s+{pkg_clean}\b",
                        rf"\bfrom\s+{pkg_clean}\b",
                        rf"\brequire\(['\"]{n.name}['\"]\)",
                        rf"\bfrom\s+['\"]{n.name}['\"]",
                    ]
                    found = any(re.search(p, combined_code, re.IGNORECASE) for p in patterns)
                    if not found and n.name.lower() not in ("uvicorn", "gunicorn", "pytest"):
                        unused.append(n.name)
                        recommendations.append(DependencyRecommendation(
                            package_name=n.name,
                            current_version=n.current_version,
                            recommended_version="NONE",
                            recommendation_type="PRUNE_UNUSED",
                            rationale="Package is declared in manifest but no imports detected in codebase.",
                            breaking_change_risk="LOW",
                            ecosystem=n.ecosystem,
                        ))

        # 5. Detect license risks
        license_warnings: List[Dict[str, Any]] = []
        for n in nodes:
            if n.license in self.RESTRICTIVE_LICENSES:
                license_warnings.append({
                    "package": n.name,
                    "license": n.license,
                    "warning": "Copyleft license may require derivative source code to be published.",
                })

        # 6. Graph cycles
        cycles = graph.detect_cycles()

        return {
            "summary": {
                "total_dependencies": len(nodes),
                "direct_dependencies_count": len([n for n in nodes if n.is_direct]),
                "transitive_dependencies_count": len([n for n in nodes if not n.is_direct]),
                "duplicate_count": len(duplicates),
                "deprecated_count": len(deprecated),
                "outdated_count": len(outdated),
                "unused_count": len(unused),
                "has_cycles": len(cycles) > 0,
            },
            "total_dependencies": len(nodes),
            "direct_dependencies_count": len([n for n in nodes if n.is_direct]),
            "transitive_dependencies_count": len([n for n in nodes if not n.is_direct]),
            "duplicates": duplicates,
            "deprecated": deprecated,
            "deprecated_libraries": deprecated,
            "outdated": outdated,
            "unused_packages": unused,
            "unused_dependencies": unused,
            "license_warnings": license_warnings,
            "circular_dependencies": cycles,
            "recommendations": [r.to_dict() for r in recommendations],
            "graph": graph.to_dict(),
        }

    def detect_unused_dependencies(
        self,
        nodes: List[DependencyNode],
        source_code_files: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Detects unused declared dependencies."""
        if not source_code_files:
            return []
        combined_code = " ".join(source_code_files.values())
        unused: List[str] = []
        for n in nodes:
            if n.is_direct and n.scope == "runtime":
                pkg_clean = n.name.replace("-", "_").lower()
                patterns = [
                    rf"\bimport\s+{pkg_clean}\b",
                    rf"\bfrom\s+{pkg_clean}\b",
                    rf"\brequire\(['\"]{n.name}['\"]\)",
                    rf"\bfrom\s+['\"]{n.name}['\"]",
                ]
                found = any(re.search(p, combined_code, re.IGNORECASE) for p in patterns)
                if not found and n.name.lower() not in ("uvicorn", "gunicorn", "pytest"):
                    unused.append(n.name)
        return unused

    def detect_duplicate_dependencies(
        self,
        nodes: List[DependencyNode],
    ) -> Dict[str, List[DependencyNode]]:
        """Identifies duplicate declarations of the same dependency across manifests."""
        grouped: Dict[str, List[DependencyNode]] = {}
        for n in nodes:
            grouped.setdefault(n.name.lower(), []).append(n)
        return {k: v for k, v in grouped.items() if len(v) > 1}

    def detect_version_conflicts(
        self,
        nodes: List[DependencyNode],
    ) -> List[DependencyConflict]:
        """Detects conflicting version constraints for the same package."""
        grouped = self.detect_duplicate_dependencies(nodes)
        conflicts: List[DependencyConflict] = []
        for name, dupes in grouped.items():
            versions = list({d.current_version for d in dupes if d.current_version})
            constraints = list({d.version_constraint for d in dupes if d.version_constraint})
            if len(versions) > 1 or len(constraints) > 1:
                conflicts.append(DependencyConflict(
                    package_name=name,
                    conflicting_versions=versions,
                    reason=f"Multiple conflicting version specs found: {', '.join(constraints or versions)}",
                    recommended_resolution=f"Align on unified version '{max(versions, key=lambda v: PackageVersion(v))}'.",
                ))
        return conflicts

    def detect_deprecated_libraries(
        self,
        nodes: List[DependencyNode],
    ) -> List[Dict[str, Any]]:
        """Identifies deprecated, abandoned, or unmaintained libraries."""
        deprecated: List[Dict[str, Any]] = []
        for n in nodes:
            base_name = n.name.lower()
            if base_name in self.DEPRECATED_PACKAGES:
                info = self.DEPRECATED_PACKAGES[base_name]
                deprecated.append({
                    "package": n.name,
                    "current_version": n.current_version,
                    "replacement": info["replacement"],
                    "reason": info["reason"],
                    "safe_version": info.get("safe_version", "latest"),
                })
        return deprecated

    def detect_license_conflicts(
        self,
        nodes: List[DependencyNode],
        project_license: str = "MIT",
    ) -> List[Dict[str, Any]]:
        """Identifies license incompatibilities (e.g. GPL copyleft in permissive/MIT project)."""
        risks: List[Dict[str, Any]] = []
        is_permissive = project_license.upper() in ("MIT", "APACHE-2.0", "BSD-3-CLAUSE", "ISC")
        for n in nodes:
            lic = n.license.upper()
            if is_permissive and lic in self.RESTRICTIVE_LICENSES:
                risks.append({
                    "package": n.name,
                    "license": n.license,
                    "project_license": project_license,
                    "severity": "HIGH",
                    "risk": f"Viral copyleft license {n.license} conflicts with permissive project license {project_license}.",
                })
        return risks

    def generate_recommendations(
        self,
        nodes: List[DependencyNode],
    ) -> List[DependencyRecommendation]:
        """Generates actionable recommendations for upgrades, replacements, and safe versions."""
        recs: List[DependencyRecommendation] = []
        for n in nodes:
            base_name = n.name.lower()
            # 1. Deprecated replacement
            if base_name in self.DEPRECATED_PACKAGES:
                info = self.DEPRECATED_PACKAGES[base_name]
                recs.append(DependencyRecommendation(
                    package_name=n.name,
                    current_version=n.current_version,
                    recommended_version=info.get("safe_version", "latest"),
                    recommendation_type="REPLACEMENT",
                    rationale=info["reason"],
                    breaking_change_risk="MEDIUM",
                    ecosystem=n.ecosystem,
                    replacement_package=info["replacement"],
                    migration_notes=[f"Replace import {n.name} with {info['replacement']}."],
                ))
            # 2. Outdated version upgrade
            elif base_name in self.LATEST_STABLE_ECOSYSTEM:
                lat = self.LATEST_STABLE_ECOSYSTEM[base_name]
                cur_v = PackageVersion(n.current_version)
                lat_v = PackageVersion(lat)
                if cur_v < lat_v:
                    diff_type = "MAJOR" if cur_v.major < lat_v.major else ("MINOR" if cur_v.minor < lat_v.minor else "PATCH")
                    recs.append(DependencyRecommendation(
                        package_name=n.name,
                        current_version=n.current_version,
                        recommended_version=lat,
                        recommendation_type="UPGRADE",
                        rationale=f"Upgrade {n.name} from {n.current_version} to latest stable {lat}.",
                        breaking_change_risk="HIGH" if diff_type == "MAJOR" else "LOW",
                        ecosystem=n.ecosystem,
                    ))
            elif n.latest_version and PackageVersion(n.current_version) < PackageVersion(n.latest_version):
                recs.append(DependencyRecommendation(
                    package_name=n.name,
                    current_version=n.current_version,
                    recommended_version=n.latest_version,
                    recommendation_type="UPGRADE",
                    rationale=f"Upgrade {n.name} to {n.latest_version}.",
                    breaking_change_risk="LOW",
                    ecosystem=n.ecosystem,
                ))
        return recs
