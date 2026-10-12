"""
core/benchmark_framework.py - Multi-Dimensional Scientific Benchmarking Framework (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import enum
import os
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from core.statistical_analyzer import DescriptiveStatistics, StatisticalAnalyzer


class BenchmarkProfile(str, enum.Enum):
    """Presets for benchmarking rigor and duration."""
    MICRO = "MICRO"
    STANDARD = "STANDARD"
    ENTERPRISE = "ENTERPRISE"
    DEEP = "DEEP"


class BenchmarkMetric(str, enum.Enum):
    """Core performance, reliability, and quality metrics tracked across the ecosystem."""
    LATENCY = "LATENCY"
    LATENCY_MS = "LATENCY_MS"
    LATENCY_MEAN_MS = "LATENCY_MEAN_MS"
    LATENCY_P95_MS = "LATENCY_P95_MS"
    THROUGHPUT_OPS_SEC = "THROUGHPUT_OPS_SEC"
    MEMORY = "MEMORY"
    MEMORY_PEAK_MB = "MEMORY_PEAK_MB"
    CPU = "CPU"
    SUCCESS_RATE = "SUCCESS_RATE"
    ERROR_RATE_PCT = "ERROR_RATE_PCT"
    RETRIES = "RETRIES"
    QUALITY = "QUALITY"
    HALLUCINATION = "HALLUCINATION"
    REGRESSION = "REGRESSION"
    COVERAGE = "COVERAGE"
    RELIABILITY = "RELIABILITY"
    SCALABILITY = "SCALABILITY"


@dataclass
class BenchmarkCase:
    """Specification of an individual benchmark test case."""
    case_id: str
    name: str
    metric: BenchmarkMetric = BenchmarkMetric.LATENCY_MEAN_MS
    target_function: Optional[Callable[..., Any]] = None
    baseline_value: float = 0.0
    regression_threshold_pct: float = 5.0
    iterations: int = 10
    warmup_iterations: int = 2
    args: Tuple[Any, ...] = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    higher_is_better: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "name": self.name,
            "metric": self.metric.value,
            "baseline_value": self.baseline_value,
            "regression_threshold_pct": self.regression_threshold_pct,
            "iterations": self.iterations,
            "warmup_iterations": self.warmup_iterations,
            "description": self.description,
            "higher_is_better": self.higher_is_better,
        }


@dataclass
class BenchmarkResult:
    """Aggregated statistical outcome of running a benchmark case."""
    case_id: str
    name: str
    metric: BenchmarkMetric = BenchmarkMetric.LATENCY_MEAN_MS
    sample_size: int = 0
    raw_measurements: List[float] = field(default_factory=list)
    statistics: Optional[DescriptiveStatistics] = None
    baseline_value: float = 0.0
    delta_pct: float = 0.0
    is_regression: bool = False
    passed: bool = True
    execution_time_sec: float = 0.0
    timestamp: float = field(default_factory=time.time)
    status: str = "completed"
    error_message: Optional[str] = None
    iterations: int = 0
    metrics: Dict[BenchmarkMetric, DescriptiveStatistics] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        mean_val = round(self.statistics.mean, 6) if self.statistics else 0.0
        median_val = round(self.statistics.median, 6) if self.statistics else 0.0
        std_val = round(self.statistics.std_dev, 6) if self.statistics else 0.0
        min_val = round(self.statistics.min_val, 6) if self.statistics else 0.0
        max_val = round(self.statistics.max_val, 6) if self.statistics else 0.0

        return {
            "case_id": self.case_id,
            "name": self.name,
            "metric": self.metric.value,
            "sample_size": self.sample_size,
            "mean": mean_val,
            "median": median_val,
            "std_dev": std_val,
            "min_val": min_val,
            "max_val": max_val,
            "p95": round(StatisticalAnalyzer.percentile(self.raw_measurements, 95.0), 6) if self.raw_measurements else 0.0,
            "baseline_value": round(self.baseline_value, 6),
            "delta_pct": round(self.delta_pct, 4),
            "is_regression": self.is_regression,
            "passed": self.passed,
            "execution_time_sec": round(self.execution_time_sec, 4),
            "timestamp": self.timestamp,
            "status": self.status,
            "error_message": self.error_message,
        }


class BenchmarkSuite:
    """Manages a suite of benchmarks."""

    def __init__(self, suite_id: str = "BENCH-SUITE-ROOT", name: str = "Enterprise Benchmark Suite") -> None:
        self._lock = threading.RLock()
        self.suite_id = suite_id
        self.name = name
        self._cases: Dict[str, BenchmarkCase] = {}
        self._history: List[BenchmarkResult] = []

    def add_benchmark(self, name: str, callable_fn: Callable[..., Any]) -> None:
        """Adds a benchmark callable to the suite."""
        with self._lock:
            case = BenchmarkCase(
                case_id=f"CASE-{len(self._cases) + 1}",
                name=name,
                target_function=callable_fn,
            )
            self._cases[name] = case

    def add_case(self, case: BenchmarkCase) -> None:
        with self._lock:
            self._cases[case.name or case.case_id] = case

    def register_simple_case(
        self,
        case_id: str,
        name: str,
        metric: BenchmarkMetric,
        fn: Callable[..., Any],
        baseline_value: float = 0.0,
        iterations: int = 10,
        higher_is_better: bool = False,
    ) -> BenchmarkCase:
        case = BenchmarkCase(
            case_id=case_id,
            name=name,
            metric=metric,
            target_function=fn,
            baseline_value=baseline_value,
            iterations=iterations,
            higher_is_better=higher_is_better,
        )
        self.add_case(case)
        return case


class BenchmarkFramework:
    """
    Multi-dimensional scientific benchmarking framework supporting micro-benchmarking,
    suites, regression analysis, threshold validation, and hypothesis comparison.
    """

    def __init__(
        self,
        default_warmup_iterations: Optional[int] = None,
        default_measurement_iterations: Optional[int] = None,
        profile: Optional[BenchmarkProfile] = None,
    ) -> None:
        self._lock = threading.RLock()
        if profile == BenchmarkProfile.MICRO:
            self.default_warmup = 1
            self.default_iterations = 3
        elif profile == BenchmarkProfile.ENTERPRISE:
            self.default_warmup = 5
            self.default_iterations = 20
        elif profile == BenchmarkProfile.DEEP:
            self.default_warmup = 10
            self.default_iterations = 50
        else:
            self.default_warmup = 2 if default_warmup_iterations is None else default_warmup_iterations
            self.default_iterations = 10 if default_measurement_iterations is None else default_measurement_iterations

        if default_warmup_iterations is not None:
            self.default_warmup = default_warmup_iterations
        if default_measurement_iterations is not None:
            self.default_iterations = default_measurement_iterations

        self._history: List[BenchmarkResult] = []

    def run_benchmark(
        self,
        name: str,
        callable_fn: Callable[..., Any],
        iterations: Optional[int] = None,
        warmup_iterations: Optional[int] = None,
        *args: Any,
        **kwargs: Any,
    ) -> BenchmarkResult:
        """Executes a single benchmark callable and computes comprehensive timing and statistics."""
        with self._lock:
            warmups = self.default_warmup if warmup_iterations is None else warmup_iterations
            total_iters = self.default_iterations if iterations is None else iterations
            case_id = f"BENCH-{name.upper()}-{int(time.time() * 1000)}"

            # Warmup
            for _ in range(warmups):
                try:
                    callable_fn(*args, **kwargs)
                except Exception as e:
                    return BenchmarkResult(
                        case_id=case_id,
                        name=name,
                        passed=False,
                        status="failed",
                        error_message=str(e),
                        iterations=0,
                    )

            measurements: List[float] = []
            t_total_start = time.perf_counter()

            for _ in range(total_iters):
                t0 = time.perf_counter()
                try:
                    callable_fn(*args, **kwargs)
                except Exception as e:
                    return BenchmarkResult(
                        case_id=case_id,
                        name=name,
                        passed=False,
                        status="failed",
                        error_message=str(e),
                        iterations=len(measurements),
                    )
                t1 = time.perf_counter()
                elapsed_ms = (t1 - t0) * 1000.0
                measurements.append(elapsed_ms)

            total_elapsed_sec = time.perf_counter() - t_total_start
            stats = StatisticalAnalyzer.summarize(measurements)

            metrics: Dict[BenchmarkMetric, DescriptiveStatistics] = {
                BenchmarkMetric.LATENCY_MEAN_MS: stats,
                BenchmarkMetric.LATENCY_MS: stats,
                BenchmarkMetric.LATENCY: stats,
            }

            result = BenchmarkResult(
                case_id=case_id,
                name=name,
                metric=BenchmarkMetric.LATENCY_MEAN_MS,
                sample_size=len(measurements),
                raw_measurements=measurements,
                statistics=stats,
                passed=True,
                status="completed",
                execution_time_sec=total_elapsed_sec,
                iterations=total_iters,
                metrics=metrics,
            )
            self._history.append(result)
            return result

    def run_suite(self, suite: BenchmarkSuite) -> Dict[str, BenchmarkResult]:
        """Runs all benchmarks in a BenchmarkSuite."""
        with self._lock:
            results: Dict[str, BenchmarkResult] = {}
            for name, case in suite._cases.items():
                if case.target_function:
                    res = self.run_benchmark(
                        name=case.name,
                        callable_fn=case.target_function,
                        iterations=case.iterations or self.default_iterations,
                        warmup_iterations=case.warmup_iterations or self.default_warmup,
                        *case.args,
                        **case.kwargs,
                    )
                    results[name] = res
            return results

    def validate_threshold(
        self,
        result: BenchmarkResult,
        metric: BenchmarkMetric,
        max_allowed: Optional[float] = None,
        min_allowed: Optional[float] = None,
    ) -> bool:
        """Validates whether a benchmark result satisfies metric boundaries."""
        if result.status != "completed":
            return False
        stat = result.metrics.get(metric) or result.statistics
        if not stat:
            return False

        val = stat.mean
        if max_allowed is not None and val > max_allowed:
            return False
        if min_allowed is not None and val < min_allowed:
            return False
        return True

    def compare(self, baseline: BenchmarkResult, candidate: BenchmarkResult) -> Dict[str, Any]:
        """Compares baseline vs candidate benchmark results with statistical hypothesis tests."""
        b_stat = baseline.metrics.get(BenchmarkMetric.LATENCY_MEAN_MS) or baseline.statistics
        c_stat = candidate.metrics.get(BenchmarkMetric.LATENCY_MEAN_MS) or candidate.statistics

        b_mean = b_stat.mean if b_stat else 0.0
        c_mean = c_stat.mean if c_stat else 0.0

        reduction_pct = 0.0
        if b_mean > 1e-12:
            reduction_pct = ((b_mean - c_mean) / b_mean) * 100.0

        # Perform Welch's t-test
        t_test = StatisticalAnalyzer.t_test_two_sample(
            baseline.raw_measurements,
            candidate.raw_measurements,
        )

        return {
            "baseline_mean_ms": round(b_mean, 4),
            "candidate_mean_ms": round(c_mean, 4),
            "latency_reduction_pct": round(reduction_pct, 4),
            "is_statistically_significant": t_test.is_significant,
            "p_value": round(t_test.p_value, 6),
            "cohens_d": round(t_test.effect_size or 0.0, 4),
        }

    def get_scorecard(self) -> Dict[str, Any]:
        """Generates an executive summary scorecard of all executed runs."""
        with self._lock:
            total = len(self._history)
            passed = sum(1 for r in self._history if r.passed and r.status == "completed")
            return {
                "total_runs": total,
                "passed_runs": passed,
                "failed_runs": total - passed,
                "success_rate_pct": round((passed / total * 100.0) if total > 0 else 100.0, 2),
                "history": [r.to_dict() for r in self._history[-10:]],
            }
