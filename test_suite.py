#!/usr/bin/env python3
"""
Finance Manager v3 — Comprehensive Test Suite
Tests all backend logic, CRUD operations, and business rules.
No display needed — runs in terminal.

Usage: python test_suite.py
"""
import sys
import os
import traceback
import uuid
import time
from pathlib import Path
from datetime import date, timedelta

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ═══════════════════════════════════════════════
# TEST RESULTS TRACKING
# ═══════════════════════════════════════════════

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.section = ""

    def set_section(self, name):
        self.section = name
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")

    def ok(self, name):
        self.passed += 1
        print(f"  ✅ {name}")

    def fail(self, name, detail=""):
        self.failed += 1
        self.errors.append(f"[{self.section}] {name}: {detail}")
        print(f"  ❌ {name} — {detail}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  RESULTS: {self.passed}/{total} passed, {self.failed} failed")
        print(f"{'='*60}")
        if self.errors:
            print(f"\n  FAILURES:")
            for e in self.errors:
                print(f"    ❌ {e}")
        else:
            print(f"\n  🎉 ALL TESTS PASSED!")
        return self.failed == 0


# ═══════════════════════════════════════════════
# TEST DATABASE SETUP
# ═══════════════════════════════════════════════

TEST_DB_PATH = Path(__file__).resolve().parent / "finance_data" / "test_finance.db"

def setup_test_db():
    """Create a fresh test database with sample data."""
    import shutil
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    from db.connection import Database
    from db.schema import run_migrations

    db = Database(str(TEST_DB_PATH))
    db.connect()
    run_migrations(db)

    # Seed sample data
    seed_data(db)
    return db


