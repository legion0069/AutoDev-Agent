"""
repository_analyzer.py - Repository Intelligence & Architecture Analysis Engine for AutoDev (v1.7)

Performs deterministic, 100% offline static analysis across an entire software repository using
CodeIndexer, SymbolGraph, and file system topology.

Detects:
- Repository metrics (classes, functions, methods, interfaces, tests, build/config files, package managers)
- Architecture patterns (Layered, MVC, MVVM, Hexagonal, Clean, Microservice, Monolith, Event-Driven,
  Repository Pattern, Service Layer, Controller Layer, Factory Pattern, Dependency Injection, Plugin)
- Architecture layers (Presentation, Business Logic, Data Access, Infrastructure, Testing)
- Module summarization (purpose, responsibilities, exports, dependencies, dependents, risk, complexity)
- Hotspots (largest modules, fan-out/fan-in hubs, most-called functions, most-inherited classes, God objects, utils)
- Circular dependencies with graph cycle algorithms and severity scoring
- Entry points (main, __main__, SpringBootApplication, Node entrypoints, CLI tools, API startups)
- Dead code candidates and public APIs
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import shutil
import sys
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Ensure project root is on sys.path
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.code_indexer import CodeIndexer
from core.symbol_graph import Dependency, Symbol, SymbolGraph, SymbolType, Visibility

logger = logging.getLogger("AutoDev.RepositoryAnalyzer")


# =============================================================================
# DATACLASSES
# =============================================================================

@dataclass
class ArchitectureLayer:
    """Represents a logical architectural layer in the project."""
    name: str
    modules: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "modules": list(self.modules),
            "responsibilities": list(self.responsibilities),
            "dependencies": list(self.dependencies),
            "confidence": round(self.confidence, 2),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArchitectureLayer:
        return cls(
            name=data.get("name", "Unknown Layer"),
            modules=list(data.get("modules", [])),
            responsibilities=list(data.get("responsibilities", [])),
            dependencies=list(data.get("dependencies", [])),
            confidence=float(data.get("confidence", 1.0)),
        )


@dataclass
class ArchitectureMetrics:
    """Represents a detected architectural pattern and confidence evaluation."""
    pattern_name: str
    confidence: float  # 0.0 to 1.0
    matched_indicators: List[str] = field(default_factory=list)
    layers_detected: List[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_name": self.pattern_name,
            "confidence": round(self.confidence, 2),
            "matched_indicators": list(self.matched_indicators),
            "layers_detected": list(self.layers_detected),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArchitectureMetrics:
        return cls(
            pattern_name=data.get("pattern_name", "Unknown"),
            confidence=float(data.get("confidence", 0.0)),
            matched_indicators=list(data.get("matched_indicators", [])),
            layers_detected=list(data.get("layers_detected", [])),
            description=data.get("description", ""),
        )


@dataclass
class ModuleSummary:
    """Detailed deterministic summary of an individual module or source file."""
    module_path: str
    purpose: str = ""
    responsibilities: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    public_classes: List[str] = field(default_factory=list)
    internal_classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    risk: str = "LOW"  # CRITICAL, HIGH, MEDIUM, LOW
    complexity: str = "LOW"  # HIGH, MEDIUM, LOW
    lines_of_code: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_path": self.module_path,
            "purpose": self.purpose,
            "responsibilities": list(self.responsibilities),
            "exports": list(self.exports),
            "dependencies": list(self.dependencies),
            "dependents": list(self.dependents),
            "public_classes": list(self.public_classes),
            "internal_classes": list(self.internal_classes),
            "functions": list(self.functions),
            "risk": self.risk,
            "complexity": self.complexity,
            "lines_of_code": self.lines_of_code,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModuleSummary:
        return cls(
            module_path=data.get("module_path", ""),
            purpose=data.get("purpose", ""),
            responsibilities=list(data.get("responsibilities", [])),
            exports=list(data.get("exports", [])),
            dependencies=list(data.get("dependencies", [])),
            dependents=list(data.get("dependents", [])),
            public_classes=list(data.get("public_classes", [])),
            internal_classes=list(data.get("internal_classes", [])),
            functions=list(data.get("functions", [])),
            risk=data.get("risk", "LOW"),
            complexity=data.get("complexity", "LOW"),
            lines_of_code=int(data.get("lines_of_code", 0)),
        )


@dataclass
class Hotspot:
    """Identifies architectural hotspots, high complexity hubs, or structural risks."""
    category: str  # largest_module, high_fan_out, high_fan_in, most_called_function, most_inherited_class, god_object, utility_class
    target: str
    score: float
    metric_name: str
    metric_value: Any
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "target": self.target,
            "score": round(self.score, 2),
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Hotspot:
        return cls(
            category=data.get("category", "unknown"),
            target=data.get("target", ""),
            score=float(data.get("score", 0.0)),
            metric_name=data.get("metric_name", ""),
            metric_value=data.get("metric_value", 0),
            description=data.get("description", ""),
        )


@dataclass
class CircularDependency:
    """Represents a detected cyclical dependency loop between files or modules."""
    cycle: List[str]
    length: int
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle": list(self.cycle),
            "length": self.length,
            "severity": self.severity,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CircularDependency:
        return cls(
            cycle=list(data.get("cycle", [])),
            length=int(data.get("length", len(data.get("cycle", [])))),
            severity=data.get("severity", "MEDIUM"),
            description=data.get("description", ""),
        )


@dataclass
class RepositoryOverview:
    """
    Comprehensive, aggregated repository intelligence report for the entire project.
    """
    project_name: str = "AutoDev Project"
    project_root: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_modules: int = 0
    total_classes: int = 0
    total_interfaces: int = 0
    total_functions: int = 0
    total_methods: int = 0
    total_tests: int = 0
    total_dependencies: int = 0
    total_symbols: int = 0
    largest_files: List[Dict[str, Any]] = field(default_factory=list)
    most_connected_modules: List[Dict[str, Any]] = field(default_factory=list)
    most_reused_classes: List[Dict[str, Any]] = field(default_factory=list)
    dead_code_candidates: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    public_apis: List[str] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)
    build_files: List[str] = field(default_factory=list)
    package_managers: List[str] = field(default_factory=list)
    detected_architectures: List[ArchitectureMetrics] = field(default_factory=list)
    architecture_layers: List[ArchitectureLayer] = field(default_factory=list)
    module_summaries: Dict[str, ModuleSummary] = field(default_factory=dict)
    hotspots: List[Hotspot] = field(default_factory=list)
    circular_dependencies: List[CircularDependency] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "project_root": self.project_root,
            "timestamp": self.timestamp,
            "total_modules": self.total_modules,
            "total_classes": self.total_classes,
            "total_interfaces": self.total_interfaces,
            "total_functions": self.total_functions,
            "total_methods": self.total_methods,
            "total_tests": self.total_tests,
            "total_dependencies": self.total_dependencies,
            "total_symbols": self.total_symbols,
            "largest_files": list(self.largest_files),
            "most_connected_modules": list(self.most_connected_modules),
            "most_reused_classes": list(self.most_reused_classes),
            "dead_code_candidates": list(self.dead_code_candidates),
            "entry_points": list(self.entry_points),
            "public_apis": list(self.public_apis),
            "config_files": list(self.config_files),
            "build_files": list(self.build_files),
            "package_managers": list(self.package_managers),
            "detected_architectures": [a.to_dict() for a in self.detected_architectures],
            "architecture_layers": [l.to_dict() for l in self.architecture_layers],
            "module_summaries": {k: v.to_dict() for k, v in self.module_summaries.items()},
            "hotspots": [h.to_dict() for h in self.hotspots],
            "circular_dependencies": [c.to_dict() for c in self.circular_dependencies],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RepositoryOverview:
        architectures = [ArchitectureMetrics.from_dict(a) for a in data.get("detected_architectures", [])]
        layers = [ArchitectureLayer.from_dict(l) for l in data.get("architecture_layers", [])]
        modules = {k: ModuleSummary.from_dict(v) for k, v in data.get("module_summaries", {}).items()}
        hotspots = [Hotspot.from_dict(h) for h in data.get("hotspots", [])]
        cycles = [CircularDependency.from_dict(c) for c in data.get("circular_dependencies", [])]

        return cls(
            project_name=data.get("project_name", "AutoDev Project"),
            project_root=data.get("project_root", ""),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            total_modules=int(data.get("total_modules", 0)),
            total_classes=int(data.get("total_classes", 0)),
            total_interfaces=int(data.get("total_interfaces", 0)),
            total_functions=int(data.get("total_functions", 0)),
            total_methods=int(data.get("total_methods", 0)),
            total_tests=int(data.get("total_tests", 0)),
            total_dependencies=int(data.get("total_dependencies", 0)),
            total_symbols=int(data.get("total_symbols", 0)),
            largest_files=list(data.get("largest_files", [])),
            most_connected_modules=list(data.get("most_connected_modules", [])),
            most_reused_classes=list(data.get("most_reused_classes", [])),
            dead_code_candidates=list(data.get("dead_code_candidates", [])),
            entry_points=list(data.get("entry_points", [])),
            public_apis=list(data.get("public_apis", [])),
            config_files=list(data.get("config_files", [])),
            build_files=list(data.get("build_files", [])),
            package_managers=list(data.get("package_managers", [])),
            detected_architectures=architectures,
            architecture_layers=layers,
            module_summaries=modules,
            hotspots=hotspots,
            circular_dependencies=cycles,
            summary=data.get("summary", ""),
        )


# Alias for backward compatibility
RepositoryAnalysis = RepositoryOverview


# =============================================================================
# REPOSITORY ANALYZER ENGINE
# =============================================================================

class RepositoryAnalyzer:
    """
    Deterministic offline repository intelligence engine that scans symbol graphs,
    file topologies, and codebase structures to extract architectural insights,
    module summaries, hotspots, and circular dependencies.
    """

    CONFIG_FILE_PATTERNS = {
        r"^\.env(\..+)?$",
        r"^config\.(py|json|yaml|yml|toml|ini)$",
        r"^settings\.(py|json|yaml|yml|toml|ini)$",
        r"^tsconfig(\..+)?\.json$",
        r"^appsettings(\..+)?\.json$",
        r"^application\.(properties|yml|yaml)$",
        r"^\.eslintrc(\..+)?$",
        r"^\.prettierrc(\..+)?$",
        r"^pyproject\.toml$",
        r"^pytest\.ini$",
        r"^setup\.cfg$",
    }

    BUILD_FILE_PATTERNS = {
        r"^Dockerfile(\..+)?$",
        r"^docker-compose(\..+)?\.(yml|yaml)$",
        r"^Makefile$",
        r"^package\.json$",
        r"^pom\.xml$",
        r"^build\.gradle(\.kts)?$",
        r"^gradlew(\.bat)?$",
        r"^CMakeLists\.txt$",
        r"^Cargo\.toml$",
        r"^go\.mod$",
        r"^requirements.*\.txt$",
        r"^setup\.py$",
    }

    PACKAGE_MANAGER_MAP = {
        "requirements.txt": "pip",
        "setup.py": "setuptools",
        "pyproject.toml": "pip/poetry/flit",
        "Pipfile": "pipenv",
        "package.json": "npm",
        "yarn.lock": "yarn",
        "pnpm-lock.yaml": "pnpm",
        "pom.xml": "maven",
        "build.gradle": "gradle",
        "build.gradle.kts": "gradle",
        "Cargo.toml": "cargo",
        "go.mod": "go modules",
    }

    DEFAULT_OUTPUT_PATH = Path("memory/repository_analysis.json")

    def __init__(
        self,
        project_root: Optional[Union[str, Path]] = None,
        symbol_graph: Optional[SymbolGraph] = None,
        output_path: Union[str, Path] = DEFAULT_OUTPUT_PATH,
    ) -> None:
        """
        Initializes the RepositoryAnalyzer.

        Args:
            project_root: Root directory of the repository.
            symbol_graph: Pre-built SymbolGraph instance.
            output_path: Path where memory/repository_analysis.json is saved.
        """
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd()
        self.output_path = Path(output_path).resolve()
        self.symbol_graph = symbol_graph

    # -------------------------------------------------------------------------
    # Core Analysis Orchestration
    # -------------------------------------------------------------------------

    def analyze(
        self,
        project_root: Optional[Union[str, Path]] = None,
        symbol_graph: Optional[SymbolGraph] = None,
        project_files: Optional[Dict[str, str]] = None,
    ) -> RepositoryOverview:
        """
        Runs comprehensive repository static analysis and returns a RepositoryOverview.

        Args:
            project_root: Optional project root override.
            symbol_graph: Optional SymbolGraph override.
            project_files: Optional in-memory mapping of relative file paths to content.
        """
        root = Path(project_root).resolve() if project_root else self.project_root
        graph = symbol_graph or self.symbol_graph

        if graph is None:
            # Build or load index on the fly
            indexer = CodeIndexer(project_root=root, auto_load=True)
            graph = indexer.index()
            self.symbol_graph = graph

        # 1. Scan Filesystem & Basic Categorization
        discovered_files = self._discover_project_files(root, graph, project_files)
        config_files, build_files, package_managers = self._categorize_special_files(discovered_files)

        # 2. Extract Graph Statistics
        stats = self.statistics(graph, discovered_files, project_files)

        # 3. Detect Entrypoints
        entry_points = self.detect_entrypoints(graph, discovered_files, project_files)

        # 4. Detect Public APIs
        public_apis = self._detect_public_apis(graph, discovered_files)

        # 5. Summarize Modules
        module_summaries = self.summarize_modules(graph, discovered_files, project_files)

        # 6. Detect Architecture Patterns & Layers
        architectures, layers = self.detect_architecture(graph, discovered_files, module_summaries)

        # 7. Hotspot Analysis
        hotspots = self.find_hotspots(graph, module_summaries)

        # 8. Circular Dependency Detection
        cycles = self.detect_cycles(graph)

        # 9. Dead Code Detection
        dead_code = self._detect_dead_code(graph, entry_points, public_apis)

        # 10. Top File Metrics
        largest_files = self._get_largest_files(graph, module_summaries)
        most_connected = self._get_most_connected_modules(graph, module_summaries)
        most_reused = self._get_most_reused_classes(graph)

        # 11. Generate Deterministic Summary
        proj_name = root.name if root else "AutoDev Project"
        summary_text = self._generate_overview_summary(
            proj_name=proj_name,
            total_modules=stats["total_modules"],
            total_classes=stats["total_classes"],
            total_functions=stats["total_functions"],
            architectures=architectures,
            cycles=cycles,
            hotspots=hotspots,
        )

        overview = RepositoryOverview(
            project_name=proj_name,
            project_root=str(root),
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_modules=stats["total_modules"],
            total_classes=stats["total_classes"],
            total_interfaces=stats["total_interfaces"],
            total_functions=stats["total_functions"],
            total_methods=stats["total_methods"],
            total_tests=stats["total_tests"],
            total_dependencies=stats["total_dependencies"],
            total_symbols=stats["total_symbols"],
            largest_files=largest_files,
            most_connected_modules=most_connected,
            most_reused_classes=most_reused,
            dead_code_candidates=dead_code,
            entry_points=entry_points,
            public_apis=public_apis,
            config_files=config_files,
            build_files=build_files,
            package_managers=package_managers,
            detected_architectures=architectures,
            architecture_layers=layers,
            module_summaries=module_summaries,
            hotspots=hotspots,
            circular_dependencies=cycles,
            summary=summary_text,
        )

        return overview

    # -------------------------------------------------------------------------
    # Public API Sub-methods
    # -------------------------------------------------------------------------

    def statistics(
        self,
        symbol_graph: Optional[SymbolGraph] = None,
        discovered_files: Optional[List[str]] = None,
        project_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, int]:
        """
        Computes accurate counts of modules, classes, functions, methods, interfaces, tests, and dependencies.
        """
        graph = symbol_graph or self.symbol_graph or SymbolGraph()
        files = discovered_files if discovered_files is not None else list(graph.files.keys())

        total_classes = 0
        total_interfaces = 0
        total_functions = 0
        total_methods = 0
        total_symbols = len(graph.symbols)

        for sym in graph.symbols.values():
            stype = (sym.symbol_type or "").lower()
            if stype == SymbolType.CLASS:
                total_classes += 1
            elif stype == SymbolType.INTERFACE:
                total_interfaces += 1
            elif stype == SymbolType.FUNCTION:
                total_functions += 1
            elif stype in (SymbolType.METHOD, SymbolType.CONSTRUCTOR):
                total_methods += 1

        # Count tests
        total_tests = 0
        test_files: Set[str] = set()
        for f in files:
            f_norm = f.replace("\\", "/").lower()
            if "test" in f_norm or f_norm.endswith("_spec.ts") or f_norm.endswith(".spec.js"):
                test_files.add(f)

        for sym in graph.symbols.values():
            sname = (sym.name or "").lower()
            if sym.file in test_files or sname.startswith("test_") or sname.startswith("test"):
                if sym.symbol_type in (SymbolType.FUNCTION, SymbolType.METHOD):
                    total_tests += 1

        # Total dependencies in the graph
        total_dependencies = len(graph.dependencies)
        if total_dependencies == 0 and graph.file_dependency_graph:
            total_dependencies = sum(len(deps) for deps in graph.file_dependency_graph.values())

        return {
            "total_modules": len(files),
            "total_classes": total_classes,
            "total_interfaces": total_interfaces,
            "total_functions": total_functions,
            "total_methods": total_methods,
            "total_tests": total_tests,
            "total_dependencies": total_dependencies,
            "total_symbols": total_symbols,
        }

    def detect_architecture(
        self,
        symbol_graph: Optional[SymbolGraph] = None,
        discovered_files: Optional[List[str]] = None,
        module_summaries: Optional[Dict[str, ModuleSummary]] = None,
    ) -> Tuple[List[ArchitectureMetrics], List[ArchitectureLayer]]:
        """
        Infers architectural patterns (Layered, MVC, Hexagonal, Clean, etc.) and layers
        with deterministic confidence scores.
        """
        graph = symbol_graph or self.symbol_graph or SymbolGraph()
        files = discovered_files if discovered_files is not None else list(graph.files.keys())
        norm_files = [f.replace("\\", "/").lower() for f in files]

        patterns: List[ArchitectureMetrics] = []
        layers: List[ArchitectureLayer] = []

        # 1. Identify Architectural Layers
        layer_map: Dict[str, List[str]] = {
            "Presentation / API / CLI": [],
            "Business Logic / Core": [],
            "Data Access / Repository": [],
            "Infrastructure / Adapters": [],
            "Testing & QA": [],
        }

        for f in files:
            fn = f.replace("\\", "/").lower()
            if any(k in fn for k in ["test", "mock", "spec", "tests/"]):
                layer_map["Testing & QA"].append(f)
            elif any(k in fn for k in ["controller", "api", "route", "endpoint", "views", "ui", "cli", "main.py", "__main__"]):
                layer_map["Presentation / API / CLI"].append(f)
            elif any(k in fn for k in ["service", "manager", "engine", "core", "agent", "domain", "logic", "usecase"]):
                layer_map["Business Logic / Core"].append(f)
            elif any(k in fn for k in ["repo", "repository", "dao", "database", "db", "model", "entity", "store"]):
                layer_map["Data Access / Repository"].append(f)
            else:
                layer_map["Infrastructure / Adapters"].append(f)

        for lname, lfiles in layer_map.items():
            if lfiles:
                deps: Set[str] = set()
                for lf in lfiles:
                    for target_f in graph.file_dependency_graph.get(lf, set()):
                        # Determine layer of target_f
                        for target_layer, member_files in layer_map.items():
                            if target_f in member_files and target_layer != lname:
                                deps.add(target_layer)
                layers.append(ArchitectureLayer(
                    name=lname,
                    modules=lfiles,
                    responsibilities=[f"Provides {lname.lower()} capabilities for {len(lfiles)} modules."],
                    dependencies=sorted(list(deps)),
                    confidence=min(1.0, 0.5 + 0.1 * len(lfiles)),
                ))

        # 2. Evaluate Patterns

        # (a) Layered Architecture
        populated_layers = sum(1 for l in [layer_map["Presentation / API / CLI"], layer_map["Business Logic / Core"], layer_map["Data Access / Repository"]] if l)
        if populated_layers >= 2:
            conf = 0.85 if populated_layers == 3 else 0.70
            patterns.append(ArchitectureMetrics(
                pattern_name="Layered Architecture",
                confidence=conf,
                matched_indicators=["Distinct separation of presentation, domain/business logic, and data access layers."],
                layers_detected=[l.name for l in layers if l.modules],
                description="Separates system concerns into hierarchical presentation, service/domain, and data persistence layers.",
            ))

        # (b) MVC Pattern
        has_model = any("model" in fn for fn in norm_files)
        has_view = any("view" in fn or "ui" in fn for fn in norm_files)
        has_controller = any("controller" in fn or "route" in fn or "api" in fn for fn in norm_files)
        mvc_count = sum([has_model, has_view, has_controller])
        if mvc_count >= 2:
            patterns.append(ArchitectureMetrics(
                pattern_name="MVC (Model-View-Controller)",
                confidence=0.90 if mvc_count == 3 else 0.65,
                matched_indicators=[k for k, v in [("Models", has_model), ("Views", has_view), ("Controllers", has_controller)] if v],
                layers_detected=["Models", "Views", "Controllers"],
                description="Organizes system into data models, presentation views, and request controllers.",
            ))

        # (c) Repository Pattern
        repo_files = [f for f in files if any(k in f.lower() for k in ["repo", "repository", "dao"])]
        if repo_files:
            patterns.append(ArchitectureMetrics(
                pattern_name="Repository Pattern",
                confidence=min(0.95, 0.60 + 0.1 * len(repo_files)),
                matched_indicators=[f"Found {len(repo_files)} repository/DAO modules: {', '.join(repo_files[:3])}"],
                layers_detected=["Data Access / Repository"],
                description="Mediates between the domain and data mapping layers using collection-like interfaces.",
            ))

        # (d) Service Layer Pattern
        service_files = [f for f in files if any(k in f.lower() for k in ["service", "usecase"])]
        if service_files:
            patterns.append(ArchitectureMetrics(
                pattern_name="Service Layer",
                confidence=min(0.95, 0.65 + 0.1 * len(service_files)),
                matched_indicators=[f"Found {len(service_files)} service modules: {', '.join(service_files[:3])}"],
                layers_detected=["Business Logic / Core"],
                description="Defines an application's boundary with a layer of services to encapsulate business workflows.",
            ))

        # (e) Clean Architecture / Hexagonal
        has_ports = any("port" in fn or "adapter" in fn for fn in norm_files)
        has_usecase = any("usecase" in fn or "interactor" in fn for fn in norm_files)
        if has_ports or (has_usecase and populated_layers >= 2):
            patterns.append(ArchitectureMetrics(
                pattern_name="Clean / Hexagonal Architecture",
                confidence=0.85 if has_ports else 0.65,
                matched_indicators=["Ports/Adapters separation and dependency inversion indicators."],
                layers_detected=[l.name for l in layers],
                description="Isolates core business domain from external adapters, databases, and delivery mechanisms.",
            ))

        # (f) Plugin / Extension Architecture
        plugin_files = [f for f in files if "plugin" in f.lower() or "provider" in f.lower() or "extension" in f.lower()]
        if plugin_files:
            patterns.append(ArchitectureMetrics(
                pattern_name="Plugin / Provider Architecture",
                confidence=min(0.95, 0.70 + 0.05 * len(plugin_files)),
                matched_indicators=[f"Detected {len(plugin_files)} pluggable provider/extension modules: {', '.join(plugin_files[:3])}"],
                layers_detected=["Infrastructure / Adapters"],
                description="Provides modular plug-and-play extensions and provider implementations.",
            ))

        # (g) Monolith vs Microservice
        has_docker_compose = any("docker-compose" in fn for fn in norm_files)
        service_subdirs = {Path(fn).parts[1] for fn in norm_files if fn.startswith("services/") and len(Path(fn).parts) > 2}
        has_multiservices = len(service_subdirs) >= 2 or any(fn.startswith("apps/") and len(Path(fn).parts) > 2 for fn in norm_files)
        if has_multiservices or (has_docker_compose and len(files) > 30):
            patterns.append(ArchitectureMetrics(
                pattern_name="Microservice Architecture",
                confidence=0.75,
                matched_indicators=["Multiple independent service boundaries or container orchestration definitions."],
                layers_detected=["Services", "Infrastructure"],
                description="Decomposes application into independently deployable service boundaries.",
            ))
        else:
            patterns.append(ArchitectureMetrics(
                pattern_name="Modular Monolith",
                confidence=0.90,
                matched_indicators=["Unified repository structure with co-located components."],
                layers_detected=[l.name for l in layers if l.modules],
                description="Single deployable application with well-defined internal modular boundaries.",
            ))

        # (h) Event-Driven / PubSub
        event_symbols = [
            s.name for s in graph.symbols.values()
            if any(k in s.name.lower() for k in ["event", "listener", "subscriber", "publisher", "emitter", "handler", "bus"])
        ]
        if len(event_symbols) >= 3:
            patterns.append(ArchitectureMetrics(
                pattern_name="Event-Driven Architecture",
                confidence=min(0.90, 0.50 + 0.08 * len(event_symbols)),
                matched_indicators=[f"Found {len(event_symbols)} event/listener/bus symbols: {', '.join(event_symbols[:4])}"],
                layers_detected=["Business Logic / Core"],
                description="Uses asynchronous message passing, events, or listener registrations for decoupled execution.",
            ))

        # (i) Factory Pattern
        factory_symbols = [s.name for s in graph.symbols.values() if "factory" in s.name.lower() or s.name.startswith("create_")]
        if len(factory_symbols) >= 2:
            patterns.append(ArchitectureMetrics(
                pattern_name="Factory Pattern",
                confidence=min(0.90, 0.60 + 0.08 * len(factory_symbols)),
                matched_indicators=[f"Found {len(factory_symbols)} factory/creator symbols: {', '.join(factory_symbols[:3])}"],
                layers_detected=["Infrastructure / Adapters"],
                description="Encapsulates object creation and dynamic instantiation mechanisms.",
            ))

        # (j) Dependency Injection
        di_symbols = [s.name for s in graph.symbols.values() if any(k in s.name.lower() for k in ["inject", "container", "provider_factory"])]
        if di_symbols:
            patterns.append(ArchitectureMetrics(
                pattern_name="Dependency Injection / Inversion of Control",
                confidence=min(0.90, 0.60 + 0.1 * len(di_symbols)),
                matched_indicators=[f"Found DI indicators in symbols: {', '.join(di_symbols[:3])}"],
                layers_detected=["Infrastructure / Adapters"],
                description="Decouples component creation from usage through injection containers and factories.",
            ))

        patterns.sort(key=lambda p: p.confidence, reverse=True)
        return patterns, layers

    def summarize_modules(
        self,
        symbol_graph: Optional[SymbolGraph] = None,
        discovered_files: Optional[List[str]] = None,
        project_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, ModuleSummary]:
        """
        Produces granular deterministic summaries for every module in the project.
        """
        graph = symbol_graph or self.symbol_graph or SymbolGraph()
        files = discovered_files if discovered_files is not None else list(graph.files.keys())

        summaries: Dict[str, ModuleSummary] = {}

        for f in files:
            symbols_in_file = [
                s for s in graph.symbols.values()
                if s.file == f or s.file.replace("\\", "/") == f.replace("\\", "/")
            ]

            exports: List[str] = []
            public_classes: List[str] = []
            internal_classes: List[str] = []
            functions: List[str] = []

            for sym in symbols_in_file:
                stype = (sym.symbol_type or "").lower()
                sname = sym.name
                if stype == SymbolType.CLASS:
                    if not sname.startswith("_"):
                        public_classes.append(sname)
                        exports.append(sname)
                    else:
                        internal_classes.append(sname)
                elif stype == SymbolType.FUNCTION:
                    if not sname.startswith("_"):
                        functions.append(sname)
                        exports.append(sname)
                    else:
                        functions.append(sname)

            dependencies = sorted(list(graph.file_dependency_graph.get(f, set())))
            dependents = sorted(list(graph.file_reverse_dependencies.get(f, set())))

            # Estimate LOC
            loc = 0
            if project_files and f in project_files:
                loc = len(project_files[f].splitlines())
            elif symbols_in_file:
                max_end = max((s.end_line for s in symbols_in_file), default=20)
                loc = max(max_end, len(symbols_in_file) * 8)
            else:
                loc = 15

            # Complexity
            if len(symbols_in_file) > 15 or len(dependencies) > 8 or loc > 300:
                complexity = "HIGH"
            elif len(symbols_in_file) > 6 or len(dependencies) > 3 or loc > 120:
                complexity = "MEDIUM"
            else:
                complexity = "LOW"

            # Risk
            if len(dependents) >= 6 or (len(dependents) >= 3 and complexity == "HIGH"):
                risk = "HIGH"
            elif len(dependents) >= 2 or complexity == "HIGH":
                risk = "MEDIUM"
            else:
                risk = "LOW"

            # Inferred purpose and responsibilities
            stem = Path(f).stem
            purpose = self._infer_module_purpose(f, public_classes, functions)
            responsibilities = self._infer_module_responsibilities(f, public_classes, functions, dependencies)

            summaries[f] = ModuleSummary(
                module_path=f,
                purpose=purpose,
                responsibilities=responsibilities,
                exports=sorted(exports),
                dependencies=dependencies,
                dependents=dependents,
                public_classes=sorted(public_classes),
                internal_classes=sorted(internal_classes),
                functions=sorted(functions),
                risk=risk,
                complexity=complexity,
                lines_of_code=loc,
            )

        return summaries

    def find_hotspots(
        self,
        symbol_graph: Optional[SymbolGraph] = None,
        module_summaries: Optional[Dict[str, ModuleSummary]] = None,
    ) -> List[Hotspot]:
        """
        Detects architectural hotspots (largest modules, high fan-out/in, most called functions,
        most inherited classes, God objects, and utility classes).
        """
        graph = symbol_graph or self.symbol_graph or SymbolGraph()
        summaries = module_summaries or self.summarize_modules(graph)

        hotspots: List[Hotspot] = []

        # 1. Largest Modules
        sorted_by_loc = sorted(summaries.values(), key=lambda m: (m.lines_of_code, len(m.exports)), reverse=True)
        for m in sorted_by_loc[:3]:
            if m.lines_of_code >= 100 or len(m.exports) >= 8:
                hotspots.append(Hotspot(
                    category="largest_module",
                    target=m.module_path,
                    score=float(m.lines_of_code),
                    metric_name="lines_of_code",
                    metric_value=m.lines_of_code,
                    description=f"Module '{m.module_path}' contains {m.lines_of_code} LOC and {len(m.exports)} exported symbols.",
                ))

        # 2. High Fan-out (High outgoing dependencies)
        sorted_by_fanout = sorted(summaries.values(), key=lambda m: len(m.dependencies), reverse=True)
        for m in sorted_by_fanout[:3]:
            if len(m.dependencies) >= 4:
                hotspots.append(Hotspot(
                    category="high_fan_out",
                    target=m.module_path,
                    score=float(len(m.dependencies)),
                    metric_name="outgoing_dependencies",
                    metric_value=len(m.dependencies),
                    description=f"Module '{m.module_path}' imports {len(m.dependencies)} distinct modules.",
                ))

        # 3. High Fan-in (High incoming dependents / Core hubs)
        sorted_by_fanin = sorted(summaries.values(), key=lambda m: len(m.dependents), reverse=True)
        for m in sorted_by_fanin[:3]:
            if len(m.dependents) >= 2:
                hotspots.append(Hotspot(
                    category="high_fan_in",
                    target=m.module_path,
                    score=float(len(m.dependents)),
                    metric_name="incoming_dependents",
                    metric_value=len(m.dependents),
                    description=f"Module '{m.module_path}' is depended on by {len(m.dependents)} other modules.",
                ))


        # 4. Most Called Functions
        call_counts: Dict[str, int] = defaultdict(int)
        for sym in graph.symbols.values():
            if sym.called_by:
                call_counts[sym.name] += len(sym.called_by)
            elif sym.name in graph.reverse_call_graph:
                call_counts[sym.name] += len(graph.reverse_call_graph[sym.name])

        for fname, count in sorted(call_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
            if count >= 2:
                hotspots.append(Hotspot(
                    category="most_called_function",
                    target=fname,
                    score=float(count),
                    metric_name="call_count",
                    metric_value=count,
                    description=f"Function/method '{fname}' is referenced by {count} call sites.",
                ))

        # 5. Most Inherited Classes
        subclass_counts: Dict[str, int] = {}
        for base_cls, subs in graph.subclass_graph.items():
            if subs:
                subclass_counts[base_cls] = len(subs)

        for cname, count in sorted(subclass_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
            if count >= 2:
                hotspots.append(Hotspot(
                    category="most_inherited_class",
                    target=cname,
                    score=float(count),
                    metric_name="subclass_count",
                    metric_value=count,
                    description=f"Class '{cname}' serves as a base class for {count} subclasses.",
                ))

        # 6. Potential God Objects (Classes with many methods/references)
        class_methods: Dict[str, List[Symbol]] = defaultdict(list)
        for sym in graph.symbols.values():
            if sym.parent_symbol:
                class_methods[sym.parent_symbol].append(sym)

        for parent, meths in class_methods.items():
            if len(meths) >= 8:
                hotspots.append(Hotspot(
                    category="god_object",
                    target=parent,
                    score=float(len(meths)),
                    metric_name="method_count",
                    metric_value=len(meths),
                    description=f"Class '{parent}' defines {len(meths)} methods, indicating high cohesion risk.",
                ))

        # 7. Utility Modules / Classes
        for m in summaries.values():
            f_lower = m.module_path.lower()
            if any(k in f_lower for k in ["util", "helper", "common", "tools"]):
                hotspots.append(Hotspot(
                    category="utility_class",
                    target=m.module_path,
                    score=float(len(m.functions) + len(m.public_classes)),
                    metric_name="utility_functions",
                    metric_value=len(m.functions),
                    description=f"Module '{m.module_path}' provides generic utility helpers across components.",
                ))

        return hotspots

    def detect_cycles(self, symbol_graph: Optional[SymbolGraph] = None) -> List[CircularDependency]:
        """
        Finds all circular dependency cycles in the module dependency graph using DFS cycle traversal.
        """
        graph = symbol_graph or self.symbol_graph or SymbolGraph()
        adj: Dict[str, Set[str]] = graph.file_dependency_graph

        cycles: List[CircularDependency] = []
        visited: Set[str] = set()
        rec_stack: List[str] = []
        seen_cycles: Set[Tuple[str, ...]] = set()

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)

            for neighbor in sorted(list(adj.get(node, set()))):
                if neighbor in rec_stack:
                    # Cycle found
                    idx = rec_stack.index(neighbor)
                    cycle_nodes = rec_stack[idx:] + [neighbor]

                    # Normalize cycle signature for deduplication
                    cycle_body = cycle_nodes[:-1]
                    min_idx = cycle_body.index(min(cycle_body))
                    canonical = tuple(cycle_body[min_idx:] + cycle_body[:min_idx])

                    if canonical not in seen_cycles:
                        seen_cycles.add(canonical)
                        clen = len(cycle_nodes) - 1
                        if clen == 2:
                            sev = "HIGH"
                        elif clen == 3:
                            sev = "MEDIUM"
                        else:
                            sev = "LOW"
                        cycles.append(CircularDependency(
                            cycle=cycle_nodes,
                            length=clen,
                            severity=sev,
                            description=f"Cyclic dependency detected across {clen} modules: {' -> '.join(cycle_nodes)}",
                        ))
                elif neighbor not in visited:
                    dfs(neighbor)

            rec_stack.pop()

        for f in sorted(list(adj.keys())):
            if f not in visited:
                dfs(f)

        cycles.sort(key=lambda c: (c.severity == "CRITICAL", c.severity == "HIGH", c.severity == "MEDIUM", -c.length), reverse=True)
        return cycles

    def detect_entrypoints(
        self,
        symbol_graph: Optional[SymbolGraph] = None,
        discovered_files: Optional[List[str]] = None,
        project_files: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """
        Detects entry points across main scripts, CLI tools, web startup files, and Spring Boot / Node servers.
        """
        graph = symbol_graph or self.symbol_graph or SymbolGraph()
        files = discovered_files if discovered_files is not None else list(graph.files.keys())

        entrypoints: Set[str] = set()

        ENTRY_FILENAMES = {
            "main.py", "__main__.py", "app.py", "server.py", "run.py", "cli.py", "index.py",
            "index.js", "server.js", "app.js", "main.js",
            "index.ts", "server.ts", "app.ts", "main.ts",
        }

        for f in files:
            p = Path(f)
            fname = p.name.lower()

            if fname in ENTRY_FILENAMES:
                entrypoints.add(f)
            elif p.stem.lower() in ("main", "app", "server", "cli", "run"):
                entrypoints.add(f)

            # Check symbols in file
            syms = [s for s in graph.symbols.values() if s.file == f or s.file.replace("\\", "/") == f.replace("\\", "/")]
            for s in syms:
                sname = s.name.lower()
                if sname in ("main", "cli", "start", "run_server", "create_app"):
                    entrypoints.add(f"{f}:{s.name}")
                if any("springbootapplication" in (d.lower()) for d in s.decorators):
                    entrypoints.add(f"{f}:{s.name} (SpringBootApplication)")

            # Check content if available
            content = ""
            if project_files and f in project_files:
                content = project_files[f]
            elif (self.project_root / f).is_file():
                try:
                    content = (self.project_root / f).read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass

            if content:
                if 'if __name__ == "__main__":' in content or "if __name__ == '__main__':" in content:
                    entrypoints.add(f"{f} (__main__ block)")
                if "@click.command" in content or "@click.group" in content or "argparse.ArgumentParser" in content:
                    entrypoints.add(f"{f} (CLI Tool)")
                if "FastAPI(" in content or "Flask(__name__)" in content or "express()" in content:
                    entrypoints.add(f"{f} (Web API Server)")

        return sorted(list(entrypoints))

    # -------------------------------------------------------------------------
    # JSON Persistence
    # -------------------------------------------------------------------------

    def save_report(
        self,
        report: RepositoryOverview,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """
        Exports RepositoryOverview as JSON to memory/repository_analysis.json.
        """
        dest = Path(output_path).resolve() if output_path else self.output_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = dest.with_suffix(".tmp")

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)

        shutil.move(str(tmp_path), str(dest))
        logger.info("Saved repository intelligence report to '%s'.", dest)
        return dest

    def load_report(self, input_path: Optional[Union[str, Path]] = None) -> RepositoryOverview:
        """
        Loads RepositoryOverview from a persisted JSON report.
        """
        src = Path(input_path).resolve() if input_path else self.output_path
        if not src.is_file():
            raise FileNotFoundError(f"Repository analysis report not found at '{src}'.")

        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)

        return RepositoryOverview.from_dict(data)

    # -------------------------------------------------------------------------
    # Private Helper Functions
    # -------------------------------------------------------------------------

    def _discover_project_files(
        self,
        root: Path,
        graph: SymbolGraph,
        project_files: Optional[Dict[str, str]],
    ) -> List[str]:
        """Returns sorted unique relative paths of all relevant project files."""
        files: Set[str] = set()

        if graph and graph.files:
            for f in graph.files.keys():
                files.add(f.replace("\\", "/"))

        if project_files:
            for f in project_files.keys():
                files.add(f.replace("\\", "/"))

        if root.exists() and root.is_dir():
            for p in root.rglob("*"):
                if p.is_file():
                    # Check ignore dirs
                    parts = p.relative_to(root).parts
                    if not any(ign in parts for ign in CodeIndexer.IGNORE_DIRS):
                        rel = str(p.relative_to(root)).replace("\\", "/")
                        files.add(rel)

        return sorted(list(files))

    def _categorize_special_files(self, files: List[str]) -> Tuple[List[str], List[str], List[str]]:
        """Identifies config files, build files, and package managers."""
        configs: List[str] = []
        builds: List[str] = []
        pms: Set[str] = set()

        for f in files:
            fname = Path(f).name
            for pat in self.CONFIG_FILE_PATTERNS:
                if re.match(pat, fname, re.IGNORECASE):
                    configs.append(f)
                    break

            for pat in self.BUILD_FILE_PATTERNS:
                if re.match(pat, fname, re.IGNORECASE):
                    builds.append(f)
                    break

            if fname in self.PACKAGE_MANAGER_MAP:
                pms.add(self.PACKAGE_MANAGER_MAP[fname])

        return sorted(configs), sorted(builds), sorted(list(pms))

    def _detect_public_apis(self, graph: SymbolGraph, files: List[str]) -> List[str]:
        """Detects exposed public APIs, route handlers, and exported interfaces."""
        apis: Set[str] = set()

        for sym in graph.symbols.values():
            if sym.visibility == Visibility.PUBLIC and not sym.name.startswith("_"):
                # Check for routes or API indicators
                if any(k in (sym.file or "").lower() for k in ["api", "controller", "route", "endpoint", "interface"]):
                    apis.add(f"{sym.file}::{sym.name}")
                elif any("app." in d or "router." in d or "endpoint" in d for d in sym.decorators):
                    apis.add(f"{sym.file}::{sym.name} (Route)")

        return sorted(list(apis))[:20]

    def _detect_dead_code(self, graph: SymbolGraph, entry_points: List[str], public_apis: List[str]) -> List[str]:
        """Detects unused/uncalled internal functions or classes."""
        candidates: List[str] = []

        entry_syms = {e.split(":")[-1].split(" ")[0].strip() for e in entry_points if ":" in e}
        public_sym_names = {a.split("::")[-1].split(" ")[0].strip() for a in public_apis if "::" in a}

        for sym in graph.symbols.values():
            sname = sym.name
            if sname.startswith("_") and not sname.startswith("__"):
                # Internal symbol with 0 callers and 0 references
                called_count = len(sym.called_by) + len(graph.reverse_call_graph.get(sname, set()))
                ref_count = len(sym.references)
                if called_count == 0 and ref_count == 0 and sname not in entry_syms and sname not in public_sym_names:
                    candidates.append(f"{sym.file}::{sname} ({sym.symbol_type})")

        return sorted(candidates)[:15]

    def _get_largest_files(self, graph: SymbolGraph, summaries: Dict[str, ModuleSummary]) -> List[Dict[str, Any]]:
        sorted_files = sorted(summaries.values(), key=lambda m: m.lines_of_code, reverse=True)
        return [
            {"file": m.module_path, "lines_of_code": m.lines_of_code, "symbols": len(m.exports) + len(m.internal_classes)}
            for m in sorted_files[:5]
        ]

    def _get_most_connected_modules(self, graph: SymbolGraph, summaries: Dict[str, ModuleSummary]) -> List[Dict[str, Any]]:
        sorted_mods = sorted(summaries.values(), key=lambda m: (len(m.dependencies) + len(m.dependents)), reverse=True)
        return [
            {"file": m.module_path, "total_connections": len(m.dependencies) + len(m.dependents), "dependencies": len(m.dependencies), "dependents": len(m.dependents)}
            for m in sorted_mods[:5]
        ]

    def _get_most_reused_classes(self, graph: SymbolGraph) -> List[Dict[str, Any]]:
        reused: List[Dict[str, Any]] = []
        for sym in graph.symbols.values():
            if sym.symbol_type == SymbolType.CLASS:
                sub_count = len(graph.subclass_graph.get(sym.name, set()))
                call_count = len(graph.reverse_call_graph.get(sym.name, set()))
                total_reuse = sub_count + call_count
                if total_reuse > 0:
                    reused.append({"class": sym.name, "file": sym.file, "subclasses": sub_count, "callers": call_count, "total_reuse": total_reuse})

        reused.sort(key=lambda x: x["total_reuse"], reverse=True)
        return reused[:5]

    def _infer_module_purpose(self, path: str, classes: List[str], functions: List[str]) -> str:
        stem = Path(path).stem.replace("_", " ")
        if classes:
            return f"Encapsulates {', '.join(classes[:2])} business logic and data structures."
        elif functions:
            return f"Provides procedural routines for {', '.join(functions[:2])}."
        return f"Component module for {stem} functionality."

    def _infer_module_responsibilities(self, path: str, classes: List[str], functions: List[str], deps: List[str]) -> List[str]:
        resps: List[str] = []
        if classes:
            resps.append(f"Declares class abstractions: {', '.join(classes[:3])}.")
        if functions:
            resps.append(f"Implements helper/procedural functions: {', '.join(functions[:3])}.")
        if deps:
            resps.append(f"Integrates with {len(deps)} downstream dependencies.")
        if not resps:
            resps.append("Maintains module-level configuration and utility exports.")
        return resps

    def _generate_overview_summary(
        self,
        proj_name: str,
        total_modules: int,
        total_classes: int,
        total_functions: int,
        architectures: List[ArchitectureMetrics],
        cycles: List[CircularDependency],
        hotspots: List[Hotspot],
    ) -> str:
        primary_arch = architectures[0].pattern_name if architectures else "Modular Monolith"
        cycle_msg = f"{len(cycles)} circular dependencies detected" if cycles else "no circular dependencies"
        return (
            f"Repository '{proj_name}' consists of {total_modules} modules, {total_classes} classes, and "
            f"{total_functions} functions. Primary architecture detected: {primary_arch}. "
            f"Static topology reveals {cycle_msg} and {len(hotspots)} potential architectural hotspots."
        )


if __name__ == "__main__":
    analyzer = RepositoryAnalyzer()
    overview = analyzer.analyze()
    print("===================== REPOSITORY INTELLIGENCE OVERVIEW =====================")
    print(json.dumps(overview.to_dict(), indent=2))
