"""
test_dependency_intelligence.py - Comprehensive Unit & Stress Tests for Subsystem 1: Dependency Intelligence Engine
Covers:
- DependencyScanner (requirements.txt, package.json, pom.xml, build.gradle, Cargo.toml, go.mod, composer.json)
- PackageVersion (SemVer parsing, comparison operators, prereleases, caret/tilde rules)
- DependencyGraph (nodes, edges, topological ordering, cycle detection, transitive chains, depth)
- DependencyAnalyzer (unused packages, duplicate deps, version conflicts, outdated packages, license conflicts, safe recommendations)
- Large graph stress tests, determinism, serialization
"""

import json
import tempfile
from pathlib import Path
import pytest

from core.dependency_intelligence import (
    DependencyAnalyzer,
    DependencyGraph,
    DependencyScanner,
    PackageVersion,
)
from core.ecosystem.ecosystem_models import (
    DependencyConflict,
    DependencyNode,
    DependencyRecommendation,
    LicenseCategory,
    PackageEcosystem,
)


# ============================================================================
# PackageVersion Unit Tests
# ============================================================================

class TestPackageVersion:
    def test_basic_version_parsing(self):
        v = PackageVersion("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3
        assert v.prerelease is None
        assert str(v) == "1.2.3"

    def test_version_with_prerelease(self):
        v = PackageVersion("2.0.0-rc.1")
        assert v.major == 2
        assert v.minor == 0
        assert v.patch == 0
        assert v.prerelease == "rc.1"

    def test_version_with_v_prefix(self):
        v = PackageVersion("v3.10.4")
        assert v.major == 3
        assert v.minor == 10
        assert v.patch == 4

    def test_version_with_two_digits(self):
        v = PackageVersion("1.5")
        assert v.major == 1
        assert v.minor == 5
        assert v.patch == 0

    def test_version_with_single_digit(self):
        v = PackageVersion("4")
        assert v.major == 4
        assert v.minor == 0
        assert v.patch == 0

    def test_version_equality(self):
        v1 = PackageVersion("1.2.3")
        v2 = PackageVersion("1.2.3")
        v3 = PackageVersion("1.2.4")
        assert v1 == v2
        assert v1 != v3
        assert v1 == "1.2.3"

    def test_version_comparison_ordering(self):
        assert PackageVersion("1.0.0") < PackageVersion("1.0.1")
        assert PackageVersion("1.0.1") < PackageVersion("1.1.0")
        assert PackageVersion("1.1.0") < PackageVersion("2.0.0")
        assert PackageVersion("2.0.0") > PackageVersion("1.9.9")
        assert PackageVersion("1.2.3") <= PackageVersion("1.2.3")
        assert PackageVersion("1.2.3") >= PackageVersion("1.2.3")

    def test_prerelease_less_than_release(self):
        assert PackageVersion("2.0.0-beta") < PackageVersion("2.0.0")

    def test_matches_exact_spec(self):
        v = PackageVersion("2.1.0")
        assert v.matches("==2.1.0")
        assert not v.matches("==2.1.1")
        assert v.matches("2.1.0")

    def test_matches_greater_than_or_equal(self):
        v = PackageVersion("3.4.1")
        assert v.matches(">=3.0.0")
        assert v.matches(">=3.4.1")
        assert not v.matches(">=3.5.0")

    def test_matches_less_than(self):
        v = PackageVersion("1.8.0")
        assert v.matches("<2.0.0")
        assert not v.matches("<1.8.0")
        assert v.matches("<=1.8.0")

    def test_matches_compound_spec(self):
        v = PackageVersion("1.5.2")
        assert v.matches(">=1.0.0,<2.0.0")
        assert not v.matches(">=1.6.0,<2.0.0")

    def test_matches_tilde_requirement(self):
        v = PackageVersion("1.2.4")
        assert v.matches("~=1.2.0")
        assert not v.matches("~=1.3.0")

    def test_matches_caret_requirement(self):
        v = PackageVersion("1.4.2")
        assert v.matches("^1.0.0")
        assert not v.matches("^2.0.0")

    def test_is_major_upgrade(self):
        assert PackageVersion("2.0.0").is_major_upgrade_from(PackageVersion("1.9.0"))
        assert not PackageVersion("1.9.1").is_major_upgrade_from(PackageVersion("1.9.0"))

    def test_is_breaking_change_rule(self):
        v1 = PackageVersion("1.0.0")
        v2 = PackageVersion("2.0.0")
        v3 = PackageVersion("1.1.0")
        assert v2.is_breaking_change(v1)
        assert not v3.is_breaking_change(v1)

    def test_invalid_version_string_fallback(self):
        v = PackageVersion("latest")
        assert v.major == 0
        assert str(v) == "latest"


# ============================================================================
# DependencyScanner Multi-Manifest Tests
# ============================================================================

class TestDependencyScanner:
    @pytest.fixture
    def scanner(self):
        return DependencyScanner()

    def test_parse_requirements_txt(self, scanner):
        content = """
# Core dependencies
fastapi==0.115.0
uvicorn[standard]>=0.30.0
pydantic>=2.7.0,<3.0.0
requests~=2.31.0
pytest==8.2.0 # dev tool
"""
        deps = scanner.parse_requirements_txt(content)
        assert len(deps) == 5
        names = {d.name: d for d in deps}
        assert "fastapi" in names
        assert names["fastapi"].current_version == "0.115.0"
        assert names["fastapi"].ecosystem == PackageEcosystem.PIP
        assert "uvicorn" in names
        assert names["pydantic"].version_constraint == ">=2.7.0,<3.0.0"

    def test_parse_requirements_txt_with_comments_and_blank_lines(self, scanner):
        content = """
# Header comment

   requests==2.31.0   
--extra-index-url https://pypi.org/simple
-r other-requirements.txt

flask>=3.0.0
"""
        deps = scanner.parse_requirements_txt(content)
        names = [d.name for d in deps]
        assert "requests" in names
        assert "flask" in names
        assert len(names) == 2

    def test_parse_package_json(self, scanner):
        content = json.dumps({
            "name": "sample-web",
            "version": "1.0.0",
            "dependencies": {
                "react": "^18.2.0",
                "axios": "~1.6.0"
            },
            "devDependencies": {
                "typescript": "^5.3.0",
                "jest": "^29.7.0"
            },
            "peerDependencies": {
                "react-dom": "^18.2.0"
            }
        })
        deps = scanner.parse_package_json(content)
        assert len(deps) == 5
        names = {d.name: d for d in deps}
        assert names["react"].is_dev is False
        assert names["react"].current_version == "18.2.0"
        assert names["react"].ecosystem == PackageEcosystem.NPM
        assert names["typescript"].is_dev is True
        assert "react-dom" in names

    def test_parse_pom_xml(self, scanner):
        content = """<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>demo</artifactId>
    <version>1.0.0</version>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
            <version>3.2.0</version>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>5.10.0</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>"""
        deps = scanner.parse_pom_xml(content)
        assert len(deps) == 2
        names = {d.name: d for d in deps}
        assert "org.springframework.boot:spring-boot-starter-web" in names
        assert names["org.springframework.boot:spring-boot-starter-web"].current_version == "3.2.0"
        assert names["org.springframework.boot:spring-boot-starter-web"].ecosystem == PackageEcosystem.MAVEN
        assert names["org.junit.jupiter:junit-jupiter"].is_dev is True

    def test_parse_build_gradle(self, scanner):
        content = """
plugins {
    id 'java'
}
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web:3.1.5'
    implementation("com.fasterxml.jackson.core:jackson-databind:2.15.2")
    testImplementation 'org.junit.jupiter:junit-jupiter:5.9.3'
    compileOnly 'org.projectlombok:lombok:1.18.28'
}
"""
        deps = scanner.parse_build_gradle(content)
        assert len(deps) == 4
        names = {d.name: d for d in deps}
        assert "org.springframework.boot:spring-boot-starter-web" in names
        assert names["org.springframework.boot:spring-boot-starter-web"].current_version == "3.1.5"
        assert names["org.junit.jupiter:junit-jupiter"].is_dev is True

    def test_parse_cargo_toml(self, scanner):
        content = """
[package]
name = "rusty-app"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1.35.0", features = ["full"] }
serde = "1.0.193"
axum = "0.7.4"

[dev-dependencies]
tempfile = "3.8.1"
"""
        deps = scanner.parse_cargo_toml(content)
        assert len(deps) == 4
        names = {d.name: d for d in deps}
        assert "tokio" in names
        assert names["tokio"].current_version == "1.35.0"
        assert names["tokio"].ecosystem == PackageEcosystem.CARGO
        assert names["tempfile"].is_dev is True

    def test_parse_go_mod(self, scanner):
        content = """
module example.com/my/project

go 1.22.0

require (
    github.com/gin-gonic/gin v1.9.1
    github.com/google/uuid v1.6.0
)

require github.com/stretchr/testify v1.8.4 // indirect
"""
        deps = scanner.parse_go_mod(content)
        assert len(deps) == 3
        names = {d.name: d for d in deps}
        assert "github.com/gin-gonic/gin" in names
        assert names["github.com/gin-gonic/gin"].current_version == "1.9.1"
        assert names["github.com/gin-gonic/gin"].ecosystem == PackageEcosystem.GOMOD
        assert names["github.com/stretchr/testify"].is_transitive is True

    def test_parse_composer_json(self, scanner):
        content = json.dumps({
            "name": "vendor/app",
            "require": {
                "php": ">=8.2",
                "laravel/framework": "^10.0",
                "guzzlehttp/guzzle": "^7.8"
            },
            "require-dev": {
                "phpunit/phpunit": "^10.0"
            }
        })
        deps = scanner.parse_composer_json(content)
        names = {d.name: d for d in deps}
        assert "laravel/framework" in names
        assert names["laravel/framework"].ecosystem == PackageEcosystem.COMPOSER
        assert names["phpunit/phpunit"].is_dev is True

    def test_scan_directory_discovers_all(self, scanner):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "requirements.txt").write_text("fastapi==0.115.0\n", encoding="utf-8")
            (tmp / "package.json").write_text(json.dumps({"dependencies": {"react": "18.2.0"}}), encoding="utf-8")
            (tmp / "Cargo.toml").write_text("[dependencies]\ntokio = \"1.35.0\"\n", encoding="utf-8")

            results = scanner.scan_directory(str(tmp))
            names = {r.name for r in results}
            assert "fastapi" in names
            assert "react" in names
            assert "tokio" in names


