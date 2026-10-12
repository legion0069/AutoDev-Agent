"""
AutoDev Repair Recovery & Journal (v2.6)
Provides durable transaction journaling, restart crash recovery,
and idempotent repair request reconciliation.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from core.repair_transaction import RepairState, RepairTransaction
from core.self_healing_engine import SelfHealingEngine

logger = logging.getLogger(__name__)


class RepairJournal:
    """Appends and persists repair transaction records to a durable JSON log file."""

    def __init__(self, journal_path: str):
        self.journal_path = os.path.abspath(journal_path)
        os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)

    def append_entry(self, transaction: RepairTransaction):
        """Appends a snapshot of transaction state to the journal file."""
        entry = {
            "repair_id": transaction.repair_id,
            "project_id": transaction.project_id,
            "state": transaction.state.value,
            "timestamp": time.time(),
            "transaction_data": transaction.to_dict(),
        }
        try:
            with open(self.journal_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed writing to repair journal: {e}")

    def load_all_transactions(self) -> Dict[str, Dict[str, Any]]:
        """Loads the most recent state for each transaction from the journal."""
        if not os.path.isfile(self.journal_path):
            return {}

        transactions: Dict[str, Dict[str, Any]] = {}
        try:
            with open(self.journal_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = json.loads(line)
                        rep_id = entry.get("repair_id")
                        if rep_id:
                            transactions[rep_id] = entry
        except Exception as e:
            logger.error(f"Failed reading repair journal: {e}")
        return transactions


class RepairRecoveryManager:
    """Manages restart recovery, incomplete transaction reconciliation, and idempotency."""

    def __init__(
        self,
        workspace_path: str,
        journal: RepairJournal,
        self_healing_engine: Optional[SelfHealingEngine] = None,
    ):
        self.workspace_path = os.path.realpath(os.path.abspath(workspace_path))
        self.journal = journal
        self.engine = self_healing_engine or SelfHealingEngine(self.workspace_path)
        self._active_transactions: Dict[str, RepairTransaction] = {}

    def reconcile_on_startup(self) -> List[str]:
        """
        Scans journal for unfinished repair transactions (e.g. APPLIED_IN_CANDIDATE, VERIFYING)
        and safely reconciles workspace state. Returns list of recovered transaction IDs.
        """
        records = self.journal.load_all_transactions()
        recovered_ids = []

        for rep_id, entry in records.items():
            state_str = entry.get("state")
            if not state_str:
                continue

            try:
                state = RepairState(state_str)
            except Exception:
                continue

            # Incomplete states that modified files without reaching final ACCEPTED / ROLLED_BACK
            if state in (
                RepairState.APPLIED_IN_CANDIDATE,
                RepairState.VERIFYING,
                RepairState.VERIFICATION_FAILED,
                RepairState.ROLLBACK_PENDING,
            ):
                logger.warning(f"Reconciling interrupted repair transaction {rep_id} in state {state.value}")
                tx_data = entry.get("transaction_data", {})
                tx = RepairTransaction(
                    repair_id=rep_id,
                    project_id=tx_data.get("project_id", "default_project"),
                    state=state,
                    file_snapshots=tx_data.get("file_snapshots", {}),
                )
                
                # Perform rollback to restore pre-repair baseline
                success = self.engine.rollback_transaction(tx)
                if not success:
                    tx.transition_to(RepairState.RECOVERY_REQUIRED, "Startup recovery rollback failed")
                self.journal.append_entry(tx)
                recovered_ids.append(rep_id)

        return recovered_ids
