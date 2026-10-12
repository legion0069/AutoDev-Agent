"""
execution_journal.py - Durable Event Journal & Crash Recovery for AutoDev (v2.1)

Provides an append-only, hash-chained durable audit trail for execution transactions,
supporting crash detection, journal integrity verification, and secret redaction.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Ensure project root is available on sys.path
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.execution_transaction import (
    ExecutionEngineError,
    ExecutionStatus,
    ExecutionTransaction,
)

logger = logging.getLogger("AutoDev.ExecutionJournal")


# =============================================================================
# EXCEPTION HIERARCHY
# =============================================================================

class JournalError(ExecutionEngineError):
    """Base exception for journal operations."""
    pass


class JournalIntegrityError(JournalError):
    """Raised when a journal's hash-chain or sequence integrity is violated."""
    pass


# =============================================================================
# SECRET REDACTION UTILITY
# =============================================================================

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|auth|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"),
    re.compile(r"(?i)sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"(?i)AIza[0-9A-Za-z\-_]{35}"),
]


def redact_secrets(data: Any) -> Any:
    """
    Recursively redacts sensitive API keys, tokens, and passwords from payloads.
    """
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if any(term in k.lower() for term in ["key", "secret", "token", "password", "auth"]):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_secrets(v)
        return redacted
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    elif isinstance(data, str):
        result = data
        result = SECRET_PATTERNS[0].sub(r"\1: [REDACTED]", result)
        for pat in SECRET_PATTERNS[1:]:
            result = pat.sub("[REDACTED]", result)
        return result
    return data


# =============================================================================
# JOURNAL EVENT DATA MODEL
# =============================================================================

