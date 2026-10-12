"""
AutoDev Collaboration Framework - Synchronization Manager (v2.8)
================================================================
Deterministic synchronization checkpoints, quality gates, multi-agent
barrier synchronization, and validation verification prior to merge,
release, architecture change, or deployment.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .collaboration_models import (
    AgentRole,
    SyncCheckpoint,
    SyncCheckpointType,
)

logger = logging.getLogger("autodev.collaboration.synchronization_manager")


class SynchronizationManager:
    """
    Manages coordination barriers, synchronization gates, and multi-domain
    pre-flight validations (tests, security audit, architecture, documentation)
    across concurrent autonomous engineering agents.
    """

    DEFAULT_VALIDATIONS = {
        SyncCheckpointType.PRE_MERGE: ["dependencies", "tests", "security"],
        SyncCheckpointType.PRE_RELEASE: ["tests", "security", "documentation", "versioning"],
        SyncCheckpointType.POST_ARCHITECTURE: ["interface_compatibility", "dependency_graph"],
        SyncCheckpointType.PRE_DEPLOYMENT: ["smoke_tests", "security_scan", "config_validation"],
    }

    def __init__(self, bus=None, workspace=None):
        self.bus = bus
        self.workspace = workspace
        self._lock = threading.RLock()
        self._checkpoints: Dict[str, SyncCheckpoint] = {}
        self._barrier_events: Dict[str, threading.Event] = {}
        self._history: List[SyncCheckpoint] = []

    # ------------------------------------------------------------------
    # Checkpoint Lifecycle
    # ------------------------------------------------------------------

    def create_checkpoint(
        self,
        checkpoint_type: SyncCheckpointType,
        name: str,
        required_validations: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> SyncCheckpoint:
        """Create and register a new synchronization checkpoint."""
        reqs = required_validations or self.DEFAULT_VALIDATIONS.get(
            checkpoint_type, ["tests", "security", "documentation"]
        )

        checkpoint = SyncCheckpoint(
            checkpoint_type=checkpoint_type,
            name=name,
            required_validations=list(reqs),
            context=context or {},
        )

        with self._lock:
            self._checkpoints[checkpoint.checkpoint_id] = checkpoint
            self._barrier_events[checkpoint.checkpoint_id] = threading.Event()

        logger.info(
            "Created Sync Checkpoint '%s' [%s] (ID: %s) with required validations: %s",
            name,
            checkpoint_type.value,
            checkpoint.checkpoint_id,
            reqs,
        )
        return checkpoint

    def record_validation(
        self,
        checkpoint_id: str,
        validator_agent: str,
        validation_type: str,
        passed: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Record a validation result from a specialized agent (e.g. TestingAgent, SecurityAgent).
        """
        with self._lock:
            checkpoint = self._checkpoints.get(checkpoint_id)
            if not checkpoint:
                raise KeyError(f"Checkpoint '{checkpoint_id}' does not exist.")

            checkpoint.validation_results[validation_type] = {
                "validator": validator_agent,
                "passed": passed,
                "timestamp": time.time(),
                "details": details or {},
            }

            if not passed:
                blocker_msg = f"Validation '{validation_type}' failed by {validator_agent}: {details.get('reason', 'Check details') if details else 'No details'}"
                if blocker_msg not in checkpoint.blockers:
                    checkpoint.blockers.append(blocker_msg)
            else:
                # Remove any existing blocker for this validation_type if now passing
                checkpoint.blockers = [b for b in checkpoint.blockers if not b.startswith(f"Validation '{validation_type}'")]

            # Auto-evaluate barrier completion
            all_passed, _ = self._evaluate_internal(checkpoint)
            if all_passed:
                checkpoint.passed = True
                if checkpoint_id in self._barrier_events:
                    self._barrier_events[checkpoint_id].set()

            return passed

    def evaluate_checkpoint(self, checkpoint_id: str) -> Tuple[bool, List[str]]:
        """
        Evaluate whether all required validations for the checkpoint have been satisfied.
        Returns: (all_passed: bool, pending_or_failed_items: List[str])
        """
        with self._lock:
            checkpoint = self._checkpoints.get(checkpoint_id)
            if not checkpoint:
                raise KeyError(f"Checkpoint '{checkpoint_id}' does not exist.")
            return self._evaluate_internal(checkpoint)

    def _evaluate_internal(self, checkpoint: SyncCheckpoint) -> Tuple[bool, List[str]]:
        """Internal evaluation helper under lock."""
        missing_or_failed: List[str] = []

        for req in checkpoint.required_validations:
            res = checkpoint.validation_results.get(req)
            if res is None:
                missing_or_failed.append(f"Pending: validation '{req}' has not been reported")
            elif not res.get("passed", False):
                missing_or_failed.append(f"Failed: validation '{req}' by {res.get('validator')}")

        if checkpoint.blockers:
            missing_or_failed.extend(checkpoint.blockers)

        is_passed = len(missing_or_failed) == 0
        checkpoint.passed = is_passed
        return is_passed, missing_or_failed

    def wait_for_barrier(self, checkpoint_id: str, timeout_seconds: float = 10.0) -> bool:
        """
        Block current thread until the synchronization barrier is cleared or timeout occurs.
        """
        event = None
        with self._lock:
            event = self._barrier_events.get(checkpoint_id)
            checkpoint = self._checkpoints.get(checkpoint_id)
            if checkpoint and checkpoint.passed:
                return True

        if not event:
            return False

        passed = event.wait(timeout=timeout_seconds)
        return passed

    def complete_checkpoint(self, checkpoint_id: str, force: bool = False) -> bool:
        """
        Mark a checkpoint as completed and archive into history.
        """
        with self._lock:
            checkpoint = self._checkpoints.get(checkpoint_id)
            if not checkpoint:
                raise KeyError(f"Checkpoint '{checkpoint_id}' not found.")

            passed, issues = self._evaluate_internal(checkpoint)
            if not passed and not force:
                logger.warning(
                    "Cannot complete checkpoint '%s'. Unmet criteria: %s",
                    checkpoint.name,
                    issues,
                )
                return False

            checkpoint.passed = True
            if checkpoint_id in self._barrier_events:
                self._barrier_events[checkpoint_id].set()

            self._history.append(checkpoint)
            return True

    # ------------------------------------------------------------------
    # Automated Multi-Agent Quality Gating Check
    # ------------------------------------------------------------------

    def run_automated_gate_checks(
        self,
        checkpoint_id: str,
        test_runner_func: Optional[Callable[[], bool]] = None,
        security_scanner_func: Optional[Callable[[], bool]] = None,
        doc_validator_func: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, bool]:
        """
        Execute automated callable quality checks and populate validation status.
        """
        checkpoint = self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise KeyError(f"Checkpoint '{checkpoint_id}' not found.")

        results = {}

        if test_runner_func and "tests" in checkpoint.required_validations:
            try:
                t_pass = bool(test_runner_func())
                self.record_validation(
                    checkpoint_id,
                    validator_agent="TestingAgent",
                    validation_type="tests",
                    passed=t_pass,
                    details={"suite": "automated_tests"},
                )
                results["tests"] = t_pass
            except Exception as e:
                self.record_validation(
                    checkpoint_id,
                    validator_agent="TestingAgent",
                    validation_type="tests",
                    passed=False,
                    details={"error": str(e)},
                )
                results["tests"] = False

        if security_scanner_func and "security" in checkpoint.required_validations:
            try:
                s_pass = bool(security_scanner_func())
                self.record_validation(
                    checkpoint_id,
                    validator_agent="SecurityAgent",
                    validation_type="security",
                    passed=s_pass,
                    details={"scan": "ast_vulnerability_audit"},
                )
                results["security"] = s_pass
            except Exception as e:
                self.record_validation(
                    checkpoint_id,
                    validator_agent="SecurityAgent",
                    validation_type="security",
                    passed=False,
                    details={"error": str(e)},
                )
                results["security"] = False

        if doc_validator_func and "documentation" in checkpoint.required_validations:
            try:
                d_pass = bool(doc_validator_func())
                self.record_validation(
                    checkpoint_id,
                    validator_agent="DocumentationAgent",
                    validation_type="documentation",
                    passed=d_pass,
                    details={"doc_check": "api_and_readme_parity"},
                )
                results["documentation"] = d_pass
            except Exception as e:
                self.record_validation(
                    checkpoint_id,
                    validator_agent="DocumentationAgent",
                    validation_type="documentation",
                    passed=False,
                    details={"error": str(e)},
                )
                results["documentation"] = False

        return results

    # ------------------------------------------------------------------
    # Telemetry & Reporting
    # ------------------------------------------------------------------

    def get_checkpoint(self, checkpoint_id: str) -> Optional[SyncCheckpoint]:
        with self._lock:
            return self._checkpoints.get(checkpoint_id)

    def get_active_checkpoints(self) -> List[SyncCheckpoint]:
        with self._lock:
            return [cp for cp in self._checkpoints.values() if not cp.passed]

    def get_all_checkpoints(self) -> List[SyncCheckpoint]:
        with self._lock:
            return list(self._checkpoints.values())

    def generate_sync_report(self, checkpoint_id: str) -> Dict[str, Any]:
        """Produce a comprehensive synchronization audit status report."""
        with self._lock:
            checkpoint = self._checkpoints.get(checkpoint_id)
            if not checkpoint:
                return {"error": f"Checkpoint '{checkpoint_id}' not found"}

            passed, pending_or_failed = self._evaluate_internal(checkpoint)

            return {
                "checkpoint_id": checkpoint.checkpoint_id,
                "name": checkpoint.name,
                "type": checkpoint.checkpoint_type.value,
                "created_at": checkpoint.created_at,
                "passed": passed,
                "required_validations": checkpoint.required_validations,
                "validation_results": checkpoint.validation_results,
                "blockers": checkpoint.blockers,
                "unmet_criteria": pending_or_failed,
            }

    def clear(self) -> None:
        with self._lock:
            self._checkpoints.clear()
            self._barrier_events.clear()
            self._history.clear()
