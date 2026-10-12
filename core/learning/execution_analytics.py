"""
execution_analytics.py - Longitudinal Execution Analytics Engine for AutoDev (v3.1)

Tracks, aggregates, and analyzes software engineering metrics across all executed projects and tasks.
Computes statistical aggregates (mean, median, std dev, p95) and produces structured JSON trend series
without requiring external plotting dependencies.
"""

from __future__ import annotations

import copy
import json
import logging
import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("AutoDev.Learning.ExecutionAnalytics")


@dataclass
class TaskMetricsRecord:
    """Record of task or project level execution KPIs."""
    run_id: str
    project: str
    task_id: str
    timestamp: float = field(default_factory=time.time)
    review_score: float = 90.0
    retry_count: int = 0
    implementation_duration_s: float = 1.0
    duration_seconds: float = 1.0
    files_changed_count: int = 1
    files_changed: int = 1
    tests_executed_count: int = 10
    tests_executed: int = 10
    coverage_pct: float = 85.0
    commits_created: int = 1
    commits_count: int = 1
    architecture_score: float = 90.0
    dora_lead_time_hours: float = 2.0
    dora_change_failure_rate: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_id": self.project,
            "project": self.project,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "review_score": self.review_score,
            "retry_count": self.retry_count,
            "implementation_duration_s": self.implementation_duration_s,
            "duration_seconds": self.duration_seconds,
            "files_changed_count": self.files_changed_count,
            "files_changed": self.files_changed,
            "tests_executed_count": self.tests_executed_count,
            "tests_executed": self.tests_executed,
            "coverage_pct": self.coverage_pct,
            "commits_created": self.commits_created,
            "commits_count": self.commits_count,
            "architecture_score": self.architecture_score,
            "dora_lead_time_hours": self.dora_lead_time_hours,
            "dora_change_failure_rate": self.dora_change_failure_rate,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> TaskMetricsRecord:
        proj = d.get("project") or d.get("project_id") or "default_project"
        dur = d.get("implementation_duration_s") or d.get("duration_seconds", 1.0)
        files = d.get("files_changed_count") or d.get("files_changed", 1)
        tests = d.get("tests_executed_count") or d.get("tests_executed", 10)
        commits = d.get("commits_created") or d.get("commits_count", 1)
        return cls(
            run_id=d.get("run_id", f"RUN-{int(time.time() * 1000)}"),
            project=proj,
            task_id=d.get("task_id", "TASK-0"),
            timestamp=d.get("timestamp", time.time()),
            review_score=float(d.get("review_score", 90.0)),
            retry_count=int(d.get("retry_count", 0)),
            implementation_duration_s=float(dur),
            duration_seconds=float(dur),
            files_changed_count=int(files),
            files_changed=int(files),
            tests_executed_count=int(tests),
            tests_executed=int(tests),
            coverage_pct=float(d.get("coverage_pct", 85.0)),
            commits_created=int(commits),
            commits_count=int(commits),
            architecture_score=float(d.get("architecture_score", 90.0)),
            dora_lead_time_hours=float(d.get("dora_lead_time_hours", 2.0)),
            dora_change_failure_rate=float(d.get("dora_change_failure_rate", 0.0)),
            metadata=dict(d.get("metadata", {})),
        )


