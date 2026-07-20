"""Transactions repository — plain SQL, no PyQt5 imports."""
import uuid
from datetime import datetime


def _rows(rows):
    return [dict(r) for r in rows] if rows else []


def _row(row):
    return dict(row) if row else None


class TransactionsRepo:
    def __init__(self, db):
        self.db = db

    def create(self, **kw):
        kw.setdefault("id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys())
        phs = ", ".join(["?"] * len(kw))
        self.db.execute(f"INSERT INTO transactions({cols}) VALUES({phs})",
                        tuple(kw.values()))
        self.db.commit()
        return kw["id"]

    def get(self, tx_id):
        return _row(self.db.execute(
            "SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone())

    def get_detailed(self, tx_id):
        """Get single transaction with all JOINed fields (cat_name, method_name, account_name)."""
        return _row(self.db.execute("""
            SELECT t.*, a.display_name AS account_name, a.account_type,
                c.display_name AS cat_name, c.color_hex AS cat_color,
                pm.display_name AS method_name
            FROM transactions t
            LEFT JOIN accounts a ON a.account_id = t.account_id
            LEFT JOIN categories c ON c.category_id = t.category
            LEFT JOIN payment_methods pm ON pm.method_id = t.pay_method
            WHERE t.id = ?
        """, (tx_id,)).fetchone())

    def update(self, tx_id, **kw):
        sets = ", ".join(f"{k}=?" for k in kw)
        self.db.execute(f"UPDATE transactions SET {sets} WHERE id=?",
                        (*kw.values(), tx_id))
        self.db.commit()

    def delete(self, tx_id):
        self.db.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        self.db.commit()

    def list_filters(self, account_id=None, category=None, tx_type=None,
                     date_from=None, date_to=None, kind=None,
                     limit=500, offset=0):
        wh, p = [], []
        if account_id: wh.append("t.account_id=?"); p.append(account_id)
        if category: wh.append("t.category=?"); p.append(category)
        if tx_type: wh.append("t.tx_type=?"); p.append(tx_type)
        if date_from: wh.append("t.tx_date>=?"); p.append(date_from)
        if date_to: wh.append("t.tx_date<=?"); p.append(date_to)
        if kind: wh.append("t.transaction_kind=?"); p.append(kind)
        w = " AND ".join(wh) if wh else "1=1"
        sql = f"""
            SELECT t.*, a.display_name AS account_name, a.account_type,
                c.display_name AS cat_name, c.color_hex AS cat_color,
                pm.display_name AS method_name
            FROM transactions t
            LEFT JOIN accounts a ON a.account_id = t.account_id
            LEFT JOIN categories c ON c.category_id = t.category
            LEFT JOIN payment_methods pm ON pm.method_id = t.pay_method
            WHERE {w} ORDER BY t.tx_date DESC, t.created_at DESC
            LIMIT ? OFFSET ?
        """
        p.extend([limit, offset])
        return _rows(self.db.execute(sql, p).fetchall())

    def get_monthly(self, y, m):
        d_from = f"{y:04d}-{m:02d}-01"
        if m == 12:
            d_to = f"{y:04d}-12-31"
        else:
            d_to = f"{y:04d}-{m+1:02d}-01"
        return self.list_filters(date_from=d_from, date_to=d_to, limit=10000)

    def most_recent_id(self):
        r = self.db.execute(
            "SELECT id FROM transactions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return r["id"] if r else None
