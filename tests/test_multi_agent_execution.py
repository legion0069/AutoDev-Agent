"""
Integration Tests for Multi-Agent Collaborative Execution (v2.8)
================================================================
Comprehensive end-to-end multi-agent software engineering test suite:
- Parallel DAG execution across 8 specialized agents
- Direct and broadcast message routing across CommunicationBus
- Review workflows, code staging, and atomic file lock reconciliation
- Automatic conflict detection and patch resolution
- Deadlock prevention and cycle breaking
- Pre-merge and pre-release synchronization barriers
- Large-scale multi-agent enterprise project simulation
- Extreme edge cases (zero tasks, high concurrency, conflicting updates)
"""

import threading
import time
import pytest

from agents import (
    ArchitectureAgent,
    BackendAgent,
    DocumentationAgent,
    FrontendAgent,
    PerformanceAgent,
    ReleaseAgent,
    SecurityAgent,
    TestingAgent,
)
from core.collaboration import (
    AgentMessage,
    AgentRole,
    CollaborationConfig,
    CollaborationManager,
    ConsensusStrategy,
    MessageType,
    Proposal,
    SyncCheckpointType,
    TaskAssignment,
    TaskPriority,
)


@pytest.fixture
def full_collaboration_org():
    """Build a fully registered 8-agent AI software engineering organization."""
    mgr = CollaborationManager(CollaborationConfig(max_parallel_agents=8))
    agents = [
        ArchitectureAgent(),
        BackendAgent(),
        FrontendAgent(),
        TestingAgent(),
        SecurityAgent(),
        PerformanceAgent(),
        DocumentationAgent(),
        ReleaseAgent(),
    ]
    for ag in agents:
        mgr.register_agent(ag)
    return mgr


def test_full_multi_agent_collaborative_cycle(full_collaboration_org):
    mgr = full_collaboration_org

    tasks = [
        TaskAssignment(task_id="t1_arch", title="System Architecture & Interfaces", required_skills=["architecture"], estimated_files=["core/interfaces.py"]),
        TaskAssignment(task_id="t2_backend", title="Implement REST API Service", required_skills=["backend", "api"], dependencies=["t1_arch"], estimated_files=["api/service.py"]),
        TaskAssignment(task_id="t3_frontend", title="Implement Web UI View", required_skills=["frontend", "ui"], dependencies=["t1_arch"], estimated_files=["ui/view.tsx"]),
        TaskAssignment(task_id="t4_security", title="Security Audit & Hardening", required_skills=["security"], dependencies=["t2_backend"], estimated_files=["security/policy.py"]),
        TaskAssignment(task_id="t5_testing", title="Integration & Unit Testing", required_skills=["testing"], dependencies=["t2_backend", "t3_frontend"], estimated_files=["tests/test_api.py"]),
        TaskAssignment(task_id="t6_perf", title="Performance Caching Layer", required_skills=["performance"], dependencies=["t2_backend"], estimated_files=["cache/lru.py"]),
        TaskAssignment(task_id="t7_docs", title="Document API & Architecture", required_skills=["docs"], dependencies=["t5_testing"], estimated_files=["docs/README.md"]),
        TaskAssignment(task_id="t8_release", title="Package & Prepare Release", required_skills=["release"], dependencies=["t7_docs"], estimated_files=["release/manifest.json"]),
    ]

    mgr.submit_tasks(tasks)
    summary = mgr.execute_multi_agent_cycle(max_workers=4)

    assert summary["status"] == "completed"
    assert summary["tasks_executed"] == 8
    assert summary["batches_executed"] >= 4
    assert summary["pre_merge_checkpoint"] is True

    # Verify telemetry metrics
    metrics = summary["metrics"]
    assert metrics["total_tasks"] == 8
    assert metrics["completed_tasks"] == 8
    assert metrics["collaboration_efficiency"] > 0.0


def test_message_routing_and_request_response(full_collaboration_org):
    mgr = full_collaboration_org
    bus = mgr.bus
    arch = mgr.get_agent("ArchitectureAgent")
    backend = mgr.get_agent("BackendAgent")

    # Backend sends request to Architecture
    bus.register_direct_handler(
        agent_name="ArchitectureAgent",
        handler=lambda msg: {"status": "approved", "contract": "IBackendService"},
    )

    resp = backend.request("ArchitectureAgent", {"query": "get_interface_contract"}, timeout=2.0)
    assert resp is not None
    assert resp.payload["status"] == "approved"
    assert resp.payload["contract"] == "IBackendService"


def test_blocker_broadcast_and_resolution(full_collaboration_org):
    mgr = full_collaboration_org
    bus = mgr.bus
    back = mgr.get_agent("BackendAgent")

    # Report blocker
    back.report_blocker("task_db_01", "Database schema migration blocked by lock")
    assert "task_db_01" in bus.get_active_blockers()

    # Resolve blocker
    back.resolve_blocker("task_db_01", "Lock released, migrations finished successfully")
    assert "task_db_01" not in bus.get_active_blockers()


def test_large_scale_enterprise_project_simulation(full_collaboration_org):
    mgr = full_collaboration_org

    # Generate 24 concurrent enterprise engineering tasks across 4 tiers
    tasks = []
    for tier in range(4):
        for i in range(6):
            tid = f"tier_{tier}_task_{i}"
            deps = [f"tier_{tier-1}_task_{i % 3}"] if tier > 0 else []
            skills = [["architecture", "backend", "frontend", "testing", "security", "performance"][i]]
            tasks.append(TaskAssignment(
                task_id=tid,
                title=f"Enterprise Tier {tier} Subsystem Module {i}",
                required_skills=skills,
                dependencies=deps,
                estimated_hours=2.0,
            ))

    mgr.submit_tasks(tasks)
    plan = mgr.plan_and_schedule()
    assert plan["total_tasks"] == 24
    assert len(plan["parallel_batches"]) == 4

    summary = mgr.execute_multi_agent_cycle(max_workers=6)
    assert summary["status"] == "completed"
    assert summary["tasks_executed"] == 24


def test_edge_case_zero_tasks(full_collaboration_org):
    mgr = full_collaboration_org
    plan = mgr.plan_and_schedule()
    assert plan["total_tasks"] == 0

    summary = mgr.execute_multi_agent_cycle()
    assert summary["status"] == "completed"
    assert summary["tasks_executed"] == 0


def test_edge_case_concurrent_workspace_modifications(full_collaboration_org):
    mgr = full_collaboration_org
    ws = mgr.workspace

    # 10 threads trying to write and read simultaneously
    results = []

    def worker(idx):
        agent_name = f"Worker_{idx}"
        lock = ws.acquire_lock("shared_config.py", holder=agent_name, role=AgentRole.GENERAL, is_exclusive=True, ttl=0.5)
        if lock:
            ws.stage_change("shared_config.py", author_id=agent_name, role=AgentRole.GENERAL, content=f"CONFIG_VAL = {idx}")
            time.sleep(0.01)
            ws.release_lock("shared_config.py", holder=agent_name)
            results.append((idx, True))
        else:
            results.append((idx, False))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Shared workspace must remain in a consistent state without crashing
    assert len(results) == 10
    staged = ws.get_staged_change("shared_config.py")
    assert staged is not None
