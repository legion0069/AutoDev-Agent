"""
Tests for ParallelExecutor in AutoDev v3.3.
"""

import time
import pytest
from core.multi_agent.agent_registry import AgentDescriptor, AgentRole
from core.multi_agent.parallel_executor import ExecutionResult, ParallelExecutor
from core.multi_agent.resource_scheduler import ResourceScheduler
from core.multi_agent.work_queue import WorkItem


def dummy_runner(task: WorkItem, agent: AgentDescriptor):
    time.sleep(0.02)
    if "fail" in task.title:
        raise ValueError("Simulated task failure")
    return {"done": True, "by": agent.agent_id}


def test_parallel_batch_execution():
    executor = ParallelExecutor(max_workers=4)
    agent = AgentDescriptor(agent_id="worker_1", name="Worker 1", role=AgentRole.BACKEND_ENGINEER)

    tasks_batch = [
        (WorkItem(task_id=f"t_{i}", title=f"Task {i}"), agent, dummy_runner)
        for i in range(8)
    ]

    results = executor.execute_batch(tasks_batch)
    assert len(results) == 8
    assert all(r.success for r in results)
    assert executor.total_executed == 8
    assert executor.peak_concurrency >= 1
    executor.shutdown()


def test_deterministic_mode_execution():
    executor = ParallelExecutor(max_workers=4, deterministic_mode=True)
    agent = AgentDescriptor(agent_id="worker_1", name="Worker 1", role=AgentRole.BACKEND_ENGINEER)

    order = []

    def tracking_runner(task: WorkItem, ag: AgentDescriptor):
        order.append(task.task_id)
        return task.task_id

    tasks_batch = [
        (WorkItem(task_id=f"t_{i}", title=f"Task {i}"), agent, tracking_runner)
        for i in range(5)
    ]

    results = executor.execute_batch(tasks_batch)
    assert len(results) == 5
    assert order == [f"t_{i}" for i in range(5)]
    executor.shutdown()


def test_parallel_execution_with_resource_locks():
    scheduler = ResourceScheduler()
    executor = ParallelExecutor(max_workers=4)
    agent1 = AgentDescriptor(agent_id="worker_1", name="Worker 1", role=AgentRole.BACKEND_ENGINEER)
    agent2 = AgentDescriptor(agent_id="worker_2", name="Worker 2", role=AgentRole.FRONTEND_ENGINEER)

    task1 = WorkItem(task_id="t_res1", title="Task with res", resources_required=["common_file.py"])
    task2 = WorkItem(task_id="t_res2", title="Task with same res", resources_required=["common_file.py"])

    tasks = [
        (task1, agent1, dummy_runner),
        (task2, agent2, dummy_runner),
    ]

    results = executor.execute_batch(tasks, scheduler=scheduler)
    assert len(results) == 2
    assert all(r.success for r in results)
    # Both successfully acquired and released lock without deadlock
    assert scheduler.is_locked("common_file.py") is False
    executor.shutdown()


def test_parallel_execution_error_handling():
    executor = ParallelExecutor(max_workers=2)
    agent = AgentDescriptor(agent_id="worker_1", name="Worker 1", role=AgentRole.BACKEND_ENGINEER)

    tasks = [
        (WorkItem(task_id="t_ok", title="Normal task"), agent, dummy_runner),
        (WorkItem(task_id="t_err", title="Please fail task"), agent, dummy_runner),
    ]

    results = executor.execute_batch(tasks)
    assert len(results) == 2
    ok_res = next(r for r in results if r.task_id == "t_ok")
    err_res = next(r for r in results if r.task_id == "t_err")

    assert ok_res.success is True
    assert err_res.success is False
    assert "Simulated task failure" in err_res.error
    executor.shutdown()
