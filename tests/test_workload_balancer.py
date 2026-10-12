"""
Tests for AutoDev Workload Balancer (v2.8)
=========================================
Verifies metric computation, imbalance detection, work-stealing, and load equalization.
"""

import pytest
from core.collaboration.collaboration_models import TaskAssignment, TaskPriority
from core.collaboration.task_allocator import TaskAllocator
from core.collaboration.workload_balancer import WorkloadBalancer


def test_workload_metrics_and_imbalance():
    allocator = TaskAllocator()
    balancer = WorkloadBalancer(allocator=allocator)

    # Overload BackendAgent with 3 heavy tasks (12 hours)
    tasks = [
        TaskAssignment(task_id="t1", title="Backend DB 1", estimated_hours=4.0),
        TaskAssignment(task_id="t2", title="Backend DB 2", estimated_hours=4.0),
        TaskAssignment(task_id="t3", title="Backend DB 3", estimated_hours=4.0),
    ]
    for t in tasks:
        allocator.submit_task(t)
        allocator.allocate_task(t.task_id)

    metrics = balancer.compute_workload_metrics()
    assert metrics["total_workload_hours"] == 12.0
    assert metrics["max_workload_hours"] == 12.0
    assert metrics["imbalance_score"] > 0.0


def test_workload_balancing_and_task_reassignment():
    allocator = TaskAllocator()
    balancer = WorkloadBalancer(allocator=allocator)

    # Assign 5 tasks (15 hours) to BackendAgent
    for i in range(5):
        t = TaskAssignment(task_id=f"t_heavy_{i}", title=f"Task {i}", estimated_hours=3.0)
        allocator.submit_task(t)
        allocator.allocate_task(t.task_id)

    # Balance workload with low threshold
    reassignments = balancer.balance_workload(threshold_hours=2.0)
    assert len(reassignments) > 0

    # Ensure tasks were stolen by other agents
    cap_back = allocator.get_capacity("BackendAgent")
    assert cap_back.current_workload_hours < 15.0
