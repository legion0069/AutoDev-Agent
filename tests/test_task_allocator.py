"""
Tests for AutoDev Task Allocator (v2.8)
======================================
Verifies skill affinity matching, capacity tracking, priority sorting,
workload distribution, and dynamic task reallocation.
"""

import pytest
from core.collaboration.collaboration_models import AgentRole, TaskAssignment, TaskPriority
from core.collaboration.task_allocator import TaskAllocator


def test_task_allocator_initialization():
    allocator = TaskAllocator()
    assert len(allocator.get_all_tasks()) == 0
    assert len(allocator.get_capacities()) == 8


def test_skill_affinity_scoring():
    allocator = TaskAllocator()

    # Backend task
    t_back = TaskAssignment(
        task_id="t1",
        title="Implement REST API and Database migrations",
        required_skills=["api", "database", "python"],
        estimated_files=["api/endpoints.py", "db/models.py"],
    )
    score_back = allocator._score_agent_for_task(allocator.get_capacity("BackendAgent"), t_back)
    score_front = allocator._score_agent_for_task(allocator.get_capacity("FrontendAgent"), t_back)
    assert score_back > score_front

    # Frontend task
    t_front = TaskAssignment(
        task_id="t2",
        title="Design React UI components and state management",
        required_skills=["react", "ui", "components"],
        estimated_files=["src/components/Dashboard.tsx"],
    )
    score_front_f = allocator._score_agent_for_task(allocator.get_capacity("FrontendAgent"), t_front)
    score_back_f = allocator._score_agent_for_task(allocator.get_capacity("BackendAgent"), t_front)
    assert score_front_f > score_back_f


def test_allocate_single_task():
    allocator = TaskAllocator()
    task = TaskAssignment(
        task_id="sec_01",
        title="Audit OWASP Top 10 vulnerabilities",
        required_skills=["security", "owasp", "cve"],
        priority=TaskPriority.CRITICAL,
    )
    allocator.submit_task(task)
    allocated = allocator.allocate_task("sec_01")
    assert allocated is not None
    assert allocated.assigned_agent == "SecurityAgent"
    assert allocated.assigned_role == AgentRole.SECURITY

    cap = allocator.get_capacity("SecurityAgent")
    assert "sec_01" in cap.assigned_task_ids
    assert cap.current_workload_hours > 0


def test_batch_allocation_with_priorities():
    allocator = TaskAllocator()
    tasks = [
        TaskAssignment(task_id="t_doc", title="Update README documentation", required_skills=["docs"], priority=TaskPriority.LOW),
        TaskAssignment(task_id="t_sec", title="Fix critical vulnerability in auth", required_skills=["security", "auth"], priority=TaskPriority.CRITICAL),
        TaskAssignment(task_id="t_perf", title="Profile and optimize slow cache queries", required_skills=["performance", "caching"], priority=TaskPriority.HIGH),
    ]
    allocator.submit_tasks(tasks)
    allocated = allocator.allocate_all()
    assert len(allocated) == 3

    # Check mapping
    task_map = {t.task_id: t for t in allocated}
    assert task_map["t_doc"].assigned_agent == "DocumentationAgent"
    assert task_map["t_sec"].assigned_agent == "SecurityAgent"
    assert task_map["t_perf"].assigned_agent == "PerformanceAgent"


def test_reassign_task():
    allocator = TaskAllocator()
    task = TaskAssignment(task_id="t_reassign", title="Build interface", required_skills=["architecture"])
    allocator.submit_task(task)
    allocator.allocate_task("t_reassign")

    # Reassign to BackendAgent
    success = allocator.reassign_task("t_reassign", "BackendAgent")
    assert success is True
    assert allocator.get_task("t_reassign").assigned_agent == "BackendAgent"
    assert "t_reassign" in allocator.get_capacity("BackendAgent").assigned_task_ids


def test_task_completion_and_stats():
    allocator = TaskAllocator()
    task = TaskAssignment(task_id="t_done", title="Test task", estimated_hours=4.0)
    allocator.submit_task(task)
    allocator.allocate_task("t_done")

    stats_before = allocator.get_allocation_stats()
    assert stats_before["assigned_tasks"] == 1

    allocator.complete_task("t_done")
    stats_after = allocator.get_allocation_stats()
    assert stats_after["completed_tasks"] == 1
    assert stats_after["assigned_tasks"] == 0
