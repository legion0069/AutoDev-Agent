"""
core/patent_generator.py - Autonomous Intellectual Property & Patent Application Generator (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PatentClaim:
    """An individual independent or dependent patent claim."""
    claim_number: int
    is_independent: bool
    text: str
    depends_on: Optional[int] = None

    def format_text(self) -> str:
        if self.is_independent:
            return f"{self.claim_number}. A computer-implemented system and method comprising: {self.text.strip()}"
        return f"{self.claim_number}. The method of claim {self.depends_on}, further comprising: {self.text.strip()}"


@dataclass
class PatentApplication:
    """Formal intellectual property patent disclosure document."""
    patent_id: str
    title: str
    inventors: List[str]
    abstract: str
    technical_field: str
    background: str
    summary: str
    detailed_description: str
    claims: List[PatentClaim]
    advantages: str
    industrial_applications: str
    created_at: float = field(default_factory=time.time)

    def to_markdown(self) -> str:
        """Renders the patent specification into standardized legal patent draft Markdown."""
        inventors_str = ", ".join(self.inventors)
        date_str = time.strftime("%Y-%m-%d", time.gmtime(self.created_at))

        claims_lines = [c.format_text() for c in self.claims]
        claims_formatted = "\n\n".join(claims_lines)

        return f"""# UNITED STATES PATENT AND TRADEMARK OFFICE SPECIFICATION

**TITLE:** {self.title}  
**DOCKET / PATENT ID:** `{self.patent_id}`  
**FILING DATE:** {date_str}  
**INVENTORS:** {inventors_str}  

---

## ABSTRACT
{self.abstract.strip()}

---

## TECHNICAL FIELD
{self.technical_field.strip()}

## BACKGROUND OF THE INVENTION
{self.background.strip()}

## BRIEF SUMMARY OF THE INVENTION
{self.summary.strip()}

## DETAILED DESCRIPTION OF THE PREFERRED EMBODIMENTS
{self.detailed_description.strip()}

## ADVANTAGES OF THE INVENTION
{self.advantages.strip()}

## INDUSTRIAL APPLICABILITY
{self.industrial_applications.strip()}

## CLAIMS
What is claimed is:

{claims_formatted}
"""


class PatentGenerator:
    """
    Autonomous patent generator drafting complete intellectual property applications
    from newly discovered algorithms, architectures, and empirical breakthroughs.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._patents: Dict[str, PatentApplication] = {}

    def draft_patent(
        self,
        title: str,
        inventors: List[str],
        abstract: str,
        technical_field: str,
        background: str,
        summary: str,
        detailed_description: str,
        claims: List[PatentClaim],
        advantages: str,
        industrial_applications: str,
    ) -> PatentApplication:
        """Assembles a formal patent application."""
        with self._lock:
            pid = f"PAT-{uuid.uuid4().hex[:8].upper()}"
            patent = PatentApplication(
                patent_id=pid,
                title=title,
                inventors=inventors,
                abstract=abstract,
                technical_field=technical_field,
                background=background,
                summary=summary,
                detailed_description=detailed_description,
                claims=claims,
                advantages=advantages,
                industrial_applications=industrial_applications,
            )
            self._patents[pid] = patent
            return patent

    def synthesize_from_algorithm(
        self,
        algorithm_name: str,
        inventors: List[str],
        algorithm_domain: str,
        specification_text: str,
        performance_gain_description: str,
    ) -> PatentApplication:
        """Synthesizes a complete patent disclosure from an algorithm record."""
        title = f"SYSTEM AND METHOD FOR {algorithm_name.upper()} IN AUTONOMOUS COMPUTING ECOSYSTEMS"
        abstract = (
            f"An autonomous computing system and computer-implemented method for {algorithm_name}. "
            f"The system provides deterministic optimization in the {algorithm_domain} domain by "
            f"dynamically scheduling resources and executing specialized algorithms. The invention "
            f"achieves substantial performance advantages, specifically {performance_gain_description}."
        )

        tech_field = (
            f"The present disclosure relates generally to autonomous multi-agent computing environments, "
            f"and more specifically to algorithmic optimization systems and computer-implemented methods for {algorithm_domain}."
        )

        bg = (
            f"Conventional automated engineering frameworks suffer from severe latency bottlenecks, non-deterministic "
            f"execution stalls, and excessive resource consumption when scaled. Existing methods fail to provide "
            f"deterministic, tamper-evident optimization without external third-party dependencies. "
            f"Therefore, an improved mechanism for {algorithm_name} is urgently needed."
        )

        summ = (
            f"To overcome the deficiencies of the prior art, the present invention discloses an autonomous system "
            f"executing {algorithm_name}. The system introduces novel state indexing, cryptographic payload verification, "
            f"and adaptive priority routing to ensure deterministic execution within strict mathematical bounds."
        )

        det_desc = (
            f"In accordance with exemplary embodiments, the system comprises a plurality of processing agents "
            f"communicating via an authenticated bus. The algorithm executes according to the following logic:\n\n"
            f"```\n{specification_text}\n```\n\n"
            f"During operation, in-flight data packets are prioritized according to empirical utility scores, "
            f"achieving bounded algorithmic complexity."
        )

        adv = (
            f"The invention provides several distinct advantages over prior systems: "
            f"(1) eliminates reliance on external runtime orchestration frameworks, "
            f"(2) delivers proven performance improvements including {performance_gain_description}, and "
            f"(3) guarantees deterministic reproducibility across multi-agent threads."
        )

        ind_app = (
            f"The disclosed embodiments are directly applicable to enterprise software development, distributed "
            f"cloud computing, real-time algorithmic arbitration, and autonomous AI infrastructure management."
        )

        claims = [
            PatentClaim(
                claim_number=1,
                is_independent=True,
                text=(
                    f"obtaining operational execution parameters for {algorithm_name}; "
                    f"evaluating a objective function across one or more processing nodes; and "
                    f"dynamically reallocating compute resources to achieve {performance_gain_description}."
                ),
            ),
            PatentClaim(
                claim_number=2,
                is_independent=False,
                depends_on=1,
                text="wherein the evaluation is performed using a deterministic Upper Confidence Bound (UCB) surrogate model.",
            ),
            PatentClaim(
                claim_number=3,
                is_independent=False,
                depends_on=1,
                text="wherein communication across said processing nodes is authenticated using SHA-256 cryptographic hashes.",
            ),
        ]

        return self.draft_patent(
            title=title,
            inventors=inventors,
            abstract=abstract,
            technical_field=tech_field,
            background=bg,
            summary=summ,
            detailed_description=det_desc,
            claims=claims,
            advantages=adv,
            industrial_applications=ind_app,
        )

    def get_patent(self, patent_id: str) -> Optional[PatentApplication]:
        with self._lock:
            return self._patents.get(patent_id)
