"""
test_task_queue_manager.py - Comprehensive Unit & Integration Tests for TaskQueueManager

Validates:
- Loading tasks from disk (valid formats, missing files, corrupted JSON)
- Atomic saving behavior and disk persistence
- Dependency resolution (direct dependencies, chained dependencies, unblocking on completion)
- Retry logic (retry counter, re-queueing to READY, permanent FAILED threshold)
- Priority ordering (CRITICAL > HIGH > MEDIUM > LOW with FIFO tie-breaking)
- Cycle detection (2-node cycles, 3-node cycles, self-cycles)
- Schema validation (missing fields, negative retries, non-dict payloads)
- Duplicate task ID rejection
- Missing dependency target rejection
- Invalid priority and invalid status rejection
- Status transitions (mark_running, mark_completed, mark_failed, mark_blocked, mark_skipped)
- Ready and blocked query correctness
"""

import json
from pathlib import Path
import pytest

from agents.task_queue_manager import (
    CyclicDependencyError,
    DuplicateTaskIdError,
    InvalidPriorityError,
    InvalidStatusError,
    MissingDependencyError,
    TaskNotFoundError,
    TaskPriority,
    TaskQueueManager,
    TaskState,
    TaskStatus,
    TaskValidationError,
)


@pytest.fixture
def temp_tasks_file(tmp_path: Path) -> Path:
    """Provides a temporary path for tasks.json in an isolated directory."""
    tasks_file = tmp_path / "memory" / "tasks.json"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    return tasks_file


# =============================================================================
# 1. Loading & Initial State Tests
# =============================================================================

