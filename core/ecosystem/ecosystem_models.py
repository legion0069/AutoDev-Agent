"""
ecosystem_models.py - Domain Models and Data Contracts for External Intelligence & Ecosystem Awareness (v3.2)

Defines dataclasses, enumerations, DTOs, and serialization schemas for:
- Dependency Intelligence (PackageVersion, DependencyGraph, DependencyRecommendation)
- Security Intelligence (CVEAdvisory, SecurityRiskAssessment, VulnerabilityReport)
- Framework Intelligence (FrameworkRelease, DeprecatedAPI, FrameworkKnowledge)
- Open Source Intelligence (RepoMetrics, CommunityHealth, OSSRecommendation)
- Technology Radar (RadarRing, TechRadarEntry, TechnologyRadarReport)
- Migration Planning (MigrationStep, BreakingChange, MigrationPlan)
- Compatibility Analysis (CompatibilityDimension, CompatibilityMatrix)
- Engineering Recommendations (RecommendationCategory, EngineeringRecommendation)
- Release Intelligence (ReleaseAnalysis, SemVerImpact, ReleaseReport)
- External Knowledge Cache (CacheEntry, EcosystemKnowledgeSnapshot)
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# ---------------------------------------------------------------------------
# 1. Enums & Classifications
# ---------------------------------------------------------------------------

class DependencyEcosystem(str, Enum):
    PYTHON = "PYTHON"
    PIP = "PYTHON"
    NPM = "NPM"
    MAVEN = "MAVEN"
    GRADLE = "GRADLE"
    CARGO = "CARGO"
    GOMOD = "GOMOD"
    COMPOSER = "COMPOSER"
    GENERIC = "GENERIC"


PackageEcosystem = DependencyEcosystem


class LicenseCategory(str, Enum):
    PERMISSIVE = "PERMISSIVE"
    COPYLEFT = "COPYLEFT"
    RESTRICTIVE = "RESTRICTIVE"
    PROPRIETARY = "PROPRIETARY"
    UNKNOWN = "UNKNOWN"


class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


class RadarRing(str, Enum):
    ADOPT = "ADOPT"
    TRIAL = "TRIAL"
    ASSESS = "ASSESS"
    HOLD = "HOLD"


class RadarQuadrant(str, Enum):
    LANGUAGES_AND_FRAMEWORKS = "LANGUAGES_AND_FRAMEWORKS"
    LIBRARIES_AND_PACKAGES = "LIBRARIES_AND_PACKAGES"
    TOOLS_AND_TESTING = "TOOLS_AND_TESTING"
    INFRASTRUCTURE_AND_STORAGE = "INFRASTRUCTURE_AND_STORAGE"


class ReleaseImpact(str, Enum):
    MAJOR_BREAKING = "MAJOR_BREAKING"
    MINOR_FEATURE = "MINOR_FEATURE"
    PATCH_SECURITY = "PATCH_SECURITY"
    HOTFIX = "HOTFIX"


class CompatibilityStatus(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    CONDITIONAL = "CONDITIONAL"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# 2. Dependency Intelligence Contracts
# ---------------------------------------------------------------------------

@dataclass
class PackageVersion:
    """Represents a discrete semantic version of a package dependency."""
    raw_version: str
    major: int = 0
    minor: int = 0
    patch: int = 0
    prerelease: Optional[str] = None
    build: str = ""

    def __post_init__(self) -> None:
        if not self.raw_version:
            self.raw_version = "0.0.0"
        self._parse()

    def _parse(self) -> None:
        clean = self.raw_version.strip().lstrip("vV^~>=< ")
        if "+" in clean:
            clean, self.build = clean.split("+", 1)
        if "-" in clean:
            ver_part, self.prerelease = clean.split("-", 1)
        else:
            ver_part = clean

        parts = ver_part.split(".")
        try:
            self.major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
            self.minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            self.patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        except (ValueError, IndexError):
            pass

    @property
    def raw(self) -> str:
        return self.raw_version

    def __str__(self) -> str:
        return self.raw_version

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, str):
            other = PackageVersion(other)
        if not isinstance(other, PackageVersion):
            return NotImplemented
        # Release vs Prerelease
        if (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch):
            if self.prerelease and not other.prerelease:
                return True
            if not self.prerelease and other.prerelease:
                return False
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: Any) -> bool:
        return self == other or self < other

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, str):
            other = PackageVersion(other)
        if not isinstance(other, PackageVersion):
            return NotImplemented
        return not (self <= other)

    def __ge__(self, other: Any) -> bool:
        return self == other or self > other

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            other = PackageVersion(other)
        if not isinstance(other, PackageVersion):
            return False
        return (self.major, self.minor, self.patch, self.prerelease) == (
            other.major, other.minor, other.patch, other.prerelease
        )

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch, self.prerelease))

    def matches(self, spec: str) -> bool:
        """Evaluates whether this version satisfies a version specification."""
        spec = spec.strip()
        if not spec or spec in ("*", "latest"):
            return True
        # Compound specs like '>=1.0.0,<2.0.0'
        if "," in spec:
            return all(self.matches(sub) for sub in spec.split(","))

        if spec.startswith("=="):
            return self == PackageVersion(spec[2:])
        elif spec.startswith(">="):
            return self >= PackageVersion(spec[2:])
        elif spec.startswith("<="):
            return self <= PackageVersion(spec[2:])
        elif spec.startswith(">"):
            return self > PackageVersion(spec[1:])
        elif spec.startswith("<"):
            return self < PackageVersion(spec[1:])
        elif spec.startswith("!="):
            return self != PackageVersion(spec[2:])
        elif spec.startswith("~="):
            target = PackageVersion(spec[2:])
            return self >= target and self.major == target.major and self.minor == target.minor
        elif spec.startswith("^"):
            target = PackageVersion(spec[1:])
            return self >= target and self.major == target.major
        else:
            return self == PackageVersion(spec)

    def is_major_upgrade_from(self, other: PackageVersion) -> bool:
        """Returns True if this version represents a breaking major release upgrade."""
        return self.major > other.major

    def is_breaking_change(self, other: PackageVersion) -> bool:
        """Returns True if this version introduces breaking API changes from other."""
        return self.is_major_upgrade_from(other)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_version": self.raw_version,
            "major": self.major,
            "minor": self.minor,
            "patch": self.patch,
            "prerelease": self.prerelease,
            "build": self.build,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PackageVersion:
        return cls(raw_version=data.get("raw_version", "0.0.0"))


@dataclass
class DependencyNode:
    """Represents a single package node within a project dependency graph."""
    name: str
    version_spec: str = "latest"
    current_version: str = "0.0.0"
    ecosystem: DependencyEcosystem = DependencyEcosystem.PYTHON
    is_direct: bool = True
    scope: str = "runtime"  # runtime, dev, test, provided
    transitive_dependencies: List[str] = field(default_factory=list)
    license: str = "UNKNOWN"
    is_deprecated: bool = False
    deprecation_notice: str = ""
    latest_stable_version: str = ""
    latest_version: str = ""
    manifest_path: str = ""
    version_constraint: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.latest_version and self.latest_stable_version:
            self.latest_version = self.latest_stable_version
        elif not self.latest_stable_version and self.latest_version:
            self.latest_stable_version = self.latest_version

        if self.version_constraint and (self.version_spec == "latest" or not self.version_spec):
            self.version_spec = self.version_constraint
        elif self.version_spec and not self.version_constraint:
            self.version_constraint = self.version_spec

    @property
    def is_dev(self) -> bool:
        return self.scope.lower() in ("dev", "test")

    @property
    def is_transitive(self) -> bool:
        return not self.is_direct

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["ecosystem"] = self.ecosystem.value if isinstance(self.ecosystem, Enum) else str(self.ecosystem)
        return d


@dataclass
class DependencyConflict:
    """Represents a version or dependency conflict between packages."""
    package_name: str
    conflicting_versions: List[str]
    reason: str
    recommended_resolution: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DependencyRecommendation:
    """Actionable recommendation for upgrading, replacing, or patching a package."""
    package_name: str
    current_version: str
    recommended_version: str
    recommendation_type: str  # UPGRADE, SECURITY_PATCH, REPLACEMENT, PRUNE_UNUSED, LICENSE_RESOLVE
    rationale: str
    breaking_change_risk: str = "LOW"  # LOW, MEDIUM, HIGH
    ecosystem: DependencyEcosystem = DependencyEcosystem.GENERIC
    migration_notes: List[str] = field(default_factory=list)
    replacement_package: Optional[str] = None
    recommended_replacement: Optional[str] = None
    reason: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.replacement_package and not self.recommended_replacement:
            self.recommended_replacement = self.replacement_package
        elif self.recommended_replacement and not self.replacement_package:
            self.replacement_package = self.recommended_replacement

        if self.rationale and not self.reason:
            self.reason = self.rationale
        elif self.reason and not self.rationale:
            self.rationale = self.reason

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["ecosystem"] = self.ecosystem.value if isinstance(self.ecosystem, Enum) else str(self.ecosystem)
        return d


# ---------------------------------------------------------------------------
# 3. Security Intelligence Contracts
# ---------------------------------------------------------------------------

@dataclass
class CVEAdvisory:
    """Represents an external security advisory or Common Vulnerability and Exposure."""
    cve_id: str
    package_name: str
    ecosystem: DependencyEcosystem
    affected_version_spec: str
    patched_versions: List[str]
    severity: SeverityLevel
    cvss_score: float
    title: str
    description: str
    cwe_id: str = ""
    remediation: str = ""
    published_date: str = ""
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["ecosystem"] = self.ecosystem.value if isinstance(self.ecosystem, Enum) else str(self.ecosystem)
        d["severity"] = self.severity.value if isinstance(self.severity, Enum) else str(self.severity)
        return d


@dataclass
class VulnerabilityFinding:
    """Discrete security vulnerability detected in code or dependencies."""
    finding_id: str
    category: str  # CVE, HARDCODED_SECRET, DEPRECATED_CRYPTO, UNSAFE_RANDOMNESS, UNSAFE_API, EXPIRED_CERT
    target: str  # File path, package name, or symbol
    severity: SeverityLevel
    description: str
    line_number: Optional[int] = None
    snippet: str = ""
    cve_id: Optional[str] = None
    remediation_advice: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value if isinstance(self.severity, Enum) else str(self.severity)
        return d


# ---------------------------------------------------------------------------
# 4. Framework Intelligence Contracts
# ---------------------------------------------------------------------------

@dataclass
class FrameworkRelease:
    """Represents a release milestone for a primary web, backend, or cloud framework."""
    framework: str
    version: str
    release_date: str
    is_lts: bool = False
    is_deprecated: bool = False
    breaking_changes: List[str] = field(default_factory=list)
    deprecated_apis: List[str] = field(default_factory=list)
    recommended_min_python_or_node: str = ""
    migration_guide_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 5. Technology Radar Contracts
# ---------------------------------------------------------------------------

@dataclass
class TechRadarEntry:
    """Entry on the organization technology radar."""
    name: str
    quadrant: RadarQuadrant
    ring: RadarRing
    description: str
    rationale: str
    maturity_score: float = 80.0
    recommended_alternatives: List[str] = field(default_factory=list)
    last_evaluated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["quadrant"] = self.quadrant.value if isinstance(self.quadrant, Enum) else str(self.quadrant)
        d["ring"] = self.ring.value if isinstance(self.ring, Enum) else str(self.ring)
        return d


# ---------------------------------------------------------------------------
# 6. Migration Planning Contracts
# ---------------------------------------------------------------------------

@dataclass
class MigrationStep:
    """Discrete executable step in a framework or runtime migration plan."""
    step_number: int
    title: str
    target_component: str
    action_type: str  # CODE_REFACTOR, CONFIG_UPDATE, DEPENDENCY_UPGRADE, TEST_VALIDATION
    instructions: str
    automated_regex_or_pattern: Optional[str] = None
    code_modification_example: str = ""
    verification_check: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MigrationPlan:
    """Comprehensive migration execution plan between major versions."""
    plan_id: str
    source_technology: str
    from_version: str
    to_version: str
    title: str
    summary: str
    breaking_apis: List[str] = field(default_factory=list)
    code_modifications: List[str] = field(default_factory=list)
    steps: List[MigrationStep] = field(default_factory=list)
    testing_requirements: List[str] = field(default_factory=list)
    rollback_plan: List[str] = field(default_factory=list)
    estimated_hours: float = 8.0
    risk_level: str = "MEDIUM"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["steps"] = [s.to_dict() for s in self.steps]
        return d


# ---------------------------------------------------------------------------
# 7. Compatibility Analysis Contracts
# ---------------------------------------------------------------------------

@dataclass
class CompatibilityCheckResult:
    """Result of checking compatibility across languages, OS, frameworks, and containers."""
    component_a: str
    component_b: str
    dimension: str  # LANGUAGE, FRAMEWORK, OS, CLOUD, CONTAINER
    status: CompatibilityStatus
    details: str
    min_required_version: str = ""
    supported_range: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, Enum) else str(self.status)
        return d


# ---------------------------------------------------------------------------
# 8. Engineering Recommendation Contracts
# ---------------------------------------------------------------------------

@dataclass
class EngineeringRecommendation:
    """Technology, architectural, or tooling recommendation based on project characteristics."""
    recommendation_id: str
    category: str  # LIBRARY, FRAMEWORK, ARCHITECTURE, TESTING_TOOL, CICD, OBSERVABILITY
    recommended_solution: str
    rationale: str
    confidence_score: float = 0.90
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 9. Release Intelligence Contracts
# ---------------------------------------------------------------------------

@dataclass
class ReleaseAnalysis:
    """Semantic analysis of a framework, runtime, or package release."""
    package_or_tool: str
    version: str
    release_date: str
    impact: ReleaseImpact
    summary: str
    breaking_changes: List[str] = field(default_factory=list)
    security_fixes: List[str] = field(default_factory=list)
    new_features: List[str] = field(default_factory=list)
    recommended_adoption_window: str = "TRIAL_IMMEDIATELY"  # IMMEDIATE, NEXT_SPRINT, ASSESS_QUARTERLY, HOLD
    risk_score: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["impact"] = self.impact.value if isinstance(self.impact, Enum) else str(self.impact)
        return d
