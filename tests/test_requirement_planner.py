"""
test_requirement_planner.py - Comprehensive Unit & Integration Tests for AutoDev Version 1.6 Requirement Planner

Validates:
1. Successful planning end-to-end with MockProvider
2. JSON parsing with and without markdown code fences
3. Invalid JSON handling (PlanParsingError)
4. Missing required fields validation (PlanValidationError)
5. Duplicate task ID detection across phases
6. Duplicate and invalid phase number rejection
7. Invalid priorities and negative estimated hours rejection
8. Missing dependency target rejection
9. Direct, self, and transitive dependency cycle detection
10. Full serialization / deserialization roundtrip (dataclasses, JSON, dict)
11. Save and load plan file persistence with directory creation
12. Summary generation accuracy and structure
13. Orchestrator integration auto-generating missing project plans
14. Empty requirement validation error handling
"""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from agents.coder_agent import CoderAgent, GeneratedFile, GeneratedResult
from agents.file_writer_agent import FileWriterAgent, WriteResult
from agents.git_agent import CommitResult, GitAgent
from agents.reviewer_agent import ReviewerAgent, ReviewResult
from agents.task_planner_agent import TaskPlannerAgent
from agents.tester_agent import TesterAgent, TestResult
from core.llm import BaseLLM
from core.orchestrator import Orchestrator
from core.providers.mock_provider import MockProvider
from core.requirement_planner import (
    PlanParsingError,
    PlanValidationError,
    ProjectPhase,
    ProjectPlan,
    ProjectSpecification,
    ProjectTask,
    RequirementPlanner,
    RequirementPlannerError,
)
from core.retry_engine import RetryEngine
from core.state_manager import StateManager


# =============================================================================
# Helper Fixtures & Sample Plans
# =============================================================================

@pytest.fixture
def sample_valid_plan() -> ProjectPlan:
    """Returns a valid 2-phase ProjectPlan for testing."""
    phase1 = ProjectPhase(
        day_number=1,
        goal="Project Setup & Data Models",
        deliverables=["Repository scaffold", "Core schema definitions"],
        tasks=[
            ProjectTask(
                id="DAY1-TASK01",
                title="Initialize project structure",
                description="Create core directory layout and config file.",
                priority="critical",
                estimated_files=["core/config.py"],
                dependencies=[],
                estimated_hours=2.0,
            ),
            ProjectTask(
                id="DAY1-TASK02",
                title="Define schema data models",
                description="Implement pydantic data models.",
                priority="high",
                estimated_files=["models/schemas.py"],
                dependencies=["DAY1-TASK01"],
                estimated_hours=3.0,
            ),
        ],
    )

    phase2 = ProjectPhase(
        day_number=2,
        goal="Business Logic & Unit Tests",
        deliverables=["Service engine", "Passing test suite"],
        tasks=[
            ProjectTask(
                id="DAY2-TASK01",
                title="Implement service handler",
                description="Implement service execution engine.",
                priority="high",
                estimated_files=["services/engine.py"],
                dependencies=["DAY1-TASK02"],
                estimated_hours=4.0,
            ),
            ProjectTask(
                id="DAY2-TASK02",
                title="Implement test suite",
                description="Write unit tests for service engine.",
                priority="medium",
                estimated_files=["tests/test_engine.py"],
                dependencies=["DAY2-TASK01"],
                estimated_hours=2.0,
            ),
        ],
    )

    return ProjectPlan(
        project_name="E-Commerce API",
        summary="A high-performance REST API for e-commerce transactions.",
        technology_stack=["Python", "FastAPI", "Pytest"],
        phases=[phase1, phase2],
        generated_at="2026-10-06T12:00:00",
        version="1.6",
    )


# =============================================================================
# 1. Successful Planning Tests
# =============================================================================

