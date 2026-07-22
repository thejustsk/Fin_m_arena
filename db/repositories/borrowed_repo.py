"""Loans I take (institution borrowing) repository."""
import uuid
from datetime import datetime, date


def _rows(rows):
    return [dict(r) for r in rows] if rows else []


def _row(row):
    return dict(row) if row else None


class BorrowedRepo:
    def __init__(self, db):
        self.db = db

    def create_lender(self, name):
        lid = str(uuid.uuid4())
        self.db.execute("INSERT INTO lenders VALUES(?,?,?)",
                        (lid, name, datetime.now().isoformat()))
        self.db.commit()
        return lid

    def list_lenders(self):
        return _rows(self.db.execute(
            "SELECT * FROM lenders ORDER BY name").fetchall())

    def create_loan(self, **kw):
        kw.setdefault("loan_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys())
        phs = ", ".join(["?"] * len(kw))
        self.db.execute(f"INSERT INTO borrowed_loans({cols}) VALUES({phs})",
                        tuple(kw.values()))
        self.db.commit()
        return kw["loan_id"]

    def list_loans(self):
        return _rows(self.db.execute(
            "SELECT bl.*, l.name AS lender_name FROM borrowed_loans bl "
            "JOIN lenders l ON l.lender_id=bl.lender_id ORDER BY bl.created_at DESC"
        ).fetchall())

    def list_active(self):
        """Only non-CLOSED loans — for list views and KPIs."""
        return _rows(self.db.execute(
            "SELECT bl.*, l.name AS lender_name FROM borrowed_loans bl "
            "JOIN lenders l ON l.lender_id=bl.lender_id "
            "WHERE bl.status != 'CLOSED' ORDER BY bl.created_at DESC"
        ).fetchall())

    def count_total(self):
        r = self.db.execute("SELECT COUNT(*) AS c FROM borrowed_loans").fetchone()
        return r["c"] if r else 0

    def get_loan(self, lid):
        return _row(self.db.execute(
            "SELECT bl.*, l.name AS lender_name FROM borrowed_loans bl "
            "JOIN lenders l ON l.lender_id=bl.lender_id WHERE bl.loan_id=?",
            (lid,)).fetchone())

    def add_repayment(self, **kw):
        kw.setdefault("repayment_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys())
        phs = ", ".join(["?"] * len(kw))
        self.db.execute(f"INSERT INTO borrowed_loan_repayments({cols}) VALUES({phs})",
                        tuple(kw.values()))
        self.db.commit()
        self.recalc_status(kw["loan_id"])

    def total_repaid(self, lid):
        r = self.db.execute(
            "SELECT COALESCE(SUM(amount_paid),0) AS t FROM borrowed_loan_repayments WHERE loan_id=?",
            (lid,)).fetchone()
        return r["t"]

    def sync_overdue(self):
        """Batch: mark ACTIVE/PARTIALLY_PAID loans past due date as OVERDUE."""
        today = date.today().isoformat()
        self.db.execute(
            "UPDATE borrowed_loans SET status='OVERDUE' WHERE status IN ('ACTIVE','PARTIALLY_PAID') "
            "AND due_date IS NOT NULL AND due_date < ?", (today,))
        self.db.commit()

    def update_status(self, loan_id, status):
        self.db.execute("UPDATE borrowed_loans SET status=? WHERE loan_id=?",
                        (status, loan_id))
        self.db.commit()

    def recalc_status(self, loan_id):
        """Comprehensive status recalculation — considers BOTH date and amount.
        
        Uses LoanService analysis to determine if fully paid (including interest).
        
        Priority:
          1. If fully paid (current_value <= 0 and total_paid > 0) → REPAID
          2. If past due date and has outstanding → OVERDUE
          3. If has some payments → PARTIALLY_PAID
          4. Otherwise → ACTIVE
          
        Note: CLOSED is never changed by recalc — only by explicit user action.
        """
        loan = self.get_loan(loan_id)
        if not loan or loan["status"] == "CLOSED":
            return
        total = self.total_repaid(loan_id)
        today_str = date.today().isoformat()
        due = loan.get("due_date")

        # Use analysis to check if fully paid (accounts for interest)
        start = loan["start_date"]
        if due:
            sd = date.fromisoformat(start)
            dd = date.fromisoformat(due)
            months = max(1, round((dd - sd).days / 30.44))
        else:
            months = 12
        freq = loan.get("interest_type") or "ANNUAL"
        method = loan.get("interest_method") or "COMPOUND"

        # Only run analysis if there's interest — otherwise use simple comparison
        rate = loan.get("interest_rate") or 0
        if rate > 0 and total > 0:
            from services.loan_service import LoanService
            analysis = LoanService.loan_analysis(
                loan["principal_amount"], rate, months, freq,
                total, start, method=method
            )
            fully_paid = analysis["current_value"] <= 0
        else:
            fully_paid = total >= loan["principal_amount"]

        if fully_paid and total > 0:
            new_status = "REPAID"
        elif due and due < today_str:
            # Past due date with outstanding
            new_status = "OVERDUE"
        elif total > 0:
            new_status = "PARTIALLY_PAID"
        else:
            new_status = "ACTIVE"

        if loan["status"] != new_status:
            self.db.execute("UPDATE borrowed_loans SET status=? WHERE loan_id=?",
                            (new_status, loan_id))
            self.db.commit()

    def get_repayments(self, loan_id):
        return _rows(self.db.execute(
            "SELECT * FROM borrowed_loan_repayments WHERE loan_id=? ORDER BY payment_date",
            (loan_id,)).fetchall())
