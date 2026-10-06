"""
refactoring_engine.py - Autonomous Refactoring & Technical Debt Engine for AutoDev (v1.9)

Analyzes source code repositories for technical debt, architectural code smells, and design
violations before code generation begins. Evaluates whether refactoring should occur BEFORE
implementing new features, computes multi-dimensional refactoring metrics, prioritizes
refactoring candidates using ROI and risk formulas, and synthesizes step-by-step safe refactoring plans.

100% deterministic, offline, and LLM-free.
"""

from __future__ import annotations

import ast
import json
import logging
import math
import os
import re
import shutil
import sys
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

# Ensure project root is available on sys.path
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if TYPE_CHECKING:
    from agents.task_planner_agent import Task

from core.architecture_manager import ArchitectureManager, DesignValidator, ValidationReport
from core.code_indexer import CodeIndexer
from core.repository_analyzer import RepositoryAnalyzer, RepositoryOverview
from core.symbol_graph import Dependency, Symbol, SymbolGraph, SymbolType, Visibility

logger = logging.getLogger("AutoDev.RefactoringEngine")


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class DebtSeverity(str, Enum):
    """Severity levels for technical debt issues."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DebtCategory(str, Enum):
    """Standardized technical debt categories."""
    LONG_METHOD = "Long Method"
    LARGE_CLASS = "Large Class"
    DUPLICATE_CODE = "Duplicate Code"
    DEAD_CODE = "Dead Code"
    MAGIC_NUMBERS = "Magic Numbers"
    GOD_OBJECT = "God Object"
    FEATURE_ENVY = "Feature Envy"
    CIRCULAR_DEPENDENCY = "Circular Dependency"
    HIGH_COUPLING = "High Coupling"
    LOW_COHESION = "Low Cohesion"
    UNUSED_IMPORTS = "Unused Imports"
    UNUSED_VARIABLES = "Unused Variables"
    DEEP_NESTING = "Deep Nesting"
    COMPLEX_CONDITIONALS = "Complex Conditionals"
    HIGH_CYCLOMATIC_COMPLEXITY = "High Cyclomatic Complexity"
    ARCHITECTURE_VIOLATION = "Architecture Violation"
    NAMING_PROBLEMS = "Naming Problems"
    INTERFACE_BLOAT = "Interface Bloat"
    IMPROPER_LAYERING = "Improper Layering"
    TOO_MANY_PARAMETERS = "Too Many Parameters"


# Ignored magic numbers and common constants
COMMON_NUMERIC_CONSTANTS = {
    -1, 0, 1, 2, 3, 4, 5, 8, 10, 16, 24, 32, 60, 64, 100, 128, 200, 201, 204, 256,
    300, 301, 302, 400, 401, 403, 404, 422, 500, 502, 503, 1000, 1024, 86400
}

# Standard single-letter variable names commonly allowed in loops / idioms
ALLOWED_SHORT_NAMES = {"i", "j", "k", "n", "m", "x", "y", "z", "e", "ex", "err", "f", "k", "v", "_", "t", "c", "p", "r", "s", "w", "h", "d"}


# =============================================================================
# DATACLASSES
# =============================================================================

@dataclass
class TechnicalDebtIssue:
    """
    Represents an individual technical debt finding, architectural flaw, or code smell.
    """
    id: str
    title: str
    description: str
    category: str
    severity: str
    confidence: float
    file: str
    symbol: str = ""
    line: Optional[int] = None
    estimated_fix_time: float = 1.0  # in hours
    maintainability_impact: float = 10.0  # score impact e.g. 5 to 25
    risk: str = "LOW"
    recommendation: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.severity, DebtSeverity):
            self.severity = self.severity.value
        elif isinstance(self.severity, str):
            self.severity = self.severity.upper()
        if isinstance(self.risk, str):
            self.risk = self.risk.upper()
        if isinstance(self.category, DebtCategory):
            self.category = self.category.value

    def to_dict(self) -> Dict[str, Any]:
        """Converts issue to dictionary representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TechnicalDebtIssue:
        """Constructs TechnicalDebtIssue from dictionary."""
        return cls(
            id=str(data.get("id", "DEBT-001")),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            category=str(data.get("category", "Code Smell")),
            severity=str(data.get("severity", "LOW")),
            confidence=float(data.get("confidence", 1.0)),
            file=str(data.get("file", "")),
            symbol=str(data.get("symbol", "")),
            line=int(data["line"]) if data.get("line") is not None else None,
            estimated_fix_time=float(data.get("estimated_fix_time", 1.0)),
            maintainability_impact=float(data.get("maintainability_impact", 10.0)),
            risk=str(data.get("risk", "LOW")),
            recommendation=str(data.get("recommendation", "")),
        )


@dataclass
class RefactoringCandidate:
    """
    Represents a consolidated candidate for architectural or structural refactoring.
    """
    id: str
    current_structure: str
    target_structure: str
    reason: str
    affected_symbols: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    risk: str = "LOW"
    dependencies: List[str] = field(default_factory=list)
    estimated_hours: float = 2.0
    priority_score: float = 0.0
    category: str = "Structural Refactoring"
    title: str = ""

    def __post_init__(self) -> None:
        if not self.title:
            self.title = f"Refactor {self.category}: {', '.join(self.affected_symbols[:2]) or self.current_structure}"
        if isinstance(self.risk, str):
            self.risk = self.risk.upper()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RefactoringCandidate:
        return cls(
            id=str(data.get("id", "CAND-01")),
            current_structure=str(data.get("current_structure", "")),
            target_structure=str(data.get("target_structure", "")),
            reason=str(data.get("reason", "")),
            affected_symbols=list(data.get("affected_symbols", [])),
            affected_files=list(data.get("affected_files", [])),
            risk=str(data.get("risk", "LOW")),
            dependencies=list(data.get("dependencies", [])),
            estimated_hours=float(data.get("estimated_hours", 2.0)),
            priority_score=float(data.get("priority_score", 0.0)),
            category=str(data.get("category", "Structural Refactoring")),
            title=str(data.get("title", "")),
        )


@dataclass
class RefactoringAction:
    """
    Represents an atomic step within a RefactoringPlan.
    """
    id: str
    action_type: str
    target_file: str
    target_symbol: str
    description: str
    priority: str = "HIGH"
    estimated_effort_hours: float = 0.5
    risk: str = "LOW"
    order: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.priority, str):
            self.priority = self.priority.upper()
        if isinstance(self.risk, str):
            self.risk = self.risk.upper()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RefactoringAction:
        return cls(
            id=str(data.get("id", "ACT-01")),
            action_type=str(data.get("action_type", "MODIFY")),
            target_file=str(data.get("target_file", "")),
            target_symbol=str(data.get("target_symbol", "")),
            description=str(data.get("description", "")),
            priority=str(data.get("priority", "HIGH")),
            estimated_effort_hours=float(data.get("estimated_effort_hours", 0.5)),
            risk=str(data.get("risk", "LOW")),
            order=int(data.get("order", 1)),
        )


@dataclass
class RefactoringPlan:
    """
    Comprehensive, structured execution plan for remediating technical debt safely.
    """
    priority_ordered_actions: List[RefactoringAction] = field(default_factory=list)
    rollback_strategy: str = "Git soft revert and isolated branch checkout."
    migration_steps: List[str] = field(default_factory=list)
    required_tests: List[str] = field(default_factory=list)
    validation_steps: List[str] = field(default_factory=list)
    candidate: Optional[RefactoringCandidate] = None
    summary: str = ""
    estimated_total_hours: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "priority_ordered_actions": [a.to_dict() for a in self.priority_ordered_actions],
            "rollback_strategy": self.rollback_strategy,
            "migration_steps": self.migration_steps,
            "required_tests": self.required_tests,
            "validation_steps": self.validation_steps,
            "candidate": self.candidate.to_dict() if self.candidate else None,
            "summary": self.summary,
            "estimated_total_hours": self.estimated_total_hours,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RefactoringPlan:
        actions = [RefactoringAction.from_dict(a) for a in data.get("priority_ordered_actions", [])]
        cand_data = data.get("candidate")
        cand = RefactoringCandidate.from_dict(cand_data) if cand_data else None
        return cls(
            priority_ordered_actions=actions,
            rollback_strategy=str(data.get("rollback_strategy", "")),
            migration_steps=list(data.get("migration_steps", [])),
            required_tests=list(data.get("required_tests", [])),
            validation_steps=list(data.get("validation_steps", [])),
            candidate=cand,
            summary=str(data.get("summary", "")),
            estimated_total_hours=float(data.get("estimated_total_hours", 0.0)),
        )


