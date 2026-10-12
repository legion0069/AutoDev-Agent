"""
Tests for distributed multi-stage DAG task execution in AutoDev v3.3.
"""

import pytest
from core.multi_agent.agent_registry import AgentDescriptor, AgentRole
from core.multi_agent.collaboration_engine import CollaborationEngine
from core.multi_agent.work_queue import WorkItem, WorkQueue


def test_topological_dag_task_execution():
    queue = WorkQueue()
    # Task Graph:
    # A (1.0) -> B (2.0) -> D (1.0)
    # A (1.0) -> C (0.5) -> D (1.0)
    queue.enqueue(WorkItem(task_id="A", title="Task A", estimated_duration=1.0))
    queue.enqueue(WorkItem(task_id="B", title="Task B", dependencies={"A"}, estimated_duration=2.0))
    queue.enqueue(WorkItem(task_id="C", title="Task C", dependencies={"A"}, estimated_duration=0.5))
    queue.enqueue(WorkItem(task_id="D", title="Task D", dependencies={"B", "C"}, estimated_duration=1.0))

    crit_path = queue.get_critical_path()
    # Longest path by duration: A (1.0) + B (2.0) + D (1.0) = 4.0
    assert crit_path == ["A", "B", "D"]

    # Initial ready: only A
    ready_1 = queue.get_ready_tasks()
    assert [t.task_id for t in ready_1] == ["A"]

    # Mark A completed
    queue.mark_completed("A")
    ready_2 = queue.get_ready_tasks()
    assert {t.task_id for t in ready_2} == {"B", "C"}

    # Mark B completed (C not completed yet) -> D is NOT ready yet
    queue.mark_completed("B")
    ready_3 = queue.get_ready_tasks()
    assert [t.task_id for t in ready_3] == ["C"]

    # Mark C completed -> D is now ready
    queue.mark_completed("C")
    ready_4 = queue.get_ready_tasks()
    assert [t.task_id for t in ready_4] == ["D"]

    queue.mark_completed("D")
    assert queue.is_finished() is True


def test_distributed_execution_with_collaboration_engine():
    engine = CollaborationEngine()
    engine.registry.register_agent(
        AgentDescriptor("ag_1", "Agent 1", AgentRole.BACKEND_ENGINEER, max_workload=2)
    )
    engine.registry.register_agent(
        AgentDescriptor("ag_2", "Agent 2", AgentRole.FRONTEND_ENGINEER, max_workload=2)
    )

    t1 = WorkItem("step_1", "Backend schema", required_role=AgentRole.BACKEND_ENGINEER)
    t2 = WorkItem("step_2", "Frontend UI", dependencies={"step_1"}, required_role=AgentRole.FRONTEND_ENGINEER)

    engine.submit_task(t1)
    engine.submit_task(t2)

    results = engine.run_all_tasks()
    assert len(results) == 2
    assert results[0].task_id == "step_1"
    assert results[1].task_id == "step_2"
    assert engine.work_queue.completed_count() == 2
    engine.shutdown()
