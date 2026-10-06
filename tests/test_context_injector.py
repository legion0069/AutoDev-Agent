"""
test_context_injector.py - Comprehensive Unit Tests for AutoDev ContextInjector

Tests memory retrieval, multi-factor deterministic ranking, duplicate removal,
token budget enforcement, section formatting, and integration with PromptBuilder.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from agents.task_planner_agent import Task
from core.context_injector import ContextInjector, ScoredMemory
from core.memory_manager import MemoryCategory, MemoryEntry, MemoryManager
from core.prompt_builder import PromptBuilder


@pytest.fixture
def temp_memory_file(tmp_path: Path) -> Path:
    """Provides a temporary path for project_memory.json."""
    return tmp_path / "memory" / "project_memory.json"


@pytest.fixture
def memory_manager(temp_memory_file: Path) -> MemoryManager:
    """Provides an initialized MemoryManager with populated engineering memories."""
    mgr = MemoryManager(memory_path=temp_memory_file, auto_create=True)

    # 1. Architecture memory
    mgr.add_memory(
        title="Repository Pattern for SQLite Access",
        content="Abstract all SQL database operations behind repository interfaces for easy mocking.",
        category=MemoryCategory.ARCHITECTURE,
        tags=["database", "sqlite", "repository", "solid"],
        importance=9,
        related_tasks=["DAY1-TASK01"],
        entry_id="mem_arch_db",
    )

    # 2. Bug memory
    mgr.add_memory(
        title="Windows File Lock on Temporary Rename",
        content="Catch PermissionError and retry with unique temp filenames and exponential backoff.",
        category=MemoryCategory.BUG,
        tags=["windows", "io", "atomic", "concurrency"],
        importance=8,
        related_tasks=["DAY1-TASK02"],
        entry_id="mem_bug_win",
    )

    # 3. Lesson / Pattern memory
    mgr.add_memory(
        title="Always Use Type Annotations in Public APIs",
        content="Enforce strict type hints and docstrings across all agent interfaces.",
        category=MemoryCategory.PATTERN,
        tags=["types", "python", "clean-code"],
        importance=7,
        entry_id="mem_pat_types",
    )

    # 4. Review memory
    mgr.add_memory(
        title="Validate File Path Traversal Defense",
        content="Verify that relative paths do not escape target workspace using Path.resolve().",
        category=MemoryCategory.REVIEW,
        tags=["security", "files", "path-traversal"],
        importance=10,
        entry_id="mem_rev_sec",
    )

    # 5. Testing memory
    mgr.add_memory(
        title="Pytest Test Discovery Standards",
        content="Place test files under tests/ directory named with test_ prefix.",
        category=MemoryCategory.TESTING,
        tags=["pytest", "tests", "testing"],
        importance=6,
        entry_id="mem_test_pytest",
    )

    # 6. TODO memory
    mgr.add_memory(
        title="Add Redis Caching Layer",
        content="Implement Redis cache in Day 3 for frequent query optimization.",
        category=MemoryCategory.TODO,
        tags=["redis", "cache", "performance"],
        importance=4,
        entry_id="mem_todo_redis",
    )

    return mgr


@pytest.fixture
def context_injector(memory_manager: MemoryManager) -> ContextInjector:
    """Provides a configured ContextInjector instance."""
    return ContextInjector(memory_manager=memory_manager, max_tokens=2500, max_memories=10)


@pytest.fixture
def sample_task() -> Task:
    """Provides a sample task targeting database repository implementation."""
    return Task(
        id="DAY1-TASK01",
        title="Implement SQLite Database Repository",
        description="Create repository class for storing project records in SQLite database safely.",
        priority=1,
        dependencies=[],
        estimated_files=["core/database.py", "core/repository.py"],
    )


@pytest.fixture
def sample_context() -> Dict[str, Any]:
    """Provides a sample project context dictionary."""
    return {
        "project_name": "TaskFlow",
        "technology_stack": "Python, SQLite, Pytest",
        "current_day": 1,
        "current_phase": {
            "phase_name": "Core Database Layer",
            "goals": ["Implement database models and repositories"],
            "deliverables": ["core/database.py"],
            "testing_focus": "Unit tests for database repositories",
        },
    }


# =============================================================================
# 1. Retrieval & Ranking Tests
# =============================================================================

def test_retrieve_relevant_memories_prioritizes_task_match(
    context_injector: ContextInjector,
    sample_context: Dict[str, Any],
    sample_task: Task,
):
    """Verifies that the database architecture memory is ranked #1 for a database task."""
    memories = context_injector.retrieve_relevant_memories(
        context=sample_context,
        task=sample_task,
        max_memories=5,
    )

    assert len(memories) > 0
    # Top memory must be the SQLite repository architecture memory
    assert memories[0].id == "mem_arch_db"
    assert "Repository Pattern" in memories[0].title


