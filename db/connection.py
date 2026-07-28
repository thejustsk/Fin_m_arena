"""Database connection manager. UI never touches this directly."""
import sqlite3
from config import DB_PATH, DB_KEY


class Database:
    """SQLite connection with foreign keys ON. SQLCipher-ready."""

    def __init__(self, path=None):
        self.path = str(path or DB_PATH)
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        # If SQLCipher is available:
        # if DB_KEY:
        #     self.conn.execute(f"PRAGMA key = '{DB_KEY}'")
        return self.conn

    def get(self):
        if not self.conn:
            self.connect()
        return self.conn

    def checkpoint(self):
        """Fold the -wal file back into the main .db.

        In WAL mode a committed row can live *only* in finance.db-wal until a
        checkpoint runs. Anything that copies finance.db on its own (file
        backup, Drive upload, git) therefore silently captures a database that
        is missing the newest data. Call this before any such copy.
        """
        if not self.conn:
            return
        try:
            self.conn.commit()
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass

    def close(self):
        if self.conn:
            # Checkpoint on the way out so finance.db is self-contained at rest.
            self.checkpoint()
            self.conn.close()
            self.conn = None

    def execute(self, sql, params=()):
        return self.get().execute(sql, params)

    def commit(self):
        self.get().commit()

    def backup(self):
        """Write a complete, self-contained snapshot to BACKUP_DIR.

        Uses sqlite3's online-backup API rather than shutil.copy2. A plain file
        copy grabs finance.db only, so every row still sitting in the -wal is
        lost -- that is how a set of backups can each be missing whole tables.
        """
        from datetime import datetime
        from config import BACKUP_DIR, BACKUP_RETENTION
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = BACKUP_DIR / f"finance_{ts}.db"
        n = 1
        while dest.exists():          # two backups in the same second
            dest = BACKUP_DIR / f"finance_{ts}_{n}.db"
            n += 1

        self.checkpoint()
        target = sqlite3.connect(str(dest))
        try:
            self.get().backup(target)
            # The snapshot inherits WAL mode, which would leave -wal/-shm
            # sidecars next to the backup. Switch it to a single-file journal
            # so each backup is one self-contained artefact.
            target.execute("PRAGMA journal_mode=DELETE")
        finally:
            target.close()
        for suffix in ("-wal", "-shm"):
            leftover = dest.with_name(dest.name + suffix)
            if leftover.exists():
                leftover.unlink()

        files = sorted(BACKUP_DIR.glob("finance_*.db"),
                       key=lambda f: f.stat().st_mtime, reverse=True)
        for f in files[BACKUP_RETENTION:]:
            f.unlink()
            for suffix in ("-wal", "-shm"):   # tidy any legacy sidecars
                s = f.with_name(f.name + suffix)
                if s.exists():
                    s.unlink()
        return dest
