"""Every CREATE TABLE — run once on startup via migrations.
Uses INSERT OR IGNORE so seeds are safe on existing databases.
You NEVER need to delete finance_data."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id      TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    short_label     TEXT NOT NULL,
    account_type    TEXT NOT NULL CHECK(account_type IN ('CURRENT','CREDIT_CARD','WALLET','CASH')),
    credit_limit    REAL DEFAULT 0,
    opening_balance REAL DEFAULT 0,
    color_hex       TEXT,
    is_active       INTEGER DEFAULT 1,
    sort_order      INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payment_methods (
    method_id       TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    is_active       INTEGER DEFAULT 1,
    sort_order      INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS categories (
    category_id         TEXT PRIMARY KEY,
    display_name        TEXT NOT NULL,
    color_hex           TEXT,
    default_pf_category TEXT,
    tax_deductible      INTEGER DEFAULT 0,
    is_active           INTEGER DEFAULT 1,
    sort_order          INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS pf_categories (
    pf_id          TEXT PRIMARY KEY,
    display_name   TEXT NOT NULL,
    is_active      INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS note_tags (
    tag_id         TEXT PRIMARY KEY,
    display_name   TEXT NOT NULL,
    is_active      INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS transactions (
    id              TEXT PRIMARY KEY,
    tx_date         TEXT NOT NULL,
    account_id      TEXT NOT NULL REFERENCES accounts,
    pay_method      TEXT NOT NULL REFERENCES payment_methods,
    tx_type         TEXT NOT NULL CHECK(tx_type IN ('CREDIT','DEBIT')),
    amount          REAL NOT NULL CHECK(amount > 0),
    person_org      TEXT,
    description     TEXT,
    created_at      TEXT NOT NULL,
    transaction_kind TEXT DEFAULT 'REGULAR',
    transfer_group_id TEXT,
    category        TEXT REFERENCES categories,
    neednwant       INTEGER DEFAULT 0,
    pf_category     TEXT REFERENCES pf_categories,
    gmail_source_id TEXT
);
CREATE TABLE IF NOT EXISTS app_security (
    id INTEGER PRIMARY KEY CHECK(id=1),
    password_hash           TEXT,
    recovery_email          TEXT,
    totp_secret             TEXT,
    totp_enabled            INTEGER DEFAULT 0,
    updated_at              TEXT
);
CREATE TABLE IF NOT EXISTS tab_security (
    tab_key         TEXT PRIMARY KEY,
    password_hash   TEXT,
    failed_attempts INTEGER DEFAULT 0,
    updated_at      TEXT
);
CREATE TABLE IF NOT EXISTS period_locks (
    period_id       TEXT PRIMARY KEY,
    is_locked       INTEGER DEFAULT 0,
    locked_at       TEXT,
    unlocked_at     TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  TEXT REFERENCES transactions,
    field_changed   TEXT NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    changed_at      TEXT NOT NULL,
    change_reason   TEXT
);
CREATE TABLE IF NOT EXISTS borrowers (
    borrower_id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS loans (
    loan_id TEXT PRIMARY KEY, borrower_id TEXT NOT NULL REFERENCES borrowers,
    loan_amount REAL NOT NULL, payment_method TEXT, start_date TEXT NOT NULL,
    due_date TEXT, status TEXT DEFAULT 'ACTIVE', description TEXT,
    trxn_id TEXT REFERENCES transactions ON DELETE CASCADE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS repayments (
    repayment_id TEXT PRIMARY KEY, loan_id TEXT NOT NULL REFERENCES loans,
    amount_paid REAL NOT NULL, payment_date TEXT NOT NULL, payment_method TEXT,
    description TEXT, created_at TEXT NOT NULL,
    linked_txn_id TEXT REFERENCES transactions ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS lenders (
    lender_id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS borrowed_loans (
    loan_id TEXT PRIMARY KEY, lender_id TEXT NOT NULL REFERENCES lenders,
    principal_amount REAL NOT NULL, interest_rate REAL DEFAULT 0,
    emi_amount REAL DEFAULT 0, start_date TEXT NOT NULL, due_date TEXT,
    status TEXT DEFAULT 'ACTIVE', description TEXT,
    linked_txn_id TEXT REFERENCES transactions ON DELETE CASCADE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS borrowed_loan_repayments (
    repayment_id TEXT PRIMARY KEY, loan_id TEXT NOT NULL REFERENCES borrowed_loans,
    amount_paid REAL NOT NULL, payment_date TEXT NOT NULL, payment_method TEXT,
    description TEXT, linked_txn_id TEXT REFERENCES transactions ON DELETE CASCADE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS depositors (
    depositor_id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deposits_from_others (
    deposit_id TEXT PRIMARY KEY, depositor_id TEXT NOT NULL REFERENCES depositors,
    principal_amount REAL NOT NULL, interest_rate REAL, deposit_date TEXT NOT NULL,
    expected_return_date TEXT, status TEXT DEFAULT 'ACTIVE', description TEXT,
    linked_txn_id TEXT REFERENCES transactions ON DELETE CASCADE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deposit_repayments_to_others (
    repayment_id TEXT PRIMARY KEY, deposit_id TEXT NOT NULL REFERENCES deposits_from_others,
    amount_paid REAL NOT NULL, payment_date TEXT NOT NULL, payment_method TEXT,
    description TEXT, linked_txn_id TEXT REFERENCES transactions ON DELETE CASCADE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fixed_deposits (
    fd_id TEXT PRIMARY KEY, bank_account_id TEXT REFERENCES accounts,
    principal_amount REAL NOT NULL, interest_rate REAL NOT NULL,
    start_date TEXT NOT NULL, maturity_date TEXT NOT NULL, maturity_amount REAL,
    status TEXT DEFAULT 'ACTIVE',
    linked_txn_id TEXT REFERENCES transactions ON DELETE CASCADE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mf_schemes (
    scheme_id TEXT PRIMARY KEY, amc_name TEXT NOT NULL, scheme_name TEXT NOT NULL,
    scheme_type TEXT, folio_number TEXT, is_active INTEGER DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mf_transactions (
    mf_txn_id TEXT PRIMARY KEY, scheme_id TEXT NOT NULL REFERENCES mf_schemes,
    txn_type TEXT NOT NULL, txn_date TEXT NOT NULL, amount REAL NOT NULL,
    nav REAL NOT NULL, units REAL NOT NULL,
    linked_txn_id TEXT REFERENCES transactions ON DELETE CASCADE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, tags TEXT, content TEXT,
    linked_transaction_ids TEXT, created_at TEXT NOT NULL, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS notes_trash (
    uuid TEXT PRIMARY KEY, original_id TEXT, title TEXT, tags TEXT, content TEXT,
    linked_transaction_ids TEXT, created_at TEXT, deleted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cards (
    card_id         TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL REFERENCES accounts,
    card_name       TEXT NOT NULL,
    issuer_bank     TEXT NOT NULL,
    card_brand      TEXT DEFAULT '',
    card_network    TEXT DEFAULT 'VISA',
    card_class      TEXT DEFAULT '',
    last_four       TEXT DEFAULT '0000',
    card_number     TEXT DEFAULT '',
    cardholder_name TEXT DEFAULT '',
    expiry_month    INTEGER DEFAULT 12,
    expiry_year     INTEGER DEFAULT 2028,
    statement_date  TEXT DEFAULT '',
    due_date        TEXT DEFAULT '',
    grace_days      INTEGER DEFAULT 20,
    annual_fee      REAL DEFAULT 0,
    card_color_1    TEXT DEFAULT '#1a1a2e',
    card_color_2    TEXT DEFAULT '#16213e',
    is_active       INTEGER DEFAULT 1,
    sort_order      INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS card_cycles (
    cycle_id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts,
    cycle_start_date TEXT, statement_date TEXT, due_date TEXT,
    total_due REAL DEFAULT 0, minimum_due REAL DEFAULT 0,
    debits REAL DEFAULT 0, paid REAL DEFAULT 0, remaining REAL DEFAULT 0,
    source TEXT DEFAULT 'MANUAL', detected_at TEXT
);
CREATE TABLE IF NOT EXISTS budgets (
    budget_id TEXT PRIMARY KEY, scope_type TEXT NOT NULL, scope_value TEXT NOT NULL,
    limit_amount REAL NOT NULL, alert_threshold_pct REAL DEFAULT 80,
    is_active INTEGER DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recurring_rules (
    rule_id TEXT PRIMARY KEY, account_id TEXT REFERENCES accounts, pay_method TEXT,
    tx_type TEXT NOT NULL, amount REAL NOT NULL, category TEXT, pf_category TEXT,
    neednwant INTEGER DEFAULT 0, description TEXT, frequency TEXT NOT NULL,
    next_run_date TEXT NOT NULL, is_active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS preferences (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS debit_cards (
    card_id         TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL REFERENCES accounts,
    card_name       TEXT NOT NULL,
    card_network    TEXT DEFAULT 'VISA',
    card_class      TEXT DEFAULT '',
    last_four       TEXT DEFAULT '0000',
    card_number     TEXT DEFAULT '',
    cardholder_name TEXT DEFAULT '',
    expiry_month    INTEGER DEFAULT 12,
    expiry_year     INTEGER DEFAULT 2028,
    annual_fee      REAL DEFAULT 0,
    card_color_1    TEXT DEFAULT '#1a1a2e',
    card_color_2    TEXT DEFAULT '#16213e',
    is_active       INTEGER DEFAULT 1,
    sort_order      INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS split_contacts (
    contact_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    phone           TEXT,
    is_self         INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS split_groups (
    group_id        TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    is_active       INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS split_group_members (
    member_id       TEXT PRIMARY KEY,
    group_id        TEXT NOT NULL REFERENCES split_groups,
    contact_id      TEXT NOT NULL REFERENCES split_contacts,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS split_expenses (
    expense_id      TEXT PRIMARY KEY,
    group_id        TEXT NOT NULL REFERENCES split_groups,
    paid_by         TEXT NOT NULL REFERENCES split_contacts,
    amount          REAL NOT NULL,
    description     TEXT,
    expense_date    TEXT NOT NULL,
    split_type      TEXT DEFAULT 'EQUAL',
    created_at      TEXT NOT NULL,
    linked_txn_id   TEXT REFERENCES transactions
);
CREATE TABLE IF NOT EXISTS split_shares (
    share_id        TEXT PRIMARY KEY,
    expense_id      TEXT NOT NULL REFERENCES split_expenses,
    contact_id      TEXT NOT NULL REFERENCES split_contacts,
    share_amount    REAL NOT NULL,
    paid_amount     REAL DEFAULT 0,
    status          TEXT DEFAULT 'PENDING',
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS split_settlements (
    settlement_id   TEXT PRIMARY KEY,
    group_id        TEXT NOT NULL REFERENCES split_groups,
    from_contact    TEXT NOT NULL REFERENCES split_contacts,
    to_contact      TEXT NOT NULL REFERENCES split_contacts,
    amount          REAL NOT NULL,
    settle_date     TEXT NOT NULL,
    method          TEXT DEFAULT 'CASH',
    description     TEXT,
    linked_txn_id   TEXT REFERENCES transactions,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(tx_date);
CREATE INDEX IF NOT EXISTS idx_tx_account ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_split_expense_group ON split_expenses(group_id);
CREATE INDEX IF NOT EXISTS idx_split_share_expense ON split_shares(expense_id);
CREATE INDEX IF NOT EXISTS idx_split_settlement_group ON split_settlements(group_id);
"""


