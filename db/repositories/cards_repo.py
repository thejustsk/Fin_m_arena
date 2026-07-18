"""Cards repository — CRUD for credit cards and billing cycles."""
import uuid
from datetime import datetime

def _rows(rows):
    return [dict(r) for r in rows] if rows else []


class CardsRepo:
    def __init__(self, db):
        self.db = db

    # ── Cards CRUD ──

    def list_active(self):
        """All active cards with their account info joined."""
        return _rows(self.db.execute("""
            SELECT c.*, a.display_name AS acct_name, a.credit_limit AS acct_limit,
                   a.opening_balance, a.color_hex
            FROM cards c
            JOIN accounts a ON a.account_id = c.account_id
            WHERE c.is_active = 1
            ORDER BY c.sort_order, c.created_at
        """).fetchall())

    def list_credit_cards(self):
        """Legacy: list CREDIT_CARD accounts (used by setup/settings)."""
        return _rows(self.db.execute(
            "SELECT * FROM accounts WHERE account_type='CREDIT_CARD' AND is_active=1"
        ).fetchall())

    def get(self, card_id):
        r = self.db.execute(
            "SELECT c.*, a.display_name AS acct_name, a.credit_limit AS acct_limit, "
            "a.opening_balance FROM cards c JOIN accounts a ON a.account_id=c.account_id "
            "WHERE c.card_id=?", (card_id,)).fetchone()
        return dict(r) if r else None

    def get_by_account(self, account_id):
        r = self.db.execute(
            "SELECT * FROM cards WHERE account_id=? AND is_active=1", (account_id,)
        ).fetchone()
        return dict(r) if r else None

    def create(self, **kw):
        kw.setdefault("card_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys())
        phs = ", ".join(["?"] * len(kw))
        self.db.execute(f"INSERT INTO cards({cols}) VALUES({phs})", tuple(kw.values()))
        self.db.commit()
        return kw["card_id"]

    def update(self, card_id, **kw):
        sets = ", ".join(f"{k}=?" for k in kw)
        self.db.execute(f"UPDATE cards SET {sets} WHERE card_id=?", (*kw.values(), card_id))
        self.db.commit()

    def delete(self, card_id):
        self.db.execute("UPDATE cards SET is_active=0 WHERE card_id=?", (card_id,))
        self.db.commit()

    # ── Card cycles ──

    def get_cycles(self, account_id):
        return _rows(self.db.execute(
            "SELECT * FROM card_cycles WHERE account_id=? ORDER BY statement_date DESC",
            (account_id,)).fetchall())

    def latest_cycle(self, account_id):
        r = self.db.execute(
            "SELECT * FROM card_cycles WHERE account_id=? ORDER BY statement_date DESC LIMIT 1",
            (account_id,)).fetchone()
        return dict(r) if r else None

    def add_cycle(self, **kw):
        kw.setdefault("cycle_id", str(uuid.uuid4()))
        kw.setdefault("source", "MANUAL")
        kw.setdefault("detected_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys())
        phs = ", ".join(["?"] * len(kw))
        self.db.execute(f"INSERT INTO card_cycles({cols}) VALUES({phs})", tuple(kw.values()))
        self.db.commit()
        return kw["cycle_id"]

    # ── Helpers ──

    def get_card_spends(self, account_id, date_from, date_to):
        """Sum of debits for a card account between two dates."""
        r = self.db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions "
            "WHERE account_id=? AND tx_type='DEBIT' AND tx_date>=? AND tx_date<=?",
            (account_id, date_from, date_to)).fetchone()
        return r[0] if r else 0

    def get_card_payments(self, account_id, date_from, date_to):
        """Sum of credits (payments) for a card account between two dates."""
        r = self.db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions "
            "WHERE account_id=? AND tx_type='CREDIT' AND tx_date>=? AND tx_date<=?",
            (account_id, date_from, date_to)).fetchone()
        return r[0] if r else 0

    def get_recent_transactions(self, account_id, limit=10):
        """Recent transactions for a card."""
        return _rows(self.db.execute(
            "SELECT t.*, c.display_name AS cat_name, c.color_hex AS cat_color, "
            "pm.display_name AS method_name "
            "FROM transactions t "
            "LEFT JOIN categories c ON c.category_id = t.category "
            "LEFT JOIN payment_methods pm ON pm.method_id = t.pay_method "
            "WHERE t.account_id=? ORDER BY t.tx_date DESC, t.created_at DESC LIMIT ?",
            (account_id, limit)).fetchall())
