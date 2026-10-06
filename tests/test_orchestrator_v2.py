"""
test_orchestrator_v2.py - Comprehensive Unit & Integration Tests for Orchestrator Version 2

Validates:
- Successful end-to-end autonomous development cycle
- CoderAgent failure handling
- FileWriterAgent failure handling
- Non-blocking test failure continuation into ReviewerAgent
- ReviewerAgent failure handling
- No pending tasks graceful completion
- Missing or invalid project plan handling
- Structured logging verification across pipeline stages
"""

import json
import logging
from pathlib import Path
import pytest
from agents.coder_agent import CoderAgent, GeneratedFile, GeneratedResult
from agents.file_writer_agent import FileWriterAgent, WriteResult
from agents.reviewer_agent import Issue, ReviewerAgent, ReviewResult, ReviewValidationError
from agents.task_planner_agent import Task, TaskPlannerAgent
from agents.tester_agent import TesterAgent, TestResult
from core.context_builder import ContextBuilder
from core.orchestrator import ExecutionResult, Orchestrator


@pytest.fixture
def temp_environment(tmp_path: Path):
    """Sets up an isolated workspace, memory store, and sample project plan."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    plan_path = memory_dir / "project_plan.json"
    state_path = memory_dir / "state.json"
    tasks_path = memory_dir / "tasks.json"

    plan_data = {
        "project_name": "Test Orchestrator App",
        "project_description": "Integration test app",
        "technology_stack": "Python, Pytest",
        "total_days": 1,
        "phases": [
            {
                "day": 1,
                "phase_name": "Core Module Setup",
                "goals": ["Create baseline scaffold"],
                "tasks": ["Implement core entry point"],
                "deliverables": ["src/app.py"],
                "testing_focus": "Unit testing",
                "git_commit_message": "feat: initial scaffold",
            }
        ],
    }
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2)

    state_data = {"current_day": 1, "completed_phases": [], "status": "initialized"}
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state_data, f, indent=2)

    return {
        "workspace": workspace,
        "plan_path": plan_path,
        "state_path": state_path,
        "tasks_path": tasks_path,
        "logs_dir": logs_dir,
    }


def test_successful_orchestrator_workflow(temp_environment):
    """Verifies that the entire 10-stage autonomous cycle executes successfully."""
    orch = Orchestrator(
        project_root=temp_environment["workspace"],
        plan_path=temp_environment["plan_path"],
        state_path=temp_environment["state_path"],
        tasks_path=temp_environment["tasks_path"],
        log_dir=temp_environment["logs_dir"],
    )

    result = orch.run()

    assert isinstance(result, ExecutionResult)
    assert result.overall_success is True
    assert result.current_task is not None
    assert result.current_task.id.startswith("DAY1-TASK")
    assert len(result.generated_files) > 0
    assert len(result.written_files) > 0
    assert result.test_result is not None
    assert result.review_result is not None
    assert result.review_result.overall_quality_score >= 0
    assert result.duration >= 0


def test_coder_agent_failure_handling(temp_environment):
    """Verifies that a CoderAgent crash halts the pipeline and records failure."""
    class FailingCoderAgent(CoderAgent):
        def execute(self, context, task):
            raise RuntimeError("Simulated LLM network timeout")

    orch = Orchestrator(
        project_root=temp_environment["workspace"],
        plan_path=temp_environment["plan_path"],
        state_path=temp_environment["state_path"],
        tasks_path=temp_environment["tasks_path"],
        log_dir=temp_environment["logs_dir"],
        coder_agent=FailingCoderAgent(),
    )

    result = orch.run()

    assert result.overall_success is False
    assert "Simulated LLM network timeout" in result.error
    assert result.test_result is None
    assert result.review_result is None


def test_file_writer_failure_handling(temp_environment):
    """Verifies that a FileWriterAgent failure stops execution safely."""
    class FailingFileWriter(FileWriterAgent):
        def write(self, result, target_dir=None, overwrite=None, backup=None):
            return WriteResult(
                files_written=[],
                files_skipped=[],
                backups_created=[],
                failed_files={"src/main.py": "Disk permission denied"},
                success=False,
                message="Write failure",
            )

    orch = Orchestrator(
        project_root=temp_environment["workspace"],
        plan_path=temp_environment["plan_path"],
        state_path=temp_environment["state_path"],
        tasks_path=temp_environment["tasks_path"],
        log_dir=temp_environment["logs_dir"],
        file_writer=FailingFileWriter(project_root=temp_environment["workspace"]),
    )

    result = orch.run()

    assert result.overall_success is False
    assert "FileWriterAgent encountered failures" in result.error
    assert result.test_result is None


def test_non_blocking_test_failures_continue_to_review(temp_environment):
    """Verifies that failing tests do NOT halt the pipeline and are forwarded to ReviewerAgent."""
    class FailingTesterAgent(TesterAgent):
        def run_tests(self, project_root, command=None, timeout_seconds=None):
            return TestResult(
                success=False,
                total_tests=3,
                passed=1,
                failed=2,
                skipped=0,
                duration=0.25,
                stdout="2 failed, 1 passed",
                stderr="AssertionError: 1 == 2",
                exit_code=1,
                command="pytest",
                message="Test suite failed with 2 failures.",
            )

    orch = Orchestrator(
        project_root=temp_environment["workspace"],
        plan_path=temp_environment["plan_path"],
        state_path=temp_environment["state_path"],
        tasks_path=temp_environment["tasks_path"],
        log_dir=temp_environment["logs_dir"],
        tester_agent=FailingTesterAgent(),
    )

    result = orch.run()

    # The pipeline should complete and execute ReviewerAgent
    assert result.test_result is not None
    assert result.test_result.success is False
    assert result.test_result.failed == 2
    assert result.review_result is not None
    assert result.review_result.overall_quality_score >= 0


def test_reviewer_failure_handling(temp_environment):
    """Verifies that a ReviewerAgent exception halts and returns failure status."""
    class FailingReviewerAgent(ReviewerAgent):
        def review(self, context, generated_result, test_result=None):
            raise ReviewValidationError("Review schema validation failed")

    orch = Orchestrator(
        project_root=temp_environment["workspace"],
        plan_path=temp_environment["plan_path"],
        state_path=temp_environment["state_path"],
        tasks_path=temp_environment["tasks_path"],
        log_dir=temp_environment["logs_dir"],
        reviewer_agent=FailingReviewerAgent(),
    )

    result = orch.run()

    assert result.overall_success is False
    assert "Review schema validation failed" in result.error
    assert result.test_result is not None  # Tester ran before Reviewer failed


def test_no_pending_tasks_graceful_exit(temp_environment):
    """Verifies behavior when all tasks are already completed or none are pending."""
    class EmptyTaskPlanner(TaskPlannerAgent):
        def execute(self, context):
            return [
                Task(
                    id="DAY1-TASK01",
                    title="Done task",
                    description="Already finished",
                    status="completed",
                )
            ]

    orch = Orchestrator(
        project_root=temp_environment["workspace"],
        plan_path=temp_environment["plan_path"],
        state_path=temp_environment["state_path"],
        tasks_path=temp_environment["tasks_path"],
        log_dir=temp_environment["logs_dir"],
        task_planner=EmptyTaskPlanner(),
    )

    result = orch.run()

    assert result.overall_success is True
    assert result.current_task is None
    assert "No pending tasks found" in result.message


def test_missing_project_plan_error(tmp_path: Path):
    """Verifies that missing project_plan.json halts early with an informative error."""
    orch = Orchestrator(
        project_root=tmp_path / "empty_workspace",
        plan_path=tmp_path / "nonexistent_plan.json",
        state_path=tmp_path / "state.json",
        tasks_path=tmp_path / "tasks.json",
        log_dir=tmp_path / "logs",
    )

    result = orch.run()

    assert result.overall_success is False
    assert "Project plan missing" in result.error or "not found" in result.error


def test_logging_verification(temp_environment, caplog):
    """Verifies that all pipeline stages produce structured log records."""
    caplog.set_level(logging.INFO, logger="AutoDev.Orchestrator")

    orch = Orchestrator(
        project_root=temp_environment["workspace"],
        plan_path=temp_environment["plan_path"],
        state_path=temp_environment["state_path"],
        tasks_path=temp_environment["tasks_path"],
        log_dir=temp_environment["logs_dir"],
    )

    orch.run()

    log_text = caplog.text
    assert "Starting AutoDev Orchestrator" in log_text
    assert "Loading project state" in log_text
    assert "Verifying project plan" in log_text
    assert "Building project context" in log_text
    assert "Generating today's atomic tasks" in log_text
    assert "Selecting highest-priority pending task" in log_text
    assert "Executing CoderAgent" in log_text
    assert "Writing" in log_text
    assert "Executing" in log_text and "test" in log_text
    assert "Performing AI code review" in log_text
    assert "Workflow Completed" in log_text
