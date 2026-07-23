"""Audit service — deficit/surplus, audit logging."""
from datetime import datetime, timedelta


class AuditService:
    def __init__(self, audit_repo, tx_repo, db):
        self.audit_repo = audit_repo
        self.tx_repo = tx_repo
        self.db = db

    def log(self, tx_id, field, old, new, reason=None):
        self.audit_repo.log(tx_id, field, old, new, reason)

    def surplus(self, y, m):
        d_from = f"{y:04d}-{m:02d}-01"
        d_to = f"{y:04d}-{m+1:02d}-01" if m < 12 else f"{y+1:04d}-01-01"
        c = self.db.get()
        inc = c.execute(
            "SELECT COALESCE(SUM(t.amount),0) FROM transactions t "
            "JOIN categories c ON c.category_id=t.category "
            "WHERE t.tx_type='CREDIT' AND t.tx_date>=? AND t.tx_date<? "
            "AND t.transaction_kind != 'TRANSFER' AND c.default_pf_category='nc'",
            (d_from, d_to)).fetchone()[0]
        exp = c.execute(
            "SELECT COALESCE(SUM(t.amount),0) FROM transactions t "
            "JOIN categories c ON c.category_id=t.category "
            "WHERE t.tx_type='DEBIT' AND t.tx_date>=? AND t.tx_date<? "
            "AND t.transaction_kind != 'TRANSFER' "
            "AND c.default_pf_category IN ('commitment','consumption','growth','safety')",
            (d_from, d_to)).fetchone()[0]
        return inc - exp

    def trend(self, months=12):
        now = datetime.now()
        results = []
        for i in range(months - 1, -1, -1):
            d = now.replace(day=1) - timedelta(days=i * 30)
            results.append((f"{d.year:04d}-{d.month:02d}", self.surplus(d.year, d.month)))
        return results
