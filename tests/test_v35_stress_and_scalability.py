"""
test_v35_stress_and_scalability.py - Stress & High-Concurrency Scalability Tests (AutoDev Version 3.5)
"""

import concurrent.futures
import threading
import time
import pytest

from core.cross_company_scheduler import CrossCompanyScheduler
from core.enterprise_knowledge import EnterpriseKnowledgeGraph, KnowledgeCategory, RelationshipType
from core.enterprise_registry import EnterpriseRegistry
from core.enterprise_security import EnterpriseSecurityManager
from core.inter_company_bus import FederationMessage, InterCompanyBus
from core.resource_marketplace import ResourceMarketplace, ResourceType


def test_concurrent_message_bus_throughput():
    bus = InterCompanyBus()
    for i in range(10):
        bus.register_company(f"COMP-{i}")

    num_threads = 10
    messages_per_thread = 50
    total_messages = num_threads * messages_per_thread

    def worker(thread_idx: int):
        src = f"COMP-{thread_idx % 10}"
        tgt = f"COMP-{(thread_idx + 1) % 10}"
        for m in range(messages_per_thread):
            msg = FederationMessage(
                company_id=src,
                target_company_id=tgt,
                payload={"thread": thread_idx, "idx": m},
            )
            bus.send_message(msg)

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        concurrent.futures.wait(futures)

    dur = max(0.0001, time.time() - t0)
    telemetry = bus.get_bus_telemetry()
    assert telemetry["total_routed_messages"] == total_messages
    throughput = total_messages / dur
    assert throughput > 500  # Should easily handle > 500 msgs/sec in pure python


def test_concurrent_marketplace_matching():
    mkt = ResourceMarketplace()
    num_orders = 100

    def place_asks():
        for i in range(num_orders):
            mkt.place_ask(f"SELLER-{i%5}", ResourceType.GPU_ALLOCATION, units=10.0, price_per_unit_usd=100.0 + (i % 20))

    def place_bids():
        for i in range(num_orders):
            mkt.place_bid(f"BUYER-{i%5}", ResourceType.GPU_ALLOCATION, units=10.0, max_price_per_unit_usd=120.0 + (i % 20))

    t1 = threading.Thread(target=place_asks)
    t2 = threading.Thread(target=place_bids)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    summary = mkt.get_marketplace_summary()
    assert summary["total_orders_placed"] == 200
    assert summary["total_settled_trades"] > 0
    assert summary["total_transacted_volume_usd"] > 0


def test_large_knowledge_graph_traversal():
    kg = EnterpriseKnowledgeGraph()
    # Create chain of 50 nodes
    node_ids = []
    for i in range(50):
        n = kg.add_knowledge_node(
            category=KnowledgeCategory.PATTERN,
            title=f"Enterprise Architecture Pattern {i:03d}",
            content=f"Pattern specification for microservice decomposition stage {i}",
            company_id="COMP-A",
            author="Architect",
            tags=[f"tag-{i % 5}", "pattern", "scalability"],
        )
        node_ids.append(n.node_id)

    # Link in a directed chain
    for i in range(49):
        kg.link_nodes(node_ids[i], node_ids[i + 1], RelationshipType.EXTENDS)

    # Search query across 50 nodes
    results = kg.search("microservice decomposition")
    assert len(results) >= 20

    # Shortest path between node 0 and node 49
    path = kg.find_path(node_ids[0], node_ids[49])
    assert path is not None
    assert len(path) == 50
    assert path[0] == node_ids[0]
    assert path[-1] == node_ids[49]


def test_concurrent_security_token_generation_and_validation():
    sec = EnterpriseSecurityManager()
    tokens = []
    lock = threading.Lock()

    def generate_and_check(worker_id: int):
        for i in range(30):
            ident = sec.create_identity(f"COMP-{worker_id}", "ENG", f"Role-{i}", clearance_level="CONFIDENTIAL", permissions=["read:data"])
            val = sec.validate_token(ident.token)
            assert val is not None
            with lock:
                tokens.append(ident.token)

    threads = [threading.Thread(target=generate_and_check, args=(w,)) for w in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(tokens) == 150
    assert sec.verify_audit_chain_integrity() is True


def test_large_dependency_dag_critical_path():
    sched = CrossCompanyScheduler()
    # Build 100-task tree
    sched.add_task("ROOT", "COMP-A", "Root Foundation", 10.0)

    # 10 parallel branches of 5 tasks each
    for branch in range(10):
        prev = "ROOT"
        for step in range(5):
            tid = f"B{branch}_S{step}"
            sched.add_task(tid, f"COMP-{branch%3}", f"Branch {branch} Step {step}", duration_hours=float(step + 1), dependencies=[prev])
            prev = tid

    # Merge all branches into END task
    branch_ends = [f"B{b}_S4" for b in range(10)]
    sched.add_task("END", "COMP-FINISH", "Global Completion", 5.0, dependencies=branch_ends)

    res = sched.compute_critical_path()
    assert res["total_tasks_scheduled"] == 52  # 1 root + 50 branch steps + 1 end
    assert "ROOT" in res["critical_path_tasks"]
    assert "END" in res["critical_path_tasks"]
    assert res["total_project_duration_hours"] > 0
