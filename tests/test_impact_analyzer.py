"""
test_impact_analyzer.py - Comprehensive Unit & Integration Tests for ImpactAnalyzer (v1.5)

Tests:
1. Graph traversal (call graph forward & reverse)
2. Dependency expansion (direct & transitive)
3. Cycle detection & recursion protection
4. Test discovery (file patterns, module stem, symbol references)
5. Confidence calculation
6. Risk scoring & level mapping (LOW, MEDIUM, HIGH, CRITICAL)
7. Large graph performance & scalability
8. Serialization & JSON roundtrip (to_dict, to_json, from_dict)
9. Edge cases (empty graph, missing symbol, dict task, None context)
10. PromptBuilder & Orchestrator integration
"""

import json
import time
from pathlib import Path
from typing import Any, Dict
import pytest

from agents.task_planner_agent import Task
from core.impact_analyzer import ImpactAnalyzer, ImpactNode, ImpactReport, RiskLevel
from core.prompt_builder import PromptBuilder
from core.symbol_graph import Dependency, Symbol, SymbolGraph, SymbolType, Visibility


@pytest.fixture
def complex_symbol_graph() -> SymbolGraph:
    """Constructs a complex, multi-module SymbolGraph for blast radius testing."""
    graph = SymbolGraph()

    # 1. Low Impact Private Helper
    private_helper = Symbol(
        id="src/utils.py::_internal_hash",
        name="_internal_hash",
        qualified_name="_internal_hash",
        symbol_type=SymbolType.FUNCTION,
        language="python",
        file="src/utils.py",
        line=1,
        end_line=10,
        visibility=Visibility.PRIVATE,
        docstring="Internal hashing utility.",
    )
    graph.add_symbol(private_helper)

    # 2. Interface with Implementations
    auth_interface = Symbol(
        id="src/interfaces.py::IAuthProvider",
        name="IAuthProvider",
        qualified_name="IAuthProvider",
        symbol_type=SymbolType.INTERFACE,
        language="python",
        file="src/interfaces.py",
        line=1,
        end_line=20,
        visibility=Visibility.PUBLIC,
        docstring="Core authentication interface.",
    )
    graph.add_symbol(auth_interface)
    graph.interface_implementers["IAuthProvider"] = {"DatabaseAuth", "LdapAuth", "OAuthProvider"}

    # 3. Base Class with Multiple Subclasses
    base_controller = Symbol(
        id="src/base_controller.py::BaseController",
        name="BaseController",
        qualified_name="BaseController",
        symbol_type=SymbolType.CLASS,
        language="python",
        file="src/base_controller.py",
        line=1,
        end_line=30,
        visibility=Visibility.PUBLIC,
        docstring="Root HTTP Controller abstraction.",
    )
    graph.add_symbol(base_controller)

    for name in ["UserController", "OrderController", "AdminController"]:
        sub_sym = Symbol(
            id=f"src/controllers.py::{name}",
            name=name,
            qualified_name=name,
            symbol_type=SymbolType.CLASS,
            language="python",
            file="src/controllers.py",
            line=10,
            end_line=50,
            inherits=["BaseController"],
            visibility=Visibility.PUBLIC,
        )
        graph.add_symbol(sub_sym)

    # 4. High-Impact Public Service with Multiple Callers
    core_service = Symbol(
        id="src/core_service.py::CoreService.process_payment",
        name="process_payment",
        qualified_name="CoreService.process_payment",
        symbol_type=SymbolType.METHOD,
        language="python",
        file="src/core_service.py",
        line=20,
        end_line=60,
        visibility=Visibility.PUBLIC,
        docstring="Primary financial transaction processor.",
    )
    graph.add_symbol(core_service)

    # 5 Callers for process_payment
    for idx in range(1, 6):
        caller_sym = Symbol(
            id=f"src/caller_{idx}.py::caller_{idx}",
            name=f"caller_{idx}",
            qualified_name=f"caller_{idx}",
            symbol_type=SymbolType.FUNCTION,
            language="python",
            file=f"src/caller_{idx}.py",
            line=1,
            end_line=15,
            visibility=Visibility.PUBLIC,
            calls=["process_payment"],
        )
        graph.add_symbol(caller_sym)
        graph.add_dependency(Dependency(f"src/caller_{idx}.py", "src/core_service.py", "import"))

    # 5. Transitive File Dependencies
    # src/caller_1.py <- src/gateway.py <- src/app.py
    graph.add_dependency(Dependency("src/gateway.py", "src/caller_1.py", "import"))
    graph.add_dependency(Dependency("src/app.py", "src/gateway.py", "import"))

    # 6. Test Files
    test_core = Symbol(
        id="tests/test_core_service.py::test_process_payment",
        name="test_process_payment",
        qualified_name="test_process_payment",
        symbol_type=SymbolType.FUNCTION,
        language="python",
        file="tests/test_core_service.py",
        line=1,
        end_line=20,
        visibility=Visibility.PUBLIC,
        calls=["process_payment"],
    )
    graph.add_symbol(test_core)
    graph.add_dependency(Dependency("tests/test_core_service.py", "src/core_service.py", "import"))

    return graph


