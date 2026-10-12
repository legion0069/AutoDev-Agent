"""
core/peer_review_engine.py - Academic Peer Review & Scientific Consensus Arbitration Engine (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import enum
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class ReviewRecommendation(str, enum.Enum):
    """Formal editorial decision on submitted manuscripts or patent proposals."""
    ACCEPT = "ACCEPT"
    MINOR_REVISION = "MINOR_REVISION"
    MAJOR_REVISION = "MAJOR_REVISION"
    REJECT = "REJECT"


@dataclass
class IndividualReview:
    """Rigorous academic assessment from an individual reviewer agent."""
    review_id: str
    paper_id: str
    reviewer: str
    novelty: float                        # Scale 1.0 (trivial) to 5.0 (breakthrough)
    correctness: float                    # Scale 1.0 (fatally flawed) to 5.0 (rigorously proven)
    reproducibility: float                # Scale 1.0 (unreplicable) to 5.0 (deterministically verified)
    experimental_quality: float           # Scale 1.0 (anecdotal) to 5.0 (extensive DoE)
    writing_quality: float                # Scale 1.0 (incomprehensible) to 5.0 (publication grade)
    statistical_soundness: float          # Scale 1.0 (spurious) to 5.0 (proper power & alpha)
    comments: str
    recommendation: ReviewRecommendation
    created_at: float = field(default_factory=time.time)

    @property
    def composite_score(self) -> float:
        return (
            0.20 * self.novelty +
            0.20 * self.correctness +
            0.20 * self.reproducibility +
            0.15 * self.experimental_quality +
            0.10 * self.writing_quality +
            0.15 * self.statistical_soundness
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "paper_id": self.paper_id,
            "reviewer": self.reviewer,
            "novelty": self.novelty,
            "correctness": self.correctness,
            "reproducibility": self.reproducibility,
            "experimental_quality": self.experimental_quality,
            "writing_quality": self.writing_quality,
            "statistical_soundness": self.statistical_soundness,
            "composite_score": round(self.composite_score, 2),
            "recommendation": self.recommendation.value,
            "comments": self.comments,
        }


@dataclass
class ConsensusReview:
    """Editorial consensus synthesis summarizing multiple peer reviews."""
    paper_id: str
    review_count: int
    mean_composite_score: float
    decision: ReviewRecommendation
    meta_review_summary: str
    individual_reviews: List[IndividualReview] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "review_count": self.review_count,
            "mean_composite_score": round(self.mean_composite_score, 2),
            "decision": self.decision.value,
            "meta_review_summary": self.meta_review_summary,
            "individual_reviews": [r.to_dict() for r in self.individual_reviews],
        }


class PeerReviewEngine:
    """
    Orchestrates the formal peer review process for submitted papers and technical proposals.
    Aggregates reviews across 6 dimensions and synthesizes editorial consensus.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._reviews: Dict[str, List[IndividualReview]] = {}  # paper_id -> reviews
        self._decisions: Dict[str, ConsensusReview] = {}

    def submit_review(
        self,
        paper_id: str,
        reviewer: str,
        novelty: float,
        correctness: float,
        reproducibility: float,
        experimental_quality: float,
        writing_quality: float,
        statistical_soundness: float,
        comments: str,
        recommendation: ReviewRecommendation,
    ) -> IndividualReview:
        """Records an individual review for a paper."""
        with self._lock:
            rid = f"REV-{uuid.uuid4().hex[:8].upper()}"
            review = IndividualReview(
                review_id=rid,
                paper_id=paper_id,
                reviewer=reviewer,
                novelty=max(1.0, min(5.0, novelty)),
                correctness=max(1.0, min(5.0, correctness)),
                reproducibility=max(1.0, min(5.0, reproducibility)),
                experimental_quality=max(1.0, min(5.0, experimental_quality)),
                writing_quality=max(1.0, min(5.0, writing_quality)),
                statistical_soundness=max(1.0, min(5.0, statistical_soundness)),
                comments=comments,
                recommendation=recommendation,
            )

            self._reviews.setdefault(paper_id, []).append(review)
            return review

    def conduct_automated_review(
        self,
        paper_id: str,
        reviewer: str = "AutomatedPeerReviewer",
        novelty_score_norm: float = 0.8,         # [0.0 - 1.0] from NoveltyDetector
        reproducible_match: bool = True,
        is_statistically_significant: bool = True,
        sample_size: int = 50,
    ) -> IndividualReview:
        """Automated algorithmic reviewer evaluating objective scientific criteria."""
        novelty = 1.0 + (novelty_score_norm * 4.0)
        correctness = 4.5 if is_statistically_significant else 2.5
        reproducibility = 5.0 if reproducible_match else 1.5
        exp_qual = 4.5 if sample_size >= 30 else 3.0
        writing_qual = 4.5
        stat_soundness = 4.8 if is_statistically_significant else 2.0

        comp = (0.20 * novelty + 0.20 * correctness + 0.20 * reproducibility + 0.15 * exp_qual + 0.10 * writing_qual + 0.15 * stat_soundness)

        if comp >= 4.0 and reproducible_match and is_statistically_significant:
            rec = ReviewRecommendation.ACCEPT
            comm = "High-quality paper with strong statistical evidence and verified reproducibility. Recommended for immediate acceptance."
        elif comp >= 3.0:
            rec = ReviewRecommendation.MINOR_REVISION
            comm = "Promising work but requires minor revisions and expanded ablation experiments."
        elif comp >= 2.0:
            rec = ReviewRecommendation.MAJOR_REVISION
            comm = "Significant methodological questions or borderline statistical significance. Major revision required."
        else:
            rec = ReviewRecommendation.REJECT
            comm = "Fatal flaws in reproducibility or statistical power. Rejected."

        return self.submit_review(
            paper_id=paper_id,
            reviewer=reviewer,
            novelty=novelty,
            correctness=correctness,
            reproducibility=reproducibility,
            experimental_quality=exp_qual,
            writing_quality=writing_qual,
            statistical_soundness=stat_soundness,
            comments=comm,
            recommendation=rec,
        )

    def synthesize_consensus(self, paper_id: str) -> ConsensusReview:
        """Synthesizes editorial meta-review from all submitted reviews for the paper."""
        with self._lock:
            revs = self._reviews.get(paper_id, [])
            if not revs:
                raise ValueError(f"No reviews submitted for paper '{paper_id}'")

            mean_score = sum(r.composite_score for r in revs) / len(revs)

            # Consensus decision
            recommendations = [r.recommendation for r in revs]
            if all(r == ReviewRecommendation.ACCEPT for r in recommendations) or (mean_score >= 4.0 and ReviewRecommendation.REJECT not in recommendations):
                decision = ReviewRecommendation.ACCEPT
                summary = f"Unanimous or overwhelming consensus to ACCEPT based on strong scores (mean={mean_score:.2f}/5.0)."
            elif ReviewRecommendation.REJECT in recommendations and mean_score < 3.0:
                decision = ReviewRecommendation.REJECT
                summary = f"Paper REJECTED due to critical flaws identified by reviewers (mean={mean_score:.2f}/5.0)."
            elif mean_score >= 3.3:
                decision = ReviewRecommendation.MINOR_REVISION
                summary = f"Decision is MINOR REVISION to address reviewer feedback (mean={mean_score:.2f}/5.0)."
            else:
                decision = ReviewRecommendation.MAJOR_REVISION
                summary = f"Decision is MAJOR REVISION due to substantial concerns (mean={mean_score:.2f}/5.0)."

            consensus = ConsensusReview(
                paper_id=paper_id,
                review_count=len(revs),
                mean_composite_score=mean_score,
                decision=decision,
                meta_review_summary=summary,
                individual_reviews=revs,
            )

            self._decisions[paper_id] = consensus
            return consensus

    def get_consensus(self, paper_id: str) -> Optional[ConsensusReview]:
        with self._lock:
            return self._decisions.get(paper_id)
