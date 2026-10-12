"""
tests/test_v36_paper_and_patent_generation.py - Tests for PaperGenerator, PatentGenerator & PeerReviewEngine
AutoDev Version 3.6 Autonomous AI Research Lab.
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import unittest

from core.paper_generator import (
    PaperGenerator,
    PaperSectionType,
    PaperTemplate,
    ScientificPaper,
)
from core.patent_generator import (
    PatentApplication,
    PatentClaim,
    PatentClaimType,
    PatentGenerator,
)
from core.peer_review_engine import (
    EditorialDecision,
    PeerReviewEngine,
    ReviewEvaluation,
    ReviewRubric,
)


class TestPaperGenerator(unittest.TestCase):
    """Verifies scientific paper structuring, section generation, and markdown export."""

    def setUp(self) -> None:
        self.generator = PaperGenerator()

    def test_create_paper(self) -> None:
        paper = self.generator.create_paper(
            title="Deterministic Memory Replay in Distributed Multi-Agent Systems",
            authors=["AutoDev Chief Scientist", "Research Team Alpha"],
            abstract="We present a formal framework for tamper-evident deterministic memory replay...",
            keywords=["multi-agent", "determinism", "reproducibility"],
        )
        self.assertIsInstance(paper, ScientificPaper)
        self.assertEqual(paper.title, "Deterministic Memory Replay in Distributed Multi-Agent Systems")
        self.assertEqual(len(paper.authors), 2)

    def test_add_sections(self) -> None:
        paper = self.generator.create_paper(title="Test Paper", authors=["Author"])
        self.generator.add_section(
            paper.paper_id,
            section_type=PaperSectionType.INTRODUCTION,
            title="1. Introduction",
            content="Modern multi-agent architectures face reproducibility challenges.",
        )
        self.generator.add_section(
            paper.paper_id,
            section_type=PaperSectionType.METHODOLOGY,
            title="2. Methodology",
            content="We formalize our approach via cryptographic state chains.",
        )
        p = self.generator.get_paper(paper.paper_id)
        self.assertEqual(len(p.sections), 2)

    def test_render_markdown(self) -> None:
        paper = self.generator.create_paper(
            title="Markdown Synthesis Test",
            authors=["Scientist A"],
            abstract="Abstract summary text.",
        )
        self.generator.add_section(paper.paper_id, PaperSectionType.RESULTS, "Results", "Observed p < 0.001.")

        md = self.generator.render_markdown(paper.paper_id)
        self.assertIn("# Markdown Synthesis Test", md)
        self.assertIn("## Abstract", md)
        self.assertIn("## Results", md)
        self.assertIn("Observed p < 0.001.", md)


class TestPatentGenerator(unittest.TestCase):
    """Verifies patent claim generation, statutory structure, and patentability evaluation."""

    def setUp(self) -> None:
        self.generator = PatentGenerator()

    def test_draft_patent(self) -> None:
        patent = self.generator.draft_patent(
            title="SYSTEM AND METHOD FOR AUTONOMOUS PEER-REVIEWED ALGORITHM DISCOVERY",
            inventors=["AutoDev Research System", "Lead Scientist"],
            abstract="A computer-implemented method for autonomous hypothesis testing and validation...",
            field_of_invention="Autonomous Software Engineering and Statistical Verification",
        )
        self.assertIsInstance(patent, PatentApplication)
        self.assertEqual(len(patent.inventors), 2)

    def test_add_claims(self) -> None:
        patent = self.generator.draft_patent(title="Patent Claims Test", inventors=["Inventor"])
        c1 = self.generator.add_claim(
            patent.application_id,
            claim_type=PatentClaimType.INDEPENDENT,
            claim_text="A method for autonomous algorithmic discovery comprising: generating a candidate...",
        )
        c2 = self.generator.add_claim(
            patent.application_id,
            claim_type=PatentClaimType.DEPENDENT,
            claim_text="The method of claim 1, wherein said verification comprises Welch's t-test...",
            depends_on=c1.claim_number,
        )
        app = self.generator.get_application(patent.application_id)
        self.assertEqual(len(app.claims), 2)
        self.assertEqual(app.claims[0].claim_type, PatentClaimType.INDEPENDENT)
        self.assertEqual(app.claims[1].claim_type, PatentClaimType.DEPENDENT)

    def test_render_patent_text(self) -> None:
        patent = self.generator.draft_patent(title="Text Render Test", inventors=["Inventor X"])
        self.generator.add_claim(patent.application_id, PatentClaimType.INDEPENDENT, "Claim 1 statement.")
        text = self.generator.render_specification(patent.application_id)
        self.assertIn("PATENT APPLICATION SPECIFICATION", text)
        self.assertIn("CLAIMS", text)


class TestPeerReviewEngine(unittest.TestCase):
    """Verifies peer review rubric scoring, reviewer submission, and editorial decisions."""

    def setUp(self) -> None:
        self.engine = PeerReviewEngine()

    def test_submit_review(self) -> None:
        rubric = ReviewRubric(
            novelty_score=8.5,
            soundness_score=9.0,
            clarity_score=8.0,
            empirical_rigor_score=9.5,
        )
        review = self.engine.submit_review(
            paper_id="paper_101",
            reviewer_name="Reviewer 1",
            rubric=rubric,
            comments="Thorough paper with solid mathematical foundation.",
            recommendation=EditorialDecision.ACCEPT,
        )
        self.assertIsInstance(review, ReviewEvaluation)
        self.assertGreater(review.rubric.overall_score, 8.0)

    def test_editorial_consensus_accept(self) -> None:
        # Submit 3 favorable reviews
        self.engine.submit_review(
            paper_id="paper_200",
            reviewer_name="Rev A",
            rubric=ReviewRubric(8.0, 8.5, 8.0, 9.0),
            comments="Good",
            recommendation=EditorialDecision.ACCEPT,
        )
        self.engine.submit_review(
            paper_id="paper_200",
            reviewer_name="Rev B",
            rubric=ReviewRubric(9.0, 9.0, 8.5, 9.5),
            comments="Strong",
            recommendation=EditorialDecision.ACCEPT,
        )

        decision = self.engine.determine_editorial_decision("paper_200")
        self.assertEqual(decision, EditorialDecision.ACCEPT)

    def test_editorial_consensus_reject(self) -> None:
        # Submit 2 rejecting reviews
        self.engine.submit_review(
            paper_id="paper_300",
            reviewer_name="Rev X",
            rubric=ReviewRubric(3.0, 4.0, 5.0, 3.5),
            comments="Lacks rigor",
            recommendation=EditorialDecision.REJECT,
        )
        self.engine.submit_review(
            paper_id="paper_300",
            reviewer_name="Rev Y",
            rubric=ReviewRubric(4.0, 3.5, 4.0, 4.0),
            comments="Flawed stats",
            recommendation=EditorialDecision.REJECT,
        )

        decision = self.engine.determine_editorial_decision("paper_300")
        self.assertEqual(decision, EditorialDecision.REJECT)


if __name__ == "__main__":
    unittest.main()
