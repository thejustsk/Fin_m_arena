"""Audit trail repository."""
import uuid
from datetime import datetime


def _rows(rows):
    return [dict(r) for r in rows] if rows else []


class AuditRepo:
    def __init__(self, db):
        self.db = db

    def log(self, tx_id, field, old_val, new_val, reason=None):
        self.db.execute(
            "INSERT INTO audit_log(transaction_id,field_changed,old_value,"
            "new_value,changed_at,change_reason) VALUES(?,?,?,?,?,?)",
            (tx_id, field,
             str(old_val) if old_val is not None else None,
             str(new_val) if new_val is not None else None,
             datetime.now().isoformat(), reason))
        self.db.commit()

    def get_for_tx(self, tx_id):
        return _rows(self.db.execute(
            "SELECT * FROM audit_log WHERE transaction_id=? ORDER BY changed_at",
            (tx_id,)).fetchall())
