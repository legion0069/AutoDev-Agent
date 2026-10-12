"""
AutoDev Patch Validator (v2.6)
Strict validation gates: workspace containment, AST syntax checking,
anti-test-weakening enforcement, and security sensitivity inspection.
"""

from __future__ import annotations

import ast
import logging
import os
import re
from typing import Any, Dict, List, Optional

from core.repair_models import (
    CandidatePatch,
    FilePatch,
    PatchValidationResult,
    RepairPolicy,
    RiskLevel,
)

logger = logging.getLogger(__name__)

SECURITY_KEYWORDS = {"auth", "crypto", "consensus", "isolation", "secret", "ebpf", "token", "sandbox", "fencing"}


class PatchValidator:
    """Validates candidate patches against workspace boundaries, syntax rules, and anti-weakening policies."""

    def __init__(self, workspace_path: str, policy: Optional[RepairPolicy] = None):
        self.workspace_path = os.path.realpath(os.path.abspath(workspace_path))
        self.policy = policy or RepairPolicy()

    def validate(self, patch: CandidatePatch) -> PatchValidationResult:
        """Executes full validation suite on candidate patch."""
        rejection_reasons: List[str] = []
        warnings: List[str] = []
        syntax_ok = True
        containment_ok = True
        size_ok = True
        anti_weakening_ok = True
        security_ok = True

        if not patch.file_patches:
            return PatchValidationResult(
                is_valid=False,
                rejection_reasons=["Candidate patch contains no file modifications."],
            )

        # 1. Size limits
        if patch.total_lines_changed > self.policy.max_diff_lines:
            size_ok = False
            rejection_reasons.append(
                f"Patch diff size ({patch.total_lines_changed} lines) exceeds maximum allowed limit ({self.policy.max_diff_lines} lines)."
            )

        # 2. File-by-file checks
        for fp in patch.file_patches:
            # Containment check
            if not self._check_containment(fp.file_path):
                containment_ok = False
                rejection_reasons.append(f"File path '{fp.file_path}' attempts path traversal outside workspace boundaries.")

            # Syntax check for Python files
            if fp.file_path.endswith(".py"):
                syntax_valid, err_msg = self._check_python_syntax(fp.new_content, fp.file_path)
                if not syntax_valid:
                    syntax_ok = False
                    rejection_reasons.append(f"Syntax validation failed in '{fp.file_path}': {err_msg}")

            # Anti-weakening check
            weakening_detected, reason = self._check_anti_weakening(fp)
            if weakening_detected:
                anti_weakening_ok = False
                rejection_reasons.append(f"Anti-weakening policy violation in '{fp.file_path}': {reason}")

            # Security sensitivity check
            if not self.policy.allow_security_sensitive_changes:
                if any(k in fp.file_path.lower() for k in SECURITY_KEYWORDS):
                    fp.is_security_sensitive = True
                    if patch.risk_level != RiskLevel.CRITICAL:
                        patch.risk_level = RiskLevel.HIGH
                    warnings.append(f"Patch touches security-sensitive file '{fp.file_path}'. Requires human approval.")

        is_valid = containment_ok and syntax_ok and size_ok and anti_weakening_ok and (len(rejection_reasons) == 0)

        return PatchValidationResult(
            is_valid=is_valid,
            rejection_reasons=rejection_reasons,
            warnings=warnings,
            syntax_ok=syntax_ok,
            containment_ok=containment_ok,
            size_ok=size_ok,
            anti_weakening_ok=anti_weakening_ok,
            security_ok=security_ok,
        )

    def _check_containment(self, rel_path: str) -> bool:
        """Verifies path resolves within the authorized workspace."""
        if os.path.isabs(rel_path):
            abs_target = os.path.realpath(rel_path)
        else:
            abs_target = os.path.realpath(os.path.abspath(os.path.join(self.workspace_path, rel_path)))

        return abs_target == self.workspace_path or abs_target.startswith(self.workspace_path + os.sep)

    def _check_python_syntax(self, code: str, filename: str) -> tuple[bool, str]:
        """Parses Python source using AST to ensure valid grammar."""
        try:
            ast.parse(code, filename=filename)
            return True, ""
        except SyntaxError as e:
            return False, f"Line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, str(e)

    def _check_anti_weakening(self, fp: FilePatch) -> tuple[bool, str]:
        """Detects malicious or deceptive test weakening and silent exception swallows."""
        # Check for bare except pass in new content
        bare_except_pass = re.search(r"except(?:\s+Exception)?\s*:\s*(?:pass|\.\.\.)", fp.new_content)
        if bare_except_pass:
            return True, "Detected silent exception suppression (`except: pass`). Defect must be properly resolved."

        # If modifying a test file, ensure assertions are not deleted or replaced with trivial 'assert True'
        if fp.is_test_file:
            orig_asserts = len(re.findall(r"\bassert\b", fp.original_content))
            new_asserts = len(re.findall(r"\bassert\b", fp.new_content))
            if orig_asserts > 0 and new_asserts == 0:
                return True, "Test weakening detected: all assert statements were removed from test file."

            if "assert True" in fp.new_content and "assert True" not in fp.original_content:
                return True, "Test weakening detected: introduced trivial 'assert True'."

        return False, ""
