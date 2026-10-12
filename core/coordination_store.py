"""
coordination_store.py - Durable State Persistence & Coordination Backend for AutoDev (v2.3)

Provides pluggable coordination state backends (Memory and SQLite) for persisting worker registrations,
task leases, idempotency tokens, and task attempt histories across coordinator restarts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("AutoDev.CoordinationStore")


class CoordinationStoreError(Exception):
    """Base exception for coordination storage errors."""
    pass


class CoordinationStore(ABC):
    """Abstract interface for distributed worker coordination persistence."""

    @abstractmethod
    def save_worker(self, worker_id: str, worker_data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_worker(self, worker_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_workers(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete_worker(self, worker_id: str) -> None:
        pass

    @abstractmethod
    def save_lease(self, operation_id: str, lease_data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_lease(self, operation_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_leases(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete_lease(self, operation_id: str) -> None:
        pass

    @abstractmethod
    def save_idempotency_record(self, key: str, value: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_idempotency_record(self, key: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_coordinator(self, coordinator_id: str, data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_coordinator(self, coordinator_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_coordinators(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_leadership(self, term: int, leader_id: str, fencing_generation: int, expires_at: float) -> None:
        pass

    @abstractmethod
    def get_leadership(self) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class MemoryCoordinationStore(CoordinationStore):
    """Thread-safe in-memory coordination store for fast execution and testing."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._workers: Dict[str, Dict[str, Any]] = {}
        self._leases: Dict[str, Dict[str, Any]] = {}
        self._idempotency: Dict[str, Dict[str, Any]] = {}
        self._coordinators: Dict[str, Dict[str, Any]] = {}
        self._leadership: Optional[Dict[str, Any]] = None

    def save_worker(self, worker_id: str, worker_data: Dict[str, Any]) -> None:
        with self._lock:
            self._workers[worker_id] = dict(worker_data)

    def get_worker(self, worker_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._workers.get(worker_id)
            return dict(data) if data is not None else None

    def list_workers(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(v) for v in self._workers.values()]

    def delete_worker(self, worker_id: str) -> None:
        with self._lock:
            self._workers.pop(worker_id, None)

    def save_lease(self, operation_id: str, lease_data: Dict[str, Any]) -> None:
        with self._lock:
            self._leases[operation_id] = dict(lease_data)

    def get_lease(self, operation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._leases.get(operation_id)
            return dict(data) if data is not None else None

    def list_leases(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(v) for v in self._leases.values()]

    def delete_lease(self, operation_id: str) -> None:
        with self._lock:
            self._leases.pop(operation_id, None)

    def save_idempotency_record(self, key: str, value: Dict[str, Any]) -> None:
        with self._lock:
            self._idempotency[key] = dict(value)

    def get_idempotency_record(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._idempotency.get(key)
            return dict(data) if data is not None else None

    def save_coordinator(self, coordinator_id: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self._coordinators[coordinator_id] = dict(data)

    def get_coordinator(self, coordinator_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._coordinators.get(coordinator_id)
            return dict(data) if data is not None else None

    def list_coordinators(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(v) for v in self._coordinators.values()]

    def save_leadership(self, term: int, leader_id: str, fencing_generation: int, expires_at: float) -> None:
        with self._lock:
            self._leadership = {
                "term": term,
                "leader_id": leader_id,
                "fencing_generation": fencing_generation,
                "expires_at": expires_at,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

    def get_leadership(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return dict(self._leadership) if self._leadership else None

    def close(self) -> None:
        with self._lock:
            self._workers.clear()
            self._leases.clear()
            self._idempotency.clear()
            self._coordinators.clear()
            self._leadership = None


class SqliteCoordinationStore(CoordinationStore):
    """
    Durable SQLite-backed coordination store persisting worker metadata,
    task leases, and idempotency tokens across coordinator restarts.
    """

    def __init__(self, db_path: Union[str, Path] = "memory/coordination.db") -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute("""
                    CREATE TABLE IF NOT EXISTS workers (
                        worker_id TEXT PRIMARY KEY,
                        data_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                self._conn.execute("""
                    CREATE TABLE IF NOT EXISTS leases (
                        operation_id TEXT PRIMARY KEY,
                        data_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                self._conn.execute("""
                    CREATE TABLE IF NOT EXISTS idempotency_records (
                        record_key TEXT PRIMARY KEY,
                        data_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
                self._conn.execute("""
                    CREATE TABLE IF NOT EXISTS coordinators (
                        coordinator_id TEXT PRIMARY KEY,
                        data_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                self._conn.execute("""
                    CREATE TABLE IF NOT EXISTS leadership_state (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        term INTEGER NOT NULL,
                        leader_id TEXT NOT NULL,
                        fencing_generation INTEGER NOT NULL,
                        expires_at REAL NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)

    def save_worker(self, worker_id: str, worker_data: Dict[str, Any]) -> None:
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            data_str = json.dumps(worker_data)
            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO workers (worker_id, data_json, updated_at) VALUES (?, ?, ?)",
                    (worker_id, data_str, now),
                )

    def get_worker(self, worker_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT data_json FROM workers WHERE worker_id = ?", (worker_id,))
            row = cur.fetchone()
            if row:
                return json.loads(row["data_json"])
            return None

    def list_workers(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT data_json FROM workers")
            return [json.loads(r["data_json"]) for r in cur.fetchall()]

    def delete_worker(self, worker_id: str) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute("DELETE FROM workers WHERE worker_id = ?", (worker_id,))

    def save_lease(self, operation_id: str, lease_data: Dict[str, Any]) -> None:
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            data_str = json.dumps(lease_data)
            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO leases (operation_id, data_json, updated_at) VALUES (?, ?, ?)",
                    (operation_id, data_str, now),
                )

    def get_lease(self, operation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT data_json FROM leases WHERE operation_id = ?", (operation_id,))
            row = cur.fetchone()
            if row:
                return json.loads(row["data_json"])
            return None

    def list_leases(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT data_json FROM leases")
            return [json.loads(r["data_json"]) for r in cur.fetchall()]

    def delete_lease(self, operation_id: str) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute("DELETE FROM leases WHERE operation_id = ?", (operation_id,))

    def save_idempotency_record(self, key: str, value: Dict[str, Any]) -> None:
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            data_str = json.dumps(value)
            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO idempotency_records (record_key, data_json, created_at) VALUES (?, ?, ?)",
                    (key, data_str, now),
                )

    def get_idempotency_record(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT data_json FROM idempotency_records WHERE record_key = ?", (key,))
            row = cur.fetchone()
            if row:
                return json.loads(row["data_json"])
            return None

    def save_coordinator(self, coordinator_id: str, data: Dict[str, Any]) -> None:
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            data_str = json.dumps(data)
            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO coordinators (coordinator_id, data_json, updated_at) VALUES (?, ?, ?)",
                    (coordinator_id, data_str, now),
                )

    def get_coordinator(self, coordinator_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT data_json FROM coordinators WHERE coordinator_id = ?", (coordinator_id,))
            row = cur.fetchone()
            if row:
                return json.loads(row["data_json"])
            return None

    def list_coordinators(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT data_json FROM coordinators")
            return [json.loads(r["data_json"]) for r in cur.fetchall()]

    def save_leadership(self, term: int, leader_id: str, fencing_generation: int, expires_at: float) -> None:
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO leadership_state (id, term, leader_id, fencing_generation, expires_at, updated_at) VALUES (1, ?, ?, ?, ?, ?)",
                    (term, leader_id, fencing_generation, expires_at, now),
                )

    def get_leadership(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT term, leader_id, fencing_generation, expires_at, updated_at FROM leadership_state WHERE id = 1")
            row = cur.fetchone()
            if row:
                return {
                    "term": row["term"],
                    "leader_id": row["leader_id"],
                    "fencing_generation": row["fencing_generation"],
                    "expires_at": row["expires_at"],
                    "updated_at": row["updated_at"],
                }
            return None

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass
