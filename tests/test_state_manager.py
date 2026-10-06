"""
test_state_manager.py - Comprehensive Unit & Integration Tests for StateManager

Validates:
- Default state creation on missing state.json
- Loading existing state files
- Marking tasks as completed
- Advancing phases and days
- Preserving audit execution history across reloads
- Invalid state validation (negative days, malformed types, out of bound scores)
- Corrupted JSON recovery with automatic backup creation
- Atomic write and persistence integrity
"""

import json
from pathlib import Path
import pytest
from core.state_manager import (
    ExecutionRecord,
    ProjectState,
    StateManager,
    StateValidationError,
)


@pytest.fixture
def temp_state_file(tmp_path: Path) -> Path:
    """Provides a path to an isolated temporary state file."""
    return tmp_path / "memory" / "state.json"


def test_default_state_creation(temp_state_file: Path):
    """Verifies that default state is created and persisted if state.json does not exist."""
    assert not temp_state_file.exists()

    manager = StateManager(state_path=temp_state_file, auto_create=True)
    state = manager.get_state()

    assert temp_state_file.is_file()
    assert state.current_day == 1
    assert state.completed_tasks == []
    assert state.completed_phases == []
    assert state.execution_history == []
    assert state.status == "initialized"


def test_loading_existing_state(temp_state_file: Path):
    """Verifies that an existing state file is accurately parsed and loaded."""
    temp_state_file.parent.mkdir(parents=True, exist_ok=True)
    existing_payload = {
        "current_day": 2,
        "completed_tasks": ["DAY1-TASK01", "DAY1-TASK02"],
        "completed_phases": [1],
        "execution_history": [
            {
                "timestamp": "2026-10-06T12:00:00",
                "task_id": "DAY1-TASK01",
                "success": True,
                "quality_score": 90,
                "test_summary": "1 passed",
                "details": {},
            }
        ],
        "last_execution_time": "2026-10-06T12:00:00",
        "status": "in_progress",
    }
    with open(temp_state_file, "w", encoding="utf-8") as f:
        json.dump(existing_payload, f)

    manager = StateManager(state_path=temp_state_file)
    state = manager.get_state()

    assert state.current_day == 2
    assert state.completed_tasks == ["DAY1-TASK01", "DAY1-TASK02"]
    assert state.completed_phases == [1]
    assert len(state.execution_history) == 1
    assert state.execution_history[0].task_id == "DAY1-TASK01"
    assert state.status == "in_progress"


def test_mark_task_completed(temp_state_file: Path):
    """Verifies marking individual tasks complete and persisting them."""
    manager = StateManager(state_path=temp_state_file)

    manager.mark_task_completed("DAY1-TASK01")
    manager.mark_task_completed("DAY1-TASK02")
    # Duplicate add should not create duplicates
    manager.mark_task_completed("DAY1-TASK01")

    # Reload from disk to verify persistence
    reloaded_manager = StateManager(state_path=temp_state_file)
    assert reloaded_manager.get_state().completed_tasks == ["DAY1-TASK01", "DAY1-TASK02"]


def test_mark_phase_completed(temp_state_file: Path):
    """Verifies marking phase/day complete and maintaining sorted completed_phases."""
    manager = StateManager(state_path=temp_state_file)

    manager.mark_phase_completed(2)
    manager.mark_phase_completed(1)

    reloaded = StateManager(state_path=temp_state_file).get_state()
    assert reloaded.completed_phases == [1, 2]


def test_advance_day(temp_state_file: Path):
    """Verifies advancing current_day incrementally and explicitly."""
    manager = StateManager(state_path=temp_state_file)
    assert manager.get_state().current_day == 1

    new_day = manager.advance_day()
    assert new_day == 2
    assert manager.get_state().current_day == 2

    explicit_day = manager.advance_day(next_day=5)
    assert explicit_day == 5
    assert manager.get_state().current_day == 5

    # Rejecting backwards advancement
    with pytest.raises(StateValidationError, match="Cannot advance day backwards"):
        manager.advance_day(next_day=3)


def test_preserving_execution_history(temp_state_file: Path):
    """Verifies that execution history accumulates and persists across multiple runs."""
    manager = StateManager(state_path=temp_state_file)

    manager.record_task_execution(
        task_id="TASK-01",
        success=True,
        quality_score=94,
        test_summary="3 passed",
    )
    manager.record_task_execution(
        task_id="TASK-02",
        success=False,
        quality_score=60,
        test_summary="1 failed",
    )

    # Reload from disk
    reloaded = StateManager(state_path=temp_state_file).get_state()

    assert len(reloaded.execution_history) == 2
    assert reloaded.execution_history[0].task_id == "TASK-01"
    assert reloaded.execution_history[0].success is True
    assert reloaded.execution_history[0].quality_score == 94
    assert reloaded.execution_history[1].task_id == "TASK-02"
    assert reloaded.execution_history[1].success is False
    assert "TASK-01" in reloaded.completed_tasks
    assert "TASK-02" not in reloaded.completed_tasks  # Failed task not marked complete


def test_invalid_state_handling(temp_state_file: Path):
    """Verifies that invalid state structures trigger StateValidationError."""
    manager = StateManager(state_path=temp_state_file)

    # Case 1: Negative day
    invalid_state_1 = ProjectState(current_day=-1)
    with pytest.raises(StateValidationError, match="current_day"):
        manager.save_state(invalid_state_1)

    # Case 2: Out-of-bounds quality score in execution history
    invalid_state_2 = ProjectState(
        current_day=1,
        execution_history=[
            ExecutionRecord(
                timestamp="2026-10-06T12:00:00",
                task_id="T1",
                success=True,
                quality_score=150,  # Invalid > 100
            )
        ],
    )
    with pytest.raises(StateValidationError, match="quality_score must be between 0 and 100"):
        manager.save_state(invalid_state_2)


def test_corrupted_json_recovery(temp_state_file: Path):
    """Verifies that corrupted JSON is backed up and recovered with a clean state."""
    temp_state_file.parent.mkdir(parents=True, exist_ok=True)
    temp_state_file.write_text("{Corrupted invalid json!$@#", encoding="utf-8")

    manager = StateManager(state_path=temp_state_file)
    recovered = manager.get_state()

    assert recovered.status == "recovered_from_corruption"
    assert recovered.current_day == 1

    # Verify backup was created
    backups = list(temp_state_file.parent.glob("state.corrupted.*.json"))
    assert len(backups) >= 1
    assert "{Corrupted invalid json!$@#" in backups[0].read_text(encoding="utf-8")


def test_atomic_save_behavior(temp_state_file: Path):
    """Verifies that save_state writes atomically and leaves no stray temporary files."""
    manager = StateManager(state_path=temp_state_file)
    manager.record_task_execution(task_id="ATOMIC-01", success=True, quality_score=98)

    assert temp_state_file.is_file()
    tmp_files = list(temp_state_file.parent.glob("*.tmp"))
    assert len(tmp_files) == 0

    with open(temp_state_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["completed_tasks"] == ["ATOMIC-01"]
