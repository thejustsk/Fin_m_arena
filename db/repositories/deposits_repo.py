"""Deposits from others repository."""
import uuid
from datetime import datetime, date


def _rows(rows):
    return [dict(r) for r in rows] if rows else []


def _row(row):
    return dict(row) if row else None


class DepositsRepo:
    def __init__(self, db):
        self.db = db

    def create_depositor(self, name):
        did = str(uuid.uuid4())
        self.db.execute("INSERT INTO depositors VALUES(?,?,?)",
                        (did, name, datetime.now().isoformat()))
        self.db.commit()
        return did

    def list_depositors(self):
        return _rows(self.db.execute(
            "SELECT * FROM depositors ORDER BY name").fetchall())

    def create_deposit(self, **kw):
        kw.setdefault("deposit_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys())
        phs = ", ".join(["?"] * len(kw))
        self.db.execute(f"INSERT INTO deposits_from_others({cols}) VALUES({phs})",
                        tuple(kw.values()))
        self.db.commit()
        return kw["deposit_id"]

    def list_deposits(self):
        return _rows(self.db.execute(
            "SELECT d.*, dep.name AS depositor_name FROM deposits_from_others d "
            "JOIN depositors dep ON dep.depositor_id=d.depositor_id ORDER BY d.created_at DESC"
        ).fetchall())

    def list_active(self):
        """Only non-CLOSED deposits — for list views and KPIs."""
        return _rows(self.db.execute(
            "SELECT d.*, dep.name AS depositor_name FROM deposits_from_others d "
            "JOIN depositors dep ON dep.depositor_id=d.depositor_id "
            "WHERE d.status != 'CLOSED' ORDER BY d.created_at DESC"
        ).fetchall())

    def count_total(self):
        r = self.db.execute("SELECT COUNT(*) AS c FROM deposits_from_others").fetchone()
        return r["c"] if r else 0

    def add_repayment(self, **kw):
        kw.setdefault("repayment_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys())
        phs = ", ".join(["?"] * len(kw))
        self.db.execute(f"INSERT INTO deposit_repayments_to_others({cols}) VALUES({phs})",
                        tuple(kw.values()))
        self.db.commit()
        self.recalc_status(kw["deposit_id"])

    def total_repaid(self, did):
        r = self.db.execute(
            "SELECT COALESCE(SUM(amount_paid),0) AS t FROM deposit_repayments_to_others WHERE deposit_id=?",
            (did,)).fetchone()
        return r["t"]

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
        self.db.execute("UPDATE deposits_from_others SET status=? WHERE deposit_id=?",
                        (status, did))
        self.db.commit()

    def recalc_status(self, deposit_id):
        """Comprehensive status recalculation — considers BOTH date and amount.
        
        For interest-bearing deposits, uses LoanService analysis to determine
        if fully paid. For interest-free, uses simple principal comparison.
        
        Priority:
          1. If fully paid (current_value <= 0 and total_paid > 0) → REPAID
          2. If past expected return date and has outstanding → OVERDUE
          3. If has some payments → PARTIALLY_PAID
          4. Otherwise → ACTIVE
          
        Note: CLOSED is never changed by recalc — only by explicit user action.
        """
        dep = self.get_deposit(deposit_id)
        if not dep or dep["status"] == "CLOSED":
            return
        total = self.total_repaid(deposit_id)
        today_str = date.today().isoformat()
        return_date = dep.get("expected_return_date")
        rate = dep.get("interest_rate") or 0

        # Determine if fully paid
        if not rate:
            # Interest-free: simple principal comparison
            fully_paid = total >= dep["principal_amount"]
        elif total > 0:
            # Interest-bearing: use analysis
            sd = date.fromisoformat(dep["deposit_date"])
            dd = return_date
            months = max(1, round((date.fromisoformat(dd) - sd).days / 30.44)) if dd else 12
            payments = self.get_repayments(deposit_id)
            from services.loan_service import LoanService
            analysis = LoanService.loan_analysis(
                dep["principal_amount"], rate, months, "ANNUAL",
                total, dep["deposit_date"], payments=payments,
                method=dep.get("interest_method") or "SIMPLE"
            )
            fully_paid = analysis["current_value"] <= 0
        else:
            fully_paid = False

        if fully_paid and total > 0:
            new_status = "REPAID"
        elif return_date and return_date < today_str:
            # Past expected return date with outstanding
            new_status = "OVERDUE"
        elif total > 0:
            new_status = "PARTIALLY_PAID"
        else:
            new_status = "ACTIVE"

        if dep["status"] != new_status:
            self.db.execute(
                "UPDATE deposits_from_others SET status=? WHERE deposit_id=?",
                (new_status, deposit_id))
            self.db.commit()
