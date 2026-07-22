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

    def list_active(self):
        """Only non-CLOSED loans — for list views and KPIs."""
        return _rows(self.db.execute(
            "SELECT l.*, b.name AS borrower_name FROM loans l "
            "JOIN borrowers b ON b.borrower_id=l.borrower_id "
            "WHERE l.status != 'CLOSED' ORDER BY l.created_at DESC"
        ).fetchall())

    def count_total(self):
        """Total loan count including CLOSED — for dashboard KPI."""
        r = self.db.execute("SELECT COUNT(*) AS c FROM loans").fetchone()
        return r["c"] if r else 0

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
        self.recalc_status(kw["loan_id"])

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
        """Batch: set ACTIVE loans past due date to OVERDUE (only if not fully paid)."""
        today = date.today().isoformat()
        # Only mark ACTIVE loans as OVERDUE; PARTIALLY_PAID stays as-is for now
        self.db.execute(
            "UPDATE loans SET status='OVERDUE' WHERE status='ACTIVE' "
            "AND due_date IS NOT NULL AND due_date < ?", (today,))
        self.db.commit()

    def update_status(self, loan_id, status):
        self.db.execute("UPDATE loans SET status=? WHERE loan_id=?", (status, loan_id))
        self.db.commit()

    def recalc_status(self, loan_id):
        """Comprehensive status recalculation — considers BOTH date and amount.
        
        Priority:
          1. If fully paid (total >= principal) → REPAID (amount trumps date)
          2. If past due date and has outstanding → OVERDUE (date-based)
          3. If has some payments → PARTIALLY_PAID (amount-based)
          4. Otherwise → ACTIVE
          
        Note: CLOSED is never changed by recalc — only by explicit user action.
        """
        loan = self.get_loan(loan_id)
        if not loan or loan["status"] == "CLOSED":
            return
        total = self.total_repaid(loan_id)
        today_str = date.today().isoformat()
        due = loan.get("due_date")

        if total >= loan["loan_amount"]:
            # Fully paid — REPAID regardless of date
            new_status = "REPAID"
        elif due and due < today_str:
            # Past due date with outstanding balance — OVERDUE
            new_status = "OVERDUE"
        elif total > 0:
            # Some payment made, not fully paid, not overdue
            new_status = "PARTIALLY_PAID"
        else:
            # No payments yet
            new_status = "ACTIVE"

        if loan["status"] != new_status:
            self.db.execute("UPDATE loans SET status=? WHERE loan_id=?",
                            (new_status, loan_id))
            self.db.commit()
