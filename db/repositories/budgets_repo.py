"""Budgets repository."""
import uuid
from datetime import datetime

def _rows(rows): return [dict(r) for r in rows] if rows else []

class BudgetsRepo:
    def __init__(self, db): self.db = db
    def list_active(self):
        return _rows(self.db.execute(
            "SELECT * FROM budgets WHERE is_active=1").fetchall())
    def create(self, **kw):
        kw.setdefault("budget_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys()); phs = ", ".join(["?"]*len(kw))
        self.db.execute(f"INSERT INTO budgets({cols}) VALUES({phs})",
                        tuple(kw.values())); self.db.commit()
