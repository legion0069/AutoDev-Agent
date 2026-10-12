"""
test_cross_company_scheduler.py - Unit Tests for CrossCompanyScheduler (AutoDev Version 3.5)
"""

import pytest

from core.cross_company_scheduler import (
    CrossCompanyScheduler,
    FederationTask,
)


def test_scheduler_initialization():
    sched = CrossCompanyScheduler()
    assert len(sched._tasks) == 0


def test_add_tasks_and_dependencies():
    sched = CrossCompanyScheduler()
    t1 = sched.add_task("TASK-01", "COMP-A", "Backend Architecture", duration_hours=10.0)
    t2 = sched.add_task("TASK-02", "COMP-B", "Frontend Integration", duration_hours=15.0, dependencies=["TASK-01"])

    assert t1.task_id == "TASK-01"
    assert t2.dependencies == ["TASK-01"]
    assert "TASK-02" in sched._successors["TASK-01"]


def test_cycle_detection_on_acyclic_graph():
    sched = CrossCompanyScheduler()
    sched.add_task("T1", "COMP-A", "Task 1", 5.0)
    sched.add_task("T2", "COMP-B", "Task 2", 8.0, dependencies=["T1"])
    sched.add_task("T3", "COMP-C", "Task 3", 4.0, dependencies=["T2"])

    has_cycle, cycle = sched.detect_cycles()
    assert has_cycle is False
    assert len(cycle) == 0


def test_cycle_detection_on_cyclic_graph():
    sched = CrossCompanyScheduler()
    sched.add_task("T1", "COMP-A", "Task 1", 5.0, dependencies=["T3"])
    sched.add_task("T2", "COMP-B", "Task 2", 8.0, dependencies=["T1"])
    sched.add_task("T3", "COMP-C", "Task 3", 4.0, dependencies=["T2"])

    has_cycle, cycle = sched.detect_cycles()
    assert has_cycle is True
    assert len(cycle) > 0


def test_critical_path_method_cpm():
    sched = CrossCompanyScheduler()
    # Path 1: T1 (10h) -> T2 (20h) = 30h
    # Path 2: T3 (5h) -> T4 (10h)  = 15h
    # Both merge into T5 (5h)
    # Critical Path should be T1 -> T2 -> T5 (total 35h)
    sched.add_task("T1", "COMP-A", "Core DB Schema", 10.0)
    sched.add_task("T2", "COMP-A", "Core API Logic", 20.0, dependencies=["T1"])
    sched.add_task("T3", "COMP-B", "UI Wireframes", 5.0)
    sched.add_task("T4", "COMP-B", "UI Mockups", 10.0, dependencies=["T3"])
    sched.add_task("T5", "COMP-C", "System Integration", 5.0, dependencies=["T2", "T4"])

    cpm_result = sched.compute_critical_path()
    assert cpm_result["total_project_duration_hours"] == 35.0

    crit_tasks = cpm_result["critical_path_tasks"]
    assert "T1" in crit_tasks
    assert "T2" in crit_tasks
    assert "T5" in crit_tasks

    # T3 and T4 have slack > 0, so they are not critical
    assert "T3" not in crit_tasks
    assert "T4" not in crit_tasks
    assert sched._tasks["T3"].slack == 15.0


def test_ready_tasks_and_completion():
    sched = CrossCompanyScheduler()
    sched.add_task("T1", "COMP-A", "Step 1", 10.0, priority=5)
    sched.add_task("T2", "COMP-B", "Step 2", 10.0, dependencies=["T1"], priority=4)

    ready = sched.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "T1"

    # Complete T1
    assert sched.complete_task("T1") is True
    assert sched._tasks["T1"].status == "COMPLETED"

    # Now T2 should be ready
    ready2 = sched.get_ready_tasks()
    assert len(ready2) == 1
    assert ready2[0].task_id == "T2"


def test_detect_conflicts_and_bottlenecks():
    sched = CrossCompanyScheduler()
    # Company A has 80 hours of tasks assigned
    sched.add_task("T1", "COMP-A", "Job 1", 50.0)
    sched.add_task("T2", "COMP-A", "Job 2", 30.0)

    # But Company A only has 40 hours of available capacity!
    bottlenecks = sched.detect_conflicts_and_bottlenecks({"COMP-A": 40.0})
    assert len(bottlenecks) == 1
    b = bottlenecks[0]
    assert b["company_id"] == "COMP-A"
    assert b["required_hours"] == 80.0
    assert b["overage_hours"] == 40.0
    assert b["severity"] == "CRITICAL"