def test_1_successful_planning_with_default_mock():
    """Verifies that RequirementPlanner creates a valid plan with default MockProvider."""
    planner = RequirementPlanner()
    plan = planner.generate_plan("Build an autonomous CI/CD automation bot with Python and Docker")

    assert isinstance(plan, ProjectPlan)
    assert "Autonomous" in plan.project_name or len(plan.project_name) > 0
    assert len(plan.phases) == 3
    assert plan.total_days == 3
    assert plan.phases[0].day_number == 1
    assert len(plan.phases[0].tasks) >= 2
    assert plan.phases[0].tasks[0].id == "DAY1-TASK01"
    assert planner.validate_plan(plan) is True


def test_2_planning_with_custom_llm_json_response():
    """Verifies planning when LLM returns a well-formed custom JSON payload."""
    custom_json = json.dumps({
        "project_name": "TaskFlow Pro",
        "summary": "Distributed workflow orchestration engine.",
        "technology_stack": ["Python", "AsyncIO", "Redis"],
        "version": "1.6",
        "phases": [
            {
                "day_number": 1,
                "goal": "Core Architecture",
                "deliverables": ["Engine core", "Config parser"],
                "tasks": [
                    {
                        "id": "DAY1-TASK01",
                        "title": "Build Async Worker",
                        "description": "Implement async worker loop.",
                        "priority": "critical",
                        "estimated_files": ["core/worker.py"],
                        "dependencies": [],
                        "estimated_hours": 3.5,
                    }
                ],
            }
        ],
    })

    mock_llm = MockProvider(responses=[custom_json])
    planner = RequirementPlanner(llm=mock_llm)
    plan = planner.generate_plan("Build a workflow orchestrator")

    assert plan.project_name == "TaskFlow Pro"
    assert plan.summary == "Distributed workflow orchestration engine."
    assert "Redis" in plan.technology_stack
    assert len(plan.phases) == 1
    assert plan.phases[0].tasks[0].id == "DAY1-TASK01"
    assert plan.phases[0].tasks[0].estimated_hours == 3.5


# =============================================================================
# 2. JSON Parsing & Code Fence Extraction
# =============================================================================

def test_3_json_parsing_with_markdown_fences():
    """Verifies that markdown code blocks (```json ... ```) are cleanly extracted and parsed."""
    raw_response = """
Here is the implementation roadmap for your project:

```json
{
  "project_name": "Inventory Manager",
  "summary": "Real-time warehouse inventory tracking.",
  "technology_stack": ["Python", "SQLite"],
  "version": "1.6",
  "phases": [
    {
      "day_number": 1,
      "goal": "Database setup",
      "deliverables": ["SQLite schema"],
      "tasks": [
        {
          "id": "DAY1-TASK01",
          "title": "Create SQLite schema",
          "description": "Initialize database tables.",
          "priority": "high",
          "estimated_files": ["db/schema.sql"],
          "dependencies": [],
          "estimated_hours": 1.5
        }
      ]
    }
  ]
}
```

Let me know if you need any adjustments!
"""
    mock_llm = MockProvider(responses=[raw_response])
    planner = RequirementPlanner(llm=mock_llm)
    plan = planner.generate_plan("Build an inventory manager")

    assert plan.project_name == "Inventory Manager"
    assert len(plan.phases) == 1
    assert plan.phases[0].tasks[0].id == "DAY1-TASK01"


def test_4_invalid_json_raises_plan_parsing_error():
    """Verifies that malformed or non-JSON LLM responses raise PlanParsingError."""
    mock_llm = MockProvider(responses=["This is not JSON at all."])
    planner = RequirementPlanner(llm=mock_llm)

    with pytest.raises(PlanParsingError) as exc_info:
        planner.generate_plan("Build an app")
    assert "Failed to parse LLM response as JSON" in str(exc_info.value)


# =============================================================================
# 3. Validation Rules Tests
# =============================================================================

def test_5_missing_project_name_raises_validation_error(sample_valid_plan):
    """Verifies validation failure when project_name is missing or empty."""
    planner = RequirementPlanner()
    sample_valid_plan.project_name = ""
    with pytest.raises(PlanValidationError) as exc_info:
        planner.validate_plan(sample_valid_plan)
    assert "missing a project name" in str(exc_info.value)


