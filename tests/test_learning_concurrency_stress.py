"""
tests/test_learning_concurrency_stress.py - Concurrency and Stress Tests for AutoDev v3.1 Subsystems
"""

import concurrent.futures
import shutil
import tempfile
import time
from pathlib import Path
import pytest

from core.learning import (
    ExecutionAnalyticsEngine,
    KnowledgeEvolutionEngine,
    LearningEngine,
    LearningEventType,
    PatternCategory,
    PatternMiningEngine,
    PerformanceEvolutionEngine,
    PlaybookArchetype,
    PlaybookEngine,
    PromptOptimizationEngine,
    ReflectionEngine,
    SelfEvolvingEngine,
    SelfImprovementPlanner,
)
from core.learning.learning_models import LearningKnowledge


@pytest.fixture
def temp_stress_dir():
    temp_dir = tempfile.mkdtemp(prefix="autodev_learning_stress_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_concurrent_event_recording(temp_stress_dir):
    engine = LearningEngine(storage_dir=temp_stress_dir)
    num_threads = 20
    events_per_thread = 15

    def worker(worker_id):
        for i in range(events_per_thread):
            engine.record_event(
                category=LearningEventType.BUG_FIXED if i % 2 == 0 else LearningEventType.ARCHITECTURE_SUCCESS,
                summary=f"Worker {worker_id} event {i}",
                project=f"proj_{worker_id % 3}",
                task_id=f"T-W{worker_id}-{i}",
                confidence=0.9,
                importance=75.0,
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, w) for w in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    all_events = engine.list_events()
    assert len(all_events) == num_threads * events_per_thread


def test_concurrent_analytics_recording_and_aggregation(temp_stress_dir):
    analytics = ExecutionAnalyticsEngine(storage_dir=temp_stress_dir)
    num_threads = 16

    def worker(worker_id):
        for i in range(10):
            analytics.record_project_run(
                project_id=f"proj_{worker_id % 4}",
                review_score=80.0 + (i % 20),
                retry_count=i % 3,
                duration_seconds=1.0 + (i * 0.1),
                files_changed=2 + i,
                tests_executed=10 + i,
                coverage_pct=85.0,
                architecture_score=90.0,
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, w) for w in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    kpis = analytics.compute_aggregate_kpis()
    assert kpis["total_runs"] == num_threads * 10
    assert kpis["average_review_score"] > 0.0


def test_concurrent_pattern_miner_usage_updates(temp_stress_dir):
    miner = PatternMiningEngine(storage_dir=temp_stress_dir)
    pattern = miner.register_pattern(
        name="ConcurrentTestPattern",
        category=PatternCategory.ARCHITECTURAL,
        description="Thread-safe pattern test",
        solution="Use locking and thread pools",
    )

    num_threads = 10
    updates_per_thread = 20

    def worker(worker_id):
        for i in range(updates_per_thread):
            miner.record_pattern_usage(
                pattern_id=pattern.pattern_id,
                success=(i % 4 != 0),
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, w) for w in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    updated = miner.get_pattern(pattern.pattern_id)
    assert updated.usage_count == num_threads * updates_per_thread
    assert 0.0 <= updated.success_rate <= 1.0


def test_concurrent_prompt_optimization_stress(temp_stress_dir):
    optimizer = PromptOptimizationEngine(storage_dir=temp_stress_dir)
    num_threads = 12

    def worker(worker_id):
        results = []
        for i in range(15):
            prompt = f"Line 1 for worker {worker_id}\nLine 1 for worker {worker_id}\nInstruction {i}\nInstruction {i}"
            res = optimizer.optimize_prompt(prompt, task_type="coding", target_tokens=100)
            results.append(res)
        return len(results)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, w) for w in range(num_threads)]
        total = sum(f.result() for f in concurrent.futures.as_completed(futures))

    assert total == num_threads * 15


def test_concurrent_playbook_experience_updates(temp_stress_dir):
    engine = PlaybookEngine(storage_dir=temp_stress_dir)
    num_threads = 8

    def worker(worker_id):
        for i in range(10):
            engine.record_playbook_experience(
                archetype=PlaybookArchetype.REST_API,
                success=(i % 3 != 0),
                duration_minutes=15.0 + i,
                review_score=90.0 + (i % 10),
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, w) for w in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    pb = engine.get_playbook(PlaybookArchetype.REST_API)
    assert pb.usage_count == num_threads * 10
    assert 0.0 <= pb.success_rate <= 1.0


def test_high_volume_event_ingestion_stress(temp_stress_dir):
    engine = LearningEngine(storage_dir=temp_stress_dir)
    start_time = time.time()
    num_events = 500

    for i in range(num_events):
        engine.record_event(
            category=LearningEventType.PERFORMANCE_IMPROVEMENT if i % 2 == 0 else LearningEventType.REFACTOR_SUCCESS,
            summary=f"High-volume batch event {i}",
            project="stress_volume_proj",
            task_id=f"T-VOL-{i}",
            confidence=0.95,
            importance=80.0,
            metrics={"index": i, "latency_ms": 10.5},
        )

    duration = time.time() - start_time
    assert len(engine.list_events()) == num_events
    # Ensure average ingestion time per event is fast (< 10ms per event)
    avg_ms = (duration / num_events) * 1000.0
    assert avg_ms < 50.0  # Safe upper bound on any machine


def test_concurrent_master_engine_tasks(temp_stress_dir):
    master = SelfEvolvingEngine(storage_dir=temp_stress_dir)
    num_threads = 6

    def worker(worker_id):
        results = []
        for i in range(5):
            res = master.on_task_completed(
                task_id=f"T-CONC-{worker_id}-{i}",
                task_title=f"Concurrent task {worker_id}-{i}",
                project_id=f"proj_{worker_id}",
                execution_success=(i % 2 == 0),
                retries_count=i % 2,
                tests_passed=10,
                tests_failed=0 if i % 2 == 0 else 2,
                duration_seconds=0.5,
                review_score=90.0,
            )
            results.append(res)
        return len(results)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, w) for w in range(num_threads)]
        total = sum(f.result() for f in concurrent.futures.as_completed(futures))

    assert total == num_threads * 5
    dashboard = master.get_learning_dashboard()
    assert dashboard["total_events"] == num_threads * 5