def test_ranking_weights_and_breakdown(
    context_injector: ContextInjector,
    sample_context: Dict[str, Any],
    sample_task: Task,
    memory_manager: MemoryManager,
):
    """Verifies ranking scores and non-zero breakdown components."""
    all_memories = list(memory_manager.load_memory().values())
    scored = context_injector.rank_memories(all_memories, task=sample_task, context=sample_context)

    assert len(scored) == len(all_memories)
    top = scored[0]
    assert top.entry.id == "mem_arch_db"
    assert top.score > scored[-1].score

    # Check breakdown dimensions
    assert "task_similarity" in top.relevance_breakdown
    assert "target_files" in top.relevance_breakdown
    assert "tags_and_tech" in top.relevance_breakdown
    assert "importance" in top.relevance_breakdown


# =============================================================================
# 2. Duplicate Removal Tests
# =============================================================================

def test_remove_duplicates_by_id_title_content(context_injector: ContextInjector):
    """Verifies that duplicate memories by ID, title, or content are filtered."""
    m1 = MemoryEntry(
        id="mem_01",
        timestamp="2026-10-06T12:00:00Z",
        category=MemoryCategory.ARCHITECTURE,
        title="Use SOLID Principles",
        content="Single responsibility per module.",
        importance=8,
    )
    # Duplicate ID
    m2 = MemoryEntry(
        id="mem_01",
        timestamp="2026-10-06T11:00:00Z",
        category=MemoryCategory.ARCHITECTURE,
        title="Different Title",
        content="Different content.",
        importance=5,
    )
    # Duplicate Title (different ID)
    m3 = MemoryEntry(
        id="mem_03",
        timestamp="2026-10-06T10:00:00Z",
        category=MemoryCategory.PATTERN,
        title="Use SOLID Principles",
        content="Another description.",
        importance=6,
    )
    # Duplicate Content (different ID & title)
    m4 = MemoryEntry(
        id="mem_04",
        timestamp="2026-10-06T09:00:00Z",
        category=MemoryCategory.LESSON,
        title="Architecture Rule",
        content="Single responsibility per module.",
        importance=4,
    )
    # Distinct entry
    m5 = MemoryEntry(
        id="mem_05",
        timestamp="2026-10-06T08:00:00Z",
        category=MemoryCategory.TESTING,
        title="Pytest Mocking",
        content="Use monkeypatch fixture.",
        importance=7,
    )

    deduped = context_injector.remove_duplicates([m1, m2, m3, m4, m5])
    assert len(deduped) == 2
    assert deduped[0].id == "mem_01"
    assert deduped[1].id == "mem_05"


# =============================================================================
# 3. Token Budgeting & Deterministic Truncation Tests
# =============================================================================

def test_token_budget_enforcement(
    context_injector: ContextInjector,
    sample_context: Dict[str, Any],
    sample_task: Task,
):
    """Verifies that small max_tokens limits truncate output while retaining top memories."""
    # Build with small token budget
    small_prompt = context_injector.build_prompt_context(
        context=sample_context,
        task=sample_task,
        max_tokens=80,
    )

    # Build with generous token budget
    large_prompt = context_injector.build_prompt_context(
        context=sample_context,
        task=sample_task,
        max_tokens=3000,
    )

    assert len(small_prompt) < len(large_prompt)
    # Top ranked item must be present in both
    assert "mem_arch_db" in small_prompt
    assert "mem_arch_db" in large_prompt


# =============================================================================
# 4. Empty & Large Store Tests
# =============================================================================

