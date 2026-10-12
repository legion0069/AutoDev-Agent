"""
enterprise_knowledge.py - Global Enterprise Knowledge Graph (AutoDev Version 3.5)

Implements a unified, cross-company enterprise knowledge graph:
- Stores ADRs, APIs, Libraries, Patterns, Reusable Modules, Incidents,
  Lessons Learned, Research Discoveries, and Best Practices.
- Directed knowledge relationships (DEPENDS_ON, IMPLEMENTS, EXTENDS, SUPERSEDES, RELATES_TO).
- Fast token-based full-text indexing, graph neighborhood traversal, and cross-company reuse analytics.
- 100% Python Standard Library.
"""

from __future__ import annotations

import collections
import enum
import logging
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("AutoDev.Federation.Knowledge")


class KnowledgeCategory(str, enum.Enum):
    """Categorization of institutional knowledge artifacts."""
    ADR = "ADR"
    API = "API"
    LIBRARY = "LIBRARY"
    PATTERN = "PATTERN"
    REUSABLE_MODULE = "REUSABLE_MODULE"
    INCIDENT = "INCIDENT"
    LESSON_LEARNED = "LESSON_LEARNED"
    RESEARCH = "RESEARCH"
    BEST_PRACTICE = "BEST_PRACTICE"


class RelationshipType(str, enum.Enum):
    """Semantic relationship types between knowledge nodes."""
    DEPENDS_ON = "DEPENDS_ON"
    IMPLEMENTS = "IMPLEMENTS"
    EXTENDS = "EXTENDS"
    SUPERSEDES = "SUPERSEDES"
    RELATES_TO = "RELATES_TO"
    MIGRATED_FROM = "MIGRATED_FROM"
    DERIVED_FROM = "DERIVED_FROM"


@dataclass
class KnowledgeNode:
    """A node in the enterprise knowledge graph."""
    node_id: str
    category: KnowledgeCategory
    title: str
    content: str
    company_id: str
    author: str
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    reuse_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value if hasattr(self.category, "value") else self.category
        return d


@dataclass
class KnowledgeEdge:
    """A directed edge linking two knowledge nodes."""
    edge_id: str
    source_id: str
    target_id: str
    relationship: RelationshipType
    description: str = ""
    weight: float = 1.0


