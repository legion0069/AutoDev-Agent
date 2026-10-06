"""
test_refactoring_planner.py - Comprehensive Unit & Integration Tests for AutoDev Version 1.7 Refactoring Planner

Validates:
1. Simple function modification
2. New feature and file creation
3. Class addition and method expansion
4. API breaking changes detection (public symbol deletion with callers)
5. Symbol rename and import propagation
6. Inheritance and base class modification safety
7. Database schema and migration keyword detection
8. Line estimation across all ActionType variants
9. Deterministic summary generation
10. PromptBuilder integration with SAFE REFACTORING PLAN section
11. Orchestrator integration with context injection
12. Empty workspace resilience
13. Large project symbol graph performance
14. Serialization and JSON roundtrip
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from agents.coder_agent import CoderAgent, GeneratedFile, GeneratedResult
from agents.file_writer_agent import FileWriterAgent, WriteResult
from agents.git_agent import CommitResult, GitAgent
from agents.reviewer_agent import ReviewerAgent, ReviewResult
from agents.task_planner_agent import Task
from agents.tester_agent import TesterAgent, TestResult
from core.impact_analyzer import ImpactAnalyzer, ImpactReport, RiskLevel
from core.orchestrator import Orchestrator
from core.prompt_builder import PromptBuilder
from core.refactoring_planner import (
    ActionType,
    ModificationAction,
    RefactoringPlan,
    RefactoringPlanner,
)
from core.symbol_graph import Reference, Symbol, SymbolGraph, SymbolType, Visibility


# =============================================================================
# Helper Fixtures
# =============================================================================

@pytest.fixture
def sample_graph() -> SymbolGraph:
    """Constructs a rich SymbolGraph with classes, methods, functions, and references."""
    graph = SymbolGraph()

    # 1. Base Class & Subclass
    base_class = Symbol(
        id="src/base_service.py:BaseService",
        name="BaseService",
        qualified_name="BaseService",
        symbol_type=SymbolType.CLASS,
        language="python",
        file="src/base_service.py",
        line=1,
        end_line=50,
        visibility=Visibility.PUBLIC,
    )
    user_service = Symbol(
        id="src/user_service.py:UserService",
        name="UserService",
        qualified_name="UserService",
        symbol_type=SymbolType.CLASS,
        language="python",
        file="src/user_service.py",
        line=1,
        end_line=120,
        visibility=Visibility.PUBLIC,
        inherits=["BaseService"],
    )

    # 2. Methods
    auth_method = Symbol(
        id="src/user_service.py:UserService.authenticate",
        name="authenticate",
        qualified_name="UserService.authenticate",
        symbol_type=SymbolType.METHOD,
        language="python",
        file="src/user_service.py",
        line=20,
        end_line=45,
        parent_symbol="UserService",
        visibility=Visibility.PUBLIC,
    )
    helper_method = Symbol(
        id="src/user_service.py:UserService._hash_password",
        name="_hash_password",
        qualified_name="UserService._hash_password",
        symbol_type=SymbolType.METHOD,
        language="python",
        file="src/user_service.py",
        line=50,
        end_line=65,
        parent_symbol="UserService",
        visibility=Visibility.PRIVATE,
    )

    # 3. Standalone Function
    process_order = Symbol(
        id="src/order_service.py:process_order",
        name="process_order",
        qualified_name="process_order",
        symbol_type=SymbolType.FUNCTION,
        language="python",
        file="src/order_service.py",
        line=10,
        end_line=40,
        visibility=Visibility.PUBLIC,
    )

    graph.add_symbol(base_class)
    graph.add_symbol(user_service)
    graph.add_symbol(auth_method)
    graph.add_symbol(helper_method)
    graph.add_symbol(process_order)

    # 4. Caller References: controller calls authenticate
    graph.add_call_edge(
        caller_id="src/controller.py:login_endpoint",
        callee_name_or_id="src/user_service.py:UserService.authenticate",
    )
    graph.add_call_edge(
        caller_id="src/controller.py:login_endpoint",
        callee_name_or_id="authenticate",
    )

    return graph



# =============================================================================
# 1. Action Generation Tests
# =============================================================================

def test_1_simple_function_update(sample_graph):
    """Verifies that modifying an existing function produces a MODIFY_FUNCTION action without breaking changes."""
    planner = RefactoringPlanner(symbol_graph=sample_graph)
    task = Task(
        id="TASK-01",
        title="Enhance process_order logic",
        description="Add tax calculation step inside process_order function.",
        estimated_files=["src/order_service.py"],
    )

    context = {
        "symbol_graph": sample_graph,
        "project_files": {"src/order_service.py": "def process_order(): pass"},
    }

    plan = planner.plan(task, context)

    assert isinstance(plan, RefactoringPlan)
    assert "src/order_service.py" in plan.files_to_modify
    assert len(plan.files_to_create) == 0 or "tests/test_order_service.py" in plan.files_to_create
    assert any(a.action_type == ActionType.MODIFY_FUNCTION.value for a in plan.actions)
    assert plan.rollback_required is False
    assert plan.migration_required is False
    assert plan.risk_level in {"LOW", "MEDIUM"}


def test_2_new_feature_and_file_creation(sample_graph):
    """Verifies that creating a new file generates CREATE_FILE and ADD_TEST actions."""
    planner = RefactoringPlanner(symbol_graph=sample_graph)
    task = Task(
        id="TASK-02",
        title="Create notification service",
        description="Implement email and SMS notification dispatcher.",
        estimated_files=["src/notification_service.py"],
    )

    context = {
        "symbol_graph": sample_graph,
        "project_files": {},  # File does not exist
    }

    plan = planner.plan(task, context)

    assert "src/notification_service.py" in plan.files_to_create
    assert any(a.action_type == ActionType.CREATE_FILE.value for a in plan.actions)
    assert any(a.action_type == ActionType.ADD_TEST.value for a in plan.actions)
    assert plan.breaking_changes == []
    assert plan.risk_level == "LOW"


def test_3_class_addition_and_methods(sample_graph):
    """Verifies class addition keyword detection produces ADD_CLASS."""
    planner = RefactoringPlanner(symbol_graph=sample_graph)
    task = Task(
        id="TASK-03",
        title="Add class PaymentProcessor",
        description="Implement new class PaymentProcessor with stripe integration.",
        estimated_files=["src/payment.py"],
    )

    context = {
        "symbol_graph": sample_graph,
        "project_files": {"src/payment.py": "# existing file"},
    }

    plan = planner.plan(task, context)
    assert any(a.action_type == ActionType.ADD_CLASS.value for a in plan.actions)
    assert "src/payment.py" in plan.files_to_modify


# =============================================================================
# 2. Breaking Change & Safety Invariant Tests
# =============================================================================

def test_4_api_breaking_changes_public_function_deleted(sample_graph):
    """Verifies that deleting a public symbol with callers triggers breaking change and rollback flags."""
    planner = RefactoringPlanner(symbol_graph=sample_graph)
    task = Task(
        id="TASK-04",
        title="Delete authenticate method",
        description="Remove and purge authenticate from UserService.",
        estimated_files=["src/user_service.py"],
    )

    context = {
        "symbol_graph": sample_graph,
        "project_files": {"src/user_service.py": "class UserService: def authenticate(): pass"},
    }

    plan = planner.plan(task, context)

    assert any(a.action_type in {ActionType.DELETE_FUNCTION.value, ActionType.DELETE_CLASS.value, ActionType.MODIFY_METHOD.value} for a in plan.actions)
    assert plan.rollback_required is True
    assert len(plan.breaking_changes) >= 1
    assert any("authenticate" in bc for bc in plan.breaking_changes)
    assert plan.risk_level in {"HIGH", "CRITICAL"}


def test_5_symbol_rename_and_import_updates(sample_graph):
    """Verifies that renaming a symbol triggers RENAME_SYMBOL and UPDATE_IMPORTS."""
    planner = RefactoringPlanner(symbol_graph=sample_graph)
    task = Task(
        id="TASK-05",
        title="Rename UserService to AccountService",
        description="Rename symbol UserService and update imports across project.",
        estimated_files=["src/user_service.py"],
    )

    context = {
        "symbol_graph": sample_graph,
        "project_files": {"src/user_service.py": "class UserService: pass"},
    }

    plan = planner.plan(task, context)

    assert any(a.action_type == ActionType.RENAME_SYMBOL.value for a in plan.actions)
    assert any(a.action_type == ActionType.UPDATE_IMPORTS.value for a in plan.actions)
    assert len(plan.breaking_changes) >= 1


def test_6_inheritance_and_base_class_modification(sample_graph):
    """Verifies modifying a base class flags derived class impacts."""
    planner = RefactoringPlanner(symbol_graph=sample_graph)
    task = Task(
        id="TASK-06",
        title="Modify BaseService class",
        description="Update BaseService core execution pipeline.",
        estimated_files=["src/base_service.py"],
    )

    context = {
        "symbol_graph": sample_graph,
        "project_files": {"src/base_service.py": "class BaseService: pass"},
    }

    plan = planner.plan(task, context)

    assert any(a.action_type == ActionType.MODIFY_CLASS.value for a in plan.actions)
    assert any("BaseService" in bc and "UserService" in bc for bc in plan.breaking_changes)


def test_7_database_schema_and_migration_detection(sample_graph):
    """Verifies database schema alteration keywords trigger migration_required and CRITICAL risk."""
    planner = RefactoringPlanner(symbol_graph=sample_graph)
    task = Task(
        id="TASK-07",
        title="Add column to users table",
        description="Execute database migration to alter table and add billing_address column.",
        estimated_files=["models/user.py"],
    )

    context = {
        "symbol_graph": sample_graph,
        "project_files": {"models/user.py": "# model"},
    }

    plan = planner.plan(task, context)

    assert plan.migration_required is True
    assert plan.risk_level == "CRITICAL"
    assert any("Database schema" in bc for bc in plan.breaking_changes)


# =============================================================================
# 3. Line Estimation & Summary Generation
# =============================================================================

def test_8_line_estimation_across_action_types():
    """Verifies line estimation defaults for all action categories."""
    planner = RefactoringPlanner()

    assert 10 <= planner.estimate_line_changes(ActionType.ADD_FUNCTION) <= 25
    assert 5 <= planner.estimate_line_changes(ActionType.MODIFY_FUNCTION) <= 20
    assert 20 <= planner.estimate_line_changes(ActionType.ADD_CLASS) <= 100
    assert 30 <= planner.estimate_line_changes(ActionType.CREATE_FILE) <= 250
    assert 5 <= planner.estimate_line_changes(ActionType.ADD_TEST) <= 50
    assert 2 <= planner.estimate_line_changes(ActionType.UPDATE_IMPORTS) <= 10


def test_9_deterministic_summary_generation():
    """Verifies the structured summary format matches expected pattern."""
    planner = RefactoringPlanner()
    actions = [
        ModificationAction(action_type=ActionType.MODIFY_FUNCTION.value, target_symbol="fn1", target_file="f1.py", reason="r1", estimated_lines_changed=15),
        ModificationAction(action_type=ActionType.MODIFY_FUNCTION.value, target_symbol="fn2", target_file="f2.py", reason="r2", estimated_lines_changed=20),
        ModificationAction(action_type=ActionType.UPDATE_TEST.value, target_symbol="t1", target_file="tests/test_f1.py", reason="r3", estimated_lines_changed=25),
    ]

    summary = planner.generate_summary(
        actions=actions,
        files_to_modify=["f1.py", "f2.py"],
        files_to_create=["new.py"],
        files_to_delete=[],
        breaking_changes=[],
        total_lines=60,
    )

    assert "This task modifies 2 existing files" in summary
    assert "creates 1 new files" in summary
    assert "updates 1 unit tests" in summary
    assert "introduces no breaking API changes" in summary
    assert "estimated 60 lines changed." in summary


# =============================================================================
# 4. PromptBuilder & Orchestrator Integration
# =============================================================================

def test_10_prompt_builder_integration(sample_graph):
    """Verifies PromptBuilder includes the SAFE REFACTORING PLAN section with all action details."""
    planner = RefactoringPlanner(symbol_graph=sample_graph)
    task = Task(
        id="TASK-REFACTOR-01",
        title="Refactor process_order",
        description="Add payment validation to order processing workflow.",
        estimated_files=["src/order_service.py"],
    )

    context = {
        "symbol_graph": sample_graph,
        "project_files": {"src/order_service.py": "def process_order(): pass"},
        "refactoring_planner": planner,
    }

    builder = PromptBuilder(refactoring_planner=planner)
    prompt = builder.build(context=context, task=task)

    assert "================================================================================" in prompt
    assert "SAFE REFACTORING PLAN" in prompt
    assert "Files To Modify" in prompt
    assert "src/order_service.py" in prompt
    assert "Actions" in prompt
    assert "MODIFY_FUNCTION" in prompt
    assert "process_order()" in prompt
    assert "Reason:" in prompt
    assert "Estimated Change:" in prompt
    assert "Breaking:" in prompt


def test_11_orchestrator_integration(tmp_path: Path, sample_graph):
    """Verifies Orchestrator executes RefactoringPlanner and stores refactoring_plan in context."""
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "src").mkdir(parents=True, exist_ok=True)
    (workspace / "src" / "service.py").write_text("def run(): pass", encoding="utf-8")

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    plan_path = memory_dir / "project_plan.json"
    plan_path.write_text(json.dumps({
        "project_name": "Refactor Demo",
        "phases": [{
            "day": 1,
            "phase_name": "Day 1",
            "goals": ["Refactor service"],
            "tasks": ["Update run function in service.py"],
            "deliverables": ["src/service.py"],
        }]
    }), encoding="utf-8")

    mock_coder = MagicMock(spec=CoderAgent)
    mock_coder.execute.return_value = GeneratedResult(
        summary="Refactored service",
        files=[GeneratedFile(path="src/service.py", content="def run(): return 'updated'")],
        explanation="Added updates",
    )

    mock_writer = MagicMock(spec=FileWriterAgent)
    mock_writer.write.return_value = WriteResult(
        files_written=["src/service.py"],
        success=True,
    )

    mock_tester = MagicMock(spec=TesterAgent)
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
        message="Tests passed",
    )

    mock_reviewer = MagicMock(spec=ReviewerAgent)
    mock_reviewer.review.return_value = ReviewResult(
        success=True,
        summary="Review passed",
        overall_quality_score=95,
        issues=[],
    )

    mock_git = MagicMock(spec=GitAgent)
    mock_git.commit.return_value = CommitResult(
        success=True,
        commit_hash="c1234",
    )

    refactoring_planner = RefactoringPlanner(symbol_graph=sample_graph)

    orch = Orchestrator(
        project_root=workspace,
        plan_path=plan_path,
        state_path=memory_dir / "state.json",
        tasks_path=memory_dir / "tasks.json",
        log_dir=tmp_path / "logs",
        refactoring_planner=refactoring_planner,
        coder_agent=mock_coder,
        file_writer=mock_writer,
        tester_agent=mock_tester,
        reviewer_agent=mock_reviewer,
        git_agent=mock_git,
    )

    summary = orch.run()
    assert summary.overall_success is True
    assert len(summary.tasks_completed) >= 1


# =============================================================================
# 5. Edge Cases & Performance
# =============================================================================

def test_12_empty_project_workspace_handling():
    """Verifies that an empty project with no symbols or files is handled gracefully."""
    empty_graph = SymbolGraph()
    planner = RefactoringPlanner(symbol_graph=empty_graph)
    task = Task(id="EMPTY-01", title="Initialize app", description="Scaffold new app")

    plan = planner.plan(task, context={})
    assert isinstance(plan, RefactoringPlan)
    assert plan.risk_level == "LOW"
    assert len(plan.actions) >= 1


def test_13_large_project_graph_performance():
    """Verifies deterministic performance on large symbol graphs (200+ symbols)."""
    graph = SymbolGraph()

    for i in range(200):
        sym = Symbol(
            id=f"src/service_{i}.py:Service_{i}",
            name=f"Service_{i}",
            qualified_name=f"Service_{i}",
            symbol_type=SymbolType.CLASS,
            language="python",
            file=f"src/service_{i}.py",
            line=1,
            end_line=50,
            visibility=Visibility.PUBLIC,
        )
        graph.add_symbol(sym)
        if i > 0:
            graph.add_call_edge(
                caller_id=f"src/service_{i}.py:Service_{i}",
                callee_name_or_id=f"src/service_{i-1}.py:Service_{i-1}",
            )


    planner = RefactoringPlanner(symbol_graph=graph)
    task = Task(
        id="PERF-TASK",
        title="Update Service_50 and Service_100",
        description="Modify core operations in Service_50 and Service_100.",
        estimated_files=["src/service_50.py", "src/service_100.py"],
    )

    start = time.perf_counter()
    plan = planner.plan(task, context={"symbol_graph": graph, "project_files": {f"src/service_{i}.py": "" for i in range(200)}})
    elapsed = time.perf_counter() - start

    assert isinstance(plan, RefactoringPlan)
    assert elapsed < 0.10  # Completed in less than 100ms
    assert len(plan.actions) >= 2


def test_14_serialization_and_json_roundtrip():
    """Verifies dataclass, dict, and JSON roundtrip serialization."""
    act = ModificationAction(
        action_type=ActionType.MODIFY_FUNCTION,
        target_symbol="compute_hash",
        target_file="src/utils.py",
        reason="Update hashing algorithm to SHA256",
        priority="HIGH",
        estimated_lines_changed=22,
        breaking_change=True,
        notes="Requires caller update",
    )

    plan = RefactoringPlan(
        actions=[act],
        files_to_modify=["src/utils.py"],
        files_to_create=["tests/test_utils.py"],
        files_to_delete=[],
        estimated_total_lines=22,
        breaking_changes=["Algorithm changed to SHA256"],
        rollback_required=True,
        migration_required=False,
        risk_level="HIGH",
        summary="Test summary",
    )

    plan_dict = plan.to_dict()
    assert plan_dict["files_to_modify"] == ["src/utils.py"]
    assert plan_dict["actions"][0]["action_type"] == "MODIFY_FUNCTION"

    restored = RefactoringPlan.from_dict(plan_dict)
    assert restored.risk_level == "HIGH"
    assert restored.actions[0].target_symbol == "compute_hash"

    json_str = plan.to_json()
    assert isinstance(json_str, str)
    from_json_plan = RefactoringPlan.from_json(json_str)
    assert from_json_plan.estimated_total_lines == 22
    assert from_json_plan.rollback_required is True
