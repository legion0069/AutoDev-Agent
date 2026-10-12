"""
AutoDev Version 2.5 - Distributed Consensus Provider Abstraction.

Defines the pluggable consensus interface, data contracts, exceptions, and
authoritative fencing validation for HA coordinators across local and multi-node clusters.
"""

from __future__ import annotations

import abc
import time
import uuid
import hmac
import hashlib
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# =====================================================================
# Consensus Exceptions
# =====================================================================

class ConsensusError(Exception):
    """Base error for consensus provider failures."""
    pass


class ConsensusUnavailableError(ConsensusError):
    """Raised when the consensus backend cannot be reached."""
    pass


class QuorumUnavailableError(ConsensusError):
    """Raised when consensus backend loses quorum."""
    pass


class LeadershipLostError(ConsensusError):
    """Raised when a coordinator discovers its leadership lease has expired or been revoked."""
    pass


class ConsensusConfigurationError(ConsensusError):
    """Raised when consensus configuration is invalid or missing required parameters."""
    pass


class FencingTokenRejectedError(ConsensusError):
    """Raised when a state mutation fails due to a stale or invalid leader fencing token."""
    pass


# =====================================================================
# Consensus Data Models
# =====================================================================

@dataclass
class LeadershipToken:
    """
    Monotonically increasing fencing token passed on all protected state mutations.
    Enforces that stale leaders (zombies) cannot commit state mutations after a term bump.
    """
    leader_id: str
    term: int
    generation: int
    signature: str = ""
    issued_at: float = field(default_factory=time.time)

    def is_newer_than(self, other: Optional[LeadershipToken]) -> bool:
        if other is None:
            return True
        if self.term > other.term:
            return True
        if self.term == other.term:
            return self.generation > other.generation
        return False

    def is_stale_compared_to(self, current_term: int, current_gen: int) -> bool:
        if self.term < current_term:
            return True
        if self.term == current_term and self.generation < current_gen:
            return True
        return False


@dataclass
class LeadershipLease:
    """Represents a granted distributed leadership lease."""
    lease_id: str
    leader_id: str
    term: int
    generation: int
    fencing_token: LeadershipToken
    granted_at: float
    expires_at: float
    is_active: bool = True

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at or not self.is_active

    @property
    def remaining_ttl(self) -> float:
        return max(0.0, self.expires_at - time.time())


@dataclass
class ConsensusConfiguration:
    """Configuration for external or local consensus backends."""
    provider_type: str = "memory"  # 'memory', 'etcd', 'consul'
    endpoints: List[str] = field(default_factory=lambda: ["127.0.0.1:2379"])
    prefix: str = "/autodev/consensus"
    timeout_seconds: float = 5.0
    lease_ttl_seconds: float = 10.0
    retry_limit: int = 3
    backoff_base_seconds: float = 0.5
    verify_tls: bool = True
    tls_ca_cert: Optional[str] = None
    tls_client_cert: Optional[str] = None
    tls_client_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    datacenter: Optional[str] = None  # Consul specific


@dataclass
class ConsensusHealth:
    """Health and readiness status of the consensus provider."""
    is_healthy: bool
    backend_type: str
    leader_id: Optional[str]
    term: int
    generation: int
    cluster_size: int
    latency_ms: float
    details: Dict[str, Any] = field(default_factory=dict)


# =====================================================================
# Consensus Provider Abstract Base Class
# =====================================================================

