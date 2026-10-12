"""
test_framework_and_oss_intelligence.py - Comprehensive Unit & Stress Tests for Subsystems 3 & 4
Covers:
- FrameworkIntelligenceEngine (Spring Boot, React, Angular, Vue, FastAPI, Flask, Django, Node, Express, MongoDB, PostgreSQL, Redis, Docker, Kubernetes)
- Version lifecycle status (CURRENT, OUTDATED, DEPRECATED, UNKNOWN)
- Breaking changes and deprecated APIs tracking
- OSSIntelligenceEngine: community health scores, maturity categorization, PR/issue velocity, abandoned package detection
"""

import pytest

from core.ecosystem.framework_intelligence import FrameworkIntelligenceEngine
from core.ecosystem.oss_intelligence import OSSIntelligenceEngine
from core.ecosystem.ecosystem_models import FrameworkRelease, PackageVersion


# ============================================================================
# FrameworkIntelligenceEngine Unit Tests
# ============================================================================

class TestFrameworkIntelligenceEngine:
    @pytest.fixture
    def engine(self):
        return FrameworkIntelligenceEngine()

    def test_framework_catalog_contains_core_technologies(self, engine):
        required = [
            "fastapi", "react", "spring boot", "django", "flask",
            "angular", "vue", "node", "express", "postgresql",
            "redis", "docker", "kubernetes", "mongodb"
        ]
        for tech in required:
            latest = engine.get_latest_version(tech)
            assert latest is not None, f"Framework '{tech}' not found in catalog"

    def test_fastapi_current_version_evaluation(self, engine):
        eval_result = engine.evaluate_framework("FastAPI", "0.115.0")
        assert eval_result["framework"] == "FastAPI"
        assert eval_result["is_supported"] is True
        assert eval_result["status"] in ("CURRENT", "OUTDATED")
        assert eval_result["migration_recommended"] is False

    def test_fastapi_outdated_version_evaluation(self, engine):
        eval_result = engine.evaluate_framework("FastAPI", "0.80.0")
        assert eval_result["status"] == "OUTDATED"
        assert eval_result["migration_recommended"] is True
        assert len(eval_result["deprecated_apis_ahead"]) > 0

    def test_react_19_breaking_changes_ahead_from_17(self, engine):
        eval_result = engine.evaluate_framework("React", "17.0.2")
        assert eval_result["status"] == "OUTDATED"
        assert eval_result["migration_recommended"] is True
        breaking = " ".join(eval_result["breaking_changes_ahead"])
        assert "defaultProps" in breaking or "Ref" in breaking or "Removed" in breaking or len(eval_result["breaking_changes_ahead"]) > 0

    def test_spring_boot_legacy_version_evaluation(self, engine):
        eval_result = engine.evaluate_framework("Spring Boot", "2.7.0")
        assert eval_result["status"] in ("OUTDATED", "DEPRECATED")
        assert eval_result["migration_recommended"] is True
        assert any("Jakarta" in b or "Java" in b for b in eval_result["breaking_changes_ahead"])

    def test_unknown_framework_fallback(self, engine):
        eval_result = engine.evaluate_framework("obscure-custom-fw", "1.0.0")
        assert eval_result["status"] == "UNKNOWN"
        assert eval_result["is_supported"] is True
        assert eval_result["recommended_version"] == "1.0.0"
        assert eval_result["breaking_changes_ahead"] == []

    def test_get_recommended_lts_version(self, engine):
        lts = engine.get_recommended_lts_version("FastAPI")
        assert lts is not None
        assert PackageVersion(lts) >= PackageVersion("0.100.0")

    def test_django_version_evaluation(self, engine):
        eval_result = engine.evaluate_framework("Django", "5.1.0")
        assert eval_result["framework"] == "Django"
        assert eval_result["is_supported"] is True

    def test_kubernetes_and_docker_support(self, engine):
        k8s_eval = engine.evaluate_framework("Kubernetes", "1.28.0")
        docker_eval = engine.evaluate_framework("Docker", "24.0.0")
        assert k8s_eval["framework"] == "Kubernetes"
        assert docker_eval["framework"] == "Docker"


# ============================================================================
# OSSIntelligenceEngine Unit Tests
# ============================================================================

