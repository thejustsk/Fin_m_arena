"""Live recurring-budget calculations against personal consumption only."""
from services.nw_constants import NW_WANT


class BudgetService:
    def __init__(self, budgets_repo, tx_repo):
        self.budget_repo = budgets_repo
        self.tx_repo = tx_repo

    def check_budgets(self, y, m):
        """Return active monthly budgets with their actual current-month spend."""
        budgets = self.budget_repo.list_active("MONTHLY")
        txns = self.tx_repo.get_monthly(y, m)
        # Budgets are for personal consumption, not transfers/income/wealth.
        expenses = [t for t in txns if t.get("tx_type") == "DEBIT"
                    and t.get("transaction_kind", "REGULAR") == "REGULAR"]
        results = []
        for budget in budgets:
            scope, value = budget["scope_type"], budget["scope_value"]
            if scope == "CATEGORY":
                matched = [t for t in expenses if t.get("category") == value]
            elif scope == "TOTAL_EXPENSE":
                matched = expenses
            elif scope == "NEED_WANT":
                matched = [t for t in expenses if t.get("neednwant") == NW_WANT]
            else:
                matched = []
            spent = sum(t.get("amount") or 0 for t in matched)
            limit = budget["limit_amount"] or 0
            pct = spent / limit * 100 if limit > 0 else 0
            results.append({**budget, "spent": spent, "pct": pct,
                            "remaining": limit - spent})
        return results