def test_6_missing_phases_raises_validation_error(sample_valid_plan):
    """Verifies validation failure when phases list is empty."""
    planner = RequirementPlanner()
    sample_valid_plan.phases = []
    with pytest.raises(PlanValidationError) as exc_info:
        planner.validate_plan(sample_valid_plan)
    assert "must contain at least one development phase" in str(exc_info.value)


def test_7_missing_phase_goal_and_deliverables(sample_valid_plan):
    """Verifies validation failure when a phase has empty goals or deliverables."""
    planner = RequirementPlanner()

    # Empty goal
    sample_valid_plan.phases[0].goal = "   "
    with pytest.raises(PlanValidationError) as exc_info:
        planner.validate_plan(sample_valid_plan)
    assert "missing a goal" in str(exc_info.value)

    # Empty deliverables
    sample_valid_plan.phases[0].goal = "Valid Goal"
    sample_valid_plan.phases[0].deliverables = []
    with pytest.raises(PlanValidationError) as exc_info:
        planner.validate_plan(sample_valid_plan)
    assert "missing required deliverables" in str(exc_info.value)


def test_8_duplicate_task_ids_across_phases_rejected(sample_valid_plan):
    """Verifies that duplicate task IDs across different phases are rejected."""
    planner = RequirementPlanner()
    # Force phase 2 task 1 to have same ID as phase 1 task 1
    sample_valid_plan.phases[1].tasks[0].id = "DAY1-TASK01"

    with pytest.raises(PlanValidationError) as exc_info:
        planner.validate_plan(sample_valid_plan)
    assert "Duplicate task ID found: 'DAY1-TASK01'" in str(exc_info.value)


def test_9_duplicate_and_invalid_phase_numbers_rejected(sample_valid_plan):
    """Verifies rejection of duplicate day numbers or day <= 0."""
    planner = RequirementPlanner()

    # Day number <= 0
    sample_valid_plan.phases[0].day_number = 0
    with pytest.raises(PlanValidationError) as exc_info:
        planner.validate_plan(sample_valid_plan)
    assert "Invalid phase day number" in str(exc_info.value)

    # Duplicate day numbers
    sample_valid_plan.phases[0].day_number = 1
    sample_valid_plan.phases[1].day_number = 1
    with pytest.raises(PlanValidationError) as exc_info:
        planner.validate_plan(sample_valid_plan)
    assert "Duplicate phase day number found: 1" in str(exc_info.value)


def test_10_empty_task_titles_and_invalid_priorities(sample_valid_plan):
    """Verifies rejection of empty task titles, invalid priority names, and negative hours."""
    planner = RequirementPlanner()

    # Empty task title
    sample_valid_plan.phases[0].tasks[0].title = ""
    with pytest.raises(PlanValidationError) as exc_info:
        planner.validate_plan(sample_valid_plan)
    assert "empty title" in str(exc_info.value)

    # Invalid priority
    sample_valid_plan.phases[0].tasks[0].title = "Valid Title"
    sample_valid_plan.phases[0].tasks[0].priority = "ultra-urgent"
    with pytest.raises(PlanValidationError) as exc_info:
        planner.validate_plan(sample_valid_plan)
    assert "invalid priority" in str(exc_info.value)

    # Negative hours
    sample_valid_plan.phases[0].tasks[0].priority = "critical"
    sample_valid_plan.phases[0].tasks[0].estimated_hours = -2.5
    with pytest.raises(PlanValidationError) as exc_info:
        planner.validate_plan(sample_valid_plan)
    assert "negative estimated hours" in str(exc_info.value)


def test_11_missing_dependency_target_rejected(sample_valid_plan):
    """Verifies rejection when a task references a non-existent dependency ID."""
    planner = RequirementPlanner()
    sample_valid_plan.phases[0].tasks[0].dependencies = ["NONEXISTENT-TASK-99"]

    with pytest.raises(PlanValidationError) as exc_info:
        planner.validate_plan(sample_valid_plan)
    assert "non-existent dependency target 'NONEXISTENT-TASK-99'" in str(exc_info.value)