@dataclass
class RefactoringMetrics:
    """
    Comprehensive quantitative software quality & maintainability metrics.
    """
    maintainability_index: float = 85.0  # 0.0 to 100.0 (higher is better)
    cyclomatic_complexity: float = 2.5   # Average complexity per function
    coupling_score: float = 85.0         # 0.0 to 100.0 (higher is lower/better coupling)
    cohesion_score: float = 80.0         # 0.0 to 100.0 (higher is more cohesive)
    duplication_score: float = 95.0      # 0.0 to 100.0 (higher is less duplicate code)
    technical_debt_score: float = 15.0   # 0.0 to 100.0 (lower is less debt)
    architecture_compliance: float = 95.0# 0.0 to 100.0 (% compliance)
    documentation_score: float = 80.0    # 0.0 to 100.0 (% docstrings & typing)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RefactoringMetrics:
        return cls(
            maintainability_index=float(data.get("maintainability_index", 85.0)),
            cyclomatic_complexity=float(data.get("cyclomatic_complexity", 2.5)),
            coupling_score=float(data.get("coupling_score", 85.0)),
            cohesion_score=float(data.get("cohesion_score", 80.0)),
            duplication_score=float(data.get("duplication_score", 95.0)),
            technical_debt_score=float(data.get("technical_debt_score", 15.0)),
            architecture_compliance=float(data.get("architecture_compliance", 95.0)),
            documentation_score=float(data.get("documentation_score", 80.0)),
        )


@dataclass
class RefactoringReport:
    """
    Global project technical debt audit and refactoring decision assessment.
    """
    project_root: str
    issues: List[TechnicalDebtIssue] = field(default_factory=list)
    metrics: RefactoringMetrics = field(default_factory=RefactoringMetrics)
    candidates: List[RefactoringCandidate] = field(default_factory=list)
    plan: Optional[RefactoringPlan] = None
    should_refactor_first: bool = False
    roi_estimate: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    telemetry: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_root": self.project_root,
            "issues": [i.to_dict() for i in self.issues],
            "metrics": self.metrics.to_dict(),
            "candidates": [c.to_dict() for c in self.candidates],
            "plan": self.plan.to_dict() if self.plan else None,
            "should_refactor_first": self.should_refactor_first,
            "roi_estimate": self.roi_estimate,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "telemetry": self.telemetry,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RefactoringReport:
        issues = [TechnicalDebtIssue.from_dict(i) for i in data.get("issues", [])]
        metrics = RefactoringMetrics.from_dict(data.get("metrics", {}))
        candidates = [RefactoringCandidate.from_dict(c) for c in data.get("candidates", [])]
        plan_data = data.get("plan")
        plan = RefactoringPlan.from_dict(plan_data) if plan_data else None
        return cls(
            project_root=str(data.get("project_root", "")),
            issues=issues,
            metrics=metrics,
            candidates=candidates,
            plan=plan,
            should_refactor_first=bool(data.get("should_refactor_first", False)),
            roi_estimate=dict(data.get("roi_estimate", {})),
            summary=str(data.get("summary", "")),
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
            telemetry=dict(data.get("telemetry", {})),
        )

    def to_markdown(self) -> str:
        """Formats the report into human-readable Markdown for reports and logging."""
        lines = [
            "# 🛠️ Technical Debt & Refactoring Assessment",
            f"**Project Root**: `{self.project_root}`  ",
            f"**Timestamp**: `{self.timestamp}`  ",
            f"**Refactor First Recommended**: {'🚨 **YES (Refactor Before Feature Implementation)**' if self.should_refactor_first else '✅ **NO (Safe to Implement Directly)**'}  ",
            "",
            "## 📊 Code Health & Maintainability Metrics",
            "| Metric | Value | Target Benchmark | Status |",
            "| :--- | :---: | :---: | :---: |",
            f"| Maintainability Index | `{self.metrics.maintainability_index:.1f}/100` | `> 75.0` | {'✅ Good' if self.metrics.maintainability_index >= 75 else '⚠️ Needs Attention'} |",
            f"| Avg Cyclomatic Complexity | `{self.metrics.cyclomatic_complexity:.1f}` | `< 5.0` | {'✅ Low' if self.metrics.cyclomatic_complexity <= 5 else '⚠️ High'} |",
            f"| Coupling Score | `{self.metrics.coupling_score:.1f}/100` | `> 70.0` | {'✅ Good' if self.metrics.coupling_score >= 70 else '⚠️ Coupled'} |",
            f"| Cohesion Score | `{self.metrics.cohesion_score:.1f}/100` | `> 70.0` | {'✅ Cohesive' if self.metrics.cohesion_score >= 70 else '⚠️ Low'} |",
            f"| Technical Debt Score | `{self.metrics.technical_debt_score:.1f}/100` | `< 25.0` | {'✅ Low' if self.metrics.technical_debt_score <= 25 else '🚨 High Debt'} |",
            f"| Architecture Compliance | `{self.metrics.architecture_compliance:.1f}%` | `100.0%` | {'✅ Compliant' if self.metrics.architecture_compliance >= 90 else '⚠️ Violations'} |",
            "",
            "## 📋 Identified Technical Debt Issues",
        ]

        if not self.issues:
            lines.append("No technical debt issues or architectural anti-patterns detected.")
        else:
            lines.append("| ID | Severity | Category | File & Symbol | Estimated Fix | Recommendation |")
            lines.append("| :--- | :---: | :--- | :--- | :---: | :--- |")
            for issue in self.issues[:20]:
                sym_str = f"`{issue.symbol}`" if issue.symbol else "`<file>`"
                line_str = f":{issue.line}" if issue.line else ""
                lines.append(f"| `{issue.id}` | **{issue.severity}** | {issue.category} | `{issue.file}{line_str}` ({sym_str}) | {issue.estimated_fix_time}h | {issue.recommendation} |")
            if len(self.issues) > 20:
                lines.append(f"\n*(+ {len(self.issues) - 20} additional low-severity issues omitted for brevity)*")

        if self.candidates:
            lines.append("")
            lines.append("## 🎯 Prioritized Refactoring Candidates")
            for idx, cand in enumerate(self.candidates, 1):
                cand_title = cand.title or cand.current_structure
                lines.append(f"### {idx}. [{cand.id}] {cand_title} (Priority Score: {cand.priority_score:.1f}, Risk: {cand.risk})")
                lines.append(f"- **Current**: {cand.current_structure}")
                lines.append(f"- **Target**: {cand.target_structure}")
                lines.append(f"- **Reason**: {cand.reason}")
                lines.append(f"- **Affected Files**: `{', '.join(cand.affected_files)}`")
                lines.append(f"- **Estimated Effort**: `{cand.estimated_hours:.1f} hours`")

        if self.roi_estimate:
            lines.append("")
            lines.append("## 📈 Return on Investment (ROI) Estimate")
            lines.append(f"- **Development Time Saved**: `{self.roi_estimate.get('development_time_saved_hours', 0):.1f} hours`")
            lines.append(f"- **Bug Reduction Probability**: `~{self.roi_estimate.get('bug_reduction_percent', 0):.1f}%`")
            lines.append(f"- **Future Maintenance Savings**: `{self.roi_estimate.get('future_maintenance_savings_hours', 0):.1f} hours`")
            lines.append(f"- **ROI Ratio**: `{self.roi_estimate.get('roi_ratio', 0):.1f}x` (Overall Benefit: **{self.roi_estimate.get('overall_engineering_benefit', 'MEDIUM')}**)")

        return "\n".join(lines)


# =============================================================================
# REFACTORING ENGINE
# =============================================================================

