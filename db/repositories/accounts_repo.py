"""Accounts repository — plain SQL, no PyQt5 imports."""
import uuid
from datetime import datetime


def _rows(rows):
    return [dict(r) for r in rows] if rows else []


def _row(row):
    return dict(row) if row else None


class AccountsRepo:
    def __init__(self, db):
        self.db = db

    def list_active(self):
        return _rows(self.db.execute(
            "SELECT * FROM accounts WHERE is_active=1 ORDER BY sort_order").fetchall())

    def list_all(self):
        return _rows(self.db.execute(
            "SELECT * FROM accounts ORDER BY sort_order").fetchall())

    def get(self, account_id):
        return _row(self.db.execute(
            "SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone())

    def exists(self, display_name):
        """Check if an account with this name already exists."""
        r = self.db.execute(
            "SELECT 1 FROM accounts WHERE LOWER(display_name)=LOWER(?)",
            (display_name,)).fetchone()
        return r is not None

    def create(self, **kw):
        kw.setdefault("account_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        # Duplicate check
        if "display_name" in kw and self.exists(kw["display_name"]):
            raise ValueError(f"Account '{kw['display_name']}' already exists")
        cols = ", ".join(kw.keys())
        phs = ", ".join(["?"] * len(kw))
        self.db.execute(f"INSERT INTO accounts({cols}) VALUES({phs})", tuple(kw.values()))
        self.db.commit()
        return kw["account_id"]

    def update(self, account_id, **kw):
        sets = ", ".join(f"{k}=?" for k in kw)
        self.db.execute(f"UPDATE accounts SET {sets} WHERE account_id=?",
                        (*kw.values(), account_id))
        self.db.commit()

    def get_balance(self, account_id):
        r = self.db.execute("""
            SELECT a.opening_balance + COALESCE(SUM(
                CASE WHEN t.tx_type='CREDIT' THEN t.amount ELSE -t.amount END), 0) AS bal
            FROM accounts a LEFT JOIN transactions t ON t.account_id = a.account_id
            WHERE a.account_id = ?
        """, (account_id,)).fetchone()
        return r["bal"] if r else 0

    def get_all_balances(self):
        return _rows(self.db.execute("""
            SELECT a.*, a.opening_balance + COALESCE(SUM(
                CASE WHEN t.tx_type='CREDIT' THEN t.amount ELSE -t.amount END), 0) AS balance
            FROM accounts a LEFT JOIN transactions t ON t.account_id = a.account_id
            WHERE a.is_active = 1 GROUP BY a.account_id ORDER BY a.sort_order
        """).fetchall())

    def get_net_worth(self):
        total = 0
        for r in self.get_all_balances():
            if r["account_type"] == "CREDIT_CARD":
                total += -abs(r["balance"]) if r["balance"] > 0 else r["balance"]
            else:
                total += r["balance"]
        return total
