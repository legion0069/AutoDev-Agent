"""
knowledge_evolution.py - Institutional Knowledge Evolution & Memory Curation Engine for AutoDev (v3.1)

Maintains long-term institutional memory quality by detecting near-duplicate knowledge items,
merging overlapping memories using Jaccard token similarity, archiving stale low-utility records,
and promoting battle-tested engineering knowledge into core corporate standards.
"""

from __future__ import annotations

import copy
import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.learning.learning_models import LearningKnowledge

logger = logging.getLogger("AutoDev.Learning.KnowledgeEvolution")


class KnowledgeEvolutionEngine:
    """
    Knowledge Evolution & Curation Engine.
    Executes similarity matching, semantic memory merging, stale item archiving, and promotion.
    """

    def __init__(self, storage_dir: Optional[str] = None, auto_persist: bool = True) -> None:
        self._lock = threading.RLock()
        self.storage_dir = Path(storage_dir) if storage_dir else Path("memory/learning")
        self.auto_persist = auto_persist
        
        self._active_knowledge: Dict[str, LearningKnowledge] = {}
        self._archived_knowledge: Dict[str, LearningKnowledge] = {}
        self._promoted_knowledge: Dict[str, LearningKnowledge] = {}

        if self.auto_persist:
            self._ensure_storage()
            self._load_state()

    def _ensure_storage(self) -> None:
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Could not create knowledge evolution storage directory: %s", e)

    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Computes semantic word token similarity (0.0 to 1.0) between two text blocks
        using stopword-filtered token overlap and Dice similarity coefficient.
        """
        t1 = text1.strip()
        t2 = text2.strip()
        if not t1 and not t2:
            return 1.0
        if not t1 or not t2:
            return 0.0
        if t1.lower() == t2.lower():
            return 1.0

        stopwords = {
            "a", "an", "the", "to", "in", "on", "at", "of", "for", "with", "by", "from",
            "is", "are", "was", "were", "be", "been", "before", "after", "and", "or", "as",
        }
        raw_tokens1 = re.findall(r"\w+", t1.lower())
        raw_tokens2 = re.findall(r"\w+", t2.lower())

        if not raw_tokens1 or not raw_tokens2:
            return 0.0

        tokens1 = set(t for t in raw_tokens1 if t not in stopwords) or set(raw_tokens1)
        tokens2 = set(t for t in raw_tokens2 if t not in stopwords) or set(raw_tokens2)

        intersection = len(tokens1 & tokens2)
        if not intersection:
            return 0.0

        jaccard = intersection / len(tokens1 | tokens2)
        dice = (2.0 * intersection) / (len(tokens1) + len(tokens2))
        overlap = intersection / min(len(tokens1), len(tokens2))

        # Combined metric balancing overlap and Dice
        score = max(jaccard, dice, 0.5 * (dice + overlap))
        return round(score, 4)

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Alias for calculate_text_similarity."""
        return self.calculate_text_similarity(text1, text2)

    def add_knowledge(self, item: LearningKnowledge) -> None:
        """Adds a knowledge item to the active working set."""
        with self._lock:
            k_id = item.id or item.knowledge_id
            self._active_knowledge[k_id] = copy.deepcopy(item)
            if self.auto_persist:
                self._persist_state()

    def consolidate_and_deduplicate(self, similarity_threshold: float = 0.40) -> List[LearningKnowledge]:
        """Merges similar items in the active knowledge base and updates active items."""
        with self._lock:
            items = list(self._active_knowledge.values())
            merged = self.merge_similar_knowledge(items, similarity_threshold=similarity_threshold)
            self._active_knowledge = {k.id or k.knowledge_id: k for k in merged}
            if self.auto_persist:
                self._persist_state()
            return [copy.deepcopy(k) for k in merged]

    def promote_proven_knowledge(self, min_utility: float = 90.0, min_confidence: float = 0.80) -> List[LearningKnowledge]:
        """Promotes high utility items from active knowledge."""
        with self._lock:
            items = list(self._active_knowledge.values())
            promoted = []
            for item in items:
                if item.utility_score >= min_utility and item.confidence >= min_confidence:
                    item.promoted = True
                    promoted.append(item)
                    self._promoted_knowledge[item.id or item.knowledge_id] = copy.deepcopy(item)
            if self.auto_persist:
                self._persist_state()
            return [copy.deepcopy(k) for k in promoted]

    def archive_stale_knowledge(self, max_idle_days: int = 180) -> List[LearningKnowledge]:
        """Archives items inactive for more than max_idle_days or having low utility (< 30.0)."""
        with self._lock:
            now = time.time()
            cutoff = now - (max_idle_days * 86400)
            archived = []
            active = {}
            for k_id, item in self._active_knowledge.items():
                if (item.last_accessed and item.last_accessed < cutoff) or item.utility_score < 30.0:
                    item.status = "ARCHIVED"
                    self._archived_knowledge[k_id] = copy.deepcopy(item)
                    archived.append(copy.deepcopy(item))
                else:
                    active[k_id] = item
            self._active_knowledge = active
            if self.auto_persist:
                self._persist_state()
            return archived

    def query_knowledge(self, query: str, top_k: int = 5) -> List[LearningKnowledge]:
        """Queries the active knowledge base for relevant items."""
        with self._lock:
            scored = []
            for item in self._active_knowledge.values():
                text = f"{item.topic} {item.title} {item.domain} {item.category} {item.summary} {item.content} {item.details}"
                sim = self.calculate_text_similarity(query, text)
                scored.append((sim, item))
            scored.sort(key=lambda x: (x[0], x[1].utility_score), reverse=True)
            return [copy.deepcopy(item) for sim, item in scored[:top_k]]

    def evolve_knowledge(self, items: List[LearningKnowledge]) -> List[LearningKnowledge]:
        """Alias for running evolution cycle returning merged active knowledge."""
        if not items:
            return []
        res = self.run_knowledge_evolution_cycle(items)
        return self.get_curated_knowledge()

    def merge_similar_knowledge(
        self,
        knowledge_items: List[LearningKnowledge],
        similarity_threshold: float = 0.60,
    ) -> List[LearningKnowledge]:
        """
        Detects and merges near-duplicate knowledge items within the provided list.
        """
        with self._lock:
            working_items = [copy.deepcopy(k) for k in knowledge_items]
            merged_result: List[LearningKnowledge] = []
            consumed_indices: Set[int] = set()

            for i in range(len(working_items)):
                if i in consumed_indices:
                    continue

                primary = working_items[i]
                for j in range(i + 1, len(working_items)):
                    if j in consumed_indices:
                        continue

                    candidate = working_items[j]
                    text_a = f"{primary.topic} {primary.summary} {primary.details}"
                    text_b = f"{candidate.topic} {candidate.summary} {candidate.details}"
                    sim = self.calculate_text_similarity(text_a, text_b)

                    if sim >= similarity_threshold:
                        # Merge candidate into primary
                        primary.confidence = max(primary.confidence, candidate.confidence)
                        primary.utility_score = max(primary.utility_score, candidate.utility_score)
                        primary.usage_count += candidate.usage_count
                        primary.last_accessed = max(primary.last_accessed, candidate.last_accessed)

                        all_events = set(primary.evidence_events) | set(candidate.evidence_events)
                        primary.evidence_events = sorted(list(all_events))
                        primary.source_events = list(primary.evidence_events)

                        all_tags = set(primary.tags) | set(candidate.tags)
                        primary.tags = sorted(list(all_tags))

                        if candidate.details and candidate.details not in primary.details:
                            primary.details = (primary.details + "\n" + candidate.details).strip()

                        consumed_indices.add(j)

                merged_result.append(primary)

            return merged_result

    def archive_obsolete_knowledge(
        self,
        knowledge_items: List[LearningKnowledge],
        utility_threshold: float = 40.0,
        confidence_threshold: float = 0.50,
    ) -> Tuple[List[LearningKnowledge], List[LearningKnowledge]]:
        """
        Partitions knowledge items into active and archived sets.
        """
        with self._lock:
            active: List[LearningKnowledge] = []
            archived: List[LearningKnowledge] = []

            for item in knowledge_items:
                if item.utility_score < utility_threshold or item.confidence < confidence_threshold:
                    archived.append(copy.deepcopy(item))
                    self._archived_knowledge[item.knowledge_id] = copy.deepcopy(item)
                else:
                    active.append(copy.deepcopy(item))
                    self._active_knowledge[item.knowledge_id] = copy.deepcopy(item)

            if self.auto_persist:
                self._persist_state()

            return active, archived

    def promote_high_utility_standards(
        self,
        knowledge_items: List[LearningKnowledge],
        min_utility: float = 90.0,
        min_confidence: float = 0.95,
    ) -> List[LearningKnowledge]:
        """
        Promotes verified, high-utility knowledge items to official engineering standards.
        """
        with self._lock:
            promoted: List[LearningKnowledge] = []
            for item in knowledge_items:
                if item.utility_score >= min_utility and item.confidence >= min_confidence:
                    promoted_item = copy.deepcopy(item)
                    promoted_item.promoted = True
                    promoted.append(promoted_item)
                    self._promoted_knowledge[item.knowledge_id] = promoted_item

            if self.auto_persist:
                self._persist_state()

            return promoted

    def run_knowledge_evolution_cycle(
        self,
        knowledge_items: List[LearningKnowledge],
        similarity_threshold: float = 0.60,
        utility_threshold: float = 40.0,
        confidence_threshold: float = 0.50,
        promote_utility: float = 90.0,
        promote_confidence: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Runs the full evolution cycle on a collection of knowledge items:
        1. Merge similar items
        2. Archive low utility / low confidence items
        3. Promote high standard items
        """
        with self._lock:
            initial_count = len(knowledge_items)
            
            # 1. Merge
            merged = self.merge_similar_knowledge(knowledge_items, similarity_threshold)
            merged_count = initial_count - len(merged)

            # 2. Archive
            active, archived = self.archive_obsolete_knowledge(
                merged, utility_threshold, confidence_threshold
            )

            # 3. Promote
            promoted = self.promote_high_utility_standards(
                active, promote_utility, promote_confidence
            )

            return {
                "initial_count": initial_count,
                "merged_count": merged_count,
                "archived_count": len(archived),
                "promoted_count": len(promoted),
                "final_active_count": len(active),
                "remaining_knowledge_count": len(active),
            }

    def evolve_knowledge_base(self, knowledge_items: List[LearningKnowledge], **kwargs: Any) -> Dict[str, Any]:
        """Alias for run_knowledge_evolution_cycle."""
        return self.run_knowledge_evolution_cycle(knowledge_items, **kwargs)

    def get_curated_knowledge(self) -> List[LearningKnowledge]:
        """Returns all active curated knowledge."""
        with self._lock:
            return [copy.deepcopy(k) for k in self._active_knowledge.values()]

    def get_promoted_knowledge(self) -> List[LearningKnowledge]:
        """Returns promoted corporate standards."""
        with self._lock:
            return [copy.deepcopy(k) for k in self._promoted_knowledge.values()]

    def get_archived_knowledge(self) -> List[LearningKnowledge]:
        """Returns archived historical knowledge."""
        with self._lock:
            return [copy.deepcopy(k) for k in self._archived_knowledge.values()]

    def _persist_state(self) -> None:
        try:
            self._ensure_storage()
            active_file = self.storage_dir / "evolved_knowledge_active.json"
            archived_file = self.storage_dir / "evolved_knowledge_archived.json"
            promoted_file = self.storage_dir / "evolved_knowledge_promoted.json"

            with open(active_file, "w", encoding="utf-8") as f:
                json.dump([k.to_dict() for k in self._active_knowledge.values()], f, indent=2)

            with open(archived_file, "w", encoding="utf-8") as f:
                json.dump([k.to_dict() for k in self._archived_knowledge.values()], f, indent=2)

            with open(promoted_file, "w", encoding="utf-8") as f:
                json.dump([k.to_dict() for k in self._promoted_knowledge.values()], f, indent=2)
        except Exception as e:
            logger.error("Failed to persist evolved knowledge: %s", e)

    def _load_state(self) -> None:
        active_file = self.storage_dir / "evolved_knowledge_active.json"
        archived_file = self.storage_dir / "evolved_knowledge_archived.json"
        promoted_file = self.storage_dir / "evolved_knowledge_promoted.json"

        if active_file.exists():
            try:
                with open(active_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        k = LearningKnowledge.from_dict(item)
                        self._active_knowledge[k.knowledge_id] = k
            except Exception as e:
                logger.warning("Could not load active evolved knowledge: %s", e)

        if archived_file.exists():
            try:
                with open(archived_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        k = LearningKnowledge.from_dict(item)
                        self._archived_knowledge[k.knowledge_id] = k
            except Exception as e:
                logger.warning("Could not load archived knowledge: %s", e)

        if promoted_file.exists():
            try:
                with open(promoted_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        k = LearningKnowledge.from_dict(item)
                        self._promoted_knowledge[k.knowledge_id] = k
            except Exception as e:
                logger.warning("Could not load promoted knowledge: %s", e)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active_items": len(self._active_knowledge),
                "archived_items": len(self._archived_knowledge),
                "promoted_items": len(self._promoted_knowledge),
                "total_merged": getattr(self, "_total_merged_count", 0),
                "total_archived": len(self._archived_knowledge),
                "total_promoted": len(self._promoted_knowledge),
            }
