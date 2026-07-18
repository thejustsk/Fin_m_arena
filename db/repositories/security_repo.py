"""Security repository."""
from datetime import datetime

def _row(row): return dict(row) if row else None

class SecurityRepo:
    def __init__(self, db): self.db = db
    def get_app(self):
        return _row(self.db.execute("SELECT * FROM app_security LIMIT 1").fetchone())
    def set_password(self, h):
        self.db.execute("UPDATE app_security SET password_hash=?, updated_at=?",
                        (h, datetime.now().isoformat())); self.db.commit()
    def set_totp(self, secret, enabled):
        self.db.execute("UPDATE app_security SET totp_secret=?, totp_enabled=?, updated_at=?",
                        (secret, 1 if enabled else 0, datetime.now().isoformat()))
        self.db.commit()
    def set_recovery_email(self, e):
        self.db.execute("UPDATE app_security SET recovery_email=?, updated_at=?",
                        (e, datetime.now().isoformat())); self.db.commit()
    def get_period(self, pid):
        return _row(self.db.execute(
            "SELECT * FROM period_locks WHERE period_id=?", (pid,)).fetchone())
    def set_period(self, pid, locked):
        now = datetime.now().isoformat()
        ex = self.get_period(pid)
        if ex:
            if locked:
                self.db.execute("UPDATE period_locks SET is_locked=1, locked_at=? WHERE period_id=?", (now, pid))
            else:
                self.db.execute("UPDATE period_locks SET is_locked=0, unlocked_at=? WHERE period_id=?", (now, pid))
        else:
            self.db.execute("INSERT INTO period_locks VALUES(?,?,?,?)", (pid, 1, now, None))
        self.db.commit()
    def set_tab_pw(self, tk, h):
        now = datetime.now().isoformat()
        ex = self.db.execute("SELECT * FROM tab_security WHERE tab_key=?", (tk,)).fetchone()
        if ex:
            self.db.execute("UPDATE tab_security SET password_hash=?, updated_at=? WHERE tab_key=?", (h, now, tk))
        else:
            self.db.execute("INSERT INTO tab_security VALUES(?,?,0,?)", (tk, h, now))
        self.db.commit()
