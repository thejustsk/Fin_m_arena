"""Live recurring-budget calculations against personal consumption only."""
from datetime import date
from services.nw_constants import NW_WANT


class BudgetService:
    def __init__(self, budgets_repo, tx_repo):
        self.budget_repo = budgets_repo
        self.tx_repo = tx_repo

    def check_budgets(self, y, m=None, period_type="MONTHLY"):
        """Return budgets and actual spend for a monthly or calendar-year period."""
        if period_type == "YEARLY":
            txns = self.tx_repo.list_filters(date_from=f"{y:04d}-01-01", date_to=f"{y:04d}-12-31", limit=50000)
        else:
            txns = self.tx_repo.get_monthly(y, m or date.today().month)
        budgets = self.budget_repo.list_active(period_type)
        expenses = [t for t in txns if t.get("tx_type") == "DEBIT"
                    and t.get("transaction_kind", "REGULAR") == "REGULAR"]
        results = []
        for budget in budgets:
            scope, value = budget["scope_type"], budget["scope_value"]
            if scope == "CATEGORY": matched = [t for t in expenses if t.get("category") == value]
            elif scope == "TOTAL_EXPENSE": matched = expenses
            elif scope == "NEED_WANT": matched = [t for t in expenses if t.get("neednwant") == NW_WANT]
            else: matched = []
            spent = sum(t.get("amount") or 0 for t in matched); limit = budget["limit_amount"] or 0
            pct = spent / limit * 100 if limit > 0 else 0
            results.append({**budget, "spent": spent, "pct": pct, "remaining": limit - spent})
        return results