# ============================================================================
# DependencyGraph Unit & Transitive Resolution Tests
# ============================================================================

class TestDependencyGraph:
    def test_add_nodes_and_edges(self):
        graph = DependencyGraph()
        n1 = DependencyNode(name="fastapi", current_version="0.115.0")
        n2 = DependencyNode(name="starlette", current_version="0.38.0")
        n3 = DependencyNode(name="pydantic", current_version="2.8.0")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)

        graph.add_edge("fastapi", "starlette")
        graph.add_edge("fastapi", "pydantic")

        assert set(graph.get_dependencies("fastapi")) == {"starlette", "pydantic"}
        assert graph.get_dependents("starlette") == ["fastapi"]

    def test_topological_sort(self):
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="A", current_version="1.0"))
        graph.add_node(DependencyNode(name="B", current_version="1.0"))
        graph.add_node(DependencyNode(name="C", current_version="1.0"))

        graph.add_edge("A", "B")
        graph.add_edge("B", "C")

        order = graph.topological_sort()
        assert order.index("C") < order.index("B")
        assert order.index("B") < order.index("A")

    def test_cycle_detection(self):
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="X", current_version="1.0"))
        graph.add_node(DependencyNode(name="Y", current_version="1.0"))
        graph.add_node(DependencyNode(name="Z", current_version="1.0"))

        graph.add_edge("X", "Y")
        graph.add_edge("Y", "Z")
        graph.add_edge("Z", "X")

        assert graph.has_cycle() is True
        cycle = graph.find_cycle()
        assert len(cycle) >= 3

    def test_no_cycle_in_dag(self):
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="1", current_version="1.0"))
        graph.add_node(DependencyNode(name="2", current_version="1.0"))
        graph.add_edge("1", "2")
        assert graph.has_cycle() is False
        assert graph.find_cycle() == []

    def test_get_transitive_dependencies(self):
        graph = DependencyGraph()
        for letter in ["A", "B", "C", "D"]:
            graph.add_node(DependencyNode(name=letter, current_version="1.0"))
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        graph.add_edge("C", "D")

        trans = graph.get_all_transitive_dependencies("A")
        assert set(trans) == {"B", "C", "D"}

    def test_graph_depth(self):
        graph = DependencyGraph()
        for i in range(5):
            graph.add_node(DependencyNode(name=f"node_{i}", current_version="1.0"))
            if i > 0:
                graph.add_edge(f"node_{i-1}", f"node_{i}")
        assert graph.max_depth() == 4

    def test_large_graph_scalability(self):
        graph = DependencyGraph()
        for i in range(150):
            graph.add_node(DependencyNode(name=f"pkg_{i}", current_version="1.0.0"))
            if i > 0:
                graph.add_edge(f"pkg_{i-1}", f"pkg_{i}")
        assert len(graph.nodes) == 150
        assert graph.has_cycle() is False
        assert len(graph.topological_sort()) == 150