def seed_data(db):
    """Populate test database with realistic sample data."""
    import uuid

    # Accounts
    accounts = [
        ("acc_sbi", "SBI Savings", "SBIS", "CURRENT", 50000),
        ("acc_hdfc", "HDFC Bank", "HDFC", "CURRENT", 120000),
        ("acc_cash", "Cash at Home", "CASH", "CASH", 5000),
        ("acc_wallet", "Paytm Wallet", "PAYT", "WALLET", 2000),
        ("acc_cc", "Amazon ICICI Card", "AMZN", "CREDIT_CARD", 200000),
    ]
    for aid, name, label, atype, bal in accounts:
        db.execute(
            "INSERT OR IGNORE INTO accounts(account_id, display_name, short_label, account_type, opening_balance, color_hex, is_active, created_at) VALUES(?,?,?,?,?,?,1,?)",
            (aid, name, label, atype, bal, "#4F46E5", "2025-01-01T00:00:00"))

    # Borrowers
    db.execute("INSERT OR IGNORE INTO borrowers VALUES('b1','Rahul','2025-01-01T00:00:00')")
    db.execute("INSERT OR IGNORE INTO borrowers VALUES('b2','Priya','2025-01-01T00:00:00')")

    # Lenders
    db.execute("INSERT OR IGNORE INTO lenders VALUES('l1','SBI Bank','2025-01-01T00:00:00')")

    # Depositors
    db.execute("INSERT OR IGNORE INTO depositors VALUES('d1','Amit','2025-01-01T00:00:00')")

    # Transactions (30 sample transactions across 3 months)
    txn_base = [
        ("txn_001", "2025-01-05", "acc_sbi", "PHONEPAY", "DEBIT", 500, "Swiggy", "Food order", "food_dining"),
        ("txn_002", "2025-01-05", "acc_sbi", "PHONEPAY", "CREDIT", 50000, "Company", "Salary", "salary"),
        ("txn_003", "2025-01-10", "acc_hdfc", "NETBANKING", "DEBIT", 15000, "Landlord", "Rent", "rent"),
        ("txn_004", "2025-01-12", "acc_cash", "CASH", "DEBIT", 200, "Local shop", "Groceries", "food_dining"),
        ("txn_005", "2025-01-15", "acc_wallet", "PAYTM", "DEBIT", 150, "Auto", "Ride", "transport"),
        ("txn_006", "2025-01-18", "acc_sbi", "PHONEPAY", "DEBIT", 3000, "Amazon", "Shopping", "shopping"),
        ("txn_007", "2025-01-20", "acc_hdfc", "NETBANKING", "DEBIT", 2500, "Hospital", "Checkup", "health"),
        ("txn_008", "2025-01-22", "acc_sbi", "BHIM UPI", "DEBIT", 5000, "School", "Fees", "education"),
        ("txn_009", "2025-01-25", "acc_cash", "CASH", "DEBIT", 500, "Theater", "Movie", "entertainment"),
        ("txn_010", "2025-01-28", "acc_sbi", "PHONEPAY", "CREDIT", 10000, "Friend", "Refund", "other"),
        ("txn_011", "2025-02-01", "acc_sbi", "PHONEPAY", "CREDIT", 50000, "Company", "Salary", "salary"),
        ("txn_012", "2025-02-05", "acc_hdfc", "NETBANKING", "DEBIT", 15000, "Landlord", "Rent", "rent"),
        ("txn_013", "2025-02-08", "acc_sbi", "BHIM UPI", "DEBIT", 800, "Restaurant", "Dinner", "food_dining"),
        ("txn_014", "2025-02-10", "acc_wallet", "PAYTM", "DEBIT", 300, "Bus", "Commute", "transport"),
        ("txn_015", "2025-02-14", "acc_sbi", "PHONEPAY", "DEBIT", 2000, "Gift shop", "Gift", "shopping"),
        ("txn_016", "2025-02-18", "acc_hdfc", "NETBANKING", "DEBIT", 10000, "Mutual Fund", "SIP", "investment"),
        ("txn_017", "2025-02-20", "acc_cash", "CASH", "DEBIT", 150, "Tea stall", "Tea", "food_dining"),
        ("txn_018", "2025-02-22", "acc_sbi", "BHIM UPI", "DEBIT", 500, "Electricity", "Bill", "bills_utilities"),
        ("txn_019", "2025-02-25", "acc_sbi", "PHONEPAY", "CREDIT", 5000, "Freelance", "Project", "other"),
        ("txn_020", "2025-02-28", "acc_hdfc", "NETBANKING", "DEBIT", 3000, "Insurance", "Premium", "bills_utilities"),
        ("txn_021", "2025-03-01", "acc_sbi", "PHONEPAY", "CREDIT", 50000, "Company", "Salary", "salary"),
        ("txn_022", "2025-03-03", "acc_hdfc", "NETBANKING", "DEBIT", 15000, "Landlord", "Rent", "rent"),
        ("txn_023", "2025-03-05", "acc_sbi", "BHIM UPI", "DEBIT", 1200, "Pharmacy", "Medicine", "health"),
        ("txn_024", "2025-03-08", "acc_cash", "CASH", "DEBIT", 400, "Market", "Vegetables", "food_dining"),
        ("txn_025", "2025-03-10", "acc_wallet", "PAYTM", "DEBIT", 200, "Metro", "Card recharge", "transport"),
        ("txn_026", "2025-03-12", "acc_sbi", "PHONEPAY", "DEBIT", 8000, "Online course", "Python", "education"),
        ("txn_027", "2025-03-15", "acc_hdfc", "NETBANKING", "DEBIT", 10000, "Mutual Fund", "SIP", "investment"),
        ("txn_028", "2025-03-18", "acc_sbi", "BHIM UPI", "DEBIT", 600, "Internet", "Broadband", "bills_utilities"),
        ("txn_029", "2025-03-22", "acc_sbi", "PHONEPAY", "CREDIT", 20000, "Client", "Invoice", "other"),
        ("txn_030", "2025-03-25", "acc_cash", "CASH", "DEBIT", 300, "Petrol", "Fuel", "transport"),
    ]

    for tid, dt, acc, method, ttype, amt, person, desc, cat in txn_base:
        db.execute(
            "INSERT OR IGNORE INTO transactions(id, tx_date, account_id, pay_method, tx_type, amount, person_org, description, category, transaction_kind, created_at) VALUES(?,?,?,?,?,?,?,?,?,'REGULAR',?)",
            (tid, dt, acc, method, ttype, amt, person, desc, cat, f"{dt}T12:00:00"))

    # Transfer transactions
    gid = "transfer_001"
    db.execute(
        "INSERT OR IGNORE INTO transactions(id, tx_date, account_id, pay_method, tx_type, amount, description, transaction_kind, transfer_group_id, category, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,'2025-02-15T12:00:00')",
        ("txn_t1", "2025-02-15", "acc_sbi", "NETBANKING", "DEBIT", 10000, "Transfer to HDFC", "TRANSFER", gid, "transfer"))
    db.execute(
        "INSERT OR IGNORE INTO transactions(id, tx_date, account_id, pay_method, tx_type, amount, description, transaction_kind, transfer_group_id, category, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,'2025-02-15T12:00:00')",
        ("txn_t2", "2025-02-15", "acc_hdfc", "NETBANKING", "CREDIT", 10000, "Transfer from SBI", "TRANSFER", gid, "transfer"))

    # Loan given
    db.execute("INSERT OR IGNORE INTO loans(loan_id, borrower_id, loan_amount, payment_method, start_date, due_date, status, trxn_id, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
               ("loan1", "b1", 25000, "PHONEPAY", "2025-01-15", "2025-04-15", "ACTIVE", "txn_001", "2025-01-15T00:00:00"))

    # Repayment
    db.execute("INSERT OR IGNORE INTO repayments(repayment_id, loan_id, amount_paid, payment_date, linked_txn_id, created_at) VALUES(?,?,?,?,?,?)",
               ("rep1", "loan1", 5000, "2025-02-10", "txn_019", "2025-02-10T00:00:00"))

    # Borrowed loan
    db.execute("INSERT OR IGNORE INTO borrowed_loans(loan_id, lender_id, principal_amount, interest_rate, emi_amount, start_date, due_date, status, linked_txn_id, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
               ("bloan1", "l1", 500000, 8.5, 15000, "2025-01-01", "2028-01-01", "ACTIVE", "txn_003", "2025-01-01T00:00:00"))

    # Fixed deposit
    db.execute("INSERT OR IGNORE INTO fixed_deposits(fd_id, bank_account_id, principal_amount, interest_rate, start_date, maturity_date, maturity_amount, status, linked_txn_id, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
               ("fd1", "acc_sbi", 100000, 7.0, "2025-01-01", "2026-01-01", 107000, "ACTIVE", "txn_002", "2025-01-01T00:00:00"))

    # Debit card
    db.execute("INSERT OR IGNORE INTO debit_cards(card_id, account_id, card_name, card_network, last_four, cardholder_name, expiry_month, expiry_year, card_color_1, card_color_2, is_active, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,1,?)",
               ("dc1", "acc_sbi", "SBI Debit Card", "VISA", "1234", "Rahul", 12, 2028, "#b8bcc2", "#5f656d", "2025-01-01T00:00:00"))

    # Credit card
    db.execute("INSERT OR IGNORE INTO cards(card_id, account_id, card_name, issuer_bank, card_network, last_four, cardholder_name, expiry_month, expiry_year, statement_date, grace_days, card_color_1, card_color_2, is_active, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               ("cc1", "acc_cc", "Amazon ICICI Card", "ICICI", "VISA", "5678", "Rahul", 12, 2028, "6th", 20, "#3a3a3a", "#0f0f0f", 1, "2025-01-01T00:00:00"))

    db.commit()
    print(f"  📦 Test database created at: {TEST_DB_PATH}")
    print(f"  📊 Seeded: 5 accounts, 30 transactions, 1 transfer, 1 loan, 1 borrowed loan, 1 FD, 1 DC, 1 CC")


# ═══════════════════════════════════════════════
# TEST CASES
# ═══════════════════════════════════════════════

def test_accounts(r, db, repos):
    r.set_section("ACCOUNTS")
    acct = repos["accounts"]

    # List all
    all_accts = acct.list_all()
    r.ok(f"list_all() returned {len(all_accts)} accounts") if len(all_accts) >= 5 else r.fail("list_all", f"Expected >=5, got {len(all_accts)}")

    # List active
    active = acct.list_active()
    r.ok(f"list_active() returned {len(active)} accounts") if len(active) >= 5 else r.fail("list_active", f"Expected >=5, got {len(active)}")

    # Create new
    try:
        acct.create(display_name="Test Bank", short_label="TSTB", account_type="CURRENT", opening_balance=10000)
        r.ok("create() new account")
    except Exception as e:
        r.fail("create()", str(e))

    # Duplicate check
    try:
        acct.create(display_name="Test Bank", short_label="TSTB", account_type="CURRENT", opening_balance=0)
        r.fail("create() duplicate", "Should have raised ValueError")
    except ValueError:
        r.ok("create() duplicate rejected")
    except Exception as e:
        r.fail("create() duplicate", str(e))

    # Update
    try:
        new_acct = acct.list_all()[-1]
        acct.update(new_acct["account_id"], display_name="Updated Bank")
        updated = acct.get(new_acct["account_id"])
        r.ok("update() account name") if updated["display_name"] == "Updated Bank" else r.fail("update", "Name not updated")
    except Exception as e:
        r.fail("update()", str(e))

    # Toggle active
    try:
        aid = new_acct["account_id"]
        acct.update(aid, is_active=0)
        inactive = [a for a in acct.list_active() if a["account_id"] == aid]
        r.ok("deactivate account") if len(inactive) == 0 else r.fail("deactivate", "Still active")
    except Exception as e:
        r.fail("deactivate", str(e))


def test_transactions(r, db, repos):
    r.set_section("TRANSACTIONS")
    tx = repos["transactions"]

    # List all
    all_txns = tx.list_filters(limit=100)
    r.ok(f"list_filters() returned {len(all_txns)} transactions") if len(all_txns) >= 30 else r.fail("list_filters", f"Expected >=30, got {len(all_txns)}")

    # Filter by date range
    jan_txns = tx.list_filters(date_from="2025-01-01", date_to="2025-01-31", limit=100)
    r.ok(f"date filter: {len(jan_txns)} Jan transactions") if len(jan_txns) >= 8 else r.fail("date filter", f"Expected >=8, got {len(jan_txns)}")

    # Filter by account
    sbi_txns = tx.list_filters(account_id="acc_sbi", limit=100)
    r.ok(f"account filter: {len(sbi_txns)} SBI transactions") if len(sbi_txns) >= 10 else r.fail("account filter", f"Expected >=10, got {len(sbi_txns)}")

    # Filter by type
    debits = tx.list_filters(tx_type="DEBIT", limit=100)
    r.ok(f"type filter: {len(debits)} DEBIT transactions") if len(debits) >= 20 else r.fail("type filter", f"Expected >=20, got {len(debits)}")

    # Create new
    try:
        new_id = tx.create(tx_date="2025-03-30", account_id="acc_sbi", pay_method="PHONEPAY",
                           tx_type="DEBIT", amount=999, description="Test transaction", category="other")
        r.ok("create() new transaction") if new_id else r.fail("create", "No ID returned")
    except Exception as e:
        r.fail("create()", str(e))

    # Get by ID
    try:
        got = tx.get("txn_001")
        r.ok("get() by ID") if got and got["id"] == "txn_001" else r.fail("get", "Wrong ID")
    except Exception as e:
        r.fail("get()", str(e))

    # Update
    try:
        tx.update("txn_001", description="Updated description")
        updated = tx.get("txn_001")
        r.ok("update() transaction") if updated["description"] == "Updated description" else r.fail("update", "Description not updated")
    except Exception as e:
        r.fail("update()", str(e))

    # Monthly
    try:
        monthly = tx.get_monthly(2025, 1)
        r.ok(f"get_monthly() returned {len(monthly)} transactions") if len(monthly) >= 8 else r.fail("get_monthly", f"Expected >=8, got {len(monthly)}")
    except Exception as e:
        r.fail("get_monthly()", str(e))


def test_loans(r, db, repos):
    r.set_section("LOANS (GIVE)")
    loans = repos["loans"]

    # List
    all_loans = loans.list_loans()
    r.ok(f"list_loans() returned {len(all_loans)} loans") if len(all_loans) >= 1 else r.fail("list_loans", "No loans found")

    # Get
    try:
        loan = loans.get_loan("loan1")
        r.ok("get_loan() by ID") if loan and loan["loan_id"] == "loan1" else r.fail("get_loan", "Wrong ID")
    except Exception as e:
        r.fail("get_loan()", str(e))

    # Total repaid
    try:
        total = loans.total_repaid("loan1")
        r.ok(f"total_repaid() = {total}") if total >= 5000 else r.fail("total_repaid", f"Expected >=5000, got {total}")
    except Exception as e:
        r.fail("total_repaid()", str(e))

    # Recalc status
    try:
        loans.recalc_status("loan1")
        r.ok("recalc_status()")
    except Exception as e:
        r.fail("recalc_status()", str(e))


def test_borrowed(r, db, repos):
    r.set_section("LOANS (TAKE)")
    borrowed = repos["borrowed"]

    # List
    all_borrowed = borrowed.list_loans()
    r.ok(f"list_loans() returned {len(all_borrowed)} borrowed loans") if len(all_borrowed) >= 1 else r.fail("list_loans", "No borrowed loans found")

    # Get
    try:
        loan = borrowed.get_loan("bloan1")
        r.ok("get_loan() by ID") if loan and loan["loan_id"] == "bloan1" else r.fail("get_loan", "Wrong ID")
    except Exception as e:
        r.fail("get_loan()", str(e))


def test_deposits(r, db, repos):
    r.set_section("DEPOSITS (FROM OTHERS)")
    deposits = repos["deposits"]

    # List depositors
    try:
        depositors = deposits.list_depositors()
        r.ok(f"list_depositors() returned {len(depositors)} depositors") if len(depositors) >= 1 else r.fail("list_depositors", "No depositors")
    except Exception as e:
        r.fail("list_depositors()", str(e))


def test_fd(r, db, repos):
    r.set_section("FIXED DEPOSITS")
    fd = repos["fd"]

    # List
    all_fds = fd.list_all()
    r.ok(f"list_all() returned {len(all_fds)} FDs") if len(all_fds) >= 1 else r.fail("list_all", "No FDs found")

    # Get
    try:
        f = fd.get("fd1")
        r.ok("get() by ID") if f and f["fd_id"] == "fd1" else r.fail("get", "Wrong ID")
    except Exception as e:
        r.fail("get()", str(e))


def test_debit_cards(r, db, repos):
    r.set_section("DEBIT CARDS")
    dcr = repos["debit_cards"]

    # List active
    active = dcr.list_active()
    r.ok(f"list_active() returned {len(active)} cards") if len(active) >= 1 else r.fail("list_active", "No active cards")

    # Get
    try:
        card = dcr.get("dc1")
        r.ok("get() by ID") if card and card["card_id"] == "dc1" else r.fail("get", "Wrong ID")
    except Exception as e:
        r.fail("get()", str(e))

    # Create new
    try:
        new_id = dcr.create(
            account_id="acc_hdfc", card_name="HDFC Debit", card_network="MASTERCARD",
            last_four="9999", cardholder_name="Rahul",
            expiry_month=6, expiry_year=2029,
            card_color_1="#8a9199", card_color_2="#2f343b")
        r.ok("create() new debit card") if new_id else r.fail("create", "No ID returned")
    except Exception as e:
        r.fail("create()", str(e))

    # Toggle active
    try:
        dcr.toggle_active(new_id)
        card = dcr.get(new_id)
        r.ok("toggle_active()") if card and card["is_active"] == 0 else r.fail("toggle_active", "Not deactivated")
    except Exception as e:
        r.fail("toggle_active()", str(e))

    # Update
    try:
        dcr.update(new_id, card_name="Updated HDFC Debit")
        card = dcr.get(new_id)
        r.ok("update() card name") if card["card_name"] == "Updated HDFC Debit" else r.fail("update", "Name not updated")
    except Exception as e:
        r.fail("update()", str(e))


def test_credit_cards(r, db, repos):
    r.set_section("CREDIT CARDS")
    cr = repos["cards"]

    # List active
    active = cr.list_active()
    r.ok(f"list_active() returned {len(active)} cards") if len(active) >= 1 else r.fail("list_active", "No active cards")

    # Get
    try:
        card = cr.get("cc1")
        r.ok("get() by ID") if card and card["card_id"] == "cc1" else r.fail("get", "Wrong ID")
    except Exception as e:
        r.fail("get()", str(e))


def test_lookups(r, db, repos):
    r.set_section("LOOKUPS")
    lu = repos["lookups"]

    # Categories
    cats = lu.list_categories()
    r.ok(f"list_categories() returned {len(cats)} categories") if len(cats) >= 10 else r.fail("list_categories", f"Expected >=10, got {len(cats)}")

    # Methods
    methods = lu.list_methods()
    r.ok(f"list_methods() returned {len(methods)} methods") if len(methods) >= 20 else r.fail("list_methods", f"Expected >=20, got {len(methods)}")

    # Tags
    tags = lu.list_tags()
    r.ok(f"list_tags() returned {len(tags)} tags") if len(tags) >= 3 else r.fail("list_tags", f"Expected >=3, got {len(tags)}")


def test_security(r, db, repos):
    r.set_section("SECURITY")
    sec = repos["security"]
    from services.security_service import SecurityService
    svc = SecurityService(sec)

    # Set password
    try:
        svc.set_pw("test1234")
        r.ok("set_pw()")
    except Exception as e:
        r.fail("set_pw()", str(e))

    # Verify password
    try:
        r.ok("verify() correct") if svc.verify("test1234") else r.fail("verify", "Correct password rejected")
    except Exception as e:
        r.fail("verify()", str(e))

    # Wrong password
    try:
        r.ok("verify() wrong rejected") if not svc.verify("wrong") else r.fail("verify", "Wrong password accepted")
    except Exception as e:
        r.fail("verify() wrong", str(e))

    # Setup 2FA (requires pyotp)
    try:
        import pyotp
        secret = svc.setup_2fa()
        r.ok("setup_2fa()") if secret else r.fail("setup_2fa", "No secret returned")
    except ImportError:
        r.ok("setup_2fa() skipped (pyotp not installed)")
    except Exception as e:
        r.fail("setup_2fa()", str(e))

    # Toggle 2FA
    try:
        svc.toggle_2fa(True)
        r.ok("toggle_2fa(True)") if svc.is_2fa() else r.fail("toggle_2fa", "Not enabled")
        svc.toggle_2fa(False)
        r.ok("toggle_2fa(False)") if not svc.is_2fa() else r.fail("toggle_2fa", "Not disabled")
    except Exception as e:
        r.fail("toggle_2fa()", str(e))


def test_preferences(r, db):
    r.set_section("PREFERENCES")

    # Set
    try:
        db.execute("INSERT OR REPLACE INTO preferences VALUES('test_key', 'test_value')")
        db.commit()
        r.ok("INSERT preference")
    except Exception as e:
        r.fail("INSERT preference", str(e))

    # Get
    try:
        row = db.execute("SELECT value FROM preferences WHERE key='test_key'").fetchone()
        r.ok("SELECT preference") if row and row["value"] == "test_value" else r.fail("SELECT", "Wrong value")
    except Exception as e:
        r.fail("SELECT preference", str(e))


def test_schema_integrity(r, db):
    r.set_section("SCHEMA INTEGRITY")

    # Check all tables exist
    tables = [
        "accounts", "transactions", "payment_methods", "categories", "pf_categories",
        "note_tags", "app_security", "tab_security", "period_locks", "audit_log",
        "borrowers", "loans", "repayments", "lenders", "borrowed_loans",
        "borrowed_loan_repayments", "depositors", "deposits_from_others",
        "deposit_repayments_to_others", "fixed_deposits", "mf_schemes",
        "mf_transactions", "notes", "notes_trash", "cards", "card_cycles",
        "budgets", "recurring_rules", "preferences", "debit_cards"
    ]
    for table in tables:
        try:
            db.execute(f"SELECT COUNT(*) FROM {table}")
            r.ok(f"Table '{table}' exists")
        except Exception as e:
            r.fail(f"Table '{table}'", str(e))

    # Check columns exist
    checks = [
        ("transactions", "transaction_kind"),
        ("transactions", "updated_at"),
        ("transactions", "transfer_group_id"),
        ("loans", "updated_at"),
        ("loans", "interest_rate"),
        ("borrowed_loans", "updated_at"),
        ("borrowed_loans", "emi_type"),
        ("deposits_from_others", "updated_at"),
        ("fixed_deposits", "updated_at"),
        ("app_security", "google_client_id"),
        ("app_security", "google_email"),
    ]
    for table, col in checks:
        try:
            db.execute(f"SELECT {col} FROM {table} LIMIT 1")
            r.ok(f"Column '{table}.{col}' exists")
        except Exception as e:
            r.fail(f"Column '{table}.{col}'", str(e))


def test_data_consistency(r, db):
    r.set_section("DATA CONSISTENCY")

    # Transactions reference valid accounts
    try:
        orphan = db.execute("""
            SELECT COUNT(*) FROM transactions t
            LEFT JOIN accounts a ON a.account_id = t.account_id
            WHERE a.account_id IS NULL
        """).fetchone()
        r.ok("No orphan transactions") if orphan[0] == 0 else r.fail("Orphan transactions", f"Found {orphan[0]}")
    except Exception as e:
        r.fail("Orphan check", str(e))

    # Loans reference valid borrowers
    try:
        orphan = db.execute("""
            SELECT COUNT(*) FROM loans l
            LEFT JOIN borrowers b ON b.borrower_id = l.borrower_id
            WHERE b.borrower_id IS NULL
        """).fetchone()
        r.ok("No orphan loans") if orphan[0] == 0 else r.fail("Orphan loans", f"Found {orphan[0]}")
    except Exception as e:
        r.fail("Orphan check", str(e))

    # Debit cards reference valid accounts
    try:
        orphan = db.execute("""
            SELECT COUNT(*) FROM debit_cards dc
            LEFT JOIN accounts a ON a.account_id = dc.account_id
            WHERE a.account_id IS NULL
        """).fetchone()
        r.ok("No orphan debit cards") if orphan[0] == 0 else r.fail("Orphan debit cards", f"Found {orphan[0]}")
    except Exception as e:
        r.fail("Orphan check", str(e))

    # Transfer pairs have matching group_id
    try:
        transfers = db.execute("""
            SELECT transfer_group_id, COUNT(*) as cnt
            FROM transactions
            WHERE transfer_group_id IS NOT NULL
            GROUP BY transfer_group_id
            HAVING cnt != 2
        """).fetchall()
        r.ok("Transfer pairs balanced") if len(transfers) == 0 else r.fail("Transfer pairs", f"{len(transfers)} unbalanced groups")
    except Exception as e:
        r.fail("Transfer check", str(e))

    # No duplicate account names
    try:
        dupes = db.execute("""
            SELECT display_name, COUNT(*) as cnt
            FROM accounts
            GROUP BY LOWER(display_name)
            HAVING cnt > 1
        """).fetchall()
        r.ok("No duplicate account names") if len(dupes) == 0 else r.fail("Duplicate accounts", f"Found {len(dupes)}")
    except Exception as e:
        r.fail("Duplicate check", str(e))


def test_services(r, db, repos):
    r.set_section("SERVICES")

    # Balance service
    from services.balance_service import BalanceService
    bal = BalanceService(repos["accounts"])
    try:
        b = bal.get_balance("acc_sbi")
        r.ok(f"get_balance('acc_sbi') = {b}") if isinstance(b, (int, float)) else r.fail("get_balance", f"Wrong type: {type(b)}")
    except Exception as e:
        r.fail("get_balance()", str(e))

    # Audit service
    from services.audit_service import AuditService
    audit = AuditService(repos["audit"], repos["transactions"], db)
    try:
        audit.log("txn_001", "amount", 500, 600, reason="Test audit")
        r.ok("audit.log()")
    except Exception as e:
        r.fail("audit.log()", str(e))


def test_loans_recalc(r, db, repos):
    r.set_section("LOANS RECALCULATION")
    loans = repos["loans"]

    # Create a loan that should be OVERDUE
    try:
        db.execute("INSERT OR IGNORE INTO borrowers VALUES('b3','Test Overdue','2025-01-01T00:00:00')")
        db.execute("INSERT OR IGNORE INTO loans(loan_id, borrower_id, loan_amount, start_date, due_date, status, created_at) VALUES(?,?,?,?,?,?,?)",
                   ("loan_overdue", "b3", 10000, "2025-01-01", "2025-02-01", "ACTIVE", "2025-01-01T00:00:00"))
        db.commit()
        loans.recalc_status("loan_overdue")
        loan = loans.get_loan("loan_overdue")
        r.ok("Overdue loan detected") if loan and loan["status"] == "OVERDUE" else r.fail("Overdue detection", f"Status: {loan.get('status') if loan else 'None'}")
    except Exception as e:
        r.fail("Overdue test", str(e))

    # Create a loan that should be REPAID
    try:
        db.execute("INSERT OR IGNORE INTO loans(loan_id, borrower_id, loan_amount, start_date, due_date, status, created_at) VALUES(?,?,?,?,?,?,?)",
                   ("loan_repaid", "b1", 5000, "2025-01-01", "2025-06-01", "ACTIVE", "2025-01-01T00:00:00"))
        db.execute("INSERT OR IGNORE INTO repayments(repayment_id, loan_id, amount_paid, payment_date, created_at) VALUES(?,?,?,?,?)",
                   ("rep_full", "loan_repaid", 5000, "2025-02-01", "2025-02-01T00:00:00"))
        db.commit()
        loans.recalc_status("loan_repaid")
        loan = loans.get_loan("loan_repaid")
        r.ok("Repaid loan detected") if loan and loan["status"] == "REPAID" else r.fail("Repaid detection", f"Status: {loan.get('status') if loan else 'None'}")
    except Exception as e:
        r.fail("Repaid test", str(e))


def test_debit_card_repo(r, db, repos):
    r.set_section("DEBIT CARD REPO DETAILS")
    dcr = repos["debit_cards"]

    # Count
    try:
        total = dcr.count_total()
        r.ok(f"count_total() = {total}") if total >= 1 else r.fail("count_total", f"Expected >=1, got {total}")
    except Exception as e:
        r.fail("count_total()", str(e))

    try:
        active = dcr.count_active()
        r.ok(f"count_active() = {active}") if active >= 1 else r.fail("count_active", f"Expected >=1, got {active}")
    except Exception as e:
        r.fail("count_active()", str(e))

    # Get by account
    try:
        cards = dcr.get_by_account("acc_sbi")
        r.ok(f"get_by_account('acc_sbi') = {len(cards)} cards") if len(cards) >= 1 else r.fail("get_by_account", f"Expected >=1, got {len(cards)}")
    except Exception as e:
        r.fail("get_by_account()", str(e))

    # Delete
    try:
        dcr.create(account_id="acc_hdfc", card_name="Temp Card", card_network="VISA",
                   last_four="0000", cardholder_name="Test",
                   expiry_month=1, expiry_year=2025,
                   card_color_1="#000", card_color_2="#111")
        all_cards = dcr.list_active()
        temp = [c for c in all_cards if c["card_name"] == "Temp Card"]
        if temp:
            dcr.delete(temp[0]["card_id"])
            deleted = dcr.get(temp[0]["card_id"])
            r.ok("delete() card") if deleted is None else r.fail("delete", "Card still exists")
        else:
            r.fail("delete", "Temp card not found")
    except Exception as e:
        r.fail("delete()", str(e))


def test_combinations(r, db, repos):
    r.set_section("COMBINATION TESTS")
    tx = repos["transactions"]
    acct = repos["accounts"]

    # Test: Create account → create transaction → verify
    try:
        acct.create(display_name="Combo Test Bank", short_label="CMBT", account_type="CURRENT", opening_balance=0)
        new_acct = [a for a in acct.list_all() if a["display_name"] == "Combo Test Bank"][0]
        tx.create(tx_date="2025-03-30", account_id=new_acct["account_id"],
                  pay_method="PHONEPAY", tx_type="CREDIT", amount=1000,
                  description="Combo test deposit", category="other")
        txns = tx.list_filters(account_id=new_acct["account_id"], limit=10)
        r.ok("Create account + transaction combo") if len(txns) == 1 else r.fail("Combo", f"Expected 1 txn, got {len(txns)}")
    except Exception as e:
        r.fail("Account + transaction combo", str(e))

    # Test: Multiple filters combined
    try:
        filtered = tx.list_filters(date_from="2025-01-01", date_to="2025-03-31",
                                   account_id="acc_sbi", tx_type="DEBIT", limit=100)
        r.ok(f"Combined filters: {len(filtered)} results") if isinstance(filtered, list) else r.fail("Combined filters", "Not a list")
    except Exception as e:
        r.fail("Combined filters", str(e))

    # Test: Edge case — empty date range
    try:
        empty = tx.list_filters(date_from="2099-01-01", date_to="2099-12-31", limit=100)
        r.ok("Empty date range") if len(empty) == 0 else r.fail("Empty range", f"Got {len(empty)} results")
    except Exception as e:
        r.fail("Empty date range", str(e))

    # Test: Edge case — zero amount
    try:
        tx.create(tx_date="2025-03-30", account_id="acc_sbi", pay_method="PHONEPAY",
                  tx_type="DEBIT", amount=0.01, description="Edge case: minimum amount", category="other")
        r.ok("Edge case: minimum amount (0.01)")
    except Exception as e:
        r.fail("Edge case: minimum amount", str(e))


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  Finance Manager v3 — Test Suite")
    print("=" * 60)

    # Setup
    print("\n  Setting up test database...")
    start = time.time()
    db = setup_test_db()

    # Initialize repos
    from db.repositories import (
        AccountsRepo, TransactionsRepo, LookupsRepo, SecurityRepo,
        LoansRepo, BorrowedRepo, DepositsRepo, FDRepo, MFRepo,
        NotesRepo, CardsRepo, DebitCardsRepo, AuditRepo
    )

    repos = {
        "accounts": AccountsRepo(db),
        "transactions": TransactionsRepo(db),
        "lookups": LookupsRepo(db),
        "security": SecurityRepo(db),
        "audit": AuditRepo(db),
        "loans": LoansRepo(db),
        "borrowed": BorrowedRepo(db),
        "deposits": DepositsRepo(db),
        "fd": FDRepo(db),
        "mf": MFRepo(db),
        "notes": NotesRepo(db),
        "cards": CardsRepo(db),
        "debit_cards": DebitCardsRepo(db),
    }

    setup_time = time.time() - start
    print(f"  Setup completed in {setup_time:.2f}s")

    # Run tests
    r = TestResults()
    start = time.time()

    try:
        test_schema_integrity(r, db)
        test_data_consistency(r, db)
        test_accounts(r, db, repos)
        test_transactions(r, db, repos)
        test_loans(r, db, repos)
        test_borrowed(r, db, repos)
        test_deposits(r, db, repos)
        test_fd(r, db, repos)
        test_debit_cards(r, db, repos)
        test_debit_card_repo(r, db, repos)
        test_credit_cards(r, db, repos)
        test_lookups(r, db, repos)
        test_security(r, db, repos)
        test_preferences(r, db)
        test_services(r, db, repos)
        test_loans_recalc(r, db, repos)
        test_combinations(r, db, repos)
    except Exception as e:
        r.fail("UNEXPECTED ERROR", f"{e}\n{traceback.format_exc()}")

    test_time = time.time() - start

    # Summary
    success = r.summary()
    print(f"\n  ⏱️  Total time: {setup_time + test_time:.2f}s (setup: {setup_time:.2f}s, tests: {test_time:.2f}s)")
    print(f"  📊 Test database: {TEST_DB_PATH}")

    # Cleanup
    db.close()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