class TestOSSIntelligenceEngine:
    @pytest.fixture
    def oss(self):
        return OSSIntelligenceEngine()

    def test_evaluate_mature_popular_repository_fastapi(self, oss):
        res = oss.evaluate_repository("fastapi")
        assert res["package_name"] == "fastapi"
        assert res["community_health_score"] >= 80.0
        assert res["project_maturity"] == "MATURE"
        assert res["is_healthy"] is True
        assert res["metrics"]["stars"] >= 70000
        assert res["metrics"]["active_maintainers"] >= 10

    def test_evaluate_mature_popular_repository_react(self, oss):
        res = oss.evaluate_repository("react")
        assert res["community_health_score"] >= 85.0
        assert res["project_maturity"] == "MATURE"
        assert res["is_healthy"] is True
        assert res["metrics"]["stars"] >= 200000

    def test_evaluate_abandoned_repository_pycrypto(self, oss):
        res = oss.evaluate_repository("pycrypto")
        assert res["package_name"] == "pycrypto"
        assert res["project_maturity"] == "ABANDONED"
        assert res["is_healthy"] is False
        assert "Caution" in res["recommendation"]
        assert res["metrics"]["active_maintainers"] == 0

    def test_evaluate_legacy_repository_moment(self, oss):
        res = oss.evaluate_repository("moment")
        assert res["project_maturity"] in ("LEGACY", "ACTIVE")
        assert "metrics" in res

    def test_evaluate_unknown_package_default_fallback(self, oss):
        res = oss.evaluate_repository("generic-internal-util")
        assert res["package_name"] == "generic-internal-util"
        assert res["community_health_score"] == 75.0
        assert res["project_maturity"] == "ACTIVE"
        assert res["is_healthy"] is True

    def test_case_insensitivity_in_repo_lookup(self, oss):
        res1 = oss.evaluate_repository("FastAPI")
        res2 = oss.evaluate_repository("FASTAPI")
        res3 = oss.evaluate_repository("fastapi")
        assert res1["community_health_score"] == res2["community_health_score"] == res3["community_health_score"]

    def test_pydantic_health_metrics(self, oss):
        res = oss.evaluate_repository("pydantic")
        assert res["is_healthy"] is True
        assert res["metrics"]["releases_per_year"] >= 20

    def test_score_bounded_between_0_and_100(self, oss):
        for pkg in ["fastapi", "react", "requests", "pycrypto", "moment"]:
            res = oss.evaluate_repository(pkg)
            assert 0.0 <= res["community_health_score"] <= 100.0

    def test_vue_evaluation(self):
        engine = FrameworkIntelligenceEngine()
        ev = engine.evaluate_framework("Vue", "3.5.10")
        assert ev["is_supported"] is True
        assert ev["framework"] == "Vue"

    def test_express_evaluation(self):
        engine = FrameworkIntelligenceEngine()
        ev = engine.evaluate_framework("Express", "4.21.0")
        assert ev["is_supported"] is True
        assert ev["framework"] == "Express"

    def test_angular_evaluation(self):
        engine = FrameworkIntelligenceEngine()
        ev = engine.evaluate_framework("Angular", "18.2.0")
        assert ev["is_supported"] is True
        assert ev["framework"] == "Angular"

    def test_mongodb_evaluation(self):
        engine = FrameworkIntelligenceEngine()
        ev = engine.evaluate_framework("MongoDB", "7.0.12")
        assert ev["is_supported"] is True
        assert ev["framework"] == "MongoDB"

    def test_redis_evaluation(self):
        engine = FrameworkIntelligenceEngine()
        ev = engine.evaluate_framework("Redis", "7.2.5")
        assert ev["is_supported"] is True
        assert ev["framework"] == "Redis"

    def test_node_deprecated_version(self):
        engine = FrameworkIntelligenceEngine()
        ev = engine.evaluate_framework("Node", "16.20.2")
        assert ev["status"] == "DEPRECATED"
        assert ev["is_supported"] is False
        assert ev["migration_recommended"] is True

    def test_framework_release_dataclass_fields(self):
        rel = FrameworkRelease(
            framework="TestFW",
            version="1.0.0",
            release_date="2026-01-01",
            is_lts=True,
            is_deprecated=False,
            breaking_changes=["Change A"],
            deprecated_apis=["API B"],
            recommended_min_python_or_node=">=3.11",
            migration_guide_summary="Migrate A to B",
        )
        d = rel.to_dict()
        assert d["framework"] == "TestFW"
        assert d["version"] == "1.0.0"
        assert d["is_lts"] is True
        assert len(d["breaking_changes"]) == 1

    def test_oss_requests_repository_metrics(self):
        oss = OSSIntelligenceEngine()
        res = oss.evaluate_repository("requests")
        assert res["metrics"]["stars"] >= 50000
        assert res["project_maturity"] in ("MATURE", "ACTIVE")

    def test_oss_evaluate_empty_string(self):
        oss = OSSIntelligenceEngine()
        res = oss.evaluate_repository("")
        assert res["community_health_score"] == 75.0
        assert res["project_maturity"] == "ACTIVE"

    def test_framework_case_insensitivity(self):
        engine = FrameworkIntelligenceEngine()
        res1 = engine.evaluate_framework("fastapi", "0.115.0")
        res2 = engine.evaluate_framework("FastAPI", "0.115.0")
        res3 = engine.evaluate_framework("FASTAPI", "0.115.0")
        assert res1["status"] == res2["status"] == res3["status"]

    def test_docker_version_evaluation(self):
        engine = FrameworkIntelligenceEngine()
        ev = engine.evaluate_framework("Docker", "27.2.0")
        assert ev["is_supported"] is True
        assert ev["status"] == "CURRENT"

    def test_flask_outdated_evaluation(self):
        engine = FrameworkIntelligenceEngine()
        ev = engine.evaluate_framework("Flask", "1.1.2")
        assert ev["status"] == "OUTDATED"
        assert ev["migration_recommended"] is True

    def test_spring_boot_3_current_evaluation(self):
        engine = FrameworkIntelligenceEngine()
        ev = engine.evaluate_framework("Spring Boot", "3.3.0")
        assert ev["is_supported"] is True
        assert ev["status"] == "CURRENT"

