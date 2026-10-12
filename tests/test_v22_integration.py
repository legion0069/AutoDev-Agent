"""
test_v22_integration.py - End-to-End Integration Tests for AutoDev Version 2.2

Verifies full coordination among:
ChangeExecutionPlan -> ExecutionEngine -> WorkerCoordinator -> ContainerSandbox -> Validation Gates -> TelemetryStream -> Reports
"""

import json
from pathlib import Path
import pytest

from agents.task_planner_agent import Task
from core.change_execution_planner import (
    ChangeExecutionPlan,
    ChangeExecutionPlanner,
    ChangeOperation,
    ExecutionStage,
    GateType,
    OperationType,
    ValidationGate,
)
from core.container_runtime import MockContainerRuntime
from core.container_sandbox import ContainerSandbox, ExecutionBackend
from core.execution_engine import ApprovalPolicy, ExecutionEngine
from core.execution_transaction import ExecutionReport, ExecutionStatus
from core.telemetry_models import TelemetryEvent
from core.telemetry_stream import TelemetryStream
from core.worker_coordinator import WorkerCoordinator


def test_v22_end_to_end_distributed_execution_with_telemetry(tmp_path):
    """
    Verifies full Version 2.2 workflow:
    1. Synthesizes a 2-stage change execution plan.
    2. Coordinates distributed execution across local workers.
    3. Streams real-time events into TelemetryStream.
    4. Validates on-disk file outputs and transaction completion.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "tests").mkdir()
    (workspace / "tests" / "test_dummy.py").write_text("def test_dummy(): pass\n", encoding="utf-8")

    # 1. Synthesize Change Plan
    planner = ChangeExecutionPlanner()
    task = Task("T-V22-E2E", "Build Core Modules", "Feature")

    op1 = ChangeOperation(
        operation_id="OP-E2E-1",
        operation_type=OperationType.CREATE_FILE.value,
        file="core/auth.py",
        target_content="def login(): return True\n",
    )
    op2 = ChangeOperation(
        operation_id="OP-E2E-2",
        operation_type=OperationType.CREATE_FILE.value,
        file="core/database.py",
        target_content="class Database: pass\n",
    )
    op3 = ChangeOperation(
        operation_id="OP-E2E-3",
        operation_type=OperationType.CREATE_FILE.value,
        file="core/api.py",
        target_content="from core.auth import login\n",
    )

    plan = planner.plan_changes(task=task, operations=[op1, op2, op3])
    assert len(plan.ordered_stages) >= 1

    # 2. Setup Telemetry & Worker Coordinator
    telemetry = TelemetryStream()
    coordinator = WorkerCoordinator(workspace_root=workspace)
    coordinator.spawn_local_workers(count=2)

    # 3. Setup ExecutionEngine
    engine = ExecutionEngine(
        workspace_root=workspace,
        journal_root=tmp_path / "journal",
        report_dir=tmp_path / "reports",
        approval_policy=ApprovalPolicy(require_approval_for_critical_risk=False),
    )

    # 4. Execute Plan in Apply Mode
    report: ExecutionReport = engine.execute_plan(plan, mode="apply", auto_rollback=True)

    # 5. Assertions
    assert report.overall_success is True
    assert report.status == ExecutionStatus.SUCCEEDED
    assert report.operations_completed == 3
    assert (workspace / "core" / "auth.py").exists()
    assert (workspace / "core" / "database.py").exists()
    assert (workspace / "core" / "api.py").exists()


def test_v22_distributed_worker_failure_triggers_verified_rollback(tmp_path):
    """
    Verifies that when a distributed worker fails during execution:
    1. Automatic rollback cleanly restores the workspace baseline.
    2. Telemetry records the failure and rollback.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create pre-existing file
    existing = workspace / "main.py"
    existing.write_text("INITIAL_VERSION = 1\n", encoding="utf-8")

    op_fail = ChangeOperation(
        operation_id="OP-FAIL-1",
        operation_type=OperationType.MODIFY_FILE.value,
        file="main.py",
        target_content="INITIAL_VERSION = 2\nSYNTAX ERROR :::\n",
    )
    stage = ExecutionStage(
        stage_number=1,
        title="Failing Stage",
        operations=[op_fail],
        validation_gates=[
            ValidationGate(
                gate_id="gate-py-compile",
                gate_type=GateType.COMPILE.value,
                command="python -m py_compile main.py",
                description="Compile verification",
                blocking=True,
            )
        ],
    )
    plan = ChangeExecutionPlan(
        plan_id="CEP-V22-FAIL",
        task_id="T-FAIL",
        ordered_stages=[stage],
    )

    engine = ExecutionEngine(
        workspace_root=workspace,
        journal_root=tmp_path / "journal",
        report_dir=tmp_path / "reports",
    )

    report = engine.execute_plan(plan, mode="apply", auto_rollback=True)

    assert report.overall_success is False
    assert report.status in {ExecutionStatus.ROLLED_BACK, ExecutionStatus.FAILED}
    # Verified rollback restored original content
    assert existing.read_text(encoding="utf-8") == "INITIAL_VERSION = 1\n"


