"""
node_registry.py - Live Node Registry & Membership Manager for AutoDev Cluster (v2.9)

Maintains the authoritative registry of cluster nodes (masters, workers, observers, backups),
their live capabilities, operational status, load telemetry, historical performance,
and membership lifecycle.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set

from core.cluster.cluster_state import NodeInfo, NodeRole, NodeStatus

logger = logging.getLogger("AutoDev.Cluster.Registry")


class NodeRegistry:
    """
    Thread-safe live registry for all nodes in the AutoDev distributed cluster.
    Provides indexing by role, capabilities, health status, and tracks task execution history.
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, NodeInfo] = {}
        self._task_history: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.RLock()
        self._created_at = time.time()

    def register_node(self, node: NodeInfo) -> bool:
        """
        Registers a new node or updates existing registration.
        """
        with self._lock:
            now = time.time()
            if node.node_id in self._nodes:
                existing = self._nodes[node.node_id]
                existing.hostname = node.hostname
                existing.ip = node.ip
                existing.port = node.port
                existing.role = node.role
                existing.status = node.status
                existing.capabilities = list(set(node.capabilities))
                existing.max_tasks = node.max_tasks
                existing.last_heartbeat = now
                existing.metadata.update(node.metadata)
                logger.debug("Updated registration for node %s (%s)", node.node_id, node.role.value)
                return True
            else:
                new_node = copy.deepcopy(node)
                new_node.registered_at = now
                new_node.last_heartbeat = now
                self._nodes[node.node_id] = new_node
                if node.node_id not in self._task_history:
                    self._task_history[node.node_id] = []
                logger.info("Registered new cluster node %s (Role: %s, Caps: %s)", node.node_id, node.role.value, node.capabilities)
                return True

    def deregister_node(self, node_id: str) -> bool:
        """
        Deregisters a node from the cluster.
        """
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].status = NodeStatus.DEREGISTERED
                logger.info("Deregistered node %s from cluster registry", node_id)
                return True
            return False

    def remove_node(self, node_id: str) -> bool:
        """
        Completely removes node from registry.
        """
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                self._task_history.pop(node_id, None)
                logger.info("Removed node %s from cluster registry", node_id)
                return True
            return False

    def update_node_status(self, node_id: str, status: NodeStatus) -> bool:
        """
        Updates node operational status.
        """
        with self._lock:
            node = self._nodes.get(node_id)
            if node:
                old_status = node.status
                node.status = status
                if old_status != status:
                    logger.info("Node %s status transition: %s -> %s", node_id, old_status.value, status.value)
                return True
            return False

    def record_heartbeat(
        self,
        node_id: str,
        cpu_utilization: Optional[float] = None,
        memory_utilization: Optional[float] = None,
        active_tasks: Optional[int] = None,
        latency_ms: Optional[float] = None,
        health_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Records a heartbeat and updates runtime metrics for a registered node.
        """
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return False
            now = time.time()
            node.last_heartbeat = now
            node.uptime = now - node.registered_at
            if cpu_utilization is not None:
                node.cpu_utilization = max(0.0, min(100.0, cpu_utilization))
            if memory_utilization is not None:
                node.memory_utilization = max(0.0, min(100.0, memory_utilization))
            if active_tasks is not None:
                node.active_tasks = max(0, active_tasks)
            if latency_ms is not None:
                node.latency_ms = max(0.0, latency_ms)
            if health_score is not None:
                node.health_score = max(0.0, min(100.0, health_score))
            if metadata:
                node.metadata.update(metadata)
            return True

    def record_task_completion(self, node_id: str, task_id: str, success: bool, duration: float = 0.0) -> None:
        """
        Updates task success/failure counters and appends to historical log.
        """
        with self._lock:
            node = self._nodes.get(node_id)
            if node:
                if success:
                    node.total_tasks_completed += 1
                else:
                    node.total_tasks_failed += 1
            if node_id in self._task_history:
                self._task_history[node_id].append({
                    "task_id": task_id,
                    "success": success,
                    "duration": duration,
                    "timestamp": time.time(),
                })
                # Cap historical task log
                if len(self._task_history[node_id]) > 500:
                    self._task_history[node_id] = self._task_history[node_id][-500:]

    def get_node(self, node_id: str) -> Optional[NodeInfo]:
        """
        Retrieves a copy of node metadata.
        """
        with self._lock:
            node = self._nodes.get(node_id)
            return copy.deepcopy(node) if node else None

    def get_all_nodes(self) -> List[NodeInfo]:
        """
        Returns all registered nodes.
        """
        with self._lock:
            return [copy.deepcopy(n) for n in self._nodes.values()]

    def get_nodes_by_role(self, role: NodeRole) -> List[NodeInfo]:
        """
        Filters nodes by role.
        """
        with self._lock:
            return [copy.deepcopy(n) for n in self._nodes.values() if n.role == role]

    def get_nodes_by_capability(self, capability: str) -> List[NodeInfo]:
        """
        Filters active worker nodes by required capability.
        """
        with self._lock:
            return [
                copy.deepcopy(n)
                for n in self._nodes.values()
                if n.role == NodeRole.WORKER
                and n.status in (NodeStatus.HEALTHY, NodeStatus.DEGRADED)
                and (capability in n.capabilities or "general" in n.capabilities)
            ]

    def get_healthy_workers(self) -> List[NodeInfo]:
        """
        Returns all healthy worker nodes ready to accept tasks.
        """
        with self._lock:
            return [
                copy.deepcopy(n)
                for n in self._nodes.values()
                if n.role == NodeRole.WORKER
                and n.status in (NodeStatus.HEALTHY, NodeStatus.DEGRADED)
                and n.active_tasks < n.max_tasks
            ]

    def get_node_count(self) -> int:
        """
        Returns total active registered nodes.
        """
        with self._lock:
            return len([n for n in self._nodes.values() if n.status != NodeStatus.DEREGISTERED])

    def get_task_history(self, node_id: str) -> List[Dict[str, Any]]:
        """
        Returns task execution history for a node.
        """
        with self._lock:
            return list(self._task_history.get(node_id, []))

    def export_state(self) -> Dict[str, Any]:
        """
        Exports serializable dictionary of registry state.
        """
        with self._lock:
            return {
                "nodes": {k: v.to_dict() for k, v in self._nodes.items()},
                "task_history": copy.deepcopy(self._task_history),
            }

    def import_state(self, data: Dict[str, Any]) -> None:
        """
        Imports registry state from snapshot.
        """
        with self._lock:
            self._nodes.clear()
            self._task_history.clear()
            for k, v in data.get("nodes", {}).items():
                self._nodes[k] = NodeInfo.from_dict(v)
            for k, v in data.get("task_history", {}).items():
                self._task_history[k] = list(v)
