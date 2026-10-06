"""
code_context_retriever.py - Code Context Retrieval Engine for AutoDev (v1.6)

Deterministically extracts and optimizes the minimal, high-utility source code snippets
required for a given task before prompting the LLM. Operates completely offline using
SymbolGraph AST indexing, ImpactAnalyzer blast radius telemetry, and token budgeting.
"""

from __future__ import annotations

import logging
import os
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
    from core.impact_analyzer import ImpactReport

from core.symbol_graph import Dependency, Symbol, SymbolGraph, SymbolType, Visibility

logger = logging.getLogger("AutoDev.CodeContextRetriever")


@dataclass
class CodeSnippet:
    """Represents an extracted source code snippet for a specific symbol or file region."""
    file: str
    start_line: int
    end_line: int
    language: str
    symbol: str
    reason: str
    content: str
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "symbol": self.symbol,
            "reason": self.reason,
            "content": self.content,
            "score": round(self.score, 2),
        }


@dataclass
class ContextBundle:
    """Encapsulates optimized snippets, affected files, and token telemetry."""
    snippets: List[CodeSnippet] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    total_tokens: int = 0
    truncated: bool = False
    summary: str = ""

    # Extended telemetry & backward compatibility fields
    task_id: str = ""
    relevant_symbols: List[Any] = field(default_factory=list)
    relevant_files: List[Any] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    callers: List[str] = field(default_factory=list)
    callees: List[str] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)
    subclasses: List[str] = field(default_factory=list)
    test_files: List[str] = field(default_factory=list)
    token_estimate: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snippets": [s.to_dict() for s in self.snippets],
            "files": list(self.files),
            "total_tokens": self.total_tokens,
            "token_estimate": self.total_tokens,
            "truncated": self.truncated,
            "summary": self.summary,
            "task_id": self.task_id,
            "relevant_symbols": [s.to_dict() if hasattr(s, "to_dict") else s for s in self.relevant_symbols],
            "relevant_files": [f.to_dict() if hasattr(f, "to_dict") else f for f in self.relevant_files],
            "dependencies": list(self.dependencies),
            "dependents": list(self.dependents),
            "callers": list(self.callers),
            "callees": list(self.callees),
            "base_classes": list(self.base_classes),
            "subclasses": list(self.subclasses),
            "test_files": list(self.test_files),
        }


# Backward compatibility aliases
RelevantSymbol = CodeSnippet
RelevantFile = CodeSnippet
CodeContextResult = ContextBundle


