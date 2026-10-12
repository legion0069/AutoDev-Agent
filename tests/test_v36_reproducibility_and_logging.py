"""
tests/test_v36_reproducibility_and_logging.py - Tests for Reproducibility, ScientificLogger & ResearchMemory
AutoDev Version 3.6 Autonomous AI Research Lab.
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import unittest

from core.reproducibility_manager import (
    ExperimentRunManifest,
    ReplayResult,
    ReproducibilityManager,
)
from core.research_memory import (
    FutureWorkItem,
    ResearchFailure,
    ResearchIdea,
    ResearchMemory,
    ResearchNote,
    ResearchSuccess,
)
from core.scientific_logger import (
    ScientificEventType,
    ScientificLogger,
    ScientificLogRecord,
)


class TestReproducibilityManager(unittest.TestCase):
    """Verifies environment capture, seed management, deterministic runs, and replay validation."""

    def setUp(self) -> None:
        self.manager = ReproducibilityManager()

    def test_capture_environment(self) -> None:
        env = self.manager.capture_environment()
        self.assertIn("python_version", env)
        self.assertIn("platform", env)
        self.assertIn("system", env)

    def test_create_manifest(self) -> None:
        manifest = self.manager.create_manifest(
            experiment_id="exp_001",
            code_hash="abcdef1234567890",
            parameters={"batch_size": 32, "lr": 0.001},
            seed=42,
        )
        self.assertIsInstance(manifest, ExperimentRunManifest)
        self.assertEqual(manifest.experiment_id, "exp_001")
        self.assertEqual(manifest.seed, 42)

    def test_verify_replay_match(self) -> None:
        manifest = self.manager.create_manifest(
            experiment_id="exp_002",
            code_hash="hash123",
            parameters={"threshold": 0.5},
            seed=100,
        )

        def deterministic_fn(params):
            return {"accuracy": 0.95, "loss": 0.05}

        # Original execution output
        original_output = deterministic_fn({"threshold": 0.5})

        replay = self.manager.verify_replay(
            manifest=manifest,
            execution_fn=deterministic_fn,
            expected_output=original_output,
        )
        self.assertIsInstance(replay, ReplayResult)
        self.assertTrue(replay.reproduced)
        self.assertAlmostEqual(replay.drift_score, 0.0)

    def test_verify_replay_drift(self) -> None:
        manifest = self.manager.create_manifest(
            experiment_id="exp_003",
            code_hash="hash456",
            parameters={},
            seed=100,
        )

        def drifting_fn(params):
            return {"metric": 50.0}

        replay = self.manager.verify_replay(
            manifest=manifest,
            execution_fn=drifting_fn,
            expected_output={"metric": 100.0},
        )
        self.assertFalse(replay.reproduced)
        self.assertGreater(replay.drift_score, 0.0)


class TestScientificLogger(unittest.TestCase):
    """Verifies cryptographic audit chain, SHA-256 verification, and tamper detection."""

    def setUp(self) -> None:
        self.logger = ScientificLogger()

    def test_log_event(self) -> None:
        rec = self.logger.log_event(
            event_type=ScientificEventType.EXPERIMENT_START,
            experiment_id="exp_test",
            data={"module": "sorting", "candidate": "quicksort"},
        )
        self.assertIsInstance(rec, ScientificLogRecord)
        self.assertEqual(rec.event_type, ScientificEventType.EXPERIMENT_START)
        self.assertEqual(self.logger.total_events, 1)

    def test_cryptographic_chain_integrity(self) -> None:
        self.logger.log_event(ScientificEventType.HYPOTHESIS_FORMULATED, "exp_1", {"hyp": "H1"})
        self.logger.log_event(ScientificEventType.BENCHMARK_EXECUTED, "exp_1", {"p95": 12.4})
        self.logger.log_event(ScientificEventType.STATISTICAL_TEST_PASSED, "exp_1", {"p": 0.001})

        valid, broken_idx = self.logger.verify_chain_integrity()
        self.assertTrue(valid)
        self.assertIsNone(broken_idx)

    def test_tamper_detection(self) -> None:
        self.logger.log_event(ScientificEventType.EXPERIMENT_START, "exp_tamper", {"a": 1})
        self.logger.log_event(ScientificEventType.BENCHMARK_EXECUTED, "exp_tamper", {"a": 2})
        self.logger.log_event(ScientificEventType.EXPERIMENT_CONCLUDED, "exp_tamper", {"a": 3})

        # Tamper with an event in memory
        self.logger._events[1].data = {"a": 999999}  # altered payload

        valid, broken_idx = self.logger.verify_chain_integrity()
        self.assertFalse(valid)
        self.assertEqual(broken_idx, 1)


class TestResearchMemory(unittest.TestCase):
    """Verifies long-term scientific knowledge storage: ideas, failures, successes, and future work."""

    def setUp(self) -> None:
        self.memory = ResearchMemory()

    def test_record_idea(self) -> None:
        idea = self.memory.add_idea(
            title="Bloom Filter Deduplication",
            description="Use counting bloom filters to deduplicate high-frequency event streams",
            tags=["probabilistic", "streaming"],
        )
        self.assertIsInstance(idea, ResearchIdea)
        self.assertEqual(len(self.memory.get_ideas()), 1)

    def test_record_failure(self) -> None:
        fail = self.memory.record_failure(
            hypothesis_statement="Lock-free queue improves multi-core throughput by 3x",
            root_cause="Cache-line bouncing and false sharing on atomic CAS pointers",
            lessons_learned="Pad queue head and tail pointers to distinct 64-byte cache lines",
        )
        self.assertIsInstance(fail, ResearchFailure)
        self.assertEqual(len(self.memory.get_failures()), 1)

    def test_record_success(self) -> None:
        succ = self.memory.record_success(
            innovation_name="ZeroCopySerializer",
            impact_summary="Achieved 4.2x serialization throughput increase with zero allocations",
            reproducibility_hash="sha256_mock_hash",
        )
        self.assertIsInstance(succ, ResearchSuccess)
        self.assertEqual(len(self.memory.get_successes()), 1)

    def test_search_notes(self) -> None:
        self.memory.add_note("Note about SIMD vector instructions on AVX2", tags=["hardware", "simd"])
        self.memory.add_note("Note about database B+ tree index page sizing", tags=["storage"])

        matches = self.memory.search_notes("SIMD")
        self.assertEqual(len(matches), 1)
        self.assertIn("AVX2", matches[0].content)

    def test_future_work(self) -> None:
        fw = self.memory.add_future_work(
            title="Investigate GPU acceleration via WebGPU",
            priority="HIGH",
        )
        self.assertIsInstance(fw, FutureWorkItem)
        self.assertEqual(len(self.memory.get_future_work()), 1)


if __name__ == "__main__":
    unittest.main()
