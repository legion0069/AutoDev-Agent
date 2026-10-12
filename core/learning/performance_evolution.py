"""
performance_evolution.py - Autonomous Performance Evolution & Latency Benchmarking Engine for AutoDev (v3.1)

Tracks computational efficiency, execution durations, memory footprints, planning latencies,
review speeds, and generation throughput across software release iterations.
Generates comparative version improvement reports and quantifies generational speedups.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.learning.learning_models import PerformanceEvolutionRecord

logger = logging.getLogger("AutoDev.Learning.PerformanceEvolution")


class PerformanceEvolutionEngine:
    """
    Performance Evolution Engine.
    Records stage latencies, memory consumption, and compares performance across system versions.
    """

    def __init__(self, storage_dir: Optional[str] = None, auto_persist: bool = True) -> None:
        self._lock = threading.RLock()
        self.storage_dir = Path(storage_dir) if storage_dir else Path("memory/learning")
        self.auto_persist = auto_persist
        
        self._records: List[PerformanceEvolutionRecord] = []
        self._benchmark_index: Dict[str, List[PerformanceEvolutionRecord]] = defaultdict(list)
        self._version_index: Dict[str, List[PerformanceEvolutionRecord]] = defaultdict(list)

        if self.auto_persist:
            self._ensure_storage()
            self._load_state()

    def _ensure_storage(self) -> None:
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Could not create performance storage directory: %s", e)

    def record_benchmark(
        self,
        version: str = "3.1.0",
        benchmark_name: str = "GeneralBenchmark",
        execution_time_seconds: float = 1.0,
        memory_usage_mb: float = 50.0,
        planning_latency_ms: float = 0.0,
        review_latency_ms: float = 0.0,
        generation_latency_ms: float = 0.0,
        metrics: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> PerformanceEvolutionRecord:
        """
        Records a benchmark run and calculates speedup / memory delta compared to previous runs of the same benchmark.
        """
        with self._lock:
            now = time.time()
            r_id = f"PERF-{version.replace('.', '_')}-{benchmark_name}-{int(now * 1000)}"

            existing_bench_runs = self._benchmark_index.get(benchmark_name, [])
            speedup = 1.0
            mem_delta = 0.0
            if existing_bench_runs:
                prev = existing_bench_runs[-1]
                if execution_time_seconds > 0:
                    speedup = round(prev.execution_time_seconds / max(0.0001, execution_time_seconds), 2)
                mem_delta = round(memory_usage_mb - prev.memory_usage_mb, 2)

            dur_ms = execution_time_seconds * 1000.0 if execution_time_seconds > 0 else (planning_latency_ms + review_latency_ms + generation_latency_ms)

            stage_val = kwargs.get("stage") or benchmark_name
            rec = PerformanceEvolutionRecord(
                record_id=r_id,
                version=version,
                version_tag=version,
                benchmark_name=benchmark_name,
                stage=stage_val,
                execution_time_seconds=float(execution_time_seconds),
                duration_ms=dur_ms,
                memory_usage_mb=float(memory_usage_mb),
                memory_kb=memory_usage_mb * 1024.0,
                planning_latency_ms=float(planning_latency_ms),
                review_latency_ms=float(review_latency_ms),
                generation_latency_ms=float(generation_latency_ms),
                speedup_vs_previous=speedup,
                memory_delta_vs_previous=mem_delta,
                metrics=dict(metrics or {}),
                timestamp=now,
            )

            self._records.append(rec)
            self._benchmark_index[benchmark_name].append(rec)
            self._version_index[version].append(rec)

            if self.auto_persist:
                self._persist_state()

            logger.info("Recorded benchmark '%s' for v%s (time=%.2fs, speedup=%.2fx)",
                        benchmark_name, version, execution_time_seconds, speedup)
            return copy.deepcopy(rec)

    def record_run(
        self,
        version_tag: str = "v3.1",
        stage: str = "task_execution",
        duration_ms: float = 100.0,
        memory_kb: float = 4000.0,
        throughput_ops_sec: float = 10.0,
        **kwargs: Any,
    ) -> PerformanceEvolutionRecord:
        """Records task-level runtime performance."""
        return self.record_benchmark(
            version=version_tag,
            benchmark_name=stage,
            execution_time_seconds=duration_ms / 1000.0,
            memory_usage_mb=memory_kb / 1024.0,
            metrics={"throughput_ops_sec": throughput_ops_sec, **kwargs},
        )

    def record_metric(
        self,
        stage: str = "execution",
        execution_time_seconds: float = 0.0,
        memory_usage_mb: float = 0.0,
        planning_latency_ms: float = 0.0,
        review_latency_ms: float = 0.0,
        generation_latency_ms: float = 0.0,
        benchmark_name: str = "",
        version: str = "3.1.0",
        **kwargs: Any,
    ) -> PerformanceEvolutionRecord:
        """Records a performance metric for a specific stage or benchmark."""
        b_name = benchmark_name or stage
        kw = dict(kwargs)
        kw["stage"] = stage
        return self.record_benchmark(
            version=version,
            benchmark_name=b_name,
            execution_time_seconds=execution_time_seconds,
            memory_usage_mb=memory_usage_mb,
            planning_latency_ms=planning_latency_ms,
            review_latency_ms=review_latency_ms,
            generation_latency_ms=generation_latency_ms,
            metrics=kwargs,
            **kw,
        )

    def generate_evolution_report(self, benchmark_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates longitudinal comparative report for a benchmark across all versions or system-wide.
        """
        with self._lock:
            if benchmark_name:
                history = self._benchmark_index.get(benchmark_name, [])
                if not history:
                    return {
                        "benchmark_name": benchmark_name,
                        "history": [],
                        "latest_version": "N/A",
                        "latest_execution_time": 0.0,
                        "total_speedup_vs_oldest": 1.0,
                        "total_memory_saved_mb": 0.0,
                    }

                oldest = history[0]
                latest = history[-1]
                total_speedup = round(oldest.execution_time_seconds / max(0.0001, latest.execution_time_seconds), 2)
                total_mem_saved = round(oldest.memory_usage_mb - latest.memory_usage_mb, 2)

                return {
                    "benchmark_name": benchmark_name,
                    "history": [r.to_dict() for r in history],
                    "latest_version": latest.version,
                    "latest_execution_time": latest.execution_time_seconds,
                    "total_speedup_vs_oldest": total_speedup,
                    "total_memory_saved_mb": total_mem_saved,
                }
            else:
                # System-wide summary
                stage_summaries = {}
                for b_name in self._benchmark_index:
                    stage_summaries[b_name] = self.generate_evolution_report(b_name)

                avg_speedup = 1.0
                if self._records:
                    speedups = [r.speedup_vs_previous for r in self._records if r.speedup_vs_previous > 0]
                    if speedups:
                        avg_speedup = round(sum(speedups) / len(speedups), 2)

                return {
                    "version": "3.1.0",
                    "timestamp": time.time(),
                    "total_benchmarks": len(self._records),
                    "total_records": len(self._records),
                    "overall_speedup": avg_speedup,
                    "average_execution_time_seconds": round(sum(r.execution_time_seconds for r in self._records) / max(1, len(self._records)), 3) if self._records else 0.0,
                    "stage_summaries": stage_summaries,
                    "benchmarks": stage_summaries,
                }

    def get_latest_record(self, benchmark_name: str) -> Optional[PerformanceEvolutionRecord]:
        """Retrieves the latest benchmark record."""
        with self._lock:
            history = self._benchmark_index.get(benchmark_name, [])
            return copy.deepcopy(history[-1]) if history else None

    def get_records_by_version(self, version: str) -> List[PerformanceEvolutionRecord]:
        """Returns all records for a specific version."""
        with self._lock:
            recs = self._version_index.get(version, [])
            return [copy.deepcopy(r) for r in recs]

    def list_records(self, version_tag: Optional[str] = None) -> List[PerformanceEvolutionRecord]:
        """Lists records with optional version filter."""
        if version_tag:
            return self.get_records_by_version(version_tag)
        with self._lock:
            return [copy.deepcopy(r) for r in self._records]

    def generate_performance_report(self) -> Dict[str, Any]:
        """Generates comprehensive performance evolution report across benchmarks."""
        with self._lock:
            benchmarks_summary = {}
            for b_name in self._benchmark_index:
                benchmarks_summary[b_name] = self.generate_evolution_report(b_name)

            latest = self._records[-1] if self._records else None
            return {
                "timestamp": time.time(),
                "total_records": len(self._records),
                "total_runs": len(self._records),
                "latest_run": latest.to_dict() if latest else None,
                "generational_speedup": round(latest.speedup_vs_previous, 2) if latest else 1.0,
                "memory_delta_pct": round(latest.memory_delta_vs_previous, 2) if latest else 0.0,
                "benchmarks_profiled": list(self._benchmark_index.keys()),
                "benchmarks": benchmarks_summary,
            }

    def _persist_state(self) -> None:
        try:
            self._ensure_storage()
            out_file = self.storage_dir / "performance_evolution.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self._records], f, indent=2)
        except Exception as e:
            logger.error("Failed to persist performance data: %s", e)

    def _load_state(self) -> None:
        out_file = self.storage_dir / "performance_evolution.json"
        if out_file.exists():
            try:
                with open(out_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._records = [PerformanceEvolutionRecord.from_dict(item) for item in data]
                    self._benchmark_index = defaultdict(list)
                    self._version_index = defaultdict(list)
                    for r in self._records:
                        self._benchmark_index[r.benchmark_name].append(r)
                        self._version_index[r.version].append(r)
            except Exception as e:
                logger.warning("Could not load performance records: %s", e)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_records": len(self._records),
                "benchmarks": list(self._benchmark_index.keys()),
            }
