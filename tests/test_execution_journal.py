"""
test_execution_journal.py - Comprehensive Tests for Durable Event Journaling & Crash Recovery (v2.1)
"""

import json
import pytest
from pathlib import Path

from core.execution_journal import (
    ExecutionJournal,
    JournalError,
    JournalEvent,
    JournalIntegrityError,
    redact_secrets,
)
from core.execution_transaction import ExecutionStatus, ExecutionTransaction


# =============================================================================
# 1. SECRET REDACTION TESTS
# =============================================================================

def test_redact_secrets_dictionary():
    """Verifies that sensitive keys and token formats are redacted."""
    raw_payload = {
        "api_key": "sk-1234567890abcdef1234567890",
        "user_password": "super_secret_password",
        "auth_token": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "safe_field": "database_table_users",
        "nested": {
            "secret_key": "AIzaSyD9876543210abcdefghijklmnopq",
            "normal": 42,
        },
    }
    redacted = redact_secrets(raw_payload)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["user_password"] == "[REDACTED]"
    assert redacted["auth_token"] == "[REDACTED]"
    assert redacted["safe_field"] == "database_table_users"
    assert redacted["nested"]["secret_key"] == "[REDACTED]"
    assert redacted["nested"]["normal"] == 42


def test_redact_secrets_string_patterns():
    """Verifies regex pattern scrubbing on string data containing keys."""
    raw_str = "Authorization: Bearer sk-1234567890123456789012345 in header."
    clean = redact_secrets(raw_str)
    assert "sk-1234567890123456789012345" not in clean
    assert "[REDACTED]" in clean


# =============================================================================
# 2. EVENT HASH CHAINING TESTS
# =============================================================================

def test_journal_event_hash_chain():
    """Verifies that JournalEvent computes deterministic SHA256 checksums."""
    evt1 = JournalEvent(
        event_id="EVT-001",
        transaction_id="tx-01",
        seq_num=1,
        event_type="TRANSACTION_CREATED",
        payload={"task_id": "T1"},
        prev_hash="GENESIS",
    )
    evt1.seal()
    assert evt1.event_hash is not None
    assert len(evt1.event_hash) == 64

    evt2 = JournalEvent(
        event_id="EVT-002",
        transaction_id="tx-01",
        seq_num=2,
        event_type="STAGE_STARTED",
        payload={"stage": 1},
        prev_hash=evt1.event_hash,
    )
    evt2.seal()
    assert evt2.event_hash is not None
    assert evt2.prev_hash == evt1.event_hash


# =============================================================================
# 3. JOURNAL APPEND & PERSISTENCE TESTS
# =============================================================================

def test_execution_journal_append_and_load(tmp_path):
    """Verifies appending events to disk and loading them with integrity verification."""
    journal = ExecutionJournal(transaction_id="tx-append-01", journal_root=tmp_path)

    evt1 = journal.append_event("TRANSACTION_CREATED", {"task": "TASK-1"})
    evt2 = journal.append_event("LOCK_ACQUIRED", {"pid": 1234})
    evt3 = journal.append_event("STAGE_COMPLETED", {"stage_number": 1})

    assert journal.event_count == 3
    assert evt1.seq_num == 1
    assert evt2.seq_num == 2
    assert evt3.seq_num == 3

    # Load from disk with hash-chain verification
    loaded_journal = ExecutionJournal(transaction_id="tx-append-01", journal_root=tmp_path)
    loaded_events = loaded_journal.load_events(verify_integrity=True)

    assert len(loaded_events) == 3
    assert loaded_events[0].event_type == "TRANSACTION_CREATED"
    assert loaded_events[1].event_type == "LOCK_ACQUIRED"
    assert loaded_events[2].event_type == "STAGE_COMPLETED"
    assert loaded_events[1].prev_hash == loaded_events[0].event_hash
    assert loaded_events[2].prev_hash == loaded_events[1].event_hash


def test_execution_journal_integrity_detection_tampering(tmp_path):
    """Verifies that JournalIntegrityError is raised if an event line is modified or corrupted."""
    journal = ExecutionJournal(transaction_id="tx-tamper-01", journal_root=tmp_path)
    journal.append_event("EVENT_1", {"data": 100})
    journal.append_event("EVENT_2", {"data": 200})

    # Tamper with the events file on disk
    events_file = tmp_path / "tx-tamper-01" / "events.jsonl"
    lines = events_file.read_text(encoding="utf-8").splitlines()
    # Modify payload of line 1 without updating hash
    tampered_data = json.loads(lines[0])
    tampered_data["payload"]["data"] = 999
    lines[0] = json.dumps(tampered_data)
    events_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Loading must detect hash mismatch
    verifier = ExecutionJournal(transaction_id="tx-tamper-01", journal_root=tmp_path)
    with pytest.raises(JournalIntegrityError) as exc_info:
        verifier.load_events(verify_integrity=True)
    assert "hash mismatch" in str(exc_info.value).lower() or "hash chain broken" in str(exc_info.value).lower()


