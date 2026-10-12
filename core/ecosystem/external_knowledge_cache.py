"""
external_knowledge_cache.py - Searchable, Versioned External Knowledge Cache (v3.2)

Persists and indexes structured external ecosystem intelligence:
- Framework metadata
- Package metadata
- Migration guides
- Release notes
- Security advisories
- Technology radar snapshots

Everything searchable with full-text keyword indexing, versioned, and persisted to JSON.
"""

from __future__ import annotations

import copy
import json
import logging
import re
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("AutoDev.ExternalKnowledgeCache")


class ExternalKnowledgeCache:
    """
    Searchable, versioned local cache for external engineering ecosystem knowledge.
    Uses pure Python Standard Library with inverted text indexing.
    """

    def __init__(self, cache_dir: Optional[str] = None, auto_persist: bool = True) -> None:
        self._lock = threading.RLock()
        self.cache_dir = Path(cache_dir) if cache_dir else Path("memory/ecosystem_cache")
        self.auto_persist = auto_persist

        # Cache stores
        self._entries: Dict[str, Dict[str, Any]] = {}
        # Inverted index: word -> set of entry_ids
        self._index: Dict[str, Set[str]] = defaultdict(set)
        # Category index: category -> set of entry_ids
        self._category_index: Dict[str, Set[str]] = defaultdict(set)

        if self.auto_persist:
            self._ensure_storage()
            self._load_cache()

    def _ensure_storage(self) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Could not create ecosystem cache directory: %s", e)

    def put(
        self,
        key: str,
        category: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        version: str = "1.0",
    ) -> Dict[str, Any]:
        """Stores or updates an indexed cache entry."""
        with self._lock:
            now = time.time()
            entry_id = f"EXT-{category.upper()}-{key.lower()}"
            entry = {
                "entry_id": entry_id,
                "key": key,
                "category": category.upper(),
                "title": title,
                "content": content,
                "version": version,
                "metadata": metadata or {},
                "created_at": self._entries.get(entry_id, {}).get("created_at", now),
                "updated_at": now,
            }

            self._entries[entry_id] = entry
            self._category_index[category.upper()].add(entry_id)

            # Index keywords
            tokens = set(re.findall(r"\w+", f"{key} {title} {content}".lower()))
            for token in tokens:
                if len(token) > 2:
                    self._index[token].add(entry_id)

            if self.auto_persist:
                self._persist_cache()

            return copy.deepcopy(entry)

    def get(self, key_or_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a cache entry by exact key or ID."""
        with self._lock:
            # Check by exact entry_id
            if key_or_id in self._entries:
                return copy.deepcopy(self._entries[key_or_id])
            # Check by key match
            for entry in self._entries.values():
                if entry["key"].lower() == key_or_id.lower():
                    return copy.deepcopy(entry)
            return None

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Executes full-text keyword search across cached knowledge."""
        with self._lock:
            query_tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
            if not query_tokens:
                # Fallback to returning entries by category if query is empty
                if category:
                    ids = self._category_index.get(category.upper(), set())
                    return [copy.deepcopy(self._entries[eid]) for eid in list(ids)[:limit]]
                return [copy.deepcopy(e) for e in list(self._entries.values())[:limit]]

            # Score entries by token intersection and frequency (TF ranking)
            scored: Dict[str, int] = defaultdict(int)
            for token in query_tokens:
                matching_ids = self._index.get(token, set())
                for eid in matching_ids:
                    if category is None or self._entries[eid]["category"] == category.upper():
                        text = f"{self._entries[eid]['key']} {self._entries[eid]['title']} {self._entries[eid]['content']}".lower()
                        scored[eid] += max(1, text.count(token))

            sorted_entries = sorted(scored.items(), key=lambda x: x[1], reverse=True)
            results = []
            for eid, score in sorted_entries[:limit]:
                res = copy.deepcopy(self._entries[eid])
                res["search_relevance_score"] = score
                results.append(res)
            return results

    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Returns all entries for a specific category."""
        with self._lock:
            ids = self._category_index.get(category.upper(), set())
            return [copy.deepcopy(self._entries[eid]) for eid in ids]

    def list_all(self) -> List[Dict[str, Any]]:
        """Returns all cached entries."""
        with self._lock:
            return [copy.deepcopy(e) for e in self._entries.values()]

    def count(self) -> int:
        """Returns total entries count."""
        with self._lock:
            return len(self._entries)

    def clear(self) -> None:
        """Clears all cached items and indices."""
        with self._lock:
            self._entries.clear()
            self._index.clear()
            self._category_index.clear()
            if self.auto_persist:
                self._persist_cache()

    def _persist_cache(self) -> None:
        """Saves cache to disk."""
        try:
            cache_file = self.cache_dir / "external_knowledge_cache.json"
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(list(self._entries.values()), f, indent=2)
        except Exception as e:
            logger.warning("Failed to persist external knowledge cache: %s", e)

    def _load_cache(self) -> None:
        """Loads cache from disk."""
        cache_file = self.cache_dir / "external_knowledge_cache.json"
        if not cache_file.exists():
            return
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    eid = item["entry_id"]
                    self._entries[eid] = item
                    self._category_index[item["category"]].add(eid)
                    tokens = set(re.findall(r"\w+", f"{item['key']} {item['title']} {item['content']}".lower()))
                    for token in tokens:
                        if len(token) > 2:
                            self._index[token].add(eid)
        except Exception as e:
            logger.warning("Failed to load external knowledge cache: %s", e)