def run_migrations(db):
    """Run schema + seeds. Fully idempotent. Safe on existing databases."""
    c = db.get()

    # 1. Create tables (IF NOT EXISTS)
    c.executescript(SCHEMA_SQL)

    # 2. Seed app_security row
    c.execute("INSERT OR IGNORE INTO app_security(id) VALUES(1)")

    # 3. Seed Money Purpose categories (INSERT OR IGNORE — skips existing)
    #    pf_id values are permanent keys referenced by transactions; only the
    #    display_name is user-facing, so renaming a label is always safe.
    for pf_id, name in [
        ("commitment", "Commitment"), ("consumption", "Consumption"),
        ("growth", "Growth"), ("safety", "Safety"),
        ("internal_transfer", "Internal Transfer"), ("nc", "Uncategorised"),
    ]:
        c.execute("INSERT OR IGNORE INTO pf_categories VALUES(?,?,1)", (pf_id, name))
    # One-time relabel for existing databases seeded with the cryptic "NC".
    c.execute("UPDATE pf_categories SET display_name='Uncategorised' "
              "WHERE pf_id='nc' AND display_name='NC'")

    # 4. Seed categories (INSERT OR IGNORE)
    for cat_id, name, col, pf, tx in [
        ("food_dining", "Food & Dining", "#F59E0B", "consumption", 0),
        ("transport", "Transport", "#3B82F6", "consumption", 0),
        ("shopping", "Shopping", "#EC4899", "consumption", 0),
        ("bills_utilities", "Bills & Utilities", "#8B5CF6", "commitment", 1),
        ("rent", "Rent", "#A855F7", "commitment", 1),
        ("salary", "Salary", "#10B981", "nc", 0),
        ("investment", "Investment", "#6366F1", "growth", 0),
        ("health", "Health", "#EF4444", "safety", 0),
        ("education", "Education", "#06B6D4", "growth", 0),
        ("entertainment", "Entertainment", "#F472B6", "consumption", 0),
        ("finance", "Finance", "#D97706", "growth", 0),
        ("transfer", "Transfer", "#6B7280", "internal_transfer", 0),
        ("other", "Other", "#9CA3AF", "nc", 0),
    ]:
        c.execute("INSERT OR IGNORE INTO categories"
                  "(category_id,display_name,color_hex,default_pf_category,"
                  "tax_deductible,is_active,sort_order) VALUES(?,?,?,?,?,1,0)",
                  (cat_id, name, col, pf, tx))

    # 5. Seed payment methods (INSERT OR IGNORE)
    for i, m in enumerate([
        "PHONEPAY", "SLICE", "DIRECT TRANSFER", "CASH", "AMAZON PAY",
        "FLIPKART 3I", "ATM", "CRED APP", "SUPER MONEY", "PAYTM",
        "GOOGLE PAY", "NAVY UPI", "BHIM UPI", "AIRTEL PAY", "NETBANKING",
        "CHEQUE", "FED UPI", "AXIS UPI", "NAMMA METRO CARD", "YONO",
        "CANARA AI", "SIB MIRROR", "OTHER"
    ]):
        c.execute("INSERT OR IGNORE INTO payment_methods VALUES(?,?,1,?)", (m, m, i))

    # 6. Seed note tags (INSERT OR IGNORE)
    for t in ["Personal", "Business", "Tax", "Recurring", "Important"]:
        c.execute("INSERT OR IGNORE INTO note_tags VALUES(?,?,1)", (t.lower(), t))

    # 7. Seed application preferences once (INSERT OR IGNORE)
    c.execute("INSERT OR IGNORE INTO preferences VALUES('min_txn_alert', '499')")
    c.execute("INSERT OR IGNORE INTO preferences VALUES('complete_page_size', '150')")
    c.execute("INSERT OR IGNORE INTO preferences VALUES('scroll_trigger_px', '400')")
    c.execute("INSERT OR IGNORE INTO preferences VALUES('user_email', '')")
    c.execute("INSERT OR IGNORE INTO preferences VALUES('user_name', '')")
    c.execute("INSERT OR IGNORE INTO preferences VALUES('theme', 'light')")
    c.execute("INSERT OR IGNORE INTO preferences VALUES('wealth_page_size', '150')")
    c.execute("INSERT OR IGNORE INTO preferences VALUES('wealth_scroll_trigger', '400')")
    c.execute("INSERT OR IGNORE INTO preferences VALUES('notes_page_size', '50')")
    c.execute("INSERT OR IGNORE INTO preferences VALUES('notes_scroll_trigger', '200')")

    # 8. Safe ALTER TABLE — add columns if missing (existing DBs)
    _safe_cols = [
        ("cards", "credit_limit", "REAL DEFAULT 0"),
        ("cards", "statement_day", "INTEGER DEFAULT 1"),
        ("cards", "joining_fee", "REAL DEFAULT 0"),
        ("cards", "interest_rate", "REAL DEFAULT 3.5"),
        ("cards", "reward_program", "TEXT"),
        ("cards", "card_name", "TEXT"),
        ("cards", "card_class", "TEXT DEFAULT ''"),
        ("cards", "card_brand", "TEXT DEFAULT ''"),
        ("cards", "card_number", "TEXT"),
        ("cards", "statement_date", "TEXT DEFAULT ''"),
        ("cards", "due_date", "TEXT DEFAULT ''"),
        ("card_cycles", "debits", "REAL DEFAULT 0"),
        ("card_cycles", "paid", "REAL DEFAULT 0"),
        ("card_cycles", "remaining", "REAL DEFAULT 0"),
        ("borrowed_loans", "interest_type", "TEXT DEFAULT 'ANNUAL'"),
        ("borrowed_loans", "interest_method", "TEXT DEFAULT 'COMPOUND'"),
        ("loans", "interest_rate", "REAL DEFAULT 0"),
        ("loans", "interest_method", "TEXT DEFAULT 'SIMPLE'"),
        ("deposits_from_others", "interest_method", "TEXT DEFAULT 'SIMPLE'"),
        ("deposits_from_others", "interest_type", "TEXT DEFAULT 'ANNUAL'"),
        ("fixed_deposits", "interest_method", "TEXT DEFAULT 'COMPOUND'"),
        ("fixed_deposits", "interest_type", "TEXT DEFAULT 'QUARTERLY'"),
        ("borrowed_loans", "emi_type", "TEXT DEFAULT 'EMI'"),
        ("borrowed_loans", "amort_enabled", "INTEGER DEFAULT 1"),
        ("borrowed_loans", "interest_start_date", "TEXT"),
        ("borrowed_loans", "target_closure_date", "TEXT"),
        ("borrowed_loans", "amort_start_date", "TEXT"),
        ("borrowed_loans", "amort_tenure", "INTEGER"),
        ("mf_schemes", "launch_date", "TEXT"),
        ("mf_schemes", "api_scheme_code", "TEXT"),
        ("loans", "updated_at", "TEXT"),
        ("borrowed_loans", "updated_at", "TEXT"),
        ("deposits_from_others", "updated_at", "TEXT"),
        ("fixed_deposits", "updated_at", "TEXT"),
        ("transactions", "updated_at", "TEXT"),
        ("app_security", "google_client_id", "TEXT"),
        ("app_security", "google_client_secret", "TEXT"),
        ("app_security", "google_email", "TEXT"),
        ("app_security", "google_refresh_token", "TEXT"),
    ]
    for table, col, typedef in _safe_cols:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
        except Exception:
            pass  # column already exists

    # ── Need/Want is only meaningful for regular debit expenses. ──
    # Preserve 0 as "Not Set" for ordinary spending, but normalize legacy
    # credits, transfers and wealth/ledger movements to 3 = Not Applicable.
    try:
        c.execute(
            "UPDATE transactions SET neednwant=3 "
            "WHERE neednwant IN (0, 1, 2) AND "
            "(tx_type='CREDIT' OR COALESCE(transaction_kind, 'REGULAR') != 'REGULAR')"
        )
    except Exception:
        pass

    # ── Migrate existing wealth-linked transactions to correct transaction_kind ──
    _KIND_SQL = [
        ("UPDATE transactions SET transaction_kind='LOAN_GIVEN' "
         "WHERE id IN (SELECT trxn_id FROM loans WHERE trxn_id IS NOT NULL) "
         "AND transaction_kind='REGULAR'"),
        ("UPDATE transactions SET transaction_kind='LOAN_REPAYMENT' "
         "WHERE id IN (SELECT linked_txn_id FROM repayments WHERE linked_txn_id IS NOT NULL) "
         "AND transaction_kind='REGULAR'"),
        ("UPDATE transactions SET transaction_kind='LOAN_TAKEN' "
         "WHERE id IN (SELECT linked_txn_id FROM borrowed_loans WHERE linked_txn_id IS NOT NULL) "
         "AND transaction_kind='REGULAR'"),
        ("UPDATE transactions SET transaction_kind='EMI_PAYMENT' "
         "WHERE id IN (SELECT linked_txn_id FROM borrowed_loan_repayments WHERE linked_txn_id IS NOT NULL) "
         "AND transaction_kind='REGULAR'"),
        ("UPDATE transactions SET transaction_kind='DEPOSIT_RECEIVED' "
         "WHERE id IN (SELECT linked_txn_id FROM deposits_from_others WHERE linked_txn_id IS NOT NULL) "
         "AND transaction_kind='REGULAR'"),
        ("UPDATE transactions SET transaction_kind='DEPOSIT_REPAYMENT' "
         "WHERE id IN (SELECT linked_txn_id FROM deposit_repayments_to_others WHERE linked_txn_id IS NOT NULL) "
         "AND transaction_kind='REGULAR'"),
        ("UPDATE transactions SET transaction_kind='FD_DEPOSIT' "
         "WHERE id IN (SELECT linked_txn_id FROM fixed_deposits WHERE linked_txn_id IS NOT NULL) "
         "AND transaction_kind='REGULAR'"),
        ("UPDATE transactions SET transaction_kind='MF_PURCHASE' "
         "WHERE id IN (SELECT linked_txn_id FROM mf_transactions WHERE linked_txn_id IS NOT NULL AND txn_type='PURCHASE') "
         "AND transaction_kind='REGULAR'"),
        ("UPDATE transactions SET transaction_kind='MF_REDEMPTION' "
         "WHERE id IN (SELECT linked_txn_id FROM mf_transactions WHERE linked_txn_id IS NOT NULL AND txn_type='REDEMPTION') "
         "AND transaction_kind='REGULAR'"),
    ]
    # ── Backfill FD_WITHDRAWAL kind (no linked_txn_id, match by description) ──
    try:
        c.execute(
            "UPDATE transactions SET transaction_kind='FD_WITHDRAWAL' "
            "WHERE transaction_kind='REGULAR' "
            "AND (description LIKE '%FD%withdrawal%' OR description LIKE '%FD withdrawal%')"
        )
    except Exception:
        pass

    for sql in _KIND_SQL:
        try:
            c.execute(sql)
        except Exception:
            pass

    # Run once more after transaction-kind backfills above, so older wealth
    # records whose kind was just repaired also become Not Applicable.
    try:
        c.execute(
            "UPDATE transactions SET neednwant=3 "
            "WHERE neednwant IN (0, 1, 2) AND "
            "(tx_type='CREDIT' OR COALESCE(transaction_kind, 'REGULAR') != 'REGULAR')"
        )
    except Exception:
        pass

    _merge_duplicate_self_contacts(c)

    c.commit()