def test_execution_journal_integrity_detection_sequence_gap(tmp_path):
    """Verifies that JournalIntegrityError is raised if an event is dropped."""
    journal = ExecutionJournal(transaction_id="tx-gap-01", journal_root=tmp_path)
    journal.append_event("EVENT_1", {})
    journal.append_event("EVENT_2", {})
    journal.append_event("EVENT_3", {})

    # Delete middle line
    events_file = tmp_path / "tx-gap-01" / "events.jsonl"
    lines = events_file.read_text(encoding="utf-8").splitlines()
    del lines[1]
    events_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    verifier = ExecutionJournal(transaction_id="tx-gap-01", journal_root=tmp_path)
    with pytest.raises(JournalIntegrityError):
        verifier.load_events(verify_integrity=True)


# =============================================================================
# 4. TRANSACTION SNAPSHOT PERSISTENCE & DISCOVERY
# =============================================================================

def test_persist_and_load_transaction_snapshot(tmp_path):
    """Verifies atomic snapshot saving and loading of ExecutionTransaction."""
    journal = ExecutionJournal(transaction_id="tx-snap-01", journal_root=tmp_path)

    tx = ExecutionTransaction(
        transaction_id="tx-snap-01",
        plan_id="plan-99",
        task_id="task-99",
        workspace_root=tmp_path,
        initial_git_head="head-sha",
    )
    tx.record_change("core/app.py", "CREATE")
    tx.transition_to(ExecutionStatus.VALIDATING)
    tx.transition_to(ExecutionStatus.READY)
    tx.transition_to(ExecutionStatus.RUNNING)

    journal.persist_transaction_snapshot(tx)

    # Load back
    loaded_tx = journal.load_transaction_snapshot()
    assert loaded_tx is not None
    assert loaded_tx.transaction_id == "tx-snap-01"
    assert loaded_tx.status == ExecutionStatus.RUNNING
    assert "core/app.py" in loaded_tx.created_files


def test_discover_interrupted_transactions(tmp_path):
    """Verifies scanning for unfinished transactions across the journal root."""
    # 1. Active RUNNING transaction
    j1 = ExecutionJournal("tx-active-01", journal_root=tmp_path)
    t1 = ExecutionTransaction("tx-active-01", "p1", "t1", tmp_path)
    t1.transition_to(ExecutionStatus.VALIDATING)
    t1.transition_to(ExecutionStatus.READY)
    t1.transition_to(ExecutionStatus.RUNNING)
    j1.persist_transaction_snapshot(t1)

    # 2. Completed SUCCEEDED transaction
    j2 = ExecutionJournal("tx-done-02", journal_root=tmp_path)
    t2 = ExecutionTransaction("tx-done-02", "p2", "t2", tmp_path)
    t2.transition_to(ExecutionStatus.VALIDATING)
    t2.transition_to(ExecutionStatus.READY)
    t2.transition_to(ExecutionStatus.RUNNING)
    t2.transition_to(ExecutionStatus.SUCCEEDED)
    j2.persist_transaction_snapshot(t2)

    # 3. Interrupted ROLLING_BACK transaction
    j3 = ExecutionJournal("tx-recovering-03", journal_root=tmp_path)
    t3 = ExecutionTransaction("tx-recovering-03", "p3", "t3", tmp_path)
    t3.transition_to(ExecutionStatus.VALIDATING)
    t3.transition_to(ExecutionStatus.READY)
    t3.transition_to(ExecutionStatus.RUNNING)
    t3.transition_to(ExecutionStatus.ROLLING_BACK)
    j3.persist_transaction_snapshot(t3)

    interrupted = ExecutionJournal.discover_interrupted_transactions(journal_root=tmp_path)
    interrupted_ids = {item[0] for item in interrupted}

    assert "tx-active-01" in interrupted_ids
    assert "tx-recovering-03" in interrupted_ids
    assert "tx-done-02" not in interrupted_ids
