"""
test_execution_engine.py - Comprehensive Unit & Integration Tests for ExecutionEngine (v2.1)
"""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from agents.coder_agent import CoderAgent, GeneratedFile, GeneratedResult
from agents.file_writer_agent import FileWriterAgent
from agents.git_agent import CommitResult, GitAgent, GitStatus
from agents.task_planner_agent import Task
from agents.tester_agent import TesterAgent, TestResult
from core.architecture_manager import ArchitectureManager, ValidationReport
from core.change_execution_planner import (
    ChangeExecutionPlan,
    ChangeExecutionPlanner,
    ChangeOperation,
    CommitPlanEntry,
    ExecutionStage,
    GateType,
    OperationType,
    RollbackPoint,
    ValidationGate,
)
from core.execution_engine import ApprovalPolicy, ExecutionEngine
from core.execution_transaction import (
    ExecutionReport,
    ExecutionStatus,
    ExecutionTransaction,
)
from core.orchestrator import Orchestrator
from core.prompt_builder import PromptBuilder


# =============================================================================
# FIXTURES & SAMPLE PLANS
# =============================================================================

@pytest.fixture
def sample_change_execution_plan():
    """Generates a structured multi-stage ChangeExecutionPlan fixture."""
    op1 = ChangeOperation(
        operation_id="OP-001",
        operation_type=OperationType.CREATE_FILE.value,
        file="models/user.py",
        reason="Create User domain model",
        target_content="class User:\n    def __init__(self, name: str):\n        self.name = name\n",
        layer="DATABASE",
    )
    op2 = ChangeOperation(
        operation_id="OP-002",
        operation_type=OperationType.CREATE_FILE.value,
        file="services/user_service.py",
        reason="Create UserService business logic",
        target_content="class UserService:\n    def get_user(self):\n        return 'User'\n",
        layer="CORE",
    )
    op3 = ChangeOperation(
        operation_id="OP-003",
        operation_type=OperationType.CREATE_FILE.value,
        file="tests/test_user.py",
        reason="Add unit tests",
        target_content="def test_user():\n    assert True\n",
        layer="TESTS",
    )

    stage1 = ExecutionStage(
        stage_number=1,
        title="Database Layer Implementation",
        operations=[op1],
        parallel=False,
        validation_gates=[
            ValidationGate(
                gate_id="gate-compile-1",
                gate_type=GateType.COMPILE.value,
                command="python -m py_compile models/user.py",
                description="Compile models",
                blocking=True,
            )
        ],
    )
    stage2 = ExecutionStage(
        stage_number=2,
        title="Core Services Implementation",
        operations=[op2],
        parallel=False,
        validation_gates=[
            ValidationGate(
                gate_id="gate-compile-2",
                gate_type=GateType.COMPILE.value,
                command="python -m py_compile services/user_service.py",
                description="Compile service",
                blocking=True,
            )
        ],
    )
    stage3 = ExecutionStage(
        stage_number=3,
        title="Testing & QA",
        operations=[op3],
        parallel=False,
        validation_gates=[
            ValidationGate(
                gate_id="gate-compile-3",
                gate_type=GateType.COMPILE.value,
                command="python -m py_compile tests/test_user.py",
                description="Compile tests",
                blocking=True,
            )
        ],
    )

    return ChangeExecutionPlan(
        plan_id="CEP-TEST-PLAN-01",
        task_id="TASK-USER-AUTH",
        ordered_stages=[stage1, stage2, stage3],
        dependency_graph={"OP-002": ["OP-001"], "OP-003": ["OP-002"]},
        estimated_duration=25.0,
        critical_path=["OP-001", "OP-002", "OP-003"],
        risk="LOW",
        confidence=0.95,
    )


# =============================================================================
# 1. PLAN VALIDATION & WORKSPACE INSPECTION TESTS
# =============================================================================

