"""
AutoDev Multi-Agent Collaboration Framework - Benchmark Suite (v2.8)
====================================================================
Performance, throughput, consensus latency, and DAG scheduling scale tests:
- 100 concurrent tasks parallel DAG scheduling & batch generation
- 1,000 inter-agent messages routed through CommunicationBus
- 500 consensus rounds scored across 5 strategies
- 200 concurrent file lock acquisitions & conflict resolutions
- Full 8-agent software engineering organization throughput benchmark
"""

import concurrent.futures
import sys
import time
from pathlib import Path
from typing import Dict, Any

# Ensure project root is available on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
    TaskAssignment,
    TaskPriority,
)


def run_v28_benchmarks() -> Dict[str, Any]:
    print("=" * 70)
    print("       AUTODEV v2.8 MULTI-AGENT COLLABORATION BENCHMARK SUITE")
    print("=" * 70)

    results = {}

    # ------------------------------------------------------------------
    # Benchmark 1: High-Scale DAG Scheduling (100 Tasks)
    # ------------------------------------------------------------------
    mgr = CollaborationManager(CollaborationConfig(max_parallel_agents=8))
    tasks = []
    for tier in range(10):
        for i in range(10):
            tid = f"bench_t{tier}_{i}"
            deps = [f"bench_t{tier-1}_{i % 5}"] if tier > 0 else []
            skills = [["architecture", "backend", "frontend", "testing", "security", "performance", "docs", "release"][i % 8]]
            tasks.append(TaskAssignment(
                task_id=tid,
                title=f"Tier {tier} Benchmark Task {i}",
                required_skills=skills,
                dependencies=deps,
                estimated_hours=1.5,
            ))

    t0 = time.perf_counter()
    mgr.submit_tasks(tasks)
    plan = mgr.plan_and_schedule()
    t_dag = time.perf_counter() - t0
    dag_throughput = len(tasks) / t_dag
    results["dag_scheduling_100_tasks_sec"] = round(t_dag, 4)
    results["dag_throughput_tasks_per_sec"] = round(dag_throughput, 1)
    results["dag_batches_count"] = len(plan["parallel_batches"])

    print(f"[1/5] 100-Task DAG Schedule & Batching: {t_dag*1000:.2f}ms ({dag_throughput:.1f} tasks/sec, {len(plan['parallel_batches'])} batches)")

    # ------------------------------------------------------------------
    # Benchmark 2: CommunicationBus Message Throughput (1,000 msgs)
    # ------------------------------------------------------------------
    bus = mgr.bus
    for name in ["ArchitectureAgent", "BackendAgent", "FrontendAgent", "TestingAgent"]:
        bus.register_agent(name)

    t0 = time.perf_counter()
    for i in range(1000):
        msg = AgentMessage(
            sender="BackendAgent",
            receiver="TestingAgent" if i % 2 == 0 else "ArchitectureAgent",
            message_type=MessageType.REVIEW,
            payload={"iteration": i, "data": "benchmark_payload"},
            task_id=f"task_{i % 20}",
        )
        bus.send_message(msg)
    t_msg = time.perf_counter() - t0
    msg_throughput = 1000 / t_msg
    results["bus_1000_msgs_sec"] = round(t_msg, 4)
    results["bus_throughput_msgs_per_sec"] = round(msg_throughput, 1)

    print(f"[2/5] CommunicationBus Message Throughput (1,000 msgs): {t_msg*1000:.2f}ms ({msg_throughput:.1f} msgs/sec)")

    # ------------------------------------------------------------------
    # Benchmark 3: Consensus Engine Strategy Evaluation (500 Rounds)
    # ------------------------------------------------------------------
    engine = mgr.consensus_engine
    proposals = [
        Proposal(proposal_id="p1", proposer="ArchitectureAgent", role=AgentRole.ARCHITECTURE, title="Option A", confidence=0.85),
        Proposal(proposal_id="p2", proposer="SecurityAgent", role=AgentRole.SECURITY, title="Option B", confidence=0.92),
        Proposal(proposal_id="p3", proposer="BackendAgent", role=AgentRole.BACKEND, title="Option C", confidence=0.88),
    ]

    t0 = time.perf_counter()
    for i in range(500):
        strategy = [ConsensusStrategy.WEIGHTED, ConsensusStrategy.SECURITY_FIRST, ConsensusStrategy.ARCHITECTURE_FIRST, ConsensusStrategy.MAJORITY][i % 4]
        engine.reach_consensus(topic=f"Dispute {i}", proposals=proposals, strategy=strategy)
    t_cons = time.perf_counter() - t0
    cons_throughput = 500 / t_cons
    results["consensus_500_rounds_sec"] = round(t_cons, 4)
    results["consensus_throughput_rounds_per_sec"] = round(cons_throughput, 1)

    print(f"[3/5] Consensus Strategy Engine (500 rounds): {t_cons*1000:.2f}ms ({cons_throughput:.1f} rounds/sec)")

    # ------------------------------------------------------------------
    # Benchmark 4: Shared Workspace Concurrent Locking & Staging (200 ops)
    # ------------------------------------------------------------------
    ws = mgr.workspace
    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        def lock_stage(idx):
            fpath = f"src/module_{idx % 10}.py"
            lock = ws.acquire_lock(fpath, holder=f"Worker_{idx}", role=AgentRole.BACKEND, is_exclusive=False)
            ws.stage_change(fpath, f"Code content for worker {idx}", author_id=f"Worker_{idx}")
            ws.release_lock(fpath, holder=f"Worker_{idx}")
            return True

        futures = [executor.submit(lock_stage, i) for i in range(200)]
        for f in concurrent.futures.as_completed(futures):
            f.result()
    t_ws = time.perf_counter() - t0
    ws_throughput = 200 / t_ws
    results["workspace_200_lock_stage_ops_sec"] = round(t_ws, 4)
    results["workspace_throughput_ops_per_sec"] = round(ws_throughput, 1)

    print(f"[4/5] Shared Workspace Concurrent Locks & Staging (200 ops): {t_ws*1000:.2f}ms ({ws_throughput:.1f} ops/sec)")

    # ------------------------------------------------------------------
    # Benchmark 5: Full 8-Agent Software Engineering Lifecycle Cycle
    # ------------------------------------------------------------------
    full_mgr = CollaborationManager(CollaborationConfig(max_parallel_agents=8))
    for ag in [ArchitectureAgent(), BackendAgent(), FrontendAgent(), TestingAgent(), SecurityAgent(), PerformanceAgent(), DocumentationAgent(), ReleaseAgent()]:
        full_mgr.register_agent(ag)

    cycle_tasks = [
        TaskAssignment(task_id="c_arch", title="System Architecture Specification", required_skills=["architecture"]),
        TaskAssignment(task_id="c_back", title="Implement REST API Service", required_skills=["backend", "api"], dependencies=["c_arch"]),
        TaskAssignment(task_id="c_front", title="Implement UI Components", required_skills=["frontend", "ui"], dependencies=["c_arch"]),
        TaskAssignment(task_id="c_test", title="Author Unit & Integration Tests", required_skills=["testing"], dependencies=["c_back", "c_front"]),
        TaskAssignment(task_id="c_sec", title="Security Vulnerability Audit", required_skills=["security"], dependencies=["c_back"]),
        TaskAssignment(task_id="c_perf", title="Performance & Caching Optimization", required_skills=["performance"], dependencies=["c_back"]),
        TaskAssignment(task_id="c_doc", title="Document API & Architecture", required_skills=["docs"], dependencies=["c_test"]),
        TaskAssignment(task_id="c_rel", title="Package & Release Manifest", required_skills=["release"], dependencies=["c_doc"]),
    ]
    t0 = time.perf_counter()
    full_mgr.submit_tasks(cycle_tasks)
    cycle_summary = full_mgr.execute_multi_agent_cycle(max_workers=8)
    t_cycle = time.perf_counter() - t0
    results["full_8_agent_cycle_sec"] = round(t_cycle, 4)
    results["cycle_status"] = cycle_summary["status"]
    results["collaboration_efficiency"] = cycle_summary["metrics"]["collaboration_efficiency"]

    print(f"[5/5] Full 8-Agent Organization Execution Cycle: {t_cycle*1000:.2f}ms (Efficiency: {results['collaboration_efficiency']})")
    print("=" * 70)
    print("All benchmarks completed successfully.")
    print("=" * 70)

    return results


if __name__ == "__main__":
    run_v28_benchmarks()
