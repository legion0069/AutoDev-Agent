"""
Tests for Subsystem 10: Performance Evolution Engine.
Measures speedup, latency tracking, memory usage profiling, and automated report generation.
"""
import pytest
import os
import shutil
import tempfile

from core.learning.learning_models import PerformanceEvolutionRecord
from core.learning.performance_evolution import PerformanceEvolutionEngine


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="autodev_test_perf_deep_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_performance_record_metrics(temp_dir):
    engine = PerformanceEvolutionEngine(storage_dir=temp_dir)
    
    rec = engine.record_metric(
        stage="generation",
        execution_time_seconds=2.4,
        memory_usage_mb=128.5,
        generation_latency_ms=240.0,
        benchmark_name="codegen_benchmark"
    )
    
    assert rec.stage == "generation"
    assert rec.execution_time_seconds == 2.4
    assert rec.memory_usage_mb == 128.5
    assert rec.generation_latency_ms == 240.0
    assert rec.duration_ms == 2400.0


def test_speedup_and_memory_delta_tracking(temp_dir):
    engine = PerformanceEvolutionEngine(storage_dir=temp_dir)
    
    # Run 1 (baseline)
    r1 = engine.record_metric(stage="planning", execution_time_seconds=2.0, memory_usage_mb=100.0)
    # Run 2 (optimized)
    r2 = engine.record_metric(stage="planning", execution_time_seconds=1.0, memory_usage_mb=80.0)
    
    report = engine.generate_evolution_report()
    assert report["total_benchmarks"] >= 2
    assert "planning" in report.get("stage_summaries", {})


def test_performance_report_serialization(temp_dir):
    engine = PerformanceEvolutionEngine(storage_dir=temp_dir)
    
    engine.record_metric(stage="review", execution_time_seconds=0.5, memory_usage_mb=32.0)
    engine.record_metric(stage="orchestration", execution_time_seconds=1.2, memory_usage_mb=64.0)
    
    report = engine.generate_evolution_report()
    assert "version" in report
    assert "timestamp" in report
    assert "average_execution_time_seconds" in report
