"""
heartbeat_manager.py - Heartbeat Protocol & Failure Detection for AutoDev Cluster (v2.9)

Monitors node health, evaluates dynamic health scores, detects degraded or offline nodes,
manages failure recovery lifecycle, and triggers automated failover notifications.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import NodeInfo, NodeStatus
from core.cluster.node_registry import NodeRegistry

logger = logging.getLogger("AutoDev.Cluster.Heartbeat")


class HeartbeatManager:
    """
    Heartbeat monitoring and fault detection engine.
    Calculates multi-criteria health scores and fires state transition events.
    """

    def __init__(
        self,
        registry: NodeRegistry,
        config: Optional[ClusterConfig] = None,
        on_node_offline: Optional[Callable[[str, NodeInfo], None]] = None,
        on_node_degraded: Optional[Callable[[str, NodeInfo], None]] = None,
        on_node_recovered: Optional[Callable[[str, NodeInfo], None]] = None,
        on_node_healthy: Optional[Callable[[str, NodeInfo], None]] = None,
    ) -> None:
        self.registry = registry
        self.config = config or ClusterConfig()
        self.on_node_offline = on_node_offline
        self.on_node_degraded = on_node_degraded
        self.on_node_recovered = on_node_recovered
        self.on_node_healthy = on_node_healthy

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._missed_heartbeats: Dict[str, int] = {}
        self._last_state_map: Dict[str, NodeStatus] = {}

    def calculate_health_score(
        self,
        cpu_utilization: float,
        memory_utilization: float,
        active_tasks: int,
        max_tasks: int,
        latency_ms: float,
    ) -> float:
        """
        Computes composite health score [0.0 - 100.0] based on resource load and latency.
        """
        # Penalties (0.0 - 100.0 scale)
        cpu_penalty = min(100.0, max(0.0, cpu_utilization))
        mem_penalty = min(100.0, max(0.0, memory_utilization))
        
        task_ratio = (active_tasks / max_tasks) if max_tasks > 0 else 1.0
        task_penalty = min(100.0, max(0.0, task_ratio * 100.0))
        
        # Latency penalty: > 200ms begins significant penalty
        lat_penalty = min(100.0, max(0.0, (latency_ms / 2.0)))

        score = 100.0 - (
            0.30 * cpu_penalty +
            0.30 * mem_penalty +
            0.20 * task_penalty +
            0.20 * lat_penalty
        )
        return max(0.0, min(100.0, round(score, 2)))

    def record_node_heartbeat(
        self,
        node_id: str,
        cpu_utilization: float = 0.0,
        memory_utilization: float = 0.0,
        active_tasks: int = 0,
        latency_ms: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Receives heartbeat ping from a node, computes health score, updates registry,
        and manages recovery transitions.
        """
        with self._lock:
            node = self.registry.get_node(node_id)
            if not node:
                return False

            max_tasks = node.max_tasks if node.max_tasks > 0 else 4
            health_score = self.calculate_health_score(
                cpu_utilization=cpu_utilization,
                memory_utilization=memory_utilization,
                active_tasks=active_tasks,
                max_tasks=max_tasks,
                latency_ms=latency_ms,
            )

            # Reset missed count
            prev_missed = self._missed_heartbeats.get(node_id, 0)
            self._missed_heartbeats[node_id] = 0

            # Determine new status
            prev_status = node.status
            new_status = NodeStatus.HEALTHY
            if health_score < self.config.health_score_threshold_degraded or cpu_utilization > 90.0 or memory_utilization > 90.0:
                new_status = NodeStatus.DEGRADED

            # Check if recovering from OFFLINE
            if prev_status == NodeStatus.OFFLINE:
                new_status = NodeStatus.RECOVERING
                logger.info("Node %s is recovering from OFFLINE status", node_id)
                self.registry.update_node_status(node_id, new_status)
                if self.on_node_recovered:
                    try:
                        self.on_node_recovered(node_id, node)
                    except Exception as e:
                        logger.error("Error in on_node_recovered hook for %s: %s", node_id, e)
            else:
                self.registry.update_node_status(node_id, new_status)

            # Update metrics
            self.registry.record_heartbeat(
                node_id=node_id,
                cpu_utilization=cpu_utilization,
                memory_utilization=memory_utilization,
                active_tasks=active_tasks,
                latency_ms=latency_ms,
                health_score=health_score,
                metadata=metadata,
            )
            return True

    def check_heartbeats(self, current_time: Optional[float] = None) -> Dict[str, NodeStatus]:
        """
        Synchronous probe checking last heartbeat timestamp of all registered nodes.
        Returns map of node_id -> updated NodeStatus.
        """
        with self._lock:
            now = current_time if current_time is not None else time.time()
            nodes = self.registry.get_all_nodes()
            status_map: Dict[str, NodeStatus] = {}

            for node in nodes:
                if node.status == NodeStatus.DEREGISTERED:
                    continue

                elapsed = now - node.last_heartbeat
                node_id = node.node_id
                old_status = node.status

                if elapsed > self.config.worker_timeout:
                    new_status = NodeStatus.OFFLINE
                    self._missed_heartbeats[node_id] = self._missed_heartbeats.get(node_id, 0) + 1
                    if old_status != NodeStatus.OFFLINE:
                        logger.warning(
                            "Node %s missed heartbeat timeout (elapsed=%.2fs > timeout=%.2fs). Marked OFFLINE.",
                            node_id, elapsed, self.config.worker_timeout
                        )
                        self.registry.update_node_status(node_id, NodeStatus.OFFLINE)
                        if self.on_node_offline:
                            try:
                                self.on_node_offline(node_id, node)
                            except Exception as e:
                                logger.error("Error in on_node_offline hook for %s: %s", node_id, e)
                elif elapsed > (self.config.heartbeat_interval * self.config.degraded_threshold_heartbeats):
                    new_status = NodeStatus.DEGRADED
                    if old_status == NodeStatus.HEALTHY:
                        logger.warning(
                            "Node %s delayed heartbeat (elapsed=%.2fs). Marked DEGRADED.",
                            node_id, elapsed
                        )
                        self.registry.update_node_status(node_id, NodeStatus.DEGRADED)
                        if self.on_node_degraded:
                            try:
                                self.on_node_degraded(node_id, node)
                            except Exception as e:
                                logger.error("Error in on_node_degraded hook for %s: %s", node_id, e)
                else:
                    if old_status == NodeStatus.RECOVERING:
                        new_status = NodeStatus.HEALTHY
                        self.registry.update_node_status(node_id, NodeStatus.HEALTHY)
                        if self.on_node_healthy:
                            try:
                                self.on_node_healthy(node_id, node)
                            except Exception as e:
                                logger.error("Error in on_node_healthy hook for %s: %s", node_id, e)
                    else:
                        new_status = old_status

                status_map[node_id] = new_status

            return status_map

    def start(self) -> None:
        """Starts background heartbeat checking thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="HeartbeatMonitor")
            self._thread.start()
            logger.info("Started cluster HeartbeatManager background loop")

    def stop(self) -> None:
        """Stops background heartbeat checking thread."""
        with self._lock:
            self._running = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
            logger.info("Stopped cluster HeartbeatManager background loop")

    def _monitor_loop(self) -> None:
        while self._running:
            try:
                self.check_heartbeats()
            except Exception as e:
                logger.error("Error in heartbeat monitor loop: %s", e)
            time.sleep(self.config.heartbeat_interval)
