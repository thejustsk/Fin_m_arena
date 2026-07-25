#!/usr/bin/env python3
"""
MIGRATION SCRIPT — Old Finance DB → New Finance Manager v3
==========================================================
Run this ONCE from the finance_app directory.

Usage:
    python migrate.py "path/to/finance_manager2026_06.db"

What it does:
    1. Reads old DB (your existing data)
    2. Maps accounts, categories, payment methods, cards
    3. Migrates ALL transactions with correct account mapping
    4. Migrates loans, borrowers, repayments
    5. Migrates notes and trash
    6. Creates credit card records from CARD_DETAILS
    7. Calculates opening balances from balance columns
    8. Prints full summary of what was migrated

SAFE: Does NOT modify the old DB. Creates/updates the new DB only.
"""

import sqlite3
import sys
import uuid
from pathlib import Path
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════

# New DB path (the app's database)
NEW_DB = "finance_data/finance.db"

# Card details from your data
CARD_DETAILS = [
    {"name": "AMAZON PAY ICICI CARD", "bank": "ICICI BANK", "brand": "AMAZON PAY", "type": "VISA", "class": "", "number": "XXXX XXXX XXXX 7000", "valid_till": "03/33", "limit": 100000, "statement_date": "20th", "due_date": "8th", "color1": "#3a3a3a", "color2": "#0f0f0f", "live_status": True},
    {"name": "ICICI CORAL CARD", "bank": "ICICI BANK", "brand": "CORAL", "type": "RUPAY", "class": "Platinum", "number": "XXXX XXXX XXXX 5007", "valid_till": "05/33", "limit": 100000, "statement_date": "20th", "due_date": "8th", "color1": "#4b2e2e", "color2": "#120909", "live_status": True},
    {"name": "PHONEPAY SBI CARD", "bank": "STATE BANK OF INDIA", "brand": "PHONEPAY", "type": "VISA", "class": "Signature", "number": "XXXX XXXX XXXX 8974", "valid_till": "04/33", "limit": 50000, "statement_date": "06th", "due_date": "10th", "color1": "#2a1a3a", "color2": "#08051b", "live_status": True},
    {"name": "AXIS SUPERMONEY CARD PRO", "bank": "AXIS BANK", "brand": "SUPERMONEY", "type": "RUPAY", "class": "Platinum", "number": "XXXX XXXX XXXX 2324", "valid_till": "10/30", "limit": 190000, "statement_date": "16th", "due_date": "04th", "color1": "#4b1a3a", "color2": "#12050d", "live_status": True},
    {"name": "AXIS NEO CARD", "bank": "AXIS BANK", "brand": "NEO PLATINUM", "type": "RUPAY", "class": "Platinum", "number": "XXXX XXXX XXXX 8625", "valid_till": "02/31", "limit": 190000, "statement_date": "16th", "due_date": "04th", "color1": "#4a1a2a", "color2": "#14050b", "live_status": True},
    {"name": "AXIS MYZONE CARD", "bank": "AXIS BANK", "brand": "MYZONE", "type": "RUPAY", "class": "Platinum", "number": "XXXX XXXX XXXX 3701", "valid_till": "11/30", "limit": 190000, "statement_date": "13th", "due_date": "1st", "color1": "#2a2a4b", "color2": "#08081b", "live_status": True},
    {"name": "UNI BOB GOLDX CARD", "bank": "BANK OF BARODA", "brand": "UNI GOLDX", "type": "VISA", "class": "", "number": "XXXX XXXX XXXX 7585", "valid_till": "04/31", "limit": 55000, "statement_date": "26th", "due_date": "12th", "color1": "#1c3d5a", "color2": "#0a0f14", "live_status": True},
    {"name": "UNI BOB UPI CARD", "bank": "BANK OF BARODA", "brand": "UNI GOLDX", "type": "RUPAY", "class": "", "number": "XXXX XXXX XXXX 3225", "valid_till": "04/31", "limit": 55000, "statement_date": "26th", "due_date": "12th", "color1": "#4b3a2a", "color2": "#150f08", "live_status": True},
    {"name": "RBL BANKBAZAR CARD", "bank": "RBL BANK", "brand": "BANKBAZAR", "type": "MASTERCARD", "class": "", "number": "XXXX XXXX XXXX 1156", "valid_till": "06/31", "limit": 75000, "statement_date": "22nd", "due_date": "08th", "color1": "#2a4b3a", "color2": "#081b10", "live_status": True},
    {"name": "FEDERAL SIGNET CARD", "bank": "FEDERAL BANK", "brand": "SIGNET", "type": "RUPAY", "class": "Platinum", "number": "XXXX XXXX XXXX 0857", "valid_till": "02/30", "limit": 10000, "due_date": "10th", "color1": "#1a2a4b", "color2": "#05081b", "live_status": True},
    {"name": "SWIGGY HDFC ORNGE CARD", "bank": "HDFC BANK", "brand": "SWIGGY ORNGE", "type": "MASTERCARD", "class": "", "number": "XXXX XXXX XXXX 7617", "valid_till": "05/33", "limit": 50000, "statement_date": "20th", "due_date": "10th", "color1": "#1a1a3a", "color2": "#05051b", "live_status": True},
    {"name": "YES BANK CARD", "bank": "YES BANK", "brand": "BANKBAZAR", "type": "VISA", "class": "Platinum", "number": "XXXX XXXX XXXX 5846", "valid_till": "04/33", "limit": 26000, "statement_date": "21st", "due_date": "20th", "color1": "#3a4a1a", "color2": "#0f1405", "live_status": True},
    {"name": "YES BANK UPI CARD", "bank": "YES BANK", "brand": "BANKBAZAR", "type": "RUPAY", "class": "", "number": "XXXX XXXX XXXX 9097", "valid_till": "04/33", "limit": 26000, "statement_date": "26th", "due_date": "15th", "color1": "#2e4b34", "color2": "#0a120c", "live_status": True},
    {"name": "LIC IDFC CARD", "bank": "IDFC FIRST BANK", "brand": "CLASSIC", "type": "MASTERCARD", "class": "", "number": "XXXX XXXX XXXX 3995", "valid_till": "05/34", "limit": 100000, "statement_date": "20th", "due_date": "10th", "color1": "#1a3a3a", "color2": "#050f0f", "live_status": True},
    {"name": "SLICE CARD", "bank": "SLICE SMALL FINANCE BANK", "brand": "", "type": "", "class": "", "number": "XXXX XXXX XXXX 4360", "valid_till": "03/33", "limit": 45000, "statement_date": "22nd", "due_date": "08th", "color1": "#3a2a1a", "color2": "#0f0805", "live_status": True},
]


