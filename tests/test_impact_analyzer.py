"""
test_impact_analyzer.py - Comprehensive Unit & Integration Tests for ImpactAnalyzer (v1.5)
"""

from pathlib import Path
from typing import Any, Dict
import pytest

from agents.task_planner_agent import Task
from core.impact_analyzer import ImpactAnalyzer, ImpactReport, RiskLevel
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
# Test Cases
# -----------------------------------------------------------------------------

def test_1_low_impact_private_helper(complex_symbol_graph: SymbolGraph):
    """Test 1: Private isolated helper receives LOW risk level and low score."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    report = analyzer.analyze_symbol("_internal_hash")

    assert isinstance(report, ImpactReport)
    assert report.target == "_internal_hash"
    assert report.risk_level == RiskLevel.LOW
    assert report.impact_score <= 25.0
    assert len(report.callers) == 0


def test_2_high_impact_public_service(complex_symbol_graph: SymbolGraph):
    """Test 2: Widely-invoked public method receives HIGH/CRITICAL risk level."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    report = analyzer.analyze_symbol("CoreService.process_payment")

    assert report.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    assert report.impact_score >= 51.0
    assert len(report.callers) >= 5
    assert len(report.affected_files) >= 5


def test_3_interface_modification(complex_symbol_graph: SymbolGraph):
    """Test 3: Interface modification detects implementers and breaking change risks."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    report = analyzer.analyze_symbol("IAuthProvider")

    assert len(report.implementations) == 3
    assert any("DatabaseAuth" in impl for impl in report.implementations)
    assert any("implemented by 3 class(es)" in risk for risk in report.breaking_change_risks)
    assert report.impact_score >= 40.0


def test_4_base_class_modification(complex_symbol_graph: SymbolGraph):
    """Test 4: Base class modification detects subclasses and inheritance risks."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    report = analyzer.analyze_symbol("BaseController")

    assert len(report.subclasses) == 3
    assert any("UserController" in sub for sub in report.subclasses)
    assert any("subclass(es)" in risk for risk in report.breaking_change_risks)


def test_5_multiple_callers(complex_symbol_graph: SymbolGraph):
    """Test 5: Correctly enumerates and scales risk for multiple callers."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    report = analyzer.analyze_symbol("process_payment")

    assert len(report.callers) >= 5
    assert all(f"caller_{i}" in str(report.callers) for i in range(1, 6))


def test_6_reverse_dependency_detection(complex_symbol_graph: SymbolGraph):
    """Test 6: File impact analysis traverses direct and transitive reverse dependents via BFS."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    report = analyzer.analyze_file("src/caller_1.py")

    assert "src/gateway.py" in report.direct_dependents
    assert "src/app.py" in report.transitive_dependents


def test_7_test_impact_detection(complex_symbol_graph: SymbolGraph):
    """Test 7: Identifies affected test files and includes them in validation recommendations."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    report = analyzer.analyze_symbol("process_payment")

    assert "tests/test_core_service.py" in report.affected_tests
    assert any("test suite" in val.lower() for val in report.recommended_validation)


def test_8_risk_scoring_brackets():
    """Test 8: Validates score to RiskLevel mapping for all 4 brackets."""
    assert RiskLevel.from_score(0.0) == RiskLevel.LOW
    assert RiskLevel.from_score(25.0) == RiskLevel.LOW
    assert RiskLevel.from_score(26.0) == RiskLevel.MEDIUM
    assert RiskLevel.from_score(50.0) == RiskLevel.MEDIUM
    assert RiskLevel.from_score(51.0) == RiskLevel.HIGH
    assert RiskLevel.from_score(75.0) == RiskLevel.HIGH
    assert RiskLevel.from_score(76.0) == RiskLevel.CRITICAL
    assert RiskLevel.from_score(100.0) == RiskLevel.CRITICAL


def test_9_deterministic_result(complex_symbol_graph: SymbolGraph):
    """Test 9: Repeating impact analysis on identical symbol yields identical report."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    rep1 = analyzer.analyze_symbol("CoreService.process_payment")
    rep2 = analyzer.analyze_symbol("CoreService.process_payment")

    assert rep1.to_dict() == rep2.to_dict()


def test_10_missing_symbol_graceful_handling(complex_symbol_graph: SymbolGraph):
    """Test 10: Analyzing nonexistent symbol returns safe LOW risk report without error."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    report = analyzer.analyze_symbol("NonexistentSymbol_123")

    assert report.risk_level == RiskLevel.LOW
    assert report.impact_score == 0.0
    assert any("not found" in r.lower() for r in report.breaking_change_risks)


def test_11_file_impact_analysis(complex_symbol_graph: SymbolGraph):
    """Test 11: Analyzes entire source file and computes comprehensive blast radius."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    report = analyzer.analyze_file("src/core_service.py")

    assert report.target == "src/core_service.py"
    assert len(report.direct_dependents) >= 5
    assert "tests/test_core_service.py" in report.affected_tests
    assert report.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}


def test_12_task_impact_analysis(complex_symbol_graph: SymbolGraph):
    """Test 12: Aggregates impact across task title keywords and estimated files."""
    analyzer = ImpactAnalyzer(symbol_graph=complex_symbol_graph)
    task = Task(
        id="TASK-PAY-01",
        title="Refactor process_payment transaction engine",
        description="Core financial pipeline overhaul",
        estimated_files=["src/core_service.py"],
    )

    report = analyzer.analyze_task(task)
    assert report.target == "TASK-PAY-01"
    assert "src/core_service.py" in report.affected_files
    assert len(report.callers) >= 5
    assert report.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
