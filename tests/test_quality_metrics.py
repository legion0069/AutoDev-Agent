"""
tests/test_quality_metrics.py - Unit tests for AutoDev Quality Metrics (v2.7)

Validates deterministic mathematical implementations of:
- Halstead Software Science metrics (Volume, Length, Vocabulary)
- Maintainability Index (SEI normalized formula)
- Martin's Package Coupling & Stability (Instability, Abstractness, Distance from Main Sequence)
- LCOM4 Cohesion (connected components graph)
- Composite Risk Scoring (weighted regression, complexity, instability, security, history)
"""

import math
import pytest

from core.quality_metrics import (
    calculate_halstead_volume,
    calculate_maintainability_index,
    calculate_instability,
    calculate_martin_instability,
    calculate_abstractness,
    calculate_martin_abstractness,
    calculate_distance_main_sequence,
    calculate_distance_from_main_sequence,
    calculate_lcom4,
    calculate_composite_risk_score,
)


def test_halstead_volume_empty():
    """Empty operators and operands should return 0 volume."""
    length, vocab, volume = calculate_halstead_volume([], [])
    assert length == 0
    assert vocab == 0
    assert volume == 0.0


def test_halstead_volume_single_element():
    """Single operator should return 0 volume as vocabulary <= 1."""
    length, vocab, volume = calculate_halstead_volume(["+"], [])
    assert length == 1
    assert vocab == 1
    assert volume == 0.0


def test_halstead_volume_standard_calculation():
    """Calculates exact N * log2(eta)."""
    operators = ["+", "-", "*", "+", "+"]  # length 5, distinct 3
    operands = ["a", "b", "c", "a"]        # length 4, distinct 3
    # total length = 9, vocabulary = 6, volume = 9 * log2(6)
    expected_vol = 9 * math.log2(6)
    length, vocab, volume = calculate_halstead_volume(operators, operands)
    assert length == 9
    assert vocab == 6
    assert abs(volume - expected_vol) < 1e-5


def test_maintainability_index_clean_code():
    """Clean, low complexity code with comments should have high MI."""
    mi = calculate_maintainability_index(
        halstead_volume=50.0,
        cyclomatic_complexity=1,
        sloc=10,
        comment_ratio=0.3,
    )
    assert 70.0 <= mi <= 100.0


def test_maintainability_index_complex_code():
    """High cyclomatic complexity and large SLOC should degrade MI."""
    mi = calculate_maintainability_index(
        halstead_volume=50000.0,
        cyclomatic_complexity=50,
        sloc=2000,
        comment_ratio=0.0,
    )
    assert mi < 50.0
    assert mi >= 0.0


def test_maintainability_index_bounds():
    """Maintainability Index must strictly stay in [0.0, 100.0]."""
    extreme_low = calculate_maintainability_index(1e9, 1000, 100000, 0.0)
    assert extreme_low == 0.0

    extreme_high = calculate_maintainability_index(1.0, 1, 1, 1.0)
    assert 0.0 <= extreme_high <= 100.0


def test_martin_instability():
    """Martin's instability I = Ce / (Ca + Ce)."""
    # 0 dependencies in and out -> 0.0
    assert calculate_instability(0, 0) == 0.0
    assert calculate_martin_instability(0, 0) == 0.0

    # Highly stable (Ca=20, Ce=0) -> 0.0
    assert calculate_instability(20, 0) == 0.0

    # Highly unstable (Ca=0, Ce=10) -> 1.0
    assert calculate_instability(0, 10) == 1.0

    # Balanced (Ca=5, Ce=5) -> 0.5
    assert calculate_instability(5, 5) == 0.5


def test_martin_abstractness():
    """Martin's abstractness A = Na / Nc."""
    assert calculate_abstractness(0, 0) == 0.0
    assert calculate_martin_abstractness(0, 10) == 0.0
    assert calculate_abstractness(5, 10) == 0.5
    assert calculate_abstractness(10, 10) == 1.0


def test_distance_from_main_sequence():
    """D = |A + I - 1.0|."""
    # Optimal point on main sequence (A=1.0, I=0.0 or A=0.5, I=0.5)
    assert calculate_distance_main_sequence(1.0, 0.0) == 0.0
    assert calculate_distance_from_main_sequence(0.5, 0.5) == 0.0

    # Zone of Pain (A=0.0, I=0.0)
    assert calculate_distance_main_sequence(0.0, 0.0) == 1.0

    # Zone of Uselessness (A=1.0, I=1.0)
    assert calculate_distance_main_sequence(1.0, 1.0) == 1.0


def test_lcom4_empty_and_single_method():
    """LCOM4 for 0 or 1 method."""
    assert calculate_lcom4([], {}) == 0
    assert calculate_lcom4(["do_work"], {"do_work": {"x"}}) == 1


def test_lcom4_shared_fields():
    """Methods sharing fields form a single connected component (LCOM4 = 1)."""
    methods = ["m1", "m2", "m3"]
    field_accesses = {
        "m1": {"a", "b"},
        "m2": {"b", "c"},  # shares 'b' with m1
        "m3": {"c", "d"},  # shares 'c' with m2
    }
    assert calculate_lcom4(methods, field_accesses) == 1


def test_lcom4_disjoint_components():
    """Methods operating on disjoint fields form multiple components (LCOM4 > 1)."""
    methods = ["user_login", "user_logout", "render_chart", "export_pdf"]
    field_accesses = {
        "user_login": {"session_token", "user_id"},
        "user_logout": {"session_token"},
        "render_chart": {"canvas_width", "colors"},
        "export_pdf": {"canvas_width", "page_orientation"},
    }
    # 2 distinct clusters: auth & chart/pdf
    assert calculate_lcom4(methods, field_accesses) == 2


def test_lcom4_method_invocation_coupling():
    """Direct method invocation links methods even without shared fields."""
    methods = ["step_a", "step_b"]
    field_accesses = {"step_a": set(), "step_b": set()}
    method_calls = {"step_a": {"step_b"}}
    assert calculate_lcom4(methods, field_accesses, method_calls=method_calls) == 1


def test_composite_risk_score():
    """Composite risk formula weighting."""
    # Zero risk everywhere
    assert calculate_composite_risk_score(0.0, 0.0, 0.0, 0.0, 0.0) == 0.0

    # Maximum risk everywhere
    assert calculate_composite_risk_score(1.0, 1.0, 1.0, 1.0, 1.0) == 1.0

    # Regression only (35% weight)
    score = calculate_composite_risk_score(1.0, 0.0, 0.0, 0.0, 0.0)
    assert abs(score - 0.35) < 1e-4

    # Bounded in [0.0, 1.0] even with out-of-range inputs
    assert calculate_composite_risk_score(2.5, -0.5, 1.2, 0.0, 0.0) <= 1.0
