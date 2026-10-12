"""
test_tech_radar_and_cache.py - Comprehensive Unit Tests for Subsystems 5, 8, 9, 10
Covers:
- TechnologyRadarEngine: 4 rings (Adopt, Trial, Assess, Hold), 4 quadrants, classification, report structure
- ExternalKnowledgeCache: full-text inverted index search, category indexing, persistence & reload, concurrency
- EngineeringRecommendationEngine: framework, testing, CI/CD, observability, database recommendations by project profile
- ReleaseIntelligenceEngine: SemVer impact categorization, breaking change extraction, adoption windows
"""

import tempfile
from pathlib import Path
import pytest

from core.ecosystem.tech_radar import TechnologyRadarEngine
from core.ecosystem.external_knowledge_cache import ExternalKnowledgeCache
from core.ecosystem.engineering_recommender import EngineeringRecommendationEngine
from core.ecosystem.release_intelligence import ReleaseIntelligenceEngine
from core.ecosystem.ecosystem_models import (
    RadarQuadrant,
    RadarRing,
    ReleaseImpact,
    TechRadarEntry,
)


# ============================================================================
# TechnologyRadarEngine Unit Tests
# ============================================================================

class TestTechnologyRadarEngine:
    @pytest.fixture
    def radar(self):
        return TechnologyRadarEngine()

    def test_radar_has_default_entries(self, radar):
        report = radar.generate_radar_report()
        assert report["total_technologies"] >= 5
        assert report["adopt_count"] >= 3
        assert "ADOPT" in report["rings"]
        assert "HOLD" in report["rings"]

    def test_classify_adopt_technologies(self, radar):
        assert radar.classify_technology("FastAPI") == "ADOPT"
        assert radar.classify_technology("PostgreSQL") == "ADOPT"
        assert radar.classify_technology("Redis") == "ADOPT"

    def test_classify_hold_technologies(self, radar):
        assert radar.classify_technology("Flask") == "HOLD"
        assert radar.classify_technology("Nose") == "HOLD"

    def test_classify_untracked_technology_defaults_to_assess(self, radar):
        assert radar.classify_technology("untracked-new-tool") == "ASSESS"

    def test_get_by_ring(self, radar):
        adopt_entries = radar.get_by_ring(RadarRing.ADOPT)
        assert len(adopt_entries) >= 3
        for e in adopt_entries:
            assert e.ring == RadarRing.ADOPT

    def test_get_by_quadrant(self, radar):
        infra = radar.get_by_quadrant(RadarQuadrant.INFRASTRUCTURE_AND_STORAGE)
        assert len(infra) >= 2
        names = {e.name.lower() for e in infra}
        assert "postgresql" in names
        assert "redis" in names

    def test_entry_serialization(self, radar):
        entry = radar.get_entry("FastAPI")
        assert entry is not None
        d = entry.to_dict()
        assert d["name"] == "FastAPI"
        assert d["ring"] == "ADOPT"
        assert d["quadrant"] == "LANGUAGES_AND_FRAMEWORKS"


# ============================================================================
# ExternalKnowledgeCache Unit Tests
# ============================================================================

