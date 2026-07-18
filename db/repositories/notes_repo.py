"""Notes repository."""
import uuid, json
from datetime import datetime

def _rows(rows): return [dict(r) for r in rows] if rows else []
def _row(row): return dict(row) if row else None

class NotesRepo:
    def __init__(self, db): self.db = db
    def create(self, **kw):
        kw.setdefault("id", str(uuid.uuid4()))
        kw.setdefault("created_at", datetime.now().isoformat())
        if isinstance(kw.get("linked_transaction_ids"), list):
            kw["linked_transaction_ids"] = json.dumps(kw["linked_transaction_ids"])
        cols = ", ".join(kw.keys()); phs = ", ".join(["?"]*len(kw))
        self.db.execute(f"INSERT INTO notes({cols}) VALUES({phs})",
                        tuple(kw.values())); self.db.commit()
        return kw["id"]
    def list_active(self, search=None):
        if search:
            return _rows(self.db.execute(
                "SELECT * FROM notes WHERE title LIKE ? OR tags LIKE ? "
                "ORDER BY updated_at DESC", (f"%{search}%", f"%{search}%")).fetchall())
        return _rows(self.db.execute(
            "SELECT * FROM notes ORDER BY updated_at DESC, created_at DESC").fetchall())
    def get(self, nid):
        return _row(self.db.execute(
            "SELECT * FROM notes WHERE id=?", (nid,)).fetchone())
    def update(self, nid, **kw):
        kw["updated_at"] = datetime.now().isoformat()
        if isinstance(kw.get("linked_transaction_ids"), list):
            kw["linked_transaction_ids"] = json.dumps(kw["linked_transaction_ids"])
        sets = ", ".join(f"{k}=?" for k in kw)
        self.db.execute(f"UPDATE notes SET {sets} WHERE id=?",
                        (*kw.values(), nid)); self.db.commit()
    def soft_delete(self, nid):
        n = self.get(nid)
        if n:
            self.db.execute("INSERT INTO notes_trash VALUES(?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), n["id"], n["title"], n["tags"],
                 n["content"], n["linked_transaction_ids"],
                 n["created_at"], datetime.now().isoformat()))
            self.db.execute("DELETE FROM notes WHERE id=?", (nid,))
            self.db.commit()
    def list_trash(self):
        return _rows(self.db.execute(
            "SELECT * FROM notes_trash ORDER BY deleted_at DESC").fetchall())
    def restore(self, uid):
        r = self.db.execute(
            "SELECT * FROM notes_trash WHERE uuid=?", (uid,)).fetchone()
        if r:
            r = dict(r)
            self.db.execute(
                "INSERT OR IGNORE INTO notes(id,title,tags,content,"
                "linked_transaction_ids,created_at) VALUES(?,?,?,?,?,?)",
                (r["original_id"], r["title"], r["tags"], r["content"],
                 r["linked_transaction_ids"], r["created_at"]))
            self.db.execute("DELETE FROM notes_trash WHERE uuid=?", (uid,))
            self.db.commit()
    def perm_delete(self, uid):
        self.db.execute("DELETE FROM notes_trash WHERE uuid=?", (uid,))
        self.db.commit()
