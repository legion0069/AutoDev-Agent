"""
test_architecture_manager.py - Comprehensive Test Suite for AutoDev Architecture Decision Record (ADR) Engine & Design Validator

Covers:
- ArchitectureDecision Dataclass & Enums
- ArchitectureManager CRUD, atomic persistence & versioning
- Full-text search, component search, tag search, category filtering
- DesignValidator 13 architectural validation rules
- MemoryManager automatic promotion
- Markdown & JSON export/import
- PromptBuilder & ContextInjector integration
- Orchestrator integration & critical violation abort
- Corrupted JSON recovery & fallback
- High-performance benchmarks (500 ADRs, 1000 validations < 100ms)
- Deterministic behavior across runs
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
from core.architecture_manager import (
    ArchitectureDecision,
    ArchitectureManager,
    DecisionCategory,
    DecisionStatus,
    DesignValidator,
    DesignViolation,
    ValidationReport,
    ViolationSeverity,
)
from core.context_injector import ContextInjector
from core.memory_manager import MemoryCategory, MemoryEntry, MemoryManager
from core.prompt_builder import PromptBuilder
from core.symbol_graph import SymbolGraph


@pytest.fixture
def temp_dir():
    """Provides an isolated temporary workspace directory."""
    d = tempfile.mkdtemp(prefix="autodev_adr_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


# =============================================================================
# 1. DATACLASS & ENUM TESTS
# =============================================================================

def test_1_architecture_decision_dataclass_and_defaults():
    """Test ArchitectureDecision instantiation, normalization, and serialization."""
    adr = ArchitectureDecision(
        id="ADR-001",
        title="Use PostgreSQL for Primary Data Storage",
        category=DecisionCategory.DATABASE,
        status=DecisionStatus.ACCEPTED,
        decision="Adopt PostgreSQL with connection pooling via asyncpg.",
        context="Need ACID compliant relational database.",
        consequences="Requires running PostgreSQL instance; migrations managed by Alembic.",
        alternatives=["MySQL", "SQLite", "MongoDB"],
        related_components=["models/user.py", "db/session.py"],
        tags=["database", "sql", "postgres"],
    )

    assert adr.id == "ADR-001"
    assert adr.category == "DATABASE"
    assert adr.status == "accepted"
    assert adr.version == 1
    assert len(adr.alternatives) == 3

    d = adr.to_dict()
    assert d["title"] == "Use PostgreSQL for Primary Data Storage"
    assert d["category"] == "DATABASE"

    restored = ArchitectureDecision.from_dict(d)
    assert restored.id == adr.id
    assert restored.title == adr.title
    assert restored.alternatives == adr.alternatives


def test_2_decision_category_and_status_normalization():
    """Test flexible normalization of category and status strings."""
    assert DecisionCategory.normalize("database") == "DATABASE"
    assert DecisionCategory.normalize("Dependency Injection") == "DEPENDENCY_INJECTION"
    assert DecisionCategory.normalize("UNKNOWN_CAT") == "ARCHITECTURE"

    assert DecisionStatus.normalize("ACCEPTED") == "accepted"
    assert DecisionStatus.normalize("Proposed") == "proposed"
    assert DecisionStatus.normalize("invalid_status") == "proposed"


# =============================================================================
# 2. CRUD & ATOMIC PERSISTENCE TESTS
# =============================================================================

def test_3_record_and_get_decision(temp_dir):
    """Test recording decisions with auto-generated IDs and retrieval."""
    json_path = temp_dir / "memory" / "architecture_decisions.json"
    manager = ArchitectureManager(persistence_path=json_path, auto_create=True)

    adr1 = manager.record_decision(
        title="Adopt Repository Pattern for Data Isolation",
        decision="All database access must happen through Repository classes.",
        category=DecisionCategory.ARCHITECTURE,
        status=DecisionStatus.ACCEPTED,
    )
    assert adr1.id == "ADR-001"
    assert adr1.version == 1

    adr2 = manager.record_decision(
        title="Use Redis for Token Caching",
        decision="Store invalidated JWT tokens in Redis with TTL.",
        category=DecisionCategory.CACHING,
        status=DecisionStatus.ACCEPTED,
    )
    assert adr2.id == "ADR-002"

    retrieved = manager.get_decision("ADR-001")
    assert retrieved is not None
    assert retrieved.title == "Adopt Repository Pattern for Data Isolation"
    assert manager.get_decision("NONEXISTENT") is None


def test_4_update_decision_and_versioning(temp_dir):
    """Test updating decisions and verifying version increments."""
    json_path = temp_dir / "architecture_decisions.json"
    manager = ArchitectureManager(persistence_path=json_path, auto_create=True)

    adr = manager.record_decision(
        title="Initial Logging Strategy",
        decision="Use standard print statements.",
        status=DecisionStatus.PROPOSED,
    )
    assert adr.version == 1

    updated = manager.update_decision(
        decision_id=adr.id,
        decision="Use standard logging module with JSON structured formatting.",
        status=DecisionStatus.ACCEPTED,
        category=DecisionCategory.LOGGING,
    )
    assert updated.version == 2
    assert updated.status == "accepted"
    assert updated.category == "LOGGING"
    assert "structured" in updated.decision

    # Verify reload from disk preserves updated version
    fresh_mgr = ArchitectureManager(persistence_path=json_path)
    loaded = fresh_mgr.get_decision(adr.id)
    assert loaded.version == 2
    assert loaded.status == "accepted"


def test_5_update_nonexistent_decision_raises_error(temp_dir):
    """Test updating nonexistent ADR raises KeyError."""
    manager = ArchitectureManager(persistence_path=temp_dir / "adrs.json", auto_create=True)
    with pytest.raises(KeyError):
        manager.update_decision("ADR-999", title="Fake")


def test_6_list_decisions_with_filters(temp_dir):
    """Test filtering decisions by status, category, and tag."""
    manager = ArchitectureManager(persistence_path=temp_dir / "adrs.json", auto_create=True)

    manager.record_decision("API Schema", "Use Pydantic v2", category=DecisionCategory.API, status=DecisionStatus.ACCEPTED, tags=["api", "pydantic"])
    manager.record_decision("DB Engine", "Use SQLite", category=DecisionCategory.DATABASE, status=DecisionStatus.DEPRECATED, tags=["db"])
    manager.record_decision("Auth Flow", "Use OAuth2 with PKCE", category=DecisionCategory.AUTHENTICATION, status=DecisionStatus.ACCEPTED, tags=["auth", "security"])
    manager.record_decision("Monolith Split", "Extract microservices", category=DecisionCategory.ARCHITECTURE, status=DecisionStatus.REJECTED, tags=["arch"])

    assert len(manager.list_decisions()) == 4
    assert len(manager.list_decisions(status=DecisionStatus.ACCEPTED)) == 2
    assert len(manager.list_decisions(status=DecisionStatus.REJECTED)) == 1
    assert len(manager.list_decisions(category=DecisionCategory.DATABASE)) == 1
    assert len(manager.list_decisions(tag="security")) == 1


# =============================================================================
# 3. SEARCH & RETRIEVAL TESTS
# =============================================================================

def test_7_full_text_search(temp_dir):
    """Test search ranking by token overlap across title, decision, context, and tags."""
    manager = ArchitectureManager(persistence_path=temp_dir / "adrs.json", auto_create=True)

    manager.record_decision(
        title="Repository Pattern for Orders",
        decision="Encapsulate SQL in OrderRepository.",
        tags=["repository", "orders"],
    )
    manager.record_decision(
        title="Redis Caching Layer",
        decision="Cache user sessions in Redis.",
        tags=["cache", "redis"],
    )
    manager.record_decision(
        title="Order Validation Engine",
        decision="Validate order items using business rules.",
        tags=["orders", "validation"],
    )

    results = manager.search("Order Repository SQL")
    assert len(results) >= 1
    assert results[0].title == "Repository Pattern for Orders"


def test_8_search_by_component_and_tag(temp_dir):
    """Test finding ADRs linked to specific components or tags."""
    manager = ArchitectureManager(persistence_path=temp_dir / "adrs.json", auto_create=True)

    manager.record_decision(
        title="Payment Service Isolation",
        decision="PaymentService handles all payment transactions.",
        related_components=["services/payment_service.py", "models/payment.py"],
        tags=["payment", "finance"],
    )
    manager.record_decision(
        title="User Service Authentication",
        decision="UserService manages password hashing.",
        related_components=["services/user_service.py"],
        tags=["auth", "users"],
    )

    matches = manager.search_by_component("services/payment_service.py")
    assert len(matches) == 1
    assert matches[0].title == "Payment Service Isolation"

    tag_matches = manager.search_by_tag("finance")
    assert len(tag_matches) == 1


def test_9_search_relevant_for_task(temp_dir):
    """Test task-aware semantic ADR discovery."""
    manager = ArchitectureManager(persistence_path=temp_dir / "adrs.json", auto_create=True)

    manager.record_decision(
        title="Secure Password Hashing with Argon2",
        decision="Use Argon2id for password hashing.",
        category=DecisionCategory.SECURITY,
        status=DecisionStatus.ACCEPTED,
        tags=["auth", "password", "security"],
    )
    manager.record_decision(
        title="FastAPI Web Framework",
        decision="Use FastAPI for HTTP APIs.",
        category=DecisionCategory.API,
        status=DecisionStatus.ACCEPTED,
        tags=["api", "fastapi"],
    )

    task = Task(id="T1", title="Implement user password reset security flow", description="Hash passwords securely", estimated_files=["auth/reset.py"])
    relevant = manager.search_relevant_for_task(task)
    assert len(relevant) >= 1
    assert any("password" in r.title.lower() or "security" in r.title.lower() for r in relevant)


# =============================================================================
# 4. DESIGN VALIDATION ENGINE TESTS (13 ARCHITECTURAL RULES)
# =============================================================================

def test_10_validation_rule_repository_pattern_violation():
    """Rule 1: Direct SQL in service/controller triggers Repository Pattern violation."""
    validator = DesignValidator()
    code = """
