"""
organization_graph.py - Corporate Organization Graph & Cross-Functional Routing for AutoDev (v3.0)

Models the corporate hierarchy, cross-departmental edges, reporting paths, approval workflows,
and span-of-control analytics using deterministic directed graph algorithms.
"""

from __future__ import annotations

import collections
import copy
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from core.enterprise.enterprise_models import (
    DepartmentType,
    EmployeeProfile,
    ExecutiveRole,
    TeamType,
)

logger = logging.getLogger("AutoDev.Enterprise.OrgGraph")


class EdgeRelation(str, Enum):
    REPORTS_TO = "REPORTS_TO"
    COLLABORATES_WITH = "COLLABORATES_WITH"
    APPROVES = "APPROVES"
    DEPENDS_ON = "DEPENDS_ON"


@dataclass
class OrgNode:
    node_id: str
    name: str
    title: str
    department: DepartmentType
    team: Optional[TeamType] = None
    role: Optional[ExecutiveRole] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "title": self.title,
            "department": self.department.value,
            "team": self.team.value if self.team else None,
            "role": self.role.value if self.role else None,
            "metadata": self.metadata,
        }


@dataclass
class OrgEdge:
    source_id: str
    target_id: str
    relation: EdgeRelation
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class OrganizationGraph:
    """
    Corporate Knowledge & Governance Organization Graph.
    Implements hierarchy traversal, escalation pathfinding, and approval routing.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._nodes: Dict[str, OrgNode] = {}
        self._adjacency: Dict[str, List[OrgEdge]] = collections.defaultdict(list)
        self._reverse_adjacency: Dict[str, List[OrgEdge]] = collections.defaultdict(list)

        self._bootstrap_enterprise_org()

    def _bootstrap_enterprise_org(self) -> None:
        """Constructs full enterprise hierarchy from Executive down to Engineering teams."""
        # Executives
        self.add_node(OrgNode("emp_ceo", "Elena Rostova", "CEO", DepartmentType.EXECUTIVE, role=ExecutiveRole.CEO))
        self.add_node(OrgNode("emp_cto", "Marcus Vance", "CTO", DepartmentType.ARCHITECTURE, role=ExecutiveRole.CTO))
        self.add_node(OrgNode("emp_vpprod", "Sarah Chen", "VP Product", DepartmentType.PRODUCT, role=ExecutiveRole.VP_PRODUCT))
        self.add_node(OrgNode("emp_vpeng", "David Kim", "VP Engineering", DepartmentType.ENGINEERING, role=ExecutiveRole.VP_ENGINEERING))
        self.add_node(OrgNode("emp_cfo", "Hannah Abbott", "Director Finance", DepartmentType.FINANCE, role=ExecutiveRole.DIRECTOR_FINANCE))
        self.add_node(OrgNode("emp_cso", "Viktor Stone", "Director Security", DepartmentType.SECURITY, role=ExecutiveRole.DIRECTOR_SECURITY))
        self.add_node(OrgNode("emp_dirqa", "Priya Sharma", "Director QA", DepartmentType.QA, role=ExecutiveRole.DIRECTOR_QA))
        self.add_node(OrgNode("emp_dirdevops", "Rachel Green", "Director DevOps", DepartmentType.DEVOPS, role=ExecutiveRole.DIRECTOR_DEVOPS))

        # Direct reports to CEO
        self.add_edge("emp_cto", "emp_ceo", EdgeRelation.REPORTS_TO)
        self.add_edge("emp_vpprod", "emp_ceo", EdgeRelation.REPORTS_TO)
        self.add_edge("emp_vpeng", "emp_ceo", EdgeRelation.REPORTS_TO)
        self.add_edge("emp_cfo", "emp_ceo", EdgeRelation.REPORTS_TO)

        # Reports to VP Engineering / CTO
        self.add_edge("emp_cso", "emp_cto", EdgeRelation.REPORTS_TO)
        self.add_edge("emp_dirqa", "emp_vpeng", EdgeRelation.REPORTS_TO)
        self.add_edge("emp_dirdevops", "emp_vpeng", EdgeRelation.REPORTS_TO)

        # Engineering Team Leads
        leads = [
            ("lead_backend", "Liam O'Connor", "Backend Lead", DepartmentType.ENGINEERING, TeamType.BACKEND),
            ("lead_frontend", "Aria Stark", "Frontend Lead", DepartmentType.ENGINEERING, TeamType.FRONTEND),
            ("lead_ai", "Dr. Alan Turing", "AI Lead", DepartmentType.ENGINEERING, TeamType.AI_ML),
            ("lead_sec", "Agent Smith", "Security Lead", DepartmentType.SECURITY, TeamType.SECURITY_OPS),
        ]

        for nid, name, title, dept, team in leads:
            self.add_node(OrgNode(nid, name, title, dept, team=team))
            self.add_edge(nid, "emp_vpeng", EdgeRelation.REPORTS_TO)

        # Cross-functional collaborations
        self.add_edge("emp_vpprod", "emp_vpeng", EdgeRelation.COLLABORATES_WITH)
        self.add_edge("lead_backend", "lead_frontend", EdgeRelation.COLLABORATES_WITH)
        self.add_edge("emp_cso", "lead_backend", EdgeRelation.APPROVES)

    def add_node(self, node: OrgNode) -> None:
        with self._lock:
            self._nodes[node.node_id] = copy.deepcopy(node)

    def add_edge(self, source_id: str, target_id: str, relation: EdgeRelation, weight: float = 1.0) -> None:
        with self._lock:
            edge = OrgEdge(source_id=source_id, target_id=target_id, relation=relation, weight=weight)
            self._adjacency[source_id].append(edge)
            self._reverse_adjacency[target_id].append(edge)

    def get_node(self, node_id: str) -> Optional[OrgNode]:
        with self._lock:
            return copy.deepcopy(self._nodes.get(node_id))

    def list_nodes(self, department: Optional[DepartmentType] = None) -> List[OrgNode]:
        """Lists registered organization nodes, optionally filtered by department."""
        with self._lock:
            if department is None:
                return [copy.deepcopy(n) for n in self._nodes.values()]
            return [copy.deepcopy(n) for n in self._nodes.values() if n.department == department]

    def get_direct_reports(self, manager_id: str) -> List[OrgNode]:
        """Returns all direct subordinate nodes for a manager."""
        with self._lock:
            direct_report_ids = [
                e.source_id for e in self._reverse_adjacency.get(manager_id, [])
                if e.relation == EdgeRelation.REPORTS_TO
            ]
            return [copy.deepcopy(self._nodes[nid]) for nid in direct_report_ids if nid in self._nodes]

    def get_reporting_chain(self, start_node_id: str) -> List[str]:
        """
        Traverses REPORTS_TO edges up to CEO.
        Returns ordered list of node IDs from subordinate to top executive.
        """
        with self._lock:
            chain: List[str] = [start_node_id]
            curr = start_node_id
            visited: Set[str] = {curr}

            while True:
                reports = [
                    e.target_id for e in self._adjacency.get(curr, [])
                    if e.relation == EdgeRelation.REPORTS_TO
                ]
                if not reports:
                    break
                nxt = reports[0]
                if nxt in visited:
                    break  # cycle protection
                visited.add(nxt)
                chain.append(nxt)
                curr = nxt

            return chain

    def find_escalation_path(self, from_node_id: str, target: Union[str, DepartmentType]) -> List[str]:
        """
        Finds shortest management path to target node ID or target department using BFS.
        """
        with self._lock:
            queue: collections.deque[List[str]] = collections.deque([[from_node_id]])
            visited: Set[str] = {from_node_id}

            while queue:
                path = queue.popleft()
                node_id = path[-1]
                node = self._nodes.get(node_id)

                if isinstance(target, str):
                    if node_id == target:
                        return path
                elif isinstance(target, DepartmentType):
                    if node and node.department == target and node_id != from_node_id:
                        return path

                # Traverse both outgoing and incoming edges
                neighbors = [e.target_id for e in self._adjacency.get(node_id, [])]
                neighbors += [e.source_id for e in self._reverse_adjacency.get(node_id, [])]

                for nxt in neighbors:
                    if nxt not in visited and nxt in self._nodes:
                        visited.add(nxt)
                        queue.append(path + [nxt])

            return [from_node_id]

    def calculate_span_of_control(self, manager_id: str) -> int:
        """Calculates direct reports count for a manager."""
        with self._lock:
            direct_reports = [
                e.source_id for e in self._reverse_adjacency.get(manager_id, [])
                if e.relation == EdgeRelation.REPORTS_TO
            ]
            return len(direct_reports)

    get_span_of_control = calculate_span_of_control

    def generate_mermaid_org_chart(self) -> str:
        """Generates deterministic Mermaid diagram of corporate reporting structure."""
        with self._lock:
            lines = [
                "```mermaid",
                "graph TD",
                "    subgraph Executive_Suite [Executive Leadership]",
            ]

            for nid, node in sorted(self._nodes.items()):
                if node.role:
                    lines.append(f"        {nid}[\"{node.title}<br/><b>{node.name}</b>\"]")

            lines.append("    end")
            lines.append("    subgraph Teams [Department Teams & Leads]")

            for nid, node in sorted(self._nodes.items()):
                if not node.role:
                    team_label = node.team.value if node.team else node.department.value
                    lines.append(f"        {nid}[\"{node.title}<br/>{node.name}<br/>({team_label})\"]")

            lines.append("    end")

            # Add reporting relations
            for src_id in sorted(self._adjacency.keys()):
                for e in self._adjacency[src_id]:
                    if e.relation == EdgeRelation.REPORTS_TO:
                        lines.append(f"    {src_id} -->|REPORTS_TO| {e.target_id}")

            lines.append("```")
            return "\n".join(lines)
