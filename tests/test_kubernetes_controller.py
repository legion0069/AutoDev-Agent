"""
Unit and Integration Tests for Kubernetes Worker Controller & Autoscaling (Phase 3 & Phase 8.2)
"""

import time
import pytest

from core.worker_scaling_policy import WorkerScalingPolicy, ScaleType, ScalingDecision
from core.kubernetes_worker_provider import (
    WorkerSecurityProfile,
    WorkerPoolSpec,
    WorkerPodInfo,
    WorkerPoolStatus,
    FakeKubernetesClient,
    KubernetesWorkerProvider,
)
from core.kubernetes_worker_controller import (
    KubernetesWorkerController,
    ReconciliationResult,
)


class TestWorkerScalingPolicy:
    def test_scaling_policy_initialization_validation(self):
        with pytest.raises(ValueError):
            WorkerScalingPolicy(min_replicas=-1)
        with pytest.raises(ValueError):
            WorkerScalingPolicy(min_replicas=10, max_replicas=2)
        with pytest.raises(ValueError):
            WorkerScalingPolicy(busy_ratio_scale_up_threshold=0.2, busy_ratio_scale_down_threshold=0.8)

    def test_scaling_policy_scale_up_on_queue_depth(self):
        policy = WorkerScalingPolicy(min_replicas=1, max_replicas=10, queue_depth_threshold=5, cooldown_seconds=0)
        # Fleet of 2 workers, 15 queued tasks -> should scale up
        decision = policy.evaluate(current_replicas=2, ready_replicas=2, busy_replicas=2, queue_depth=15)
        assert decision.scale_type == ScaleType.SCALE_UP
        assert decision.desired_replicas > 2
        assert decision.delta > 0
        assert decision.changed is True

    def test_scaling_policy_scale_down_on_idle(self):
        policy = WorkerScalingPolicy(min_replicas=1, max_replicas=10, busy_ratio_scale_down_threshold=0.3, cooldown_seconds=0)
        # Fleet of 6 workers, only 1 busy, queue depth 0 -> should scale down
        decision = policy.evaluate(current_replicas=6, ready_replicas=6, busy_replicas=1, queue_depth=0)
        assert decision.scale_type == ScaleType.SCALE_DOWN
        assert decision.desired_replicas < 6

    def test_scaling_policy_respects_cooldown(self):
        policy = WorkerScalingPolicy(min_replicas=1, max_replicas=10, cooldown_seconds=30.0)
        t0 = 1000.0
        # Trigger first scale
        d1 = policy.evaluate(current_replicas=1, ready_replicas=1, busy_replicas=1, queue_depth=10, now=t0)
        assert d1.changed is True

        # Second evaluation 5 seconds later should be blocked by cooldown
        d2 = policy.evaluate(current_replicas=d1.desired_replicas, ready_replicas=d1.desired_replicas, busy_replicas=d1.desired_replicas, queue_depth=20, now=t0 + 5.0)
        assert d2.scale_type == ScaleType.MAINTAIN
        assert "Cooldown active" in d2.reason

        # After cooldown passes (35s later)
        d3 = policy.evaluate(current_replicas=d1.desired_replicas, ready_replicas=d1.desired_replicas, busy_replicas=d1.desired_replicas, queue_depth=20, now=t0 + 35.0)
        assert d3.scale_type == ScaleType.SCALE_UP

    def test_scaling_policy_hard_caps(self):
        policy = WorkerScalingPolicy(min_replicas=2, max_replicas=5, cooldown_seconds=0)
        # Below min replicas
        d_under = policy.evaluate(current_replicas=0, ready_replicas=0, busy_replicas=0, queue_depth=0)
        assert d_under.desired_replicas == 2

        # Above max replicas
        d_over = policy.evaluate(current_replicas=10, ready_replicas=10, busy_replicas=10, queue_depth=100)
        assert d_over.desired_replicas == 5

    def test_scaling_policy_to_dict_export(self):
        policy = WorkerScalingPolicy(min_replicas=3, max_replicas=12)
        d = policy.to_dict()
        assert d["min_replicas"] == 3
        assert d["max_replicas"] == 12


