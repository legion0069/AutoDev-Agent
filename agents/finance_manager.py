"""
finance_manager.py - Finance & Cost Estimator Agent (AutoDev Version 3.4)

Tracks enterprise development expenses, token economics, and burn rate:
- Development, infrastructure, AI API, and testing cost estimation
- Monthly corporate burn rate tracking
- Token expenditure auditing and efficiency optimization
- Unit economic modeling per feature and customer
- Financial report synthesis and executive budget variance analysis
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType
from core.organization_state import OrganizationState

logger = logging.getLogger("AutoDev.Org.FinanceManager")


class FinanceManagerAgent:
    """
    Autonomous Finance Manager AI Agent.
    """

    def __init__(
        self,
        name: str = "Finance",
        bus: Optional[CommunicationBus] = None,
        state: Optional[OrganizationState] = None,
    ) -> None:
        self.name = name
        self.bus = bus
        self.state = state
        self.authority_level = 3  # Managerial Finance
        self.token_cost_per_million: float = 2.50  # USD per million tokens
        self.developer_hourly_rate: float = 65.0  # USD per hour benchmark

        if self.bus:
            self.bus.register_entity(self.name)

    def estimate_project_cost(
        self,
        engineer_hours: float,
        tokens_consumed: int = 500000,
        infra_hours: float = 24.0,
    ) -> Dict[str, Any]:
        """Calculates multi-dimensional financial cost breakdown for an initiative."""
        dev_cost = round(engineer_hours * self.developer_hourly_rate, 2)
        ai_cost = round((tokens_consumed / 1_000_000) * self.token_cost_per_million, 2)
        infra_cost = round(infra_hours * 1.25, 2)
        testing_cost = round(dev_cost * 0.20, 2)
        total = round(dev_cost + ai_cost + infra_cost + testing_cost, 2)

        result = {
            "developer_labor_cost_usd": dev_cost,
            "ai_token_cost_usd": ai_cost,
            "infrastructure_cost_usd": infra_cost,
            "testing_and_qa_cost_usd": testing_cost,
            "total_estimated_cost_usd": total,
            "engineer_hours": engineer_hours,
            "tokens_consumed": tokens_consumed,
        }

        logger.info("Project cost estimated: Total=$%.2f (Dev=$%.2f, AI=$%.2f)", total, dev_cost, ai_cost)
        return result

    def calculate_monthly_burn(self, department_reports: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Synthesizes monthly corporate burn rate across all departments."""
        total_burn = 0.0
        dept_breakdown = {}

        for dept, rep in department_reports.items():
            spent = rep.get("budget_spent", 0.0)
            total_burn += spent
            dept_breakdown[dept] = round(spent, 2)

        return {
            "total_monthly_burn_usd": round(total_burn, 2),
            "department_breakdown_usd": dept_breakdown,
            "timestamp": time.time(),
        }

    def generate_financial_report(self, total_spent: float, total_budget: float) -> Dict[str, Any]:
        """Generates formal corporate financial audit statement."""
        variance = round(total_budget - total_spent, 2)
        burn_pct = round((total_spent / max(1.0, total_budget)) * 100.0, 1)

        report = {
            "total_budget_usd": total_budget,
            "total_spent_usd": total_spent,
            "remaining_budget_usd": variance,
            "budget_utilized_pct": burn_pct,
            "financial_health": "ON_BUDGET" if variance >= 0 else "BUDGET_OVERRUN",
            "timestamp": time.time(),
        }

        if self.state:
            self.state.record_financial_report(report)

        return report
