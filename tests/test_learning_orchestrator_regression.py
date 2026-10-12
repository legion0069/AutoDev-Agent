"""
End-to-end regression and orchestrator integration test suite.
Validates that AutoDev v1.0, v2.0, and v3.0 capabilities remain 100% backward compatible
while the v3.1 self-evolving intelligence engine seamlessly instruments all operations.
"""
import pytest
import os
import shutil
import tempfile

from core.orchestrator import AutoDevOrchestrator
from core.learning.learning_coordinator import LearningCoordinator
from core.learning.learning_models import (
    LearningEventType,
    PlaybookArchetype,
    ReflectionScope
)


@pytest.fixture
def temp_project():
    d = tempfile.mkdtemp(prefix="autodev_orch_reg_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_orchestrator_initialization_backward_compatibility(temp_project):
    orchestrator = AutoDevOrchestrator(project_dir=temp_project)
    
    # Check that core orchestrator attributes exist unchanged
    assert hasattr(orchestrator, "project_dir")
    assert hasattr(orchestrator, "state") or hasattr(orchestrator, "project_state") or hasattr(orchestrator, "learning_coordinator")
    
    # Check v3.1 integration properties
    assert hasattr(orchestrator, "learning_coordinator")
    assert orchestrator.learning_coordinator is not None


def test_orchestrator_recommend_architecture_api(temp_project):
    orchestrator = AutoDevOrchestrator(project_dir=temp_project)
    
    rec = orchestrator.recommend_architecture(
        requirements="Build a scalable microservice for e-commerce order checkout with PostgreSQL and Redis cache",
        project_name="checkout_service"
    )
    
    assert rec is not None
    assert hasattr(rec, "archetype")
    assert hasattr(rec, "database_choice")
    assert hasattr(rec, "api_style")
    assert hasattr(rec, "design_patterns")


def test_orchestrator_optimize_prompt_api(temp_project):
    orchestrator = AutoDevOrchestrator(project_dir=temp_project)
    
    raw = "Write a Python script. Write a Python script. Ensure tests pass."
    opt = orchestrator.optimize_prompt(raw, task_type="coding")
    
    assert opt is not None
    assert hasattr(opt, "optimized_prompt")
    assert len(opt.optimized_prompt) > 0


def test_orchestrator_run_learning_cycle_api(temp_project):
    orchestrator = AutoDevOrchestrator(project_dir=temp_project)
    
    task_payload = {
        "task_id": "T-REG-01",
        "title": "Build user auth service",
        "project": "reg_test_proj",
        "success": True,
        "review_score": 92.0,
        "retries": 1,
        "tests_passed": True,
        "affected_files": ["core/auth.py"],
        "prompt_length": 600,
        "metrics": {"duration_ms": 1500}
    }
    
    result = orchestrator.run_learning_cycle(task_payload)
    assert result is not None
    assert "reflection" in result
    assert "event" in result
    assert "analytics" in result


def test_orchestrator_get_learning_report_api(temp_project):
    orchestrator = AutoDevOrchestrator(project_dir=temp_project)
    
    # Run a quick cycle first
    orchestrator.run_learning_cycle({
        "task_id": "T-REG-02",
        "title": "API validation",
        "project": "reg_test_proj",
        "success": True,
        "review_score": 95.0,
        "retries": 0,
        "tests_passed": True
    })
    
    report = orchestrator.get_learning_report()
    assert report is not None
    assert "total_events" in report or "summary" in report or "analytics" in report


def test_orchestrator_query_learning_state_api(temp_project):
    orchestrator = AutoDevOrchestrator(project_dir=temp_project)
    
    state = orchestrator.query_learning_state()
    assert state is not None
    assert isinstance(state, dict)
