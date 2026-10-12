"""
tests/test_quality_rules.py - Unit tests for AutoDev Quality Rules Engine (v2.7)

Validates:
- RuleRegistry registration, unregistration, retrieval, and category filtering
- HighCyclomaticComplexityRule evaluation and debt calculation
- HighCognitiveComplexityRule evaluation and debt calculation
- CircularDependencyRule cycle detection
- GodObjectRule coupling and cohesion violation detection
- DuplicatedCodeRule exact and near duplicate detection
- UnclosedResourceRule standalone open() AST detection
- ThreadSafetyRiskRule global mutable state detection
"""

import pytest
from core.quality_models import (
    CodeLocation,
    ComplexityMetrics,
    DependencyHealthMetrics,
    DuplicationBlock,
    QualityIssue,
    QualityRiskCategory,
    QualitySeverity,
)
from core.quality_rules import (
    CircularDependencyRule,
    DEFAULT_QUALITY_RULES,
    DuplicatedCodeRule,
    GodObjectRule,
    HighCognitiveComplexityRule,
    HighCyclomaticComplexityRule,
    QualityRule,
    RuleRegistry,
    ThreadSafetyRiskRule,
    UnclosedResourceRule,
)


def test_rule_registry_defaults():
    """RuleRegistry initializes with default rules and supports lookup."""
    registry = RuleRegistry()
    rules = registry.get_rules()
    assert len(rules) >= 7

    cc_rule = registry.get_rule("QUAL-COMPLEX-001")
    assert cc_rule is not None
    assert cc_rule.rule_name == "High Cyclomatic Complexity"
    assert cc_rule.category == QualityRiskCategory.COMPLEXITY_EXPLOSION

    arch_rules = registry.get_rules_by_category(QualityRiskCategory.CYCLIC_DEPENDENCY)
    assert len(arch_rules) == 1
    assert arch_rules[0].rule_id == "QUAL-ARCH-001"


def test_rule_registry_custom_registration_and_unregistration():
    """Custom rules can be registered and removed dynamically."""
    class CustomSecurityRule(QualityRule):
        @property
        def rule_id(self) -> str:
            return "CUSTOM-SEC-999"

        @property
        def rule_name(self) -> str:
            return "Custom Hardcoded Token Rule"

        @property
        def category(self) -> QualityRiskCategory:
            return QualityRiskCategory.SECURITY_VULNERABILITY

        @property
        def severity(self) -> QualitySeverity:
            return QualitySeverity.CRITICAL

        def evaluate(self, context):
            return []

    registry = RuleRegistry([])
    assert len(registry.get_rules()) == 0

    custom = CustomSecurityRule()
    registry.register(custom)
    assert registry.get_rule("CUSTOM-SEC-999") is not None
    assert len(registry.get_rules_by_category(QualityRiskCategory.SECURITY_VULNERABILITY)) == 1

    removed = registry.unregister("CUSTOM-SEC-999")
    assert removed == custom
    assert registry.get_rule("CUSTOM-SEC-999") is None


def test_high_cyclomatic_complexity_rule():
    """Detects functions exceeding maximum cyclomatic complexity limit."""
    rule = HighCyclomaticComplexityRule(max_allowed=10)
    context = {
        "file_path": "math_solver.py",
        "functions_complexity": {
            "solve_polynomial": ComplexityMetrics(cyclomatic_complexity=16),
            "simple_add": ComplexityMetrics(cyclomatic_complexity=2),
        },
        "function_locations": {
            "solve_polynomial": CodeLocation(file_path="math_solver.py", start_line=10, end_line=50),
        },
    }

    issues = rule.evaluate(context)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.rule_id == "QUAL-COMPLEX-001"
    assert issue.severity == QualitySeverity.HIGH
    assert issue.technical_debt_minutes == (16 - 10) * 15
    assert issue.affected_symbols == ["solve_polynomial"]


def test_high_cognitive_complexity_rule():
    """Detects deeply nested logic with cognitive complexity over threshold."""
    rule = HighCognitiveComplexityRule(max_allowed=15)
    context = {
        "functions_complexity": {
            "nested_parser": ComplexityMetrics(cognitive_complexity=22),
        },
    }

    issues = rule.evaluate(context)
    assert len(issues) == 1
    assert issues[0].rule_id == "QUAL-COMPLEX-002"
    assert issues[0].technical_debt_minutes == (22 - 15) * 15


def test_circular_dependency_rule():
    """Detects cyclic module dependencies and reports single cycle keys."""
    rule = CircularDependencyRule()
    context = {
        "dependency_health": {
            "app.router": DependencyHealthMetrics(
                has_circular_dependencies=True,
                circular_dependency_cycles=[["app/router.py", "app/controller.py", "app/router.py"]],
            ),
        }
    }

    issues = rule.evaluate(context)
    assert len(issues) == 1
    assert issues[0].rule_id == "QUAL-ARCH-001"
    assert issues[0].severity == QualitySeverity.CRITICAL
    assert issues[0].technical_debt_minutes == 60


def test_god_object_rule():
    """Detects hub modules with low cohesion and high coupling."""
    rule = GodObjectRule()
    context = {
        "dependency_health": {
            "app.monolith": DependencyHealthMetrics(
                afferent_coupling=15,
                efferent_coupling=18,
                is_god_object=True,
                lack_of_cohesion_lcom4=4,
            ),
        }
    }

    issues = rule.evaluate(context)
    assert len(issues) == 1
    assert issues[0].rule_id == "QUAL-ARCH-002"
    assert issues[0].severity == QualitySeverity.HIGH


def test_duplicated_code_rule():
    """Detects duplicate blocks across files."""
    rule = DuplicatedCodeRule()
    dup = DuplicationBlock(
        locations=[
            CodeLocation(file_path="pkg/a.py", start_line=10, end_line=25),
            CodeLocation(file_path="pkg/b.py", start_line=15, end_line=30),
        ],
        line_count=15,
        duplication_type="exact",
    )
    context = {"duplications": [dup]}

    issues = rule.evaluate(context)
    assert len(issues) == 1
    assert issues[0].rule_id == "QUAL-DUP-001"
    assert issues[0].technical_debt_minutes == 15 * 5


def test_unclosed_resource_rule():
    """Detects standalone open() assignments without 'with' statement."""
    rule = UnclosedResourceRule()
    source_code = """
def read_log():
    f = open('output.log', 'r')
    data = f.read()
    return data
"""
    context = {"source_code": source_code, "file_path": "logger.py"}
    issues = rule.evaluate(context)
    assert len(issues) == 1
    assert issues[0].rule_id == "QUAL-RES-001"
    assert issues[0].category == QualityRiskCategory.RESOURCE_MEMORY_LEAK
    assert issues[0].location.start_line == 3


def test_thread_safety_risk_rule():
    """Detects use of mutable global state inside functions."""
    rule = ThreadSafetyRiskRule()
    source_code = """
shared_counter = 0

def increment():
    global shared_counter
    shared_counter += 1
"""
    context = {"source_code": source_code, "file_path": "counter.py"}
    issues = rule.evaluate(context)
    assert len(issues) == 1
    assert issues[0].rule_id == "QUAL-CONCURR-001"
    assert issues[0].category == QualityRiskCategory.THREAD_SAFETY_RACE
    assert "shared_counter" in issues[0].affected_symbols