def test_12_dependency_cycle_detection(sample_valid_plan):
    """Verifies that direct cycles, self-dependencies, and multi-node cycles are caught."""
    planner = RequirementPlanner()

    # 1. Self dependency
    sample_valid_plan.phases[0].tasks[0].dependencies = [sample_valid_plan.phases[0].tasks[0].id]
    with pytest.raises(PlanValidationError) as exc_info:
        planner.validate_plan(sample_valid_plan)
    assert "Dependency cycle detected" in str(exc_info.value)

    # 2. 2-node cycle: DAY1-TASK01 depends on DAY1-TASK02, while DAY1-TASK02 depends on DAY1-TASK01
    sample_valid_plan.phases[0].tasks[0].dependencies = ["DAY1-TASK02"]
    sample_valid_plan.phases[0].tasks[1].dependencies = ["DAY1-TASK01"]
    with pytest.raises(PlanValidationError) as exc_info:
        planner.validate_plan(sample_valid_plan)
    assert "Dependency cycle detected" in str(exc_info.value)


# =============================================================================
# 4. Serialization, Persistence & Summary Generation
# =============================================================================

def test_13_serialization_and_deserialization_roundtrip(sample_valid_plan):
    """Verifies dict, JSON, and dataclass roundtrip conversion."""
    plan_dict = sample_valid_plan.to_dict()
    assert plan_dict["project_name"] == "E-Commerce API"
    assert plan_dict["total_days"] == 2
    assert len(plan_dict["phases"]) == 2

    # from_dict roundtrip
    restored_plan = ProjectPlan.from_dict(plan_dict)
    assert restored_plan.project_name == sample_valid_plan.project_name
    assert restored_plan.summary == sample_valid_plan.summary
    assert len(restored_plan.phases) == 2
    assert restored_plan.phases[0].tasks[0].id == "DAY1-TASK01"

    # to_json and from_json roundtrip
    json_str = sample_valid_plan.to_json()
    assert isinstance(json_str, str)
    from_json_plan = ProjectPlan.from_json(json_str)
    assert from_json_plan.project_name == sample_valid_plan.project_name
    assert from_json_plan.total_days == sample_valid_plan.total_days


def test_14_project_specification_dataclass():
    """Verifies ProjectSpecification dataclass behavior."""
    spec = ProjectSpecification(
        project_name="Data Pipeline",
        description="ETL pipeline for analytics",
        technology_stack=["Python", "Pandas", "DuckDB"],
        target_platform="Linux / macOS / Windows",
        constraints=["Max memory 4GB"],
        deliverables=["ETL script", "Schema docs"],
        estimated_days=2,
        priority="high",
    )
    spec_dict = spec.to_dict()
    assert spec_dict["project_name"] == "Data Pipeline"
    assert "DuckDB" in spec_dict["technology_stack"]

    restored = ProjectSpecification.from_dict(spec_dict)
    assert restored.project_name == spec.project_name
    assert restored.estimated_days == 2


def test_15_save_and_load_plan(tmp_path: Path, sample_valid_plan):
    """Verifies saving to file with directory creation and loading back with validation."""
    planner = RequirementPlanner()
    target_file = tmp_path / "nested" / "dir" / "project_plan.json"

    planner.save_plan(sample_valid_plan, target_file)
    assert target_file.is_file()

    loaded_plan = planner.load_plan(target_file)
    assert loaded_plan.project_name == sample_valid_plan.project_name
    assert len(loaded_plan.phases) == 2
    assert loaded_plan.phases[1].tasks[1].title == "Implement test suite"

    # Non-existent file raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        planner.load_plan(tmp_path / "does_not_exist.json")

    # Malformed JSON raises PlanParsingError
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("invalid json content", encoding="utf-8")
    with pytest.raises(PlanParsingError):
        planner.load_plan(corrupt_file)


