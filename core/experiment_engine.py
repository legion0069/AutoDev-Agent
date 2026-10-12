"""
core/experiment_engine.py - Full Lifecycle Scientific Experimentation Engine (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import enum
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.ab_testing_engine import ABTestingEngine
from core.hypothesis_engine import HypothesisEngine, HypothesisStatus, ResearchHypothesis
from core.reproducibility_manager import ReproducibilityManager
from core.research_memory import ResearchMemory
from core.scientific_logger import ScientificEventType, ScientificLogger
from core.statistical_analyzer import DescriptiveStatistics, HypothesisTestResult, StatisticalAnalyzer


class ExperimentLifecycleStage(str, enum.Enum):
    """Rigorous sequential stages of the scientific experiment lifecycle."""
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    MEASUREMENT = "MEASUREMENT"
    VALIDATION = "VALIDATION"
    COMPARISON = "COMPARISON"
    STATISTICAL_ANALYSIS = "STATISTICAL_ANALYSIS"
    RESULT_CLASSIFICATION = "RESULT_CLASSIFICATION"
    CONCLUDED = "CONCLUDED"
    FAILED = "FAILED"


class ExperimentOutcome(str, enum.Enum):
    """Empirical determination of the hypothesis test."""
    SUPPORTED = "SUPPORTED"          # Statistically significant improvement confirmed
    REFUTED = "REFUTED"              # Significant degradation or null outcome disproving hypothesis
    INCONCLUSIVE = "INCONCLUSIVE"    # Insufficient effect size or p >= alpha


@dataclass
class ExperimentRecord:
    """Comprehensive immutable record of an experimental trial."""
    experiment_id: str
    title: str
    hypothesis_id: Optional[str]
    metric_name: str
    stage: ExperimentLifecycleStage
    outcome: Optional[ExperimentOutcome] = None
    control_stats: Optional[Dict[str, Any]] = None
    variant_stats: Optional[Dict[str, Any]] = None
    statistical_test: Optional[Dict[str, Any]] = None
    manifest_id: Optional[str] = None
    winner_arm: Optional[str] = None
    summary_report: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "title": self.title,
            "hypothesis_id": self.hypothesis_id,
            "metric_name": self.metric_name,
            "stage": self.stage.value,
            "outcome": self.outcome.value if self.outcome else None,
            "control_stats": self.control_stats,
            "variant_stats": self.variant_stats,
            "statistical_test": self.statistical_test,
            "manifest_id": self.manifest_id,
            "winner_arm": self.winner_arm,
            "summary_report": self.summary_report,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class ExperimentEngine:
    """
    Executes the complete 8-stage scientific experiment lifecycle:
    Planning -> Execution -> Measurement -> Validation -> Comparison -> Statistical Analysis -> Classification -> Archival.
    """

    def __init__(
        self,
        hypothesis_engine: Optional[HypothesisEngine] = None,
        ab_testing_engine: Optional[ABTestingEngine] = None,
        reproducibility_manager: Optional[ReproducibilityManager] = None,
        scientific_logger: Optional[ScientificLogger] = None,
        research_memory: Optional[ResearchMemory] = None,
    ) -> None:
        self._lock = threading.RLock()
        self.hypothesis_engine = hypothesis_engine or HypothesisEngine()
        self.ab_testing_engine = ab_testing_engine or ABTestingEngine()
        self.reproducibility_manager = reproducibility_manager or ReproducibilityManager()
        self.scientific_logger = scientific_logger or ScientificLogger()
        self.research_memory = research_memory or ResearchMemory()
        self._experiments: Dict[str, ExperimentRecord] = {}

    def run_experiment(
        self,
        title: str,
        metric_name: str,
        control_evaluator: Callable[[], float],
        variant_evaluator: Callable[[], float],
        hypothesis: Optional[ResearchHypothesis] = None,
        sample_size: int = 35,
        alpha: float = 0.05,
        higher_is_better: bool = False,
        seed: int = 42,
    ) -> ExperimentRecord:
        """
        Executes the full scientific experiment lifecycle synchronously from planning to conclusion.
        """
        with self._lock:
            exp_id = f"EXP-{uuid.uuid4().hex[:8].upper()}"
            hyp_id = hypothesis.hypothesis_id if hypothesis else None

            # --- Stage 1: Planning ---
            record = ExperimentRecord(
                experiment_id=exp_id,
                title=title,
                hypothesis_id=hyp_id,
                metric_name=metric_name,
                stage=ExperimentLifecycleStage.PLANNING,
            )
            self._experiments[exp_id] = record

            if hyp_id:
                self.hypothesis_engine.update_status(hyp_id, HypothesisStatus.IN_EXPERIMENTATION, experiment_id=exp_id)

            self.scientific_logger.log_event(
                event_type=ScientificEventType.EXPERIMENT_START,
                actor="ExperimentEngine",
                entity_id=exp_id,
                payload={"title": title, "metric": metric_name, "sample_size": sample_size},
            )

            # --- Stage 2 & 3: Execution & Measurement ---
            record.stage = ExperimentLifecycleStage.EXECUTION
            control_samples: List[float] = []
            variant_samples: List[float] = []

            for _ in range(sample_size):
                control_samples.append(float(control_evaluator()))
                variant_samples.append(float(variant_evaluator()))

            record.stage = ExperimentLifecycleStage.MEASUREMENT
            c_stats = StatisticalAnalyzer.summarize(control_samples)
            v_stats = StatisticalAnalyzer.summarize(variant_samples)
            record.control_stats = c_stats.to_dict()
            record.variant_stats = v_stats.to_dict()

            # --- Stage 4: Validation (Reproducibility Manifest) ---
            record.stage = ExperimentLifecycleStage.VALIDATION
            manifest = self.reproducibility_manager.record_manifest(
                experiment_id=exp_id,
                seed=seed,
                config={"metric_name": metric_name, "sample_size": sample_size, "alpha": alpha},
                inputs={"sample_size": sample_size},
                outputs={"control_mean": c_stats.mean, "variant_mean": v_stats.mean},
                execution_logs=[f"Collected {sample_size} observations per arm."],
                code_snippet=title,
            )
            record.manifest_id = manifest.manifest_id

            # --- Stage 5: Comparison ---
            record.stage = ExperimentLifecycleStage.COMPARISON
            delta = v_stats.mean - c_stats.mean
            delta_pct = (delta / c_stats.mean * 100.0) if abs(c_stats.mean) > 1e-9 else 0.0

            # --- Stage 6: Statistical Analysis ---
            record.stage = ExperimentLifecycleStage.STATISTICAL_ANALYSIS
            t_res = StatisticalAnalyzer.t_test_two_sample(
                sample_a=variant_samples,
                sample_b=control_samples,
                alpha=alpha,
            )
            record.statistical_test = t_res.to_dict()

            # --- Stage 7: Result Classification ---
            record.stage = ExperimentLifecycleStage.RESULT_CLASSIFICATION
            is_improvement = (delta > 0) if higher_is_better else (delta < 0)

            if t_res.is_significant and is_improvement:
                outcome = ExperimentOutcome.SUPPORTED
                winner = "VARIANT"
                summary = (
                    f"Hypothesis SUPPORTED: Variant achieved {abs(delta_pct):.2f}% improvement "
                    f"in {metric_name} with statistical significance (p={t_res.p_value:.6f} < {alpha}, "
                    f"Cohen's d={t_res.effect_size:.2f})."
                )
                if hyp_id:
                    self.hypothesis_engine.update_status(hyp_id, HypothesisStatus.VALIDATED, evidence=summary)
                self.research_memory.record_success(
                    experiment_id=exp_id,
                    breakthrough_summary=summary,
                    performance_gain_pct=abs(delta_pct),
                )
            elif t_res.is_significant and not is_improvement:
                outcome = ExperimentOutcome.REFUTED
                winner = "CONTROL"
                summary = (
                    f"Hypothesis REFUTED: Variant caused a statistically significant {abs(delta_pct):.2f}% degradation "
                    f"in {metric_name} (p={t_res.p_value:.6f} < {alpha})."
                )
                if hyp_id:
                    self.hypothesis_engine.update_status(hyp_id, HypothesisStatus.REFUTED, evidence=summary)
                self.research_memory.record_failure(
                    experiment_id=exp_id,
                    description=summary,
                    root_cause=f"Unfavorable trade-off in {metric_name}",
                    lessons_learned="Avoid variant design under current workload conditions.",
                )
            else:
                outcome = ExperimentOutcome.INCONCLUSIVE
                winner = "CONTROL"
                summary = (
                    f"Experiment INCONCLUSIVE: Observed delta of {delta_pct:.2f}% is not statistically significant "
                    f"(p={t_res.p_value:.4f} >= {alpha}). Null hypothesis cannot be rejected."
                )

            record.outcome = outcome
            record.winner_arm = winner
            record.summary_report = summary
            record.stage = ExperimentLifecycleStage.CONCLUDED
            record.completed_at = time.time()

            # Store in research memory & scientific logger
            self.research_memory.store_experiment(exp_id, record.to_dict())
            self.scientific_logger.log_event(
                event_type=ScientificEventType.EXPERIMENT_COMPLETE,
                actor="ExperimentEngine",
                entity_id=exp_id,
                payload={"outcome": outcome.value, "winner": winner, "delta_pct": delta_pct, "p_value": t_res.p_value},
            )

            return record

    def get_experiment(self, experiment_id: str) -> Optional[ExperimentRecord]:
        with self._lock:
            return self._experiments.get(experiment_id)