# -----------------------------------------------------------------------------
# 1. Graph Traversal & Call Graph Expansion
# -----------------------------------------------------------------------------

def test_1_call_graph_traversal(complex_symbol_graph: SymbolGraph):
    """Test 1: Call graph traversal locates callers and callees with depth tracking."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph, max_depth=3)
    sym = complex_symbol_graph.find_symbol("CoreService.process_payment")
    assert sym is not None

    callers, callees, nodes = analyzer.expand_call_graph([sym], max_depth=3)
    assert len(callers) >= 5
    assert any("caller_1" in c for c in callers)
    assert len(nodes) >= 5
    assert all(isinstance(n, ImpactNode) for n in nodes)
    assert all(n.depth >= 1 for n in nodes)


# -----------------------------------------------------------------------------
# 2. Dependency Expansion
# -----------------------------------------------------------------------------

def test_2_dependency_graph_expansion(complex_symbol_graph: SymbolGraph):
    """Test 2: Traverses direct and transitive upstream and downstream file dependencies."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph, max_depth=3)
    all_files, deps, rev_deps = analyzer.expand_dependency_graph({"src/caller_1.py"}, max_depth=3)

    assert "src/gateway.py" in rev_deps
    assert "src/app.py" in rev_deps
    assert "src/core_service.py" in deps
    assert "src/caller_1.py" in all_files


# -----------------------------------------------------------------------------
# 3. Cycle Detection
# -----------------------------------------------------------------------------

def test_3_cycle_detection_in_call_and_dependency_graphs():
    """Test 3: Cyclic calls and circular module dependencies do not cause infinite loops."""
    cyclic_graph = SymbolGraph()

    # Create 3 mutually recursive symbols: A -> B -> C -> A
    sym_a = Symbol(
        id="a.py::func_a", name="func_a", qualified_name="func_a",
        symbol_type=SymbolType.FUNCTION, language="python", file="a.py",
        line=1, end_line=10, calls=["func_b"],
    )
    sym_b = Symbol(
        id="b.py::func_b", name="func_b", qualified_name="func_b",
        symbol_type=SymbolType.FUNCTION, language="python", file="b.py",
        line=1, end_line=10, calls=["func_c"],
    )
    sym_c = Symbol(
        id="c.py::func_c", name="func_c", qualified_name="func_c",
        symbol_type=SymbolType.FUNCTION, language="python", file="c.py",
        line=1, end_line=10, calls=["func_a"],
    )

    cyclic_graph.add_symbol(sym_a)
    cyclic_graph.add_symbol(sym_b)
    cyclic_graph.add_symbol(sym_c)

    # Circular file dependencies
    cyclic_graph.add_dependency(Dependency("a.py", "b.py", "import"))
    cyclic_graph.add_dependency(Dependency("b.py", "c.py", "import"))
    cyclic_graph.add_dependency(Dependency("c.py", "a.py", "import"))

    analyzer = ImpactAnalyzer(symbol_graph=cyclic_graph, max_depth=5)
    task = Task(id="CYCLE-01", title="Modify func_a in a.py", description="Cyclic test", estimated_files=["a.py"])

    # Must complete quickly and safely
    start_t = time.time()
    report = analyzer.analyze(task)
    duration = time.time() - start_t

    assert duration < 1.0
    assert "a.py" in report.affected_files
    assert "b.py" in report.affected_files
    assert "c.py" in report.affected_files


