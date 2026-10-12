"""
distributed_lock_manager.py - Cluster Distributed Lock Manager & Deadlock Detector for AutoDev (v2.9)

Provides cluster-wide atomic locking for files, tasks, memory regions, and artifacts.
Supports lease TTLs, non-blocking / blocking acquisition, renewal heartbeats, shared/exclusive locks,
and automated deadlock detection via Wait-For-Graph (WFG) cycle analysis.
"""

from __future__ import annotations

import contextlib
import copy
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import LockLease, LockType

logger = logging.getLogger("AutoDev.Cluster.LockManager")


class LockAcquisitionError(Exception):
    """Raised when lock acquisition fails or deadlocks."""
    pass


class DistributedLockManager:
    """
    Cluster distributed lock manager with lease expiration and deadlock cycle resolution.
    """

    def __init__(self, config: Optional[ClusterConfig] = None) -> None:
        self.config = config or ClusterConfig()
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)

        # Active leases: resource_id -> LockLease
        self._leases: Dict[str, LockLease] = {}
        # Shared holders: resource_id -> Set[owner_id]
        self._shared_holders: Dict[str, Set[str]] = {}
        # Wait-For-Graph: waiter_owner_id -> Set[blocking_owner_id]
        self._wait_for_graph: Dict[str, Set[str]] = {}
        # Resource waiters: resource_id -> List[owner_id]
        self._resource_waiters: Dict[str, List[str]] = {}

    def acquire(
        self,
        resource_id: str,
        owner_id: str,
        lock_type: LockType = LockType.EXCLUSIVE,
        ttl_seconds: Optional[float] = None,
        timeout: float = 0.0,
    ) -> bool:
        """
        Acquires an exclusive or shared lock lease on a cluster resource.
        If timeout > 0, blocks until acquired or timeout expires.
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.config.lease_ttl_seconds
        deadline = time.time() + timeout if timeout > 0 else 0.0

        with self._lock:
            # Sweep expired leases
            self.sweep_expired_leases()

            while True:
                # 1. Try immediate acquisition
                if self._try_acquire_internal(resource_id, owner_id, lock_type, ttl):
                    self._remove_waiter(resource_id, owner_id)
                    logger.debug("Lock acquired on %s by %s (type=%s, ttl=%.1fs)", resource_id, owner_id, lock_type.value, ttl)
                    return True

                if timeout <= 0.0:
                    return False

                # 2. Register in Wait-For Graph and check deadlocks
                self._add_waiter(resource_id, owner_id)
                if self.config.enable_deadlock_detection:
                    cycle = self.detect_deadlock_cycle()
                    if cycle:
                        self._remove_waiter(resource_id, owner_id)
                        logger.error("Deadlock detected in lock acquisition cycle: %s", " -> ".join(cycle))
                        raise LockAcquisitionError(f"Deadlock detected involving owners: {cycle}")

                # 3. Wait on condition
                remaining = deadline - time.time()
                if remaining <= 0.0:
                    self._remove_waiter(resource_id, owner_id)
                    logger.warning("Lock acquisition timed out for %s on %s", owner_id, resource_id)
                    return False

                self._cond.wait(timeout=min(remaining, 0.2))
                self.sweep_expired_leases()

    def _try_acquire_internal(
        self,
        resource_id: str,
        owner_id: str,
        lock_type: LockType,
        ttl: float,
    ) -> bool:
        now = time.time()
        existing = self._leases.get(resource_id)

        if existing is None:
            # Free resource
            lease = LockLease(
                resource_id=resource_id,
                lock_type=lock_type,
                owner_id=owner_id,
                acquired_at=now,
                expires_at=now + ttl,
                renewed_count=0,
            )
            self._leases[resource_id] = lease
            if lock_type == LockType.SHARED:
                self._shared_holders[resource_id] = {owner_id}
            return True

        if existing.is_expired(now):
            logger.info("Overwriting expired lease on %s (prev owner: %s)", resource_id, existing.owner_id)
            del self._leases[resource_id]
            self._shared_holders.pop(resource_id, None)
            return self._try_acquire_internal(resource_id, owner_id, lock_type, ttl)

        # Same owner re-acquiring or renewing
        if existing.owner_id == owner_id and existing.lock_type == lock_type:
            existing.expires_at = now + ttl
            existing.renewed_count += 1
            return True

        # Shared lock compatibility
        if lock_type == LockType.SHARED and existing.lock_type == LockType.SHARED:
            holders = self._shared_holders.setdefault(resource_id, set())
            holders.add(owner_id)
            existing.expires_at = max(existing.expires_at, now + ttl)
            return True

        return False

    def release(self, resource_id: str, owner_id: str) -> bool:
        """
        Releases lock lease held by owner_id on resource_id.
        """
        with self._lock:
            existing = self._leases.get(resource_id)
            if not existing:
                return False

            if existing.lock_type == LockType.SHARED:
                holders = self._shared_holders.get(resource_id, set())
                holders.discard(owner_id)
                if not holders:
                    self._shared_holders.pop(resource_id, None)
                    del self._leases[resource_id]
            else:
                if existing.owner_id != owner_id:
                    logger.warning("Unauthorized lock release attempt on %s by %s (owner is %s)", resource_id, owner_id, existing.owner_id)
                    return False
                del self._leases[resource_id]

            self._remove_waiter(resource_id, owner_id)
            self._cond.notify_all()
            logger.debug("Released lock on %s by %s", resource_id, owner_id)
            return True

    def renew(self, resource_id: str, owner_id: str, ttl_seconds: Optional[float] = None) -> bool:
        """
        Extends the lease duration for an active lock.
        """
        with self._lock:
            ttl = ttl_seconds if ttl_seconds is not None else self.config.lease_ttl_seconds
            existing = self._leases.get(resource_id)
            if not existing or existing.is_expired():
                return False

            if existing.lock_type == LockType.SHARED:
                if owner_id in self._shared_holders.get(resource_id, set()):
                    existing.expires_at = time.time() + ttl
                    existing.renewed_count += 1
                    return True
                return False

            if existing.owner_id == owner_id:
                existing.expires_at = time.time() + ttl
                existing.renewed_count += 1
                return True
            return False

    def sweep_expired_leases(self, current_time: Optional[float] = None) -> List[str]:
        """
        Reclaims all expired lock leases.
        """
        with self._lock:
            now = current_time if current_time is not None else time.time()
            expired: List[str] = []

            for r_id, lease in list(self._leases.items()):
                if lease.is_expired(now):
                    expired.append(r_id)
                    del self._leases[r_id]
                    self._shared_holders.pop(r_id, None)
                    logger.warning("Swept expired lock lease on %s (owner: %s)", r_id, lease.owner_id)

            if expired:
                self._cond.notify_all()
            return expired

    def _add_waiter(self, resource_id: str, owner_id: str) -> None:
        waiters = self._resource_waiters.setdefault(resource_id, [])
        if owner_id not in waiters:
            waiters.append(owner_id)

        existing = self._leases.get(resource_id)
        if existing:
            blocking_owners = {existing.owner_id}
            if existing.lock_type == LockType.SHARED:
                blocking_owners = set(self._shared_holders.get(resource_id, set()))
            self._wait_for_graph.setdefault(owner_id, set()).update(blocking_owners)

    def _remove_waiter(self, resource_id: str, owner_id: str) -> None:
        if resource_id in self._resource_waiters:
            self._resource_waiters[resource_id] = [w for w in self._resource_waiters[resource_id] if w != owner_id]
            if not self._resource_waiters[resource_id]:
                del self._resource_waiters[resource_id]
        self._wait_for_graph.pop(owner_id, None)

    def detect_deadlock_cycle(self) -> Optional[List[str]]:
        """
        Detects cycles in the Wait-For-Graph using depth-first search.
        Returns list of owner IDs in the cycle if detected, else None.
        """
        with self._lock:
            visited: Set[str] = set()
            rec_stack: Set[str] = set()
            path: List[str] = []

            def dfs(node: str) -> Optional[List[str]]:
                visited.add(node)
                rec_stack.add(node)
                path.append(node)

                for neighbor in self._wait_for_graph.get(node, set()):
                    if neighbor == node:
                        continue
                    if neighbor not in visited:
                        res = dfs(neighbor)
                        if res:
                            return res
                    elif neighbor in rec_stack:
                        # Cycle found
                        cycle_start_idx = path.index(neighbor)
                        return path[cycle_start_idx:] + [neighbor]

                rec_stack.remove(node)
                path.pop()
                return None

            for node in list(self._wait_for_graph.keys()):
                if node not in visited:
                    cycle = dfs(node)
                    if cycle:
                        return cycle
            return None

    @contextlib.contextmanager
    def lock_context(
        self,
        resource_id: str,
        owner_id: str,
        lock_type: LockType = LockType.EXCLUSIVE,
        ttl_seconds: Optional[float] = None,
        timeout: float = 5.0,
    ) -> Generator[bool, None, None]:
        """
        Convenience context manager for safe distributed lock acquisition & automatic release.
        """
        acquired = self.acquire(resource_id, owner_id, lock_type, ttl_seconds, timeout)
        if not acquired:
            raise LockAcquisitionError(f"Failed to acquire lock for {owner_id} on {resource_id} within timeout {timeout}s")
        try:
            yield acquired
        finally:
            self.release(resource_id, owner_id)

    def is_locked(self, resource_id: str) -> bool:
        with self._lock:
            self.sweep_expired_leases()
            return resource_id in self._leases

    def get_lease(self, resource_id: str) -> Optional[LockLease]:
        with self._lock:
            self.sweep_expired_leases()
            lease = self._leases.get(resource_id)
            return copy.deepcopy(lease) if lease else None

    def export_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "leases": {k: v.to_dict() for k, v in self._leases.items()},
                "shared_holders": {k: list(v) for k, v in self._shared_holders.items()},
            }

    def import_state(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self._leases.clear()
            self._shared_holders.clear()
            for k, v in data.get("leases", {}).items():
                lt = LockType(v["lock_type"]) if isinstance(v["lock_type"], str) else v["lock_type"]
                self._leases[k] = LockLease(
                    resource_id=v["resource_id"],
                    lock_type=lt,
                    owner_id=v["owner_id"],
                    acquired_at=v["acquired_at"],
                    expires_at=v["expires_at"],
                    renewed_count=v.get("renewed_count", 0),
                    waiters=v.get("waiters", []),
                )
            for k, v in data.get("shared_holders", {}).items():
                self._shared_holders[k] = set(v)
