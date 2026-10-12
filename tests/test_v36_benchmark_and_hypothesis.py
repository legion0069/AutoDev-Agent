"""
tests/test_v36_benchmark_and_hypothesis.py - Tests for BenchmarkFramework & HypothesisEngine
AutoDev Version 3.6 Autonomous AI Research Lab.
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import time
import unittest

from core.benchmark_framework import (
    BenchmarkFramework,
    BenchmarkMetric,
    BenchmarkProfile,
    BenchmarkResult,
    BenchmarkSuite,
)
from core.hypothesis_engine import (
    HypothesisEngine,
    HypothesisPriority,
    HypothesisStatus,
    ResearchHypothesis,
)


class TestBenchmarkFramework(unittest.TestCase):
    """Verifies timing, metrics, warm-ups, and thresholds in BenchmarkFramework."""

    def setUp(self) -> None:
        self.framework = BenchmarkFramework(default_warmup_iterations=2, default_measurement_iterations=5)

    def test_run_benchmark_simple(self) -> None:
        def dummy_task():
            time.sleep(0.001)
            return 42

        res = self.framework.run_benchmark(name="simple_sleep", callable_fn=dummy_task)
        self.assertIsInstance(res, BenchmarkResult)
        self.assertEqual(res.name, "simple_sleep")
        self.assertEqual(res.iterations, 5)
        self.assertGreater(res.metrics[BenchmarkMetric.LATENCY_MEAN_MS].mean, 0.5)

    def test_run_benchmark_with_args(self) -> None:
        def compute_sum(a, b):
            return a + b

        res = self.framework.run_benchmark(name="compute_sum", callable_fn=compute_sum, a=10, b=25)
        self.assertEqual(res.status, "completed")
        self.assertIn(BenchmarkMetric.LATENCY_MEAN_MS, res.metrics)

    def test_benchmark_suite(self) -> None:
        suite = BenchmarkSuite(name="math_ops")
        suite.add_benchmark("add", lambda: 1 + 1)
        suite.add_benchmark("mul", lambda: 2 * 3)

        results = self.framework.run_suite(suite)
        self.assertEqual(len(results), 2)
        self.assertIn("add", results)
        self.assertIn("mul", results)

    def test_threshold_validation_pass(self) -> None:
        res = self.framework.run_benchmark("quick", lambda: sum(range(100)))
        passes = self.framework.validate_threshold(res, BenchmarkMetric.LATENCY_MEAN_MS, max_allowed=500.0)
        self.assertTrue(passes)

    def test_threshold_validation_fail(self) -> None:
        res = self.framework.run_benchmark("quick", lambda: sum(range(100)))
        passes = self.framework.validate_threshold(res, BenchmarkMetric.LATENCY_MEAN_MS, max_allowed=0.00000001)
        self.assertFalse(passes)

    def test_compare_benchmarks(self) -> None:
        b1 = self.framework.run_benchmark("baseline", lambda: time.sleep(0.005))
        b2 = self.framework.run_benchmark("optimized", lambda: time.sleep(0.001))

        comp = self.framework.compare(baseline=b1, candidate=b2)
        self.assertIn("latency_reduction_pct", comp)
        self.assertGreater(comp["latency_reduction_pct"], 50.0)
        self.assertTrue(comp["is_statistically_significant"])

    def test_benchmark_profile_presets(self) -> None:
        fw_fast = BenchmarkFramework(profile=BenchmarkProfile.MICRO)
        self.assertEqual(fw_fast.default_warmup, 1)
        self.assertEqual(fw_fast.default_iterations, 3)

        fw_rigor = BenchmarkFramework(profile=BenchmarkProfile.ENTERPRISE)
        self.assertEqual(fw_rigor.default_warmup, 5)
        self.assertEqual(fw_rigor.default_iterations, 20)

    def test_error_handling_in_benchmark(self) -> None:
        def faulty_task():
            raise ValueError("Task failed unexpectedly")

        res = self.framework.run_benchmark("faulty", faulty_task)
        self.assertEqual(res.status, "failed")
        self.assertIn("Task failed unexpectedly", res.error_message or "")


class TestHypothesisEngine(unittest.TestCase):
    """Verifies hypothesis tracking, status transitions, and falsification."""

    def setUp(self) -> None:
        self.engine = HypothesisEngine()

    def test_formulate_hypothesis(self) -> None:
        hyp = self.engine.formulate(
            statement="Replacing linear scan with hash lookup reduces query latency by 50%",
            rationale="Hash table lookup possesses O(1) average time complexity vs O(N).",
            metric_target="latency_ms",
            expected_effect_direction="decrease",
            target_effect_size=0.5,
            priority=HypothesisPriority.HIGH,
        )
        self.assertIsInstance(hyp, ResearchHypothesis)
        self.assertEqual(hyp.status, HypothesisStatus.PROPOSED)
        self.assertEqual(hyp.priority, HypothesisPriority.HIGH)
        self.assertEqual(self.engine.total_count, 1)

    def test_transition_status(self) -> None:
        hyp = self.engine.formulate("Memory footprint decreases", "Object pooling reuse")
        self.engine.transition_status(hyp.hypothesis_id, HypothesisStatus.UNDER_TEST)
        self.assertEqual(self.engine.get(hyp.hypothesis_id).status, HypothesisStatus.UNDER_TEST)

    def test_confirm_hypothesis(self) -> None:
        hyp = self.engine.formulate("Speed increases by 2x", "Vectorized calculations")
        updated = self.engine.confirm(
            hypothesis_id=hyp.hypothesis_id,
            evidence="Observed p < 0.001 with 2.4x latency speedup.",
            p_value=0.0004,
            effect_size=1.85,
        )
        self.assertEqual(updated.status, HypothesisStatus.CONFIRMED)
        self.assertEqual(updated.p_value, 0.0004)
        self.assertEqual(self.engine.confirmed_count, 1)

    def test_falsify_hypothesis(self) -> None:
        hyp = self.engine.formulate("Cache reduces query latency", "Local LRU cache")
        updated = self.engine.falsify(
            hypothesis_id=hyp.hypothesis_id,
            reason="Lock contention on cache dictionary caused 15% slowdown.",
            p_value=0.72,
        )
        self.assertEqual(updated.status, HypothesisStatus.FALSIFIED)
        self.assertEqual(self.engine.falsified_count, 1)

    def test_retire_hypothesis(self) -> None:
        hyp = self.engine.formulate("Quantum sort is faster", "Theoretical quantum advantage")
        updated = self.engine.retire(hyp.hypothesis_id, reason="Classical hardware environment only")
        self.assertEqual(updated.status, HypothesisStatus.RETIRED)

    def test_filter_by_status(self) -> None:
        h1 = self.engine.formulate("Hyp 1", "Rat 1")
        h2 = self.engine.formulate("Hyp 2", "Rat 2")
        self.engine.confirm(h1.hypothesis_id, "Evidence 1", p_value=0.01)

        confirmed = self.engine.get_by_status(HypothesisStatus.CONFIRMED)
        proposed = self.engine.get_by_status(HypothesisStatus.PROPOSED)
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(len(proposed), 1)

    def test_serialization(self) -> None:
        hyp = self.engine.formulate("Statement A", "Rationale B")
        d = hyp.to_dict()
        self.assertEqual(d["statement"], "Statement A")
        self.assertEqual(d["rationale"], "Rationale B")
        self.assertEqual(d["status"], "PROPOSED")


if __name__ == "__main__":
    unittest.main()
