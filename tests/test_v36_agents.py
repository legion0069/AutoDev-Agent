"""
tests/test_v36_agents.py - Tests for the 10 Specialized AI Research Agents
AutoDev Version 3.6 Autonomous AI Research Lab.
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import unittest

from agents.algorithm_architect_agent import AlgorithmArchitectAgent
from agents.benchmark_engineer_agent import BenchmarkEngineerAgent
from agents.chief_scientist_agent import ChiefScientistAgent
from agents.experiment_designer_agent import ExperimentDesignerAgent
from agents.paper_author_agent import PaperAuthorAgent
from agents.patent_specialist_agent import PatentSpecialistAgent
from agents.peer_reviewer_agent import PeerReviewerAgent
from agents.principal_researcher_agent import PrincipalResearcherAgent
from agents.research_curator_agent import ResearchCuratorAgent
from agents.statistical_analyst_agent import StatisticalAnalystAgent
from core.algorithm_registry import AlgorithmDomain
from core.hypothesis_engine import HypothesisPriority
from core.peer_review_engine import ReviewRubric


class TestResearchAgents(unittest.TestCase):
    """Verifies operational actions, role competencies, and collaboration among all 10 AI research agents."""

    def test_chief_scientist_agent(self) -> None:
        agent = ChiefScientistAgent()
        self.assertEqual(agent.role, "Chief Scientist")
        charter = agent.set_research_charter("Advance Deterministic AI Computing", 500000.0)
        self.assertEqual(charter["focus_area"], "Advance Deterministic AI Computing")
        self.assertEqual(charter["budget_usd"], 500000.0)

        approval = agent.approve_experiment_proposal("exp_001", expected_impact="High", estimated_cost=12000.0)
        self.assertTrue(approval["approved"])

    def test_principal_researcher_agent(self) -> None:
        agent = PrincipalResearcherAgent()
        self.assertEqual(agent.role, "Principal Researcher")
        hyp = agent.propose_hypothesis(
            statement="Radix trees reduce lookup overhead by 40%",
            rationale="Compact key representation minimizes branch mispredictions",
            priority=HypothesisPriority.HIGH,
        )
        self.assertEqual(hyp["priority"], "HIGH")

        gap = agent.identify_literature_gap("Vector Search", ["FlatIndex", "IVFFlat"])
        self.assertIn("opportunity", gap)

    def test_experiment_designer_agent(self) -> None:
        agent = ExperimentDesignerAgent()
        self.assertEqual(agent.role, "Experiment Designer")
        design = agent.design_experiment(
            target_metric="latency_ms",
            sample_size=30,
            independent_vars=["cache_size", "thread_count"],
        )
        self.assertEqual(design["target_metric"], "latency_ms")
        self.assertEqual(design["sample_size"], 30)

    def test_statistical_analyst_agent(self) -> None:
        agent = StatisticalAnalystAgent()
        self.assertEqual(agent.role, "Statistical Analyst")
        sample_a = [10.0, 10.2, 9.9, 10.1, 10.0]
        sample_b = [5.0, 5.1, 4.9, 5.0, 5.2]
        analysis = agent.analyze_comparative_data(sample_a, sample_b, alpha=0.01)
        self.assertTrue(analysis["is_significant"])
        self.assertLess(analysis["p_value"], 0.01)

    def test_benchmark_engineer_agent(self) -> None:
        agent = BenchmarkEngineerAgent()
        self.assertEqual(agent.role, "Benchmark Engineer")
        bench = agent.profile_execution("quick_fn", lambda: sum(x * 2 for x in range(100)))
        self.assertEqual(bench["name"], "quick_fn")
        self.assertIn("latency_mean_ms", bench)

    def test_algorithm_architect_agent(self) -> None:
        agent = AlgorithmArchitectAgent()
        self.assertEqual(agent.role, "Algorithm Architect")
        design = agent.design_algorithm(
            name="BloomFilterLRU",
            domain=AlgorithmDomain.DATA_STRUCTURES,
            time_complexity="O(1)",
            space_complexity="O(M)",
        )
        self.assertEqual(design["name"], "BloomFilterLRU")
        self.assertEqual(design["time_complexity"], "O(1)")

    def test_peer_reviewer_agent(self) -> None:
        agent = PeerReviewerAgent(reviewer_id="rev_alpha")
        self.assertEqual(agent.role, "Peer Reviewer")
        rubric = ReviewRubric(novelty_score=8.0, soundness_score=9.0, clarity_score=8.5, empirical_rigor_score=9.0)
        review = agent.review_paper(
            paper_id="paper_999",
            rubric=rubric,
            comments="Extremely thorough empirical benchmarks.",
        )
        self.assertEqual(review["reviewer_id"], "rev_alpha")
        self.assertEqual(review["recommendation"], "ACCEPT")

    def test_patent_specialist_agent(self) -> None:
        agent = PatentSpecialistAgent()
        self.assertEqual(agent.role, "Patent Specialist")
        eval_result = agent.evaluate_patentability(novelty_score=0.85, non_obviousness_score=0.9, utility_score=0.95)
        self.assertTrue(eval_result["is_patentable"])

        draft = agent.draft_patent_claims(
            title="METHOD FOR ASYNCHRONOUS GRAPH PARTITIONING",
            independent_elements=["partitioning graph into k subgraphs", "dispatching subgraphs to worker nodes"],
        )
        self.assertEqual(len(draft["claims"]), 2)

    def test_paper_author_agent(self) -> None:
        agent = PaperAuthorAgent()
        self.assertEqual(agent.role, "Paper Author")
        manuscript = agent.draft_manuscript(
            title="Scalable Multi-Agent Consensus Algorithms",
            abstract="We investigate consensus latency across decentralized agent topologies.",
            keywords=["consensus", "decentralized", "agents"],
        )
        self.assertEqual(manuscript["title"], "Scalable Multi-Agent Consensus Algorithms")
        self.assertEqual(len(manuscript["keywords"]), 3)

    def test_research_curator_agent(self) -> None:
        agent = ResearchCuratorAgent()
        self.assertEqual(agent.role, "Research Curator")
        entry = agent.archive_findings(
            experiment_id="exp_curate_1",
            summary="Established baseline sorting metrics",
            tags=["sorting", "baseline"],
        )
        self.assertEqual(entry["experiment_id"], "exp_curate_1")
        self.assertIn("sorting", entry["tags"])


if __name__ == "__main__":
    unittest.main()
