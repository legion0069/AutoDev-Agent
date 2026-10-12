"""
AutoDev Shared Workspace Subsystem.

Provides thread-safe blackboard / shared memory accessible by every engineer in the
organization, holding project state, current branch, artifacts, design decisions,
active bugs, active reviews, and execution logs.
"""

from __future__ import annotations

import copy
import threading
import time
from typing import Any, Dict, List, Optional


class SharedWorkspace:
    """
    Centralized shared memory and blackboard architecture for multi-agent organization.
    Thread-safe and deterministic.
    """

    def __init__(self, initial_branch: str = "main") -> None:
        self._lock = threading.RLock()
        self._current_branch = initial_branch
        self._project_state: Dict[str, Any] = {}
        self._artifacts: Dict[str, Dict[str, Any]] = {}
        self._temporary_notes: List[Dict[str, Any]] = []
        self._design_decisions: List[Dict[str, Any]] = []
        self._active_bugs: Dict[str, Dict[str, Any]] = {}
        self._active_reviews: Dict[str, Dict[str, Any]] = {}
        self._execution_logs: List[Dict[str, Any]] = []

    # Branch & Project State
    def set_branch(self, branch_name: str) -> None:
        """Sets current active branch in the workspace."""
        with self._lock:
            self._current_branch = branch_name
            self.append_log(f"Switched branch to '{branch_name}'", level="INFO")

    def get_branch(self) -> str:
        """Returns current branch name."""
        with self._lock:
            return self._current_branch

    def set_state(self, key: str, value: Any) -> None:
        """Sets arbitrary project state key."""
        with self._lock:
            self._project_state[key] = copy.deepcopy(value)

    def get_state(self, key: str, default: Any = None) -> Any:
        """Retrieves project state value."""
        with self._lock:
            val = self._project_state.get(key, default)
            return copy.deepcopy(val)

    # Artifacts
    def store_artifact(
        self,
        artifact_id: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Stores or overwrites an artifact in the shared workspace."""
        with self._lock:
            self._artifacts[artifact_id] = {
                "artifact_id": artifact_id,
                "content": copy.deepcopy(content),
                "metadata": copy.deepcopy(metadata or {}),
                "updated_at": time.time(),
            }

    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves an artifact by ID."""
        with self._lock:
            if artifact_id in self._artifacts:
                return copy.deepcopy(self._artifacts[artifact_id])
            return None

    def list_artifacts(self) -> List[str]:
        """Lists all stored artifact IDs in sorted order."""
        with self._lock:
            return sorted(list(self._artifacts.keys()))

    # Temporary Notes
    def add_note(self, topic: str, note: str, author_id: str) -> None:
        """Adds a temporary engineer note/scratchpad entry."""
        with self._lock:
            self._temporary_notes.append({
                "topic": topic,
                "note": note,
                "author_id": author_id,
                "timestamp": time.time(),
            })

    def get_notes(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all notes, optionally filtered by topic."""
        with self._lock:
            if topic is None:
                return copy.deepcopy(self._temporary_notes)
            return [
                copy.deepcopy(n) for n in self._temporary_notes
                if n["topic"] == topic
            ]

    # Design Decisions
    def record_design_decision(
        self,
        decision_id: str,
        title: str,
        decision: str,
        author_id: str,
        rationale: str = "",
    ) -> None:
        """Records an architectural or design decision in the shared record."""
        with self._lock:
            self._design_decisions.append({
                "decision_id": decision_id,
                "title": title,
                "decision": decision,
                "author_id": author_id,
                "rationale": rationale,
                "timestamp": time.time(),
            })

    def get_design_decisions(self) -> List[Dict[str, Any]]:
        """Returns all recorded design decisions."""
        with self._lock:
            return copy.deepcopy(self._design_decisions)

    # Bugs
    def report_bug(
        self,
        bug_id: str,
        title: str,
        severity: str,
        reported_by: str,
        details: str = "",
    ) -> None:
        """Registers a discovered bug in the shared workspace."""
        with self._lock:
            self._active_bugs[bug_id] = {
                "bug_id": bug_id,
                "title": title,
                "severity": severity,
                "reported_by": reported_by,
                "details": details,
                "status": "OPEN",
                "created_at": time.time(),
                "resolved_by": None,
                "resolved_at": None,
                "fix_notes": "",
            }

    def resolve_bug(self, bug_id: str, resolved_by: str, fix_notes: str = "") -> bool:
        """Marks a bug as resolved."""
        with self._lock:
            if bug_id in self._active_bugs:
                bug = self._active_bugs[bug_id]
                bug["status"] = "RESOLVED"
                bug["resolved_by"] = resolved_by
                bug["resolved_at"] = time.time()
                bug["fix_notes"] = fix_notes
                return True
            return False

    def get_active_bugs(self, include_resolved: bool = False) -> List[Dict[str, Any]]:
        """Returns active bugs list."""
        with self._lock:
            if include_resolved:
                return copy.deepcopy(list(self._active_bugs.values()))
            return [
                copy.deepcopy(b) for b in self._active_bugs.values()
                if b["status"] == "OPEN"
            ]

    # Reviews
    def add_review(
        self,
        review_id: str,
        task_id: str,
        reviewer_id: str,
        status: str = "PENDING",
        comments: str = "",
    ) -> None:
        """Adds or updates a code review record."""
        with self._lock:
            self._active_reviews[review_id] = {
                "review_id": review_id,
                "task_id": task_id,
                "reviewer_id": reviewer_id,
                "status": status,
                "comments": comments,
                "updated_at": time.time(),
            }

    def get_active_reviews(self) -> List[Dict[str, Any]]:
        """Returns list of all registered reviews."""
        with self._lock:
            return copy.deepcopy(list(self._active_reviews.values()))

    # Execution Logs
    def append_log(
        self,
        entry: str,
        level: str = "INFO",
        source: str = "workspace"
    ) -> None:
        """Appends an execution log entry to shared workspace memory."""
        with self._lock:
            self._execution_logs.append({
                "entry": entry,
                "level": level,
                "source": source,
                "timestamp": time.time(),
            })

    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns recent logs up to limit."""
        with self._lock:
            return copy.deepcopy(self._execution_logs[-limit:])

    # Snapshotting
    def export_snapshot(self) -> Dict[str, Any]:
        """Exports full state of shared workspace as a serializable dictionary."""
        with self._lock:
            return {
                "current_branch": self._current_branch,
                "project_state": copy.deepcopy(self._project_state),
                "artifacts": copy.deepcopy(self._artifacts),
                "temporary_notes": copy.deepcopy(self._temporary_notes),
                "design_decisions": copy.deepcopy(self._design_decisions),
                "active_bugs": copy.deepcopy(self._active_bugs),
                "active_reviews": copy.deepcopy(self._active_reviews),
                "execution_logs": copy.deepcopy(self._execution_logs),
            }

    def load_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Loads state from an exported snapshot dictionary."""
        with self._lock:
            self._current_branch = snapshot.get("current_branch", "main")
            self._project_state = copy.deepcopy(snapshot.get("project_state", {}))
            self._artifacts = copy.deepcopy(snapshot.get("artifacts", {}))
            self._temporary_notes = copy.deepcopy(snapshot.get("temporary_notes", []))
            self._design_decisions = copy.deepcopy(snapshot.get("design_decisions", []))
            self._active_bugs = copy.deepcopy(snapshot.get("active_bugs", {}))
            self._active_reviews = copy.deepcopy(snapshot.get("active_reviews", {}))
            self._execution_logs = copy.deepcopy(snapshot.get("execution_logs", []))
