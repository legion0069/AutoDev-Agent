"""
core/citation_manager.py - Scientific Citation Graph, BibTeX Engine & Bibliometrics (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import collections
import enum
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set


class CitationFormat(str, enum.Enum):
    """Citation formatting standards."""
    APA = "APA"
    BIBTEX = "BIBTEX"
    IEEE = "IEEE"
    MLA = "MLA"
    CHICAGO = "CHICAGO"


@dataclass
class CitationEntry:
    """Bibliographic entry for an academic or internal scientific publication."""
    citation_id: str
    key: str
    title: str
    authors: List[str]
    year: int
    venue: str = ""
    volume: str = ""
    pages: str = ""
    doi_or_url: str = ""
    bibtex: str = ""
    citation_count: int = 0
    citing_paper_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "key": self.key,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "venue": self.venue,
            "volume": self.volume,
            "pages": self.pages,
            "citation_count": self.citation_count,
            "doi_or_url": self.doi_or_url,
            "bibtex": self.bibtex,
        }


# Backwards compatibility alias
CitationRecord = CitationEntry


class CitationManager:
    """
    Manages bibliographic reference collections, BibTeX generation, citation tracking,
    and bibliometric impact indicators (h-index, i10-index).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._citations: Dict[str, CitationEntry] = {}
        self._key_index: Dict[str, str] = {}
        self._author_index: Dict[str, Set[str]] = collections.defaultdict(set)

    @property
    def total_citations(self) -> int:
        with self._lock:
            return len(self._citations)

    def register(
        self,
        key: str,
        title: str,
        authors: List[str],
        year: int,
        venue: str = "",
        volume: str = "",
        pages: str = "",
        doi_or_url: str = "",
        bibtex: str = "",
    ) -> CitationEntry:
        """Registers a bibliographic entry."""
        with self._lock:
            cid = f"CITE-{uuid.uuid4().hex[:8].upper()}"

            if not bibtex:
                authors_str = " and ".join(authors)
                bibtex = (
                    f"@article{{{key},\n"
                    f"  title={{{title}}},\n"
                    f"  author={{{authors_str}}},\n"
                    f"  journal={{{venue}}},\n"
                    f"  year={{{year}}}\n"
                    f"}}"
                )

            entry = CitationEntry(
                citation_id=cid,
                key=key,
                title=title,
                authors=authors,
                year=year,
                venue=venue,
                volume=volume,
                pages=pages,
                doi_or_url=doi_or_url,
                bibtex=bibtex,
            )

            self._citations[cid] = entry
            self._key_index[key] = cid

            for author in authors:
                self._author_index[author.strip().lower()].add(cid)

            return entry

    def register_citation(
        self,
        title: str,
        authors: List[str],
        year: int,
        venue: str,
        doi_or_url: str = "",
        custom_bibtex: Optional[str] = None,
    ) -> CitationEntry:
        """Backwards compatibility for registering citations."""
        first_author = authors[0].split()[-1].lower() if authors else "autodev"
        key = f"{first_author}{year}{title.split()[0].lower()}"
        return self.register(
            key=key,
            title=title,
            authors=authors,
            year=year,
            venue=venue,
            doi_or_url=doi_or_url,
            bibtex=custom_bibtex or "",
        )

    def format_citation(self, citation_id: str, fmt: CitationFormat = CitationFormat.APA) -> str:
        """Formats citation entry according to academic formatting styles."""
        with self._lock:
            entry = self._citations.get(citation_id)
            if not entry:
                # Try finding by key
                cid = self._key_index.get(citation_id)
                entry = self._citations.get(cid) if cid else None

            if not entry:
                return ""

            if fmt == CitationFormat.BIBTEX:
                return entry.bibtex

            if fmt == CitationFormat.APA:
                # Authors: Turing, A. M.
                auth_str = ", ".join(entry.authors)
                venue_str = f" {entry.venue}." if entry.venue else ""
                vol_str = f" {entry.volume}" if entry.volume else ""
                pages_str = f", {entry.pages}." if entry.pages else ""
                return f"{auth_str} ({entry.year}). {entry.title}.{venue_str}{vol_str}{pages_str}".strip()

            if fmt == CitationFormat.IEEE:
                auth_str = ", ".join(entry.authors)
                return f'{auth_str}, "{entry.title}," {entry.venue}, {entry.year}.'

            return f"{', '.join(entry.authors)} ({entry.year}). {entry.title}."

    def import_bibtex(self, bibtex_str: str) -> List[CitationEntry]:
        """Parses a BibTeX string and imports all valid bibliography entries."""
        with self._lock:
            entries: List[CitationEntry] = []
            pattern = re.compile(r"@(\w+)\s*\{\s*([^,]+),\s*([\s\S]*?)\n\s*\}", re.MULTILINE)
            field_pattern = re.compile(r"(\w+)\s*=\s*\{([^}]*)\}", re.IGNORECASE)

            for match in pattern.finditer(bibtex_str):
                entry_type = match.group(1).lower()
                key = match.group(2).strip()
                body = match.group(3)

                fields = {}
                for fmatch in field_pattern.finditer(body):
                    fname = fmatch.group(1).lower()
                    fval = fmatch.group(2).strip()
                    fields[fname] = fval

                title = fields.get("title", "Untitled")
                author_raw = fields.get("author", fields.get("authors", ""))
                authors = [a.strip() for a in author_raw.split(" and ")] if author_raw else ["Anonymous"]
                year_raw = fields.get("year", "2024")
                try:
                    year = int(year_raw)
                except ValueError:
                    year = 2024
                venue = fields.get("journal", fields.get("booktitle", fields.get("venue", "")))

                entry = self.register(
                    key=key,
                    title=title,
                    authors=authors,
                    year=year,
                    venue=venue,
                    bibtex=match.group(0).strip(),
                )
                entries.append(entry)

            return entries

    def record_citations(self, citation_id: str, count: int) -> None:
        """Sets external citation count for a publication."""
        with self._lock:
            entry = self._citations.get(citation_id)
            if not entry:
                cid = self._key_index.get(citation_id)
                entry = self._citations.get(cid) if cid else None
            if entry:
                entry.citation_count = count

    def record_citation(self, citing_id: str, cited_id: str) -> bool:
        """Records internal citation between two registered entries."""
        with self._lock:
            cited = self._citations.get(cited_id)
            if not cited:
                return False
            if citing_id not in cited.citing_paper_ids:
                cited.citing_paper_ids.append(citing_id)
                cited.citation_count = len(cited.citing_paper_ids)
            return True

    def compute_h_index(self, author_name: Optional[str] = None) -> int:
        """
        Computes Hirsch h-index: the maximum h such that h publications
        have at least h citations each.
        """
        with self._lock:
            if author_name:
                cids = self._author_index.get(author_name.strip().lower(), set())
                entries = [self._citations[cid] for cid in cids if cid in self._citations]
            else:
                entries = list(self._citations.values())

            if not entries:
                return 0

            counts = sorted([e.citation_count for e in entries], reverse=True)
            h = 0
            for i, count in enumerate(counts):
                if count >= i + 1:
                    h = i + 1
                else:
                    break
            return h
