"""
tests/test_v27_edge_cases.py - Deep Edge Cases and Resilience Tests for AutoDev v2.7

Validates:
1. Empty workspace / 0 SLOC graceful handling
2. Deeply nested comprehension structures
3. God object with disjoint LCOM4 components
4. Strict mode QualityGate behavior
5. 100% duplicate workspace handling
6. Multi-level diamond inheritance resolution
7. MemoryManager query fallback when no historical matches exist
8. Multi-category risk score convergence and upper bounding
9. Heatmap generation across nested folder hierarchies
10. QualityGatePolicy JSON serialization / deserialization roundtrip
"""

import json
import pytest
from core.complexity_analyzer import ComplexityAnalyzer
from core.dependency_health import DependencyHealthAnalyzer
from core.duplication_detector import DuplicationDetector
from core.predictive_quality_engine import PredictiveQualityEngine
from core.quality_gate import QualityGate
from core.quality_models import (
    CodeLocation,
    ComplexityMetrics,
    DependencyHealthMetrics,
    PredictiveRiskScores,
    QualityAssessmentResult,
    QualityGatePolicy,
    QualityGateResult,
    QualityGateStatus,
    QualityIssue,
    QualityRiskCategory,
    QualitySeverity,
)
from core.risk_predictor import RiskPredictor


def test_empty_workspace_assessment(tmp_path):
    """Assessing an empty workspace yields zero technical debt and clean scores."""
    engine = PredictiveQualityEngine(workspace_path=str(tmp_path))
    result = engine.assess_workspace(files_content={})

    assert result.analyzed_files_count == 0
    assert result.total_sloc == 0
    assert result.overall_maintainability_index == 100.0
    assert result.total_technical_debt_minutes == 0
    assert result.gate_result.status == QualityGateStatus.PASSED


def test_deeply_nested_comprehension():
    """Analyzer computes nested comprehension complexity without crashing."""
    code = """
def nested_comp(data):
    return [
        x * y * z
        for sublist in data
        if sublist is not None
        for x in sublist
        if x > 0
        for y in range(x)
        if y % 2 == 0
        for z in [y, y + 1]
    ]
"""
    analyzer = ComplexityAnalyzer()
    metrics = analyzer.analyze_source(code)
    assert metrics.cyclomatic_complexity >= 4
    assert metrics.cognitive_complexity >= 4


def test_god_object_with_disjoint_lcom4():
    """Class with disconnected method clusters gets flagged for high LCOM4."""
    analyzer = DependencyHealthAnalyzer()
    code = """
class MultiConcernService:
    def __init__(self):
        self.auth_token = "abc"
        self.db_conn = "sql"
        self.cache = {}

    def login_user(self):
        return self.auth_token

    def execute_query(self):
        return self.db_conn

    def get_cached_item(self, k):
        return self.cache.get(k)
"""
    res = analyzer.analyze_code(code)
    assert res.lack_of_cohesion_lcom4 >= 2


def test_strict_quality_gate_mode():
    """Strict mode treats warnings as rejections."""
    policy = QualityGatePolicy(strict_mode=True, max_cyclomatic_complexity=10)
    gate = QualityGate(policy=policy)

    # Moderate complexity triggers warning or rejection in strict mode
    complexity = ComplexityMetrics(cyclomatic_complexity=12)
    dep_health = DependencyHealthMetrics()
    risks = PredictiveRiskScores(regression_probability=0.10, security_confidence=0.90)

    result = gate.evaluate(complexity, dep_health, risks, issues=[])
    assert result.status == QualityGateStatus.REJECTED
    assert not result.is_passed


def test_extreme_duplication_workspace(tmp_path):
    """Workspace with 100% duplicate modules is caught with high duplication density."""
    engine = PredictiveQualityEngine(workspace_path=str(tmp_path))
    identical_func = """
def process_data_block(items):
    res = []
    for item in items:
        if item.get("valid"):
            val = item.get("score", 0) * 2
            res.append(val)
    return res
"""
    files = {
        "service_a.py": identical_func,
        "service_b.py": identical_func,
        "service_c.py": identical_func,
    }
    result = engine.assess_workspace(files_content=files)
    assert len(result.duplications) >= 1
    assert result.duplication_percentage > 0.0