# -----------------------------------------------------------------------------
# 4. Test Discovery
# -----------------------------------------------------------------------------

def test_4_test_discovery(complex_symbol_graph: SymbolGraph):
    """Test 4: Discovers matching test suites for affected files and symbols."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    tests = analyzer.find_related_tests(
        affected_files={"src/core_service.py"},
        affected_symbols={"process_payment", "CoreService.process_payment"},
    )

    assert "tests/test_core_service.py" in tests


# -----------------------------------------------------------------------------
# 5. Confidence Calculation
# -----------------------------------------------------------------------------

def test_5_confidence_calculation(complex_symbol_graph: SymbolGraph):
    """Test 5: Calculates deterministic confidence scores bounded in [0.0, 1.0]."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    task = Task(
        id="TASK-CONF-01",
        title="Update process_payment",
        description="Process payment transaction overhaul",
        estimated_files=["src/core_service.py"],
    )

    report = analyzer.analyze(task)
    assert 0.0 <= report.confidence <= 1.0
    assert report.confidence >= 0.85


# -----------------------------------------------------------------------------
# 6. Risk Scoring & Classification
# -----------------------------------------------------------------------------

def test_6_risk_scoring_and_levels(complex_symbol_graph: SymbolGraph):
    """Test 6: Tests LOW, MEDIUM, HIGH, and CRITICAL risk classifications."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)

    # 1. Low Impact
    low_rep = analyzer.analyze_symbol("_internal_hash")
    assert low_rep.risk_level == RiskLevel.LOW
    assert low_rep.impact_score <= 25.0

    # 2. High / Critical Impact
    high_rep = analyzer.analyze_symbol("CoreService.process_payment")
    assert high_rep.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    assert high_rep.impact_score >= 51.0

    # 3. Base class modification
    base_rep = analyzer.analyze_symbol("BaseController")
    assert len(base_rep.subclasses) == 3
    assert base_rep.impact_score >= 40.0


# -----------------------------------------------------------------------------
# 7. Large Graph Performance
# -----------------------------------------------------------------------------

def test_7_large_graph_performance():
    """Test 7: Benchmarks analysis performance on a large graph (500+ symbols, 100+ files)."""
    large_graph = SymbolGraph()

    for i in range(100):
        fname = f"src/module_{i}.py"
        cls_name = f"Service_{i}"
        sym_cls = Symbol(
            id=f"{fname}::{cls_name}",
            name=cls_name,
            qualified_name=cls_name,
            symbol_type=SymbolType.CLASS,
            language="python",
            file=fname,
            line=1,
            end_line=50,
            visibility=Visibility.PUBLIC,
        )
        large_graph.add_symbol(sym_cls)

        for j in range(5):
            fn_name = f"method_{i}_{j}"
            sym_fn = Symbol(
                id=f"{fname}::{cls_name}.{fn_name}",
                name=fn_name,
                qualified_name=f"{cls_name}.{fn_name}",
                symbol_type=SymbolType.METHOD,
                language="python",
                file=fname,
                line=10 + j * 8,
                end_line=17 + j * 8,
                visibility=Visibility.PUBLIC,
                calls=[f"method_{max(0, i-1)}_{j}"],
            )
            large_graph.add_symbol(sym_fn)

        if i > 0:
            large_graph.add_dependency(Dependency(fname, f"src/module_{i-1}.py", "import"))

    analyzer = ImpactAnalyzer(symbol_graph=large_graph, max_depth=3)
    task = Task(
        id="LARGE-01",
        title="Refactor Service_50 and method_50_0",
        description="Scaling test on large symbol graph",
        estimated_files=["src/module_50.py"],
    )

    start_t = time.time()
    report = analyzer.analyze(task)
    duration = time.time() - start_t

    assert duration < 0.20  # Under 200ms
    assert report.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.MEDIUM}
    assert len(report.affected_files) > 0


# -----------------------------------------------------------------------------
# 8. Serialization & JSON Roundtrip
# -----------------------------------------------------------------------------

def test_8_serialization_and_json_roundtrip(complex_symbol_graph: SymbolGraph):
    """Test 8: Validates to_dict, to_json, and from_dict roundtrip."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    task = Task(
        id="SERIAL-01",
        title="Refactor process_payment",
        description="Serialization verification",
        estimated_files=["src/core_service.py"],
    )

    report = analyzer.analyze(task)
    report_dict = report.to_dict()

    assert "risk" in report_dict
    assert "risk_level" in report_dict
    assert "confidence" in report_dict
    assert "affected_files" in report_dict
    assert "affected_symbols" in report_dict
    assert "affected_tests" in report_dict
    assert "summary" in report_dict

    json_str = report.to_json()
    assert isinstance(json_str, str)

    restored = ImpactReport.from_dict(json.loads(json_str))
    assert restored.risk_level == report.risk_level
    assert restored.confidence == report.confidence
    assert restored.affected_files == report.affected_files


