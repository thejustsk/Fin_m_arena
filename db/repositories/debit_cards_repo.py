"""Debit Cards repository — CRUD for debit cards linked to current accounts."""
import uuid
from datetime import datetime


def _rows(rows):
    return [dict(r) for r in rows] if rows else []


class DebitCardsRepo:
    def __init__(self, db):
        self.db = db

    def list_active(self):
        return _rows(self.db.execute("""
            SELECT dc.*, a.display_name AS acct_name, a.short_label AS acct_label
            FROM debit_cards dc
            JOIN accounts a ON a.account_id = dc.account_id
            WHERE dc.is_active = 1
            ORDER BY dc.sort_order, dc.created_at
        """).fetchall())

    def list_closed(self):
        return _rows(self.db.execute("""
            SELECT dc.*, a.display_name AS acct_name, a.short_label AS acct_label
            FROM debit_cards dc
            JOIN accounts a ON a.account_id = dc.account_id
            WHERE dc.is_active = 0
            ORDER BY dc.sort_order, dc.created_at
        """).fetchall())

    def get(self, card_id):
        r = self.db.execute(
            "SELECT dc.*, a.display_name AS acct_name, a.short_label AS acct_label "
            "FROM debit_cards dc JOIN accounts a ON a.account_id=dc.account_id "
            "WHERE dc.card_id=?", (card_id,)).fetchone()
        return dict(r) if r else None

    def get_by_account(self, account_id):
        return _rows(self.db.execute(
            "SELECT * FROM debit_cards WHERE account_id=? ORDER BY sort_order",
            (account_id,)).fetchall())

    def create(self, **kw):
        kw.setdefault("card_id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        cols = ", ".join(kw.keys())
        phs = ", ".join(["?"] * len(kw))
        self.db.execute(f"INSERT INTO debit_cards({cols}) VALUES({phs})", tuple(kw.values()))
        self.db.commit()
        return kw["card_id"]

    def update(self, card_id, **kw):
        sets = ", ".join(f"{k}=?" for k in kw)
        self.db.execute(f"UPDATE debit_cards SET {sets} WHERE card_id=?", (*kw.values(), card_id))
        self.db.commit()

    def toggle_active(self, card_id):
        card = self.get(card_id)
        if not card:
            return
        new_val = 0 if card.get("is_active", 1) else 1
        self.update(card_id, is_active=new_val)
        return new_val

    def delete(self, card_id):
        self.db.execute("DELETE FROM debit_cards WHERE card_id=?", (card_id,))
        self.db.commit()

    def count_active(self):
        r = self.db.execute("SELECT COUNT(*) FROM debit_cards WHERE is_active=1").fetchone()
        return r[0] if r else 0

    def count_total(self):
        r = self.db.execute("SELECT COUNT(*) FROM debit_cards").fetchone()
        return r[0] if r else 0
