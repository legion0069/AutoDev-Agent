"""
impact_analyzer.py - Dependency-Aware Code Impact Analysis Engine for AutoDev (v1.5)

Predicts which files, classes, functions, tests, callers, callees, and modules
are affected before code generation begins.
Operates completely offline using the AST SymbolGraph without LLM calls.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

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
class ImpactNode:
    """Represents a discrete symbol or file node in the blast radius graph."""
    symbol_id: str
    symbol_name: str
    file: str
    reason: str
    depth: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol_id": self.symbol_id,
            "symbol_name": self.symbol_name,
            "file": self.file,
            "reason": self.reason,
            "depth": self.depth,
        }


@dataclass
class ImpactReport:
    """Structured impact analysis and blast radius telemetry."""
    affected_files: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    affected_tests: List[str] = field(default_factory=list)
    callers: List[str] = field(default_factory=list)
    callees: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    inheritance_chain: List[str] = field(default_factory=list)
    estimated_change_scope: str = "isolated"
    risk_level: str = RiskLevel.LOW
    confidence: float = 1.0
    summary: str = ""

    # Extended telemetry & backward compatibility fields
    target: str = ""
    direct_dependents: List[str] = field(default_factory=list)
    transitive_dependents: List[str] = field(default_factory=list)
    subclasses: List[str] = field(default_factory=list)
    implementations: List[str] = field(default_factory=list)
    breaking_change_risks: List[str] = field(default_factory=list)
    recommended_validation: List[str] = field(default_factory=list)
    impact_score: float = 0.0
    nodes: List[ImpactNode] = field(default_factory=list)

    @property
    def risk(self) -> str:
        """Alias for risk_level."""
        return self.risk_level

    def to_dict(self) -> Dict[str, Any]:
        """Converts impact report to serializable dictionary."""
        return {
            "risk": self.risk_level,
            "risk_level": self.risk_level,
            "confidence": round(self.confidence, 2),
            "affected_files": list(self.affected_files),
            "affected_symbols": list(self.affected_symbols),
            "affected_tests": list(self.affected_tests),
            "callers": list(self.callers),
            "callees": list(self.callees),
            "dependencies": list(self.dependencies),
            "dependents": list(self.dependents),
            "direct_dependents": list(self.direct_dependents),
            "transitive_dependents": list(self.transitive_dependents),
            "subclasses": list(self.subclasses),
            "implementations": list(self.implementations),
            "inheritance_chain": list(self.inheritance_chain),
            "estimated_change_scope": self.estimated_change_scope,
            "breaking_change_risks": list(self.breaking_change_risks),
            "recommended_validation": list(self.recommended_validation),
            "impact_score": round(self.impact_score, 2),
            "summary": self.summary,
            "target": self.target,
            "nodes": [n.to_dict() for n in self.nodes],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serializes report to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ImpactReport:
        """Constructs ImpactReport from dictionary."""
        nodes_data = data.get("nodes", [])
        nodes = [
            ImpactNode(
                symbol_id=n.get("symbol_id", ""),
                symbol_name=n.get("symbol_name", ""),
                file=n.get("file", ""),
                reason=n.get("reason", ""),
                depth=int(n.get("depth", 1)),
            )
            for n in nodes_data if isinstance(n, dict)
        ]

        return cls(
            affected_files=list(data.get("affected_files", [])),
            affected_symbols=list(data.get("affected_symbols", [])),
            affected_tests=list(data.get("affected_tests", [])),
            callers=list(data.get("callers", [])),
            callees=list(data.get("callees", [])),
            dependencies=list(data.get("dependencies", [])),
            dependents=list(data.get("dependents", [])),
            inheritance_chain=list(data.get("inheritance_chain", [])),
            estimated_change_scope=data.get("estimated_change_scope", "isolated"),
            risk_level=data.get("risk_level", data.get("risk", RiskLevel.LOW)),
            confidence=float(data.get("confidence", 1.0)),
            summary=data.get("summary", ""),
            target=data.get("target", ""),
            direct_dependents=list(data.get("direct_dependents", [])),
            transitive_dependents=list(data.get("transitive_dependents", [])),
            subclasses=list(data.get("subclasses", [])),
            implementations=list(data.get("implementations", [])),
            breaking_change_risks=list(data.get("breaking_change_risks", [])),
            recommended_validation=list(data.get("recommended_validation", [])),
            impact_score=float(data.get("impact_score", 0.0)),
            nodes=nodes,
        )


class ImpactAnalyzer:
    """
    Dependency-aware impact analysis engine.
    Predicts affected files, symbols, callers, callees, dependencies, and test suites
    before code changes occur.
    """

    TEST_PATTERNS = [
        re.compile(r"^test_.*\.py$", re.IGNORECASE),
        re.compile(r".*_test\.py$", re.IGNORECASE),
        re.compile(r"^tests/.*\.py$", re.IGNORECASE),
        re.compile(r".*Test\.java$", re.IGNORECASE),
        re.compile(r".*Tests\.java$", re.IGNORECASE),
        re.compile(r".*\.test\.(js|jsx|ts|tsx)$", re.IGNORECASE),
        re.compile(r".*\.spec\.(js|jsx|ts|tsx)$", re.IGNORECASE),
        re.compile(r"^__tests__/.*", re.IGNORECASE),
    ]

    def __init__(
        self,
        symbol_graph: Optional[SymbolGraph] = None,
        max_depth: int = 3,
        index_path: Union[str, Path] = "memory/code_index.json",
        project_root: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Initializes the ImpactAnalyzer.

        Args:
            symbol_graph: Optional SymbolGraph instance.
            max_depth: Maximum graph expansion depth (default: 3 hops).
            index_path: Path to code_index.json if symbol_graph is omitted.
            project_root: Workspace root directory.
        """
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd()
        self.index_path = Path(index_path).resolve()
        self.max_depth = max_depth
        self.graph = symbol_graph if symbol_graph is not None else self._load_or_empty_graph()

    # -------------------------------------------------------------------------
    # Core Pipeline API
    # -------------------------------------------------------------------------

    def analyze(
        self,
        task: Union[Task, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> ImpactReport:
        """
        Analyzes the blast radius for a given task and context.

        Pipeline:
        1. Extract target files and search keywords from task/context.
        2. Locate matching initial symbols.
        3. Expand call graph (forward & reverse calls) up to max_depth with cycle avoidance.
        4. Expand dependency graph (imported and dependent files) up to max_depth.
        5. Trace inheritance chains and interface implementers.
        6. Discover affected test suites.
        7. Compute deterministic risk score, risk level, confidence, and summary.

        Args:
            task: Target engineering task.
            context: Optional project context.

        Returns:
            Comprehensive ImpactReport.
        """
        ctx = context or {}
        task_id, task_title, task_desc, estimated_files = self._extract_task_signals(task)

        if not self.graph or not self.graph.symbols:
            logger.info("SymbolGraph is empty. Returning baseline low-risk ImpactReport.")
            return ImpactReport(
                target=task_id,
                risk_level=RiskLevel.LOW,
                confidence=0.50,
                estimated_change_scope="isolated",
                summary="No indexed symbols available. Isolated task execution presumed.",
                recommended_validation=["Run unit tests after task execution."],
                impact_score=0.0,
            )

        # 1. Locate initial symbols
        initial_symbols = self.find_initial_symbols(task, ctx)

        # Collect initial files
        target_files: Set[str] = {f.replace("\\", "/").strip() for f in estimated_files if f.strip()}
        for s in initial_symbols:
            target_files.add(s.file)

        # If estimated files given but no symbols matched, add all symbols in those files
        for f in list(target_files):
            for s in self.graph.find_file(f):
                if s not in initial_symbols:
                    initial_symbols.append(s)

        # 2. Expand call graph (callers & callees)
        callers, callees, call_nodes = self.expand_call_graph(initial_symbols, max_depth=self.max_depth)

        # 3. Expand dependency graph (dependencies & dependents)
        all_affected_files, dependencies, dependents = self.expand_dependency_graph(
            target_files, max_depth=self.max_depth
        )

        # 4. Trace inheritance & interfaces
        inheritance_chain: Set[str] = set()
        subclasses: Set[str] = set()
        implementations: Set[str] = set()
        breaking_risks: List[str] = []

        for sym in initial_symbols:
            # Base classes
            for base in sym.inherits:
                inheritance_chain.add(f"Base: {base}")
                base_sym = self.graph.find_symbol(base)
                if base_sym:
                    all_affected_files.add(base_sym.file)

            # Subclasses
            for sub in self.graph.find_subclasses(sym.name):
                subclasses.add(sub.qualified_name)
                inheritance_chain.add(f"Subclass: {sub.qualified_name}")
                all_affected_files.add(sub.file)
                breaking_risks.append(
                    f"Base class '{sym.name}' modified; {sub.qualified_name} inherits from it."
                )

            # Interfaces
            if sym.symbol_type == SymbolType.INTERFACE:
                impls = set(self.graph.interface_implementers.get(sym.name, set()))
                impls.update(self.graph.interface_implementers.get(sym.qualified_name, set()))
                for impl in impls:
                    implementations.add(impl)
                    inheritance_chain.add(f"Implements: {impl}")
                    breaking_risks.append(
                        f"Interface '{sym.name}' modified; requires updating implementer '{impl}'."
                    )

            if sym.visibility == Visibility.PUBLIC and callers:
                breaking_risks.append(f"Public symbol '{sym.name}' is invoked by {len(callers)} caller(s).")

        # Add files containing callers and callees
        for c_name in callers:
            c_sym = self.graph.find_symbol(c_name)
            if c_sym:
                all_affected_files.add(c_sym.file)
        for c_name in callees:
            c_sym = self.graph.find_symbol(c_name)
            if c_sym:
                all_affected_files.add(c_sym.file)

        # 5. Discover related tests
        affected_symbols_set: Set[str] = {s.qualified_name for s in initial_symbols}
        affected_symbols_set.update(callers)
        affected_symbols_set.update(callees)
        affected_tests = self.find_related_tests(all_affected_files, affected_symbols_set)

        # 6. Calculate risk score, level, and confidence
        has_public_api = any(s.visibility == Visibility.PUBLIC for s in initial_symbols)
        has_inheritance = bool(inheritance_chain or subclasses or implementations)

        risk_lvl, impact_score, confidence = self.calculate_risk(
            affected_files=all_affected_files,
            affected_symbols=affected_symbols_set,
            callers=callers,
            dependencies=dependencies,
            dependents=dependents,
            is_public_api=has_public_api,
            has_inheritance=has_inheritance,
        )

        # Determine change scope
        if len(all_affected_files) <= 1 and len(initial_symbols) <= 1:
            scope = "isolated_function"
        elif len(all_affected_files) <= 1:
            scope = "module_local"
        elif len(all_affected_files) <= 4:
            scope = "cross_module"
        else:
            scope = "system_wide"

        # 7. Synthesize Summary & Validation recommendations
        summary = self.summarize(
            risk_level=risk_lvl,
            confidence=confidence,
            affected_files=sorted(list(all_affected_files)),
            affected_symbols=sorted(list(affected_symbols_set)),
            affected_tests=affected_tests,
        )

        validation: List[str] = []
        if affected_tests:
            validation.append(f"Execute {len(affected_tests)} affected test file(s): {', '.join(affected_tests[:3])}")
        else:
            validation.append("Create unit tests for modified components.")

        if callers:
            validation.append(f"Verify {len(callers)} call sites across codebase.")
        if implementations or subclasses:
            validation.append(f"Validate {len(implementations) + len(subclasses)} polymorphic implementers/subclasses.")

        # Transitive vs Direct Dependents
        direct_deps = set(self.graph.find_dependents(list(target_files)[0])) if target_files else set()
        transitive_deps = dependents - direct_deps

        return ImpactReport(
            affected_files=sorted(list(all_affected_files)),
            affected_symbols=sorted(list(affected_symbols_set)),
            affected_tests=sorted(list(affected_tests)),
            callers=sorted(list(callers)),
            callees=sorted(list(callees)),
            dependencies=sorted(list(dependencies)),
            dependents=sorted(list(dependents)),
            inheritance_chain=sorted(list(inheritance_chain)),
            estimated_change_scope=scope,
            risk_level=risk_lvl,
            confidence=confidence,
            summary=summary,
            target=task_id,
            direct_dependents=sorted(list(direct_deps)),
            transitive_dependents=sorted(list(transitive_deps)),
            subclasses=sorted(list(subclasses)),
            implementations=sorted(list(implementations)),
            breaking_change_risks=sorted(list(set(breaking_risks))) or [f"Low risk: isolated modification to {task_id}"],
            recommended_validation=validation,
            impact_score=impact_score,
            nodes=call_nodes,
        )

    # -------------------------------------------------------------------------
    # Backward Compatibility Methods
    # -------------------------------------------------------------------------

    def analyze_task(
        self,
        task: Union[Task, Dict[str, Any]],
        graph: Optional[SymbolGraph] = None,
    ) -> ImpactReport:
        """Alias for analyze() to preserve backward compatibility."""
        if graph:
            old_graph = self.graph
            self.graph = graph
            try:
                return self.analyze(task)
            finally:
                self.graph = old_graph
        return self.analyze(task)

    def analyze_symbol(
        self,
        symbol_name: str,
        graph: Optional[SymbolGraph] = None,
    ) -> ImpactReport:
        """Analyzes impact for a single symbol name."""
        active_graph = graph or self.graph
        sym = active_graph.find_symbol(symbol_name) if active_graph else None

        if not sym:
            return ImpactReport(
                target=symbol_name,
                risk_level=RiskLevel.LOW,
                confidence=0.50,
                breaking_change_risks=[f"Symbol '{symbol_name}' not found in active graph."],
                recommended_validation=["Verify symbol definition."],
                impact_score=0.0,
                summary=f"Symbol '{symbol_name}' not found in graph.",
            )

        fake_task = {
            "id": sym.qualified_name,
            "title": sym.name,
            "description": sym.docstring or "",
            "estimated_files": [sym.file],
        }
        return self.analyze_task(fake_task, graph=active_graph)

    def analyze_file(
        self,
        file_path: str,
        graph: Optional[SymbolGraph] = None,
    ) -> ImpactReport:
        """Analyzes impact for an entire target file."""
        active_graph = graph or self.graph
        norm_file = file_path.replace("\\", "/").strip()

        fake_task = {
            "id": norm_file,
            "title": Path(norm_file).stem,
            "description": f"Modifications to {norm_file}",
            "estimated_files": [norm_file],
        }
        return self.analyze_task(fake_task, graph=active_graph)

    # -------------------------------------------------------------------------
    # Individual Analysis Pipeline Steps
    # -------------------------------------------------------------------------

    def find_initial_symbols(
        self,
        task: Union[Task, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Symbol]:
        """
        Locates initial candidate symbols matching task title, description,
        estimated files, and tech stack.
        """
        task_id, task_title, task_desc, estimated_files = self._extract_task_signals(task)
        title_tokens = self._tokenize(task_title)
        desc_tokens = self._tokenize(task_desc)
        all_tokens = set(title_tokens + desc_tokens)

        matched: List[Symbol] = []
        matched_ids: Set[str] = set()

        for sym in self.graph.symbols.values():
            sym_name_lower = sym.name.lower()
            sym_qname_lower = sym.qualified_name.lower()

            # Exact name or substring match
            is_match = False
            if any(t == sym_name_lower for t in title_tokens):
                is_match = True
            elif task_title.lower() in sym_name_lower or sym_name_lower in task_title.lower():
                is_match = True
            elif any(t in sym_qname_lower for t in title_tokens if len(t) > 2):
                is_match = True

            if is_match and sym.id not in matched_ids:
                matched.append(sym)
                matched_ids.add(sym.id)

        return matched

    def expand_call_graph(
        self,
        initial_symbols: List[Symbol],
        max_depth: int = 3,
    ) -> Tuple[Set[str], Set[str], List[ImpactNode]]:
        """
        Expands callers and callees via BFS traversal up to max_depth with cycle avoidance.
        """
        callers: Set[str] = set()
        callees: Set[str] = set()
        nodes: List[ImpactNode] = []

        visited_callers: Set[str] = set()
        visited_callees: Set[str] = set()

        # Caller queue: (symbol_name, current_depth)
        caller_queue: deque[Tuple[str, int]] = deque((s.name, 1) for s in initial_symbols)
        for s in initial_symbols:
            visited_callers.add(s.name)

        while caller_queue:
            curr_name, depth = caller_queue.popleft()
            if depth > max_depth:
                continue

            for caller_sym in self.graph.find_callers(curr_name):
                callers.add(caller_sym.qualified_name)
                nodes.append(
                    ImpactNode(
                        symbol_id=caller_sym.id,
                        symbol_name=caller_sym.qualified_name,
                        file=caller_sym.file,
                        reason=f"Caller of {curr_name}",
                        depth=depth,
                    )
                )
                if caller_sym.name not in visited_callers:
                    visited_callers.add(caller_sym.name)
                    caller_queue.append((caller_sym.name, depth + 1))

        # Callee queue: (symbol_name, current_depth)
        callee_queue: deque[Tuple[str, int]] = deque((s.name, 1) for s in initial_symbols)
        for s in initial_symbols:
            visited_callees.add(s.name)

        while callee_queue:
            curr_name, depth = callee_queue.popleft()
            if depth > max_depth:
                continue

            for callee_sym in self.graph.find_callees(curr_name):
                callees.add(callee_sym.qualified_name)
                nodes.append(
                    ImpactNode(
                        symbol_id=callee_sym.id,
                        symbol_name=callee_sym.qualified_name,
                        file=callee_sym.file,
                        reason=f"Callee of {curr_name}",
                        depth=depth,
                    )
                )
                if callee_sym.name not in visited_callees:
                    visited_callees.add(callee_sym.name)
                    callee_queue.append((callee_sym.name, depth + 1))

        return callers, callees, nodes

    def expand_dependency_graph(
        self,
        initial_files: Set[str],
        max_depth: int = 3,
    ) -> Tuple[Set[str], Set[str], Set[str]]:
        """
        Expands dependencies and dependents via BFS traversal up to max_depth with cycle avoidance.
        """
        all_files: Set[str] = set(initial_files)
        dependencies: Set[str] = set()
        dependents: Set[str] = set()

        # Dependencies queue (downstream imports)
        dep_visited: Set[str] = set(initial_files)
        dep_queue: deque[Tuple[str, int]] = deque((f, 1) for f in initial_files)

        while dep_queue:
            curr_file, depth = dep_queue.popleft()
            if depth > max_depth:
                continue

            for dep in self.graph.find_dependencies(curr_file):
                dependencies.add(dep)
                all_files.add(dep)
                if dep not in dep_visited:
                    dep_visited.add(dep)
                    dep_queue.append((dep, depth + 1))

        # Dependents queue (upstream reverse importers)
        rev_visited: Set[str] = set(initial_files)
        rev_queue: deque[Tuple[str, int]] = deque((f, 1) for f in initial_files)

        while rev_queue:
            curr_file, depth = rev_queue.popleft()
            if depth > max_depth:
                continue

            for rev in self.graph.find_dependents(curr_file):
                dependents.add(rev)
                all_files.add(rev)
                if rev not in rev_visited:
                    rev_visited.add(rev)
                    rev_queue.append((rev, depth + 1))

        return all_files, dependencies, dependents

    def find_related_tests(
        self,
        affected_files: Set[str],
        affected_symbols: Set[str],
    ) -> List[str]:
        """
        Discovers test files exercising or importing any affected files or symbols.
        """
        matched_tests: Set[str] = set()

        # 1. Directly check if affected files are test files
        for f in affected_files:
            if self._is_test_file(f):
                matched_tests.add(f)

        # 2. Match package/module name patterns (e.g., auth.py -> test_auth.py)
        for f in affected_files:
            base_stem = Path(f).stem
            for graph_file in self.graph.files.keys():
                if self._is_test_file(graph_file):
                    test_stem = Path(graph_file).stem
                    if base_stem in test_stem or test_stem in base_stem:
                        matched_tests.add(graph_file)

        # 3. Check test file symbol calls & references
        for graph_file, sym_ids in self.graph.files.items():
            if self._is_test_file(graph_file):
                for sid in sym_ids:
                    sym = self.graph.symbols.get(sid)
                    if sym:
                        calls_set = set(sym.calls) | {sym.name}
                        if any(s in calls_set or s in (sym.docstring or "") for s in affected_symbols):
                            matched_tests.add(graph_file)
                            break

        return sorted(list(matched_tests))

    def calculate_risk(
        self,
        affected_files: Set[str],
        affected_symbols: Set[str],
        callers: Set[str],
        dependencies: Set[str],
        dependents: Set[str],
        is_public_api: bool = False,
        has_inheritance: bool = False,
    ) -> Tuple[str, float, float]:
        """
        Calculates deterministic impact score (0-100), RiskLevel, and confidence (0.0-1.0).
        """
        score = 10.0

        # Affected files scale (+7 per file, max 35)
        score += min(len(affected_files) * 7.0, 35.0)

        # Call graph fan-in (+4 per caller, max 25)
        score += min(len(callers) * 4.0, 25.0)

        # Reverse dependents (+5 per dependent, max 20)
        score += min(len(dependents) * 5.0, 20.0)

        # Public API exposure
        if is_public_api:
            score += 10.0

        # Inheritance & Interface polymorphism
        if has_inheritance:
            score += 15.0

        final_score = round(min(max(score, 0.0), 100.0), 2)
        risk_level = RiskLevel.from_score(final_score)

        # Confidence calculation
        confidence = 0.85
        if len(affected_symbols) > 0 and len(affected_files) > 0:
            confidence += 0.10
        if len(callers) > 0 or len(dependents) > 0:
            confidence += 0.03
        confidence = round(min(confidence, 0.99), 2)

        return risk_level, final_score, confidence

    def summarize(
        self,
        risk_level: str,
        confidence: float,
        affected_files: List[str],
        affected_symbols: List[str],
        affected_tests: List[str],
    ) -> str:
        """Synthesizes a standardized, human-readable impact summary."""
        test_msg = f"{len(affected_tests)} test suite(s)" if affected_tests else "no automated test suite"
        return (
            f"Target modifications propagate to {len(affected_files)} file(s) and "
            f"{len(affected_symbols)} symbol(s) across {test_msg}. "
            f"Risk assessed as {risk_level} (confidence: {confidence:.2f})."
        )

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
        return any(p.search(norm) or p.search(fname) for p in self.TEST_PATTERNS)

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

    def _tokenize(self, text: str) -> List[str]:
        """Extracts normalized alphanumeric word tokens."""
        return [t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 1]
