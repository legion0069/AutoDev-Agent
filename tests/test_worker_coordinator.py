"""
test_worker_coordinator.py - Tests for Worker Coordinator & Distributed Stage Execution (v2.2)
"""

import pytest
from pathlib import Path

from core.change_execution_planner import ChangeOperation, ExecutionStage
from core.execution_transaction import ExecutionStatus, ExecutionTransaction
from core.worker_coordinator import WorkerCoordinator


def test_spawn_local_worker_pool(tmp_path):
    """Verifies spawning and registering local worker agents."""
    coord = WorkerCoordinator(workspace_root=tmp_path)
    workers = coord.spawn_local_workers(count=3)

    assert len(workers) == 3
    registered = coord.registry.list_workers()
    assert len(registered) == 3
    assert registered[0].worker_id == "local-worker-1"


def test_execute_stage_distributed_success(tmp_path):
    """Verifies executing a stage distributed across local workers."""
    coord = WorkerCoordinator(workspace_root=tmp_path)
    coord.spawn_local_workers(count=2)

    tx = ExecutionTransaction(
        transaction_id="tx-coord-01",
        plan_id="p1",
        task_id="t1",
        workspace_root=tmp_path,
    )

    op1 = ChangeOperation(
        operation_id="OP-C1",
        operation_type="CREATE_FILE",
        file="src/mod_a.py",
        target_content="def func_a(): pass\n",
    )
    op2 = ChangeOperation(
        operation_id="OP-C2",
        operation_type="CREATE_FILE",
        file="src/mod_b.py",
        target_content="def func_b(): pass\n",
    )
    stage = ExecutionStage(stage_number=1, title="Parallel Stage", operations=[op1, op2])

    res = coord.execute_stage_distributed(tx, stage)

    assert res.status == ExecutionStatus.SUCCEEDED
    assert len(res.operation_results) == 2
    assert (tmp_path / "src" / "mod_a.py").exists()
    assert (tmp_path / "src" / "mod_b.py").exists()
    assert "src/mod_a.py" in tx.created_files
    assert "src/mod_b.py" in tx.created_files


def test_execute_stage_distributed_path_traversal_rejection(tmp_path):
    """Verifies that an operation attempting path traversal fails and marks stage as FAILED."""
    coord = WorkerCoordinator(workspace_root=tmp_path)
    coord.spawn_local_workers(count=1)

    tx = ExecutionTransaction(
        transaction_id="tx-coord-02",
        plan_id="p1",
        task_id="t1",
        workspace_root=tmp_path,
    )

    op_bad = ChangeOperation(
        operation_id="OP-TRAVERSAL",
        operation_type="CREATE_FILE",
        file="../escaped.py",
        target_content="# Bad",
    )
    stage = ExecutionStage(stage_number=1, title="Bad Stage", operations=[op_bad])

    res = coord.execute_stage_distributed(tx, stage)

    assert res.status == ExecutionStatus.FAILED
    assert res.operation_results[0].error_type == "PathContainmentError" or "containment violation" in str(res.failure_reason)
    assert not (tmp_path.parent / "escaped.py").exists()


def test_execute_stage_distributed_modify_and_delete(tmp_path):
    """Verifies modifying and deleting existing files in a distributed stage."""
    file_a = tmp_path / "file_a.py"
    file_a.write_text("v1\n", encoding="utf-8")
    file_b = tmp_path / "file_b.py"
    file_b.write_text("to delete\n", encoding="utf-8")

    coord = WorkerCoordinator(workspace_root=tmp_path)
    coord.spawn_local_workers(count=2)

    tx = ExecutionTransaction("tx-mod-del", "p1", "t1", tmp_path)

    op_mod = ChangeOperation(
        operation_id="OP-MOD",
        operation_type="MODIFY_FILE",
        file="file_a.py",
        target_content="v2\n",
    )
    op_del = ChangeOperation(
        operation_id="OP-DEL",
        operation_type="DELETE_FILE",
        file="file_b.py",
    )
    stage = ExecutionStage(stage_number=1, title="Mod/Del Stage", operations=[op_mod, op_del])

    res = coord.execute_stage_distributed(tx, stage)

    assert res.status == ExecutionStatus.SUCCEEDED
    assert file_a.read_text(encoding="utf-8") == "v2\n"
    assert not file_b.exists()
    assert "file_a.py" in tx.modified_files
    assert "file_b.py" in tx.deleted_files


def test_execute_stage_distributed_protected_path_rejection(tmp_path):
    """Verifies that writing to .env or .git is rejected with ProtectedPathViolationError."""
    coord = WorkerCoordinator(workspace_root=tmp_path)
    coord.spawn_local_workers(count=1)

    tx = ExecutionTransaction("tx-prot", "p1", "t1", tmp_path)

    op_env = ChangeOperation(
        operation_id="OP-ENV",
        operation_type="CREATE_FILE",
        file=".env",
        target_content="SECRET_KEY=12345\n",
    )
    stage = ExecutionStage(stage_number=1, title="Protected Stage", operations=[op_env])

    res = coord.execute_stage_distributed(tx, stage)
    assert res.status == ExecutionStatus.FAILED
    assert not (tmp_path / ".env").exists()