class CodeContextRetriever:
    """
    Code Context Retrieval Engine.
    Locates, extracts, ranks, and budgets relevant source code snippets for task execution.
    """

    # Language mapping
    EXT_TO_LANG = {
        ".py": "python",
        ".java": "java",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
    }

    def __init__(
        self,
        graph: Optional[SymbolGraph] = None,
        symbol_graph: Optional[SymbolGraph] = None,
        project_root: Optional[Union[str, Path]] = None,
        max_tokens: int = 4000,
        index_path: Union[str, Path] = "memory/code_index.json",
        max_graph_depth: int = 2,
    ) -> None:
        """
        Initializes the CodeContextRetriever.

        Args:
            graph: Optional SymbolGraph instance.
            symbol_graph: Alias for graph (backward compatibility).
            project_root: Project root directory for loading files.
            max_tokens: Default token budget limit (default: 4000).
            index_path: Path to persisted code_index.json.
            max_graph_depth: Max depth for call/inheritance expansion (default: 2).
        """
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd()
        self.index_path = Path(index_path).resolve()
        self.max_tokens = max_tokens
        self.max_graph_depth = max_graph_depth
        self.graph = graph if graph is not None else (symbol_graph or self._load_or_empty_graph())

        # In-memory file cache: path -> (mtime, lines)
        self._file_cache: Dict[str, Tuple[float, List[str]]] = {}

    # -------------------------------------------------------------------------
    # Public Retrieval Pipeline
    # -------------------------------------------------------------------------

    def retrieve(
        self,
        task: Union[Task, Dict[str, Any]],
        impact_report: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
        max_tokens: Optional[int] = None,
        max_files: int = 15,
        max_symbols: int = 30,
    ) -> ContextBundle:
        """
        Retrieves, extracts, ranks, and budgets relevant code snippets for the given task.

        Pipeline:
        1. Extract task signals (title, desc, estimated_files).
        2. Locate initial primary symbols matching task signals or impact report.
        3. Expand related symbols (imports, parent classes, subclasses, callers, callees, helpers).
        4. Extract exact AST/regex code snippets.
        5. Rank snippets by multi-factor score.
        6. Deduplicate overlapping snippets.
        7. Enforce token budget (drop lower-ranked snippets atomically without splitting).
        8. Return structured ContextBundle.

        Args:
            task: Current task object or dictionary.
            impact_report: Optional ImpactReport produced by ImpactAnalyzer.
            context: Project context dictionary.
            max_tokens: Override for token budget limit.
            max_files: Max files to consider.
            max_symbols: Max symbols to consider.

        Returns:
            ContextBundle containing selected snippets and telemetry.
        """
        token_budget = max_tokens if max_tokens is not None else self.max_tokens
        task_id, task_title, task_desc, estimated_files = self._extract_task_signals(task)

        if not self.graph or not self.graph.symbols:
            logger.info("SymbolGraph is empty. Returning empty ContextBundle.")
            return ContextBundle(
                task_id=task_id,
                summary="No indexed symbols available.",
            )

        # 1. Locate primary candidate symbols
        initial_symbols = self._find_primary_symbols(task_title, task_desc, estimated_files, impact_report)

        # If estimated_files are specified, add all symbols in those files
        norm_est_files = {f.replace("\\", "/").strip() for f in estimated_files if f.strip()}
        for f in norm_est_files:
            for s in self.graph.find_file(f):
                if s not in initial_symbols:
                    initial_symbols.append(s)

        # 2. Expand related context (callers, callees, inheritance, interfaces)
        expanded_pairs = self.expand_related_symbols(
            initial_symbols=initial_symbols,
            impact_report=impact_report,
            max_depth=self.max_graph_depth,
        )

        # 3. Extract exact code snippets
        raw_snippets: List[CodeSnippet] = []
        seen_regions: Set[Tuple[str, int, int]] = set()

        for sym, reason, base_score in expanded_pairs:
            snippet = self.extract_symbol(sym.file, sym, reason=reason, score=base_score)
            if snippet:
                region_key = (snippet.file, snippet.start_line, snippet.end_line)
                if region_key not in seen_regions:
                    seen_regions.add(region_key)
                    raw_snippets.append(snippet)

        # If physical files exist in estimated_files but have no parsed symbols, extract top region
        for f in norm_est_files:
            if not any(s.file == f for s in raw_snippets):
                abs_f = (self.project_root / f).resolve()
                if abs_f.exists() and abs_f.is_file():
                    top_snippet = self.extract_file_region(
                        file_path=f,
                        start_line=1,
                        end_line=40,
                        reason=f"Target file declared in task ({f})",
                        symbol_name=Path(f).stem,
                        score=60.0,
                    )
                    if top_snippet:
                        raw_snippets.append(top_snippet)

        # 4. Rank snippets
        ranked_snippets = self.rank_snippets(raw_snippets)

        # 5. Optimize token budget (strictly never split snippets)
        budgeted_snippets, total_tokens, was_truncated = self.optimize_budget(
            snippets=ranked_snippets,
            max_tokens=token_budget,
        )

        # 6. Assemble telemetry & summary
        affected_files = sorted(list({s.file for s in budgeted_snippets}))
        summary = self.summarize(budgeted_snippets, total_tokens, was_truncated)

        # Extract topological relations for backward compatibility
        callers: Set[str] = set()
        callees: Set[str] = set()
        dependencies: Set[str] = set()
        dependents: Set[str] = set()
        base_classes: Set[str] = set()
        subclasses: Set[str] = set()

        for s in initial_symbols:
            for c in self.graph.find_callers(s.name):
                callers.add(c.qualified_name)
            for c in self.graph.find_callees(s.name):
                callees.add(c.qualified_name)
            for b in s.inherits:
                base_classes.add(b)
            for sub in self.graph.find_subclasses(s.name):
                subclasses.add(sub.qualified_name)

        for f in affected_files:
            for dep in self.graph.find_dependencies(f):
                dependencies.add(dep)
            for rev in self.graph.find_dependents(f):
                dependents.add(rev)

        # Discover test files
        test_files = [f for f in affected_files if self._is_test_file(f)]
        for f in self.graph.files.keys():
            if self._is_test_file(f) and f not in test_files:
                for s in initial_symbols:
                    if s.name.lower() in f.lower() or Path(s.file).stem.lower() in f.lower():
                        test_files.append(f)
                        break

        return ContextBundle(
            snippets=budgeted_snippets,
            files=affected_files,
            total_tokens=total_tokens,
            truncated=was_truncated,
            summary=summary,
            task_id=task_id,
            relevant_symbols=budgeted_snippets,
            relevant_files=budgeted_snippets,
            dependencies=sorted(list(dependencies)),
            dependents=sorted(list(dependents)),
            callers=sorted(list(callers)),
            callees=sorted(list(callees)),
            base_classes=sorted(list(base_classes)),
            subclasses=sorted(list(subclasses)),
            test_files=sorted(list(test_files)),
            token_estimate=total_tokens,
        )

    # -------------------------------------------------------------------------
    # Snippet Extraction (AST & Line Bounds)
    # -------------------------------------------------------------------------

    def extract_symbol(
        self,
        file_path: str,
        symbol: Symbol,
        reason: str = "",
        score: float = 0.0,
    ) -> Optional[CodeSnippet]:
        """
        Extracts exact source code lines for a given Symbol from the project filesystem.
        Uses cached file lines to avoid rereading unchanged files.
        """
        lines = self._read_file_lines(file_path)
        if lines is None:
            return None

        total_lines = len(lines)
        if total_lines == 0:
            return None

        start = max(1, symbol.line)
        end = min(total_lines, symbol.end_line if symbol.end_line >= start else start)

        content = "".join(lines[start - 1 : end])
        lang = self.detect_language(file_path)

        return CodeSnippet(
            file=file_path.replace("\\", "/").strip(),
            start_line=start,
            end_line=end,
            language=lang,
            symbol=symbol.qualified_name or symbol.name,
            reason=reason or f"Symbol definition ({symbol.symbol_type})",
            content=content,
            score=score,
        )

    def extract_file_region(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        reason: str = "",
        symbol_name: str = "",
        score: float = 0.0,
    ) -> Optional[CodeSnippet]:
        """
        Extracts a specific line range [start_line, end_line] from a source file.
        """
        lines = self._read_file_lines(file_path)
        if lines is None:
            return None

        total_lines = len(lines)
        if total_lines == 0:
            return None

        start = max(1, min(start_line, total_lines))
        end = max(start, min(end_line, total_lines))

        content = "".join(lines[start - 1 : end])
        lang = self.detect_language(file_path)

        return CodeSnippet(
            file=file_path.replace("\\", "/").strip(),
            start_line=start,
            end_line=end,
            language=lang,
            symbol=symbol_name or f"Region L{start}-L{end}",
            reason=reason or f"Source region L{start}-L{end}",
            content=content,
            score=score,
        )

    # -------------------------------------------------------------------------
    # Related Symbol Expansion
    # -------------------------------------------------------------------------

    def expand_related_symbols(
        self,
        initial_symbols: List[Symbol],
        impact_report: Optional[Any] = None,
        max_depth: int = 2,
    ) -> List[Tuple[Symbol, str, float]]:
        """
        Expands initial symbols to include callers, callees, base classes,
        subclasses, interface definitions, and adjacent methods.
        Returns a list of (Symbol, reason, base_score).
        """
        expanded: List[Tuple[Symbol, str, float]] = []
        seen_symbol_ids: Set[str] = set()

        # 1. Primary Direct Symbols (Score 100.0)
        for sym in initial_symbols:
            if sym.id not in seen_symbol_ids:
                seen_symbol_ids.add(sym.id)
                expanded.append((sym, f"Target symbol: {sym.qualified_name} ({sym.symbol_type})", 100.0))

        # 2. Impacted symbols from ImpactReport
        if impact_report and hasattr(impact_report, "affected_symbols"):
            for s_name in impact_report.affected_symbols:
                s_obj = self.graph.find_symbol(s_name)
                if s_obj and s_obj.id not in seen_symbol_ids:
                    seen_symbol_ids.add(s_obj.id)
                    expanded.append((s_obj, f"Impacted by blast radius: {s_name}", 85.0))

        # 3. Callers & Callees (Score 75.0 / 65.0)
        for sym in initial_symbols:
            # Callers (who invokes this)
            for caller_sym in self.graph.find_callers(sym.name):
                if caller_sym.id not in seen_symbol_ids:
                    seen_symbol_ids.add(caller_sym.id)
                    expanded.append((caller_sym, f"Direct caller of {sym.name}", 75.0))

            # Callees (what does this invoke)
            for callee_sym in self.graph.find_callees(sym.name):
                if callee_sym.id not in seen_symbol_ids:
                    seen_symbol_ids.add(callee_sym.id)
                    expanded.append((callee_sym, f"Helper / callee used by {sym.name}", 65.0))

            # Base classes & Interfaces (Score 70.0)
            for base in sym.inherits:
                base_sym = self.graph.find_symbol(base)
                if base_sym and base_sym.id not in seen_symbol_ids:
                    seen_symbol_ids.add(base_sym.id)
                    expanded.append((base_sym, f"Base class / Interface: {base}", 70.0))

            # Subclasses (Score 60.0)
            for sub_sym in self.graph.find_subclasses(sym.name):
                if sub_sym.id not in seen_symbol_ids:
                    seen_symbol_ids.add(sub_sym.id)
                    expanded.append((sub_sym, f"Subclass of {sym.name}", 60.0))

            # Adjacent methods in same class
            if sym.parent_symbol:
                for sibling in self.graph.find_file(sym.file):
                    if (
                        sibling.parent_symbol == sym.parent_symbol
                        and sibling.id != sym.id
                        and sibling.id not in seen_symbol_ids
                    ):
                        seen_symbol_ids.add(sibling.id)
                        expanded.append((sibling, f"Adjacent method in {sym.parent_symbol}", 50.0))

        return expanded

    # -------------------------------------------------------------------------
    # Ranking & Budget Optimization
    # -------------------------------------------------------------------------

    def rank_snippets(self, snippets: List[CodeSnippet]) -> List[CodeSnippet]:
        """
        Sorts snippets in descending priority order using multi-factor scores.
        """
        return sorted(snippets, key=lambda s: s.score, reverse=True)

    def optimize_budget(
        self,
        snippets: List[CodeSnippet],
        max_tokens: int,
    ) -> Tuple[List[CodeSnippet], int, bool]:
        """
        Selects the highest-ranked snippets that fit strictly within max_tokens.
        Never splits snippets; drops lowest-ranked snippets atomically.
        """
        accepted: List[CodeSnippet] = []
        current_tokens = 0
        truncated = False

        for snip in snippets:
            snip_tokens = self._estimate_tokens(snip.content)
            if current_tokens + snip_tokens <= max_tokens:
                accepted.append(snip)
                current_tokens += snip_tokens
            else:
                truncated = True

        return accepted, current_tokens, truncated

    def summarize(
        self,
        snippets: List[CodeSnippet],
        total_tokens: int,
        truncated: bool,
    ) -> str:
        """
        Generates a concise summary of the retrieved context bundle.
        """
        files_count = len({s.file for s in snippets})
        trunc_msg = " [TRUNCATED to token budget]" if truncated else ""
        return (
            f"Extracted {len(snippets)} exact snippet(s) across {files_count} file(s) "
            f"(~{total_tokens} tokens){trunc_msg}."
        )

    # -------------------------------------------------------------------------
    # Language & File Cache Helpers
    # -------------------------------------------------------------------------

    def detect_language(self, file_path: str) -> str:
        """Determines programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        return self.EXT_TO_LANG.get(ext, "text")

    def _read_file_lines(self, file_path: str) -> Optional[List[str]]:
        """
        Reads lines from file with caching based on os.path.getmtime.
        Avoids repeated disk I/O on unchanged files.
        """
        abs_path = (self.project_root / file_path).resolve()
        if not abs_path.exists() or not abs_path.is_file():
            return None

        try:
            mtime = os.path.getmtime(abs_path)
            if file_path in self._file_cache:
                cached_mtime, cached_lines = self._file_cache[file_path]
                if cached_mtime == mtime:
                    return cached_lines

            content = abs_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines(keepends=True)
            self._file_cache[file_path] = (mtime, lines)
            return lines
        except Exception as err:
            logger.warning(f"Failed to read file {abs_path}: {err}")
            return None

    def _find_primary_symbols(
        self,
        task_title: str,
        task_desc: str,
        estimated_files: List[str],
        impact_report: Optional[Any],
    ) -> List[Symbol]:
        """Locates candidate primary symbols matching task title, description, or files."""
        title_tokens = set(self._tokenize(task_title))
        desc_tokens = set(self._tokenize(task_desc))
        task_tokens = title_tokens | desc_tokens
        norm_est_files = {f.replace("\\", "/").strip() for f in estimated_files if f.strip()}

        candidates: List[Symbol] = []
        seen_ids: Set[str] = set()

        for sym in self.graph.symbols.values():
            sym_name_lower = sym.name.lower()
            sym_qname_lower = sym.qualified_name.lower()

            is_match = False
            # Title exact or substring match
            if any(t == sym_name_lower for t in title_tokens):
                is_match = True
            elif task_title.lower() in sym_name_lower or sym_name_lower in task_title.lower():
                is_match = True
            elif sym.file in norm_est_files:
                is_match = True
            elif any(t in sym_qname_lower for t in title_tokens if len(t) > 2):
                is_match = True

            if is_match and sym.id not in seen_ids:
                seen_ids.add(sym.id)
                candidates.append(sym)

        return candidates

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

    def _tokenize(self, text: str) -> List[str]:
        """Extracts normalized alphanumeric word tokens."""
        return [t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 1]

    def _estimate_tokens(self, text: str) -> int:
        """Deterministic token estimator (1 token ~= 4 chars)."""
        if not text:
            return 0
        return max(1, len(text) // 4)
