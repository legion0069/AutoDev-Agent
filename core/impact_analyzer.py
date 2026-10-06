"""
impact_analyzer.py - Code Impact Analysis & Breaking Change Detection for AutoDev (v1.5)

Analyzes the blast radius of proposed file or symbol modifications before execution.
Evaluates direct and transitive dependents, caller graphs, inheritance hierarchies,
interface implementations, and generates deterministic risk scores (0-100) and validation plans.
"""

from __future__ import annotations

import logging
import sys
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union

# Ensure project root is available on sys.path for direct execution
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if TYPE_CHECKING:
    from agents.task_planner_agent import Task

from core.symbol_graph import Symbol, SymbolGraph, SymbolType, Visibility

logger = logging.getLogger("AutoDev.ImpactAnalyzer")


class RiskLevel:
    """Standardized blast radius risk classifications."""
    LOW = "LOW"            # 0 - 25
    MEDIUM = "MEDIUM"      # 26 - 50
    HIGH = "HIGH"          # 51 - 75
    CRITICAL = "CRITICAL"  # 76 - 100

    @classmethod
    def from_score(cls, score: float) -> str:
        """Maps numerical score (0-100) to risk level string."""
        if score <= 25.0:
            return cls.LOW
        if score <= 50.0:
            return cls.MEDIUM
        if score <= 75.0:
            return cls.HIGH
        return cls.CRITICAL


