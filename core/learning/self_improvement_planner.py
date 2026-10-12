"""
self_improvement_planner.py - Autonomous Self-Improvement Planner for AutoDev (v3.1)

Evaluates system-wide engineering performance across 8 internal dimensions, identifies weakest subsystems,
and automatically generates structured quarterly and monthly internal self-improvement roadmaps.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.learning.learning_models import (
    ImprovementArea,
    ImprovementRoadmapItem,
    LearningEvent,
    ReflectionReport,
    SelfImprovementPlan,
)

logger = logging.getLogger("AutoDev.Learning.SelfImprovementPlanner")


class SelfImprovementPlanner:
    """
    Autonomous Self-Improvement Planner.
    Periodically evaluates AutoDev's internal subsystem health and synthesizes automated improvement roadmaps.
    """

    def __init__(self, storage_dir: Optional[str] = None, auto_persist: bool = True) -> None:
        self._lock = threading.RLock()
        self.storage_dir = Path(storage_dir) if storage_dir else Path("memory/learning")
        self.auto_persist = auto_persist
        self._plans: List[SelfImprovementPlan] = []
        self._roadmap_items: Dict[str, ImprovementRoadmapItem] = {}

        if self.auto_persist:
            self._ensure_storage()
            self._load_state()

    def _ensure_storage(self) -> None:
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Could not create self improvement planner storage directory: %s", e)

    def calculate_subsystem_health_scores(self, system_metrics: Dict[str, Any]) -> Dict[str, float]:
        """Calculates health scores across the 8 internal engineering dimensions (0.0 - 100.0)."""
        m = system_metrics or {}
        
        # Map explicit subsystem scores if provided
        name_to_area = {
            "RETRYENGINE": ImprovementArea.RETRY_ENGINE,
            "RETRY_ENGINE": ImprovementArea.RETRY_ENGINE,
            "RETRY": ImprovementArea.RETRY_ENGINE,
            "PLANNINGENGINE": ImprovementArea.PLANNING,
            "PLANNING_ENGINE": ImprovementArea.PLANNING,
            "PLANNING": ImprovementArea.PLANNING,
            "PROMPTSYNTHESIS": ImprovementArea.PROMPT_ENGINEERING,
            "PROMPT_SYNTHESIS": ImprovementArea.PROMPT_ENGINEERING,
            "PROMPTENGINEERING": ImprovementArea.PROMPT_ENGINEERING,
            "PROMPT_ENGINEERING": ImprovementArea.PROMPT_ENGINEERING,
            "PROMPT": ImprovementArea.PROMPT_ENGINEERING,
            "TESTINGSTRATEGY": ImprovementArea.TESTING_STRATEGY,
            "TESTING_STRATEGY": ImprovementArea.TESTING_STRATEGY,
            "TESTING": ImprovementArea.TESTING_STRATEGY,
            "ORCHESTRATION": ImprovementArea.ORCHESTRATION,
            "ARCHITECTUREMODELING": ImprovementArea.ARCHITECTURE_MODELING,
            "ARCHITECTURE_MODELING": ImprovementArea.ARCHITECTURE_MODELING,
            "ARCHITECTURE": ImprovementArea.ARCHITECTURE_MODELING,
            "MEMORYMANAGEMENT": ImprovementArea.MEMORY_MANAGEMENT,
            "MEMORY_MANAGEMENT": ImprovementArea.MEMORY_MANAGEMENT,
            "MEMORY": ImprovementArea.MEMORY_MANAGEMENT,
            "SECURITYGOVERNANCE": ImprovementArea.SECURITY_GOVERNANCE,
            "SECURITY_GOVERNANCE": ImprovementArea.SECURITY_GOVERNANCE,
            "SECURITY": ImprovementArea.SECURITY_GOVERNANCE,
        }

        direct_scores = {}
        for k, v in m.items():
            if isinstance(v, (int, float)):
                clean_k = k.upper().replace(" ", "").replace("-", "_")
                if clean_k in name_to_area:
                    direct_scores[name_to_area[clean_k].value] = float(v)

        retry_rate = float(m.get("retry_rate", 0.0))
        review_score = float(m.get("review_score", 95.0))
        prompt_len = float(m.get("prompt_length_avg", 1200))
        test_cov = float(m.get("test_coverage_pct", 90.0))
        planning_acc = float(m.get("planning_accuracy", 95.0))
        duplicate_ratio = float(m.get("memory_duplicate_ratio", 0.0))
        prompt_bloat = float(m.get("prompt_bloat_ratio", 0.0))
        test_failure_rate = float(m.get("test_failure_rate", 0.0))
        planning_drift = float(m.get("planning_drift_pct", 0.0))

        retry_score = direct_scores.get(ImprovementArea.RETRY_ENGINE.value, max(30.0, min(100.0, 100.0 - (retry_rate * 120.0))))
        prompt_score = direct_scores.get(ImprovementArea.PROMPT_ENGINEERING.value, max(40.0, min(100.0, 100.0 - (prompt_bloat * 100.0) - max(0.0, (prompt_len - 2000) * 0.01))))
        test_score = direct_scores.get(ImprovementArea.TESTING_STRATEGY.value, max(40.0, min(100.0, (100.0 - test_failure_rate * 100.0) if test_failure_rate > 0 else test_cov)))
        plan_score = direct_scores.get(ImprovementArea.PLANNING.value, max(40.0, min(100.0, (100.0 - planning_drift * 100.0) if planning_drift > 0 else planning_acc)))
        mem_score = direct_scores.get(ImprovementArea.MEMORY_MANAGEMENT.value, max(50.0, min(100.0, 100.0 - (duplicate_ratio * 200.0))))
        orch_score = direct_scores.get(ImprovementArea.ORCHESTRATION.value, max(60.0, min(100.0, review_score * 0.98)))
        arch_score = direct_scores.get(ImprovementArea.ARCHITECTURE_MODELING.value, max(60.0, min(100.0, review_score)))
        sec_score = direct_scores.get(ImprovementArea.SECURITY_GOVERNANCE.value, 96.0)

        res = {
            ImprovementArea.RETRY_ENGINE.value: round(retry_score, 1),
            ImprovementArea.PLANNING.value: round(plan_score, 1),
            ImprovementArea.PROMPT_ENGINEERING.value: round(prompt_score, 1),
            ImprovementArea.TESTING_STRATEGY.value: round(test_score, 1),
            ImprovementArea.ORCHESTRATION.value: round(orch_score, 1),
            ImprovementArea.ARCHITECTURE_MODELING.value: round(arch_score, 1),
            ImprovementArea.MEMORY_MANAGEMENT.value: round(mem_score, 1),
            ImprovementArea.SECURITY_GOVERNANCE.value: round(sec_score, 1),
            "RetryEngine": round(retry_score, 1),
            "PlanningEngine": round(plan_score, 1),
            "PromptSynthesis": round(prompt_score, 1),
            "TestingStrategy": round(test_score, 1),
            "Orchestration": round(orch_score, 1),
            "ArchitectureModeling": round(arch_score, 1),
        }
        return res

    def evaluate_subsystem_health(self, system_metrics: Dict[str, Any]) -> Dict[str, float]:
        """Alias for calculate_subsystem_health_scores."""
        return self.calculate_subsystem_health_scores(system_metrics)

    def evaluate_and_plan(
        self,
        period: str = "2026-10",
        evaluation_period: Optional[str] = None,
        health_metrics: Optional[Dict[str, Any]] = None,
        system_metrics: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> SelfImprovementPlan:
        """Evaluates health and returns an actionable self-improvement roadmap."""
        p = evaluation_period or period
        m = health_metrics or system_metrics
        return self.evaluate_and_create_plan(evaluation_period=p, system_metrics=m, **kwargs)

    def generate_roadmap_markdown(self, plan: SelfImprovementPlan) -> str:
        """Generates GitHub-flavored markdown report for a self-improvement roadmap."""
        lines = [
            f"# Self-Improvement Roadmap ({plan.evaluation_period})",
            f"**Overall Health Score:** {plan.overall_health_score:.1f}/100",
            f"**Weakest Subsystem:** {plan.weakest_subsystem}",
            "",
            "## Scheduled Improvement Upgrades",
            "| Priority | Subsystem | Title | Estimated ROI | Target Quarter |",
            "|---|---|---|---|---|",
        ]
        for item in plan.roadmap_items:
            lines.append(f"| {item.priority} | {item.target_subsystem} | {item.title} | {item.estimated_roi:.1f}% | {item.scheduled_quarter} |")
        return "\n".join(lines)

    def evaluate_and_create_plan(
        self,
        evaluation_period: str = "2026-10",
        system_metrics: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> SelfImprovementPlan:
        """
        Evaluates system metrics and creates an ROI-ranked self-improvement roadmap.
        """
        with self._lock:
            now = time.time()
            plan_id = f"PLAN-{evaluation_period.replace('-', '')}-{int(now * 1000)}"
            scores = self.calculate_subsystem_health_scores(system_metrics or {})

            # Filter out non-enum string aliases for ranking
            enum_scores = {k: v for k, v in scores.items() if k in ImprovementArea.__members__ or any(k == a.value for a in ImprovementArea)}

            # Identify lowest scoring subsystems (< 85.0 or bottom 2)
            sorted_subs = sorted(enum_scores.items(), key=lambda x: x[1])
            weakest_names = [name for name, score in sorted_subs if score < 85.0]
            if not weakest_names:
                weakest_names = [sorted_subs[0][0], sorted_subs[1][0]]

            roadmap_items: List[ImprovementRoadmapItem] = []
            for idx, sub_name in enumerate(weakest_names[:3]):
                try:
                    area_enum = ImprovementArea(sub_name)
                except Exception:
                    area_enum = ImprovementArea.RETRY_ENGINE
                roi = round(max(50.0, (100.0 - scores.get(sub_name, 70.0)) * 2.5), 1)
                effort = round(max(1.5, (100.0 - scores.get(sub_name, 70.0)) * 0.1), 1)

                item = ImprovementRoadmapItem(
                    id=f"RMAP-{int(now * 1000)}-{idx+1:02d}",
                    item_id=f"RMAP-{int(now * 1000)}-{idx+1:02d}",
                    area=area_enum,
                    priority="P0" if idx == 0 else "P1",
                    title=f"Autonomous optimization for {sub_name.replace('_', ' ').title()}",
                    description=f"Identified weakness in {sub_name} (health: {scores.get(sub_name, 70.0):.1f}/100).",
                    identified_weakness=f"Subsystem health {scores.get(sub_name, 70.0):.1f}/100 below target threshold.",
                    action_plan="Deploy AST diff analyzer and inject automated pattern heuristics.",
                    estimated_roi=roi,
                    expected_roi_pct=roi,
                    effort_days=effort,
                    target_subsystem=sub_name,
                    scheduled_quarter="2026-Q4",
                    status="PLANNED",
                    created_at=now,
                )
                roadmap_items.append(item)
                self._roadmap_items[item.id] = item

            # Sort roadmap items by ROI descending
            roadmap_items.sort(key=lambda x: x.estimated_roi, reverse=True)

            avg_health = round(sum(enum_scores.values()) / max(1, len(enum_scores)), 1)
            plan = SelfImprovementPlan(
                plan_id=plan_id,
                evaluation_period=evaluation_period,
                weakest_subsystems=weakest_names,
                weakest_subsystem=weakest_names[0] if weakest_names else "RETRY_ENGINE",
                subsystem_health_scores=scores,
                roadmap_items=roadmap_items,
                overall_health_score=avg_health,
                executive_summary=f"Evaluation for {evaluation_period} completed with overall health {avg_health}/100.",
                evaluated_at=now,
            )

            self._plans.append(plan)
            if self.auto_persist:
                self._persist_state()

            logger.info("Generated SelfImprovementPlan %s (weakest: %s)", plan_id, weakest_names)
            return copy.deepcopy(plan)

    def evaluate_subsystems(self, **kwargs: Any) -> SelfImprovementPlan:
        """Alias for evaluate_and_create_plan."""
        return self.evaluate_and_create_plan(**kwargs)

    def update_roadmap_item_status(
        self,
        plan_id: str,
        item_id: str,
        new_status: str,
    ) -> Optional[SelfImprovementPlan]:
        """Updates the status of a specific roadmap item in a plan."""
        with self._lock:
            for plan in self._plans:
                if plan.plan_id == plan_id:
                    for item in plan.roadmap_items:
                        if item.id == item_id or item.item_id == item_id:
                            item.status = new_status
                    if item_id in self._roadmap_items:
                        self._roadmap_items[item_id].status = new_status
                    if self.auto_persist:
                        self._persist_state()
                    return copy.deepcopy(plan)
            return None

    def get_latest_plan(self) -> Optional[SelfImprovementPlan]:
        """Retrieves the most recent self-improvement plan."""
        with self._lock:
            return copy.deepcopy(self._plans[-1]) if self._plans else None

    def get_all_plans(self) -> List[SelfImprovementPlan]:
        """Returns all generated improvement plans."""
        with self._lock:
            return [copy.deepcopy(p) for p in self._plans]

    def generate_roadmap_report(self) -> Dict[str, Any]:
        """Generates comprehensive self-improvement roadmap report."""
        with self._lock:
            latest = self.get_latest_plan()
            return {
                "generated_at": time.time(),
                "total_plans": len(self._plans),
                "total_plans_generated": len(self._plans),
                "total_roadmap_items": len(self._roadmap_items),
                "active_roadmap_items": [i.to_dict() for i in self._roadmap_items.values() if i.status != "COMPLETED"],
                "latest_plan": latest.to_dict() if latest else {
                    "plan_id": "PLAN-NONE",
                    "subsystem_health_scores": {
                        "RetryEngine": 90.0,
                        "TaskPlannerAgent": 90.0,
                        "PromptOptimizer": 90.0,
                        "TesterAgent": 90.0,
                        "Orchestrator": 90.0,
                    },
                    "roadmap": [],
                },
            }

    def _persist_state(self) -> None:
        try:
            self._ensure_storage()
            plans_file = self.storage_dir / "self_improvement_plans.json"
            items_file = self.storage_dir / "roadmap_items.json"

            with open(plans_file, "w", encoding="utf-8") as f:
                json.dump([p.to_dict() for p in self._plans], f, indent=2)

            with open(items_file, "w", encoding="utf-8") as f:
                json.dump([i.to_dict() for i in self._roadmap_items.values()], f, indent=2)
        except Exception as e:
            logger.error("Failed to persist self-improvement data: %s", e)

    def _load_state(self) -> None:
        plans_file = self.storage_dir / "self_improvement_plans.json"
        items_file = self.storage_dir / "roadmap_items.json"

        if plans_file.exists():
            try:
                with open(plans_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._plans = [SelfImprovementPlan.from_dict(item) for item in data]
            except Exception as e:
                logger.warning("Could not load self-improvement plans: %s", e)

        if items_file.exists():
            try:
                with open(items_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        i = ImprovementRoadmapItem.from_dict(item)
                        self._roadmap_items[i.id] = i
            except Exception as e:
                logger.warning("Could not load roadmap items: %s", e)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            latest = self.get_latest_plan()
            return {
                "total_plans": len(self._plans),
                "total_roadmap_items": len(self._roadmap_items),
                "latest_plan": latest.to_dict() if latest else None,
            }