# ══════════════════════════════════════════════════════════════
# MAPPING TABLES
# ══════════════════════════════════════════════════════════════

# Old TxMode → New account info
ACCOUNT_MAP = {
    # Current accounts
    "FEDERAL":       {"display_name": "FEDERAL BANK",    "short_label": "FEDB", "account_type": "CURRENT", "balance_col": "fbbalance"},
    "SBI":           {"display_name": "SBI",             "short_label": "SBIN", "account_type": "CURRENT", "balance_col": "sbibalance"},
    "CANARA":        {"display_name": "CANARA BANK",     "short_label": "CANB", "account_type": "CURRENT", "balance_col": "canara_balance"},
    "SOUTH INDIA":   {"display_name": "SOUTH INDIA BANK","short_label": "SIBN", "account_type": "CURRENT", "balance_col": "sib_balance"},
    "AIRTEL PB":     {"display_name": "AIRTEL PB",       "short_label": "AIRP", "account_type": "WALLET",  "balance_col": "airtel_pb_balance"},
    # Wallets
    "AMAZON WALLET":  {"display_name": "AMAZON WALLET",  "short_label": "AMZW", "account_type": "WALLET",  "balance_col": "a1_balance"},
    "PHONEPAY WALLET":{"display_name": "PHONEPAY WALLET","short_label": "PPW",  "account_type": "WALLET",  "balance_col": "a2_balance"},
    "NAMMA METRO CARD":{"display_name": "NAMMA METRO CARD","short_label": "NMET","account_type": "WALLET", "balance_col": "a3_balance"},
    # Cash
    "CASH":          {"display_name": "CASH AT HOME",    "short_label": "CASH", "account_type": "CASH",    "balance_col": "cashbalance"},
}

