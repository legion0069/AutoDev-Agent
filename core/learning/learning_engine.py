"""
learning_engine.py - Core Autonomous Learning Engine for AutoDev (v3.1)

Coordinates learning events, sessions, snapshots, and distilled institutional knowledge.
Persists learning records to JSON storage and provides high-speed indexing and query capabilities.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.learning.learning_models import (
    LearningEvent,
    LearningEventType,
    LearningKnowledge,
    LearningSession,
    LearningSnapshot,
)

logger = logging.getLogger("AutoDev.Learning.LearningEngine")


class LearningEngine:
    """
    Autonomous Learning Engine.
    Records, indexes, persists, and synthesizes continuous engineering learning events across tasks.
    """

    def __init__(self, storage_dir: Optional[str] = None, auto_persist: bool = True) -> None:
        self._lock = threading.RLock()
        self.storage_dir = Path(storage_dir) if storage_dir else Path("memory/learning")
        self.auto_persist = auto_persist

        # In-memory stores
        self._events: Dict[str, LearningEvent] = {}
        self._sessions: Dict[str, LearningSession] = {}
        self._snapshots: Dict[str, LearningSnapshot] = {}
        self._knowledge_items: Dict[str, LearningKnowledge] = {}

        # Inverted indexes for sub-millisecond retrieval
        self._category_index: Dict[LearningEventType, Set[str]] = defaultdict(set)
        self._project_index: Dict[str, Set[str]] = defaultdict(set)
        self._tag_index: Dict[str, Set[str]] = defaultdict(set)
        self._task_index: Dict[str, Set[str]] = defaultdict(set)

        self._active_session_id: Optional[str] = None
        self._last_persist_time: float = 0.0

        if self.auto_persist:
            self._ensure_storage()
            self._load_state()

    def _ensure_storage(self) -> None:
        """Ensures storage directory exists."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create learning storage dir: {e}")

    def start_session(
        self,
        project: Optional[str] = None,
        project_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LearningSession:
        """Starts a new learning session for a project execution."""
        with self._lock:
            p = project or project_id or "default_project"
            s_id = f"SESS-{int(time.time() * 1000)}-{len(self._sessions) + 1}"
            session = LearningSession(
                session_id=s_id,
                project=p,
                project_id=p,
                start_time=time.time(),
                metadata=metadata or {},
            )
            self._sessions[s_id] = session
            self._active_session_id = s_id
            if self.auto_persist:
                self._persist_state()
            logger.info("Started LearningSession %s for project %s", s_id, p)
            return copy.deepcopy(session)

    def add_event_to_session(self, session_id: str, event: LearningEvent) -> bool:
        """Appends a learning event to an existing session."""
        with self._lock:
            if session_id not in self._sessions:
                return False
            session = self._sessions[session_id]
            if not any(e.id == event.id for e in session.events):
                session.events.append(event)
            session.events_count = len(session.events)
            if event.category == LearningEventType.PATTERN_DISCOVERED:
                session.patterns_discovered = sum(
                    1 for e in session.events if e.category == LearningEventType.PATTERN_DISCOVERED
                )
            session.metrics["events_count"] = session.events_count
            if self.auto_persist:
                self._persist_state()
            return True

    def end_session(self, session_id: Optional[str] = None) -> Optional[LearningSession]:
        """Closes an active learning session and finalizes summary counters."""
        with self._lock:
            target_id = session_id or self._active_session_id
            if not target_id or target_id not in self._sessions:
                return None

            session = self._sessions[target_id]
            session.end_time = time.time()
            session.status = "COMPLETED"
            session.events_count = len(session.events)
            session.metrics["events_count"] = session.events_count
            if self._active_session_id == target_id:
                self._active_session_id = None

            if self.auto_persist:
                self._persist_state()
            logger.info("Closed LearningSession %s (events: %d)", target_id, session.events_count)
            return copy.deepcopy(session)

    def close_session(self, session_id: str) -> Optional[LearningSession]:
        """Alias for end_session."""
        return self.end_session(session_id=session_id)

    def record_event(
        self,
        event_or_category: Union[LearningEvent, LearningEventType] = LearningEventType.BUG_FIXED,
        summary: str = "",
        project: str = "default_project",
        task: Optional[str] = None,
        task_id: Optional[str] = None,
        confidence: float = 0.85,
        importance: float = 75.0,
        affected_files: Optional[List[str]] = None,
        root_cause: str = "",
        solution: str = "",
        metrics: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> LearningEvent:
        """
        Records a new discrete learning event (supports passing a LearningEvent dataclass or field arguments).
        """
        with self._lock:
            now = time.time()
            if isinstance(event_or_category, LearningEvent):
                event = copy.deepcopy(event_or_category)
                if not event.id:
                    event.id = f"EVT-{int(now * 1000)}-{len(self._events) + 1:04d}"
                    event.event_id = event.id
                e_id = event.id
                clean_tags = [t.lower().strip() for t in (event.tags or []) if t.strip()]
                event.tags = clean_tags
            else:
                t_id = task_id or task or kwargs.get("task_id", "task_0")
                e_id = kwargs.get("id") or kwargs.get("event_id") or f"EVT-{int(now * 1000)}-{len(self._events) + 1:04d}"
                if "category" in kwargs:
                    cat_val = kwargs["category"]
                elif event_or_category is not None:
                    cat_val = event_or_category
                else:
                    cat_val = LearningEventType.BUG_FIXED
                cat = cat_val if isinstance(cat_val, LearningEventType) else LearningEventType(cat_val)
                clean_tags = [t.lower().strip() for t in (tags or kwargs.get("tags", [])) if t.strip()]
                event = LearningEvent(
                    id=e_id,
                    event_id=e_id,
                    timestamp=now,
                    project=project or kwargs.get("project_id", "default_project"),
                    task=t_id,
                    task_id=t_id,
                    category=cat,
                    confidence=max(0.0, min(1.0, confidence)),
                    importance=max(0.0, min(100.0, importance)),
                    summary=summary,
                    affected_files=list(affected_files or kwargs.get("files", [])),
                    root_cause=root_cause,
                    solution=solution,
                    metrics=dict(metrics or kwargs.get("key_metrics", {})),
                    tags=clean_tags,
                )

            self._events[e_id] = event

            # Update indexes
            self._category_index[event.category].add(e_id)
            self._project_index[event.project].add(e_id)
            self._task_index[event.task].add(e_id)
            for t in event.tags:
                self._tag_index[t].add(e_id)

            # Update active session counters
            if self._active_session_id and self._active_session_id in self._sessions:
                sess = self._sessions[self._active_session_id]
                sess.events.append(event)
                sess.events_count = len(sess.events)
                sess.metrics["events_count"] = sess.events_count
                if event.category == LearningEventType.PATTERN_DISCOVERED:
                    sess.patterns_discovered += 1

            if self.auto_persist:
                if (now - self._last_persist_time) > 0.05:
                    self._persist_state()
                    self._last_persist_time = now

            logger.debug("Recorded LearningEvent [%s] %s (%s)", e_id, event.category.value, event.summary)
            return copy.deepcopy(event)

    def query_events(
        self,
        category: Optional[LearningEventType] = None,
        project: Optional[str] = None,
        task_id: Optional[str] = None,
        min_confidence: float = 0.0,
        min_importance: float = 0.0,
        tags: Optional[List[str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
    ) -> List[LearningEvent]:
        """
        Executes fast filtered search over historical learning events.
        """
        with self._lock:
            candidate_ids: Optional[Set[str]] = None

            if category is not None:
                candidate_ids = set(self._category_index.get(category, set()))

            if project is not None:
                proj_set = self._project_index.get(project, set())
                candidate_ids = proj_set if candidate_ids is None else (candidate_ids & proj_set)

            if task_id is not None:
                task_set = self._task_index.get(task_id, set())
                candidate_ids = task_set if candidate_ids is None else (candidate_ids & task_set)

            if tags:
                for t in tags:
                    tag_set = self._tag_index.get(t.lower().strip(), set())
                    candidate_ids = tag_set if candidate_ids is None else (candidate_ids & tag_set)

            if candidate_ids is None:
                all_ids = list(self._events.keys())
            else:
                all_ids = list(candidate_ids)

            results: List[LearningEvent] = []
            for eid in all_ids:
                e = self._events.get(eid)
                if not e:
                    continue
                if e.confidence < min_confidence:
                    continue
                if e.importance < min_importance:
                    continue
                if start_time is not None and e.timestamp < start_time:
                    continue
                if end_time is not None and e.timestamp > end_time:
                    continue
                results.append(e)

            # Sort descending by timestamp
            results.sort(key=lambda x: x.timestamp, reverse=True)
            return [copy.deepcopy(x) for x in results[:limit]]

    def get_all_events(self) -> List[LearningEvent]:
        """Returns all registered learning events."""
        with self._lock:
            return [copy.deepcopy(e) for e in self._events.values()]

    def list_events(self) -> List[LearningEvent]:
        """Alias for get_all_events."""
        return self.get_all_events()

    def get_events_by_category(self, category: LearningEventType) -> List[LearningEvent]:
        """Queries events by category."""
        return self.query_events(category=category)

    def get_events_by_project(self, project: str, limit: Optional[int] = None) -> List[LearningEvent]:
        """Queries events by project."""
        return self.query_events(project=project, limit=limit or 100000)

    def get_events_for_project(self, project: str, limit: Optional[int] = None) -> List[LearningEvent]:
        """Alias for get_events_by_project."""
        return self.get_events_by_project(project, limit=limit)

    def get_event(self, event_id: str) -> Optional[LearningEvent]:
        """Retrieves a single learning event by ID."""
        with self._lock:
            e = self._events.get(event_id)
            if not e:
                for ev in self._events.values():
                    if ev.id == event_id or ev.event_id == event_id:
                        e = ev
                        break
            return copy.deepcopy(e) if e else None

    def create_snapshot(self, project: Optional[str] = None) -> LearningSnapshot:
        """Creates a consolidated snapshot of learning intelligence for a project or globally."""
        with self._lock:
            now = time.time()
            snap_id = f"SNAP-{int(now * 1000)}-{len(self._snapshots) + 1}"
            
            target_events = [
                e for e in self._events.values()
                if project is None or e.project == project
            ]
            total_events = len(target_events)
            avg_conf = (
                sum(e.confidence for e in target_events) / total_events
                if total_events > 0
                else 0.0
            )

            category_counts: Dict[str, int] = defaultdict(int)
            for e in target_events:
                category_counts[e.category.value] += 1

            snapshot = LearningSnapshot(
                snapshot_id=snap_id,
                project=project or "ALL",
                timestamp=now,
                total_events=total_events,
                total_patterns=category_counts.get(LearningEventType.PATTERN_DISCOVERED.value, 0),
                total_reflections=len(self._sessions),
                active_playbooks=10,
                average_confidence=round(avg_conf, 2),
                categories_count=dict(category_counts),
                events_by_category=dict(category_counts),
                events=list(target_events),
                key_learnings=[e.summary for e in target_events if e.importance >= 80.0][:10],
                summary_stats={
                    "category_distribution": dict(category_counts),
                    "projects_tracked": len(self._project_index),
                    "unique_tags": len(self._tag_index),
                },
            )
            self._snapshots[snap_id] = snapshot
            if self.auto_persist:
                self._persist_state()
            return copy.deepcopy(snapshot)

    def get_latest_snapshot(self, project: Optional[str] = None) -> Optional[LearningSnapshot]:
        """Retrieves the latest snapshot matching project."""
        with self._lock:
            snaps = [
                s for s in self._snapshots.values()
                if project is None or s.project in (project, "ALL")
            ]
            if not snaps:
                return None
            snaps.sort(key=lambda x: x.timestamp, reverse=True)
            return copy.deepcopy(snaps[0])

    def list_snapshots(self) -> List[LearningSnapshot]:
        """Lists all snapshots."""
        with self._lock:
            return [copy.deepcopy(s) for s in self._snapshots.values()]

    def record_knowledge(
        self,
        domain: str = "General",
        topic: str = "",
        summary: str = "",
        details: str = "",
        evidence_events: Optional[List[str]] = None,
        confidence: float = 0.85,
        utility_score: float = 50.0,
        promoted: bool = False,
        tags: Optional[List[str]] = None,
        title: Optional[str] = None,
        category: Optional[str] = None,
        content: Optional[str] = None,
    ) -> LearningKnowledge:
        """Stores distilled knowledge derived from learning and reflections."""
        with self._lock:
            now = time.time()
            k_id = f"KN-{int(now * 1000)}-{len(self._knowledge_items) + 1:03d}"
            item = LearningKnowledge(
                knowledge_id=k_id,
                domain=domain or category or "General",
                category=category or domain or "General",
                topic=topic or title or "",
                title=title or topic or "",
                summary=summary or content or "",
                content=content or summary or "",
                details=details,
                evidence_events=list(evidence_events or []),
                source_events=list(evidence_events or []),
                confidence=confidence,
                utility_score=utility_score,
                promoted=promoted,
                created_at=now,
                last_accessed=now,
                tags=list(tags or []),
            )
            self._knowledge_items[k_id] = item
            if self.auto_persist:
                self._persist_state()
            return copy.deepcopy(item)

    def store_knowledge(self, **kwargs: Any) -> LearningKnowledge:
        """Alias for record_knowledge."""
        return self.record_knowledge(**kwargs)

    def query_knowledge(
        self,
        domain: Optional[str] = None,
        min_utility: float = 0.0,
        min_confidence: float = 0.0,
        promoted_only: bool = False,
    ) -> List[LearningKnowledge]:
        """Queries stored knowledge items with filtering."""
        with self._lock:
            results: List[LearningKnowledge] = []
            for k in self._knowledge_items.values():
                if domain and k.domain.lower() != domain.lower() and k.category.lower() != domain.lower():
                    continue
                if k.utility_score < min_utility:
                    continue
                if k.confidence < min_confidence:
                    continue
                if promoted_only and not k.promoted:
                    continue
                results.append(k)
            results.sort(key=lambda x: x.utility_score, reverse=True)
            return [copy.deepcopy(k) for k in results]

    def get_all_knowledge(self) -> List[LearningKnowledge]:
        """Returns all knowledge items."""
        with self._lock:
            return [copy.deepcopy(k) for k in self._knowledge_items.values()]

    def list_knowledge(self) -> List[LearningKnowledge]:
        """Alias for get_all_knowledge."""
        return self.get_all_knowledge()

    def get_knowledge(self, knowledge_id: str) -> Optional[LearningKnowledge]:
        """Retrieves a specific knowledge item by ID."""
        with self._lock:
            k = self._knowledge_items.get(knowledge_id)
            if not k:
                for item in self._knowledge_items.values():
                    if item.id == knowledge_id or item.knowledge_id == knowledge_id or item.title == knowledge_id:
                        k = item
                        break
            return copy.deepcopy(k) if k else None

    def get_learning_summary(self) -> Dict[str, Any]:
        """Returns statistical summary of learning intelligence."""
        with self._lock:
            cat_counts = {cat.value: len(ids) for cat, ids in self._category_index.items()}
            return {
                "total_events": len(self._events),
                "total_sessions": len(self._sessions),
                "total_snapshots": len(self._snapshots),
                "total_knowledge_items": len(self._knowledge_items),
                "categories": cat_counts,
                "projects_count": len(self._project_index),
            }

    def list_sessions(self) -> List[LearningSession]:
        """Lists all learning sessions."""
        with self._lock:
            return [copy.deepcopy(s) for s in self._sessions.values()]

    def _persist_state(self) -> None:
        """Atomic serialization of learning state to disk."""
        try:
            self._ensure_storage()
            events_file = self.storage_dir / "learning_events.json"
            sessions_file = self.storage_dir / "learning_sessions.json"
            knowledge_file = self.storage_dir / "learning_knowledge.json"

            with open(events_file, "w", encoding="utf-8") as f:
                json.dump([e.to_dict() for e in self._events.values()], f, indent=2)

            with open(sessions_file, "w", encoding="utf-8") as f:
                json.dump([s.to_dict() for s in self._sessions.values()], f, indent=2)

            with open(knowledge_file, "w", encoding="utf-8") as f:
                json.dump([k.to_dict() for k in self._knowledge_items.values()], f, indent=2)
        except Exception as e:
            logger.error("Failed to persist learning state: %s", e)

    def _load_state(self) -> None:
        """Loads state from JSON files if they exist."""
        events_file = self.storage_dir / "learning_events.json"
        sessions_file = self.storage_dir / "learning_sessions.json"
        knowledge_file = self.storage_dir / "learning_knowledge.json"

        if events_file.exists():
            try:
                with open(events_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        e = LearningEvent.from_dict(item)
                        self._events[e.id] = e
                        self._category_index[e.category].add(e.id)
                        self._project_index[e.project].add(e.id)
                        self._task_index[e.task].add(e.id)
                        for t in e.tags:
                            self._tag_index[t].add(e.id)
            except Exception as e:
                logger.warning("Could not load learning events: %s", e)

        if sessions_file.exists():
            try:
                with open(sessions_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        s = LearningSession.from_dict(item)
                        self._sessions[s.session_id] = s
            except Exception as e:
                logger.warning("Could not load learning sessions: %s", e)

        if knowledge_file.exists():
            try:
                with open(knowledge_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        k = LearningKnowledge.from_dict(item)
                        self._knowledge_items[k.knowledge_id] = k
            except Exception as e:
                logger.warning("Could not load learning knowledge: %s", e)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes current engine state."""
        with self._lock:
            return {
                "total_events": len(self._events),
                "total_sessions": len(self._sessions),
                "total_snapshots": len(self._snapshots),
                "total_knowledge_items": len(self._knowledge_items),
                "categories_active": [c.value for c in self._category_index.keys()],
            }
