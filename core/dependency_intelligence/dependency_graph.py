"""
dependency_graph.py - Project Dependency Graph & Topological Resolution (v3.2)

Builds directed acyclic dependency graphs, detects version conflicts, circular transitive chains,
calculates depth, and analyzes multi-manifest dependencies.
"""

from __future__ import annotations

import copy
import logging
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple

from core.ecosystem.ecosystem_models import (
    DependencyEcosystem,
    DependencyNode,
    PackageVersion,
)

logger = logging.getLogger("AutoDev.DependencyIntelligence.Graph")


class DependencyGraph:
    """
    Directed Graph representation of project direct and transitive dependencies.
    Provides cycle detection, conflict analysis, and topological ordering.
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, DependencyNode] = {}
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_adjacency: Dict[str, Set[str]] = defaultdict(set)

    def add_dependency(self, node: DependencyNode) -> None:
        """Adds a dependency node to the graph."""
        self._nodes[node.name] = copy.deepcopy(node)
        for dep in node.transitive_dependencies:
            self._adjacency[node.name].add(dep)
            self._reverse_adjacency[dep].add(node.name)

    def add_node(self, node: Any, version: Optional[str] = None) -> None:
        """Adds a dependency node or package name to the graph."""
        if isinstance(node, str):
            node_obj = DependencyNode(name=node, current_version=version or "1.0.0")
        else:
            node_obj = node
        self.add_dependency(node_obj)

    @property
    def nodes(self) -> Dict[str, DependencyNode]:
        """Provides access to graph nodes dictionary."""
        return self._nodes

    @property
    def edges(self) -> Dict[str, List[str]]:
        """Provides access to graph edges as lists."""
        return {k: sorted(list(v)) for k, v in self._adjacency.items()}

    def get_dependencies(self, name: str) -> List[str]:
        """Returns direct dependency names for a package."""
        return sorted(list(self._adjacency.get(name, set())))

    def get_dependents(self, name: str) -> List[str]:
        """Returns packages that directly depend on the given package."""
        return sorted(list(self._reverse_adjacency.get(name, set())))

    def add_edge(self, parent_name: str, child_name: str) -> None:
        """Explicitly connects parent dependency to child transitive dependency."""
        if parent_name not in self._nodes:
            self.add_node(parent_name)
        if child_name not in self._nodes:
            self.add_node(child_name)
        self._adjacency[parent_name].add(child_name)
        self._reverse_adjacency[child_name].add(parent_name)
        if parent_name in self._nodes:
            if child_name not in self._nodes[parent_name].transitive_dependencies:
                self._nodes[parent_name].transitive_dependencies.append(child_name)

    def get_node(self, name: str) -> Optional[DependencyNode]:
        """Retrieves a dependency node by name."""
        return copy.deepcopy(self._nodes.get(name))

    def get_all_nodes(self) -> List[DependencyNode]:
        """Returns all dependency nodes."""
        return [copy.deepcopy(n) for n in self._nodes.values()]

    def get_direct_dependencies(self) -> List[DependencyNode]:
        """Returns direct dependencies."""
        return [copy.deepcopy(n) for n in self._nodes.values() if n.is_direct]

    def get_transitive_dependencies(self, name: Optional[str] = None) -> Any:
        """Returns transitive dependencies (all nodes if name is None, or transitive chain if name given)."""
        if name is not None:
            return self.get_transitive_chain(name)
        return [copy.deepcopy(n) for n in self._nodes.values() if not n.is_direct]

    def has_cycle(self) -> bool:
        """Returns True if the graph contains any circular dependency cycles."""
        return len(self.detect_cycles()) > 0

    def has_cycles(self) -> bool:
        """Alias for has_cycle."""
        return self.has_cycle()

    def find_cycle(self) -> List[str]:
        """Returns the first detected cycle, or empty list if acyclic."""
        cycles = self.detect_cycles()
        return cycles[0] if cycles else []

    def find_cycles(self) -> List[List[str]]:
        """Alias for detect_cycles."""
        return self.detect_cycles()

    def get_all_transitive_dependencies(self, root_package: str) -> List[str]:
        """Alias for get_transitive_chain."""
        return self.get_transitive_chain(root_package)

    def topological_sort(self) -> List[str]:
        """
        Calculates topological ordering of nodes.
        Dependencies appear before dependents.
        """
        in_degree: Dict[str, int] = {node: 0 for node in self._nodes}
        for parent, children in self._adjacency.items():
            for child in children:
                if child in in_degree:
                    in_degree[child] += 1

        queue = deque([node for node, deg in in_degree.items() if deg == 0])
        ordered: List[str] = []

        while queue:
            curr = queue.popleft()
            ordered.append(curr)
            for neighbor in self._adjacency.get(curr, []):
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        # Fallback if remaining nodes (e.g. cycle)
        for node in self._nodes:
            if node not in ordered:
                ordered.append(node)

        # Dependencies first: reverse if needed
        return list(reversed(ordered))

    def max_depth(self) -> int:
        """Computes maximum dependency depth in the graph."""
        if not self._nodes:
            return 0
        depths: Dict[str, int] = {}

        def get_d(node: str, visited: Set[str]) -> int:
            if node in depths:
                return depths[node]
            if node in visited:
                return 0
            visited.add(node)
            children = self._adjacency.get(node, set())
            if not children:
                d = 0
            else:
                d = 1 + max(get_d(c, set(visited)) for c in children)
            visited.remove(node)
            depths[node] = d
            return d

        return max(get_d(n, set()) for n in self._nodes)

    def detect_cycles(self) -> List[List[str]]:
        """Detects circular dependency loops using Depth-First Search."""
        visited: Dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=visited
        cycles: List[List[str]] = []
        path: List[str] = []

        def dfs(node: str) -> None:
            visited[node] = 1
            path.append(node)

            for neighbor in self._adjacency.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    cycle_start = path.index(neighbor)
                    cycles.append(list(path[cycle_start:] + [neighbor]))
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor)

            path.pop()
            visited[node] = 2

        for node in self._nodes:
            if visited.get(node, 0) == 0:
                dfs(node)

        return cycles

    def get_transitive_chain(self, root_package: str) -> List[str]:
        """Computes complete downstream transitive chain from a package."""
        visited: Set[str] = set()
        queue = deque([root_package])
        chain: List[str] = []

        while queue:
            curr = queue.popleft()
            for child in sorted(self._adjacency.get(curr, [])):
                if child not in visited:
                    visited.add(child)
                    chain.append(child)
                    queue.append(child)

        return chain

    def to_dict(self) -> Dict[str, Any]:
        """Serializes graph structure."""
        return {
            "total_packages": len(self._nodes),
            "direct_count": len([n for n in self._nodes.values() if n.is_direct]),
            "transitive_count": len([n for n in self._nodes.values() if not n.is_direct]),
            "nodes": {name: node.to_dict() for name, node in self._nodes.items()},
            "edges": {parent: sorted(list(children)) for parent, children in self._adjacency.items()},
        }