class EnterpriseKnowledgeGraph:
    """
    Unified knowledge repository with semantic graph linking and full-text discovery.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._nodes: Dict[str, KnowledgeNode] = {}
        self._edges: Dict[str, KnowledgeEdge] = {}
        # Adjacency lists
        self._outgoing: Dict[str, List[str]] = collections.defaultdict(list)  # source_id -> [edge_id]
        self._incoming: Dict[str, List[str]] = collections.defaultdict(list)  # target_id -> [edge_id]
        # Inverted index: token -> set of node_ids
        self._inverted_index: Dict[str, Set[str]] = collections.defaultdict(set)
        # Contributions per company
        self._company_contributions: Dict[str, int] = collections.defaultdict(int)

    def add_knowledge_node(
        self,
        category: KnowledgeCategory | str,
        title: str,
        content: str,
        company_id: str,
        author: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeNode:
        """Publishes a new knowledge item into the enterprise graph."""
        with self._lock:
            nid = f"KNOW-{uuid.uuid4().hex[:8].upper()}"
            cat = KnowledgeCategory(category) if isinstance(category, str) else category
            node = KnowledgeNode(
                node_id=nid,
                category=cat,
                title=title,
                content=content,
                company_id=company_id,
                author=author,
                tags=tags or [],
                metadata=metadata or {},
            )
            self._nodes[nid] = node
            self._company_contributions[company_id] += 1

            # Tokenize & index
            self._index_node(node)
            logger.info("Published knowledge node '%s': %s (Company: %s)", nid, title, company_id)
            return node

    def link_nodes(
        self,
        source_id: str,
        target_id: str,
        relationship: RelationshipType | str,
        description: str = "",
        weight: float = 1.0,
    ) -> Optional[KnowledgeEdge]:
        """Creates a semantic relationship between two knowledge nodes."""
        with self._lock:
            if source_id not in self._nodes or target_id not in self._nodes:
                logger.warning("Cannot link non-existent nodes: %s -> %s", source_id, target_id)
                return None

            rel = RelationshipType(relationship) if isinstance(relationship, str) else relationship
            eid = f"EDGE-{uuid.uuid4().hex[:8].upper()}"
            edge = KnowledgeEdge(
                edge_id=eid,
                source_id=source_id,
                target_id=target_id,
                relationship=rel,
                description=description,
                weight=weight,
            )
            self._edges[eid] = edge
            self._outgoing[source_id].append(eid)
            self._incoming[target_id].append(eid)
            return edge

    def record_reuse(self, node_id: str) -> None:
        """Increments reuse counter when another company adopts this knowledge."""
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].reuse_count += 1

    def search(
        self,
        query: str,
        category: Optional[KnowledgeCategory | str] = None,
        company_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Tuple[KnowledgeNode, float]]:
        """
        Full-text token matching with relevance scoring and category filtering.
        Returns ranked list of (KnowledgeNode, score) tuples.
        """
        with self._lock:
            tokens = self._tokenize(query)
            if not tokens:
                matched_nodes = list(self._nodes.values())
                if category:
                    cat_val = category.value if hasattr(category, "value") else str(category)
                    matched_nodes = [n for n in matched_nodes if (n.category.value if hasattr(n.category, "value") else n.category) == cat_val]
                if company_id:
                    matched_nodes = [n for n in matched_nodes if n.company_id == company_id]
                return [(n, 1.0) for n in matched_nodes[:limit]]

            node_scores: Dict[str, float] = collections.defaultdict(float)
            cat_val = (category.value if hasattr(category, "value") else str(category)) if category else None

            for tok in tokens:
                matching_nids = self._inverted_index.get(tok, set())
                for nid in matching_nids:
                    node = self._nodes[nid]
                    if cat_val and (node.category.value if hasattr(node.category, "value") else node.category) != cat_val:
                        continue
                    if company_id and node.company_id != company_id:
                        continue

                    # Weight title match higher than body
                    score = 2.0 if tok in node.title.lower() else 1.0
                    # Weight tag matches
                    if any(tok in t.lower() for t in node.tags):
                        score += 3.0
                    node_scores[nid] += score

            # Sort by score descending
            ranked = sorted(node_scores.items(), key=lambda x: -x[1])
            results = [(self._nodes[nid], score) for nid, score in ranked[:limit]]
            return results

    def get_related_nodes(
        self,
        node_id: str,
        relationship: Optional[RelationshipType | str] = None,
    ) -> List[Tuple[KnowledgeNode, RelationshipType]]:
        """Retrieves nodes directly connected to this node."""
        with self._lock:
            if node_id not in self._nodes:
                return []

            rel_val = (relationship.value if hasattr(relationship, "value") else str(relationship)) if relationship else None
            results = []

            for eid in self._outgoing.get(node_id, []):
                edge = self._edges[eid]
                if rel_val is None or (edge.relationship.value if hasattr(edge.relationship, "value") else edge.relationship) == rel_val:
                    if edge.target_id in self._nodes:
                        results.append((self._nodes[edge.target_id], edge.relationship))

            return results

    def find_path(self, start_node_id: str, end_node_id: str) -> Optional[List[str]]:
        """BFS shortest path discovery between two knowledge nodes."""
        with self._lock:
            if start_node_id not in self._nodes or end_node_id not in self._nodes:
                return None
            if start_node_id == end_node_id:
                return [start_node_id]

            queue = collections.deque([[start_node_id]])
            visited = {start_node_id}

            while queue:
                path = queue.popleft()
                curr = path[-1]

                for eid in self._outgoing.get(curr, []):
                    edge = self._edges[eid]
                    nxt = edge.target_id
                    if nxt == end_node_id:
                        return path + [nxt]
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(path + [nxt])

            return None

    def _index_node(self, node: KnowledgeNode) -> None:
        """Tokenizes title, content, and tags into inverted index."""
        text = f"{node.title} {node.content} {' '.join(node.tags)}"
        tokens = self._tokenize(text)
        for tok in tokens:
            self._inverted_index[tok].add(node.node_id)

    def _tokenize(self, text: str) -> List[str]:
        """Simple deterministic tokenizer."""
        clean = re.sub(r"[^\w\s-]", " ", text.lower())
        return [w for w in clean.split() if len(w) > 2]

    def get_knowledge_analytics(self) -> Dict[str, Any]:
        """Returns knowledge reuse, contribution, and volume metrics."""
        with self._lock:
            total_nodes = len(self._nodes)
            total_edges = len(self._edges)
            total_reuses = sum(n.reuse_count for n in self._nodes.values())
            category_counts = collections.Counter(
                (n.category.value if hasattr(n.category, "value") else n.category) for n in self._nodes.values()
            )

            return {
                "total_nodes": total_nodes,
                "total_edges": total_edges,
                "total_reuses": total_reuses,
                "nodes_by_category": dict(category_counts),
                "contributions_by_company": dict(self._company_contributions),
                "top_reused_nodes": [
                    {"node_id": n.node_id, "title": n.title, "reuses": n.reuse_count}
                    for n in sorted(self._nodes.values(), key=lambda x: -x.reuse_count)[:5]
                ],
            }
