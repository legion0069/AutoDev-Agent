"""
__init__.py - Ecosystem & External Intelligence Package Exports (v3.2)
"""

from core.ecosystem.compatibility_analyzer import CompatibilityAnalyzer
from core.ecosystem.ecosystem_engine import EcosystemEngine, ExternalIntelligenceEngine
from core.ecosystem.ecosystem_models import (
    CVEAdvisory,
    CompatibilityCheckResult,
    CompatibilityStatus,
    DependencyEcosystem,
    DependencyNode,
    DependencyRecommendation,
    EngineeringRecommendation,
    FrameworkRelease,
    MigrationPlan,
    MigrationStep,
    PackageVersion,
    RadarQuadrant,
    RadarRing,
    ReleaseAnalysis,
    ReleaseImpact,
    SeverityLevel,
    TechRadarEntry,
    VulnerabilityFinding,
)
from core.ecosystem.engineering_recommender import EngineeringRecommendationEngine
from core.ecosystem.external_knowledge_cache import ExternalKnowledgeCache
from core.ecosystem.framework_intelligence import FrameworkIntelligenceEngine
from core.ecosystem.migration_planner import MigrationPlanner
from core.ecosystem.oss_intelligence import OSSIntelligenceEngine
from core.ecosystem.release_intelligence import ReleaseIntelligenceEngine
from core.ecosystem.security_intelligence import (
    CVEAnalyzer,
    SecurityAdvisoryDatabase,
    SecurityIntelligenceEngine,
    VulnerabilityScanner,
)
from core.ecosystem.tech_radar import TechnologyRadarEngine

__all__ = [
    "ExternalIntelligenceEngine",
    "EcosystemEngine",
    "SecurityIntelligenceEngine",
    "SecurityAdvisoryDatabase",
    "CVEAnalyzer",
    "VulnerabilityScanner",
    "FrameworkIntelligenceEngine",
    "OSSIntelligenceEngine",
    "TechnologyRadarEngine",
    "MigrationPlanner",
    "CompatibilityAnalyzer",
    "EngineeringRecommendationEngine",
    "ReleaseIntelligenceEngine",
    "ExternalKnowledgeCache",
    "DependencyEcosystem",
    "SeverityLevel",
    "RadarRing",
    "RadarQuadrant",
    "ReleaseImpact",
    "CompatibilityStatus",
    "PackageVersion",
    "DependencyNode",
    "DependencyRecommendation",
    "CVEAdvisory",
    "VulnerabilityFinding",
    "FrameworkRelease",
    "TechRadarEntry",
    "MigrationStep",
    "MigrationPlan",
    "CompatibilityCheckResult",
    "EngineeringRecommendation",
    "ReleaseAnalysis",
]