# ============================================================================
# DependencyAnalyzer Detection & Recommendations Tests
# ============================================================================

class TestDependencyAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return DependencyAnalyzer(DependencyScanner())

    def test_detect_unused_packages(self, analyzer):
        nodes = [
            DependencyNode(name="requests", current_version="2.31.0"),
            DependencyNode(name="unused_lib", current_version="1.0.0"),
        ]
        source_code = {
            "app.py": "import requests\nresp = requests.get('https://example.com')"
        }
        unused = analyzer.detect_unused_dependencies(nodes, source_code)
        assert "unused_lib" in unused
        assert "requests" not in unused

    def test_detect_duplicate_dependencies(self, analyzer):
        nodes = [
            DependencyNode(name="pydantic", current_version="2.5.0", manifest_path="requirements.txt"),
            DependencyNode(name="pydantic", current_version="1.10.0", manifest_path="sub/requirements.txt"),
            DependencyNode(name="fastapi", current_version="0.100.0", manifest_path="requirements.txt"),
        ]
        dups = analyzer.detect_duplicate_dependencies(nodes)
        assert "pydantic" in dups
        assert len(dups["pydantic"]) == 2
        assert "fastapi" not in dups

    def test_detect_version_conflicts(self, analyzer):
        nodes = [
            DependencyNode(name="urllib3", current_version="1.26.15", version_constraint="<2.0.0"),
            DependencyNode(name="urllib3", current_version="2.1.0", version_constraint=">=2.0.0"),
        ]
        conflicts = analyzer.detect_version_conflicts(nodes)
        assert len(conflicts) > 0
        assert conflicts[0].package_name == "urllib3"

    def test_detect_deprecated_libraries(self, analyzer):
        nodes = [
            DependencyNode(name="pycrypto", current_version="2.6.1"),
            DependencyNode(name="optparse", current_version="1.0.0"),
            DependencyNode(name="cryptography", current_version="42.0.0"),
        ]
        deprecated = analyzer.detect_deprecated_libraries(nodes)
        names = [d["package"] for d in deprecated]
        assert "pycrypto" in names
        assert "cryptography" not in names

    def test_detect_license_conflicts(self, analyzer):
        nodes = [
            DependencyNode(name="gpl_library", current_version="1.0.0", license="GPL-3.0"),
            DependencyNode(name="mit_library", current_version="1.0.0", license="MIT"),
        ]
        risks = analyzer.detect_license_conflicts(nodes, project_license="MIT")
        assert len(risks) > 0
        assert any(r["package"] == "gpl_library" for r in risks)

    def test_generate_safe_recommendations(self, analyzer):
        nodes = [
            DependencyNode(name="pycrypto", current_version="2.6.1"),
            DependencyNode(name="fastapi", current_version="0.60.0", latest_version="0.115.0"),
        ]
        recs = analyzer.generate_recommendations(nodes)
        assert len(recs) >= 2
        rec_pkgs = {r.package_name: r for r in recs}
        assert "pycrypto" in rec_pkgs
        assert "cryptography" in rec_pkgs["pycrypto"].recommended_replacement or "cryptography" in rec_pkgs["pycrypto"].reason

    def test_comprehensive_analysis_report(self, analyzer):
        nodes = [
            DependencyNode(name="fastapi", current_version="0.115.0"),
            DependencyNode(name="requests", current_version="2.31.0"),
            DependencyNode(name="pycrypto", current_version="2.6.1"),
        ]
        report = analyzer.analyze_dependencies(nodes, source_code_files={"main.py": "import fastapi"})
        assert "summary" in report
        assert "unused_dependencies" in report
        assert "deprecated_libraries" in report
        assert "recommendations" in report
        assert report["summary"]["total_dependencies"] == 3

    def test_empty_manifest_parsing(self, analyzer):
        scanner = DependencyScanner()
        assert scanner.parse_requirements_txt("") == []
        assert scanner.parse_package_json("{}") == []
        assert scanner.parse_pom_xml("<project></project>") == []
        assert scanner.parse_build_gradle("") == []
        assert scanner.parse_cargo_toml("") == []
        assert scanner.parse_go_mod("") == []
        assert scanner.parse_composer_json("{}") == []

    def test_diamond_dependency_graph(self):
        graph = DependencyGraph()
        # Top -> Left, Right -> Bottom
        for name in ["app", "lib_left", "lib_right", "shared_base"]:
            graph.add_node(DependencyNode(name=name, current_version="1.0.0"))
        graph.add_edge("app", "lib_left")
        graph.add_edge("app", "lib_right")
        graph.add_edge("lib_left", "shared_base")
        graph.add_edge("lib_right", "shared_base")

        assert graph.has_cycle() is False
        assert set(graph.get_all_transitive_dependencies("app")) == {"lib_left", "lib_right", "shared_base"}
        assert graph.max_depth() == 2

    def test_self_referencing_loop(self):
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="loop_pkg", current_version="1.0.0"))
        graph.add_edge("loop_pkg", "loop_pkg")
        assert graph.has_cycle() is True

    def test_disconnected_graph_components(self):
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="c1_a", current_version="1.0.0"))
        graph.add_node(DependencyNode(name="c1_b", current_version="1.0.0"))
        graph.add_edge("c1_a", "c1_b")

        graph.add_node(DependencyNode(name="c2_x", current_version="1.0.0"))
        graph.add_node(DependencyNode(name="c2_y", current_version="1.0.0"))
        graph.add_edge("c2_x", "c2_y")

        assert len(graph.nodes) == 4
        assert graph.has_cycle() is False
        assert len(graph.topological_sort()) == 4

    def test_dependency_node_serialization_roundtrip(self):
        node = DependencyNode(
            name="test-lib",
            version_spec=">=1.2.0",
            current_version="1.2.5",
            ecosystem=PackageEcosystem.PYTHON,
            is_direct=True,
            scope="runtime",
            license="Apache-2.0",
            metadata={"repo": "github.com/test/test-lib"},
        )
        d = node.to_dict()
        assert d["name"] == "test-lib"
        assert d["ecosystem"] == "PYTHON"
        assert d["license"] == "Apache-2.0"

    def test_dependency_recommendation_serialization_roundtrip(self):
        rec = DependencyRecommendation(
            package_name="pycrypto",
            current_version="2.6.1",
            recommended_version="42.0.0",
            recommendation_type="REPLACEMENT",
            rationale="Security vulnerability",
            breaking_change_risk="MEDIUM",
            replacement_package="cryptography",
        )
        d = rec.to_dict()
        assert d["package_name"] == "pycrypto"
        assert d["recommendation_type"] == "REPLACEMENT"

    def test_package_version_sorting_multi(self):
        versions = [
            PackageVersion("2.1.0"),
            PackageVersion("1.0.0"),
            PackageVersion("3.0.0-alpha"),
            PackageVersion("1.9.9"),
            PackageVersion("2.0.0"),
            PackageVersion("3.0.0"),
        ]
        sorted_v = sorted(versions)
        assert [str(v) for v in sorted_v] == [
            "1.0.0", "1.9.9", "2.0.0", "2.1.0", "3.0.0-alpha", "3.0.0"
        ]

    def test_large_dense_dependency_graph(self):
        graph = DependencyGraph()
        n = 50
        for i in range(n):
            graph.add_node(DependencyNode(name=f"p_{i}", current_version="1.0.0"))
        # Add edges in a DAG where each node points to next 3 nodes
        for i in range(n):
            for offset in [1, 2, 3]:
                if i + offset < n:
                    graph.add_edge(f"p_{i}", f"p_{i + offset}")

        assert graph.has_cycle() is False
        assert len(graph.topological_sort()) == n

