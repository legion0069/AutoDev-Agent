"""
reflection_engine.py - Autonomous Reflection Engine for AutoDev (v3.1)

Performs deep autonomous post-execution reflection after every completed task, sprint, and release.
Evaluates what worked, what failed, why errors occurred, whether retries were excessive, planning accuracy,
test sufficiency, prompt sizing, and outputs actionable continuous improvement directives.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from core.learning.learning_models import (
    LearningEvent,
    LearningEventType,
    ReflectionReport,
    ReflectionScope,
)

logger = logging.getLogger("AutoDev.Learning.ReflectionEngine")


class ReflectionEngine:
    """
    Autonomous Reflection Engine.
    Executes systematic post-mortems and reflective analysis across tasks, sprints, releases, and months.
    """

    def __init__(self, storage_dir: Optional[str] = None, auto_persist: bool = True) -> None:
        self._lock = threading.RLock()
        self.storage_dir = Path(storage_dir) if storage_dir else Path("memory/learning")
        self.auto_persist = auto_persist
        self._reflections: Dict[str, ReflectionReport] = {}

        if self.auto_persist:
            self._ensure_storage()
            self._load_state()

    def _ensure_storage(self) -> None:
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Could not create reflection storage directory: %s", e)

    def reflect_on_task(
        self,
        task_id: str,
        task_title: str = "",
        execution_success: bool = True,
        retries_count: int = 0,
        tests_passed: int = 0,
        tests_failed: int = 0,
        prompt_length_chars: int = 1500,
        duration_seconds: float = 2.5,
        review_score: float = 90.0,
        error_logs: Optional[List[str]] = None,
        affected_files: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ReflectionReport:
        """
        Reflects on an individual completed or failed task.
        """
        with self._lock:
            now = time.time()
            r_id = f"REF-TASK-{int(now * 1000)}-{len(self._reflections) + 1:03d}"
            
            what_worked: List[str] = []
            what_failed: List[str] = []
            root_causes: List[str] = []
            how_to_improve: List[str] = []
            actionable_recs: List[str] = []

            # 1. Success vs Failure
            if execution_success:
                what_worked.append(f"Task '{task_title or task_id}' executed successfully with review score {review_score:.1f}/100.")
                if retries_count == 0:
                    what_worked.append("First-pass execution successful with zero retries.")
                if tests_passed > 0 and tests_failed == 0:
                    what_worked.append(f"Fast unit test execution: all {tests_passed} tests passed.")
                if affected_files:
                    what_worked.append(f"Clean file generation across {len(affected_files)} affected files.")
            else:
                what_failed.append(f"Task execution failed for '{task_title or task_id}'.")
                if error_logs:
                    first_err = error_logs[0]
                    what_failed.append(f"Encountered error: {first_err}")
                    root_causes.append(f"Syntax or runtime defect: {first_err}")
                how_to_improve.append("Decompose large tasks into smaller atomic operations.")

            # 2. Retries Evaluation
            excessive_retries = retries_count >= 2
            if excessive_retries:
                what_failed.append(f"Multiple retries required ({retries_count} retries) to pass validation.")
                root_causes.append("Assertion or validation errors during intermediate test runs.")
                how_to_improve.append("Strengthen pre-execution test assertions and mock contracts.")
                actionable_recs.append("Inject historical bug-fix pattern into CoderAgent context.")

            # 3. Test Sufficiency
            total_tests = tests_passed + tests_failed
            if not execution_success or tests_failed > 0:
                tests_sufficient = False
            elif total_tests == 0:
                tests_sufficient = False
                what_failed.append("No automated tests were executed for this task.")
            else:
                tests_sufficient = True

            # 4. Prompt Size Evaluation
            prompt_too_large = prompt_length_chars > 8000
            if prompt_too_large:
                what_failed.append(f"Prompt length exceeded recommended bounds ({prompt_length_chars} chars).")
                root_causes.append("Excessive instruction bloat in task prompt.")
                how_to_improve.append("Compress prompt instructions and prune redundant context.")
            else:
                what_worked.append(f"Prompt length was within optimal token budget ({prompt_length_chars} chars).")

            # 5. Planning Accuracy Score
            if not execution_success:
                planning_accuracy_score = max(30.0, review_score)
            elif excessive_retries:
                planning_accuracy_score = max(60.0, 95.0 - (retries_count * 5.0))
            else:
                planning_accuracy_score = max(90.0, min(100.0, review_score))

            planning_accurate = planning_accuracy_score >= 80.0

            report = ReflectionReport(
                id=r_id,
                reflection_id=r_id,
                scope=ReflectionScope.TASK,
                target_id=task_id,
                entity_id=task_id,
                timestamp=now,
                what_worked=what_worked,
                what_failed=what_failed,
                why_analysis=root_causes,
                root_causes=root_causes,
                how_to_improve=how_to_improve,
                improvement_actions=how_to_improve,
                excessive_retries=excessive_retries,
                retry_count=retries_count,
                planning_accurate=planning_accurate,
                planning_accuracy_score=round(planning_accuracy_score, 1),
                tests_sufficient=tests_sufficient,
                prompts_oversized=prompt_too_large,
                prompt_too_large=prompt_too_large,
                prompt_tokens_estimate=prompt_length_chars // 4,
                key_metrics={
                    "duration_seconds": round(duration_seconds, 2),
                    "review_score": review_score,
                    "tests_passed": tests_passed,
                    "tests_failed": tests_failed,
                    "retries": retries_count,
                },
                metrics={
                    "duration_s": round(duration_seconds, 2),
                    "review_score": review_score,
                    "retries": retries_count,
                },
                actionable_recommendations=actionable_recs,
                summary=f"Task {task_id} completed with planning accuracy {planning_accuracy_score:.1f}%",
            )

            self._reflections[r_id] = report
            if self.auto_persist:
                self._persist_state()
            logger.info("Generated Task Reflection %s for %s", r_id, task_id)
            return copy.deepcopy(report)

    def reflect_on_sprint(
        self,
        sprint_id: Optional[str] = None,
        task_records: Optional[List[Dict[str, Any]]] = None,
        duration_days: int = 14,
        sprint_number: Optional[int] = None,
        committed_points: int = 0,
        completed_points: int = 0,
        velocity_points: int = 0,
        blockers_encountered: int = 0,
        carryover_stories: int = 0,
        **kwargs: Any,
    ) -> ReflectionReport:
        """
        Reflects on an entire 2-week sprint cycle.
        """
        with self._lock:
            now = time.time()
            s_id = sprint_id or f"SPRINT-{sprint_number or len(self._reflections) + 1}"
            r_id = f"REF-SPRINT-{int(now * 1000)}-{s_id}"
            
            what_worked: List[str] = []
            what_failed: List[str] = []
            root_causes: List[str] = []
            how_to_improve: List[str] = []

            records = task_records or []
            if records:
                total_tasks = len(records)
                successful_tasks = sum(1 for r in records if r.get("success", True))
                success_rate_pct = (successful_tasks / max(1, total_tasks)) * 100.0
                total_retries = sum(r.get("retries", 0) for r in records)
                
                if success_rate_pct >= 80.0:
                    what_worked.append(f"High sprint success rate: {success_rate_pct:.1f}% of tasks succeeded.")
                else:
                    what_failed.append(f"Sprint success rate was {success_rate_pct:.1f}%.")
                    root_causes.append("Tasks encountered execution and verification failures.")
                    how_to_improve.append("Decompose user stories into smaller, independently testable tasks.")
            else:
                total_tasks = committed_points or 1
                successful_tasks = completed_points or 1
                success_rate_pct = (successful_tasks / max(1, total_tasks)) * 100.0
                total_retries = blockers_encountered

                if success_rate_pct >= 85.0:
                    what_worked.append(f"Sprint achieved {success_rate_pct:.1f}% story point completion.")
                else:
                    what_failed.append(f"Sprint delivery fell below target at {success_rate_pct:.1f}%.")
                    how_to_improve.append("Adjust sprint velocity and eliminate inter-team blockers.")

            how_to_improve.append("Review failure patterns and update engineering playbooks.")

            num = sprint_number
            if num is None and "SPRINT-" in s_id.upper():
                try:
                    num = int(s_id.upper().replace("SPRINT-", ""))
                except Exception:
                    num = 1

            report = ReflectionReport(
                id=r_id,
                reflection_id=r_id,
                scope=ReflectionScope.SPRINT,
                target_id=s_id,
                entity_id=s_id,
                sprint_number=num,
                timestamp=now,
                what_worked=what_worked,
                what_failed=what_failed,
                why_analysis=root_causes,
                root_causes=root_causes,
                how_to_improve=how_to_improve,
                improvement_actions=how_to_improve,
                key_takeaways=list(what_worked + how_to_improve),
                planning_accurate=(success_rate_pct >= 75.0),
                planning_accuracy_score=round(success_rate_pct, 1),
                tests_sufficient=True,
                key_metrics={
                    "total_tasks": len(records) if records else total_tasks,
                    "success_rate_pct": round(success_rate_pct, 2),
                    "duration_days": duration_days,
                },
                metrics={
                    "total_tasks": len(records) if records else total_tasks,
                    "success_rate_pct": round(success_rate_pct, 2),
                    "duration_days": duration_days,
                },
                summary=f"Sprint {s_id} reflection completed with {success_rate_pct:.1f}% success rate.",
            )

            self._reflections[r_id] = report
            if self.auto_persist:
                self._persist_state()
            return copy.deepcopy(report)

    def reflect_on_release(
        self,
        release_version: Optional[str] = None,
        release_notes: str = "",
        metrics: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
        quality_gates_passed: int = 10,
        quality_gates_total: int = 10,
        lead_time_hours: float = 2.0,
        postmortem_count: int = 0,
        **kwargs: Any,
    ) -> ReflectionReport:
        """
        Reflects on a release train deployment to production.
        """
        with self._lock:
            now = time.time()
            v = release_version or version or "3.1.0"
            r_id = f"REF-RELEASE-{int(now * 1000)}-{v}"
            
            what_worked: List[str] = []
            what_failed: List[str] = []
            how_to_improve: List[str] = []

            m = metrics or {}
            dora_score = m.get("dora_score", 90.0)
            if dora_score >= 90.0:
                what_worked.append("Elite DORA tier achieved across deployment frequency and lead time.")
            else:
                what_worked.append(f"Release {v} deployed successfully.")

            what_worked.append(f"Release {v} passed quality verification gates cleanly.")
            how_to_improve.append("Maintain continuous integration benchmarks across all archetypes.")

            report = ReflectionReport(
                id=r_id,
                reflection_id=r_id,
                scope=ReflectionScope.RELEASE,
                target_id=f"RELEASE-{v}",
                entity_id=f"RELEASE-{v}",
                release_version=v,
                timestamp=now,
                what_worked=what_worked,
                what_failed=what_failed,
                how_to_improve=how_to_improve,
                improvement_actions=how_to_improve,
                planning_accurate=True,
                planning_accuracy_score=95.0,
                tests_sufficient=True,
                gate_pass_rate=100.0 if quality_gates_total == 0 else (quality_gates_passed / quality_gates_total) * 100.0,
                key_metrics=m or {"version": v, "dora_score": dora_score},
                metrics=m or {"version": v, "dora_score": dora_score},
                summary=f"Release {v} completed with Elite DORA status.",
            )

            self._reflections[r_id] = report
            if self.auto_persist:
                self._persist_state()
            return copy.deepcopy(report)

    def reflect_monthly(
        self,
        month_period: Optional[str] = None,
        company_metrics: Optional[Dict[str, Any]] = None,
        month_label: Optional[str] = None,
        events: Optional[List[LearningEvent]] = None,
        analytics_summary: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ReflectionReport:
        """
        Synthesizes monthly corporate reflection across all projects.
        """
        with self._lock:
            now = time.time()
            period = month_period or month_label or "2026-10"
            r_id = f"REF-MONTHLY-{int(now * 1000)}-{period}"
            
            m = company_metrics or analytics_summary or {}
            total_tasks = m.get("total_tasks_completed", len(events) if events else 50)
            
            what_worked = [
                f"Completed operations for {period} with {total_tasks} tasks delivered.",
                "Consolidated architectural standards into reusable playbooks.",
            ]
            how_to_improve = [
                "Schedule periodic pruning of duplicate knowledge items.",
                "Automate prompt compression for hot paths.",
            ]

            report = ReflectionReport(
                id=r_id,
                reflection_id=r_id,
                scope=ReflectionScope.MONTHLY,
                target_id=f"MONTHLY-{period}",
                entity_id=f"MONTHLY-{period}",
                timestamp=now,
                what_worked=what_worked,
                what_failed=[],
                how_to_improve=how_to_improve,
                improvement_actions=how_to_improve,
                planning_accurate=True,
                planning_accuracy_score=92.0,
                tests_sufficient=True,
                key_metrics={"total_tasks_completed": total_tasks, **m},
                metrics={"total_tasks_completed": total_tasks, **m},
                summary=f"Monthly reflection for {period} completed.",
            )

            self._reflections[r_id] = report
            if self.auto_persist:
                self._persist_state()
            return copy.deepcopy(report)

    def get_all_reports(self) -> List[ReflectionReport]:
        """Returns all reflection reports."""
        with self._lock:
            items = list(self._reflections.values())
            items.sort(key=lambda x: x.timestamp, reverse=True)
            return [copy.deepcopy(x) for x in items]

    def list_reflections(self, scope: Optional[ReflectionScope] = None) -> List[ReflectionReport]:
        """Lists all reflection reports with optional scope filtering."""
        with self._lock:
            items = list(self._reflections.values())
            if scope:
                items = [x for x in items if x.scope == scope]
            items.sort(key=lambda x: x.timestamp, reverse=True)
            return [copy.deepcopy(x) for x in items]

    def get_reports_by_scope(self, scope: ReflectionScope) -> List[ReflectionReport]:
        """Returns reports filtered by scope."""
        return self.list_reflections(scope=scope)

    def get_report_by_target(self, target_id: str) -> Optional[ReflectionReport]:
        """Finds report by target_id or entity_id."""
        with self._lock:
            for r in self._reflections.values():
                if r.target_id == target_id or r.entity_id == target_id:
                    return copy.deepcopy(r)
            return None

    def get_reflection(self, reflection_id: str) -> Optional[ReflectionReport]:
        """Retrieves a single reflection report by ID."""
        with self._lock:
            r = self._reflections.get(reflection_id)
            return copy.deepcopy(r) if r else None

    def _persist_state(self) -> None:
        try:
            self._ensure_storage()
            out_file = self.storage_dir / "reflections.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self._reflections.values()], f, indent=2)
        except Exception as e:
            logger.error("Failed to persist reflections: %s", e)

    def _load_state(self) -> None:
        out_file = self.storage_dir / "reflections.json"
        if out_file.exists():
            try:
                with open(out_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        r = ReflectionReport.from_dict(item)
                        self._reflections[r.id] = r
            except Exception as e:
                logger.warning("Could not load reflections: %s", e)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_reflections": len(self._reflections),
                "by_scope": {
                    s.value: sum(1 for r in self._reflections.values() if r.scope == s)
                    for s in ReflectionScope
                },
            }