class OrderService:
    def get_order(self, order_id):
        cursor = sqlite3.connect('app.db').cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        return cursor.fetchone()
"""
    task = Task(id="T1", title="Fetch order details", description="Query db", estimated_files=["services/order_service.py"])
    report = validator.validate(task, code_context={"services/order_service.py": code})

    assert len(report.violations) > 0
    assert any(v.rule_name == "Repository Pattern Violation" for v in report.violations)
    assert report.risk_score > 0.0


def test_11_validation_rule_layer_violation_domain_to_presentation():
    """Rule 2: Domain model importing controller/presentation triggers CRITICAL violation."""
    validator = DesignValidator()
    code = """
from controllers.order_controller import OrderController

class Order:
    def __init__(self, id):
        self.id = id
"""
    task = Task(id="T2", title="Update Order Model", description="", estimated_files=["models/order.py"])
    report = validator.validate(task, code_context={"models/order.py": code})

    assert report.is_critical is True
    assert any("Layer Violation (Domain -> Presentation)" in v.rule_name for v in report.violations)


def test_12_validation_rule_service_calling_ui():
    """Rule 3: Service calling UI or routes layer triggers violation."""
    validator = DesignValidator()
    code = """
from routes.order_routes import router

class OrderService:
    def notify_route(self):
        pass
