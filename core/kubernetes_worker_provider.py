"""
AutoDev Kubernetes Worker Provider (Phase 3 - Kubernetes-Native Worker Orchestration)
Provides abstraction over Kubernetes API for managing worker pools, Deployments,
and Pod lifecycles with strict isolation and fake client test doubles.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import copy
import uuid


@dataclass
class WorkerSecurityProfile:
    run_as_non_root: bool = True
    read_only_root_filesystem: bool = True
    allow_privilege_escalation: bool = False
    privileged: bool = False
    run_as_user: int = 10001
    run_as_group: int = 10001


@dataclass
class WorkerPoolSpec:
    name: str
    namespace: str = "autodev-system"
    image: str = "autodev/worker:v2.4.0"
    replicas: int = 1
    min_replicas: int = 1
    max_replicas: int = 10
    required_capabilities: List[str] = field(default_factory=lambda: ["python", "sandbox"])
    allowed_operation_types: List[str] = field(default_factory=lambda: ["file_edit", "shell_exec", "test_run"])
    resources_requests: Dict[str, str] = field(default_factory=lambda: {"cpu": "250m", "memory": "512Mi"})
    resources_limits: Dict[str, str] = field(default_factory=lambda: {"cpu": "1000m", "memory": "1Gi"})
    security_profile: WorkerSecurityProfile = field(default_factory=WorkerSecurityProfile)
    heartbeat_timeout_seconds: int = 30
    graceful_shutdown_seconds: int = 60
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)


@dataclass
class WorkerPodInfo:
    name: str
    namespace: str
    pool_name: str
    phase: str  # Pending, Running, Succeeded, Failed, Unknown
    ready: bool
    ip: Optional[str] = None
    node_name: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    labels: Dict[str, str] = field(default_factory=dict)
    draining: bool = False


@dataclass
class WorkerPoolStatus:
    replicas: int = 0
    ready_replicas: int = 0
    active_tasks: int = 0
    phase: str = "Pending"  # Pending, Scaling, Running, Degraded, Failed
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    last_scale_time: Optional[str] = None
    observed_generation: int = 0


class KubernetesClientInterface(ABC):
    """Abstract interface for interacting with Kubernetes API."""

    @abstractmethod
    def get_custom_resource(self, group: str, version: str, plural: str, name: str, namespace: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_custom_resources(self, group: str, version: str, plural: str, namespace: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def update_custom_resource_status(self, group: str, version: str, plural: str, name: str, namespace: str, status: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def get_deployment(self, name: str, namespace: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def create_deployment(self, deployment: Dict[str, Any], namespace: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def update_deployment(self, name: str, deployment: Dict[str, Any], namespace: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def scale_deployment(self, name: str, replicas: int, namespace: str) -> bool:
        pass

    @abstractmethod
    def delete_deployment(self, name: str, namespace: str) -> bool:
        pass

    @abstractmethod
    def list_pods(self, namespace: str, label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete_pod(self, name: str, namespace: str, grace_period_seconds: int = 30) -> bool:
        pass


class FakeKubernetesClient(KubernetesClientInterface):
    """
    In-memory mock implementation of Kubernetes API client for hermetic testing.
    Provides full CRD, Deployment, and Pod simulation with labels and status.
    """

    def __init__(self) -> None:
        self.custom_resources: Dict[str, Dict[str, Any]] = {}
        self.deployments: Dict[str, Dict[str, Any]] = {}
        self.pods: Dict[str, Dict[str, Any]] = {}
        self.deleted_resources: List[str] = []

    def _key(self, kind: str, name: str, namespace: str) -> str:
        return f"{namespace}/{kind}/{name}"

    def get_custom_resource(self, group: str, version: str, plural: str, name: str, namespace: str) -> Optional[Dict[str, Any]]:
        key = self._key(plural, name, namespace)
        return copy.deepcopy(self.custom_resources.get(key))

    def list_custom_resources(self, group: str, version: str, plural: str, namespace: str) -> List[Dict[str, Any]]:
        prefix = f"{namespace}/{plural}/"
        return [copy.deepcopy(v) for k, v in self.custom_resources.items() if k.startswith(prefix)]

    def create_custom_resource(self, group: str, version: str, plural: str, resource: Dict[str, Any], namespace: str) -> Dict[str, Any]:
        name = resource.get("metadata", {}).get("name", "unnamed")
        key = self._key(plural, name, namespace)
        self.custom_resources[key] = copy.deepcopy(resource)
        return copy.deepcopy(resource)

    def update_custom_resource_status(self, group: str, version: str, plural: str, name: str, namespace: str, status: Dict[str, Any]) -> bool:
        key = self._key(plural, name, namespace)
        if key not in self.custom_resources:
            return False
        self.custom_resources[key]["status"] = copy.deepcopy(status)
        return True

    def get_deployment(self, name: str, namespace: str) -> Optional[Dict[str, Any]]:
        key = self._key("deployment", name, namespace)
        return copy.deepcopy(self.deployments.get(key))

    def create_deployment(self, deployment: Dict[str, Any], namespace: str) -> Dict[str, Any]:
        name = deployment["metadata"]["name"]
        key = self._key("deployment", name, namespace)
        self.deployments[key] = copy.deepcopy(deployment)
        # Automatically create initial simulated pods
        replicas = deployment.get("spec", {}).get("replicas", 1)
        self._sync_pods(name, namespace, replicas, deployment)
        return copy.deepcopy(deployment)

    def update_deployment(self, name: str, deployment: Dict[str, Any], namespace: str) -> Dict[str, Any]:
        key = self._key("deployment", name, namespace)
        self.deployments[key] = copy.deepcopy(deployment)
        replicas = deployment.get("spec", {}).get("replicas", 1)
        self._sync_pods(name, namespace, replicas, deployment)
        return copy.deepcopy(deployment)

    def scale_deployment(self, name: str, replicas: int, namespace: str) -> bool:
        key = self._key("deployment", name, namespace)
        if key not in self.deployments:
            return False
        self.deployments[key]["spec"]["replicas"] = replicas
        self._sync_pods(name, namespace, replicas, self.deployments[key])
        return True

    def delete_deployment(self, name: str, namespace: str) -> bool:
        key = self._key("deployment", name, namespace)
        if key in self.deployments:
            del self.deployments[key]
            self.deleted_resources.append(key)
            # Delete corresponding pods
            pods_to_del = [
                pk for pk, p in self.pods.items()
                if p.get("metadata", {}).get("labels", {}).get("app.kubernetes.io/instance") == name
                or p.get("metadata", {}).get("name", "").startswith(f"{name}-")
            ]
            for pk in pods_to_del:
                del self.pods[pk]
            return True
        return False

    def list_pods(self, namespace: str, label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        prefix = f"{namespace}/pod/"
        results = [copy.deepcopy(v) for k, v in self.pods.items() if k.startswith(prefix)]
        if label_selector:
            # Simple k=v parsing
            pairs = [p.split("=") for p in label_selector.split(",") if "=" in p]
            filtered = []
            for pod in results:
                pod_labels = pod.get("metadata", {}).get("labels", {})
                if all(pod_labels.get(k.strip()) == v.strip() for k, v in pairs):
                    filtered.append(pod)
            return filtered
        return results

    def delete_pod(self, name: str, namespace: str, grace_period_seconds: int = 30) -> bool:
        key = self._key("pod", name, namespace)
        if key in self.pods:
            del self.pods[key]
            self.deleted_resources.append(key)
            return True
        return False

    def _sync_pods(self, deployment_name: str, namespace: str, target_replicas: int, deployment: Dict[str, Any]) -> None:
        prefix = f"{namespace}/pod/"
        existing_pods = [k for k, p in self.pods.items() if k.startswith(prefix) and p.get("metadata", {}).get("labels", {}).get("app.kubernetes.io/instance") == deployment_name]
        
        current_count = len(existing_pods)
        labels = deployment.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {}).copy()
        labels["app.kubernetes.io/instance"] = deployment_name

        if current_count < target_replicas:
            for _ in range(target_replicas - current_count):
                pod_name = f"{deployment_name}-{uuid.uuid4().hex[:6]}"
                pod_key = self._key("pod", pod_name, namespace)
                self.pods[pod_key] = {
                    "metadata": {
                        "name": pod_name,
                        "namespace": namespace,
                        "labels": labels,
                        "creationTimestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    "status": {
                        "phase": "Running",
                        "podIP": f"10.244.1.{len(self.pods)+1}",
                        "conditions": [{"type": "Ready", "status": "True"}],
                    }
                }
        elif current_count > target_replicas:
            to_remove = existing_pods[:(current_count - target_replicas)]
            for k in to_remove:
                del self.pods[k]


class KubernetesWorkerProvider:
    """
    Manages AutoDev worker deployments and pods using Kubernetes API.
    Enforces security profiles (non-root, read-only rootfs) and isolation.
    """

    def __init__(self, client: Optional[KubernetesClientInterface] = None) -> None:
        self.client = client or FakeKubernetesClient()

    def create_or_update_pool_deployment(self, spec: WorkerPoolSpec) -> Dict[str, Any]:
        """Create or update Kubernetes Deployment corresponding to WorkerPoolSpec."""
        labels = {
            "app.kubernetes.io/name": "autodev-worker",
            "app.kubernetes.io/instance": spec.name,
            "app.kubernetes.io/managed-by": "autodev-controller",
            "autodev.io/pool": spec.name,
        }
        labels.update(spec.labels)

        deployment_manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": f"autodev-worker-{spec.name}",
                "namespace": spec.namespace,
                "labels": labels,
                "annotations": spec.annotations,
            },
            "spec": {
                "replicas": spec.replicas,
                "selector": {
                    "matchLabels": {
                        "app.kubernetes.io/name": "autodev-worker",
                        "autodev.io/pool": spec.name,
                    }
                },
                "template": {
                    "metadata": {
                        "labels": labels,
                    },
                    "spec": {
                        "serviceAccountName": "autodev-worker",
                        "securityContext": {
                            "runAsNonRoot": spec.security_profile.run_as_non_root,
                            "runAsUser": spec.security_profile.run_as_user,
                            "runAsGroup": spec.security_profile.run_as_group,
                        },
                        "containers": [
                            {
                                "name": "worker",
                                "image": spec.image,
                                "resources": {
                                    "requests": spec.resources_requests,
                                    "limits": spec.resources_limits,
                                },
                                "securityContext": {
                                    "readOnlyRootFilesystem": spec.security_profile.read_only_root_filesystem,
                                    "allowPrivilegeEscalation": spec.security_profile.allow_privilege_escalation,
                                    "privileged": spec.security_profile.privileged,
                                },
                                "env": [
                                    {"name": "AUTODEV_POOL_NAME", "value": spec.name},
                                    {"name": "AUTODEV_CAPABILITIES", "value": ",".join(spec.required_capabilities)},
                                ],
                            }
                        ],
                        "terminationGracePeriodSeconds": spec.graceful_shutdown_seconds,
                    }
                }
            }
        }

        existing = self.client.get_deployment(f"autodev-worker-{spec.name}", spec.namespace)
        if existing:
            return self.client.update_deployment(f"autodev-worker-{spec.name}", deployment_manifest, spec.namespace)
        return self.client.create_deployment(deployment_manifest, spec.namespace)

    def scale_pool(self, pool_name: str, namespace: str, desired_replicas: int) -> bool:
        deployment_name = f"autodev-worker-{pool_name}"
        return self.client.scale_deployment(deployment_name, desired_replicas, namespace)

    def list_pool_workers(self, pool_name: str, namespace: str) -> List[WorkerPodInfo]:
        label_selector = f"autodev.io/pool={pool_name}"
        pods = self.client.list_pods(namespace=namespace, label_selector=label_selector)
        worker_pods: List[WorkerPodInfo] = []

        for p in pods:
            meta = p.get("metadata", {})
            status = p.get("status", {})
            conditions = status.get("conditions", [])
            is_ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conditions)

            worker_pods.append(
                WorkerPodInfo(
                    name=meta.get("name", "unknown"),
                    namespace=meta.get("namespace", namespace),
                    pool_name=pool_name,
                    phase=status.get("phase", "Unknown"),
                    ready=is_ready,
                    ip=status.get("podIP"),
                    node_name=status.get("nodeName"),
                    created_at=meta.get("creationTimestamp", datetime.now(timezone.utc).isoformat()),
                    labels=meta.get("labels", {}),
                )
            )
        return worker_pods
