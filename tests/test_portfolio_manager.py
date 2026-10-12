"""
test_portfolio_manager.py - Unit Tests for PortfolioManager (AutoDev Version 3.5)
"""

import pytest

from core.portfolio_manager import (
    PortfolioManager,
    PortfolioProject,
    ProjectStatus,
)


def test_portfolio_manager_initialization():
    pm = PortfolioManager()
    dash = pm.get_portfolio_dashboard()
    assert dash["total_projects"] == 0
    assert dash["active_projects"] == 0


def test_create_portfolio_project():
    pm = PortfolioManager()
    proj = pm.create_project(
        title="Enterprise Neural Search",
        lead_company_id="COMP-A",
        participating_companies=["COMP-A", "COMP-C"],
        strategic_theme="AI Modernization",
        estimated_roi=4.5,
        business_value=90.0,
        strategic_alignment=95.0,
        risk_score=15.0,
        budget_usd=300000.0,
        milestones_total=4,
    )
    assert proj.project_id.startswith("PRJ-")
    assert proj.lead_company_id == "COMP-A"
    assert proj.budget_variance_usd == 300000.0  # 300k - 0 spent
    assert proj.cost_performance_index == 1.0


def test_update_project_progress_and_completion():
    pm = PortfolioManager()
    proj = pm.create_project(
        title="Payment Modernization",
        lead_company_id="COMP-A",
        budget_usd=100000.0,
        milestones_total=2,
    )

    # Complete 1 milestone and spend 40,000
    pm.update_progress(
        project_id=proj.project_id,
        milestones_completed=1,
        spent_budget_usd=40000.0,
        days_elapsed=15.0,
        delivery_confidence=0.90,
        status=ProjectStatus.ACTIVE,
    )
    assert proj.milestones_completed == 1
    assert proj.budget_variance_usd == 60000.0
    # Earned value = (1/2)*100k = 50k. CPI = 50k / 40k = 1.25
    assert proj.cost_performance_index == 1.25

    # Complete 2nd milestone
    pm.update_progress(
        project_id=proj.project_id,
        milestones_completed=2,
    )
    assert proj.status == ProjectStatus.COMPLETED


def test_auto_flag_at_risk_projects():
    pm = PortfolioManager()
    proj = pm.create_project("High Risk Migration", "COMP-A", budget_usd=50000.0)

    # Deliver confidence drops to 0.50
    pm.update_progress(proj.project_id, delivery_confidence=0.50, status=ProjectStatus.ACTIVE)
    assert proj.status == ProjectStatus.AT_RISK


def test_ranked_portfolio_by_priority():
    pm = PortfolioManager()
    p1 = pm.create_project("Low Priority", "COMP-A", business_value=30.0, strategic_alignment=40.0, risk_score=50.0)
    p2 = pm.create_project("High Priority Strategic", "COMP-A", business_value=95.0, strategic_alignment=98.0, risk_score=10.0)

    ranked = pm.get_ranked_portfolio()
    assert len(ranked) == 2
    assert ranked[0].project_id == p2.project_id
    assert ranked[1].project_id == p1.project_id


def test_portfolio_dashboard_aggregation():
    pm = PortfolioManager()
    pm.create_project("Project Alpha", "COMP-A", budget_usd=200000.0, estimated_roi=3.0)
    pm.create_project("Project Beta", "COMP-B", budget_usd=400000.0, estimated_roi=2.0)

    dash = pm.get_portfolio_dashboard()
    assert dash["total_projects"] == 2
    assert dash["total_allocated_budget_usd"] == 600000.0
    assert dash["average_roi_multiplier"] == 2.5
    # (200k * 3) + (400k * 2) = 600k + 800k = $1.4M
    assert dash["expected_portfolio_return_usd"] == 1400000.0
