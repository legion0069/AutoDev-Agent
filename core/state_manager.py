"""
state_manager.py - Persistent State Management for AutoDev

Responsible for maintaining, validating, and atomically persisting AutoDev's
execution lifecycle state, including active day progress, completed tasks,
completed phases, and audit execution history.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure project root is available on sys.path for direct execution
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Module logger
logger = logging.getLogger("AutoDev.StateManager")


class StateValidationError(ValueError):
    """
    Raised when an execution state structure fails validation rules.
    """
    pass


@dataclass
class ExecutionRecord:
    """
    Audit log entry capturing the telemetry of a single task execution.
    """
    timestamp: str
    task_id: str
    success: bool
    quality_score: Optional[int] = None
    test_summary: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converts execution record to serializable dictionary representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionRecord:
        """Constructs an ExecutionRecord from a dictionary."""
        return cls(
            timestamp=data.get("timestamp", datetime.now().isoformat(timespec="seconds")),
            task_id=data.get("task_id", "UNKNOWN"),
            success=bool(data.get("success", False)),
            quality_score=data.get("quality_score"),
            test_summary=data.get("test_summary"),
            details=data.get("details", {}),
        )


@dataclass
class ProjectState:
    """
    Complete state payload representing the lifecycle of an AutoDev project.
    """
    current_day: int = 1
    completed_tasks: List[str] = field(default_factory=list)
    completed_phases: List[int] = field(default_factory=list)
    execution_history: List[ExecutionRecord] = field(default_factory=list)
    last_execution_time: Optional[str] = None
    status: str = "initialized"

    def to_dict(self) -> Dict[str, Any]:
        """Converts state instance into a clean serializable dictionary."""
        return {
            "current_day": self.current_day,
            "completed_tasks": self.completed_tasks,
            "completed_phases": self.completed_phases,
            "execution_history": [r.to_dict() for r in self.execution_history],
            "last_execution_time": self.last_execution_time,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectState:
        """Constructs a ProjectState from a dictionary with schema compatibility."""
        raw_history = data.get("execution_history", [])
        history_records: List[ExecutionRecord] = []
        for item in raw_history:
            if isinstance(item, dict):
                history_records.append(ExecutionRecord.from_dict(item))
            elif isinstance(item, ExecutionRecord):
                history_records.append(item)

        raw_phases = data.get("completed_phases", [])
        completed_phases: List[int] = []
        for p in raw_phases:
            if isinstance(p, int):
                completed_phases.append(p)
            elif str(p).isdigit():
                completed_phases.append(int(p))

        raw_tasks = [str(t) for t in data.get("completed_tasks", [])]

        raw_day = data.get("current_day", 1)
        current_day = int(raw_day) if str(raw_day).isdigit() else 1

        return cls(
            current_day=current_day,
            completed_tasks=raw_tasks,
            completed_phases=completed_phases,
            execution_history=history_records,
            last_execution_time=data.get("last_execution_time"),
            status=str(data.get("status", "initialized")),
        )


class StateManager:
    """
    Manages persistent state operations, atomic filesystem writes,
    phase/day advancements, and historical execution logging for AutoDev.
    """

    def __init__(
        self,
        state_path: Union[str, Path] = "memory/state.json",
        auto_create: bool = True,
    ) -> None:
        """
        Initializes the StateManager.

        Args:
            state_path: Path to memory/state.json.
            auto_create: If True, automatically initializes default state on missing file.
        """
        self.state_path = Path(state_path).resolve()
        self.auto_create = auto_create
        self.state: ProjectState = self.load_state()

    def validate_state(self, state: ProjectState) -> None:
        """
        Validates the ProjectState structure against business integrity rules.

        Args:
            state: The ProjectState instance to validate.

        Raises:
            StateValidationError: If invalid types, out-of-bound numbers, or corrupted data exist.
        """
        if not isinstance(state.current_day, int) or state.current_day < 0:
            raise StateValidationError(
                f"Field 'current_day' must be a non-negative integer, got {state.current_day}."
            )

        if not isinstance(state.completed_tasks, list):
            raise StateValidationError("Field 'completed_tasks' must be a list of strings.")

        if not isinstance(state.completed_phases, list):
            raise StateValidationError("Field 'completed_phases' must be a list of integers.")

        if not isinstance(state.execution_history, list):
            raise StateValidationError("Field 'execution_history' must be a list of ExecutionRecord objects.")

        if not isinstance(state.status, str) or not state.status.strip():
            raise StateValidationError("Field 'status' must be a non-empty string.")

        for idx, rec in enumerate(state.execution_history):
            if not isinstance(rec, ExecutionRecord):
                raise StateValidationError(
                    f"Item at execution_history[{idx}] must be an ExecutionRecord, got {type(rec).__name__}."
                )
            if rec.quality_score is not None:
                if isinstance(rec.quality_score, bool) or not isinstance(rec.quality_score, int):
                    raise StateValidationError(
                        f"ExecutionRecord quality_score must be int or None, got {type(rec.quality_score).__name__}."
                    )
                if not (0 <= rec.quality_score <= 100):
                    raise StateValidationError(
                        f"ExecutionRecord quality_score must be between 0 and 100, got {rec.quality_score}."
                    )

    def load_state(self) -> ProjectState:
        """
        Safely loads state from disk. Handles missing files and recovers from JSON corruption.

        Returns:
            Loaded or recovered ProjectState instance.
        """
        if not self.state_path.is_file():
            if self.auto_create:
                logger.info("State file not found at '%s'. Creating default state.", self.state_path)
                default_state = ProjectState(
                    current_day=1,
                    completed_tasks=[],
                    completed_phases=[],
                    execution_history=[],
                    last_execution_time=None,
                    status="initialized",
                )
                self.state = default_state
                self.save_state(default_state)
                return default_state
            else:
                raise FileNotFoundError(f"State file '{self.state_path}' does not exist.")

        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded = ProjectState.from_dict(data)
            self.validate_state(loaded)
            self.state = loaded
            logger.info("State loaded successfully from '%s' (Day: %d, Status: %s).", self.state_path, loaded.current_day, loaded.status)
            return loaded

        except json.JSONDecodeError as err:
            logger.error("Corrupted JSON detected in state file '%s': %s", self.state_path, err)
            # Create timestamped corrupted backup
            corrupted_backup = self.state_path.with_name(
                f"{self.state_path.stem}.corrupted.{int(datetime.now().timestamp())}.json"
            )
            try:
                shutil.copy2(self.state_path, corrupted_backup)
                logger.warning("Created backup of corrupted state at '%s'.", corrupted_backup)
            except OSError:
                pass

            recovered_state = ProjectState(
                current_day=1,
                completed_tasks=[],
                completed_phases=[],
                execution_history=[],
                last_execution_time=None,
                status="recovered_from_corruption",
            )
            self.state = recovered_state
            self.save_state(recovered_state)
            return recovered_state

    def save_state(self, state: Optional[ProjectState] = None) -> Path:
        """
        Atomically saves state to disk using a temporary file and atomic rename.

        Args:
            state: Optional ProjectState override (defaults to self.state).

        Returns:
            Path of saved state file.

        Raises:
            StateValidationError: If state fails validation rules.
            OSError: If disk write fails.
        """
        target_state = state or self.state
        self.validate_state(target_state)

        # Ensure parent directory exists
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = self.state_path.with_name(f"{self.state_path.name}.{os.getpid()}.{time.time_ns()}.tmp")
        payload = target_state.to_dict()

        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replace with transient lock retry (Windows resiliency)
            last_err = None
            for attempt in range(5):
                try:
                    os.replace(temp_path, self.state_path)
                    break
                except PermissionError as err:
                    last_err = err
                    time.sleep(0.01 * (attempt + 1))
            else:
                if last_err:
                    raise last_err

            self.state = target_state
            logger.info("Atomically saved state to '%s'.", self.state_path)
            return self.state_path

        except Exception as exc:
            logger.error("Failed to atomically save state to '%s': %s", self.state_path, exc)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise

    def record_task_execution(
        self,
        task_id: str,
        success: bool,
        quality_score: Optional[int] = None,
        test_summary: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        auto_save: bool = True,
    ) -> ExecutionRecord:
        """
        Appends an execution record to history and updates last_execution_time.

        Args:
            task_id: Identifier of the executed task.
            success: Whether the task execution succeeded.
            quality_score: Optional review quality score (0-100).
            test_summary: Optional test outcome summary.
            details: Optional dictionary of additional execution metrics.
            auto_save: Whether to immediately persist state to disk.

        Returns:
            The created ExecutionRecord instance.
        """
        timestamp = datetime.now().isoformat(timespec="seconds")
        record = ExecutionRecord(
            timestamp=timestamp,
            task_id=task_id,
            success=success,
            quality_score=quality_score,
            test_summary=test_summary,
            details=details or {},
        )

        self.state.execution_history.append(record)
        self.state.last_execution_time = timestamp
        self.state.status = "in_progress"

        if success and task_id not in self.state.completed_tasks:
            self.state.completed_tasks.append(task_id)

        logger.info("Recorded task execution: Task [%s], Success: %s, Score: %s.", task_id, success, quality_score)

        if auto_save:
            self.save_state()

        return record

    def mark_task_completed(self, task_id: str, auto_save: bool = True) -> None:
        """
        Marks an individual task as completed.

        Args:
            task_id: Identifier of the completed task.
            auto_save: Whether to persist state immediately.
        """
        if task_id not in self.state.completed_tasks:
            self.state.completed_tasks.append(task_id)
            logger.info("Marked task [%s] as completed.", task_id)
            if auto_save:
                self.save_state()

    def mark_phase_completed(self, day: int, auto_save: bool = True) -> None:
        """
        Marks an entire development phase/day as completed.

        Args:
            day: Day number index of the completed phase.
            auto_save: Whether to persist state immediately.
        """
        if day not in self.state.completed_phases:
            self.state.completed_phases.append(day)
            self.state.completed_phases.sort()
            logger.info("Marked Day %d phase as completed.", day)
            if auto_save:
                self.save_state()

    def advance_day(self, next_day: Optional[int] = None, auto_save: bool = True) -> int:
        """
        Advances the project's current_day pointer.

        Args:
            next_day: Optional explicit day target. If None, increments current_day by 1.
            auto_save: Whether to persist state immediately.

        Returns:
            The new current_day value.
        """
        if next_day is not None:
            if next_day < self.state.current_day:
                raise StateValidationError(
                    f"Cannot advance day backwards from {self.state.current_day} to {next_day}."
                )
            self.state.current_day = next_day
        else:
            self.state.current_day += 1

        self.state.status = "in_progress"
        logger.info("Advanced active development day to Day %d.", self.state.current_day)

        if auto_save:
            self.save_state()

        return self.state.current_day

    def get_state(self) -> ProjectState:
        """Returns the active ProjectState instance."""
        return self.state

    def reset_state(self, initial_day: int = 1, auto_save: bool = True) -> ProjectState:
        """
        Resets the state to initial values while clearing history.

        Args:
            initial_day: Starting day index.
            auto_save: Whether to save immediately.

        Returns:
            Cleaned ProjectState instance.
        """
        self.state = ProjectState(
            current_day=initial_day,
            completed_tasks=[],
            completed_phases=[],
            execution_history=[],
            last_execution_time=None,
            status="initialized",
        )
        if auto_save:
            self.save_state()
        return self.state


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-5s] %(message)s")

    manager = StateManager(state_path="memory/state.json")
    print("\nInitial State:")
    print(manager.get_state())

    manager.record_task_execution(
        task_id="DAY1-TASK01",
        success=True,
        quality_score=92,
        test_summary="2 passed",
    )

    print("\nState after Task Execution:")
    print(manager.get_state())
