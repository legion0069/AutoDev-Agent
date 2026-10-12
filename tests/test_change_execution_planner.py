"""
test_change_execution_planner.py - Comprehensive Unit and Integration Test Suite
for AutoDev Version 2.0 Autonomous Change Execution Planning Engine.

Contains 45+ deterministic tests covering:
- Data models & dataclass roundtrips (ChangeOperation, RollbackPoint, ValidationGate, CommitPlanEntry, ExecutionStage, ChangeExecutionPlan)
- Dependency DAG construction (imports, inheritance, call graph, architecture layers)
- Topological sorting & deterministic tie-breaking
- Cycle detection & robust fallback resolution
- Critical path calculation & duration analysis
- Parallel execution group discovery
- Conflict detection (same file multiple edits, same symbol twice, architecture violations, merge conflicts)
- Validation gate synthesis (Compile, Lint, Unit Tests, Integration Tests, Architecture Validation, etc.)
- Commit strategy generation (Database, Core, API, Frontend, Tests, Docs)
- Rollback engine & checkpoint synthesis
- Execution cost & risk estimation models
- Serialization / JSON export & import
- PromptBuilder integration
- Orchestrator integration
- Large scale benchmark (1000+ operations in <100ms)
- Edge cases (empty task, single operation, disconnected components)
"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

from agents.task_planner_agent import Task
from core.architecture_manager import ArchitectureDecision, ArchitectureManager
from core.change_execution_planner import (
    ChangeExecutionPlan,
    ChangeExecutionPlanner,
    ChangeOperation,
    CommitPlanEntry,
    ConflictType,
    ExecutionStage,
    GateType,
    OperationType,
    RollbackPoint,
    ValidationGate,
)
from core.engineering_decision_engine import EngineeringDecisionEngine
from core.impact_analyzer import ImpactAnalyzer, ImpactReport, RiskLevel
from core.orchestrator import Orchestrator
from core.prompt_builder import PromptBuilder
from core.refactoring_engine import RefactoringEngine
from core.repository_analyzer import ArchitectureLayer, RepositoryAnalyzer
from core.symbol_graph import Dependency, Symbol, SymbolGraph, SymbolType


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_workspace():
    """Provides an isolated temporary workspace directory."""
    temp_dir = tempfile.mkdtemp(prefix="autodev_plan_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def populated_symbol_graph():
    """Provides a pre-populated SymbolGraph with realistic multi-layer symbols."""
    graph = SymbolGraph()

    # User Model (Database Layer)
    graph.add_symbol(
        Symbol(
            id="core/models/user.py::UserModel",
            name="UserModel",
            symbol_type=SymbolType.CLASS,
            file="core/models/user.py",
            line=1,
            end_line=40,
        )
    )

    # User Repository (Data Access Layer)
    graph.add_symbol(
        Symbol(
            id="core/repositories/user_repo.py::UserRepository",
            name="UserRepository",
            symbol_type=SymbolType.CLASS,
            file="core/repositories/user_repo.py",
            line=1,
            end_line=60,
        )
    )
    graph.add_dependency(
        Dependency(
            source_file="core/repositories/user_repo.py",
            target_file="core/models/user.py",
            dependency_type="import",
        )
    )

    # User Service (Service / Business Layer)
    graph.add_symbol(
        Symbol(
            id="core/services/user_service.py::UserService",
            name="UserService",
            symbol_type=SymbolType.CLASS,
            file="core/services/user_service.py",
            line=1,
            end_line=80,
            calls=["UserRepository"],
        )
    )
    graph.add_dependency(
        Dependency(
            source_file="core/services/user_service.py",
            target_file="core/repositories/user_repo.py",
            dependency_type="call",
        )
    )

    # User Controller / API (API Layer)
    graph.add_symbol(
        Symbol(
            id="api/controllers/user_controller.py::UserController",
            name="UserController",
            symbol_type=SymbolType.CLASS,
            file="api/controllers/user_controller.py",
            line=1,
            end_line=100,
            calls=["UserService"],
        )
    )
    graph.add_dependency(
        Dependency(
            source_file="api/controllers/user_controller.py",
            target_file="core/services/user_service.py",
            dependency_type="call",
        )
    )

    # Frontend View
    graph.add_symbol(
        Symbol(
            id="frontend/src/components/UserProfile.tsx::UserProfile",
            name="UserProfile",
            symbol_type=SymbolType.FUNCTION,
            file="frontend/src/components/UserProfile.tsx",
            line=1,
            end_line=120,
        )
    )

    # Tests
    graph.add_symbol(
        Symbol(
            id="tests/test_user_service.py::test_user_creation",
            name="test_user_creation",
            symbol_type=SymbolType.FUNCTION,
            file="tests/test_user_service.py",
            line=1,
            end_line=30,
        )
    )
    graph.add_dependency(
        Dependency(
            source_file="tests/test_user_service.py",
            target_file="core/services/user_service.py",
            dependency_type="tests",
        )
    )

    return graph


@pytest.fixture
def planner(populated_symbol_graph):
    """Provides a ChangeExecutionPlanner instance with a symbol graph."""
    return ChangeExecutionPlanner(symbol_graph=populated_symbol_graph)


# =============================================================================
# 1. DATA MODEL TESTS
# =============================================================================

def test_change_operation_defaults_and_post_init():
    """Verifies ChangeOperation initializes defaults, risk normalization, and descriptions."""
    op = ChangeOperation(
        operation_id="op-001",
        operation_type=OperationType.MODIFY_FILE.value,
        file="core/models/user.py",
        symbol="UserModel",
        reason="Add email verification field",
        risk="medium",
    )
    assert op.operation_id == "op-001"
    assert op.risk == "MEDIUM"
    assert "UserModel" in op.description
    assert op.inverse_operation == "REVERT_CHANGES on 'core/models/user.py'"
    assert op.validation_required is True
    assert op.rollback_required is True


def test_change_operation_create_and_delete_inverse():
    """Verifies inverse operation mapping for CREATE_FILE and DELETE_FILE."""
    create_op = ChangeOperation(
        operation_id="op-create",
        operation_type=OperationType.CREATE_FILE.value,
        file="core/new_file.py",
    )
    assert create_op.inverse_operation == "DELETE_FILE on 'core/new_file.py'"

    delete_op = ChangeOperation(
        operation_id="op-del",
        operation_type=OperationType.DELETE_FILE.value,
        file="core/old_file.py",
    )
    assert delete_op.inverse_operation == "RESTORE_FILE on 'core/old_file.py'"


def test_change_operation_to_dict_and_from_dict():
    """Verifies ChangeOperation dictionary roundtrip serialization."""
    op = ChangeOperation(
        operation_id="op-002",
        operation_type=OperationType.ADD_SYMBOL.value,
        file="core/auth.py",
        symbol="verify_token",
        reason="Add JWT validation",
        dependencies=["op-001"],
        estimated_minutes=15.0,
        risk="HIGH",
        layer="SERVICE",
    )
    data = op.to_dict()
    restored = ChangeOperation.from_dict(data)
    assert restored.operation_id == op.operation_id
    assert restored.symbol == op.symbol
    assert restored.dependencies == ["op-001"]
    assert restored.estimated_minutes == 15.0
    assert restored.risk == "HIGH"
    assert restored.layer == "SERVICE"


def test_rollback_point_to_dict_and_from_dict():
    """Verifies RollbackPoint serialization roundtrip."""
    rb = RollbackPoint(
        point_id="rb-stage-1",
        stage_number=1,
        git_reference="HEAD~1",
        modified_files=["core/user.py", "core/db.py"],
        inverse_operations=["REVERT core/user.py"],
        recovery_strategy="Hard reset to commit hash",
    )
    data = rb.to_dict()
    restored = RollbackPoint.from_dict(data)
    assert restored.point_id == "rb-stage-1"
    assert restored.stage_number == 1
    assert restored.modified_files == ["core/user.py", "core/db.py"]
    assert restored.recovery_strategy == "Hard reset to commit hash"


def test_validation_gate_to_dict_and_from_dict():
    """Verifies ValidationGate properties and serialization roundtrip."""
    gate = ValidationGate(
        gate_id="gate-unit-tests",
        gate_type=GateType.UNIT_TESTS.value,
        command="pytest tests/test_user.py",
        description="Verify User unit tests pass",
        blocking=True,
        required_pass_rate=100.0,
        timeout_seconds=45.0,
    )
    data = gate.to_dict()
    restored = ValidationGate.from_dict(data)
    assert restored.gate_id == "gate-unit-tests"
    assert restored.gate_type == GateType.UNIT_TESTS.value
    assert restored.blocking is True
    assert restored.timeout_seconds == 45.0


def test_commit_plan_entry_roundtrip():
    """Verifies CommitPlanEntry serialization roundtrip."""
    commit = CommitPlanEntry(
        commit_id="commit-stage-1",
        title="Database Layer",
        message="feat(db): update user schema and repository",
        files=["models/user.py", "repositories/user_repo.py"],
        stage_number=1,
        layer="DATABASE",
    )
    data = commit.to_dict()
    restored = CommitPlanEntry.from_dict(data)
    assert restored.commit_id == "commit-stage-1"
    assert restored.layer == "DATABASE"
    assert len(restored.files) == 2


def test_execution_stage_duration_calculation():
    """Verifies ExecutionStage calculates total time sequentially or by parallel max."""
    op1 = ChangeOperation("op1", OperationType.MODIFY_FILE.value, "a.py", estimated_minutes=10.0)
    op2 = ChangeOperation("op2", OperationType.MODIFY_FILE.value, "b.py", estimated_minutes=15.0)

    # Sequential stage: sum of operations = 25.0
    seq_stage = ExecutionStage(
        stage_number=1,
        title="Sequential Stage",
        operations=[op1, op2],
        parallel=False,
    )
    assert seq_stage.estimated_time == 25.0

    # Parallel stage with 2 subgroups: max of subgroup durations
    par_stage = ExecutionStage(
        stage_number=2,
        title="Parallel Stage",
        operations=[op1, op2],
        parallel=True,
        parallel_subgroups=[["op1"], ["op2"]],
    )
    assert par_stage.estimated_time == 15.0


def test_change_execution_plan_roundtrip_and_markdown():
    """Verifies complete ChangeExecutionPlan serialization and markdown export."""
    op = ChangeOperation("op1", OperationType.MODIFY_FILE.value, "user.py", estimated_minutes=10.0)
    stage = ExecutionStage(stage_number=1, title="Core Stage", operations=[op])
    gate = ValidationGate("gate1", GateType.UNIT_TESTS.value, "pytest", "Unit tests")
    rb = RollbackPoint("rb1", 1)
    commit = CommitPlanEntry("c1", "Core", "msg", ["user.py"], 1)

    stage.validation_gates = [gate]
    stage.rollback_checkpoint = rb
    stage.commit_entry = commit

    plan = ChangeExecutionPlan(
        plan_id="plan-test-01",
        task_id="TASK-101",
        ordered_stages=[stage],
        dependency_graph={"op1": []},
        parallel_groups=[["op1"]],
        rollback_plan=[rb],
        commit_plan=[commit],
        validation_plan=[gate],
        estimated_duration=10.0,
        critical_path=["op1"],
        risk="LOW",
        confidence=0.98,
    )

    data = plan.to_dict()
    restored = ChangeExecutionPlan.from_dict(data)
    assert restored.plan_id == "plan-test-01"
    assert restored.task_id == "TASK-101"
    assert len(restored.ordered_stages) == 1
    assert restored.confidence == 0.98

    md = plan.to_markdown()
    assert "# 🧭 Change Execution Plan" in md
    assert "Stage 1: Core Stage" in md
    assert "user.py" in md


# =============================================================================
# 2. DEPENDENCY GRAPH & TOPOLOGICAL SORTING
# =============================================================================

def test_build_dependency_graph_from_operations(planner):
    """Verifies dependency DAG links operations based on explicit deps and symbol graph."""
    ops = [
        ChangeOperation("op_model", OperationType.MODIFY_FILE.value, "core/models/user.py"),
        ChangeOperation("op_repo", OperationType.MODIFY_FILE.value, "core/repositories/user_repo.py"),
        ChangeOperation("op_service", OperationType.MODIFY_FILE.value, "core/services/user_service.py"),
    ]
    graph = planner.build_dependency_graph(ops)
    assert "op_model" in graph
    assert "op_repo" in graph
    assert "op_service" in graph

    # UserRepo depends on UserModel
    assert "op_model" in graph["op_repo"]
    # UserService depends on UserRepo
    assert "op_repo" in graph["op_service"]


def test_topological_sort_linear_chain(planner):
    """Verifies topological sorting produces strict predecessor order."""
    ops = [
        ChangeOperation("op3", OperationType.MODIFY_FILE.value, "c.py", dependencies=["op2"]),
        ChangeOperation("op1", OperationType.MODIFY_FILE.value, "a.py", dependencies=[]),
        ChangeOperation("op2", OperationType.MODIFY_FILE.value, "b.py", dependencies=["op1"]),
    ]
    order = planner.topological_sort(ops)
    assert order == ["op1", "op2", "op3"]


def test_topological_sort_diamond_dag(planner):
    """Verifies diamond DAG resolves all prerequisites before convergence."""
    ops = [
        ChangeOperation("start", OperationType.MODIFY_FILE.value, "start.py"),
        ChangeOperation("left", OperationType.MODIFY_FILE.value, "left.py", dependencies=["start"]),
        ChangeOperation("right", OperationType.MODIFY_FILE.value, "right.py", dependencies=["start"]),
        ChangeOperation("end", OperationType.MODIFY_FILE.value, "end.py", dependencies=["left", "right"]),
    ]
    order = planner.topological_sort(ops)
    assert order[0] == "start"
    assert order[-1] == "end"
    assert set(order[1:3]) == {"left", "right"}


def test_topological_sort_cycle_detection_fallback(planner):
    """Verifies cyclical dependencies are detected and deterministically broken."""
    ops = [
        ChangeOperation("cycle_a", OperationType.MODIFY_FILE.value, "a.py", dependencies=["cycle_b"]),
        ChangeOperation("cycle_b", OperationType.MODIFY_FILE.value, "b.py", dependencies=["cycle_a"]),
        ChangeOperation("indep", OperationType.MODIFY_FILE.value, "c.py", dependencies=[]),
    ]
    # Should not raise an unhandled exception or hang in infinite loop
    order = planner.topological_sort(ops)
    assert len(order) == 3
    assert set(order) == {"cycle_a", "cycle_b", "indep"}


def test_topological_sort_empty_and_single():
    """Verifies boundary cases for empty and single-node graphs."""
    planner = ChangeExecutionPlanner()
    assert planner.topological_sort([]) == []

    single_op = [ChangeOperation("op1", OperationType.MODIFY_FILE.value, "main.py")]
    assert planner.topological_sort(single_op) == ["op1"]


# =============================================================================
# 3. CRITICAL PATH ANALYSIS
# =============================================================================

def test_critical_path_linear_graph(planner):
    """Verifies critical path on a linear graph includes all nodes."""
    ops = [
        ChangeOperation("op1", OperationType.MODIFY_FILE.value, "a.py", estimated_minutes=5.0),
        ChangeOperation("op2", OperationType.MODIFY_FILE.value, "b.py", dependencies=["op1"], estimated_minutes=15.0),
    ]
    cp = planner.calculate_critical_path(ops)
    assert cp == ["op1", "op2"]


def test_critical_path_diamond_weighted(planner):
    """Verifies critical path chooses the highest duration branch in a diamond DAG."""
    ops = [
        ChangeOperation("start", OperationType.MODIFY_FILE.value, "start.py", estimated_minutes=5.0),
        ChangeOperation("short_branch", OperationType.MODIFY_FILE.value, "s.py", dependencies=["start"], estimated_minutes=2.0),
        ChangeOperation("long_branch", OperationType.MODIFY_FILE.value, "l.py", dependencies=["start"], estimated_minutes=20.0),
        ChangeOperation("end", OperationType.MODIFY_FILE.value, "end.py", dependencies=["short_branch", "long_branch"], estimated_minutes=5.0),
    ]
    cp = planner.calculate_critical_path(ops)
    assert cp == ["start", "long_branch", "end"]


# =============================================================================
# 4. PARALLEL EXECUTION GROUP DISCOVERY
# =============================================================================

def test_detect_parallelism_independent_files(planner):
    """Verifies independent files across different components are grouped into parallel sets."""
    ops = [
        ChangeOperation("db_op", OperationType.MODIFY_FILE.value, "backend/database.py"),
        ChangeOperation("ui_op", OperationType.MODIFY_FILE.value, "frontend/login.tsx"),
        ChangeOperation("doc_op", OperationType.MODIFY_FILE.value, "docs/api.md"),
    ]
    parallel_groups = planner.detect_parallelism(ops)
    # Since they have no shared dependencies or files, they can run in parallel
    assert len(parallel_groups) >= 1
    # Check that independent operations are detected
    all_ops_in_groups = [op_id for grp in parallel_groups for op_id in grp]
    assert "db_op" in all_ops_in_groups
    assert "ui_op" in all_ops_in_groups
    assert "doc_op" in all_ops_in_groups


def test_detect_parallelism_with_dependencies(planner):
    """Verifies dependent operations are not placed in the same simultaneous parallel group."""
    ops = [
        ChangeOperation("op1", OperationType.MODIFY_FILE.value, "a.py"),
        ChangeOperation("op2", OperationType.MODIFY_FILE.value, "b.py", dependencies=["op1"]),
    ]
    groups = planner.detect_parallelism(ops)
    # op1 and op2 cannot be in the same parallel execution group
    for g in groups:
        assert not ("op1" in g and "op2" in g)


# =============================================================================
# 5. CONFLICT DETECTION
# =============================================================================

def test_detect_conflicts_same_file_multiple_edits(planner):
    """Detects SAME_FILE_MULTIPLE_EDITS conflict when multiple operations edit the same file."""
    ops = [
        ChangeOperation("op1", OperationType.MODIFY_FILE.value, "core/user.py", symbol="func_a"),
        ChangeOperation("op2", OperationType.MODIFY_FILE.value, "core/user.py", symbol="func_b"),
    ]
    conflicts = planner.detect_conflicts(ops)
    file_conflicts = [c for c in conflicts if c.get("conflict_type") == ConflictType.SAME_FILE_MULTIPLE_EDITS.value]
    assert len(file_conflicts) > 0
    assert "core/user.py" in file_conflicts[0]["files"]


def test_detect_conflicts_same_symbol_modified_twice(planner):
    """Detects SAME_SYMBOL_MODIFIED_TWICE conflict."""
    ops = [
        ChangeOperation("op1", OperationType.MODIFY_SYMBOL.value, "core/user.py", symbol="update_user"),
        ChangeOperation("op2", OperationType.MODIFY_SYMBOL.value, "core/user.py", symbol="update_user"),
    ]
    conflicts = planner.detect_conflicts(ops)
    sym_conflicts = [c for c in conflicts if c.get("conflict_type") == ConflictType.SAME_SYMBOL_MODIFIED_TWICE.value]
    assert len(sym_conflicts) > 0
    assert sym_conflicts[0]["symbol"] == "update_user"


def test_detect_conflicts_architecture_inversion(planner):
    """Detects ARCHITECTURE_CONFLICT when lower layer illegally depends on upper layer."""
    ops = [
        ChangeOperation("db_op", OperationType.MODIFY_FILE.value, "core/models/user.py", layer="DATABASE", dependencies=["api_op"]),
        ChangeOperation("api_op", OperationType.MODIFY_FILE.value, "api/controllers/user.py", layer="API"),
    ]
    conflicts = planner.detect_conflicts(ops)
    arch_conflicts = [c for c in conflicts if c.get("conflict_type") == ConflictType.ARCHITECTURE_CONFLICT.value]
    assert len(arch_conflicts) > 0


def test_detect_conflicts_clean_plan(planner):
    """Verifies no false positive conflicts on a clean, disjoint plan."""
    ops = [
        ChangeOperation("op_db", OperationType.MODIFY_FILE.value, "db/schema.sql", layer="DATABASE"),
        ChangeOperation("op_docs", OperationType.MODIFY_FILE.value, "docs/readme.md", layer="DOCS"),
    ]
    conflicts = planner.detect_conflicts(ops)
    assert len(conflicts) == 0


# =============================================================================
# 6. STAGE PARTITIONING & LAYER ORDERING
# =============================================================================

def test_stage_partitioning_layer_hierarchy(planner):
    """Verifies operations are partitioned into stages in proper architectural layer order."""
    ops = [
        ChangeOperation("doc_op", OperationType.UPDATE_DOCS.value, "docs/index.md", layer="DOCS"),
        ChangeOperation("api_op", OperationType.MODIFY_FILE.value, "api/routes.py", layer="API"),
        ChangeOperation("db_op", OperationType.MODIFY_FILE.value, "models/schema.py", layer="DATABASE"),
        ChangeOperation("svc_op", OperationType.MODIFY_FILE.value, "services/user_service.py", layer="SERVICE"),
    ]
    stages = planner._partition_into_stages(ops)
    assert len(stages) >= 3

    # Database stage must come before Service, API, and Docs
    stage_titles = [s.title.lower() for s in stages]
    db_idx = next(i for i, t in enumerate(stage_titles) if "database" in t or "data" in t or "model" in t or "foundation" in t)
    doc_idx = next(i for i, t in enumerate(stage_titles) if "documentation" in t or "docs" in t or "final" in t)
    assert db_idx < doc_idx


# =============================================================================
# 7. VALIDATION GATES ENGINE
# =============================================================================

def test_build_validation_plan_generates_comprehensive_gates(planner):
    """Verifies validation gates include Compile, Lint, Unit Tests, Integration Tests, etc."""
    ops = [
        ChangeOperation("op_api", OperationType.MODIFY_FILE.value, "api/routes.py", layer="API"),
        ChangeOperation("op_test", OperationType.ADD_TEST.value, "tests/test_api.py", layer="TESTS"),
    ]
    gates = planner.build_validation_plan(ops)
    gate_types = [g.gate_type for g in gates]

    assert GateType.COMPILE.value in gate_types
    assert GateType.LINT.value in gate_types
    assert GateType.UNIT_TESTS.value in gate_types
    assert GateType.INTEGRATION_TESTS.value in gate_types
    assert GateType.GIT_STATUS_CLEAN.value in gate_types


def test_build_validation_plan_with_architecture_manager(populated_symbol_graph, temp_workspace):
    """Verifies ARCHITECTURE_VALIDATION gate is added when ArchitectureManager is provided."""
    adr_mgr = ArchitectureManager(persistence_path=temp_workspace / "adrs.json")
    planner = ChangeExecutionPlanner(symbol_graph=populated_symbol_graph)
    ops = [ChangeOperation("op1", OperationType.MODIFY_FILE.value, "core/service.py")]
    gates = planner.build_validation_plan(ops, architecture_manager=adr_mgr)
    gate_types = [g.gate_type for g in gates]
    assert GateType.ARCHITECTURE_VALIDATION.value in gate_types


# =============================================================================
# 8. COMMIT STRATEGY GENERATION
# =============================================================================

def test_build_commit_plan_groups_by_layer(planner):
    """Verifies atomic commits are generated for distinct architectural layers."""
    ops = [
        ChangeOperation("op_db", OperationType.MODIFY_FILE.value, "models/user.py", layer="DATABASE"),
        ChangeOperation("op_api", OperationType.MODIFY_FILE.value, "api/users.py", layer="API"),
        ChangeOperation("op_doc", OperationType.UPDATE_DOCS.value, "docs/api.md", layer="DOCS"),
    ]
    stages = planner._partition_into_stages(ops)
    commits = planner.build_commit_plan(stages)

    assert len(commits) >= 2
    commit_layers = [c.layer for c in commits]
    assert "DATABASE" in commit_layers or "CORE" in commit_layers
    assert all(len(c.files) > 0 for c in commits)
    assert all(c.message for c in commits)


# =============================================================================
# 9. ROLLBACK ENGINE
# =============================================================================

def test_build_rollback_plan_checkpoints(planner):
    """Verifies each execution stage receives an atomic RollbackPoint."""
    ops = [
        ChangeOperation("op1", OperationType.MODIFY_FILE.value, "models/user.py", layer="DATABASE"),
        ChangeOperation("op2", OperationType.MODIFY_FILE.value, "services/user.py", layer="SERVICE"),
    ]
    stages = planner._partition_into_stages(ops)
    rollback_points = planner.build_rollback_plan(stages)

    assert len(rollback_points) == len(stages)
    for idx, rb in enumerate(rollback_points, start=1):
        assert rb.stage_number == idx
        assert rb.point_id == f"rollback-stage-{idx}"
        assert len(rb.modified_files) > 0
        assert rb.recovery_strategy != ""


# =============================================================================
# 10. EXECUTION COST & RISK MODELS
# =============================================================================

def test_estimate_cost_breakdown(planner):
    """Verifies multi-dimensional execution cost model returns all expected metrics."""
    ops = [
        ChangeOperation("op1", OperationType.MODIFY_FILE.value, "a.py", estimated_minutes=10.0),
        ChangeOperation("op2", OperationType.ADD_TEST.value, "test_a.py", estimated_minutes=5.0),
    ]
    stages = planner._partition_into_stages(ops)
    cost = planner.estimate_cost(ops, stages)

    assert "editing_time_minutes" in cost
    assert "testing_time_minutes" in cost
    assert "review_time_minutes" in cost
    assert "rollback_cost_minutes" in cost
    assert "merge_cost_minutes" in cost
    assert "overall_duration_minutes" in cost
    assert cost["overall_duration_minutes"] > 0


def test_risk_scoring_critical_on_conflicts(planner):
    """Verifies overall risk elevates to HIGH or CRITICAL when severe conflicts exist."""
    ops = [
        ChangeOperation("op1", OperationType.MODIFY_FILE.value, "a.py", layer="DATABASE", dependencies=["op2"]),
        ChangeOperation("op2", OperationType.MODIFY_FILE.value, "b.py", layer="API", dependencies=["op1"]),
    ]
    plan = planner.plan_changes(
        task=Task("TASK-CONFLICT", "Cyclic Task", "Task with cyclic deps"),
        operations=ops,
    )
    assert plan.risk in ("HIGH", "CRITICAL")
    assert plan.confidence < 0.95


def test_risk_scoring_low_on_docs(planner):
    """Verifies low risk and high confidence on documentation changes."""
    ops = [
        ChangeOperation("doc1", OperationType.UPDATE_DOCS.value, "README.md", layer="DOCS"),
    ]
    plan = planner.plan_changes(
        task=Task("TASK-DOCS", "Docs Task", "Update readme"),
        operations=ops,
    )
    assert plan.risk == "LOW"
    assert plan.confidence >= 0.90


# =============================================================================
# 11. SERIALIZATION & PERSISTENCE
# =============================================================================

def test_serialize_and_deserialize(planner):
    """Verifies full plan JSON serialization and deserialization."""
    task = Task("TASK-SER", "Serialization Test", "Test JSON roundtrip")
    plan = planner.plan_changes(task=task)

    json_str = planner.serialize(plan)
    assert isinstance(json_str, str)
    assert "TASK-SER" in json_str

    restored = planner.deserialize(json_str)
    assert restored.task_id == "TASK-SER"
    assert len(restored.ordered_stages) == len(plan.ordered_stages)
    assert restored.risk == plan.risk


def test_save_and_load_plan(planner, temp_workspace):
    """Verifies save_plan and load_plan write and read from disk."""
    plan_file = temp_workspace / "memory" / "change_execution_plan.json"
    task = Task("TASK-IO", "Disk IO Test", "Test save/load")
    plan = planner.plan_changes(task=task)

    saved_path = planner.save_plan(plan, plan_file)
    assert saved_path.exists()

    loaded_plan = planner.load_plan(plan_file)
    assert loaded_plan.plan_id == plan.plan_id
    assert loaded_plan.task_id == "TASK-IO"


# =============================================================================
# 12. PROMPT BUILDER INTEGRATION
# =============================================================================

def test_prompt_builder_renders_change_execution_plan(populated_symbol_graph, temp_workspace):
    """Verifies PromptBuilder injects CHANGE EXECUTION PLAN section."""
    planner = ChangeExecutionPlanner(symbol_graph=populated_symbol_graph)
    builder = PromptBuilder(
        symbol_graph=populated_symbol_graph,
        change_execution_planner=planner,
    )

    task = Task("TASK-PROMPT", "Implement User Profile API", "Add user endpoint and view")
    ctx = {
        "project_name": "AutoDev Test",
        "description": "Integration testing",
        "technology_stack": "Python 3.11, FastAPI",
        "current_phase": "Phase 1",
        "symbol_graph": populated_symbol_graph,
        "project_files": {},
        "directory_tree": [],
        "project_root": temp_workspace,
    }

    prompt = builder.build(context=ctx, task=task)
    assert "CHANGE EXECUTION PLAN" in prompt
    assert "Execution Order:" in prompt
    assert "Stage 1:" in prompt
    assert "Validation Gate:" in prompt


# =============================================================================
# 13. ORCHESTRATOR INTEGRATION
# =============================================================================

def test_orchestrator_initializes_and_invokes_change_execution_planner(temp_workspace, populated_symbol_graph):
    """Verifies Orchestrator incorporates ChangeExecutionPlanner and outputs JSON plan."""
    # Write mock project plan
    plan_file = temp_workspace / "memory" / "project_plan.json"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump({"phases": [{"name": "Phase 1", "days": [{"day": 1, "tasks": ["TASK-ORCH"]}]}]}, f)

    planner = ChangeExecutionPlanner(symbol_graph=populated_symbol_graph)
    orchestrator = Orchestrator(
        project_root=temp_workspace,
        plan_path=plan_file,
        state_path=temp_workspace / "memory" / "state.json",
        tasks_path=temp_workspace / "memory" / "tasks.json",
        change_execution_planner=planner,
    )

    assert orchestrator.change_execution_planner is not None
    # Verify plan execution method callable
    task = Task("TASK-ORCH", "Orchestrator Task", "Test execution pipeline")
    exec_plan = orchestrator.change_execution_planner.plan_changes(
        task=task,
        symbol_graph=populated_symbol_graph,
    )
    assert isinstance(exec_plan, ChangeExecutionPlan)
    assert exec_plan.task_id == "TASK-ORCH"


# =============================================================================
# 14. LARGE SCALE BENCHMARK & DETERMINISM
# =============================================================================

def test_large_scale_1000_operations_benchmark():
    """Verifies planning for 1000+ operations executes in <100ms with 100% determinism."""
    ops: List[ChangeOperation] = []
    # Create 1000 operations organized in 10 layers with 100 operations each
    for layer_idx in range(10):
        for op_idx in range(100):
            oid = f"op_L{layer_idx}_{op_idx:03d}"
            deps = []
            if layer_idx > 0:
                # Depend on previous layer's corresponding operation
                deps.append(f"op_L{layer_idx-1}_{op_idx:03d}")
            ops.append(
                ChangeOperation(
                    operation_id=oid,
                    operation_type=OperationType.MODIFY_FILE.value,
                    file=f"layer_{layer_idx}/module_{op_idx}.py",
                    symbol=f"Symbol_{layer_idx}_{op_idx}",
                    dependencies=deps,
                    estimated_minutes=5.0,
                    layer="CORE" if layer_idx < 5 else "API",
                )
            )

    planner = ChangeExecutionPlanner()
    task = Task("TASK-BENCHMARK-1000", "Benchmark 1000 Operations", "Stress test DAG planning")

    start_t = time.perf_counter()
    plan1 = planner.plan_changes(task=task, operations=ops)
    elapsed_ms = (time.perf_counter() - start_t) * 1000.0

    print(f"\n[BENCHMARK] 1000 Operations Planning Time: {elapsed_ms:.2f} ms")
    assert elapsed_ms < 100.0, f"Expected <100ms, took {elapsed_ms:.2f} ms"
    assert len(plan1.ordered_stages) > 0

    # Determinism test: Second run must yield identical stage counts and operations
    plan2 = planner.plan_changes(task=task, operations=ops)
    assert plan1.plan_id.split("-")[0] == plan2.plan_id.split("-")[0]
    assert len(plan1.ordered_stages) == len(plan2.ordered_stages)
    assert plan1.critical_path == plan2.critical_path
    assert plan1.estimated_duration == plan2.estimated_duration


# =============================================================================
# 15. EDGE CASES
# =============================================================================

def test_edge_case_empty_operations(planner):
    """Verifies planner handles task with no operations gracefully."""
    task = Task("TASK-EMPTY", "Empty Task", "No files modified")
    plan = planner.plan_changes(task=task, operations=[])
    assert plan.plan_id != ""
    assert plan.task_id == "TASK-EMPTY"
    assert len(plan.ordered_stages) == 0
    assert plan.risk == "LOW"


def test_edge_case_single_operation_plan(planner):
    """Verifies planner handles a single operation without errors."""
    op = ChangeOperation("single_op", OperationType.MODIFY_FILE.value, "single.py")
    plan = planner.plan_changes(task=Task("TASK-SINGLE", "Single", "Single op"), operations=[op])
    assert len(plan.ordered_stages) == 1
    assert plan.critical_path == ["single_op"]
    assert len(plan.rollback_plan) == 1
    assert len(plan.commit_plan) == 1


def test_edge_case_unconnected_subgraphs(planner):
    """Verifies planner handles completely disconnected subgraphs properly."""
    ops = [
        ChangeOperation("g1_a", OperationType.MODIFY_FILE.value, "g1_a.py"),
        ChangeOperation("g1_b", OperationType.MODIFY_FILE.value, "g1_b.py", dependencies=["g1_a"]),
        ChangeOperation("g2_a", OperationType.MODIFY_FILE.value, "g2_a.py"),
        ChangeOperation("g2_b", OperationType.MODIFY_FILE.value, "g2_b.py", dependencies=["g2_a"]),
    ]
    order = planner.topological_sort(ops)
    assert len(order) == 4
    # Within each subgraph, order must be preserved
    assert order.index("g1_a") < order.index("g1_b")
    assert order.index("g2_a") < order.index("g2_b")


def test_edge_case_nonexistent_file_in_operation(planner):
    """Verifies planner infers layers correctly for unknown file paths."""
    op = ChangeOperation("unknown_op", OperationType.MODIFY_FILE.value, "custom_path/nested/something.unknown")
    assert op.layer == "CORE"
    plan = planner.plan_changes(task=Task("TASK-UNK", "Unknown", "Unknown file"), operations=[op])
    assert len(plan.ordered_stages) >= 1


def test_all_operation_types_enum():
    """Verifies all enum operation types are defined and valid strings."""
    expected = [
        "CREATE_FILE", "MODIFY_FILE", "DELETE_FILE", "RENAME_FILE",
        "ADD_SYMBOL", "MODIFY_SYMBOL", "DELETE_SYMBOL", "EXTRACT_METHOD",
        "SPLIT_CLASS", "UPDATE_IMPORTS", "ADD_TEST", "MODIFY_TEST",
        "MIGRATE_SCHEMA", "UPDATE_CONFIG", "UPDATE_DOCS", "REFACTOR_STRUCTURE"
    ]
    for exp in expected:
        assert hasattr(OperationType, exp)
        assert OperationType[exp].value == exp


def test_all_gate_types_enum():
    """Verifies all validation gate types are defined."""
    expected = [
        "COMPILE", "LINT", "UNIT_TESTS", "INTEGRATION_TESTS",
        "ARCHITECTURE_VALIDATION", "DEPENDENCY_VALIDATION", "SECURITY_SCAN",
        "COVERAGE_CHECK", "PERFORMANCE_BENCHMARK", "GIT_STATUS_CLEAN"
    ]
    for exp in expected:
        assert hasattr(GateType, exp)
        assert GateType[exp].value == exp


def test_all_conflict_types_enum():
    """Verifies all conflict types are defined."""
    expected = [
        "SAME_FILE_MULTIPLE_EDITS", "SAME_SYMBOL_MODIFIED_TWICE",
        "OVERLAPPING_METHODS", "MERGE_CONFLICT_RISK",
        "ARCHITECTURE_CONFLICT", "STATE_CONFLICT",
        "DEPENDENCY_CONFLICT", "CYCLIC_DEPENDENCY"
    ]
    for exp in expected:
        assert hasattr(ConflictType, exp)
        assert ConflictType[exp].value == exp


def test_layer_rank_and_inference(planner):
    """Verifies layer inference and architectural ordering ranks."""
    assert planner._infer_layer_from_path("db/models/user.py") == "DATABASE"
    assert planner._infer_layer_from_path("config/settings.env") == "CONFIG"
    assert planner._infer_layer_from_path("services/auth_service.py") == "SERVICE"
    assert planner._infer_layer_from_path("api/controllers/auth.py") == "API"
    assert planner._infer_layer_from_path("frontend/src/App.tsx") == "FRONTEND"
    assert planner._infer_layer_from_path("tests/unit/test_auth.py") == "TESTS"
    assert planner._infer_layer_from_path("docs/architecture.md") == "DOCS"

    db_rank = planner._get_layer_rank("DATABASE")
    api_rank = planner._get_layer_rank("API")
    test_rank = planner._get_layer_rank("TESTS")
    assert db_rank < api_rank < test_rank


def test_partition_disjoint_file_groups(planner):
    """Verifies file-level conflict separation into disjoint parallel subgroups."""
    op1 = ChangeOperation("op1", OperationType.MODIFY_FILE.value, "file_a.py")
    op2 = ChangeOperation("op2", OperationType.MODIFY_FILE.value, "file_a.py")
    op3 = ChangeOperation("op3", OperationType.MODIFY_FILE.value, "file_b.py")
    op_map = {"op1": op1, "op2": op2, "op3": op3}

    groups = planner._partition_disjoint_file_groups(["op1", "op2", "op3"], op_map)
    assert len(groups) == 2
    # op1 and op3 can be in group 1, op2 in group 2
    assert "op1" in groups[0]
    assert "op3" in groups[0]
    assert "op2" in groups[1]


def test_cycle_finder_dfs(planner):
    """Verifies elementary cycle detection via DFS."""
    graph = {
        "A": ["B"],
        "B": ["C"],
        "C": ["A"],
        "D": [],
    }
    cycles = planner._find_cycles(graph, ["A", "B", "C", "D"])
    assert len(cycles) > 0
    flat = [node for c in cycles for node in c]
    assert "A" in flat and "B" in flat and "C" in flat


def test_custom_persistence_path_and_atomic_replace(temp_workspace):
    """Verifies custom persistence path initialization and atomic save."""
    custom_path = temp_workspace / "custom" / "plan.json"
    planner = ChangeExecutionPlanner(persistence_path=custom_path)
    task = Task("TASK-CUSTOM-PATH", "Custom Path Task", "Test persistence")
    plan = planner.plan_changes(task=task, auto_save=True)

    assert custom_path.exists()
    loaded = planner.load_plan(custom_path)
    assert loaded is not None
    assert loaded.plan_id == plan.plan_id


def test_deterministic_tie_breaking(planner):
    """Verifies priority ordering with equal in-degree breaks ties deterministically."""
    ops = [
        ChangeOperation("op_z", OperationType.MODIFY_FILE.value, "z.py", layer="DOCS", risk="LOW"),
        ChangeOperation("op_a", OperationType.MODIFY_FILE.value, "a.py", layer="DATABASE", risk="HIGH"),
        ChangeOperation("op_m", OperationType.MODIFY_FILE.value, "m.py", layer="CORE", risk="MEDIUM"),
    ]
    order = planner.topological_sort(ops)
    # Lower layer rank (DATABASE = 1, CORE = 3, DOCS = 8) must come first
    assert order == ["op_a", "op_m", "op_z"]
