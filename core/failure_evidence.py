"""
AutoDev Failure Evidence Collector (v2.6)
Extracts, structures, and bounds failure context from test outcomes,
stack traces, symbol graphs, impact analyses, and workspace source code.
"""

from __future__ import annotations

import ast
import linecache
import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Set

from core.diagnostic_models import FailureEvidence, StackFrameEvidence
from core.test_result_models import SingleTestResult, bound_log_text, redact_secrets

logger = logging.getLogger(__name__)


class FailureEvidenceCollector:
    """Collects structured evidence from failing tests, stack traces, ASTs, and symbol graphs."""

    def __init__(self, workspace_path: str):
        self.workspace_path = os.path.realpath(os.path.abspath(workspace_path))

    def parse_stack_trace(self, stack_text: str) -> List[StackFrameEvidence]:
        """Parses standard Python traceback text into structured StackFrameEvidence."""
        frames: List[StackFrameEvidence] = []
        if not stack_text:
            return frames

        # Python traceback format: File "path/to/file.py", line 123, in func_name
        frame_pattern = re.compile(r'File\s+["\']([^"\']+)["\'],\s+line\s+(\d+)(?:,\s+in\s+([^\n\r]+))?')
        
        lines = stack_text.splitlines()
        for i, line in enumerate(lines):
            match = frame_pattern.search(line)
            if match:
                raw_file = match.group(1).strip()
                line_no = int(match.group(2))
                func_name = match.group(3).strip() if match.group(3) else "<module>"
                
                # Check next line for code snippet
                code_line = ""
                if i + 1 < len(lines) and not lines[i + 1].strip().startswith("File "):
                    code_line = lines[i + 1].strip()

                # Normalize and check workspace containment
                abs_file = os.path.realpath(os.path.abspath(os.path.join(self.workspace_path, raw_file)))
                is_in_ws = abs_file.startswith(self.workspace_path + os.sep) or abs_file == self.workspace_path
                
                rel_path = raw_file
                if is_in_ws:
                    try:
                        rel_path = os.path.relpath(abs_file, self.workspace_path)
                    except Exception:
                        rel_path = raw_file

                frames.append(
                    StackFrameEvidence(
                        file_path=rel_path,
                        line_number=line_no,
                        function_name=func_name,
                        code_line=code_line,
                        is_in_workspace=is_in_ws,
                    )
                )
        return frames

    def extract_source_context(
        self,
        rel_file_path: str,
        target_line: int,
        context_radius: int = 5,
    ) -> List[str]:
        """Extracts source lines surrounding a target line in the workspace."""
        abs_path = os.path.join(self.workspace_path, rel_file_path)
        if not os.path.isfile(abs_path):
            return []

        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            start = max(0, target_line - context_radius - 1)
            end = min(len(lines), target_line + context_radius)
            
            snippet = []
            for idx in range(start, end):
                prefix = ">>" if (idx + 1) == target_line else "  "
                snippet.append(f"{prefix} {idx + 1:4d}: {lines[idx].rstrip()}")
            return snippet
        except Exception as e:
            logger.warning(f"Could not read source context from {abs_path}: {e}")
            return []

    def extract_affected_symbols(self, rel_file_path: str, line_no: int) -> List[str]:
        """Finds functions and classes enclosing the line number using AST analysis."""
        abs_path = os.path.join(self.workspace_path, rel_file_path)
        if not os.path.isfile(abs_path) or not abs_path.endswith(".py"):
            return []

        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                tree = ast.parse(f.read(), filename=abs_path)

            enclosing_symbols = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    start = getattr(node, "lineno", 0)
                    end = getattr(node, "end_lineno", start + 50)
                    if start <= line_no <= end:
                        kind = "class" if isinstance(node, ast.ClassDef) else "def"
                        enclosing_symbols.append(f"{kind} {node.name} (L{start}-L{end})")
            return enclosing_symbols
        except Exception:
            return []

    def collect_evidence(
        self,
        test_result: SingleTestResult,
        recently_changed_files: Optional[List[str]] = None,
        recent_diffs: Optional[Dict[str, str]] = None,
        impact_summary: Optional[Dict[str, Any]] = None,
        journal_events: Optional[List[Dict[str, Any]]] = None,
    ) -> FailureEvidence:
        """Assembles a bounded, complete FailureEvidence bundle for diagnosis."""
        raw_stack = f"{test_result.stack_trace}\n{test_result.message}"
        sanitized_stack = redact_secrets(raw_stack)
        frames = self.parse_stack_trace(sanitized_stack)

        # Focus on the most recent in-workspace frame
        ws_frames = [f for f in frames if f.is_in_workspace]
        primary_frame = ws_frames[-1] if ws_frames else (frames[-1] if frames else None)

        failing_lines = []
        affected_symbols: List[str] = []
        if primary_frame and primary_frame.is_in_workspace:
            failing_lines = self.extract_source_context(primary_frame.file_path, primary_frame.line_number)
            affected_symbols = self.extract_affected_symbols(primary_frame.file_path, primary_frame.line_number)

        evidence = FailureEvidence(
            test_id=test_result.test_id,
            test_name=test_result.test_name,
            test_file=test_result.test_file,
            failure_message=redact_secrets(test_result.message),
            stack_trace=bound_log_text(sanitized_stack, max_bytes=8192),
            stack_frames=frames[:15],  # Bound to top 15 frames
            failing_source_lines=failing_lines,
            affected_symbols=affected_symbols,
            recently_changed_files=recently_changed_files or [],
            recent_diffs=recent_diffs or {},
            impact_analysis_summary=impact_summary or {},
            journal_events=journal_events or [],
            is_environmental=False,
            is_flaky=test_result.flaky,
            redacted=True,
        )
        return evidence
