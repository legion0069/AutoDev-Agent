"""
benchmark_v30.py - Production Scalability & Performance Benchmarks for AutoDev Enterprise Company (v3.0)

Measures throughput, latency, and scalability across all autonomous corporate subsystems:
- Executive Decision Engine (Consensus & Veto throughput)
- Product Management (RICE prioritization & story generation)
- Architecture Review Board (9-pillar evaluation & ADR generation)
- Sprint Planning & Velocity Execution (Sprint cycles/sec)
- HR Hiring & Performance Review Engine (Candidates/sec)
- Financial Multi-Quarter Ledger & Runway Analytics (Transactions/sec)
- Support Center Incident & Ticket Routing Engine (Tickets/sec)
- Enterprise Company Brain (Knowledge Indexing & Full-text search)
- Discrete-Event Company Simulator (1, 2, 5, 10 Year Scale)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.enterprise import (
    ArchitectureBoard,
    ArchitectureScorecard,
    BusinessAnalytics,
    CompanyBrain,
    CompanySimulator,
    ComplianceStandard,
    DecisionStatus,
    DepartmentType,
    DoraMetrics,
    EngineeringManager,
    EnterpriseCompany,
    ExecutiveDecisionEngine,
    ExecutiveRole,
    ExpenseCategory,
    FinanceManager,
    GovernanceManager,
    HiringManager,
    KnowledgeCategory,
    OrganizationGraph,
    PriorityLevel,
    ProductManager,
    ProductVision,
    ReleaseStage,
    ReleaseTrain,
    SprintManager,
    SupportCenter,
    TeamType,
    TicketPriority,
    TicketType,
)


def run_v30_benchmarks() -> dict:
    print("=" * 80)
    print("      AUTODEV VERSION 3.0 - AUTONOMOUS AI ENTERPRISE BENCHMARKS")
    print("=" * 80)

    results = {}

    # 1. Executive Decision Engine Consensus Throughput
    print("\n[Benchmark 1] Executive Decision Engine Consensus Throughput...")
    exec_engine = ExecutiveDecisionEngine()
    num_proposals = 2000
    t0 = time.time()
    for i in range(num_proposals):
        prop = exec_engine.propose_decision(
            title=f"Strategic Initiative #{i}",
            description="Automated enterprise scaling initiative",
            proposer_role=ExecutiveRole.VP_PRODUCT,
            budget_impact_usd=25000.0,
            risk_score=15.0,
            strategic_alignment_score=95.0,
        )
        exec_engine.signoff_decision(prop.decision_id, role=ExecutiveRole.CEO, approved=True)
        exec_engine.signoff_decision(prop.decision_id, role=ExecutiveRole.CTO, approved=True)
        exec_engine.signoff_decision(prop.decision_id, role=ExecutiveRole.DIRECTOR_FINANCE, approved=True)
    decision_time = time.time() - t0
    decision_rate = num_proposals / decision_time
    print(f"  - Proposal & Voting Throughput : {decision_rate:,.1f} decisions/sec ({decision_time*1000:.2f} ms for {num_proposals} full cycles)")
    results["executive_decision_rate"] = decision_rate

    # 2. Product Management RICE Prioritization & Story Breakdown Throughput
    print("\n[Benchmark 2] Product Management RICE Ranking & Story Generation...")
    pm = ProductManager()
    num_epics = 500
    t0 = time.time()
    for i in range(num_epics):
        epic = pm.create_epic(
            title=f"Enterprise Scalability Module {i}",
            description="High performance distributed synchronization",
            strategic_theme="Scalability & Reliability",
            target_quarter="2026-Q3",
            estimated_roi_multiplier=4.0,
        )
        feat = pm.create_feature(
            epic_id=epic.epic_id,
            name=f"Cluster Lock Sharding {i}",
            description="Automated lock distribution across nodes",
            reach=1000,
            impact=3.0,
            confidence=0.9,
            effort=2.0,
        )
        pm.create_user_story(
            feature_id=feat.feature_id,
            title=f"As a platform engineer, I want sharded locks {i}",
            user_role="Platform Engineer",
            action="acquire distributed sharded mutexes",
            benefit="throughput scales linearly across cluster nodes",
            story_points=5,
            priority=PriorityLevel.HIGH,
        )
    prioritized = pm.prioritize_backlog_rice()
    pm_time = time.time() - t0
    pm_rate = (num_epics * 3) / pm_time
    print(f"  - Product Entity Breakdown Rate : {pm_rate:,.1f} entities/sec ({pm_time*1000:.2f} ms for {num_epics*3} entities, {len(prioritized)} stories ranked)")
    results["product_breakdown_rate"] = pm_rate

    # 3. Architecture Review Board 9-Pillar Scoring Throughput
    print("\n[Benchmark 3] Architecture Review Board 9-Pillar Scoring...")
    arb = ArchitectureBoard()
    num_evals = 2000
    t0 = time.time()
    for i in range(num_evals):
        scorecard = ArchitectureScorecard(
            solid_score=92.0,
            ddd_score=90.0,
            layering_score=95.0,
            scalability_score=98.0,
            security_score=99.0,
            performance_score=96.0,
            maintainability_score=91.0,
            complexity_penalty=5.0,
            testability_score=94.0,
        )
        arb.submit_proposal(
            title=f"Microkernel Architecture ADR {i}",
            author="Lead Architect",
            system_component="EnterpriseCore",
            changes_summary="Pure decoupled modularity",
            adr_markdown=f"# ADR-{i}: Microkernel Architecture\nDecoupled domain layers.",
            scorecard=scorecard,
        )
    arb_time = time.time() - t0
    arb_rate = num_evals / arb_time
    print(f"  - Architecture Evaluation Rate : {arb_rate:,.1f} evals/sec ({arb_time*1000:.2f} ms for {num_evals} scorecards)")
    results["architecture_eval_rate"] = arb_rate

    # 4. Financial Ledger Multi-Transaction Throughput
    print("\n[Benchmark 4] Financial Multi-Category Ledger & Runway Analytics...")
    fm = FinanceManager(initial_cash_reserve_usd=50000000.0)
    fm.create_quarterly_budget(
        quarter="Q1",
        year=2026,
        category_limits_usd={c.value: 2000000.0 for c in ExpenseCategory},
    )
    num_tx = 10000
    t0 = time.time()
    for i in range(num_tx):
        fm.record_expense(
            category=ExpenseCategory.INFRASTRUCTURE_CLOUD,
            amount_usd=150.0,
            description=f"Compute Node Instance #{i}",
            department=DepartmentType.DEVOPS,
            quarter_key="2026-Q1",
        )
    runway = fm.calculate_runway_months(monthly_burn_usd=500000.0)
    total_spent = fm.get_total_spend_usd()
    fm_time = time.time() - t0
    fm_rate = num_tx / fm_time
    print(f"  - Ledger Transaction Rate     : {fm_rate:,.1f} tx/sec ({fm_time*1000:.2f} ms for {num_tx} entries)")
    print(f"  - Total Spent / Runway        : ${total_spent:,.2f} spent | {runway:.1f} months runway remaining")
    results["financial_tx_rate"] = fm_rate

    # 5. Support Center SLA Engine & Ticket Ingestion
    print("\n[Benchmark 5] Support Center SLA Routing & Resolution Throughput...")
    sc = SupportCenter()
    num_tickets = 5000
    t0 = time.time()
    for i in range(num_tickets):
        tick = sc.submit_ticket(
            customer_id=f"cust_{i % 200}",
            ticket_type=TicketType.BUG_REPORT if i % 2 == 0 else TicketType.INCIDENT,
            priority=TicketPriority.P1_HIGH if i % 5 == 0 else TicketPriority.P2_MEDIUM,
            title=f"Automated Service Query {i}",
            description="High load latency check",
        )
        sc.resolve_ticket(
            ticket_id=tick.ticket_id,
            resolution_notes="Auto-scaled connection pool",
            csat_score=5,
        )
    sc_time = time.time() - t0
    sc_rate = (num_tickets * 2) / sc_time
    print(f"  - Ticket Ingestion & Resolution : {sc_rate:,.1f} tickets/sec ({sc_time*1000:.2f} ms for {num_tickets*2} operations)")
    results["support_ticket_rate"] = sc_rate

    # 6. Company Brain Knowledge Indexing & Full-Text Search
    print("\n[Benchmark 6] Company Brain Knowledge Indexing & Tagged Retrieval...")
    brain = CompanyBrain()
    num_kb = 3000
    t0 = time.time()
    for i in range(num_kb):
        brain.store_knowledge(
            title=f"Architecture Pattern {i}: Event Bus Optimization",
            category=KnowledgeCategory.ARCHITECTURE_ADR,
            content=f"Detailed specifications for asynchronous event broker distribution across cluster node {i}.",
            tags=["async", "cluster", "performance", f"node_{i % 10}"],
            author="Principal Architect",
            department=DepartmentType.ENGINEERING,
        )
    index_time = time.time() - t0
    index_rate = num_kb / index_time

    t1 = time.time()
    num_queries = 1000
    for i in range(num_queries):
        res = brain.search_knowledge(query="event broker distribution", category=KnowledgeCategory.ARCHITECTURE_ADR)
    search_time = time.time() - t1
    search_rate = num_queries / search_time

    print(f"  - KB Article Indexing Rate    : {index_rate:,.1f} articles/sec ({index_time*1000:.2f} ms for {num_kb} articles)")
    print(f"  - KB Search Retrieval Rate    : {search_rate:,.1f} queries/sec ({search_time*1000:.2f} ms for {num_queries} queries)")
    results["brain_indexing_rate"] = index_rate
    results["brain_search_rate"] = search_rate

    # 7. Discrete-Event Company Simulator Multi-Year Scalability
    print("\n[Benchmark 7] Discrete-Event Company Multi-Year Simulation Scalability...")
    print(f"  {'Years Simulated':<16} | {'Quarters':<10} | {'Duration (s)':<14} | {'Speed (Quarters/s)':<20} | {'Total Spending ($)':<20}")
    print("  " + "-" * 88)

    sim_scales = [1, 2, 5, 10]
    sim_metrics = []

    for num_years in sim_scales:
        company = EnterpriseCompany(company_name=f"AutoDev Benchmark Corp ({num_years}Y)")
        t0 = time.time()
        for y_idx in range(num_years):
            year = 2026 + y_idx
            res = company.simulator.simulate_year(year)
        duration = time.time() - t0
        total_quarters = num_years * 4
        q_rate = total_quarters / duration
        total_spending = company.finance_mgr.get_total_spend_usd()

        print(f"  {num_years:<16} | {total_quarters:<10} | {duration:<14.3f} | {q_rate:<20.1f} | ${total_spending:<19,.2f}")
        sim_metrics.append({
            "years": num_years,
            "quarters": total_quarters,
            "duration_s": duration,
            "quarters_per_sec": q_rate,
            "spending_usd": total_spending,
        })
    results["simulation_metrics"] = sim_metrics

    # 8. Summary
    print("\n" + "=" * 80)
    print("               AUTODEV V3.0 BENCHMARK SUITE COMPLETED SUCCESSFULLY")
    print("=" * 80)

    # Save benchmark results to JSON
    out_path = Path(__file__).resolve().parent / "benchmark_results_v30.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Benchmark results saved to: {out_path}\n")

    return results


if __name__ == "__main__":
    run_benchmarks = run_v30_benchmarks()