class ConsensusProvider(abc.ABC):
    """
    Abstract contract for distributed consensus backends (etcd, Consul, Memory).
    Provides atomic leader election, leases, authoritative fencing tokens,
    and conditional compare-and-swap state mutations.
    """

    @abc.abstractmethod
    def acquire_leadership(
        self, coordinator_id: str, term: int, ttl_seconds: float = 10.0
    ) -> LeadershipLease:
        """Attempt to atomically acquire leadership for a specified term."""
        pass

    @abc.abstractmethod
    def renew_leadership(
        self, lease: LeadershipLease, ttl_seconds: float = 10.0
    ) -> LeadershipLease:
        """Renew an existing active leadership lease."""
        pass

    @abc.abstractmethod
    def verify_leadership(self, lease: LeadershipLease) -> bool:
        """Authoritatively verify if the lease holder is still the active leader."""
        pass

    @abc.abstractmethod
    def release_leadership(self, lease: LeadershipLease) -> bool:
        """Voluntarily release leadership during graceful shutdown."""
        pass

    @abc.abstractmethod
    def get_fencing_token(self) -> LeadershipToken:
        """Retrieve the current authoritative fencing token."""
        pass

    @abc.abstractmethod
    def get(self, key: str) -> Optional[Tuple[str, int]]:
        """Retrieve a key's value and its monotonic version/revision."""
        pass

    @abc.abstractmethod
    def conditional_put(
        self,
        key: str,
        value: str,
        expected_version: Optional[int] = None,
        fencing_token: Optional[LeadershipToken] = None,
    ) -> bool:
        """
        Atomic Compare-And-Swap. Fails if key version does not match expected_version
        or if fencing_token is stale compared to authoritative backend generation.
        """
        pass

    @abc.abstractmethod
    def conditional_delete(
        self,
        key: str,
        expected_version: int,
        fencing_token: Optional[LeadershipToken] = None,
    ) -> bool:
        """Atomic deletion conditional on version and valid fencing token."""
        pass

    @abc.abstractmethod
    def get_health(self) -> ConsensusHealth:
        """Check provider connectivity, leader status, and latency."""
        pass

    @abc.abstractmethod
    def close(self) -> None:
        """Cleanly close sessions and background connections."""
        pass


# =====================================================================
# In-Memory Consensus Provider (Default Local / Unit Testing Backend)
# =====================================================================

