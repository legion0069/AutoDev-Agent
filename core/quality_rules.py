"""
AutoDev Declarative Quality Rules Engine (v2.7)
Static and structural quality rules for complexity, architectural boundaries,
duplication, thread safety, and resource leaks.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional, Set

from core.quality_models import (
    CodeLocation,
    ComplexityMetrics,
    DependencyHealthMetrics,
    DuplicationBlock,
    QualityIssue,
    QualityRiskCategory,
    QualitySeverity,
)


class QualityRule:
    """Base class for static and architectural quality rules."""

    @property
    def rule_id(self) -> str:
        raise NotImplementedError

    @property
    def rule_name(self) -> str:
        raise NotImplementedError

    @property
    def category(self) -> QualityRiskCategory:
        raise NotImplementedError

    @property
    def severity(self) -> QualitySeverity:
        raise NotImplementedError

    def evaluate(self, context: Dict[str, Any]) -> List[QualityIssue]:
        """Evaluates context and returns any identified quality issues."""
        raise NotImplementedError


class HighCyclomaticComplexityRule(QualityRule):
    """Detects functions exceeding cyclomatic complexity limits."""

    def __init__(self, max_allowed: int = 15):
        self.max_allowed = max_allowed

    @property
    def rule_id(self) -> str:
        return "QUAL-COMPLEX-001"

    @property
    def rule_name(self) -> str:
        return "High Cyclomatic Complexity"

    @property
    def category(self) -> QualityRiskCategory:
        return QualityRiskCategory.COMPLEXITY_EXPLOSION

    @property
    def severity(self) -> QualitySeverity:
        return QualitySeverity.HIGH

    def evaluate(self, context: Dict[str, Any]) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        file_path = context.get("file_path", "")
        funcs = context.get("functions_complexity", {})

        for func_name, metrics in funcs.items():
            if metrics.cyclomatic_complexity > self.max_allowed:
                loc = context.get("function_locations", {}).get(func_name)
                issues.append(
                    QualityIssue(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        category=self.category,
                        severity=self.severity,
                        description=(
                            f"Function '{func_name}' has Cyclomatic Complexity of "
                            f"{metrics.cyclomatic_complexity} (threshold: {self.max_allowed})."
                        ),
                        location=loc,
                        affected_symbols=[func_name],
                        remediation_suggestion="Decompose function into smaller, single-responsibility helper methods.",
                        technical_debt_minutes=(metrics.cyclomatic_complexity - self.max_allowed) * 15,
                        evidence={"complexity": metrics.cyclomatic_complexity, "file": file_path},
                    )
                )
        return issues


class HighCognitiveComplexityRule(QualityRule):
    """Detects functions exceeding cognitive complexity limits."""

    def __init__(self, max_allowed: int = 20):
        self.max_allowed = max_allowed

    @property
    def rule_id(self) -> str:
        return "QUAL-COMPLEX-002"

    @property
    def rule_name(self) -> str:
        return "High Cognitive Complexity"

    @property
    def category(self) -> QualityRiskCategory:
        return QualityRiskCategory.COMPLEXITY_EXPLOSION

    @property
    def severity(self) -> QualitySeverity:
        return QualitySeverity.HIGH

    def evaluate(self, context: Dict[str, Any]) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        funcs = context.get("functions_complexity", {})

        for func_name, metrics in funcs.items():
            if metrics.cognitive_complexity > self.max_allowed:
                loc = context.get("function_locations", {}).get(func_name)
                issues.append(
                    QualityIssue(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        category=self.category,
                        severity=self.severity,
                        description=(
                            f"Function '{func_name}' has Cognitive Complexity of "
                            f"{metrics.cognitive_complexity} (threshold: {self.max_allowed})."
                        ),
                        location=loc,
                        affected_symbols=[func_name],
                        remediation_suggestion="Flatten nested control flow structures and simplify boolean logic.",
                        technical_debt_minutes=(metrics.cognitive_complexity - self.max_allowed) * 15,
                    )
                )
        return issues


class CircularDependencyRule(QualityRule):
    """Detects cyclic module import loops."""

    @property
    def rule_id(self) -> str:
        return "QUAL-ARCH-001"

    @property
    def rule_name(self) -> str:
        return "Circular Import Dependency"

    @property
    def category(self) -> QualityRiskCategory:
        return QualityRiskCategory.CYCLIC_DEPENDENCY

    @property
    def severity(self) -> QualitySeverity:
        return QualitySeverity.CRITICAL

    def evaluate(self, context: Dict[str, Any]) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        dep_health: Dict[str, DependencyHealthMetrics] = context.get("dependency_health", {})

        reported_cycles: Set[str] = set()
        for mod_name, metrics in dep_health.items():
            if metrics.has_circular_dependencies:
                for cycle in metrics.circular_dependency_cycles:
                    cycle_key = " -> ".join(sorted(cycle))
                    if cycle_key not in reported_cycles:
                        reported_cycles.add(cycle_key)
                        issues.append(
                            QualityIssue(
                                rule_id=self.rule_id,
                                rule_name=self.rule_name,
                                category=self.category,
                                severity=self.severity,
                                description=f"Circular dependency cycle detected: {' -> '.join(cycle)} -> {cycle[0]}",
                                affected_symbols=cycle,
                                remediation_suggestion="Introduce dependency inversion (interfaces) or extract shared abstractions.",
                                technical_debt_minutes=60,
                                evidence={"cycle": cycle},
                            )
                        )
        return issues


class GodObjectRule(QualityRule):
    """Detects God Classes or Hub Modules with excessive coupling and low cohesion."""

    @property
    def rule_id(self) -> str:
        return "QUAL-ARCH-002"

    @property
    def rule_name(self) -> str:
        return "God Object / Low Cohesion"

    @property
    def category(self) -> QualityRiskCategory:
        return QualityRiskCategory.GOD_OBJECT

    @property
    def severity(self) -> QualitySeverity:
        return QualitySeverity.HIGH

    def evaluate(self, context: Dict[str, Any]) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        dep_health: Dict[str, DependencyHealthMetrics] = context.get("dependency_health", {})

        for mod_name, metrics in dep_health.items():
            if metrics.is_god_object or metrics.lack_of_cohesion_lcom4 > 2:
                issues.append(
                    QualityIssue(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        category=self.category,
                        severity=self.severity,
                        description=(
                            f"Module '{mod_name}' behaves as a God Object with high coupling (Ca={metrics.afferent_coupling}, Ce={metrics.efferent_coupling}) "
                            f"and low cohesion (LCOM4={metrics.lack_of_cohesion_lcom4})."
                        ),
                        affected_symbols=[mod_name],
                        remediation_suggestion="Decompose module according to single-responsibility principle.",
                        technical_debt_minutes=90,
                    )
                )
        return issues


class DuplicatedCodeRule(QualityRule):
    """Detects duplicate blocks and copy-paste code."""

    @property
    def rule_id(self) -> str:
        return "QUAL-DUP-001"

    @property
    def rule_name(self) -> str:
        return "Duplicated Code Block"

    @property
    def category(self) -> QualityRiskCategory:
        return QualityRiskCategory.CODE_DUPLICATION

    @property
    def severity(self) -> QualitySeverity:
        return QualitySeverity.MEDIUM

    def evaluate(self, context: Dict[str, Any]) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        duplications: List[DuplicationBlock] = context.get("duplications", [])

        for dup in duplications:
            if dup.duplication_type in ("exact", "near_duplicate") and len(dup.locations) > 1:
                loc_desc = ", ".join(f"{l.file_path}:L{l.start_line}" for l in dup.locations[:3])
                issues.append(
                    QualityIssue(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        category=self.category,
                        severity=self.severity,
                        description=f"Duplicate code block of {dup.line_count} lines found in {len(dup.locations)} locations ({loc_desc}).",
                        location=dup.locations[0],
                        affected_symbols=[l.file_path for l in dup.locations],
                        remediation_suggestion="Extract shared logic into a reusable utility or base function.",
                        technical_debt_minutes=dup.line_count * 5,
                    )
                )
        return issues


class UnclosedResourceRule(QualityRule):
    """Detects potential resource/file leaks where open() is used without a context manager."""

    @property
    def rule_id(self) -> str:
        return "QUAL-RES-001"

    @property
    def rule_name(self) -> str:
        return "Unclosed Resource Leak"

    @property
    def category(self) -> QualityRiskCategory:
        return QualityRiskCategory.RESOURCE_MEMORY_LEAK

    @property
    def severity(self) -> QualitySeverity:
        return QualitySeverity.HIGH

    def evaluate(self, context: Dict[str, Any]) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        content = context.get("source_code", "")
        file_path = context.get("file_path", "")

        if not content:
            return issues

        try:
            tree = ast.parse(content, filename=file_path)
        except Exception:
            return issues

        # Check for standalone open() calls not inside With
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                    if node.value.func.id == "open":
                        # Check if inside a with statement
                        loc = CodeLocation(
                            file_path=file_path,
                            start_line=getattr(node, "lineno", 0),
                            end_line=getattr(node, "end_lineno", getattr(node, "lineno", 0)),
                        )
                        issues.append(
                            QualityIssue(
                                rule_id=self.rule_id,
                                rule_name=self.rule_name,
                                category=self.category,
                                severity=self.severity,
                                description=f"File opened via standalone assignment at line {node.lineno} without a 'with' context manager.",
                                location=loc,
                                remediation_suggestion="Wrap resource in 'with open(...) as ...:' statement to guarantee closure.",
                                technical_debt_minutes=20,
                            )
                        )
        return issues


class ThreadSafetyRiskRule(QualityRule):
    """Detects shared mutable module globals modified inside functions without synchronization."""

    @property
    def rule_id(self) -> str:
        return "QUAL-CONCURR-001"

    @property
    def rule_name(self) -> str:
        return "Thread Safety Risk on Mutable Global"

    @property
    def category(self) -> QualityRiskCategory:
        return QualityRiskCategory.THREAD_SAFETY_RACE

    @property
    def severity(self) -> QualitySeverity:
        return QualitySeverity.HIGH

    def evaluate(self, context: Dict[str, Any]) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        content = context.get("source_code", "")
        file_path = context.get("file_path", "")

        if not content:
            return issues

        try:
            tree = ast.parse(content, filename=file_path)
        except Exception:
            return issues

        for node in ast.walk(tree):
            if isinstance(node, ast.Global):
                loc = CodeLocation(
                    file_path=file_path,
                    start_line=getattr(node, "lineno", 0),
                    end_line=getattr(node, "end_lineno", getattr(node, "lineno", 0)),
                )
                issues.append(
                    QualityIssue(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        category=self.category,
                        severity=self.severity,
                        description=f"Global mutable state modified via 'global {', '.join(node.names)}' at line {node.lineno} without lock.",
                        location=loc,
                        affected_symbols=node.names,
                        remediation_suggestion="Encapsulate shared state in a thread-safe synchronized manager or lock-protected store.",
                        technical_debt_minutes=45,
                    )
                )
        return issues


# Default rule catalog
DEFAULT_QUALITY_RULES: List[QualityRule] = [
    HighCyclomaticComplexityRule(),
    HighCognitiveComplexityRule(),
    CircularDependencyRule(),
    GodObjectRule(),
    DuplicatedCodeRule(),
    UnclosedResourceRule(),
    ThreadSafetyRiskRule(),
]


class RuleRegistry:
    """Registry for managing active and custom quality rules."""

    def __init__(self, initial_rules: Optional[List[QualityRule]] = None):
        self._rules: Dict[str, QualityRule] = {}
        rules_to_load = DEFAULT_QUALITY_RULES if initial_rules is None else initial_rules
        for r in rules_to_load:
            self.register(r)

    def register(self, rule: QualityRule) -> None:
        self._rules[rule.rule_id] = rule

    def unregister(self, rule_id: str) -> Optional[QualityRule]:
        return self._rules.pop(rule_id, None)

    def get_rule(self, rule_id: str) -> Optional[QualityRule]:
        return self._rules.get(rule_id)

    def get_rules(self) -> List[QualityRule]:
        return list(self._rules.values())

    def get_rules_by_category(self, category: QualityRiskCategory) -> List[QualityRule]:
        return [r for r in self._rules.values() if r.category == category]
