"""
Tests for AutoDev Dependency Scheduler (v2.8)
=============================================
Verifies DAG construction, cycle detection (deadlock prevention),
Kahn topological sorting for parallel batching, and critical path analysis.
"""

import pytest
from core.collaboration.collaboration_models import TaskAssignment
from core.collaboration.dependency_scheduler import DependencyScheduler


def test_dag_parallel_batches():
    scheduler = DependencyScheduler()
    # T1, T2 independent; T3 depends on T1; T4 depends on T1, T2; T5 depends on T3, T4
    t1 = TaskAssignment(task_id="T1", title="Scaffold models", estimated_hours=2.0)
    t2 = TaskAssignment(task_id="T2", title="Scaffold UI components", estimated_hours=1.0)
    t3 = TaskAssignment(task_id="T3", title="Implement API service", dependencies=["T1"], estimated_hours=3.0)
    t4 = TaskAssignment(task_id="T4", title="Implement UI controller", dependencies=["T1", "T2"], estimated_hours=2.0)
    t5 = TaskAssignment(task_id="T5", title="Integration tests", dependencies=["T3", "T4"], estimated_hours=1.5)

    scheduler.add_tasks([t1, t2, t3, t4, t5])

    batches = scheduler.get_parallel_batches()
    assert len(batches) == 3
    assert set(batches[0]) == {"T1", "T2"}
    assert set(batches[1]) == {"T3", "T4"}
    assert set(batches[2]) == {"T5"}


def test_cycle_detection_and_deadlock_prevention():
    scheduler = DependencyScheduler()
    # Cyclic: A -> B -> C -> A
    ta = TaskAssignment(task_id="A", title="Task A", dependencies=["C"])
    tb = TaskAssignment(task_id="B", title="Task B", dependencies=["A"])
    tc = TaskAssignment(task_id="C", title="Task C", dependencies=["B"])

    scheduler.add_tasks([ta, tb, tc])
    cycles = scheduler.detect_cycles()
    assert len(cycles) > 0

    # Parallel batches handle cycles gracefully without infinite loop
    batches = scheduler.get_parallel_batches()
    assert len(batches) > 0


def test_critical_path_calculation():
    scheduler = DependencyScheduler()
    # Path 1: T1(2h) -> T3(4h) -> T5(1h) = 7h
    # Path 2: T2(1h) -> T4(2h) -> T5(1h) = 4h
    t1 = TaskAssignment(task_id="T1", title="T1", estimated_hours=2.0)
    t2 = TaskAssignment(task_id="T2", title="T2", estimated_hours=1.0)
    t3 = TaskAssignment(task_id="T3", title="T3", dependencies=["T1"], estimated_hours=4.0)
    t4 = TaskAssignment(task_id="T4", title="T4", dependencies=["T2"], estimated_hours=2.0)
    t5 = TaskAssignment(task_id="T5", title="T5", dependencies=["T3", "T4"], estimated_hours=1.0)

    scheduler.add_tasks([t1, t2, t3, t4, t5])
    cpath = scheduler.get_critical_path()
    assert cpath["total_hours"] == 7.0
    assert cpath["critical_path"] == ["T1", "T3", "T5"]


def test_ready_and_blocked_task_filtering():
    scheduler = DependencyScheduler()
    t1 = TaskAssignment(task_id="T1", title="T1")
    t2 = TaskAssignment(task_id="T2", title="T2", dependencies=["T1"])

    scheduler.add_tasks([t1, t2])
    ready = scheduler.get_ready_tasks()
    blocked = scheduler.get_blocked_tasks()

    assert [t.task_id for t in ready] == ["T1"]
    assert [t.task_id for t in blocked] == ["T2"]

    # Mark T1 completed
    scheduler.mark_completed("T1")
    ready_after = scheduler.get_ready_tasks()
    assert [t.task_id for t in ready_after] == ["T2"]