def test_validate_plan_success(sample_change_execution_plan, tmp_path):
    """Verifies that a valid ChangeExecutionPlan passes validation."""
    engine = ExecutionEngine(workspace_root=tmp_path)
    is_valid, errors = engine.validate_plan(sample_change_execution_plan)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_plan_empty_is_handled(tmp_path):
    """Verifies that an empty plan validates cleanly without errors."""
    engine = ExecutionEngine(workspace_root=tmp_path)
    empty_plan = ChangeExecutionPlan(
        plan_id="CEP-EMPTY",
        task_id="TASK-EMPTY",
        ordered_stages=[],
    )
    is_valid, errors = engine.validate_plan(empty_plan)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_plan_duplicate_op_ids_rejected(tmp_path):
    """Verifies that duplicate operation IDs in a plan are detected and rejected."""
    op_dup = ChangeOperation(
        operation_id="OP-001",
        operation_type=OperationType.MODIFY_FILE.value,
        file="core/app.py",
    )
    stage = ExecutionStage(
        stage_number=1,
        title="Stage 1",
        operations=[op_dup, op_dup],
    )
    plan = ChangeExecutionPlan(
        plan_id="CEP-DUP",
        task_id="TASK-DUP",
        ordered_stages=[stage],
    )
    engine = ExecutionEngine(workspace_root=tmp_path)
    is_valid, errors = engine.validate_plan(plan)
    assert is_valid is False
    assert any("duplicate operation_id" in e.lower() for e in errors)


def test_inspect_workspace(tmp_path):
    """Verifies workspace inspection telemetry."""
    engine = ExecutionEngine(workspace_root=tmp_path)
    inspection = engine.inspect_workspace(target_files=["models/user.py"])
    assert inspection["workspace_root"] == str(tmp_path.resolve())
    assert inspection["is_locked"] is False


# =============================================================================
# 2. APPROVAL POLICY TESTS
# =============================================================================

def test_approval_policy_critical_risk_requires_approval(tmp_path):
    """Verifies that plans marked CRITICAL require approval by default."""
    plan = ChangeExecutionPlan(
        plan_id="CEP-CRIT",
        task_id="TASK-CRIT",
        ordered_stages=[],
        risk="CRITICAL",
    )
    engine = ExecutionEngine(workspace_root=tmp_path)
    authorized, msg = engine.authorize_execution(plan, mode="apply")
    assert authorized is False
    assert "CRITICAL risk" in msg


def test_approval_policy_approver_callback(tmp_path):
    """Verifies that an injected approver function callback can grant authorization."""
    plan = ChangeExecutionPlan(
        plan_id="CEP-CRIT-OK",
        task_id="TASK-CRIT-OK",
        ordered_stages=[],
        risk="CRITICAL",
    )
    policy = ApprovalPolicy(
        require_approval_for_critical_risk=True,
        approver_fn=lambda p, insp: True,  # Grant approval
    )
    engine = ExecutionEngine(workspace_root=tmp_path, approval_policy=policy)
    authorized, msg = engine.authorize_execution(plan, mode="apply")
    assert authorized is True
    assert "Authorized via approver function" in msg


# =============================================================================
# 3. DRY RUN EXECUTION TESTS
# =============================================================================

def test_dry_run_is_strictly_non_mutating(sample_change_execution_plan, tmp_path):
    """Verifies that DRY RUN mode performs genuine simulation without modifying the filesystem."""
    engine = ExecutionEngine(
        workspace_root=tmp_path,
        journal_root=tmp_path / "journal",
        report_dir=tmp_path / "reports",
    )

    report: ExecutionReport = engine.execute_plan(sample_change_execution_plan, mode="dry_run")

    assert report.overall_success is True
    assert report.status == ExecutionStatus.SUCCEEDED
    assert report.stages_completed == 3
    assert report.operations_completed == 3
    assert len(report.files_created) == 3

    # Verify that NO files were created on disk
    assert not (tmp_path / "models" / "user.py").exists()
    assert not (tmp_path / "services" / "user_service.py").exists()
    assert not (tmp_path / "tests" / "test_user.py").exists()


# =============================================================================
# 4. APPLY EXECUTION & ATOMIC MATERIALIZATION TESTS
# =============================================================================

