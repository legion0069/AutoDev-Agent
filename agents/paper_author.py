"""
agents/paper_author.py - Paper Author Agent (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.citation_manager import CitationRecord
from core.communication_bus import CommunicationBus
from core.paper_generator import EngineeringPaper
from core.research_lab import ResearchLab

logger = logging.getLogger("AutoDev.Research.PaperAuthor")


class PaperAuthorAgent:
    """
    Paper Author Agent - Voice of Scientific Dissemination & Scholarship:
    - Composes structured academic publications in GitHub-flavored Markdown
    - Formulates abstracts, theoretical backgrounds, methodology, and empirical evaluations
    - Formats bibliographies and manages external academic citations
    """

    def __init__(
        self,
        name: str = "PaperAuthor",
        lab: Optional[ResearchLab] = None,
        bus: Optional[CommunicationBus] = None,
    ) -> None:
        self.name = name
        self.lab = lab or ResearchLab()
        self.bus = bus
        self.authority_level = 3

        if self.bus:
            self.bus.register_entity(self.name)

    def write_manuscript(
        self,
        title: str,
        authors: List[str],
        abstract: str,
        introduction: str,
        background: str,
        methodology: str,
        experimental_setup: str,
        results: str,
        discussion: str,
        threats_to_validity: str,
        future_work: str,
        references: Optional[List[str]] = None,
    ) -> EngineeringPaper:
        """Composes a complete scholarly engineering publication."""
        paper = self.lab.paper_generator.compose_paper(
            title=title,
            authors=authors,
            abstract=abstract,
            introduction=introduction,
            background=background,
            methodology=methodology,
            experimental_setup=experimental_setup,
            results=results,
            discussion=discussion,
            threats_to_validity=threats_to_validity,
            future_work=future_work,
            references=references or [],
        )
        self.lab.research_memory.store_paper(paper.paper_id, {"title": paper.title, "markdown": paper.to_markdown()})
        return paper

    def add_reference(
        self,
        title: str,
        authors: List[str],
        year: int,
        venue: str,
        doi_or_url: str = "",
    ) -> CitationRecord:
        """Registers a bibliographic reference in the laboratory citation database."""
        return self.lab.citation_manager.register_citation(
            title=title,
            authors=authors,
            year=year,
            venue=venue,
            doi_or_url=doi_or_url,
        )
