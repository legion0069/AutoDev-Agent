"""
test_learning_models.py - AutoDev Version 3.1
Tests data contracts, dataclasses, enums, serialization, and deserialization
across the entire Self-Evolving Intelligence Engine.
"""

import json
import pytest
from core.learning.learning_models import (
    ArchitectureRecommendation,
    EngineeringPattern,
    EngineeringPlaybook,
    ImprovementArea,
    ImprovementRoadmapItem,
    LearningEvent,
    LearningEventType,
    LearningKnowledge,
    LearningSession,
    LearningSnapshot,
    PatternCategory,
    PerformanceEvolutionRecord,
    PlaybookArchetype,
    PromptOptimizationRecord,
    ReflectionReport,
    ReflectionScope,
    SelfImprovementPlan,
)


def test_learning_event_type_values():
    assert LearningEventType.BUG_FIXED.value == "BUG_FIXED"
    assert LearningEventType.PATTERN_DISCOVERED.value == "PATTERN_DISCOVERED"
    assert LearningEventType.REVIEW_FAILURE.value == "REVIEW_FAILURE"
    assert LearningEventType.ARCHITECTURE_SUCCESS.value == "ARCHITECTURE_SUCCESS"
    assert LearningEventType.PERFORMANCE_IMPROVEMENT.value == "PERFORMANCE_IMPROVEMENT"
    assert LearningEventType.TEST_STRATEGY.value == "TEST_STRATEGY"
    assert LearningEventType.REFACTOR_SUCCESS.value == "REFACTOR_SUCCESS"
    assert LearningEventType.DEPLOYMENT_FAILURE.value == "DEPLOYMENT_FAILURE"


def test_pattern_category_values():
    assert PatternCategory.ARCHITECTURE.value == "ARCHITECTURE"
    assert PatternCategory.BUG_FIX.value == "BUG_FIX"
    assert PatternCategory.FILE_LAYOUT.value == "FILE_LAYOUT"
    assert PatternCategory.API_DESIGN.value == "API_DESIGN"
    assert PatternCategory.TESTING.value == "TESTING"
    assert PatternCategory.PROMPT_TEMPLATE.value == "PROMPT_TEMPLATE"


def test_playbook_archetype_values():
    assert PlaybookArchetype.REST_API.value == "REST_API"
    assert PlaybookArchetype.SPRING_BOOT.value == "SPRING_BOOT"
    assert PlaybookArchetype.PYTHON_CLI.value == "PYTHON_CLI"
    assert PlaybookArchetype.AI_AGENT.value == "AI_AGENT"
    assert PlaybookArchetype.WEB_DASHBOARD.value == "WEB_DASHBOARD"
    assert PlaybookArchetype.MICROSERVICES.value == "MICROSERVICES"
    assert PlaybookArchetype.AUTHENTICATION.value == "AUTHENTICATION"
    assert PlaybookArchetype.CRUD_APPLICATION.value == "CRUD_APPLICATION"
    assert PlaybookArchetype.EVENT_STREAMING.value == "EVENT_STREAMING"
    assert PlaybookArchetype.DISTRIBUTED_WORKER.value == "DISTRIBUTED_WORKER"


def test_reflection_scope_values():
    assert ReflectionScope.TASK.value == "TASK"
    assert ReflectionScope.SPRINT.value == "SPRINT"
    assert ReflectionScope.RELEASE.value == "RELEASE"
    assert ReflectionScope.MONTHLY.value == "MONTHLY"


def test_improvement_area_values():
    assert ImprovementArea.RETRY_ENGINE.value == "RETRY_ENGINE"
    assert ImprovementArea.PLANNING.value == "PLANNING"
    assert ImprovementArea.PROMPT_ENGINEERING.value == "PROMPT_ENGINEERING"
    assert ImprovementArea.TESTING_STRATEGY.value == "TESTING_STRATEGY"
    assert ImprovementArea.ORCHESTRATION.value == "ORCHESTRATION"
    assert ImprovementArea.ARCHITECTURE_MODELING.value == "ARCHITECTURE_MODELING"
    assert ImprovementArea.MEMORY_MANAGEMENT.value == "MEMORY_MANAGEMENT"
    assert ImprovementArea.SECURITY_GOVERNANCE.value == "SECURITY_GOVERNANCE"


def test_learning_event_serialization_roundtrip():
    event = LearningEvent(
        category=LearningEventType.BUG_FIXED,
        summary="Fixed race condition in token bucket",
        project="AutoDev",
        task="T-01",
        confidence=0.95,
        importance=80.0,
        affected_files=["core/ratelimit.py", "tests/test_ratelimit.py"],
        root_cause="Missing mutex lock during decrement",
        solution="Wrapped counter decrement in threading.Lock",
        metrics={"duration_ms": 12.5, "tests_passed": 5},
        tags=["concurrency", "thread-safety"],
    )
    d = event.to_dict()
    assert d["category"] == "BUG_FIXED"
    assert d["summary"] == "Fixed race condition in token bucket"
    assert d["affected_files"] == ["core/ratelimit.py", "tests/test_ratelimit.py"]

    json_str = event.to_json()
    assert isinstance(json_str, str)

    restored = LearningEvent.from_dict(d)
    assert restored.id == event.id
    assert restored.category == LearningEventType.BUG_FIXED
    assert restored.root_cause == event.root_cause
    assert restored.solution == event.solution
    assert restored.metrics["tests_passed"] == 5


