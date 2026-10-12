"""
AutoDev Root-Cause Analyzer (v2.6)
Deterministic diagnostics and schema-constrained LLM hypothesis generation
for evidence-based root-cause identification.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from core.diagnostic_models import (
    ConfidenceLevel,
    DiagnosticReport,
    FailureCategory,
    FailureEvidence,
    RootCauseHypothesis,
)
from core.failure_classifier import FailureClassifier
from core.failure_evidence import FailureEvidenceCollector
from core.test_result_models import FailureType, SingleTestResult

logger = logging.getLogger(__name__)


class RootCauseAnalyzer:
    """Analyzes test failure evidence using deterministic heuristics first, with optional LLM enhancement."""

    def __init__(self, workspace_path: str, llm_client: Optional[Any] = None):
        self.workspace_path = os.path.realpath(os.path.abspath(workspace_path))
        self.evidence_collector = FailureEvidenceCollector(self.workspace_path)
        self.llm_client = llm_client

    def analyze(
        self,
        test_result: SingleTestResult,
        recently_changed_files: Optional[List[str]] = None,
        recent_diffs: Optional[Dict[str, str]] = None,
        impact_summary: Optional[Dict[str, Any]] = None,
        journal_events: Optional[List[Dict[str, Any]]] = None,
        run_id: str = "",
        transaction_id: Optional[str] = None,
    ) -> DiagnosticReport:
        """Performs complete diagnostic workflow: evidence collection, deterministic rules, and ranking."""
        evidence = self.evidence_collector.collect_evidence(
            test_result=test_result,
            recently_changed_files=recently_changed_files,
            recent_diffs=recent_diffs,
            impact_summary=impact_summary,
            journal_events=journal_events,
        )

        hypotheses: List[RootCauseHypothesis] = []
        deterministic_findings: List[str] = []

        # 1. Deterministic diagnostics
        det_hypo, findings = self._run_deterministic_analysis(test_result, evidence)
        if det_hypo:
            hypotheses.append(det_hypo)
        deterministic_findings.extend(findings)

        # 2. LLM-assisted analysis if needed and available
        llm_enhanced = False
        if self.llm_client and (not hypotheses or hypotheses[0].confidence < 0.90):
            llm_hypotheses = self._generate_llm_hypotheses(test_result, evidence)
            if llm_hypotheses:
                hypotheses.extend(llm_hypotheses)
                llm_enhanced = True

        # Fallback hypothesis if none generated
        if not hypotheses:
            hypotheses.append(
                RootCauseHypothesis(
                    summary=f"Unresolved failure in {test_result.test_name}: {test_result.message[:100]}",
                    failure_category=FailureCategory.UNKNOWN,
                    affected_files=[test_result.test_file] if test_result.test_file else [],
                    supporting_evidence=[test_result.message],
                    confidence=0.20,
                    confidence_level=ConfidenceLevel.UNCERTAIN,
                    estimated_risk="high",
                    recommended_next_action="Manual inspection required",
                    requires_human_review=True,
                )
            )

        # Sort hypotheses by confidence descending
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        selected_hypo = hypotheses[0] if hypotheses else None

        report = DiagnosticReport(
            run_id=run_id or f"run_{uuid.uuid4().hex[:6]}",
            project_id="default_project",
            transaction_id=transaction_id,
            test_id=test_result.test_id,
            evidence=evidence,
            hypotheses=hypotheses,
            selected_hypothesis=selected_hypo,
            deterministic_findings=deterministic_findings,
            llm_enhanced=llm_enhanced,
        )
        return report

    def _run_deterministic_analysis(
        self,
        test_result: SingleTestResult,
        evidence: FailureEvidence,
    ) -> Tuple[Optional[RootCauseHypothesis], List[str]]:
        """Applies deterministic diagnostic rules directly to stack frames and error messages."""
        findings: List[str] = []
        msg = test_result.message
        stack = test_result.stack_trace
        combined = f"{msg}\n{stack}"

        # Check for Environmental / Network failures
        if FailureClassifier.is_environmental(test_result.failure_type or FailureType.UNKNOWN_FAILURE):
            findings.append("Identified external service/environment failure.")
            return (
                RootCauseHypothesis(
                    summary=f"Environmental failure detected: {msg[:120]}",
                    failure_category=FailureCategory.ENVIRONMENTAL,
                    affected_files=[],
                    affected_symbols=[],
                    supporting_evidence=[msg],
                    confidence=0.95,
                    confidence_level=ConfidenceLevel.CERTAIN,
                    estimated_risk="low",
                    recommended_next_action="Verify external infrastructure, services, or environment configuration",
                    requires_human_review=True,
                    is_environmental=True,
                    suggested_fix_description="No code change needed; verify external services.",
                ),
                findings,
            )

        # Check for Syntax Errors
        if test_result.failure_type == FailureType.SYNTAX_ERROR or "SyntaxError" in combined:
            findings.append("Deterministic syntax error identified.")
            target_file = ""
            target_line = 0
            for frame in reversed(evidence.stack_frames):
                if frame.is_in_workspace:
                    target_file = frame.file_path
                    target_line = frame.line_number
                    break

            return (
                RootCauseHypothesis(
                    summary=f"Syntax error in {target_file or 'source'}: {msg[:100]}",
                    failure_category=FailureCategory.SYNTAX_ERROR,
                    affected_files=[target_file] if target_file else [],
                    affected_symbols=[],
                    supporting_evidence=[msg] + evidence.failing_source_lines[:3],
                    confidence=0.98,
                    confidence_level=ConfidenceLevel.CERTAIN,
                    estimated_risk="low",
                    recommended_next_action="Fix syntax at specified line",
                    suggested_fix_description="Correct the invalid Python syntax token or indentation.",
                ),
                findings,
            )

        # Check for Import / Module Errors
        if test_result.failure_type == FailureType.IMPORT_FAILURE or "ModuleNotFoundError" in combined or "ImportError" in combined:
            findings.append("Deterministic module resolution or import error identified.")
            target_files = [f.file_path for f in evidence.stack_frames if f.is_in_workspace]
            return (
                RootCauseHypothesis(
                    summary=f"Import resolution error: {msg[:100]}",
                    failure_category=FailureCategory.IMPORT_ERROR,
                    affected_files=target_files[:2],
                    affected_symbols=[],
                    supporting_evidence=[msg],
                    confidence=0.92,
                    confidence_level=ConfidenceLevel.CERTAIN,
                    estimated_risk="low",
                    recommended_next_action="Correct module import path or restore missing symbol",
                    suggested_fix_description="Fix import statement or add missing export.",
                ),
                findings,
            )

        # Check for Assertion Errors
        if test_result.failure_type == FailureType.ASSERTION_FAILURE or "AssertionError" in combined or "assert " in combined:
            findings.append("Deterministic assertion mismatch identified.")
            target_files = [f.file_path for f in evidence.stack_frames if f.is_in_workspace and not f.file_path.startswith("tests")]
            if not target_files:
                target_files = [f.file_path for f in evidence.stack_frames if f.is_in_workspace]

            return (
                RootCauseHypothesis(
                    summary=f"Logic / boundary failure leading to assertion mismatch in {test_result.test_name}",
                    failure_category=FailureCategory.LOGIC_ERROR,
                    affected_files=target_files[:2],
                    affected_symbols=evidence.affected_symbols[:2],
                    supporting_evidence=[msg] + evidence.failing_source_lines[:4],
                    confidence=0.85,
                    confidence_level=ConfidenceLevel.HIGH,
                    estimated_risk="medium",
                    recommended_next_action="Inspect business logic return value or condition",
                    suggested_fix_description="Adjust algorithm to produce expected value matching specification.",
                ),
                findings,
            )

        # Check for Type Errors
        if test_result.failure_type == FailureType.TYPE_CHECKING_FAILURE or "TypeError" in combined:
            findings.append("Deterministic type mismatch identified.")
            target_files = [f.file_path for f in evidence.stack_frames if f.is_in_workspace]
            return (
                RootCauseHypothesis(
                    summary=f"Type mismatch error: {msg[:100]}",
                    failure_category=FailureCategory.TYPE_MISMATCH,
                    affected_files=target_files[:2],
                    affected_symbols=evidence.affected_symbols[:2],
                    supporting_evidence=[msg],
                    confidence=0.88,
                    confidence_level=ConfidenceLevel.HIGH,
                    estimated_risk="medium",
                    recommended_next_action="Cast or validate argument types",
                    suggested_fix_description="Ensure arguments match required type signatures.",
                ),
                findings,
            )

        return None, findings

    def _generate_llm_hypotheses(
        self,
        test_result: SingleTestResult,
        evidence: FailureEvidence,
    ) -> List[RootCauseHypothesis]:
        """Queries LLM with structured diagnostic schema to produce ranked hypotheses."""
        prompt = (
            "You are AutoDev's Diagnostic Engine. Analyze this test failure and produce structured root-cause hypotheses.\n\n"
            f"Test Name: {test_result.test_name}\n"
            f"Test File: {test_result.test_file}\n"
            f"Failure Message: {evidence.failure_message}\n"
            f"Stack Trace Summary:\n{evidence.stack_trace[:1500]}\n\n"
            f"Failing Source Lines:\n{chr(10).join(evidence.failing_source_lines[:10])}\n\n"
            "Return JSON matching this schema:\n"
            "{\n"
            '  "hypotheses": [\n'
            "    {\n"
            '      "summary": "Brief explanation of root cause",\n'
            '      "failure_category": "logic_error|boundary_condition|off_by_one|null_dereference|syntax_error|type_mismatch|unknown",\n'
            '      "affected_files": ["path/to/file.py"],\n'
            '      "affected_symbols": ["function_or_class_name"],\n'
            '      "supporting_evidence": ["evidence points"],\n'
            '      "confidence": 0.85,\n'
            '      "estimated_risk": "low|medium|high",\n'
            '      "suggested_fix_description": "What specifically needs to be changed"\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        try:
            response = self.llm_client.generate(prompt) if hasattr(self.llm_client, "generate") else self.llm_client.chat([{"role": "user", "content": prompt}])
            raw_text = response if isinstance(response, str) else getattr(response, "content", str(response))
            
            # Extract JSON block
            json_match = re.search(r"\{[\s\S]*\}", raw_text)
            if not json_match:
                return []

            data = json.loads(json_match.group(0))
            hypo_list = []
            for item in data.get("hypotheses", []):
                cat_str = item.get("failure_category", "unknown")
                try:
                    cat = FailureCategory(cat_str)
                except Exception:
                    cat = FailureCategory.UNKNOWN

                conf = float(item.get("confidence", 0.6))
                conf = max(0.1, min(conf, 0.95))

                hypo_list.append(
                    RootCauseHypothesis(
                        summary=item.get("summary", "LLM proposed root cause"),
                        failure_category=cat,
                        affected_files=item.get("affected_files", []),
                        affected_symbols=item.get("affected_symbols", []),
                        supporting_evidence=item.get("supporting_evidence", []),
                        confidence=conf,
                        estimated_risk=item.get("estimated_risk", "medium"),
                        suggested_fix_description=item.get("suggested_fix_description", ""),
                    )
                )
            return hypo_list
        except Exception as e:
            logger.warning(f"LLM root cause generation failed: {e}")
            return []