# -----------------------------------------------------------------------------
# 9. Edge Cases & Robustness
# -----------------------------------------------------------------------------

def test_9_edge_cases_empty_graph_and_missing_symbol(tmp_path: Path):
    """Test 9: Handles empty graph, missing symbols, and dictionary tasks gracefully."""
    empty_graph = SymbolGraph()
    analyzer = ImpactAnalyzer(symbol_graph=empty_graph, project_root=tmp_path)

    # Empty graph
    rep_empty = analyzer.analyze(Task(id="EMPTY-01", title="Empty task", description="No graph"))
    assert rep_empty.risk_level == RiskLevel.LOW
    assert rep_empty.impact_score == 0.0

    # Nonexistent symbol on populated graph
    nonexistent_rep = analyzer.analyze_symbol("UnknownClass.unknownMethod")
    assert nonexistent_rep.risk_level == RiskLevel.LOW

    # Dict task
    dict_task = {"id": "DICT-01", "title": "Dict Title", "description": "Dict Desc", "estimated_files": []}
    rep_dict = analyzer.analyze(dict_task)
    assert rep_dict.target == "DICT-01"


# -----------------------------------------------------------------------------
# 10. PromptBuilder & Orchestrator Integration
# -----------------------------------------------------------------------------

def test_10_prompt_builder_integration(complex_symbol_graph: SymbolGraph):
    """Test 10: Ensures PromptBuilder correctly formats and incorporates the impact report."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    builder = PromptBuilder(impact_analyzer=analyzer)

    task = Task(
        id="TASK-PAY-01",
        title="Refactor process_payment transaction engine",
        description="Core financial pipeline overhaul",
        estimated_files=["src/core_service.py"],
    )
    context = {
        "project_name": "PaymentCore",
        "description": "Payment Gateway Engine",
        "technology_stack": "Python 3.11",
        "current_day": 1,
        "current_phase": {"phase_name": "Phase 1", "goals": ["Payments"]},
        "directory_tree": ["src/core_service.py"],
        "project_files": {"src/core_service.py": "# source"},
    }

    prompt = builder.build(context=context, task=task)
    assert "7. CODE IMPACT ANALYSIS" in prompt
    assert "Risk Level" in prompt
    assert "Confidence:" in prompt
    assert "src/core_service.py" in prompt
    assert "tests/test_core_service.py" in prompt
    assert "Summary:" in prompt