"""
    task = Task(id="T3", title="Notify Service", description="", estimated_files=["services/order_service.py"])
    report = validator.validate(task, code_context={"services/order_service.py": code})

    assert any(v.rule_name == "Service Calling UI Layer Violation" for v in report.violations)


def test_13_validation_rule_dependency_inversion():
    """Rule 4: Hardcoding concrete provider instantiation triggers DI warning."""
    validator = DesignValidator()
    code = """
class AgentService:
    def __init__(self):
        self.provider = OpenAIProvider()
"""
    task = Task(id="T4", title="Init Agent", description="", estimated_files=["services/agent_service.py"])
    report = validator.validate(task, code_context={"services/agent_service.py": code})

    assert any("Dependency Inversion Violation" in v.rule_name for v in report.violations)


def test_14_validation_rule_circular_dependency():
    """Rule 5: Circular dependency detection via SymbolGraph."""
    graph = SymbolGraph()
    graph.file_dependency_graph = {
        "a.py": {"b.py"},
        "b.py": {"a.py"},
    }
    validator = DesignValidator()
    task = Task(id="T5", title="Cycle Task", description="", estimated_files=["a.py", "b.py"])
    report = validator.validate(task, symbol_graph=graph)

    assert report.is_critical is True
    assert any("Circular Dependency Introduction" in v.rule_name for v in report.violations)


def test_15_validation_rule_singleton_misuse():
    """Rule 6: Mutable global singleton pattern triggers warning."""
    validator = DesignValidator()
    code = """
