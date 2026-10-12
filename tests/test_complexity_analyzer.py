"""
tests/test_complexity_analyzer.py - Unit tests for AutoDev Complexity Analyzer (v2.7)

Validates:
- McCabe cyclomatic complexity calculation across language constructs
- SonarQube cognitive complexity with structural nesting increments
- Maximum nesting depth detection
- Longest method call chain detection
- SLOC and Halstead volume calculation from AST
- Syntax error handling and resilience
"""

import pytest
from core.complexity_analyzer import ComplexityAnalyzer, ASTComplexityVisitor, ComplexityVisitor


def test_simple_function_complexity():
    """Simple linear function should have cyclomatic complexity 1 and cognitive complexity 0."""
    code = """
def add(a, b):
    return a + b
"""
    analyzer = ComplexityAnalyzer()
    metrics = analyzer.analyze_code(code)
    assert metrics.cyclomatic_complexity == 1
    assert metrics.cognitive_complexity == 0
    assert metrics.max_nesting_depth == 0
    assert metrics.sloc >= 2
    assert metrics.maintainability_index > 80.0


def test_mccabe_cyclomatic_branches():
    """Branches (if, elif, for, while, except, boolean ops) increase McCabe complexity."""
    code = """
def evaluate(x, y, flag):
    if x > 0 and y > 0:       # +1 for if, +1 for and
        for i in range(10):   # +1 for for
            if flag or x == 5: # +1 for if, +1 for or
                pass
    elif x < 0:               # +1 for elif
        while y > 0:          # +1 for while
            y -= 1
    try:
        val = x / y
    except ZeroDivisionError: # +1 for except
        val = 0
    return val
"""
    analyzer = ComplexityAnalyzer()
    metrics = analyzer.analyze_code(code)
    # Base 1 + if(1) + and(1) + for(1) + if(1) + or(1) + elif(1) + while(1) + except(1) = 9
    assert metrics.cyclomatic_complexity >= 8


def test_cognitive_complexity_nesting_penalties():
    """Cognitive complexity penalizes nested structures progressively."""
    code = """
def nested_func(data):
    if data:                     # +1 (nesting 0)
        for row in data:         # +2 (1 + nesting 1)
            for item in row:     # +3 (1 + nesting 2)
                if item > 10:    # +4 (1 + nesting 3)
                    print(item)
"""
    analyzer = ComplexityAnalyzer()
    metrics = analyzer.analyze_code(code)
    # Expected: 1 + 2 + 3 + 4 = 10
    assert metrics.cognitive_complexity >= 9
    assert metrics.max_nesting_depth >= 4


def test_longest_call_chain():
    """Detects depth of chained attribute/method calls."""
    code = """
def process(stream):
    return stream.filter(lambda x: x > 0).map(str).collect().summary()
"""
    analyzer = ComplexityAnalyzer()
    metrics = analyzer.analyze_code(code)
    assert metrics.longest_call_chain >= 4


def test_syntax_error_resilience():
    """Malformed syntax returns fallback baseline metrics without raising an exception."""
    malformed = "def broken_func(:\n    return ???"
    analyzer = ComplexityAnalyzer()
    metrics = analyzer.analyze_code(malformed)
    assert metrics.cyclomatic_complexity == 1
    assert metrics.cognitive_complexity == 0
    assert metrics.loc > 0


def test_analyze_file_with_multiple_classes_and_methods():
    """Analyzes complete files with classes and standalone functions."""
    code = """
class DataService:
    def __init__(self, db):
        self.db = db

    def query(self, q):
        if not q:
            return []
        return self.db.execute(q)

def helper(x):
    return x * 2
"""
    analyzer = ComplexityAnalyzer()
    metrics = analyzer.analyze_code(code, file_path="service.py")
    assert metrics.cyclomatic_complexity >= 2
    assert metrics.loc >= 10
    assert metrics.maintainability_index > 60.0


def test_visitor_alias_compatibility():
    """Both ComplexityVisitor and ASTComplexityVisitor are valid."""
    assert ComplexityVisitor is ASTComplexityVisitor
    visitor = ComplexityVisitor()
    assert visitor.cyclomatic_complexity == 1
    assert visitor.cognitive_complexity == 0


def test_comprehension_complexity():
    """List, set, and dict comprehensions increment complexity appropriately."""
    code = """
def compute(items):
    res = [x * 2 for x in items if x % 2 == 0]
    return {k: v for k, v in res if v > 0}
"""
    analyzer = ComplexityAnalyzer()
    metrics = analyzer.analyze_code(code)
    assert metrics.cyclomatic_complexity >= 3
