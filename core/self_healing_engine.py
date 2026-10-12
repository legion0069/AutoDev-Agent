"""
AutoDev Self-Healing Engine (v2.6)
Orchestrates isolated candidate patch application, multi-tier validation gates,
and verified transactional rollback on verification failure.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from core.patch_validator import PatchValidator
from core.regression_test_selector import RegressionTestSelector, TestSelectionResult
from core.repair_models import (
    CandidatePatch,
    PatchStatus,
    PatchValidationResult,
    RepairPlan,
    RepairPolicy,
    ValidationGateStatus,
)
from core.repair_transaction import RepairState, RepairTransaction
from core.test_execution_engine import TestExecutionEngine, TestRunner
from core.test_result_models import TestRunnerType, TestStatus, TestSuiteResult

logger = logging.getLogger(__name__)


class SelfHealingEngine:
    """Coordinates isolated candidate patch testing, validation gates, and safe rollback."""

    def __init__(
        self,
        workspace_path: str,
        policy: Optional[RepairPolicy] = None,
        test_engine: Optional[TestExecutionEngine] = None,
    ):
        self.workspace_path = os.path.realpath(os.path.abspath(workspace_path))
        self.policy = policy or RepairPolicy()
        self.test_engine = test_engine or TestExecutionEngine(self.workspace_path)
        self.patch_validator = PatchValidator(self.workspace_path, self.policy)
        self.test_selector = RegressionTestSelector(self.workspace_path)

    def apply_and_verify(
        self,
        transaction: RepairTransaction,
        patch: CandidatePatch,
        primary_failing_test: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Applies candidate patch, executes all validation gates, and commits or rolls back.
        Returns: (success_boolean, validation_gate_results_dict)
        """
        gate_results: Dict[str, Any] = {
            "gate_1_patch_validation": ValidationGateStatus.FAILED.value,
            "gate_2_syntax_check": ValidationGateStatus.BLOCKED.value,
            "gate_3_primary_test": ValidationGateStatus.BLOCKED.value,
            "gate_4_regression_tests": ValidationGateStatus.BLOCKED.value,
            "rollback_verified": False,
        }

        # --- GATE 1: Patch Structure & Policy Validation ---
        transaction.transition_to(RepairState.PATCH_VALIDATED, "Validating patch static constraints")
        val_result = self.patch_validator.validate(patch)
        gate_results["patch_validation_details"] = val_result.to_dict()

        if not val_result.is_valid:
            gate_results["gate_1_patch_validation"] = ValidationGateStatus.FAILED.value
            transaction.transition_to(RepairState.REJECTED, f"Patch failed static validation: {val_result.rejection_reasons}")
            patch.status = PatchStatus.REJECTED
            return False, gate_results

        gate_results["gate_1_patch_validation"] = ValidationGateStatus.PASSED.value

        # --- SNAPSHOT & APPLICATION IN CANDIDATE STATE ---
        try:
            self._take_snapshots_and_apply(transaction, patch)
            transaction.transition_to(RepairState.APPLIED_IN_CANDIDATE, "Patch applied to candidate files")
            patch.status = PatchStatus.APPLIED
        except Exception as e:
            logger.error(f"Failed during snapshot / patch application: {e}")
            transaction.transition_to(RepairState.RECOVERY_REQUIRED, f"Application error: {str(e)}")
            self.rollback_transaction(transaction)
            return False, gate_results

        # --- GATE 2: Syntax & Parsing Check ---
        transaction.transition_to(RepairState.VERIFYING, "Beginning validation gates")
        syntax_ok = self._verify_syntax_of_modified_files(patch)
        if not syntax_ok:
            gate_results["gate_2_syntax_check"] = ValidationGateStatus.FAILED.value
            self._handle_verification_failure(transaction, patch, "Syntax error in applied patch", gate_results)
            return False, gate_results
        gate_results["gate_2_syntax_check"] = ValidationGateStatus.PASSED.value

        # --- GATE 3: Primary Failing Test ---
        primary_target = primary_failing_test or (transaction.plan.test_id if transaction.plan else None)
        if primary_target:
            primary_suite = self.test_engine.execute_test_suite(
                runner_type=TestRunnerType.PYTEST,
                test_targets=[primary_target],
                timeout_seconds=60,
                transaction_id=transaction.repair_id,
            )
            gate_results["primary_test_result"] = primary_suite.to_dict()

            if not primary_suite.success:
                gate_results["gate_3_primary_test"] = ValidationGateStatus.FAILED.value
                self._handle_verification_failure(transaction, patch, "Primary test failed after repair", gate_results)
                return False, gate_results
            gate_results["gate_3_primary_test"] = ValidationGateStatus.PASSED.value
        else:
            gate_results["gate_3_primary_test"] = ValidationGateStatus.SKIPPED.value

        # --- GATE 4: Risk-Based Regression Suite ---
        selection: TestSelectionResult = self.test_selector.select_tests(
            patch=patch,
            validation_level=self.policy.validation_level,
            primary_failing_test=primary_target,
        )
        gate_results["test_selection"] = selection.to_dict()

        if selection.selected_tests:
            regression_suite = self.test_engine.execute_test_suite(
                runner_type=TestRunnerType.PYTEST,
                test_targets=selection.selected_tests,
                timeout_seconds=120,
                transaction_id=transaction.repair_id,
            )
            gate_results["regression_test_result"] = regression_suite.to_dict()

            if not regression_suite.success:
                gate_results["gate_4_regression_tests"] = ValidationGateStatus.FAILED.value
                self._handle_verification_failure(transaction, patch, "Regression test suite detected failures", gate_results)
                return False, gate_results
            gate_results["gate_4_regression_tests"] = ValidationGateStatus.PASSED.value
        else:
            gate_results["gate_4_regression_tests"] = ValidationGateStatus.SKIPPED.value

        # --- ALL GATES PASSED -> ACCEPT ---
        transaction.transition_to(RepairState.ACCEPTED, "All validation gates passed successfully")
        patch.status = PatchStatus.VERIFIED
        transaction.validation_gate_results = gate_results
        return True, gate_results

    def _take_snapshots_and_apply(self, transaction: RepairTransaction, patch: CandidatePatch):
        """Snapshots original contents before modifying files."""
        for fp in patch.file_patches:
            abs_path = os.path.join(self.workspace_path, fp.file_path)
            orig_content = ""
            if os.path.isfile(abs_path):
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    orig_content = f.read()
            transaction.record_file_snapshot(fp.file_path, orig_content)

            # Atomic file write
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(fp.new_content)

    def _verify_syntax_of_modified_files(self, patch: CandidatePatch) -> bool:
        """Verifies syntax on disk for all modified files."""
        for fp in patch.file_patches:
            if fp.file_path.endswith(".py"):
                abs_path = os.path.join(self.workspace_path, fp.file_path)
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        compile(f.read(), abs_path, "exec")
                except Exception as e:
                    logger.error(f"Syntax compile check failed on {abs_path}: {e}")
                    return False
        return True

    def _handle_verification_failure(
        self,
        transaction: RepairTransaction,
        patch: CandidatePatch,
        reason: str,
        gate_results: Dict[str, Any],
    ):
        """Rolls back changes and sets transaction state on verification failure."""
        transaction.transition_to(RepairState.VERIFICATION_FAILED, reason)
        patch.status = PatchStatus.REJECTED
        if self.policy.rollback_on_verification_failure:
            rollback_ok = self.rollback_transaction(transaction)
            gate_results["rollback_verified"] = rollback_ok

    def rollback_transaction(self, transaction: RepairTransaction) -> bool:
        """Restores original files from snapshots and strictly verifies SHA256 hashes."""
        transaction.transition_to(RepairState.ROLLBACK_PENDING, "Initiating rollback to snapshot baseline")
        all_verified = True

        for rel_path, original_content in transaction.file_snapshots.items():
            abs_path = os.path.join(self.workspace_path, rel_path)
            try:
                if original_content == "" and not os.path.exists(abs_path):
                    continue
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(original_content)

                # Verify restored content hash
                with open(abs_path, "r", encoding="utf-8") as f:
                    restored = f.read()
                expected_hash = hashlib.sha256(original_content.encode("utf-8")).hexdigest()
                actual_hash = hashlib.sha256(restored.encode("utf-8")).hexdigest()
                if expected_hash != actual_hash:
                    all_verified = False
                    logger.critical(f"Rollback hash mismatch for {rel_path}!")
            except Exception as e:
                all_verified = False
                logger.critical(f"Failed restoring {rel_path} during rollback: {e}")

        if all_verified:
            transaction.transition_to(RepairState.ROLLED_BACK, "Rollback verified successfully")
            return True
        else:
            transaction.transition_to(RepairState.RECOVERY_REQUIRED, "Rollback verification failed")
            return False
