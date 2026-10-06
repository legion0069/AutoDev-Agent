"""
code_context_retriever.py - Code-Aware Context Retrieval Engine for AutoDev (v1.5)

Determines the smallest useful section of the codebase required to execute a given task
by traversing the SymbolGraph, scoring symbol relevance, expanding 1-hop dependencies,
discovering relevant tests, and enforcing strict token budgeting.
"""

from __future__ import annotations

import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

# Ensure project root is available on sys.path for direct execution
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if TYPE_CHECKING:
    from agents.task_planner_agent import Task

from core.symbol_graph import Symbol, SymbolGraph, SymbolType

logger = logging.getLogger("AutoDev.CodeContextRetriever")


@dataclass
class RelevantSymbol:
    """Represents a code symbol identified as relevant to the current engineering task."""
    symbol_id: str
    name: str
    qualified_name: str
    symbol_type: str
    file: str
    line: int
    end_line: int
    relevance_score: float
    relevance_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol_id": self.symbol_id,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "symbol_type": self.symbol_type,
            "file": self.file,
            "line": self.line,
            "end_line": self.end_line,
            "relevance_score": round(self.relevance_score, 2),
            "relevance_reasons": list(self.relevance_reasons),
        }


@dataclass
class RelevantFile:
    """Represents a source file selected for code context inclusion."""
    path: str
    relevance_score: float
    symbols: List[str] = field(default_factory=list)
    relationship: str = "direct_target"  # direct_target, imported_dependency, caller_file, test_file, base_class
    content: str = ""
    truncated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "relevance_score": round(self.relevance_score, 2),
            "symbols": list(self.symbols),
            "relationship": self.relationship,
            "content": self.content,
            "truncated": self.truncated,
        }


@dataclass
class CodeContextResult:
    """Encapsulates the retrieved code context, topological dependencies, and token telemetry."""
    task_id: str
    relevant_symbols: List[RelevantSymbol] = field(default_factory=list)
    relevant_files: List[RelevantFile] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    callers: List[str] = field(default_factory=list)
    callees: List[str] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)
    subclasses: List[str] = field(default_factory=list)
    test_files: List[str] = field(default_factory=list)
    token_estimate: int = 0
    truncated: bool = False
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "relevant_symbols": [s.to_dict() for s in self.relevant_symbols],
            "relevant_files": [f.to_dict() for f in self.relevant_files],
            "dependencies": list(self.dependencies),
            "dependents": list(self.dependents),
            "callers": list(self.callers),
            "callees": list(self.callees),
            "base_classes": list(self.base_classes),
            "subclasses": list(self.subclasses),
            "test_files": list(self.test_files),
            "token_estimate": self.token_estimate,
            "truncated": self.truncated,
            "summary": self.summary,
        }


