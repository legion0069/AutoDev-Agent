"""
AutoDev Resource Scheduler Subsystem.

Provides distributed file/resource locking with read/write locks, lease expirations,
canonical resource sorting for deadlock prevention, and multi-resource reservations.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class LockType(str, Enum):
    """Resource access lock mode."""
    READ = "read"
    WRITE = "write"


@dataclass
class ResourceLock:
    """Represents a lock held on a specific resource."""
    resource_id: str
    holder_id: str
    lock_type: LockType
    acquired_at: float = field(default_factory=time.time)
    lease_expiration: Optional[float] = None

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        """Checks if the lock lease has expired."""
        now = current_time if current_time is not None else time.time()
        return self.lease_expiration is not None and self.lease_expiration < now


@dataclass
class ResourceReservation:
    """Group reservation of multiple resources for transactional safety."""
    reservation_id: str
    agent_id: str
    resource_ids: List[str]
    lock_type: LockType
    acquired_at: float = field(default_factory=time.time)
    lease_expiration: Optional[float] = None
    released: bool = False


class ResourceScheduler:
    """
    Thread-safe resource locking and reservation manager.
    Prevents race conditions, conflicting edits, and deadlocks across concurrent agents.
    """

    def __init__(self, default_lease_duration: float = 30.0) -> None:
        self.default_lease_duration = default_lease_duration
        self._mutex = threading.RLock()
        self._cond = threading.Condition(self._mutex)

        # resource_id -> list of ResourceLock (can have multiple READ locks, or single WRITE lock)
        self._locks: Dict[str, List[ResourceLock]] = {}
        # reservation_id -> ResourceReservation
        self._reservations: Dict[str, ResourceReservation] = {}

    def _cleanup_expired_locked(self, current_time: float) -> None:
        """Internal helper to clean expired locks without re-acquiring lock."""
        for resource_id in list(self._locks.keys()):
            valid_locks = [
                lk for lk in self._locks[resource_id]
                if not lk.is_expired(current_time)
            ]
            if valid_locks:
                self._locks[resource_id] = valid_locks
            else:
                self._locks.pop(resource_id, None)

    def acquire_lock(
        self,
        resource_id: str,
        agent_id: str,
        lock_type: LockType = LockType.WRITE,
        lease_duration: Optional[float] = None,
        timeout: float = 5.0,
    ) -> bool:
        """
        Attempts to acquire a read or write lock on a resource.
        Blocks up to timeout seconds waiting for conflicting locks to clear.
        """
        lease_sec = lease_duration if lease_duration is not None else self.default_lease_duration
        deadline = time.time() + timeout

        with self._cond:
            while True:
                now = time.time()
                self._cleanup_expired_locked(now)

                current_locks = self._locks.get(resource_id, [])

                can_acquire = False
                if not current_locks:
                    can_acquire = True
                elif lock_type == LockType.READ:
                    # Can acquire read lock if all existing locks are READ
                    can_acquire = all(lk.lock_type == LockType.READ for lk in current_locks)
                elif lock_type == LockType.WRITE:
                    # Can acquire write lock only if agent already holds sole lock or no locks exist
                    if len(current_locks) == 1 and current_locks[0].holder_id == agent_id:
                        # Re-entrant upgrade/renewal
                        current_locks[0].lock_type = LockType.WRITE
                        current_locks[0].lease_expiration = now + lease_sec
                        return True
                    can_acquire = False

                if can_acquire:
                    # For read lock, if same agent already holds read lock, simply extend lease
                    existing = next(
                        (lk for lk in current_locks if lk.holder_id == agent_id), None
                    )
                    if existing:
                        existing.lease_expiration = now + lease_sec
                    else:
                        new_lock = ResourceLock(
                            resource_id=resource_id,
                            holder_id=agent_id,
                            lock_type=lock_type,
                            acquired_at=now,
                            lease_expiration=now + lease_sec,
                        )
                        if resource_id not in self._locks:
                            self._locks[resource_id] = []
                        self._locks[resource_id].append(new_lock)
                    return True

                remaining = deadline - time.time()
                if remaining <= 0:
                    return False
                self._cond.wait(remaining)

    def release_lock(self, resource_id: str, agent_id: str) -> bool:
        """Releases lock held by agent on specified resource."""
        with self._cond:
            current_locks = self._locks.get(resource_id, [])
            filtered = [lk for lk in current_locks if lk.holder_id != agent_id]

            if len(filtered) != len(current_locks):
                if filtered:
                    self._locks[resource_id] = filtered
                else:
                    self._locks.pop(resource_id, None)
                self._cond.notify_all()
                return True
            return False

    def acquire_multi(
        self,
        resource_ids: List[str],
        agent_id: str,
        lock_type: LockType = LockType.WRITE,
        lease_duration: Optional[float] = None,
        timeout: float = 5.0,
    ) -> bool:
        """
        Acquires locks on multiple resources atomically with DEADLOCK PREVENTION.
        Resources are sorted canonically (lexicographically) before acquisition.
        If acquisition fails on any resource, all previously acquired resources are released.
        """
        # Canonical order prevents circular wait deadlocks
        canonical_resources = sorted(list(set(resource_ids)))
        acquired: List[str] = []
        deadline = time.time() + timeout

        with self._mutex:
            for r_id in canonical_resources:
                remaining = max(0.01, deadline - time.time())
                success = self.acquire_lock(
                    resource_id=r_id,
                    agent_id=agent_id,
                    lock_type=lock_type,
                    lease_duration=lease_duration,
                    timeout=remaining,
                )
                if success:
                    acquired.append(r_id)
                else:
                    # Rollback all acquired locks in this batch
                    for acquired_id in acquired:
                        self.release_lock(acquired_id, agent_id)
                    return False
            return True

    def reserve_resources(
        self,
        agent_id: str,
        resource_ids: List[str],
        lock_type: LockType = LockType.WRITE,
        lease_duration: Optional[float] = None,
        timeout: float = 5.0,
    ) -> Optional[str]:
        """
        Reserves multiple resources under a single transactional reservation_id.
        Returns reservation_id on success, or None on failure.
        """
        lease_sec = lease_duration if lease_duration is not None else self.default_lease_duration
        success = self.acquire_multi(
            resource_ids=resource_ids,
            agent_id=agent_id,
            lock_type=lock_type,
            lease_duration=lease_sec,
            timeout=timeout,
        )
        if not success:
            return None

        with self._mutex:
            res_id = f"res_{uuid.uuid4().hex[:10]}"
            reservation = ResourceReservation(
                reservation_id=res_id,
                agent_id=agent_id,
                resource_ids=sorted(list(set(resource_ids))),
                lock_type=lock_type,
                acquired_at=time.time(),
                lease_expiration=time.time() + lease_sec,
            )
            self._reservations[res_id] = reservation
            return res_id

    def release_reservation(self, reservation_id: str) -> bool:
        """Releases all resources tied to a reservation."""
        with self._mutex:
            reservation = self._reservations.get(reservation_id)
            if not reservation or reservation.released:
                return False

            for r_id in reservation.resource_ids:
                self.release_lock(r_id, reservation.agent_id)

            reservation.released = True
            return True

    def renew_lease(
        self,
        resource_id: str,
        agent_id: str,
        lease_duration: Optional[float] = None,
    ) -> bool:
        """Renews an active lock held by the given agent."""
        lease_sec = lease_duration if lease_duration is not None else self.default_lease_duration
        with self._cond:
            current_locks = self._locks.get(resource_id, [])
            for lk in current_locks:
                if lk.holder_id == agent_id:
                    lk.lease_expiration = time.time() + lease_sec
                    return True
            return False

    def clean_expired_leases(self, now: Optional[float] = None) -> List[str]:
        """Cleans up expired locks and returns list of freed resource IDs."""
        current_time = now if now is not None else time.time()
        freed: List[str] = []
        with self._cond:
            for r_id in list(self._locks.keys()):
                before_count = len(self._locks[r_id])
                self._locks[r_id] = [
                    lk for lk in self._locks[r_id]
                    if not lk.is_expired(current_time)
                ]
                if not self._locks[r_id]:
                    self._locks.pop(r_id, None)
                    freed.append(r_id)
                elif len(self._locks[r_id]) < before_count:
                    freed.append(r_id)

            if freed:
                self._cond.notify_all()
        return freed

    def is_locked(self, resource_id: str) -> bool:
        """Checks if a resource currently has any active locks."""
        with self._mutex:
            self._cleanup_expired_locked(time.time())
            return resource_id in self._locks and len(self._locks[resource_id]) > 0

    def get_lock_holders(self, resource_id: str) -> List[str]:
        """Returns list of agents currently holding a lock on the resource."""
        with self._mutex:
            self._cleanup_expired_locked(time.time())
            return [lk.holder_id for lk in self._locks.get(resource_id, [])]

    def get_active_locks(self) -> List[Dict[str, Any]]:
        """Returns snapshot of all active locks."""
        with self._mutex:
            self._cleanup_expired_locked(time.time())
            results: List[Dict[str, Any]] = []
            for r_id, lock_list in self._locks.items():
                for lk in lock_list:
                    results.append({
                        "resource_id": r_id,
                        "holder_id": lk.holder_id,
                        "lock_type": lk.lock_type.value,
                        "acquired_at": lk.acquired_at,
                        "lease_expiration": lk.lease_expiration,
                    })
            return results
