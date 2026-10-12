"""
global_metrics.py - Enterprise Global Analytics & Executive Dashboard Engine (AutoDev Version 3.5)

Synthesizes macroscopic executive analytics across the entire enterprise ecosystem:
- Multi-company consolidated velocity, defect rate, health, and delivery confidence
- Innovation Score (derived from AI research, model checkpoints, and knowledge publication)
- Knowledge Reuse Rate (cross-company knowledge sharing & adoption ratio)
- Enterprise Technical Debt & Architecture Health across companies
- Security Index & Cross-Company Zero Trust Compliance
- Budgetary burn rate, variance, and financial runway
- 100% Python Standard Library.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AutoDev.Federation.Metrics")


@dataclass
class GlobalEnterpriseDashboard:
    """Master executive analytics dashboard covering the entire enterprise group."""
    timestamp: float
    enterprise_name: str
    total_companies: int
    active_companies: int
    total_projects: int
    active_projects: int
    consolidated_velocity: float
    global_defect_rate_pct: float
    enterprise_health_score: float
    enterprise_security_score: float
    global_delivery_confidence: float
    innovation_score: float
    knowledge_reuse_rate_pct: float
    total_technical_debt_hours: float
    total_allocated_budget_usd: float
    total_spent_budget_usd: float
    net_budget_variance_usd: float
    monthly_burn_rate_usd: float
    company_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    summary_headline: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GlobalMetricsCalculator:
    """
    Computes unified enterprise analytics from registry, portfolio, security, and knowledge engines.
    """

    def __init__(self, enterprise_name: str = "AutoDev Global Enterprise") -> None:
        self._lock = threading.RLock()
        self.enterprise_name = enterprise_name

    def calculate_global_dashboard(
        self,
        companies: Dict[str, Any],
        portfolio_summary: Optional[Dict[str, Any]] = None,
        security_dashboard: Optional[Dict[str, Any]] = None,
        knowledge_analytics: Optional[Dict[str, Any]] = None,
        marketplace_summary: Optional[Dict[str, Any]] = None,
        governance_summary: Optional[Dict[str, Any]] = None,
    ) -> GlobalEnterpriseDashboard:
        """
        Synthesizes macro metrics across companies, portfolio, security, and knowledge bases.
        """
        with self._lock:
            now = time.time()
            total_companies = len(companies)

            # 1. Company-level aggregations
            active_companies = 0
            health_scores = []
            total_budget = 0.0
            total_spent = 0.0
            company_breakdown: Dict[str, Dict[str, Any]] = {}
            tech_debt_hours = 0.0
            velocity_sum = 0.0

            for cid, comp in companies.items():
                if hasattr(comp, "to_dict"):
                    c_dict = comp.to_dict()
                elif hasattr(comp, "get_status_report"):
                    c_dict = comp.get_status_report()
                elif isinstance(comp, dict):
                    c_dict = comp
                else:
                    c_dict = {}

                status = str(c_dict.get("status", "ACTIVE"))
                if "ACTIVE" in status:
                    active_companies += 1

                health = float(c_dict.get("health_score", 100.0))
                health_scores.append(health)

                b_alloc = float(c_dict.get("allocated_budget_usd", c_dict.get("budget", 500000.0)))
                b_spent = float(c_dict.get("spent_budget_usd", c_dict.get("spent_budget", 0.0)))
                total_budget += b_alloc
                total_spent += b_spent

                # Estimate technical debt if available
                debt = float(c_dict.get("technical_debt_hours", 12.0))
                tech_debt_hours += debt

                # Velocity
                vel = float(c_dict.get("velocity", 25.0))
                velocity_sum += vel

                company_breakdown[cid] = {
                    "company_name": c_dict.get("company_name", cid),
                    "status": status,
                    "health_score": round(health, 1),
                    "allocated_budget_usd": b_alloc,
                    "spent_budget_usd": b_spent,
                    "headcount": c_dict.get("headcount", 50),
                }

            avg_health = (sum(health_scores) / max(1, len(health_scores))) if health_scores else 95.0

            # 2. Portfolio Metrics
            p_dash = portfolio_summary or {}
            total_projects = p_dash.get("total_projects", 0)
            active_projects = p_dash.get("active_projects", 0)
            portfolio_conf = float(p_dash.get("average_delivery_confidence", 0.85))

            # 3. Security Metrics
            sec_dash = security_dashboard or {}
            quarantined = len(sec_dash.get("quarantined_companies", []))
            sec_audit_valid = sec_dash.get("audit_chain_valid", True)
            known_threats = sec_dash.get("known_threats_count", 0)

            sec_score = 100.0 - (quarantined * 25.0) - (known_threats * 10.0)
            if not sec_audit_valid:
                sec_score -= 30.0
            sec_score = max(10.0, min(100.0, round(sec_score, 1)))

            # 4. Knowledge & Innovation Metrics
            know_dash = knowledge_analytics or {}
            total_nodes = know_dash.get("total_nodes", 0)
            total_reuses = know_dash.get("total_reuses", 0)
            research_count = know_dash.get("nodes_by_category", {}).get("RESEARCH", 0)

            reuse_rate = round((total_reuses / max(1, total_nodes)) * 100.0, 1) if total_nodes > 0 else 0.0
            # Innovation score: derived from research nodes, model registrations, and active projects
            innovation_score = min(100.0, round((research_count * 15.0) + (reuse_rate * 0.4) + (active_projects * 2.5), 1))

            # 5. Global Defect Rate
            defect_rate = max(1.0, min(15.0, round((100.0 - avg_health) * 0.25, 2)))

            # 6. Global Delivery Confidence
            delivery_conf = round(
                (avg_health / 100.0) * 0.35
                + (sec_score / 100.0) * 0.30
                + (portfolio_conf) * 0.25
                + ((100.0 - defect_rate) / 100.0) * 0.10,
                3,
            )

            variance = total_budget - total_spent
            headline = (
                f"{self.enterprise_name}: {active_companies}/{total_companies} Companies Active | "
                f"Health: {avg_health:.1f}/100 | Security: {sec_score:.1f}/100 | "
                f"Confidence: {delivery_conf*100:.1f}% | Innovation: {innovation_score:.1f}/100"
            )

            return GlobalEnterpriseDashboard(
                timestamp=now,
                enterprise_name=self.enterprise_name,
                total_companies=total_companies,
                active_companies=active_companies,
                total_projects=total_projects,
                active_projects=active_projects,
                consolidated_velocity=round(velocity_sum, 1),
                global_defect_rate_pct=defect_rate,
                enterprise_health_score=round(avg_health, 1),
                enterprise_security_score=sec_score,
                global_delivery_confidence=delivery_conf,
                innovation_score=innovation_score,
                knowledge_reuse_rate_pct=reuse_rate,
                total_technical_debt_hours=round(tech_debt_hours, 1),
                total_allocated_budget_usd=round(total_budget, 2),
                total_spent_budget_usd=round(total_spent, 2),
                net_budget_variance_usd=round(variance, 2),
                monthly_burn_rate_usd=round(total_spent / 3.0, 2),  # Estimated monthly burn
                company_breakdown=company_breakdown,
                summary_headline=headline,
            )