def test_learning_session_serialization_roundtrip():
    event = LearningEvent(
        category=LearningEventType.PATTERN_DISCOVERED,
        summary="Repository Pattern with in-memory caching",
        project="PaymentGateway",
    )
    session = LearningSession(
        session_id="SESS-101",
        project="PaymentGateway",
        events=[event],
        metrics={"events_count": 1},
    )
    d = session.to_dict()
    assert d["session_id"] == "SESS-101"
    assert len(d["events"]) == 1

    restored = LearningSession.from_dict(d)
    assert restored.session_id == "SESS-101"
    assert len(restored.events) == 1
    assert restored.events[0].category == LearningEventType.PATTERN_DISCOVERED


def test_learning_snapshot_serialization_roundtrip():
    snapshot = LearningSnapshot(
        snapshot_id="SNAP-001",
        project="AutoDev",
        total_events=42,
        categories_count={"BUG_FIXED": 20, "PATTERN_DISCOVERED": 22},
        key_learnings=["Never mutate shared dict without lock"],
        average_confidence=0.91,
    )
    d = snapshot.to_dict()
    restored = LearningSnapshot.from_dict(d)
    assert restored.snapshot_id == "SNAP-001"
    assert restored.total_events == 42
    assert restored.average_confidence == 0.91
    assert restored.categories_count["BUG_FIXED"] == 20


def test_learning_knowledge_serialization_roundtrip():
    knowledge = LearningKnowledge(
        knowledge_id="KN-999",
        domain="Backend",
        topic="Database Connection Pooling",
        summary="Always set min/max pool size and pre-ping connections",
        details="Prevents stale TCP socket drops under heavy idle periods.",
        evidence_events=["EVT-01", "EVT-02"],
        confidence=0.98,
        utility_score=95.0,
        promoted=True,
    )
    d = knowledge.to_dict()
    restored = LearningKnowledge.from_dict(d)
    assert restored.knowledge_id == "KN-999"
    assert restored.promoted is True
    assert restored.confidence == 0.98
    assert len(restored.evidence_events) == 2


def test_engineering_pattern_serialization_roundtrip():
    pattern = EngineeringPattern(
        id="PAT-501",
        name="Clean Layered Architecture",
        category=PatternCategory.ARCHITECTURE,
        description="Strict domain -> service -> repository -> controller separation",
        structure_template={"models": "domain/models.py", "services": "core/services.py"},
        applicable_scenarios=["Enterprise Web APIs", "SaaS Backends"],
        usage_count=15,
        confidence=0.96,
        quality_score=92.5,
        success_rate=0.98,
    )
    d = pattern.to_dict()
    assert d["category"] == "ARCHITECTURE"
    assert d["usage_count"] == 15

    restored = EngineeringPattern.from_dict(d)
    assert restored.id == "PAT-501"
    assert restored.category == PatternCategory.ARCHITECTURE
    assert restored.confidence == 0.96
    assert restored.structure_template["models"] == "domain/models.py"


def test_reflection_report_serialization_roundtrip():
    report = ReflectionReport(
        id="REF-101",
        scope=ReflectionScope.TASK,
        target_id="TASK-88",
        what_worked=["Fast unit test execution", "Clean file generation"],
        what_failed=["Initial regex was too greedy"],
        root_causes=["Unescaped wildcard in regex pattern"],
        improvement_actions=["Use strict non-greedy token matching"],
        excessive_retries=False,
        planning_accuracy_score=94.0,
        tests_sufficient=True,
        prompt_too_large=False,
        metrics={"duration_s": 3.2, "retries": 1},
        summary="Task completed smoothly after single regex fix.",
    )
    d = report.to_dict()
    assert d["scope"] == "TASK"
    assert d["planning_accuracy_score"] == 94.0

    restored = ReflectionReport.from_dict(d)
    assert restored.id == "REF-101"
    assert restored.scope == ReflectionScope.TASK
    assert restored.tests_sufficient is True
    assert len(restored.what_worked) == 2


def test_prompt_optimization_record_serialization_roundtrip():
    record = PromptOptimizationRecord(
        template_id="TPL-01",
        task_type="coding",
        original_prompt="Please generate clean python code with lots of boilerplate...",
        optimized_prompt="Implement clean python module with SOLID principles and standard typing.",
        original_tokens=150,
        optimized_tokens=45,
        token_compression_ratio=0.70,
        retry_count=0,
        success_rate=1.0,
        token_efficiency_score=92.0,
        discovered_rules=["Explicit return types", "Never use global state"],
    )
    d = record.to_dict()
    assert d["task_type"] == "coding"
    assert d["token_compression_ratio"] == 0.70

    restored = PromptOptimizationRecord.from_dict(d)
    assert restored.template_id == "TPL-01"
    assert restored.token_efficiency_score == 92.0
    assert len(restored.discovered_rules) == 2


