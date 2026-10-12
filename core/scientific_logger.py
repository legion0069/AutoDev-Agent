"""
core/scientific_logger.py - Cryptographically Verifiable Scientific Audit Trail (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import enum
import hashlib
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class ScientificEventType(str, enum.Enum):
    """Categorization of scientific events recorded in the immutable audit trail."""
    HYPOTHESIS_FORMULATED = "HYPOTHESIS_FORMULATED"
    EXPERIMENT_START = "EXPERIMENT_START"
    EXPERIMENT_COMPLETE = "EXPERIMENT_COMPLETE"
    BENCHMARK_RECORD = "BENCHMARK_RECORD"
    OPTIMIZATION_STEP = "OPTIMIZATION_STEP"
    ALGORITHM_REGISTERED = "ALGORITHM_REGISTERED"
    PEER_REVIEW = "PEER_REVIEW"
    PAPER_PUBLISHED = "PAPER_PUBLISHED"
    PATENT_FILED = "PATENT_FILED"
    REPRODUCIBILITY_VERIFIED = "REPRODUCIBILITY_VERIFIED"


@dataclass
class ScientificLogRecord:
    """An individual cryptographically sealed entry in the scientific journal."""
    record_id: str
    timestamp: float
    event_type: ScientificEventType
    actor: str
    entity_id: str
    payload: Dict[str, Any]
    previous_hash: str
    record_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "actor": self.actor,
            "entity_id": self.entity_id,
            "payload": self.payload,
            "previous_hash": self.previous_hash,
            "record_hash": self.record_hash,
        }


class ScientificLogger:
    """
    Maintains a tamper-evident, SHA-256 chained scientific audit journal documenting
    all hypotheses, experiments, benchmarks, reviews, papers, and patents.
    """

    GENESIS_HASH = "GENESIS_SCIENTIFIC_CHAIN_ROOT_V36"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._chain: List[ScientificLogRecord] = []
        self._latest_hash: str = self.GENESIS_HASH

    @staticmethod
    def _compute_hash(
        record_id: str,
        timestamp: float,
        event_type: str,
        actor: str,
        entity_id: str,
        previous_hash: str,
        payload: Dict[str, Any],
    ) -> str:
        payload_serialized = json.dumps(payload, sort_keys=True, default=str)
        raw = f"{record_id}|{timestamp:.6f}|{event_type}|{actor}|{entity_id}|{previous_hash}|{payload_serialized}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def log_event(
        self,
        event_type: ScientificEventType,
        actor: str,
        entity_id: str,
        payload: Dict[str, Any],
    ) -> ScientificLogRecord:
        """Appends a new scientific event to the chain, linking it to the previous hash."""
        with self._lock:
            rec_id = f"SLOG-{uuid.uuid4().hex[:8].upper()}"
            ts = time.time()
            prev = self._latest_hash

            rec_hash = self._compute_hash(
                record_id=rec_id,
                timestamp=ts,
                event_type=event_type.value,
                actor=actor,
                entity_id=entity_id,
                previous_hash=prev,
                payload=payload,
            )

            record = ScientificLogRecord(
                record_id=rec_id,
                timestamp=ts,
                event_type=event_type,
                actor=actor,
                entity_id=entity_id,
                payload=payload,
                previous_hash=prev,
                record_hash=rec_hash,
            )

            self._chain.append(record)
            self._latest_hash = rec_hash
            return record

    def verify_chain_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Validates the entire audit chain from genesis to head.
        Returns (True, None) if completely valid, or (False, reason) if corrupted.
        """
        with self._lock:
            expected_prev = self.GENESIS_HASH
            for idx, rec in enumerate(self._chain):
                if rec.previous_hash != expected_prev:
                    return False, f"Broken chain link at index {idx} ({rec.record_id}): expected {expected_prev}, got {rec.previous_hash}"

                recomputed = self._compute_hash(
                    record_id=rec.record_id,
                    timestamp=rec.timestamp,
                    event_type=rec.event_type.value,
                    actor=rec.actor,
                    entity_id=rec.entity_id,
                    previous_hash=rec.previous_hash,
                    payload=rec.payload,
                )

                if recomputed != rec.record_hash:
                    return False, f"Hash mismatch at index {idx} ({rec.record_id}): computed {recomputed}, recorded {rec.record_hash}"

                expected_prev = rec.record_hash

            return True, None

    def get_records(
        self,
        event_type: Optional[ScientificEventType] = None,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ScientificLogRecord]:
        """Retrieves scientific records filtered by event type or entity ID."""
        with self._lock:
            recs = list(self._chain)
            if event_type:
                recs = [r for r in recs if r.event_type == event_type]
            if entity_id:
                recs = [r for r in recs if r.entity_id == entity_id]
            return recs[-limit:]

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._chain)
