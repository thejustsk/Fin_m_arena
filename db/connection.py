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

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def execute(self, sql, params=()):
        return self.get().execute(sql, params)

    def commit(self):
        self.get().commit()

    def backup(self):
        import shutil
        from datetime import datetime
        from config import BACKUP_DIR, BACKUP_RETENTION
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(self.path, str(BACKUP_DIR / f"finance_{ts}.db"))
        files = sorted(BACKUP_DIR.glob("finance_*.db"),
                       key=lambda f: f.stat().st_mtime, reverse=True)
        for f in files[BACKUP_RETENTION:]:
            f.unlink()