def test_multi_level_diamond_inheritance():
    """Analyzer handles complex multi-level diamond hierarchies."""
    analyzer = DependencyHealthAnalyzer()
    code = """
class BaseRoot:
    pass

class LeftBranch(BaseRoot):
    pass

class RightBranch(BaseRoot):
    pass

class SubLeft(LeftBranch):
    pass

class SubRight(RightBranch):
    pass

class DiamondChild(SubLeft, SubRight):
    pass
"""
    health = analyzer.analyze_code(code)
    assert health.diamond_inheritance_count >= 1
    assert len(health.diamond_inheritances) >= 1
    assert health.depth_of_inheritance >= 3


def test_memory_manager_no_match_graceful(tmp_path):
    """When MemoryManager returns no matches, risk estimation proceeds normally."""
    class EmptyMemoryManager:
        def search(self, query, limit=5, category=None):
            return []

    engine = PredictiveQualityEngine(workspace_path=str(tmp_path), memory_manager=EmptyMemoryManager())
    files = {"clean.py": "def add(a, b): return a + b\n"}
    result = engine.assess_workspace(files_content=files)
    assert result.historical_patterns_found == []
    assert result.gate_result.status == QualityGateStatus.PASSED


def test_multi_risk_convergence_and_bounding():
    """Predictor bounds all composite risk scores between 0.0 and 1.0 (or 0-100)."""
    predictor = RiskPredictor()
    worst_complexity = ComplexityMetrics(
        cyclomatic_complexity=150,
        cognitive_complexity=200,
        max_nesting_depth=12,
        longest_call_chain=15,
        maintainability_index=5.0,
    )
    worst_dep_health = DependencyHealthMetrics(
        instability=1.0,
        has_circular_dependencies=True,
        is_god_object=True,
    )
    critical_issues = [
        QualityIssue(
            rule_id="SEC-001",
            category=QualityRiskCategory.SECURITY_VULNERABILITY,
            severity=QualitySeverity.CRITICAL,
        ),
        QualityIssue(
            rule_id="RACE-001",
            category=QualityRiskCategory.THREAD_SAFETY_RACE,
            severity=QualitySeverity.HIGH,
        ),
    ]

    scores = predictor.predict_risks(
        complexity=worst_complexity,
        dependency_health=worst_dep_health,
        issues=critical_issues,
        duplication_count=20,
        historical_defects_count=5,
    )

    assert 0.0 <= scores.regression_probability <= 1.0
    assert 0.0 <= scores.overall_risk_score <= 1.0
    assert 0.0 <= scores.composite_risk_score <= 100.0
    assert scores.security_confidence <= 0.35
    assert scores.concurrency_race_risk > 0.50


def test_heatmap_generation_nested_hierarchy(tmp_path):
    """Engine computes risk heatmap across multi-directory trees."""
    engine = PredictiveQualityEngine(workspace_path=str(tmp_path))
    files = {
        "core/engine.py": "def heavy_work():\n" + "    if True:\n" * 5 + "        return 1\n",
        "utils/helpers.py": "def quick(): return 42\n",
        "api/v1/endpoints.py": "def endpoint(): return 'ok'\n",
    }
    result = engine.assess_workspace(files_content=files)
    assert len(result.heatmap_data) == 3
    # engine.py has higher complexity, thus higher risk weight
    assert result.heatmap_data["core/engine.py"] >= result.heatmap_data["utils/helpers.py"]


def test_quality_gate_policy_serialization_roundtrip():
    """QualityGatePolicy serializes to dict/JSON and deserializes correctly."""
    policy = QualityGatePolicy(
        max_cyclomatic_complexity=12,
        min_maintainability_index=55.0,
        allow_circular_dependencies=False,
    )
    data = policy.to_dict()
    assert data["max_cyclomatic_complexity"] == 12
    assert data["min_maintainability_index"] == 55.0
    assert data["disallow_circular_dependencies"] is True

    json_str = json.dumps(data)
    loaded_data = json.loads(json_str)
    recreated_policy = QualityGatePolicy(**{k: v for k, v in loaded_data.items() if k != "allow_circular_dependencies"})
    assert recreated_policy.max_cyclomatic_complexity == 12
    assert recreated_policy.min_maintainability_index == 55.0
