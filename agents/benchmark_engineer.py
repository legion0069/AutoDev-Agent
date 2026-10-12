"""
agents/benchmark_engineer.py - Benchmark Engineer Agent (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from core.benchmark_framework import BenchmarkMetric, BenchmarkProfile, BenchmarkResult
from core.communication_bus import CommunicationBus
from core.research_lab import ResearchLab

logger = logging.getLogger("AutoDev.Research.BenchmarkEngineer")


class BenchmarkEngineerAgent:
    """
    Benchmark Engineer Agent - Guardian of Execution Performance & System Telemetry:
    - Designs and maintains multi-dimensional micro-benchmarks
    - Evaluates latency, memory allocation, CPU cycles, and throughput
    - Enforces warmup phases and detects performance regressions against baselines
    """

    def __init__(
        self,
        name: str = "BenchmarkEngineer",
        lab: Optional[ResearchLab] = None,
        bus: Optional[CommunicationBus] = None,
    ) -> None:
        self.name = name
        self.lab = lab or ResearchLab()
        self.bus = bus
        self.authority_level = 3

        if self.bus:
            self.bus.register_entity(self.name)

    def register_benchmark(
        self,
        name: str,
        target_fn: Callable[[], Any],
        metric_type: BenchmarkMetric = BenchmarkMetric.LATENCY_MS,
        iterations: int = 50,
        warmup_runs: int = 5,
        threshold: float = 100.0,
    ) -> BenchmarkProfile:
        """Registers a performance benchmark in the laboratory benchmark suite."""
        return self.lab.benchmark_suite.register_benchmark(
            name=name,
            target_fn=target_fn,
            metric_type=metric_type,
            iterations=iterations,
            warmup_runs=warmup_runs,
            target_threshold=threshold,
        )

    def run_suite(self) -> Dict[str, Any]:
        """Executes all registered performance benchmarks and compiles a scorecard."""
        results = self.lab.benchmark_suite.run_all()
        scorecard = self.lab.benchmark_suite.get_scorecard()
        return {
            "scorecard": scorecard,
            "individual_results": {k: v.to_dict() for k, v in results.items()},
            "evaluated_by": self.name,
        }

    def detect_regression(self, baseline_val: float, candidate_val: float, max_allowed_pct: float = 5.0) -> Dict[str, Any]:
        """Verifies whether a candidate change exceeds the allowable regression budget."""
        delta = candidate_val - baseline_val
        delta_pct = (delta / baseline_val * 100.0) if baseline_val > 0 else 0.0

        is_regressed = delta_pct > max_allowed_pct
        return {
            "baseline": baseline_val,
            "candidate": candidate_val,
            "delta_pct": round(delta_pct, 2),
            "is_regression": is_regressed,
            "verdict": "FAIL" if is_regressed else "PASS",
        }