def test_empty_memory_store_returns_empty_prompt_block(tmp_path: Path, sample_context: Dict[str, Any], sample_task: Task):
    """Verifies that an empty memory manager returns empty string without error."""
    empty_mgr = MemoryManager(memory_path=tmp_path / "empty_mem.json", auto_create=True)
    injector = ContextInjector(memory_manager=empty_mgr)

    memories = injector.retrieve_relevant_memories(sample_context, sample_task)
    assert memories == []

    prompt_block = injector.build_prompt_context(sample_context, sample_task)
    assert prompt_block == ""


def test_large_memory_store_handling(tmp_path: Path, sample_context: Dict[str, Any], sample_task: Task):
    """Verifies ranking and retrieval across 100+ memory entries."""
    large_mgr = MemoryManager(memory_path=tmp_path / "large_mem.json", auto_create=True)
    for i in range(100):
        large_mgr.add_memory(
            title=f"Generic Note #{i}",
            content=f"Some generic engineering detail #{i}",
            category=MemoryCategory.TODO if i % 2 == 0 else MemoryCategory.PATTERN,
            importance=i % 10,
            entry_id=f"mem_gen_{i:03d}",
        )

    # Add 1 highly relevant target
    large_mgr.add_memory(
        title="SQLite Repository Implementation Spec",
        content="Target details for SQLite Database Repository DAY1-TASK01",
        category=MemoryCategory.ARCHITECTURE,
        tags=["sqlite", "database"],
        importance=10,
        related_tasks=["DAY1-TASK01"],
        entry_id="mem_target_high",
    )

    injector = ContextInjector(memory_manager=large_mgr, max_memories=5)
    retrieved = injector.retrieve_relevant_memories(sample_context, sample_task)

    assert len(retrieved) == 5
    assert retrieved[0].id == "mem_target_high"


# =============================================================================
# 5. Output Formatting & Categorization Tests
# =============================================================================

def test_build_prompt_context_section_headers(
    context_injector: ContextInjector,
    sample_context: Dict[str, Any],
    sample_task: Task,
):
    """Verifies that formatted prompt contains structured section headers."""
    prompt_text = context_injector.build_prompt_context(sample_context, sample_task)

    assert "PROJECT MEMORY & RELEVANT ENGINEERING CONTEXT" in prompt_text
    assert "### Architecture Decisions" in prompt_text
    assert "### Common Bugs & Pitfalls" in prompt_text
    assert "### Reviewer Directives & Quality Feedback" in prompt_text


# =============================================================================
# 6. Integration with PromptBuilder Tests
# =============================================================================

def test_prompt_builder_integration_with_context_injector(
    context_injector: ContextInjector,
    sample_context: Dict[str, Any],
    sample_task: Task,
):
    """Verifies that PromptBuilder automatically includes injected memory section."""
    builder = PromptBuilder(context_injector=context_injector)
    full_prompt = builder.build(context=sample_context, task=sample_task)

    # Check that system role, project info, and memory appear in order
    assert "1. SYSTEM ROLE" in full_prompt
    assert "2. PROJECT INFORMATION" in full_prompt
    assert "PROJECT MEMORY & RELEVANT ENGINEERING CONTEXT" in full_prompt
    assert "CURRENT TASK TO IMPLEMENT" in full_prompt
    assert "ENGINEERING CONSTRAINTS" in full_prompt
    assert "REQUIRED JSON OUTPUT FORMAT" in full_prompt

    # Verify memory content is present
    assert "Repository Pattern for SQLite Access" in full_prompt


def test_prompt_builder_without_memories_cleanly_omits_section(
    tmp_path: Path,
    sample_context: Dict[str, Any],
    sample_task: Task,
):
    """Verifies that PromptBuilder cleanly omits the memory block when store is empty."""
    empty_mgr = MemoryManager(memory_path=tmp_path / "empty_store.json", auto_create=True)
    builder = PromptBuilder(memory_manager=empty_mgr)

    full_prompt = builder.build(context=sample_context, task=sample_task)
    assert "PROJECT MEMORY & RELEVANT ENGINEERING CONTEXT" not in full_prompt
    assert "CURRENT TASK TO IMPLEMENT" in full_prompt


def test_deterministic_output(
    context_injector: ContextInjector,
    sample_context: Dict[str, Any],
    sample_task: Task,
):
    """Verifies that repeated invocations produce byte-for-byte identical output."""
    output_1 = context_injector.build_prompt_context(sample_context, sample_task)
    output_2 = context_injector.build_prompt_context(sample_context, sample_task)
    assert output_1 == output_2