class CodeContextRetriever:
    """
    Code-aware context retrieval engine. Extracts the minimal, highly-relevant subset
    of project source files and symbols for LLM code synthesis without loading full repositories.
    """

    # Relevance Scoring Weights
    WEIGHT_TASK_TEXT = 0.30        # Task title & description token match
    WEIGHT_ESTIMATED_FILES = 0.20  # Task estimated_files match
    WEIGHT_DEPENDENCY = 0.15       # Direct module imports / dependencies
    WEIGHT_CALL_RELATION = 0.10    # Callers and callees
    WEIGHT_INHERITANCE = 0.10      # Base classes, subclasses, interfaces
    WEIGHT_TEST_RELATION = 0.05    # Associated test files
    WEIGHT_TECH_CONTEXT = 0.05     # Tech stack / phase focus keywords
    WEIGHT_DIRECT_BONUS = 0.05     # Exact name or file match bonus

    # Test file discovery patterns
    TEST_FILE_PATTERNS = [
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
        index_path: Union[str, Path] = "memory/code_index.json",
        project_root: Optional[Union[str, Path]] = None,
        max_graph_depth: int = 1,
    ) -> None:
        """
        Initializes the CodeContextRetriever.

        Args:
            symbol_graph: Optional existing SymbolGraph instance.
            index_path: Path to persisted code_index.json.
            project_root: Project root directory for loading file contents.
            max_graph_depth: Maximum graph expansion depth (default: 1 hop).
        """
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd()
        self.index_path = Path(index_path).resolve()
        self.max_graph_depth = max_graph_depth
        self.graph = symbol_graph or self._load_or_empty_graph()

    def retrieve(
        self,
        context: Dict[str, Any],
        task: Union[Task, Dict[str, Any]],
        max_files: int = 15,
        max_symbols: int = 30,
        max_tokens: int = 6000,
    ) -> CodeContextResult:
        """
        Retrieves relevant symbols, files, dependency edges, and tests for the current task.

        Args:
            context: Project context produced by ContextBuilder.
            task: Current target task.
            max_files: Maximum number of relevant files to include (default: 15).
            max_symbols: Maximum number of relevant symbols to track (default: 30).
            max_tokens: Token budget limit for extracted code context (default: 6000).

        Returns:
            Structured CodeContextResult containing symbols, files, graph relations, and token metrics.
        """
        task_id, task_title, task_desc, estimated_files, priority = self._extract_task_signals(task)

        if not self.graph or not self.graph.symbols:
            logger.info("SymbolGraph is empty. Returning empty CodeContextResult.")
            return CodeContextResult(
                task_id=task_id,
                summary="No symbols or indexed codebase available.",
            )

        # 1. Score all symbols in the graph against task signals
        scored_symbols = self._score_symbols(
            task_title=task_title,
            task_desc=task_desc,
            estimated_files=estimated_files,
            context=context,
        )

        # 2. Select top direct symbols
        top_symbols = scored_symbols[:max_symbols]
        direct_files: Set[str] = {s.file for s in top_symbols}
        direct_files.update(self._normalize_file_paths(estimated_files))

        # 3. 1-Hop Graph Expansion
        (
            expanded_files,
            callers,
            callees,
            base_classes,
            subclasses,
            dependencies,
            dependents,
            test_files,
        ) = self._expand_graph(top_symbols, direct_files)

        # 4. Assemble and Rank Relevant Files
        ranked_files = self._rank_files(
            direct_files=direct_files,
            expanded_files=expanded_files,
            test_files=test_files,
            top_symbols=top_symbols,
            max_files=max_files,
        )

        # 5. Extract Code Slices under Token Budget
        relevant_files_with_content, total_tokens, was_truncated = self._assemble_file_contents(
            ranked_files=ranked_files,
            top_symbols=top_symbols,
            max_tokens=max_tokens,
        )

        summary = (
            f"Retrieved {len(top_symbols)} symbols across {len(relevant_files_with_content)} files "
            f"({len(dependencies)} deps, {len(callers)} callers, {len(test_files)} tests, ~{total_tokens} tokens)."
        )

        return CodeContextResult(
            task_id=task_id,
            relevant_symbols=top_symbols,
            relevant_files=relevant_files_with_content,
            dependencies=sorted(list(dependencies)),
            dependents=sorted(list(dependents)),
            callers=sorted(list(callers)),
            callees=sorted(list(callees)),
            base_classes=sorted(list(base_classes)),
            subclasses=sorted(list(subclasses)),
            test_files=sorted(list(test_files)),
            token_estimate=total_tokens,
            truncated=was_truncated,
            summary=summary,
        )

    def refresh_index(self) -> SymbolGraph:
        """Reloads the SymbolGraph from index_path."""
        self.graph = self._load_or_empty_graph()
        return self.graph

    # -------------------------------------------------------------------------
    # Symbol Scoring & Relevance
    # -------------------------------------------------------------------------

    def _score_symbols(
        self,
        task_title: str,
        task_desc: str,
        estimated_files: List[str],
        context: Dict[str, Any],
    ) -> List[RelevantSymbol]:
        """Calculates multi-factor relevance scores for all symbols in the graph."""
        title_tokens = set(self._tokenize(task_title))
        desc_tokens = set(self._tokenize(task_desc))
        task_tokens = title_tokens | desc_tokens
        tech_tokens = set(self._tokenize(str(context.get("technology_stack", ""))))
        phase_tokens = set(self._tokenize(str(context.get("current_phase", {}).get("phase_name", ""))))

        norm_est_files = self._normalize_file_paths(estimated_files)

        results: List[RelevantSymbol] = []

        for sym in self.graph.symbols.values():
            score = 0.0
            reasons: List[str] = []

            sym_name_lower = sym.name.lower()
            sym_qname_lower = sym.qualified_name.lower()
            sym_tokens = set(self._tokenize(f"{sym.name} {sym.qualified_name}"))
            doc_tokens = set(self._tokenize(sym.docstring or ""))

            # 1. Task Text Match (30%)
            text_score = 0.0
            if task_title.lower() in sym_name_lower or sym_name_lower in task_title.lower():
                text_score += 0.60
                reasons.append(f"Title match '{sym.name}'")
            if task_tokens and (sym_tokens & task_tokens):
                overlap = len(sym_tokens & task_tokens) / len(sym_tokens)
                text_score += overlap * 0.40
                reasons.append("Task keyword overlap")
            score += min(text_score, 1.0) * (self.WEIGHT_TASK_TEXT * 100)

            # 2. Estimated Files Match (20%)
            if sym.file in norm_est_files:
                score += self.WEIGHT_ESTIMATED_FILES * 100
                reasons.append(f"Declared in target file '{sym.file}'")

            # 3. Direct Exact Bonus (5%)
            if any(t.lower() == sym_name_lower for t in title_tokens):
                score += self.WEIGHT_DIRECT_BONUS * 100
                reasons.append("Exact symbol name match")

            # 4. Tech / Phase Context Match (5%)
            if (tech_tokens | phase_tokens) & (sym_tokens | doc_tokens):
                score += self.WEIGHT_TECH_CONTEXT * 100
                reasons.append("Technology / Phase context relevance")

            # 5. Test File Match
            if self._is_test_file(sym.file):
                score += self.WEIGHT_TEST_RELATION * 100
                reasons.append("Test verification symbol")

            if score > 0.0:
                results.append(
                    RelevantSymbol(
                        symbol_id=sym.id,
                        name=sym.name,
                        qualified_name=sym.qualified_name,
                        symbol_type=sym.symbol_type,
                        file=sym.file,
                        line=sym.line,
                        end_line=sym.end_line,
                        relevance_score=score,
                        relevance_reasons=reasons,
                    )
                )

        # Sort descending by relevance score
        results.sort(key=lambda s: s.relevance_score, reverse=True)
        return results

    # -------------------------------------------------------------------------
    # 1-Hop Graph Expansion
    # -------------------------------------------------------------------------

    def _expand_graph(
        self,
        top_symbols: List[RelevantSymbol],
        direct_files: Set[str],
    ) -> Tuple[Set[str], Set[str], Set[str], Set[str], Set[str], Set[str], Set[str], Set[str]]:
        """
        Traverses 1-hop graph edges: callers, callees, base classes, subclasses,
        file dependencies, and matching test files without graph explosion.
        """
        expanded_files: Set[str] = set()
        callers: Set[str] = set()
        callees: Set[str] = set()
        base_classes: Set[str] = set()
        subclasses: Set[str] = set()
        dependencies: Set[str] = set()
        dependents: Set[str] = set()
        test_files: Set[str] = set()

        for sym_rel in top_symbols:
            sym = self.graph.symbols.get(sym_rel.symbol_id)
            if not sym:
                continue

            # Callers (who calls this symbol)
            for caller_sym in self.graph.find_callers(sym.name):
                callers.add(caller_sym.qualified_name)
                expanded_files.add(caller_sym.file)

            # Callees (what does this symbol call)
            for callee_sym in self.graph.find_callees(sym.name):
                callees.add(callee_sym.qualified_name)
                expanded_files.add(callee_sym.file)

            # Inheritance (base classes & subclasses)
            for base in sym.inherits:
                base_classes.add(base)
                base_sym = self.graph.find_symbol(base)
                if base_sym:
                    expanded_files.add(base_sym.file)

            for sub in self.graph.find_subclasses(sym.name):
                subclasses.add(sub.qualified_name)
                expanded_files.add(sub.file)

        # File dependencies & reverse dependencies
        for f in direct_files:
            for dep in self.graph.find_dependencies(f):
                dependencies.add(dep)
                expanded_files.add(dep)

            for rev in self.graph.find_dependents(f):
                dependents.add(rev)
                expanded_files.add(rev)

        # Discover test files referencing direct symbols or files
        for f in self.graph.files.keys():
            if self._is_test_file(f):
                test_syms = self.graph.find_file(f)
                test_text = " ".join(s.name + " " + " ".join(s.calls) for s in test_syms).lower()
                for top_s in top_symbols:
                    if top_s.name.lower() in test_text or top_s.file.lower() in f.lower():
                        test_files.add(f)
                        expanded_files.add(f)
                        break

        return (
            expanded_files,
            callers,
            callees,
            base_classes,
            subclasses,
            dependencies,
            dependents,
            test_files,
        )

    # -------------------------------------------------------------------------
    # File Ranking & Token Budgeting
    # -------------------------------------------------------------------------

    def _rank_files(
        self,
        direct_files: Set[str],
        expanded_files: Set[str],
        test_files: Set[str],
        top_symbols: List[RelevantSymbol],
        max_files: int,
    ) -> List[Tuple[str, float, str]]:
        """Scores and ranks files in descending priority order."""
        file_scores: Dict[str, float] = {}
        file_relationships: Dict[str, str] = {}

        # Direct targets: base score 100.0
        for f in direct_files:
            file_scores[f] = 100.0
            file_relationships[f] = "direct_target"

        # Expanded files: base score 50.0
        for f in expanded_files:
            if f not in file_scores:
                if f in test_files:
                    file_scores[f] = 60.0
                    file_relationships[f] = "test_file"
                else:
                    file_scores[f] = 40.0
                    file_relationships[f] = "dependency"

        # Boost score by symbol density
        for s in top_symbols:
            if s.file in file_scores:
                file_scores[s.file] += s.relevance_score * 0.10

        ranked = sorted(file_scores.items(), key=lambda item: item[1], reverse=True)
        return [(f, score, file_relationships.get(f, "dependency")) for f, score in ranked[:max_files]]

    def _assemble_file_contents(
        self,
        ranked_files: List[Tuple[str, float, str]],
        top_symbols: List[RelevantSymbol],
        max_tokens: int,
    ) -> Tuple[List[RelevantFile], int, bool]:
        """
        Extracts source content or focused symbol slices while strictly adhering to max_tokens budget.
        """
        output_files: List[RelevantFile] = []
        current_tokens = 0
        was_truncated = False

        for file_path, score, relationship in ranked_files:
            abs_file = (self.project_root / file_path).resolve()
            if not abs_file.exists() or not abs_file.is_file():
                continue

            try:
                full_content = abs_file.read_text(encoding="utf-8", errors="replace")
            except Exception as err:
                logger.warning(f"Could not read source file {abs_file}: {err}")
                continue

            file_syms = [s for s in top_symbols if s.file == file_path]
            file_sym_names = [s.name for s in file_syms]
            file_tokens = self._estimate_tokens(full_content)

            if current_tokens + file_tokens <= max_tokens:
                # Full file content fits
                output_files.append(
                    RelevantFile(
                        path=file_path,
                        relevance_score=score,
                        symbols=file_sym_names,
                        relationship=relationship,
                        content=full_content,
                        truncated=False,
                    )
                )
                current_tokens += file_tokens
            else:
                # File exceeds remaining token budget: extract focused slice around top symbols
                available_tokens = max(0, max_tokens - current_tokens)
                if available_tokens > 0:
                    max_chars = available_tokens * 4
                    if file_syms and file_syms[0].line > 0:
                        lines = full_content.splitlines(keepends=True)
                        start_idx = max(0, file_syms[0].line - 3)
                        focused_text = "".join(lines[start_idx:])
                        if len(focused_text) > max_chars:
                            focused_text = focused_text[:max_chars]
                        snippet = f"... [Focus: {file_syms[0].qualified_name}] ...\n" + focused_text + "\n... [TRUNCATED] ..."
                    else:
                        snippet = full_content[:max_chars] + "\n... [TRUNCATED: Exceeded token budget] ..."

                    snippet_tokens = self._estimate_tokens(snippet)
                    output_files.append(
                        RelevantFile(
                            path=file_path,
                            relevance_score=score,
                            symbols=file_sym_names,
                            relationship=relationship,
                            content=snippet,
                            truncated=True,
                        )
                    )
                    current_tokens += min(available_tokens, snippet_tokens)
                    was_truncated = True
                else:
                    was_truncated = True
                break

        return output_files, current_tokens, was_truncated

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
        return any(p.search(norm) or p.search(fname) for p in self.TEST_FILE_PATTERNS)

    def _normalize_file_paths(self, paths: List[str]) -> Set[str]:
        """Normalizes list of file paths to forward slashes."""
        return {p.replace("\\", "/").strip() for p in paths if p and p.strip()}

    def _extract_task_signals(self, task: Any) -> Tuple[str, str, str, List[str], int]:
        """Extracts standardized attributes from Task object or dict."""
        if hasattr(task, "id") and hasattr(task, "title"):
            return (
                str(getattr(task, "id", "UNKNOWN-TASK")),
                str(getattr(task, "title", "")),
                str(getattr(task, "description", "")),
                list(getattr(task, "estimated_files", [])),
                int(getattr(task, "priority", 1)),
            )
        if isinstance(task, dict):
            return (
                str(task.get("id", "UNKNOWN-TASK")),
                str(task.get("title", "")),
                str(task.get("description", "")),
                list(task.get("estimated_files", [])),
                int(task.get("priority", 1)),
            )
        return ("UNKNOWN-TASK", str(task), "", [], 1)

    def _tokenize(self, text: str) -> List[str]:
        """Extracts normalized alphanumeric word tokens."""
        return [t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 1]

    def _estimate_tokens(self, text: str) -> int:
        """Deterministic token estimator (1 token ~= 4 chars)."""
        if not text:
            return 0
        return max(1, len(text) // 4)