class RefactoringEngine:
    """
    Autonomous Refactoring & Technical Debt Engine for AutoDev.
    Performs deterministic static analysis, calculates quality & technical debt metrics,
    identifies refactoring candidates, calculates ROI and risk, and generates safe execution plans.
    """

    DEFAULT_TECHNICAL_DEBT_PATH = Path("memory/technical_debt.json")
    DEFAULT_HISTORY_PATH = Path("memory/refactoring_history.json")

    def __init__(
        self,
        symbol_graph: Optional[SymbolGraph] = None,
        code_indexer: Optional[CodeIndexer] = None,
        repository_analyzer: Optional[RepositoryAnalyzer] = None,
        architecture_manager: Optional[ArchitectureManager] = None,
        memory_manager: Optional[Any] = None,
        technical_debt_path: Optional[Union[str, Path]] = None,
        history_path: Optional[Union[str, Path]] = None,
        auto_create_persistence: bool = True,
    ) -> None:
        """
        Initializes the RefactoringEngine with optional existing subsystems and persistence paths.
        """
        if code_indexer is not None:
            self.code_indexer = code_indexer
            self.symbol_graph = symbol_graph or self.code_indexer.graph
        elif symbol_graph is not None:
            self.symbol_graph = symbol_graph
            self.code_indexer = CodeIndexer(auto_load=False)
            self.code_indexer.graph = self.symbol_graph
        else:
            self.code_indexer = CodeIndexer(auto_load=False)
            self.symbol_graph = self.code_indexer.graph
        self.repository_analyzer = repository_analyzer
        self.architecture_manager = architecture_manager
        self.memory_manager = memory_manager

        self.technical_debt_path = Path(technical_debt_path).resolve() if technical_debt_path else self.DEFAULT_TECHNICAL_DEBT_PATH.resolve()
        self.history_path = Path(history_path).resolve() if history_path else self.DEFAULT_HISTORY_PATH.resolve()
        self.auto_create_persistence = auto_create_persistence

        # Telemetry
        self._telemetry: Dict[str, Any] = {
            "technical_debt_trend": [],
            "average_complexity": 0.0,
            "refactoring_history": [],
            "files_improved": 0,
            "maintainability_improvement": 0.0,
            "debt_removed": 0.0,
            "time_saved": 0.0,
            "analysis_count": 0,
            "last_analysis_time_ms": 0.0,
        }

        self._load_history_on_init()

    # -------------------------------------------------------------------------
    # Core Analysis Pipeline
    # -------------------------------------------------------------------------

    def analyze_project(
        self,
        project_root: Union[str, Path],
        task: Optional[Any] = None,
        target_files: Optional[List[str]] = None,
    ) -> RefactoringReport:
        """
        Performs full project static analysis, detects technical debt issues,
        computes quantitative quality metrics, identifies refactoring candidates,
        and generates an actionable RefactoringPlan if necessary.
        """
        start_time = time.perf_counter()
        root_path = Path(project_root).resolve()

        # 1. Update / populate symbol graph if empty or out of date
        if not self.symbol_graph.symbols and root_path.is_dir():
            self.code_indexer.project_root = root_path
            self.code_indexer.index_project()

        # 2. Detect technical debt issues
        issues = self.detect_technical_debt(root_path, target_files=target_files)

        # 3. Compute quantitative metrics
        metrics = self.compute_metrics(root_path, issues=issues)

        # 4. Identify & prioritize refactoring candidates
        candidates = self.identify_candidates(issues, root_path)
        candidates = self.prioritize_refactoring(candidates, issues, task=task)

        # 5. Determine whether to refactor first
        should_refactor_first = self._evaluate_should_refactor_first(issues, candidates, metrics, task=task)

        # 6. Generate execution plan for top candidate if refactoring recommended
        plan: Optional[RefactoringPlan] = None
        if candidates:
            plan = self.generate_plan(candidates[0], issues=issues)

        # 7. Compute ROI estimate
        roi_estimate = self.estimate_roi(issues, candidates, plan=plan)

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

        # Build summary
        summary = (
            f"Technical Debt Audit: {len(issues)} issues detected across project. "
            f"Maintainability Index: {metrics.maintainability_index:.1f}/100. "
            f"Technical Debt Score: {metrics.technical_debt_score:.1f}/100. "
            f"Refactor First: {'YES' if should_refactor_first else 'NO'}."
        )

        telemetry = {
            "analysis_time_ms": duration_ms,
            "total_issues": len(issues),
            "critical_issues": sum(1 for i in issues if i.severity == "CRITICAL"),
            "high_issues": sum(1 for i in issues if i.severity == "HIGH"),
            "candidates_count": len(candidates),
            "should_refactor_first": should_refactor_first,
        }

        report = RefactoringReport(
            project_root=str(root_path),
            issues=issues,
            metrics=metrics,
            candidates=candidates,
            plan=plan,
            should_refactor_first=should_refactor_first,
            roi_estimate=roi_estimate,
            summary=summary,
            timestamp=datetime.now(timezone.utc).isoformat(),
            telemetry=telemetry,
        )

        # Update engine telemetry
        self._telemetry["analysis_count"] += 1
        self._telemetry["last_analysis_time_ms"] = duration_ms
        self._telemetry["average_complexity"] = metrics.cyclomatic_complexity
        self._telemetry["technical_debt_trend"].append({
            "timestamp": report.timestamp,
            "debt_score": metrics.technical_debt_score,
            "maintainability_index": metrics.maintainability_index,
        })

        # Save to technical debt persistence
        self.save_technical_debt(report)

        return report

    # -------------------------------------------------------------------------
    # Technical Debt Detection API
    # -------------------------------------------------------------------------

    def detect_technical_debt(
        self,
        project_root: Union[str, Path],
        target_files: Optional[List[str]] = None,
    ) -> List[TechnicalDebtIssue]:
        """
        Scans Python, JavaScript, TypeScript, and Java files in the project to detect
        deterministic technical debt issues, anti-patterns, and architecture smells.
        """
        root_path = Path(project_root).resolve()
        issues: List[TechnicalDebtIssue] = []
        issue_counter = 1

        # Collect source files if directory or file exists
        source_files: List[Path] = []
        if root_path.exists():
            if root_path.is_file():
                source_files.append(root_path)
            else:
                for ext in ("*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.java"):
                    for p in root_path.rglob(ext):
                        if any(part.startswith(".") or part in ("node_modules", "venv", ".venv", "__pycache__", "build", "dist", ".pytest_cache") for part in p.parts):
                            continue
                        source_files.append(p)

        if target_files:
            target_set = {str(Path(tf).as_posix()).lower() for tf in target_files}
            source_files = [p for p in source_files if p.as_posix().lower() in target_set or p.name.lower() in target_set]

        # 1. AST & Pattern Analysis on Python files
        code_block_hashes: Dict[str, List[Tuple[str, int]]] = defaultdict(list)

        for file_path in source_files:
            rel_file = str(file_path.relative_to(root_path)).replace("\\", "/") if root_path.is_dir() else file_path.name

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception as err:
                logger.warning("Could not read file %s: %s", file_path, err)
                continue

            lines = content.splitlines()
            loc = len(lines)

            # File-level checks for non-Python or Python
            if file_path.suffix == ".py":
                try:
                    tree = ast.parse(content, filename=str(file_path))
                    py_issues = self._analyze_python_ast(tree, rel_file, lines, code_block_hashes, issue_counter)
                    issues.extend(py_issues)
                    issue_counter += len(py_issues)
                except Exception as parse_err:
                    logger.debug("AST parse error in %s: %s", file_path, parse_err)
            else:
                # Multi-language heuristic scanner (Java / JS / TS)
                ml_issues = self._analyze_generic_source(content, rel_file, lines, file_path.suffix, issue_counter)
                issues.extend(ml_issues)
                issue_counter += len(ml_issues)

        # 2. Duplicate code detection from collected block hashes
        for block_hash, occurrences in code_block_hashes.items():
            if len(occurrences) > 1:
                files_repr = ", ".join(f"{f}:{l}" for f, l in occurrences[:3])
                issues.append(
                    TechnicalDebtIssue(
                        id=f"DEBT-{issue_counter:03d}",
                        title="Duplicate Code Block Detected",
                        description=f"Identical code sequence duplicated across {len(occurrences)} locations: {files_repr}.",
                        category=DebtCategory.DUPLICATE_CODE.value,
                        severity=DebtSeverity.HIGH.value if len(occurrences) > 3 else DebtSeverity.MEDIUM.value,
                        confidence=0.95,
                        file=occurrences[0][0],
                        line=occurrences[0][1],
                        estimated_fix_time=1.5,
                        maintainability_impact=15.0,
                        risk="LOW",
                        recommendation="Extract duplicate logic into a shared helper function, base class, or reusable module.",
                    )
                )
                issue_counter += 1

        # 3. Graph-level analysis (Circular Dependencies & Dead Code via SymbolGraph & RepositoryAnalyzer)
        graph_issues = self._detect_graph_level_issues(root_path, issue_counter)
        issues.extend(graph_issues)
        issue_counter += len(graph_issues)

        # 4. Architecture & Layer Violations via ArchitectureManager / RepositoryAnalyzer
        arch_issues = self._detect_architecture_violations(root_path, issue_counter)
        issues.extend(arch_issues)

        return issues

    def _analyze_python_ast(
        self,
        tree: ast.AST,
        rel_file: str,
        lines: List[str],
        code_block_hashes: Dict[str, List[Tuple[str, int]]],
        start_counter: int,
    ) -> List[TechnicalDebtIssue]:
        """Analyzes a Python AST tree for code smells and technical debt."""
        issues: List[TechnicalDebtIssue] = []
        counter = start_counter

        imported_names: Set[str] = set()
        imported_nodes: Dict[str, ast.AST] = {}
        used_names: Set[str] = set()

        for node in ast.walk(tree):
            # Imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name_to_check = alias.asname or alias.name.split(".")[0]
                    imported_names.add(name_to_check)
                    imported_nodes[name_to_check] = node
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name_to_check = alias.asname or alias.name
                    imported_names.add(name_to_check)
                    imported_nodes[name_to_check] = node
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_names.add(node.id)

            # Class Analysis
            if isinstance(node, ast.ClassDef):
                class_lines = (node.end_lineno or node.lineno) - node.lineno + 1
                methods = [m for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]

                # Large Class
                if class_lines > 500 or len(methods) > 20:
                    issues.append(
                        TechnicalDebtIssue(
                            id=f"DEBT-{counter:03d}",
                            title=f"Large Class ({node.name})",
                            description=f"Class '{node.name}' contains {class_lines} lines and {len(methods)} methods, violating single responsibility.",
                            category=DebtCategory.LARGE_CLASS.value,
                            severity=DebtSeverity.HIGH.value if class_lines > 800 else DebtSeverity.MEDIUM.value,
                            confidence=0.98,
                            file=rel_file,
                            symbol=node.name,
                            line=node.lineno,
                            estimated_fix_time=3.0,
                            maintainability_impact=20.0,
                            risk="MEDIUM",
                            recommendation="Split class into smaller cohesive classes or delegate responsibilities using composition.",
                        )
                    )
                    counter += 1

                # God Object Smell
                if (class_lines >= 300 or len(lines) >= 300) and len(methods) >= 15:
                    issues.append(
                        TechnicalDebtIssue(
                            id=f"DEBT-{counter:03d}",
                            title=f"God Object Anti-Pattern ({node.name})",
                            description=f"Class '{node.name}' orchestrates excessive disparate responsibilities with {len(methods)} methods.",
                            category=DebtCategory.GOD_OBJECT.value,
                            severity=DebtSeverity.CRITICAL.value,
                            confidence=0.92,
                            file=rel_file,
                            symbol=node.name,
                            line=node.lineno,
                            estimated_fix_time=4.5,
                            maintainability_impact=25.0,
                            risk="HIGH",
                            recommendation="Refactor God Object into focused domain services and repository abstractions.",
                        )
                    )
                    counter += 1

                # Low Cohesion (LCOM heuristic based on attribute usage across methods)
                if len(methods) >= 4:
                    lcom_score = self._compute_class_lcom(node)
                    if lcom_score > 0.75:
                        issues.append(
                            TechnicalDebtIssue(
                                id=f"DEBT-{counter:03d}",
                                title=f"Low Class Cohesion ({node.name})",
                                description=f"Class '{node.name}' methods share few common instance variables (LCOM metric: {lcom_score:.2f}).",
                                category=DebtCategory.LOW_COHESION.value,
                                severity=DebtSeverity.MEDIUM.value,
                                confidence=0.85,
                                file=rel_file,
                                symbol=node.name,
                                line=node.lineno,
                                estimated_fix_time=2.0,
                                maintainability_impact=15.0,
                                risk="LOW",
                                recommendation="Group independent methods and instance fields into separate cohesive classes.",
                            )
                        )
                        counter += 1

                # Interface Bloat (for ABC or interface-like classes)
                is_abc = any(
                    (isinstance(b, ast.Name) and "ABC" in b.id) or
                    (isinstance(b, ast.Attribute) and "ABC" in b.attr)
                    for b in node.bases
                )
                if is_abc and len(methods) > 10:
                    issues.append(
                        TechnicalDebtIssue(
                            id=f"DEBT-{counter:03d}",
                            title=f"Interface Bloat ({node.name})",
                            description=f"Abstract interface '{node.name}' exposes {len(methods)} methods, violating Interface Segregation Principle.",
                            category=DebtCategory.INTERFACE_BLOAT.value,
                            severity=DebtSeverity.HIGH.value,
                            confidence=0.90,
                            file=rel_file,
                            symbol=node.name,
                            line=node.lineno,
                            estimated_fix_time=2.5,
                            maintainability_impact=18.0,
                            risk="MEDIUM",
                            recommendation="Apply Interface Segregation Principle (ISP) by breaking into smaller role-specific interfaces.",
                        )
                    )
                    counter += 1

            # Function / Method Analysis
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_lines = (node.end_lineno or node.lineno) - node.lineno + 1
                params = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]

                # Long Method
                if fn_lines > 50:
                    issues.append(
                        TechnicalDebtIssue(
                            id=f"DEBT-{counter:03d}",
                            title=f"Long Method ({node.name})",
                            description=f"Function '{node.name}' spans {fn_lines} lines (>50 LOC limit).",
                            category=DebtCategory.LONG_METHOD.value,
                            severity=DebtSeverity.HIGH.value if fn_lines > 100 else DebtSeverity.MEDIUM.value,
                            confidence=0.98,
                            file=rel_file,
                            symbol=node.name,
                            line=node.lineno,
                            estimated_fix_time=1.5,
                            maintainability_impact=15.0,
                            risk="LOW",
                            recommendation="Extract sub-methods and helper functions to decompose routine into atomic actions.",
                        )
                    )
                    counter += 1

                # Too Many Parameters
                if len(params) > 7:
                    issues.append(
                        TechnicalDebtIssue(
                            id=f"DEBT-{counter:03d}",
                            title=f"Too Many Parameters ({node.name})",
                            description=f"Function '{node.name}' accepts {len(params)} parameters (>7 limit).",
                            category=DebtCategory.TOO_MANY_PARAMETERS.value,
                            severity=DebtSeverity.HIGH.value if len(params) > 10 else DebtSeverity.MEDIUM.value,
                            confidence=0.95,
                            file=rel_file,
                            symbol=node.name,
                            line=node.lineno,
                            estimated_fix_time=1.0,
                            maintainability_impact=12.0,
                            risk="LOW",
                            recommendation="Introduce a Parameter Object, typed dataclass, or configuration dictionary.",
                        )
                    )
                    counter += 1

                # High Cyclomatic Complexity
                cc = self._calculate_ast_cyclomatic_complexity(node)
                if cc >= 10:
                    issues.append(
                        TechnicalDebtIssue(
                            id=f"DEBT-{counter:03d}",
                            title=f"High Cyclomatic Complexity ({node.name})",
                            description=f"Function '{node.name}' has cyclomatic complexity of {cc} (threshold >=10).",
                            category=DebtCategory.HIGH_CYCLOMATIC_COMPLEXITY.value,
                            severity=DebtSeverity.CRITICAL.value if cc >= 20 else DebtSeverity.HIGH.value,
                            confidence=0.95,
                            file=rel_file,
                            symbol=node.name,
                            line=node.lineno,
                            estimated_fix_time=2.0,
                            maintainability_impact=20.0,
                            risk="MEDIUM",
                            recommendation="Simplify branching logic using guard clauses, polymorphism, or table-driven dispatch.",
                        )
                    )
                    counter += 1

                # Deep Nesting
                depth = self._calculate_ast_max_nesting_depth(node)
                if depth >= 5:
                    issues.append(
                        TechnicalDebtIssue(
                            id=f"DEBT-{counter:03d}",
                            title=f"Deep Nesting ({node.name})",
                            description=f"Function '{node.name}' reaches nesting depth of {depth} levels (threshold >=5).",
                            category=DebtCategory.DEEP_NESTING.value,
                            severity=DebtSeverity.HIGH.value if depth >= 7 else DebtSeverity.MEDIUM.value,
                            confidence=0.95,
                            file=rel_file,
                            symbol=node.name,
                            line=node.lineno,
                            estimated_fix_time=1.0,
                            maintainability_impact=14.0,
                            risk="LOW",
                            recommendation="Flatten indentation using early returns, guard clauses, and extracted helper subroutines.",
                        )
                    )
                    counter += 1

                # Complex Conditionals
                for sub in ast.walk(node):
                    if isinstance(sub, ast.BoolOp) and len(sub.values) >= 4:
                        issues.append(
                            TechnicalDebtIssue(
                                id=f"DEBT-{counter:03d}",
                                title=f"Complex Conditional in '{node.name}'",
                                description=f"Boolean expression in '{node.name}' contains {len(sub.values)} chained logical conditions.",
                                category=DebtCategory.COMPLEX_CONDITIONALS.value,
                                severity=DebtSeverity.MEDIUM.value,
                                confidence=0.90,
                                file=rel_file,
                                symbol=node.name,
                                line=getattr(sub, "lineno", node.lineno),
                                estimated_fix_time=0.5,
                                maintainability_impact=10.0,
                                risk="LOW",
                                recommendation="Extract complex boolean logic into descriptive predicate helper functions.",
                            )
                        )
                        counter += 1
                        break

                # Unused Local Variables
                assigned_vars: Dict[str, int] = {}
                read_vars: Set[str] = set()
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Name):
                        if isinstance(sub.ctx, ast.Store):
                            if not sub.id.startswith("_") and sub.id not in params:
                                assigned_vars[sub.id] = sub.lineno
                        elif isinstance(sub.ctx, ast.Load):
                            read_vars.add(sub.id)

                for var_name, var_line in assigned_vars.items():
                    if var_name not in read_vars:
                        issues.append(
                            TechnicalDebtIssue(
                                id=f"DEBT-{counter:03d}",
                                title=f"Unused Local Variable '{var_name}'",
                                description=f"Variable '{var_name}' in function '{node.name}' is assigned but never read.",
                                category=DebtCategory.UNUSED_VARIABLES.value,
                                severity=DebtSeverity.LOW.value,
                                confidence=0.90,
                                file=rel_file,
                                symbol=node.name,
                                line=var_line,
                                estimated_fix_time=0.25,
                                maintainability_impact=5.0,
                                risk="LOW",
                                recommendation=f"Remove unused variable '{var_name}' or prefix with an underscore.",
                            )
                        )
                        counter += 1

            # Magic Numbers
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                val = node.value
                if val not in COMMON_NUMERIC_CONSTANTS and not (0 <= val <= 10):
                    issues.append(
                        TechnicalDebtIssue(
                            id=f"DEBT-{counter:03d}",
                            title=f"Magic Number ({val})",
                            description=f"Unnamed numeric literal {val} used inline.",
                            category=DebtCategory.MAGIC_NUMBERS.value,
                            severity=DebtSeverity.LOW.value,
                            confidence=0.85,
                            file=rel_file,
                            line=getattr(node, "lineno", None),
                            estimated_fix_time=0.25,
                            maintainability_impact=5.0,
                            risk="LOW",
                            recommendation=f"Replace literal {val} with a named constant or Enum definition.",
                        )
                    )
                    counter += 1

        # Unused Imports Check
        unused_imports = imported_names - used_names
        for imp in unused_imports:
            if imp in ("__all__", "annotations", "TYPE_CHECKING", "pytest"):
                continue
            imp_node = imported_nodes.get(imp)
            issues.append(
                TechnicalDebtIssue(
                    id=f"DEBT-{counter:03d}",
                    title=f"Unused Import '{imp}'",
                    description=f"Module imports '{imp}' but never references it in the file.",
                    category=DebtCategory.UNUSED_IMPORTS.value,
                    severity=DebtSeverity.LOW.value,
                    confidence=0.90,
                    file=rel_file,
                    line=getattr(imp_node, "lineno", None),
                    estimated_fix_time=0.25,
                    maintainability_impact=5.0,
                    risk="LOW",
                    recommendation=f"Remove unused import statement '{imp}' to clean up namespace.",
                )
            )
            counter += 1

        # Duplicate Code Block Indexing (hashes of 5-line normalized chunks)
        for i in range(len(lines) - 5):
            chunk = [l.strip() for l in lines[i:i+5] if l.strip() and not l.strip().startswith(("#", "//", "/*", "*"))]
            if len(chunk) >= 4:
                norm_text = "".join(re.sub(r"\s+", "", l) for l in chunk)
                if len(norm_text) > 40:
                    code_block_hashes[norm_text].append((rel_file, i + 1))

        return issues

    def _analyze_generic_source(
        self,
        content: str,
        rel_file: str,
        lines: List[str],
        ext: str,
        start_counter: int,
    ) -> List[TechnicalDebtIssue]:
        """Performs structural scanning for Java / JavaScript / TypeScript sources."""
        issues: List[TechnicalDebtIssue] = []
        counter = start_counter

        # Heuristic line count
        if len(lines) > 500:
            issues.append(
                TechnicalDebtIssue(
                    id=f"DEBT-{counter:03d}",
                    title=f"Large Source File ({rel_file})",
                    description=f"File contains {len(lines)} lines of code (>500 limit).",
                    category=DebtCategory.LARGE_CLASS.value,
                    severity=DebtSeverity.HIGH.value if len(lines) > 800 else DebtSeverity.MEDIUM.value,
                    confidence=0.90,
                    file=rel_file,
                    line=1,
                    estimated_fix_time=3.0,
                    maintainability_impact=20.0,
                    risk="MEDIUM",
                    recommendation="Decompose large file into modular components and isolated service classes.",
                )
            )
            counter += 1

        # Heuristic method scanning for Java / JS / TS
        brace_stack = 0
        for idx, line in enumerate(lines, 1):
            s_line = line.strip()

            # Check magic numbers
            numbers = re.findall(r"\b\d+\b", s_line)
            for n_str in numbers:
                val = int(n_str)
                if val not in COMMON_NUMERIC_CONSTANTS and not (0 <= val <= 10):
                    if not any(k in s_line.upper() for k in ("CONST", "STATIC", "FINAL", "PORT", "TIMEOUT", "STATUS")):
                        issues.append(
                            TechnicalDebtIssue(
                                id=f"DEBT-{counter:03d}",
                                title=f"Magic Number ({val})",
                                description=f"Unnamed literal {val} found in {rel_file}:{idx}.",
                                category=DebtCategory.MAGIC_NUMBERS.value,
                                severity=DebtSeverity.LOW.value,
                                confidence=0.80,
                                file=rel_file,
                                line=idx,
                                estimated_fix_time=0.25,
                                maintainability_impact=5.0,
                                risk="LOW",
                                recommendation=f"Replace literal {val} with named constant.",
                            )
                        )
                        counter += 1
                        break

            # Nesting depth via braces
            open_b = line.count("{")
            close_b = line.count("}")
            brace_stack += open_b - close_b
            if brace_stack >= 6:
                issues.append(
                    TechnicalDebtIssue(
                        id=f"DEBT-{counter:03d}",
                        title=f"Deep Nesting ({rel_file})",
                        description=f"Nesting level reaches {brace_stack} at line {idx}.",
                        category=DebtCategory.DEEP_NESTING.value,
                        severity=DebtSeverity.MEDIUM.value,
                        confidence=0.85,
                        file=rel_file,
                        line=idx,
                        estimated_fix_time=1.0,
                        maintainability_impact=12.0,
                        risk="LOW",
                        recommendation="Flatten nested blocks using early returns and guard clauses.",
                    )
                )
                counter += 1

        return issues

    def _detect_graph_level_issues(self, project_root: Path, start_counter: int) -> List[TechnicalDebtIssue]:
        """Detects circular dependencies and dead code using the SymbolGraph & RepositoryAnalyzer."""
        issues: List[TechnicalDebtIssue] = []
        counter = start_counter

        # 1. Circular Dependencies
        cycles: List[List[str]] = []
        if self.repository_analyzer:
            try:
                repo_cycles = self.repository_analyzer.detect_circular_dependencies()
                for c in repo_cycles:
                    cycles.append(c.cycle_path if hasattr(c, "cycle_path") else list(c))
            except Exception as err:
                logger.debug("RepositoryAnalyzer circular dependency check error: %s", err)

        if not cycles and hasattr(self.symbol_graph, "find_cycles"):
            try:
                cycles = self.symbol_graph.find_cycles()
            except Exception:
                pass

        if not cycles:
            cycles = self._find_cycles_in_symbol_graph()

        for cycle in cycles:
            cycle_str = " -> ".join(cycle)
            first_mod = cycle[0] if cycle else "codebase"
            issues.append(
                TechnicalDebtIssue(
                    id=f"DEBT-{counter:03d}",
                    title="Circular Dependency Cycle Detected",
                    description=f"Circular dependency detected between modules: {cycle_str}.",
                    category=DebtCategory.CIRCULAR_DEPENDENCY.value,
                    severity=DebtSeverity.CRITICAL.value,
                    confidence=1.0,
                    file=first_mod,
                    estimated_fix_time=3.5,
                    maintainability_impact=25.0,
                    risk="HIGH",
                    recommendation="Decouple dependency cycle using Interface Segregation, Dependency Injection, or shared DTO types.",
                )
            )
            counter += 1

        # 2. Dead Code Detection
        dead_symbols: List[Symbol] = []
        if self.repository_analyzer and hasattr(self.repository_analyzer, "find_dead_code_candidates"):
            try:
                dead_names = self.repository_analyzer.find_dead_code_candidates()
                for sym_name in dead_names:
                    sym = self.symbol_graph.get_symbol(sym_name) if hasattr(self.symbol_graph, "get_symbol") else None
                    if sym:
                        dead_symbols.append(sym)
            except Exception:
                pass

        if not dead_symbols:
            for sym in self.symbol_graph.symbols.values():
                s_file = getattr(sym, "file_path", None) or getattr(sym, "file", "")
                if sym.name.startswith("__") or "test" in s_file.lower() or sym.name.lower() in ("main", "app", "cli", "run"):
                    continue
                incoming_refs = getattr(self.symbol_graph, "get_incoming_references", None)
                incoming = incoming_refs(sym.name) if incoming_refs else []
                if not incoming and not sym.called_by:
                    has_ref = False
                    for other in self.symbol_graph.symbols.values():
                        if other.id == sym.id:
                            continue
                        if sym.name in other.calls or sym.name in other.references:
                            has_ref = True
                            break
                        for d in other.dependencies:
                            tgt = getattr(d, "target", "") or getattr(d, "target_file", "")
                            if sym.name in (tgt, getattr(d, "imported_symbols", [])):
                                has_ref = True
                                break
                    if not has_ref and sym.symbol_type in (SymbolType.FUNCTION, SymbolType.CLASS, SymbolType.METHOD):
                        dead_symbols.append(sym)

        for sym in dead_symbols[:15]:
            s_file = getattr(sym, "file_path", None) or getattr(sym, "file", "unknown.py")
            s_line = getattr(sym, "line_start", None) or getattr(sym, "line", 1)
            issues.append(
                TechnicalDebtIssue(
                    id=f"DEBT-{counter:03d}",
                    title=f"Dead Code Candidate ('{sym.name}')",
                    description=f"Symbol '{sym.name}' has 0 incoming references across the codebase.",
                    category=DebtCategory.DEAD_CODE.value,
                    severity=DebtSeverity.MEDIUM.value,
                    confidence=0.85,
                    file=s_file,
                    symbol=sym.name,
                    line=s_line,
                    estimated_fix_time=0.5,
                    maintainability_impact=8.0,
                    risk="LOW",
                    recommendation=f"Safely delete unused symbol '{sym.name}' or export explicitly in public API.",
                )
            )
            counter += 1

        return issues

    def _detect_architecture_violations(self, project_root: Path, start_counter: int) -> List[TechnicalDebtIssue]:
        """Detects layer and architectural rule violations via ArchitectureManager and heuristics."""
        issues: List[TechnicalDebtIssue] = []
        counter = start_counter

        # 1. ADR & DesignValidator Violations
        if self.architecture_manager:
            try:
                validator = DesignValidator(self.architecture_manager)
                val_report = validator.validate(project_root)
                for viol in val_report.violations:
                    issues.append(
                        TechnicalDebtIssue(
                            id=f"DEBT-{counter:03d}",
                            title=f"Architecture ADR Violation: {viol.rule_id}",
                            description=viol.description,
                            category=DebtCategory.ARCHITECTURE_VIOLATION.value,
                            severity=viol.severity.value if hasattr(viol.severity, "value") else str(viol.severity),
                            confidence=0.95,
                            file=viol.file,
                            symbol=viol.symbol or "",
                            line=viol.line,
                            estimated_fix_time=2.0,
                            maintainability_impact=20.0,
                            risk="HIGH" if viol.severity in ("CRITICAL", "HIGH") else "MEDIUM",
                            recommendation=viol.recommendation or "Ensure code changes adhere to recorded Architecture Decision Records.",
                        )
                    )
                    counter += 1
            except Exception as err:
                logger.debug("ArchitectureManager validation check error: %s", err)

        # 2. Improper Layering (e.g. data layer importing presentation / API directly)
        for sym in self.symbol_graph.symbols.values():
            s_file = getattr(sym, "file_path", None) or getattr(sym, "file", "")
            f_lower = s_file.lower()
            if any(db_kw in f_lower for db_kw in ("db/", "database/", "repository/", "dao/", "models/")):
                for dep in sym.dependencies:
                    target_name = getattr(dep, "target", "") or getattr(dep, "target_file", "")
                    target_sym = (
                        self.symbol_graph.get_symbol(target_name)
                        if hasattr(self.symbol_graph, "get_symbol") else None
                    ) or next((s for s in self.symbol_graph.symbols.values() if s.name == target_name or s.id == target_name or s.file == target_name or getattr(s, "file_path", "") == target_name), None)
                    t_lower = (getattr(target_sym, "file_path", None) or getattr(target_sym, "file", target_name) if target_sym else target_name).lower()
                    if any(ui_kw in t_lower for ui_kw in ("api/", "controllers/", "routes/", "views/", "presentation/")):
                        issues.append(
                            TechnicalDebtIssue(
                                id=f"DEBT-{counter:03d}",
                                title="Improper Layering: Data Layer Depends on Presentation Layer",
                                description=f"Database module '{s_file}' directly imports higher layer '{t_lower}'.",
                                category=DebtCategory.IMPROPER_LAYERING.value,
                                severity=DebtSeverity.CRITICAL.value,
                                confidence=0.98,
                                file=s_file,
                                symbol=sym.name,
                                line=getattr(sym, "line_start", None) or getattr(sym, "line", 1),
                                estimated_fix_time=3.0,
                                maintainability_impact=25.0,
                                risk="HIGH",
                                recommendation="Invert dependency flow using Dependency Injection or Event Bus to maintain Clean Architecture hierarchy.",
                            )
                        )
                        counter += 1

        return issues

    def _find_cycles_in_symbol_graph(self) -> List[List[str]]:
        """Simple DFS cycle detection on symbol dependencies."""
        adj: Dict[str, Set[str]] = defaultdict(set)
        for sym in self.symbol_graph.symbols.values():
            mod_a = getattr(sym, "file_path", None) or getattr(sym, "file", None) or sym.name
            for dep in sym.dependencies:
                target_name = getattr(dep, "target", "") or getattr(dep, "target_file", "")
                target_sym = (
                    self.symbol_graph.get_symbol(target_name)
                    if hasattr(self.symbol_graph, "get_symbol") else None
                ) or next((s for s in self.symbol_graph.symbols.values() if s.name == target_name or s.id == target_name or s.file == target_name or getattr(s, "file_path", "") == target_name), None)
                mod_b = (getattr(target_sym, "file_path", None) or getattr(target_sym, "file", None) or getattr(target_sym, "name", target_name)) if target_sym else target_name
                if mod_a and mod_b and mod_a != mod_b:
                    adj[mod_a].add(mod_b)

        # Also incorporate file_dependency_graph
        if hasattr(self.symbol_graph, "file_dependency_graph"):
            for src_f, tgts in self.symbol_graph.file_dependency_graph.items():
                for tgt_f in tgts:
                    if src_f != tgt_f:
                        adj[src_f].add(tgt_f)

        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        cycles: List[List[str]] = []

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adj.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, list(path))
                elif neighbor in rec_stack:
                    idx = path.index(neighbor) if neighbor in path else 0
                    cycle = path[idx:] + [neighbor]
                    if len(cycle) >= 2 and cycle not in cycles:
                        cycles.append(cycle)

            rec_stack.remove(node)

        for node in list(adj.keys()):
            if node not in visited:
                dfs(node, [])

        return cycles

    # -------------------------------------------------------------------------
    # Metrics Computation API
    # -------------------------------------------------------------------------

    def compute_metrics(
        self,
        project_root: Union[str, Path],
        issues: Optional[List[TechnicalDebtIssue]] = None,
    ) -> RefactoringMetrics:
        """
        Computes 8 quantitative software health, technical debt, and maintainability metrics.
        """
        root_path = Path(project_root).resolve()
        detected_issues = issues if issues is not None else self.detect_technical_debt(root_path)

        total_files = 0
        total_loc = 0
        total_cc = 0
        fn_count = 0
        total_comments = 0
        docstring_count = 0
        public_symbol_count = 0

        if root_path.exists():
            py_files = [p for p in root_path.rglob("*.py") if not any(p.startswith(".") for p in p.parts)] if root_path.is_dir() else ([root_path] if root_path.suffix == ".py" else [])
            total_files = len(py_files)

            for pf in py_files:
                try:
                    content = pf.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()
                    total_loc += len(lines)
                    total_comments += sum(1 for l in lines if l.strip().startswith("#"))

                    tree = ast.parse(content, filename=str(pf))
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            fn_count += 1
                            total_cc += self._calculate_ast_cyclomatic_complexity(node)
                            if not node.name.startswith("_"):
                                public_symbol_count += 1
                                if ast.get_docstring(node):
                                    docstring_count += 1
                        elif isinstance(node, ast.ClassDef):
                            if not node.name.startswith("_"):
                                public_symbol_count += 1
                                if ast.get_docstring(node):
                                    docstring_count += 1
                except Exception:
                    pass

        avg_loc = (total_loc / max(1, total_files)) if total_files > 0 else 50.0
        avg_cc = (total_cc / max(1, fn_count)) if fn_count > 0 else 2.5

        # 1. Maintainability Index Formula (SEI Standard):
        halstead_vol = max(10.0, avg_loc * 8.0)
        raw_mi = 171.0 - (5.2 * math.log(halstead_vol)) - (0.23 * avg_cc) - (16.2 * math.log(max(1.0, avg_loc)))
        norm_mi = max(0.0, min(100.0, (raw_mi * 100.0) / 171.0))

        # 2. Technical Debt Score
        severity_penalties = {
            "CRITICAL": 30.0,
            "HIGH": 20.0,
            "MEDIUM": 10.0,
            "LOW": 5.0,
        }
        total_penalty = sum(severity_penalties.get(i.severity, 10.0) for i in detected_issues)
        kloc = max(0.1, total_loc / 1000.0)
        debt_score = max(0.0, min(100.0, (total_penalty / (kloc * 15.0 + 1.0))))

        # 3. Coupling Score
        avg_coupling = 3.0
        if self.symbol_graph and self.symbol_graph.symbols:
            couplings = [len(s.dependencies) for s in self.symbol_graph.symbols.values()]
            avg_coupling = sum(couplings) / max(1, len(couplings))
        coupling_score = max(0.0, min(100.0, 100.0 - (avg_coupling * 6.0)))

        # 4. Cohesion Score
        cohesion_score = max(40.0, min(100.0, 90.0 - sum(5.0 for i in detected_issues if i.category in (DebtCategory.LOW_COHESION.value, DebtCategory.GOD_OBJECT.value, DebtCategory.LARGE_CLASS.value))))

        # 5. Duplication Score
        dup_issues = sum(1 for i in detected_issues if i.category == DebtCategory.DUPLICATE_CODE.value)
        duplication_score = max(0.0, min(100.0, 100.0 - (dup_issues * 12.0)))

        # 6. Architecture Compliance
        arch_issues = sum(1 for i in detected_issues if i.category in (DebtCategory.ARCHITECTURE_VIOLATION.value, DebtCategory.CIRCULAR_DEPENDENCY.value, DebtCategory.IMPROPER_LAYERING.value))
        architecture_compliance = max(0.0, min(100.0, 100.0 - (arch_issues * 15.0)))

        # 7. Documentation Score
        documentation_score = ((docstring_count / max(1, public_symbol_count)) * 100.0) if public_symbol_count > 0 else 85.0
        documentation_score = max(0.0, min(100.0, documentation_score))

        return RefactoringMetrics(
            maintainability_index=round(norm_mi, 2),
            cyclomatic_complexity=round(avg_cc, 2),
            coupling_score=round(coupling_score, 2),
            cohesion_score=round(cohesion_score, 2),
            duplication_score=round(duplication_score, 2),
            technical_debt_score=round(debt_score, 2),
            architecture_compliance=round(architecture_compliance, 2),
            documentation_score=round(documentation_score, 2),
        )

    # -------------------------------------------------------------------------
    # Candidate Identification & Prioritization API
    # -------------------------------------------------------------------------

    def identify_candidates(
        self,
        issues: List[TechnicalDebtIssue],
        project_root: Optional[Union[str, Path]] = None,
    ) -> List[RefactoringCandidate]:
        """
        Groups related technical debt issues into cohesive, actionable RefactoringCandidate structures.
        """
        candidates: List[RefactoringCandidate] = []
        cand_counter = 1

        grouped_by_file_sym: Dict[Tuple[str, str], List[TechnicalDebtIssue]] = defaultdict(list)
        for issue in issues:
            grouped_by_file_sym[(issue.file, issue.symbol)].append(issue)

        for (file_path, symbol_name), issue_group in grouped_by_file_sym.items():
            primary = issue_group[0]
            categories = {i.category for i in issue_group}
            severities = [i.severity for i in issue_group]

            max_risk = "LOW"
            if "CRITICAL" in severities:
                max_risk = "CRITICAL"
            elif "HIGH" in severities:
                max_risk = "HIGH"
            elif "MEDIUM" in severities:
                max_risk = "MEDIUM"

            total_hours = sum(i.estimated_fix_time for i in issue_group)
            affected_syms = [s for s in [symbol_name] if s]
            affected_files = [file_path]

            current_struct = f"Module '{file_path}'" + (f" with symbol '{symbol_name}'" if symbol_name else "") + f" exhibiting {', '.join(categories)}"
            target_struct = f"Refactored modular structure in '{file_path}' adhering to SOLID principles and clean decoupling."
            reason = f"Remediates {len(issue_group)} debt issues ({', '.join(categories)}) to improve maintainability and eliminate engineering risk."

            candidates.append(
                RefactoringCandidate(
                    id=f"CAND-{cand_counter:02d}",
                    current_structure=current_struct,
                    target_structure=target_struct,
                    reason=reason,
                    affected_symbols=affected_syms,
                    affected_files=affected_files,
                    risk=max_risk,
                    dependencies=[],
                    estimated_hours=round(total_hours, 1),
                    priority_score=0.0,
                    category=primary.category,
                    title=f"Refactor {primary.category} in {Path(file_path).name}" + (f" ({symbol_name})" if symbol_name else ""),
                )
            )
            cand_counter += 1

        return candidates

    def prioritize_refactoring(
        self,
        candidates: List[RefactoringCandidate],
        issues: List[TechnicalDebtIssue],
        task: Optional[Any] = None,
    ) -> List[RefactoringCandidate]:
        """
        Calculates deterministic priority scores for refactoring candidates using the formula:
        Priority Score = Severity + Technical Debt + Business Impact + Architecture Risk + Maintainability Gain - Refactoring Cost
        """
        task_files: Set[str] = set()
        if task:
            task_files = {
                str(Path(f).as_posix()).lower()
                for f in getattr(task, "estimated_files", []) if isinstance(f, str)
            }

        severity_map = {"CRITICAL": 30.0, "HIGH": 20.0, "MEDIUM": 10.0, "LOW": 5.0}

        for cand in candidates:
            sev_score = severity_map.get(cand.risk, 10.0)

            related_issues = [i for i in issues if any(af in i.file for af in cand.affected_files)]
            tech_debt_score = sum(i.maintainability_impact for i in related_issues) / max(1, len(related_issues)) if related_issues else 10.0

            cand_files_norm = {str(Path(f).as_posix()).lower() for f in cand.affected_files}
            is_task_target = bool(task_files & cand_files_norm) or any(any(tf in cf for tf in task_files) for cf in cand_files_norm)
            business_impact = 25.0 if is_task_target else 10.0

            arch_risk = 25.0 if cand.risk in ("CRITICAL", "HIGH") else 10.0
            maint_gain = 20.0 if len(related_issues) >= 3 else 12.0
            cost = cand.estimated_hours * 2.0

            priority_score = round(sev_score + tech_debt_score + business_impact + arch_risk + maint_gain - cost, 2)
            cand.priority_score = max(0.0, priority_score)

        candidates.sort(
            key=lambda c: (
                c.priority_score,
                -severity_map.get(c.risk, 0),
                -c.estimated_hours,
            ),
            reverse=True,
        )
        return candidates

    # -------------------------------------------------------------------------
    # Plan Generation API
    # -------------------------------------------------------------------------

    def generate_plan(
        self,
        candidate: RefactoringCandidate,
        issues: Optional[List[TechnicalDebtIssue]] = None,
    ) -> RefactoringPlan:
        """
        Synthesizes a deterministic, safe, step-by-step RefactoringPlan for a candidate.
        """
        actions: List[RefactoringAction] = []
        action_order = 1

        rel_issues = [i for i in (issues or []) if any(af in i.file for af in candidate.affected_files)]

        if not rel_issues:
            actions.append(
                RefactoringAction(
                    id=f"ACT-{action_order:02d}",
                    action_type="RESTRUCTURE_MODULE",
                    target_file=candidate.affected_files[0] if candidate.affected_files else "src/module.py",
                    target_symbol=candidate.affected_symbols[0] if candidate.affected_symbols else "",
                    description=f"Restructure {candidate.current_structure} to {candidate.target_structure}.",
                    priority="HIGH",
                    estimated_effort_hours=candidate.estimated_hours,
                    risk=candidate.risk,
                    order=action_order,
                )
            )
            action_order += 1
        else:
            for issue in rel_issues:
                action_type = "EXTRACT_SUBROUTINE"
                if issue.category == DebtCategory.LONG_METHOD.value:
                    action_type = "EXTRACT_METHOD"
                elif issue.category in (DebtCategory.LARGE_CLASS.value, DebtCategory.GOD_OBJECT.value):
                    action_type = "SPLIT_CLASS"
                elif issue.category == DebtCategory.CIRCULAR_DEPENDENCY.value:
                    action_type = "BREAK_CYCLE_WITH_INTERFACE"
                elif issue.category == DebtCategory.DUPLICATE_CODE.value:
                    action_type = "EXTRACT_SHARED_HELPER"
                elif issue.category == DebtCategory.DEAD_CODE.value:
                    action_type = "REMOVE_DEAD_CODE"
                elif issue.category == DebtCategory.UNUSED_IMPORTS.value:
                    action_type = "REMOVE_UNUSED_IMPORTS"
                elif issue.category == DebtCategory.DEEP_NESTING.value:
                    action_type = "FLATTEN_NESTING_WITH_GUARD_CLAUSES"
                elif issue.category == DebtCategory.HIGH_CYCLOMATIC_COMPLEXITY.value:
                    action_type = "SIMPLIFY_BRANCHING_LOGIC"
                elif issue.category == DebtCategory.MAGIC_NUMBERS.value:
                    action_type = "PARAMETRIZE_NAMED_CONSTANT"

                actions.append(
                    RefactoringAction(
                        id=f"ACT-{action_order:02d}",
                        action_type=action_type,
                        target_file=issue.file,
                        target_symbol=issue.symbol,
                        description=f"{issue.recommendation} (Resolves {issue.id}: {issue.title})",
                        priority=issue.severity,
                        estimated_effort_hours=issue.estimated_fix_time,
                        risk=issue.risk,
                        order=action_order,
                    )
                )
                action_order += 1

        migration_steps = [
            f"1. Stage isolated refactoring branch for '{', '.join(candidate.affected_files)}'.",
            "2. Apply structural extractions while maintaining backward-compatible function signatures.",
            "3. Add deprecation shims or type aliases if any public symbol signatures are modified.",
            "4. Verify all internal callers resolve to updated modular routines.",
        ]

        required_tests = [
            f"tests/test_{Path(f).stem}.py" for f in candidate.affected_files
        ]
        if not required_tests:
            required_tests = ["tests/test_refactoring.py"]

        validation_steps = [
            "1. Execute unit and integration test suite via TesterAgent (`pytest tests/ -v`).",
            "2. Verify cyclomatic complexity drops below 10 for all modified routines.",
            "3. Confirm zero circular dependency cycles via SymbolGraph verification.",
            "4. Validate architecture layer compliance with DesignValidator.",
        ]

        rollback_strategy = (
            f"If regression tests fail or defects are detected by ReviewerAgent, perform Git soft reset to "
            f"pre-refactoring commit hash and preserve modified files in stash."
        )

        total_hours = sum(a.estimated_effort_hours for a in actions)
        summary = f"Refactoring plan with {len(actions)} atomic actions targeting {len(candidate.affected_files)} files. Estimated effort: {total_hours:.1f}h."

        return RefactoringPlan(
            priority_ordered_actions=actions,
            rollback_strategy=rollback_strategy,
            migration_steps=migration_steps,
            required_tests=required_tests,
            validation_steps=validation_steps,
            candidate=candidate,
            summary=summary,
            estimated_total_hours=round(total_hours, 1),
        )

    # -------------------------------------------------------------------------
    # ROI & Decision Evaluation API
    # -------------------------------------------------------------------------

    def estimate_roi(
        self,
        issues: List[TechnicalDebtIssue],
        candidates: List[RefactoringCandidate],
        plan: Optional[RefactoringPlan] = None,
    ) -> Dict[str, Any]:
        """
        Estimates Return on Investment (ROI) across development time saved,
        bug reduction probability, and long-term maintenance savings.
        """
        total_refactoring_hours = plan.estimated_total_hours if plan else sum(c.estimated_hours for c in candidates[:3])
        total_refactoring_hours = max(0.5, total_refactoring_hours)

        crit_count = sum(1 for i in issues if i.severity == "CRITICAL")
        high_count = sum(1 for i in issues if i.severity == "HIGH")
        med_count = sum(1 for i in issues if i.severity == "MEDIUM")

        dev_time_saved = round((crit_count * 6.0) + (high_count * 3.5) + (med_count * 1.5), 1)
        future_maintenance_savings = round((crit_count * 12.0) + (high_count * 7.0) + (med_count * 3.0), 1)
        bug_reduction = min(65.0, round((crit_count * 15.0) + (high_count * 8.0) + (med_count * 3.0), 1))
        test_stability_improvement = min(50.0, round((crit_count * 12.0) + (high_count * 6.0) + 10.0, 1))

        net_savings = round(dev_time_saved + future_maintenance_savings - total_refactoring_hours, 1)
        roi_ratio = round((dev_time_saved + future_maintenance_savings) / total_refactoring_hours, 2)

        benefit = "LOW"
        if roi_ratio >= 3.0 or crit_count > 0:
            benefit = "HIGH"
        elif roi_ratio >= 1.5 or high_count > 0:
            benefit = "MEDIUM"

        return {
            "development_time_saved_hours": dev_time_saved,
            "bug_reduction_percent": bug_reduction,
            "future_maintenance_savings_hours": future_maintenance_savings,
            "test_stability_improvement_percent": test_stability_improvement,
            "overall_engineering_benefit": benefit,
            "roi_ratio": roi_ratio,
            "estimated_refactoring_hours": total_refactoring_hours,
            "net_hours_saved": net_savings,
        }

    def _evaluate_should_refactor_first(
        self,
        issues: List[TechnicalDebtIssue],
        candidates: List[RefactoringCandidate],
        metrics: RefactoringMetrics,
        task: Optional[Any] = None,
    ) -> bool:
        """
        Determines whether refactoring should strictly occur BEFORE feature implementation.
        """
        if not issues or not candidates:
            return False

        if any(i.severity == "CRITICAL" for i in issues):
            return True

        if metrics.technical_debt_score >= 40.0 or metrics.maintainability_index < 60.0:
            return True

        if task:
            task_files = {
                str(Path(f).as_posix()).lower()
                for f in getattr(task, "estimated_files", []) if isinstance(f, str)
            }
            if task_files:
                for cand in candidates:
                    cand_files = {str(Path(f).as_posix()).lower() for f in cand.affected_files}
                    if (task_files & cand_files) and cand.risk in ("HIGH", "CRITICAL"):
                        return True

        if candidates and candidates[0].priority_score >= 60.0:
            return True

        return False

    # -------------------------------------------------------------------------
    # Helper AST Complexity & LCOM Methods
    # -------------------------------------------------------------------------

    def _calculate_ast_cyclomatic_complexity(self, fn_node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> int:
        """Calculates standard McCabe cyclomatic complexity for a function AST."""
        complexity = 1
        for sub in ast.walk(fn_node):
            if isinstance(sub, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.AsyncWith)):
                complexity += 1
            elif isinstance(sub, ast.BoolOp):
                complexity += max(1, len(sub.values) - 1)
            elif isinstance(sub, ast.IfExp):
                complexity += 1
            elif hasattr(ast, "Match") and isinstance(sub, getattr(ast, "Match")):
                complexity += len(getattr(sub, "cases", []))
        return complexity

    def _calculate_ast_max_nesting_depth(self, fn_node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> int:
        """Computes maximum control flow nesting depth in a function AST."""
        max_depth = 0

        def walk_depth(node: ast.AST, current_depth: int) -> None:
            nonlocal max_depth
            if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)):
                current_depth += 1
                if current_depth > max_depth:
                    max_depth = current_depth

            for child in ast.iter_child_nodes(node):
                walk_depth(child, current_depth)

        walk_depth(fn_node, 0)
        return max_depth

    def _compute_class_lcom(self, class_node: ast.ClassDef) -> float:
        """Computes Lack of Cohesion in Methods (LCOM) metric (0.0 = cohesive, 1.0 = low cohesion)."""
        methods = [m for m in class_node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name != "__init__"]
        if len(methods) < 2:
            return 0.0

        method_attributes: List[Set[str]] = []
        for m in methods:
            attrs: Set[str] = set()
            for sub in ast.walk(m):
                if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == "self":
                    attrs.add(sub.attr)
            method_attributes.append(attrs)

        total_pairs = 0
        empty_intersection_pairs = 0
        for i in range(len(method_attributes)):
            for j in range(i + 1, len(method_attributes)):
                total_pairs += 1
                if not (method_attributes[i] & method_attributes[j]):
                    empty_intersection_pairs += 1

        if total_pairs == 0:
            return 0.0
        return round(empty_intersection_pairs / total_pairs, 3)

    # -------------------------------------------------------------------------
    # MemoryManager & Persistence API
    # -------------------------------------------------------------------------

    def record_completed_refactoring(
        self,
        candidate: RefactoringCandidate,
        task: Optional[Any] = None,
        metrics_before: Optional[RefactoringMetrics] = None,
        metrics_after: Optional[RefactoringMetrics] = None,
    ) -> None:
        """Records a successfully completed refactoring to MemoryManager and history."""
        task_id = getattr(task, "id", "TASK-REF") if task else "TASK-REF"

        maint_imp = 0.0
        if metrics_before and metrics_after:
            maint_imp = round(metrics_after.maintainability_index - metrics_before.maintainability_index, 2)

        self._telemetry["files_improved"] += len(candidate.affected_files)
        self._telemetry["maintainability_improvement"] += max(0.0, maint_imp)
        self._telemetry["debt_removed"] += candidate.priority_score
        self._telemetry["time_saved"] += candidate.estimated_hours * 1.5

        cand_title = candidate.title or candidate.current_structure

        if self.memory_manager:
            try:
                content = (
                    f"Refactoring Action: {cand_title}\n"
                    f"Target Structure: {candidate.target_structure}\n"
                    f"Files Modified: {', '.join(candidate.affected_files)}\n"
                    f"Maintainability Improvement: +{maint_imp:.1f}\n"
                    f"Reason: {candidate.reason}"
                )
                title = f"Refactoring Completed: {cand_title} [{task_id}]"

                if hasattr(self.memory_manager, "add_memory"):
                    self.memory_manager.add_memory(
                        title=title,
                        content=content,
                        category="REFACTORING",
                        tags=["refactoring", "technical_debt", "code_health"],
                        importance=4,
                    )
                logger.info("Recorded refactoring memory for Task [%s].", task_id)
            except Exception as err:
                logger.warning("Failed to record refactoring to MemoryManager: %s", err)

        self._save_to_refactoring_history({
            "task_id": task_id,
            "candidate": candidate.to_dict(),
            "maintainability_improvement": maint_imp,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def save_technical_debt(self, report: RefactoringReport, path: Optional[Union[str, Path]] = None) -> Path:
        """Atomically saves RefactoringReport to persistent JSON storage."""
        dest = Path(path).resolve() if path else self.technical_debt_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        payload = report.to_dict()
        tmp_dest = dest.with_suffix(".tmp")
        with open(tmp_dest, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        shutil.move(str(tmp_dest), str(dest))
        return dest

    def load_technical_debt(self, path: Optional[Union[str, Path]] = None) -> RefactoringReport:
        """Loads RefactoringReport from persistent JSON storage."""
        src = Path(path).resolve() if path else self.technical_debt_path
        if not src.is_file():
            if self.auto_create_persistence:
                report = RefactoringReport(project_root=str(src.parent))
                self.save_technical_debt(report, src)
                return report
            raise FileNotFoundError(f"Technical debt file not found at '{src}'.")

        try:
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)
            return RefactoringReport.from_dict(data)
        except Exception as err:
            logger.warning("Failed to parse technical debt JSON (%s). Returning default report.", err)
            return RefactoringReport(project_root=str(src.parent))

    def _save_to_refactoring_history(self, record: Dict[str, Any]) -> None:
        """Appends record to persistent refactoring history JSON."""
        dest = self.history_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        self._telemetry["refactoring_history"].append(record)
        payload = {
            "history": self._telemetry["refactoring_history"],
            "total_records": len(self._telemetry["refactoring_history"]),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        tmp_dest = dest.with_suffix(".tmp")
        with open(tmp_dest, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        shutil.move(str(tmp_dest), str(dest))

    def _load_history_on_init(self) -> None:
        """Loads refactoring history from disk on startup if available."""
        if self.history_path.is_file():
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                records = data.get("history", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                self._telemetry["refactoring_history"] = records
            except Exception as err:
                logger.warning("Could not load initial refactoring history: %s", err)

    # -------------------------------------------------------------------------
    # Serialization API
    # -------------------------------------------------------------------------

    def serialize(self, report: RefactoringReport) -> Dict[str, Any]:
        """Serializes RefactoringReport to dictionary."""
        return report.to_dict()

    def deserialize(self, data: Union[str, Dict[str, Any]]) -> RefactoringReport:
        """Deserializes RefactoringReport from JSON string or dictionary."""
        if isinstance(data, str):
            data = json.loads(data)
        return RefactoringReport.from_dict(data)

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns structured technical debt telemetry."""
        return dict(self._telemetry)
