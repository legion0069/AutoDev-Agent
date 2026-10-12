"""
AutoDev Shared Workspace (v2.8)
===============================
Thread-safe shared project memory, atomic fine-grained file locking,
pending change staging, review comment threads, and approval state tracking.
"""

from __future__ import annotations

import collections
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from core.collaboration.collaboration_models import (
    AgentRole,
    FileLock,
    ReviewComment,
    StagedChange,
)

logger = logging.getLogger("AutoDev.SharedWorkspace")


class LockAcquisitionError(Exception):
    """Raised when an exclusive or shared lock cannot be acquired."""
    pass


class SharedWorkspace:
    """
    Shared project memory coordinating concurrent agent activities.
    Manages atomic file locks, pending staged changes, temporary artifacts,
    and threaded review comments.
    """

    def __init__(self, workspace_root: str = ".", default_lock_timeout: float = 60.0):
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.default_lock_timeout = default_lock_timeout
        self._lock = threading.RLock()

        # Active locks: normalized_path -> FileLock
        self._locks: Dict[str, FileLock] = {}
        # Shared read locks: normalized_path -> Set[agent_id]
        self._shared_read_locks: Dict[str, Set[str]] = collections.defaultdict(set)

        # File ownership tracking: normalized_path -> primary_owner_agent_id
        self._file_ownership: Dict[str, str] = {}
        # Modified files history: normalized_path -> List of agent_ids who modified it
        self._file_modification_history: Dict[str, List[str]] = collections.defaultdict(list)

        # Staged pending changes: normalized_path -> StagedChange
        self._staged_changes: Dict[str, StagedChange] = {}

        # Temporary artifacts: artifact_key -> {"data": Any, "created_by": str, "timestamp": float}
        self._artifacts: Dict[str, Dict[str, Any]] = {}

        # Review comments: file_path -> List[ReviewComment]
        self._review_comments: Dict[str, List[ReviewComment]] = collections.defaultdict(list)

    def _normalize_path(self, path: str) -> str:
        """Normalizes relative or absolute file paths for consistent indexing."""
        clean = path.replace("\\", "/")
        if os.path.isabs(clean):
            try:
                clean = os.path.relpath(clean, self.workspace_root).replace("\\", "/")
            except ValueError:
                pass
        return clean.lstrip("./")

    # ------------------------------------------------------------------
    # Ownership & Locks
    # ------------------------------------------------------------------

    def claim_ownership(self, file_path: str, owner_id: str, role: Optional[AgentRole] = None) -> None:
        """Assign primary ownership of a file to an agent."""
        norm_path = self._normalize_path(file_path)
        with self._lock:
            self._file_ownership[norm_path] = owner_id

    def get_owner(self, file_path: str) -> Optional[str]:
        norm_path = self._normalize_path(file_path)
        with self._lock:
            return self._file_ownership.get(norm_path)

    def acquire_lock(
        self,
        file_path: str,
        holder: Optional[str] = None,
        agent_id: Optional[str] = None,
        role: Optional[Union[AgentRole, str]] = None,
        is_exclusive: bool = True,
        lock_type: Optional[str] = None,
        ttl: Optional[float] = None,
        timeout: Optional[float] = None,
        task_id: Optional[str] = None,
    ) -> Optional[FileLock]:
        """
        Acquire an atomic read/write lock on a file path.
        Returns FileLock on success, None or raises LockAcquisitionError on conflict.
        """
        agent = holder or agent_id or "anonymous"
        exclusive = is_exclusive if lock_type is None else (lock_type == "exclusive")
        duration = ttl or timeout or self.default_lock_timeout
        norm_path = self._normalize_path(file_path)
        agent_role = role if isinstance(role, AgentRole) else AgentRole.GENERAL

        with self._lock:
            self._cleanup_expired_locks()

            existing_lock = self._locks.get(norm_path)

            if exclusive:
                # Exclusive write lock requires no other exclusive lock and no active shared read locks
                if existing_lock and not existing_lock.is_expired and existing_lock.holder != agent:
                    return None
                if self._shared_read_locks.get(norm_path) and any(aid != agent for aid in self._shared_read_locks[norm_path]):
                    return None

                lock = FileLock(
                    file_path=norm_path,
                    holder=agent,
                    role=agent_role,
                    is_exclusive=True,
                    acquired_at=time.time(),
                    expires_at=time.time() + duration,
                    task_id=task_id,
                )
                self._locks[norm_path] = lock
                return lock
            else:
                # Shared read lock requires no exclusive write lock
                if existing_lock and not existing_lock.is_expired and existing_lock.is_exclusive and existing_lock.holder != agent:
                    return None

                self._shared_read_locks[norm_path].add(agent)
                lock = FileLock(
                    file_path=norm_path,
                    holder=agent,
                    role=agent_role,
                    is_exclusive=False,
                    acquired_at=time.time(),
                    expires_at=time.time() + duration,
                    task_id=task_id,
                )
                return lock

    def release_lock(self, file_path: str, holder: Optional[str] = None, agent_id: Optional[str] = None) -> bool:
        """Release a held lock on a workspace file."""
        agent = holder or agent_id
        norm_path = self._normalize_path(file_path)

        with self._lock:
            released = False
            if norm_path in self._locks:
                if not agent or self._locks[norm_path].holder == agent:
                    del self._locks[norm_path]
                    released = True

            if norm_path in self._shared_read_locks:
                if agent and agent in self._shared_read_locks[norm_path]:
                    self._shared_read_locks[norm_path].remove(agent)
                    released = True
                elif not agent:
                    self._shared_read_locks[norm_path].clear()
                    released = True

            return released

    def _cleanup_expired_locks(self) -> None:
        """Removes expired exclusive and shared locks."""
        now = time.time()
        expired_paths = [p for p, l in self._locks.items() if l.expires_at < now]
        for p in expired_paths:
            del self._locks[p]

    # ------------------------------------------------------------------
    # Staging & Reviews
    # ------------------------------------------------------------------

    def stage_change(
        self,
        file_path: str,
        content: str,
        author_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        role: Optional[Union[AgentRole, str]] = None,
        commit_message: str = "",
        diff: Optional[str] = None,
    ) -> StagedChange:
        """Stage an in-memory modification for peer review."""
        norm_path = self._normalize_path(file_path)
        author = author_id or agent_id or "anonymous"
        agent_role = role if isinstance(role, AgentRole) else AgentRole.GENERAL

        staged = StagedChange(
            file_path=norm_path,
            author_id=author,
            role=agent_role,
            content=content,
            diff=diff,
            commit_message=commit_message,
            staged_at=time.time(),
        )

        with self._lock:
            self._staged_changes[norm_path] = staged
            self._file_modification_history[norm_path].append(author)

        logger.info("Staged change on '%s' by %s (%s)", norm_path, author, commit_message)
        return staged

    def get_staged_change(self, file_path: str) -> Optional[StagedChange]:
        norm_path = self._normalize_path(file_path)
        with self._lock:
            return self._staged_changes.get(norm_path)

    def get_staged_changes(self) -> Dict[str, StagedChange]:
        with self._lock:
            return dict(self._staged_changes)

    def add_review_comment(
        self,
        file_path: str,
        comment: str,
        author_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        role: Optional[Union[AgentRole, str]] = None,
        severity: str = "INFO",
        line_number: Optional[int] = None,
        is_blocking: bool = False,
    ) -> ReviewComment:
        """Attach a review comment to a staged file."""
        norm_path = self._normalize_path(file_path)
        author = author_id or agent_id or "reviewer"
        agent_role = role if isinstance(role, AgentRole) else AgentRole.GENERAL

        rc = ReviewComment(
            file_path=norm_path,
            author_id=author,
            role=agent_role,
            comment=comment,
            line_number=line_number,
            severity=severity,
            is_blocking=is_blocking,
            timestamp=time.time(),
        )

        with self._lock:
            self._review_comments[norm_path].append(rc)
            if norm_path in self._staged_changes:
                self._staged_changes[norm_path].comments.append(rc)
                if author not in self._staged_changes[norm_path].reviewers:
                    self._staged_changes[norm_path].reviewers.append(author)

        return rc

    def approve_staged_change(self, file_path: str, reviewer_id: str = "Reviewer") -> bool:
        """Approve a staged change for commit."""
        norm_path = self._normalize_path(file_path)
        with self._lock:
            staged = self._staged_changes.get(norm_path)
            if not staged:
                return False
            staged.is_approved = True
            staged.approved_at = time.time()
            if reviewer_id not in staged.reviewers:
                staged.reviewers.append(reviewer_id)
            return True

    def reject_staged_change(self, file_path: str, reviewer_id: str = "Reviewer", reason: str = "") -> bool:
        """Reject a staged change."""
        norm_path = self._normalize_path(file_path)
        with self._lock:
            staged = self._staged_changes.get(norm_path)
            if not staged:
                return False
            staged.is_approved = False
            self.add_review_comment(file_path, comment=reason or "Rejected by reviewer", author_id=reviewer_id, severity="BLOCKER", is_blocking=True)
            return True

    # ------------------------------------------------------------------
    # Artifact Storage
    # ------------------------------------------------------------------

    def put_artifact(
        self,
        artifact_key: str,
        data: Any,
        creator: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> None:
        """Store an in-memory temporary artifact."""
        author = creator or created_by or "system"
        with self._lock:
            self._artifacts[artifact_key] = {
                "data": data,
                "created_by": author,
                "timestamp": time.time(),
            }

    def get_artifact(self, artifact_key: str) -> Optional[Any]:
        """Retrieve stored temporary artifact."""
        with self._lock:
            entry = self._artifacts.get(artifact_key)
            if not entry:
                return None
            return entry.get("data")

    def clear(self) -> None:
        """Reset workspace state."""
        with self._lock:
            self._locks.clear()
            self._shared_read_locks.clear()
            self._file_ownership.clear()
            self._staged_changes.clear()
            self._artifacts.clear()
            self._review_comments.clear()
