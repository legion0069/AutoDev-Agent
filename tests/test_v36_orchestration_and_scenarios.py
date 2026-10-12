"""
tests/test_v36_orchestration_and_scenarios.py - End-to-End Scientific Orchestration & Scenarios
AutoDev Version 3.6 Autonomous AI Research Lab.
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import unittest

from core.experiment_engine import (
    ExperimentEngine,
    ExperimentStage,
    ScientificExperiment,
)
from core.experiment_scheduler import (
    ExperimentScheduler,
    QueuedExperiment,
    SchedulePriority,
)
from core.orchestrator import AutoDevOrchestrator, Orchestrator
from core.research_lab import (
    GlobalResearchMetrics,
    ResearchCycleSummary,
    ResearchLab,
)


class TestExperimentEngineAndScheduler(unittest.TestCase):
    """Verifies execution lifecycle in ExperimentEngine and prioritized queueing in ExperimentScheduler."""

    def test_experiment_engine_lifecycle(self) -> None:
        engine = ExperimentEngine()
        exp = engine.create_experiment(
            name="memory_allocator_bench",
            hypothesis_statement="Arena allocator reduces allocation latency by 60%",
            candidate_code="class ArenaAllocator: pass",
            baseline_code="class StandardAllocator: pass",
        )
        self.assertIsInstance(exp, ScientificExperiment)
        self.assertEqual(exp.stage, ExperimentStage.PROPOSED)

        # Transition stages
        engine.transition_stage(exp.experiment_id, ExperimentStage.DESIGNED)
        self.assertEqual(engine.get_experiment(exp.experiment_id).stage, ExperimentStage.DESIGNED)

        engine.transition_stage(exp.experiment_id, ExperimentStage.EXECUTING)
        engine.transition_stage(exp.experiment_id, ExperimentStage.COMPLETED)
        self.assertEqual(engine.get_experiment(exp.experiment_id).stage, ExperimentStage.COMPLETED)

    def test_experiment_scheduler_priority_order(self) -> None:
        scheduler = ExperimentScheduler()
        q_low = scheduler.enqueue(
            experiment_id="exp_low",
            name="Low Priority Exp",
            priority=SchedulePriority.LOW,
            task_fn=lambda: {"res": "low"},
        )
        q_urgent = scheduler.enqueue(
            experiment_id="exp_urgent",
            name="Urgent Exp",
            priority=SchedulePriority.CRITICAL,
            task_fn=lambda: {"res": "urgent"},
        )
        q_normal = scheduler.enqueue(
            experiment_id="exp_normal",
            name="Normal Exp",
            priority=SchedulePriority.NORMAL,
            task_fn=lambda: {"res": "normal"},
        )

        # First to dispatch should be critical, then normal, then low
        nxt1 = scheduler.get_next()
        self.assertIsNotNone(nxt1)
        self.assertEqual(nxt1.experiment_id, "exp_urgent")

        nxt2 = scheduler.get_next()
        self.assertIsNotNone(nxt2)
        self.assertEqual(nxt2.experiment_id, "exp_normal")

        nxt3 = scheduler.get_next()
        self.assertIsNotNone(nxt3)
        self.assertEqual(nxt3.experiment_id, "exp_low")


class TestResearchLabAutonomousCycle(unittest.TestCase):
    """Verifies end-to-end 10-step autonomous scientific research cycle in ResearchLab."""

    def setUp(self) -> None:
        self.lab = ResearchLab()

    def test_conduct_research_cycle_success(self) -> None:
        candidate_code = """
def optimized_sum(n):
    return (n * (n + 1)) // 2
"""
        baseline_code = """
def baseline_sum(n):
    total = 0
    for i in range(1, n + 1):
        total += i
    return total
"""
        cycle = self.lab.conduct_research_cycle(
            module_name="arithmetic_summation",
            candidate_code=candidate_code,
            baseline_code=baseline_code,
        )

        self.assertIsInstance(cycle, ResearchCycleSummary)
        self.assertTrue(cycle.success)
        self.assertEqual(cycle.module_name, "arithmetic_summation")
        self.assertIsNotNone(cycle.hypothesis_id)
        self.assertIsNotNone(cycle.paper_id)
        self.assertIsNotNone(cycle.patent_application_id)
        self.assertGreater(cycle.statistical_p_value, 0.0)

    def test_global_metrics_aggregation(self) -> None:
        # Run a cycle
        self.lab.conduct_research_cycle(
            module_name="matrix_ops",
            candidate_code="def dot(a, b): return sum(x * y for x, y in zip(a, b))",
            baseline_code="def dot_slow(a, b): return 0",
        )
        metrics = self.lab.compute_global_metrics()
        self.assertIsInstance(metrics, GlobalResearchMetrics)
        self.assertGreaterEqual(metrics.total_hypotheses_tested, 1)
        self.assertGreaterEqual(metrics.papers_generated, 1)
        self.assertGreaterEqual(metrics.patents_filed, 1)
        self.assertTrue(metrics.audit_chain_valid)

    def test_search_and_retrieval(self) -> None:
        self.lab.conduct_research_cycle(
            module_name="compression",
            candidate_code="def compress(d): return d",
            baseline_code="def compress_base(d): return d",
        )
        papers = self.lab.paper_generator.get_all_papers()
        self.assertGreaterEqual(len(papers), 1)

        patents = self.lab.patent_generator.get_all_applications()
        self.assertGreaterEqual(len(patents), 1)


class TestOrchestratorIntegrationV36(unittest.TestCase):
    """Verifies AutoDev Orchestrator integration with Version 3.6 Research Lab."""

    def setUp(self) -> None:
        self.orchestrator = Orchestrator()

    def test_orchestrator_research_lab_property(self) -> None:
        self.assertIsNotNone(self.orchestrator.research_lab)
        self.assertEqual(self.orchestrator.research_lab.lab_name, "AutoDev Autonomous AI Research Lab")

    def test_conduct_autonomous_research_cycle_facade(self) -> None:
        res = self.orchestrator.conduct_autonomous_research_cycle(
            module_name="facade_search",
            candidate_code="def fast_search(): pass",
            baseline_code="def slow_search(): pass",
        )
        self.assertTrue(res["success"])
        self.assertIn("cycle_id", res)
        self.assertIn("paper_id", res)
        self.assertIn("patent_application_id", res)

    def test_query_research_metrics_facade(self) -> None:
        self.orchestrator.conduct_autonomous_research_cycle()
        metrics = self.orchestrator.query_research_metrics()
        self.assertIn("total_hypotheses_tested", metrics)
        self.assertIn("audit_chain_valid", metrics)
        self.assertTrue(metrics["audit_chain_valid"])

    def test_query_patent_portfolio_facade(self) -> None:
        self.orchestrator.conduct_autonomous_research_cycle()
        patents = self.orchestrator.query_patent_portfolio()
        self.assertGreaterEqual(len(patents), 1)
        self.assertIn("title", patents[0])

    def test_query_paper_repository_facade(self) -> None:
        self.orchestrator.conduct_autonomous_research_cycle()
        papers = self.orchestrator.query_paper_repository()
        self.assertGreaterEqual(len(papers), 1)
        self.assertIn("abstract", papers[0])

    def test_backwards_compatibility_alias(self) -> None:
        self.assertIs(AutoDevOrchestrator, Orchestrator)


if __name__ == "__main__":
    unittest.main()