class ExecutionAnalyticsEngine:
    """
    Longitudinal Execution Analytics Engine.
    Aggregates software development KPIs across projects and generates structured trend charts.
    """

    def __init__(self, storage_dir: Optional[str] = None, auto_persist: bool = True) -> None:
        self._lock = threading.RLock()
        self.storage_dir = Path(storage_dir) if storage_dir else Path("memory/learning")
        self.auto_persist = auto_persist
        
        # In-memory metrics records: project_id -> list of run dicts
        self._project_runs: Dict[str, List[TaskMetricsRecord]] = defaultdict(list)
        self._global_runs: List[TaskMetricsRecord] = []

        if self.auto_persist:
            self._ensure_storage()
            self._load_state()

    def _ensure_storage(self) -> None:
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Could not create analytics storage directory: %s", e)

    def record_task_metrics(
        self,
        project: str = "default_project",
        task_id: str = "TASK-0",
        review_score: float = 90.0,
        retry_count: int = 0,
        implementation_duration_s: float = 1.0,
        files_changed_count: int = 1,
        tests_executed_count: int = 10,
        coverage_pct: float = 85.0,
        commits_created: int = 1,
        architecture_score: float = 90.0,
        **kwargs: Any,
    ) -> TaskMetricsRecord:
        """
        Records telemetry from a completed task execution run.
        """
        with self._lock:
            now = time.time()
            run_id = f"RUN-{int(now * 1000)}-{len(self._global_runs) + 1}"
            dur = implementation_duration_s or kwargs.get("duration_seconds", 1.0)
            rec = TaskMetricsRecord(
                run_id=run_id,
                project=project,
                task_id=task_id,
                timestamp=now,
                review_score=float(review_score),
                retry_count=int(retry_count),
                implementation_duration_s=float(dur),
                duration_seconds=float(dur),
                files_changed_count=int(files_changed_count),
                files_changed=int(files_changed_count),
                tests_executed_count=int(tests_executed_count),
                tests_executed=int(tests_executed_count),
                coverage_pct=float(coverage_pct),
                commits_created=int(commits_created),
                commits_count=int(commits_created),
                architecture_score=float(architecture_score),
                metadata=dict(kwargs.get("metadata", {})),
            )

            self._project_runs[project].append(rec)
            self._global_runs.append(rec)

            if self.auto_persist:
                self._persist_state()

            logger.debug("Recorded task metrics [%s] for %s (task=%s)", run_id, project, task_id)
            return copy.deepcopy(rec)

    def record_project_run(
        self,
        project_id: str,
        review_score: Union[float, Dict[str, Any]] = 90.0,
        retry_count: int = 0,
        duration_seconds: float = 1.0,
        files_changed: int = 5,
        tests_executed: int = 10,
        coverage_pct: float = 85.0,
        commits_count: int = 1,
        architecture_score: float = 90.0,
        dora_lead_time_hours: float = 2.0,
        dora_change_failure_rate: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Records telemetry from a completed project run.
        """
        if isinstance(review_score, dict):
            m = review_score
            r_score = float(m.get("review_score", 90.0))
            r_retries = int(m.get("retry_count", 0))
            r_dur = float(m.get("duration_seconds", m.get("implementation_duration_s", 1.0)))
            r_files = int(m.get("files_changed", m.get("files_changed_count", 5)))
            r_tests = int(m.get("tests_executed", m.get("tests_executed_count", m.get("tests_passed", 10))))
            r_cov = float(m.get("coverage_pct", 85.0))
            r_commits = int(m.get("commits_count", m.get("commits_created", 1)))
            r_arch = float(m.get("architecture_score", 90.0))
            r_meta = m.get("metadata", metadata or {})
        else:
            r_score = float(review_score)
            r_retries = retry_count
            r_dur = duration_seconds
            r_files = files_changed
            r_tests = tests_executed
            r_cov = coverage_pct
            r_commits = commits_count
            r_arch = architecture_score
            r_meta = metadata or {}

        rec = self.record_task_metrics(
            project=project_id,
            task_id=kwargs.get("task_id", f"RUN-{len(self._global_runs)+1}"),
            review_score=r_score,
            retry_count=r_retries,
            implementation_duration_s=r_dur,
            files_changed_count=r_files,
            tests_executed_count=r_tests,
            coverage_pct=r_cov,
            commits_created=r_commits,
            architecture_score=r_arch,
            metadata=r_meta,
        )
        return rec.to_dict()

    def compute_aggregated_statistics(self) -> Dict[str, Any]:
        """Computes system-wide aggregated summary statistics across all recorded project runs."""
        with self._lock:
            runs = self._global_runs
            total = len(runs)
            if not total:
                return {
                    "total_projects": len(self._project_runs),
                    "total_runs": 0,
                    "avg_review_score": 0.0,
                    "avg_retry_count": 0.0,
                    "avg_duration_seconds": 0.0,
                    "avg_coverage_pct": 0.0,
                    "review_score": self._calc_stats([]),
                    "retry_count": self._calc_stats([]),
                    "duration_seconds": self._calc_stats([]),
                    "coverage_pct": self._calc_stats([]),
                }
            return {
                "total_projects": len(self._project_runs),
                "total_runs": total,
                "avg_review_score": round(sum(r.review_score for r in runs) / total, 2),
                "avg_retry_count": round(sum(r.retry_count for r in runs) / total, 2),
                "avg_duration_seconds": round(sum(r.implementation_duration_s for r in runs) / total, 2),
                "avg_coverage_pct": round(sum(r.coverage_pct for r in runs) / total, 2),
                "review_score": self._calc_stats([r.review_score for r in runs]),
                "retry_count": self._calc_stats([float(r.retry_count) for r in runs]),
                "duration_seconds": self._calc_stats([r.implementation_duration_s for r in runs]),
                "coverage_pct": self._calc_stats([r.coverage_pct for r in runs]),
            }

    def _calc_stats(self, values: List[float]) -> Dict[str, float]:
        """Computes mean, median, standard deviation, min, max, and p95."""
        if not values:
            return {"mean": 0.0, "median": 0.0, "std_dev": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0}

        sorted_v = sorted(values)
        n = len(sorted_v)
        mean_v = sum(sorted_v) / n
        median_v = sorted_v[n // 2] if n % 2 == 1 else (sorted_v[n // 2 - 1] + sorted_v[n // 2]) / 2.0
        
        variance = sum((x - mean_v) ** 2 for x in sorted_v) / n
        std_v = math.sqrt(variance)
        
        p95_idx = min(n - 1, int(math.ceil(0.95 * n)) - 1)
        p95_v = sorted_v[p95_idx]

        return {
            "mean": round(mean_v, 2),
            "median": round(median_v, 2),
            "std_dev": round(std_v, 2),
            "min": round(sorted_v[0], 2),
            "max": round(sorted_v[-1], 2),
            "p95": round(p95_v, 2),
        }

    def get_project_statistics(self, project: str) -> Dict[str, Any]:
        """Computes comprehensive aggregated metrics for a project."""
        with self._lock:
            runs = self._project_runs.get(project, [])
            total_tasks = len(runs)
            if not runs:
                return {
                    "project": project,
                    "total_tasks": 0,
                    "review_score": self._calc_stats([]),
                    "retry_count": self._calc_stats([]),
                    "duration_seconds": self._calc_stats([]),
                    "coverage_pct": self._calc_stats([]),
                    "architecture_score": self._calc_stats([]),
                }

            review_scores = [r.review_score for r in runs]
            retries = [float(r.retry_count) for r in runs]
            durations = [r.implementation_duration_s for r in runs]
            coverages = [r.coverage_pct for r in runs]
            arch_scores = [r.architecture_score for r in runs]

            return {
                "project": project,
                "total_tasks": total_tasks,
                "review_score": self._calc_stats(review_scores),
                "retry_count": self._calc_stats(retries),
                "duration_seconds": self._calc_stats(durations),
                "coverage_pct": self._calc_stats(coverages),
                "architecture_score": self._calc_stats(arch_scores),
            }

    def generate_trend_graphs(self, project: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates trend series for review scores, retries, durations, and coverage.
        """
        with self._lock:
            runs = self._project_runs.get(project, []) if project else self._global_runs
            
            data_points = [r.to_dict() for r in runs]
            trend_series = {
                "review_score": [r.review_score for r in runs],
                "retry_count": [r.retry_count for r in runs],
                "duration": [r.implementation_duration_s for r in runs],
                "coverage": [r.coverage_pct for r in runs],
                "architecture_score": [r.architecture_score for r in runs],
            }

            return {
                "project": project or "ALL_PROJECTS",
                "sample_count": len(runs),
                "data_points": data_points,
                "trend_series": trend_series,
            }

    def generate_trend_series(
        self,
        metric_or_project: str = "review_score",
        project_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generates time-series points or project trend series."""
        with self._lock:
            # Handle if called with project name: generate_trend_series("no_such_project")
            proj = project_id or (metric_or_project if metric_or_project in self._project_runs or metric_or_project not in ("review_score", "retry_count", "duration", "coverage", "architecture_score") else None)
            metric = metric_or_project if proj != metric_or_project else "review_score"
            
            runs = self._project_runs.get(proj, []) if proj else self._global_runs
            points = []
            values = []
            for r in runs:
                d = r.to_dict()
                if metric in d:
                    val = float(d[metric])
                    values.append(val)
                    points.append({"timestamp": r.timestamp, "value": val, "project": r.project})

            return {
                "metric_name": metric,
                "project": proj or "ALL",
                "statistics": self._calc_stats(values),
                "data_points": points,
                "review_scores": [r.review_score for r in runs],
                "retry_counts": [r.retry_count for r in runs],
                "durations": [r.implementation_duration_s for r in runs],
                "coverages": [r.coverage_pct for r in runs],
            }

    def get_all_projects_summary(self) -> Dict[str, Any]:
        """Returns summary overview across all tracked projects."""
        with self._lock:
            projects = list(self._project_runs.keys())
            return {
                "total_records": len(self._global_runs),
                "total_projects": len(projects),
                "projects": projects,
            }

    def compute_aggregate_kpis(self) -> Dict[str, Any]:
        """Calculates global aggregate metrics across all projects."""
        with self._lock:
            if not self._global_runs:
                return {
                    "total_runs": 0,
                    "total_projects": 0,
                    "average_review_score": 0.0,
                    "avg_review_score": 0.0,
                    "average_retry_count": 0.0,
                    "avg_retry_count": 0.0,
                    "average_duration_seconds": 0.0,
                    "avg_duration_seconds": 0.0,
                    "average_coverage_pct": 0.0,
                    "avg_coverage_pct": 0.0,
                    "average_architecture_score": 0.0,
                    "avg_architecture_score": 0.0,
                    "review_score": self._calc_stats([]),
                    "retry_count": self._calc_stats([]),
                    "duration_seconds": self._calc_stats([]),
                    "coverage_pct": self._calc_stats([]),
                    "architecture_score": self._calc_stats([]),
                }

            review_scores = [r.review_score for r in self._global_runs]
            retries = [float(r.retry_count) for r in self._global_runs]
            durations = [r.implementation_duration_s for r in self._global_runs]
            coverages = [r.coverage_pct for r in self._global_runs]
            arch_scores = [r.architecture_score for r in self._global_runs]

            rev_stats = self._calc_stats(review_scores)
            ret_stats = self._calc_stats(retries)
            dur_stats = self._calc_stats(durations)
            cov_stats = self._calc_stats(coverages)
            arch_stats = self._calc_stats(arch_scores)

            return {
                "total_runs": len(self._global_runs),
                "total_projects": len(self._project_runs),
                "average_review_score": rev_stats["mean"],
                "avg_review_score": rev_stats["mean"],
                "average_retry_count": ret_stats["mean"],
                "avg_retry_count": ret_stats["mean"],
                "average_duration_seconds": dur_stats["mean"],
                "avg_duration_seconds": dur_stats["mean"],
                "average_coverage_pct": cov_stats["mean"],
                "avg_coverage_pct": cov_stats["mean"],
                "average_architecture_score": arch_stats["mean"],
                "avg_architecture_score": arch_stats["mean"],
                "review_score": rev_stats,
                "retry_count": ret_stats,
                "duration_seconds": dur_stats,
                "coverage_pct": cov_stats,
                "architecture_score": arch_stats,
            }

    def generate_analytics_report(self) -> Dict[str, Any]:
        """Generates comprehensive execution analytics report."""
        with self._lock:
            return {
                "generated_at": time.time(),
                "aggregate_kpis": self.compute_aggregate_kpis(),
                "all_projects_summary": self.get_all_projects_summary(),
                "trends": self.generate_trend_graphs(),
            }

    def _persist_state(self) -> None:
        try:
            self._ensure_storage()
            out_file = self.storage_dir / "execution_analytics.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self._global_runs], f, indent=2)
        except Exception as e:
            logger.error("Failed to persist execution analytics: %s", e)

    def _load_state(self) -> None:
        out_file = self.storage_dir / "execution_analytics.json"
        if out_file.exists():
            try:
                with open(out_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._global_runs = [TaskMetricsRecord.from_dict(d) for d in data]
                    self._project_runs = defaultdict(list)
                    for r in self._global_runs:
                        self._project_runs[r.project].append(r)
            except Exception as e:
                logger.warning("Could not load execution analytics: %s", e)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_runs": len(self._global_runs),
                "total_projects": len(self._project_runs),
            }
