"""
core/research_memory.py - Persistent Enterprise Research Knowledge & Memory Bank (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ResearchIdea:
    """An ideation entry or preliminary scientific proposition."""
    idea_id: str
    title: str
    description: str
    author: str
    priority: str = "MEDIUM"            # LOW, MEDIUM, HIGH
    tags: List[str] = field(default_factory=list)
    status: str = "PROPOSED"            # PROPOSED, EXPLORING, CONVERTED, ARCHIVED
    created_at: float = field(default_factory=time.time)


@dataclass
class ResearchFailure:
    """Negative result or anti-pattern recorded to prevent repetitive dead ends."""
    failure_id: str
    experiment_id: str
    description: str
    root_cause: str
    lessons_learned: str
    tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ResearchSuccess:
    """Scientific breakthrough or confirmed performance leap."""
    success_id: str
    experiment_id: str
    breakthrough_summary: str
    performance_gain_pct: float
    impact_level: str = "HIGH"          # MODERATE, HIGH, TRANSFORMATIVE
    timestamp: float = field(default_factory=time.time)


@dataclass
class ResearchNote:
    """Informal laboratory note, theoretical derivation, or observation."""
    note_id: str
    title: str
    content: str
    author: str
    tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class FutureWorkItem:
    """Identified research avenue or open problem for subsequent cycles."""
    item_id: str
    title: str
    description: str
    domain: str
    estimated_effort: str = "MEDIUM"    # SMALL, MEDIUM, LARGE
    tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class ResearchMemory:
    """
    Longitudinal memory bank managing corporate ideas, experiments, benchmarks,
    failures, successes, papers, patents, research notes, and future work.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ideas: Dict[str, ResearchIdea] = {}
        self._failures: Dict[str, ResearchFailure] = {}
        self._successes: Dict[str, ResearchSuccess] = {}
        self._notes: Dict[str, ResearchNote] = {}
        self._future_work: Dict[str, FutureWorkItem] = {}
        self._experiments: Dict[str, Dict[str, Any]] = {}
        self._benchmarks: Dict[str, Dict[str, Any]] = {}
        self._papers: Dict[str, Dict[str, Any]] = {}
        self._patents: Dict[str, Dict[str, Any]] = {}

    # -------------------------------------------------------------------------
    # Ideas
    # -------------------------------------------------------------------------

    def add_idea(self, title: str, description: str, author: str = "Researcher", priority: str = "MEDIUM", tags: Optional[List[str]] = None) -> ResearchIdea:
        with self._lock:
            iid = f"IDEA-{uuid.uuid4().hex[:8].upper()}"
            idea = ResearchIdea(iid, title, description, author, priority, tags or [])
            self._ideas[iid] = idea
            return idea

    def get_idea(self, idea_id: str) -> Optional[ResearchIdea]:
        with self._lock:
            return self._ideas.get(idea_id)

    def list_ideas(self) -> List[ResearchIdea]:
        with self._lock:
            return list(self._ideas.values())

    # -------------------------------------------------------------------------
    # Failures & Successes
    # -------------------------------------------------------------------------

    def record_failure(self, experiment_id: str, description: str, root_cause: str, lessons_learned: str, tags: Optional[List[str]] = None) -> ResearchFailure:
        with self._lock:
            fid = f"FAIL-{uuid.uuid4().hex[:8].upper()}"
            fail = ResearchFailure(fid, experiment_id, description, root_cause, lessons_learned, tags or [])
            self._failures[fid] = fail
            return fail

    def record_success(self, experiment_id: str, breakthrough_summary: str, performance_gain_pct: float, impact_level: str = "HIGH") -> ResearchSuccess:
        with self._lock:
            sid = f"SUCC-{uuid.uuid4().hex[:8].upper()}"
            succ = ResearchSuccess(sid, experiment_id, breakthrough_summary, performance_gain_pct, impact_level)
            self._successes[sid] = succ
            return succ

    # -------------------------------------------------------------------------
    # Notes & Future Work
    # -------------------------------------------------------------------------

    def add_note(self, title: str, content: str, author: str = "Researcher", tags: Optional[List[str]] = None) -> ResearchNote:
        with self._lock:
            nid = f"NOTE-{uuid.uuid4().hex[:8].upper()}"
            note = ResearchNote(nid, title, content, author, tags or [])
            self._notes[nid] = note
            return note

    def add_future_work(self, title: str, description: str, domain: str = "General", estimated_effort: str = "MEDIUM", tags: Optional[List[str]] = None) -> FutureWorkItem:
        with self._lock:
            fwid = f"FW-{uuid.uuid4().hex[:8].upper()}"
            fw = FutureWorkItem(fwid, title, description, domain, estimated_effort, tags or [])
            self._future_work[fwid] = fw
            return fw

    # -------------------------------------------------------------------------
    # Experiments, Benchmarks, Papers, Patents Storage
    # -------------------------------------------------------------------------

    def store_experiment(self, exp_id: str, record: Dict[str, Any]) -> None:
        with self._lock:
            self._experiments[exp_id] = record

    def get_experiment(self, exp_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._experiments.get(exp_id)

    def store_benchmark(self, bench_id: str, record: Dict[str, Any]) -> None:
        with self._lock:
            self._benchmarks[bench_id] = record

    def store_paper(self, paper_id: str, record: Dict[str, Any]) -> None:
        with self._lock:
            self._papers[paper_id] = record

    def get_paper(self, paper_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._papers.get(paper_id)

    def store_patent(self, patent_id: str, record: Dict[str, Any]) -> None:
        with self._lock:
            self._patents[patent_id] = record

    def get_patent(self, patent_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._patents.get(patent_id)

    # -------------------------------------------------------------------------
    # Search & Summary Telemetry
    # -------------------------------------------------------------------------

    def search(self, query: str) -> Dict[str, List[Any]]:
        """Multi-category keyword search across ideas, successes, failures, notes, and publications."""
        with self._lock:
            q = query.lower()
            return {
                "ideas": [i for i in self._ideas.values() if q in i.title.lower() or q in i.description.lower()],
                "successes": [s for s in self._successes.values() if q in s.breakthrough_summary.lower()],
                "failures": [f for f in self._failures.values() if q in f.description.lower() or q in f.lessons_learned.lower()],
                "notes": [n for n in self._notes.values() if q in n.title.lower() or q in n.content.lower()],
                "papers": [p for p in self._papers.values() if q in p.get("title", "").lower() or q in p.get("abstract", "").lower()],
                "patents": [pt for pt in self._patents.values() if q in pt.get("title", "").lower() or q in pt.get("abstract", "").lower()],
            }

    def get_memory_stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "ideas_count": len(self._ideas),
                "experiments_count": len(self._experiments),
                "benchmarks_count": len(self._benchmarks),
                "failures_count": len(self._failures),
                "successes_count": len(self._successes),
                "papers_count": len(self._papers),
                "patents_count": len(self._patents),
                "notes_count": len(self._notes),
                "future_work_count": len(self._future_work),
            }
