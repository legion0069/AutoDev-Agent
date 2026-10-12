"""
leader_election.py - Deterministic Leader Election & High Availability for AutoDev Cluster (v2.9)

Provides deterministic leader election, backup master promotion, term/epoch coordination,
split-brain prevention via quorum calculation, and automated leader failover.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import NodeInfo, NodeRole, NodeStatus
from core.cluster.node_registry import NodeRegistry

logger = logging.getLogger("AutoDev.Cluster.LeaderElection")


class ElectionState(str, Enum):
    FOLLOWER = "FOLLOWER"
    CANDIDATE = "CANDIDATE"
    LEADER = "LEADER"


@dataclass
class ElectionAuditRecord:
    epoch: int
    leader_id: str
    elected_at: float
    total_votes: int
    quorum_size: int
    reason: str
    candidates_ranked: List[Dict[str, Any]]


class LeaderElection:
    """
    Deterministic leader election coordinator.
    Evaluates role precedence, health score, uptime, and node_id tie-breaking to elect a cluster master.
    """

    def __init__(
        self,
        local_node_id: str,
        registry: NodeRegistry,
        config: Optional[ClusterConfig] = None,
        on_leader_changed: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        self.local_node_id = local_node_id
        self.registry = registry
        self.config = config or ClusterConfig()
        self.on_leader_changed = on_leader_changed

        self._epoch: int = 1
        self._current_leader: Optional[str] = None
        self._state: ElectionState = ElectionState.FOLLOWER
        self._lock = threading.RLock()
        self._audit_log: List[ElectionAuditRecord] = []
        self._last_election_time: float = 0.0

    @property
    def current_leader(self) -> Optional[str]:
        with self._lock:
            return self._current_leader

    @property
    def current_epoch(self) -> int:
        with self._lock:
            return self._epoch

    @property
    def state(self) -> ElectionState:
        with self._lock:
            return self._state

    def is_leader(self, node_id: Optional[str] = None) -> bool:
        """Returns True if the specified node (or local node) is current cluster leader."""
        target = node_id or self.local_node_id
        with self._lock:
            return self._current_leader == target

    def validate_quorum(self, active_node_count: Optional[int] = None) -> bool:
        """
        Validates if active node count satisfies quorum to prevent split-brain partition.
        Quorum requires count >= split_brain_quorum_size.
        """
        with self._lock:
            all_nodes = [
                n for n in self.registry.get_all_nodes()
                if n.status not in (NodeStatus.OFFLINE, NodeStatus.DEREGISTERED)
            ]
            count = active_node_count if active_node_count is not None else len(all_nodes)
            required = max(1, self.config.split_brain_quorum_size)
            return count >= required

    def compute_candidate_score(self, node: NodeInfo) -> Tuple[int, float, float, str]:
        """
        Computes deterministic sorting tuple for leader candidacy:
        1. Role Priority (MASTER = 3, BACKUP_MASTER = 2, WORKER = 1, OBSERVER = 0)
        2. Health Score (0.0 - 100.0)
        3. Historical uptime / success ratio
        4. Node ID (lexicographical inverse string for deterministic tie-breaking)
        Higher tuple value wins the election.
        """
        role_rank = 0
        if node.role == NodeRole.MASTER:
            role_rank = 3
        elif node.role == NodeRole.BACKUP_MASTER:
            role_rank = 2
        elif node.role == NodeRole.WORKER:
            role_rank = 1
        elif node.role == NodeRole.OBSERVER:
            role_rank = 0

        # Penalize degraded nodes
        status_penalty = 0.0 if node.status == NodeStatus.HEALTHY else -30.0
        adjusted_health = max(0.0, node.health_score + status_penalty)

        uptime_score = node.uptime
        return (role_rank, adjusted_health, uptime_score, node.node_id)

    def start_election(self, reason: str = "scheduled_or_failover") -> Optional[str]:
        """
        Conducts a deterministic leader election across eligible cluster nodes.
        Returns the newly elected leader ID, or None if quorum is not reached.
        """
        with self._lock:
            now = time.time()
            eligible_nodes = [
                n for n in self.registry.get_all_nodes()
                if n.status in (NodeStatus.HEALTHY, NodeStatus.DEGRADED, NodeStatus.RECOVERING)
                and n.role in (NodeRole.MASTER, NodeRole.BACKUP_MASTER, NodeRole.WORKER)
            ]

            if not self.validate_quorum(len(eligible_nodes)):
                logger.warning(
                    "Election aborted: Insufficient quorum (%d active nodes < %d required)",
                    len(eligible_nodes), self.config.split_brain_quorum_size
                )
                return None

            # Sort candidates deterministically descending by priority score
            ranked_candidates = sorted(
                eligible_nodes,
                key=lambda n: self.compute_candidate_score(n),
                reverse=True,
            )

            if not ranked_candidates:
                logger.error("Election failed: No eligible candidates in cluster")
                return None

            elected_node = ranked_candidates[0]
            new_leader_id = elected_node.node_id
            old_leader_id = self._current_leader

            self._epoch += 1
            self._current_leader = new_leader_id
            self._last_election_time = now

            if new_leader_id == self.local_node_id:
                self._state = ElectionState.LEADER
                logger.info("Local node %s successfully elected LEADER for Epoch %d (%s)", new_leader_id, self._epoch, reason)
            else:
                self._state = ElectionState.FOLLOWER
                logger.info("Node %s elected cluster LEADER for Epoch %d (%s)", new_leader_id, self._epoch, reason)

            # Record election audit
            audit_record = ElectionAuditRecord(
                epoch=self._epoch,
                leader_id=new_leader_id,
                elected_at=now,
                total_votes=len(ranked_candidates),
                quorum_size=self.config.split_brain_quorum_size,
                reason=reason,
                candidates_ranked=[
                    {"node_id": n.node_id, "score": self.compute_candidate_score(n)}
                    for n in ranked_candidates
                ],
            )
            self._audit_log.append(audit_record)

            # Fire callback if leader changed
            if old_leader_id != new_leader_id and self.on_leader_changed:
                try:
                    self.on_leader_changed(new_leader_id, self._epoch)
                except Exception as e:
                    logger.error("Error in on_leader_changed hook: %s", e)

            return new_leader_id

    def handle_leader_failure(self, failed_leader_id: str) -> Optional[str]:
        """
        Invoked when heartbeat manager detects leader is offline.
        Promotes highest-priority backup master or candidate.
        """
        with self._lock:
            logger.warning("Handling leader failure for %s. Triggering election.", failed_leader_id)
            if self._current_leader == failed_leader_id:
                self._current_leader = None
            return self.start_election(reason=f"leader_failure_{failed_leader_id}")

    def step_down(self, reason: str = "voluntary") -> None:
        """
        Steps down from leadership role.
        """
        with self._lock:
            if self._state == ElectionState.LEADER:
                logger.info("Node %s stepping down as LEADER: %s", self.local_node_id, reason)
                self._state = ElectionState.FOLLOWER
                if self._current_leader == self.local_node_id:
                    self._current_leader = None

    def get_audit_history(self) -> List[Dict[str, Any]]:
        """Returns list of audit log entries."""
        with self._lock:
            return [
                {
                    "epoch": r.epoch,
                    "leader_id": r.leader_id,
                    "elected_at": r.elected_at,
                    "total_votes": r.total_votes,
                    "reason": r.reason,
                    "candidates_ranked": r.candidates_ranked,
                }
                for r in self._audit_log
            ]
