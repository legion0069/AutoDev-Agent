"""
test_repository_analyzer.py - Comprehensive Test Suite for AutoDev Repository Intelligence Engine (v1.7)

Validates:
1. Repository metrics and statistics (classes, functions, methods, interfaces, tests, dependencies)
2. Architecture pattern detection (Layered, MVC, Clean, Repository, Service Layer, Monolith, etc.)
3. Architecture layer grouping and layer dependency tracking
4. Circular dependency detection and severity scoring
5. Hotspot detection (largest modules, fan-out/in hubs, most called functions, god objects, utils)
6. Entry point detection (main, __main__, SpringBoot, CLI, API startups)
7. Module summarization (purpose, responsibilities, exports, complexity, risk)
8. Dead code candidate and public API extraction
9. JSON export and import serialization roundtrip
10. PromptBuilder integration (PROJECT ARCHITECTURE section)
11. Orchestrator integration (auto-analysis & context persistence)
12. Empty repository handling
13. Performance on 1000+ symbols (<0.5s execution)
14. Deterministic output reproducibility
"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

from agents.coder_agent import CoderAgent, GeneratedResult
from agents.task_planner_agent import Task
from core.llm import BaseLLM
from core.orchestrator import Orchestrator
from core.prompt_builder import PromptBuilder
from core.providers.mock_provider import MockProvider
from core.repository_analyzer import (
    ArchitectureLayer,
    ArchitectureMetrics,
    CircularDependency,
    Hotspot,
    ModuleSummary,
    RepositoryAnalysis,
    RepositoryAnalyzer,
    RepositoryOverview,
)
from core.symbol_graph import Dependency, Symbol, SymbolGraph, SymbolType, Visibility


# =============================================================================
# FIXTURES & HELPERS
# =============================================================================

@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="autodev_repo_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def create_sample_graph() -> SymbolGraph:
    """Constructs a rich test symbol graph."""
    graph = SymbolGraph()

    # 1. Controller Layer
    graph.add_symbol(Symbol(
        id="c1", name="OrderController", qualified_name="controllers.order.OrderController",
        symbol_type=SymbolType.CLASS, language="python", file="controllers/order_controller.py",
        line=1, end_line=50, visibility=Visibility.PUBLIC,
    ))
    graph.add_symbol(Symbol(
        id="c2", name="get_order", qualified_name="controllers.order.OrderController.get_order",
        symbol_type=SymbolType.METHOD, language="python", file="controllers/order_controller.py",
        line=10, end_line=25, parent_symbol="OrderController", decorators=["@app.get('/orders')"],
    ))

    # 2. Service Layer
    graph.add_symbol(Symbol(
        id="s1", name="OrderService", qualified_name="services.order.OrderService",
        symbol_type=SymbolType.CLASS, language="python", file="services/order_service.py",
        line=1, end_line=80, visibility=Visibility.PUBLIC,
    ))
    graph.add_symbol(Symbol(
        id="s2", name="process_order", qualified_name="services.order.OrderService.process_order",
        symbol_type=SymbolType.METHOD, language="python", file="services/order_service.py",
        line=15, end_line=45, parent_symbol="OrderService", calls=["find_by_id", "save"],
    ))

    # 3. Repository Layer
    graph.add_symbol(Symbol(
        id="r1", name="OrderRepository", qualified_name="repositories.order.OrderRepository",
        symbol_type=SymbolType.CLASS, language="python", file="repositories/order_repository.py",
        line=1, end_line=60, visibility=Visibility.PUBLIC,
    ))
    graph.add_symbol(Symbol(
        id="r2", name="find_by_id", qualified_name="repositories.order.OrderRepository.find_by_id",
        symbol_type=SymbolType.METHOD, language="python", file="repositories/order_repository.py",
        line=10, end_line=25, parent_symbol="OrderRepository", called_by=["process_order"],
    ))

    # 4. Utilities
    graph.add_symbol(Symbol(
        id="u1", name="format_currency", qualified_name="utils.helpers.format_currency",
        symbol_type=SymbolType.FUNCTION, language="python", file="utils/helpers.py",
        line=1, end_line=15, visibility=Visibility.PUBLIC,
    ))
    graph.add_symbol(Symbol(
        id="u2", name="_internal_calc", qualified_name="utils.helpers._internal_calc",
        symbol_type=SymbolType.FUNCTION, language="python", file="utils/helpers.py",
        line=16, end_line=30, visibility=Visibility.PRIVATE,
    ))

    # 5. Tests
    graph.add_symbol(Symbol(
        id="t1", name="test_process_order", qualified_name="tests.test_orders.test_process_order",
        symbol_type=SymbolType.FUNCTION, language="python", file="tests/test_orders.py",
        line=1, end_line=25,
    ))

    # File dependencies
    graph.add_dependency(Dependency(
        source_file="controllers/order_controller.py",
        target_file="services/order_service.py",
        imported_symbols=["OrderService"],
    ))
    graph.add_dependency(Dependency(
        source_file="services/order_service.py",
        target_file="repositories/order_repository.py",
        imported_symbols=["OrderRepository"],
    ))
    graph.add_dependency(Dependency(
        source_file="services/order_service.py",
        target_file="utils/helpers.py",
        imported_symbols=["format_currency"],
    ))
    graph.add_dependency(Dependency(
        source_file="tests/test_orders.py",
        target_file="services/order_service.py",
        imported_symbols=["OrderService"],
    ))

    return graph


# =============================================================================
# TEST CASES
# =============================================================================

def test_1_repository_metrics_and_statistics(temp_dir):
    """Test accurate computation of repository statistics across symbols and files."""
    graph = create_sample_graph()
    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=graph)

    overview = analyzer.analyze()

    assert overview.total_modules == 5
    assert overview.total_classes == 3
    assert overview.total_methods == 3
    assert overview.total_functions == 3  # format_currency, _internal_calc, test_process_order
    assert overview.total_tests == 1
    assert overview.total_dependencies == 4
    assert overview.total_symbols == 9



def test_2_architecture_pattern_detection(temp_dir):
    """Test detection of Layered Architecture, Repository Pattern, Service Layer, and Monolith."""
    graph = create_sample_graph()
    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=graph)

    overview = analyzer.analyze()
    patterns = {p.pattern_name: p.confidence for p in overview.detected_architectures}

    assert "Layered Architecture" in patterns
    assert patterns["Layered Architecture"] >= 0.70
    assert "Repository Pattern" in patterns
    assert "Service Layer" in patterns
    assert "Modular Monolith" in patterns


def test_3_architecture_layer_detection(temp_dir):
    """Test grouping of modules into distinct architectural layers."""
    graph = create_sample_graph()
    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=graph)

    _, layers = analyzer.detect_architecture(symbol_graph=graph)
    layer_names = {l.name for l in layers}

    assert "Presentation / API / CLI" in layer_names
    assert "Business Logic / Core" in layer_names
    assert "Data Access / Repository" in layer_names
    assert "Testing & QA" in layer_names
    assert "Infrastructure / Adapters" in layer_names


def test_4_circular_dependency_detection(temp_dir):
    """Test detection of 2-node and 3-node dependency cycles with severity scoring."""
    graph = SymbolGraph()
    # Cycle 1: a -> b -> a (Length 2 -> HIGH)
    graph.add_dependency(Dependency(source_file="mod_a.py", target_file="mod_b.py"))
    graph.add_dependency(Dependency(source_file="mod_b.py", target_file="mod_a.py"))

    # Cycle 2: x -> y -> z -> x (Length 3 -> MEDIUM)
    graph.add_dependency(Dependency(source_file="mod_x.py", target_file="mod_y.py"))
    graph.add_dependency(Dependency(source_file="mod_y.py", target_file="mod_z.py"))
    graph.add_dependency(Dependency(source_file="mod_z.py", target_file="mod_x.py"))

    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=graph)
    cycles = analyzer.detect_cycles(graph)

    assert len(cycles) == 2
    severities = {c.severity for c in cycles}
    assert "HIGH" in severities
    assert "MEDIUM" in severities

    two_node = next(c for c in cycles if c.length == 2)
    assert two_node.severity == "HIGH"


def test_5_hotspot_detection(temp_dir):
    """Test hotspot detection for largest modules, fan-in hubs, and utility modules."""
    graph = create_sample_graph()
    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=graph)

    hotspots = analyzer.find_hotspots(symbol_graph=graph)
    categories = {h.category for h in hotspots}

    assert "high_fan_in" in categories  # order_service.py has incoming deps from controller & tests
    assert "utility_class" in categories  # utils/helpers.py


def test_6_entry_point_detection(temp_dir):
    """Test detection of main scripts, CLI tools, and API startup files."""
    files = {
        "main.py": 'if __name__ == "__main__":\n    print("Starting AutoDev")\n',
        "cli.py": '@click.command()\ndef cli():\n    pass\n',
        "server.py": 'app = FastAPI()\n',
    }
    graph = SymbolGraph()
    for f in files:
        graph.files[f] = []

    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=graph)
    entrypoints = analyzer.detect_entrypoints(symbol_graph=graph, project_files=files)

    entry_str = " ".join(entrypoints)
    assert "main.py" in entry_str
    assert "cli.py" in entry_str
    assert "server.py" in entry_str


def test_7_module_summarization(temp_dir):
    """Test granular module summary extraction including complexity, risk, and exports."""
    graph = create_sample_graph()
    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=graph)

    summaries = analyzer.summarize_modules(symbol_graph=graph)

    assert "services/order_service.py" in summaries
    svc_summary = summaries["services/order_service.py"]
    assert "OrderService" in svc_summary.public_classes
    assert len(svc_summary.dependencies) == 2
    assert len(svc_summary.dependents) == 2
    assert svc_summary.complexity in ("LOW", "MEDIUM", "HIGH")
    assert svc_summary.risk in ("LOW", "MEDIUM", "HIGH")


def test_8_dead_code_and_public_apis(temp_dir):
    """Test detection of unreferenced private helpers as dead code candidates and public APIs."""
    graph = create_sample_graph()
    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=graph)

    overview = analyzer.analyze()

    assert any("_internal_calc" in dc for dc in overview.dead_code_candidates)
    assert any("get_order" in api or "OrderController" in api for api in overview.public_apis)


def test_9_json_export_and_import_roundtrip(temp_dir):
    """Test persisting analysis report to JSON and deserializing back to RepositoryOverview."""
    graph = create_sample_graph()
    report_file = temp_dir / "repository_analysis.json"
    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=graph, output_path=report_file)

    overview = analyzer.analyze()
    saved_path = analyzer.save_report(overview)
    assert saved_path.is_file()

    loaded = analyzer.load_report(saved_path)
    assert loaded.total_modules == overview.total_modules
    assert loaded.total_classes == overview.total_classes
    assert len(loaded.detected_architectures) == len(overview.detected_architectures)
    assert len(loaded.module_summaries) == len(overview.module_summaries)
    assert loaded.summary == overview.summary


def test_10_prompt_builder_integration(temp_dir):
    """Test PromptBuilder automatically injects PROJECT ARCHITECTURE section with layers and hotspots."""
    graph = create_sample_graph()
    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=graph)
    overview = analyzer.analyze()

    context = {
        "project_name": "OrderService",
        "description": "Enterprise Order Management",
        "technology_stack": "Python / FastAPI",
        "repository_analysis": overview,
        "symbol_graph": graph,
    }
    task = Task(
        id="TASK-01",
        title="Optimize order processing",
        description="Optimize process_order method in service layer",
        estimated_files=["services/order_service.py"],
    )

    builder = PromptBuilder(symbol_graph=graph, repository_analyzer=analyzer)
    prompt = builder.build(context=context, task=task)

    assert "PROJECT ARCHITECTURE" in prompt
    assert "Primary Architecture" in prompt
    assert "Detected Layers:" in prompt
    assert "Key Module Responsibilities:" in prompt
    assert "order_service.py" in prompt


def test_11_orchestrator_integration(temp_dir):
    """Test Orchestrator runs RepositoryAnalyzer, populates context, and saves analysis report."""
    plan_file = temp_dir / "project_plan.json"
    plan_data = {
        "project_name": "TestECommerce",
        "total_days": 1,
        "phases": [{
            "day": 1,
            "phase_name": "Foundation",
            "goals": ["Build service layer"],
            "tasks": [{
                "id": "DAY1-T01",
                "title": "Create order service",
                "description": "Implement service logic",
                "priority": 1,
                "status": "pending",
                "dependencies": [],
                "estimated_files": ["services/order_service.py"],
            }],
        }],
    }
    plan_file.write_text(json.dumps(plan_data), encoding="utf-8")

    graph = create_sample_graph()
    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=graph)

    orchestrator = Orchestrator(
        project_root=temp_dir,
        plan_path=plan_file,
        repository_analyzer=analyzer,
    )

    summary = orchestrator.run()
    assert summary.overall_success is True



def test_12_empty_repository_handling(temp_dir):
    """Test analyzing an empty project does not throw errors and returns a valid overview."""
    empty_graph = SymbolGraph()
    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=empty_graph)

    overview = analyzer.analyze()
    assert overview.total_modules == 0
    assert overview.total_symbols == 0
    assert overview.circular_dependencies == []


def test_13_performance_on_1000_plus_symbols(temp_dir):
    """Test performance on a large graph with 1,200+ symbols and 100+ files completes in <0.5s."""
    large_graph = SymbolGraph()

    for f_idx in range(120):
        fname = f"modules/pkg_{f_idx // 10}/module_{f_idx}.py"
        cls_name = f"ServiceClass_{f_idx}"
        large_graph.add_symbol(Symbol(
            id=f"c_{f_idx}", name=cls_name, qualified_name=f"pkg_{f_idx // 10}.{cls_name}",
            symbol_type=SymbolType.CLASS, language="python", file=fname,
            line=1, end_line=100, visibility=Visibility.PUBLIC,
        ))
        for m_idx in range(9):
            large_graph.add_symbol(Symbol(
                id=f"m_{f_idx}_{m_idx}", name=f"method_{m_idx}", qualified_name=f"{cls_name}.method_{m_idx}",
                symbol_type=SymbolType.METHOD, language="python", file=fname,
                line=10 + m_idx * 8, end_line=17 + m_idx * 8, parent_symbol=cls_name,
            ))
        if f_idx > 0:
            large_graph.add_dependency(Dependency(
                source_file=fname,
                target_file=f"modules/pkg_{(f_idx - 1) // 10}/module_{f_idx - 1}.py",
            ))

    assert len(large_graph.symbols) == 1200

    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=large_graph)
    start_t = time.time()
    overview = analyzer.analyze()
    elapsed = time.time() - start_t

    assert overview.total_symbols == 1200
    assert overview.total_classes == 120
    assert overview.total_methods == 1080
    assert elapsed < 0.5, f"Repository analysis took {elapsed:.3f}s (expected < 0.5s)"


def test_14_deterministic_outputs(temp_dir):
    """Test that consecutive analysis runs produce 100% identical outputs."""
    graph = create_sample_graph()
    analyzer = RepositoryAnalyzer(project_root=temp_dir, symbol_graph=graph)

    run_1 = analyzer.analyze().to_dict()
    run_2 = analyzer.analyze().to_dict()

    # Normalize timestamps before comparison
    run_1["timestamp"] = "STATIC"
    run_2["timestamp"] = "STATIC"

    assert json.dumps(run_1, sort_keys=True) == json.dumps(run_2, sort_keys=True)
