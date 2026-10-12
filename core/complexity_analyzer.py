"""
AutoDev Complexity Analyzer (v2.7)
Deterministic AST-based static analyzer for Cyclomatic Complexity (McCabe),
Cognitive Complexity (SonarQube specification), Maximum Nesting Depth,
Call Chain Length, SLOC, and Halstead Volume.
"""

from __future__ import annotations

import ast
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from core.quality_metrics import calculate_halstead_volume, calculate_maintainability_index
from core.quality_models import ComplexityMetrics

logger = logging.getLogger(__name__)


class ASTComplexityVisitor(ast.NodeVisitor):
    """AST visitor calculating McCabe cyclomatic complexity, cognitive complexity, and nesting depth."""

    def __init__(self):
        self.cyclomatic_complexity = 1
        self.cognitive_complexity = 0
        self.current_nesting = 0
        self.max_nesting = 0
        self.longest_call_chain = 0
        self.branch_depths: List[int] = []
        self.operators: List[str] = []
        self.operands: List[str] = []

    def _enter_nesting(self):
        self.current_nesting += 1
        if self.current_nesting > self.max_nesting:
            self.max_nesting = self.current_nesting

    def _exit_nesting(self):
        self.current_nesting = max(0, self.current_nesting - 1)

    def visit_If(self, node: ast.If):
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1 + self.current_nesting
        self.branch_depths.append(self.current_nesting + 1)
        self.operators.append("if")

        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()

    def visit_IfExp(self, node: ast.IfExp):
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1 + self.current_nesting
        self.operators.append("if_exp")
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1 + self.current_nesting
        self.operators.append("for")

        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()

    def visit_AsyncFor(self, node: ast.AsyncFor):
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1 + self.current_nesting
        self.operators.append("async_for")

        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()

    def visit_While(self, node: ast.While):
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1 + self.current_nesting
        self.operators.append("while")

        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1 + self.current_nesting
        self.operators.append("except")

        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()

    def visit_With(self, node: ast.With):
        self.cyclomatic_complexity += len(node.items)
        self.operators.append("with")
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith):
        self.cyclomatic_complexity += len(node.items)
        self.operators.append("async_with")
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert):
        self.cyclomatic_complexity += 1
        self.operators.append("assert")
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp):
        # Each boolean branch (and, or) adds complexity
        count = len(node.values) - 1
        self.cyclomatic_complexity += count
        self.cognitive_complexity += count
        op_name = "and" if isinstance(node.op, ast.And) else "or"
        self.operators.extend([op_name] * count)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension):
        self.cyclomatic_complexity += 1 + len(node.ifs)
        self.cognitive_complexity += 1 + len(node.ifs)
        self.operators.append("comprehension")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        chain_len = self._compute_call_chain_depth(node)
        if chain_len > self.longest_call_chain:
            self.longest_call_chain = chain_len
        self.operators.append("call")
        self.generic_visit(node)

    def _compute_call_chain_depth(self, node: ast.AST) -> int:
        depth = 0
        curr = node
        while isinstance(curr, ast.Call):
            depth += 1
            curr = curr.func
            while isinstance(curr, ast.Attribute):
                curr = curr.value
        return depth

    def visit_Name(self, node: ast.Name):
        self.operands.append(node.id)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        self.operands.append(str(node.value))
        self.generic_visit(node)


class ComplexityAnalyzer:
    """Analyzes source code complexity and computes comprehensive ComplexityMetrics."""

    def analyze_source(self, code_str: str, file_path: str = "") -> ComplexityMetrics:
        """Parses Python source code and returns computed ComplexityMetrics."""
        if not code_str or not code_str.strip():
            return ComplexityMetrics(
                cyclomatic_complexity=1,
                cognitive_complexity=0,
                max_nesting_depth=0,
                longest_call_chain=0,
                loc=0,
                sloc=0,
                comment_loc=0,
                blank_loc=0,
                maintainability_index=100.0,
            )

        lines = code_str.splitlines()
        loc = len(lines)
        blank_loc = sum(1 for line in lines if not line.strip())
        comment_loc = sum(1 for line in lines if line.strip().startswith("#"))
        sloc = max(1, loc - blank_loc - comment_loc)

        try:
            tree = ast.parse(code_str, filename=file_path or "<source>")
        except SyntaxError as e:
            logger.warning(f"Syntax error during complexity analysis of {file_path}: {e}")
            return ComplexityMetrics(
                cyclomatic_complexity=1,
                cognitive_complexity=0,
                loc=loc,
                sloc=sloc,
                comment_loc=comment_loc,
                blank_loc=blank_loc,
                maintainability_index=50.0,
            )

        visitor = ASTComplexityVisitor()
        visitor.visit(tree)

        # Average branch depth
        avg_branch_depth = (
            sum(visitor.branch_depths) / len(visitor.branch_depths)
            if visitor.branch_depths
            else 0.0
        )

        # Average method length
        method_lengths: List[int] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = getattr(node, "lineno", 0)
                end = getattr(node, "end_lineno", start)
                method_lengths.append(max(1, end - start + 1))

        avg_method_length = (
            sum(method_lengths) / len(method_lengths) if method_lengths else float(sloc)
        )

        # Halstead calculations
        _, _, halstead_volume = calculate_halstead_volume(visitor.operators, visitor.operands)

        # Maintainability Index
        comment_ratio = float(comment_loc) / float(loc) if loc > 0 else 0.0
        mi = calculate_maintainability_index(
            halstead_volume=halstead_volume,
            cyclomatic_complexity=visitor.cyclomatic_complexity,
            sloc=sloc,
            comment_ratio=comment_ratio,
        )

        return ComplexityMetrics(
            cyclomatic_complexity=visitor.cyclomatic_complexity,
            cognitive_complexity=visitor.cognitive_complexity,
            max_nesting_depth=visitor.max_nesting,
            longest_call_chain=visitor.longest_call_chain,
            loc=loc,
            sloc=sloc,
            comment_loc=comment_loc,
            blank_loc=blank_loc,
            avg_branch_depth=round(avg_branch_depth, 2),
            avg_method_length=round(avg_method_length, 2),
            halstead_volume=round(halstead_volume, 2),
            maintainability_index=mi,
        )

    def analyze_function(self, func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> ComplexityMetrics:
        """Calculates complexity metrics for a specific function/method AST node."""
        visitor = ASTComplexityVisitor()
        visitor.visit(func_node)

        start = getattr(func_node, "lineno", 0)
        end = getattr(func_node, "end_lineno", start)
        sloc = max(1, end - start + 1)

        _, _, volume = calculate_halstead_volume(visitor.operators, visitor.operands)
        mi = calculate_maintainability_index(
            halstead_volume=volume,
            cyclomatic_complexity=visitor.cyclomatic_complexity,
            sloc=sloc,
        )

        return ComplexityMetrics(
            cyclomatic_complexity=visitor.cyclomatic_complexity,
            cognitive_complexity=visitor.cognitive_complexity,
            max_nesting_depth=visitor.max_nesting,
            longest_call_chain=visitor.longest_call_chain,
            loc=sloc,
            sloc=sloc,
            halstead_volume=round(volume, 2),
            maintainability_index=mi,
        )

    # Alias for analyze_source
    analyze_code = analyze_source


# Alias for explicit class name
ComplexityVisitor = ASTComplexityVisitor
