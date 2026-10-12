"""
tests/test_v36_novelty_and_optimization.py - Tests for NoveltyDetector & OptimizationEngine
AutoDev Version 3.6 Autonomous AI Research Lab.
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import unittest

from core.novelty_detector import (
    NoveltyAssessment,
    NoveltyClassification,
    NoveltyDetector,
    SolutionArtifact,
)
from core.optimization_engine import (
    OptimizationEngine,
    OptimizationProblem,
    OptimizationResult,
    OptimizationStrategy,
    ParameterSpec,
)


class TestNoveltyDetector(unittest.TestCase):
    """Verifies syntactic and structural novelty detection against solution baselines."""

    def setUp(self) -> None:
        self.detector = NoveltyDetector()
        # Seed detector with an existing standard solution
        self.detector.register_prior_art(
            SolutionArtifact(
                artifact_id="prior_001",
                name="standard_search",
                code="""
def search_items(items, target):
    for item in items:
        if item == target:
            return True
    return False
""",
            )
        )

    def test_identical_code_detection(self) -> None:
        identical_code = """
def search_items(items, target):
    for item in items:
        if item == target:
            return True
    return False
"""
        assessment = self.detector.assess_novelty(
            candidate_code=identical_code,
            candidate_name="duplicate_search",
        )
        self.assertIsInstance(assessment, NoveltyAssessment)
        self.assertEqual(assessment.classification, NoveltyClassification.DUPLICATE)
        self.assertAlmostEqual(assessment.novelty_score, 0.0, delta=0.05)

    def test_minor_variable_rename_trivial(self) -> None:
        trivial_code = """
def search_items(lst, elem):
    for x in lst:
        if x == elem:
            return True
    return False
"""
        assessment = self.detector.assess_novelty(
            candidate_code=trivial_code,
            candidate_name="trivial_rename",
        )
        self.assertIn(
            assessment.classification,
            [NoveltyClassification.TRIVIAL_VARIANT, NoveltyClassification.INCREMENTAL_IMPROVEMENT],
        )
        self.assertLess(assessment.novelty_score, 0.5)

    def test_breakthrough_algorithmic_novelty(self) -> None:
        novel_code = """
import bisect

class SegmentTreeIndex:
    def __init__(self, data):
        self.tree = [0] * (4 * len(data))
        self._build(data, 1, 0, len(data) - 1)

    def _build(self, data, node, start, end):
        if start == end:
            self.tree[node] = data[start]
            return
        mid = (start + end) // 2
        self._build(data, 2 * node, start, mid)
        self._build(data, 2 * node + 1, mid + 1, end)
        self.tree[node] = min(self.tree[2 * node], self.tree[2 * node + 1])
"""
        assessment = self.detector.assess_novelty(
            candidate_code=novel_code,
            candidate_name="segment_tree_index",
        )
        self.assertIn(
            assessment.classification,
            [NoveltyClassification.SIGNIFICANT_INNOVATION, NoveltyClassification.BREAKTHROUGH],
        )
        self.assertGreater(assessment.novelty_score, 0.7)

    def test_ast_similarity_robust_to_whitespace(self) -> None:
        code_a = "def add(x, y):\n    return x + y\n"
        code_b = "def add(x,y):\n\n    return x+y"
        sim = self.detector.compute_ast_structural_similarity(code_a, code_b)
        self.assertAlmostEqual(sim, 1.0, places=2)

    def test_invalid_syntax_fallback(self) -> None:
        bad_code = "def syntax_error(::: return"
        assessment = self.detector.assess_novelty(bad_code, "bad_syntax")
        self.assertIsInstance(assessment, NoveltyAssessment)
        self.assertGreaterEqual(assessment.novelty_score, 0.0)


class TestOptimizationEngine(unittest.TestCase):
    """Verifies hyperparameter and algorithmic tuning using heuristic search strategies."""

    def setUp(self) -> None:
        self.engine = OptimizationEngine()

    def test_grid_search_quadratic(self) -> None:
        # Minimize (x - 3)^2 => minimum at x = 3
        problem = OptimizationProblem(
            name="quadratic_min",
            objective_function=lambda p: (p["x"] - 3.0) ** 2,
            parameters=[
                ParameterSpec(name="x", param_type="float", min_val=0.0, max_val=6.0, step=1.0)
            ],
            strategy=OptimizationStrategy.GRID_SEARCH,
            maximize=False,
        )
        res = self.engine.optimize(problem)
        self.assertIsInstance(res, OptimizationResult)
        self.assertEqual(res.best_parameters["x"], 3.0)
        self.assertAlmostEqual(res.best_score, 0.0)

    def test_random_search_sphere(self) -> None:
        # Maximize -(x^2 + y^2) => maximum at (0, 0)
        problem = OptimizationProblem(
            name="sphere_max",
            objective_function=lambda p: -(p["x"] ** 2 + p["y"] ** 2),
            parameters=[
                ParameterSpec(name="x", param_type="float", min_val=-5.0, max_val=5.0),
                ParameterSpec(name="y", param_type="float", min_val=-5.0, max_val=5.0),
            ],
            strategy=OptimizationStrategy.RANDOM_SEARCH,
            max_iterations=100,
            maximize=True,
            seed=42,
        )
        res = self.engine.optimize(problem)
        self.assertGreater(res.best_score, -5.0)
        self.assertEqual(len(res.history), 100)

    def test_hill_climbing_discrete(self) -> None:
        # Maximize 10 - |x - 7|
        problem = OptimizationProblem(
            name="peak_search",
            objective_function=lambda p: 10.0 - abs(p["val"] - 7),
            parameters=[
                ParameterSpec(name="val", param_type="int", min_val=0, max_val=15, step=1)
            ],
            strategy=OptimizationStrategy.HILL_CLIMBING,
            max_iterations=50,
            maximize=True,
            seed=123,
        )
        res = self.engine.optimize(problem)
        self.assertEqual(res.best_parameters["val"], 7)
        self.assertEqual(res.best_score, 10.0)

    def test_simulated_annealing(self) -> None:
        # Rastrigin-like 1D or multimodal function
        problem = OptimizationProblem(
            name="annealing_test",
            objective_function=lambda p: -(p["x"] - 2) ** 2,
            parameters=[
                ParameterSpec(name="x", param_type="float", min_val=-10.0, max_val=10.0, step=0.1)
            ],
            strategy=OptimizationStrategy.SIMULATED_ANNEALING,
            max_iterations=100,
            maximize=True,
            seed=999,
        )
        res = self.engine.optimize(problem)
        self.assertAlmostEqual(res.best_parameters["x"], 2.0, delta=1.0)

    def test_categorical_parameter(self) -> None:
        problem = OptimizationProblem(
            name="algorithm_choice",
            objective_function=lambda p: 100.0 if p["algo"] == "quicksort" else 50.0,
            parameters=[
                ParameterSpec(
                    name="algo",
                    param_type="categorical",
                    choices=["bubblesort", "insertionsort", "quicksort"],
                )
            ],
            strategy=OptimizationStrategy.GRID_SEARCH,
            maximize=True,
        )
        res = self.engine.optimize(problem)
        self.assertEqual(res.best_parameters["algo"], "quicksort")
        self.assertEqual(res.best_score, 100.0)


if __name__ == "__main__":
    unittest.main()
