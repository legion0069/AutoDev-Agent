"""
Tests for AgentRegistry and AgentDescriptor in AutoDev v3.3.
"""

import time
import pytest
from core.multi_agent.agent_registry import (
    AgentDescriptor,
    AgentRegistry,
    AgentRole,
    AgentStatus,
)


def test_agent_descriptor_initialization():
    agent = AgentDescriptor(
        agent_id="agent_arch_1",
        name="Chief Architect",
        role=AgentRole.CHIEF_ARCHITECT,
        capabilities=["system_design", "governance"],
        priority=90,
        workload=2,
        max_workload=5,
    )
    assert agent.agent_id == "agent_arch_1"
    assert agent.role == AgentRole.CHIEF_ARCHITECT
    assert agent.is_available is True
    assert agent.success_rate == 1.0

    agent.record_task_completion(success=True, duration=1.5)
    agent.record_task_completion(success=False, duration=2.5)
    assert agent.total_tasks_completed == 1
    assert agent.total_tasks_failed == 1
    assert agent.success_rate == 0.5
    assert agent.average_duration == 2.0


def test_agent_registry_crud():
    registry = AgentRegistry()
    agent1 = AgentDescriptor(
        agent_id="dev_1",
        name="Backend Dev",
        role=AgentRole.BACKEND_ENGINEER,
        capabilities=["python", "fastapi"],
    )
    agent2 = AgentDescriptor(
        agent_id="dev_2",
        name="Frontend Dev",
        role=AgentRole.FRONTEND_ENGINEER,
        capabilities=["react", "typescript"],
    )

    registry.register_agent(agent1)
    registry.register_agent(agent2)
    assert registry.count == 2
    assert registry.get_agent("dev_1") == agent1

    # Duplicate registration raises ValueError
    with pytest.raises(ValueError):
        registry.register_agent(agent1)

    # Removal
    assert registry.remove_agent("dev_2") is True
    assert registry.get_agent("dev_2") is None
    assert registry.count == 1
    assert registry.remove_agent("non_existent") is False


def test_agent_discovery_and_filtering():
    registry = AgentRegistry()
    registry.register_agent(
        AgentDescriptor(
            agent_id="qa_1",
            name="QA 1",
            role=AgentRole.QA_ENGINEER,
            capabilities=["pytest", "e2e"],
            priority=70,
        )
    )
    registry.register_agent(
        AgentDescriptor(
            agent_id="qa_2",
            name="QA 2",
            role=AgentRole.QA_ENGINEER,
            capabilities=["security", "pytest"],
            priority=85,
            workload=5,
            max_workload=5,  # busy
        )
    )
    registry.register_agent(
        AgentDescriptor(
            agent_id="sec_1",
            name="Sec 1",
            role=AgentRole.SECURITY_ENGINEER,
            capabilities=["security"],
            priority=95,
        )
    )

    # Filter by role
    qa_agents = registry.discover_agents(role=AgentRole.QA_ENGINEER)
    assert len(qa_agents) == 2
    # Sorted by -priority: qa_2 (85) then qa_1 (70)
    assert qa_agents[0].agent_id == "qa_2"
    assert qa_agents[1].agent_id == "qa_1"

    # Filter by available only
    avail_qa = registry.discover_agents(role=AgentRole.QA_ENGINEER, available_only=True)
    assert len(avail_qa) == 1
    assert avail_qa[0].agent_id == "qa_1"

    # Filter by capability
    sec_agents = registry.discover_agents(required_capabilities=["security"])
    assert len(sec_agents) == 2
    assert {a.agent_id for a in sec_agents} == {"sec_1", "qa_2"}


def test_health_monitoring_and_heartbeats():
    registry = AgentRegistry()
    agent = AgentDescriptor(
        agent_id="be_1",
        name="Backend",
        role=AgentRole.BACKEND_ENGINEER,
        last_heartbeat=time.time() - 100.0,  # Stale heartbeat
    )
    registry.register_agent(agent)

    unhealthy = registry.check_health(stale_timeout_seconds=30.0)
    assert len(unhealthy) == 1
    assert unhealthy[0].agent_id == "be_1"
    assert unhealthy[0].status == AgentStatus.OFFLINE

    # Send heartbeat
    assert registry.heartbeat("be_1") is True
    assert registry.get_agent("be_1").status == AgentStatus.IDLE
    assert len(registry.check_health(stale_timeout_seconds=30.0)) == 0


def test_workload_and_status_updates():
    registry = AgentRegistry()
    registry.register_agent(
        AgentDescriptor(
            agent_id="ai_1",
            name="AI Dev",
            role=AgentRole.AI_ENGINEER,
            workload=0,
            max_workload=3,
        )
    )
    assert registry.update_workload("ai_1", delta=2) == 2
    assert registry.update_workload("ai_1", delta=-1) == 1
    assert registry.set_status("ai_1", AgentStatus.BUSY) is True
    assert registry.get_agent("ai_1").status == AgentStatus.BUSY
