"""
AutoDev Repair Models (v2.6)
Data models for repair plans, candidate patches, diff analysis,
validation gates, and policy constraints.
"""

from __future__ import annotations

import enum
import hashlib
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class RepairMode(str, enum.Enum):
    """Operational mode for the self-healing repair engine."""
    OBSERVE_ONLY = "observe_only"   # Diagnoses and generates candidate diff without applying
    ASSISTED = "assisted"           # Applies candidate in isolation, requires approval before acceptance
    AUTONOMOUS = "autonomous"       # Autonomously repairs and verifies within policy bounds


class PatchStatus(str, enum.Enum):
    """Lifecycle status of an individual candidate patch."""
    DRAFT = "draft"
    VALIDATED = "validated"
    REJECTED = "rejected"
    APPLIED = "applied"
    VERIFIED = "verified"
    ROLLED_BACK = "rolled_back"


class ValidationGateStatus(str, enum.Enum):
    """Status for a single validation gate."""
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class RiskLevel(str, enum.Enum):
    """Risk rating for a code repair change."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FilePatch:
    """Represents a minimal file-level patch within a candidate repair."""
    file_path: str
    original_content: str = ""
    new_content: str = ""
    diff_unified: str = ""
    original_hash: str = ""
    new_hash: str = ""
    lines_added: int = 0
    lines_removed: int = 0
    is_test_file: bool = False
    is_security_sensitive: bool = False

    def __post_init__(self):
        if not self.original_hash and self.original_content:
            self.original_hash = hashlib.sha256(self.original_content.encode("utf-8")).hexdigest()
        if not self.new_hash and self.new_content:
            self.new_hash = hashlib.sha256(self.new_content.encode("utf-8")).hexdigest()
        if self.file_path.startswith("tests/") or "test" in self.file_path.lower():
            self.is_test_file = True

    @property
    def total_lines_changed(self) -> int:
        return self.lines_added + self.lines_removed

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CandidatePatch:
    """A full candidate patch containing one or more file modifications."""
    patch_id: str = field(default_factory=lambda: f"patch_{uuid.uuid4().hex[:8]}")
    plan_id: str = ""
    hypothesis_id: str = ""
    file_patches: List[FilePatch] = field(default_factory=list)
    rationale: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    status: PatchStatus = PatchStatus.DRAFT
    created_at: float = field(default_factory=time.time)

    @property
    def total_lines_changed(self) -> int:
        return sum(fp.total_lines_changed for fp in self.file_patches)

    @property
    def modified_files(self) -> List[str]:
        return [fp.file_path for fp in self.file_patches]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "plan_id": self.plan_id,
            "hypothesis_id": self.hypothesis_id,
            "file_patches": [fp.to_dict() for fp in self.file_patches],
            "rationale": self.rationale,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "total_lines_changed": self.total_lines_changed,
            "modified_files": self.modified_files,
            "created_at": self.created_at,
        }


@dataclass
class RepairPlan:
    """Detailed specification of what and why a repair should be performed."""
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    hypothesis_id: str = ""
    test_id: str = ""
    failing_behavior: str = ""
    expected_behavior: str = ""
    target_files: List[str] = field(default_factory=list)
    target_symbols: List[str] = field(default_factory=list)
    targeted_tests: List[str] = field(default_factory=list)
    rationale: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    requires_human_approval: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["risk_level"] = self.risk_level.value
        return data


@dataclass
class PatchValidationResult:
    """Result of static and policy checks on a proposed CandidatePatch."""
    is_valid: bool = True
    rejection_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    syntax_ok: bool = True
    containment_ok: bool = True
    size_ok: bool = True
    anti_weakening_ok: bool = True
    security_ok: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RepairPolicy:
    """Configuration and guardrails for autonomous self-healing execution."""
    enabled: bool = True
    mode: RepairMode = RepairMode.AUTONOMOUS
    max_repair_attempts: int = 3
    max_candidate_patches: int = 5
    max_total_duration_seconds: int = 300
    max_diagnostic_runs: int = 5
    max_test_runs: int = 15
    max_diff_lines: int = 150
    validation_level: str = "standard"  # "targeted", "standard", "comprehensive", "full_suite"
    require_human_approval: bool = False
    allow_security_sensitive_changes: bool = False
    allow_dependency_changes: bool = False
    allow_public_api_changes: bool = False
    rollback_on_verification_failure: bool = True

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["mode"] = self.mode.value
        return data