class TestKubernetesWorkerController:
    def test_reconcile_creates_deployment_and_pods(self):
        client = FakeKubernetesClient()
        provider = KubernetesWorkerProvider(client)
        controller = KubernetesWorkerController(client, provider)

        # Create WorkerPool CRD
        crd_dict = {
            "apiVersion": "autodev.io/v1alpha1",
            "kind": "AutoDevWorkerPool",
            "metadata": {"name": "test-pool", "namespace": "autodev-system"},
            "spec": {
                "replicas": 3,
                "minReplicas": 1,
                "maxReplicas": 5,
                "image": "autodev/worker:v2.4.0",
                "scalingPolicy": {"enabled": False},
            }
        }
        client.create_custom_resource("autodev.io", "v1alpha1", "autodevworkerpools", crd_dict, "autodev-system")

        result = controller.reconcile_pool("test-pool", "autodev-system")
        assert result.status == "Success"

        # Check deployment created in fake client
        dep = client.get_deployment("autodev-worker-test-pool", "autodev-system")
        assert dep is not None
        assert dep["spec"]["replicas"] == 3

        # Check pods created
        pods = client.list_pods("autodev-system", label_selector="autodev.io/pool=test-pool")
        assert len(pods) == 3

    def test_reconcile_autoscales_on_queue_load(self):
        client = FakeKubernetesClient()
        provider = KubernetesWorkerProvider(client)
        controller = KubernetesWorkerController(client, provider)

        crd_dict = {
            "apiVersion": "autodev.io/v1alpha1",
            "kind": "AutoDevWorkerPool",
            "metadata": {"name": "cpu-pool", "namespace": "autodev-system"},
            "spec": {
                "replicas": 2,
                "minReplicas": 1,
                "maxReplicas": 8,
                "image": "autodev/worker:v2.4.0",
                "scalingPolicy": {
                    "enabled": True,
                    "queueDepthThreshold": 4,
                    "cooldownSeconds": 0,
                },
            }
        }
        client.create_custom_resource("autodev.io", "v1alpha1", "autodevworkerpools", crd_dict, "autodev-system")

        # Initial reconciliation
        controller.reconcile_pool("cpu-pool", "autodev-system")

        # Now simulate high queue depth (16 tasks queued, 2 busy workers)
        res_scale = controller.reconcile_pool("cpu-pool", "autodev-system", queue_depth=16, busy_workers=2)
        assert res_scale.action_taken.startswith("scaled_")
        assert res_scale.desired_replicas > 2

        # Check updated status on CRD
        updated_crd = client.get_custom_resource("autodev.io", "v1alpha1", "autodevworkerpools", "cpu-pool", "autodev-system")
        assert updated_crd["status"]["phase"] in ("Running", "Scaling")

    def test_reconcile_missing_pool_returns_error(self):
        client = FakeKubernetesClient()
        controller = KubernetesWorkerController(client)
        res = controller.reconcile_pool("nonexistent-pool", "autodev-system")
        assert res.status == "Error"
        assert "not found" in res.error

    def test_reconcile_all_multiple_pools(self):
        client = FakeKubernetesClient()
        controller = KubernetesWorkerController(client)

        for name in ["pool-a", "pool-b"]:
            crd = {
                "apiVersion": "autodev.io/v1alpha1",
                "kind": "AutoDevWorkerPool",
                "metadata": {"name": name, "namespace": "autodev-system"},
                "spec": {"replicas": 1, "image": "autodev/worker:v2.4.0", "scalingPolicy": {"enabled": False}},
            }
            client.create_custom_resource("autodev.io", "v1alpha1", "autodevworkerpools", crd, "autodev-system")

        results = controller.reconcile_all("autodev-system")
        assert len(results) == 2
        assert all(r.status == "Success" for r in results)

    def test_security_profile_enforcement(self):
        client = FakeKubernetesClient()
        provider = KubernetesWorkerProvider(client)

        spec = WorkerPoolSpec(
            name="secure-pool",
            namespace="autodev-system",
            security_profile=WorkerSecurityProfile(
                run_as_non_root=True,
                read_only_root_filesystem=True,
                allow_privilege_escalation=False,
                privileged=False,
            )
        )
        dep = provider.create_or_update_pool_deployment(spec)
        pod_spec = dep["spec"]["template"]["spec"]
        assert pod_spec["securityContext"]["runAsNonRoot"] is True
        container_sec = pod_spec["containers"][0]["securityContext"]
        assert container_sec["readOnlyRootFilesystem"] is True
        assert container_sec["allowPrivilegeEscalation"] is False
        assert container_sec["privileged"] is False