class MemoryConsensusProvider(ConsensusProvider):
    """
    Thread-safe in-memory consensus provider supporting simulation of
    quorum, fencing, network partitions, and CAS operations.
    """

    def __init__(self, config: Optional[ConsensusConfiguration] = None):
        self.config = config or ConsensusConfiguration(provider_type="memory")
        self._lock = threading.RLock()
        self._store: Dict[str, Tuple[str, int]] = {}  # key -> (value, version)
        self._current_leader: Optional[str] = None
        self._current_term: int = 0
        self._current_generation: int = 0
        self._active_lease: Optional[LeadershipLease] = None
        self._partitioned: bool = False
        self._secret_key: bytes = uuid.uuid4().bytes

    def set_partitioned(self, partitioned: bool) -> None:
        """Simulate network partition / quorum unavailability."""
        with self._lock:
            self._partitioned = partitioned

    def _sign_token(self, leader_id: str, term: int, generation: int) -> str:
        msg = f"{leader_id}:{term}:{generation}".encode()
        return hmac.new(self._secret_key, msg, hashlib.sha256).hexdigest()

    def acquire_leadership(
        self, coordinator_id: str, term: int, ttl_seconds: float = 10.0
    ) -> LeadershipLease:
        with self._lock:
            if self._partitioned:
                raise QuorumUnavailableError("Consensus partition active; cannot reach quorum.")

            now = time.time()
            if self._active_lease and not self._active_lease.is_expired:
                if self._active_lease.leader_id != coordinator_id:
                    raise LeadershipLostError(
                        f"Active leader '{self._active_lease.leader_id}' holds valid lease until {self._active_lease.expires_at}"
                    )
                if term < self._current_term:
                    raise LeadershipLostError(f"Requested term {term} is older than current term {self._current_term}")

            self._current_leader = coordinator_id
            self._current_term = max(self._current_term, term)
            self._current_generation += 1

            token = LeadershipToken(
                leader_id=coordinator_id,
                term=self._current_term,
                generation=self._current_generation,
                signature=self._sign_token(coordinator_id, self._current_term, self._current_generation),
                issued_at=now,
            )

            lease = LeadershipLease(
                lease_id=f"lease-{uuid.uuid4().hex[:8]}",
                leader_id=coordinator_id,
                term=self._current_term,
                generation=self._current_generation,
                fencing_token=token,
                granted_at=now,
                expires_at=now + ttl_seconds,
                is_active=True,
            )
            self._active_lease = lease
            return lease

    def renew_leadership(
        self, lease: LeadershipLease, ttl_seconds: float = 10.0
    ) -> LeadershipLease:
        with self._lock:
            if self._partitioned:
                raise QuorumUnavailableError("Consensus partition active; cannot reach quorum.")

            if not self._active_lease or self._active_lease.is_expired:
                raise LeadershipLostError("Lease has already expired.")

            if self._active_lease.leader_id != lease.leader_id or self._active_lease.term != lease.term:
                raise LeadershipLostError(
                    f"Leadership hijacked by '{self._active_lease.leader_id}' (term {self._active_lease.term})"
                )

            now = time.time()
            self._current_generation += 1
            token = LeadershipToken(
                leader_id=lease.leader_id,
                term=self._current_term,
                generation=self._current_generation,
                signature=self._sign_token(lease.leader_id, self._current_term, self._current_generation),
                issued_at=now,
            )

            renewed = LeadershipLease(
                lease_id=lease.lease_id,
                leader_id=lease.leader_id,
                term=lease.term,
                generation=self._current_generation,
                fencing_token=token,
                granted_at=now,
                expires_at=now + ttl_seconds,
                is_active=True,
            )
            self._active_lease = renewed
            return renewed

    def verify_leadership(self, lease: LeadershipLease) -> bool:
        with self._lock:
            if self._partitioned:
                return False
            if not self._active_lease or self._active_lease.is_expired:
                return False
            return (
                self._active_lease.leader_id == lease.leader_id
                and self._active_lease.term == lease.term
                and self._active_lease.lease_id == lease.lease_id
            )

    def release_leadership(self, lease: LeadershipLease) -> bool:
        with self._lock:
            if self._active_lease and self._active_lease.leader_id == lease.leader_id:
                self._active_lease.is_active = False
                self._active_lease = None
                self._current_leader = None
                return True
            return False

    def get_fencing_token(self) -> LeadershipToken:
        with self._lock:
            if not self._current_leader:
                raise LeadershipLostError("No active leader elected.")
            return LeadershipToken(
                leader_id=self._current_leader,
                term=self._current_term,
                generation=self._current_generation,
                signature=self._sign_token(self._current_leader, self._current_term, self._current_generation),
            )

    def _validate_fencing_token(self, token: Optional[LeadershipToken]) -> None:
        if token is None:
            return
        if token.is_stale_compared_to(self._current_term, self._current_generation):
            raise FencingTokenRejectedError(
                f"Fencing token stale: token (term={token.term}, gen={token.generation}) < current (term={self._current_term}, gen={self._current_generation})"
            )
        expected_sig = self._sign_token(token.leader_id, token.term, token.generation)
        if token.signature != expected_sig:
            raise FencingTokenRejectedError("Fencing token signature verification failed.")

    def get(self, key: str) -> Optional[Tuple[str, int]]:
        with self._lock:
            if self._partitioned:
                raise QuorumUnavailableError("Consensus partition active; cannot reach quorum.")
            return self._store.get(key)

    def conditional_put(
        self,
        key: str,
        value: str,
        expected_version: Optional[int] = None,
        fencing_token: Optional[LeadershipToken] = None,
    ) -> bool:
        with self._lock:
            if self._partitioned:
                raise QuorumUnavailableError("Consensus partition active; cannot reach quorum.")
            self._validate_fencing_token(fencing_token)

            existing = self._store.get(key)
            current_ver = existing[1] if existing else 0

            if expected_version is not None and current_ver != expected_version:
                return False

            new_version = current_ver + 1
            self._store[key] = (value, new_version)
            return True

    def conditional_delete(
        self,
        key: str,
        expected_version: int,
        fencing_token: Optional[LeadershipToken] = None,
    ) -> bool:
        with self._lock:
            if self._partitioned:
                raise QuorumUnavailableError("Consensus partition active; cannot reach quorum.")
            self._validate_fencing_token(fencing_token)

            existing = self._store.get(key)
            if not existing:
                return False
            if existing[1] != expected_version:
                return False

            del self._store[key]
            return True

    def get_health(self) -> ConsensusHealth:
        with self._lock:
            return ConsensusHealth(
                is_healthy=not self._partitioned,
                backend_type="memory",
                leader_id=self._current_leader,
                term=self._current_term,
                generation=self._current_generation,
                cluster_size=1,
                latency_ms=0.05,
                details={"keys_count": len(self._store), "partitioned": self._partitioned},
            )

    def close(self) -> None:
        with self._lock:
            self._store.clear()
            self._active_lease = None
            self._current_leader = None