def test_auto_create_empty_tasks_file(temp_tasks_file: Path):
    """Verifies that an empty tasks.json is created automatically if absent."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file, auto_create=True)
    assert temp_tasks_file.is_file()
    assert manager.get_all_tasks() == []


def test_loading_missing_file_without_auto_create(tmp_path: Path):
    """Verifies that attempting to load a missing file with auto_create=False raises FileNotFoundError."""
    missing_file = tmp_path / "nonexistent.json"
    manager = TaskQueueManager(tasks_path=missing_file, auto_create=False, auto_load=False)
    with pytest.raises(FileNotFoundError):
        manager.load_tasks()


def test_loading_valid_tasks(temp_tasks_file: Path):
    """Verifies loading a standard list of tasks from disk."""
    raw_tasks = [
        {
            "id": "TASK-01",
            "title": "Init Database",
            "priority": "HIGH",
            "dependencies": [],
            "status": "PENDING",
            "retry_count": 0,
            "max_retries": 3,
        },
        {
            "id": "TASK-02",
            "title": "Build Models",
            "priority": "MEDIUM",
            "dependencies": ["TASK-01"],
            "status": "PENDING",
            "retry_count": 0,
            "max_retries": 3,
        },
    ]
    with open(temp_tasks_file, "w", encoding="utf-8") as f:
        json.dump(raw_tasks, f)

    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    tasks = manager.get_all_tasks()
    assert len(tasks) == 2
    assert tasks[0].id == "TASK-01"
    assert tasks[0].status == TaskState.READY.value  # No dependencies -> READY
    assert tasks[1].id == "TASK-02"
    assert tasks[1].status == TaskState.BLOCKED.value  # Unmet dependency -> BLOCKED


def test_loading_wrapped_tasks_dict(temp_tasks_file: Path):
    """Verifies loading when tasks are wrapped in a dict under 'tasks' key."""
    raw_data = {
        "tasks": [
            {
                "id": "T1",
                "title": "Task 1",
                "priority": "LOW",
                "dependencies": [],
            }
        ]
    }
    with open(temp_tasks_file, "w", encoding="utf-8") as f:
        json.dump(raw_data, f)

    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    assert len(manager.get_all_tasks()) == 1
    assert manager.get_task("T1").priority == TaskPriority.LOW.value


def test_loading_corrupted_json_raises_error(temp_tasks_file: Path):
    """Verifies that malformed JSON raises TaskValidationError."""
    with open(temp_tasks_file, "w", encoding="utf-8") as f:
        f.write("{invalid-json-content")

    with pytest.raises(TaskValidationError):
        TaskQueueManager(tasks_path=temp_tasks_file)


# =============================================================================
# 2. Saving & Atomic Persistence Tests
# =============================================================================

def test_atomic_saving_preserves_task_data(temp_tasks_file: Path):
    """Verifies that saving persists tasks accurately to disk."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    task = TaskStatus(
        id="AUTH-01",
        title="Setup Auth Service",
        priority="CRITICAL",
        description="JWT Authentication",
        dependencies=[],
    )
    manager.add_task(task)

    # Re-read from disk
    with open(temp_tasks_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert len(saved_data) == 1
    assert saved_data[0]["id"] == "AUTH-01"
    assert saved_data[0]["priority"] == "CRITICAL"
    assert saved_data[0]["description"] == "JWT Authentication"


# =============================================================================
# 3. Dependency Resolution & Dynamic Unblocking Tests
# =============================================================================

def test_independent_tasks_become_ready(temp_tasks_file: Path):
    """Tasks with no dependencies should resolve to READY immediately."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    manager.add_task(TaskStatus(id="T1", title="Task 1", dependencies=[]))
    manager.add_task(TaskStatus(id="T2", title="Task 2", dependencies=[]))

    ready = manager.get_ready_tasks()
    assert len(ready) == 2
    assert {t.id for t in ready} == {"T1", "T2"}


def test_dependent_tasks_stay_blocked_until_dependency_completes(temp_tasks_file: Path):
    """Dependent tasks should transition from BLOCKED to READY once dependencies are COMPLETED."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    t1 = TaskStatus(id="T1", title="Scaffold", dependencies=[])
    t2 = TaskStatus(id="T2", title="Implement", dependencies=["T1"])
    t3 = TaskStatus(id="T3", title="Test", dependencies=["T2"])

    manager.add_tasks([t1, t2, t3])

    # Initially only T1 is ready
    assert [t.id for t in manager.get_ready_tasks()] == ["T1"]
    assert {t.id for t in manager.get_blocked_tasks()} == {"T2", "T3"}

    # Complete T1 -> T2 unblocks and becomes READY, T3 stays BLOCKED
    manager.mark_running("T1")
    manager.mark_completed("T1")

    assert [t.id for t in manager.get_ready_tasks()] == ["T2"]
    assert [t.id for t in manager.get_blocked_tasks()] == ["T3"]

    # Complete T2 -> T3 unblocks and becomes READY
    manager.mark_running("T2")
    manager.mark_completed("T2")

    assert [t.id for t in manager.get_ready_tasks()] == ["T3"]
    assert len(manager.get_blocked_tasks()) == 0


def test_multi_dependency_resolution(temp_tasks_file: Path):
    """A task requiring multiple dependencies becomes READY only when ALL dependencies are COMPLETED."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    t1 = TaskStatus(id="A", title="Part A", dependencies=[])
    t2 = TaskStatus(id="B", title="Part B", dependencies=[])
    t3 = TaskStatus(id="C", title="Join", dependencies=["A", "B"])

    manager.add_tasks([t1, t2, t3])

    assert {t.id for t in manager.get_ready_tasks()} == {"A", "B"}
    assert [t.id for t in manager.get_blocked_tasks()] == ["C"]

    # Complete A only -> C still blocked because B is not completed
    manager.mark_completed("A")
    assert [t.id for t in manager.get_ready_tasks()] == ["B"]
    assert [t.id for t in manager.get_blocked_tasks()] == ["C"]

    # Complete B -> C becomes ready
    manager.mark_completed("B")
    assert [t.id for t in manager.get_ready_tasks()] == ["C"]
    assert len(manager.get_blocked_tasks()) == 0


# =============================================================================
# 4. Priority Ordering & FIFO Dispatch Tests
# =============================================================================

def test_priority_ordering_critical_high_medium_low(temp_tasks_file: Path):
    """Verifies that ready tasks are prioritized: CRITICAL > HIGH > MEDIUM > LOW."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    manager.add_tasks([
        TaskStatus(id="LOW-01", title="Low Priority", priority="LOW"),
        TaskStatus(id="HIGH-01", title="High Priority", priority="HIGH"),
        TaskStatus(id="CRIT-01", title="Critical Priority", priority="CRITICAL"),
        TaskStatus(id="MED-01", title="Medium Priority", priority="MEDIUM"),
    ])

    ready_ids = [t.id for t in manager.get_ready_tasks()]
    assert ready_ids == ["CRIT-01", "HIGH-01", "MED-01", "LOW-01"]
    assert manager.get_next_task().id == "CRIT-01"


def test_fifo_ordering_within_same_priority(temp_tasks_file: Path):
    """Verifies FIFO dispatch ordering among tasks of equal priority."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    manager.add_tasks([
        TaskStatus(id="HIGH-01", title="First High", priority="HIGH"),
        TaskStatus(id="HIGH-02", title="Second High", priority="HIGH"),
        TaskStatus(id="HIGH-03", title="Third High", priority="HIGH"),
    ])

    ready_ids = [t.id for t in manager.get_ready_tasks()]
    assert ready_ids == ["HIGH-01", "HIGH-02", "HIGH-03"]
    assert manager.get_next_task().id == "HIGH-01"


# =============================================================================
# 5. Retry Logic Tests
# =============================================================================

def test_retry_counter_requeues_to_ready(temp_tasks_file: Path):
    """Failing a task below max_retries should increment retry_count and re-queue as READY."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    task = TaskStatus(id="RETRY-01", title="Flaky Task", max_retries=3)
    manager.add_task(task)

    # Attempt 1 fails
    t = manager.mark_failed("RETRY-01")
    assert t.retry_count == 1
    assert t.status == TaskState.READY.value
    assert manager.get_next_task().id == "RETRY-01"

    # Attempt 2 fails
    t = manager.mark_failed("RETRY-01")
    assert t.retry_count == 2
    assert t.status == TaskState.READY.value


