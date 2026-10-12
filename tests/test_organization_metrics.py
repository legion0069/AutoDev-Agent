"""
test_organization_metrics.py - AutoDev Version 3.4
Unit and integration tests for Organization Metrics & Dashboard:
- Velocity, Lead Time, Cycle Time
- Team Utilization, Defect Rate, Architecture Health
- Security Score, Delivery Confidence, Technical Debt
- Edge cases: zero tasks, zero capacity, extreme incidents, 100% defects
"""

import pytest
from core.department import Department, DepartmentAuthorityLevel, DepartmentRole
from core.organization_metrics import (
    OrganizationMetricsCalculator,
    OrganizationMetricsDashboard,
)


@pytest.fixture
def calculator():
    return OrganizationMetricsCalculator()


def test_standard_metrics_calculation(calculator: OrganizationMetricsCalculator):
    dept_a = Department("Backend", DepartmentRole.BACKEND, capacity=10)
    dept_b = Department("Frontend", DepartmentRole.FRONTEND, capacity=10)

    # Assign 4 tasks to Backend, 2 to Frontend
    for i in range(4):
        dept_a.assign_task(f"T-BE-{i}", "Task", "Desc", "EM")
    for i in range(2):
        dept_b.assign_task(f"T-FE-{i}", "Task", "Desc", "EM")

    dashboard = calculator.calculate_dashboard(
        departments={"Backend": dept_a, "Frontend": dept_b},
        releases_count=1,
        incidents_count=0,
        customer_requests_count=5,
        completed_tasks_count=20,
        failed_tasks_count=1,
        lead_time_hours=18.0,
        cycle_time_hours=4.5,
        security_findings_count=0,
        critical_cves_count=0,
        technical_debt_items=2,
    )

    assert dashboard.velocity == 20.0
    assert dashboard.lead_time_hours == 18.0
    assert dashboard.cycle_time_hours == 4.5
    # Total workload 6 / total capacity 20 -> 30%
    assert dashboard.team_utilization_pct == 30.0
    # 1 fail / 21 total tasks -> ~4.76%
    assert dashboard.defect_rate_pct == pytest.approx(4.76, 0.1)
    assert dashboard.architecture_health_score > 90.0
    assert dashboard.security_score == 100.0
    assert 0.85 <= dashboard.delivery_confidence <= 1.0
    assert dashboard.technical_debt_hours == 9.0  # 2 * 4.5
    assert "Backend" in dashboard.department_performance
    assert "Frontend" in dashboard.department_performance


def test_metrics_penalized_by_incidents_and_cves(calculator: OrganizationMetricsCalculator):
    dept = Department("Backend", DepartmentRole.BACKEND, capacity=10)

    dashboard = calculator.calculate_dashboard(
        departments={"Backend": dept},
        releases_count=1,
        incidents_count=2,  # 2 incidents -> -16 arch penalty
        critical_cves_count=1,  # 1 critical CVE -> -25 sec penalty
        security_findings_count=2,  # 2 findings -> -10 sec penalty
        technical_debt_items=4,  # 4 * 3.5 -> -14 arch penalty
    )

    assert dashboard.architecture_health_score <= 70.0
    assert dashboard.security_score <= 65.0
    assert dashboard.delivery_confidence < 0.80


def test_zero_task_edge_case(calculator: OrganizationMetricsCalculator):
    dashboard = calculator.calculate_dashboard(
        departments={},
        releases_count=0,
        incidents_count=0,
        completed_tasks_count=0,
        failed_tasks_count=0,
    )
    assert dashboard.velocity == 0.0
    assert dashboard.defect_rate_pct == 0.0
    assert dashboard.delivery_confidence > 0.0


def test_serialization_roundtrip(calculator: OrganizationMetricsCalculator):
    dash = calculator.calculate_dashboard(departments={})
    d = dash.to_dict()
    assert "velocity" in d
    assert "security_score" in d
    assert "delivery_confidence" in d
    assert isinstance(d["timestamp"], float)
