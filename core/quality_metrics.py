"""
AutoDev Quality Metrics Engine (v2.7)
Deterministic mathematical calculations for Maintainability Index (MI),
Halstead Software Science, Martin's Package Metrics, LCOM4 Cohesion,
and Composite Predictive Risk Scoring.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


def calculate_halstead_volume(
    operators: Sequence[str],
    operands: Sequence[str],
) -> Tuple[int, int, float]:
    """
    Calculates Halstead Length (N), Vocabulary (eta), and Volume (V).
    Formula: N = N1 + N2, eta = eta1 + eta2, V = N * log2(eta)
    """
    n1 = len(operators)
    n2 = len(operands)
    total_length = n1 + n2

    distinct_operators = len(set(operators))
    distinct_operands = len(set(operands))
    vocabulary = distinct_operators + distinct_operands

    if total_length == 0 or vocabulary <= 1:
        return total_length, vocabulary, 0.0

    volume = total_length * math.log2(vocabulary)
    return total_length, vocabulary, volume


def calculate_maintainability_index(
    halstead_volume: float,
    cyclomatic_complexity: int,
    sloc: int,
    comment_ratio: float = 0.0,
) -> float:
    """
    Calculates Maintainability Index (MI) normalized to a 0-100 scale using the SEI formula.
    Formula:
      MI_raw = 171 - 5.2 * ln(V) - 0.23 * G - 16.2 * ln(SLOC) + (50 * sin(sqrt(2.4 * comment_ratio)))
      MI_norm = max(0.0, min(100.0, MI_raw * 100.0 / 171.0))
    """
    v = max(1.0, halstead_volume)
    g = max(1, cyclomatic_complexity)
    s = max(1, sloc)

    mi_raw = 171.0 - (5.2 * math.log(v)) - (0.23 * float(g)) - (16.2 * math.log(s))

    # Add comment bonus if available
    if comment_ratio > 0.0:
        bounded_ratio = min(1.0, max(0.0, comment_ratio))
        mi_raw += 50.0 * math.sin(math.sqrt(2.4 * bounded_ratio))

    # Normalize to [0.0, 100.0]
    normalized = max(0.0, min(100.0, (mi_raw * 100.0) / 171.0))
    return round(normalized, 2)


def calculate_instability(afferent_coupling: int, efferent_coupling: int) -> float:
    """
    Calculates Martin's Package Instability (I).
    Formula: I = Ce / (Ca + Ce)
    Range: 0.0 (completely stable / independent) to 1.0 (completely unstable / dependent).
    """
    total = afferent_coupling + efferent_coupling
    if total == 0:
        return 0.0
    return round(float(efferent_coupling) / float(total), 4)


def calculate_abstractness(abstract_classes_count: int, total_classes_count: int) -> float:
    """
    Calculates Martin's Abstractness (A).
    Formula: A = Na / Nc
    Range: 0.0 (all concrete) to 1.0 (all abstract interfaces).
    """
    if total_classes_count == 0:
        return 0.0
    return round(float(abstract_classes_count) / float(total_classes_count), 4)


def calculate_distance_main_sequence(abstractness: float, instability: float) -> float:
    """
    Calculates Normalized Distance from the Main Sequence (D).
    Formula: D = |A + I - 1.0|
    Range: 0.0 (optimal balance) to 1.0 (Zone of Pain or Zone of Uselessness).
    """
    d = abs(abstractness + instability - 1.0)
    return round(min(1.0, max(0.0, d)), 4)


def calculate_lcom4(
    methods: Sequence[str],
    method_field_accesses: Dict[str, Set[str]],
    method_calls: Optional[Dict[str, Set[str]]] = None,
) -> int:
    """
    Calculates Lack of Cohesion of Methods (LCOM4).
    Computes number of connected components in the undirected graph where
    methods are connected if they share an attribute or call each other.
    LCOM4 = 1 is cohesive; LCOM4 > 1 suggests the class should be decomposed.
    """
    if not methods:
        return 0
    
    non_ctor = [m for m in methods if m not in ("__init__", "__new__")]
    eval_methods = non_ctor if len(non_ctor) >= 2 else list(methods)

    if len(eval_methods) <= 1:
        return 1

    calls = method_calls or {}
    adj: Dict[str, Set[str]] = {m: set() for m in eval_methods}

    # Connect methods that share instance fields or call each other
    method_list = list(eval_methods)
    for i in range(len(method_list)):
        m1 = method_list[i]
        f1 = method_field_accesses.get(m1, set())
        for j in range(i + 1, len(method_list)):
            m2 = method_list[j]
            f2 = method_field_accesses.get(m2, set())
            
            # Shared field
            if f1 and f2 and not f1.isdisjoint(f2):
                adj[m1].add(m2)
                adj[m2].add(m1)
            # Direct method invocation
            elif m2 in calls.get(m1, set()) or m1 in calls.get(m2, set()):
                adj[m1].add(m2)
                adj[m2].add(m1)

    # Count connected components via BFS / DFS
    visited: Set[str] = set()
    components = 0

    for m in eval_methods:
        if m not in visited:
            components += 1
            queue = [m]
            visited.add(m)
            while queue:
                curr = queue.pop(0)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

    return components


def calculate_composite_risk_score(
    regression_prob: float,
    complexity_risk: float,
    instability_risk: float,
    security_risk: float,
    historical_defect_risk: float = 0.0,
) -> float:
    """
    Calculates weighted composite risk score in [0.0, 1.0].
    Weights: Regression (35%), Complexity (25%), Instability (15%), Security (15%), History (10%).
    """
    score = (
        0.35 * min(1.0, max(0.0, regression_prob))
        + 0.25 * min(1.0, max(0.0, complexity_risk))
        + 0.15 * min(1.0, max(0.0, instability_risk))
        + 0.15 * min(1.0, max(0.0, security_risk))
        + 0.10 * min(1.0, max(0.0, historical_defect_risk))
    )
    return round(min(1.0, max(0.0, score)), 4)


# Aliases for explicit terminology
calculate_martin_instability = calculate_instability
calculate_martin_abstractness = calculate_abstractness
calculate_distance_from_main_sequence = calculate_distance_main_sequence
