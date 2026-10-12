"""
test_distributed_queue.py - Unit tests for reliable DistributedQueue (v2.9)
"""

import pytest
import time
from core.cluster.cluster_config import ClusterConfig
from core.cluster.cluster_state import TaskExecutionStatus, TaskSpec
from core.cluster.distributed_queue import DistributedQueue


def test_priority_queue_dispatch():
    config = ClusterConfig(queue_visibility_timeout=2.0)
    q = DistributedQueue(config=config)

    t1 = TaskSpec(task_id="t1", title="Low Priority", priority=80)
    t2 = TaskSpec(task_id="t2", title="Critical Priority", priority=10)
    t3 = TaskSpec(task_id="t3", title="Medium Priority", priority=50)

    q.enqueue_batch([t1, t2, t3])
    assert q.get_queue_depth() == 3

    # Dequeue should yield t2 first (priority 10), then t3, then t1
    d1 = q.dequeue(worker_id="w1")
    assert d1.task_id == "t2"
    assert d1.status == TaskExecutionStatus.RUNNING

    d2 = q.dequeue(worker_id="w1")
    assert d2.task_id == "t3"

    d3 = q.dequeue(worker_id="w1")
    assert d3.task_id == "t1"


def test_queue_ack_and_dependency_promotion():
    q = DistributedQueue()

    # t_parent -> t_child
    t_parent = TaskSpec(task_id="parent_task", priority=10)
    t_child = TaskSpec(task_id="child_task", priority=20, dependencies=["parent_task"])

    q.enqueue(t_child)
    # Child is held in waiting pool because parent not completed
    assert q.get_queue_depth() == 0

    q.enqueue(t_parent)
    assert q.get_queue_depth() == 1

    d_parent = q.dequeue(worker_id="w1")
    assert d_parent.task_id == "parent_task"

    # Ack parent
    q.ack(task_id="parent_task", result={"ok": True})

    # Child should be automatically promoted to ready queue
    assert q.get_queue_depth() == 1
    d_child = q.dequeue(worker_id="w1")
    assert d_child.task_id == "child_task"


def test_queue_nack_and_dead_letter():
    config = ClusterConfig(max_task_retries=2)
    q = DistributedQueue(config=config)

    task = TaskSpec(task_id="failing_task", max_retries=2, priority=10)
    q.enqueue(task)

    # 1st attempt
    d1 = q.dequeue(worker_id="w1")
    q.nack(d1.task_id, error="syntax error 1", retry=True)

    # 2nd attempt
    d2 = q.dequeue(worker_id="w1")
    assert d2.retry_count == 1
    q.nack(d2.task_id, error="syntax error 2", retry=True)

    # 3rd attempt: retries exhausted -> DLQ
    d3 = q.dequeue(worker_id="w1")
    assert d3.retry_count == 2
    q.nack(d3.task_id, error="final fatal error", retry=True)

    # Should now be in Dead-Letter Queue
    dlq = q.get_dead_letter_tasks()
    assert len(dlq) == 1
    assert dlq[0].task_id == "failing_task"
    assert dlq[0].status == TaskExecutionStatus.DEAD_LETTER

    # Manual retry from DLQ
    assert q.retry_dead_letter("failing_task") is True
    assert q.get_queue_depth() == 1
