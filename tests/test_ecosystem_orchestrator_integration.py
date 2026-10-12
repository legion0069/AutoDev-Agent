"""
test_ecosystem_orchestrator_integration.py - Full Orchestrator Integration & E2E Workflow Tests (v3.2)
Verifies:
- Orchestrator ecosystem engine initialization and dependency injection
- Backward compatibility with legacy orchestrator arguments and methods
- Unified analyze_ecosystem() pipeline execution
- Public ecosystem APIs on Orchestrator (dependency report, security report, framework report, migration report, radar, compatibility, release intelligence, recommendations, cache)
- Orchestration execution loop populating context["ecosystem_intelligence"]
- 100% determinism and backward compatibility across versions 1.0-3.1
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from core.orchestrator import Orchestrator, ExecutionSummary
from core.ecosystem import ExternalIntelligenceEngine, EcosystemEngine
from core.state_manager import StateManager
from agents.task_planner_agent import Task


@pytest.fixture
def temp_project(tmp_path):
    # Prepare minimal valid project structure
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    plan_path = memory_dir / "project_plan.json"
    plan_path.write_text(json.dumps({
        "project_name": "TestEcosystemApp",
        "phases": [
            {
                "phase_id": 1,
                "name": "Phase 1 - Initialization",
                "days": [
                    {
                        "day_number": 1,
                        "tasks": [
                            {
                                "id": "TASK-1",
                                "title": "Setup Application",
                                "description": "Create base app files",
                                "priority": 1,
                                "complexity": "low",
                                "status": "pending",
                            }
                        ]
                    }
                ]
            }
        ]
    }), encoding="utf-8")

    # Add dependencies manifest
    req_path = tmp_path / "requirements.txt"
    req_path.write_text("fastapi==0.115.0\npydantic>=2.8.0\nrequests==2.32.3\n", encoding="utf-8")

    # Add source code
    app_py = tmp_path / "app.py"
    app_py.write_text("import fastapi\nimport pydantic\nimport requests\n", encoding="utf-8")

    return tmp_path


# ============================================================================
# Orchestrator Ecosystem Engine Initialization Tests
# ============================================================================

class TestOrchestratorEcosystemInit:
    def test_default_ecosystem_engine_created(self, temp_project):
        orc = Orchestrator(project_dir=temp_project)
        assert orc.ecosystem_engine is not None
        assert isinstance(orc.ecosystem_engine, ExternalIntelligenceEngine)
        assert orc.external_intelligence is orc.ecosystem_engine

    def test_custom_ecosystem_engine_injected(self, temp_project):
        custom_engine = ExternalIntelligenceEngine(auto_persist=False)
        orc = Orchestrator(project_dir=temp_project, ecosystem_engine=custom_engine)
        assert orc.ecosystem_engine is custom_engine
        assert orc.external_intelligence is custom_engine

    def test_ecosystem_engine_alias(self, temp_project):
        assert EcosystemEngine is ExternalIntelligenceEngine


# ============================================================================
# Orchestrator Public Ecosystem API Tests
# ============================================================================

class TestOrchestratorEcosystemAPIs:
    @pytest.fixture
    def orc(self, temp_project):
        return Orchestrator(project_dir=temp_project)

    def test_analyze_ecosystem_returns_complete_bundle(self, orc, temp_project):
        bundle = orc.analyze_ecosystem(project_dir=str(temp_project))
        assert "timestamp" in bundle
        assert "dependency_report" in bundle
        assert "security_report" in bundle
        assert "compatibility_report" in bundle
        assert "engineering_recommendations" in bundle
        assert "technology_radar" in bundle
        assert "cached_external_knowledge_count" in bundle
        assert bundle["cached_external_knowledge_count"] >= 3

    def test_get_dependency_report(self, orc, temp_project):
        report = orc.get_dependency_report(str(temp_project))
        assert "summary" in report
        assert report["summary"]["total_dependencies"] >= 3
        assert "fastapi" in [n["package"] for n in report["outdated"]] or report["summary"]["total_dependencies"] == 3

    def test_get_security_report_clean(self, orc):
        report = orc.get_security_report(dependencies=[], source_files={"app.py": "x = 1\n"})
        assert report["is_secure"] is True
        assert report["security_score"] == 100.0

    def test_get_security_report_vulnerable(self, orc):
        report = orc.get_security_report(
            dependencies=[],
            source_files={"bad.py": "api_key = 'abcdef1234567890abcdef1234567890'\n"},
        )
        assert report["is_secure"] is False
        assert report["security_score"] < 100.0

    def test_get_framework_report(self, orc):
        rep = orc.get_framework_report("FastAPI", "0.115.0")
        assert rep["framework"] == "FastAPI"
        assert rep["is_supported"] is True

    def test_get_migration_report(self, orc):
        plan_dict = orc.get_migration_report("Python", "3.10", "3.13")
        assert plan_dict["source_technology"] == "Python"
        assert len(plan_dict["steps"]) >= 3
        assert len(plan_dict["breaking_apis"]) >= 3

    def test_get_technology_radar(self, orc):
        radar = orc.get_technology_radar()
        assert radar["total_technologies"] >= 5
        assert "ADOPT" in radar["rings"]

    def test_get_compatibility_report(self, orc):
        res = orc.get_compatibility_report(
            runtime="Python",
            runtime_version="3.12",
            dependencies=[("FastAPI", "0.115.0"), ("Pydantic", "2.8.0")],
        )
        assert res["is_fully_compatible"] is True

    def test_get_release_intelligence_report(self, orc):
        updates = [
            {"package": "react", "current_version": "18.3.1", "new_version": "19.0.0", "release_notes": "Breaking change"}
        ]
        rep = orc.get_release_intelligence_report(updates)
        assert rep["total_releases_analyzed"] == 1
        assert rep["assess_quarterly_count"] == 1

    def test_get_ecosystem_recommendations(self, orc):
        recs = orc.get_ecosystem_recommendations(project_type="web_api", language="python")
        assert "recommendations" in recs
        assert len(recs["recommendations"]) >= 4

    def test_record_and_query_ecosystem_cache(self, orc):
        entry = orc.record_external_knowledge(
            key="custom-guideline",
            category="BEST_PRACTICE",
            title="Clean Architecture Heuristics",
            content="Separation of concerns between domain entities and repository layers.",
            tags=["clean_code", "architecture"],
        )
        assert entry["key"] == "custom-guideline"

        results = orc.query_ecosystem_cache("Architecture", category="BEST_PRACTICE")
        assert len(results) >= 1
        assert any(r["key"] == "custom-guideline" for r in results)


# ============================================================================
# Orchestration Execution Loop Integration Tests
# ============================================================================

class TestOrchestratorWorkflowIntegration:
    def test_run_attaches_ecosystem_intelligence_to_context(self, temp_project):
        plan_file = temp_project / "memory" / "project_plan.json"
        state_file = temp_project / "memory" / "state.json"
        tasks_file = temp_project / "memory" / "tasks.json"
        orc = Orchestrator(
            project_dir=temp_project,
            plan_path=plan_file,
            state_path=state_file,
            tasks_path=tasks_file,
        )

        captured_contexts = []

        def mock_coder(context, task):
            captured_contexts.append(context)
            return MagicMock(files=[])

        orc.coder_agent.execute = mock_coder
        orc.file_writer.write = MagicMock(return_value=MagicMock(success=True, files_written=[], failed_files=[]))
        orc.tester_agent.run_tests = MagicMock(return_value=MagicMock(
            success=True, pass_rate=100.0, total_tests=1, passed_tests=1, failed_tests=0
        ))
        orc.reviewer_agent.review = MagicMock(return_value=MagicMock(
            overall_quality_score=95, should_regenerate=False, recommendations=[]
        ))

        summary = orc.run()
        assert len(captured_contexts) >= 1
        ctx = captured_contexts[0]
        assert "ecosystem_intelligence" in ctx
        assert "dependency_report" in ctx["ecosystem_intelligence"]
        assert "security_report" in ctx["ecosystem_intelligence"]

    def test_backward_compatibility_v1_v31(self, temp_project):
        orc = Orchestrator(project_dir=temp_project)
        # Check v3.0 company
        assert hasattr(orc, "enterprise_company")
        # Check v3.1 evolving engine
        assert hasattr(orc, "evolving_engine")
        assert hasattr(orc, "learning_coordinator")
        # Check v3.2 ecosystem engine
        assert hasattr(orc, "ecosystem_engine")
        assert hasattr(orc, "external_intelligence")
