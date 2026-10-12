"""
tests/test_predictive_quality_engine.py - Unit tests for Predictive Quality Engine (v2.7)

Validates:
- End-to-end workspace assessment pipeline
- Incremental caching using SHA-256 hashes
- Single code snippet evaluation
- Historical defect learning integration via MemoryManager
- Rejection handling and recommendations synthesis
"""

import pytest
from core.predictive_quality_engine import PredictiveQualityEngine
from core.quality_models import (
    QualityAssessmentResult,
    QualityGatePolicy,
    QualityGateStatus,
    QualitySeverity,
)


def test_assess_single_code_snippet(tmp_path):
    """Assesses a single Python code snippet in isolation."""
    engine = PredictiveQualityEngine(workspace_path=str(tmp_path))
    code = """
def process_user_records(records):
    results = []
    for r in records:
        if r.get("active"):
            results.append(r["name"])
    return results
"""
    result = engine.assess_code(code, file_path="users.py")
    assert isinstance(result, QualityAssessmentResult)
    assert result.aggregate_complexity.maintainability_index > 70.0
    assert result.gate_result.status == QualityGateStatus.PASSED


def test_workspace_assessment_with_caching(tmp_path):
    """Verifies that incremental assessment utilizes the SHA-256 cache without recalculation."""
    engine = PredictiveQualityEngine(workspace_path=str(tmp_path))
    files = {
        "module_one.py": "def f1(): return 1\n",
        "module_two.py": "def f2(): return 2\n",
    }

    # First run populates cache
    res1 = engine.assess_workspace(files_content=files)
    assert len(engine._file_cache) == 2

    # Second run with same content uses cache
    res2 = engine.assess_workspace(files_content=files)
    assert res1.aggregate_complexity.sloc == res2.aggregate_complexity.sloc

    # Modifying one file updates its cache entry
    files["module_one.py"] = "def f1():\n    if True:\n        return 1\n"
    res3 = engine.assess_workspace(files_content=files)
    assert res3.aggregate_complexity.cyclomatic_complexity >= res1.aggregate_complexity.cyclomatic_complexity


def test_workspace_with_memory_manager_integration(tmp_path):
    """Engine checks MemoryManager for historical regressions or bad patterns."""
    class MockMemoryManager:
        def search(self, query, limit=5, category=None):
            from core.memory_manager import ScoredMemory, MemoryEntry, MemoryCategory
            entry = MemoryEntry(
                id="mem-001",
                category=MemoryCategory.LESSON_LEARNED,
                title="Circular import regression in auth module",
                content="Avoid direct import of users in auth middleware",
                tags=["regression", "auth", "circular_import"],
            )
            return [ScoredMemory(entry=entry, score=0.92, match_reason="Historical regression match")]

    mock_memory = MockMemoryManager()
    engine = PredictiveQualityEngine(workspace_path=str(tmp_path), memory_manager=mock_memory)

    files = {
        "auth/middleware.py": "from auth.users import get_current_user\n",
        "auth/users.py": "from auth.middleware import check_auth\n",
    }
    result = engine.assess_workspace(files_content=files)
    assert result.dependency_health.has_circular_dependencies is True
    assert result.risk_scores.regression_probability > 0.30


def test_strict_quality_gate_policy_rejection(tmp_path):
    """Engine enforces strict custom QualityGatePolicy thresholds."""
    strict_policy = QualityGatePolicy(
        max_cyclomatic_complexity=5,
        min_maintainability_index=85.0,
    )
    engine = PredictiveQualityEngine(workspace_path=str(tmp_path), gate_policy=strict_policy)

    complex_code = """
def complex_routine(a, b, c, d, e):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return 42
    return 0
"""
    files = {"nested.py": complex_code}
    result = engine.assess_workspace(files_content=files)
    assert result.gate_result.status == QualityGateStatus.REJECTED
    assert len(result.gate_result.refactoring_suggestions) >= 1