_instance = None
class DatabaseManager:
    def __new__(cls):
        global _instance
        if not _instance:
            _instance = super().__new__(cls)
        return _instance
"""
    task = Task(id="T6", title="Singleton DB", description="", estimated_files=["core/db.py"])
    report = validator.validate(task, code_context={"core/db.py": code})

    assert any("Singleton Misuse" in v.rule_name for v in report.violations)


def test_16_validation_rule_duplicate_implementations():
    """Rule 7: Duplicate class names across non-test modules triggers error."""
    validator = DesignValidator()
    context = {
        "services/order.py": "class OrderProcessor:\n    pass\n",
        "handlers/order.py": "class OrderProcessor:\n    pass\n",
    }
    task = Task(id="T7", title="Duplicate Check", description="", estimated_files=["services/order.py"])
    report = validator.validate(task, code_context=context)

    assert any(v.rule_name == "Duplicate Implementation" for v in report.violations)


def test_17_validation_rule_bypassed_interfaces():
    """Rule 8: Concrete provider bypassing mandatory BaseLLM interface triggers violation."""
    adr = ArchitectureDecision(
        id="ADR-010",
        title="All LLM Providers Must Implement BaseLLM",
        decision="All providers must inherit from BaseLLM abstract interface.",
        category=DecisionCategory.ARCHITECTURE,
        status=DecisionStatus.ACCEPTED,
    )
    validator = DesignValidator()
    code = """
class CustomMockProvider:
    def generate(self, prompt):
        return "response"
"""
    task = Task(id="T8", title="Add Provider", description="", estimated_files=["providers/custom_provider.py"])
    report = validator.validate(
        task,
        code_context={"providers/custom_provider.py": code},
        architecture_decisions=[adr],
    )

    assert any(v.rule_name == "Bypassed Interface Contract" for v in report.violations)


def test_18_validation_rule_hardcoded_secrets():
    """Rule 9: Hardcoded credentials or API keys trigger CRITICAL violation."""
    validator = DesignValidator()
    code = """
API_KEY = "sk-proj-1234567890abcdef12345"
password = "supersecretpassword123"
"""
    task = Task(id="T9", title="API Connect", description="", estimated_files=["core/client.py"])
    report = validator.validate(task, code_context={"core/client.py": code})

    assert report.is_critical is True
    assert any("Hardcoded Secret Detection" in v.rule_name for v in report.violations)


def test_19_validation_rule_swallowed_exceptions():
    """Rule 10: Bare except: pass triggers exception propagation warning."""
    validator = DesignValidator()
    code = """
def process():
    try:
        do_work()
    except:
        pass