def test_apply_mode_successful_execution(sample_change_execution_plan, tmp_path):
    """Verifies full transactional mutation, compilation validation, and report persistence."""
    journal_dir = tmp_path / "memory" / "journal"
    report_dir = tmp_path / "memory" / "reports"

    engine = ExecutionEngine(
        workspace_root=tmp_path,
        journal_root=journal_dir,
        report_dir=report_dir,
    )

    report: ExecutionReport = engine.execute_plan(sample_change_execution_plan, mode="apply")

    assert report.overall_success is True
    assert report.status == ExecutionStatus.SUCCEEDED
    assert report.stages_completed == 3
    assert report.stages_failed == 0
    assert report.operations_completed == 3

    # Verify files materialized on disk
    user_model = tmp_path / "models" / "user.py"
    user_service = tmp_path / "services" / "user_service.py"
    user_test = tmp_path / "tests" / "test_user.py"

    assert user_model.exists()
    assert "class User:" in user_model.read_text(encoding="utf-8")
    assert user_service.exists()
    assert user_test.exists()

    # Verify report was persisted
    saved_report = engine.get_execution_report(report.transaction_id)
    assert saved_report is not None
    assert saved_report.transaction_id == report.transaction_id
    assert saved_report.overall_success is True


# =============================================================================
# 5. BLOCKING VALIDATION GATE FAILURE & AUTOMATIC ROLLBACK TESTS
# =============================================================================

def test_blocking_validation_gate_failure_triggers_automatic_verified_rollback(tmp_path):
    """
    Verifies that when a blocking validation gate fails:
    1. Downstream stages are NOT scheduled.
    2. Automatic rollback restores the original workspace state.
    3. The restored state is 100% verified.
    """
    # Pre-existing file
    existing_file = tmp_path / "core" / "app.py"
    existing_file.parent.mkdir(parents=True)
    existing_file.write_text("APP_INITIAL_STATE = True\n", encoding="utf-8")

    op_modify = ChangeOperation(
        operation_id="OP-MOD-1",
        operation_type=OperationType.MODIFY_FILE.value,
        file="core/app.py",
        target_content="APP_INITIAL_STATE = False\nSYNTAX_ERROR_BROKEN ::::\n",
    )
    op_downstream = ChangeOperation(
        operation_id="OP-DOWNSTREAM-2",
        operation_type=OperationType.CREATE_FILE.value,
        file="core/downstream.py",
        target_content="# Should never be created\n",
    )

    # Stage 1 has a syntax error that will fail py_compile validation
    stage1 = ExecutionStage(
        stage_number=1,
        title="Failing Stage",
        operations=[op_modify],
        validation_gates=[
            ValidationGate(
                gate_id="gate-compile-fail",
                gate_type=GateType.COMPILE.value,
                command="python -m py_compile core/app.py",
                description="Syntax verification",
                blocking=True,
            )
        ],
    )
    stage2 = ExecutionStage(
        stage_number=2,
        title="Downstream Stage",
        operations=[op_downstream],
    )

    failing_plan = ChangeExecutionPlan(
        plan_id="CEP-FAIL-ROLLBACK",
        task_id="TASK-FAIL",
        ordered_stages=[stage1, stage2],
    )

    engine = ExecutionEngine(
        workspace_root=tmp_path,
        journal_root=tmp_path / "journal",
        report_dir=tmp_path / "reports",
    )

    report: ExecutionReport = engine.execute_plan(
        failing_plan, mode="apply", auto_rollback=True
    )

    # 1. Overall execution failed
    assert report.overall_success is False
    assert report.status in {ExecutionStatus.ROLLED_BACK, ExecutionStatus.FAILED}
    assert report.stages_failed == 1
    assert report.stages_completed == 0

    # 2. Downstream stage was NEVER executed
    assert not (tmp_path / "core" / "downstream.py").exists()

    # 3. Modified file was automatically restored to original content
    assert existing_file.read_text(encoding="utf-8") == "APP_INITIAL_STATE = True\n"
    assert report.rollback_summary is not None
    assert report.rollback_summary["verification_passed"] is True


# =============================================================================
# 6. CONTROL FLOW: PAUSE, RESUME, CANCEL TESTS
# =============================================================================

def test_cancel_transaction(tmp_path):
    """Verifies that cancelling an active transaction halts execution."""
    engine = ExecutionEngine(workspace_root=tmp_path)
    tx_id = "tx-cancel-01"
    cancelled = engine.cancel(tx_id)
    assert cancelled is True
    assert engine._is_cancelled(tx_id) is True


