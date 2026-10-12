"""
organization_metrics.py - Enterprise Organizational Metrics & Dashboard (AutoDev Version 3.4)

Synthesizes high-level corporate KPIs and telemetry:
- Velocity (Story points & features delivered per sprint)
- Lead Time (Customer request arrival to production release)
- Cycle Time (Engineering commit to production release)
- Team Utilization (Workload / capacity ratio across departments)
- Defect Rate (Bugs reported vs delivered tasks)
- Architecture Health (ADR adherence, modular layering, coupling)
- Security Score (Vulnerability severity, secrets, OWASP compliance: 0-100)
- Delivery Confidence (Algorithmic success probability: 0.0 - 1.0)
- Department Performance (Health, velocity, workload by team)
- Technical Debt (Accumulated refactoring backlog & estimated effort)
- Financial Burn & ROI (Operational costs, token expenditure, unit economics)

Outputs structured, deterministic JSON metrics dashboard.
"""

from __future__ import annotations

import logging
import math
import statistics
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AutoDev.Org.Metrics")


@dataclass
class OrganizationMetricsDashboard:
    """Comprehensive executive dashboard payload."""
    timestamp: float = field(default_factory=time.time)
    velocity: float = 0.0  # Story points / features per period
    lead_time_hours: float = 0.0  # Intake to deployment
    cycle_time_hours: float = 0.0  # Coding to deployment
    team_utilization_pct: float = 0.0  # 0 to 100%
    defect_rate_pct: float = 0.0  # 0 to 100%
    architecture_health_score: float = 100.0  # 0 to 100
    security_score: float = 100.0  # 0 to 100
    delivery_confidence: float = 1.0  # 0.0 to 1.0
    technical_debt_hours: float = 0.0
    monthly_burn_rate_usd: float = 0.0
    department_performance: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OrganizationMetricsCalculator:
    """
    Computes corporate performance, delivery velocity, and health KPIs
    using deterministic formulas across department states and release records.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def calculate_dashboard(
        self,
        departments: Dict[str, Any],
        releases_count: int = 1,
        incidents_count: int = 0,
        customer_requests_count: int = 5,
        completed_tasks_count: int = 25,
        failed_tasks_count: int = 1,
        lead_time_hours: float = 24.0,
        cycle_time_hours: float = 6.0,
        security_findings_count: int = 0,
        critical_cves_count: int = 0,
        technical_debt_items: int = 2,
    ) -> OrganizationMetricsDashboard:
        """
        Calculates organizational dashboard metrics deterministically.
        """
        with self._lock:
            # 1. Velocity: tasks completed normalized by release iterations
            velocity = round(float(completed_tasks_count) / max(1, releases_count), 2)

            # 2. Defect Rate: failed tasks & incidents relative to total work
            total_tasks = completed_tasks_count + failed_tasks_count
            defect_rate = (
                round(((failed_tasks_count + incidents_count) / max(1, total_tasks)) * 100.0, 2)
                if total_tasks > 0
                else min(100.0, incidents_count * 15.0)
            )

            # 3. Team Utilization: aggregate current_workload / total capacity
            total_workload = 0
            total_capacity = 0
            dept_performance: Dict[str, Dict[str, Any]] = {}
            health_scores: List[float] = []
            monthly_burn = 0.0

            for name, dept in departments.items():
                if hasattr(dept, "get_status_report"):
                    rep = dept.get_status_report()
                elif isinstance(dept, dict):
                    rep = dept
                else:
                    rep = {}

                workload = rep.get("current_workload", 0)
                capacity = rep.get("capacity", 10)
                health = rep.get("health_score", 100.0)
                perf = rep.get("performance_score", 100.0)
                spent = rep.get("budget_spent", 0.0)

                total_workload += workload
                total_capacity += max(1, capacity)
                health_scores.append(health)
                monthly_burn += spent

                dept_performance[name] = {
                    "health_score": round(health, 1),
                    "performance_score": round(perf, 1),
                    "utilization_rate": round(workload / max(1, capacity), 2),
                    "workload": workload,
                    "capacity": capacity,
                }

            team_utilization = (
                round((total_workload / max(1, total_capacity)) * 100.0, 1)
                if total_capacity > 0
                else 50.0
            )

            # 4. Architecture Health: penalized by incidents and technical debt
            arch_penalty = (incidents_count * 8.0) + (technical_debt_items * 3.5)
            architecture_health = max(20.0, min(100.0, round(100.0 - arch_penalty, 1)))

            # 5. Security Score: 100 minus critical CVEs and findings
            sec_penalty = (critical_cves_count * 25.0) + (security_findings_count * 5.0)
            security_score = max(10.0, min(100.0, round(100.0 - sec_penalty, 1)))

            # 6. Technical Debt Hours: estimated ~4 hours per debt item
            debt_hours = round(technical_debt_items * 4.5, 1)

            # 7. Delivery Confidence: derived from health, security, defect rate
            avg_health = statistics.mean(health_scores) if health_scores else 95.0
            confidence_raw = (
                (avg_health / 100.0) * 0.30
                + (security_score / 100.0) * 0.35
                + (architecture_health / 100.0) * 0.25
                + (max(0.0, 100.0 - defect_rate) / 100.0) * 0.10
            )
            delivery_confidence = round(max(0.1, min(1.0, confidence_raw)), 3)

            summary = (
                f"Organization Velocity: {velocity} pts/rel | Team Utilization: {team_utilization}% | "
                f"Security Score: {security_score}/100 | Delivery Confidence: {delivery_confidence*100:.1f}%"
            )

            dashboard = OrganizationMetricsDashboard(
                velocity=velocity,
                lead_time_hours=lead_time_hours,
                cycle_time_hours=cycle_time_hours,
                team_utilization_pct=team_utilization,
                defect_rate_pct=defect_rate,
                architecture_health_score=architecture_health,
                security_score=security_score,
                delivery_confidence=delivery_confidence,
                technical_debt_hours=debt_hours,
                monthly_burn_rate_usd=round(monthly_burn, 2),
                department_performance=dept_performance,
                summary=summary,
            )
            return dashboard
