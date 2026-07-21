"""Loans I give repository."""
import uuid
from datetime import datetime, date


def _rows(rows):
    return [dict(r) for r in rows] if rows else []


def _row(row):
    return dict(row) if row else None


class LoansRepo:
    def __init__(self, db):
        self.db = db

    def create_borrower(self, name):
        bid = str(uuid.uuid4())
        self.db.execute("INSERT INTO borrowers VALUES(?,?,?)",
                        (bid, name, datetime.now().isoformat()))
        self.db.commit()
        return bid

    def list_borrowers(self):
        return _rows(self.db.execute(
            "SELECT * FROM borrowers ORDER BY name").fetchall())

    def create_loan(self, **kw):
        kw.setdefault("loan_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys())
        phs = ", ".join(["?"] * len(kw))
        self.db.execute(f"INSERT INTO loans({cols}) VALUES({phs})",
                        tuple(kw.values()))
        self.db.commit()
        return kw["loan_id"]

    def list_loans(self, status=None):
        wh, p = [], []
        if status:
            wh.append("l.status=?"); p.append(status)
        w = " AND ".join(wh) if wh else "1=1"
        return _rows(self.db.execute(
            f"SELECT l.*, b.name AS borrower_name FROM loans l "
            f"JOIN borrowers b ON b.borrower_id=l.borrower_id "
            f"WHERE {w} ORDER BY l.created_at DESC", p).fetchall())

    def get_loan(self, loan_id):
        return _row(self.db.execute(
            "SELECT l.*, b.name AS borrower_name FROM loans l "
            "JOIN borrowers b ON b.borrower_id=l.borrower_id "
            "WHERE l.loan_id=?", (loan_id,)).fetchone())

    def add_repayment(self, **kw):
        kw.setdefault("repayment_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys())
        phs = ", ".join(["?"] * len(kw))
        self.db.execute(f"INSERT INTO repayments({cols}) VALUES({phs})",
                        tuple(kw.values()))
        self.db.commit()
        total = self.total_repaid(kw["loan_id"])
        loan = self.get_loan(kw["loan_id"])
        if loan:
            if total >= loan["loan_amount"]:
                self.db.execute("UPDATE loans SET status='CLOSED' WHERE loan_id=?",
                                (kw["loan_id"],))
            elif total > 0:
                self.db.execute("UPDATE loans SET status='PARTIALLY_PAID' WHERE loan_id=?",
                                (kw["loan_id"],))
        self.db.commit()

    def get_repayments(self, loan_id):
        return _rows(self.db.execute(
            "SELECT * FROM repayments WHERE loan_id=? ORDER BY payment_date",
            (loan_id,)).fetchall())

    def total_repaid(self, loan_id):
        r = self.db.execute(
            "SELECT COALESCE(SUM(amount_paid),0) AS t FROM repayments WHERE loan_id=?",
            (loan_id,)).fetchone()
        return r["t"]

    def sync_overdue(self):
        today = date.today().isoformat()
        self.db.execute(
            "UPDATE loans SET status='OVERDUE' WHERE status='ACTIVE' AND due_date IS NOT NULL AND due_date < ?",
            (today,))
        self.db.commit()

    def update_status(self, loan_id, status):
        self.db.execute("UPDATE loans SET status=? WHERE loan_id=?", (status, loan_id))
        self.db.commit()
