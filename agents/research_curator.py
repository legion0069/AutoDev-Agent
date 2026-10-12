"""
agents/research_curator.py - Research Curator Agent (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.communication_bus import CommunicationBus
from core.research_lab import ResearchLab
from core.research_memory import FutureWorkItem, ResearchFailure, ResearchIdea, ResearchSuccess

logger = logging.getLogger("AutoDev.Research.ResearchCurator")


class ResearchCuratorAgent:
    """
    Research Curator Agent - Custodian of Institutional Memory & Scientific Lineage:
    - Catalogs ideas, breakthroughs, failures, and future directions in ResearchMemory
    - Traces technological lineage and builds Mermaid visualization graphs
    - Computes scholar bibliometrics (h-index, i10-index) and audits the SHA-256 scientific chain
    """

    def __init__(
        self,
        name: str = "ResearchCurator",
        lab: Optional[ResearchLab] = None,
        bus: Optional[CommunicationBus] = None,
    ) -> None:
        self.name = name
        self.lab = lab or ResearchLab()
        self.bus = bus
        self.authority_level = 3

        if self.bus:
            self.bus.register_entity(self.name)

    def record_idea(self, title: str, description: str, author: str = "Researcher") -> ResearchIdea:
        """Stores an ideation concept in the persistent memory bank."""
        return self.lab.research_memory.add_idea(title=title, description=description, author=author)

    def record_negative_result(
        self,
        experiment_id: str,
        description: str,
        root_cause: str,
        lessons_learned: str,
    ) -> ResearchFailure:
        """Preserves a negative experiment result to prevent redundant exploration."""
        return self.lab.research_memory.record_failure(
            experiment_id=experiment_id,
            description=description,
            root_cause=root_cause,
            lessons_learned=lessons_learned,
        )

    def trace_artifact_lineage(self, node_id: str) -> Dict[str, Any]:
        """Traces the complete ancestry and descendant impact of an artifact in the Innovation Graph."""
        return self.lab.innovation_graph.get_lineage(node_id=node_id)

    def generate_lineage_diagram(self, max_nodes: int = 40) -> str:
        """Generates a GitHub-flavored Mermaid graph visualizing research lineage."""
        return self.lab.innovation_graph.to_mermaid(max_nodes=max_nodes)

    def compute_author_h_index(self, author_name: str) -> int:
        """Calculates Hirsch h-index for an author across registered publications."""
        return self.lab.citation_manager.compute_h_index(author_name=author_name)

    def verify_scientific_audit_trail(self) -> Dict[str, Any]:
        """Verifies cryptographic SHA-256 chain integrity of the laboratory journal."""
        is_valid, error = self.lab.scientific_logger.verify_chain_integrity()
        return {
            "is_valid": is_valid,
            "total_records": self.lab.scientific_logger.total_records,
            "error": error,
            "verified_by": self.name,
        }
