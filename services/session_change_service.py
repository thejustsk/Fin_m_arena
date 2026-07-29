"""Human-readable session activity tracker for the exit summary."""
import re
from collections import Counter

_PATTERN = re.compile(r'^\s*(INSERT(?:\s+OR\s+\w+)?\s+INTO|UPDATE|DELETE\s+FROM)\s+["\[]?([A-Za-z_]+)', re.I)

# Tables that are implementation details of a parent action are deliberately
# omitted (for example split_shares is part of recording one Split expense).
_NOUNS = {
    'transactions': 'regular transaction', 'accounts': 'account', 'categories': 'category', 'payment_methods': 'payment method',
    'pf_categories': 'money purpose', 'notes': 'note', 'notes_trash': 'note',
    'budgets': 'budget', 'recurring_rules': 'recurring rule',
    'cards': 'credit card', 'debit_cards': 'debit card',
    'split_contacts': 'split contact', 'split_groups': 'split group',
    'split_expenses': 'split expense', 'split_settlements': 'split settlement',
    'loans': 'money lent loan', 'repayments': 'money lent repayment',
    'borrowed_loans': 'money borrowed loan', 'borrowed_loan_repayments': 'EMI payment',
    'fixed_deposits': 'fixed deposit', 'deposits_from_others': 'deposit received',
    'deposit_repayments_to_others': 'deposit repayment', 'mf_schemes': 'mutual fund scheme',
    'mf_transactions': 'mutual fund transaction', 'preferences': 'preference',
}
_SKIP = {'card_cycles', 'split_group_members', 'split_shares', 'audit_log'}

class SessionChangeTracker:
    def __init__(self, db):
        self.db = db
        self._changes = Counter()
        self._enabled = False

    def start(self):
        self._enabled = True
        self.db.get().set_trace_callback(self._trace)

    def _activity(self, table, op, sql):
        if table in _SKIP or table not in _NOUNS:
            return None
        upper = sql.upper()
        # Startup/dashboard maintenance regularly runs status and timestamp
        # updates (often affecting zero rows). Those are not user actions and
        # must never make a fresh session look modified.
        if op.startswith('UPDATE') and (
            ' SET STATUS=' in upper or ' SET STATUS =' in upper or
            ' SET UPDATED_AT=' in upper or ' SET UPDATED_AT =' in upper
        ):
            return None
        noun = _NOUNS[table]
        if op.startswith('INSERT'):
            # Regular is the default transaction kind when the column is absent.
            if table == 'transactions':
                if 'TRANSFER' in upper: noun = 'transfer transaction'
                elif 'SPLIT' in upper: noun = 'split ledger transaction'
                elif any(k in upper for k in ('LOAN_', 'EMI_', 'FD_', 'MF_', 'DEPOSIT_')): noun = 'wealth transaction'
                else: noun = 'regular transaction'
            return noun, 'added'
        if op.startswith('DELETE'):
            return noun, 'deleted'
        # UPDATE: activation/deactivation deserves a user-facing verb.
        if 'IS_ACTIVE=0' in upper or 'IS_ACTIVE = 0' in upper:
            return noun, 'deactivated'
        if 'IS_ACTIVE=1' in upper or 'IS_ACTIVE = 1' in upper:
            return noun, 'activated'
        return noun, 'updated'

    def _trace(self, sql):
        if not self._enabled:
            return
        match = _PATTERN.match(sql or '')
        if not match:
            return
        activity = self._activity(match.group(2).lower(), match.group(1).upper(), sql)
        if activity:
            self._changes[activity] += 1

    def summary(self):
        lines = []
        for (noun, action), count in self._changes.most_common():
            plural = noun if count == 1 else (noun + 'es' if noun.endswith('s') else noun + 's')
            lines.append(f"{count} {plural if count != 1 else noun} {action}")
        return lines

    def has_changes(self):
        return bool(self._changes)
