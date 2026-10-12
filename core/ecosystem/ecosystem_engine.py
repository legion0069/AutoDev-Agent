"""
ecosystem_engine.py - Master External Intelligence & Ecosystem Awareness Engine (v3.2)

Coordinates all 10 ecosystem intelligence subsystems:
1. DependencyScanner & DependencyAnalyzer (core/dependency_intelligence)
2. SecurityIntelligenceEngine & VulnerabilityScanner (core/ecosystem/security_intelligence.py)
3. FrameworkIntelligenceEngine (core/ecosystem/framework_intelligence.py)
4. OSSIntelligenceEngine (core/ecosystem/oss_intelligence.py)
5. TechnologyRadarEngine (core/ecosystem/tech_radar.py)
6. MigrationPlanner (core/ecosystem/migration_planner.py)
7. CompatibilityAnalyzer (core/ecosystem/compatibility_analyzer.py)
8. EngineeringRecommendationEngine (core/ecosystem/engineering_recommender.py)
9. ReleaseIntelligenceEngine (core/ecosystem/release_intelligence.py)
10. ExternalKnowledgeCache (core/ecosystem/external_knowledge_cache.py)
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from core.ecosystem.compatibility_analyzer import CompatibilityAnalyzer
from core.ecosystem.engineering_recommender import EngineeringRecommendationEngine
from core.ecosystem.external_knowledge_cache import ExternalKnowledgeCache
from core.ecosystem.framework_intelligence import FrameworkIntelligenceEngine
from core.ecosystem.migration_planner import MigrationPlanner
from core.ecosystem.oss_intelligence import OSSIntelligenceEngine
from core.ecosystem.release_intelligence import ReleaseIntelligenceEngine
from core.ecosystem.security_intelligence import SecurityIntelligenceEngine
from core.ecosystem.tech_radar import TechnologyRadarEngine

logger = logging.getLogger("AutoDev.EcosystemEngine")


class ExternalIntelligenceEngine:
    """
    Master External Intelligence & Ecosystem Awareness Engine for AutoDev Version 3.2.
    Integrates scanning, security, framework tracking, tech radar, migration planning,
    and release intelligence into a unified pipeline.
    """

    def __init__(self, cache_dir: Optional[str] = None, auto_persist: bool = True) -> None:
        self._lock = threading.RLock()

        # Import lazily to avoid circular imports
        from core.dependency_intelligence.dependency_scanner import DependencyScanner
        from core.dependency_intelligence.dependency_analyzer import DependencyAnalyzer

        # Initialize the 10 subsystems
        self.dependency_scanner = DependencyScanner()
        self.dependency_analyzer = DependencyAnalyzer(self.dependency_scanner)
        self.security_engine = SecurityIntelligenceEngine()
        self.framework_intelligence = FrameworkIntelligenceEngine()
        self.oss_intelligence = OSSIntelligenceEngine()
        self.tech_radar = TechnologyRadarEngine()
        self.migration_planner = MigrationPlanner()
        self.compatibility_analyzer = CompatibilityAnalyzer()
        self.recommendation_engine = EngineeringRecommendationEngine()
        self.release_intelligence = ReleaseIntelligenceEngine()
        self.knowledge_cache = ExternalKnowledgeCache(cache_dir=cache_dir, auto_persist=auto_persist)

        self._seed_cache()

    def _seed_cache(self) -> None:
        """Seeds cache with baseline framework and advisory data if empty."""
        if self.knowledge_cache.count() == 0:
            self.knowledge_cache.put(
                key="fastapi",
                category="FRAMEWORK",
                title="FastAPI Web Framework",
                content="FastAPI modern async framework with Pydantic v2 validation and OpenAPI generation.",
                version="0.115.0",
            )
            self.knowledge_cache.put(
                key="react",
                category="FRAMEWORK",
                title="React UI Framework",
                content="React 18/19 declarative frontend library with concurrent mode and actions.",
                version="18.3.1",
            )
            self.knowledge_cache.put(
                key="spring_boot",
                category="FRAMEWORK",
                title="Spring Boot Enterprise Framework",
                content="Spring Boot 3.3 Java enterprise framework with Jakarta EE and native AOT compilation.",
                version="3.3.0",
            )
            self.knowledge_cache.put(
                key="cve_2024_21503",
                category="SECURITY_ADVISORY",
                title="PyCrypto Critical Vulnerability Advisory",
                content="PyCrypto unmaintained buffer overflow vulnerability CVE-2024-21503. Migrate to cryptography.",
                version="2.6.1",
            )

    # -----------------------------------------------------------------------
    # Comprehensive Analysis Pipeline
    # -----------------------------------------------------------------------

    def analyze_ecosystem(
        self,
        project_dir: Optional[str] = None,
        source_files: Optional[Dict[str, str]] = None,
        project_type: str = "web_api",
        primary_runtime: str = "Python",
        runtime_version: str = "3.12",
    ) -> Dict[str, Any]:
        """
        Executes complete multi-dimensional ecosystem analysis:
        Dependencies + Security + Frameworks + Compatibility + Recommendations.
        """
        with self._lock:
            # 1. Scan and analyze dependencies
            nodes = self.dependency_scanner.scan_directory(project_dir) if project_dir else []
            dep_report = self.dependency_analyzer.analyze_dependencies(nodes, source_code_files=source_files)

            # 2. Security intelligence scan
            sec_report = self.security_engine.scan_project(nodes, source_files or {})

            # 3. Compatibility matrix
            dep_pairs = [(n.name, n.current_version) for n in nodes]
            compat_report = self.compatibility_analyzer.generate_compatibility_matrix(
                primary_runtime=primary_runtime,
                runtime_version=runtime_version,
                dependencies=dep_pairs,
            )

            # 4. Recommendations
            recommendations = self.recommendation_engine.recommend_for_project(
                project_type=project_type,
                language=primary_runtime.lower(),
            )

            # 5. Technology radar
            radar_report = self.tech_radar.generate_radar_report()

            # Compile unified report bundle
            return {
                "timestamp": time.time(),
                "dependency_report": dep_report,
                "security_report": sec_report,
                "compatibility_report": compat_report,
                "engineering_recommendations": [r.to_dict() for r in recommendations],
                "technology_radar": radar_report,
                "cached_external_knowledge_count": self.knowledge_cache.count(),
            }

    def run_full_ecosystem_analysis(
        self,
        project_dir: Optional[str] = None,
        source_files: Optional[Dict[str, str]] = None,
        project_type: str = "web_api",
        primary_runtime: str = "Python",
        runtime_version: str = "3.12",
    ) -> Dict[str, Any]:
        """Alias for analyze_ecosystem."""
        return self.analyze_ecosystem(
            project_dir=project_dir,
            source_files=source_files,
            project_type=project_type,
            primary_runtime=primary_runtime,
            runtime_version=runtime_version,
        )

    # -----------------------------------------------------------------------
    # Reporting Subsystem Helpers
    # -----------------------------------------------------------------------

    def generate_dependency_report(self, project_dir: str) -> Dict[str, Any]:
        nodes = self.dependency_scanner.scan_directory(project_dir)
        return self.dependency_analyzer.analyze_dependencies(nodes)

    def generate_security_report(
        self,
        dependencies: Optional[List[Any]] = None,
        source_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return self.security_engine.scan_project(dependencies or [], source_files or {})

    def generate_framework_report(self, framework_name: str, current_version: str) -> Dict[str, Any]:
        return self.framework_intelligence.evaluate_framework(framework_name, current_version)

    def generate_migration_report(self, technology: str, from_version: str, to_version: str) -> Dict[str, Any]:
        return self.migration_planner.plan_migration(technology, from_version, to_version).to_dict()

    def generate_technology_radar_report(self) -> Dict[str, Any]:
        return self.tech_radar.generate_radar_report()

    def generate_compatibility_report(
        self,
        runtime: str,
        runtime_version: str,
        dependencies: List[tuple],
    ) -> Dict[str, Any]:
        return self.compatibility_analyzer.generate_compatibility_matrix(runtime, runtime_version, dependencies)

    def generate_release_intelligence_report(self, updates: List[Dict[str, str]]) -> Dict[str, Any]:
        return self.release_intelligence.generate_batch_release_report(updates)

    def generate_engineering_recommendation_report(self, project_type: str = "web_api", language: str = "python") -> Dict[str, Any]:
        recs = self.recommendation_engine.recommend_for_project(project_type=project_type, language=language)
        return {"recommendations": [r.to_dict() for r in recs]}


# Backwards compatibility alias
EcosystemEngine = ExternalIntelligenceEngine
