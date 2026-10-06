"""
symbol_graph.py - Searchable Symbol Graph for AutoDev Code Intelligence (v1.4)

Defines data models and graph data structures for software symbols, callers, callees,
inheritance hierarchies, interface implementations, and inter-file dependency topologies.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("AutoDev.SymbolGraph")


class SymbolType:
    """Standardized symbol types recognized by AutoDev."""
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    CONSTRUCTOR = "constructor"
    INTERFACE = "interface"
    ENUM = "enum"
    VARIABLE = "variable"
    CONSTANT = "constant"
    DECORATOR = "decorator"
    ANNOTATION = "annotation"
    MODULE = "module"

    ALL_TYPES = {
        CLASS,
        FUNCTION,
        METHOD,
        CONSTRUCTOR,
        INTERFACE,
        ENUM,
        VARIABLE,
        CONSTANT,
        DECORATOR,
        ANNOTATION,
        MODULE,
    }


class Visibility:
    """Symbol visibility scope."""
    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"
    INTERNAL = "internal"


@dataclass
class Reference:
    """Represents a directional symbol or token reference."""
    source_symbol: str
    target_symbol: str
    reference_type: str  # "call", "inheritance", "implements", "import", "type_usage"
    file: str
    line: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Reference:
        return cls(
            source_symbol=data.get("source_symbol", ""),
            target_symbol=data.get("target_symbol", ""),
            reference_type=data.get("reference_type", "reference"),
            file=data.get("file", ""),
            line=int(data.get("line", 1)),
        )


@dataclass
class Dependency:
    """Represents an inter-file dependency relationship."""
    source_file: str = ""
    target_file: str = ""
    imported_symbols: List[str] = field(default_factory=list)
    raw_import_statement: str = ""
    line: int = 1
    source: str = ""
    target: str = ""
    dependency_type: str = "import"

    def __post_init__(self) -> None:
        if not self.source_file and self.source:
            self.source_file = self.source
        if not self.target_file and self.target:
            self.target_file = self.target
        if not self.source and self.source_file:
            self.source = self.source_file
        if not self.target and self.target_file:
            self.target = self.target_file

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Dependency:
        return cls(
            source_file=data.get("source_file", data.get("source", "")),
            target_file=data.get("target_file", data.get("target", "")),
            imported_symbols=list(data.get("imported_symbols", [])),
            raw_import_statement=data.get("raw_import_statement", ""),
            line=int(data.get("line", 1)),
            source=data.get("source", data.get("source_file", "")),
            target=data.get("target", data.get("target_file", "")),
            dependency_type=data.get("dependency_type", "import"),
        )


@dataclass
class Symbol:
    """
    Represents a code symbol (class, function, method, interface, enum, etc.).
    """
    id: str = ""
    name: str = ""
    qualified_name: str = ""
    symbol_type: str = SymbolType.FUNCTION
    language: str = "python"
    file: str = ""
    line: int = 1
    end_line: int = 1
    parent_symbol: Optional[str] = None
    visibility: str = Visibility.PUBLIC
    docstring: Optional[str] = None
    signature: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)
    called_by: List[str] = field(default_factory=list)
    inherits: List[str] = field(default_factory=list)
    implements: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    hash: str = ""
    dependencies: List[Dependency] = field(default_factory=list)
    file_path: str = ""
    line_start: int = 1
    line_end: int = 1

    def __post_init__(self) -> None:
        if not self.file and self.file_path:
            self.file = self.file_path
        elif not self.file_path and self.file:
            self.file_path = self.file
        if self.line_start != 1 and self.line == 1:
            self.line = self.line_start
        elif self.line != 1 and self.line_start == 1:
            self.line_start = self.line
        if self.line_end != 1 and self.end_line == 1:
            self.end_line = self.line_end
        elif self.end_line != 1 and self.line_end == 1:
            self.line_end = self.end_line
        if not self.qualified_name and self.name:
            self.qualified_name = self.name
        if not self.id:
            self.id = f"{self.file}::{self.qualified_name or self.name}"

    def to_dict(self) -> Dict[str, Any]:
        """Converts Symbol to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "symbol_type": self.symbol_type,
            "language": self.language,
            "file": self.file,
            "line": self.line,
            "end_line": self.end_line,
            "parent_symbol": self.parent_symbol,
            "visibility": self.visibility,
            "docstring": self.docstring,
            "signature": self.signature,
            "imports": list(self.imports),
            "calls": list(self.calls),
            "called_by": list(self.called_by),
            "inherits": list(self.inherits),
            "implements": list(self.implements),
            "references": list(self.references),
            "decorators": list(self.decorators),
            "hash": self.hash,
            "file_path": self.file_path or self.file,
            "line_start": self.line_start,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Symbol:
        """Constructs Symbol from dictionary representation."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            qualified_name=data.get("qualified_name", data.get("name", "")),
            symbol_type=data.get("symbol_type", SymbolType.FUNCTION),
            language=data.get("language", "python"),
            file=data.get("file", data.get("file_path", "")),
            line=int(data.get("line", data.get("line_start", 1))),
            end_line=int(data.get("end_line", data.get("line", 1))),
            parent_symbol=data.get("parent_symbol"),
            visibility=data.get("visibility", Visibility.PUBLIC),
            docstring=data.get("docstring"),
            signature=data.get("signature"),
            imports=list(data.get("imports", [])),
            calls=list(data.get("calls", [])),
            called_by=list(data.get("called_by", [])),
            inherits=list(data.get("inherits", [])),
            implements=list(data.get("implements", [])),
            references=list(data.get("references", [])),
            decorators=list(data.get("decorators", [])),
            hash=data.get("hash", ""),
            file_path=data.get("file_path", data.get("file", "")),
            line_start=int(data.get("line_start", data.get("line", 1))),
        )


@dataclass
class IndexStatistics:
    """Aggregated metrics and code telemetry across the codebase."""
    total_files: int
    total_symbols: int
    classes: int
    functions: int
    methods: int
    interfaces: int
    enums: int
    imports: int
    dependencies: int
    largest_file: Optional[str] = None
    average_symbols_per_file: float = 0.0
    languages: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_files": self.total_files,
            "total_symbols": self.total_symbols,
            "classes": self.classes,
            "functions": self.functions,
            "methods": self.methods,
            "interfaces": self.interfaces,
            "enums": self.enums,
            "imports": self.imports,
            "dependencies": self.dependencies,
            "largest_file": self.largest_file,
            "average_symbols_per_file": round(self.average_symbols_per_file, 2),
            "languages": self.languages,
        }


class SymbolGraph:
    """
    Searchable Symbol Graph and dependency topology model.
    Maintains forward and reverse mappings for call graphs, inheritance hierarchies,
    interface implementations, and inter-file imports.
    """

    def __init__(self) -> None:
        self.symbols: Dict[str, Symbol] = {}  # symbol_id -> Symbol
        self.files: Dict[str, List[str]] = defaultdict(list)  # file_path -> [symbol_ids]
        self.file_hashes: Dict[str, str] = {}  # file_path -> SHA256 hash
        self.dependencies: List[Dependency] = []

        # Graph Adjacency Lists
        self.file_dependency_graph: Dict[str, Set[str]] = defaultdict(set)  # source_file -> target_files
        self.file_reverse_dependencies: Dict[str, Set[str]] = defaultdict(set)  # target_file -> source_files
        self.call_graph: Dict[str, Set[str]] = defaultdict(set)  # caller_id/name -> callee_names
        self.reverse_call_graph: Dict[str, Set[str]] = defaultdict(set)  # callee_name -> caller_ids
        self.inheritance_graph: Dict[str, Set[str]] = defaultdict(set)  # subclass -> base_classes
        self.subclass_graph: Dict[str, Set[str]] = defaultdict(set)  # base_class -> subclasses
        self.implementation_graph: Dict[str, Set[str]] = defaultdict(set)  # class -> interfaces
        self.interface_implementers: Dict[str, Set[str]] = defaultdict(set)  # interface -> classes

    # -------------------------------------------------------------------------
    # Symbol & Dependency Mutations
    # -------------------------------------------------------------------------

    def add_symbol(self, symbol: Symbol) -> None:
        """
        Registers a symbol and updates graph relations.
        """
        self.symbols[symbol.id] = symbol
        if symbol.id not in self.files[symbol.file]:
            self.files[symbol.file].append(symbol.id)

        # Update inheritance graph
        for base in symbol.inherits:
            self.add_inheritance_edge(symbol.qualified_name, base)
            self.add_inheritance_edge(symbol.name, base)

        # Update interface implementation graph
        for iface in symbol.implements:
            self.implementation_graph[symbol.qualified_name].add(iface)
            self.interface_implementers[iface].add(symbol.qualified_name)

        # Update call graph
        for callee in symbol.calls:
            self.add_call_edge(symbol.id, callee)

    def remove_symbol(self, symbol_id: str) -> None:
        """Removes a symbol from the graph and cleans its edges."""
        if symbol_id not in self.symbols:
            return
        sym = self.symbols.pop(symbol_id)
        if sym.file in self.files and symbol_id in self.files[sym.file]:
            self.files[sym.file].remove(symbol_id)

        # Clean edges
        self.call_graph.pop(symbol_id, None)

    def remove_file_symbols(self, file_path: str) -> None:
        """Removes all symbols and dependencies associated with a file."""
        norm_file = file_path.replace("\\", "/").strip()
        symbol_ids = list(self.files.get(norm_file, []))
        for sym_id in symbol_ids:
            self.remove_symbol(sym_id)

        self.files.pop(norm_file, None)
        self.file_hashes.pop(norm_file, None)

        # Remove file dependencies
        self.dependencies = [d for d in self.dependencies if d.source_file != norm_file]
        targets = self.file_dependency_graph.pop(norm_file, set())
        for tgt in targets:
            self.file_reverse_dependencies[tgt].discard(norm_file)

    def add_dependency(self, dependency: Dependency) -> None:
        """Registers an inter-file dependency."""
        self.dependencies.append(dependency)
        src = dependency.source_file.replace("\\", "/").strip()
        tgt = dependency.target_file.replace("\\", "/").strip()
        self.file_dependency_graph[src].add(tgt)
        self.file_reverse_dependencies[tgt].add(src)

    def add_call_edge(self, caller_id: str, callee_name_or_id: str) -> None:
        """Adds a call relationship edge."""
        self.call_graph[caller_id].add(callee_name_or_id)
        self.reverse_call_graph[callee_name_or_id].add(caller_id)

    def add_inheritance_edge(self, subclass: str, base_class: str) -> None:
        """Adds an inheritance relationship edge."""
        self.inheritance_graph[subclass].add(base_class)
        self.subclass_graph[base_class].add(subclass)

    # -------------------------------------------------------------------------
    # Queries & Graph Traversals
    # -------------------------------------------------------------------------

    def find_symbol(self, name_or_id: str) -> Optional[Symbol]:
        """
        Finds a symbol by its unique ID, qualified name, or short name.
        """
        if name_or_id in self.symbols:
            return self.symbols[name_or_id]

        for sym in self.symbols.values():
            if sym.qualified_name == name_or_id or sym.name == name_or_id:
                return sym
        return None

    def find_symbols_by_name(self, name: str) -> List[Symbol]:
        """Returns all symbols matching the given short or qualified name."""
        return [
            s for s in self.symbols.values()
            if s.name == name or s.qualified_name == name
        ]

    def find_file(self, file_path: str) -> List[Symbol]:
        """Returns all symbols declared within a file."""
        norm_file = file_path.replace("\\", "/").strip()
        sym_ids = self.files.get(norm_file, [])
        return [self.symbols[sid] for sid in sym_ids if sid in self.symbols]

    def find_callers(self, symbol_name_or_id: str) -> List[Symbol]:
        """
        Finds all symbols that invoke the target function or method.
        """
        target_sym = self.find_symbol(symbol_name_or_id)
        keys_to_check = {symbol_name_or_id}
        if target_sym:
            keys_to_check.add(target_sym.id)
            keys_to_check.add(target_sym.name)
            keys_to_check.add(target_sym.qualified_name)

        caller_ids: Set[str] = set()
        for k in keys_to_check:
            caller_ids.update(self.reverse_call_graph.get(k, set()))

        results: List[Symbol] = []
        for cid in caller_ids:
            if cid in self.symbols:
                results.append(self.symbols[cid])
            else:
                sym = self.find_symbol(cid)
                if sym and sym not in results:
                    results.append(sym)
        return results

    def find_callees(self, symbol_name_or_id: str) -> List[Symbol]:
        """
        Finds all resolved symbols invoked by the target function or method.
        """
        target_sym = self.find_symbol(symbol_name_or_id)
        caller_key = target_sym.id if target_sym else symbol_name_or_id
        callee_names = self.call_graph.get(caller_key, set())

        results: List[Symbol] = []
        for cname in callee_names:
            resolved = self.find_symbol(cname)
            if resolved and resolved not in results:
                results.append(resolved)
        return results

    def find_subclasses(self, class_name_or_id: str) -> List[Symbol]:
        """
        Finds all classes that inherit from the specified base class.
        """
        target_sym = self.find_symbol(class_name_or_id)
        keys_to_check = {class_name_or_id}
        if target_sym:
            keys_to_check.add(target_sym.name)
            keys_to_check.add(target_sym.qualified_name)

        subclass_names: Set[str] = set()
        for k in keys_to_check:
            subclass_names.update(self.subclass_graph.get(k, set()))

        results: List[Symbol] = []
        for sc in subclass_names:
            sym = self.find_symbol(sc)
            if sym and sym not in results:
                results.append(sym)
        return results

    def find_base_classes(self, class_name_or_id: str) -> List[str]:
        """
        Returns list of base class names for the given class.
        """
        target_sym = self.find_symbol(class_name_or_id)
        keys_to_check = {class_name_or_id}
        if target_sym:
            keys_to_check.add(target_sym.name)
            keys_to_check.add(target_sym.qualified_name)

        base_classes: Set[str] = set()
        for k in keys_to_check:
            base_classes.update(self.inheritance_graph.get(k, set()))
        return sorted(list(base_classes))

    def find_dependents(self, file_path: str) -> List[str]:
        """
        Returns list of files that depend on / import file_path (reverse dependencies).
        """
        norm_file = file_path.replace("\\", "/").strip()
        return sorted(list(self.file_reverse_dependencies.get(norm_file, set())))

    def find_dependencies(self, file_path: str) -> List[str]:
        """
        Returns list of files that file_path depends on / imports (forward dependencies).
        """
        norm_file = file_path.replace("\\", "/").strip()
        return sorted(list(self.file_dependency_graph.get(norm_file, set())))

    def topological_order(self) -> List[str]:
        """
        Computes a topological ordering of files based on import dependencies.
        Dependencies appear before dependents. Handles cycles deterministically.
        """
        all_files = set(self.files.keys()) | set(self.file_dependency_graph.keys())
        in_degree: Dict[str, int] = {f: 0 for f in all_files}

        # Calculate in-degrees (number of dependencies that must precede this file)
        for src, tgts in self.file_dependency_graph.items():
            for tgt in tgts:
                if tgt in in_degree and src in in_degree:
                    in_degree[src] += 1

        queue = deque([f for f, deg in in_degree.items() if deg == 0])
        order: List[str] = []

        while queue:
            curr = queue.popleft()
            order.append(curr)
            for dependent in self.file_reverse_dependencies.get(curr, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        # If cyclic dependencies left unvisited nodes, append remaining deterministically
        if len(order) < len(all_files):
            remaining = sorted([f for f in all_files if f not in order])
            order.extend(remaining)

        return order

    # -------------------------------------------------------------------------
    # Search API
    # -------------------------------------------------------------------------

    def search_by_name(self, name: str, exact: bool = False) -> List[Symbol]:
        """Searches symbols by name with exact or substring matching."""
        q = name.strip().lower()
        if exact:
            return [s for s in self.symbols.values() if s.name.lower() == q or s.qualified_name.lower() == q]
        return [s for s in self.symbols.values() if q in s.name.lower() or q in s.qualified_name.lower()]

    def search_by_type(self, symbol_type: str) -> List[Symbol]:
        """Searches symbols matching the specified SymbolType."""
        st = symbol_type.strip().lower()
        return [s for s in self.symbols.values() if s.symbol_type.lower() == st]

    def search_by_file(self, file_path: str) -> List[Symbol]:
        """Searches symbols declared in a file path (supports partial path match)."""
        norm = file_path.replace("\\", "/").strip().lower()
        return [s for s in self.symbols.values() if norm in s.file.lower()]

    def search_by_language(self, language: str) -> List[Symbol]:
        """Searches symbols implemented in a target language."""
        lang = language.strip().lower()
        return [s for s in self.symbols.values() if s.language.lower() == lang]

    def search_regex(
        self,
        pattern: str,
        search_fields: Optional[List[str]] = None,
    ) -> List[Symbol]:
        """
        Searches symbols using a regular expression across specified fields
        (name, docstring, signature, file).
        """
        compiled = re.compile(pattern, re.IGNORECASE)
        fields = search_fields or ["name", "qualified_name", "docstring", "signature"]
        matches: List[Symbol] = []

        for sym in self.symbols.values():
            found = False
            for f in fields:
                val = getattr(sym, f, None)
                if val and compiled.search(str(val)):
                    found = True
                    break
            if found:
                matches.append(sym)
        return matches

    def search_docstring(self, query: str) -> List[Symbol]:
        """Searches symbols whose docstrings contain the query string."""
        q = query.strip().lower()
        return [
            s for s in self.symbols.values()
            if s.docstring and q in s.docstring.lower()
        ]

    # -------------------------------------------------------------------------
    # Statistics & Telemetry
    # -------------------------------------------------------------------------

    def statistics(self) -> IndexStatistics:
        """Computes comprehensive codebase graph statistics."""
        total_syms = len(self.symbols)
        total_files = len(self.files)

        class_count = sum(1 for s in self.symbols.values() if s.symbol_type == SymbolType.CLASS)
        func_count = sum(1 for s in self.symbols.values() if s.symbol_type == SymbolType.FUNCTION)
        method_count = sum(1 for s in self.symbols.values() if s.symbol_type == SymbolType.METHOD)
        interface_count = sum(1 for s in self.symbols.values() if s.symbol_type == SymbolType.INTERFACE)
        enum_count = sum(1 for s in self.symbols.values() if s.symbol_type == SymbolType.ENUM)

        import_count = sum(len(s.imports) for s in self.symbols.values())
        dep_count = len(self.dependencies)

        # Largest file by symbol count
        largest_f = None
        max_f_syms = 0
        for f, s_list in self.files.items():
            if len(s_list) > max_f_syms:
                max_f_syms = len(s_list)
                largest_f = f

        avg_syms = (total_syms / total_files) if total_files > 0 else 0.0

        lang_counts: Dict[str, int] = defaultdict(int)
        for s in self.symbols.values():
            lang_counts[s.language] += 1

        return IndexStatistics(
            total_files=total_files,
            total_symbols=total_syms,
            classes=class_count,
            functions=func_count,
            methods=method_count,
            interfaces=interface_count,
            enums=enum_count,
            imports=import_count,
            dependencies=dep_count,
            largest_file=largest_f,
            average_symbols_per_file=avg_syms,
            languages=dict(lang_counts),
        )

    # -------------------------------------------------------------------------
    # Serialization (Export / Import)
    # -------------------------------------------------------------------------

    def export_json(self, filepath: Optional[Union[str, Path]] = None) -> str:
        """Serializes the SymbolGraph to JSON and optionally saves to file."""
        payload = {
            "version": "1.4",
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "file_hashes": self.file_hashes,
            "symbols": [s.to_dict() for s in self.symbols.values()],
            "dependencies": [d.to_dict() for d in self.dependencies],
        }
        json_str = json.dumps(payload, indent=2, ensure_ascii=False)

        if filepath:
            target = Path(filepath).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json_str, encoding="utf-8")
            logger.info(f"Exported SymbolGraph to {target}")

        return json_str

    def import_json(self, filepath_or_json: Union[str, Path]) -> None:
        """Loads and reconstructs SymbolGraph state from JSON string or file."""
        possible_path = Path(filepath_or_json)
        if possible_path.exists() and possible_path.is_file():
            raw_content = possible_path.read_text(encoding="utf-8")
        else:
            raw_content = str(filepath_or_json)

        data = json.loads(raw_content)
        self.file_hashes = data.get("file_hashes", {})

        # Clear existing
        self.symbols.clear()
        self.files.clear()
        self.dependencies.clear()
        self.file_dependency_graph.clear()
        self.file_reverse_dependencies.clear()
        self.call_graph.clear()
        self.reverse_call_graph.clear()
        self.inheritance_graph.clear()
        self.subclass_graph.clear()
        self.implementation_graph.clear()
        self.interface_implementers.clear()

        # Load symbols
        for s_data in data.get("symbols", []):
            sym = Symbol.from_dict(s_data)
            self.add_symbol(sym)

        # Load dependencies
        for d_data in data.get("dependencies", []):
            dep = Dependency.from_dict(d_data)
            self.add_dependency(dep)

        logger.info(f"Imported SymbolGraph with {len(self.symbols)} symbols across {len(self.files)} files.")
