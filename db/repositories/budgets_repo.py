"""Budget persistence — recurring monthly budgets are stored once."""
import uuid
from datetime import datetime


def _rows(rows):
    return [dict(r) for r in rows] if rows else []


class BudgetsRepo:
    def __init__(self, db):
        self.db = db

    def list_active(self, period_type="MONTHLY"):
        return _rows(self.db.execute(
            "SELECT * FROM budgets WHERE is_active=1 AND COALESCE(period_type,'MONTHLY')=? "
            "ORDER BY scope_type, created_at", (period_type,)).fetchall())

    def list_inactive(self, period_type="MONTHLY"):
        return _rows(self.db.execute(
            "SELECT * FROM budgets WHERE is_active=0 AND COALESCE(period_type,'MONTHLY')=? "
            "ORDER BY created_at DESC", (period_type,)).fetchall())

    def exists(self, scope_type, scope_value, period_type, exclude_id=None):
        sql = ("SELECT 1 FROM budgets WHERE is_active=1 AND scope_type=? "
               "AND scope_value=? AND COALESCE(period_type,'MONTHLY')=?")
        params = [scope_type, scope_value, period_type]
        if exclude_id:
            sql += " AND budget_id != ?"
            params.append(exclude_id)
        return self.db.execute(sql, params).fetchone() is not None

    def create(self, scope_type, scope_value, limit_amount, alert_threshold_pct=80,
               period_type="MONTHLY"):
        budget_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO budgets(budget_id,scope_type,scope_value,limit_amount,"
            "alert_threshold_pct,is_active,created_at,period_type) VALUES(?,?,?,?,?,1,?,?)",
            (budget_id, scope_type, scope_value, float(limit_amount),
             float(alert_threshold_pct), datetime.now().isoformat(), period_type))
        self.db.commit()
        return budget_id

    def update(self, budget_id, scope_type, scope_value, limit_amount,
               alert_threshold_pct=80):
        self.db.execute(
            "UPDATE budgets SET scope_type=?,scope_value=?,limit_amount=?,"
            "alert_threshold_pct=? WHERE budget_id=?",
            (scope_type, scope_value, float(limit_amount),
             float(alert_threshold_pct), budget_id))
        self.db.commit()

    def deactivate(self, budget_id):
        self.db.execute("UPDATE budgets SET is_active=0 WHERE budget_id=?", (budget_id,))
        self.db.commit()

    def reactivate(self, budget_id):
        self.db.execute("UPDATE budgets SET is_active=1 WHERE budget_id=?", (budget_id,))
        self.db.commit()

    def delete(self, budget_id):
        self.db.execute("DELETE FROM budgets WHERE budget_id=?", (budget_id,))
        self.db.commit()
