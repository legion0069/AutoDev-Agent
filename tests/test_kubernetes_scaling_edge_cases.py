"""
Kubernetes Worker Scaling & Provider Edge Case Tests (Phase 8.2)
Exercises extreme queue bursts, fractional load boundaries, stabilization windows,
and fake client pod operations.
"""

import time
import pytest

from core.worker_scaling_policy import WorkerScalingPolicy, ScaleType, ScalingDecision
from core.kubernetes_worker_provider import (
    WorkerSecurityProfile,
    WorkerPoolSpec,
    WorkerPodInfo,
    FakeKubernetesClient,
    KubernetesWorkerProvider,
)
from core.kubernetes_worker_controller import KubernetesWorkerController


class TestKubernetesScalingEdgeCases:
    def test_extreme_queue_burst_capped_by_max_scale_interval(self):
        policy = WorkerScalingPolicy(
            min_replicas=1,
            max_replicas=50,
            max_scale_change_per_interval=5,
            cooldown_seconds=0,
        )
        # 10,000 tasks queued -> should scale up by at most max_scale_change_per_interval (5)
        decision = policy.evaluate(current_replicas=2, ready_replicas=2, busy_replicas=2, queue_depth=10000)
        assert decision.scale_type == ScaleType.SCALE_UP
        assert decision.desired_replicas == 7  # 2 + 5
        assert decision.delta == 5

    def test_zero_busy_workers_empty_queue_scales_down_within_interval(self):
        policy = WorkerScalingPolicy(
            min_replicas=2,
            max_replicas=20,
            max_scale_change_per_interval=3,
            cooldown_seconds=0,
        )
        # Fleet of 10 idle workers
        decision = policy.evaluate(current_replicas=10, ready_replicas=10, busy_replicas=0, queue_depth=0)
        assert decision.scale_type == ScaleType.SCALE_DOWN
        assert decision.desired_replicas == 7  # 10 - 3
        assert decision.delta == -3

    def test_busy_ratio_boundary_values(self):
        policy = WorkerScalingPolicy(
            min_replicas=1,
            max_replicas=10,
            busy_ratio_scale_up_threshold=0.8,
            busy_ratio_scale_down_threshold=0.2,
            cooldown_seconds=0,
        )
        # Exact 0.8 busy ratio with queue > 0 triggers scale up
        d_up = policy.evaluate(current_replicas=5, ready_replicas=5, busy_replicas=4, queue_depth=1)
        assert d_up.scale_type == ScaleType.SCALE_UP

        # Exact 0.2 busy ratio with queue == 0 triggers scale down
        d_down = policy.evaluate(current_replicas=5, ready_replicas=5, busy_replicas=1, queue_depth=0)
        assert d_down.scale_type == ScaleType.SCALE_DOWN

    def test_fake_client_deployment_scaling_and_deletion(self):
        client = FakeKubernetesClient()
        dep = {
            "metadata": {"name": "worker-pool-a"},
            "spec": {"replicas": 3, "template": {"metadata": {"labels": {"app": "worker"}}}},
        }
        client.create_deployment(dep, "default")
        assert len(client.list_pods("default")) == 3

        # Scale up
        client.scale_deployment("worker-pool-a", 6, "default")
        assert len(client.list_pods("default")) == 6

        # Scale down
        client.scale_deployment("worker-pool-a", 2, "default")
        assert len(client.list_pods("default")) == 2

        # Delete
        client.delete_deployment("worker-pool-a", "default")
        assert len(client.list_pods("default")) == 0

    def test_fake_client_pod_deletion(self):
        client = FakeKubernetesClient()
        dep = {
            "metadata": {"name": "single-worker"},
            "spec": {"replicas": 1, "template": {"metadata": {"labels": {"app": "worker"}}}},
        }
        client.create_deployment(dep, "autodev-system")
        pods = client.list_pods("autodev-system")
        assert len(pods) == 1
        pod_name = pods[0]["metadata"]["name"]

        deleted = client.delete_pod(pod_name, "autodev-system")
        assert deleted is True
        assert len(client.list_pods("autodev-system")) == 0
