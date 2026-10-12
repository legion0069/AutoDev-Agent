"""
AutoDev Regression Test Selector (v2.6)
Selects risk-proportional regression tests across four validation levels
using static impact analysis and symbol graph relationships.
"""

from __future__ import annotations

import ast
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

from core.repair_models import CandidatePatch

logger = logging.getLogger(__name__)

SECURITY_MODULES = {"auth", "crypto", "consensus", "isolation", "sandbox", "fencing", "transaction"}


@dataclass
class TestSelectionResult:
    """Outcome of regression test selection analysis."""
    validation_level: str
    selected_tests: List[str] = field(default_factory=list)
    rationale: Dict[str, str] = field(default_factory=dict)  # test_path -> selection reason
    escalated: bool = False
    escalation_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RegressionTestSelector:
    """Selects targeted and regression test suites based on patch blast radius and risk."""

    def __init__(self, workspace_path: str, all_discovered_tests: Optional[List[str]] = None):
        self.workspace_path = os.path.realpath(os.path.abspath(workspace_path))
        self.all_discovered_tests = all_discovered_tests or self._discover_all_test_files()

    def _discover_all_test_files(self) -> List[str]:
        """Discovers all test files in the workspace tests/ directory."""
        test_dir = os.path.join(self.workspace_path, "tests")
        if not os.path.isdir(test_dir):
            return []

        tests = []
        for root, _, files in os.walk(test_dir):
            for file in files:
                if file.startswith("test_") and file.endswith(".py"):
                    rel_path = os.path.relpath(os.path.join(root, file), self.workspace_path)
                    tests.append(rel_path.replace("\\", "/"))
        return sorted(tests)

    def select_tests(
        self,
        patch: CandidatePatch,
        validation_level: str = "standard",
        primary_failing_test: Optional[str] = None,
    ) -> TestSelectionResult:
        """Selects proportional test suite for verifying a candidate patch."""
        selected: Set[str] = set()
        rationale: Dict[str, str] = {}
        escalated = False
        escalation_reason = None

        # Always include the primary failing test target
        if primary_failing_test:
            selected.add(primary_failing_test)
            rationale[primary_failing_test] = "Primary failing test target"

        modified_files = patch.modified_files

        # Check for security escalation
        for f in modified_files:
            f_lower = f.lower()
            if any(sec in f_lower for sec in SECURITY_MODULES):
                if validation_level in ("targeted", "standard"):
                    validation_level = "comprehensive"
                    escalated = True
                    escalation_reason = f"Escalated to comprehensive due to security-sensitive file: {f}"
                break

        # Level: Full Suite
        if validation_level == "full_suite":
            for t in self.all_discovered_tests:
                selected.add(t)
                if t not in rationale:
                    rationale[t] = "Full suite execution policy"
            return TestSelectionResult(
                validation_level=validation_level,
                selected_tests=sorted(list(selected)),
                rationale=rationale,
                escalated=escalated,
                escalation_reason=escalation_reason,
            )

        # 1. Direct unit tests corresponding to modified files (e.g. core/foo.py -> tests/test_foo.py)
        for f in modified_files:
            basename = os.path.splitext(os.path.basename(f))[0]
            expected_test_name = f"test_{basename}.py"
            
            for t in self.all_discovered_tests:
                if expected_test_name in t:
                    selected.add(t)
                    rationale[t] = f"Direct unit test for modified module {f}"

        # Level: Targeted - return after direct matching
        if validation_level == "targeted":
            if not selected and primary_failing_test:
                selected.add(primary_failing_test)
            # Fallback if no test found
            if not selected and self.all_discovered_tests:
                selected.add(self.all_discovered_tests[0])
                rationale[self.all_discovered_tests[0]] = "Fallback test target"
            return TestSelectionResult(
                validation_level=validation_level,
                selected_tests=sorted(list(selected)),
                rationale=rationale,
                escalated=escalated,
                escalation_reason=escalation_reason,
            )

        # 2. Level: Standard - add importing and dependent tests
        for f in modified_files:
            module_name = os.path.splitext(os.path.basename(f))[0]
            for t in self.all_discovered_tests:
                if t in selected:
                    continue
                if self._test_imports_module(t, module_name):
                    selected.add(t)
                    rationale[t] = f"Test imports or references {module_name}"

        if validation_level == "standard":
            return TestSelectionResult(
                validation_level=validation_level,
                selected_tests=sorted(list(selected)),
                rationale=rationale,
                escalated=escalated,
                escalation_reason=escalation_reason,
            )

        # 3. Level: Comprehensive - add integration and end-to-end tests
        for t in self.all_discovered_tests:
            if "integration" in t.lower() or "e2e" in t.lower():
                selected.add(t)
                if t not in rationale:
                    rationale[t] = "Integration regression suite covering subsystem boundaries"

        return TestSelectionResult(
            validation_level=validation_level,
            selected_tests=sorted(list(selected)),
            rationale=rationale,
            escalated=escalated,
            escalation_reason=escalation_reason,
        )

    def _test_imports_module(self, test_rel_path: str, module_name: str) -> bool:
        """Inspects test file imports using AST to see if it depends on module_name."""
        abs_path = os.path.join(self.workspace_path, test_rel_path)
        if not os.path.isfile(abs_path):
            return False

        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            # Fast string check before AST parse
            if module_name not in content:
                return False

            tree = ast.parse(content, filename=abs_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if module_name in alias.name:
                            return True
                elif isinstance(node, ast.ImportFrom):
                    if node.module and module_name in node.module:
                        return True
            return False
        except Exception:
            return module_name in content
