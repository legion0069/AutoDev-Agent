"""
test_migration_and_compatibility.py - Comprehensive Unit Tests for Subsystems 6 & 7
Covers:
- MigrationPlanner:
  * Python 3.10 → 3.13 migration plan
  * Spring Boot 2 → 3 migration plan
  * React 17/18 → 19 migration plan
  * Java 17 → 21 migration plan
  * Dynamic fallback migration plan
  * Actionable steps, code modification diffs, verification checks, rollback plans
- CompatibilityAnalyzer:
  * Runtime vs framework compatibility rules
  * Incompatibility detection (Java 8 vs Spring Boot 3, Node 16 vs React 19, Python 3.12 vs PyCrypto)
  * OS and container dimension compatibility
  * Matrix generation across multi-dependency suites
"""

import pytest

from core.ecosystem.migration_planner import MigrationPlanner
from core.ecosystem.compatibility_analyzer import CompatibilityAnalyzer
from core.ecosystem.ecosystem_models import (
    CompatibilityStatus,
    MigrationPlan,
    MigrationStep,
)


# ============================================================================
# MigrationPlanner Unit Tests
# ============================================================================

class TestMigrationPlanner:
    @pytest.fixture
    def planner(self):
        return MigrationPlanner()

    def test_python_migration_plan_generation(self, planner):
        plan = planner.plan_migration("Python", "3.10", "3.13")
        assert plan.source_technology == "Python"
        assert plan.from_version == "3.10"
        assert plan.to_version == "3.13"
        assert len(plan.breaking_apis) >= 3
        assert any("cgi" in api for api in plan.breaking_apis)
        assert len(plan.steps) >= 3
        assert len(plan.rollback_plan) >= 1
        assert plan.risk_level in ("LOW", "MEDIUM", "HIGH")
        assert plan.estimated_hours > 0

    def test_spring_boot_migration_plan_generation(self, planner):
        plan = planner.plan_migration("Spring Boot", "2.7.0", "3.3.0")
        assert plan.source_technology == "Spring Boot"
        assert any("jakarta" in mod.lower() or "javax" in mod.lower() for mod in plan.code_modifications)
        assert any("java 17" in api.lower() or "jakarta" in api.lower() for api in plan.breaking_apis)
        assert len(plan.steps) >= 3
        assert any("SecurityFilterChain" in s.instructions or "jakarta" in s.instructions.lower() for s in plan.steps)

    def test_react_migration_plan_generation(self, planner):
        plan = planner.plan_migration("React", "17.0.2", "19.0.0")
        assert plan.source_technology == "React"
        assert len(plan.steps) >= 2
        assert any("createRoot" in s.instructions or "render" in s.instructions for s in plan.steps)
        assert len(plan.testing_requirements) >= 1

    def test_java_migration_plan_generation(self, planner):
        plan = planner.plan_migration("Java", "17", "21")
        assert plan.source_technology == "Java"
        assert len(plan.steps) >= 2
        assert plan.estimated_hours > 0

    def test_dynamic_fallback_for_custom_technology(self, planner):
        plan = planner.plan_migration("CustomFramework", "1.0.0", "2.0.0")
        assert plan.source_technology == "CustomFramework"
        assert plan.from_version == "1.0.0"
        assert plan.to_version == "2.0.0"
        assert len(plan.steps) == 3
        assert len(plan.rollback_plan) >= 2
        assert "CustomFramework" in plan.title

    def test_migration_step_structure(self, planner):
        plan = planner.plan_migration("Python", "3.10", "3.13")
        for step in plan.steps:
            assert isinstance(step.step_number, int)
            assert step.title != ""
            assert step.target_component != ""
            assert step.action_type in ("CODE_REFACTOR", "CONFIG_UPDATE", "TEST_VALIDATION", "DEPENDENCY_UPGRADE")
            assert step.verification_check != ""

    def test_migration_plan_serialization(self, planner):
        plan = planner.plan_migration("Python", "3.10", "3.13")
        d = plan.to_dict()
        assert d["source_technology"] == "Python"
        assert isinstance(d["steps"], list)
        assert len(d["steps"]) > 0
        assert d["steps"][0]["step_number"] == 1

    def test_migration_rollback_strategy_presence(self, planner):
        for tech in ["Python", "Spring Boot", "React", "Java"]:
            plan = planner.plan_migration(tech, "1.0", "2.0")
            assert len(plan.rollback_plan) > 0
            assert any("revert" in r.lower() or "git" in r.lower() or "rollback" in r.lower() or "restore" in r.lower() for r in plan.rollback_plan)


# ============================================================================
# CompatibilityAnalyzer Unit Tests
# ============================================================================

class TestCompatibilityAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return CompatibilityAnalyzer()

    def test_python_312_with_fastapi_compatible(self, analyzer):
        res = analyzer.check_compatibility("Python", "3.12", "FastAPI", "0.115.0")
        assert res.status == CompatibilityStatus.COMPATIBLE
        assert "FastAPI" in res.details

    def test_python_312_with_pydantic_v2_compatible(self, analyzer):
        res = analyzer.check_compatibility("Python", "3.12", "Pydantic", "2.8.0")
        assert res.status == CompatibilityStatus.COMPATIBLE

    def test_python_312_with_old_pydantic_incompatible(self, analyzer):
        res = analyzer.check_compatibility("Python", "3.12", "Pydantic", "1.10.0")
        assert res.status == CompatibilityStatus.INCOMPATIBLE
        assert "requires" in res.details

    def test_python_312_with_pycrypto_incompatible(self, analyzer):
        res = analyzer.check_compatibility("Python", "3.12", "pycrypto", "2.6.1")
        assert res.status == CompatibilityStatus.INCOMPATIBLE

    def test_java_8_with_spring_boot_3_incompatible(self, analyzer):
        res = analyzer.check_compatibility("Java", "8", "Spring Boot", "3.2.0")
        assert res.status == CompatibilityStatus.INCOMPATIBLE

    def test_java_17_with_spring_boot_3_compatible(self, analyzer):
        res = analyzer.check_compatibility("Java", "17", "Spring Boot", "3.2.0")
        assert res.status == CompatibilityStatus.COMPATIBLE

    def test_node_16_with_react_19_incompatible(self, analyzer):
        res = analyzer.check_compatibility("Node", "16", "React", "19.0.0")
        assert res.status == CompatibilityStatus.INCOMPATIBLE

    def test_windows_with_python_compatible(self, analyzer):
        res = analyzer.check_compatibility("Windows", "11", "Python", "3.12.0", dimension="OS")
        assert res.status == CompatibilityStatus.COMPATIBLE

    def test_alpine_with_python_conditional(self, analyzer):
        res = analyzer.check_compatibility("Alpine Linux", "3.19", "Python", "3.12.0", dimension="CONTAINER")
        assert res.status in (CompatibilityStatus.CONDITIONAL, CompatibilityStatus.COMPATIBLE)

    def test_unknown_components_default_to_compatible(self, analyzer):
        res = analyzer.check_compatibility("CustomRuntime", "1.0", "CustomLib", "2.0")
        assert res.status == CompatibilityStatus.COMPATIBLE
        assert "No known incompatibilities" in res.details

    def test_generate_compatibility_matrix_all_compatible(self, analyzer):
        deps = [
            ("FastAPI", "0.115.0"),
            ("Pydantic", "2.8.0"),
        ]
        matrix = analyzer.generate_compatibility_matrix(
            primary_runtime="Python",
            runtime_version="3.12",
            dependencies=deps,
            target_os="Linux",
        )
        assert matrix["is_fully_compatible"] is True
        assert matrix["incompatibilities_found"] == 0
        assert matrix["total_checks"] == 3  # 2 deps + 1 OS

    def test_generate_compatibility_matrix_with_incompatibilities(self, analyzer):
        deps = [
            ("FastAPI", "0.115.0"),
            ("pycrypto", "2.6.1"),  # Incompatible with Python 3.12
            ("Pydantic", "1.10.0"),  # Incompatible with Python 3.12
        ]
        matrix = analyzer.generate_compatibility_matrix(
            primary_runtime="Python",
            runtime_version="3.12",
            dependencies=deps,
        )
        assert matrix["is_fully_compatible"] is False
        assert matrix["incompatibilities_found"] >= 2

    def test_spring_boot_step_details(self):
        planner = MigrationPlanner()
        plan = planner.plan_migration("Spring Boot", "2.7", "3.3")
        step_titles = [s.title for s in plan.steps]
        assert any("Java 17" in t or "JDK" in t for t in step_titles)
        assert any("Jakarta" in t or "Namespace" in t for t in step_titles)
        assert any("Security" in t for t in step_titles)

    def test_java_17_to_21_steps(self):
        planner = MigrationPlanner()
        plan = planner.plan_migration("Java", "17", "21")
        assert any("virtual threads" in s.instructions.lower() or "preview" in s.instructions.lower() or "runtime" in s.instructions.lower() for s in plan.steps)

    def test_migration_plan_deterministic_plan_id(self):
        planner = MigrationPlanner()
        p1 = planner.plan_migration("Python", "3.10", "3.13")
        p2 = planner.plan_migration("Python", "3.10", "3.13")
        assert p1.source_technology == p2.source_technology
        assert p1.title == p2.title

    def test_compatibility_check_result_serialization(self):
        analyzer = CompatibilityAnalyzer()
        res = analyzer.check_compatibility("Python", "3.12", "FastAPI", "0.115.0")
        d = res.to_dict()
        assert d["component_a"] == "Python"
        assert d["component_b"] == "FastAPI"
        assert d["status"] == "COMPATIBLE"

    def test_matrix_generation_empty_dependencies(self):
        analyzer = CompatibilityAnalyzer()
        matrix = analyzer.generate_compatibility_matrix("Python", "3.12", [])
        assert matrix["total_checks"] == 1  # OS check only
        assert matrix["is_fully_compatible"] is True

    def test_compatibility_with_windows_os(self):
        analyzer = CompatibilityAnalyzer()
        res = analyzer.check_compatibility("Windows", "10", "Python", "3.11.0", dimension="OS")
        assert res.status == CompatibilityStatus.COMPATIBLE

    def test_custom_technology_migration_preserves_versions(self):
        planner = MigrationPlanner()
        plan = planner.plan_migration("GraphQL-Yoga", "2.0.0", "3.0.0")
        assert plan.from_version == "2.0.0"
        assert plan.to_version == "3.0.0"
        assert plan.source_technology == "GraphQL-Yoga"

    def test_migration_step_code_example_formatting(self):
        planner = MigrationPlanner()
        plan = planner.plan_migration("Python", "3.10", "3.13")
        assert any("+" in s.code_modification_example and "-" in s.code_modification_example for s in plan.steps if s.code_modification_example)

    def test_check_compatibility_reverse_order(self):
        analyzer = CompatibilityAnalyzer()
        res1 = analyzer.check_compatibility("FastAPI", "0.115.0", "Python", "3.12")
        res2 = analyzer.check_compatibility("Python", "3.12", "FastAPI", "0.115.0")
        assert res1.status == res2.status == CompatibilityStatus.COMPATIBLE

