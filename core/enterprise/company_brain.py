"""
company_brain.py - Central Enterprise Knowledge Brain & Institutional Memory for AutoDev (v3.0)

Provides a centralized, searchable corporate institutional memory covering 10 distinct
knowledge categories: Business Vision, Architecture ADRs, Customer Insights, Product Roadmaps,
Engineering Standards, Financial Metrics, Legal & Compliance, Support KB, Meeting Notes, and Postmortems.
"""

from __future__ import annotations

import collections
import copy
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from core.enterprise.enterprise_models import (
    DepartmentType,
    KnowledgeCategory,
    KnowledgeItem,
)

logger = logging.getLogger("AutoDev.Enterprise.CompanyBrain")


class CompanyBrain:
    """
    Autonomous Enterprise Knowledge & Institutional Memory Engine.
    Stores, indexes, versions, and retrieves cross-departmental documentation, ADRs, and postmortems.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: Dict[str, KnowledgeItem] = {}  # knowledge_id -> KnowledgeItem
        self._tag_index: Dict[str, Set[str]] = collections.defaultdict(set)
        self._category_index: Dict[KnowledgeCategory, Set[str]] = collections.defaultdict(set)
        self._links: Dict[str, Set[str]] = collections.defaultdict(set)  # source_id -> set of target_ids

        self._seed_default_knowledge()

    def _seed_default_knowledge(self) -> None:
        """Seeds foundational corporate documentation."""
        seeds = [
            (
                "KB-CORP-01",
                "AutoDev 3.0 Corporate Vision & Operating Principles",
                KnowledgeCategory.BUSINESS_VISION,
                "AutoDev is an autonomous AI software company delivering world-class engineering through deterministic AI agents.",
                ["vision", "principles", "c-suite"],
                "Elena Rostova (CEO)",
                DepartmentType.EXECUTIVE,
            ),
            (
                "KB-ARCH-01",
                "ADR-001: Pure Native Python Standard Library Architecture",
                KnowledgeCategory.ARCHITECTURE_ADR,
                "Strict architectural prohibition on heavy external orchestrators (LangGraph, Ray, Celery). Pure standard library ensures zero bloat.",
                ["architecture", "adr", "python", "standard-library"],
                "Marcus Vance (CTO)",
                DepartmentType.ARCHITECTURE,
            ),
            (
                "KB-ENG-01",
                "Enterprise Engineering Code Quality and TDD Guidelines",
                KnowledgeCategory.ENGINEERING_STANDARDS,
                "All code changes must have 100% backward compatibility, comprehensive pytest suites, strict type annotations, and thread safety.",
                ["engineering", "standards", "tdd", "testing"],
                "David Kim (VP Engineering)",
                DepartmentType.ENGINEERING,
            ),
        ]

        for kid, title, cat, content, tags, author, dept in seeds:
            item = KnowledgeItem(
                knowledge_id=kid,
                title=title,
                category=cat,
                content=content,
                tags=tags,
                author=author,
                source_department=dept,
                version=1,
                created_at=time.time(),
                updated_at=time.time(),
            )
            self._items[kid] = item
            self._category_index[cat].add(kid)
            for t in tags:
                self._tag_index[t.lower()].add(kid)

    def store_knowledge(
        self,
        title: str,
        category: KnowledgeCategory,
        content: str,
        tags: List[str],
        author: str,
        department: DepartmentType,
        knowledge_id: Optional[str] = None,
    ) -> KnowledgeItem:
        """
        Stores or updates a knowledge document with automatic indexing and versioning.
        """
        with self._lock:
            now = time.time()
            if knowledge_id and knowledge_id in self._items:
                existing = self._items[knowledge_id]
                existing.title = title
                existing.category = category
                existing.content = content
                existing.tags = list(tags)
                existing.author = author
                existing.source_department = department
                existing.version += 1
                existing.updated_at = now
                item = existing
            else:
                kid = knowledge_id or f"KB-{category.value[:4]}-{int(now * 1000)}-{len(self._items) + 1:04d}"
                item = KnowledgeItem(
                    knowledge_id=kid,
                    title=title,
                    category=category,
                    content=content,
                    tags=list(tags),
                    author=author,
                    source_department=department,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                self._items[kid] = item

            # Update indices
            self._category_index[category].add(item.knowledge_id)
            for t in tags:
                self._tag_index[t.lower()].add(item.knowledge_id)

            logger.info(f"Stored knowledge item [{item.knowledge_id}] v{item.version} under {category.value}")
            return copy.deepcopy(item)

    def link_knowledge(self, source_id: str, target_id: str) -> None:
        """Creates a bidirectional conceptual link between two knowledge entities."""
        with self._lock:
            if source_id in self._items and target_id in self._items:
                self._links[source_id].add(target_id)
                self._links[target_id].add(source_id)

    def search_knowledge(
        self,
        query: str = "",
        category: Optional[KnowledgeCategory] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[KnowledgeItem]:
        """
        Performs full-text keyword, tag, and category search across company institutional knowledge.
        """
        with self._lock:
            candidates: Set[str] = set(self._items.keys())

            if category:
                candidates &= self._category_index.get(category, set())

            if tags:
                for t in tags:
                    tag_matches = self._tag_index.get(t.lower(), set())
                    candidates &= tag_matches

            results: List[KnowledgeItem] = []
            q_lower = query.lower().strip()

            for kid in candidates:
                item = self._items[kid]
                if not q_lower or (
                    q_lower in item.title.lower()
                    or q_lower in item.content.lower()
                    or any(q_lower in t.lower() for t in item.tags)
                ):
                    results.append(item)

            results.sort(key=lambda x: x.updated_at, reverse=True)
            return [copy.deepcopy(x) for x in results[:limit]]

    def get_knowledge(self, knowledge_id: str) -> Optional[KnowledgeItem]:
        """Retrieves a single knowledge item by ID."""
        with self._lock:
            return copy.deepcopy(self._items.get(knowledge_id))

    def get_related_knowledge(self, knowledge_id: str) -> List[KnowledgeItem]:
        """Returns all knowledge items linked to a given entity."""
        with self._lock:
            linked_ids = self._links.get(knowledge_id, set())
            return [copy.deepcopy(self._items[kid]) for kid in linked_ids if kid in self._items]

    def to_dict(self) -> Dict[str, Any]:
        """Serializes knowledge repository overview."""
        with self._lock:
            return {
                "total_items": len(self._items),
                "categories": {cat.value: len(ids) for cat, ids in self._category_index.items()},
                "tags_count": len(self._tag_index),
                "items": [item.to_dict() for item in self._items.values()],
            }
