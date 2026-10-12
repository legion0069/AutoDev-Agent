"""
test_global_metrics.py - Unit Tests for GlobalMetricsCalculator (AutoDev Version 3.5)
"""

import pytest

from core.global_metrics import GlobalEnterpriseDashboard, GlobalMetricsCalculator


def test_metrics_calculator_empty():
    calc = GlobalMetricsCalculator(enterprise_name="Test Enterprise")
    dash = calc.calculate_global_dashboard(companies={})
    assert dash.enterprise_name == "Test Enterprise"
    assert dash.total_companies == 0
    assert dash.enterprise_health_score == 95.0
    assert dash.enterprise_security_score == 100.0


def test_metrics_calculator_multi_company_aggregation():
    calc = GlobalMetricsCalculator()

    companies = {
        "COMP-A": {
            "company_name": "Alpha Corp",
            "status": "ACTIVE",
            "health_score": 90.0,
            "allocated_budget_usd": 1000000.0,
            "spent_budget_usd": 200000.0,
            "headcount": 100,
            "velocity": 30.0,
            "technical_debt_hours": 15.0,
        },
        "COMP-B": {
            "company_name": "Beta Corp",
            "status": "ACTIVE",
            "health_score": 96.0,
            "allocated_budget_usd": 2000000.0,
            "spent_budget_usd": 500000.0,
            "headcount": 150,
            "velocity": 45.0,
            "technical_debt_hours": 10.0,
        },
    }

    portfolio_summary = {
        "total_projects": 10,
        "active_projects": 8,
        "average_delivery_confidence": 0.92,
    }

    security_dashboard = {
        "quarantined_companies": [],
        "audit_chain_valid": True,
        "known_threats_count": 0,
    }

    knowledge_analytics = {
        "total_nodes": 50,
        "total_reuses": 120,
        "nodes_by_category": {"RESEARCH": 5},
    }

    dash = calc.calculate_global_dashboard(
        companies=companies,
        portfolio_summary=portfolio_summary,
        security_dashboard=security_dashboard,
        knowledge_analytics=knowledge_analytics,
    )

    assert dash.total_companies == 2
    assert dash.active_companies == 2
    assert dash.consolidated_velocity == 75.0
    assert dash.enterprise_health_score == 93.0  # (90 + 96) / 2
    assert dash.enterprise_security_score == 100.0
    assert dash.total_allocated_budget_usd == 3000000.0
    assert dash.total_spent_budget_usd == 700000.0
    assert dash.net_budget_variance_usd == 2300000.0
    assert dash.total_technical_debt_hours == 25.0
    assert dash.knowledge_reuse_rate_pct == 240.0  # 120 / 50 * 100
    assert dash.innovation_score > 80.0
    assert dash.global_delivery_confidence > 0.85
    assert "Alpha Corp" in dash.company_breakdown["COMP-A"]["company_name"]


def test_security_penalty_on_quarantine():
    calc = GlobalMetricsCalculator()
    companies = {"C1": {"health_score": 90.0, "status": "ACTIVE"}}

    sec_compromised = {
        "quarantined_companies": ["C2"],
        "audit_chain_valid": True,
        "known_threats_count": 1,
    }
    dash = calc.calculate_global_dashboard(companies=companies, security_dashboard=sec_compromised)
    # 100 - (1*25) - (1*10) = 65.0
    assert dash.enterprise_security_score == 65.0
