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
