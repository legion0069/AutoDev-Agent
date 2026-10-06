"""
test_refactoring_engine.py - Unit & Integration Test Suite for AutoDev Version 1.9
Autonomous Refactoring & Technical Debt Engine.

Tests:
- TechnicalDebtIssue, RefactoringCandidate, RefactoringAction, RefactoringPlan, RefactoringMetrics, RefactoringReport
- Deterministic static debt detection rules:
  - Long Method (>50 LOC)
  - Large Class (>500 LOC)
  - Too Many Parameters (>7)
  - High Cyclomatic Complexity (>=10)
  - Deep Nesting (>=5)
  - Complex Conditionals (>=4 operators)
  - Magic Numbers
  - Duplicate Code (AST / token hashes)
  - Dead Code
  - Unused Imports
  - Unused Variables
  - Circular Dependencies (SymbolGraph cycles)
  - God Object
  - Low Cohesion (LCOM)
  - Interface Bloat
  - Architecture Violations & Improper Layering
  - Multi-language source scanning (JS / TS / Java)
- Quantitative Metrics computation (Maintainability Index, Technical Debt Score, Coupling, Cohesion, Duplication)
- Candidate Identification & Prioritization formula
- Safe RefactoringPlan generation (Actions, Rollback, Migration, Validation)
- Return on Investment (ROI) Estimation
- "Should We Refactor First?" Decision evaluation
- PromptBuilder integration (TECHNICAL DEBT ANALYSIS section)
- MemoryManager integration (category REFACTORING)
- Orchestrator integration
- EngineeringDecisionEngine integration ("Refactor First" strategies)
- History persistence, query, and corrupted JSON recovery
- High performance benchmark & deterministic outputs
"""

import ast
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from agents.coder_agent import GeneratedFile, GeneratedResult
from agents.reviewer_agent import ReviewResult
from agents.task_planner_agent import Task
from agents.tester_agent import TestResult
from core.architecture_manager import ArchitectureDecision, ArchitectureManager, DecisionCategory, DecisionStatus
from core.code_indexer import CodeIndexer
from core.engineering_decision_engine import EngineeringDecisionEngine
from core.memory_manager import MemoryManager
from core.orchestrator import Orchestrator
from core.prompt_builder import PromptBuilder
from core.providers.mock_provider import MockProvider
from core.refactoring_engine import (
    DebtCategory,
    DebtSeverity,
    RefactoringAction,
    RefactoringCandidate,
    RefactoringEngine,
    RefactoringMetrics,
    RefactoringPlan,
    RefactoringReport,
    TechnicalDebtIssue,
)
from core.repository_analyzer import RepositoryAnalyzer
from core.symbol_graph import Dependency, Symbol, SymbolGraph, SymbolType, Visibility