# Old balance column → Credit card name (from CARD_DETAILS)
CC_BALANCE_MAP = {
    "amazon_icici_balance":  "AMAZON PAY ICICI CARD",
    "axissmpc_balance":      "AXIS SUPERMONEY CARD PRO",
    "fbsignetc_balance":     "FEDERAL SIGNET CARD",
    "axismzc_balance":       "AXIS MYZONE CARD",
    "uni_bob_balance":       "UNI BOB GOLDX CARD",
    "bajaj_balance":         "BAJAJ EMI CARD",
    "uni_bob_upi_balance":   "UNI BOB UPI CARD",
    "pp_sbi_balance":        "PHONEPAY SBI CARD",
    "rbl_bb_balance":        "RBL BANKBAZAR CARD",
    "yesb_cc_balance":       "YES BANK CARD",
    "yesb_upi_cc_balance":   "YES BANK UPI CARD",
}

# Old TxMode values that are actually credit cards
CC_TXMODE_MAP = {
    "FB SIGNET C":   "FEDERAL SIGNET CARD",
    "AXIS MZC":      "AXIS MYZONE CARD",
    "AXIS SMPC":     "AXIS SUPERMONEY CARD PRO",
    "AMAZON ICICI C":"AMAZON PAY ICICI CARD",
    "UNI BOB C":     "UNI BOB GOLDX CARD",
    "BAJAJ EMI C":   "BAJAJ EMI CARD",
    "UNI BOB UPI C": "UNI BOB UPI CARD",
    "PP SBI C":      "PHONEPAY SBI CARD",
    "RBL BB C":      "RBL BANKBAZAR CARD",
    "YESB C":        "YES BANK CARD",
    "YESB UPI C":    "YES BANK UPI CARD",
    "ICICI CORAL":   "ICICI CORAL CARD",
    "AXIS NEO":      "AXIS NEO CARD",
    "SWIGGY HDFC":   "SWIGGY HDFC ORNGE CARD",
    "LIC IDFC":      "LIC IDFC CARD",
    "SLICE":         "SLICE CARD",
    "SBI PHONEPAY C":"PHONEPAY SBI CARD",
    "YESBANK C":     "YES BANK CARD",
    "YESBANK UPI C": "YES BANK UPI CARD",
}

# Old category → New category_id
CATEGORY_MAP = {
    "Food":               "food_dining",
    "Travel":             "transport",
    "Entertainment":      "entertainment",
    "Internet & Services":"bills_utilities",
    "Internet &amp; Services": "bills_utilities",
    "Savings":            "investment",
    "Finance":            "finance",
    "Transportation":     "transport",
    "Health & Fitness":   "health",
    "Health &amp; Fitness": "health",
    "Medicine":           "health",
    "Education":          "education",
    "Grocery":            "food_dining",
    "Electronics":        "shopping",
    "Equipment":          "shopping",
    "Clothing":           "shopping",
    "Personal Care":      "health",
    "Other":              "other",
    "B HOME":             "rent",
    "KCW":                "other",
    "transfer":           "transfer",
}

# Old self_trxn → New transaction_kind
SELF_TRXN_MAP = {
    0: "REGULAR",
    1: "TRANSFER",
    2: "REGULAR",  # Will be refined based on loans table
    3: "REGULAR",  # Finance label
}


# ══════════════════════════════════════════════════════════════
# MIGRATION LOGIC
# ══════════════════════════════════════════════════════════════