def _merge_duplicate_self_contacts(c):
    """Collapse multiple ``split_contacts.is_self=1`` rows into one.

    Only one row may represent "you". A second one can appear when the app is
    opened against a database whose split tables are empty -- SplitTab's
    constructor calls get_self_contact(), which creates a fresh "You" -- and
    the real contact is restored afterwards.

    The damage is silent and total: get_self_contact() returns whichever row
    SQLite hands back first, and if that is the freshly created one it belongs
    to no group, so the Split header reports 0 owed / 0 owing and marks every
    group settled while the real balances sit under the other id.

    The surviving row is the one actually referenced by group memberships,
    expenses, shares and settlements; the empty impostor is repointed to it and
    deleted. A tie is broken by the oldest created_at, so the original wins.
    """
    try:
        rows = c.execute(
            "SELECT contact_id, name, created_at FROM split_contacts "
            "WHERE is_self=1").fetchall()
    except Exception:
        return
    if len(rows) < 2:
        return

    def usage(cid):
        n = 0
        for sql in (
            "SELECT COUNT(*) FROM split_group_members WHERE contact_id=?",
            "SELECT COUNT(*) FROM split_expenses      WHERE paid_by=?",
            "SELECT COUNT(*) FROM split_shares        WHERE contact_id=?",
            "SELECT COUNT(*) FROM split_settlements   WHERE from_contact=?",
            "SELECT COUNT(*) FROM split_settlements   WHERE to_contact=?",
        ):
            try:
                n += c.execute(sql, (cid,)).fetchone()[0]
            except Exception:
                pass
        return n

    scored = []
    for r in rows:
        cid = r["contact_id"] if hasattr(r, "keys") else r[0]
        created = (r["created_at"] if hasattr(r, "keys") else r[2]) or ""
        named = (r["name"] if hasattr(r, "keys") else r[1]) or ""
        scored.append((usage(cid), named.strip().lower() != "you", created, cid))
    # Most referenced first; then a real name over the "You" placeholder;
    # then oldest. Negate created_at ordering by sorting ascending on it.
    scored.sort(key=lambda t: (-t[0], not t[1], t[2]))
    keep = scored[0][3]

    for _, _, _, cid in scored[1:]:
        for sql in (
            "UPDATE OR IGNORE split_group_members SET contact_id=?  WHERE contact_id=?",
            "UPDATE split_expenses                SET paid_by=?     WHERE paid_by=?",
            "UPDATE split_shares                  SET contact_id=?  WHERE contact_id=?",
            "UPDATE split_settlements             SET from_contact=? WHERE from_contact=?",
            "UPDATE split_settlements             SET to_contact=?   WHERE to_contact=?",
        ):
            try:
                c.execute(sql, (keep, cid))
            except Exception:
                pass
        try:
            c.execute("DELETE FROM split_group_members WHERE contact_id=?", (cid,))
            c.execute("DELETE FROM split_contacts WHERE contact_id=?", (cid,))
        except Exception:
            pass
