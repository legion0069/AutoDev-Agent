"""
test_retry_engine.py - Comprehensive Unit & Integration Tests for RetryEngine

Validates:
- Success on first attempt
- Multi-attempt self-healing convergence (success on 2nd attempt)
- Reaching maximum retry attempts without meeting threshold
- Reviewer-triggered retry (score < threshold or should_regenerate=True)
- Tester-triggered retry (failing automated tests)
- Infrastructure failure handling
- Accurate execution history telemetry tracking
"""

from pathlib import Path
from typing import List
import pytest
from agents.coder_agent import CoderAgent, GeneratedFile, GeneratedResult
from agents.file_writer_agent import FileWriterAgent, WriteResult
from agents.reviewer_agent import Issue, ReviewerAgent, ReviewResult
from agents.task_planner_agent import Task
from agents.tester_agent import TesterAgent, TestResult
from core.retry_engine import AttemptRecord, RetryEngine, RetryResult


@pytest.fixture
def sample_context():
    return {
        "project_name": "SelfHealingApp",
        "description": "App for retry engine testing",
        "technology_stack": "Python, Pytest",
        "current_day": 1,
        "current_phase": {
            "day": 1,
            "phase_name": "Core Phase",
            "goals": ["Build resilient engine"],
            "deliverables": ["src/core.py"],
            "testing_focus": "Unit testing",
        },
        "directory_tree": [],
        "project_files": {},
    }


@pytest.fixture
def sample_task():
    return Task(
        id="TASK-RETRY-01",
        title="Implement self-healing feature",
        description="Write core logic with self-healing capabilities.",
        priority=1,
    )


def test_success_on_first_attempt(tmp_path: Path, sample_context, sample_task):
    """Verifies that when all quality checks pass on Attempt 1, execution stops immediately."""
    engine = RetryEngine(project_root=tmp_path, default_max_attempts=3, default_minimum_quality_score=85)
    result = engine.execute(context=sample_context, task=sample_task)

    assert isinstance(result, RetryResult)
    assert result.success is True
    assert result.attempts == 1
    assert result.max_attempts == 3
    assert len(result.execution_history) == 1
    assert result.execution_history[0].quality_score >= 85


def test_success_after_second_attempt(tmp_path: Path, sample_context, sample_task):
    """Verifies that low score on Attempt 1 triggers feedback injection and succeeds on Attempt 2."""
    review_calls = 0

    class MultiAttemptReviewer(ReviewerAgent):
        def review(self, context, generated_result, test_result=None):
            nonlocal review_calls
            review_calls += 1
            if review_calls == 1:
                # Attempt 1: Low quality score
                return ReviewResult(
                    success=True,
                    summary="Initial draft has style and typing issues",
                    overall_quality_score=70,  # Below 85 threshold
                    issues=[Issue(severity="MEDIUM", category="TypeCheck", file="src/core.py", line=1, description="Missing types", recommendation="Add types")],
                    should_regenerate=False,
                    explanation="Needs improvement",
                )
            else:
                # Attempt 2: High quality score
                return ReviewResult(
                    success=True,
                    summary="All issues resolved",
                    overall_quality_score=95,
                    issues=[],
                    should_regenerate=False,
                    explanation="Production ready",
                )

    engine = RetryEngine(
        project_root=tmp_path,
        reviewer_agent=MultiAttemptReviewer(),
        default_max_attempts=3,
        default_minimum_quality_score=85,
    )

    result = engine.execute(context=sample_context, task=sample_task)

    assert result.success is True
    assert result.attempts == 2
    assert len(result.execution_history) == 2
    assert result.execution_history[0].quality_score == 70
    assert result.execution_history[1].quality_score == 95
    assert "Attempt 2" in result.message or "attempt 2" in result.message


def test_reaching_maximum_retries(tmp_path: Path, sample_context, sample_task):
    """Verifies that persistently low score halts after max_attempts with success=False."""
    class AlwaysLowScoreReviewer(ReviewerAgent):
        def review(self, context, generated_result, test_result=None):
            return ReviewResult(
                success=True,
                summary="Persistent architectural flaw",
                overall_quality_score=60,
                should_regenerate=True,
                explanation="Fails standards",
            )

    engine = RetryEngine(
        project_root=tmp_path,
        reviewer_agent=AlwaysLowScoreReviewer(),
        default_max_attempts=3,
        default_minimum_quality_score=85,
    )

    result = engine.execute(context=sample_context, task=sample_task)

    assert result.success is False
    assert result.attempts == 3
    assert result.max_attempts == 3
    assert len(result.execution_history) == 3
    assert "reached maximum retry limit" in result.message.lower()