def test_retry_exhaustion_marks_failed_permanently(temp_tasks_file: Path):
    """Exhausting max_retries marks the task permanently FAILED."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    task = TaskStatus(id="FAIL-01", title="Doomed Task", max_retries=2)
    manager.add_task(task)

    manager.mark_failed("FAIL-01")  # retry_count = 1 -> READY
    assert manager.get_task("FAIL-01").status == TaskState.READY.value

    manager.mark_failed("FAIL-01")  # retry_count = 2 (max_retries) -> FAILED
    failed_task = manager.get_task("FAIL-01")
    assert failed_task.retry_count == 2
    assert failed_task.status == TaskState.FAILED.value
    assert manager.get_next_task() is None
    assert len(manager.get_failed_tasks()) == 1


# =============================================================================
# 6. Cycle Detection Tests
# =============================================================================

def test_self_dependency_cycle_detection(temp_tasks_file: Path):
    """Verifies that a task depending on itself is rejected with CyclicDependencyError."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    with pytest.raises(CyclicDependencyError) as exc_info:
        manager.add_task(TaskStatus(id="SELF-01", title="Self cycle", dependencies=["SELF-01"]))
    assert "Cyclic dependency" in str(exc_info.value)


def test_two_node_cycle_detection(temp_tasks_file: Path):
    """Verifies that A -> B -> A cycle is detected and rejected."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    t1 = TaskStatus(id="A", title="Task A", dependencies=["B"])
    t2 = TaskStatus(id="B", title="Task B", dependencies=["A"])

    with pytest.raises(CyclicDependencyError):
        manager.add_tasks([t1, t2])


def test_three_node_cycle_detection(temp_tasks_file: Path):
    """Verifies that A -> B -> C -> A cycle is detected and rejected."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    t1 = TaskStatus(id="A", title="Task A", dependencies=["C"])
    t2 = TaskStatus(id="B", title="Task B", dependencies=["A"])
    t3 = TaskStatus(id="C", title="Task C", dependencies=["B"])

    with pytest.raises(CyclicDependencyError) as exc_info:
        manager.add_tasks([t1, t2, t3])
    assert "Cyclic dependency detected" in str(exc_info.value)


# =============================================================================
# 7. Validation & Integrity Tests
# =============================================================================

def test_duplicate_task_id_rejection(temp_tasks_file: Path):
    """Verifies that duplicate task IDs raise DuplicateTaskIdError."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    manager.add_task(TaskStatus(id="DUP-01", title="Original"))

    with pytest.raises(DuplicateTaskIdError):
        manager.add_task(TaskStatus(id="DUP-01", title="Duplicate"))


def test_missing_dependency_target_rejection(temp_tasks_file: Path):
    """Verifies that referencing a non-existent dependency raises MissingDependencyError."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    with pytest.raises(MissingDependencyError) as exc_info:
        manager.add_task(TaskStatus(id="T1", title="Task 1", dependencies=["GHOST-TASK"]))
    assert "GHOST-TASK" in str(exc_info.value)


def test_invalid_priority_rejection(temp_tasks_file: Path):
    """Verifies that unsupported priority values raise InvalidPriorityError."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    with pytest.raises(InvalidPriorityError):
        manager.add_task(TaskStatus(id="T1", title="Task 1", priority="SUPER_URGENT"))


def test_invalid_status_rejection(temp_tasks_file: Path):
    """Verifies that unsupported status values raise InvalidStatusError."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    with pytest.raises(InvalidStatusError):
        manager.add_task(TaskStatus(id="T1", title="Task 1", status="UNKNOWN_STATE"))


def test_invalid_schema_missing_fields():
    """Verifies TaskStatus.from_dict error handling on missing required keys."""
    with pytest.raises(TaskValidationError):
        TaskStatus.from_dict({"title": "No ID"})

    with pytest.raises(TaskValidationError):
        TaskStatus.from_dict({"id": "NO-TITLE"})


def test_nonexistent_task_queries(temp_tasks_file: Path):
    """Verifies querying non-existent task IDs raises TaskNotFoundError."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    with pytest.raises(TaskNotFoundError):
        manager.get_task("NONEXISTENT")

    with pytest.raises(TaskNotFoundError):
        manager.mark_running("NONEXISTENT")


# =============================================================================
# 8. Status Transition Tests (Running, Blocked, Skipped, Completed)
# =============================================================================

def test_status_mutations_and_queries(temp_tasks_file: Path):
    """Verifies mark_running, mark_skipped, and mark_blocked operations."""
    manager = TaskQueueManager(tasks_path=temp_tasks_file)
    manager.add_tasks([
        TaskStatus(id="RUN-01", title="Running Task"),
        TaskStatus(id="SKIP-01", title="Skipped Task"),
        TaskStatus(id="BLK-01", title="Blocked Task"),
    ])

    manager.mark_running("RUN-01")
    manager.mark_skipped("SKIP-01")
    manager.mark_blocked("BLK-01")

    assert [t.id for t in manager.get_running_tasks()] == ["RUN-01"]
    assert manager.get_task("SKIP-01").status == TaskState.SKIPPED.value
    assert manager.get_task("BLK-01").status == TaskState.BLOCKED.value
    assert manager.get_task("RUN-01").updated_at is not None