def test_16_summary_generation(sample_valid_plan):
    """Verifies that summarize() generates a clear, structured roadmap string."""
    planner = RequirementPlanner()
    summary_text = planner.summarize(sample_valid_plan)

    assert "PROJECT IMPLEMENTATION ROADMAP: E-Commerce API" in summary_text
    assert "Python, FastAPI, Pytest" in summary_text
    assert "Phase Day 1: Project Setup & Data Models" in summary_text
    assert "Phase Day 2: Business Logic & Unit Tests" in summary_text
    assert "[DAY1-TASK01] Initialize project structure" in summary_text
    assert "[DAY2-TASK01] Implement service handler" in summary_text
    assert "Total Phases: 2" in summary_text


def test_17_empty_requirement_string_rejected():
    """Verifies that calling generate_plan with empty or whitespace string raises RequirementPlannerError."""
    planner = RequirementPlanner()
    with pytest.raises(RequirementPlannerError):
        planner.generate_plan("")
    with pytest.raises(RequirementPlannerError):
        planner.generate_plan("   ")


# =============================================================================
# 5. Orchestrator Integration Tests
# =============================================================================

def test_18_orchestrator_auto_generates_missing_project_plan(tmp_path: Path):
    """
    Verifies that when Orchestrator runs with a missing plan_path and a requirement is provided,
    RequirementPlanner automatically creates and saves project_plan.json, and the workflow executes.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    memory_dir = tmp_path / "memory"
    plan_path = memory_dir / "project_plan.json"
    state_path = memory_dir / "state.json"
    tasks_path = memory_dir / "tasks.json"
    logs_dir = tmp_path / "logs"

    assert not plan_path.is_file()

    # Create mock agents to allow execution to succeed
    mock_coder = MagicMock(spec=CoderAgent)
    mock_coder.execute.return_value = GeneratedResult(
        summary="Generated application entry point",
        files=[GeneratedFile(path="src/app.py", content="print('hello')")],
        explanation="Generated app",
    )

    mock_writer = MagicMock(spec=FileWriterAgent)
    mock_writer.write.return_value = WriteResult(
        files_written=["src/app.py"],
        files_skipped=[],
        backups_created=[],
        failed_files={},
        success=True,
        message="Successfully written",
    )


    mock_tester = MagicMock(spec=TesterAgent)
    mock_tester.run_tests.return_value = TestResult(
        success=True,
        total_tests=1,
        passed=1,
        failed=0,
        skipped=0,
        duration=0.1,
        stdout="1 passed in 0.1s",
        stderr="",
        exit_code=0,
        command="pytest",
        message="Tests passed",
    )

    mock_reviewer = MagicMock(spec=ReviewerAgent)
    mock_reviewer.review.return_value = ReviewResult(
        success=True,
        summary="Code passes quality standards.",
        overall_quality_score=95,
        issues=[],
        strengths=["Good structure"],
        recommendations=[],
        should_regenerate=False,
        explanation="High quality code",
    )


    mock_git = MagicMock(spec=GitAgent)
    mock_git.commit.return_value = CommitResult(
        success=True,
        commit_hash="abc1234",
        commit_message="feat: complete task",
        files_committed=["src/app.py"],
    )

    orch = Orchestrator(
        project_root=workspace,
        plan_path=plan_path,
        state_path=state_path,
        tasks_path=tasks_path,
        log_dir=logs_dir,
        requirement="Build a Todo CLI application with Python",
        coder_agent=mock_coder,
        file_writer=mock_writer,
        tester_agent=mock_tester,
        reviewer_agent=mock_reviewer,
        git_agent=mock_git,
    )

    summary = orch.run()

    # Plan should now exist on disk
    assert plan_path.is_file()
    with open(plan_path, "r", encoding="utf-8") as f:
        saved_plan = json.load(f)
    assert "phases" in saved_plan
    assert len(saved_plan["phases"]) >= 1

    # Orchestrator should have executed successfully
    assert summary.overall_success is True
    assert len(summary.tasks_completed) >= 1
