"""
finance_manager.py - Enterprise Financial Operations & Cost Optimization for AutoDev (v3.0)

Manages corporate budgets, departmental spending, multi-category cost accounting
(salaries, cloud infrastructure, LLM tokens, CAS storage, CI/CD, testing, support),
burn rate, runway forecasting, ROI calculations, and cost optimization recommendations.
"""

from __future__ import annotations

import collections
import copy
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from core.enterprise.enterprise_models import (
    DepartmentType,
    ExpenseCategory,
    FinancialLedgerEntry,
    QuarterlyBudget,
)

logger = logging.getLogger("AutoDev.Enterprise.Finance")


class FinanceManager:
    """
    Autonomous Enterprise Financial Engine.
    Tracks budgets, expense ledgers, burn rate, runway, ROI, and cost optimizations.
    """

    def __init__(self, initial_cash_reserve_usd: float = 10000000.0) -> None:
        self._lock = threading.RLock()
        self._cash_reserve_usd = initial_cash_reserve_usd
        self._budgets: Dict[str, QuarterlyBudget] = {}  # "2026-Q1" -> QuarterlyBudget
        self._ledger: List[FinancialLedgerEntry] = []
        self._category_expenses: Dict[ExpenseCategory, float] = collections.defaultdict(float)
        self._dept_expenses: Dict[DepartmentType, float] = collections.defaultdict(float)

        self._init_default_budgets()

    def _init_default_budgets(self) -> None:
        """Initializes default quarterly corporate budgets."""
        default_limits = {
            ExpenseCategory.ENGINEERING_SALARIES.value: 1500000.0,
            ExpenseCategory.INFRASTRUCTURE_CLOUD.value: 300000.0,
            ExpenseCategory.LLM_API_TOKENS.value: 200000.0,
            ExpenseCategory.STORAGE_CAS.value: 50000.0,
            ExpenseCategory.CI_CD_BUILD.value: 100000.0,
            ExpenseCategory.TESTING_QA.value: 80000.0,
            ExpenseCategory.MAINTENANCE.value: 70000.0,
            ExpenseCategory.SECURITY_AUDIT.value: 100000.0,
            ExpenseCategory.CUSTOMER_SUPPORT.value: 100000.0,
            ExpenseCategory.GENERAL_ADMIN.value: 150000.0,
        }
        q1_budget = QuarterlyBudget(
            quarter="Q1",
            year=2026,
            total_allocated_usd=sum(default_limits.values()),
            category_limits_usd=default_limits,
            actual_spent_usd={cat: 0.0 for cat in default_limits},
        )
        self._budgets["2026-Q1"] = q1_budget

    def record_expense(
        self,
        category: ExpenseCategory,
        amount_usd: float,
        description: str,
        department: DepartmentType,
        quarter_key: str = "2026-Q1",
    ) -> FinancialLedgerEntry:
        """
        Records a financial transaction in the general ledger and updates budget counters.
        """
        if amount_usd <= 0:
            raise ValueError(f"Expense amount must be positive, got {amount_usd}")

        with self._lock:
            entry_id = f"tx_{int(time.time() * 1000)}_{len(self._ledger) + 1}"
            entry = FinancialLedgerEntry(
                entry_id=entry_id,
                category=category,
                amount_usd=amount_usd,
                description=description,
                department=department,
                timestamp=time.time(),
            )
            self._ledger.append(entry)
            self._category_expenses[category] += amount_usd
            self._dept_expenses[department] += amount_usd
            self._cash_reserve_usd -= amount_usd

            # Update quarterly budget if exists
            if quarter_key in self._budgets:
                q_budget = self._budgets[quarter_key]
                cat_key = category.value
                current_spent = q_budget.actual_spent_usd.get(cat_key, 0.0)
                q_budget.actual_spent_usd[cat_key] = current_spent + amount_usd

            logger.info(f"Recorded expense [{entry_id}] ${amount_usd:.2f} under {category.value} for {department.value}")
            return entry

    def create_quarterly_budget(
        self,
        quarter: str,
        year: int,
        category_limits_usd: Dict[str, float],
    ) -> QuarterlyBudget:
        """Sets up a new quarterly corporate budget."""
        key = f"{year}-{quarter}"
        total = sum(category_limits_usd.values())
        with self._lock:
            budget = QuarterlyBudget(
                quarter=quarter,
                year=year,
                total_allocated_usd=total,
                category_limits_usd=copy.deepcopy(category_limits_usd),
                actual_spent_usd={cat: 0.0 for cat in category_limits_usd},
            )
            self._budgets[key] = budget
            return budget

    def get_budget(self, quarter_key: str = "2026-Q1") -> Optional[QuarterlyBudget]:
        """Retrieves quarterly budget summary."""
        with self._lock:
            return copy.deepcopy(self._budgets.get(quarter_key))

    def get_cash_reserve_usd(self) -> float:
        """Returns total remaining liquid cash reserves."""
        with self._lock:
            return self._cash_reserve_usd

    def get_total_spend_usd(self) -> float:
        """Returns total historical expenses recorded."""
        with self._lock:
            return sum(self._category_expenses.values())

    def get_spending_by_category(self) -> Dict[str, float]:
        """Returns breakdown of expenses by category."""
        with self._lock:
            return {k.value: round(v, 2) for k, v in self._category_expenses.items()}

    def get_spending_by_department(self) -> Dict[str, float]:
        """Returns breakdown of expenses by department."""
        with self._lock:
            return {k.value: round(v, 2) for k, v in self._dept_expenses.items()}

    def calculate_runway_months(self, monthly_burn_usd: Optional[float] = None) -> float:
        """
        Calculates company runway in months based on cash reserve and burn rate.
        """
        with self._lock:
            if monthly_burn_usd is not None:
                if monthly_burn_usd == 0:
                    return float("inf")
                elif monthly_burn_usd < 0:
                    return float("inf")
                return round(max(0.0, self._cash_reserve_usd / monthly_burn_usd), 1)

            # Estimate monthly burn from total spend or fallback
            total_spent = self.get_total_spend_usd()
            effective_burn = max(50000.0, total_spent)
            runway = self._cash_reserve_usd / effective_burn
            return round(max(0.0, runway), 1)

    def calculate_roi(
        self,
        invested_cost_usd: float,
        expected_revenue_or_savings_usd: float,
    ) -> float:
        """
        Calculates Return on Investment (ROI) percentage: ((Gain - Cost) / Cost) * 100.
        """
        if invested_cost_usd <= 0:
            return 0.0
        roi = ((expected_revenue_or_savings_usd - invested_cost_usd) / invested_cost_usd) * 100.0
        return round(roi, 2)

    def generate_cost_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """
        Analyzes spending patterns and outputs actionable cost optimization strategies.
        """
        with self._lock:
            recommendations: List[Dict[str, Any]] = []
            cloud_cost = self._category_expenses.get(ExpenseCategory.INFRASTRUCTURE_CLOUD, 0.0)
            llm_cost = self._category_expenses.get(ExpenseCategory.LLM_API_TOKENS, 0.0)
            cicd_cost = self._category_expenses.get(ExpenseCategory.CI_CD_BUILD, 0.0)

            if cloud_cost > 200000.0:
                recommendations.append({
                    "category": ExpenseCategory.INFRASTRUCTURE_CLOUD.value,
                    "action": "Right-size cluster instances and leverage spot nodes for build workloads",
                    "estimated_savings_pct": 25.0,
                    "estimated_monthly_savings_usd": round(cloud_cost * 0.25, 2),
                    "priority": "HIGH",
                })

            if llm_cost > 100000.0:
                recommendations.append({
                    "category": ExpenseCategory.LLM_API_TOKENS.value,
                    "action": "Enable prompt caching, response deduplication, and model distillation",
                    "estimated_savings_pct": 35.0,
                    "estimated_monthly_savings_usd": round(llm_cost * 0.35, 2),
                    "priority": "HIGH",
                })

            if cicd_cost > 50000.0:
                recommendations.append({
                    "category": ExpenseCategory.CI_CD_BUILD.value,
                    "action": "Optimize test sharding and activate CAS artifact caching for build stages",
                    "estimated_savings_pct": 20.0,
                    "estimated_monthly_savings_usd": round(cicd_cost * 0.20, 2),
                    "priority": "MEDIUM",
                })

            if not recommendations:
                recommendations.append({
                    "category": "GENERAL",
                    "action": "Maintain active cost monitoring; spending remains within optimal enterprise targets",
                    "estimated_savings_pct": 0.0,
                    "estimated_monthly_savings_usd": 0.0,
                    "priority": "LOW",
                })

            return recommendations

    def to_dict(self) -> Dict[str, Any]:
        """Serializes financial summary to dictionary."""
        with self._lock:
            return {
                "cash_reserve_usd": round(self._cash_reserve_usd, 2),
                "total_spent_usd": round(self.get_total_spend_usd(), 2),
                "runway_months": self.calculate_runway_months(),
                "spending_by_category": self.get_spending_by_category(),
                "spending_by_department": self.get_spending_by_department(),
                "total_transactions": len(self._ledger),
                "budgets": {k: b.to_dict() for k, b in self._budgets.items()},
                "optimization_recommendations": self.generate_cost_optimization_recommendations(),
            }
