# Split data loss — what happened, and what stops it happening again

## Symptom

The Split tab opened with no groups, ₹0 owed, ₹0 owing, an empty dropdown and a
blank page. No crash, no error dialog, nothing in the console. Other tabs looked
normal, which made it look like a Split-tab bug.

It was not a Split-tab bug. The Split tab was reading the database correctly.
The rows were gone from the database.

## Root cause

Three facts combined into a data-loss trap.

**1. SQLite runs in WAL mode.** `db/connection.py` sets
`PRAGMA journal_mode = WAL`. In WAL mode a committed row is written to
`finance.db-wal` and only later folded into `finance.db` by a checkpoint. Until
that checkpoint happens the row lives in the `-wal` file *and nowhere else*.

The repository state proved this exactly. Reading `finance.db` on its own:

| tables                                            | in `finance.db` | in `finance.db` + `-wal` |
| ------------------------------------------------- | --------------- | ------------------------ |
| `split_groups`, `split_expenses`, `split_shares` … | **did not exist** | 5 / 12 / 46 rows        |
| `transactions`                                    | 2,431           | 2,451                    |

Seven whole tables existed *only* inside the `-wal` file.

**2. The database was tracked in git.** `finance.db`, `finance.db-wal` **and**
`finance.db-shm` were all committed. So `git reset --hard` — the documented way
to pull updates for this project — overwrote the live database *and* its WAL
with the copies frozen at commit time. The database was rolled back to whatever
state it was in when that commit was made. Anything done since was gone.

Restoring a stale `.db` next to a stale `-wal` is the worst case: SQLite happily
opens the pair and reports no error at all.

**3. Migrations hid the evidence.** `run_migrations()` uses
`CREATE TABLE IF NOT EXISTS`. With the split tables now missing, it recreated
them — empty. The app started cleanly and rendered a confident, healthy-looking
zero.

There was no backup to fall back on either: `Database.backup()` used
`shutil.copy2(finance.db)`, which copies the main file only. Every one of the 12
backups in `finance_data/backups/` is missing the split tables entirely. The
Google Drive backup had the same flaw.

## What was recovered

Everything. The committed `-wal` blob still held the data, and it has been
extracted to `finance_data/recovery/split_recovery.sql`:

| table                 | rows |
| --------------------- | ---- |
| `split_contacts`      | 12   |
| `split_groups`        | 5    |
| `split_group_members` | 20   |
| `split_expenses`      | 12   |
| `split_shares`        | 46   |
| `split_settlements`   | 15   |
| linked `transactions` | 20   |

Groups: MOJO ASTE, KPM, BANGLROE, MAHARASHRA, BANGLORE FOODIES.

Restore with the app closed:

```bash
python tools/restore_split_data.py
```

It backs up first, verifies that backup, then replays the SQL. Every statement
is `INSERT OR IGNORE`, so it never updates or deletes and is safe to re-run.

## Fixes

| # | Fix | File |
| - | --- | ---- |
| 1 | Database files untracked and ignored — git can no longer overwrite them | `.gitignore` |
| 2 | `backup()` uses sqlite's online-backup API, so WAL contents are included | `db/connection.py` |
| 3 | Drive backup snapshots via the same API instead of `shutil.copy2` | `services/drive_backup.py` |
| 4 | `checkpoint()` added; runs at startup and on close, so `finance.db` is self-contained at rest | `db/connection.py`, `main.py` |
| 5 | Startup preflight warns when tables exist only in the `-wal` | `db/integrity.py` |
| 6 | `safe_update.py` snapshots, updates, and restores the DB if git removes it | `tools/safe_update.py` |

## Updating from now on

Use:

```bash
python tools/safe_update.py
```

`git reset --hard` is now safe for the database (it is untracked and therefore
untouched) — with one exception. On the *first* update after this change, git
deletes `finance_data/finance.db`, because the file is tracked in your current
commit and untracked in the new one. `safe_update.py` snapshots beforehand and
puts it back automatically. After that first update the hazard is gone for good.
