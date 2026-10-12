"""
AutoDev Kubernetes Worker Controller (Phase 3 - Kubernetes-Native Worker Orchestration)
Continuous reconciliation loop managing AutoDevWorkerPool custom resources,
worker pool Deployments, autoscaling policies, and lifecycle telemetry.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

from core.kubernetes_worker_provider import (
    KubernetesClientInterface,
    KubernetesWorkerProvider,
    FakeKubernetesClient,
    WorkerPoolSpec,
    WorkerPoolStatus,
    WorkerSecurityProfile,
)
from core.worker_scaling_policy import WorkerScalingPolicy, ScalingDecision, ScaleType

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationResult:
    pool_name: str
    namespace: str
    action_taken: str
    current_replicas: int
    desired_replicas: int
    ready_replicas: int
    scaling_decision: Optional[ScalingDecision] = None
    status: str = "Success"
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class KubernetesWorkerController:
    """
    Operator controller reconciling AutoDevWorkerPool CRDs with underlying
    Kubernetes Deployments, Pods, and scaling policies.
    """

    def __init__(
        self,
        client: Optional[KubernetesClientInterface] = None,
        provider: Optional[KubernetesWorkerProvider] = None,
        default_namespace: str = "autodev-system",
    ) -> None:
        self.client = client or FakeKubernetesClient()
        self.provider = provider or KubernetesWorkerProvider(self.client)
        self.default_namespace = default_namespace
        self.scaling_policies: Dict[str, WorkerScalingPolicy] = {}
        self.reconciliation_history: List[ReconciliationResult] = []

    def get_or_create_scaling_policy(self, spec: WorkerPoolSpec, policy_cfg: Dict[str, Any]) -> WorkerScalingPolicy:
        pool_key = f"{spec.namespace}/{spec.name}"
        if pool_key not in self.scaling_policies:
            self.scaling_policies[pool_key] = WorkerScalingPolicy(
                min_replicas=spec.min_replicas,
                max_replicas=spec.max_replicas,
                queue_depth_threshold=policy_cfg.get("queueDepthThreshold", 5),
                busy_ratio_scale_up_threshold=policy_cfg.get("busyRatioScaleUpThreshold", 0.8),
                busy_ratio_scale_down_threshold=policy_cfg.get("busyRatioScaleDownThreshold", 0.2),
                cooldown_seconds=policy_cfg.get("cooldownSeconds", 30.0),
                stabilization_window_seconds=policy_cfg.get("stabilizationWindowSeconds", 60.0),
                max_scale_change_per_interval=policy_cfg.get("maxScaleChangePerInterval", 5),
            )
        return self.scaling_policies[pool_key]

    def parse_worker_pool_crd(self, crd: Dict[str, Any]) -> WorkerPoolSpec:
        """Extract and validate WorkerPoolSpec from a CRD dictionary."""
        meta = crd.get("metadata", {})
        spec = crd.get("spec", {})
        name = meta.get("name")
        namespace = meta.get("namespace", self.default_namespace)

        if not name:
            raise ValueError("WorkerPool CRD missing metadata.name")

        sec_dict = spec.get("securityProfile", {})
        sec_profile = WorkerSecurityProfile(
            run_as_non_root=sec_dict.get("runAsNonRoot", True),
            read_only_root_filesystem=sec_dict.get("readOnlyRootFilesystem", True),
            allow_privilege_escalation=sec_dict.get("allowPrivilegeEscalation", False),
            privileged=sec_dict.get("privileged", False),
        )

        res_dict = spec.get("resources", {})
        reqs = res_dict.get("requests", {"cpu": "250m", "memory": "512Mi"})
        limits = res_dict.get("limits", {"cpu": "1000m", "memory": "1Gi"})

        return WorkerPoolSpec(
            name=name,
            namespace=namespace,
            image=spec.get("image", "autodev/worker:v2.4.0"),
            replicas=spec.get("replicas", 1),
            min_replicas=spec.get("minReplicas", 1),
            max_replicas=spec.get("maxReplicas", 10),
            required_capabilities=spec.get("requiredCapabilities", ["python", "sandbox"]),
            allowed_operation_types=spec.get("allowedOperationTypes", ["file_edit", "shell_exec", "test_run"]),
            resources_requests=reqs,
            resources_limits=limits,
            security_profile=sec_profile,
            heartbeat_timeout_seconds=spec.get("heartbeatTimeoutSeconds", 30),
            graceful_shutdown_seconds=spec.get("gracefulShutdownSeconds", 60),
            labels=meta.get("labels", {}),
            annotations=meta.get("annotations", {}),
        )

    def reconcile_pool(
        self,
        pool_name: str,
        namespace: Optional[str] = None,
        queue_depth: int = 0,
        busy_workers: int = 0,
        now: Optional[float] = None,
    ) -> ReconciliationResult:
        """
        Reconcile a single AutoDevWorkerPool resource with its deployment and pods.
        """
        ns = namespace or self.default_namespace
        crd = self.client.get_custom_resource("autodev.io", "v1alpha1", "autodevworkerpools", pool_name, ns)

        if not crd:
            res = ReconciliationResult(
                pool_name=pool_name,
                namespace=ns,
                action_taken="none",
                current_replicas=0,
                desired_replicas=0,
                ready_replicas=0,
                status="Error",
                error=f"AutoDevWorkerPool {ns}/{pool_name} not found",
            )
            self.reconciliation_history.append(res)
            return res

        try:
            spec = self.parse_worker_pool_crd(crd)
            scaling_cfg = crd.get("spec", {}).get("scalingPolicy", {})
            autoscaling_enabled = scaling_cfg.get("enabled", True)

            # Ensure deployment exists
            self.provider.create_or_update_pool_deployment(spec)

            # Query current workers
            workers = self.provider.list_pool_workers(spec.name, spec.namespace)
            current_replicas = len(workers)
            ready_replicas = sum(1 for w in workers if w.ready and not w.draining)

            desired_replicas = spec.replicas
            decision: Optional[ScalingDecision] = None

            if autoscaling_enabled:
                policy = self.get_or_create_scaling_policy(spec, scaling_cfg)
                decision = policy.evaluate(
                    current_replicas=current_replicas,
                    ready_replicas=ready_replicas,
                    busy_replicas=busy_workers,
                    queue_depth=queue_depth,
                    now=now,
                )
                if decision.changed:
                    desired_replicas = decision.desired_replicas

            action_taken = "maintained"
            if desired_replicas != current_replicas:
                self.provider.scale_pool(spec.name, spec.namespace, desired_replicas)
                action_taken = f"scaled_{decision.scale_type.value if decision else 'manual'}"

            # Update CRD Status
            phase = "Running"
            if desired_replicas != current_replicas:
                phase = "Scaling"
            elif ready_replicas < desired_replicas:
                phase = "Degraded" if ready_replicas == 0 else "Scaling"

            status_payload = {
                "replicas": current_replicas,
                "readyReplicas": ready_replicas,
                "activeTasks": busy_workers,
                "labelSelector": f"autodev.io/pool={spec.name}",
                "phase": phase,
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True" if ready_replicas >= spec.min_replicas else "False",
                        "reason": "MinimumReplicasSatisfied" if ready_replicas >= spec.min_replicas else "InsufficientReadyReplicas",
                        "lastTransitionTime": datetime.now(timezone.utc).isoformat(),
                    }
                ],
                "lastScaleTime": decision.timestamp if decision and decision.changed else None,
            }

            self.client.update_custom_resource_status(
                "autodev.io", "v1alpha1", "autodevworkerpools", spec.name, spec.namespace, status_payload
            )

            result = ReconciliationResult(
                pool_name=spec.name,
                namespace=spec.namespace,
                action_taken=action_taken,
                current_replicas=current_replicas,
                desired_replicas=desired_replicas,
                ready_replicas=ready_replicas,
                scaling_decision=decision,
                status="Success",
            )
            self.reconciliation_history.append(result)
            return result

        except Exception as e:
            logger.exception("Error reconciling worker pool %s/%s: %s", ns, pool_name, e)
            res = ReconciliationResult(
                pool_name=pool_name,
                namespace=ns,
                action_taken="failed",
                current_replicas=0,
                desired_replicas=0,
                ready_replicas=0,
                status="Failed",
                error=str(e),
            )
            self.reconciliation_history.append(res)
            return res

    def reconcile_all(
        self,
        namespace: Optional[str] = None,
        queue_metrics: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> List[ReconciliationResult]:
        """
        Reconcile all AutoDevWorkerPool resources found in namespace.
        """
        ns = namespace or self.default_namespace
        pools = self.client.list_custom_resources("autodev.io", "v1alpha1", "autodevworkerpools", ns)
        results = []
        metrics = queue_metrics or {}

        for pool in pools:
            name = pool.get("metadata", {}).get("name")
            if name:
                m = metrics.get(name, {})
                q_depth = m.get("queue_depth", 0)
                busy = m.get("busy_workers", 0)
                res = self.reconcile_pool(name, ns, queue_depth=q_depth, busy_workers=busy)
                results.append(res)

        return results
