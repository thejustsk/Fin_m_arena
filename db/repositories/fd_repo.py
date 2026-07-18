"""Fixed Deposits repository."""
import uuid
from datetime import datetime

def _rows(rows): return [dict(r) for r in rows] if rows else []

class FDRepo:
    def __init__(self, db): self.db = db
    def create(self, **kw):
        kw.setdefault("fd_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        if "maturity_amount" not in kw and all(k in kw for k in
                ("principal_amount","interest_rate","start_date","maturity_date")):
            from services.fd_service import FDService
            kw["maturity_amount"] = FDService.maturity(
                kw["principal_amount"], kw["interest_rate"],
                kw["start_date"], kw["maturity_date"])
        cols = ", ".join(kw.keys()); phs = ", ".join(["?"]*len(kw))
        self.db.execute(f"INSERT INTO fixed_deposits({cols}) VALUES({phs})",
                        tuple(kw.values())); self.db.commit()
        return kw["fd_id"]
    def list_all(self):
        return _rows(self.db.execute(
            "SELECT fd.*, a.display_name AS account_name FROM fixed_deposits fd "
            "LEFT JOIN accounts a ON a.account_id=fd.bank_account_id ORDER BY fd.created_at DESC"
        ).fetchall())
