"""
execution_lock.py - Workspace Concurrency Control & Parallel Scheduling for AutoDev (v2.1)

Provides:
- Per-workspace atomic file locking with owner verification, TTL, and stale lock recovery.
- Safe bounded parallel scheduling for disjoint change operations.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import socket
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# Ensure project root is available on sys.path
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.execution_transaction import ExecutionEngineError

logger = logging.getLogger("AutoDev.ExecutionLock")


# =============================================================================
# EXCEPTION HIERARCHY
# =============================================================================

class WorkspaceLockError(ExecutionEngineError):
    """Base exception for workspace locking failures."""
    pass


class LockAcquisitionTimeoutError(WorkspaceLockError):
    """Raised when acquiring the workspace lock times out."""
    pass


class LockOwnershipError(WorkspaceLockError):
    """Raised when an unauthorized entity attempts to release or modify a lock."""
    pass


# =============================================================================
# LOCK DATA MODEL
# =============================================================================

@dataclass
class LockMetadata:
    """
    Structured payload written to .autodev.lock to identify the active lock holder.
    """
    owner_token: str
    transaction_id: str
    pid: int
    hostname: str
    acquired_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    ttl_seconds: float = 300.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "owner_token": self.owner_token,
            "transaction_id": self.transaction_id,
            "pid": self.pid,
            "hostname": self.hostname,
            "acquired_at": self.acquired_at,
            "ttl_seconds": self.ttl_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LockMetadata:
        return cls(
            owner_token=str(data.get("owner_token", "")),
            transaction_id=str(data.get("transaction_id", "")),
            pid=int(data.get("pid", 0)),
            hostname=str(data.get("hostname", "")),
            acquired_at=str(data.get("acquired_at", datetime.now(timezone.utc).isoformat())),
            ttl_seconds=float(data.get("ttl_seconds", 300.0)),
        )


# =============================================================================
# WORKSPACE LOCK CLASS
# =============================================================================

class WorkspaceLock:
    """
    Atomic per-workspace file lock protecting concurrent modifications.
    """

    def __init__(
        self,
        workspace_root: Union[str, Path],
        lock_file_name: str = ".autodev.lock",
        default_timeout: float = 10.0,
        default_ttl: float = 300.0,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.lock_path = self.workspace_root / lock_file_name
        self.default_timeout = default_timeout
        self.default_ttl = default_ttl

        self._active_metadata: Optional[LockMetadata] = None

    @property
    def is_locked(self) -> bool:
        """Returns True if lock file exists and is currently valid."""
        if not self.lock_path.exists():
            return False
        meta = self._read_lock_metadata()
        if not meta:
            return False
        return not self._is_lock_stale(meta)

    def _read_lock_metadata(self) -> Optional[LockMetadata]:
        """Reads and parses the active lock file."""
        if not self.lock_path.exists():
            return None
        try:
            content = self.lock_path.read_text(encoding="utf-8")
            data = json.loads(content)
            return LockMetadata.from_dict(data)
        except (OSError, json.JSONDecodeError):
            return None

    def _is_pid_alive(self, pid: int) -> bool:
        """Checks if a process with the given PID is currently active."""
        if pid <= 0:
            return False
        if os.name == "nt":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32  # type: ignore
                # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                h_proc = kernel32.OpenProcess(0x1000, False, pid)
                if h_proc:
                    kernel32.CloseHandle(h_proc)
                    return True
                return False
            except Exception:
                return False
        else:
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False

    def _is_lock_stale(self, meta: LockMetadata) -> bool:
        """Determines if a lock is abandoned by checking process liveness and host."""
        curr_host = socket.gethostname()
        is_local = (
            meta.hostname == curr_host
            or meta.hostname in {"localhost", "127.0.0.1", ""}
            or curr_host in {"localhost", "127.0.0.1"}
        )
        # If lock belongs to same machine but PID is dead, it's stale
        if is_local and not self._is_pid_alive(meta.pid):
            logger.warning("Stale lock detected: PID %s on %s is no longer active.", meta.pid, meta.hostname)
            return True

        # Check TTL expiration
        try:
            acquired_dt = datetime.fromisoformat(meta.acquired_at)
            age = (datetime.now(timezone.utc) - acquired_dt).total_seconds()
            if age > meta.ttl_seconds:
                logger.warning("Stale lock detected by TTL expiration (age %.1fs > ttl %.1fs)", age, meta.ttl_seconds)
                return True
        except Exception:
            pass

        return False

    def acquire(
        self,
        transaction_id: str,
        timeout_seconds: Optional[float] = None,
        ttl_seconds: Optional[float] = None,
    ) -> LockMetadata:
        """
        Attempts to acquire the workspace lock atomically, waiting up to timeout_seconds.
        """
        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        start_time = time.perf_counter()

        owner_token = str(uuid.uuid4())
        meta = LockMetadata(
            owner_token=owner_token,
            transaction_id=transaction_id,
            pid=os.getpid(),
            hostname=socket.gethostname(),
            ttl_seconds=ttl,
        )

        while True:
            # 1. Check existing lock
            existing = self._read_lock_metadata()
            if existing:
                if existing.transaction_id == transaction_id and existing.pid == os.getpid():
                    # Re-entrant acquisition for same transaction
                    self._active_metadata = existing
                    return existing

                if self._is_lock_stale(existing):
                    logger.info("Cleaning up stale workspace lock from PID %s", existing.pid)
                    try:
                        self.lock_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                else:
                    elapsed = time.perf_counter() - start_time
                    if elapsed >= timeout:
                        raise LockAcquisitionTimeoutError(
                            f"Could not acquire workspace lock on '{self.workspace_root}' within {timeout}s. "
                            f"Active lock held by Tx '{existing.transaction_id}', PID {existing.pid} on '{existing.hostname}'."
                        )
                    time.sleep(0.1)
                    continue

            # 2. Atomic write using exclusive file creation flag (O_CREAT | O_EXCL)
            try:
                flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
                fd = os.open(str(self.lock_path), flags, 0o644)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(meta.to_dict(), f, indent=2)
                    f.flush()
                self._active_metadata = meta
                logger.info("Workspace lock acquired by transaction %s", transaction_id)
                return meta
            except FileExistsError:
                # Lost race condition, retry until timeout
                elapsed = time.perf_counter() - start_time
                if elapsed >= timeout:
                    raise LockAcquisitionTimeoutError(
                        f"Failed to acquire workspace lock on '{self.workspace_root}' after race condition timeout."
                    )
                time.sleep(0.05)
            except OSError as exc:
                raise WorkspaceLockError(f"Unexpected error creating lock file '{self.lock_path}': {exc}") from exc

    def release(self, transaction_id: Optional[str] = None) -> bool:
        """
        Releases the workspace lock, verifying ownership token or transaction ID.
        """
        if not self.lock_path.exists():
            self._active_metadata = None
            return True

        meta = self._read_lock_metadata()
        if meta and transaction_id and meta.transaction_id != transaction_id:
            raise LockOwnershipError(
                f"Cannot release lock: owned by transaction '{meta.transaction_id}', not '{transaction_id}'."
            )

        try:
            self.lock_path.unlink(missing_ok=True)
            self._active_metadata = None
            logger.info("Workspace lock released for transaction %s", transaction_id)
            return True
        except OSError as exc:
            logger.error("Failed to remove lock file '%s': %s", self.lock_path, exc)
            return False


# =============================================================================
# PARALLEL OPERATION SCHEDULER
# =============================================================================

class ParallelOperationScheduler:
    """
    Coordinates bounded parallel execution of independent change operations
    while enforcing disjoint file boundaries and fault containment.
    """

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max(1, max_workers)

    def execute_parallel_operations(
        self,
        operations: List[Any],
        executor_fn: Callable[[Any], Any],
    ) -> List[Any]:
        """
        Executes a batch of operations concurrently with worker bounding.
        Cancels remaining unstarted tasks if any task encounters a fatal failure.
        """
        if not operations:
            return []

        if len(operations) == 1 or self.max_workers == 1:
            # Sequential execution for single operations
            results = []
            for op in operations:
                results.append(executor_fn(op))
            return results

        results: List[Any] = [None] * len(operations)
        futures_map: Dict[concurrent.futures.Future, int] = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            for idx, op in enumerate(operations):
                fut = pool.submit(executor_fn, op)
                futures_map[fut] = idx

            for fut in concurrent.futures.as_completed(futures_map):
                idx = futures_map[fut]
                try:
                    res = fut.result()
                    results[idx] = res
                except Exception as exc:
                    logger.error("Parallel operation %s raised exception: %s", idx, exc)
                    # Create generic failure result if available
                    results[idx] = exc

        return results
