"""Loans I take (institution borrowing) repository."""
import uuid
from datetime import datetime, date

def _rows(rows): return [dict(r) for r in rows] if rows else []
def _row(row): return dict(row) if row else None

class BorrowedRepo:
    def __init__(self, db): self.db = db
    def create_lender(self, name):
        lid = str(uuid.uuid4())
        self.db.execute("INSERT INTO lenders VALUES(?,?,?)",
                        (lid, name, datetime.now().isoformat()))
        self.db.commit(); return lid
    def list_lenders(self):
        return _rows(self.db.execute("SELECT * FROM lenders ORDER BY name").fetchall())
    def create_loan(self, **kw):
        kw.setdefault("loan_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys()); phs = ", ".join(["?"]*len(kw))
        self.db.execute(f"INSERT INTO borrowed_loans({cols}) VALUES({phs})",
                        tuple(kw.values())); self.db.commit()
        return kw["loan_id"]
    def list_loans(self):
        return _rows(self.db.execute(
            "SELECT bl.*, l.name AS lender_name FROM borrowed_loans bl "
            "JOIN lenders l ON l.lender_id=bl.lender_id ORDER BY bl.created_at DESC"
        ).fetchall())
    def get_loan(self, lid):
        return _row(self.db.execute(
            "SELECT bl.*, l.name AS lender_name FROM borrowed_loans bl "
            "JOIN lenders l ON l.lender_id=bl.lender_id WHERE bl.loan_id=?",
            (lid,)).fetchone())
    def add_repayment(self, **kw):
        kw.setdefault("repayment_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys()); phs = ", ".join(["?"]*len(kw))
        self.db.execute(f"INSERT INTO borrowed_loan_repayments({cols}) VALUES({phs})",
                        tuple(kw.values())); self.db.commit()
        self._sync_status(kw["loan_id"])
    def total_repaid(self, lid):
        r = self.db.execute(
            "SELECT COALESCE(SUM(amount_paid),0) AS t FROM borrowed_loan_repayments WHERE loan_id=?",
            (lid,)).fetchone(); return r["t"]

    def sync_overdue(self):
        today = date.today().isoformat()
        self.db.execute(
            "UPDATE borrowed_loans SET status='OVERDUE' WHERE status IN ('ACTIVE','PARTIALLY_PAID') "
            "AND due_date IS NOT NULL AND due_date < ?", (today,))
        self.db.commit()

    def update_status(self, loan_id, status):
        self.db.execute("UPDATE borrowed_loans SET status=? WHERE loan_id=?", (status, loan_id))
        self.db.commit()

    def recalc_status(self, loan_id):
        """Recalculate status — same algo as _sync_status used by add_repayment."""
        self._sync_status(loan_id)

    def get_repayments(self, loan_id):
        return _rows(self.db.execute(
            "SELECT * FROM borrowed_loan_repayments WHERE loan_id=? ORDER BY payment_date",
            (loan_id,)).fetchall())

    # ── internal: auto-detect REPAID / PARTIALLY_PAID ────────────────
    def _sync_status(self, loan_id):
        loan = self.get_loan(loan_id)
        if not loan or loan["status"] in ("CLOSED", "REPAID"):
            return
        total = self.total_repaid(loan_id)
        from services.loan_service import LoanService
        start = loan["start_date"]
        due = loan.get("due_date")
        if due:
            sd = date.fromisoformat(start)
            dd = date.fromisoformat(due)
            months = max(1, round((dd - sd).days / 30.44))
        else:
            months = 12
        freq = loan.get("interest_type") or "ANNUAL"
        analysis = LoanService.loan_analysis(
            loan["principal_amount"], loan["interest_rate"] or 0,
            months, freq, total, start
        )
        if analysis["current_value"] <= 0 and total > 0:
            self.db.execute("UPDATE borrowed_loans SET status='REPAID' WHERE loan_id=?",
                            (loan_id,))
        elif total > 0:
            self.db.execute("UPDATE borrowed_loans SET status='PARTIALLY_PAID' WHERE loan_id=?",
                            (loan_id,))
        self.db.commit()
