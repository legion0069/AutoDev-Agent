"""
tests/test_v36_registry_and_ab_testing.py - Tests for AlgorithmRegistry & ABTestingEngine
AutoDev Version 3.6 Autonomous AI Research Lab.
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import unittest

from core.ab_testing_engine import (
    ABExperiment,
    ABTestingEngine,
    ExperimentArm,
)
from core.algorithm_registry import (
    AlgorithmAdoptionStatus,
    AlgorithmDomain,
    AlgorithmRecord,
    AlgorithmRegistry,
)


class TestAlgorithmRegistry(unittest.TestCase):
    """Verifies algorithm registration, versioning, status updates, and catalog queries."""

    def setUp(self) -> None:
        self.registry = AlgorithmRegistry()

    def test_register_algorithm(self) -> None:
        algo = self.registry.register(
            name="RadixTrieIndex",
            domain=AlgorithmDomain.DATA_STRUCTURES,
            version="1.0.0",
            description="Compressed prefix tree index for substring search",
            code="class RadixTrieIndex: pass",
            time_complexity="O(K)",
            space_complexity="O(N * K)",
            author="AlgorithmArchitectAgent",
        )
        self.assertIsInstance(algo, AlgorithmRecord)
        self.assertEqual(algo.name, "RadixTrieIndex")
        self.assertEqual(algo.adoption_status, AlgorithmAdoptionStatus.CANDIDATE)
        self.assertEqual(self.registry.total_count, 1)

    def test_version_progression(self) -> None:
        self.registry.register(name="CacheMap", domain=AlgorithmDomain.SYSTEMS, version="1.0.0")
        self.registry.register(name="CacheMap", domain=AlgorithmDomain.SYSTEMS, version="1.1.0")
        versions = self.registry.get_versions("CacheMap")
        self.assertEqual(len(versions), 2)
        latest = self.registry.get_latest("CacheMap")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.version, "1.1.0")

    def test_update_status(self) -> None:
        algo = self.registry.register(name="SkipList", domain=AlgorithmDomain.DATA_STRUCTURES)
        self.registry.update_status(algo.algorithm_id, AlgorithmAdoptionStatus.BENCHMARKED)
        self.assertEqual(self.registry.get(algo.algorithm_id).adoption_status, AlgorithmAdoptionStatus.BENCHMARKED)

        self.registry.promote_to_production(algo.algorithm_id)
        self.assertEqual(self.registry.get(algo.algorithm_id).adoption_status, AlgorithmAdoptionStatus.PRODUCTION_READY)

    def test_deprecate_algorithm(self) -> None:
        algo = self.registry.register(name="SlowBubbleSort", domain=AlgorithmDomain.SEARCH_SORT)
        self.registry.deprecate(algo.algorithm_id, reason="Superseded by Timsort")
        self.assertEqual(self.registry.get(algo.algorithm_id).adoption_status, AlgorithmAdoptionStatus.DEPRECATED)

    def test_filter_by_domain(self) -> None:
        self.registry.register(name="AStar", domain=AlgorithmDomain.GRAPH_ALGORITHMS)
        self.registry.register(name="Dijkstra", domain=AlgorithmDomain.GRAPH_ALGORITHMS)
        self.registry.register(name="AES256", domain=AlgorithmDomain.CRYPTOGRAPHY)

        graphs = self.registry.get_by_domain(AlgorithmDomain.GRAPH_ALGORITHMS)
        cryptos = self.registry.get_by_domain(AlgorithmDomain.CRYPTOGRAPHY)
        self.assertEqual(len(graphs), 2)
        self.assertEqual(len(cryptos), 1)

    def test_search_by_keyword(self) -> None:
        self.registry.register(name="FastFourierTransform", domain=AlgorithmDomain.NUMERICAL, description="FFT signal analysis")
        self.registry.register(name="LevenshteinMetric", domain=AlgorithmDomain.NATURAL_LANGUAGE, description="String edit distance")

        matches = self.registry.search("signal")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].name, "FastFourierTransform")


class TestABTestingEngine(unittest.TestCase):
    """Verifies A/B split-testing, metric recording, and significance testing."""

    def setUp(self) -> None:
        self.ab_engine = ABTestingEngine()

    def test_create_experiment(self) -> None:
        exp = self.ab_engine.create_experiment(
            name="search_algorithm_comparison",
            description="Comparing binary search vs interpolation search",
            traffic_split={"control": 0.5, "treatment": 0.5},
            metric_of_interest="latency_ms",
            higher_is_better=False,
        )
        self.assertIsInstance(exp, ABExperiment)
        self.assertEqual(exp.name, "search_algorithm_comparison")
        self.assertEqual(len(exp.arms), 2)

    def test_traffic_assignment_deterministic(self) -> None:
        exp = self.ab_engine.create_experiment(
            name="user_routing",
            traffic_split={"A": 0.5, "B": 0.5},
        )
        arm_user1_call1 = self.ab_engine.assign_arm(exp.experiment_id, entity_id="user_123")
        arm_user1_call2 = self.ab_engine.assign_arm(exp.experiment_id, entity_id="user_123")
        self.assertEqual(arm_user1_call1, arm_user1_call2)

    def test_record_observations_and_evaluate(self) -> None:
        exp = self.ab_engine.create_experiment(
            name="compression_eval",
            traffic_split={"gzip": 0.5, "zstandard": 0.5},
            metric_of_interest="duration_ms",
            higher_is_better=False,
        )

        # Record fast measurements for zstandard, slower for gzip
        for _ in range(30):
            self.ab_engine.record_observation(exp.experiment_id, "gzip", 10.0 + (_ % 3))
            self.ab_engine.record_observation(exp.experiment_id, "zstandard", 4.0 + (_ % 2))

        result = self.ab_engine.evaluate(exp.experiment_id)
        self.assertTrue(result["is_conclusive"])
        self.assertEqual(result["winner"], "zstandard")
        self.assertLess(result["p_value"], 0.05)

    def test_conclude_experiment(self) -> None:
        exp = self.ab_engine.create_experiment(name="ui_flow", traffic_split={"v1": 0.5, "v2": 0.5})
        for _ in range(10):
            self.ab_engine.record_observation(exp.experiment_id, "v1", 100.0)
            self.ab_engine.record_observation(exp.experiment_id, "v2", 150.0)

        concluded = self.ab_engine.conclude(exp.experiment_id)
        self.assertEqual(concluded.status, "completed")
        self.assertIsNotNone(concluded.winner)


if __name__ == "__main__":
    unittest.main()