@dataclass
class JournalEvent:
    """
    Individual append-only audit event in an execution transaction journal.
    """
    event_id: str
    transaction_id: str
    seq_num: int
    event_type: str
    payload: Dict[str, Any]
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    prev_hash: str = "GENESIS"
    event_hash: Optional[str] = None

    def compute_hash(self) -> str:
        """
        Computes the SHA256 checksum over the event fields for tamper-detection.
        """
        payload_str = json.dumps(self.payload, sort_keys=True, default=str)
        raw = (
            f"{self.seq_num}:{self.timestamp}:{self.transaction_id}:"
            f"{self.event_type}:{payload_str}:{self.prev_hash}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def seal(self) -> None:
        """Seals the event with its computed SHA256 hash."""
        self.event_hash = self.compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        """Serializes event to dictionary."""
        return {
            "event_id": self.event_id,
            "transaction_id": self.transaction_id,
            "seq_num": self.seq_num,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "event_hash": self.event_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JournalEvent:
        """Deserializes event from dictionary representation."""
        evt = cls(
            event_id=str(data.get("event_id", "")),
            transaction_id=str(data.get("transaction_id", "")),
            seq_num=int(data.get("seq_num", 1)),
            event_type=str(data.get("event_type", "UNKNOWN")),
            payload=dict(data.get("payload", {})),
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
            prev_hash=str(data.get("prev_hash", "GENESIS")),
            event_hash=data.get("event_hash"),
        )
        return evt


# =============================================================================
# EXECUTION JOURNAL CLASS
# =============================================================================

class ExecutionJournal:
    """
    Manages the durable on-disk append-only event log and transaction state
    under memory/execution_journal/<transaction_id>/.
    """

    def __init__(
        self,
        transaction_id: str = "default_tx",
        journal_root: Union[str, Path] = "memory/execution_journal",
        journal_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self.transaction_id = transaction_id
        root_path = journal_dir if journal_dir is not None else journal_root
        self.journal_root = Path(root_path).resolve()
        self.tx_dir = self.journal_root / transaction_id
        self.events_file = self.tx_dir / "events.jsonl"
        self.state_file = self.tx_dir / "transaction.json"

        self._seq_num = 0
        self._last_hash = "GENESIS"
        self._events: List[JournalEvent] = []

        # Ensure journal directory exists
        self.tx_dir.mkdir(parents=True, exist_ok=True)

    @property
    def event_count(self) -> int:
        return len(self._events)

    def append_event(
        self,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        operation_id: Optional[str] = None,
        stage_number: Optional[int] = None,
    ) -> JournalEvent:
        """
        Appends a new structured event to the journal, computes its hash-chain checksum,
        and atomically flushes it to disk.
        """
        self._seq_num += 1
        safe_payload = redact_secrets(payload or {})
        if operation_id:
            safe_payload["operation_id"] = operation_id
        if stage_number is not None:
            safe_payload["stage_number"] = stage_number

        event = JournalEvent(
            event_id=f"EVT-{self.transaction_id[:8]}-{self._seq_num:05d}",
            transaction_id=self.transaction_id,
            seq_num=self._seq_num,
            event_type=event_type,
            payload=safe_payload,
            prev_hash=self._last_hash,
        )
        event.seal()
        self._last_hash = event.event_hash  # type: ignore

        self._events.append(event)
        self._flush_event_to_disk(event)
        return event

    def _flush_event_to_disk(self, event: JournalEvent) -> None:
        """Appends an individual event line to events.jsonl with sync flush."""
        try:
            line = json.dumps(event.to_dict(), default=str) + "\n"
            with open(self.events_file, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        except OSError as exc:
            logger.error(
                "Failed to flush journal event %s to %s: %s",
                event.event_id,
                self.events_file,
                exc,
            )
            raise JournalError(f"Could not persist journal event: {exc}") from exc

    def persist_transaction_snapshot(
        self, transaction: ExecutionTransaction
    ) -> None:
        """
        Atomically writes full transaction state snapshot to transaction.json.
        """
        try:
            raw_dict = transaction.to_dict()
            safe_dict = redact_secrets(raw_dict)
            content = json.dumps(safe_dict, indent=2, default=str)

            # Atomic file replacement via temp file
            temp_file = self.tx_dir / f"transaction.tmp.{os.getpid()}"
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            temp_file.replace(self.state_file)
        except OSError as exc:
            logger.error("Failed to atomically persist transaction snapshot: %s", exc)
            raise JournalError(f"Failed to persist transaction snapshot: {exc}") from exc

    def load_events(self, verify_integrity: bool = True) -> List[JournalEvent]:
        """
        Reads all events from events.jsonl and optionally validates the hash-chain.
        """
        if not self.events_file.exists():
            return []

        loaded_events: List[JournalEvent] = []
        expected_prev_hash = "GENESIS"
        expected_seq = 1

        try:
            with open(self.events_file, "r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f, start=1):
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        data = json.loads(line_str)
                    except json.JSONDecodeError as jde:
                        raise JournalIntegrityError(
                            f"Corrupted journal JSON at line {line_idx} in '{self.events_file}': {jde}"
                        ) from jde

                    evt = JournalEvent.from_dict(data)

                    if verify_integrity:
                        if evt.seq_num != expected_seq:
                            raise JournalIntegrityError(
                                f"Journal sequence gap at line {line_idx}: expected seq {expected_seq}, got {evt.seq_num}"
                            )
                        if evt.prev_hash != expected_prev_hash:
                            raise JournalIntegrityError(
                                f"Journal hash chain broken at line {line_idx}: expected prev_hash '{expected_prev_hash}', got '{evt.prev_hash}'"
                            )
                        computed = evt.compute_hash()
                        if evt.event_hash != computed:
                            raise JournalIntegrityError(
                                f"Journal event hash mismatch at line {line_idx}: recorded '{evt.event_hash}', computed '{computed}'"
                            )

                    expected_prev_hash = evt.event_hash or ""
                    expected_seq += 1
                    loaded_events.append(evt)

            self._events = loaded_events
            if loaded_events:
                self._seq_num = loaded_events[-1].seq_num
                self._last_hash = loaded_events[-1].event_hash or "GENESIS"

            return loaded_events
        except OSError as exc:
            raise JournalError(f"Failed to read events from '{self.events_file}': {exc}") from exc

    def load_transaction_snapshot(self) -> Optional[ExecutionTransaction]:
        """
        Loads the latest transaction snapshot from transaction.json.
        """
        if not self.state_file.exists():
            return None
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ExecutionTransaction.from_dict(data)
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load transaction snapshot from %s: %s", self.state_file, exc)
            return None

    @classmethod
    def discover_interrupted_transactions(
        cls, journal_root: Union[str, Path] = "memory/execution_journal"
    ) -> List[Tuple[str, ExecutionStatus, Path]]:
        """
        Scans journal directory for transactions that were RUNNING, PAUSED, or ROLLING_BACK
        when the previous process terminated unexpectedly.
        """
        root = Path(journal_root).resolve()
        if not root.exists():
            return []

        interrupted: List[Tuple[str, ExecutionStatus, Path]] = []
        for child in root.iterdir():
            if not child.is_dir():
                continue
            tx_file = child / "transaction.json"
            if not tx_file.exists():
                continue
            try:
                with open(tx_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tx_id = data.get("transaction_id", child.name)
                raw_status = data.get("status", "PENDING")
                try:
                    status = ExecutionStatus(raw_status)
                except ValueError:
                    status = ExecutionStatus.PENDING

                if status in {
                    ExecutionStatus.RUNNING,
                    ExecutionStatus.PAUSED,
                    ExecutionStatus.ROLLING_BACK,
                    ExecutionStatus.RECOVERY_REQUIRED,
                }:
                    interrupted.append((tx_id, status, child))
            except Exception as exc:
                logger.warning("Error reading transaction file '%s': %s", tx_file, exc)

        return interrupted
