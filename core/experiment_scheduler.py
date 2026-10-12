"""
core/experiment_scheduler.py - Priority Queue & Dependency-Aware Experiment Scheduler (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import enum
import heapq
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


class ScheduledExperimentStatus(str, enum.Enum):
    """Execution status of a queued experiment job."""
    QUEUED = "QUEUED"
    BLOCKED = "BLOCKED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ScheduledExperiment:
    """An individual experiment job queued for automated execution."""
    job_id: str
    name: str
    experiment_fn: Optional[Callable[[], Any]] = None
    priority: int = 50                  # Higher value = higher priority (0 - 100)
    dependencies: List[str] = field(default_factory=list)
    status: ScheduledExperimentStatus = ScheduledExperimentStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


class ExperimentScheduler:
    """
    Priority-based experiment scheduler enforcing dependency sequencing
    and execution lifecycle management.
    """

    def __init__(self, max_concurrent: int = 4) -> None:
        self._lock = threading.RLock()
        self.max_concurrent = max_concurrent
        self._jobs: Dict[str, ScheduledExperiment] = {}
        self._completed_jobs: Dict[str, ScheduledExperiment] = {}

    def schedule_experiment(
        self,
        name: str,
        experiment_fn: Callable[[], Any],
        priority: int = 50,
        dependencies: Optional[List[str]] = None,
    ) -> ScheduledExperiment:
        """Enqueues an experiment job with priority and dependency tracking."""
        with self._lock:
            jid = f"EXPJOB-{uuid.uuid4().hex[:8].upper()}"
            deps = dependencies or []

            # Check if any dependencies are still unfinished
            init_status = ScheduledExperimentStatus.QUEUED
            for dep in deps:
                if dep not in self._completed_jobs or self._completed_jobs[dep].status != ScheduledExperimentStatus.COMPLETED:
                    init_status = ScheduledExperimentStatus.BLOCKED
                    break

            job = ScheduledExperiment(
                job_id=jid,
                name=name,
                experiment_fn=experiment_fn,
                priority=priority,
                dependencies=deps,
                status=init_status,
            )
            self._jobs[jid] = job
            return job

    def get_job(self, job_id: str) -> Optional[ScheduledExperiment]:
        with self._lock:
            return self._jobs.get(job_id) or self._completed_jobs.get(job_id)

    def _update_blocked_statuses(self) -> None:
        """Unblocks jobs whose dependencies have all completed successfully."""
        for job in self._jobs.values():
            if job.status == ScheduledExperimentStatus.BLOCKED:
                all_done = True
                for dep in job.dependencies:
                    dep_job = self._completed_jobs.get(dep)
                    if not dep_job or dep_job.status != ScheduledExperimentStatus.COMPLETED:
                        all_done = False
                        break
                if all_done:
                    job.status = ScheduledExperimentStatus.QUEUED

    def step(self) -> Optional[ScheduledExperiment]:
        """
        Picks and executes the highest-priority eligible QUEUED job.
        Returns the completed job, or None if no jobs are ready.
        """
        with self._lock:
            self._update_blocked_statuses()

            eligible = [j for j in self._jobs.values() if j.status == ScheduledExperimentStatus.QUEUED]
            if not eligible:
                return None

            # Sort by priority descending, then created_at ascending
            eligible.sort(key=lambda j: (-j.priority, j.created_at))
            job = eligible[0]

            job.status = ScheduledExperimentStatus.RUNNING
            job.started_at = time.time()

            try:
                if job.experiment_fn:
                    job.result = job.experiment_fn()
                job.status = ScheduledExperimentStatus.COMPLETED
            except Exception as e:
                job.status = ScheduledExperimentStatus.FAILED
                job.error = str(e)
            finally:
                job.completed_at = time.time()
                # Move to completed
                del self._jobs[job.job_id]
                self._completed_jobs[job.job_id] = job
                self._update_blocked_statuses()

            return job

    def run_all(self, max_steps: int = 100) -> List[ScheduledExperiment]:
        """Drains the experiment queue by stepping until empty or max_steps reached."""
        completed = []
        for _ in range(max_steps):
            job = self.step()
            if not job:
                break
            completed.append(job)
        return completed

    def get_queue_stats(self) -> Dict[str, Any]:
        with self._lock:
            queued = sum(1 for j in self._jobs.values() if j.status == ScheduledExperimentStatus.QUEUED)
            blocked = sum(1 for j in self._jobs.values() if j.status == ScheduledExperimentStatus.BLOCKED)
            completed = sum(1 for j in self._completed_jobs.values() if j.status == ScheduledExperimentStatus.COMPLETED)
            failed = sum(1 for j in self._completed_jobs.values() if j.status == ScheduledExperimentStatus.FAILED)

            return {
                "active_queue_size": len(self._jobs),
                "queued_jobs": queued,
                "blocked_jobs": blocked,
                "completed_jobs": completed,
                "failed_jobs": failed,
            }