def test_tester_triggered_retry(tmp_path: Path, sample_context, sample_task):
    """Verifies that high review score with failing tests triggers a retry."""
    test_calls = 0

    class MultiAttemptTester(TesterAgent):
        def run_tests(self, project_root, command=None, timeout_seconds=None):
            nonlocal test_calls
            test_calls += 1
            if test_calls == 1:
                return TestResult(
                    success=False,
                    total_tests=2,
                    passed=1,
                    failed=1,
                    skipped=0,
                    duration=0.1,
                    stdout="1 failed, 1 passed",
                    stderr="AssertionError",
                    exit_code=1,
                    command="pytest",
                    message="1 test failed",
                )
            else:
                return TestResult(
                    success=True,
                    total_tests=2,
                    passed=2,
                    failed=0,
                    skipped=0,
                    duration=0.1,
                    stdout="2 passed",
                    stderr="",
                    exit_code=0,
                    command="pytest",
                    message="All tests passed",
                )

    class HighScoreReviewer(ReviewerAgent):
        def review(self, context, generated_result, test_result=None):
            return ReviewResult(
                success=True,
                summary="Good code structure",
                overall_quality_score=90,
                should_regenerate=False,
                explanation="Clean code",
            )

    engine = RetryEngine(
        project_root=tmp_path,
        tester_agent=MultiAttemptTester(),
        reviewer_agent=HighScoreReviewer(),
        default_max_attempts=3,
    )

    result = engine.execute(context=sample_context, task=sample_task)

    assert result.success is True
    assert result.attempts == 2
    assert result.execution_history[0].tests_failed == 1
    assert result.execution_history[1].tests_failed == 0


def test_reviewer_should_regenerate_triggered_retry(tmp_path: Path, sample_context, sample_task):
    """Verifies that should_regenerate=True triggers retry even if score is high."""
    review_calls = 0

    class RegenerateReviewer(ReviewerAgent):
        def review(self, context, generated_result, test_result=None):
            nonlocal review_calls
            review_calls += 1
            return ReviewResult(
                success=True,
                summary="Critical logic defect",
                overall_quality_score=88,
                should_regenerate=(review_calls == 1),  # True on 1st, False on 2nd
                explanation="Need clean rewrite of algorithm",
            )

    engine = RetryEngine(
        project_root=tmp_path,
        reviewer_agent=RegenerateReviewer(),
        default_max_attempts=3,
    )

    result = engine.execute(context=sample_context, task=sample_task)

    assert result.success is True
    assert result.attempts == 2
    assert result.execution_history[0].should_regenerate is True
    assert result.execution_history[1].should_regenerate is False


def test_infrastructure_failure_halts_retry_loop(tmp_path: Path, sample_context, sample_task):
    """Verifies that disk/infrastructure errors raise exceptions and halt immediately."""
    class FailingWriter(FileWriterAgent):
        def write(self, result, target_dir=None, overwrite=None, backup=None):
            return WriteResult(
                files_written=[],
                failed_files={"src/core.py": "Disk I/O Error"},
                success=False,
            )

    engine = RetryEngine(
        project_root=tmp_path,
        file_writer=FailingWriter(project_root=tmp_path),
    )

    with pytest.raises(RuntimeError, match="FileWriterAgent failed on attempt 1"):
        engine.execute(context=sample_context, task=sample_task)


def test_execution_history_telemetry(tmp_path: Path, sample_context, sample_task):
    """Verifies that every retry attempt records complete AttemptRecord metrics."""
    engine = RetryEngine(project_root=tmp_path, default_max_attempts=1)
    result = engine.execute(context=sample_context, task=sample_task)

    assert len(result.execution_history) == 1
    rec = result.execution_history[0]
    assert isinstance(rec, AttemptRecord)
    assert rec.attempt_number == 1
    assert rec.quality_score >= 0
    assert rec.tests_passed >= 0
    assert rec.tests_failed >= 0
    assert isinstance(rec.should_regenerate, bool)
    assert len(rec.summary) > 0
