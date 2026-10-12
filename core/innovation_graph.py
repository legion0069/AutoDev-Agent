"""
core/innovation_graph.py - Directed Knowledge & Innovation Lineage Graph (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import collections
import enum
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class InnovationNodeType(str, enum.Enum):
    """Categorization of scientific and technological artifacts in the graph."""
    BASELINE = "BASELINE"
    ALGORITHM = "ALGORITHM"
    IDEA = "IDEA"
    HYPOTHESIS = "HYPOTHESIS"
    EXPERIMENT = "EXPERIMENT"
    BENCHMARK = "BENCHMARK"
    PUBLICATION = "PUBLICATION"
    PATENT = "PATENT"
    DISCOVERY = "DISCOVERY"


class InnovationRelationType(str, enum.Enum):
    """Semantic edges connecting research artifacts."""
    DERIVED_FROM = "DERIVED_FROM"
    OPTIMIZES = "OPTIMIZES"
    SUPERSEDES = "SUPERSEDES"
    INSPIRES = "INSPIRES"
    TESTS = "TESTS"
    IMPLEMENTS = "IMPLEMENTS"
    EVALUATES = "EVALUATES"
    DOCUMENTS = "DOCUMENTS"
    PROTECTS = "PROTECTS"
    DEPENDS_ON = "DEPENDS_ON"


# Alias for backwards compatibility with tests
InnovationEdgeType = InnovationRelationType


@dataclass
class InnovationNode:
    """A discrete node representing an idea, experiment, algorithm, or paper."""
    node_id: str
    name: str = ""
    node_type: InnovationNodeType = InnovationNodeType.ALGORITHM
    description: str = ""
    title: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.name and self.title:
            self.name = self.title
        if not self.title and self.name:
            self.title = self.name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "node_type": self.node_type.value,
            "title": self.title,
            "description": self.description,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class InnovationEdge:
    """A directed semantic relationship between two nodes."""
    source_id: str
    target_id: str
    relation: InnovationRelationType
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation.value,
            "weight": self.weight,
        }


class LineageList(list):
    """List of ancestor nodes that also supports dict access for summary reporting."""
    def __init__(self, items: List[InnovationNode], summary_dict: Optional[Dict[str, Any]] = None):
        super().__init__(items)
        self.summary_dict = summary_dict or {}

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, str):
            return self.summary_dict[item]
        return super().__getitem__(item)

    def get(self, key: str, default: Any = None) -> Any:
        return self.summary_dict.get(key, default)


class InnovationGraph:
    """
    Maintains a directed acyclic or cyclic graph of technological evolution.
    Supports lineage tracking, topological traversal, shortest path analysis, and Mermaid rendering.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._nodes: Dict[str, InnovationNode] = {}
        self._adj: Dict[str, List[InnovationEdge]] = {}       # source -> outgoing edges
        self._rev_adj: Dict[str, List[InnovationEdge]] = {}   # target -> incoming edges

    @property
    def total_nodes(self) -> int:
        with self._lock:
            return len(self._nodes)

    def add_node(
        self,
        name: Optional[str] = None,
        node_type: InnovationNodeType = InnovationNodeType.ALGORITHM,
        description: str = "",
        node_id: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> InnovationNode:
        """Registers a research node."""
        with self._lock:
            nid = node_id or f"NODE-{len(self._nodes) + 1}"
            node_name = name or title or nid
            node_title = title or node_name

            node = InnovationNode(
                node_id=nid,
                name=node_name,
                node_type=node_type,
                description=description,
                title=node_title,
                metadata=metadata or {},
            )
            self._nodes[nid] = node
            self._adj.setdefault(nid, [])
            self._rev_adj.setdefault(nid, [])
            return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: Union[InnovationRelationType, InnovationEdgeType] = InnovationRelationType.DERIVED_FROM,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InnovationEdge:
        """Adds a directed relationship between two existing nodes."""
        with self._lock:
            if source_id not in self._nodes or target_id not in self._nodes:
                raise ValueError(f"Both source '{source_id}' and target '{target_id}' must exist")

            edge = InnovationEdge(
                source_id=source_id,
                target_id=target_id,
                relation=relation,
                weight=weight,
                metadata=metadata or {},
            )
            self._adj[source_id].append(edge)
            self._rev_adj[target_id].append(edge)
            return edge

    def get_node(self, node_id: str) -> Optional[InnovationNode]:
        with self._lock:
            return self._nodes.get(node_id)

    def get_lineage(self, node_id: str) -> LineageList:
        """
        Traces complete ancestral lineage (incoming dependencies) leading up to `node_id`.
        Returns ordered list from earliest root ancestor down to `node_id`.
        """
        with self._lock:
            if node_id not in self._nodes:
                return LineageList([], {"error": f"Node '{node_id}' not found"})

            # Upstream ancestors (BFS on rev_adj)
            ancestor_ids = set()
            queue = collections.deque([node_id])
            while queue:
                curr = queue.popleft()
                for in_edge in self._rev_adj.get(curr, []):
                    if in_edge.source_id not in ancestor_ids:
                        ancestor_ids.add(in_edge.source_id)
                        queue.append(in_edge.source_id)

            subgraph_nodes = ancestor_ids | {node_id}

            # Topological sort of subgraph_nodes
            in_degree = {nid: 0 for nid in subgraph_nodes}
            for nid in subgraph_nodes:
                for edge in self._adj.get(nid, []):
                    if edge.target_id in in_degree:
                        in_degree[edge.target_id] += 1

            zero_deg = collections.deque([nid for nid, deg in in_degree.items() if deg == 0])
            ordered: List[str] = []
            while zero_deg:
                curr = zero_deg.popleft()
                ordered.append(curr)
                for edge in self._adj.get(curr, []):
                    if edge.target_id in in_degree:
                        in_degree[edge.target_id] -= 1
                        if in_degree[edge.target_id] == 0:
                            zero_deg.append(edge.target_id)

            # In case of cycles, add any remaining nodes
            for nid in subgraph_nodes:
                if nid not in ordered:
                    ordered.append(nid)

            node_objs = [self._nodes[nid] for nid in ordered if nid in self._nodes]

            summary = {
                "node_id": node_id,
                "node_title": self._nodes[node_id].title,
                "node_type": self._nodes[node_id].node_type.value,
                "ancestors_count": len(ancestor_ids),
                "ancestors": [self._nodes[a].to_dict() for a in ancestor_ids if a in self._nodes],
            }

            return LineageList(node_objs, summary)

    def has_cycles(self) -> bool:
        """Returns True if the directed graph contains any cycle."""
        with self._lock:
            # 0 = unvisited, 1 = visiting, 2 = visited
            visited = {nid: 0 for nid in self._nodes}

            def dfs(u: str) -> bool:
                visited[u] = 1
                for edge in self._adj.get(u, []):
                    v = edge.target_id
                    if visited.get(v, 0) == 1:
                        return True
                    if visited.get(v, 0) == 0:
                        if dfs(v):
                            return True
                visited[u] = 2
                return False

            for nid in self._nodes:
                if visited[nid] == 0:
                    if dfs(nid):
                        return True
            return False

    def shortest_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        """Finds shortest unweighted path using Breadth-First Search (BFS)."""
        with self._lock:
            if source_id not in self._nodes or target_id not in self._nodes:
                return None
            if source_id == target_id:
                return [source_id]

            queue = collections.deque([[source_id]])
            visited = {source_id}

            while queue:
                path = queue.popleft()
                curr = path[-1]

                for edge in self._adj.get(curr, []):
                    nxt = edge.target_id
                    if nxt == target_id:
                        return path + [nxt]
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(path + [nxt])

            return None

    def export_mermaid(self, max_nodes: int = 50) -> str:
        """Generates GitHub-compatible Mermaid graph visualization."""
        with self._lock:
            lines = ["graph TD"]
            displayed_nodes = list(self._nodes.keys())[:max_nodes]
            disp_set = set(displayed_nodes)

            for nid in displayed_nodes:
                node = self._nodes[nid]
                clean_name = (node.name or node.title or nid).replace('"', "'")
                lines.append(f'    {nid}["{clean_name}"]')

            for nid in displayed_nodes:
                for edge in self._adj.get(nid, []):
                    if edge.target_id in disp_set:
                        rel = edge.relation.value if hasattr(edge.relation, "value") else str(edge.relation)
                        lines.append(f"    {edge.source_id} -->|{rel}| {edge.target_id}")

            return "\n".join(lines)

    def to_mermaid(self, max_nodes: int = 50) -> str:
        return self.export_mermaid(max_nodes=max_nodes)

    def get_stats(self) -> Dict[str, Any]:
        """Provides structural graph metrics."""
        with self._lock:
            type_counts = collections.defaultdict(int)
            for n in self._nodes.values():
                type_counts[n.node_type.value] += 1

            total_edges = sum(len(edges) for edges in self._adj.values())
            return {
                "total_nodes": len(self._nodes),
                "total_edges": total_edges,
                "type_breakdown": dict(type_counts),
            }