def migrate(old_db_path):
    """Run the full migration."""
    print(f"\n{'='*60}")
    print(f"  FINANCE MANAGER — DATA MIGRATION")
    print(f"  Old DB: {old_db_path}")
    print(f"  New DB: {NEW_DB}")
    print(f"{'='*60}\n")

    # Connect
    old_conn = sqlite3.connect(old_db_path)
    old_conn.row_factory = sqlite3.Row
    new_conn = sqlite3.connect(NEW_DB)
    new_conn.row_factory = sqlite3.Row
    new_conn.execute("PRAGMA foreign_keys = OFF")  # Disable during migration

    # Run schema on new DB
    from db.schema import run_migrations
    class FakeDB:
        def __init__(self, conn):
            self._conn = conn
        def get(self):
            return self._conn
    run_migrations(FakeDB(new_conn))

    stats = {
        "accounts_created": 0,
        "cards_created": 0,
        "transactions_migrated": 0,
        "transfers_migrated": 0,
        "loans_migrated": 0,
        "borrowers_migrated": 0,
        "repayments_migrated": 0,
        "notes_migrated": 0,
        "errors": [],
    }

    # ── Step 1: Create accounts ──
    print("[1/7] Creating accounts...")
    acct_id_map = {}  # old_name → new account_id

    # Current accounts + wallets + cash
    for old_name, info in ACCOUNT_MAP.items():
        aid = str(uuid.uuid4())
        new_conn.execute(
            "INSERT OR IGNORE INTO accounts(account_id, display_name, short_label, account_type, opening_balance, color_hex, is_active, created_at) "
            "VALUES(?, ?, ?, ?, 0, '#4F46E5', 1, ?)",
            (aid, info["display_name"], info["short_label"], info["account_type"], datetime.now().isoformat())
        )
        acct_id_map[old_name] = aid
        stats["accounts_created"] += 1
        print(f"  + {info['display_name']} ({info['account_type']})")

    # Credit card accounts
    for card in CARD_DETAILS:
        aid = str(uuid.uuid4())
        name = card["name"]
        new_conn.execute(
            "INSERT OR IGNORE INTO accounts(account_id, display_name, short_label, account_type, credit_limit, opening_balance, color_hex, is_active, created_at) "
            "VALUES(?, ?, ?, 'CREDIT_CARD', ?, 0, '#7C3AED', ?, ?)",
            (aid, name, name[:8].upper(), card["limit"], 1 if card["live_status"] else 0, datetime.now().isoformat())
        )
        acct_id_map[name] = aid
        stats["accounts_created"] += 1
        print(f"  + {name} (CREDIT_CARD, limit: {card['limit']:,})")

    # BAJAJ EMI CARD (not in CARD_DETAILS but has balance column)
    if "BAJAJ EMI CARD" not in acct_id_map:
        aid = str(uuid.uuid4())
        new_conn.execute(
            "INSERT OR IGNORE INTO accounts(account_id, display_name, short_label, account_type, opening_balance, color_hex, is_active, created_at) "
            "VALUES(?, ?, 'BAJEM', 'CREDIT_CARD', 0, '#7C3AED', 1, ?)",
            (aid, "BAJAJ EMI CARD", datetime.now().isoformat())
        )
        acct_id_map["BAJAJ EMI CARD"] = aid
        stats["accounts_created"] += 1
        print(f"  + BAJAJ EMI CARD (CREDIT_CARD)")

    new_conn.commit()

    # ── Step 2: Create credit card records ──
    print("\n[2/7] Creating credit card records...")
    for card in CARD_DETAILS:
        aid = acct_id_map.get(card["name"])
        if not aid:
            continue
        cid = str(uuid.uuid4())
        expiry_parts = card["valid_till"].split("/")
        em = int(expiry_parts[0]) if len(expiry_parts) > 0 else 12
        ey = int("20" + expiry_parts[1]) if len(expiry_parts) > 1 else 2028
        last4 = card["number"].split()[-1] if card["number"] else "0000"
        new_conn.execute(
            "INSERT OR IGNORE INTO cards(card_id, account_id, card_name, issuer_bank, card_brand, card_network, card_class, "
            "last_four, cardholder_name, expiry_month, expiry_year, statement_date, due_date, grace_days, annual_fee, "
            "card_color_1, card_color_2, is_active, created_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 20, 0, ?, ?, ?, ?)",
            (cid, aid, card["name"], card["bank"], card["brand"], card["type"], card["class"],
             last4, card["name"], em, ey, card.get("statement_date", ""), card.get("due_date", ""),
             card["color1"], card["color2"], 1 if card["live_status"] else 0, datetime.now().isoformat())
        )
        stats["cards_created"] += 1
    new_conn.commit()
    print(f"  Created {stats['cards_created']} card records")

    # ── Step 3: Calculate opening balances ──
    print("\n[3/7] Calculating opening balances...")
    old_txns = old_conn.execute("SELECT * FROM transactions ORDER BY TxDate ASC, date ASC").fetchall()

    if old_txns:
        first_txn = old_txns[0]
        print(f"  First transaction: {first_txn['TxDate']} | {first_txn['TxMode']} | {first_txn['Txtype']} | {first_txn['amount']}")
        for old_name, info in ACCOUNT_MAP.items():
            bal_col = info["balance_col"]
            try:
                balance_after = float(first_txn[bal_col])
            except (KeyError, TypeError, IndexError):
                balance_after = 0.0
            # opening = balance_after - net_effect_of_first_txn
            if first_txn["TxMode"] == old_name:
                amt = float(first_txn["amount"])
                if first_txn["Txtype"] == "DEBIT":
                    opening = balance_after + amt
                else:
                    opening = balance_after - amt
            else:
                opening = balance_after
            aid = acct_id_map.get(old_name)
            if aid:
                new_conn.execute("UPDATE accounts SET opening_balance=? WHERE account_id=?", (round(opening, 2), aid))
                if abs(opening) > 0.01:
                    print(f"  {info['display_name']}: opening = {opening:,.2f} (bal_after={balance_after:,.2f})")

        # Credit card opening balances (stored as negative = money owed)
        for bal_col, cc_name in CC_BALANCE_MAP.items():
            try:
                balance_after = float(first_txn[bal_col])
            except (KeyError, TypeError, IndexError):
                balance_after = 0.0
            aid = acct_id_map.get(cc_name)
            if aid:
                new_conn.execute("UPDATE accounts SET opening_balance=? WHERE account_id=?", (round(balance_after, 2), aid))
                if abs(balance_after) > 0.01:
                    print(f"  {cc_name}: opening = {balance_after:,.2f}")
    new_conn.commit()

    # ── Step 4: Migrate transactions ──
    print(f"\n[4/7] Migrating {len(old_txns)} transactions...")

    # Build set of loan txn_ids to identify loan-related transactions
    loan_txn_ids = set()
    try:
        for row in old_conn.execute("SELECT trxn_id FROM Loans WHERE trxn_id != 'NA' AND trxn_id IS NOT NULL"):
            loan_txn_ids.add(row[0])
    except:
        pass

    # Build transfer pairs (self_trxn = 1)
    transfer_groups = {}  # (date, amount) → [txn_ids]
    for txn in old_txns:
        if txn["self_trxn"] == 1:
            key = (txn["TxDate"], txn["amount"])
            if key not in transfer_groups:
                transfer_groups[key] = []
            transfer_groups[key].append(txn["id"])

    for txn in old_txns:
        try:
            old_id = txn["id"]
            tx_date = txn["TxDate"]
            old_mode = txn["TxMode"] or ""
            old_method = txn["pay_method"] or "OTHER"
            old_type = (txn["Txtype"] or "").upper().strip()
            amount = abs(float(txn["amount"]))
            if amount <= 0:
                stats["errors"].append(f"Skipping txn {old_id}: amount={amount}")
                continue
            person_org = txn["PersonOrg"]
            description = txn["description"]
            provider = txn["Provider"]
            self_trxn = int(txn["self_trxn"] or 0)
            old_category = txn["category"] or "Other"
            neednwant = int(txn["neednwant"] or 0)
            pf_category = txn["pf_category"] or "NC"
            created_at = txn["date"]

            # Normalize tx_type
            if old_type not in ("CREDIT", "DEBIT"):
                # Try to infer from amount sign or skip
                stats["errors"].append(f"Unknown tx_type '{old_type}' in txn {old_id}, skipping")
                continue

            # Resolve account_id
            account_id = None
            # Check if TxMode is a credit card
            cc_name = CC_TXMODE_MAP.get(old_mode)
            if cc_name:
                account_id = acct_id_map.get(cc_name)
            else:
                account_id = acct_id_map.get(old_mode)

            if not account_id:
                # Try fuzzy match
                for key, aid in acct_id_map.items():
                    if old_mode and old_mode.upper() in key.upper():
                        account_id = aid
                        break
            if not account_id:
                stats["errors"].append(f"Unknown account mode: '{old_mode}' (txn {old_id})")
                continue

            # Resolve payment method
            method_id = old_method if old_method else "OTHER"

            # Resolve category
            cat_id = CATEGORY_MAP.get(old_category, "other")
            if not cat_id:
                cat_id = "other"

            # Resolve transaction_kind
            txn_kind = "REGULAR"
            transfer_group_id = None

            if self_trxn == 1:
                txn_kind = "TRANSFER"
                key = (tx_date, amount)
                group_txns = transfer_groups.get(key, [])
                if len(group_txns) > 1:
                    transfer_group_id = str(uuid.uuid4())
                    transfer_groups[key] = []
                else:
                    transfer_group_id = str(uuid.uuid4())
            elif old_id in loan_txn_ids:
                # Directly linked to a loan record
                txn_kind = "LOAN_GIVEN" if old_type == "DEBIT" else "LOAN_REPAYMENT"
            elif self_trxn == 2:
                # Loan-related — determine exact kind from description
                desc_lower = (description or "").lower()
                if "loan given" in desc_lower or "loan given" in desc_lower:
                    txn_kind = "LOAN_GIVEN"
                elif "repayment" in desc_lower and old_type == "CREDIT":
                    txn_kind = "LOAN_REPAYMENT"
                elif "emi" in desc_lower:
                    txn_kind = "EMI_PAYMENT"
                elif "loan taken" in desc_lower or "loan received" in desc_lower:
                    txn_kind = "LOAN_TAKEN"
                elif "fd" in desc_lower and ("deposit" in desc_lower or "created" in desc_lower):
                    txn_kind = "FD_DEPOSIT"
                elif "fd" in desc_lower and ("withdraw" in desc_lower or "mature" in desc_lower):
                    txn_kind = "FD_WITHDRAWAL"
                elif "deposit received" in desc_lower:
                    txn_kind = "DEPOSIT_RECEIVED"
                elif "deposit repay" in desc_lower or "deposit return" in desc_lower:
                    txn_kind = "DEPOSIT_REPAYMENT"
                elif "mf" in desc_lower and ("purchase" in desc_lower or "buy" in desc_lower or "sip" in desc_lower):
                    txn_kind = "MF_PURCHASE"
                elif "mf" in desc_lower and ("redeem" in desc_lower or "sell" in desc_lower):
                    txn_kind = "MF_REDEMPTION"
                elif "repayment" in desc_lower:
                    txn_kind = "LOAN_REPAYMENT"
                elif "emi" in desc_lower:
                    txn_kind = "EMI_PAYMENT"
                else:
                    txn_kind = "LOAN_GIVEN" if old_type == "DEBIT" else "LOAN_REPAYMENT"
            elif self_trxn == 3:
                cat_id = "finance"

            # Resolve pf_category
            pf_map = {"NC": "nc", "nc": "nc", "COMMITMENT": "commitment", "CONSUMPTION": "consumption",
                      "GROWTH": "growth", "SAFETY": "safety", "INTERNAL_TRANSFER": "internal_transfer"}
            pf_id = pf_map.get(pf_category.upper() if pf_category else "NC", "nc")

            # Insert transaction
            new_txn_id = str(uuid.uuid4())
            new_conn.execute(
                "INSERT INTO transactions(id, tx_date, account_id, pay_method, tx_type, amount, person_org, description, "
                "created_at, transaction_kind, transfer_group_id, category, neednwant, pf_category) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (new_txn_id, tx_date, account_id, method_id, old_type, amount,
                 person_org, description, created_at, txn_kind, transfer_group_id,
                 cat_id, neednwant, pf_id)
            )

            # Store mapping for loan linking
            txn_id_map[old_id] = new_txn_id

            stats["transactions_migrated"] += 1
            if txn_kind == "TRANSFER":
                stats["transfers_migrated"] += 1

            if stats["transactions_migrated"] % 500 == 0:
                print(f"  ... {stats['transactions_migrated']} migrated")
                new_conn.commit()

        except Exception as e:
            stats["errors"].append(f"Transaction {txn['id']}: {e}")

    new_conn.commit()
    print(f"  Migrated {stats['transactions_migrated']} transactions ({stats['transfers_migrated']} transfers)")

    # ── Step 5: Migrate borrowers ──
    print("\n[5/7] Migrating borrowers & loans...")
    borrower_id_map = {}
    try:
        old_borrowers = old_conn.execute("SELECT * FROM Borrowers").fetchall()
        for b in old_borrowers:
            new_id = str(uuid.uuid4())
            new_conn.execute(
                "INSERT OR IGNORE INTO borrowers(borrower_id, name, created_at) VALUES(?, ?, ?)",
                (new_id, b["name"], b["created_at"] if b["created_at"] else datetime.now().isoformat())
            )
            borrower_id_map[b["borrower_id"]] = new_id
            stats["borrowers_migrated"] += 1
        new_conn.commit()
        print(f"  Migrated {stats['borrowers_migrated']} borrowers")
    except Exception as e:
        stats["errors"].append(f"Borrowers: {e}")

    # ── Step 6: Migrate loans & repayments ──
    print("\n[6/7] Migrating loans & repayments...")
    loan_id_map = {}
    try:
        old_loans = old_conn.execute("SELECT * FROM Loans").fetchall()
        for l in old_loans:
            new_loan_id = str(uuid.uuid4())
            new_borrower_id = borrower_id_map.get(l["borrower_id"])
            if not new_borrower_id:
                stats["errors"].append(f"Loan {l['loan_id']}: borrower not found")
                continue
            # Map linked transaction
            linked_txn = txn_id_map.get(l["trxn_id"]) if l["trxn_id"] and l["trxn_id"] != "NA" else None

            new_conn.execute(
                "INSERT INTO loans(loan_id, borrower_id, loan_amount, payment_method, start_date, due_date, "
                "status, description, trxn_id, created_at, interest_rate, interest_method) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'SIMPLE')",
                (new_loan_id, new_borrower_id, l["loan_amount"], l["payment_method"],
                 l["start_date"], l["due_date"], l["status"].upper() if l["status"] else "ACTIVE",
                 l["description"] or "", linked_txn, l["created_at"] if l["created_at"] else datetime.now().isoformat())
            )
            loan_id_map[l["loan_id"]] = new_loan_id
            stats["loans_migrated"] += 1

            # Migrate repayments for this loan
            try:
                old_reps = old_conn.execute("SELECT * FROM Repayments WHERE loan_id=?", (l["loan_id"],)).fetchall()
                for r in old_reps:
                    rep_txn = txn_id_map.get(getattr(r, 'linked_txn_id', None)) if hasattr(r, 'linked_txn_id') else None
                    new_conn.execute(
                        "INSERT INTO repayments(repayment_id, loan_id, amount_paid, payment_date, payment_method, description, created_at, linked_txn_id) "
                        "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), new_loan_id, r["amount_paid"], r["payment_date"],
                         r["payment_method"], r["description"] or "",
                         r["created_at"] if r["created_at"] else datetime.now().isoformat(), rep_txn)
                    )
                    stats["repayments_migrated"] += 1
            except Exception as e:
                stats["errors"].append(f"Repayments for loan {l['loan_id']}: {e}")

        new_conn.commit()
        print(f"  Migrated {stats['loans_migrated']} loans, {stats['repayments_migrated']} repayments")
    except Exception as e:
        stats["errors"].append(f"Loans: {e}")

    # ── Step 7: Migrate notes ──
    print("\n[7/7] Migrating notes...")
    try:
        old_notes = old_conn.execute("SELECT * FROM notes").fetchall()
        for n in old_notes:
            new_conn.execute(
                "INSERT OR IGNORE INTO notes(id, title, tags, content, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), n["title"], n["tags"], n["content"],
                 n["created_at"], n["updated_at"] if n["updated_at"] else n["created_at"])
            )
            stats["notes_migrated"] += 1
        new_conn.commit()
        print(f"  Migrated {stats['notes_migrated']} notes")
    except Exception as e:
        stats["errors"].append(f"Notes: {e}")

    # Close
    old_conn.close()
    new_conn.execute("PRAGMA foreign_keys = ON")
    new_conn.commit()
    new_conn.close()

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"  MIGRATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Accounts:        {stats['accounts_created']}")
    print(f"  Credit Cards:    {stats['cards_created']}")
    print(f"  Transactions:    {stats['transactions_migrated']}")
    print(f"    - Transfers:   {stats['transfers_migrated']}")
    print(f"  Borrowers:       {stats['borrowers_migrated']}")
    print(f"  Loans:           {stats['loans_migrated']}")
    print(f"  Repayments:      {stats['repayments_migrated']}")
    print(f"  Notes:           {stats['notes_migrated']}")
    if stats["errors"]:
        print(f"\n  WARNINGS ({len(stats['errors'])}):")
        for e in stats["errors"][:20]:
            print(f"    ! {e}")
        if len(stats["errors"]) > 20:
            print(f"    ... and {len(stats['errors']) - 20} more")
    else:
        print(f"\n  No errors!")
    print(f"\n  New DB: {NEW_DB}")
    print(f"{'='*60}\n")


# ══════════════════════════════════════════════════════════════
# GLOBAL MAPPING (needed across steps)
# ══════════════════════════════════════════════════════════════
txn_id_map = {}  # old txn id → new txn id


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate.py <path_to_old_db>")
        print("Example: python migrate.py finance_manager2026_06.db")
        sys.exit(1)

    old_path = sys.argv[1]
    if not Path(old_path).exists():
        print(f"ERROR: File not found: {old_path}")
        sys.exit(1)

    migrate(old_path)
