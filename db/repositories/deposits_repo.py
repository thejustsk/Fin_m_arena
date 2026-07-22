"""Deposits from others repository."""
import uuid
from datetime import datetime

def _rows(rows): return [dict(r) for r in rows] if rows else []

class DepositsRepo:
    def __init__(self, db): self.db = db
    def create_depositor(self, name):
        did = str(uuid.uuid4())
        self.db.execute("INSERT INTO depositors VALUES(?,?,?)",
                        (did, name, datetime.now().isoformat()))
        self.db.commit(); return did
    def list_depositors(self):
        return _rows(self.db.execute("SELECT * FROM depositors ORDER BY name").fetchall())
    def create_deposit(self, **kw):
        kw.setdefault("deposit_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys()); phs = ", ".join(["?"]*len(kw))
        self.db.execute(f"INSERT INTO deposits_from_others({cols}) VALUES({phs})",
                        tuple(kw.values())); self.db.commit()
        return kw["deposit_id"]
    def list_deposits(self):
        return _rows(self.db.execute(
            "SELECT d.*, dep.name AS depositor_name FROM deposits_from_others d "
            "JOIN depositors dep ON dep.depositor_id=d.depositor_id ORDER BY d.created_at DESC"
        ).fetchall())
    def add_repayment(self, **kw):
        kw.setdefault("repayment_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys()); phs = ", ".join(["?"]*len(kw))
        self.db.execute(f"INSERT INTO deposit_repayments_to_others({cols}) VALUES({phs})",
                        tuple(kw.values())); self.db.commit()
    def total_repaid(self, did):
        r = self.db.execute(
            "SELECT COALESCE(SUM(amount_paid),0) AS t FROM deposit_repayments_to_others WHERE deposit_id=?",
            (did,)).fetchone(); return r["t"]

    def get_deposit(self, did):
        rows = _rows(self.db.execute(
            "SELECT d.*, dep.name AS depositor_name FROM deposits_from_others d "
            "JOIN depositors dep ON dep.depositor_id=d.depositor_id WHERE d.deposit_id=?",
            (did,)).fetchall())
        return rows[0] if rows else None

    def get_repayments(self, did):
        return _rows(self.db.execute(
            "SELECT * FROM deposit_repayments_to_others WHERE deposit_id=? ORDER BY payment_date",
            (did,)).fetchall())

    def update_status(self, did, status):
        self.db.execute("UPDATE deposits_from_others SET status=? WHERE deposit_id=?", (status, did))
        self.db.commit()

    def recalc_status(self, deposit_id):
        """Recalculate deposit status. Same algo as FDOthersPage._check_repaid."""
        dep = self.get_deposit(deposit_id)
        if not dep or dep["status"] in ("CLOSED", "REPAID"):
            return
        total = self.total_repaid(deposit_id)
        rate = dep.get("interest_rate") or 0
        if not rate:
            cv = max(dep["principal_amount"] - total, 0)
        else:
            from datetime import date as _date
            from services.loan_service import LoanService
            sd = _date.fromisoformat(dep["deposit_date"])
            dd = dep.get("expected_return_date")
            months = max(1, round((_date.fromisoformat(dd) - sd).days / 30.44)) if dd else 12
            payments = self.get_repayments(deposit_id)
            analysis = LoanService.loan_analysis(
                dep["principal_amount"], rate, months, "ANNUAL",
                total, dep["deposit_date"], payments=payments,
                method=dep.get("interest_method") or "SIMPLE"
            )
            cv = analysis["current_value"]
        if cv <= 0 and total > 0:
            self.db.execute("UPDATE deposits_from_others SET status='REPAID' WHERE deposit_id=?",
                            (deposit_id,))
        elif total > 0:
            self.db.execute("UPDATE deposits_from_others SET status='PARTIALLY_PAID' WHERE deposit_id=?",
                            (deposit_id,))
        self.db.commit()