@dataclass
class ImpactReport:
    """Structured impact analysis and blast radius report."""
    target: str
    risk_level: str
    affected_files: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    direct_dependents: List[str] = field(default_factory=list)
    transitive_dependents: List[str] = field(default_factory=list)
    callers: List[str] = field(default_factory=list)
    subclasses: List[str] = field(default_factory=list)
    implementations: List[str] = field(default_factory=list)
    affected_tests: List[str] = field(default_factory=list)
    breaking_change_risks: List[str] = field(default_factory=list)
    recommended_validation: List[str] = field(default_factory=list)
    impact_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Converts impact report to serializable dictionary."""
        return {
            "target": self.target,
            "risk_level": self.risk_level,
            "affected_files": list(self.affected_files),
            "affected_symbols": list(self.affected_symbols),
            "direct_dependents": list(self.direct_dependents),
            "transitive_dependents": list(self.transitive_dependents),
            "callers": list(self.callers),
            "subclasses": list(self.subclasses),
            "implementations": list(self.implementations),
            "affected_tests": list(self.affected_tests),
            "breaking_change_risks": list(self.breaking_change_risks),
            "recommended_validation": list(self.recommended_validation),
            "impact_score": round(self.impact_score, 2),
        }


class ImpactAnalyzer:
    """
    Evaluates blast radius, downstream dependencies, and breaking-change risks
    for tasks, individual symbols, or target files.
    """

    def __init__(
        self,
        symbol_graph: Optional[SymbolGraph] = None,
        index_path: Union[str, Path] = "memory/code_index.json",
        project_root: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Initializes the ImpactAnalyzer.

        Args:
            symbol_graph: Optional existing SymbolGraph.
            index_path: Path to code_index.json if symbol_graph is omitted.
            project_root: Workspace root directory.
        """
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd()
        self.index_path = Path(index_path).resolve()
        self.graph = symbol_graph or self._load_or_empty_graph()

    # -------------------------------------------------------------------------
    # Public Analysis API
    # -------------------------------------------------------------------------

    def analyze_task(
        self,
        task: Union[Task, Dict[str, Any]],
        graph: Optional[SymbolGraph] = None,
    ) -> ImpactReport:
        """
        Analyzes the blast radius for an entire task based on its estimated files and keywords.

        Args:
            task: Task object or dictionary.
            graph: Optional SymbolGraph override.

        Returns:
            Aggregated ImpactReport across all target files and symbols.
        """
        active_graph = graph or self.graph
        task_id, task_title, task_desc, estimated_files = self._extract_task_signals(task)

        if not active_graph or not active_graph.symbols:
            return ImpactReport(
                target=task_id,
                risk_level=RiskLevel.LOW,
                recommended_validation=["Run unit tests after task execution."],
                impact_score=0.0,
            )

        # 1. Collect target files and target symbols
        target_files: Set[str] = {f.replace("\\", "/").strip() for f in estimated_files if f.strip()}
        target_symbols: List[Symbol] = []

        # Find symbols matching task title
        for word in task_title.split():
            if len(word) > 2:
                matching = active_graph.search_by_name(word, exact=False)
                for m in matching:
                    if m not in target_symbols:
                        target_symbols.append(m)
                        target_files.add(m.file)

        # If estimated_files given, include all symbols in those files
        for f in list(target_files):
            for sym in active_graph.find_file(f):
                if sym not in target_symbols:
                    target_symbols.append(sym)

        # 2. Aggregate impact across targets
        all_affected_files: Set[str] = set(target_files)
        all_affected_symbols: Set[str] = {s.qualified_name for s in target_symbols}
        all_direct_dependents: Set[str] = set()
        all_transitive_dependents: Set[str] = set()
        all_callers: Set[str] = set()
        all_subclasses: Set[str] = set()
        all_implementations: Set[str] = set()
        all_affected_tests: Set[str] = set()
        all_risks: List[str] = []
        all_validation: List[str] = []

        total_score_acc = 0.0

        for f in target_files:
            file_report = self.analyze_file(f, graph=active_graph)
            all_affected_files.update(file_report.affected_files)
            all_direct_dependents.update(file_report.direct_dependents)
            all_transitive_dependents.update(file_report.transitive_dependents)
            all_affected_tests.update(file_report.affected_tests)
            all_risks.extend(file_report.breaking_change_risks)
            all_validation.extend(file_report.recommended_validation)
            total_score_acc = max(total_score_acc, file_report.impact_score)

        for sym in target_symbols:
            sym_report = self.analyze_symbol(sym.qualified_name, graph=active_graph)
            all_affected_symbols.update(sym_report.affected_symbols)
            all_callers.update(sym_report.callers)
            all_subclasses.update(sym_report.subclasses)
            all_implementations.update(sym_report.implementations)
            all_risks.extend(sym_report.breaking_change_risks)
            total_score_acc = max(total_score_acc, sym_report.impact_score)

        # Task priority boost
        priority_boost = (len(all_direct_dependents) * 5.0) + (len(all_callers) * 3.0)
        final_score = min(max(total_score_acc + (priority_boost * 0.2), 0.0), 100.0)
        risk_lvl = RiskLevel.from_score(final_score)

        # Deduplicate recommendations and risks
        dedup_risks = sorted(list(set(all_risks)))
        dedup_val = sorted(list(set(all_validation)))
        if not dedup_val:
            dedup_val = ["Run targeted unit tests for modified components."]

        return ImpactReport(
            target=task_id,
            risk_level=risk_lvl,
            affected_files=sorted(list(all_affected_files)),
            affected_symbols=sorted(list(all_affected_symbols)),
            direct_dependents=sorted(list(all_direct_dependents)),
            transitive_dependents=sorted(list(all_transitive_dependents)),
            callers=sorted(list(all_callers)),
            subclasses=sorted(list(all_subclasses)),
            implementations=sorted(list(all_implementations)),
            affected_tests=sorted(list(all_affected_tests)),
            breaking_change_risks=dedup_risks,
            recommended_validation=dedup_val,
            impact_score=final_score,
        )

    def analyze_symbol(
        self,
        symbol_name: str,
        graph: Optional[SymbolGraph] = None,
    ) -> ImpactReport:
        """
        Analyzes the blast radius of modifying a specific function, class, or method.

        Args:
            symbol_name: Short or qualified name of the target symbol.
            graph: Optional SymbolGraph override.

        Returns:
            ImpactReport detailing callers, subclasses, affected tests, and risk score.
        """
        active_graph = graph or self.graph
        sym = active_graph.find_symbol(symbol_name) if active_graph else None

        if not sym:
            return ImpactReport(
                target=symbol_name,
                risk_level=RiskLevel.LOW,
                breaking_change_risks=[f"Symbol '{symbol_name}' not found in active graph."],
                recommended_validation=["Verify symbol definition."],
                impact_score=0.0,
            )

        callers: Set[str] = {c.qualified_name for c in active_graph.find_callers(sym.name)}
        subclasses: Set[str] = {s.qualified_name for s in active_graph.find_subclasses(sym.name)}
        implementations: Set[str] = set()

        if sym.symbol_type == SymbolType.INTERFACE:
            implementations = set(active_graph.interface_implementers.get(sym.name, set()))
            implementations.update(active_graph.interface_implementers.get(sym.qualified_name, set()))

        affected_files: Set[str] = {sym.file}
        for c in active_graph.find_callers(sym.name):
            affected_files.add(c.file)
        for s in active_graph.find_subclasses(sym.name):
            affected_files.add(s.file)

        # Identify tests referencing this symbol
        affected_tests: Set[str] = set()
        for f in affected_files:
            if self._is_test_file(f):
                affected_tests.add(f)
        for f in active_graph.find_dependents(sym.file):
            if self._is_test_file(f):
                affected_tests.add(f)

        # Breaking change risks
        risks: List[str] = []
        validation: List[str] = []

        if sym.visibility == Visibility.PUBLIC:
            if callers:
                risks.append(f"Public symbol '{sym.name}' is invoked by {len(callers)} caller(s).")
            if subclasses:
                risks.append(f"Base class '{sym.name}' has {len(subclasses)} subclass(es). Signature changes will break inheritance.")
            if sym.symbol_type == SymbolType.INTERFACE and implementations:
                risks.append(f"Interface '{sym.name}' is implemented by {len(implementations)} class(es). Modifying methods requires updating all implementers.")
            if sym.symbol_type == SymbolType.CONSTRUCTOR and callers:
                risks.append(f"Constructor '{sym.name}' modified; requires updating instantiation call sites.")

        if not risks:
            risks.append(f"Low risk: Internal or isolated {sym.symbol_type} '{sym.name}'.")

        if affected_tests:
            validation.append(f"Run {len(affected_tests)} test suite(s): {', '.join(sorted(list(affected_tests))[:3])}")
        else:
            validation.append(f"Create unit tests covering '{sym.name}'.")

        if callers:
            validation.append(f"Verify {len(callers)} downstream caller(s) after modifying signature.")

        # Compute Score
        score = self._compute_symbol_score(sym, callers, subclasses, implementations, affected_files)
        risk_lvl = RiskLevel.from_score(score)

        return ImpactReport(
            target=sym.qualified_name,
            risk_level=risk_lvl,
            affected_files=sorted(list(affected_files)),
            affected_symbols=[sym.qualified_name],
            direct_dependents=sorted(list(active_graph.find_dependents(sym.file))),
            callers=sorted(list(callers)),
            subclasses=sorted(list(subclasses)),
            implementations=sorted(list(implementations)),
            affected_tests=sorted(list(affected_tests)),
            breaking_change_risks=risks,
            recommended_validation=validation,
            impact_score=score,
        )

    def analyze_file(
        self,
        file_path: str,
        graph: Optional[SymbolGraph] = None,
    ) -> ImpactReport:
        """
        Analyzes the blast radius of modifying an entire source file.

        Args:
            file_path: Relative path of the target file.
            graph: Optional SymbolGraph override.

        Returns:
            ImpactReport detailing direct/transitive dependents, affected tests, and score.
        """
        active_graph = graph or self.graph
        norm_file = file_path.replace("\\", "/").strip()

        if not active_graph:
            return ImpactReport(
                target=norm_file,
                risk_level=RiskLevel.LOW,
                impact_score=0.0,
            )

        direct_deps = set(active_graph.find_dependents(norm_file))
        transitive_deps = self._compute_transitive_dependents(norm_file, active_graph)
        all_dependents = direct_deps | transitive_deps

        file_symbols = active_graph.find_file(norm_file)
        affected_sym_names = [s.qualified_name for s in file_symbols]

        affected_tests = {f for f in (all_dependents | {norm_file}) if self._is_test_file(f)}
        affected_files = sorted(list(all_dependents | {norm_file}))

        risks: List[str] = []
        validation: List[str] = []

        if len(direct_deps) >= 5:
            risks.append(f"Core shared module '{norm_file}' directly imported by {len(direct_deps)} files.")
        elif direct_deps:
            risks.append(f"Module '{norm_file}' imported by {len(direct_deps)} dependent file(s).")
        else:
            risks.append(f"Isolated file '{norm_file}' with zero external dependents.")

        if affected_tests:
            validation.append(f"Execute affected test files: {', '.join(sorted(list(affected_tests))[:3])}")
        validation.append(f"Verify exports in '{norm_file}'.")

        # Score calculation
        score = self._compute_file_score(norm_file, direct_deps, transitive_deps, file_symbols, affected_tests)
        risk_lvl = RiskLevel.from_score(score)

        return ImpactReport(
            target=norm_file,
            risk_level=risk_lvl,
            affected_files=affected_files,
            affected_symbols=affected_sym_names,
            direct_dependents=sorted(list(direct_deps)),
            transitive_dependents=sorted(list(transitive_deps)),
            affected_tests=sorted(list(affected_tests)),
            breaking_change_risks=risks,
            recommended_validation=validation,
            impact_score=score,
        )

    # -------------------------------------------------------------------------
    # Scoring Algorithm Internals
    # -------------------------------------------------------------------------

    def _compute_symbol_score(
        self,
        sym: Symbol,
        callers: Set[str],
        subclasses: Set[str],
        implementations: Set[str],
        affected_files: Set[str],
    ) -> float:
        """
        Computes deterministic symbol blast radius score (0-100).
        """
        base_score = 10.0

        # Public vs Private
        if sym.visibility == Visibility.PUBLIC:
            base_score += 15.0
        elif sym.visibility == Visibility.PRIVATE:
            base_score -= 5.0

        # Symbol type sensitivity
        if sym.symbol_type == SymbolType.INTERFACE:
            base_score += 25.0
        elif sym.symbol_type == SymbolType.CLASS:
            base_score += 15.0
        elif sym.symbol_type == SymbolType.CONSTRUCTOR:
            base_score += 10.0

        # Caller scale (+5 per caller, max 30)
        caller_pts = min(len(callers) * 6.0, 30.0)

        # Subclass scale (+10 per subclass, max 25)
        subclass_pts = min(len(subclasses) * 10.0, 25.0)

        # Implementation scale (+10 per implementer, max 20)
        impl_pts = min(len(implementations) * 10.0, 20.0)

        # File breadth scale (+4 per file, max 15)
        file_pts = min(len(affected_files) * 4.0, 15.0)

        total = base_score + caller_pts + subclass_pts + impl_pts + file_pts
        return round(min(max(total, 0.0), 100.0), 2)

    def _compute_file_score(
        self,
        file_path: str,
        direct_deps: Set[str],
        transitive_deps: Set[str],
        file_symbols: List[Symbol],
        affected_tests: Set[str],
    ) -> float:
        """
        Computes deterministic file blast radius score (0-100).
        """
        base_score = 10.0

        # Direct dependents (+8 per dependent, max 40)
        direct_pts = min(len(direct_deps) * 8.0, 40.0)

        # Transitive dependents (+3 per transitive dependent, max 25)
        transitive_pts = min(len(transitive_deps) * 3.0, 25.0)

        # Symbol density (+1 per symbol, max 15)
        sym_pts = min(len(file_symbols) * 1.5, 15.0)

        # Test coverage mitigation/relevance (+3 per test file, max 15)
        test_pts = min(len(affected_tests) * 3.0, 15.0)

        total = base_score + direct_pts + transitive_pts + sym_pts + test_pts
        return round(min(max(total, 0.0), 100.0), 2)

    def _compute_transitive_dependents(self, file_path: str, graph: SymbolGraph) -> Set[str]:
        """Performs BFS graph traversal to calculate transitive downstream dependents."""
        visited: Set[str] = set()
        queue = deque([file_path])

        while queue:
            curr = queue.popleft()
            dependents = graph.find_dependents(curr)
            for dep in dependents:
                if dep not in visited and dep != file_path:
                    visited.add(dep)
                    queue.append(dep)

        return visited

    # -------------------------------------------------------------------------
    # Helper Utilities
    # -------------------------------------------------------------------------

    def _load_or_empty_graph(self) -> SymbolGraph:
        """Loads SymbolGraph from index_path or returns empty SymbolGraph."""
        if self.index_path.exists():
            try:
                graph = SymbolGraph()
                graph.import_json(self.index_path)
                return graph
            except Exception as err:
                logger.warning(f"Failed to load SymbolGraph from {self.index_path}: {err}")
        return SymbolGraph()

    def _is_test_file(self, file_path: str) -> bool:
        """Checks if a file path matches standard test naming conventions."""
        norm = file_path.replace("\\", "/").strip()
        fname = Path(norm).name
        return (
            norm.startswith("tests/")
            or norm.startswith("__tests__/")
            or fname.startswith("test_")
            or fname.endswith("_test.py")
            or fname.endswith("Test.java")
            or fname.endswith("Tests.java")
            or ".test." in fname
            or ".spec." in fname
        )

    def _extract_task_signals(self, task: Any) -> Tuple[str, str, str, List[str]]:
        """Extracts standardized attributes from Task object or dict."""
        if hasattr(task, "id") and hasattr(task, "title"):
            return (
                str(getattr(task, "id", "UNKNOWN-TASK")),
                str(getattr(task, "title", "")),
                str(getattr(task, "description", "")),
                list(getattr(task, "estimated_files", [])),
            )
        if isinstance(task, dict):
            return (
                str(task.get("id", "UNKNOWN-TASK")),
                str(task.get("title", "")),
                str(task.get("description", "")),
                list(task.get("estimated_files", [])),
            )
        return ("UNKNOWN-TASK", str(task), "", [])
