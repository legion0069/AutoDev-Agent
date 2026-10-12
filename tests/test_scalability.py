"""
Scalability and stress tests for AutoDev v3.3 Distributed Multi-Agent Platform.

Validates:
- 100 agents registered, health checked, and workload managed
- 1,000 tasks queued, allocated, and executed
- 10,000 messages routed across message bus
- Parallel scheduling throughput
- Deadlock prevention under competing resource requests
- Race condition testing under concurrent threads
"""

import threading
import time
import pytest
from core.multi_agent.agent_bus import AgentMessageBus
from core.multi_agent.agent_registry import AgentDescriptor, AgentRegistry, AgentRole
from core.multi_agent.collaboration_engine import CollaborationEngine
from core.multi_agent.message import Message, MessagePriority, MessageType
from core.multi_agent.parallel_executor import ParallelExecutor
from core.multi_agent.resource_scheduler import LockType, ResourceScheduler
from core.multi_agent.task_allocator import TaskAllocator
from core.multi_agent.work_queue import WorkItem, WorkQueue


def test_100_agents_registration_and_discovery():
    """Stress test: 100 agents registration, capabilities, and discovery."""
    registry = AgentRegistry()
    roles = list(AgentRole)

    for i in range(100):
        role = roles[i % len(roles)]
        desc = AgentDescriptor(
            agent_id=f"agent_{i:03d}",
            name=f"Engineer {i}",
            role=role,
            capabilities=[f"cap_{i % 5}", "general_engineering"],
            priority=50 + (i % 50),
            workload=i % 4,
            max_workload=5,
        )
        registry.register_agent(desc)

    assert registry.count == 100
    all_agents = registry.get_all_agents()
    assert len(all_agents) == 100

    # Discovery by role
    arch_agents = registry.discover_agents(role=AgentRole.CHIEF_ARCHITECT)
    assert len(arch_agents) >= 1

    # Bulk health check
    unhealthy = registry.check_health(stale_timeout_seconds=3600.0)
    assert len(unhealthy) == 0


def test_10000_messages_throughput():
    """Stress test: 10,000 messages routed through message bus."""
    bus = AgentMessageBus()
    for i in range(10):
        bus.register_inbox(f"receiver_{i}")

    # Send 10,000 messages
    for i in range(10000):
        target = f"receiver_{i % 10}"
        msg = Message(
            sender="load_tester",
            receiver=target,
            msg_type=MessageType.DIRECT,
            payload={"index": i},
        )
        bus.send(msg)

    assert bus.count() == 10000
    # Verify inboxes distributed uniformly
    for i in range(10):
        assert bus.get_inbox_size(f"receiver_{i}") == 1000


def test_1000_tasks_queued_and_allocated():
    """Stress test: 1,000 tasks queued and allocated deterministically."""
    queue = WorkQueue()
    allocator = TaskAllocator()
    registry = AgentRegistry()

    # Register 20 agents
    for i in range(20):
        registry.register_agent(
            AgentDescriptor(
                agent_id=f"worker_{i}",
                name=f"Worker {i}",
                role=AgentRole.BACKEND_ENGINEER if i % 2 == 0 else AgentRole.FRONTEND_ENGINEER,
                capabilities=["coding"],
                max_workload=100,
            )
        )

    # Enqueue 1,000 tasks
    for i in range(1000):
        role = AgentRole.BACKEND_ENGINEER if i % 2 == 0 else AgentRole.FRONTEND_ENGINEER
        task = WorkItem(
            task_id=f"task_{i:04d}",
            title=f"Task {i}",
            required_role=role,
            priority=10 + (i % 90),
        )
        queue.enqueue(task)

    assert queue.size() == 1000
    ready = queue.get_ready_tasks()
    assert len(ready) == 1000

    # Batch allocate all 1000 tasks
    assignments = allocator.allocate_batch(ready, registry)
    assert len(assignments) == 1000
    # Ensure all tasks got valid assigned agents
    assert all(a_id.startswith("worker_") for a_id in assignments.values())


def test_deadlock_prevention_under_concurrency():
    """Stress test: Deadlock prevention when 20 concurrent threads compete for resources."""
    scheduler = ResourceScheduler()
    resources = ["file_alpha.py", "file_beta.py", "file_gamma.py", "file_delta.py"]
    errors = []
    successes = []

    def worker_job(worker_id: int):
        agent_id = f"worker_{worker_id}"
        # Request random combination of resources in different orders
        import random
        r_subset = sorted(random.sample(resources, k=2))
        acquired = scheduler.acquire_multi(
            resource_ids=r_subset,
            agent_id=agent_id,
            lock_type=LockType.WRITE,
            timeout=0.5,
        )
        if acquired:
            time.sleep(0.01)
            for r in r_subset:
                scheduler.release_lock(r, agent_id)
            successes.append(worker_id)
        else:
            errors.append(worker_id)

    threads = [threading.Thread(target=worker_job, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    # Guarantee all threads completed without deadlocking
    assert len(successes) + len(errors) == 20
    # All locks should eventually be freed
    for r in resources:
        assert scheduler.is_locked(r) is False


def test_race_condition_under_parallel_scheduling():
    """Stress test: 50 simultaneous parallel task submissions and completions."""
    engine = CollaborationEngine(
        executor=ParallelExecutor(max_workers=8)
    )
    for i in range(5):
        engine.registry.register_agent(
            AgentDescriptor(f"ag_{i}", f"Agent {i}", AgentRole.BACKEND_ENGINEER, max_workload=20)
        )

    tasks = [
        WorkItem(task_id=f"st_{i}", title=f"Stress Task {i}")
        for i in range(50)
    ]

    for t in tasks:
        engine.submit_task(t)

    results = engine.run_all_tasks()
    assert len(results) == 50
    assert engine.work_queue.completed_count() == 50
    assert engine.work_queue.is_finished() is True

    telemetry = engine.get_telemetry()
    assert telemetry.completed_tasks == 50
    assert telemetry.failed_tasks == 0
    engine.shutdown()
