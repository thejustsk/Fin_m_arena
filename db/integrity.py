"""Startup safety checks for the database file itself.

Background
----------
The Split tab once came up completely empty. Nothing had crashed and nothing
was logged. The cause was the database file, not the code:

* SQLite runs in WAL mode here, so a committed row can live only in
  ``finance.db-wal`` until a checkpoint folds it into ``finance.db``.
* ``finance.db`` and ``finance.db-wal`` were both tracked in git, so
  ``git reset --hard`` replaced the live pair with the copies frozen at commit
  time -- rolling the database back to that moment.
* ``run_migrations()`` then recreated the now-missing tables as empty ones, and
  every tab rendered a perfectly healthy-looking zero.

The failure was invisible, which is what made it dangerous. These checks make
that class of problem loud instead of silent. They only ever *report*; nothing
here writes to or repairs the database.
"""
import os
import sqlite3
from datetime import datetime

# Tables whose disappearance means a rollback rather than a fresh install.
_CORE_TABLES = ("transactions", "accounts", "split_groups", "split_expenses")


def _table_names(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


def inspect_db(db_path):
    """Describe the on-disk state without modifying anything.

    Returns a dict with the keys ``exists``, ``fresh``, ``wal_bytes``,
    ``wal_only_tables`` and ``warnings``.
    """
    info = {
        "exists": os.path.exists(db_path),
        "fresh": False,
        "wal_bytes": 0,
        "wal_only_tables": [],
        "warnings": [],
    }
    if not info["exists"]:
        info["fresh"] = True
        return info

    wal = db_path + "-wal"
    info["wal_bytes"] = os.path.getsize(wal) if os.path.exists(wal) else 0

    try:
        # Reading with the -wal in place shows the true, current contents.
        with_wal = _table_names(db_path)
    except sqlite3.DatabaseError as exc:
        info["warnings"].append(f"Database could not be opened: {exc}")
        return info

    if not with_wal:
        info["fresh"] = True
        return info

    # A brand-new install has no core tables yet; that is not a rollback.
    if not any(t in with_wal for t in _CORE_TABLES):
        info["fresh"] = True
        return info

    if info["wal_bytes"] > 0:
        # Which tables would vanish if the -wal were lost or replaced?
        try:
            import shutil
            import tempfile
            tmp = tempfile.mkdtemp(prefix="fin_wal_check_")
            probe = os.path.join(tmp, "probe.db")
            shutil.copyfile(db_path, probe)  # main file only, no -wal
            try:
                without_wal = _table_names(probe)
                info["wal_only_tables"] = sorted(with_wal - without_wal)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass

    if info["wal_only_tables"]:
        info["warnings"].append(
            "These tables exist only inside finance.db-wal and would be lost "
            "if that file were deleted or replaced: "
            + ", ".join(info["wal_only_tables"])
            + ". They will be folded into finance.db now."
        )
    return info


def preflight_check(db_path=None, verbose=True):
    """Run at startup, before migrations. Reports; never repairs."""
    if db_path is None:
        from config import DB_PATH
        db_path = str(DB_PATH)

    info = inspect_db(db_path)
    if verbose and info["warnings"]:
        stamp = datetime.now().strftime("%H:%M:%S")
        for w in info["warnings"]:
            print(f"[{stamp}] DB CHECK: {w}")
    return info
