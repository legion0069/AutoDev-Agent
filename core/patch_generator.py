"""
AutoDev Patch Generator (v2.6)
Generates minimal, defensible CandidatePatch objects with unified diffs,
hashing, and adherence to minimal-diff policies.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from core.diagnostic_models import DiagnosticReport
from core.repair_models import CandidatePatch, FilePatch, PatchStatus, RepairPlan, RiskLevel

logger = logging.getLogger(__name__)


class PatchGenerator:
    """Generates minimal, targeted candidate patches from a repair plan and diagnostic context."""

    def __init__(self, workspace_path: str, llm_client: Optional[Any] = None):
        self.workspace_path = os.path.realpath(os.path.abspath(workspace_path))
        self.llm_client = llm_client

    def generate_patch(
        self,
        plan: RepairPlan,
        diagnostic_report: Optional[DiagnosticReport] = None,
        file_modifications: Optional[Dict[str, str]] = None,
    ) -> Optional[CandidatePatch]:
        """
        Creates a CandidatePatch either from direct file modifications
        or by prompting the LLM for a minimal targeted diff.
        """
        if file_modifications:
            return self._build_patch_from_modifications(plan, file_modifications)

        if not plan.target_files:
            logger.warning("No target files in repair plan.")
            return None

        # If LLM client is available, request minimal repair
        if self.llm_client:
            return self._generate_llm_patch(plan, diagnostic_report)

        return None

    def _build_patch_from_modifications(
        self,
        plan: RepairPlan,
        file_modifications: Dict[str, str],
    ) -> CandidatePatch:
        """Builds a structured CandidatePatch from explicit file new contents."""
        file_patches: List[FilePatch] = []

        for rel_path, new_content in file_modifications.items():
            abs_path = os.path.join(self.workspace_path, rel_path)
            original_content = ""
            if os.path.isfile(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                        original_content = f.read()
                except Exception as e:
                    logger.warning(f"Failed to read original file {abs_path}: {e}")

            # Compute unified diff
            orig_lines = original_content.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            diff_lines = list(
                difflib.unified_diff(
                    orig_lines,
                    new_lines,
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}",
                )
            )
            diff_str = "".join(diff_lines)

            added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

            file_patches.append(
                FilePatch(
                    file_path=rel_path,
                    original_content=original_content,
                    new_content=new_content,
                    diff_unified=diff_str,
                    lines_added=added,
                    lines_removed=removed,
                )
            )

        return CandidatePatch(
            plan_id=plan.plan_id,
            hypothesis_id=plan.hypothesis_id,
            file_patches=file_patches,
            rationale=plan.rationale,
            risk_level=plan.risk_level,
            status=PatchStatus.DRAFT,
        )

    def _generate_llm_patch(
        self,
        plan: RepairPlan,
        diagnostic_report: Optional[DiagnosticReport] = None,
    ) -> Optional[CandidatePatch]:
        """Queries LLM with strict context constraints to produce minimal file repairs."""
        target_file = plan.target_files[0]
        abs_path = os.path.join(self.workspace_path, target_file)
        if not os.path.isfile(abs_path):
            return None

        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            original_content = f.read()

        prompt = (
            "You are AutoDev Minimal-Patch Repair Engine. Repair the identified defect with the SMALLEST necessary change.\n"
            "Do NOT rewrite entire files. Do NOT remove or weaken tests. Do NOT silence exceptions with empty try-except.\n\n"
            f"Failing Test / Behavior: {plan.failing_behavior}\n"
            f"Expected Behavior: {plan.expected_behavior}\n"
            f"Target File: {target_file}\n\n"
            f"Original Content:\n```python\n{original_content}\n```\n\n"
            "Return JSON matching:\n"
            "{\n"
            '  "file_path": "' + target_file + '",\n'
            '  "new_content": "complete new content of the file",\n'
            '  "rationale": "one sentence explaining the minimal change"\n'
            "}"
        )

        try:
            response = self.llm_client.generate(prompt) if hasattr(self.llm_client, "generate") else self.llm_client.chat([{"role": "user", "content": prompt}])
            raw_text = response if isinstance(response, str) else getattr(response, "content", str(response))
            
            json_match = re.search(r"\{[\s\S]*\}", raw_text)
            if not json_match:
                return None

            data = json.loads(json_match.group(0))
            new_content = data.get("new_content", "")
            if not new_content:
                return None

            return self._build_patch_from_modifications(
                plan=plan,
                file_modifications={target_file: new_content},
            )
        except Exception as e:
            logger.warning(f"LLM patch generation failed: {e}")
            return None
