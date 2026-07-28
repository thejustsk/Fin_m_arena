"""Pull the latest code WITHOUT ever putting the database at risk.

Why this exists
---------------
finance.db, finance.db-wal and finance.db-shm used to be tracked in git. That
meant `git reset --hard` rewrote the live database with the copy frozen at
commit time -- silently rolling the app back and, in one case, wiping the whole
Split tab.

Those files are untracked now, which fixes the rollback but introduces a second
hazard for exactly one update: git deletes a file that is untracked in the new
commit but tracked in the current one. This script sidesteps both problems by
taking a verified snapshot first, updating, then putting the database back if
git removed it.

Usage (with the app CLOSED):

    python tools/safe_update.py
"""
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "finance_data"
DB = DB_DIR / "finance.db"
BRANCH = "arena/019fa316-fin-m-arena"
SIDECARS = ("finance.db-wal", "finance.db-shm")


def _run(*args):
    return subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True)


def snapshot():
    """Full, self-contained copy of the DB (WAL folded in) + raw file copies."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_dir = DB_DIR / "pre_update" / stamp
    safe_dir.mkdir(parents=True, exist_ok=True)

    if DB.exists():
        # sqlite backup API captures rows still sitting in the -wal.
        src = sqlite3.connect(str(DB))
        try:
            src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            dst = sqlite3.connect(str(safe_dir / "finance.db"))
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        # Belt and braces: keep byte-for-byte copies too.
        shutil.copy2(DB, safe_dir / "finance.db.rawcopy")
        for name in SIDECARS:
            p = DB_DIR / name
            if p.exists():
                shutil.copy2(p, safe_dir / name)

        c = sqlite3.connect(str(safe_dir / "finance.db"))
        counts = {}
        for t in ("transactions", "split_groups", "split_expenses", "accounts"):
            try:
                counts[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except sqlite3.Error:
                counts[t] = "n/a"
        ok = c.execute("PRAGMA integrity_check").fetchone()[0]
        c.close()
        print(f"  snapshot -> {safe_dir}")
        print(f"  integrity: {ok} | " + " ".join(f"{k}={v}" for k, v in counts.items()))
        if ok != "ok":
            print("  !! snapshot failed integrity check - stopping.")
            sys.exit(1)
    else:
        print("  no finance.db found (first run?) - nothing to snapshot")
    return safe_dir


def main():
    print("1/4  Snapshotting the database...")
    safe_dir = snapshot()

    print("2/4  Fetching latest code...")
    r = _run("git", "fetch", "origin", BRANCH)
    if r.returncode:
        print(r.stderr)
        sys.exit(1)

    print("3/4  Updating working tree...")
    r = _run("git", "reset", "--hard", f"origin/{BRANCH}")
    if r.returncode:
        print(r.stderr)
        sys.exit(1)
    print("  " + r.stdout.strip())

    print("4/4  Verifying the database survived...")
    if not DB.exists():
        # Expected exactly once: the update that untracks finance_data/.
        shutil.copy2(safe_dir / "finance.db", DB)
        for name in SIDECARS:
            p = safe_dir / name
            if p.exists():
                shutil.copy2(p, DB_DIR / name)
        print("  git removed finance.db - restored from snapshot.")
    else:
        print("  finance.db still present.")

    c = sqlite3.connect(str(DB))
    try:
        n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        try:
            g = c.execute("SELECT COUNT(*) FROM split_groups").fetchone()[0]
        except sqlite3.Error:
            g = 0
        print(f"  transactions={n}  split_groups={g}")
    finally:
        c.close()

    print(f"\nDone. Snapshot kept at: {safe_dir}")
    print("Start the app normally: python main.py")


if __name__ == "__main__":
    main()
