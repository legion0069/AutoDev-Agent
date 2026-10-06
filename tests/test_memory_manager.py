"""
test_memory_manager.py - Comprehensive Unit Tests for AutoDev MemoryManager

Tests memory entry creation, deterministic semantic search ranking, tag/category filtering,
summarization, statistics, atomic file persistence, corruption auto-recovery, and import/export.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.memory_manager import (
    MemoryCategory,
    MemoryEntry,
    MemoryManager,
    MemorySearchResult,
    MemoryStatistics,
    MemoryValidationError,
)


@pytest.fixture
def temp_memory_file(tmp_path: Path) -> Path:
    """Provides a temporary path for project_memory.json."""
    return tmp_path / "memory" / "project_memory.json"


@pytest.fixture
def memory_manager(temp_memory_file: Path) -> MemoryManager:
    """Provides an initialized MemoryManager with a clean temporary file."""
    return MemoryManager(memory_path=temp_memory_file, auto_create=True)


# =============================================================================
# 1. Memory Creation & Validation Tests
# =============================================================================

def test_add_valid_memory(memory_manager: MemoryManager):
    """Verifies adding a valid memory entry persists and returns MemoryEntry."""
    entry = memory_manager.add_memory(
        title="Use Repository Pattern for Database Access",
        content="Abstract all DB queries behind repository interfaces to facilitate mocking.",
        category=MemoryCategory.ARCHITECTURE,
        tags=["database", "repository", "architecture"],
        importance=8,
        related_tasks=["DAY1-TASK01"],
        entry_id="mem_arch_001",
    )

    assert entry.id == "mem_arch_001"
    assert entry.title == "Use Repository Pattern for Database Access"
    assert entry.category == "ARCHITECTURE"
    assert entry.importance == 8
    assert "database" in entry.tags
    assert "DAY1-TASK01" in entry.related_tasks

    # Verify retrieval
    retrieved = memory_manager.get_memory("mem_arch_001")
    assert retrieved is not None
    assert retrieved.title == entry.title


def test_add_memory_rejects_empty_title(memory_manager: MemoryManager):
    """Verifies that empty or whitespace title raises MemoryValidationError."""
    with pytest.raises(MemoryValidationError) as exc_info:
        memory_manager.add_memory(
            title="   ",
            content="Some content",
            category=MemoryCategory.BUG,
        )
    assert "title cannot be empty" in str(exc_info.value).lower()


def test_add_memory_rejects_empty_content(memory_manager: MemoryManager):
    """Verifies that empty content raises MemoryValidationError."""
    with pytest.raises(MemoryValidationError) as exc_info:
        memory_manager.add_memory(
            title="Valid Title",
            content="",
            category=MemoryCategory.DECISION,
        )
    assert "content cannot be empty" in str(exc_info.value).lower()


def test_add_memory_rejects_invalid_category(memory_manager: MemoryManager):
    """Verifies that invalid category raises MemoryValidationError."""
    with pytest.raises(MemoryValidationError) as exc_info:
        memory_manager.add_memory(
            title="Valid Title",
            content="Valid content",
            category="RANDOM_INVALID_CATEGORY",
        )
    assert "invalid memory category" in str(exc_info.value).lower()


def test_add_memory_rejects_negative_importance(memory_manager: MemoryManager):
    """Verifies that negative importance values are rejected."""
    with pytest.raises(MemoryValidationError) as exc_info:
        memory_manager.add_memory(
            title="Title",
            content="Content",
            category=MemoryCategory.LESSON,
            importance=-5,
        )
    assert "non-negative integer" in str(exc_info.value).lower()


def test_add_memory_rejects_duplicate_id(memory_manager: MemoryManager):
    """Verifies that attempting to add an entry with an existing ID fails."""
    memory_manager.add_memory(
        title="First",
        content="Content 1",
        category=MemoryCategory.PATTERN,
        entry_id="unique_id_123",
    )

    with pytest.raises(MemoryValidationError) as exc_info:
        memory_manager.add_memory(
            title="Second",
            content="Content 2",
            category=MemoryCategory.PATTERN,
            entry_id="unique_id_123",
        )
    assert "already exists" in str(exc_info.value).lower()


# =============================================================================
# 2. Persistence & Auto-Recovery Tests
# =============================================================================

def test_auto_create_memory_file(temp_memory_file: Path):
    """Verifies that MemoryManager creates the file and parent dirs on init."""
    assert not temp_memory_file.exists()
    mgr = MemoryManager(memory_path=temp_memory_file, auto_create=True)
    assert temp_memory_file.exists()
    assert mgr.statistics().total_entries == 0


def test_data_persists_across_instances(temp_memory_file: Path):
    """Verifies that saved memories reload correctly in a new MemoryManager instance."""
    mgr1 = MemoryManager(memory_path=temp_memory_file, auto_create=True)
    mgr1.add_memory(
        title="Avoid Global State",
        content="Always pass dependencies explicitly via constructor parameters.",
        category=MemoryCategory.DECISION,
        tags=["solid", "di"],
        importance=9,
        entry_id="mem_di_01",
    )

    # Reload from disk
    mgr2 = MemoryManager(memory_path=temp_memory_file)
    entry = mgr2.get_memory("mem_di_01")
    assert entry is not None
    assert entry.title == "Avoid Global State"
    assert entry.importance == 9
    assert entry.tags == ["solid", "di"]


def test_corrupted_json_auto_recovery(temp_memory_file: Path):
    """Verifies that corrupted JSON is backed up and a clean store initialized."""
    temp_memory_file.parent.mkdir(parents=True, exist_ok=True)
    temp_memory_file.write_text("{ MALFORMED_JSON ::: invalid syntax }", encoding="utf-8")

    mgr = MemoryManager(memory_path=temp_memory_file, auto_create=True)
    assert mgr.statistics().total_entries == 0

    # Verify backup file was created
    backups = list(temp_memory_file.parent.glob("project_memory.json.corrupted.*.bak"))
    assert len(backups) == 1
    assert "MALFORMED_JSON" in backups[0].read_text(encoding="utf-8")


# =============================================================================
# 3. CRUD Operations Tests
# =============================================================================

def test_update_memory_entry(memory_manager: MemoryManager):
    """Verifies updating fields of an existing memory entry."""
    entry = memory_manager.add_memory(
        title="Initial Title",
        content="Initial Content",
        category=MemoryCategory.TODO,
        importance=1,
        entry_id="mem_todo_1",
    )

    updated = memory_manager.update(
        entry_id="mem_todo_1",
        title="Updated Title",
        content="Updated Content",
        category=MemoryCategory.OPTIMIZATION,
        importance=7,
        tags=["perf", "caching"],
    )

    assert updated.title == "Updated Title"
    assert updated.content == "Updated Content"
    assert updated.category == "OPTIMIZATION"
    assert updated.importance == 7
    assert updated.tags == ["perf", "caching"]

    # Verify persistence
    reloaded = memory_manager.get_memory("mem_todo_1")
    assert reloaded.title == "Updated Title"
    assert reloaded.category == "OPTIMIZATION"


def test_update_nonexistent_entry_raises_key_error(memory_manager: MemoryManager):
    """Verifies updating a nonexistent ID raises KeyError."""
    with pytest.raises(KeyError):
        memory_manager.update(entry_id="nonexistent_id", title="New Title")


def test_delete_memory_entry(memory_manager: MemoryManager):
    """Verifies deleting an existing entry."""
    memory_manager.add_memory(
        title="Temporary Note",
        content="To be deleted",
        category=MemoryCategory.LESSON,
        entry_id="mem_temp",
    )

    assert memory_manager.get_memory("mem_temp") is not None
    deleted = memory_manager.delete("mem_temp")
    assert deleted is True
    assert memory_manager.get_memory("mem_temp") is None

    # Deleting again returns False
    assert memory_manager.delete("mem_temp") is False


def test_clear_all_memories(memory_manager: MemoryManager):
    """Verifies clear wipes all entries."""
    memory_manager.add_memory("T1", "C1", MemoryCategory.BUG)
    memory_manager.add_memory("T2", "C2", MemoryCategory.TODO)
    assert memory_manager.statistics().total_entries == 2

    memory_manager.clear()
    assert memory_manager.statistics().total_entries == 0
    assert memory_manager.get_recent() == []


# =============================================================================
# 4. Deterministic Search & Ranking Tests
# =============================================================================

def test_search_by_title_similarity_and_ranking(memory_manager: MemoryManager):
    """Verifies that exact and title-matching entries score higher."""
    memory_manager.add_memory(
        title="FastAPI SQLite Database Connection",
        content="Configure connection pooling with SQLite for background workers.",
        category=MemoryCategory.ARCHITECTURE,
        tags=["fastapi", "sqlite", "database"],
        importance=8,
        entry_id="mem_db_1",
    )
    memory_manager.add_memory(
        title="User Authentication JWT",
        content="JWT token expiration set to 24 hours. SQLite mentioned in passing.",
        category=MemoryCategory.IMPLEMENTATION,
        tags=["auth", "jwt"],
        importance=5,
        entry_id="mem_auth_1",
    )
    memory_manager.add_memory(
        title="CSS Styling Standards",
        content="Vanilla CSS color palette definition.",
        category=MemoryCategory.PATTERN,
        tags=["frontend", "css"],
        importance=3,
        entry_id="mem_css_1",
    )

    results = memory_manager.search(query="SQLite Database")
    assert len(results) >= 2
    # The dedicated DB architecture memory must rank first
    assert results[0].entry.id == "mem_db_1"
    assert results[0].score > results[1].score


def test_search_with_category_filter(memory_manager: MemoryManager):
    """Verifies searching with a category filter restricts results."""
    memory_manager.add_memory(
        title="Auth Bug in Token Parsing",
        content="Malformed header causes 500 error in auth.",
        category=MemoryCategory.BUG,
        tags=["auth", "bug"],
        importance=7,
    )
    memory_manager.add_memory(
        title="Auth Architecture Pattern",
        content="Use OAuth2 password flow with JWT.",
        category=MemoryCategory.ARCHITECTURE,
        tags=["auth", "jwt"],
        importance=8,
    )

    bug_results = memory_manager.search(query="Auth", category=MemoryCategory.BUG)
    assert len(bug_results) == 1
    assert bug_results[0].entry.category == "BUG"


def test_search_with_tag_filter(memory_manager: MemoryManager):
    """Verifies searching with a tag filter restricts results."""
    memory_manager.add_memory(
        title="Rate Limiter Implementation",
        content="Token bucket algorithm for API rate limiting.",
        category=MemoryCategory.IMPLEMENTATION,
        tags=["security", "rate-limit"],
    )
    memory_manager.add_memory(
        title="CORS Configuration",
        content="Allow all origins during local dev.",
        category=MemoryCategory.ARCHITECTURE,
        tags=["web", "security"],
    )

    results = memory_manager.search(query="API", tag="rate-limit")
    assert len(results) == 1
    assert "rate-limit" in results[0].entry.tags


def test_search_empty_query_returns_importance_ordered_results(memory_manager: MemoryManager):
    """Verifies searching with empty string returns entries ranked by importance and recency."""
    memory_manager.add_memory("Low Importance", "Content", MemoryCategory.TODO, importance=2)
    memory_manager.add_memory("High Importance", "Content", MemoryCategory.ARCHITECTURE, importance=10)

    results = memory_manager.search(query="", limit=5)
    assert len(results) == 2
    assert results[0].entry.title == "High Importance"


# =============================================================================
# 5. Tag, Category, and Recency Retrieval Tests
# =============================================================================

def test_search_by_tag(memory_manager: MemoryManager):
    """Verifies search_by_tag retrieves exact matching entries."""
    memory_manager.add_memory("T1", "C1", MemoryCategory.BUG, tags=["pytest", "flaky"])
    memory_manager.add_memory("T2", "C2", MemoryCategory.TESTING, tags=["pytest", "coverage"])
    memory_manager.add_memory("T3", "C3", MemoryCategory.PATTERN, tags=["solid"])

    pytest_memories = memory_manager.search_by_tag("pytest")
    assert len(pytest_memories) == 2
    assert all("pytest" in m.tags for m in pytest_memories)


def test_search_by_category(memory_manager: MemoryManager):
    """Verifies search_by_category retrieves entries for the requested category."""
    memory_manager.add_memory("Arch 1", "Content", MemoryCategory.ARCHITECTURE, importance=5)
    memory_manager.add_memory("Arch 2", "Content", MemoryCategory.ARCHITECTURE, importance=9)
    memory_manager.add_memory("Bug 1", "Content", MemoryCategory.BUG, importance=4)

    arch_entries = memory_manager.search_by_category(MemoryCategory.ARCHITECTURE)
    assert len(arch_entries) == 2
    assert arch_entries[0].importance == 9  # Sorted by importance descending


def test_get_recent_memories(memory_manager: MemoryManager):
    """Verifies get_recent returns items sorted newest to oldest."""
    memory_manager.add_memory("Oldest", "C1", MemoryCategory.TODO, timestamp="2026-01-01T10:00:00Z")
    memory_manager.add_memory("Middle", "C2", MemoryCategory.TODO, timestamp="2026-02-01T10:00:00Z")
    memory_manager.add_memory("Newest", "C3", MemoryCategory.TODO, timestamp="2026-03-01T10:00:00Z")

    recent = memory_manager.get_recent(limit=2)
    assert len(recent) == 2
    assert recent[0].title == "Newest"
    assert recent[1].title == "Middle"


# =============================================================================
# 6. Summarization Tests
# =============================================================================

def test_summarize_project_memory(memory_manager: MemoryManager):
    """Verifies structured categorization of project memory."""
    memory_manager.add_memory(
        title="Microservices Boundary",
        content="Split services by domain context.",
        category=MemoryCategory.ARCHITECTURE,
    )
    memory_manager.add_memory(
        title="File Locking on Windows",
        content="Use retry loops with unique temp filenames.",
        category=MemoryCategory.BUG,
    )
    memory_manager.add_memory(
        title="Always Use Type Hints",
        content="Enforce strict typing across all modules.",
        category=MemoryCategory.PATTERN,
    )
    memory_manager.add_memory(
        title="Add Redis Caching",
        content="Implement Redis cache in Phase 3.",
        category=MemoryCategory.TODO,
    )
    memory_manager.add_memory(
        title="Check Boundary Conditions",
        content="Ensure empty lists do not raise index errors.",
        category=MemoryCategory.REVIEW,
    )

    summary = memory_manager.summarize_project_memory()
    assert len(summary["important_architecture_decisions"]) == 1
    assert "Microservices Boundary" in summary["important_architecture_decisions"][0]

    assert len(summary["common_failures"]) == 1
    assert "File Locking on Windows" in summary["common_failures"][0]

    assert len(summary["coding_conventions"]) == 1
    assert "Always Use Type Hints" in summary["coding_conventions"][0]

    assert len(summary["unresolved_todos"]) == 1
    assert "Add Redis Caching" in summary["unresolved_todos"][0]

    assert len(summary["recurring_review_comments"]) == 1
    assert "Check Boundary Conditions" in summary["recurring_review_comments"][0]


def test_format_summary_for_prompt(memory_manager: MemoryManager):
    """Verifies markdown prompt formatting."""
    memory_manager.add_memory("Modular Architecture", "Separate core from agents.", MemoryCategory.ARCHITECTURE)
    memory_manager.add_memory("Flaky Test on Socket", "Use mock socket server.", MemoryCategory.LESSON)

    prompt_md = memory_manager.format_summary_for_prompt()
    assert "### Key Architectural Decisions" in prompt_md
    assert "Modular Architecture" in prompt_md
    assert "### Known Bugs & Lessons Learned" in prompt_md
    assert "Flaky Test on Socket" in prompt_md


def test_format_summary_for_empty_memory(memory_manager: MemoryManager):
    """Verifies markdown formatting when memory is empty."""
    prompt_md = memory_manager.format_summary_for_prompt()
    assert "No previous engineering memory recorded" in prompt_md


# =============================================================================
# 7. Statistics & Telemetry Tests
# =============================================================================

def test_statistics_calculation(memory_manager: MemoryManager):
    """Verifies computation of total entries, categories, and average importance."""
    memory_manager.add_memory("A", "C", MemoryCategory.ARCHITECTURE, importance=10, timestamp="2026-01-01T00:00:00Z")
    memory_manager.add_memory("B", "C", MemoryCategory.BUG, importance=6, timestamp="2026-02-01T00:00:00Z")
    memory_manager.add_memory("C", "C", MemoryCategory.BUG, importance=2, timestamp="2026-03-01T00:00:00Z")

    stats = memory_manager.statistics()
    assert stats.total_entries == 3
    assert stats.categories[MemoryCategory.ARCHITECTURE] == 1
    assert stats.categories[MemoryCategory.BUG] == 2
    assert stats.average_importance == 6.0  # (10 + 6 + 2) / 3
    assert stats.oldest_entry == "2026-01-01T00:00:00Z"
    assert stats.newest_entry == "2026-03-01T00:00:00Z"

    # Dict serialization
    stats_dict = stats.to_dict()
    assert stats_dict["total_entries"] == 3
    assert stats_dict["average_importance"] == 6.0


# =============================================================================
# 8. Export / Import Tests
# =============================================================================

def test_export_and_import_json(memory_manager: MemoryManager, tmp_path: Path):
    """Verifies exporting memory to a file and importing into a separate instance."""
    memory_manager.add_memory("M1", "Content 1", MemoryCategory.ARCHITECTURE, tags=["tag1"], importance=5, entry_id="id_1")
    memory_manager.add_memory("M2", "Content 2", MemoryCategory.BUG, tags=["tag2"], importance=8, entry_id="id_2")

    export_file = tmp_path / "export" / "backup_memory.json"
    exported_str = memory_manager.export_json(filepath=export_file)

    assert export_file.exists()
    assert "id_1" in exported_str
    assert "id_2" in exported_str

    # Create new fresh MemoryManager and import
    new_memory_file = tmp_path / "new_memory" / "project_memory.json"
    new_mgr = MemoryManager(memory_path=new_memory_file, auto_create=True)
    assert new_mgr.statistics().total_entries == 0

    count = new_mgr.import_json(export_file)
    assert count == 2
    assert new_mgr.get_memory("id_1") is not None
    assert new_mgr.get_memory("id_2") is not None
    assert new_mgr.statistics().total_entries == 2
