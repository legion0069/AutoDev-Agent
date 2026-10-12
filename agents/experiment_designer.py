"""
agents/experiment_designer.py - Experiment Designer Agent (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.ab_testing_engine import ABExperiment
from core.communication_bus import CommunicationBus
from core.experiment_engine import ExperimentRecord
from core.hypothesis_engine import ResearchHypothesis
from core.research_lab import ResearchLab

logger = logging.getLogger("AutoDev.Research.ExperimentDesigner")


class ExperimentDesignerAgent:
    """
    Experiment Designer Agent - Architect of Empirical Methodology:
    - Formulates Design of Experiments (DoE) protocols
    - Configures treatment arms (Control vs Variants) and statistical power requirements
    - Establishes sample size guidelines and random assignment procedures
    """

    def __init__(
        self,
        name: str = "ExperimentDesigner",
        lab: Optional[ResearchLab] = None,
        bus: Optional[CommunicationBus] = None,
    ) -> None:
        self.name = name
        self.lab = lab or ResearchLab()
        self.bus = bus
        self.authority_level = 3

        if self.bus:
            self.bus.register_entity(self.name)

    def calculate_required_sample_size(
        self,
        expected_effect_size_d: float = 0.8,  # Cohen's d (0.2=small, 0.5=medium, 0.8=large)
        alpha: float = 0.05,
        power: float = 0.80,
    ) -> int:
        """
        Approximates required sample size per arm for a two-sample t-test:
        N ~ 2 * ((z_alpha/2 + z_power) / d)^2
        """
        # Standard normal quantiles:
        # z_(0.05/2) ~ 1.96, z_(0.80) ~ 0.8416
        z_alpha = 1.96
        z_power = 0.8416
        numerator = z_alpha + z_power
        n_est = 2.0 * ((numerator / max(1e-4, expected_effect_size_d)) ** 2)
        return max(15, int(math.ceil(n_est)))

    def design_ab_test(
        self,
        experiment_name: str,
        metric_name: str,
        variants: List[Tuple[str, str]],
        higher_is_better: bool = False,
        expected_effect_size: float = 0.8,
    ) -> ABExperiment:
        """Configures a scientifically sound multi-arm experiment in the lab engine."""
        n_req = self.calculate_required_sample_size(expected_effect_size)
        return self.lab.ab_testing_engine.create_experiment(
            name=experiment_name,
            metric_name=metric_name,
            variants=variants,
            higher_is_better=higher_is_better,
            min_sample_size=n_req,
        )

    def execute_design(
        self,
        title: str,
        metric_name: str,
        control_evaluator: Callable[[], float],
        variant_evaluator: Callable[[], float],
        hypothesis: Optional[ResearchHypothesis] = None,
        higher_is_better: bool = False,
    ) -> ExperimentRecord:
        """Executes the designed experimental protocol via the master ExperimentEngine."""
        sample_size = self.calculate_required_sample_size(expected_effect_size_d=0.7)
        return self.lab.experiment_engine.run_experiment(
            title=title,
            metric_name=metric_name,
            control_evaluator=control_evaluator,
            variant_evaluator=variant_evaluator,
            hypothesis=hypothesis,
            sample_size=sample_size,
            higher_is_better=higher_is_better,
        )
