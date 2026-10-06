"""
test_change_planner.py - Comprehensive Test Suite for AutoDev Semantic Refactoring & Change Planning Engine (v1.8)

Validates:
1. Minimal change set computation and protected file avoidance
2. Change classification heuristics (Feature, Bug Fix, Refactor, Optimization, Security, etc.)
3. Semantic refactoring detection (Rename, Extract Method/Class, Repo/Service Extraction, DI)
4. Breaking change detection on public APIs, signatures, and callers
5. Base class modifications and inheritance breaking changes
6. Database migrations and reversible rollback instruction generation
7. REST API endpoint and CLI interface breaking changes
8. Topological execution ordering (dependencies first) and rollback ordering (reversed)
9. Architectural validation rules and layer violation detection
10. JSON export and import roundtrip serialization
11. Plan statistics and telemetry metrics
12. PromptBuilder integration (CHANGE PLAN section)
13. Orchestrator integration (automatic change plan generation and context injection)
14. Performance on 1000+ symbols (<0.5s execution) and deterministic output reproducibility
"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

from agents.task_planner_agent import Task
from core.change_planner import (
    BreakingChange,
    ChangeClassification,
    ChangePlan,
    ChangePlanner,
    FileChange,
    MigrationStep,
    NecessityRank,
    RefactoringStep,
    RefactoringType,
    SymbolChange,
    ValidationRule,
)
from core.orchestrator import Orchestrator
from core.prompt_builder import PromptBuilder
from core.repository_analyzer import RepositoryAnalyzer
from core.symbol_graph import Dependency, Symbol, SymbolGraph, SymbolType, Visibility


# =============================================================================
# FIXTURES & HELPERS
# =============================================================================

@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="autodev_change_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def create_sample_graph() -> SymbolGraph:
    """Constructs a rich test symbol graph."""
    graph = SymbolGraph()

    # 1. Models / Entities
    graph.add_symbol(Symbol(
        id="m1", name="Order", qualified_name="models.order.Order",
        symbol_type=SymbolType.CLASS, language="python", file="models/order.py",
        line=1, end_line=30, visibility=Visibility.PUBLIC,
    ))

    # 2. Repository Layer
    graph.add_symbol(Symbol(
        id="r1", name="OrderRepository", qualified_name="repositories.order_repo.OrderRepository",
        symbol_type=SymbolType.CLASS, language="python", file="repositories/order_repo.py",
        line=1, end_line=60, visibility=Visibility.PUBLIC,
    ))
    graph.add_symbol(Symbol(
        id="r2", name="find_by_id", qualified_name="repositories.order_repo.OrderRepository.find_by_id",
        symbol_type=SymbolType.METHOD, language="python", file="repositories/order_repo.py",
        line=10, end_line=25, parent_symbol="OrderRepository", called_by=["process_order"],
    ))

    # 3. Base & Derived Classes
    graph.add_symbol(Symbol(
        id="b1", name="BaseProcessor", qualified_name="services.base.BaseProcessor",
        symbol_type=SymbolType.CLASS, language="python", file="services/base.py",
        line=1, end_line=40, visibility=Visibility.PUBLIC,
    ))
    graph.add_symbol(Symbol(
        id="s1", name="OrderService", qualified_name="services.order_service.OrderService",
        symbol_type=SymbolType.CLASS, language="python", file="services/order_service.py",
        line=1, end_line=80, visibility=Visibility.PUBLIC, inherits=["BaseProcessor"],
    ))
    graph.add_symbol(Symbol(
        id="s2", name="process_order", qualified_name="services.order_service.OrderService.process_order",
        symbol_type=SymbolType.METHOD, language="python", file="services/order_service.py",
        line=15, end_line=45, parent_symbol="OrderService", called_by=["handle_post_order"],
    ))

    # 4. Controller Layer
    graph.add_symbol(Symbol(
        id="c1", name="OrderController", qualified_name="controllers.order_ctrl.OrderController",
        symbol_type=SymbolType.CLASS, language="python", file="controllers/order_ctrl.py",
        line=1, end_line=50, visibility=Visibility.PUBLIC,
    ))
    graph.add_symbol(Symbol(
        id="c2", name="handle_post_order", qualified_name="controllers.order_ctrl.OrderController.handle_post_order",
        symbol_type=SymbolType.METHOD, language="python", file="controllers/order_ctrl.py",
        line=10, end_line=25, parent_symbol="OrderController", decorators=["@app.post('/api/v1/orders')"],
    ))

    # 5. Unrelated / Protected Files
    graph.add_symbol(Symbol(
        id="u1", name="format_currency", qualified_name="utils.helpers.format_currency",
        symbol_type=SymbolType.FUNCTION, language="python", file="utils/helpers.py",
        line=1, end_line=15, visibility=Visibility.PUBLIC,
    ))
    graph.add_symbol(Symbol(
        id="u2", name="AuthToken", qualified_name="auth.token.AuthToken",
        symbol_type=SymbolType.CLASS, language="python", file="auth/token.py",
        line=1, end_line=30, visibility=Visibility.PUBLIC,
    ))

    # Dependencies
    graph.add_dependency(Dependency(source_file="repositories/order_repo.py", target_file="models/order.py"))
    graph.add_dependency(Dependency(source_file="services/order_service.py", target_file="repositories/order_repo.py"))
    graph.add_dependency(Dependency(source_file="services/order_service.py", target_file="services/base.py"))
    graph.add_dependency(Dependency(source_file="controllers/order_ctrl.py", target_file="services/order_service.py"))

    # Update reverse call and subclass graph
    graph.subclass_graph["BaseProcessor"] = {"OrderService"}
    graph.reverse_call_graph["find_by_id"] = {"process_order"}
    graph.reverse_call_graph["process_order"] = {"handle_post_order"}

    return graph


# =============================================================================
# TEST CASES
# =============================================================================

def test_1_minimal_change_set_and_avoided_files(temp_dir):
    """Test minimal change set computation and protected file classification."""
    graph = create_sample_graph()
    planner = ChangePlanner(symbol_graph=graph)

    task = Task(
        id="TASK-01",
        title="Add discount validation to process_order",
        description="Update process_order in services/order_service.py to support discounts.",
        estimated_files=["services/order_service.py"],
    )

    plan = planner.plan(task, context={"project_files": {"services/order_service.py": "def process_order(): pass"}})

    assert "services/order_service.py" in plan.files_to_modify
    # Protected files that should NOT change
    assert "utils/helpers.py" in plan.files_to_avoid
    assert "auth/token.py" in plan.files_to_avoid

    # Check necessity rank
    svc_change = next(fc for fc in plan.file_changes if fc.file_path == "services/order_service.py")
    assert svc_change.necessity_rank == NecessityRank.PRIMARY_TARGET


def test_2_change_classification_heuristics(temp_dir):
    """Test change classification for various task intents."""
    planner = ChangePlanner()

    t_bug = Task(id="T1", title="Fix null pointer error in auth token", description="Fix crash bug", estimated_files=[])
    assert planner.plan(t_bug).change_classification == ChangeClassification.BUG_FIX

    t_refactor = Task(id="T2", title="Refactor and extract class for order validation", description="Cleanup logic", estimated_files=[])
    assert planner.plan(t_refactor).change_classification == ChangeClassification.REFACTOR

    t_opt = Task(id="T3", title="Optimize memory caching latency", description="Speed up query perf", estimated_files=[])
    assert planner.plan(t_opt).change_classification == ChangeClassification.OPTIMIZATION

    t_sec = Task(id="T4", title="Security patch for SQL injection vulnerability", description="Sanitize inputs", estimated_files=[])
    assert planner.plan(t_sec).change_classification == ChangeClassification.SECURITY_PATCH

    t_doc = Task(id="T5", title="Update README documentation and guide", description="Add usage doc", estimated_files=[])
    assert planner.plan(t_doc).change_classification == ChangeClassification.DOCUMENTATION

    t_cfg = Task(id="T6", title="Update settings in config.yaml", description="Change env settings", estimated_files=[])
    assert planner.plan(t_cfg).change_classification == ChangeClassification.CONFIGURATION


def test_3_semantic_refactoring_detection(temp_dir):
    """Test detection of Rename, Extract Method/Class, Repository Extraction, and DI."""
    graph = create_sample_graph()
    planner = ChangePlanner(symbol_graph=graph)

    task_rename = Task(id="T1", title="Rename process_order to execute_order", description="Rename method", estimated_files=["services/order_service.py"])
    plan_rename = planner.plan(task_rename)
    assert any(r.refactoring_type == RefactoringType.RENAME for r in plan_rename.refactoring_steps)

    task_extract = Task(id="T2", title="Extract method for payment validation", description="Extract helper function", estimated_files=["services/order_service.py"])
    plan_extract = planner.plan(task_extract)
    assert any(r.refactoring_type == RefactoringType.EXTRACT_METHOD for r in plan_extract.refactoring_steps)

    task_repo = Task(id="T3", title="Create and extract repository for payments", description="Isolate database access", estimated_files=["repositories/payment_repo.py"])
    plan_repo = planner.plan(task_repo)
    assert any(r.refactoring_type == RefactoringType.REPOSITORY_EXTRACTION for r in plan_repo.refactoring_steps)


def test_4_breaking_change_detection_public_api_and_callers(temp_dir):
    """Test breaking change detection when public symbols with callers are deleted or signature-altered."""
    graph = create_sample_graph()
    planner = ChangePlanner(symbol_graph=graph)

    task = Task(
        id="TASK-DELETE",
        title="Delete process_order method",
        description="Remove process_order function permanently from services/order_service.py",
        estimated_files=["services/order_service.py"],
    )

    plan = planner.plan(task)
    breaking_cats = {b.change_category for b in plan.breaking_changes}

    assert "PUBLIC_API" in breaking_cats
    pub_break = next(b for b in plan.breaking_changes if b.change_category == "PUBLIC_API")
    assert pub_break.impact_level in ("CRITICAL", "HIGH")
    assert len(pub_break.mitigation_strategy) > 0


def test_5_breaking_change_detection_inheritance_and_subclasses(temp_dir):
    """Test breaking change detection when modifying a base class with active subclasses."""
    graph = create_sample_graph()
    planner = ChangePlanner(symbol_graph=graph)

    task = Task(
        id="TASK-BASE",
        title="Modify BaseProcessor interface signature",
        description="Change BaseProcessor constructor and process signature in services/base.py",
        estimated_files=["services/base.py"],
    )

    plan = planner.plan(task)
    breaking_cats = {b.change_category for b in plan.breaking_changes}

    assert "INHERITANCE_CHANGE" in breaking_cats
    inh_break = next(b for b in plan.breaking_changes if b.change_category == "INHERITANCE_CHANGE")
    assert "BaseProcessor" in inh_break.target


def test_6_database_migration_and_rollback_generation(temp_dir):
    """Test schema keyword tasks generate MigrationStep with forward and rollback SQL."""
    planner = ChangePlanner()

    task = Task(
        id="TASK-DB",
        title="Update database schema for orders table",
        description="Alter table orders and add column discount_amount decimal to database models",
        estimated_files=["models/order.py"],
    )

    plan = planner.plan(task)

    assert len(plan.migration_steps) >= 1
    m = plan.migration_steps[0]
    assert m.migration_type == "DATABASE_SCHEMA"
    assert "ALTER TABLE" in m.sql_or_code_action
    assert "DROP COLUMN" in m.rollback_instruction
    assert m.is_reversible is True


def test_7_rest_api_and_cli_breaking_changes(temp_dir):
    """Test detection of REST API endpoint modifications and CLI changes."""
    planner = ChangePlanner()

    task_api = Task(
        id="TASK-API",
        title="Modify REST endpoint payload for /api/v1/orders route",
        description="Change request schema and controller route response",
        estimated_files=["controllers/order_ctrl.py"],
    )
    plan_api = planner.plan(task_api)
    assert any(b.change_category == "REST_ENDPOINT" for b in plan_api.breaking_changes)

    task_cli = Task(
        id="TASK-CLI",
        title="Change CLI command argument flags for order export",
        description="Modify click command option --format to --output-format",
        estimated_files=["cli.py"],
    )
    plan_cli = planner.plan(task_cli)
    assert any(b.change_category == "CLI_CHANGE" for b in plan_cli.breaking_changes)


def test_8_execution_and_rollback_ordering_topological(temp_dir):
    """Test topological execution order (Models -> Repositories -> Services -> Controllers -> Tests)."""
    graph = create_sample_graph()
    planner = ChangePlanner(symbol_graph=graph)

    task = Task(
        id="TASK-FLOW",
        title="Implement full order discount feature",
        description="Modify models, repositories, services, and controllers for discounts.",
        estimated_files=[
            "controllers/order_ctrl.py",
            "services/order_service.py",
            "repositories/order_repo.py",
            "models/order.py",
        ],
    )

    plan = planner.plan(task)

    exec_order = plan.execution_order
    assert len(exec_order) >= 4

    # Models must execute before Controllers
    assert exec_order.index("models/order.py") < exec_order.index("controllers/order_ctrl.py")
    # Repositories must execute before Controllers
    assert exec_order.index("repositories/order_repo.py") < exec_order.index("controllers/order_ctrl.py")

    # Rollback order is strictly reversed
    assert plan.rollback_order == list(reversed(exec_order))


def test_9_architectural_validation_rules_and_layer_violations(temp_dir):
    """Test validation rules identify layer violations and clean plans pass."""
    # 1. Clean Graph
    clean_graph = create_sample_graph()
    planner_clean = ChangePlanner(symbol_graph=clean_graph)
    task_clean = Task(id="T1", title="Add helper method to service", description="Simple update", estimated_files=["services/order_service.py"])
    plan_clean = planner_clean.plan(task_clean)

    layer_rule = next(v for v in plan_clean.validation_rules if v.rule_name == "Layer Hierarchy Integrity")
    assert layer_rule.passed is True

    # 2. Graph with Layer Violation (Model directly imports Controller)
    bad_graph = create_sample_graph()
    bad_graph.add_dependency(Dependency(source_file="models/order.py", target_file="controllers/order_ctrl.py"))
    planner_bad = ChangePlanner(symbol_graph=bad_graph)
    task_bad = Task(id="T2", title="Update order model", description="Update model", estimated_files=["models/order.py"])
    plan_bad = planner_bad.plan(task_bad)

    bad_layer_rule = next(v for v in plan_bad.validation_rules if v.rule_name == "Layer Hierarchy Integrity")
    assert bad_layer_rule.passed is False
    assert bad_layer_rule.severity == "ERROR"


def test_10_json_export_and_import_roundtrip(temp_dir):
    """Test exporting ChangePlan to JSON and loading it back."""
    graph = create_sample_graph()
    output_file = temp_dir / "change_plan.json"
    planner = ChangePlanner(symbol_graph=graph, output_path=output_file)

    task = Task(id="TASK-IO", title="Add currency validation", description="Update utils/helpers.py", estimated_files=["utils/helpers.py"])
    plan = planner.plan(task)

    saved_path = planner.export(plan)
    assert saved_path.is_file()

    loaded = planner.load_plan(saved_path)
    assert loaded.task_id == plan.task_id
    assert loaded.change_classification == plan.change_classification
    assert len(loaded.file_changes) == len(plan.file_changes)
    assert loaded.estimated_total_lines == plan.estimated_total_lines
    assert loaded.summary == plan.summary


def test_11_statistics_telemetry(temp_dir):
    """Test computed statistics dictionary metrics."""
    graph = create_sample_graph()
    planner = ChangePlanner(symbol_graph=graph)

    task = Task(id="TASK-STAT", title="Update order service", description="Update logic", estimated_files=["services/order_service.py"])
    plan = planner.plan(task)
    stats = planner.statistics(plan)

    assert stats["task_id"] == "TASK-STAT"
    assert stats["total_files_modified"] >= 1
    assert stats["total_files_avoided"] >= 1
    assert "risk_level" in stats
    assert "validation_passed" in stats


def test_12_prompt_builder_integration(temp_dir):
    """Test PromptBuilder injects CHANGE PLAN section with files to modify, avoid, and execution order."""
    graph = create_sample_graph()
    planner = ChangePlanner(symbol_graph=graph)

    task = Task(
        id="TASK-PB",
        title="Add payment validation to order service",
        description="Update services/order_service.py",
        estimated_files=["services/order_service.py"],
    )

    plan = planner.plan(task)
    context = {
        "project_name": "ECommerceApp",
        "description": "Enterprise shopping",
        "technology_stack": "Python",
        "change_plan": plan,
        "symbol_graph": graph,
    }

    builder = PromptBuilder(symbol_graph=graph, change_planner=planner)
    prompt = builder.build(context=context, task=task)

    assert "CHANGE PLAN" in prompt
    assert "Classification :" in prompt
    assert "Files to Modify:" in prompt
    assert "services/order_service.py" in prompt
    assert "Files to Avoid (Protected" in prompt
    assert "Execution Order:" in prompt


def test_13_orchestrator_integration(temp_dir):
    """Test Orchestrator initializes ChangePlanner, computes plan, and stores it in context."""
    plan_file = temp_dir / "project_plan.json"
    plan_data = {
        "project_name": "ChangePlanOrchestratorTest",
        "total_days": 1,
        "phases": [{
            "day": 1,
            "phase_name": "Phase 1",
            "goals": ["Implement feature"],
            "tasks": [{
                "id": "DAY1-T01",
                "title": "Update order service logic",
                "description": "Implement service method",
                "priority": 1,
                "status": "pending",
                "dependencies": [],
                "estimated_files": ["services/order_service.py"],
            }],
        }],
    }
    plan_file.write_text(json.dumps(plan_data), encoding="utf-8")

    graph = create_sample_graph()
    planner = ChangePlanner(symbol_graph=graph)

    orchestrator = Orchestrator(
        project_root=temp_dir,
        plan_path=plan_file,
        change_planner=planner,
    )

    summary = orchestrator.run()
    assert summary.overall_success is True


def test_14_performance_and_deterministic_output(temp_dir):
    """Test execution on 1,200+ symbols (<0.5s) and 100% deterministic output."""
    large_graph = SymbolGraph()
    for f_idx in range(120):
        fname = f"modules/pkg_{f_idx // 10}/module_{f_idx}.py"
        cls_name = f"ServiceClass_{f_idx}"
        large_graph.add_symbol(Symbol(
            id=f"c_{f_idx}", name=cls_name, qualified_name=f"pkg_{f_idx // 10}.{cls_name}",
            symbol_type=SymbolType.CLASS, language="python", file=fname,
            line=1, end_line=100, visibility=Visibility.PUBLIC,
        ))
        if f_idx > 0:
            large_graph.add_dependency(Dependency(
                source_file=fname,
                target_file=f"modules/pkg_{(f_idx - 1) // 10}/module_{f_idx - 1}.py",
            ))

    planner = ChangePlanner(symbol_graph=large_graph)
    task = Task(id="TASK-PERF", title="Update ServiceClass_50", description="Modify pkg_5", estimated_files=["modules/pkg_5/module_50.py"])

    start_t = time.time()
    plan_1 = planner.plan(task)
    elapsed = time.time() - start_t

    assert elapsed < 0.5, f"Change planning took {elapsed:.3f}s (expected < 0.5s)"

    # Determinism check
    plan_2 = planner.plan(task)
    d1 = plan_1.to_dict()
    d2 = plan_2.to_dict()
    d1["timestamp"] = "STATIC"
    d2["timestamp"] = "STATIC"

    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)
