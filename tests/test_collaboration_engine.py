"""
Tests for CollaborationEngine workflow coordination and telemetry in AutoDev v3.3.
"""

import pytest
from core.multi_agent.agent_registry import AgentDescriptor, AgentRegistry, AgentRole
from core.multi_agent.collaboration_engine import CollaborationEngine
from core.multi_agent.parallel_executor import ParallelExecutor
from core.multi_agent.work_queue import TaskPriority, WorkItem, WorkQueue


def test_collaboration_engine_task_lifecycle():
    engine = CollaborationEngine(
        executor=ParallelExecutor(max_workers=2, deterministic_mode=True)
    )

    # Register engineers
    engine.registry.register_agent(
        AgentDescriptor(
            agent_id="dev_be",
            name="Backend Eng",
            role=AgentRole.BACKEND_ENGINEER,
            capabilities=["python"],
        )
    )
    engine.registry.register_agent(
        AgentDescriptor(
            agent_id="dev_qa",
            name="QA Eng",
            role=AgentRole.QA_ENGINEER,
            capabilities=["testing"],
        )
    )

    # Submit tasks with dependencies
    t1 = WorkItem(task_id="t_api", title="Implement API", required_role=AgentRole.BACKEND_ENGINEER)
    t2 = WorkItem(task_id="t_test", title="Write Tests", required_role=AgentRole.QA_ENGINEER, dependencies={"t_api"})

    engine.submit_task(t1)
    engine.submit_task(t2)

    assert engine.work_queue.size() == 2
    assert engine.work_queue.completed_count() == 0

    # Run all tasks
    results = engine.run_all_tasks()
    assert len(results) == 2
    assert engine.work_queue.completed_count() == 2
    assert engine.work_queue.is_finished() is True

    # Validate telemetry
    telemetry = engine.get_telemetry()
    assert telemetry.completed_tasks == 2
    assert telemetry.queue_length == 2
    assert telemetry.avg_execution_latency >= 0.0
    assert "dev_be" in telemetry.agent_utilization
    engine.shutdown()


def test_collaboration_graph_and_telemetry():
    engine = CollaborationEngine()
    engine.record_communication("agent_arch", "agent_be")
    engine.record_communication("agent_arch", "agent_be")
    engine.record_communication("agent_be", "agent_qa")

    telemetry = engine.get_telemetry()
    assert telemetry.collaboration_graph["agent_arch"]["agent_be"] == 2
    assert telemetry.collaboration_graph["agent_be"]["agent_qa"] == 1
    engine.shutdown()
