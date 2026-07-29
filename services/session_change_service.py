"""Session-wide SQLite change tracker for the exit summary."""
import re
from collections import Counter

_TABLE_LABELS = {
    'transactions': 'Transactions', 'accounts': 'Accounts',
    'categories': 'Categories & Lookups', 'payment_methods': 'Categories & Lookups',
    'pf_categories': 'Categories & Lookups', 'notes': 'Notes', 'notes_trash': 'Notes',
    'budgets': 'Budgets', 'recurring_rules': 'Recurring Rules',
    'cards': 'Credit Cards', 'card_cycles': 'Credit Cards', 'debit_cards': 'Debit Cards',
    'split_contacts': 'Split', 'split_groups': 'Split', 'split_group_members': 'Split',
    'split_expenses': 'Split', 'split_shares': 'Split', 'split_settlements': 'Split',
    'loans': 'Money Lent', 'borrowers': 'Money Lent', 'repayments': 'Money Lent',
    'borrowed_loans': 'Money Borrowed', 'borrowed_loan_repayments': 'Money Borrowed',
    'lenders': 'Money Borrowed', 'fixed_deposits': 'Fixed Deposits',
    'deposits_from_others': 'Deposits Received', 'deposit_repayments_to_others': 'Deposits Received',
    'depositors': 'Deposits Received', 'mf_schemes': 'Mutual Funds', 'mf_transactions': 'Mutual Funds',
    'preferences': 'Preferences',
}
_PATTERN = re.compile(r'^\s*(INSERT(?:\s+OR\s+\w+)?\s+INTO|UPDATE|DELETE\s+FROM)\s+["\[]?([A-Za-z_]+)', re.I)

class SessionChangeTracker:
    def __init__(self, db):
        self.db = db
        self._changes = Counter()
        self._enabled = False

    def start(self):
        self._enabled = True
        self.db.get().set_trace_callback(self._trace)

    def _trace(self, sql):
        if not self._enabled:
            return
        match = _PATTERN.match(sql or '')
        if not match:
            return
        table = match.group(2).lower()
        label = _TABLE_LABELS.get(table)
        if label:
            self._changes[label] += 1

    def summary(self):
        return [(label, count) for label, count in self._changes.most_common()]

    def has_changes(self):
        return bool(self._changes)