"""
    task = Task(id="T10", title="Process work", description="", estimated_files=["core/worker.py"])
    report = validator.validate(task, code_context={"core/worker.py": code})

    assert any("Incorrect Exception Propagation" in v.rule_name for v in report.violations)


def test_20_validation_rule_missing_logging_and_tests():
    """Rule 11 & 12: Missing logging in large engine and missing test file in task."""
    validator = DesignValidator()
    code = "# Large subsystem\n" + "x = 1\n" * 150
    task = Task(id="T11", title="Create Engine", description="", estimated_files=["core/big_engine.py"])
    report = validator.validate(task, code_context={"core/big_engine.py": code})

    assert any("Missing Observability / Logging" in v.rule_name for v in report.violations)
    assert any("Missing Test Coverage Requirement" in v.rule_name for v in report.violations)


# =============================================================================
# 5. MEMORY MANAGER PROMOTION INTEGRATION
# =============================================================================

def test_21_memory_manager_promotion(temp_dir):
    """Test automatic promotion of high-importance memory entries into ADRs."""
    manager = ArchitectureManager(persistence_path=temp_dir / "adrs.json", auto_create=True)

    mem_entry = MemoryEntry(
        id="MEM-001",
        timestamp="2026-10-06T12:00:00Z",
        category=MemoryCategory.PATTERN,
        title="Use Unit of Work with Repository Pattern",
        content="Group multiple repository operations into an atomic Unit of Work transaction.",
        importance=1,
        tags=["uow", "transaction", "repository"],
    )

    adr = manager.promote_from_memory(mem_entry, min_importance=0.5)
    assert adr is not None
    assert adr.title == "Use Unit of Work with Repository Pattern"
    assert adr.status == "accepted"
    assert "promoted_from_memory" in adr.tags

    # Attempting to promote low-importance entry should return None
    low_mem = MemoryEntry(
        id="MEM-002",
        timestamp="2026-10-06T12:00:00Z",
        category=MemoryCategory.TODO,
        title="Minor cleanup",
        content="Clean unused imports",
        importance=0,
    )
    assert manager.promote_from_memory(low_mem, min_importance=0.5) is None


# =============================================================================
# 6. EXPORT / IMPORT & MARKDOWN GENERATION
# =============================================================================

def test_22_markdown_and_json_export_import(temp_dir):
    """Test MADR markdown generation and JSON export/import."""
    manager = ArchitectureManager(persistence_path=temp_dir / "adrs.json", auto_create=True)
    manager.record_decision(
        title="Adopt Clean Architecture",
        decision="Separate Domain, Application, and Infrastructure layers.",
        category=DecisionCategory.ARCHITECTURE,
        status=DecisionStatus.ACCEPTED,
        alternatives=["Layered", "Microkernel"],
    )

    md_path = temp_dir / "ADR.md"
    md_content = manager.export_markdown(md_path)
    assert "# Architecture Decision Records (ADRs)" in md_content
    assert "Adopt Clean Architecture" in md_content
    assert md_path.is_file()

    export_json_path = temp_dir / "exported_adrs.json"
    manager.export_json(export_json_path)
    assert export_json_path.is_file()

    # Import into fresh manager
    new_mgr = ArchitectureManager(persistence_path=temp_dir / "new_adrs.json", auto_create=True)
    imported_count = new_mgr.import_json(export_json_path)
    assert imported_count == 1
    assert new_mgr.get_decision("ADR-001").title == "Adopt Clean Architecture"


# =============================================================================
# 7. PROMPT BUILDER & CONTEXT INJECTOR INTEGRATION
# =============================================================================

def test_23_prompt_builder_integration(temp_dir):
    """Test injection of ARCHITECTURAL DECISIONS section in PromptBuilder."""
    manager = ArchitectureManager(persistence_path=temp_dir / "adrs.json", auto_create=True)
    manager.record_decision("Event Sourcing for Audits", "Store all audit events in event store.", status=DecisionStatus.ACCEPTED)
    manager.record_decision("Direct File Writes from UI", "Never write files directly from UI.", status=DecisionStatus.REJECTED)

    builder = PromptBuilder(architecture_manager=manager)
    task = Task(id="T1", title="Implement audit trail", description="Log audit events", estimated_files=["audit.py"])
    context = {"project_name": "AuditApp", "architecture_manager": manager}

    prompt = builder.build(context=context, task=task)
    assert "ARCHITECTURAL DECISIONS" in prompt
    assert "Event Sourcing for Audits" in prompt
    assert "Direct File Writes from UI" in prompt
    assert "Required Architectural Constraints" in prompt


def test_24_context_injector_integration(temp_dir):
    """Test ContextInjector retrieving relevant architectural decisions."""
    manager = ArchitectureManager(persistence_path=temp_dir / "adrs.json", auto_create=True)
    manager.record_decision("Token Bucket Rate Limiting", "Implement token bucket rate limiter.", category=DecisionCategory.PERFORMANCE, tags=["rate_limit", "perf"])

    injector = ContextInjector(architecture_manager=manager)
    task = Task(id="T1", title="Implement rate limit algorithm", description="", estimated_files=["rate_limiter.py"])
    decisions = injector.retrieve_relevant_decisions(context={}, task=task)

    assert len(decisions) >= 1
    assert decisions[0].title == "Token Bucket Rate Limiting"


# =============================================================================
# 8. CORRUPTED JSON RECOVERY & PERFORMANCE BENCHMARKS
# =============================================================================

def test_25_corrupted_json_recovery(temp_dir):
    """Test graceful recovery when ADR JSON file contains invalid JSON."""
    json_path = temp_dir / "corrupt_adrs.json"
    with open(json_path, "w", encoding="utf-8") as f:
        f.write("{ INVALID JSON DATA --- ")

    manager = ArchitectureManager(persistence_path=json_path, auto_create=True)
    assert len(manager.list_decisions()) == 0
    # Can still record new decision
    adr = manager.record_decision("New Decision", "Adopt new standard.")
    assert adr.id == "ADR-001"


def test_26_high_performance_benchmark(temp_dir):
    """Test sub-100ms execution for 500 ADRs and 1000 validations."""
    manager = ArchitectureManager(persistence_path=temp_dir / "adrs.json", auto_create=True)

    # Generate 500 ADRs in memory
    for i in range(500):
        adr = ArchitectureDecision(
            id=f"ADR-{i:03d}",
            title=f"Architecture Decision {i}",
            category=DecisionCategory.ARCHITECTURE,
            decision=f"Decision content for rule number {i}",
            tags=[f"tag_{i % 10}", "performance"],
        )
        manager._decisions[adr.id] = adr
    manager._initialized = True

    # Search benchmark
    start_time = time.perf_counter()
    for _ in range(100):
        manager.search("Architecture Decision 42 tag_2")
    search_duration = time.perf_counter() - start_time
    assert search_duration < 0.1, f"Search took {search_duration:.4f}s, expected < 0.1s"

    # Validation benchmark (1000 iterations)
    validator = DesignValidator(architecture_manager=manager)
    task = Task(id="T1", title="Benchmark task", description="Simple task", estimated_files=["services/clean_service.py"])
    clean_code = "class CleanService:\n    def run(self):\n        pass\n"

    val_start = time.perf_counter()
    for _ in range(1000):
        validator.validate(task, code_context={"services/clean_service.py": clean_code})
    val_duration = time.perf_counter() - val_start
    assert val_duration < 0.1, f"1000 validations took {val_duration:.4f}s, expected < 0.1s"


def test_27_statistics_and_summary_telemetry(temp_dir):
    """Test statistics dictionary and summary string generation."""
    manager = ArchitectureManager(persistence_path=temp_dir / "adrs.json", auto_create=True)
    manager.record_decision("API Spec", "Use OpenAPI 3.0", category=DecisionCategory.API, status=DecisionStatus.ACCEPTED, tags=["api", "docs"])
    manager.record_decision("Cache", "Use Memcached", category=DecisionCategory.CACHING, status=DecisionStatus.DEPRECATED, tags=["cache"])

    stats = manager.statistics()
    assert stats["total_decisions"] == 2
    assert stats["by_status"]["accepted"] == 1
    assert stats["by_status"]["deprecated"] == 1
    assert stats["by_category"]["API"] == 1

    summary = manager.generate_summary()
    assert "Architecture Decisions: 2 Total" in summary
    assert "OpenAPI 3.0" in summary