def test_resume_transaction(tmp_path):
    """Verifies resuming a saved transaction from journal."""
    journal_dir = tmp_path / "journal"
    engine = ExecutionEngine(workspace_root=tmp_path, journal_root=journal_dir)

    tx_id = "tx-resume-01"
    journal = engine.journal_root / tx_id
    journal.mkdir(parents=True, exist_ok=True)
    tx = ExecutionTransaction(tx_id, "p1", "t1", tmp_path)
    tx.transition_to(ExecutionStatus.VALIDATING)
    tx.transition_to(ExecutionStatus.READY)
    tx.transition_to(ExecutionStatus.RUNNING)
    tx.transition_to(ExecutionStatus.PAUSED)

    j = engine.journal_root
    from core.execution_journal import ExecutionJournal
    ej = ExecutionJournal(tx_id, journal_root=j)
    ej.persist_transaction_snapshot(tx)

    report = engine.resume(tx_id)
    assert report.overall_success is True
    assert report.transaction_id == tx_id


# =============================================================================
# 7. PROMPT BUILDER & ORCHESTRATOR INTEGRATION TESTS
# =============================================================================

def test_prompt_builder_renders_execution_safety_section():
    """Verifies PromptBuilder includes EXECUTION SAFETY & TRANSACTION POLICY section."""
    builder = PromptBuilder()
    context = {
        "project_name": "SecureApp",
        "description": "Secure autonomous agent",
        "technology_stack": "Python",
        "transaction_id": "TX-PROMPT-01",
        "execution_mode": "apply",
        "workspace_root": "projects/SecureApp",
    }
    task = Task("TASK-01", "Build Auth", "Create authentication middleware", estimated_files=["src/auth.py"])
    prompt = builder.build(context=context, task=task)

    assert "EXECUTION SAFETY & TRANSACTION POLICY" in prompt
    assert "Transaction ID : TX-PROMPT-01" in prompt
    assert "Security Notice" in prompt
    assert "Authorized Target Files:" in prompt
    assert "src/auth.py" in prompt


def test_orchestrator_initializes_with_execution_engine(tmp_path):
    """Verifies Orchestrator attaches and provides ExecutionEngine subsystem."""
    plan_file = tmp_path / "memory" / "project_plan.json"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(json.dumps({"phases": [{"name": "Phase 1", "days": [{"day": 1, "tasks": ["T1"]}]}]}), encoding="utf-8")

    orch = Orchestrator(
        project_root=tmp_path,
        plan_path=plan_file,
        state_path=tmp_path / "memory" / "state.json",
        tasks_path=tmp_path / "memory" / "tasks.json",
    )
    assert orch.execution_engine is not None
    assert isinstance(orch.execution_engine, ExecutionEngine)


# =============================================================================
# 8. HIGH-SCALE PERFORMANCE BENCHMARKS (100 & 1,000 OPERATIONS)
# =============================================================================

def test_large_scale_1000_operations_dry_run_benchmark(tmp_path):
    """Verifies that dry-run planning and simulation of 1,000 operations executes in <100ms."""
    ops: List[ChangeOperation] = []
    for layer_idx in range(10):
        for op_idx in range(100):
            ops.append(
                ChangeOperation(
                    operation_id=f"op_{layer_idx}_{op_idx:03d}",
                    operation_type=OperationType.CREATE_FILE.value,
                    file=f"src/layer_{layer_idx}/mod_{op_idx}.py",
                    reason="Benchmark test",
                )
            )

    planner = ChangeExecutionPlanner()
    task = Task("TASK-PERF-1000", "Stress 1000 Ops", "Benchmark")
    plan = planner.plan_changes(task=task, operations=ops)

    engine = ExecutionEngine(workspace_root=tmp_path)
    start_t = time.perf_counter()
    report = engine.execute_plan(plan, mode="dry_run")
    elapsed_ms = (time.perf_counter() - start_t) * 1000.0

    print(f"\n[BENCHMARK] 1,000 Operations ExecutionEngine Dry-Run Time: {elapsed_ms:.2f} ms")
    assert report.overall_success is True
    assert report.operations_completed == 1000
    assert elapsed_ms < 100.0  # Must complete in under 100ms
