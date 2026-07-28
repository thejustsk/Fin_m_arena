"""Offline, explainable financial insight rules.

This service deliberately has no UI or network dependency.  Each result is a
plain dict that can be displayed in the Insights tab or Home dashboard.
"""
from collections import Counter, defaultdict
from datetime import date
from statistics import median

from services.nw_constants import is_untagged

MIN_TRANSACTIONS = 20


class InsightService:
    def __init__(self, tx_repo, db, repos=None):
        self.tx_repo = tx_repo
        self.db = db
        self.repos = repos or {}

    def analyze(self):
        rows = self.tx_repo.list_filters(limit=50000)
        if len(rows) < MIN_TRANSACTIONS:
            return {"ready": False, "transaction_count": len(rows), "insights": []}
        insights = []
        debits = [r for r in rows if r.get("tx_type") == "DEBIT" and r.get("transaction_kind") != "TRANSFER"]
        insights += self._large_transactions(debits)
        insights += self._monthly_anomalies(debits)
        insights += self._category_trends(debits)
        insights += self._merchant_frequency(debits)
        insights += self._untagged_spend(debits)
        insights += self._overdue_positions()
        insights.sort(key=lambda x: ({"critical": 0, "warning": 1, "positive": 2, "info": 3}[x["severity"]], -x.get("amount", 0)))
        return {"ready": True, "transaction_count": len(rows), "insights": insights}

    @staticmethod
    def _item(severity, title, message, amount=0, category="General"):
        return {"severity": severity, "title": title, "message": message, "amount": round(amount or 0, 2), "category": category}

    def _large_transactions(self, rows):
        amounts = [r.get("amount") or 0 for r in rows]
        if len(amounts) < 10:
            return []
        baseline = median(amounts)
        if baseline <= 0:
            return []
        out = []
        for r in sorted(rows, key=lambda x: x.get("amount") or 0, reverse=True)[:5]:
            amount = r.get("amount") or 0
            if amount >= max(50000, baseline * 12):
                who = r.get("person_org") or r.get("description") or "an entry"
                out.append(self._item("critical", "Unusually large transaction", f"₹{amount:,.0f} for {who} is {amount / baseline:,.0f}× your typical transaction.", amount, "Data review"))
        return out

    def _monthly_anomalies(self, rows):
        months = defaultdict(float)
        for r in rows:
            months[(r.get("tx_date") or "")[:7]] += r.get("amount") or 0
        if len(months) < 3:
            return []
        latest = max(months)
        prior = [v for k, v in months.items() if k != latest and v > 0]
        base = median(prior) if prior else 0
        value = months[latest]
        if base and value >= base * 2:
            return [self._item("critical" if value >= base * 5 else "warning", "Monthly spending anomaly", f"{latest} spending is ₹{value:,.0f}, {value / base:,.1f}× your historical monthly median of ₹{base:,.0f}.", value, "Spending trend")]
        return []

    def _category_trends(self, rows):
        by_month = defaultdict(lambda: defaultdict(float))
        for r in rows:
            by_month[(r.get("tx_date") or "")[:7]][r.get("cat_name") or "Uncategorised"] += r.get("amount") or 0
        if len(by_month) < 2:
            return []
        latest = max(by_month)
        previous = sorted(k for k in by_month if k != latest)[-3:]
        out = []
        for cat, value in by_month[latest].items():
            baseline_values = [by_month[m].get(cat, 0) for m in previous]
            base = median(baseline_values) if baseline_values else 0
            if base >= 500 and value >= base * 1.5:
                out.append(self._item("warning", f"{cat} spending increased", f"This month: ₹{value:,.0f}; recent baseline: ₹{base:,.0f} ({(value/base-1)*100:.0f}% higher).", value, "Category trend"))
        return out[:3]

    def _merchant_frequency(self, rows):
        names = Counter((r.get("person_org") or "").strip().upper() for r in rows)
        amounts = defaultdict(float)
        for r in rows:
            amounts[(r.get("person_org") or "").strip().upper()] += r.get("amount") or 0
        out = []
        for name, count in names.most_common(5):
            if name and count >= 8:
                out.append(self._item("info", "Frequent merchant", f"{name.title()} appears in {count} transactions, totalling ₹{amounts[name]:,.0f}. Consider a budget or recurring rule if this is expected.", amounts[name], "Merchant pattern"))
        return out[:2]

    def _untagged_spend(self, rows):
        total = sum(r.get("amount") or 0 for r in rows)
        untagged = sum(r.get("amount") or 0 for r in rows if is_untagged(r.get("neednwant")))
        if total and untagged >= total * .15:
            return [self._item("warning", "Spending needs classification", f"₹{untagged:,.0f} ({untagged/total*100:.0f}%) of expense spending is still Not Set for Need vs Want.", untagged, "Data quality")]
        return []

    def _overdue_positions(self):
        out = []
        try:
            row = self.db.execute("SELECT COALESCE(SUM(l.loan_amount-COALESCE((SELECT SUM(amount_paid) FROM repayments r WHERE r.loan_id=l.loan_id),0)),0) AS amount, COUNT(*) AS n FROM loans l WHERE l.status='OVERDUE'").fetchone()
            if row and row["n"]:
                out.append(self._item("warning", "Loans overdue", f"{row['n']} money-lent loan(s) are overdue, with about ₹{row['amount']:,.0f} outstanding.", row["amount"], "Wealth"))
        except Exception:
            pass
        return out
