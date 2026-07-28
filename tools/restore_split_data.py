"""Restore the Split-tab data that was lost when the database rolled back.

Run this ONCE, with the app CLOSED:

    python tools/restore_split_data.py

What it does
------------
1. Takes a full backup of the current database first (nothing is done until
   that backup verifies clean).
2. Replays finance_data/recovery/split_recovery.sql, which contains 12
   contacts, 5 groups, 20 memberships, 12 expenses, 46 shares, 15 settlements
   and the 20 linked split transactions.
3. Re-checks integrity and foreign keys, then prints the row counts.

It is safe to run more than once. Every statement is INSERT OR IGNORE, so
rows that already exist are skipped and nothing is ever updated or deleted.
"""
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SQL_FILE = ROOT / "finance_data" / "recovery" / "split_recovery.sql"
TABLES = ["split_contacts", "split_groups", "split_group_members",
          "split_expenses", "split_shares", "split_settlements"]


def counts(con):
    out = {}
    for t in TABLES + ["transactions"]:
        try:
            out[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except sqlite3.Error:
            out[t] = 0
    return out


def main():
    from config import DB_PATH
    db_path = Path(DB_PATH)

    if not SQL_FILE.exists():
        print(f"ERROR: recovery file not found: {SQL_FILE}")
        return 1
    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}")
        return 1

    # Make sure the schema exists before inserting into it.
    from db.connection import Database
    from db.schema import run_migrations
    db = Database(str(db_path))
    db.connect()
    run_migrations(db)
    db.commit()
    con = db.get()

    before = counts(con)
    print("Current row counts:")
    for k, v in before.items():
        print(f"   {k:24s} {v}")

    if all(before[t] for t in TABLES):
        print("\nSplit tables already populated - nothing to restore.")
        db.close()
        return 0

    print("\nBacking up before touching anything...")
    dest = db.backup()
    chk = sqlite3.connect(str(dest))
    ok = chk.execute("PRAGMA integrity_check").fetchone()[0]
    chk.close()
    if ok != "ok":
        print(f"   backup failed integrity check ({ok}) - aborting.")
        db.close()
        return 1
    print(f"   backup OK -> {dest}")

    print("\nRestoring split data...")
    con.executescript(SQL_FILE.read_text(encoding="utf-8"))
    db.commit()

    after = counts(con)
    print("\nRestored:")
    for k in after:
        delta = after[k] - before[k]
        flag = f"  (+{delta})" if delta else ""
        print(f"   {k:24s} {after[k]}{flag}")

    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    fks = con.execute("PRAGMA foreign_key_check").fetchall()
    print(f"\nintegrity_check : {integrity}")
    print(f"foreign keys    : {len(fks)} violations")

    db.checkpoint()
    db.close()

    if integrity == "ok" and not fks:
        print("\nDone. Start the app and open the Split tab - "
              "you should see 5 groups.")
        return 0
    print("\nSomething looks wrong. Your pre-restore backup is at:")
    print(f"   {dest}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
