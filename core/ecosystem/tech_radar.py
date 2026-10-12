"""
tech_radar.py - Organization Technology Radar Engine (v3.2)

Classifies technologies across 4 rings:
- Adopt: Strongly proven, recommended default for production.
- Trial: Successful in POCs, ready for pilot projects.
- Assess: Promising, explore to understand impact.
- Hold: Proceed with caution, sunsetting, or not recommended for new projects.

Across 4 quadrants:
- Languages & Frameworks
- Libraries & Packages
- Tools & Testing
- Infrastructure & Storage
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

from core.ecosystem.ecosystem_models import RadarQuadrant, RadarRing, TechRadarEntry

logger = logging.getLogger("AutoDev.TechnologyRadar")


class TechnologyRadarEngine:
    """
    Maintains and generates the organizational Technology Radar,
    providing technology governance and adoption guidance.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, TechRadarEntry] = {}
        self._load_default_radar()

    def _load_default_radar(self) -> None:
        default_items = [
            # Languages & Frameworks
            TechRadarEntry(
                name="FastAPI",
                quadrant=RadarQuadrant.LANGUAGES_AND_FRAMEWORKS,
                ring=RadarRing.ADOPT,
                description="Modern, high-performance async Python web framework using type hints.",
                rationale="Standard framework for high-throughput microservices and AI agent endpoints.",
                maturity_score=95.0,
            ),
            TechRadarEntry(
                name="Python 3.12",
                quadrant=RadarQuadrant.LANGUAGES_AND_FRAMEWORKS,
                ring=RadarRing.ADOPT,
                description="Latest high-performance stable Python runtime with sub-interpreter support.",
                rationale="Substantial speedup and enhanced tracebacks.",
                maturity_score=98.0,
            ),
            TechRadarEntry(
                name="Flask",
                quadrant=RadarQuadrant.LANGUAGES_AND_FRAMEWORKS,
                ring=RadarRing.HOLD,
                description="WSGI synchronous micro-framework.",
                rationale="Hold for new API projects in favor of FastAPI for async concurrency.",
                maturity_score=85.0,
                recommended_alternatives=["FastAPI"],
            ),
            TechRadarEntry(
                name="React 18",
                quadrant=RadarQuadrant.LANGUAGES_AND_FRAMEWORKS,
                ring=RadarRing.ADOPT,
                description="Industry standard declarative UI library.",
                rationale="Widespread enterprise ecosystem and mature tooling.",
                maturity_score=99.0,
            ),
            TechRadarEntry(
                name="React 19",
                quadrant=RadarQuadrant.LANGUAGES_AND_FRAMEWORKS,
                ring=RadarRing.TRIAL,
                description="Latest React release with Actions and server directives.",
                rationale="Trial for greenfield UI projects; verify library compatibility.",
                maturity_score=82.0,
            ),
            TechRadarEntry(
                name="Spring Boot 3",
                quadrant=RadarQuadrant.LANGUAGES_AND_FRAMEWORKS,
                ring=RadarRing.ADOPT,
                description="Java 17+ baseline enterprise service framework.",
                rationale="Official current LTS line for JVM architectures.",
                maturity_score=96.0,
            ),
            TechRadarEntry(
                name="Spring Boot 2",
                quadrant=RadarQuadrant.LANGUAGES_AND_FRAMEWORKS,
                ring=RadarRing.HOLD,
                description="Legacy Spring Boot 2.x line.",
                rationale="OSS support ended. Migrate all projects to Spring Boot 3.",
                maturity_score=60.0,
                recommended_alternatives=["Spring Boot 3"],
            ),
            # Libraries & Packages
            TechRadarEntry(
                name="Pydantic v2",
                quadrant=RadarQuadrant.LIBRARIES_AND_PACKAGES,
                ring=RadarRing.ADOPT,
                description="High-performance data validation engine with Rust core.",
                rationale="5-10x throughput speedup over v1.",
                maturity_score=96.0,
            ),
            TechRadarEntry(
                name="Requests",
                quadrant=RadarQuadrant.LIBRARIES_AND_PACKAGES,
                ring=RadarRing.ADOPT,
                description="Standard synchronous HTTP library.",
                rationale="Proven reliability for sync workloads.",
                maturity_score=95.0,
            ),
            TechRadarEntry(
                name="HTTPX",
                quadrant=RadarQuadrant.LIBRARIES_AND_PACKAGES,
                ring=RadarRing.ADOPT,
                description="Next-generation HTTP client with async support.",
                rationale="Full async compatibility matching requests API.",
                maturity_score=92.0,
            ),
            TechRadarEntry(
                name="Moment.js",
                quadrant=RadarQuadrant.LIBRARIES_AND_PACKAGES,
                ring=RadarRing.HOLD,
                description="Legacy JavaScript date library.",
                rationale="Unmaintained, large bundle footprint. Use date-fns or dayjs.",
                maturity_score=50.0,
                recommended_alternatives=["date-fns", "dayjs"],
            ),
            # Tools & Testing
            TechRadarEntry(
                name="Pytest",
                quadrant=RadarQuadrant.TOOLS_AND_TESTING,
                ring=RadarRing.ADOPT,
                description="De facto standard testing framework for Python.",
                rationale="Rich fixture system, concise assertions, and broad plugin ecosystem.",
                maturity_score=99.0,
            ),
            TechRadarEntry(
                name="Ruff",
                quadrant=RadarQuadrant.TOOLS_AND_TESTING,
                ring=RadarRing.ADOPT,
                description="Ultra-fast Python linter and formatter written in Rust.",
                rationale="10-100x faster than Flake8 and Black combined.",
                maturity_score=94.0,
            ),
            TechRadarEntry(
                name="Nose",
                quadrant=RadarQuadrant.TOOLS_AND_TESTING,
                ring=RadarRing.HOLD,
                description="Obsolete test runner.",
                rationale="Completely abandoned.",
                maturity_score=20.0,
                recommended_alternatives=["Pytest"],
            ),
            # Infrastructure & Storage
            TechRadarEntry(
                name="PostgreSQL",
                quadrant=RadarQuadrant.INFRASTRUCTURE_AND_STORAGE,
                ring=RadarRing.ADOPT,
                description="Primary relational database with JSONB support.",
                rationale="ACID guarantees, extensibility, and cloud-native support.",
                maturity_score=100.0,
            ),
            TechRadarEntry(
                name="Redis",
                quadrant=RadarQuadrant.INFRASTRUCTURE_AND_STORAGE,
                ring=RadarRing.ADOPT,
                description="In-memory key-value data store for caching and pub/sub.",
                rationale="Sub-millisecond latencies for session states.",
                maturity_score=98.0,
            ),
            TechRadarEntry(
                name="Kubernetes",
                quadrant=RadarQuadrant.INFRASTRUCTURE_AND_STORAGE,
                ring=RadarRing.ADOPT,
                description="Container orchestration platform.",
                rationale="Standard for microservices deployment and autoscaling.",
                maturity_score=97.0,
            ),
        ]
        for item in default_items:
            self._entries[item.name.lower()] = item

    def get_entry(self, technology_name: str) -> Optional[TechRadarEntry]:
        """Looks up a technology on the radar."""
        return copy.deepcopy(self._entries.get(technology_name.lower().strip()))

    def get_by_ring(self, ring: RadarRing) -> List[TechRadarEntry]:
        """Returns all entries in a specific ring."""
        return [copy.deepcopy(e) for e in self._entries.values() if e.ring == ring]

    def get_by_quadrant(self, quadrant: RadarQuadrant) -> List[TechRadarEntry]:
        """Returns all entries in a quadrant."""
        return [copy.deepcopy(e) for e in self._entries.values() if e.quadrant == quadrant]

    def classify_technology(self, name: str) -> str:
        """Returns ring classification string ('ADOPT', 'TRIAL', 'ASSESS', 'HOLD', or 'UNTRACKED')."""
        entry = self.get_entry(name)
        return entry.ring.value if entry else "ASSESS"

    def generate_radar_report(self) -> Dict[str, Any]:
        """Generates structured organizational Technology Radar report."""
        rings: Dict[str, List[Dict[str, Any]]] = {
            "ADOPT": [],
            "TRIAL": [],
            "ASSESS": [],
            "HOLD": [],
        }
        for entry in self._entries.values():
            rings[entry.ring.value].append(entry.to_dict())

        return {
            "total_technologies": len(self._entries),
            "rings": rings,
            "adopt_count": len(rings["ADOPT"]),
            "trial_count": len(rings["TRIAL"]),
            "assess_count": len(rings["ASSESS"]),
            "hold_count": len(rings["HOLD"]),
        }
