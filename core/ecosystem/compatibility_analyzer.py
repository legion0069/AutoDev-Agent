"""
compatibility_analyzer.py - Multi-Dimensional Compatibility Matrix Engine (v3.2)

Evaluates:
- Dependency compatibility
- Framework compatibility
- Language runtime compatibility (e.g. Python 3.12 with Pydantic v1 vs v2)
- Operating system compatibility (Windows, Linux, macOS)
- Container compatibility (Alpine vs Debian vs Distroless)
- Cloud runtime compatibility (AWS Lambda, GCP Cloud Run, Azure Container Apps)
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

from core.ecosystem.ecosystem_models import (
    CompatibilityCheckResult,
    CompatibilityStatus,
    PackageVersion,
)

logger = logging.getLogger("AutoDev.CompatibilityAnalyzer")


class CompatibilityAnalyzer:
    """
    Evaluates multi-dimensional compatibility matrices across languages,
    frameworks, dependencies, operating systems, and container runtimes.
    """

    KNOWN_COMPATIBILITY_RULES = [
        # Python Runtime vs Frameworks
        {
            "dim": "LANGUAGE",
            "comp_a": "Python",
            "ver_a": "3.12",
            "comp_b": "FastAPI",
            "min_ver_b": "0.100.0",
            "status": CompatibilityStatus.COMPATIBLE,
            "details": "FastAPI >=0.100.0 fully supports Python 3.12.",
        },
        {
            "dim": "LANGUAGE",
            "comp_a": "Python",
            "ver_a": "3.12",
            "comp_b": "Pydantic",
            "min_ver_b": "2.4.0",
            "status": CompatibilityStatus.COMPATIBLE,
            "details": "Python 3.12 requires Pydantic v2.4+ for binary wheels without compile errors.",
        },
        {
            "dim": "LANGUAGE",
            "comp_a": "Python",
            "ver_a": "3.12",
            "comp_b": "pycrypto",
            "min_ver_b": "999.0.0",
            "status": CompatibilityStatus.INCOMPATIBLE,
            "details": "pycrypto cannot build on Python 3.12 due to removed C headers.",
        },
        # Java Runtime vs Spring Boot
        {
            "dim": "LANGUAGE",
            "comp_a": "Java",
            "ver_a": "17",
            "comp_b": "Spring Boot",
            "min_ver_b": "3.0.0",
            "status": CompatibilityStatus.COMPATIBLE,
            "details": "Spring Boot 3.x baseline requirement is Java 17.",
        },
        {
            "dim": "LANGUAGE",
            "comp_a": "Java",
            "ver_a": "8",
            "comp_b": "Spring Boot",
            "min_ver_b": "3.0.0",
            "status": CompatibilityStatus.INCOMPATIBLE,
            "details": "Spring Boot 3 cannot run on Java 8 (class file version 61 required).",
        },
        # Node vs React
        {
            "dim": "LANGUAGE",
            "comp_a": "Node",
            "ver_a": "16",
            "comp_b": "React",
            "min_ver_b": "19.0.0",
            "status": CompatibilityStatus.INCOMPATIBLE,
            "details": "React 19 requires Node.js >=18.17.0 for SSR and compiler features.",
        },
        # OS vs Runtime
        {
            "dim": "OS",
            "comp_a": "Windows",
            "ver_a": "11",
            "comp_b": "Python",
            "min_ver_b": "3.8.0",
            "status": CompatibilityStatus.COMPATIBLE,
            "details": "Standard Windows 64-bit Python installer supported.",
        },
        # Container vs Alpine
        {
            "dim": "CONTAINER",
            "comp_a": "Alpine Linux",
            "ver_a": "3.19",
            "comp_b": "Python",
            "min_ver_b": "3.10.0",
            "status": CompatibilityStatus.CONDITIONAL,
            "details": "Requires musl-compatible wheels or build-base toolchain.",
        },
    ]

    def check_compatibility(
        self,
        component_a: str,
        version_a: str,
        component_b: str,
        version_b: str,
        dimension: str = "LANGUAGE",
    ) -> CompatibilityCheckResult:
        """Evaluates pair-wise compatibility between two components."""
        ca_clean = component_a.lower()
        cb_clean = component_b.lower()

        for rule in self.KNOWN_COMPATIBILITY_RULES:
            ra = rule["comp_a"].lower()
            rb = rule["comp_b"].lower()

            if ra in ca_clean and rb in cb_clean:
                ver_a_input = version_a
                ver_b_input = version_b
            elif ra in cb_clean and rb in ca_clean:
                ver_a_input = version_b
                ver_b_input = version_a
            else:
                continue

            # Verify ver_a condition if present
            if "ver_a" in rule:
                rule_ver_a = PackageVersion(rule["ver_a"])
                input_ver_a = PackageVersion(ver_a_input)
                if rule["status"] == CompatibilityStatus.INCOMPATIBLE:
                    if input_ver_a > rule_ver_a:
                        continue
                else:
                    if input_ver_a < rule_ver_a:
                        continue

            target_v = PackageVersion(ver_b_input)
            min_v = PackageVersion(rule["min_ver_b"])

            if rule["status"] == CompatibilityStatus.INCOMPATIBLE:
                return CompatibilityCheckResult(
                    component_a=component_a,
                    component_b=component_b,
                    dimension=rule["dim"],
                    status=CompatibilityStatus.INCOMPATIBLE,
                    details=rule["details"],
                )

            if target_v >= min_v:
                return CompatibilityCheckResult(
                    component_a=component_a,
                    component_b=component_b,
                    dimension=rule["dim"],
                    status=CompatibilityStatus.COMPATIBLE,
                    details=rule["details"],
                    min_required_version=rule["min_ver_b"],
                )
            else:
                return CompatibilityCheckResult(
                    component_a=component_a,
                    component_b=component_b,
                    dimension=rule["dim"],
                    status=CompatibilityStatus.INCOMPATIBLE,
                    details=f"{component_a} {version_a} requires {component_b} >={rule['min_ver_b']}, but found {ver_b_input}.",
                    min_required_version=rule["min_ver_b"],
                )

        # Default compatibility assumption for standard packages
        return CompatibilityCheckResult(
            component_a=component_a,
            component_b=component_b,
            dimension=dimension,
            status=CompatibilityStatus.COMPATIBLE,
            details=f"No known incompatibilities detected between {component_a} and {component_b}.",
        )

    def generate_compatibility_matrix(
        self,
        primary_runtime: str,
        runtime_version: str,
        dependencies: List[Tuple[str, str]],
        target_os: str = "Linux",
        target_cloud: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generates comprehensive compatibility matrix across dependencies, runtime, OS, and cloud."""
        matrix: List[Dict[str, Any]] = []
        incompatible_count = 0

        for dep_name, dep_ver in dependencies:
            res = self.check_compatibility(primary_runtime, runtime_version, dep_name, dep_ver)
            if res.status == CompatibilityStatus.INCOMPATIBLE:
                incompatible_count += 1
            matrix.append(res.to_dict())

        # Check OS
        os_res = self.check_compatibility(target_os, "latest", primary_runtime, runtime_version, dimension="OS")
        matrix.append(os_res.to_dict())

        # Check Cloud if specified
        if target_cloud:
            cloud_res = self.check_compatibility(target_cloud, "latest", primary_runtime, runtime_version, dimension="CLOUD")
            matrix.append(cloud_res.to_dict())

        return {
            "runtime": f"{primary_runtime} {runtime_version}",
            "target_os": target_os,
            "target_cloud": target_cloud,
            "total_checks": len(matrix),
            "is_fully_compatible": (incompatible_count == 0),
            "incompatibilities_found": incompatible_count,
            "matrix": matrix,
        }
