"""
AutoDev Self-Healing Orchestrator (v2.6)
Coordinates the autonomous failure investigation, diagnosis, minimal repair planning,
validation gate execution, rollback recovery, and human approval controls.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.diagnostic_models import DiagnosticReport, FailureCategory
from core.failure_classifier import FailureClassifier
from core.patch_generator import PatchGenerator
from core.patch_validator import PatchValidator
from core.repair_models import (
    CandidatePatch,
    PatchStatus,
    RepairMode,
    RepairPlan,
    RepairPolicy,
    RiskLevel,
    ValidationGateStatus,
)
from core.repair_recovery import RepairJournal, RepairRecoveryManager
from core.repair_transaction import RepairState, RepairTransaction
from core.root_cause_analyzer import RootCauseAnalyzer
from core.self_healing_engine import SelfHealingEngine
from core.test_execution_engine import TestExecutionEngine
from core.test_result_models import FailureType, SingleTestResult, TestRunnerType, TestStatus, TestSuiteResult

logger = logging.getLogger(__name__)


@dataclass
class SelfHealingExecutionSummary:
    """Complete summary of an autonomous self-healing repair run."""
    repair_id: str
    project_id: str
    initial_failure: str
    diagnostic_report: Optional[Dict[str, Any]] = None
    repair_plan: Optional[Dict[str, Any]] = None
    candidate_patch: Optional[Dict[str, Any]] = None
    final_state: str = RepairState.CREATED.value
    success: bool = False
    attempts_made: int = 0
    duration_ms: float = 0.0
    validation_gates: Dict[str, Any] = field(default_factory=dict)
    rollback_performed: bool = False
    human_approval_required: bool = False
    summary_markdown: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SelfHealingOrchestrator:
    """Orchestrates test intelligence, root-cause diagnosis, minimal repair, and verification."""

    def __init__(
        self,
        workspace_path: str,
        policy: Optional[RepairPolicy] = None,
        llm_client: Optional[Any] = None,
        journal_path: Optional[str] = None,
    ):
        self.workspace_path = os.path.realpath(os.path.abspath(workspace_path))
        self.policy = policy or RepairPolicy()
        self.llm_client = llm_client

        self.test_engine = TestExecutionEngine(self.workspace_path)
        self.analyzer = RootCauseAnalyzer(self.workspace_path, self.llm_client)
        self.patch_generator = PatchGenerator(self.workspace_path, self.llm_client)
        self.patch_validator = PatchValidator(self.workspace_path, self.policy)
        self.engine = SelfHealingEngine(self.workspace_path, self.policy, self.test_engine)

        j_path = journal_path or os.path.join(self.workspace_path, ".autodev", "repair_journal.jsonl")
        self.journal = RepairJournal(j_path)
        self.recovery_mgr = RepairRecoveryManager(self.workspace_path, self.journal, self.engine)

        # Reconcile any interrupted transactions on startup
        self.recovery_mgr.reconcile_on_startup()

    def run_self_healing_workflow(
        self,
        failing_test_id: Optional[str] = None,
        initial_test_result: Optional[SingleTestResult] = None,
        file_modifications: Optional[Dict[str, str]] = None,
        human_approval_callback: Optional[Callable[[RepairPlan, CandidatePatch], bool]] = None,
    ) -> SelfHealingExecutionSummary:
        """
        Runs the end-to-end self-healing lifecycle within policy budgets and safety bounds.
        """
        start_time = time.perf_counter()
        repair_id = f"repair_{uuid.uuid4().hex[:8]}"
        transaction = RepairTransaction(repair_id=repair_id)
        self.journal.append_entry(transaction)

        # 1. Obtain or execute failing test
        test_res = initial_test_result
        if not test_res and failing_test_id:
            suite = self.test_engine.execute_test_suite(
                runner_type=TestRunnerType.PYTEST,
                test_targets=[failing_test_id],
                timeout_seconds=60,
                transaction_id=repair_id,
            )
            if suite.failing_tests:
                test_res = suite.failing_tests[0]
            elif suite.tests:
                test_res = suite.tests[0]

        if not test_res:
            test_res = SingleTestResult(
                test_id=failing_test_id or "unknown_test",
                test_name=failing_test_id or "unknown_test",
                status=TestStatus.FAILED,
                message="Unknown initial failure",
            )

        # 2. Evidence-Based Root Cause Diagnosis
        transaction.transition_to(RepairState.DIAGNOSING, "Analyzing test failure and extracting evidence")
        self.journal.append_entry(transaction)

        diag_report = self.analyzer.analyze(
            test_result=test_res,
            run_id=repair_id,
            transaction_id=repair_id,
        )

        # Check for environmental non-defect failures
        selected_hypo = diag_report.selected_hypothesis
        if selected_hypo and selected_hypo.is_environmental:
            transaction.transition_to(RepairState.REJECTED, "Environmental failure detected; no code repair needed.")
            self.journal.append_entry(transaction)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return SelfHealingExecutionSummary(
                repair_id=repair_id,
                project_id=transaction.project_id,
                initial_failure=test_res.message,
                diagnostic_report=diag_report.to_dict(),
                final_state=transaction.state.value,
                success=False,
                attempts_made=0,
                duration_ms=duration_ms,
                summary_markdown="### Environmental Failure\nNo code modification performed. Please verify external service configuration.",
            )

        # 3. Formulate Repair Plan
        from core.repair_planner import RepairPlanner
        planner = RepairPlanner(self.workspace_path, self.policy)
        plan = planner.create_repair_plan(diag_report, selected_hypo)

        # Ensure explicit file modifications are reflected in plan target files
        if file_modifications:
            if not plan:
                plan = RepairPlan(
                    test_id=test_res.test_id,
                    target_files=list(file_modifications.keys()),
                    rationale="Direct candidate file modifications provided",
                )
            else:
                for mod_file in file_modifications.keys():
                    if mod_file not in plan.target_files:
                        plan.target_files.append(mod_file)

        transaction.plan = plan
        transaction.transition_to(RepairState.PLANNED, f"Repair plan generated: {plan.rationale if plan else 'None'}")
        self.journal.append_entry(transaction)

        if not plan or not plan.target_files:
            transaction.transition_to(RepairState.REJECTED, "Cannot formulate repair plan: no target files identified.")
            self.journal.append_entry(transaction)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return SelfHealingExecutionSummary(
                repair_id=repair_id,
                project_id=transaction.project_id,
                initial_failure=test_res.message,
                diagnostic_report=diag_report.to_dict(),
                final_state=transaction.state.value,
                success=False,
                duration_ms=duration_ms,
                summary_markdown="### Repair Planning Incomplete\nInsufficient diagnostic evidence to select target files.",
            )

        # 4. Generate Candidate Patch
        transaction.transition_to(RepairState.PATCH_GENERATED, "Generating minimal candidate patch")
        patch = self.patch_generator.generate_patch(
            plan=plan,
            diagnostic_report=diag_report,
            file_modifications=file_modifications,
        )
        transaction.patch = patch
        self.journal.append_entry(transaction)

        if not patch:
            transaction.transition_to(RepairState.REJECTED, "Failed to generate candidate patch.")
            self.journal.append_entry(transaction)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return SelfHealingExecutionSummary(
                repair_id=repair_id,
                project_id=transaction.project_id,
                initial_failure=test_res.message,
                diagnostic_report=diag_report.to_dict(),
                repair_plan=plan.to_dict(),
                final_state=transaction.state.value,
                success=False,
                duration_ms=duration_ms,
                summary_markdown="### Candidate Patch Generation Failed\nCould not construct valid code modification.",
            )

        # Check OBSERVE_ONLY Mode
        if self.policy.mode == RepairMode.OBSERVE_ONLY:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return SelfHealingExecutionSummary(
                repair_id=repair_id,
                project_id=transaction.project_id,
                initial_failure=test_res.message,
                diagnostic_report=diag_report.to_dict(),
                repair_plan=plan.to_dict(),
                candidate_patch=patch.to_dict(),
                final_state=transaction.state.value,
                success=True,
                duration_ms=duration_ms,
                summary_markdown="### Observe-Only Mode\nCandidate patch generated but not applied per policy.",
            )

        # Check Human Approval Gate
        is_approval_needed = plan.requires_human_approval or (self.policy.mode == RepairMode.ASSISTED)
        if is_approval_needed:
            transaction.transition_to(RepairState.NEEDS_HUMAN_REVIEW, "Human review required before candidate application")
            self.journal.append_entry(transaction)
            approved = True
            if human_approval_callback:
                approved = human_approval_callback(plan, patch)
            
            if not approved:
                transaction.transition_to(RepairState.REJECTED, "Repair rejected by human reviewer")
                self.journal.append_entry(transaction)
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                return SelfHealingExecutionSummary(
                    repair_id=repair_id,
                    project_id=transaction.project_id,
                    initial_failure=test_res.message,
                    diagnostic_report=diag_report.to_dict(),
                    repair_plan=plan.to_dict(),
                    candidate_patch=patch.to_dict(),
                    final_state=transaction.state.value,
                    success=False,
                    human_approval_required=True,
                    duration_ms=duration_ms,
                    summary_markdown="### Human Approval Denied\nCandidate patch rejected during human review gate.",
                )

        # 5. Apply and Verify Candidate Patch
        success, gate_results = self.engine.apply_and_verify(
            transaction=transaction,
            patch=patch,
            primary_failing_test=failing_test_id,
        )
        self.journal.append_entry(transaction)
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        summary_md = self._render_summary_markdown(transaction, plan, patch, diag_report, gate_results, success)

        return SelfHealingExecutionSummary(
            repair_id=repair_id,
            project_id=transaction.project_id,
            initial_failure=test_res.message,
            diagnostic_report=diag_report.to_dict(),
            repair_plan=plan.to_dict(),
            candidate_patch=patch.to_dict(),
            final_state=transaction.state.value,
            success=success,
            attempts_made=1,
            duration_ms=duration_ms,
            validation_gates=gate_results,
            rollback_performed=gate_results.get("rollback_verified", False),
            human_approval_required=is_approval_needed,
            summary_markdown=summary_md,
        )

    def _render_summary_markdown(
        self,
        transaction: RepairTransaction,
        plan: RepairPlan,
        patch: CandidatePatch,
        diag: DiagnosticReport,
        gates: Dict[str, Any],
        success: bool,
    ) -> str:
        status_badge = "✅ **REPAIR ACCEPTED & VERIFIED**" if success else "❌ **REPAIR VERIFICATION FAILED (ROLLED BACK)**"
        return (
            f"## AutoDev v2.6 Self-Healing Report\n\n"
            f"**Status:** {status_badge}\n"
            f"- **Repair ID:** `{transaction.repair_id}`\n"
            f"- **Target Files:** {', '.join(plan.target_files)}\n"
            f"- **Diff Size:** {patch.total_lines_changed} lines\n\n"
            f"### Root Cause Diagnosis\n"
            f"- **Category:** `{diag.selected_hypothesis.failure_category.value if diag.selected_hypothesis else 'unknown'}`\n"
            f"- **Confidence:** `{diag.selected_hypothesis.confidence if diag.selected_hypothesis else 0.0:.2f}`\n"
            f"- **Summary:** {plan.rationale}\n\n"
            f"### Validation Gates\n"
            f"- Gate 1 (Patch Structure): `{gates.get('gate_1_patch_validation')}`\n"
            f"- Gate 2 (Syntax Check): `{gates.get('gate_2_syntax_check')}`\n"
            f"- Gate 3 (Primary Test): `{gates.get('gate_3_primary_test')}`\n"
            f"- Gate 4 (Regression Suite): `{gates.get('gate_4_regression_tests')}`\n"
            f"- Rollback Verified: `{gates.get('rollback_verified')}`\n"
        )
