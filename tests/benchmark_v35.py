"""
benchmark_v35.py - Performance Benchmark Suite for AutoDev Version 3.5
Autonomous Enterprise Ecosystem (Federation of AI Companies)
"""

import json
import os
import sys
import time

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cross_company_scheduler import CrossCompanyScheduler
from core.enterprise_federation import EnterpriseFederation
from core.enterprise_governance import EnterpriseGovernanceManager
from core.enterprise_knowledge import EnterpriseKnowledgeGraph, KnowledgeCategory, RelationshipType
from core.enterprise_policy_engine import EnterprisePolicyEngine, PolicyDomain
from core.enterprise_registry import EnterpriseRegistry
from core.enterprise_router import EnterpriseRouter
from core.enterprise_security import EnterpriseSecurityManager
from core.inter_company_bus import FederationMessage, FederationMessagePriority, InterCompanyBus
from core.resource_marketplace import ResourceMarketplace, ResourceType


def benchmark_inter_company_bus(num_messages: int = 10000) -> dict:
    bus = InterCompanyBus()
    for i in range(10):
        bus.register_company(f"COMP-{i}")

    t0 = time.perf_counter()
    for i in range(num_messages):
        src = f"COMP-{i % 10}"
        tgt = f"COMP-{(i + 1) % 10}"
        bus.send_message(FederationMessage(
            company_id=src,
            target_company_id=tgt,
            priority=FederationMessagePriority.NORMAL,
            payload={"counter": i},
        ))
    elapsed = max(1e-6, time.perf_counter() - t0)
    throughput = num_messages / elapsed
    return {
        "operation": "Inter-Company Bus Throughput",
        "iterations": num_messages,
        "elapsed_sec": round(elapsed, 4),
        "throughput_msgs_per_sec": round(throughput, 2),
        "latency_us_per_msg": round((elapsed / num_messages) * 1e6, 2),
    }


def benchmark_router_latency(num_messages: int = 5000) -> dict:
    bus = InterCompanyBus()
    reg = EnterpriseRegistry()
    router = EnterpriseRouter(bus=bus, registry=reg)

    for i in range(5):
        cid = f"COMP-{i}"
        reg.register_company(cid, f"Company {i}", "Domain")
        bus.register_company(cid)
        router.allow_all_traffic(cid)

    messages = [
        FederationMessage(
            company_id=f"COMP-{i % 5}",
            target_company_id=f"COMP-{(i + 1) % 5}",
            payload={"msg_index": i},
        )
        for i in range(num_messages)
    ]

    t0 = time.perf_counter()
    for msg in messages:
        router.route_message(msg)
    elapsed = max(1e-6, time.perf_counter() - t0)
    return {
        "operation": "Enterprise Router Evaluation",
        "iterations": num_messages,
        "elapsed_sec": round(elapsed, 4),
        "throughput_ops_per_sec": round(num_messages / elapsed, 2),
        "latency_us_per_op": round((elapsed / num_messages) * 1e6, 2),
    }


def benchmark_security_tokens(num_tokens: int = 5000) -> dict:
    sec = EnterpriseSecurityManager()
    tokens = []

    t0 = time.perf_counter()
    for i in range(num_tokens):
        ident = sec.create_identity(f"COMP-{i%10}", "ENG", f"Role-{i}", clearance_level="CONFIDENTIAL")
        tokens.append(ident.token)
    gen_elapsed = max(1e-6, time.perf_counter() - t0)

    t1 = time.perf_counter()
    for tok in tokens:
        sec.validate_token(tok)
    val_elapsed = max(1e-6, time.perf_counter() - t1)

    return {
        "operation": "Federated IAM Token Issuance & Verification",
        "iterations": num_tokens,
        "token_generation_rate_per_sec": round(num_tokens / gen_elapsed, 2),
        "token_validation_rate_per_sec": round(num_tokens / val_elapsed, 2),
        "total_elapsed_sec": round(gen_elapsed + val_elapsed, 4),
    }


def benchmark_marketplace_matching(num_pairs: int = 2500) -> dict:
    mkt = ResourceMarketplace()

    t0 = time.perf_counter()
    for i in range(num_pairs):
        mkt.place_ask(f"SELLER-{i%10}", ResourceType.GPU_ALLOCATION, units=10.0, price_per_unit_usd=100.0)
        mkt.place_bid(f"BUYER-{i%10}", ResourceType.GPU_ALLOCATION, units=10.0, max_price_per_unit_usd=110.0)
    elapsed = max(1e-6, time.perf_counter() - t0)

    summary = mkt.get_marketplace_summary()
    return {
        "operation": "Resource Marketplace Double-Auction Matching",
        "order_pairs_placed": num_pairs,
        "trades_settled": summary["total_settled_trades"],
        "transacted_volume_usd": summary["total_transacted_volume_usd"],
        "elapsed_sec": round(elapsed, 4),
        "trades_per_sec": round(summary["total_settled_trades"] / elapsed, 2),
    }