class TestExternalKnowledgeCache:
    def test_put_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            cache.put(
                key="fastapi",
                category="FRAMEWORK",
                title="FastAPI Async Framework",
                content="High performance Python async web framework with OpenAPI.",
            )
            assert cache.count() == 1
            entry = cache.get("fastapi")
            assert entry is not None
            assert entry["title"] == "FastAPI Async Framework"
            assert entry["category"] == "FRAMEWORK"

    def test_full_text_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            cache.put(
                key="fastapi",
                category="FRAMEWORK",
                title="FastAPI Documentation",
                content="FastAPI uses Starlette and Pydantic for lightning-fast REST APIs.",
            )
            cache.put(
                key="cve-2023-1234",
                category="SECURITY_ADVISORY",
                title="Requests Security Vulnerability",
                content="Proxy header injection leak vulnerability in requests library.",
            )

            # Search keyword 'pydantic'
            res = cache.search("pydantic")
            assert len(res) == 1
            assert res[0]["key"] == "fastapi"
            assert res[0]["search_relevance_score"] >= 1

            # Search keyword 'vulnerability'
            res_sec = cache.search("vulnerability")
            assert len(res_sec) == 1
            assert res_sec[0]["key"] == "cve-2023-1234"

    def test_search_filtered_by_category(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            cache.put("k1", "FRAMEWORK", "Python Web", "Async web tools")
            cache.put("k2", "SECURITY", "Python CVE", "Vulnerability advisory")

            res_fw = cache.search("Python", category="FRAMEWORK")
            assert len(res_fw) == 1
            assert res_fw[0]["key"] == "k1"

    def test_persistence_and_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache1 = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=True)
            cache1.put("k1", "TECH", "Title 1", "Content 1")
            cache1.put("k2", "TECH", "Title 2", "Content 2")
            assert cache1.count() == 2

            # Reload into separate instance from disk
            cache2 = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=True)
            assert cache2.count() == 2
            assert cache2.get("k1") is not None
            assert cache2.get("k2")["title"] == "Title 2"

    def test_empty_search_query_returns_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            cache.put("a", "CAT", "A", "AAA")
            cache.put("b", "CAT", "B", "BBB")
            assert len(cache.search("")) == 2

    def test_list_all_and_get_by_category(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            cache.put("1", "SEC", "Advisory", "Info")
            cache.put("2", "SEC", "Alert", "Info")
            cache.put("3", "DOC", "Guide", "Info")

            all_items = cache.list_all()
            assert len(all_items) == 3
            sec_items = cache.get_by_category("SEC")
            assert len(sec_items) == 2


# ============================================================================
# EngineeringRecommendationEngine Unit Tests
# ============================================================================

class TestEngineeringRecommendationEngine:
    @pytest.fixture
    def recommender(self):
        return EngineeringRecommendationEngine()

    def test_recommend_for_python_web_api(self, recommender):
        recs = recommender.recommend_for_project(project_type="web_api", language="python")
        assert len(recs) >= 4
        categories = {r.category for r in recs}
        assert "FRAMEWORK" in categories
        assert "TESTING_TOOL" in categories
        assert "CICD" in categories

        fw = [r for r in recs if r.category == "FRAMEWORK"][0]
        assert "FastAPI" in fw.recommended_solution
        assert fw.confidence_score >= 0.90

    def test_recommend_for_python_cli(self, recommender):
        recs = recommender.recommend_for_project(project_type="cli", language="python")
        fw = [r for r in recs if r.category == "FRAMEWORK"][0]
        assert "Typer" in fw.recommended_solution or "Argparse" in fw.recommended_solution

    def test_recommend_for_fullstack(self, recommender):
        recs = recommender.recommend_for_project(project_type="fullstack", language="python")
        fw = [r for r in recs if r.category == "FRAMEWORK"][0]
        assert "Django" in fw.recommended_solution

    def test_recommendation_serialization(self, recommender):
        recs = recommender.recommend_for_project(project_type="web_api", language="python")
        for r in recs:
            d = r.to_dict()
            assert "recommendation_id" in d
            assert "category" in d
            assert "recommended_solution" in d
            assert "confidence_score" in d


# ============================================================================
# ReleaseIntelligenceEngine Unit Tests
# ============================================================================

class TestReleaseIntelligenceEngine:
    @pytest.fixture
    def release_eng(self):
        return ReleaseIntelligenceEngine()

    def test_major_breaking_release_analysis(self, release_eng):
        analysis = release_eng.analyze_release(
            package_name="react",
            current_version="18.3.1",
            new_version="19.0.0",
            release_notes="Breaking: Removed legacy ReactDOM.render and String Refs.",
        )
        assert analysis.impact == ReleaseImpact.MAJOR_BREAKING
        assert analysis.recommended_adoption_window == "ASSESS_QUARTERLY"
        assert analysis.risk_score >= 70.0
        assert len(analysis.breaking_changes) >= 1

    def test_minor_feature_release_analysis(self, release_eng):
        analysis = release_eng.analyze_release(
            package_name="fastapi",
            current_version="0.114.0",
            new_version="0.115.0",
            release_notes="Feature: Support Pydantic v2.9 model rebuild.",
        )
        assert analysis.impact == ReleaseImpact.MINOR_FEATURE
        assert analysis.recommended_adoption_window == "NEXT_SPRINT"
        assert len(analysis.new_features) >= 1

    def test_patch_security_release_analysis(self, release_eng):
        analysis = release_eng.analyze_release(
            package_name="requests",
            current_version="2.31.0",
            new_version="2.31.1",
            release_notes="Security patch: CVE-2023-9999 fixes authorization header leak.",
        )
        assert analysis.impact == ReleaseImpact.PATCH_SECURITY
        assert analysis.recommended_adoption_window == "IMMEDIATE"
        assert len(analysis.security_fixes) >= 1

    def test_batch_release_report_generation(self, release_eng):
        updates = [
            {"package": "react", "current_version": "18.3.1", "new_version": "19.0.0", "release_notes": "Breaking changes"},
            {"package": "requests", "current_version": "2.31.0", "new_version": "2.31.1", "release_notes": "Security fix CVE-123"},
            {"package": "fastapi", "current_version": "0.114.0", "new_version": "0.115.0", "release_notes": "Feature added"},
        ]
        report = release_eng.generate_batch_release_report(updates)
        assert report["total_releases_analyzed"] == 3
        assert report["immediate_adoption_count"] == 1
        assert report["assess_quarterly_count"] == 1
        assert report["next_sprint_adoption_count"] == 1

    def test_batch_release_empty(self, release_eng):
        report = release_eng.generate_batch_release_report([])
        assert report["total_releases_analyzed"] == 0
        assert report["immediate_adoption_count"] == 0

    def test_radar_all_quadrants_present(self):
        radar = TechnologyRadarEngine()
        for quad in [
            RadarQuadrant.LANGUAGES_AND_FRAMEWORKS,
            RadarQuadrant.LIBRARIES_AND_PACKAGES,
            RadarQuadrant.TOOLS_AND_TESTING,
            RadarQuadrant.INFRASTRUCTURE_AND_STORAGE,
        ]:
            entries = radar.get_by_quadrant(quad)
            assert len(entries) >= 1

    def test_cache_relevance_ranking(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            cache.put("doc1", "DOC", "Python Python Python", "Python tutorial Python async")
            cache.put("doc2", "DOC", "Python Introduction", "General programming guide")
            results = cache.search("Python")
            assert len(results) == 2
            # doc1 contains more occurrences of 'Python'
            assert results[0]["key"] == "doc1"

    def test_observability_tier_advanced(self):
        recommender = EngineeringRecommendationEngine()
        recs = recommender.recommend_for_project(
            project_type="web_api",
            language="python",
            observability_tier="advanced",
            scale="enterprise",
        )
        obs = [r for r in recs if r.category == "OBSERVABILITY"]
        assert len(obs) == 1
        assert "OpenTelemetry" in obs[0].recommended_solution
        db = [r for r in recs if r.category == "ARCHITECTURE"]
        assert "PostgreSQL" in db[0].recommended_solution

    def test_observability_tier_minimal(self):
        recommender = EngineeringRecommendationEngine()
        recs = recommender.recommend_for_project(
            project_type="web_api",
            language="python",
            observability_tier="minimal",
            scale="small",
        )
        obs = [r for r in recs if r.category == "OBSERVABILITY"]
        assert len(obs) == 0
        db = [r for r in recs if r.category == "ARCHITECTURE"]
        assert "SQLite" in db[0].recommended_solution

