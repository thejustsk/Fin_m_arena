"""Split Expense repository — CRUD + balance calculations."""
import uuid
from datetime import date


def _uid():
    return str(uuid.uuid4())


def _now():
    return date.today().isoformat()


class SplitRepo:
    def __init__(self, db):
        self.db = db

    # ── Contacts (global list) ──
    def create_contact(self, name, phone=None, is_self=0):
        cid = _uid()
        self.db.execute(
            "INSERT INTO split_contacts(contact_id, name, phone, is_self, created_at) VALUES(?,?,?,?,?)",
            (cid, name, phone, is_self, _now()))
        self.db.commit()
        return cid

    def get_self_contact(self):
        """Get or create the 'self' contact, named after the user profile."""
        # If more than one is_self row exists, prefer the one actually used by
        # the data. An unqualified SELECT can return an empty duplicate, which
        # makes every balance read as zero. run_migrations() merges duplicates,
        # but ordering here keeps the answer right even before that runs.
        row = self.db.execute(
            "SELECT c.contact_id FROM split_contacts c "
            "WHERE c.is_self=1 "
            "ORDER BY ("
            "  (SELECT COUNT(*) FROM split_group_members m WHERE m.contact_id=c.contact_id)"
            " + (SELECT COUNT(*) FROM split_shares s WHERE s.contact_id=c.contact_id)"
            " + (SELECT COUNT(*) FROM split_expenses e WHERE e.paid_by=c.contact_id)"
            ") DESC, c.created_at ASC LIMIT 1").fetchone()
        if row:
            return row["contact_id"]
        name = "You"
        try:
            from services.user_service import get_user_name
            name = get_user_name(self.db) or "You"
        except Exception:
            pass
        return self.create_contact(name, is_self=1)

    def self_display_name(self):
        """Label for the current user in Split UIs — "Alex (You)" or "You"."""
        try:
            row = self.db.execute(
                "SELECT name FROM split_contacts WHERE is_self=1").fetchone()
            nm = (row["name"] or "").strip() if row else ""
        except Exception:
            nm = ""
        if not nm:
            try:
                from services.user_service import get_user_name
                nm = get_user_name(self.db)
            except Exception:
                nm = ""
        if not nm or nm.lower() == "you":
            return "You"
        return f"{nm} (You)"

    def display_name_for(self, contact):
        """Display label for a contact row/dict — adds "(You)" for self."""
        if contact is None:
            return ""
        try:
            is_self = contact["is_self"]
            name = contact["name"]
        except (KeyError, IndexError, TypeError):
            return ""
        name = (name or "").strip()
        if not is_self:
            return name
        if not name or name.lower() == "you":
            return "You"
        return f"{name} (You)"

    def list_contacts(self):
        return self.db.execute("SELECT * FROM split_contacts ORDER BY is_self DESC, name ASC").fetchall()

    def update_contact(self, contact_id, name=None, phone=None):
        if name is not None:
            self.db.execute("UPDATE split_contacts SET name=? WHERE contact_id=?", (name, contact_id))
        if phone is not None:
            self.db.execute("UPDATE split_contacts SET phone=? WHERE contact_id=?", (phone, contact_id))
        self.db.commit()

    def delete_contact(self, contact_id):
        self.db.execute("DELETE FROM split_contacts WHERE contact_id=?", (contact_id,))
        self.db.commit()

    # ── Groups ──
    def create_group(self, name, member_contact_ids):
        gid = _uid()
        self.db.execute("INSERT INTO split_groups(group_id, name, created_at) VALUES(?,?,?)",
                        (gid, name, _now()))
        for cid in member_contact_ids:
            mid = _uid()
            self.db.execute("INSERT INTO split_group_members(member_id, group_id, contact_id, created_at) VALUES(?,?,?,?)",
                            (mid, gid, cid, _now()))
        self.db.commit()
        return gid

    def list_groups(self):
        return self.db.execute("SELECT * FROM split_groups WHERE is_active=1 ORDER BY created_at DESC").fetchall()

    def get_group(self, group_id):
        return self.db.execute("SELECT * FROM split_groups WHERE group_id=?", (group_id,)).fetchone()

    def list_group_members(self, group_id):
        return self.db.execute(
            "SELECT m.*, c.name, c.phone, c.is_self FROM split_group_members m "
            "JOIN split_contacts c ON c.contact_id=m.contact_id "
            "WHERE m.group_id=? ORDER BY c.is_self DESC, c.name ASC",
            (group_id,)).fetchall()

    def update_group(self, group_id, name=None, is_active=None):
        if name is not None:
            self.db.execute("UPDATE split_groups SET name=? WHERE group_id=?", (name, group_id))
        if is_active is not None:
            self.db.execute("UPDATE split_groups SET is_active=? WHERE group_id=?", (is_active, group_id))
        self.db.commit()

    # ── Expenses ──
    def create_expense(self, group_id, paid_by, amount, description, expense_date, split_type, shares, linked_txn_id=None):
        """Create expense with shares.
        
        shares: list of (contact_id, share_amount)
        """
        eid = _uid()
        self.db.execute(
            "INSERT INTO split_expenses(expense_id, group_id, paid_by, amount, description, expense_date, split_type, created_at, linked_txn_id) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (eid, group_id, paid_by, amount, description, expense_date, split_type, _now(), linked_txn_id))
        for contact_id, share_amount in shares:
            sid = _uid()
            self.db.execute(
                "INSERT INTO split_shares(share_id, expense_id, contact_id, share_amount, created_at) VALUES(?,?,?,?,?)",
                (sid, eid, contact_id, share_amount, _now()))
        self.db.commit()
        return eid

    def list_expenses(self, group_id):
        return self.db.execute(
            "SELECT e.*, c.name AS paid_by_name FROM split_expenses e "
            "JOIN split_contacts c ON c.contact_id=e.paid_by "
            "WHERE e.group_id=? ORDER BY e.expense_date DESC",
            (group_id,)).fetchall()

    def get_expense(self, expense_id):
        return self.db.execute(
            "SELECT e.*, c.name AS paid_by_name FROM split_expenses e "
            "JOIN split_contacts c ON c.contact_id=e.paid_by "
            "WHERE e.expense_id=?",
            (expense_id,)).fetchone()

    def list_shares(self, expense_id):
        return self.db.execute(
            "SELECT s.*, c.name FROM split_shares s "
            "JOIN split_contacts c ON c.contact_id=s.contact_id "
            "WHERE s.expense_id=? ORDER BY c.is_self DESC, c.name ASC",
            (expense_id,)).fetchall()

    def update_share_paid(self, share_id, paid_amount):
        self.db.execute("UPDATE split_shares SET paid_amount=? WHERE share_id=?", (paid_amount, share_id))
        share = self.db.execute("SELECT * FROM split_shares WHERE share_id=?", (share_id,)).fetchone()
        if share:
            if paid_amount >= share["share_amount"]:
                self.db.execute("UPDATE split_shares SET status='PAID' WHERE share_id=?", (share_id,))
            elif paid_amount > 0:
                self.db.execute("UPDATE split_shares SET status='PARTIALLY_PAID' WHERE share_id=?", (share_id,))
            else:
                self.db.execute("UPDATE split_shares SET status='PENDING' WHERE share_id=?", (share_id,))
        self.db.commit()

    # ── Settlements ──
    def create_settlement(self, group_id, from_contact, to_contact, amount, settle_date, method, description=None, linked_txn_id=None):
        sid = _uid()
        self.db.execute(
            "INSERT INTO split_settlements(settlement_id, group_id, from_contact, to_contact, amount, settle_date, method, description, created_at, linked_txn_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (sid, group_id, from_contact, to_contact, amount, settle_date, method, description, _now(), linked_txn_id))
        self.db.commit()
        return sid

    def list_settlements(self, group_id):
        return self.db.execute(
            "SELECT s.*, fc.name AS from_name, tc.name AS to_name "
            "FROM split_settlements s "
            "JOIN split_contacts fc ON fc.contact_id=s.from_contact "
            "JOIN split_contacts tc ON tc.contact_id=s.to_contact "
            "WHERE s.group_id=? ORDER BY s.settle_date DESC",
            (group_id,)).fetchall()

    # ── Balance Calculation ──
    def get_group_balances(self, group_id):
        """Calculate net balance for each contact in a group.
        
        Positive = is owed money (others owe them)
        Negative = owes money (they owe others)
        """
        members = self.list_group_members(group_id)
        balances = {m["contact_id"]: 0.0 for m in members}

        # Expenses: paid_by gets +amount, each share holder gets -share_amount
        expenses = self.list_expenses(group_id)
        for exp in expenses:
            paid_by = exp["paid_by"]
            if paid_by in balances:
                balances[paid_by] += exp["amount"]
            shares = self.list_shares(exp["expense_id"])
            for s in shares:
                cid = s["contact_id"]
                if cid in balances:
                    balances[cid] -= s["share_amount"]

        # Settlements: from pays to
        settlements = self.list_settlements(group_id)
        for st in settlements:
            fc = st["from_contact"]
            tc = st["to_contact"]
            if fc in balances:
                balances[fc] += st["amount"]
            if tc in balances:
                balances[tc] -= st["amount"]

        return balances

    def get_group_summary(self, group_id):
        """Get summary stats for a group."""
        expenses = self.list_expenses(group_id)
        total_expenses = sum(e["amount"] for e in expenses)
        shares = []
        for e in expenses:
            shares.extend(self.list_shares(e["expense_id"]))
        total_pending = sum(s["share_amount"] - s["paid_amount"] for s in shares if s["status"] != "PAID")
        total_settled = sum(s["paid_amount"] for s in shares)
        return {
            "total_expenses": total_expenses,
            "total_pending": total_pending,
            "total_settled": total_settled,
            "expense_count": len(expenses),
        }

    def suggest_settlements(self, group_id):
        """Minimize number of transfers to settle all debts.
        
        Returns list of (from_contact_id, from_name, to_contact_id, to_name, amount).
        """
        balances = self.get_group_balances(group_id)
        # Get names ("Alex (You)" for the current user)
        contacts = {c["contact_id"]: self.display_name_for(c)
                    for c in self.list_contacts()}

        creditors = [(cid, amt) for cid, amt in balances.items() if amt > 0.01]
        debtors = [(cid, -amt) for cid, amt in balances.items() if amt < -0.01]

        creditors.sort(key=lambda x: -x[1])
        debtors.sort(key=lambda x: -x[1])

        suggestions = []
        ci, di = 0, 0
        while ci < len(creditors) and di < len(debtors):
            c_id, c_amt = creditors[ci]
            d_id, d_amt = debtors[di]
            transfer = min(c_amt, d_amt)
            if transfer > 0.01:
                suggestions.append((d_id, contacts.get(d_id, "?"), c_id, contacts.get(c_id, "?"), round(transfer, 2)))
            creditors[ci] = (c_id, c_amt - transfer)
            debtors[di] = (d_id, d_amt - transfer)
            if creditors[ci][1] <= 0.01:
                ci += 1
            if debtors[di][1] <= 0.01:
                di += 1
        return suggestions