def benchmark_cpm_scheduler(num_iterations: int = 100) -> dict:
    t0 = time.perf_counter()
    for _ in range(num_iterations):
        sched = CrossCompanyScheduler()
        sched.add_task("ROOT", "C1", "Root", 10.0)
        for b in range(5):
            prev = "ROOT"
            for s in range(4):
                tid = f"B{b}_S{s}"
                sched.add_task(tid, f"C{b}", f"Step {s}", 2.0, dependencies=[prev])
                prev = tid
        branch_ends = [f"B{b}_S3" for b in range(5)]
        sched.add_task("END", "C0", "End", 5.0, dependencies=branch_ends)
        sched.compute_critical_path()
    elapsed = max(1e-6, time.perf_counter() - t0)

    return {
        "operation": "Critical Path Method (CPM) DAG Computation",
        "dag_evaluations": num_iterations,
        "tasks_per_dag": 22,
        "elapsed_sec": round(elapsed, 4),
        "dags_computed_per_sec": round(num_iterations / elapsed, 2),
        "latency_ms_per_dag": round((elapsed / num_iterations) * 1e3, 3),
    }


def benchmark_knowledge_graph(num_nodes: int = 1000) -> dict:
    kg = EnterpriseKnowledgeGraph()
    t0 = time.perf_counter()
    node_ids = []
    for i in range(num_nodes):
        n = kg.add_knowledge_node(
            category=KnowledgeCategory.ADR,
            title=f"Architecture Decision Record {i}",
            content=f"Decision details regarding database sharding and caching for partition {i}",
            company_id=f"COMP-{i%8}",
            author="Architect",
            tags=[f"tag-{i%10}", "database", "sharding"],
        )
        node_ids.append(n.node_id)
        if i > 0:
            kg.link_nodes(node_ids[i-1], n.node_id, RelationshipType.EXTENDS)
    pop_elapsed = max(1e-6, time.perf_counter() - t0)

    t1 = time.perf_counter()
    for _ in range(500):
        kg.search("database sharding")
    search_elapsed = max(1e-6, time.perf_counter() - t1)

    return {
        "operation": "Enterprise Knowledge Graph Search & Traversal",
        "nodes_indexed": num_nodes,
        "population_time_sec": round(pop_elapsed, 4),
        "searches_per_sec": round(500 / search_elapsed, 2),
        "latency_us_per_search": round((search_elapsed / 500) * 1e6, 2),
    }


def benchmark_policy_evaluations(num_evals: int = 10000) -> dict:
    gov = EnterpriseGovernanceManager()
    clean_ctx = {
        "budget_spent": 50000,
        "budget_allocated": 100000,
        "dependencies": ["python-std-lib"],
        "has_eval_or_exec": False,
        "critical_cves_count": 0,
        "qa_pass_rate_pct": 99.0,
        "has_api_docs": True,
    }

    t0 = time.perf_counter()
    for _ in range(num_evals):
        gov.audit_target("COMP-A", "COMPANY", clean_ctx)
    elapsed = max(1e-6, time.perf_counter() - t0)

    return {
        "operation": "Enterprise Governance Policy Audit",
        "evaluations": num_evals,
        "elapsed_sec": round(elapsed, 4),
        "evaluations_per_sec": round(num_evals / elapsed, 2),
        "latency_us_per_eval": round((elapsed / num_evals) * 1e6, 2),
    }


def benchmark_cross_company_collaboration_pipeline() -> dict:
    fed = EnterpriseFederation()

    t0 = time.perf_counter()
    result = fed.execute_cross_company_ai_collaboration(
        algorithm_name="ZeroCopyFederation-v35",
        expected_business_impact_usd=10000000.0,
    )
    elapsed = max(1e-6, time.perf_counter() - t0)

    return {
        "operation": "End-to-End Cross-Company AI Collaboration Pipeline",
        "pipeline_status": result["overall_status"],
        "steps_executed": len(result),
        "elapsed_ms": round(elapsed * 1000, 3),
    }


def benchmark_ecosystem_simulation(num_cycles: int = 10) -> dict:
    fed = EnterpriseFederation()

    t0 = time.perf_counter()
    sim_res = fed.simulate_ecosystem(
        num_cycles=num_cycles,
        messages_per_cycle=50,
        trade_resources=True,
    )
    elapsed = max(1e-6, time.perf_counter() - t0)

    return {
        "operation": "Multi-Company Discrete Ecosystem Simulation",
        "cycles_executed": num_cycles,
        "total_messages": sim_res["total_messages_routed"],
        "elapsed_sec": round(elapsed, 4),
        "cycles_per_sec": round(num_cycles / elapsed, 2),
        "messages_per_sec": round(sim_res["total_messages_routed"] / elapsed, 2),
    }


def run_all_benchmarks():
    print("=" * 75)
    print("      AUTODEV VERSION 3.5 — ENTERPRISE FEDERATION BENCHMARK SUITE")
    print("=" * 75)

    benchmarks = {
        "inter_company_bus": benchmark_inter_company_bus(10000),
        "router_latency": benchmark_router_latency(5000),
        "security_tokens": benchmark_security_tokens(5000),
        "marketplace_matching": benchmark_marketplace_matching(2500),
        "cpm_scheduler": benchmark_cpm_scheduler(100),
        "knowledge_graph": benchmark_knowledge_graph(1000),
        "policy_evaluations": benchmark_policy_evaluations(10000),
        "collaboration_pipeline": benchmark_cross_company_collaboration_pipeline(),
        "ecosystem_simulation": benchmark_ecosystem_simulation(10),
    }

    for name, res in benchmarks.items():
        print(f"\n[*] {res['operation']}")
        for k, v in res.items():
            if k != "operation":
                print(f"    - {k}: {v}")

    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "benchmark_results_v35.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(benchmarks, f, indent=2)

    print("\n" + "=" * 75)
    print(f"Benchmark results successfully saved to: {output_path}")
    print("=" * 75)
    return benchmarks


if __name__ == "__main__":
    run_all_benchmarks()
