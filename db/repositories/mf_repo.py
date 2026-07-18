"""Mutual Funds repository."""
import uuid
from datetime import datetime

def _rows(rows): return [dict(r) for r in rows] if rows else []

class MFRepo:
    def __init__(self, db): self.db = db
    def create_scheme(self, **kw):
        kw.setdefault("scheme_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys()); phs = ", ".join(["?"]*len(kw))
        self.db.execute(f"INSERT INTO mf_schemes({cols}) VALUES({phs})",
                        tuple(kw.values())); self.db.commit()
        return kw["scheme_id"]
    def list_schemes(self):
        return _rows(self.db.execute(
            "SELECT * FROM mf_schemes WHERE is_active=1").fetchall())
    def add_txn(self, **kw):
        kw.setdefault("mf_txn_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        if "units" not in kw and "amount" in kw and "nav" in kw and kw["nav"] > 0:
            kw["units"] = round(kw["amount"] / kw["nav"], 4)
        cols = ", ".join(kw.keys()); phs = ", ".join(["?"]*len(kw))
        self.db.execute(f"INSERT INTO mf_transactions({cols}) VALUES({phs})",
                        tuple(kw.values())); self.db.commit()
    def holdings(self, sid):
        rows = _rows(self.db.execute(
            "SELECT txn_type, SUM(amount) AS amt, SUM(units) AS u "
            "FROM mf_transactions WHERE scheme_id=? GROUP BY txn_type",
            (sid,)).fetchall())
        inv = red = units = 0
        for r in rows:
            if r["txn_type"] in ("PURCHASE","SIP","SWITCH_IN"):
                inv += r["amt"]; units += r["u"]
            else:
                red += r["amt"]; units -= r["u"]
        return {"invested": inv, "redeemed": red, "units": units}
