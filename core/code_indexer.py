"""
code_indexer.py - Source Code Indexer & Symbol Graph Generator for AutoDev (v1.4)

Performs deterministic, AST/regex-based static analysis across Python, Java, JavaScript,
and TypeScript codebases to construct searchable symbol graphs, call graphs, inheritance trees,
and file dependency topologies without calling external LLMs or vector databases.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Ensure project root is available on sys.path for direct execution
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.symbol_graph import (
    Dependency,
    IndexStatistics,
    Reference,
    Symbol,
    SymbolGraph,
    SymbolType,
    Visibility,
)

logger = logging.getLogger("AutoDev.CodeIndexer")


class CodeIndexer:
    """
    Scans project source files, parses AST and symbol declarations, builds dependency
    graphs, and provides incremental indexing with SHA256 caching.
    """

    SUPPORTED_EXTENSIONS: Dict[str, str] = {
        ".py": "python",
        ".java": "java",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
    }

    IGNORE_DIRS: Set[str] = {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "env",
        ".pytest_cache",
        "dist",
        "build",
        "target",
        ".idea",
        ".vscode",
        ".gemini",
        "brain",
    }

    DEFAULT_OUTPUT_PATH = Path("memory/code_index.json")

    def __init__(
        self,
        project_root: Optional[Union[str, Path]] = None,
        output_path: Union[str, Path] = DEFAULT_OUTPUT_PATH,
        auto_load: bool = True,
    ) -> None:
        """
        Initializes the CodeIndexer.

        Args:
            project_root: Root directory of the target project to index.
            output_path: Path where memory/code_index.json is persisted.
            auto_load: If True, attempts to load existing index from output_path.
        """
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd()
        self.output_path = Path(output_path).resolve()
        self.graph = SymbolGraph()

        if auto_load and self.output_path.exists():
            try:
                self.load_index(self.output_path)
            except Exception as err:
                logger.warning(f"Could not load existing index from {self.output_path}: {err}. Starting fresh.")

    # -------------------------------------------------------------------------
    # Indexing Lifecycle
    # -------------------------------------------------------------------------

    def index_project(self, force_reindex: bool = False) -> SymbolGraph:
        """
        Scans all supported source files in the project root, incrementally parses
        modified or newly added files, purges deleted files, and persists the graph.

        Args:
            force_reindex: If True, ignores cached hashes and re-parses everything.

        Returns:
            Populated SymbolGraph instance.
        """
        if not self.project_root.exists():
            logger.warning(f"Project root {self.project_root} does not exist.")
            return self.graph

        discovered_files: Dict[str, Path] = {}
        for root, dirs, files in os.walk(self.project_root):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS and not d.startswith(".")]

            for fname in files:
                ext = Path(fname).suffix.lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    abs_path = Path(root) / fname
                    rel_path = self._get_relative_path(abs_path)
                    discovered_files[rel_path] = abs_path

        # 1. Clean up deleted files from graph
        existing_indexed_files = list(self.graph.file_hashes.keys())
        for old_rel_file in existing_indexed_files:
            if old_rel_file not in discovered_files:
                logger.info(f"Removing deleted file from index: {old_rel_file}")
                self.graph.remove_file_symbols(old_rel_file)

        # 2. Parse modified and newly added files
        parsed_count = 0
        for rel_path, abs_path in sorted(discovered_files.items()):
            try:
                content = abs_path.read_text(encoding="utf-8", errors="replace")
                content_hash = self._compute_hash(content)

                cached_hash = self.graph.file_hashes.get(rel_path)
                if not force_reindex and cached_hash == content_hash:
                    continue  # Unchanged file

                # Remove old file symbols prior to re-indexing
                if cached_hash:
                    self.graph.remove_file_symbols(rel_path)

                ext = abs_path.suffix.lower()
                language = self.SUPPORTED_EXTENSIONS[ext]

                self.index_file(rel_path, content=content, language=language)
                self.graph.file_hashes[rel_path] = content_hash
                parsed_count += 1

            except Exception as err:
                logger.error(f"Failed to index file {rel_path}: {err}", exc_info=True)

        # 3. Post-process call graph and references
        self._resolve_cross_references()

        # 4. Save updated graph
        self.save_index()
        logger.info(
            f"Indexing complete. Parsed {parsed_count} modified/new files. "
            f"Total: {len(self.graph.symbols)} symbols across {len(self.graph.files)} files."
        )
        return self.graph

    def index_file(
        self,
        file_path: Union[str, Path],
        content: Optional[str] = None,
        language: Optional[str] = None,
    ) -> List[Symbol]:
        """
        Parses an individual source file and adds its symbols and dependencies to the graph.

        Args:
            file_path: Relative or absolute path to the file.
            content: Optional source content string (read from disk if omitted).
            language: Optional language name (inferred from extension if omitted).

        Returns:
            List of generated Symbol instances for the file.
        """
        norm_path = str(file_path).replace("\\", "/").strip()
        abs_path = (self.project_root / norm_path).resolve() if not Path(norm_path).is_absolute() else Path(norm_path)

        if content is None:
            if not abs_path.exists():
                raise FileNotFoundError(f"File not found: {abs_path}")
            content = abs_path.read_text(encoding="utf-8", errors="replace")

        rel_path = self._get_relative_path(abs_path)
        ext = abs_path.suffix.lower()
        resolved_lang = language or self.SUPPORTED_EXTENSIONS.get(ext, "python")

        symbols: List[Symbol] = []

        if resolved_lang == "python":
            symbols = self._parse_python(rel_path, content)
        elif resolved_lang == "java":
            symbols = self._parse_java(rel_path, content)
        elif resolved_lang in ("javascript", "typescript"):
            symbols = self._parse_js_ts(rel_path, content, resolved_lang)
        else:
            logger.warning(f"Unsupported language '{resolved_lang}' for file {rel_path}")

        for sym in symbols:
            self.graph.add_symbol(sym)

        return symbols

    # -------------------------------------------------------------------------
    # Python Parser (AST-based)
    # -------------------------------------------------------------------------

    def _parse_python(self, file_path: str, content: str) -> List[Symbol]:
        """Parses Python source code using Python's standard `ast` library."""
        symbols: List[Symbol] = []
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError as err:
            logger.warning(f"Python SyntaxError in {file_path}:{err.lineno}: {err.msg}")
            return symbols

        lines = content.splitlines()

        # 1. Collect module-level imports & dependencies
        module_imports: List[str] = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_imports.append(alias.name)
                    self.graph.add_dependency(
                        Dependency(
                            source_file=file_path,
                            target_file=alias.name.replace(".", "/") + ".py",
                            imported_symbols=[alias.name],
                            raw_import_statement=f"import {alias.name}",
                            line=node.lineno,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                sym_names = [a.name for a in node.names]
                import_stmt = f"from {mod} import {', '.join(sym_names)}"
                module_imports.append(import_stmt)
                target_rel = mod.replace(".", "/") + ".py"
                self.graph.add_dependency(
                    Dependency(
                        source_file=file_path,
                        target_file=target_rel,
                        imported_symbols=sym_names,
                        raw_import_statement=import_stmt,
                        line=node.lineno,
                    )
                )

        # 2. Walk AST definitions
        class PythonVisitor(ast.NodeVisitor):
            def __init__(self, outer: CodeIndexer):
                self.outer = outer
                self.scope_stack: List[str] = []
                self.current_class: Optional[str] = None

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                qname = ".".join(self.scope_stack + [node.name]) if self.scope_stack else node.name
                parent = self.scope_stack[-1] if self.scope_stack else None

                bases = [ast.unparse(b) for b in node.bases]
                doc = ast.get_docstring(node)
                decorators = [ast.unparse(d) for d in node.decorator_list]
                vis = Visibility.PRIVATE if node.name.startswith("_") and not node.name.startswith("__") else Visibility.PUBLIC

                sym = Symbol(
                    id=f"{file_path}:{qname}",
                    name=node.name,
                    qualified_name=qname,
                    symbol_type=SymbolType.CLASS,
                    language="python",
                    file=file_path,
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    parent_symbol=parent,
                    visibility=vis,
                    docstring=doc,
                    signature=f"class {node.name}({', '.join(bases)}):",
                    imports=list(module_imports),
                    inherits=bases,
                    decorators=decorators,
                    hash=self.outer._compute_hash(ast.unparse(node)),
                )
                symbols.append(sym)

                prev_class = self.current_class
                self.current_class = qname
                self.scope_stack.append(node.name)
                self.generic_visit(node)
                self.scope_stack.pop()
                self.current_class = prev_class

            def visit_FunctionDef(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> None:
                self._handle_function(node, is_async=False)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._handle_function(node, is_async=True)

            def _handle_function(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef], is_async: bool) -> None:
                qname = ".".join(self.scope_stack + [node.name]) if self.scope_stack else node.name
                parent = self.scope_stack[-1] if self.scope_stack else None

                # Determine symbol type
                if self.current_class:
                    stype = SymbolType.CONSTRUCTOR if node.name == "__init__" else SymbolType.METHOD
                else:
                    stype = SymbolType.FUNCTION

                doc = ast.get_docstring(node)
                decorators = [ast.unparse(d) for d in node.decorator_list]
                vis = Visibility.PRIVATE if node.name.startswith("_") and not node.name.startswith("__") else Visibility.PUBLIC

                # Collect calls inside function
                calls: List[str] = []
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        call_name = ast.unparse(sub.func)
                        calls.append(call_name)

                # Signature
                try:
                    args_unparsed = ast.unparse(node.args)
                    async_prefix = "async " if is_async else ""
                    ret_ann = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                    sig = f"{async_prefix}def {node.name}({args_unparsed}){ret_ann}"
                except Exception:
                    sig = f"def {node.name}(...)"

                sym = Symbol(
                    id=f"{file_path}:{qname}",
                    name=node.name,
                    qualified_name=qname,
                    symbol_type=stype,
                    language="python",
                    file=file_path,
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    parent_symbol=parent,
                    visibility=vis,
                    docstring=doc,
                    signature=sig,
                    imports=list(module_imports),
                    calls=calls,
                    decorators=decorators,
                    hash=self.outer._compute_hash(ast.unparse(node)),
                )
                symbols.append(sym)

                self.scope_stack.append(node.name)
                self.generic_visit(node)
                self.scope_stack.pop()

            def visit_Assign(self, node: ast.Assign) -> None:
                if not self.scope_stack:  # Module-level variable / constant
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            is_const = target.id.isupper()
                            sym = Symbol(
                                id=f"{file_path}:{target.id}",
                                name=target.id,
                                qualified_name=target.id,
                                symbol_type=SymbolType.CONSTANT if is_const else SymbolType.VARIABLE,
                                language="python",
                                file=file_path,
                                line=node.lineno,
                                end_line=node.end_lineno or node.lineno,
                                parent_symbol=None,
                                visibility=Visibility.PUBLIC if not target.id.startswith("_") else Visibility.PRIVATE,
                                signature=f"{target.id} = {ast.unparse(node.value)[:60]}",
                            )
                            symbols.append(sym)

        visitor = PythonVisitor(self)
        visitor.visit(tree)
        return symbols

    # -------------------------------------------------------------------------
    # Java Parser
    # -------------------------------------------------------------------------

    def _parse_java(self, file_path: str, content: str) -> List[Symbol]:
        """Parses Java source code using pattern matching and token structure."""
        symbols: List[Symbol] = []
        lines = content.splitlines()

        # 1. Imports & Package
        package_name = ""
        pkg_match = re.search(r"^\s*package\s+([a-zA-Z0-9_.]+)\s*;", content, re.MULTILINE)
        if pkg_match:
            package_name = pkg_match.group(1)

        imports: List[str] = []
        for imp_match in re.finditer(r"^\s*import\s+(?:static\s+)?([a-zA-Z0-9_.*]+)\s*;", content, re.MULTILINE):
            imp_target = imp_match.group(1)
            imports.append(imp_target)
            target_file = imp_target.replace(".", "/") + ".java"
            self.graph.add_dependency(
                Dependency(
                    source_file=file_path,
                    target_file=target_file,
                    imported_symbols=[imp_target.split(".")[-1]],
                    raw_import_statement=imp_match.group(0),
                    line=self._get_line_number(content, imp_match.start()),
                )
            )

        # 2. Class / Interface / Enum pattern
        type_pattern = re.compile(
            r"(?:\/\*\*[\s\S]*?\*\/\s*)?"
            r"((?:@\w+(?:\([^)]*\))?\s*)*)"
            r"(public|protected|private)?\s*(?:static\s+)?(?:final\s+)?(?:abstract\s+)?"
            r"(class|interface|enum|record)\s+([A-Za-z0-9_]+)"
            r"(?:<[^>]+>)?"
            r"(?:\s+extends\s+([A-Za-z0-9_., <>]+))?"
            r"(?:\s+implements\s+([A-Za-z0-9_., <>]+))?",
            re.MULTILINE,
        )

        current_class: Optional[str] = None
        for match in type_pattern.finditer(content):
            annotations_str, vis, kind, type_name, extends_str, implements_str = match.groups()
            line_no = self._get_line_number(content, match.start())
            qname = f"{package_name}.{type_name}" if package_name else type_name

            stype = SymbolType.CLASS
            if kind == "interface":
                stype = SymbolType.INTERFACE
            elif kind == "enum":
                stype = SymbolType.ENUM

            bases = [b.strip() for b in extends_str.split(",") if b.strip()] if extends_str else []
            ifaces = [i.strip() for i in implements_str.split(",") if i.strip()] if implements_str else []
            annos = re.findall(r"@\w+", annotations_str) if annotations_str else []

            sym = Symbol(
                id=f"{file_path}:{qname}",
                name=type_name,
                qualified_name=qname,
                symbol_type=stype,
                language="java",
                file=file_path,
                line=line_no,
                end_line=line_no,
                visibility=vis or Visibility.PUBLIC,
                signature=f"{kind} {type_name}",
                imports=list(imports),
                inherits=bases,
                implements=ifaces,
                decorators=annos,
            )
            symbols.append(sym)
            current_class = type_name

        # 3. Methods & Constructors pattern
        method_pattern = re.compile(
            r"(?:\/\*\*([\s\S]*?)\*\/\s*)?"
            r"((?:@\w+(?:\([^)]*\))?\s*)*)"
            r"(public|protected|private)?\s*(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:abstract\s+)?"
            r"(?:<[A-Za-z0-9_, ]+>\s+)?"
            r"([A-Za-z0-9_<>[\]]+)\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)\s*(?:throws\s+[A-Za-z0-9_., ]+)?\s*\{",
            re.MULTILINE,
        )

        for match in method_pattern.finditer(content):
            doc, annotations_str, vis, ret_type, method_name, params = match.groups()
            if method_name in ("if", "for", "while", "switch", "catch"):
                continue

            line_no = self._get_line_number(content, match.start())
            parent = current_class or package_name
            qname = f"{parent}.{method_name}" if parent else method_name

            is_constructor = (current_class and method_name == current_class)
            stype = SymbolType.CONSTRUCTOR if is_constructor else SymbolType.METHOD
            annos = re.findall(r"@\w+", annotations_str) if annotations_str else []

            sym = Symbol(
                id=f"{file_path}:{qname}",
                name=method_name,
                qualified_name=qname,
                symbol_type=stype,
                language="java",
                file=file_path,
                line=line_no,
                end_line=line_no,
                parent_symbol=parent,
                visibility=vis or Visibility.PUBLIC,
                docstring=doc.strip() if doc else None,
                signature=f"{ret_type} {method_name}({params})",
                imports=list(imports),
                decorators=annos,
            )
            symbols.append(sym)

        return symbols

    # -------------------------------------------------------------------------
    # JavaScript & TypeScript Parser
    # -------------------------------------------------------------------------

    def _parse_js_ts(self, file_path: str, content: str, language: str) -> List[Symbol]:
        """Parses JavaScript and TypeScript source files."""
        symbols: List[Symbol] = []

        # 1. Imports
        imports: List[str] = []
        import_pattern = re.compile(
            r"^\s*import\s+(?:(?:\{([^}]+)\})|([A-Za-z0-9_*]+))\s+from\s+['\"]([^'\"]+)['\"]",
            re.MULTILINE,
        )
        for match in import_pattern.finditer(content):
            named, default_sym, mod_path = match.groups()
            syms = [s.strip() for s in named.split(",") if s.strip()] if named else ([default_sym] if default_sym else [])
            imports.append(f"import from {mod_path}")

            target_file = mod_path if mod_path.endswith((".js", ".ts", ".jsx", ".tsx")) else f"{mod_path}.{ 'ts' if language == 'typescript' else 'js' }"
            self.graph.add_dependency(
                Dependency(
                    source_file=file_path,
                    target_file=target_file,
                    imported_symbols=syms,
                    raw_import_statement=match.group(0),
                    line=self._get_line_number(content, match.start()),
                )
            )

        # 2. Class, Interface, Enum patterns
        class_pattern = re.compile(
            r"(?:\/\*\*([\s\S]*?)\*\/\s*)?"
            r"((?:@\w+(?:\([^)]*\))?\s*)*)"
            r"(?:export\s+)?(?:default\s+)?(class|interface|enum)\s+([A-Za-z0-9_]+)"
            r"(?:\s+extends\s+([A-Za-z0-9_., <>]+))?"
            r"(?:\s+implements\s+([A-Za-z0-9_., <>]+))?",
            re.MULTILINE,
        )

        current_class: Optional[str] = None
        for match in class_pattern.finditer(content):
            doc, annos_str, kind, name, extends_str, implements_str = match.groups()
            line_no = self._get_line_number(content, match.start())

            stype = SymbolType.CLASS
            if kind == "interface":
                stype = SymbolType.INTERFACE
            elif kind == "enum":
                stype = SymbolType.ENUM

            bases = [b.strip() for b in extends_str.split(",") if b.strip()] if extends_str else []
            ifaces = [i.strip() for i in implements_str.split(",") if i.strip()] if implements_str else []
            annos = re.findall(r"@\w+", annos_str) if annos_str else []

            sym = Symbol(
                id=f"{file_path}:{name}",
                name=name,
                qualified_name=name,
                symbol_type=stype,
                language=language,
                file=file_path,
                line=line_no,
                end_line=line_no,
                docstring=doc.strip() if doc else None,
                signature=f"{kind} {name}",
                imports=list(imports),
                inherits=bases,
                implements=ifaces,
                decorators=annos,
            )
            symbols.append(sym)
            current_class = name

        # 3. Function & Method patterns
        func_pattern = re.compile(
            r"(?:\/\*\*([\s\S]*?)\*\/\s*)?"
            r"(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)",
            re.MULTILINE,
        )
        for match in func_pattern.finditer(content):
            doc, fname, params = match.groups()
            line_no = self._get_line_number(content, match.start())
            sym = Symbol(
                id=f"{file_path}:{fname}",
                name=fname,
                qualified_name=fname,
                symbol_type=SymbolType.FUNCTION,
                language=language,
                file=file_path,
                line=line_no,
                end_line=line_no,
                docstring=doc.strip() if doc else None,
                signature=f"function {fname}({params})",
                imports=list(imports),
            )
            symbols.append(sym)

        # 4. Arrow function assignments (const foo = () => ...)
        arrow_pattern = re.compile(
            r"(?:export\s+)?const\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*[^=]+)?\s*=>",
            re.MULTILINE,
        )
        for match in arrow_pattern.finditer(content):
            fname, params = match.groups()
            line_no = self._get_line_number(content, match.start())
            sym = Symbol(
                id=f"{file_path}:{fname}",
                name=fname,
                qualified_name=fname,
                symbol_type=SymbolType.FUNCTION,
                language=language,
                file=file_path,
                line=line_no,
                end_line=line_no,
                signature=f"const {fname} = ({params}) =>",
                imports=list(imports),
            )
            symbols.append(sym)

        return symbols

    # -------------------------------------------------------------------------
    # Graph Post-Processing
    # -------------------------------------------------------------------------

    def _resolve_cross_references(self) -> None:
        """
        Connects caller-callee links and reverse references across symbols.
        """
        all_symbol_names = {s.name: s.id for s in self.graph.symbols.values()}

        for sym in self.graph.symbols.values():
            # Populate called_by links
            for callee_name in sym.calls:
                # Direct name match or attribute match
                short_callee = callee_name.split(".")[-1]
                if short_callee in all_symbol_names:
                    target_id = all_symbol_names[short_callee]
                    target_sym = self.graph.symbols.get(target_id)
                    if target_sym and sym.qualified_name not in target_sym.called_by:
                        target_sym.called_by.append(sym.qualified_name)

    # -------------------------------------------------------------------------
    # Persistence & Helpers
    # -------------------------------------------------------------------------

    def get_graph(self) -> SymbolGraph:
        """Returns the active SymbolGraph instance."""
        return self.graph

    def statistics(self) -> IndexStatistics:
        """Computes metrics from the current graph."""
        return self.graph.statistics()

    def save_index(self, output_path: Optional[Union[str, Path]] = None) -> Path:
        """Atomically persists the index to JSON."""
        target = Path(output_path).resolve() if output_path else self.output_path
        target.parent.mkdir(parents=True, exist_ok=True)
        self.graph.export_json(filepath=target)
        return target

    def load_index(self, input_path: Optional[Union[str, Path]] = None) -> SymbolGraph:
        """Loads index from JSON file."""
        target = Path(input_path).resolve() if input_path else self.output_path
        if not target.exists():
            raise FileNotFoundError(f"Code index file not found: {target}")
        self.graph.import_json(target)
        return self.graph

    def _get_relative_path(self, path: Path) -> str:
        """Normalizes path relative to project root with forward slashes."""
        try:
            rel = path.resolve().relative_to(self.project_root)
            return str(rel).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    def _compute_hash(self, content: str) -> str:
        """Computes SHA256 hex digest of string content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _get_line_number(self, text: str, char_index: int) -> int:
        """Calculates 1-indexed line number from character offset."""
        return text.count("\n", 0, char_index) + 1
