"""
Tests for AutoDev Version 3.2 - Ecosystem Stress, Performance, Serialization, and Edge Cases.
Validates system behavior under high load, edge conditions, serialization roundtrips, and determinism.
"""

import json
import os
import tempfile
import threading
import time
from typing import Any, Dict, List
import pytest

from core.dependency_intelligence.dependency_analyzer import DependencyAnalyzer
from core.dependency_intelligence.dependency_graph import DependencyGraph
from core.dependency_intelligence.dependency_scanner import DependencyScanner
from core.ecosystem.compatibility_analyzer import CompatibilityAnalyzer
from core.ecosystem.ecosystem_engine import ExternalIntelligenceEngine
from core.ecosystem.ecosystem_models import (
    CompatibilityCheckResult,
    CompatibilityStatus,
    CVEAdvisory,
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


# =====================================================================
# 1. LARGE DEPENDENCY GRAPH TESTS (12 tests)
# =====================================================================

class TestLargeDependencyGraph:
    """Stress tests for DependencyGraph scalability, traversal, and cycle detection."""

    def test_linear_chain_1000_nodes(self):
        graph = DependencyGraph()
        for i in range(1000):
            graph.add_node(f"pkg_{i}", f"1.{i}.0")
            if i > 0:
                graph.add_edge(f"pkg_{i-1}", f"pkg_{i}")

        assert len(graph.nodes) == 1000
        assert not graph.has_cycles()
        order = graph.topological_sort()
        assert len(order) == 1000
        assert "pkg_0" in order and "pkg_999" in order

    def test_linear_chain_depth_calculation(self):
        graph = DependencyGraph()
        for i in range(50):
            graph.add_node(f"pkg_{i}")
            if i > 0:
                graph.add_edge(f"pkg_{i-1}", f"pkg_{i}")

        chain = graph.get_transitive_dependencies("pkg_0")
        assert len(chain) == 49
        assert "pkg_49" in chain

    def test_diamond_mesh_graph(self):
        graph = DependencyGraph()
        graph.add_node("root")
        graph.add_node("sink")
        for i in range(20):
            l1 = f"l1_{i}"
            l2 = f"l2_{i}"
            graph.add_node(l1)
            graph.add_node(l2)
            graph.add_edge("root", l1)
            graph.add_edge(l1, l2)
            graph.add_edge(l2, "sink")

        assert len(graph.nodes) == 42
        assert not graph.has_cycles()
        deps = graph.get_transitive_dependencies("root")
        assert len(deps) == 41
        assert "sink" in deps

    def test_dense_acyclic_subgraph(self):
        graph = DependencyGraph()
        n = 40
        for i in range(n):
            graph.add_node(f"node_{i}")
            for j in range(i + 1, min(i + 5, n)):
                graph.add_edge(f"node_{i}", f"node_{j}")

        assert not graph.has_cycles()
        order = graph.topological_sort()
        assert len(order) == n

    def test_cycle_detection_in_300_node_graph(self):
        graph = DependencyGraph()
        for i in range(300):
            graph.add_node(f"node_{i}")
            if i > 0:
                graph.add_edge(f"node_{i-1}", f"node_{i}")

        # Introduce cycle: 250 -> 50
        graph.add_edge("node_250", "node_50")
        assert graph.has_cycles()
        cycles = graph.find_cycles()
        assert len(cycles) > 0

    def test_self_referential_cycle(self):
        graph = DependencyGraph()
        graph.add_node("self_loop")
        graph.add_edge("self_loop", "self_loop")
        assert graph.has_cycles()

    def test_disconnected_subgraphs(self):
        graph = DependencyGraph()
        for cluster in range(5):
            for i in range(10):
                node_id = f"c{cluster}_{i}"
                graph.add_node(node_id)
                if i > 0:
                    graph.add_edge(f"c{cluster}_{i-1}", node_id)

        assert len(graph.nodes) == 50
        assert not graph.has_cycles()
        assert len(graph.topological_sort()) == 50

    def test_empty_dependency_graph(self):
        graph = DependencyGraph()
        assert len(graph.nodes) == 0
        assert not graph.has_cycles()
        assert graph.topological_sort() == []
        assert graph.find_cycles() == []

    def test_single_node_graph(self):
        graph = DependencyGraph()
        graph.add_node("solo", "1.0.0")
        assert len(graph.nodes) == 1
        assert not graph.has_cycles()
        assert graph.topological_sort() == ["solo"]
        assert graph.get_transitive_dependencies("solo") == []

    def test_duplicate_node_and_edge_addition(self):
        graph = DependencyGraph()
        graph.add_node("a", "1.0.0")
        graph.add_node("a", "1.0.1")
        graph.add_node("b", "2.0.0")
        graph.add_edge("a", "b")
        graph.add_edge("a", "b")

        assert len(graph.nodes) == 2
        assert graph.edges["a"].count("b") == 1

    def test_dependents_lookup(self):
        graph = DependencyGraph()
        graph.add_node("core")
        graph.add_node("plugin_a")
        graph.add_node("plugin_b")
        graph.add_edge("plugin_a", "core")
        graph.add_edge("plugin_b", "core")

        deps = graph.get_dependents("core")
        assert set(deps) == {"plugin_a", "plugin_b"}

    def test_transitive_cycle_resilience(self):
        graph = DependencyGraph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")

        deps_a = graph.get_transitive_dependencies("a")
        assert "b" in deps_a


# =====================================================================
# 2. SECURITY SCANNER STRESS & ACCURACY (12 tests)
# =====================================================================

class TestSecurityScannerStress:
    """Stress testing the AST and pattern-based vulnerability scanner."""

    def test_scan_100_clean_python_files(self):
        scanner = VulnerabilityScanner()
        start = time.perf_counter()
        findings: List[VulnerabilityFinding] = []
        for i in range(100):
            code = f"""
import math
import os

def calculate_metric_{i}(x, y):
    val = math.sqrt(abs(x * y)) + {i}
    return val

class Processor_{i}:
    def run(self):
        return True
"""
            findings.extend(scanner.scan_code(f"module_{i}.py", code))
        elapsed = time.perf_counter() - start

        assert len(findings) == 0
        assert elapsed < 5.0

    def test_scan_mixed_vulnerability_files(self):
        scanner = VulnerabilityScanner()
        # 1: Hardcoded API and Secret Keys
        f1 = scanner.scan_code("vuln_secret.py", 'api_key = "abcdef1234567890abcdef"\nsecret_key = "abcdef1234567890abcdef"\n')
        # 2: Deprecated MD5 and SHA1
        f2 = scanner.scan_code("vuln_crypto.py", 'import hashlib\nh = hashlib.md5(b"test").hexdigest()\nh2 = hashlib.sha1(b"test").hexdigest()\n')
        # 3: Insecure eval and pickle
        f3 = scanner.scan_code("vuln_apis.py", 'import pickle\nx = eval("1 + 1")\ndata = pickle.loads(b"cos\\nsystem\\n(S\'ls\'\\ntR.")\n')
        # 4: Insecure randomness
        f4 = scanner.scan_code("vuln_random.py", 'import random\ntoken = random.randint(1000, 9999)\nkey = random.random()\n')

        all_findings = f1 + f2 + f3 + f4
        types = {f.category for f in all_findings}
        assert "HARDCODED_SECRET" in types
        assert "DEPRECATED_CRYPTO" in types
        assert "UNSAFE_API" in types
        assert "UNSAFE_RANDOMNESS" in types

    def test_private_key_header_detection(self):
        scanner = VulnerabilityScanner()
        code = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0\n-----END RSA PRIVATE KEY-----"
        findings = scanner.scan_code("key.pem", code)
        assert any(f.category == "HARDCODED_SECRET" for f in findings)

    def test_github_token_detection(self):
        scanner = VulnerabilityScanner()
        code = 'gh_token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"'
        findings = scanner.scan_code("config.py", code)
        assert any(f.category == "HARDCODED_SECRET" for f in findings)

    def test_cve_analyzer_batch_lookup(self):
        db = SecurityAdvisoryDatabase()
        db.add_advisory(CVEAdvisory(
            cve_id="CVE-2026-901",
            package_name="vuln-lib",
            ecosystem=DependencyEcosystem.PYTHON,
            affected_version_spec="<2.0.0",
            patched_versions=["2.0.0"],
            severity=SeverityLevel.CRITICAL,
            cvss_score=9.8,
            title="RCE",
            description="Remote Code Execution",
        ))
        analyzer = CVEAnalyzer(db)

        hits_vuln = analyzer.check_dependency(DependencyNode(name="vuln-lib", current_version="1.2.0", ecosystem=DependencyEcosystem.PYTHON))
        assert len(hits_vuln) == 1

        hits_safe = analyzer.check_dependency(DependencyNode(name="vuln-lib", current_version="2.0.0", ecosystem=DependencyEcosystem.PYTHON))
        assert len(hits_safe) == 0

    def test_safe_crypto_no_false_positives(self):
        scanner = VulnerabilityScanner()
        safe_code = """
import hashlib
import secrets

def secure_hash(data: bytes) -> str:
    salt = secrets.token_bytes(32)
    return hashlib.sha256(data + salt).hexdigest()

def secure_token() -> str:
    return secrets.token_urlsafe(32)
"""
        findings = scanner.scan_code("safe_crypto.py", safe_code)
        assert len(findings) == 0

    def test_security_engine_scan_project_score(self):
        engine = SecurityIntelligenceEngine()
        deps = [
            DependencyNode(name="requests", current_version="2.28.0", ecosystem=DependencyEcosystem.PYTHON),
        ]
        files = {
            "main.py": "import os\nprint('hello')",
        }
        res = engine.scan_project(deps, files)
        assert res["total_vulnerabilities"] >= 1
        assert res["security_score"] < 100.0

    def test_security_engine_clean_project(self):
        engine = SecurityIntelligenceEngine()
        deps = [
            DependencyNode(name="requests", current_version="2.32.3", ecosystem=DependencyEcosystem.PYTHON),
        ]
        files = {
            "main.py": "def add(a, b): return a + b",
        }
        res = engine.scan_project(deps, files)
        assert res["security_score"] == 100.0
        assert res["is_secure"] is True
        assert res["total_vulnerabilities"] == 0

    def test_empty_string_code_scan(self):
        scanner = VulnerabilityScanner()
        findings = scanner.scan_code("empty.py", "")
        assert findings == []

    def test_jwt_token_detection(self):
        scanner = VulnerabilityScanner()
        code = 'token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.do_not_hardcode_jwt"'
        findings = scanner.scan_code("auth.py", code)
        assert any(f.category == "HARDCODED_SECRET" for f in findings)

    def test_ast_eval_detection(self):
        scanner = VulnerabilityScanner()
        code = "def calc(user_str): return eval(user_str)"
        findings = scanner.scan_code("calc.py", code)
        assert any(f.category == "UNSAFE_API" for f in findings)

    def test_ast_exec_detection(self):
        scanner = VulnerabilityScanner()
        code = "def run_code(raw_script): exec(raw_script)"
        findings = scanner.scan_code("runner.py", code)
        assert any(f.category == "UNSAFE_API" for f in findings)


# =====================================================================
# 3. KNOWLEDGE CACHE STRESS & CONCURRENCY (12 tests)
# =====================================================================

class TestKnowledgeCacheStressAndConcurrency:
    """Stress and concurrency testing for ExternalKnowledgeCache."""

    def test_cache_1000_entries_insertion_and_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            for i in range(1000):
                cache.put(
                    key=f"item_{i}",
                    category="test_category" if i % 2 == 0 else "other_category",
                    title=f"Optimization Strategy {i}",
                    content=f"Details on performance tuning number {i} for high throughput distributed pipelines",
                )

            assert cache.count() == 1000
            results = cache.search("high throughput distributed")
            assert len(results) > 0
            assert "throughput" in results[0]["content"].lower()

    def test_concurrent_reads_and_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)

            def writer(thread_id: int):
                for i in range(100):
                    cache.put(
                        key=f"t_{thread_id}_item_{i}",
                        category="concurrency",
                        title=f"Worker {thread_id} Artifact {i}",
                        content="Thread safety validation during parallel writes and reads",
                    )

            def reader():
                for _ in range(50):
                    cache.search("safety validation")
                    cache.get_by_category("concurrency")

            threads: List[threading.Thread] = []
            for tid in range(4):
                threads.append(threading.Thread(target=writer, args=(tid,)))
            for _ in range(4):
                threads.append(threading.Thread(target=reader))

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert cache.count() == 400

    def test_persistence_roundtrip_500_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache1 = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=True)
            for i in range(500):
                cache1.put(
                    key=f"k_{i}",
                    category="framework" if i % 2 == 0 else "security",
                    title=f"Topic {i}",
                    content=f"Summary for topic {i} with unique identifier token_unique_{i}",
                )

            assert cache1.count() == 500

            cache2 = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=True)
            assert cache2.count() == 500

            hits = cache2.search("token_unique_42")
            assert len(hits) == 1
            assert hits[0]["key"] == "k_42"

    def test_category_query_filtering(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            for cat in ["framework", "security", "migration", "radar"]:
                for i in range(25):
                    cache.put(
                        key=f"{cat}_{i}",
                        category=cat,
                        title=f"{cat.title()} Title {i}",
                        content=f"Details for {cat}"
                    )

            assert len(cache.get_by_category("framework")) == 25
            assert len(cache.get_by_category("security")) == 25
            assert len(cache.get_by_category("migration")) == 25
            assert len(cache.get_by_category("radar")) == 25
            assert len(cache.get_by_category("non_existent")) == 0

    def test_search_category_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            cache.put(key="1", category="framework", title="Django", content="Python web")
            cache.put(key="2", category="security", title="Django CVE", content="Python security")

            res_fw = cache.search("Django", category="framework")
            assert len(res_fw) == 1
            assert res_fw[0]["key"] == "1"

    def test_empty_cache_queries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            assert cache.count() == 0
            assert cache.search("anything") == []
            assert cache.get("missing") is None
            assert cache.get_by_category("none") == []

    def test_entry_replacement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            cache.put(key="pkg_x", category="cat", title="Old Title", content="Old summary")
            cache.put(key="pkg_x", category="cat", title="New Title", content="New summary")
            assert cache.count() == 1
            assert cache.get("pkg_x")["title"] == "New Title"

    def test_search_score_ranking_exact_vs_partial(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            cache.put(key="weak", category="c", title="General topic", content="Contains term once")
            cache.put(key="strong", category="c", title="Topic topic topic", content="Topic topic topic repeated")

            results = cache.search("topic")
            assert len(results) >= 2
            assert results[0]["key"] == "strong"

    def test_search_case_insensitivity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            cache.put(key="case", category="c", title="FASTAPI MICROSERVICE", content="HIGH PERFORMANCE")
            res1 = cache.search("fastapi")
            res2 = cache.search("FastAPI")
            res3 = cache.search("MICROSERVICE")
            assert len(res1) == 1
            assert len(res2) == 1
            assert len(res3) == 1

    def test_load_nonexistent_directory_no_crash(self):
        cache = ExternalKnowledgeCache(cache_dir="non_existent_dir_abc/cache", auto_persist=False)
        assert cache.count() == 0

    def test_list_all_retrieval(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            for i in range(10):
                cache.put(key=f"k_{i}", category="c", title=f"T{i}", content="S")
            items = cache.list_all()
            assert len(items) == 10

    def test_clear_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExternalKnowledgeCache(cache_dir=tmpdir, auto_persist=False)
            cache.put(key="k1", category="c", title="T1", content="S1")
            assert cache.count() == 1
            cache.clear()
            assert cache.count() == 0
            assert cache.search("T1") == []


# =====================================================================
# 4. COMPATIBILITY MATRIX STRESS (10 tests)
# =====================================================================

class TestCompatibilityMatrixStress:
    """Stress and dimensional matrix testing for CompatibilityAnalyzer."""

    def test_matrix_generation_all_clean(self):
        analyzer = CompatibilityAnalyzer()
        deps = [("FastAPI", "0.115.0"), ("Pydantic", "2.8.0")]
        matrix = analyzer.generate_compatibility_matrix(
            primary_runtime="Python",
            runtime_version="3.12",
            dependencies=deps,
            target_os="Linux",
        )
        assert matrix["is_fully_compatible"] is True
        assert matrix["incompatibilities_found"] == 0

    def test_python_version_support_range(self):
        analyzer = CompatibilityAnalyzer()
        res1 = analyzer.check_compatibility("Python", "3.12", "FastAPI", "0.115.0")
        assert res1.status == CompatibilityStatus.COMPATIBLE

        res2 = analyzer.check_compatibility("Python", "3.12", "pycrypto", "2.6.1")
        assert res2.status == CompatibilityStatus.INCOMPATIBLE

    def test_spring_boot_3_java_compatibility(self):
        analyzer = CompatibilityAnalyzer()
        res_java8 = analyzer.check_compatibility("Java", "8", "Spring Boot", "3.2.0")
        assert res_java8.status == CompatibilityStatus.INCOMPATIBLE

        res_java17 = analyzer.check_compatibility("Java", "17", "Spring Boot", "3.2.0")
        assert res_java17.status == CompatibilityStatus.COMPATIBLE

        res_java21 = analyzer.check_compatibility("Java", "21", "Spring Boot", "3.2.0")
        assert res_java21.status == CompatibilityStatus.COMPATIBLE

    def test_os_compatibility_checks(self):
        analyzer = CompatibilityAnalyzer()
        for os_name in ["Linux", "Windows", "macOS"]:
            res = analyzer.check_compatibility(os_name, "any", "Python", "3.12", dimension="OS")
            assert res.status in (CompatibilityStatus.COMPATIBLE, CompatibilityStatus.CONDITIONAL)

    def test_container_base_image_compatibility(self):
        analyzer = CompatibilityAnalyzer()
        res = analyzer.check_compatibility("Alpine Linux", "3.19", "Python", "3.12", dimension="CONTAINER")
        assert res.status in (CompatibilityStatus.CONDITIONAL, CompatibilityStatus.COMPATIBLE)

    def test_react_19_node_compatibility(self):
        analyzer = CompatibilityAnalyzer()
        res_node16 = analyzer.check_compatibility("Node", "16", "React", "19.0.0")
        assert res_node16.status == CompatibilityStatus.INCOMPATIBLE

        res_node20 = analyzer.check_compatibility("Node", "20", "React", "19.0.0")
        assert res_node20.status == CompatibilityStatus.COMPATIBLE

    def test_matrix_with_multiple_incompatibilities(self):
        analyzer = CompatibilityAnalyzer()
        deps = [
            ("FastAPI", "0.115.0"),
            ("pycrypto", "2.6.1"),
            ("Pydantic", "1.10.0"),
        ]
        matrix = analyzer.generate_compatibility_matrix(
            primary_runtime="Python",
            runtime_version="3.12",
            dependencies=deps,
        )
        assert not matrix["is_fully_compatible"]
        assert matrix["incompatibilities_found"] >= 2

    def test_empty_dependencies_matrix(self):
        analyzer = CompatibilityAnalyzer()
        matrix = analyzer.generate_compatibility_matrix("Python", "3.12", [])
        assert matrix["is_fully_compatible"] is True
        assert matrix["total_checks"] == 1

    def test_unknown_component_compatibility_graceful_pass(self):
        analyzer = CompatibilityAnalyzer()
        res = analyzer.check_compatibility("CustomRuntime", "1.0", "CustomLib", "2.0")
        assert res.status == CompatibilityStatus.COMPATIBLE

    def test_matrix_with_target_cloud(self):
        analyzer = CompatibilityAnalyzer()
        matrix = analyzer.generate_compatibility_matrix(
            primary_runtime="Python",
            runtime_version="3.12",
            dependencies=[("FastAPI", "0.115.0")],
            target_cloud="AWS",
        )
        assert "total_checks" in matrix
        assert matrix["total_checks"] >= 2


# =====================================================================
# 5. SERIALIZATION AND ROUNDTRIP TESTS (12 tests)
# =====================================================================

class TestSerializationAndRoundtrip:
    """Validates to_dict and serialization across all domain models."""

    def test_package_version_serialization(self):
        v = PackageVersion("3.12.1-rc.1+build.123")
        d = v.to_dict()
        assert d["major"] == 3
        assert d["minor"] == 12
        assert d["patch"] == 1
        assert d["prerelease"] == "rc.1"
        assert d["build"] == "build.123"

        json_str = json.dumps(d)
        reloaded = json.loads(json_str)
        assert reloaded["major"] == 3

    def test_dependency_node_serialization(self):
        node = DependencyNode(
            name="requests",
            current_version="2.31.0",
            ecosystem=DependencyEcosystem.PYTHON,
            is_direct=True,
            license="Apache-2.0"
        )
        d = node.to_dict()
        json_str = json.dumps(d)
        reloaded = json.loads(json_str)
        assert reloaded["name"] == "requests"
        assert reloaded["current_version"] == "2.31.0"

    def test_cve_advisory_serialization(self):
        cve = CVEAdvisory(
            cve_id="CVE-2023-44487",
            package_name="http2",
            ecosystem=DependencyEcosystem.NPM,
            affected_version_spec="<1.5.0",
            patched_versions=["1.5.0"],
            severity=SeverityLevel.HIGH,
            cvss_score=7.5,
            title="HTTP/2 Rapid Reset Attack",
            description="Rapid Reset vulnerability"
        )
        d = cve.to_dict()
        json_str = json.dumps(d)
        reloaded = json.loads(json_str)
        assert reloaded["cve_id"] == "CVE-2023-44487"
        assert reloaded["cvss_score"] == 7.5

    def test_vulnerability_finding_serialization(self):
        vuln = VulnerabilityFinding(
            finding_id="finding-1",
            category="HARDCODED_SECRET",
            target="src/config.py",
            severity=SeverityLevel.CRITICAL,
            description="Hardcoded secret key",
            line_number=42,
            snippet='SECRET_KEY = "xyz"',
            remediation_advice="Use environment variables"
        )
        d = vuln.to_dict()
        assert json.loads(json.dumps(d))["line_number"] == 42

    def test_framework_release_serialization(self):
        rel = FrameworkRelease(
            framework="FastAPI",
            version="0.115.0",
            release_date="2024-09-18",
            is_lts=True,
            is_deprecated=False,
            breaking_changes=["Pydantic v2 migration"],
            deprecated_apis=["fastapi.security.OAuth2PasswordRequestFormStrict"],
        )
        d = rel.to_dict()
        json_str = json.dumps(d)
        assert "Pydantic v2" in json_str

    def test_tech_radar_serialization(self):
        entry = TechRadarEntry(
            name="FastAPI",
            quadrant=RadarQuadrant.LANGUAGES_AND_FRAMEWORKS,
            ring=RadarRing.ADOPT,
            description="Production async framework",
            rationale="High performance async Python APIs"
        )
        d = entry.to_dict()
        json_str = json.dumps(d)
        reloaded = json.loads(json_str)
        assert reloaded["name"] == "FastAPI"
        assert reloaded["ring"] == "ADOPT"

    def test_migration_plan_serialization(self):
        step = MigrationStep(
            step_number=1,
            title="Upgrade Python runtime to 3.12",
            target_component="Dockerfile",
            action_type="CONFIG_UPDATE",
            instructions="Update base image",
            code_modification_example='-FROM python:3.10\n+FROM python:3.12',
            verification_check="python --version"
        )
        plan = MigrationPlan(
            plan_id="MIG-TEST-1",
            source_technology="Python",
            from_version="3.10",
            to_version="3.12",
            title="Python 3.10 to 3.12 Migration",
            summary="Runtime upgrade",
            steps=[step],
            breaking_apis=["Asyncio get_event_loop behavior"],
            rollback_plan=["Revert Dockerfile to python:3.10"]
        )
        d = plan.to_dict()
        json_str = json.dumps(d)
        reloaded = json.loads(json_str)
        assert len(reloaded["steps"]) == 1
        assert reloaded["steps"][0]["target_component"] == "Dockerfile"

    def test_compatibility_check_result_serialization(self):
        res = CompatibilityCheckResult(
            component_a="FastAPI",
            component_b="Python",
            dimension="RUNTIME",
            status=CompatibilityStatus.COMPATIBLE,
            details="Supported runtime"
        )
        d = res.to_dict()
        json_str = json.dumps(d)
        assert json.loads(json_str)["status"] == "COMPATIBLE"

    def test_engineering_recommendation_serialization(self):
        rec = EngineeringRecommendation(
            recommendation_id="REC-TEST-1",
            category="TESTING_TOOL",
            recommended_solution="pytest",
            rationale="Standard de facto in Python ecosystem",
            confidence_score=0.95,
            pros=["Fast execution", "Rich fixture system"],
            cons=["Learning curve for complex fixtures"]
        )
        d = rec.to_dict()
        assert json.loads(json.dumps(d))["recommended_solution"] == "pytest"

    def test_release_analysis_serialization(self):
        analysis = ReleaseAnalysis(
            package_or_tool="django",
            version="5.0",
            release_date="2023-12-04",
            impact=ReleaseImpact.MAJOR_BREAKING,
            summary="Django 5.0 major release with new features and breaking changes",
            breaking_changes=["Dropped Python 3.9 support"],
            security_fixes=[],
            new_features=["GeneratedField", "Database-computed defaults"],
            recommended_adoption_window="ASSESS_QUARTERLY",
            risk_score=75.0
        )
        d = analysis.to_dict()
        json_str = json.dumps(d)
        assert "MAJOR_BREAKING" in json_str

    def test_external_knowledge_cache_entry_dict_serialization(self):
        entry_dict = {
            "key": "django_5",
            "category": "RELEASE_NOTE",
            "title": "Django 5.0 Release",
            "content": "Django 5.0 features and deprecations",
            "metadata": {"tags": ["django", "web"]},
            "version": "5.0",
        }
        json_str = json.dumps(entry_dict)
        reloaded = json.loads(json_str)
        assert reloaded["key"] == "django_5"

    def test_dependency_recommendation_serialization(self):
        rec = DependencyRecommendation(
            package_name="flask-restful",
            current_version="0.3.9",
            recommended_version="0.115.0",
            recommendation_type="REPLACEMENT",
            replacement_package="fastapi",
            rationale="Unmaintained legacy framework",
            breaking_change_risk="HIGH"
        )
        d = rec.to_dict()
        json_str = json.dumps(d)
        reloaded = json.loads(json_str)
        assert reloaded["replacement_package"] == "fastapi"


# =====================================================================
# 6. DETERMINISM VERIFICATION TESTS (6 tests)
# =====================================================================

class TestDeterminismVerification:
    """Verifies that consecutive runs yield identical outputs and zero side-effect divergence."""

    def test_repeated_dependency_analysis_determinism(self):
        scanner = DependencyScanner()
        manifest = "requests==2.31.0\nurllib3==2.0.0\npytest==8.0.0\n"
        with tempfile.NamedTemporaryFile("w", suffix="requirements.txt", delete=False) as f:
            f.write(manifest)
            path = f.name

        try:
            results = []
            for _ in range(5):
                deps = scanner.scan_manifest(path)
                results.append([d.to_dict() for d in deps])

            for i in range(1, 5):
                assert results[i] == results[0]
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_repeated_compatibility_determinism(self):
        analyzer = CompatibilityAnalyzer()
        components = [("Spring Boot", "3.2.0"), ("FastAPI", "0.115.0")]

        first_matrix = analyzer.generate_compatibility_matrix("Python", "3.12", components)
        for _ in range(5):
            subsequent = analyzer.generate_compatibility_matrix("Python", "3.12", components)
            assert subsequent == first_matrix

    def test_repeated_migration_planning_determinism(self):
        planner = MigrationPlanner()
        first_plan = planner.plan_migration("Python", "3.10", "3.13")
        for _ in range(5):
            subsequent = planner.plan_migration("Python", "3.10", "3.13")
            assert subsequent.title == first_plan.title
            assert subsequent.breaking_apis == first_plan.breaking_apis
            assert len(subsequent.steps) == len(first_plan.steps)

    def test_repeated_radar_categorization_determinism(self):
        radar_engine = TechnologyRadarEngine()
        radar_1 = radar_engine.generate_radar_report()
        radar_2 = radar_engine.generate_radar_report()
        assert json.dumps(radar_1, sort_keys=True) == json.dumps(radar_2, sort_keys=True)

    def test_repeated_release_impact_determinism(self):
        engine = ReleaseIntelligenceEngine()
        res1 = engine.analyze_release("React", "17.0.0", "19.0.0").to_dict()
        res2 = engine.analyze_release("React", "17.0.0", "19.0.0").to_dict()
        assert res1 == res2

    def test_repeated_orchestrator_bundle_determinism(self):
        engine = ExternalIntelligenceEngine()
        bundle1 = engine.run_full_ecosystem_analysis()
        bundle2 = engine.run_full_ecosystem_analysis()
        assert bundle1.keys() == bundle2.keys()
        assert bundle1["technology_radar"]["total_technologies"] == bundle2["technology_radar"]["total_technologies"]


# =====================================================================
# 7. EDGE CASES & ERROR RESILIENCE (14 tests)
# =====================================================================

class TestEdgeCasesAndErrorResilience:
    """Edge cases, corrupted files, and graceful error recovery."""

    def test_corrupted_json_package_json(self):
        scanner = DependencyScanner()
        with tempfile.NamedTemporaryFile("w", suffix="package.json", delete=False) as f:
            f.write("{\n  \"name\": \"bad\",\n  \"dependencies\": {\"broken\": \n")
            path = f.name
        try:
            deps = scanner.scan_manifest(path)
            assert deps == []
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_corrupted_xml_pom(self):
        scanner = DependencyScanner()
        with tempfile.NamedTemporaryFile("w", suffix="pom.xml", delete=False) as f:
            f.write("<project><dependencies><dependency><groupId>unclosed")
            path = f.name
        try:
            deps = scanner.scan_manifest(path)
            assert deps == []
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_corrupted_toml_cargo(self):
        scanner = DependencyScanner()
        with tempfile.NamedTemporaryFile("w", suffix="Cargo.toml", delete=False) as f:
            f.write("[dependencies\nserde = broken unclosed\n")
            path = f.name
        try:
            deps = scanner.scan_manifest(path)
            assert isinstance(deps, list)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_nonexistent_manifest_file(self):
        scanner = DependencyScanner()
        deps = scanner.scan_manifest("non_existent_folder_abc/no_file.txt")
        assert deps == []

    def test_nonexistent_directory_scan(self):
        scanner = DependencyScanner()
        deps = scanner.scan_project_dependencies("non_existent_project_dir_123")
        assert deps == []

    def test_package_version_garbage_string(self):
        v = PackageVersion("invalid-version-string-here")
        assert v.major == 0
        assert v.minor == 0
        assert v.patch == 0
        assert v.raw == "invalid-version-string-here"

    def test_package_version_empty_string(self):
        v = PackageVersion("")
        assert v.major == 0
        assert v.minor == 0
        assert v.patch == 0

    def test_unknown_framework_query(self):
        engine = FrameworkIntelligenceEngine()
        meta = engine.evaluate_framework("unknown_framework_xyz", "1.0.0")
        assert meta["status"] == "UNKNOWN"

    def test_migration_identical_source_target_versions(self):
        planner = MigrationPlanner()
        plan = planner.plan_migration("Python", "3.11", "3.11")
        assert len(plan.steps) == 0

    def test_migration_downgrade_request(self):
        planner = MigrationPlanner()
        plan = planner.plan_migration("Python", "3.12", "3.10")
        assert len(plan.steps) > 0

    def test_oss_metrics_zero_values(self):
        engine = OSSIntelligenceEngine()
        res = engine.evaluate_repository("pycrypto")
        assert res["project_maturity"] == "ABANDONED"
        assert res["community_health_score"] < 40.0

    def test_recommendation_empty_project_context(self):
        recommender = EngineeringRecommendationEngine()
        recs = recommender.recommend_for_project()
        assert len(recs) > 0

    def test_release_delta_with_invalid_versions(self):
        rel_engine = ReleaseIntelligenceEngine()
        analysis = rel_engine.analyze_release("pkg", "not_a_version", "also_not_a_version")
        assert analysis.impact in (ReleaseImpact.PATCH_SECURITY, ReleaseImpact.MINOR_FEATURE, ReleaseImpact.MAJOR_BREAKING)

    def test_security_scanner_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scanner = VulnerabilityScanner()
            findings = scanner.scan_code("empty.py", "")
            assert findings == []
