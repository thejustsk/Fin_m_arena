"""Recurring rules repository."""
import uuid
from datetime import datetime

def _rows(rows): return [dict(r) for r in rows] if rows else []

class RecurringRepo:
    def __init__(self, db): self.db = db
    def list_active(self):
        return _rows(self.db.execute(
            "SELECT * FROM recurring_rules WHERE is_active=1 ORDER BY next_run_date"
        ).fetchall())
    def create(self, **kw):
        kw.setdefault("rule_id", str(uuid.uuid4()))
        cols = ", ".join(kw.keys()); phs = ", ".join(["?"]*len(kw))
        self.db.execute(f"INSERT INTO recurring_rules({cols}) VALUES({phs})",
                        tuple(kw.values())); self.db.commit()
