"""Budget service — computed live against actual spend."""


class BudgetService:
    def __init__(self, budgets_repo, tx_repo):
        self.budget_repo = budgets_repo
        self.tx_repo = tx_repo

    def check_budgets(self, y, m):
        """Return list of (budget, spent, pct) for active budgets."""
        budgets = self.budget_repo.list_active()
        txns = self.tx_repo.get_monthly(y, m)
        results = []
        for b in budgets:
            spent = 0
            for t in txns:
                if t["tx_type"] == "DEBIT":
                    if b["scope_type"] == "CATEGORY" and t.get("category") == b["scope_value"]:
                        spent += t["amount"]
                    elif b["scope_type"] == "PF_CATEGORY" and t.get("pf_category") == b["scope_value"]:
                        spent += t["amount"]
            pct = spent / b["limit_amount"] * 100 if b["limit_amount"] > 0 else 0
            results.append((b, spent, pct))
        return results
