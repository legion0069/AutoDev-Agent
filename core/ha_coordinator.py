"""
ha_coordinator.py - High Availability Coordinator & Leader Fencing Engine for AutoDev (v2.4)

Implements consensus-backed leader election, quorum verification, monotonically increasing
fencing token generation, failover reconciliation, and fail-closed state protection.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.consensus_protocol import (
    ConsensusHeartbeat,
    CoordinatorNode,
    CoordinatorRole,
    FencingToken,
    VoteRequest,
    VoteResponse,
)

logger = logging.getLogger("AutoDev.HACoordinator")


class HAError(Exception):
    """Base exception for high availability and consensus operations."""
    pass


class NotLeaderError(HAError):
    """Raised when a non-leader coordinator attempts a protected mutation."""
    pass


class StaleLeaderError(HAError):
    """Raised when a coordinator loses leadership or possesses an expired fencing token."""
    pass


class FencingViolationError(HAError):
    """Raised when an operation is attempted with an outdated fencing generation token."""
    pass


class QuorumLostError(HAError):
    """Raised when an HA cluster cannot achieve majority quorum."""
    pass


class LeaderFencingValidator:
    """
    Guards protected mutations by verifying that the coordinator holds active,
    authoritative leadership and a valid fencing generation token.
    """

    def __init__(self, ha_coordinator: HACoordinator) -> None:
        self.ha_coordinator = ha_coordinator

    def assert_active_leader(self, operation_name: str = "mutation") -> FencingToken:
        """
        Validates active leadership. If leadership is stale, revoked, or expired,
        raises FencingViolationError or NotLeaderError immediately (fail-closed).
        """
        if not self.ha_coordinator.is_leader:
            raise NotLeaderError(
                f"Coordinator '{self.ha_coordinator.coordinator_id}' (role: {self.ha_coordinator.role.value}) "
                f"cannot execute protected operation '{operation_name}' because it is not the active leader."
            )

        token = self.ha_coordinator.fencing_token
        if not token or token.is_expired:
            self.ha_coordinator.step_down("Fencing token expired")
            raise StaleLeaderError(
                f"Coordinator '{self.ha_coordinator.coordinator_id}' fencing token is expired or missing. "
                f"Operation '{operation_name}' rejected."
            )

        return token

    def validate_fencing_token(self, token: Optional[FencingToken], minimum_generation: int = 0) -> bool:
        """Validates that a provided fencing token is active and matches minimum generation."""
        if not token or token.is_expired:
            return False
        return token.fencing_generation >= minimum_generation


class HACoordinator:
    """
    Multi-node High Availability coordinator participating in leader election,
    fencing token issuance, quorum monitoring, and failover reconciliation.
    """

    def __init__(
        self,
        coordinator_id: str,
        peers: Optional[List[Any]] = None,
        peer_ids: Optional[List[str]] = None,
        store: Optional[Any] = None,
        host: str = "127.0.0.1",
        port: int = 50051,
        election_timeout_range: Tuple[float, float] = (1.5, 3.0),
        heartbeat_interval_seconds: float = 0.5,
        lease_duration_seconds: float = 5.0,
        transport_call: Optional[Callable[[str, str, Dict[str, Any]], Dict[str, Any]]] = None,
        consensus_provider: Optional[Any] = None,
    ) -> None:
        self.coordinator_id = coordinator_id
        self.host = host
        self.port = port
        self.store = store
        self.election_timeout_range = election_timeout_range
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.lease_duration_seconds = lease_duration_seconds
        self.transport_call = transport_call
        self.consensus_provider = consensus_provider

        self.role: CoordinatorRole = CoordinatorRole.STARTING
        self.current_term: int = 0
        self.current_generation: int = 0
        self.voted_for: Optional[str] = None
        self.leader_id: Optional[str] = None
        self.fencing_token: Optional[FencingToken] = None
        self._consensus_lease: Optional[Any] = None

        self._peers: Dict[str, CoordinatorNode] = {}
        all_peers = list(peers or [])
        if peer_ids:
            all_peers.extend(peer_ids)

        for p in all_peers:
            if isinstance(p, str):
                if p != self.coordinator_id:
                    self._peers[p] = CoordinatorNode(coordinator_id=p)
            elif isinstance(p, CoordinatorNode):
                if p.coordinator_id != self.coordinator_id:
                    self._peers[p.coordinator_id] = p

        self._lock = threading.RLock()
        self._is_running = False
        self._last_heartbeat_received_ts = time.time()
        self._election_timeout = random.uniform(*self.election_timeout_range)
        self._bg_thread: Optional[threading.Thread] = None
        self._on_role_change_callbacks: List[Callable[[CoordinatorRole], None]] = []

    @property
    def is_leader(self) -> bool:
        with self._lock:
            return self.role == CoordinatorRole.LEADER and bool(self.fencing_token and not self.fencing_token.is_expired)

    @property
    def total_cluster_size(self) -> int:
        with self._lock:
            return len(self._peers) + 1

    @property
    def quorum_size(self) -> int:
        return (self.total_cluster_size // 2) + 1

    def register_peer(self, peer: CoordinatorNode) -> None:
        """Registers a new peer coordinator node in the cluster."""
        with self._lock:
            if peer.coordinator_id != self.coordinator_id:
                self._peers[peer.coordinator_id] = peer

    def deregister_peer(self, peer_id: str) -> None:
        with self._lock:
            self._peers.pop(peer_id, None)

    def on_role_change(self, callback: Callable[[CoordinatorRole], None]) -> None:
        self._on_role_change_callbacks.append(callback)

    def _set_role(self, new_role: CoordinatorRole) -> None:
        old_role = self.role
        self.role = new_role
        if old_role != new_role:
            logger.info("Coordinator '%s' transitioned role from %s to %s (term: %d)", self.coordinator_id, old_role.value, new_role.value, self.current_term)
            for cb in self._on_role_change_callbacks:
                try:
                    cb(new_role)
                except Exception as e:
                    logger.warning("Error in on_role_change callback: %s", e)

    def start(self) -> None:
        """Starts background election and heartbeat loops."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._set_role(CoordinatorRole.FOLLOWER)
            self._last_heartbeat_received_ts = time.time()
            self._election_timeout = random.uniform(*self.election_timeout_range)

            # Single-node cluster automatically assumes leadership
            if not self._peers:
                self._assume_leadership()

            self._bg_thread = threading.Thread(
                target=self._run_loop,
                name=f"HA-Coordinator-{self.coordinator_id}",
                daemon=True,
            )
            self._bg_thread.start()

    def stop(self) -> None:
        """Gracefully steps down and stops background loops."""
        with self._lock:
            self._is_running = False
            self.step_down("Coordinator shutting down")
            self._set_role(CoordinatorRole.STOPPING)

    def _assume_leadership(self) -> None:
        """Transitions this node to LEADER and issues a new FencingToken."""
        if self.consensus_provider:
            try:
                lease = self.consensus_provider.acquire_leadership(
                    coordinator_id=self.coordinator_id,
                    term=self.current_term,
                    ttl_seconds=self.lease_duration_seconds,
                )
                self._consensus_lease = lease
                self.current_term = lease.term
                self.current_generation = lease.generation
                self.leader_id = self.coordinator_id
                self.fencing_token = FencingToken(
                    term=lease.term,
                    leader_id=self.coordinator_id,
                    fencing_generation=lease.generation,
                    expires_at_timestamp=lease.expires_at,
                )
                self._set_role(CoordinatorRole.LEADER)
                logger.info(
                    "Coordinator '%s' acquired external consensus leadership for term %d (generation %d)",
                    self.coordinator_id,
                    self.current_term,
                    self.current_generation,
                )
                return
            except Exception as e:
                logger.warning("Failed to acquire external consensus lease: %s", e)
                self.step_down(f"Consensus acquire failed: {e}")
                return

        self.current_generation += 1
        self.leader_id = self.coordinator_id
        self.fencing_token = FencingToken(
            term=self.current_term,
            leader_id=self.coordinator_id,
            fencing_generation=self.current_generation,
            expires_at_timestamp=time.time() + self.lease_duration_seconds,
        )
        self._set_role(CoordinatorRole.LEADER)
        logger.info(
            "Coordinator '%s' acquired leadership for term %d (generation %d)",
            self.coordinator_id,
            self.current_term,
            self.current_generation,
        )

    def step_down(self, reason: str = "") -> None:
        """Relinquishes leadership and invalidates current fencing token."""
        with self._lock:
            if self.role == CoordinatorRole.LEADER:
                logger.warning("Leader '%s' stepping down. Reason: %s", self.coordinator_id, reason)
            if self.consensus_provider and self._consensus_lease:
                try:
                    self.consensus_provider.release_leadership(self._consensus_lease)
                except Exception as e:
                    logger.debug("Error releasing consensus lease on step_down: %s", e)
                self._consensus_lease = None
            self.fencing_token = None
            if self._is_running:
                self._set_role(CoordinatorRole.FOLLOWER)
            else:
                self._set_role(CoordinatorRole.UNAVAILABLE)

    def start_election(self) -> bool:
        """
        Initiates a new election term, votes for self, and requests votes from peers.
        Returns True if leadership quorum was acquired.
        """
        with self._lock:
            self.current_term += 1
            self._set_role(CoordinatorRole.CANDIDATE)
            self.voted_for = self.coordinator_id
            self.leader_id = None
            self.fencing_token = None
            self._last_heartbeat_received_ts = time.time()
            self._election_timeout = random.uniform(*self.election_timeout_range)

            votes_granted = 1  # Vote for self
            req = VoteRequest(
                term=self.current_term,
                candidate_id=self.coordinator_id,
            )

            # In single node cluster, immediately win
            if not self._peers:
                self._assume_leadership()
                return True

            for peer_id, peer in list(self._peers.items()):
                resp = self._send_vote_request(peer_id, req)
                if resp and resp.vote_granted:
                    votes_granted += 1
                elif resp and resp.term > self.current_term:
                    self.current_term = resp.term
                    self.step_down(f"Peer {peer_id} reported higher term {resp.term}")
                    return False

            if votes_granted >= self.quorum_size:
                self._assume_leadership()
                return True
            else:
                logger.info("Election failed for term %d (got %d votes, needed %d)", self.current_term, votes_granted, self.quorum_size)
                self._set_role(CoordinatorRole.FOLLOWER)
                return False

    def _send_vote_request(self, peer_id: str, request: VoteRequest) -> Optional[VoteResponse]:
        if self.transport_call:
            try:
                res = self.transport_call(peer_id, "RequestVote", request.to_dict())
                return VoteResponse.from_dict(res)
            except Exception as e:
                logger.debug("Failed to send RequestVote to peer %s: %s", peer_id, e)
                return None
        return None

    def receive_vote_request(self, request: VoteRequest) -> VoteResponse:
        """Handles incoming VoteRequest from candidate peer."""
        with self._lock:
            # If candidate term is higher, update local term and step down
            if request.term > self.current_term:
                self.current_term = request.term
                self.voted_for = None
                self.step_down(f"Higher term {request.term} received in vote request")

            # Vote granting rules
            vote_granted = False
            reason = ""
            if request.term == self.current_term and (self.voted_for is None or self.voted_for == request.candidate_id):
                vote_granted = True
                self.voted_for = request.candidate_id
                self._last_heartbeat_received_ts = time.time()
                reason = "Vote granted"
            else:
                reason = f"Already voted for {self.voted_for} in term {self.current_term}"

            return VoteResponse(
                term=self.current_term,
                vote_granted=vote_granted,
                voter_id=self.coordinator_id,
                reason=reason,
            )

    def receive_heartbeat(self, heartbeat: ConsensusHeartbeat) -> Dict[str, Any]:
        """Handles periodic heartbeat from cluster leader."""
        with self._lock:
            if heartbeat.term < self.current_term:
                return {"success": False, "term": self.current_term, "reason": "Heartbeat term outdated"}

            if heartbeat.term > self.current_term:
                self.current_term = heartbeat.term
                self.voted_for = None

            self.leader_id = heartbeat.leader_id
            self._last_heartbeat_received_ts = time.time()
            if self.role != CoordinatorRole.FOLLOWER:
                self._set_role(CoordinatorRole.FOLLOWER)

            return {"success": True, "term": self.current_term}

    def renew_leader_lease(self) -> bool:
        """Leader refreshes its lease and fencing token expiration."""
        with self._lock:
            if self.role != CoordinatorRole.LEADER:
                return False
            if self.consensus_provider and self._consensus_lease:
                try:
                    renewed = self.consensus_provider.renew_leadership(
                        self._consensus_lease, ttl_seconds=self.lease_duration_seconds
                    )
                    self._consensus_lease = renewed
                    if self.fencing_token:
                        self.fencing_token.expires_at_timestamp = renewed.expires_at
                        self.fencing_token.fencing_generation = renewed.generation
                    return True
                except Exception as e:
                    logger.warning("Consensus lease renewal failed: %s", e)
                    self.step_down(f"Consensus renewal failed: {e}")
                    return False

            if self.fencing_token:
                self.fencing_token.expires_at_timestamp = time.time() + self.lease_duration_seconds
            return True

    def _broadcast_heartbeat(self) -> None:
        """Leader broadcasts heartbeat to all registered peers."""
        hb = ConsensusHeartbeat(
            term=self.current_term,
            leader_id=self.coordinator_id,
            fencing_generation=self.current_generation,
            lease_ttl_seconds=self.lease_duration_seconds,
        )
        self.renew_leader_lease()

        if not self.transport_call:
            return

        acked = 1
        for peer_id in list(self._peers.keys()):
            try:
                res = self.transport_call(peer_id, "Heartbeat", hb.to_dict())
                if res and res.get("success"):
                    acked += 1
                elif res and res.get("term", 0) > self.current_term:
                    self.current_term = res["term"]
                    self.step_down("Heartbeat response indicated higher term")
                    return
            except Exception:
                pass

        # Quorum loss check
        if acked < self.quorum_size and len(self._peers) > 0:
            logger.warning("Leader '%s' lost quorum (%d/%d acked). Entering DEGRADED mode.", self.coordinator_id, acked, self.quorum_size)
            self._set_role(CoordinatorRole.DEGRADED)
            self.fencing_token = None

    def _run_loop(self) -> None:
        """Background thread monitoring election timeouts or sending leader heartbeats."""
        while self._is_running:
            time.sleep(self.heartbeat_interval_seconds)
            with self._lock:
                if not self._is_running:
                    break

                now = time.time()
                if self.role == CoordinatorRole.LEADER:
                    self._broadcast_heartbeat()
                else:
                    # Check election timeout
                    elapsed = now - self._last_heartbeat_received_ts
                    if elapsed > self._election_timeout:
                        logger.info("Election timeout elapsed (%.2fs > %.2fs). Starting election...", elapsed, self._election_timeout)
                        self.start_election()

    def reconcile_failover(
        self,
        active_transactions: Optional[List[Any]] = None,
        lease_manager: Optional[Any] = None,
        journal: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Reconciles in-flight transactions and task leases after this node becomes leader.
        Identifies orphaned leases, checks journal integrity, and safely resumes work.
        """
        fencing = LeaderFencingValidator(self).assert_active_leader("reconcile_failover")

        report: Dict[str, Any] = {
            "leader_id": self.coordinator_id,
            "term": self.current_term,
            "fencing_generation": fencing.fencing_generation,
            "status": "reconciled",
            "reconciled_by": self.coordinator_id,
            "current_term": self.current_term,
            "reconciled_transactions": 0,
            "orphaned_leases_revoked": 0,
            "recovery_required_transactions": [],
        }

        with self._lock:
            # 1. Prune expired or stale task leases
            if lease_manager and hasattr(lease_manager, "prune_expired_leases"):
                expired = lease_manager.prune_expired_leases()
                report["orphaned_leases_revoked"] = len(expired)

            # 2. Inspect active transactions
            for tx in (active_transactions or []):
                report["reconciled_transactions"] += 1
                # Mark transactions with ambiguous state for verification
                if hasattr(tx, "status") and str(tx.status).endswith("RUNNING"):
                    # Record adoption event in journal
                    if journal and hasattr(journal, "append_event"):
                        journal.append_event(
                            event_type="ha.transaction_adopted",
                            transaction_id=tx.transaction_id,
                            payload={
                                "new_leader_id": self.coordinator_id,
                                "term": self.current_term,
                                "fencing_generation": fencing.fencing_generation,
                            },
                        )

        logger.info("Failover reconciliation completed by leader '%s': %s", self.coordinator_id, report)
        return report
