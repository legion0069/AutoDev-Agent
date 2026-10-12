"""
AutoDev Quality Models (v2.7)
Structured data models, metrics containers, risk predictions, quality gate policies,
rejection diagnostics, and multi-format report payloads for predictive quality intelligence.
"""

from __future__ import annotations

import enum
import hashlib
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


class QualitySeverity(str, enum.Enum):
    """Severity levels for quality risks and rule violations."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class QualityRiskCategory(str, enum.Enum):
    """Categorization of predictive quality risks."""
    COMPLEXITY_EXPLOSION = "complexity_explosion"
    MAINTAINABILITY_DEGRADATION = "maintainability_degradation"
    REGRESSION_RISK = "regression_risk"
    ARCHITECTURAL_DRIFT = "architectural_drift"
    CYCLIC_DEPENDENCY = "cyclic_dependency"
    CODE_DUPLICATION = "code_duplication"
    THREAD_SAFETY_RACE = "thread_safety_race"
    RESOURCE_MEMORY_LEAK = "resource_memory_leak"
    API_CONTRACT_VIOLATION = "api_contract_violation"
    DEAD_CODE = "dead_code"
    GOD_OBJECT = "god_object"
    FRAGILE_BASE_CLASS = "fragile_base_class"
    LAYER_VIOLATION = "layer_violation"
    SECURITY_VULNERABILITY = "security_vulnerability"
    CONCURRENCY_RISK = "concurrency_risk"


class QualityGateStatus(str, enum.Enum):
    """Outcome status for Quality Gate evaluation."""
    PASSED = "PASSED"
    REJECTED = "REJECTED"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"


@dataclass
class CodeLocation:
    """Precise source code location of an issue, symbol, or duplicate block."""
    file_path: str
    start_line: int
    end_line: int
    start_col: int = 0
    end_col: int = 0
    symbol_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComplexityMetrics:
    """Deterministic complexity measurements for functions, classes, or files."""
    cyclomatic_complexity: int = 1
    cognitive_complexity: int = 0
    max_nesting_depth: int = 0
    longest_call_chain: int = 0
    loc: int = 0           # Lines of code (raw)
    sloc: int = 0          # Source lines of code (executable)
    comment_loc: int = 0   # Comment lines
    blank_loc: int = 0     # Blank lines
    avg_branch_depth: float = 0.0
    avg_method_length: float = 0.0
    halstead_volume: float = 0.0
    maintainability_index: float = 100.0  # 0 to 100

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DuplicationBlock:
    """Information regarding a detected duplicated code block or fragment."""
    block_id: str = field(default_factory=lambda: f"dup_{uuid.uuid4().hex[:8]}")
    locations: List[CodeLocation] = field(default_factory=list)
    line_count: int = 0
    token_count: int = 0
    duplication_type: str = "exact"  # "exact", "near_duplicate", "repeated_condition", "repeated_sql", "repeated_regex"
    code_snippet: str = ""
    similarity_score: float = 1.0

    @property
    def occurrences(self) -> List[CodeLocation]:
        return self.locations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "locations": [loc.to_dict() for loc in self.locations],
            "occurrences": [loc.to_dict() for loc in self.locations],
            "line_count": self.line_count,
            "token_count": self.token_count,
            "duplication_type": self.duplication_type,
            "code_snippet": self.code_snippet,
            "similarity_score": self.similarity_score,
        }


@dataclass
class DiamondInheritance:
    """Represents a detected diamond inheritance topology."""
    derived_class: str
    common_ancestor: str
    intermediate_parents: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GodObjectFinding:
    """Represents a God Object class violating SRP and metric thresholds."""
    class_name: str
    method_count: int
    attribute_count: int
    file_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HubModuleFinding:
    """Represents a central Hub module with excessive fan-in and fan-out."""
    module_name: str
    afferent_coupling: int
    efferent_coupling: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FragileBaseClassFinding:
    """Represents a deep inheritance hierarchy vulnerable to fragile base class defects."""
    class_name: str
    depth_of_inheritance: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DependencyHealthMetrics:
    """Graph-theoretic structural metrics for modules and packages."""
    afferent_coupling: int = 0     # Ca (incoming dependencies)
    efferent_coupling: int = 0     # Ce (outgoing dependencies)
    instability: float = 0.0       # I = Ce / (Ca + Ce)
    abstractness: float = 0.0      # A = Na / Nc
    distance_main_sequence: float = 0.0  # D = |A + I - 1|
    package_instability: Optional[float] = None
    distance_from_main_sequence: Optional[float] = None
    has_circular_dependencies: bool = False
    circular_dependency_cycles: List[List[str]] = field(default_factory=list)
    diamond_inheritance_count: int = 0
    diamond_inheritances: List[DiamondInheritance] = field(default_factory=list)
    god_objects: List[GodObjectFinding] = field(default_factory=list)
    hub_modules: List[HubModuleFinding] = field(default_factory=list)
    fragile_base_classes: List[FragileBaseClassFinding] = field(default_factory=list)
    is_god_object: bool = False
    is_hub_module: bool = False
    depth_of_inheritance: int = 0
    lack_of_cohesion_lcom4: int = 1

    def __post_init__(self):
        if self.package_instability is not None and self.instability == 0.0:
            self.instability = float(self.package_instability)
        elif self.package_instability is None:
            self.package_instability = float(self.instability)

        if self.distance_from_main_sequence is not None and self.distance_main_sequence == 0.0:
            self.distance_main_sequence = float(self.distance_from_main_sequence)
        elif self.distance_from_main_sequence is None:
            self.distance_from_main_sequence = float(self.distance_main_sequence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "afferent_coupling": self.afferent_coupling,
            "efferent_coupling": self.efferent_coupling,
            "instability": self.instability,
            "package_instability": self.instability,
            "abstractness": self.abstractness,
            "distance_main_sequence": self.distance_main_sequence,
            "distance_from_main_sequence": self.distance_main_sequence,
            "has_circular_dependencies": self.has_circular_dependencies,
            "circular_dependency_cycles": self.circular_dependency_cycles,
            "diamond_inheritance_count": len(self.diamond_inheritances) or self.diamond_inheritance_count,
            "diamond_inheritances": [d.to_dict() for d in self.diamond_inheritances],
            "god_objects": [g.to_dict() for g in self.god_objects],
            "hub_modules": [h.to_dict() for h in self.hub_modules],
            "fragile_base_classes": [f.to_dict() for f in self.fragile_base_classes],
            "is_god_object": self.is_god_object or len(self.god_objects) > 0,
            "is_hub_module": self.is_hub_module or len(self.hub_modules) > 0,
            "depth_of_inheritance": self.depth_of_inheritance,
            "lack_of_cohesion_lcom4": self.lack_of_cohesion_lcom4,
        }


@dataclass
class QualityIssue:
    """Structured finding identified during predictive quality assessment."""
    issue_id: str = field(default_factory=lambda: f"qissue_{uuid.uuid4().hex[:8]}")
    rule_id: str = ""
    rule_name: str = ""
    category: QualityRiskCategory = QualityRiskCategory.COMPLEXITY_EXPLOSION
    severity: QualitySeverity = QualitySeverity.MEDIUM
    description: str = ""
    location: Optional[CodeLocation] = None
    affected_symbols: List[str] = field(default_factory=list)
    remediation_suggestion: str = ""
    technical_debt_minutes: int = 15
    evidence: Dict[str, Any] = field(default_factory=dict)

    @property
    def file_path(self) -> str:
        return self.location.file_path if self.location else ""

    @property
    def line_number(self) -> int:
        return self.location.start_line if self.location else 1

    @property
    def remediation(self) -> str:
        return self.remediation_suggestion

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "category": self.category.value if hasattr(self.category, "value") else str(self.category),
            "severity": self.severity.value if hasattr(self.severity, "value") else str(self.severity),
            "description": self.description,
            "location": self.location.to_dict() if self.location else None,
            "affected_symbols": self.affected_symbols,
            "remediation_suggestion": self.remediation_suggestion,
            "technical_debt_minutes": self.technical_debt_minutes,
            "evidence": self.evidence,
        }


@dataclass
class PredictiveRiskScores:
    """Deterministic probabilistic forecast of pre-execution risks."""
    overall_risk_score: float = 0.0        # 0.0 (safe) to 1.0 (extreme risk)
    regression_probability: float = 0.0    # 0.0 to 1.0
    future_failure_probability: float = 0.0 # 0.0 to 1.0
    architecture_drift_risk: float = 0.0   # 0.0 to 1.0
    api_breaking_risk: float = 0.0         # 0.0 to 1.0
    performance_regression_risk: float = 0.0 # 0.0 to 1.0
    security_risk: float = 0.0             # 0.0 to 1.0
    concurrency_race_risk: float = 0.0     # 0.0 to 1.0
    timeout_leak_risk: float = 0.0         # 0.0 to 1.0
    review_confidence: float = 1.0         # 0.0 to 1.0
    security_confidence: float = 1.0       # 0.0 to 1.0
    testing_confidence: float = 1.0        # 0.0 to 1.0
    public_exposure_score: float = 0.0     # 0.0 to 1.0
    mutation_risk: float = 0.0             # 0.0 to 1.0

    @property
    def composite_risk_score(self) -> float:
        return self.overall_risk_score * 100.0 if self.overall_risk_score <= 1.0 else self.overall_risk_score

    @property
    def architecture_drift_probability(self) -> float:
        return self.architecture_drift_risk

    @property
    def deadlock_risk(self) -> float:
        return self.concurrency_race_risk

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QualityGatePolicy:
    """Configurable thresholds that govern automated task gate approval/rejection."""
    max_cyclomatic_complexity: int = 15
    max_cognitive_complexity: int = 20
    max_nesting_depth: int = 4
    min_maintainability_index: float = 40.0
    max_duplication_percentage: float = 10.0
    max_regression_probability: float = 0.40
    min_security_confidence: float = 0.70
    min_review_confidence: float = 0.60
    max_dependency_instability: float = 0.85
    max_technical_debt_minutes: int = 180
    disallow_circular_dependencies: bool = True
    allow_circular_dependencies: Optional[bool] = None
    disallow_god_objects: bool = True
    strict_mode: bool = False

    def __post_init__(self):
        if self.allow_circular_dependencies is not None:
            self.disallow_circular_dependencies = not self.allow_circular_dependencies

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QualityGateResult:
    """Outcome of QualityGate evaluation against a set of quality metrics and issues."""
    status: QualityGateStatus = QualityGateStatus.PASSED
    rejection_reasons: List[str] = field(default_factory=list)
    warning_reasons: List[str] = field(default_factory=list)
    refactoring_suggestions: List[str] = field(default_factory=list)
    evaluated_policy: Optional[QualityGatePolicy] = None
    summary: str = ""
    reasons: Optional[List[str]] = None
    score: float = 100.0

    def __post_init__(self):
        if self.reasons is not None and not self.rejection_reasons:
            if self.status == QualityGateStatus.REJECTED:
                self.rejection_reasons = list(self.reasons)
            else:
                self.warning_reasons = list(self.reasons)
        elif self.reasons is None:
            self.reasons = self.rejection_reasons + self.warning_reasons
        if not self.is_passed and self.score == 100.0:
            self.score = 0.0

    @property
    def is_passed(self) -> bool:
        return self.status in (QualityGateStatus.PASSED, QualityGateStatus.WARNING)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "rejection_reasons": self.rejection_reasons,
            "warning_reasons": self.warning_reasons,
            "reasons": self.reasons or (self.rejection_reasons + self.warning_reasons),
            "refactoring_suggestions": self.refactoring_suggestions,
            "evaluated_policy": self.evaluated_policy.to_dict() if self.evaluated_policy else None,
            "summary": self.summary,
            "score": self.score,
        }


@dataclass
class QualityAssessmentResult:
    """Aggregated assessment bundle generated by PredictiveQualityEngine for a task or workspace."""
    assessment_id: str = field(default_factory=lambda: f"qassess_{uuid.uuid4().hex[:8]}")
    project_id: str = "default_project"
    task_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    analyzed_files_count: int = 0
    total_loc: int = 0
    total_sloc: int = 0
    overall_maintainability_index: float = 100.0
    total_technical_debt_minutes: int = 0
    complexity_summary: ComplexityMetrics = field(default_factory=ComplexityMetrics)
    aggregate_complexity: Optional[ComplexityMetrics] = None
    dependency_health: DependencyHealthMetrics = field(default_factory=DependencyHealthMetrics)
    duplications: List[DuplicationBlock] = field(default_factory=list)
    duplication_percentage: float = 0.0
    issues: List[QualityIssue] = field(default_factory=list)
    risk_scores: PredictiveRiskScores = field(default_factory=PredictiveRiskScores)
    gate_result: QualityGateResult = field(default_factory=QualityGateResult)
    historical_patterns_found: List[str] = field(default_factory=list)
    heatmap_data: Dict[str, float] = field(default_factory=dict)
    recommendations: Optional[List[str]] = None
    remediation_suggestions: Optional[List[str]] = None

    def __post_init__(self):
        if self.aggregate_complexity is not None:
            self.complexity_summary = self.aggregate_complexity
        else:
            self.aggregate_complexity = self.complexity_summary
        if self.overall_maintainability_index == 100.0 and self.complexity_summary.maintainability_index != 100.0:
            self.overall_maintainability_index = self.complexity_summary.maintainability_index
        if self.recommendations is not None and not self.gate_result.refactoring_suggestions:
            self.gate_result.refactoring_suggestions = list(self.recommendations)
        elif self.recommendations is None:
            self.recommendations = list(self.gate_result.refactoring_suggestions)
        if self.remediation_suggestions is not None and not self.gate_result.refactoring_suggestions:
            self.gate_result.refactoring_suggestions = list(self.remediation_suggestions)
        elif self.remediation_suggestions is None:
            self.remediation_suggestions = list(self.gate_result.refactoring_suggestions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "analyzed_files_count": self.analyzed_files_count,
            "total_loc": self.total_loc,
            "total_sloc": self.total_sloc,
            "overall_maintainability_index": self.overall_maintainability_index,
            "total_technical_debt_minutes": self.total_technical_debt_minutes,
            "complexity_summary": self.complexity_summary.to_dict(),
            "aggregate_complexity": self.complexity_summary.to_dict(),
            "dependency_health": self.dependency_health.to_dict(),
            "duplications": [d.to_dict() for d in self.duplications],
            "duplication_percentage": self.duplication_percentage,
            "issues": [i.to_dict() for i in self.issues],
            "risk_scores": self.risk_scores.to_dict() if hasattr(self.risk_scores, "to_dict") else self.risk_scores,
            "gate_result": self.gate_result.to_dict() if hasattr(self.gate_result, "to_dict") else self.gate_result,
            "recommendations": self.recommendations or self.gate_result.refactoring_suggestions,
            "remediation_suggestions": self.remediation_suggestions or self.gate_result.refactoring_suggestions,
            "historical_patterns_found": self.historical_patterns_found,
            "heatmap_data": self.heatmap_data,
        }
