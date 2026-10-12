"""
test_execution_analytics.py - AutoDev Version 3.1
Unit and integration tests for ExecutionAnalyticsEngine, statistics calculations,
metric distributions, trend graph JSON generation, and multi-project analytics.
"""

from pathlib import Path
import pytest
from core.learning.execution_analytics import ExecutionAnalyticsEngine


@pytest.fixture
def analytics_engine(tmp_path: Path):
    storage_dir = tmp_path / "analytics"
    return ExecutionAnalyticsEngine(storage_dir=str(storage_dir), auto_persist=True)


def test_record_and_query_analytics(analytics_engine: ExecutionAnalyticsEngine):
    evt = analytics_engine.record_task_metrics(
        project="PaymentEngine",
        task_id="TASK-01",
        review_score=95.0,
        retry_count=0,
        implementation_duration_s=2.5,
        files_changed_count=3,
        tests_executed_count=12,
        coverage_pct=92.5,
        commits_created=1,
        architecture_score=94.0,
    )

    assert evt.task_id == "TASK-01"
    assert evt.review_score == 95.0

    stats = analytics_engine.get_project_statistics("PaymentEngine")
    assert stats["total_tasks"] == 1
    assert stats["review_score"]["mean"] == 95.0
    assert stats["retry_count"]["mean"] == 0.0
    assert stats["coverage_pct"]["mean"] == 92.5


def test_statistics_calculations_multi_event(analytics_engine: ExecutionAnalyticsEngine):
    # Record 5 diverse events
    scores = [80.0, 85.0, 90.0, 95.0, 100.0]
    for i, s in enumerate(scores):
        analytics_engine.record_task_metrics(
            project="CoreEngine",
            task_id=f"TASK-0{i+1}",
            review_score=s,
            retry_count=i % 2,
            implementation_duration_s=1.0 + i,
            files_changed_count=2,
            tests_executed_count=10 + i * 2,
            coverage_pct=85.0 + i * 2,
            commits_created=1,
            architecture_score=90.0,
        )

    stats = analytics_engine.get_project_statistics("CoreEngine")
    assert stats["total_tasks"] == 5
    assert stats["review_score"]["min"] == 80.0
    assert stats["review_score"]["max"] == 100.0
    assert stats["review_score"]["mean"] == 90.0
    assert stats["review_score"]["median"] == 90.0
    assert stats["review_score"]["std_dev"] > 0.0
    assert stats["review_score"]["p95"] >= 95.0


def test_generate_trend_series(analytics_engine: ExecutionAnalyticsEngine):
    for i in range(10):
        analytics_engine.record_task_metrics(
            project="TrendsProject",
            task_id=f"T-{i}",
            review_score=80.0 + i * 1.5,
            retry_count=max(0, 3 - i // 3),
            implementation_duration_s=5.0 - (i * 0.3),
            files_changed_count=2,
            tests_executed_count=10 + i,
            coverage_pct=75.0 + i * 2,
            commits_created=1,
            architecture_score=85.0 + i,
        )

    trends = analytics_engine.generate_trend_graphs("TrendsProject")
    assert trends["project"] == "TrendsProject"
    assert len(trends["data_points"]) == 10

    series = trends["trend_series"]
    assert len(series["review_score"]) == 10
    assert len(series["retry_count"]) == 10
    assert len(series["duration"]) == 10
    assert len(series["coverage"]) == 10


def test_empty_project_statistics(analytics_engine: ExecutionAnalyticsEngine):
    stats = analytics_engine.get_project_statistics("NonExistentProject")
    assert stats["total_tasks"] == 0
    assert stats["review_score"]["mean"] == 0.0
    assert stats["review_score"]["min"] == 0.0
    assert stats["review_score"]["max"] == 0.0


def test_all_projects_summary(analytics_engine: ExecutionAnalyticsEngine):
    analytics_engine.record_task_metrics(project="P1", task_id="T1", review_score=90.0)
    analytics_engine.record_task_metrics(project="P2", task_id="T2", review_score=95.0)

    summary = analytics_engine.get_all_projects_summary()
    assert summary["total_records"] == 2
    assert "P1" in summary["projects"]
    assert "P2" in summary["projects"]
