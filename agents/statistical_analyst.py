"""
agents/statistical_analyst.py - Statistical Analyst Agent (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.communication_bus import CommunicationBus
from core.research_lab import ResearchLab
from core.statistical_analyzer import DescriptiveStatistics, HypothesisTestResult, StatisticalAnalyzer

logger = logging.getLogger("AutoDev.Research.StatisticalAnalyst")


class StatisticalAnalystAgent:
    """
    Statistical Analyst Agent - Arbiter of Mathematical & Inferential Rigor:
    - Computes descriptive metrics, standard deviations, and percentiles
    - Conducts Welch's t-tests, Mann-Whitney U tests, and ANOVA
    - Evaluates Cohen's d effect sizes and statistical power
    - Identifies spurious correlations and confirms statistical significance
    """

    def __init__(
        self,
        name: str = "StatisticalAnalyst",
        lab: Optional[ResearchLab] = None,
        bus: Optional[CommunicationBus] = None,
    ) -> None:
        self.name = name
        self.lab = lab or ResearchLab()
        self.bus = bus
        self.authority_level = 3

        if self.bus:
            self.bus.register_entity(self.name)

    def analyze_dataset(self, data: List[float]) -> DescriptiveStatistics:
        """Computes comprehensive summary statistics for a sample dataset."""
        return StatisticalAnalyzer.summarize(data)

    def compare_treatment_arms(
        self,
        variant_data: List[float],
        control_data: List[float],
        alpha: float = 0.05,
    ) -> Dict[str, Any]:
        """Performs parametric and non-parametric two-sample hypothesis testing."""
        t_res = StatisticalAnalyzer.t_test_two_sample(variant_data, control_data, alpha)
        u_res = StatisticalAnalyzer.mann_whitney_u(variant_data, control_data, alpha)
        norm_var = StatisticalAnalyzer.shapiro_wilk_normality_approx(variant_data)
        norm_ctrl = StatisticalAnalyzer.shapiro_wilk_normality_approx(control_data)

        # Consensus validation
        both_agree = t_res.is_significant == u_res.is_significant
        confidence = "HIGH" if both_agree else "MODERATE"

        return {
            "welch_t_test": t_res.to_dict(),
            "mann_whitney_u": u_res.to_dict(),
            "normality_check": {"variant_normal": norm_var, "control_normal": norm_ctrl},
            "statistical_consensus": confidence,
            "effect_size_cohens_d": t_res.effect_size,
            "analyzed_by": self.name,
        }

    def evaluate_multiple_groups(self, groups: List[List[float]], alpha: float = 0.05) -> Dict[str, Any]:
        """Conducts one-way Analysis of Variance (ANOVA) across multiple experimental arms."""
        anova_res = StatisticalAnalyzer.one_way_anova(groups, alpha)
        return anova_res.to_dict()