def test_architecture_recommendation_serialization_roundtrip():
    rec = ArchitectureRecommendation(
        recommendation_id="REC-701",
        requirement_summary="Build high-throughput payment transaction processor",
        recommended_folder_structure={"core": "Transaction pipeline", "db": "Ledger persistence"},
        design_patterns=["Transactional Outbox", "Repository Pattern"],
        database_recommendation="PostgreSQL with row-level locking",
        api_style="RESTful JSON with idempotency keys",
        testing_strategy="Pytest with SQLite in-memory fixture and mock gateways",
        security_model="HMAC-SHA256 signature verification and TLS 1.3",
        confidence_score=0.94,
        rationale="Matches financial ledger archetype from previous successful sprint.",
    )
    d = rec.to_dict()
    assert d["database_recommendation"] == "PostgreSQL with row-level locking"
    assert len(d["design_patterns"]) == 2

    restored = ArchitectureRecommendation.from_dict(d)
    assert restored.recommendation_id == "REC-701"
    assert restored.confidence_score == 0.94
    assert restored.api_style == "RESTful JSON with idempotency keys"


def test_engineering_playbook_serialization_roundtrip():
    playbook = EngineeringPlaybook(
        archetype=PlaybookArchetype.REST_API,
        title="Production REST API Standard Playbook",
        description="Full lifecycle guidelines for designing and building scalable REST services.",
        recommended_sequence=[
            "1. Define domain models & validation schemas",
            "2. Implement repository layer with thread-safe persistence",
            "3. Implement service handlers with error wrapping",
            "4. Wire REST controllers and endpoints",
            "5. Build unit and integration test suite",
        ],
        best_practices=["Use status code 201 for creation", "Standardize error envelope"],
        common_mistakes=["Leaking ORM entities directly to API response", "Ignoring timeout limits"],
        estimated_effort_hours=12.0,
        quality_metrics={"min_coverage": 90.0, "max_cyclomatic_complexity": 8},
        usage_count=8,
        success_rate=0.95,
    )
    d = playbook.to_dict()
    assert d["archetype"] == "REST_API"
    assert len(d["recommended_sequence"]) == 5

    restored = EngineeringPlaybook.from_dict(d)
    assert restored.archetype == PlaybookArchetype.REST_API
    assert restored.title == "Production REST API Standard Playbook"
    assert restored.quality_metrics["min_coverage"] == 90.0


def test_self_improvement_plan_serialization_roundtrip():
    item1 = ImprovementRoadmapItem(
        id="RMAP-01",
        area=ImprovementArea.RETRY_ENGINE,
        title="Enhance defect classification precision",
        description="Add AST-level diff analysis to pin compiler syntax errors automatically.",
        priority="P1",
        estimated_roi=85.0,
        effort_days=3.0,
        target_subsystem="RetryEngine",
        status="PLANNED",
    )
    plan = SelfImprovementPlan(
        plan_id="PLAN-OCT2026",
        evaluation_period="2026-10",
        weakest_subsystems=["RETRY_ENGINE", "PROMPT_ENGINEERING"],
        subsystem_health_scores={"RETRY_ENGINE": 72.0, "PLANNING": 94.0, "PROMPT_ENGINEERING": 78.0},
        roadmap_items=[item1],
        overall_health_score=81.3,
        executive_summary="Subsystem audit indicates prompt bloat and retry overhead require optimization.",
    )
    d = plan.to_dict()
    assert d["plan_id"] == "PLAN-OCT2026"
    assert len(d["roadmap_items"]) == 1

    restored = SelfImprovementPlan.from_dict(d)
    assert restored.plan_id == "PLAN-OCT2026"
    assert restored.roadmap_items[0].area == ImprovementArea.RETRY_ENGINE
    assert restored.subsystem_health_scores["RETRY_ENGINE"] == 72.0


def test_performance_evolution_record_serialization_roundtrip():
    rec = PerformanceEvolutionRecord(
        record_id="PERF-310",
        version="3.1.0",
        benchmark_name="MultiTaskOrchestrationBenchmark",
        execution_time_seconds=4.12,
        memory_usage_mb=34.5,
        planning_latency_ms=120.5,
        review_latency_ms=85.2,
        generation_latency_ms=310.0,
        speedup_vs_previous=1.28,
        memory_delta_vs_previous=-5.2,
        metrics={"total_tasks": 20, "throughput_tps": 4.85},
    )
    d = rec.to_dict()
    assert d["version"] == "3.1.0"
    assert d["speedup_vs_previous"] == 1.28

    restored = PerformanceEvolutionRecord.from_dict(d)
    assert restored.record_id == "PERF-310"
    assert restored.planning_latency_ms == 120.5
    assert restored.memory_delta_vs_previous == -5.2
