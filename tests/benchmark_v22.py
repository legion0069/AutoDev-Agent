"""
benchmark_v22.py - Performance and Reliability Benchmarks for AutoDev Version 2.2
"""

import time
from pathlib import Path
from core.change_execution_planner import ChangeOperation
from core.container_runtime import ContainerRuntimeDetector, MockContainerRuntime, ContainerExecutionConfig
from core.distributed_scheduler import DistributedScheduler, SchedulerConfig
from core.task_lease_manager import TaskLeaseManager
from core.telemetry_models import TelemetryEvent
from core.telemetry_stream import TelemetryStream
from core.worker_protocol import WorkerCapabilities, WorkerHeartbeat, WorkerRegistrationRequest, WorkerStatus
from core.worker_registry import WorkerRegistry


def run_benchmarks():
    results = {}
    
    # 1. Worker Registration Latency
    registry = WorkerRegistry()
    req = WorkerRegistrationRequest(
        worker_id="bench-worker",
        worker_name="Benchmark Worker",
        capabilities=WorkerCapabilities(max_concurrency=4),
    )
    t0 = time.perf_counter()
    for _ in range(1000):
        registry.register_worker(req)
    t1 = time.perf_counter()
    reg_latency_us = ((t1 - t0) / 1000) * 1_000_000
    results["worker_registration_latency_us"] = round(reg_latency_us, 2)

    # 2. Heartbeat Processing Latency
    hb = WorkerHeartbeat(worker_id="bench-worker", status=WorkerStatus.BUSY, current_load=1)
    t0 = time.perf_counter()
    for _ in range(1000):
        registry.process_heartbeat(hb)
    t1 = time.perf_counter()
    hb_latency_us = ((t1 - t0) / 1000) * 1_000_000
    results["heartbeat_processing_latency_us"] = round(hb_latency_us, 2)

    # 3. Task Lease Acquisition & Renewal Latency
    lease_mgr = TaskLeaseManager()
    t0 = time.perf_counter()
    lease = lease_mgr.acquire_lease("task-b1", "op1", "tx-b1", "bench-worker")
    token = lease.owner_token
    for _ in range(1000):
        lease_mgr.renew_lease(token, ttl_seconds=10.0)
    t1 = time.perf_counter()
    lease_renewal_us = ((t1 - t0) / 1000) * 1_000_000
    results["lease_renewal_overhead_us"] = round(lease_renewal_us, 2)

    # 4. Disjoint-Batch Scheduling for 100 and 1,000 Operations
    scheduler = DistributedScheduler(registry, lease_mgr)
    ops_100 = [ChangeOperation(f"op-{i}", "CREATE_FILE", f"src/file_{i % 10}.py") for i in range(100)]
    t0 = time.perf_counter()
    batches_100 = scheduler.partition_disjoint_batches(ops_100)
    t1 = time.perf_counter()
    sched_100_ms = (t1 - t0) * 1000
    results["scheduler_100_ops_ms"] = round(sched_100_ms, 3)

    ops_1000 = [ChangeOperation(f"op-{i}", "CREATE_FILE", f"src/file_{i % 25}.py") for i in range(1000)]
    t0 = time.perf_counter()
    batches_1000 = scheduler.partition_disjoint_batches(ops_1000)
    t1 = time.perf_counter()
    sched_1000_ms = (t1 - t0) * 1000
    results["scheduler_1000_ops_ms"] = round(sched_1000_ms, 3)

    # 5. Telemetry Ring Buffer Event Ingestion & Delivery Latency
    stream = TelemetryStream(max_buffer_size=1000)
    sub_q, _ = stream.subscribe()
    t0 = time.perf_counter()
    for i in range(1000):
        stream.publish_event("BENCH_EVENT", message=f"Event {i}", transaction_id="tx-bench")
    t1 = time.perf_counter()
    event_ingest_us = ((t1 - t0) / 1000) * 1_000_000
    results["telemetry_event_ingest_latency_us"] = round(event_ingest_us, 2)
    stream.unsubscribe(sub_q)

    # 6. Container Runtime Probe
    detector = ContainerRuntimeDetector()
    t0 = time.perf_counter()
    info = detector.detect(force_refresh=True)
    t1 = time.perf_counter()
    detection_ms = (t1 - t0) * 1000
    results["container_detection_ms"] = round(detection_ms, 2)
    results["detected_runtime"] = info.runtime_type.value
    results["is_daemon_running"] = info.is_daemon_running

    print("--- BENCHMARK RESULTS ---")
    for k, v in results.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    run_benchmarks()