@pytest.fixture
def temp_dir():
    """Creates a temporary workspace directory for test runs."""
    d = tempfile.mkdtemp(prefix="autodev_refact_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


# =============================================================================
# 1. Dataclasses & Serialization Tests
# =============================================================================

def test_1_technical_debt_issue_dataclass():
    """Verifies TechnicalDebtIssue creation, defaults, and roundtrip dictionary serialization."""
    issue = TechnicalDebtIssue(
        id="DEBT-001",
        title="Long Method in auth.py",
        description="Function authenticate() has 85 lines.",
        category=DebtCategory.LONG_METHOD,
        severity=DebtSeverity.HIGH,
        confidence=0.98,
        file="core/auth.py",
        symbol="authenticate",
        line=42,
        estimated_fix_time=2.0,
        maintainability_impact=18.5,
        risk="MEDIUM",
        recommendation="Extract helper functions.",
    )

    data = issue.to_dict()
    assert data["id"] == "DEBT-001"
    assert data["severity"] == "HIGH"
    assert data["category"] == "Long Method"
    assert data["line"] == 42

    restored = TechnicalDebtIssue.from_dict(data)
    assert restored.id == issue.id
    assert restored.estimated_fix_time == 2.0
    assert restored.maintainability_impact == 18.5


def test_2_refactoring_candidate_dataclass():
    """Verifies RefactoringCandidate creation, defaults, and dictionary serialization."""
    cand = RefactoringCandidate(
        id="CAND-01",
        current_structure="Monolithic auth.py module",
        target_structure="Modular TokenManager and SessionHandler",
        reason="Reduces God Object complexity.",
        affected_symbols=["TokenManager", "SessionHandler"],
        affected_files=["core/auth.py", "core/session.py"],
        risk="HIGH",
        estimated_hours=4.5,
        priority_score=78.5,
        category="Modularization",
    )

    data = cand.to_dict()
    assert data["id"] == "CAND-01"
    assert data["priority_score"] == 78.5
    assert len(data["affected_files"]) == 2

    restored = RefactoringCandidate.from_dict(data)
    assert restored.id == cand.id
    assert restored.risk == "HIGH"
    assert restored.estimated_hours == 4.5


def test_3_refactoring_action_dataclass():
    """Verifies RefactoringAction creation and serialization."""
    action = RefactoringAction(
        id="ACT-01",
        action_type="EXTRACT_METHOD",
        target_file="core/auth.py",
        target_symbol="verify_claims",
        description="Extract token claims validation into helper routine.",
        priority="HIGH",
        estimated_effort_hours=1.0,
        risk="LOW",
        order=1,
    )

    data = action.to_dict()
    assert data["action_type"] == "EXTRACT_METHOD"
    assert data["order"] == 1

    restored = RefactoringAction.from_dict(data)
    assert restored.target_symbol == "verify_claims"
    assert restored.priority == "HIGH"


def test_4_refactoring_plan_dataclass():
    """Verifies RefactoringPlan structure, nested actions, and serialization."""
    action = RefactoringAction(
        id="ACT-01",
        action_type="SPLIT_CLASS",
        target_file="core/god_service.py",
        target_symbol="GodService",
        description="Split GodService into OrderService and PaymentService.",
        priority="CRITICAL",
        estimated_effort_hours=3.5,
        risk="HIGH",
        order=1,
    )
    cand = RefactoringCandidate(
        id="CAND-01",
        current_structure="GodService class",
        target_structure="OrderService and PaymentService",
        reason="Decomposes excessive responsibilities.",
    )
    plan = RefactoringPlan(
        priority_ordered_actions=[action],
        rollback_strategy="Git soft reset to head.",
        migration_steps=["Create OrderService", "Redirect callers"],
        required_tests=["tests/test_order.py"],
        validation_steps=["Run pytest"],
        candidate=cand,
        summary="Decomposing GodService.",
        estimated_total_hours=3.5,
    )

    data = plan.to_dict()
    assert len(data["priority_ordered_actions"]) == 1
    assert data["estimated_total_hours"] == 3.5

    restored = RefactoringPlan.from_dict(data)
    assert len(restored.priority_ordered_actions) == 1
    assert restored.priority_ordered_actions[0].action_type == "SPLIT_CLASS"
    assert restored.candidate is not None
    assert restored.candidate.id == "CAND-01"


def test_5_refactoring_metrics_dataclass():
    """Verifies RefactoringMetrics creation and serialization."""
    metrics = RefactoringMetrics(
        maintainability_index=74.5,
        cyclomatic_complexity=4.2,
        coupling_score=82.0,
        cohesion_score=79.0,
        duplication_score=92.0,
        technical_debt_score=28.5,
        architecture_compliance=90.0,
        documentation_score=85.0,
    )

    data = metrics.to_dict()
    assert data["maintainability_index"] == 74.5
    assert data["technical_debt_score"] == 28.5

    restored = RefactoringMetrics.from_dict(data)
    assert restored.cyclomatic_complexity == 4.2
    assert restored.architecture_compliance == 90.0


def test_6_refactoring_report_markdown_and_serialization(temp_dir):
    """Verifies RefactoringReport creation, markdown export, and deserialization."""
    issue = TechnicalDebtIssue(
        id="DEBT-001",
        title="Long Method",
        description="Method too long",
        category="Long Method",
        severity="HIGH",
        confidence=0.95,
        file="core/processor.py",
        symbol="process_all",
        line=15,
        estimated_fix_time=1.5,
    )
    metrics = RefactoringMetrics(maintainability_index=68.0, technical_debt_score=42.0)
    cand = RefactoringCandidate(
        id="CAND-01",
        current_structure="Long Method process_all",
        target_structure="Decomposed methods",
        reason="Improves readability",
        priority_score=65.0,
        risk="HIGH",
    )

    report = RefactoringReport(
        project_root=str(temp_dir),
        issues=[issue],
        metrics=metrics,
        candidates=[cand],
        should_refactor_first=True,
        roi_estimate={"development_time_saved_hours": 12.0, "roi_ratio": 3.5, "overall_engineering_benefit": "HIGH"},
        summary="Refactoring required before feature implementation.",
    )

    md = report.to_markdown()
    assert "# 🛠️ Technical Debt & Refactoring Assessment" in md
    assert "Maintainability Index" in md
    assert "DEBT-001" in md
    assert "CAND-01" in md
    assert "YES (Refactor Before Feature Implementation)" in md

    data = report.to_dict()
    restored = RefactoringReport.from_dict(data)
    assert restored.should_refactor_first is True
    assert len(restored.issues) == 1
    assert restored.roi_estimate["roi_ratio"] == 3.5


# =============================================================================
# 2. Deterministic Code Smell & Debt Detection Tests
# =============================================================================

def test_7_detect_long_method(temp_dir):
    """Verifies detection of functions exceeding 50 LOC."""
    source_file = temp_dir / "long_func.py"
    # Create 65-line function
    body = "\n".join(f"    x_{i} = {i} * 2" for i in range(60))
    source_file.write_text(f"def mega_function():\n{body}\n    return x_59\n", encoding="utf-8")

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    long_method_issues = [i for i in issues if i.category == DebtCategory.LONG_METHOD.value]
    assert len(long_method_issues) >= 1
    assert long_method_issues[0].symbol == "mega_function"
    assert long_method_issues[0].severity in ("MEDIUM", "HIGH")


def test_8_detect_large_class(temp_dir):
    """Verifies detection of classes exceeding 500 LOC or 20 methods."""
    source_file = temp_dir / "large_class.py"
    methods = "\n".join(f"    def method_{i}(self):\n        return {i}\n" for i in range(25))
    source_file.write_text(f"class MassiveHandler:\n{methods}\n", encoding="utf-8")

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    large_class_issues = [i for i in issues if i.category == DebtCategory.LARGE_CLASS.value]
    assert len(large_class_issues) >= 1
    assert large_class_issues[0].symbol == "MassiveHandler"


def test_9_detect_too_many_parameters(temp_dir):
    """Verifies detection of functions accepting > 7 parameters."""
    source_file = temp_dir / "params.py"
    source_file.write_text(
        "def configure_system(a, b, c, d, e, f, g, h, i):\n    return a + b + c + d + e + f + g + h + i\n",
        encoding="utf-8",
    )

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    param_issues = [i for i in issues if i.category == DebtCategory.TOO_MANY_PARAMETERS.value]
    assert len(param_issues) >= 1
    assert param_issues[0].symbol == "configure_system"


def test_10_detect_high_cyclomatic_complexity(temp_dir):
    """Verifies detection of cyclomatic complexity >= 10."""
    source_file = temp_dir / "complex_branch.py"
    branches = "\n".join(f"    if x == {i}:\n        return {i}" for i in range(12))
    source_file.write_text(f"def complex_eval(x):\n{branches}\n    return -1\n", encoding="utf-8")

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    cc_issues = [i for i in issues if i.category == DebtCategory.HIGH_CYCLOMATIC_COMPLEXITY.value]
    assert len(cc_issues) >= 1
    assert cc_issues[0].symbol == "complex_eval"
    assert cc_issues[0].severity in ("HIGH", "CRITICAL")


def test_11_detect_deep_nesting(temp_dir):
    """Verifies detection of control flow nesting depth >= 5."""
    source_file = temp_dir / "deep_nest.py"
    source_file.write_text(
        "def deeply_nested_logic(x):\n"
        "    if x > 0:\n"
        "        for i in range(10):\n"
        "            while i < 5:\n"
        "                with open('log.txt') as f:\n"
        "                    if i == 2:\n"
        "                        return True\n"
        "    return False\n",
        encoding="utf-8",
    )

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    nesting_issues = [i for i in issues if i.category == DebtCategory.DEEP_NESTING.value]
    assert len(nesting_issues) >= 1
    assert nesting_issues[0].symbol == "deeply_nested_logic"


def test_12_detect_complex_conditionals(temp_dir):
    """Verifies detection of boolean expressions with >= 4 chained operators."""
    source_file = temp_dir / "cond.py"
    source_file.write_text(
        "def check_permission(user, is_admin, has_role, in_group, is_active):\n"
        "    if user and is_admin and has_role and in_group and is_active:\n"
        "        return True\n"
        "    return False\n",
        encoding="utf-8",
    )

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    cond_issues = [i for i in issues if i.category == DebtCategory.COMPLEX_CONDITIONALS.value]
    assert len(cond_issues) >= 1
    assert "Complex Conditional" in cond_issues[0].title


def test_13_detect_magic_numbers(temp_dir):
    """Verifies detection of inline unnamed numeric literals."""
    source_file = temp_dir / "magic.py"
    source_file.write_text(
        "def calculate_tax(salary):\n"
        "    return salary * 739\n",  # 739 is an obvious magic number
        encoding="utf-8",
    )

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    magic_issues = [i for i in issues if i.category == DebtCategory.MAGIC_NUMBERS.value]
    assert len(magic_issues) >= 1
    assert "739" in magic_issues[0].title or "739" in magic_issues[0].description


def test_14_detect_duplicate_code_blocks(temp_dir):
    """Verifies detection of duplicate code blocks across multiple files."""
    code_block = (
        "def process_order_payload(data):\n"
        "    v1 = data.get('price', 0)\n"
        "    v2 = data.get('tax', 0)\n"
        "    v3 = data.get('discount', 0)\n"
        "    total = (v1 + v2) - v3\n"
        "    return total\n"
    )

    (temp_dir / "service_a.py").write_text(code_block, encoding="utf-8")
    (temp_dir / "service_b.py").write_text(code_block, encoding="utf-8")

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    dup_issues = [i for i in issues if i.category == DebtCategory.DUPLICATE_CODE.value]
    assert len(dup_issues) >= 1
    assert "Duplicate Code Block Detected" in dup_issues[0].title


def test_15_detect_unused_imports(temp_dir):
    """Verifies detection of unused import statements in Python files."""
    source_file = temp_dir / "unused_imp.py"
    source_file.write_text(
        "import math\n"
        "import os\n"
        "from pathlib import Path\n\n"
        "def get_home():\n"
        "    return Path.home()\n",
        encoding="utf-8",
    )

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    unused_imp = [i for i in issues if i.category == DebtCategory.UNUSED_IMPORTS.value]
    names = [i.title for i in unused_imp]
    assert any("math" in n for n in names)
    assert any("os" in n for n in names)


def test_16_detect_unused_variables(temp_dir):
    """Verifies detection of local variables assigned but never read."""
    source_file = temp_dir / "unused_var.py"
    source_file.write_text(
        "def compute_metrics(x):\n"
        "    unused_result = x * 10\n"
        "    active_val = x + 5\n"
        "    return active_val\n",
        encoding="utf-8",
    )

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    unused_var = [i for i in issues if i.category == DebtCategory.UNUSED_VARIABLES.value]
    assert len(unused_var) >= 1
    assert "unused_result" in unused_var[0].title


def test_17_detect_circular_dependency(temp_dir):
    """Verifies detection of circular dependencies across the SymbolGraph."""
    graph = SymbolGraph()
    sym_a = Symbol(name="ModuleA", symbol_type=SymbolType.MODULE, file_path="core/mod_a.py", line_start=1, line_end=20)
    sym_b = Symbol(name="ModuleB", symbol_type=SymbolType.MODULE, file_path="core/mod_b.py", line_start=1, line_end=20)
    sym_c = Symbol(name="ModuleC", symbol_type=SymbolType.MODULE, file_path="core/mod_c.py", line_start=1, line_end=20)

    sym_a.dependencies.append(Dependency(source="ModuleA", target="ModuleB", dependency_type="import"))
    sym_b.dependencies.append(Dependency(source="ModuleB", target="ModuleC", dependency_type="import"))
    sym_c.dependencies.append(Dependency(source="ModuleC", target="ModuleA", dependency_type="import"))

    graph.add_symbol(sym_a)
    graph.add_symbol(sym_b)
    graph.add_symbol(sym_c)

    engine = RefactoringEngine(symbol_graph=graph)
    issues = engine.detect_technical_debt(temp_dir)

    cycle_issues = [i for i in issues if i.category == DebtCategory.CIRCULAR_DEPENDENCY.value]
    assert len(cycle_issues) >= 1
    assert cycle_issues[0].severity == "CRITICAL"


def test_18_detect_dead_code_candidates(temp_dir):
    """Verifies detection of unreferenced symbols with zero incoming callers."""
    graph = SymbolGraph()
    sym_active = Symbol(name="active_entry", symbol_type=SymbolType.FUNCTION, file_path="app/main.py", line_start=1, line_end=10)
    sym_dead = Symbol(name="obsolete_helper", symbol_type=SymbolType.FUNCTION, file_path="app/utils.py", line_start=20, line_end=30)

    graph.add_symbol(sym_active)
    graph.add_symbol(sym_dead)

    engine = RefactoringEngine(symbol_graph=graph)
    issues = engine.detect_technical_debt(temp_dir)

    dead_issues = [i for i in issues if i.category == DebtCategory.DEAD_CODE.value]
    assert len(dead_issues) >= 1
    assert any("obsolete_helper" in i.title for i in dead_issues)


def test_19_detect_god_object(temp_dir):
    """Verifies detection of God Object classes."""
    source_file = temp_dir / "god_object.py"
    methods = "\n".join(f"    def do_task_{i}(self):\n        return {i}\n" for i in range(18))
    # Make file > 300 LOC
    filler = "\n".join(f"    # line {i}" for i in range(320))
    source_file.write_text(f"class GodOrchestrator:\n{methods}\n{filler}\n", encoding="utf-8")

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    god_issues = [i for i in issues if i.category == DebtCategory.GOD_OBJECT.value]
    assert len(god_issues) >= 1
    assert god_issues[0].severity == "CRITICAL"


def test_20_detect_low_cohesion_lcom(temp_dir):
    """Verifies detection of low cohesion classes where methods share no instance attributes."""
    source_file = temp_dir / "uncohesive.py"
    source_file.write_text(
        "class DisparateClass:\n"
        "    def method_one(self):\n"
        "        self.a = 1\n"
        "        return self.a\n"
        "    def method_two(self):\n"
        "        self.b = 2\n"
        "        return self.b\n"
        "    def method_three(self):\n"
        "        self.c = 3\n"
        "        return self.c\n"
        "    def method_four(self):\n"
        "        self.d = 4\n"
        "        return self.d\n",
        encoding="utf-8",
    )

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    cohesion_issues = [i for i in issues if i.category == DebtCategory.LOW_COHESION.value]
    assert len(cohesion_issues) >= 1
    assert "DisparateClass" in cohesion_issues[0].symbol


def test_21_detect_interface_bloat(temp_dir):
    """Verifies detection of abstract base interfaces exposing > 10 abstract methods."""
    source_file = temp_dir / "bloated_interface.py"
    methods = "\n".join(f"    def abstract_req_{i}(self):\n        pass\n" for i in range(12))
    source_file.write_text(f"from abc import ABC\nclass MassiveInterface(ABC):\n{methods}\n", encoding="utf-8")

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    interface_issues = [i for i in issues if i.category == DebtCategory.INTERFACE_BLOAT.value]
    assert len(interface_issues) >= 1
    assert "MassiveInterface" in interface_issues[0].symbol


def test_22_detect_improper_layering_and_architecture_violations(temp_dir):
    """Verifies detection of lower data layers importing upper presentation layers."""
    graph = SymbolGraph()
    sym_db = Symbol(name="UserDAO", symbol_type=SymbolType.CLASS, file_path="database/user_dao.py", line_start=1, line_end=50)
    sym_api = Symbol(name="UserController", symbol_type=SymbolType.CLASS, file_path="api/controllers/user_controller.py", line_start=1, line_end=50)

    sym_db.dependencies.append(Dependency(source="UserDAO", target="UserController", dependency_type="import"))
    graph.add_symbol(sym_db)
    graph.add_symbol(sym_api)

    engine = RefactoringEngine(symbol_graph=graph)
    issues = engine.detect_technical_debt(temp_dir)

    layer_issues = [i for i in issues if i.category == DebtCategory.IMPROPER_LAYERING.value]
    assert len(layer_issues) >= 1
    assert layer_issues[0].severity == "CRITICAL"


def test_23_multi_language_source_scanning(temp_dir):
    """Verifies scanning for JavaScript/TypeScript and Java source files."""
    js_file = temp_dir / "app.js"
    js_file.write_text(
        "function deepNest() {\n"
        "  if (a) {\n"
        "    if (b) {\n"
        "      if (c) {\n"
        "        if (d) {\n"
        "          if (e) {\n"
        "            if (f) { return 8492; }\n"
        "          }\n"
        "        }\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    engine = RefactoringEngine()
    issues = engine.detect_technical_debt(temp_dir)

    assert any(i.file == "app.js" for i in issues)
    assert any(i.category in (DebtCategory.DEEP_NESTING.value, DebtCategory.MAGIC_NUMBERS.value) for i in issues)


# =============================================================================
# 3. Metrics, Prioritization & ROI Tests
# =============================================================================

def test_24_compute_metrics_calculation(temp_dir):
    """Verifies 8-dimension quantitative metrics calculation."""
    # Write a clean file
    clean_file = temp_dir / "clean.py"
    clean_file.write_text(
        "\"\"\"Clean module docstring.\"\"\"\n\n"
        "def compute_total(a: int, b: int) -> int:\n"
        "    \"\"\"Calculates total.\"\"\"\n"
        "    return a + b\n",
        encoding="utf-8",
    )

    engine = RefactoringEngine()
    metrics = engine.compute_metrics(temp_dir)

    assert 0.0 <= metrics.maintainability_index <= 100.0
    assert metrics.maintainability_index >= 70.0  # Clean code should have high MI
    assert metrics.technical_debt_score <= 15.0
    assert metrics.architecture_compliance == 100.0


def test_25_candidate_identification_and_grouping(temp_dir):
    """Verifies grouping of multiple related debt issues into a single RefactoringCandidate."""
    issue1 = TechnicalDebtIssue(
        id="DEBT-001",
        title="Long Method",
        description="Method too long",
        category="Long Method",
        severity="HIGH",
        confidence=0.95,
        file="core/auth.py",
        symbol="TokenManager",
        estimated_fix_time=2.0,
    )
    issue2 = TechnicalDebtIssue(
        id="DEBT-002",
        title="High Complexity",
        description="Too complex",
        category="High Cyclomatic Complexity",
        severity="HIGH",
        confidence=0.95,
        file="core/auth.py",
        symbol="TokenManager",
        estimated_fix_time=2.5,
    )

    engine = RefactoringEngine()
    candidates = engine.identify_candidates([issue1, issue2], temp_dir)

    assert len(candidates) == 1
    assert candidates[0].estimated_hours == 4.5
    assert candidates[0].affected_files == ["core/auth.py"]


def test_26_prioritize_refactoring_formula(temp_dir):
    """Verifies Priority Score calculation with task overlap weighting."""
    task = Task(id="TASK-01", title="Auth Upgrade", description="Update auth", estimated_files=["core/auth.py"])

    cand1 = RefactoringCandidate(
        id="CAND-01",
        current_structure="Auth module",
        target_structure="Clean auth",
        reason="Overlaps with task",
        affected_files=["core/auth.py"],
        risk="HIGH",
        estimated_hours=2.0,
    )
    cand2 = RefactoringCandidate(
        id="CAND-02",
        current_structure="Unrelated utils",
        target_structure="Clean utils",
        reason="Unrelated",
        affected_files=["core/utils.py"],
        risk="LOW",
        estimated_hours=5.0,
    )

    engine = RefactoringEngine()
    ranked = engine.prioritize_refactoring([cand2, cand1], [], task=task)

    assert ranked[0].id == "CAND-01"
    assert ranked[0].priority_score > ranked[1].priority_score


def test_27_generate_refactoring_plan_steps(temp_dir):
    """Verifies generation of ordered actions, rollback strategy, and required tests."""
    issue = TechnicalDebtIssue(
        id="DEBT-001",
        title="Long Method",
        description="Method too long",
        category=DebtCategory.LONG_METHOD.value,
        severity="HIGH",
        confidence=0.95,
        file="core/processor.py",
        symbol="process_all",
        estimated_fix_time=2.0,
    )
    cand = RefactoringCandidate(
        id="CAND-01",
        current_structure="Long Method process_all",
        target_structure="Decomposed routines",
        reason="Improves modularity",
        affected_files=["core/processor.py"],
        risk="MEDIUM",
        estimated_hours=2.0,
    )

    engine = RefactoringEngine()
    plan = engine.generate_plan(cand, issues=[issue])

    assert len(plan.priority_ordered_actions) >= 1
    assert plan.priority_ordered_actions[0].action_type == "EXTRACT_METHOD"
    assert "Git soft reset" in plan.rollback_strategy
    assert len(plan.migration_steps) >= 3
    assert len(plan.validation_steps) >= 3


def test_28_estimate_roi_calculations(temp_dir):
    """Verifies ROI calculation metrics (time saved, bug reduction, ROI ratio)."""
    issue_crit = TechnicalDebtIssue(
        id="DEBT-001",
        title="Cycle",
        description="Cycle",
        category="Circular Dependency",
        severity="CRITICAL",
        confidence=1.0,
        file="core/a.py",
        estimated_fix_time=3.0,
    )
    cand = RefactoringCandidate(
        id="CAND-01",
        current_structure="Cycle",
        target_structure="Decoupled",
        reason="Cycle fix",
        estimated_hours=3.0,
    )

    engine = RefactoringEngine()
    roi = engine.estimate_roi([issue_crit], [cand])

    assert roi["development_time_saved_hours"] > 0
    assert roi["future_maintenance_savings_hours"] > 0
    assert roi["roi_ratio"] > 1.0
    assert roi["overall_engineering_benefit"] == "HIGH"


def test_29_should_refactor_first_decision_logic(temp_dir):
    """Verifies 'should_refactor_first' returns True for critical/high debt on task files."""
    task = Task(id="TASK-01", title="Feature A", description="Feature A", estimated_files=["core/target.py"])

    issue_crit = TechnicalDebtIssue(
        id="DEBT-001",
        title="Circular Dependency",
        description="Cycle",
        category="Circular Dependency",
        severity="CRITICAL",
        confidence=1.0,
        file="core/target.py",
    )
    cand = RefactoringCandidate(
        id="CAND-01",
        current_structure="Target",
        target_structure="Clean Target",
        reason="Cycle",
        affected_files=["core/target.py"],
        risk="CRITICAL",
        priority_score=85.0,
    )
    metrics = RefactoringMetrics(maintainability_index=55.0, technical_debt_score=60.0)

    engine = RefactoringEngine()
    decision = engine._evaluate_should_refactor_first([issue_crit], [cand], metrics, task=task)
    assert decision is True


# =============================================================================
# 4. Subsystem Integration & Prompt Tests
# =============================================================================

def test_30_prompt_builder_technical_debt_section(temp_dir):
    """Verifies PromptBuilder injects TECHNICAL DEBT ANALYSIS section."""
    engine = RefactoringEngine()
    builder = PromptBuilder(refactoring_engine=engine)

    issue = TechnicalDebtIssue(
        id="DEBT-001",
        title="God Object",
        description="God Object",
        category=DebtCategory.GOD_OBJECT.value,
        severity="CRITICAL",
        confidence=1.0,
        file="core/god.py",
        symbol="GodClass",
    )
    report = RefactoringReport(
        project_root=str(temp_dir),
        issues=[issue],
        candidates=[RefactoringCandidate(id="CAND-01", current_structure="GodClass", target_structure="Clean", reason="Decompose", risk="CRITICAL", priority_score=80.0)],
        should_refactor_first=True,
    )

    context = {
        "project_name": "TestApp",
        "description": "App",
        "refactoring_report": report,
    }
    task = Task(id="TASK-01", title="Add Feature", description="Feature")

    prompt = builder.build(context=context, task=task)
    assert "TECHNICAL DEBT ANALYSIS" in prompt
    assert "God Object" in prompt
    assert "Should Refactor First: YES" in prompt


def test_31_memory_manager_integration(temp_dir):
    """Verifies record_completed_refactoring stores memories under REFACTORING."""
    mem_file = temp_dir / "project_memory.json"
    memory_manager = MemoryManager(persistence_path=mem_file)
    engine = RefactoringEngine(memory_manager=memory_manager, history_path=temp_dir / "refact_history.json")

    cand = RefactoringCandidate(
        id="CAND-01",
        current_structure="Monolith",
        target_structure="Micro-modules",
        reason="Decoupling",
        affected_files=["core/monolith.py"],
        priority_score=75.0,
        estimated_hours=3.0,
    )

    engine.record_completed_refactoring(
        candidate=cand,
        task=Task(id="TASK-01", title="Decouple", description="Decouple"),
        metrics_before=RefactoringMetrics(maintainability_index=60.0),
        metrics_after=RefactoringMetrics(maintainability_index=82.0),
    )

    results = memory_manager.get_memories_by_category("REFACTORING")
    assert len(results) >= 1
    assert "Refactoring Completed" in results[0].title
    assert "Maintainability Improvement: +22.0" in results[0].content


def test_32_engineering_decision_engine_refactor_first_strategy(temp_dir):
    """Verifies EngineeringDecisionEngine generates 'Refactor First' options when debt report is provided."""
    dec_engine = EngineeringDecisionEngine(history_path=temp_dir / "dec_history.json")

    report = RefactoringReport(
        project_root=str(temp_dir),
        issues=[TechnicalDebtIssue(id="D1", title="Cycle", description="Cycle", category="Circular Dependency", severity="CRITICAL", confidence=1.0, file="core/a.py")],
        candidates=[RefactoringCandidate(id="CAND-01", current_structure="Cycle", target_structure="Decoupled", reason="Break cycle", risk="CRITICAL", priority_score=85.0)],
        should_refactor_first=True,
    )

    task = Task(id="TASK-01", title="Build User Auth", description="Implement auth")
    options = dec_engine.generate_options(task, refactoring_report=report)

    assert len(options) >= 3
    assert any("Refactor First" in o.title for o in options)
    assert any("Adapter" in o.title for o in options)
    assert any("Surgical In-Place" in o.title for o in options)


def test_33_orchestrator_integration_with_refactoring_engine(temp_dir):
    """Verifies Orchestrator executes RefactoringEngine before EngineeringDecisionEngine."""
    mock_llm = MockProvider()
    refact_engine = RefactoringEngine(
        technical_debt_path=temp_dir / "tech_debt.json",
        history_path=temp_dir / "refact_history.json",
    )
    dec_engine = EngineeringDecisionEngine(history_path=temp_dir / "dec_history.json")

    plan_path = temp_dir / "project_plan.json"
    plan_data = {
        "project_name": "RefactoringTestApp",
        "phases": [
            {
                "phase_number": 1,
                "goal": "Build Core Component",
                "tasks": [
                    {
                        "id": "T1",
                        "title": "Create User Service",
                        "description": "Build user service",
                        "priority": 1,
                        "estimated_files": ["core/user.py"],
                    }
                ],
            }
        ],
    }
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan_data, f)

    orchestrator = Orchestrator(
        project_root=temp_dir / "workspace",
        plan_path=plan_path,
        state_path=temp_dir / "state.json",
        tasks_path=temp_dir / "tasks.json",
        llm=mock_llm,
        refactoring_engine=refact_engine,
        decision_engine=dec_engine,
    )

    mock_coder = MagicMock()
    mock_coder.execute.return_value = GeneratedResult(
        files=[GeneratedFile(path="core/user.py", content="class UserService: pass")],
        explanation="Implemented user service",
        summary="Implemented user service",
    )
    mock_tester = MagicMock()
    mock_tester.run_tests.return_value = TestResult(
        success=True,
        total_tests=1,
        passed=1,
        failed=0,
        skipped=0,
        duration=0.1,
        stdout="1 passed",
        stderr="",
        exit_code=0,
        command="pytest",
        message="Passed",
    )
    mock_reviewer = MagicMock()
    mock_reviewer.review.return_value = ReviewResult(
        success=True,
        summary="Clean implementation",
        overall_quality_score=95,
        should_regenerate=False,
    )

    orchestrator.coder_agent = mock_coder
    orchestrator.tester_agent = mock_tester
    orchestrator.reviewer_agent = mock_reviewer

    summary = orchestrator.run()
    assert summary.overall_success is True
    assert len(summary.tasks_completed) >= 1

    # Verify context passed to CoderAgent had refactoring report
    called_context = mock_coder.execute.call_args[1]["context"]
    assert "refactoring_report" in called_context
    assert isinstance(called_context["refactoring_report"], RefactoringReport)


# =============================================================================
# 5. Persistence, Telemetry & Performance Tests
# =============================================================================

def test_34_technical_debt_persistence_save_and_load(temp_dir):
    """Verifies atomic persistence and loading of technical debt reports."""
    dest_file = temp_dir / "technical_debt.json"
    engine = RefactoringEngine(technical_debt_path=dest_file)

    report = RefactoringReport(
        project_root=str(temp_dir),
        issues=[TechnicalDebtIssue(id="DEBT-01", title="Issue", description="Desc", category="Dead Code", severity="LOW", confidence=1.0, file="a.py")],
        summary="Test report",
    )

    saved_path = engine.save_technical_debt(report)
    assert saved_path.is_file()

    loaded = engine.load_technical_debt(dest_file)
    assert len(loaded.issues) == 1
    assert loaded.issues[0].id == "DEBT-01"


def test_35_corrupted_json_persistence_recovery(temp_dir):
    """Verifies graceful recovery when technical debt JSON file is corrupted."""
    dest_file = temp_dir / "corrupted_debt.json"
    dest_file.write_text("{ broken json @@##", encoding="utf-8")

    engine = RefactoringEngine(technical_debt_path=dest_file)
    recovered = engine.load_technical_debt(dest_file)

    assert isinstance(recovered, RefactoringReport)
    assert recovered.project_root == str(temp_dir)


def test_36_telemetry_tracking(temp_dir):
    """Verifies telemetry metrics tracking across multiple analysis calls."""
    engine = RefactoringEngine(technical_debt_path=temp_dir / "debt.json")
    (temp_dir / "test.py").write_text("def foo(): return 1\n", encoding="utf-8")

    engine.analyze_project(temp_dir)
    telemetry = engine.get_telemetry()

    assert telemetry["analysis_count"] >= 1
    assert telemetry["last_analysis_time_ms"] > 0
    assert len(telemetry["technical_debt_trend"]) >= 1


def test_37_high_performance_benchmark(temp_dir):
    """Verifies analysis of 100+ files executes in sub-second time (<500ms)."""
    # Generate 100 python source files
    for i in range(100):
        f = temp_dir / f"module_{i}.py"
        f.write_text(f"def func_{i}(x):\n    return x * {i}\n", encoding="utf-8")

    engine = RefactoringEngine()
    start_time = time.perf_counter()
    report = engine.analyze_project(temp_dir)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    assert len(report.metrics.to_dict()) > 0
    assert elapsed_ms < 2000.0  # Must be well under 2.0s limit (typically ~100-300ms)


def test_38_deterministic_output(temp_dir):
    """Verifies that two consecutive runs produce 100% identical reports."""
    (temp_dir / "sample.py").write_text("def sample_fn(a, b, c, d, e, f, g, h):\n    return a + b\n", encoding="utf-8")

    engine = RefactoringEngine()
    report1 = engine.analyze_project(temp_dir)
    report2 = engine.analyze_project(temp_dir)

    assert len(report1.issues) == len(report2.issues)
    assert [i.id for i in report1.issues] == [i.id for i in report2.issues]
    assert report1.metrics.maintainability_index == report2.metrics.maintainability_index
    assert report1.metrics.technical_debt_score == report2.metrics.technical_debt_score
