"""Balance service — the ONE place balance math happens."""


class BalanceService:
    def __init__(self, accounts_repo):
        self.repo = accounts_repo

    def get_balance(self, account_id):
        return self.repo.get_balance(account_id)

    def get_all(self):
        return self.repo.get_all_balances()

    def net_worth(self):
        return self.repo.get_net_worth()

    def by_type(self):
        totals = {"CURRENT": 0, "WALLET": 0, "CASH": 0, "CREDIT_CARD": 0}
        for r in self.get_all():
            totals[r["account_type"]] += r["balance"]
        return totals
