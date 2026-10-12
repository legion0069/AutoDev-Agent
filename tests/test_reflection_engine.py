"""
test_reflection_engine.py - AutoDev Version 3.1
Unit and integration tests for ReflectionEngine across task, sprint, release,
and monthly autonomous reflection cycles.
"""

from pathlib import Path
import pytest
from core.learning.learning_models import ReflectionScope
from core.learning.reflection_engine import ReflectionEngine


@pytest.fixture
def reflection_engine(tmp_path: Path):
    storage_dir = tmp_path / "reflection"
    return ReflectionEngine(storage_dir=str(storage_dir), auto_persist=True)


def test_task_reflection_successful_clean(reflection_engine: ReflectionEngine):
    rep = reflection_engine.reflect_on_task(
        task_id="TASK-01",
        task_title="Scaffold auth handler",
        execution_success=True,
        retries_count=0,
        tests_passed=10,
        tests_failed=0,
        prompt_length_chars=800,
        duration_seconds=1.5,
        review_score=95.0,
    )

    assert rep.scope == ReflectionScope.TASK
    assert rep.target_id == "TASK-01"
    assert rep.excessive_retries is False
    assert rep.tests_sufficient is True
    assert rep.prompt_too_large is False
    assert rep.planning_accuracy_score >= 90.0
    assert any("First-pass execution successful" in w for w in rep.what_worked)


def test_task_reflection_with_excessive_retries(reflection_engine: ReflectionEngine):
    rep = reflection_engine.reflect_on_task(
        task_id="TASK-02",
        task_title="Implement rate limiter",
        execution_success=True,
        retries_count=3,
        tests_passed=8,
        tests_failed=0,
        prompt_length_chars=1200,
        duration_seconds=9.5,
        review_score=80.0,
        error_logs=["AssertionError: expected 429 but got 200"],
    )

    assert rep.excessive_retries is True
    assert any("Multiple retries" in f for f in rep.what_failed)
    assert any("Assertion or validation errors" in rc for rc in rep.root_causes)
    assert any("Strengthen pre-execution test" in act for act in rep.improvement_actions)


def test_task_reflection_prompt_bloat(reflection_engine: ReflectionEngine):
    rep = reflection_engine.reflect_on_task(
        task_id="TASK-03",
        task_title="Generate big entity",
        execution_success=True,
        retries_count=0,
        tests_passed=5,
        tests_failed=0,
        prompt_length_chars=9500,  # exceeds 8000 threshold
        duration_seconds=4.0,
        review_score=90.0,
    )

    assert rep.prompt_too_large is True
    assert any("Prompt length" in f for f in rep.what_failed)
    assert any("Compress prompt instructions" in act for act in rep.improvement_actions)


def test_task_reflection_failed_execution(reflection_engine: ReflectionEngine):
    rep = reflection_engine.reflect_on_task(
        task_id="TASK-04",
        task_title="Complex refactor",
        execution_success=False,
        retries_count=3,
        tests_passed=2,
        tests_failed=4,
        prompt_length_chars=2000,
        duration_seconds=12.0,
        review_score=45.0,
        error_logs=["SyntaxError: invalid syntax", "Compilation failed"],
    )

    assert rep.tests_sufficient is False
    assert rep.planning_accuracy_score < 70.0
    assert any("Task execution failed" in f for f in rep.what_failed)
    assert any("Decompose large tasks" in act for act in rep.improvement_actions)


def test_sprint_reflection(reflection_engine: ReflectionEngine):
    task_records = [
        {"success": True, "retries": 0, "tests_passed": 5, "tests_failed": 0, "quality_score": 95.0, "duration": 2.0},
        {"success": True, "retries": 1, "tests_passed": 8, "tests_failed": 0, "quality_score": 90.0, "duration": 3.0},
        {"success": False, "retries": 2, "tests_passed": 3, "tests_failed": 2, "quality_score": 60.0, "duration": 5.0},
    ]

    rep = reflection_engine.reflect_on_sprint(
        sprint_id="SPRINT-01",
        task_records=task_records,
        duration_days=14,
    )

    assert rep.scope == ReflectionScope.SPRINT
    assert rep.target_id == "SPRINT-01"
    assert rep.metrics["total_tasks"] == 3
    assert rep.metrics["success_rate_pct"] == pytest.approx(66.67, 0.1)
    assert len(rep.improvement_actions) > 0


def test_release_reflection(reflection_engine: ReflectionEngine):
    rep = reflection_engine.reflect_on_release(
        release_version="3.1.0",
        release_notes="AutoDev Version 3.1 Self-Evolving Intelligence Engine",
        metrics={
            "lead_time_for_changes_hours": 1.5,
            "deployment_frequency_per_day": 12.0,
            "change_failure_rate_pct": 2.0,
            "time_to_restore_service_minutes": 5.0,
            "dora_score": 95.0,
        },
    )

    assert rep.scope == ReflectionScope.RELEASE
    assert rep.target_id == "RELEASE-3.1.0"
    assert any("Elite DORA tier" in w for w in rep.what_worked)
    assert rep.planning_accuracy_score >= 90.0


def test_monthly_reflection(reflection_engine: ReflectionEngine):
    rep = reflection_engine.reflect_monthly(
        month_period="2026-10",
        company_metrics={
            "sprints_completed": 2,
            "total_tasks_completed": 85,
            "average_review_score": 92.4,
            "system_uptime_pct": 99.98,
        },
    )

    assert rep.scope == ReflectionScope.MONTHLY
    assert rep.target_id == "MONTHLY-2026-10"
    assert rep.metrics["total_tasks_completed"] == 85
    assert len(rep.what_worked) > 0


def test_get_reflection_reports_query(reflection_engine: ReflectionEngine):
    r1 = reflection_engine.reflect_on_task(task_id="T1", task_title="T1", execution_success=True)
    r2 = reflection_engine.reflect_on_task(task_id="T2", task_title="T2", execution_success=False)
    r3 = reflection_engine.reflect_on_sprint(sprint_id="S1", task_records=[])

    all_reports = reflection_engine.get_all_reports()
    assert len(all_reports) == 3

    task_reports = reflection_engine.get_reports_by_scope(ReflectionScope.TASK)
    assert len(task_reports) == 2

    sprint_reports = reflection_engine.get_reports_by_scope(ReflectionScope.SPRINT)
    assert len(sprint_reports) == 1

    fetched_t1 = reflection_engine.get_report_by_target("T1")
    assert fetched_t1 is not None
    assert fetched_t1.id == r1.id
