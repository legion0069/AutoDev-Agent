"""
test_performance_evolution.py - AutoDev Version 3.1
Unit and integration tests for PerformanceEvolutionEngine, generational tracking,
speedup calculation, memory reduction analysis, and performance report synthesis.
"""

from pathlib import Path
import pytest
from core.learning.learning_models import PerformanceEvolutionRecord
from core.learning.performance_evolution import PerformanceEvolutionEngine


@pytest.fixture
def perf_engine(tmp_path: Path):
    storage_dir = tmp_path / "perf"
    return PerformanceEvolutionEngine(storage_dir=str(storage_dir), auto_persist=True)


def test_record_benchmark_result(perf_engine: PerformanceEvolutionEngine):
    rec = perf_engine.record_benchmark(
        version="3.1.0",
        benchmark_name="MultiAgentPlanningBenchmark",
        execution_time_seconds=2.45,
        memory_usage_mb=42.0,
        planning_latency_ms=115.0,
        review_latency_ms=78.0,
        generation_latency_ms=280.0,
        metrics={"tasks_planned": 15, "throughput": 6.12},
    )

    assert rec.record_id.startswith("PERF-")
    assert rec.version == "3.1.0"
    assert rec.benchmark_name == "MultiAgentPlanningBenchmark"
    assert rec.planning_latency_ms == 115.0


def test_generational_speedup_and_memory_comparison(perf_engine: PerformanceEvolutionEngine):
    # Benchmark v3.0 baseline
    perf_engine.record_benchmark(
        version="3.0.0",
        benchmark_name="FullSprintBenchmark",
        execution_time_seconds=10.0,
        memory_usage_mb=100.0,
        planning_latency_ms=300.0,
        review_latency_ms=200.0,
        generation_latency_ms=500.0,
    )

    # Benchmark v3.1 optimized
    rec_v31 = perf_engine.record_benchmark(
        version="3.1.0",
        benchmark_name="FullSprintBenchmark",
        execution_time_seconds=6.0,   # 40% reduction in time -> 1.67x speedup
        memory_usage_mb=80.0,         # 20 MB reduction
        planning_latency_ms=180.0,
        review_latency_ms=120.0,
        generation_latency_ms=300.0,
    )

    assert rec_v31.speedup_vs_previous == pytest.approx(1.67, 0.05)
    assert rec_v31.memory_delta_vs_previous == pytest.approx(-20.0, 0.1)


def test_generate_evolution_report(perf_engine: PerformanceEvolutionEngine):
    perf_engine.record_benchmark("2.9.0", "TaskExec", 12.0, 120.0)
    perf_engine.record_benchmark("3.0.0", "TaskExec", 9.0, 110.0)
    perf_engine.record_benchmark("3.1.0", "TaskExec", 5.0, 85.0)

    report = perf_engine.generate_evolution_report("TaskExec")
    assert report["benchmark_name"] == "TaskExec"
    assert len(report["history"]) == 3
    assert report["latest_version"] == "3.1.0"
    assert report["latest_execution_time"] == 5.0
    assert report["total_speedup_vs_oldest"] == pytest.approx(2.4, 0.1)
    assert report["total_memory_saved_mb"] == pytest.approx(35.0, 0.1)


def test_get_latest_and_all_records(perf_engine: PerformanceEvolutionEngine):
    r1 = perf_engine.record_benchmark("3.0.0", "BenchA", 1.0, 50.0)
    r2 = perf_engine.record_benchmark("3.1.0", "BenchA", 0.5, 40.0)

    latest = perf_engine.get_latest_record("BenchA")
    assert latest is not None
    assert latest.record_id == r2.record_id

    records = perf_engine.get_records_by_version("3.1.0")
    assert len(records) == 1
    assert records[0].version == "3.1.0"
