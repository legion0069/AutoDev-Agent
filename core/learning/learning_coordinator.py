"""
learning_coordinator.py - Master Self-Evolving Intelligence Engine for AutoDev (v3.1)

Coordinates all 10 learning subsystems into a seamless continuous self-evolution pipeline:
1. LearningEngine
2. ReflectionEngine
3. PatternMiningEngine
4. PromptOptimizationEngine
5. ExecutionAnalyticsEngine
6. ArchitectureRecommendationEngine
7. PlaybookEngine
8. SelfImprovementPlanner
9. KnowledgeEvolutionEngine
10. PerformanceEvolutionEngine
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.learning.architecture_recommender import ArchitectureRecommendationEngine
from core.learning.execution_analytics import ExecutionAnalyticsEngine
from core.learning.knowledge_evolution import KnowledgeEvolutionEngine
from core.learning.learning_engine import LearningEngine
from core.learning.learning_models import (
    ArchitectureRecommendation,
    EngineeringPattern,
    EngineeringPlaybook,
    ImprovementRoadmapItem,
    LearningEvent,
    LearningEventType,
    LearningKnowledge,
    LearningSession,
    LearningSnapshot,
    PatternCategory,
    PerformanceEvolutionRecord,
    PlaybookArchetype,
    PromptOptimizationRecord,
    ReflectionReport,
    ReflectionScope,
    SelfImprovementPlan,
)
from core.learning.pattern_miner import PatternMiningEngine
from core.learning.performance_evolution import PerformanceEvolutionEngine
from core.learning.playbook_engine import PlaybookEngine
from core.learning.prompt_optimizer import PromptOptimizationEngine
from core.learning.reflection_engine import ReflectionEngine
from core.learning.self_improvement_planner import SelfImprovementPlanner

logger = logging.getLogger("AutoDev.Learning.SelfEvolvingEngine")


class SelfEvolvingEngine:
    """
    Master Self-Evolving Intelligence Engine.
    Unifies autonomous learning, reflection, pattern mining, prompt optimization, execution analytics,
    architecture recommendations, playbooks, self-improvement planning, and performance benchmarking.
    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        learning_engine: Optional[LearningEngine] = None,
        reflection_engine: Optional[ReflectionEngine] = None,
        pattern_miner: Optional[PatternMiningEngine] = None,
        prompt_optimizer: Optional[PromptOptimizationEngine] = None,
        analytics_engine: Optional[ExecutionAnalyticsEngine] = None,
        recommender: Optional[ArchitectureRecommendationEngine] = None,
        playbook_engine: Optional[PlaybookEngine] = None,
        planner: Optional[SelfImprovementPlanner] = None,
        knowledge_evolution: Optional[KnowledgeEvolutionEngine] = None,
        performance_evolution: Optional[PerformanceEvolutionEngine] = None,
        project_root: Optional[str] = None,
        llm: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        self._lock = threading.RLock()
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.llm = llm
        self.storage_dir = Path(storage_dir) if storage_dir else Path("memory/learning")

        # Subsystems
        self.learning_engine = learning_engine or LearningEngine(storage_dir=str(self.storage_dir))
        self.reflection_engine = reflection_engine or ReflectionEngine(storage_dir=str(self.storage_dir))
        self.pattern_miner = pattern_miner or PatternMiningEngine(storage_dir=str(self.storage_dir))
        self.prompt_optimizer = prompt_optimizer or PromptOptimizationEngine(storage_dir=str(self.storage_dir))
        self.analytics_engine = analytics_engine or ExecutionAnalyticsEngine(storage_dir=str(self.storage_dir))
        self.recommender = recommender or ArchitectureRecommendationEngine(storage_dir=str(self.storage_dir))
        self.playbook_engine = playbook_engine or PlaybookEngine(storage_dir=str(self.storage_dir))
        self.planner = planner or SelfImprovementPlanner(storage_dir=str(self.storage_dir))
        self.knowledge_evolution = knowledge_evolution or KnowledgeEvolutionEngine(storage_dir=str(self.storage_dir))
        self.performance_evolution = performance_evolution or PerformanceEvolutionEngine(storage_dir=str(self.storage_dir))

        logger.info("SelfEvolvingEngine initialized across all 10 learning subsystems.")

    def on_task_completed(
        self,
        task_id: str,
        task_title: str,
        project_id: str = "default_project",
        execution_success: bool = True,
        retries_count: int = 0,
        tests_passed: int = 0,
        tests_failed: int = 0,
        prompt_text: str = "",
        duration_seconds: float = 1.0,
        review_score: float = 90.0,
        affected_files: Optional[List[str]] = None,
        error_logs: Optional[List[str]] = None,
        root_cause: str = "",
        solution: str = "",
        architecture_score: float = 90.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Executes the complete autonomous learning lifecycle after a task completes:
        1. Task Reflection
        2. Learning Event Generation
        3. Pattern Mining & Ingestion
        4. Prompt Optimization
        5. Execution Analytics Recording
        6. Performance Benchmarking Run
        """
        # Handle keyword aliases for flexible invocation
        if "success" in kwargs:
            execution_success = bool(kwargs["success"])
        if "quality_score" in kwargs:
            review_score = float(kwargs["quality_score"])
        if "test_pass_rate" in kwargs:
            pr = float(kwargs["test_pass_rate"])
            tests_passed = int(pr / 10.0)
            tests_failed = max(0, 10 - tests_passed)
        if "execution_time" in kwargs:
            duration_seconds = float(kwargs["execution_time"])
        if "retry_count" in kwargs:
            retries_count = int(kwargs["retry_count"])
        if "files_affected" in kwargs and kwargs["files_affected"] is not None:
            affected_files = list(kwargs["files_affected"])
        if "project" in kwargs and kwargs["project"]:
            project_id = str(kwargs["project"])
        if "review_feedback" in kwargs and kwargs["review_feedback"]:
            if error_logs is None:
                error_logs = []
            error_logs.append(str(kwargs["review_feedback"]))

        with self._lock:
            start_ts = time.time()
            prompt_len = len(prompt_text) if prompt_text else 1200

            # 1. Autonomous Task Reflection
            reflection = self.reflection_engine.reflect_on_task(
                task_id=task_id,
                task_title=task_title,
                execution_success=execution_success,
                retries_count=retries_count,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                prompt_length_chars=prompt_len,
                duration_seconds=duration_seconds,
                review_score=review_score,
                error_logs=error_logs,
                affected_files=affected_files,
            )

            # 2. Generate Learning Events
            event_category = LearningEventType.ARCHITECTURE_SUCCESS if execution_success else LearningEventType.REVIEW_FAILURE
            if execution_success and retries_count > 0:
                event_category = LearningEventType.BUG_FIXED
            elif not execution_success:
                event_category = LearningEventType.REVIEW_FAILURE

            event = self.learning_engine.record_event(
                category=event_category,
                summary=f"Task '{task_title}' completed with {retries_count} retries and review {review_score:.1f}/100",
                project=project_id,
                task_id=task_id,
                confidence=0.92 if execution_success else 0.70,
                importance=85.0 if retries_count > 0 else 70.0,
                affected_files=affected_files or [],
                root_cause=root_cause or ("" if execution_success else "Validation or compilation defect"),
                solution=solution or ("" if not execution_success else "Synthesized verified module implementation"),
                metrics={
                    "retries": retries_count,
                    "review_score": review_score,
                    "duration_seconds": duration_seconds,
                    "tests_passed": tests_passed,
                },
                tags=[project_id, "autonomous_task", event_category.value.lower()],
            )

            # 3. Pattern Mining from event stream
            recent_events = self.learning_engine.list_events()
            mined_patterns = self.pattern_miner.mine_patterns_from_events(recent_events)

            # 4. Prompt Optimization Pass
            prompt_analysis = self.prompt_optimizer.analyze_prompt_performance(
                prompt_text=prompt_text or "Standard task prompt",
                retries_count=retries_count,
                review_score=review_score,
                duration_seconds=duration_seconds,
            )

            # 5. Record Execution Analytics
            analytics_run = self.analytics_engine.record_project_run(
                project_id=project_id,
                review_score=review_score,
                retry_count=retries_count,
                duration_seconds=duration_seconds,
                files_changed=len(affected_files or []),
                tests_executed=tests_passed + tests_failed,
                coverage_pct=85.0 if tests_passed > 0 else 0.0,
                architecture_score=architecture_score,
            )

            # 6. Record Performance Evolution Telemetry
            self.performance_evolution.record_run(
                version_tag="v3.1",
                stage="task_execution",
                duration_ms=duration_seconds * 1000.0,
                memory_kb=4200.0,
                throughput_ops_sec=round(1.0 / max(0.001, duration_seconds), 2),
            )

            elapsed_ms = (time.time() - start_ts) * 1000.0
            logger.info("Autonomous learning cycle completed for task %s in %.2f ms", task_id, elapsed_ms)

            return {
                "task_id": task_id,
                "project_id": project_id,
                "reflection_id": reflection.reflection_id,
                "learning_event_id": event.event_id,
                "event_category": event.category.value,
                "mined_patterns_count": len(mined_patterns),
                "prompt_efficiency_score": prompt_analysis["token_efficiency_score"],
                "run_id": analytics_run["run_id"],
                "learning_duration_ms": round(elapsed_ms, 2),
            }

    def on_sprint_completed(
        self,
        sprint_number: int,
        committed_points: int,
        completed_points: int,
        velocity_points: int,
        blockers_count: int,
        carryover_stories: int,
    ) -> ReflectionReport:
        """Executes reflective learning after a 2-week sprint completes."""
        with self._lock:
            reflection = self.reflection_engine.reflect_on_sprint(
                sprint_number=sprint_number,
                committed_points=committed_points,
                completed_points=completed_points,
                velocity_points=velocity_points,
                blockers_encountered=blockers_count,
                carryover_stories=carryover_stories,
            )

            self.learning_engine.record_event(
                category=LearningEventType.TEST_STRATEGY if blockers_count == 0 else LearningEventType.REVIEW_FAILURE,
                summary=f"Sprint {sprint_number} closed with {completed_points}/{committed_points} pts delivered",
                project="sprint_cadence",
                task_id=f"Sprint-{sprint_number}",
                confidence=0.95,
                importance=80.0,
                metrics={
                    "completed_points": completed_points,
                    "velocity": velocity_points,
                    "blockers": blockers_count,
                },
                tags=["sprint", f"sprint_{sprint_number}", "velocity"],
            )

            return reflection

    def on_release_completed(
        self,
        version: str,
        quality_gates_passed: int,
        quality_gates_total: int,
        lead_time_hours: float,
        postmortem_count: int = 0,
    ) -> ReflectionReport:
        """Executes reflective learning following a production release."""
        with self._lock:
            reflection = self.reflection_engine.reflect_on_release(
                version=version,
                quality_gates_passed=quality_gates_passed,
                quality_gates_total=quality_gates_total,
                lead_time_hours=lead_time_hours,
                postmortem_count=postmortem_count,
            )

            self.learning_engine.record_event(
                category=LearningEventType.ARCHITECTURE_SUCCESS if postmortem_count == 0 else LearningEventType.DEPLOYMENT_FAILURE,
                summary=f"Release {version} deployed to GA with {quality_gates_passed}/{quality_gates_total} gates",
                project="release_train",
                task_id=f"Release-{version}",
                confidence=0.98 if postmortem_count == 0 else 0.75,
                importance=95.0,
                metrics={
                    "lead_time_hours": lead_time_hours,
                    "postmortems": postmortem_count,
                },
                tags=["release", version, "ga_deployment"],
            )

            return reflection

    def recommend_architecture(
        self,
        project_name: str = "project",
        requirement: str = "",
        requirements: str = "",
        domain: str = "general",
        domain_tags: Optional[List[str]] = None,
        language: str = "python",
        scale: str = "medium",
        **kwargs: Any,
    ) -> ArchitectureRecommendation:
        """
        Recommends folder structure, design patterns, database, API style,
        and testing strategy based on historical project success.
        """
        req = requirement or requirements or kwargs.get("req_text", "") or "General Software Architecture"
        p_name = project_name or kwargs.get("name", "project")
        tags = domain_tags or ([domain] if domain else [])
        with self._lock:
            return self.recommender.recommend_architecture(
                project_name=p_name,
                requirements=req,
                domain_tags=tags,
                language=language,
                scale=scale,
            )

    def recommend_for_new_project(
        self,
        project_name: str,
        requirements: str,
        domain_tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes architecture recommendations, matching playbooks, and relevant historical patterns.
        """
        with self._lock:
            rec = self.recommender.recommend_architecture(
                project_name=project_name,
                requirements=requirements,
                domain_tags=domain_tags,
            )

            playbook = self.playbook_engine.get_playbook(rec.archetype)
            top_patterns = self.pattern_miner.get_top_patterns(5)

            return {
                "project_name": project_name,
                "recommendation": rec.to_dict(),
                "matched_playbook": playbook.to_dict() if playbook else None,
                "recommended_patterns": [p.to_dict() for p in top_patterns],
            }

    def run_sprint_reflection(
        self,
        sprint_id: str = "SPRINT-1",
        sprint_number: int = 1,
        committed_points: int = 20,
        completed_points: int = 20,
        velocity_points: int = 20,
        blockers_count: int = 0,
        carryover_stories: int = 0,
        task_records: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> ReflectionReport:
        """Runs reflection and learning on completed sprint."""
        if task_records:
            total_tasks = len(task_records)
            passed = sum(1 for t in task_records if getattr(t, "success", True))
            committed_points = total_tasks * 5
            completed_points = passed * 5
            velocity_points = completed_points
            blockers_count = total_tasks - passed

        num = sprint_number
        if sprint_id and "SPRINT-" in sprint_id.upper():
            try:
                num = int(sprint_id.upper().replace("SPRINT-", ""))
            except Exception:
                pass

        return self.on_sprint_completed(
            sprint_number=num,
            committed_points=committed_points,
            completed_points=completed_points,
            velocity_points=velocity_points,
            blockers_count=blockers_count,
            carryover_stories=carryover_stories,
        )

    def run_release_reflection(
        self,
        release_version: str = "3.1.0",
        version: str = "",
        quality_gates_passed: int = 5,
        quality_gates_total: int = 5,
        lead_time_hours: float = 2.0,
        postmortem_count: int = 0,
        release_notes: str = "",
        metrics: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ReflectionReport:
        """Runs reflection and learning on completed release."""
        v = version or release_version
        if metrics:
            quality_gates_passed = metrics.get("quality_gates_passed", quality_gates_passed)
            quality_gates_total = metrics.get("quality_gates_total", quality_gates_total)
            lead_time_hours = metrics.get("lead_time_hours", lead_time_hours)
            postmortem_count = metrics.get("postmortem_count", postmortem_count)

        return self.on_release_completed(
            version=v,
            quality_gates_passed=quality_gates_passed,
            quality_gates_total=quality_gates_total,
            lead_time_hours=lead_time_hours,
            postmortem_count=postmortem_count,
        )

    def optimize_prompt(
        self,
        raw_prompt: str = "",
        prompt_text: str = "",
        task_type: str = "coding",
        target_tokens: int = 1500,
        **kwargs: Any,
    ) -> PromptOptimizationRecord:
        """Optimizes and compresses prompts using discovered patterns and heuristics."""
        p_text = raw_prompt or prompt_text or kwargs.get("prompt", "")
        with self._lock:
            return self.prompt_optimizer.optimize_prompt(
                prompt_text=p_text,
                task_type=task_type,
                target_tokens=target_tokens,
            )

    def run_monthly_evolution_cycle(
        self,
        month_label: str = "2026-10",
        evaluation_period: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Runs the comprehensive monthly self-evolution cycle:
        1. Monthly Reflection
        2. Knowledge Evolution & Deduplication
        3. Self-Improvement Subsystem Evaluation & Roadmap Synthesis
        4. Performance Comparison Generation
        """
        label = evaluation_period or month_label
        with self._lock:
            start_ts = time.time()
            all_events = self.learning_engine.list_events()
            all_reflections = self.reflection_engine.list_reflections()
            analytics_kpis = self.analytics_engine.compute_aggregate_kpis()

            # 1. Monthly Reflection
            monthly_refl = self.reflection_engine.reflect_monthly(
                month_label=label,
                events=all_events,
                analytics_summary=analytics_kpis,
            )

            # 2. Knowledge Evolution
            all_knowledge = self.learning_engine.list_knowledge()
            evolved_res = self.knowledge_evolution.evolve_knowledge_base(all_knowledge)

            # 3. Self-Improvement Roadmap Planning
            failure_events = [e for e in all_events if e.category in (LearningEventType.REVIEW_FAILURE, LearningEventType.DEPLOYMENT_FAILURE)]
            plan = self.planner.evaluate_subsystems(
                execution_kpis=analytics_kpis,
                reflection_reports=all_reflections,
                failure_events=failure_events,
            )

            # 4. Performance Evolution Report
            perf_report = self.performance_evolution.generate_performance_report()

            duration_ms = (time.time() - start_ts) * 1000.0
            return {
                "month_label": label,
                "monthly_reflection": monthly_refl.to_dict(),
                "knowledge_evolution": evolved_res,
                "self_improvement_plan": plan.to_dict(),
                "performance_evolution": perf_report,
                "cycle_duration_ms": round(duration_ms, 2),
            }

    def get_learning_dashboard(self) -> Dict[str, Any]:
        """Returns consolidated live learning telemetry dashboard."""
        with self._lock:
            return {
                "total_events": len(self.learning_engine.list_events()),
                "total_reflections": len(self.reflection_engine.list_reflections()),
                "discovered_patterns_count": len(self.pattern_miner.get_all_patterns()),
                "playbooks_count": len(self.playbook_engine.list_playbooks()),
                "knowledge_items_count": len(self.learning_engine.list_knowledge()),
                "kpi_metrics": self.analytics_engine.compute_aggregate_kpis(),
                "top_patterns": [p.to_dict() for p in self.pattern_miner.get_top_patterns(5)],
                "recent_events": [e.to_dict() for e in self.learning_engine.list_events()[-10:]],
            }

    @property
    def self_improvement_planner(self) -> SelfImprovementPlanner:
        return self.planner

    @property
    def architecture_recommender(self) -> ArchitectureRecommendationEngine:
        return self.recommender

    @property
    def pattern_mining_engine(self) -> PatternMiningEngine:
        return self.pattern_miner

    @property
    def prompt_optimization_engine(self) -> PromptOptimizationEngine:
        return self.prompt_optimizer

    @property
    def execution_analytics(self) -> ExecutionAnalyticsEngine:
        return self.analytics_engine

    @property
    def knowledge_evolution_engine(self) -> KnowledgeEvolutionEngine:
        return self.knowledge_evolution

    @property
    def performance_evolution_engine(self) -> PerformanceEvolutionEngine:
        return self.performance_evolution

    def generate_learning_report(self) -> Dict[str, Any]:
        """Generates structured learning report."""
        return self.learning_engine.create_snapshot().to_dict()

    def generate_comprehensive_learning_report(self) -> Dict[str, Any]:
        """Generates comprehensive multi-dimensional learning report bundle with all 8 core reports."""
        learning_rep = self.generate_learning_report()
        reflection_rep = self.generate_reflection_report()
        evolution_rep = self.generate_evolution_report()
        performance_rep = self.generate_performance_report()
        architecture_rep = self.generate_architecture_report()
        prompt_improvement_rep = self.generate_prompt_improvement_report()
        pattern_discovery_rep = self.generate_pattern_discovery_report()
        self_improvement_roadmap = self.generate_self_improvement_roadmap_report()
        analytics = self.analytics_engine.to_dict()

        return {
            "total_events": learning_rep.get("total_events", 0),
            "summary": learning_rep,
            "analytics": analytics,
            "patterns_count": len(self.pattern_miner.get_top_patterns(limit=100)),
            "playbooks_count": len(self.playbook_engine.get_all_playbooks()),
            "timestamp": time.time(),
            "learning_report": learning_rep,
            "reflection_report": reflection_rep,
            "evolution_report": evolution_rep,
            "performance_report": performance_rep,
            "architecture_report": architecture_rep,
            "prompt_improvement_report": prompt_improvement_rep,
            "pattern_discovery_report": pattern_discovery_rep,
            "self_improvement_roadmap": self_improvement_roadmap,
        }

    def generate_reflection_report(self, target_id: Optional[str] = None) -> Dict[str, Any]:
        """Generates reflection report."""
        return self.reflection_engine.to_dict()

    def generate_evolution_report(self) -> Dict[str, Any]:
        """Generates knowledge evolution report."""
        return {
            "timestamp": time.time(),
            "institutional_knowledge": [k.to_dict() for k in self.knowledge_evolution.get_curated_knowledge()],
            "promoted_standards": [k.to_dict() for k in self.knowledge_evolution.get_promoted_knowledge()],
            "archived_knowledge": [k.to_dict() for k in self.knowledge_evolution.get_archived_knowledge()],
            "total_knowledge_items": len(self.knowledge_evolution.get_curated_knowledge()),
        }

    def generate_performance_report(self) -> Dict[str, Any]:
        """Generates performance benchmarking and speedup evolution report."""
        return self.performance_evolution.generate_performance_report()

    def generate_architecture_report(self, recommendation: Optional[Any] = None) -> Dict[str, Any]:
        """Generates architecture recommendation report."""
        if recommendation is not None:
            return recommendation.to_dict() if hasattr(recommendation, "to_dict") else dict(recommendation)
        return self.recommender.to_dict()

    def generate_prompt_improvement_report(self) -> Dict[str, Any]:
        """Generates prompt optimization and token efficiency report."""
        return self.prompt_optimizer.generate_prompt_report()

    def generate_pattern_discovery_report(self) -> Dict[str, Any]:
        """Generates pattern discovery report."""
        return self.pattern_miner.to_dict()

    def generate_self_improvement_roadmap_report(self, plan: Optional[SelfImprovementPlan] = None) -> Dict[str, Any]:
        """Generates self improvement roadmap report."""
        if plan is not None:
            return plan.to_dict()
        return self.planner.generate_roadmap_report()

    def to_dict(self) -> Dict[str, Any]:
        """Serializes current master learning engine state."""
        with self._lock:
            return {
                "learning_engine": self.learning_engine.to_dict(),
                "reflection_engine": self.reflection_engine.to_dict(),
                "pattern_miner": self.pattern_miner.to_dict(),
                "prompt_optimizer": self.prompt_optimizer.to_dict(),
                "analytics_engine": self.analytics_engine.to_dict(),
                "recommender": self.recommender.to_dict(),
                "playbook_engine": self.playbook_engine.to_dict(),
                "planner": self.planner.to_dict(),
                "knowledge_evolution": self.knowledge_evolution.to_dict(),
                "performance_evolution": self.performance_evolution.to_dict(),
            }


# Backwards compatibility alias
LearningCoordinator = SelfEvolvingEngine

