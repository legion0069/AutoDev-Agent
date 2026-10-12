"""
AutoDev Diagnostic Models (v2.6)
Data structures representing failure evidence, root-cause hypotheses,
confidence levels, and diagnostic analysis reports.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class ConfidenceLevel(str, enum.Enum):
    """Calibrated confidence scale for diagnostic hypotheses."""
    CERTAIN = "certain"    # 0.90 - 1.00 (deterministic proof from compiler/syntax/stack)
    HIGH = "high"          # 0.75 - 0.89 (strong stack trace + symbol correlation)
    MEDIUM = "medium"      # 0.50 - 0.74 (partial correlation, multiple possibilities)
    LOW = "low"            # 0.25 - 0.49 (speculative inference)
    UNCERTAIN = "uncertain"# 0.00 - 0.24 (insufficient evidence)

    @classmethod
    def from_score(cls, score: float) -> ConfidenceLevel:
        if score >= 0.90:
            return cls.CERTAIN
        elif score >= 0.75:
            return cls.HIGH
        elif score >= 0.50:
            return cls.MEDIUM
        elif score >= 0.25:
            return cls.LOW
        return cls.UNCERTAIN


class FailureCategory(str, enum.Enum):
    """Categorization of underlying software root causes."""
    LOGIC_ERROR = "logic_error"
    BOUNDARY_CONDITION = "boundary_condition"
    OFF_BY_ONE = "off_by_one"
    NULL_DEREFERENCE = "null_dereference"
    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    TYPE_MISMATCH = "type_mismatch"
    ENVIRONMENTAL = "environmental"
    FLAKY = "flaky"
    SECURITY_VIOLATION = "security_violation"
    CONCURRENCY_RACE = "concurrency_race"
    PERFORMANCE_REGRESSION = "performance_regression"
    UNKNOWN = "unknown"


@dataclass
class StackFrameEvidence:
    """Detailed information for a single frame extracted from a stack trace."""
    file_path: str
    line_number: int
    function_name: str
    code_line: str = ""
    is_in_workspace: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FailureEvidence:
    """Aggregated, bounded evidence bundle used for root-cause analysis."""
    test_id: str
    test_name: str
    test_file: str = ""
    failure_message: str = ""
    stack_trace: str = ""
    stack_frames: List[StackFrameEvidence] = field(default_factory=list)
    failing_source_lines: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    recently_changed_files: List[str] = field(default_factory=list)
    recent_diffs: Dict[str, str] = field(default_factory=dict)
    symbol_graph_context: Dict[str, Any] = field(default_factory=dict)
    impact_analysis_summary: Dict[str, Any] = field(default_factory=dict)
    journal_events: List[Dict[str, Any]] = field(default_factory=list)
    is_environmental: bool = False
    is_flaky: bool = False
    redacted: bool = True

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["stack_frames"] = [f.to_dict() for f in self.stack_frames]
        return data


@dataclass
class RootCauseHypothesis:
    """A ranked hypothesis explaining the root cause of a failure."""
    hypothesis_id: str = field(default_factory=lambda: f"hypo_{uuid.uuid4().hex[:8]}")
    summary: str = ""
    failure_category: FailureCategory = FailureCategory.UNKNOWN
    affected_files: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    supporting_evidence: List[str] = field(default_factory=list)
    contradicting_evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    estimated_risk: str = "medium"  # "low", "medium", "high", "critical"
    recommended_next_action: str = ""
    requires_additional_test: bool = False
    requires_human_review: bool = False
    is_environmental: bool = False
    suggested_fix_description: str = ""

    def __post_init__(self):
        self.confidence_level = ConfidenceLevel.from_score(self.confidence)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["failure_category"] = self.failure_category.value
        data["confidence_level"] = self.confidence_level.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RootCauseHypothesis:
        payload = dict(data)
        if isinstance(payload.get("failure_category"), str):
            payload["failure_category"] = FailureCategory(payload["failure_category"])
        if isinstance(payload.get("confidence_level"), str):
            payload["confidence_level"] = ConfidenceLevel(payload["confidence_level"])
        return cls(**payload)


@dataclass
class DiagnosticReport:
    """Comprehensive diagnostic analysis output containing evidence and ranked hypotheses."""
    report_id: str = field(default_factory=lambda: f"diag_{uuid.uuid4().hex[:8]}")
    run_id: str = ""
    project_id: str = "default_project"
    transaction_id: Optional[str] = None
    test_id: str = ""
    timestamp: float = field(default_factory=time.time)
    evidence: Optional[FailureEvidence] = None
    hypotheses: List[RootCauseHypothesis] = field(default_factory=list)
    selected_hypothesis: Optional[RootCauseHypothesis] = None
    deterministic_findings: List[str] = field(default_factory=list)
    llm_enhanced: bool = False

    @property
    def highest_confidence_hypothesis(self) -> Optional[RootCauseHypothesis]:
        if not self.hypotheses:
            return None
        return max(self.hypotheses, key=lambda h: h.confidence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "run_id": self.run_id,
            "project_id": self.project_id,
            "transaction_id": self.transaction_id,
            "test_id": self.test_id,
            "timestamp": self.timestamp,
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "selected_hypothesis": self.selected_hypothesis.to_dict() if self.selected_hypothesis else None,
            "deterministic_findings": self.deterministic_findings,
            "llm_enhanced": self.llm_enhanced,
        }
