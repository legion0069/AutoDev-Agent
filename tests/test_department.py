"""
test_department.py - AutoDev Version 3.4
Unit and integration tests for Department Architecture:
- Roles, authority levels, capacities, and budgets
- Task lifecycle: assignment, completion, failure, blocking, unblocking
- Budget tracking and allocation
- Health score, performance score, and confidence calculations
- Inter-department messaging and inbox processing
"""

import pytest
from core.communication_bus import CommunicationBus, MessagePriority, OrgMessageType
from core.department import (
    Department,
    DepartmentAuthorityLevel,
    DepartmentRole,
    DepartmentTask,
)


@pytest.fixture
def bus():
    return CommunicationBus()


@pytest.fixture
def backend_dept(bus: CommunicationBus):
    return Department(
        name="Backend",
        role=DepartmentRole.BACKEND,
        authority=DepartmentAuthorityLevel.SPECIALIST,
        bus=bus,
        budget=50000.0,
        capacity=5,
        priority=7,
        headcount=4,
    )


def test_department_initialization(backend_dept: Department):
    assert backend_dept.name == "Backend"
    assert backend_dept.role == DepartmentRole.BACKEND
    assert backend_dept.authority == DepartmentAuthorityLevel.SPECIALIST
    assert backend_dept.budget == 50000.0
    assert backend_dept.spent_budget == 0.0
    assert backend_dept.capacity == 5
    assert backend_dept.health_score == 100.0
    assert backend_dept.performance_score == 100.0
    assert backend_dept.confidence >= 0.90


def test_task_assignment_under_capacity(backend_dept: Department):
    task = backend_dept.assign_task(
        task_id="T-01",
        title="Develop auth endpoint",
        description="JWT based authentication handler",
        assigned_by="EngineeringManager",
        priority=3,
    )
    assert task.status == "IN_PROGRESS"
    assert backend_dept.current_workload == 1
    assert "T-01" in backend_dept.active_tasks


def test_task_assignment_exceeds_capacity(backend_dept: Department):
    # Capacity is 5; assign 6 tasks
    for i in range(5):
        backend_dept.assign_task(f"T-{i}", f"Task {i}", "Desc", "EM")

    assert backend_dept.current_workload == 5
    assert len(backend_dept.active_tasks) == 5

    # 6th task should be BLOCKED due to capacity
    t6 = backend_dept.assign_task("T-OVERFLOW", "Overflow Task", "Desc", "EM")
    assert t6.status == "BLOCKED"
    assert t6.blocker_reason == "Department at maximum capacity"
    assert "T-OVERFLOW" in backend_dept.blocked_tasks
    assert backend_dept.health_score < 100.0


def test_task_completion_and_rebalance(backend_dept: Department):
    for i in range(5):
        backend_dept.assign_task(f"T-{i}", f"Task {i}", "Desc", "EM")
    backend_dept.assign_task("T-BLOCKED", "Blocked task", "Desc", "EM")

    assert "T-BLOCKED" in backend_dept.blocked_tasks

    # Complete one active task
    completed = backend_dept.complete_task("T-0", artifacts=["src/auth.py"], cost=500.0)
    assert completed is not None
    assert completed.status == "COMPLETED"
    assert "src/auth.py" in completed.artifacts
    assert backend_dept.spent_budget == 500.0

    # The blocked task should automatically be unblocked to fill the freed slot!
    assert "T-BLOCKED" in backend_dept.active_tasks
    assert "T-BLOCKED" not in backend_dept.blocked_tasks


def test_task_failure(backend_dept: Department):
    backend_dept.assign_task("T-FAIL", "Failing task", "Desc", "EM")
    failed = backend_dept.fail_task("T-FAIL", reason="Syntax error in dependency")

    assert failed is not None
    assert failed.status == "FAILED"
    assert failed.blocker_reason == "Syntax error in dependency"
    assert len(backend_dept.failed_tasks) == 1
    assert backend_dept.performance_score < 100.0


def test_manual_block_and_unblock(backend_dept: Department):
    backend_dept.assign_task("T-MANUAL", "Manual task", "Desc", "EM")
    blocked = backend_dept.block_task("T-MANUAL", reason="Waiting for API spec from Architecture")
    assert blocked is not None
    assert blocked.status == "BLOCKED"
    assert "T-MANUAL" in backend_dept.blocked_tasks

    unblocked = backend_dept.unblock_task("T-MANUAL")
    assert unblocked is not None
    assert unblocked.status == "IN_PROGRESS"
    assert "T-MANUAL" in backend_dept.active_tasks


def test_budget_expenditure_and_allocation(backend_dept: Department):
    assert backend_dept.spend_budget(15000.0) is True
    assert backend_dept.spent_budget == 15000.0
    assert backend_dept.spend_budget(40000.0) is False  # Exceeds total budget 50000.0
    assert backend_dept.spent_budget == 55000.0

    backend_dept.allocate_budget(20000.0)
    assert backend_dept.budget == 70000.0


def test_health_score_calculation(backend_dept: Department):
    assert backend_dept.health_score == 100.0
    backend_dept.assign_task("T-1", "T1", "Desc", "EM")
    backend_dept.block_task("T-1", reason="External dependency down")

    # Health score penalized by blocked task
    assert backend_dept.health_score <= 88.0


def test_performance_score_calculation(backend_dept: Department):
    # 3 successes, 1 failure -> 75% performance score
    backend_dept.assign_task("T-1", "T1", "D", "EM")
    backend_dept.assign_task("T-2", "T2", "D", "EM")
    backend_dept.assign_task("T-3", "T3", "D", "EM")
    backend_dept.assign_task("T-4", "T4", "D", "EM")

    backend_dept.complete_task("T-1")
    backend_dept.complete_task("T-2")
    backend_dept.complete_task("T-3")
    backend_dept.fail_task("T-4", "Test assertion failure")

    assert backend_dept.performance_score == 75.0


def test_department_messaging_and_inbox_processing(bus: CommunicationBus):
    dept_a = Department("TeamA", DepartmentRole.BACKEND, bus=bus)
    dept_b = Department("TeamB", DepartmentRole.FRONTEND, bus=bus)

    dept_a.send_message(
        receiver="TeamB",
        message_type=OrgMessageType.TASK_REQUEST,
        payload={"request": "Connect WebSocket stream"},
        priority=MessagePriority.HIGH,
    )

    inbox_b = dept_b.process_inbox()
    assert len(inbox_b) == 1
    assert inbox_b[0].sender == "TeamA"
    assert inbox_b[0].payload["request"] == "Connect WebSocket stream"
    assert dept_b.total_processed_messages == 1


def test_department_escalation(bus: CommunicationBus):
    dept = Department("Backend", DepartmentRole.BACKEND, bus=bus)
    esc_msg = dept.escalate_issue(
        escalate_to="CEO",
        issue_title="Production database outage",
        details={"server": "db-primary", "error": "Connection refused"},
    )
    assert esc_msg is not None
    assert esc_msg.priority == MessagePriority.CRITICAL
    assert esc_msg.message_type == OrgMessageType.ESCALATION


def test_get_status_report(backend_dept: Department):
    backend_dept.assign_task("T-REP", "Report task", "Desc", "EM")
    rep = backend_dept.get_status_report()

    assert rep["name"] == "Backend"
    assert rep["role"] == "BACKEND"
    assert rep["capacity"] == 5
    assert rep["current_workload"] == 1
    assert rep["budget_total"] == 50000.0
    assert "health_score" in rep
    assert "performance_score" in rep
    assert "confidence" in rep