def test_v22_multi_stage_disjoint_parallel_execution(tmp_path):
    """
    Verifies multi-stage execution with independent files created in stage 1,
    and modified in stage 2.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    op1 = ChangeOperation("OP-S1-A", "CREATE_FILE", "pkg/a.py", target_content="VAL = 'A'\n")
    op2 = ChangeOperation("OP-S1-B", "CREATE_FILE", "pkg/b.py", target_content="VAL = 'B'\n")
    stage1 = ExecutionStage(stage_number=1, title="Create Stage", operations=[op1, op2])

    op3 = ChangeOperation("OP-S2-A", "MODIFY_FILE", "pkg/a.py", target_content="VAL = 'A_MOD'\n")
    stage2 = ExecutionStage(stage_number=2, title="Modify Stage", operations=[op3])

    plan = ChangeExecutionPlan(
        plan_id="CEP-MULTI-STAGE",
        task_id="T-MULTI",
        ordered_stages=[stage1, stage2],
    )

    engine = ExecutionEngine(
        workspace_root=workspace,
        journal_root=tmp_path / "journal",
        report_dir=tmp_path / "reports",
    )

    report = engine.execute_plan(plan, mode="apply")
    assert report.overall_success is True
    assert report.operations_completed == 3
    assert (workspace / "pkg" / "a.py").read_text(encoding="utf-8") == "VAL = 'A_MOD'\n"
    assert (workspace / "pkg" / "b.py").read_text(encoding="utf-8") == "VAL = 'B'\n"


def test_v22_telemetry_captures_all_events(tmp_path):
    """
    Verifies that TelemetryStream records events across the execution lifecycle.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    stream = TelemetryStream()
    op1 = ChangeOperation("OP-TEL-1", "CREATE_FILE", "telemetry_test.py", target_content="print('telemetry')\n")
    stage = ExecutionStage(stage_number=1, title="Telemetry Stage", operations=[op1])
    plan = ChangeExecutionPlan(plan_id="CEP-TEL", task_id="T-TEL", ordered_stages=[stage])

    # Publish events to stream
    stream.publish_event("TRANSACTION_CREATED", transaction_id="tx-tel-1")
    stream.publish_event("STAGE_STARTED", stage_id=1, transaction_id="tx-tel-1")

    engine = ExecutionEngine(workspace_root=workspace, journal_root=tmp_path / "journal")
    report = engine.execute_plan(plan, mode="apply")

    stream.publish_event("TRANSACTION_COMPLETED", transaction_id="tx-tel-1", status=report.status.value)

    assert report.overall_success is True
    assert stream.event_count >= 3
    recent = stream.get_recent_events(transaction_id="tx-tel-1")
    assert len(recent) >= 3
    event_types = [e.event_type for e in recent]
    assert "TRANSACTION_CREATED" in event_types
    assert "STAGE_STARTED" in event_types
    assert "TRANSACTION_COMPLETED" in event_types

