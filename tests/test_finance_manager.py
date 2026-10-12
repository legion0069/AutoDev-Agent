"""
test_finance_manager.py - Unit and Integration Tests for Finance & Budget Operations (v3.0)
"""

import pytest
from core.enterprise.enterprise_models import DepartmentType, ExpenseCategory
from core.enterprise.finance_manager import FinanceManager


@pytest.fixture
def finance():
    return FinanceManager(initial_cash_reserve_usd=5000000.0)


class TestFinanceManager:
    def test_initial_reserves_and_budgets(self, finance: FinanceManager):
        assert finance.get_cash_reserve_usd() == 5000000.0
        assert finance.get_total_spend_usd() == 0.0
        budget = finance.get_budget("2026-Q1")
        assert budget is not None
        assert budget.total_allocated_usd > 0

    def test_record_expense_updates_ledger_and_budget(self, finance: FinanceManager):
        entry = finance.record_expense(
            category=ExpenseCategory.LLM_API_TOKENS,
            amount_usd=5000.0,
            description="LLM API calls for code generation",
            department=DepartmentType.ENGINEERING,
            quarter_key="2026-Q1",
        )
        assert entry.entry_id.startswith("tx_")
        assert entry.amount_usd == 5000.0
        assert finance.get_cash_reserve_usd() == 4995000.0
        assert finance.get_total_spend_usd() == 5000.0

        budget = finance.get_budget("2026-Q1")
        assert budget.actual_spent_usd[ExpenseCategory.LLM_API_TOKENS.value] == 5000.0

    def test_invalid_negative_expense_raises_error(self, finance: FinanceManager):
        with pytest.raises(ValueError):
            finance.record_expense(ExpenseCategory.STORAGE_CAS, -500.0, "Invalid", DepartmentType.DEVOPS)

    def test_calculate_runway_months(self, finance: FinanceManager):
        # With $5,000,000 cash and $250,000 monthly burn => 20.0 months
        runway = finance.calculate_runway_months(monthly_burn_usd=250000.0)
        assert runway == 20.0

    def test_calculate_roi(self, finance: FinanceManager):
        # Invest $100k, return $300k => ((300 - 100) / 100) * 100 = 200.0%
        roi = finance.calculate_roi(invested_cost_usd=100000.0, expected_revenue_or_savings_usd=300000.0)
        assert roi == 200.0

    def test_cost_optimization_recommendations(self, finance: FinanceManager):
        # Spend heavily on cloud and LLM to trigger recommendations
        finance.record_expense(ExpenseCategory.INFRASTRUCTURE_CLOUD, 250000.0, "High Cloud Compute", DepartmentType.DEVOPS)
        finance.record_expense(ExpenseCategory.LLM_API_TOKENS, 150000.0, "High Token Inference", DepartmentType.ENGINEERING)

        recs = finance.generate_cost_optimization_recommendations()
        assert len(recs) >= 2
        categories = {r["category"] for r in recs}
        assert ExpenseCategory.INFRASTRUCTURE_CLOUD.value in categories
        assert ExpenseCategory.LLM_API_TOKENS.value in categories

    def test_to_dict_summary(self, finance: FinanceManager):
        d = finance.to_dict()
        assert "cash_reserve_usd" in d
        assert "total_spent_usd" in d
        assert "runway_months" in d
        assert "budgets" in d
