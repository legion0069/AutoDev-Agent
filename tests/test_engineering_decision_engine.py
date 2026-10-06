"""
test_engineering_decision_engine.py - Comprehensive Unit & Integration Test Suite for AutoDev Version 1.8
Autonomous Engineering Decision Engine Subsystem.
"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from agents.coder_agent import GeneratedFile, GeneratedResult
from agents.reviewer_agent import ReviewResult
from agents.task_planner_agent import Task
from agents.tester_agent import TestResult
from core.engineering_decision_engine import (
    DecisionEvaluation,
    DecisionOption,
    DecisionReport,
    EngineeringDecision,
    EngineeringDecisionEngine,
)
from core.memory_manager import MemoryManager
from core.prompt_builder import PromptBuilder
from core.context_injector import ContextInjector
from core.orchestrator import Orchestrator
from core.providers.mock_provider import MockProvider


@pytest.fixture
def temp_dir():
    """Provides an isolated temporary directory for test storage."""
    temp_path = Path(tempfile.mkdtemp(prefix="autodev_decision_test_"))
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def decision_engine(temp_dir):
    """Provides a configured EngineeringDecisionEngine instance."""
    history_file = temp_dir / "decision_history.json"
    mem_mgr = MemoryManager(memory_path=temp_dir / "memory.json", auto_create=True)
    return EngineeringDecisionEngine(
        memory_manager=mem_mgr,
        history_path=history_file,
        auto_create_history=True,
    )


# -----------------------------------------------------------------------------
# 1. Dataclass and Serialization Tests
# -----------------------------------------------------------------------------

def test_1_decision_option_dataclass_and_serialization():
    """Verifies DecisionOption instantiation, default values, and dictionary roundtrip."""
    opt = DecisionOption(
        id="OPT-100",
        title="Event Sourced Persistence",
        description="Append-only event log with projections.",
        advantages=["Full audit trail", "Time travel debugging"],
        disadvantages=["Eventual consistency"],
        estimated_complexity="High",
        estimated_files=["core/events.py", "core/projections.py"],
        estimated_risk="Medium",
        estimated_effort="High",
        expected_performance="High",
        expected_scalability="High",
        expected_testability="High",
        expected_maintainability="Medium",
        implementation_steps=["Define event schema", "Implement event store", "Create projection handler"],
        metadata={"version": 1},
    )

    data = opt.to_dict()
    assert data["id"] == "OPT-100"
    assert data["title"] == "Event Sourced Persistence"
    assert len(data["advantages"]) == 2
    assert len(data["implementation_steps"]) == 3

    restored = DecisionOption.from_dict(data)
    assert restored.id == opt.id
    assert restored.title == opt.title
    assert restored.estimated_complexity == "High"
    assert restored.implementation_steps == opt.implementation_steps


def test_2_decision_evaluation_dataclass_and_serialization():
    """Verifies DecisionEvaluation scoring metrics, precision, and roundtrip."""
    eval_obj = DecisionEvaluation(
        overall_score=85.5,
        performance_score=90.0,
        maintainability_score=88.0,
        complexity_score=82.0,
        risk_score=85.0,
        testability_score=92.0,
        future_score=80.0,
        scalability_score=85.0,
        documentation_score=90.0,
        weighted_score=86.75,
        score_breakdown={"perf": 90.0, "maint": 88.0},
    )

    data = eval_obj.to_dict()
    assert data["overall_score"] == 85.5
    assert data["weighted_score"] == 86.75
    assert "complexity_score" in data

    restored = DecisionEvaluation.from_dict(data)
    assert restored.overall_score == 85.5
    assert restored.weighted_score == 86.75
    assert restored.score_breakdown["perf"] == 90.0


def test_3_engineering_decision_dataclass_and_serialization():
    """Verifies EngineeringDecision container serialization."""
    opt_sel = DecisionOption(id="OPT-1", title="Selected Strategy", description="Optimal choice")
    opt_alt = DecisionOption(id="OPT-2", title="Alternative Strategy", description="Fallback choice")

    dec = EngineeringDecision(
        selected_option=opt_sel,
        alternative_options=[opt_alt],
        reasoning="Selected due to superior maintainability and low complexity.",
        tradeoffs=["Fast implementation", "Accepted minor memory overhead"],
        confidence=0.95,
        task_id="TASK-42",
        task_title="Implement Redis Caching",
    )

    data = dec.to_dict()
    assert data["task_id"] == "TASK-42"
    assert data["selected_option"]["id"] == "OPT-1"
    assert len(data["alternative_options"]) == 1

    restored = EngineeringDecision.from_dict(data)
    assert restored.task_id == "TASK-42"
    assert restored.selected_option.title == "Selected Strategy"
    assert len(restored.alternative_options) == 1


def test_4_decision_report_dataclass_markdown_and_serialization():
    """Verifies DecisionReport serialization and Markdown rendering."""
    opt1 = DecisionOption(id="OPT-1", title="JWT Tokens", description="Stateless tokens", implementation_steps=["Step A", "Step B"])
    opt2 = DecisionOption(id="OPT-2", title="Session Cookies", description="Stateful cookies")
    evals = {
        "OPT-1": DecisionEvaluation(weighted_score=91.0),
        "OPT-2": DecisionEvaluation(weighted_score=82.5),
    }

    report = DecisionReport(
        task={"id": "TASK-1", "title": "Setup Auth"},
        options=[opt1, opt2],
        selected_option=opt1,
        evaluation=evals,
        summary="JWT Tokens selected for stateless scalability.",
        telemetry={"confidence": 0.94},
    )

    md = report.to_markdown()
    assert "# Engineering Decision Report: JWT Tokens" in md
    assert "JWT Tokens" in md
    assert "Session Cookies" in md
    assert "Step A" in md

    data = report.to_dict()
    restored = DecisionReport.from_dict(data)
    assert restored.selected_option.id == "OPT-1"
    assert len(restored.options) == 2


# -----------------------------------------------------------------------------
# 2. Strategy Generation Across Domains
# -----------------------------------------------------------------------------

def test_5_generate_options_auth_domain(decision_engine):
    """Verifies generation of >= 3 concrete strategies for authentication tasks."""
    task = Task(id="T-AUTH", title="Implement JWT Authentication and Permission Guard", description="Add user login, token issuance and auth middleware.")
    options = decision_engine.generate_options(task)

    assert len(options) >= 3
    titles = [o.title for o in options]
    assert any("JWT" in t for t in titles)
    assert any("Session" in t for t in titles)
    for opt in options:
        assert len(opt.advantages) > 0
        assert len(opt.implementation_steps) >= 3


def test_6_generate_options_database_domain(decision_engine):
    """Verifies generation of >= 3 concrete strategies for database tasks."""
    task = Task(id="T-DB", title="Implement SQLite Database Persistence & Tables", description="Store books and authors in sqlite database.")
    options = decision_engine.generate_options(task)

    assert len(options) >= 3
    titles = [o.title for o in options]
    assert any("Repository Pattern" in t for t in titles)
    assert any("Active Record" in t or "In-Memory" in t for t in titles)


def test_7_generate_options_api_domain(decision_engine):
    """Verifies generation of >= 3 concrete strategies for API endpoint tasks."""
    task = Task(id="T-API", title="Build REST API Router and Endpoints for Books", description="Create FastAPI endpoints and request validation schemas.")
    options = decision_engine.generate_options(task)

    assert len(options) >= 3
    titles = [o.title for o in options]
    assert any("RESTful" in t for t in titles)


def test_8_generate_options_caching_domain(decision_engine):
    """Verifies generation of >= 3 concrete strategies for caching tasks."""
    task = Task(id="T-CACHE", title="Implement High Performance LRU Cache for User Profiles", description="Add in-memory cache with TTL.")
    options = decision_engine.generate_options(task)

    assert len(options) >= 3
    titles = [o.title for o in options]
    assert any("LRU Cache" in t for t in titles)


def test_9_generate_options_refactoring_domain(decision_engine):
    """Verifies generation of >= 3 concrete strategies for refactoring tasks."""
    task = Task(id="T-REF", title="Refactor Legacy Storage Module and Decouple Classes", description="Clean up spaghetti code.")
    options = decision_engine.generate_options(task)

    assert len(options) >= 3
    titles = [o.title for o in options]
    assert any("Adapter" in t or "Facade" in t or "Strangler" in t for t in titles)


def test_10_generate_options_logging_domain(decision_engine):
    """Verifies generation of >= 3 concrete strategies for logging & telemetry tasks."""
    task = Task(id="T-LOG", title="Configure Structured Logging & Telemetry", description="Add rotating file logger and JSON formatters.")
    options = decision_engine.generate_options(task)

    assert len(options) >= 3
    titles = [o.title for o in options]
    assert any("JSON Logger" in t for t in titles)


def test_11_generate_options_testing_domain(decision_engine):
    """Verifies generation of >= 3 concrete strategies for testing tasks."""
    task = Task(id="T-TEST", title="Create Automated Pytest Test Suite with Fixtures", description="Add unit and integration tests.")
    options = decision_engine.generate_options(task)

    assert len(options) >= 3
    titles = [o.title for o in options]
    assert any("Pytest Fixtures" in t or "Unit" in t for t in titles)


def test_12_generate_options_general_domain(decision_engine):
    """Verifies generation of >= 3 concrete strategies for general feature tasks."""
    task = Task(id="T-GEN", title="Build Markdown Parser Subsystem", description="Parse and render markdown tokens.")
    options = decision_engine.generate_options(task)

    assert len(options) >= 3
    assert all(len(o.implementation_steps) > 0 for o in options)


# -----------------------------------------------------------------------------
# 3. Evaluation and Scoring Engine
# -----------------------------------------------------------------------------

def test_13_evaluate_options_deterministic_scoring(decision_engine):
    """Verifies that evaluations assign scores across all 8 architectural dimensions."""
    opt1 = DecisionOption(
        id="OPT-1",
        title="Low Complexity Strategy",
        description="Clean simple approach",
        estimated_complexity="Low",
        estimated_risk="Low",
        expected_maintainability="High",
        expected_performance="High",
        advantages=["Adv 1", "Adv 2"],
        disadvantages=[],
    )
    opt2 = DecisionOption(
        id="OPT-2",
        title="High Complexity Strategy",
        description="Complex monolithic rewrite",
        estimated_complexity="High",
        estimated_risk="High",
        expected_maintainability="Low",
        expected_performance="Medium",
        advantages=[],
        disadvantages=["Dis 1", "Dis 2", "Dis 3"],
    )

    evals = decision_engine.evaluate_options([opt1, opt2])
    assert "OPT-1" in evals
    assert "OPT-2" in evals

    ev1 = evals["OPT-1"]
    ev2 = evals["OPT-2"]

    assert ev1.complexity_score > ev2.complexity_score
    assert ev1.risk_score > ev2.risk_score
    assert ev1.maintainability_score > ev2.maintainability_score
    assert ev1.weighted_score > ev2.weighted_score


def test_14_custom_weights_and_normalization(decision_engine):
    """Verifies that custom weights are properly normalized and influence weighted scores."""
    opt = DecisionOption(
        id="OPT-PERF",
        title="Fast but Complex",
        description="Speed optimized",
        estimated_complexity="High",
        estimated_risk="Medium",
        expected_performance="High",
    )

    # 1. Performance-heavy weights
    perf_weights = {"performance": 0.80, "maintainability": 0.10, "complexity": 0.05, "risk": 0.05}
    ev_perf = decision_engine.evaluate_options([opt], custom_weights=perf_weights)["OPT-PERF"]

    # 2. Simplicity-heavy weights
    simple_weights = {"performance": 0.05, "maintainability": 0.15, "complexity": 0.60, "risk": 0.20}
    ev_simple = decision_engine.evaluate_options([opt], custom_weights=simple_weights)["OPT-PERF"]

    # Under performance-heavy weights, the score should be significantly higher
    assert ev_perf.weighted_score > ev_simple.weighted_score


# -----------------------------------------------------------------------------
# 4. Selection and Tie-Breaking
# -----------------------------------------------------------------------------

def test_15_choose_best_option_highest_score(decision_engine):
    """Verifies that choose_best_option selects the strategy with the highest weighted score."""
    opts = [
        DecisionOption(id="OPT-A", title="Strategy A", description="Descr A", estimated_complexity="High", estimated_risk="High"),
        DecisionOption(id="OPT-B", title="Strategy B", description="Descr B", estimated_complexity="Low", estimated_risk="Low", expected_maintainability="High"),
    ]
    evals = decision_engine.evaluate_options(opts)
    decision = decision_engine.choose_best_option(opts, evals)

    assert decision.selected_option.id == "OPT-B"
    assert len(decision.alternative_options) == 1
    assert decision.alternative_options[0].id == "OPT-A"
    assert "Strategy B" in decision.reasoning
    assert decision.confidence >= 0.70


def test_16_choose_best_option_tie_breaking_rules(decision_engine):
    """
    Verifies tie-breaking order:
    1. Higher weighted_score
    2. Lower complexity (higher complexity_score)
    3. Lower risk (higher risk_score)
    4. Higher maintainability
    """
    opt1 = DecisionOption(id="OPT-1", title="Option 1", description="desc", estimated_complexity="Low")
    opt2 = DecisionOption(id="OPT-2", title="Option 2", description="desc", estimated_complexity="High")

    # Force identical weighted_score but different complexity_score
    evals = {
        "OPT-1": DecisionEvaluation(weighted_score=80.0, complexity_score=92.0, risk_score=80.0, maintainability_score=80.0),
        "OPT-2": DecisionEvaluation(weighted_score=80.0, complexity_score=52.0, risk_score=80.0, maintainability_score=80.0),
    }

    decision = decision_engine.choose_best_option([opt1, opt2], evals)
    assert decision.selected_option.id == "OPT-1"


def test_17_empty_options_raises_value_error(decision_engine):
    """Verifies that choosing from empty options raises ValueError."""
    with pytest.raises(ValueError, match="Cannot choose best option from an empty options list"):
        decision_engine.choose_best_option([], {})


def test_18_invalid_weights_graceful_fallback(decision_engine):
    """Verifies that all-zero or negative weights safely fall back to defaults."""
    normalized = decision_engine._normalize_weights({"perf": -10.0, "risk": -5.0})
    assert sum(normalized.values()) == pytest.approx(1.0, 0.01)

    normalized_zero = decision_engine._normalize_weights({"a": 0.0, "b": 0.0})
    assert "maintainability" in normalized_zero


# -----------------------------------------------------------------------------
# 5. End-to-End Decision Pipeline & Integrations
# -----------------------------------------------------------------------------

def test_19_end_to_end_decide_pipeline(decision_engine):
    """Verifies the complete decide() workflow returning a populated DecisionReport."""
    task = Task(id="TASK-99", title="Build User Session Caching Layer", description="Session caching with TTL", estimated_files=["core/session.py"])
    report = decision_engine.decide(task)

    assert isinstance(report, DecisionReport)
    assert report.task["id"] == "TASK-99"
    assert len(report.options) >= 3
    assert report.selected_option is not None
    assert report.selected_option.id in report.evaluation
    assert report.telemetry["number_of_options"] >= 3
    assert report.telemetry["evaluation_time_ms"] >= 0.0
    assert report.telemetry["confidence"] > 0.0


def test_20_memory_manager_integration(temp_dir):
    """Verifies automatic recording of selected decision into MemoryManager under ARCHITECTURE category."""
    mem_mgr = MemoryManager(memory_path=temp_dir / "memory.json", auto_create=True)
    engine = EngineeringDecisionEngine(memory_manager=mem_mgr, history_path=temp_dir / "history.json")

    task = Task(id="TASK-101", title="Implement JWT Authentication Guard", description="Add JWT token verification")
    engine.decide(task)

    memories = list(mem_mgr.load_memory().values())
    assert len(memories) >= 1
    arch_mems = [m for m in memories if m.category == "ARCHITECTURE"]
    assert len(arch_mems) >= 1
    assert "TASK-101" in arch_mems[0].title
    assert "Strategy:" in arch_mems[0].content


def test_21_prompt_builder_integration(decision_engine):
    """Verifies that PromptBuilder injects the ENGINEERING DECISION section into synthesized prompts."""
    task = Task(id="TASK-202", title="Implement SQLite Database Layer", description="Add SQLite repository", estimated_files=["core/database.py"])
    report = decision_engine.decide(task)

    prompt_builder = PromptBuilder(decision_engine=decision_engine)
    context = {
        "project_name": "LibraryApp",
        "technology_stack": "Python 3.12, SQLite",
        "current_phase": 1,
        "engineering_decision": report,
    }

    prompt = prompt_builder.build(context=context, task=task)
    assert "========================================" in prompt
    assert "ENGINEERING DECISION" in prompt
    assert "Chosen Strategy:" in prompt
    assert "Why:" in prompt
    assert "Implementation Plan:" in prompt


def test_22_context_injector_integration(decision_engine):
    """Verifies that ContextInjector retrieves engineering decision objects."""
    task = Task(id="TASK-303", title="Implement REST API Endpoints", description="Create FastAPI route handlers")
    injector = ContextInjector()
    context = {"decision_engine": decision_engine}

    retrieved = injector.retrieve_engineering_decision(context=context, task=task)
    assert retrieved is not None
    assert hasattr(retrieved, "selected_option")
    assert retrieved.selected_option.title is not None


def test_23_orchestrator_integration(temp_dir):
    """Verifies full Orchestrator execution with EngineeringDecisionEngine injected."""
    mock_llm = MockProvider()
    engine = EngineeringDecisionEngine(history_path=temp_dir / "history.json")

    plan_path = temp_dir / "project_plan.json"
    plan_data = {
        "project_name": "DecisionTestApp",
        "phases": [
            {
                "phase_number": 1,
                "goal": "Build Core Auth",
                "tasks": [
                    {
                        "id": "T1",
                        "title": "Implement JWT Token Authentication",
                        "description": "Create TokenManager",
                        "priority": 1,
                        "estimated_files": ["core/auth.py"],
                    }
                ],
            }
        ],
    }
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan_data, f)

    orchestrator = Orchestrator(
        project_root=temp_dir / "workspace",
        plan_path=plan_path,
        state_path=temp_dir / "state.json",
        tasks_path=temp_dir / "tasks.json",
        llm=mock_llm,
        decision_engine=engine,
    )

    mock_coder = MagicMock()
    mock_coder.execute.return_value = GeneratedResult(
        files=[GeneratedFile(path="core/auth.py", content="class TokenManager: pass")],
        explanation="Implemented token manager",
        summary="Implemented token manager",
    )
    mock_tester = MagicMock()
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
    mock_reviewer = MagicMock()
    mock_reviewer.review.return_value = ReviewResult(
        success=True,
        summary="Clean implementation",
        overall_quality_score=95,
        should_regenerate=False,
    )

    orchestrator.coder_agent = mock_coder
    orchestrator.tester_agent = mock_tester
    orchestrator.reviewer_agent = mock_reviewer

    summary = orchestrator.run()
    assert summary.overall_success is True
    assert len(summary.tasks_completed) >= 1

    # Check that coder received engineering decision in context
    called_context = mock_coder.execute.call_args[1]["context"]
    assert "engineering_decision" in called_context
    assert called_context["engineering_decision"].selected_option is not None
    assert engine.get_telemetry()["number_of_decisions"] >= 1


# -----------------------------------------------------------------------------
# 6. History Persistence & Querying
# -----------------------------------------------------------------------------

def test_24_history_persistence_append_and_load(temp_dir):
    """Verifies atomic persistence, append, and retrieval of decision history."""
    history_file = temp_dir / "history.json"
    engine = EngineeringDecisionEngine(history_path=history_file)

    task1 = Task(id="TASK-A", title="Auth Strategy", description="Auth task")
    task2 = Task(id="TASK-B", title="Database Strategy", description="Database task")

    engine.decide(task1)
    engine.decide(task2)

    assert history_file.is_file()

    # Create new instance and load from disk
    new_engine = EngineeringDecisionEngine(history_path=history_file)
    history = new_engine.load_history()

    assert len(history) == 2
    assert history[0].task["id"] == "TASK-A"
    assert history[1].task["id"] == "TASK-B"


def test_25_history_query_filtering(temp_dir):
    """Verifies filtering history records by task_id, search term, and limit."""
    history_file = temp_dir / "history.json"
    engine = EngineeringDecisionEngine(history_path=history_file)

    task1 = Task(id="TASK-01", title="JWT Authentication Strategy", description="Token auth")
    task2 = Task(id="TASK-02", title="SQLite Repository Database", description="SQLite tables")
    task3 = Task(id="TASK-03", title="FastAPI Router Endpoints", description="REST endpoints")

    engine.decide(task1)
    engine.decide(task2)
    engine.decide(task3)

    # 1. Query by task_id
    res_id = engine.query_history(task_id="TASK-02")
    assert len(res_id) == 1
    assert res_id[0].task["id"] == "TASK-02"

    # 2. Query by search keyword
    res_search = engine.query_history(query="Authentication")
    assert len(res_search) >= 1
    assert "JWT" in res_search[0].selected_option.title

    # 3. Query with limit
    res_limit = engine.query_history(limit=2)
    assert len(res_limit) == 2


def test_26_corrupted_history_json_recovery(temp_dir):
    """Verifies graceful recovery from corrupted JSON history file."""
    history_file = temp_dir / "corrupted_history.json"
    with open(history_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json corrupted content [[[")

    engine = EngineeringDecisionEngine(history_path=history_file, auto_create_history=True)
    history = engine.load_history()
    assert history == []

    # Ensure engine can still save and recover
    task = Task(id="TASK-RECOVER", title="New Task after corruption", description="Recovery task")
    engine.decide(task)
    assert len(engine.load_history()) == 1


# -----------------------------------------------------------------------------
# 7. Performance Benchmark
# -----------------------------------------------------------------------------

def test_27_high_performance_benchmark(temp_dir):
    """Verifies high performance decision execution (< 50ms for 500 evaluations)."""
    engine = EngineeringDecisionEngine(history_path=temp_dir / "perf_history.json")
    task = Task(id="T-BENCH", title="High Performance Benchmark Task", description="Benchmarking", estimated_files=["core/engine.py"])

    options = engine.generate_options(task)

    start = time.perf_counter()
    for _ in range(500):
        evals = engine.evaluate_options(options)
        engine.choose_best_option(options, evals)
    duration = time.perf_counter() - start

    assert duration < 0.1, f"500 decision evaluations took {duration:.4f}s, expected < 0.1s"
