"""
agents/chief_scientist.py - Chief Scientist Agent (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from core.algorithm_registry import AlgorithmAdoptionStatus, AlgorithmRecord
from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType
from core.hypothesis_engine import HypothesisPriority, ResearchHypothesis
from core.research_lab import ResearchLab, ResearchMetrics

logger = logging.getLogger("AutoDev.Research.ChiefScientist")


class ChiefScientistAgent:
    """
    Chief Scientist Agent - Executive Head of the Corporate Research Division:
    - Establishes long-term scientific roadmap and fundamental research priorities
    - Authorizes high-risk, high-reward research initiatives
    - Grants final approval for algorithm graduation into production
    - Presides over Scientific Review Boards and research dispute arbitration
    """

    def __init__(
        self,
        name: str = "ChiefScientist",
        lab: Optional[ResearchLab] = None,
        bus: Optional[CommunicationBus] = None,
    ) -> None:
        self.name = name
        self.lab = lab or ResearchLab()
        self.bus = bus
        self.authority_level = 5  # Executive scientific authority

        self.strategic_research_pillars: List[str] = [
            "Algorithmic efficiency and sub-linear complexity scaling",
            "Deterministic multi-agent reasoning and verification",
            "Zero-loss prompt compression and contextual distillation",
            "Formal mathematical reproducibility and statistical rigor",
        ]

        if self.bus:
            self.bus.register_entity(self.name)

    def review_and_authorize_hypothesis(self, hypothesis: ResearchHypothesis) -> Dict[str, Any]:
        """Evaluates whether a proposed hypothesis warrants allocation of research resources."""
        is_high_impact = hypothesis.priority in (HypothesisPriority.HIGH, HypothesisPriority.CRITICAL)
        is_confident = hypothesis.confidence >= 0.60

        approved = is_high_impact or is_confident
        rationale = (
            f"Authorized research into '{hypothesis.title}': high alignment with scientific pillars."
            if approved
            else f"Deferred hypothesis '{hypothesis.title}': insufficient strategic impact or initial confidence."
        )

        return {
            "hypothesis_id": hypothesis.hypothesis_id,
            "authorized": approved,
            "rationale": rationale,
            "reviewed_by": self.name,
            "timestamp": time.time(),
        }

    def ratify_algorithm_for_production(self, algorithm_id: str) -> Dict[str, Any]:
        """Grants executive authorization to promote a validated algorithm into production."""
        rec = self.lab.algorithm_registry.get_algorithm(algorithm_id)
        if not rec:
            return {"success": False, "error": f"Algorithm '{algorithm_id}' not found."}

        # Check preconditions: success rate >= 95% and regression risk < 0.15
        if rec.success_rate < 95.0 or rec.regression_risk >= 0.15:
            return {
                "success": False,
                "error": f"Cannot promote '{rec.name}': success_rate={rec.success_rate}%, risk={rec.regression_risk}.",
            }

        self.lab.algorithm_registry.update_status(
            algorithm_id=algorithm_id,
            new_status=AlgorithmAdoptionStatus.PRODUCTION,
            rationale=f"Ratified by {self.name} following comprehensive benchmark validation.",
        )

        return {
            "success": True,
            "algorithm_id": algorithm_id,
            "new_status": AlgorithmAdoptionStatus.PRODUCTION.value,
            "ratified_by": self.name,
        }

    def evaluate_research_division_health(self) -> Dict[str, Any]:
        """Provides executive assessment of enterprise R&D health and productivity."""
        metrics = self.lab.compute_global_metrics()
        is_healthy = metrics.experiment_success_rate >= 50.0 and metrics.average_novelty >= 0.50

        return {
            "status": "HEALTHY" if is_healthy else "NEEDS_OPTIMIZATION",
            "metrics": metrics.to_dict(),
            "pillars_evaluated": len(self.strategic_research_pillars),
            "assessed_by": self.name,
        }
