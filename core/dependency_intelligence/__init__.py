"""
__init__.py - Dependency Intelligence Package Exports (v3.2)
"""

from core.dependency_intelligence.dependency_analyzer import DependencyAnalyzer
from core.dependency_intelligence.dependency_graph import DependencyGraph
from core.dependency_intelligence.dependency_scanner import DependencyScanner
from core.ecosystem.ecosystem_models import (
    DependencyEcosystem,
    DependencyNode,
    DependencyRecommendation,
    PackageVersion,
)

__all__ = [
    "DependencyScanner",
    "DependencyGraph",
    "DependencyAnalyzer",
    "PackageVersion",
    "DependencyNode",
    "DependencyRecommendation",
    "DependencyEcosystem",
]
