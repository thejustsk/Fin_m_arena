"""Lookups repository — categories, methods, tags."""
def _rows(rows):
    return [dict(r) for r in rows] if rows else []


class LookupsRepo:
    def __init__(self, db):
        self.db = db

    def list_categories(self):
        return _rows(self.db.execute(
            "SELECT * FROM categories WHERE is_active=1 ORDER BY sort_order").fetchall())

    def list_methods(self):
        return _rows(self.db.execute(
            "SELECT * FROM payment_methods WHERE is_active=1 ORDER BY sort_order").fetchall())

    def list_pf_categories(self):
        return _rows(self.db.execute(
            "SELECT * FROM pf_categories WHERE is_active=1").fetchall())

    def list_tags(self):
        return _rows(self.db.execute(
            "SELECT * FROM note_tags WHERE is_active=1").fetchall())

    def category_exists(self, name):
        r = self.db.execute(
            "SELECT 1 FROM categories WHERE LOWER(display_name)=LOWER(?)", (name,)).fetchone()
        return r is not None

    def tag_exists(self, name):
        r = self.db.execute(
            "SELECT 1 FROM note_tags WHERE LOWER(display_name)=LOWER(?)", (name,)).fetchone()
        return r is not None

    def add_category(self, cid, name, col, pf, tax=0):
        if self.category_exists(name):
            raise ValueError(f"Category '{name}' already exists")
        self.db.execute(
            "INSERT INTO categories"
            "(category_id,display_name,color_hex,default_pf_category,"
            "tax_deductible,is_active,sort_order) VALUES(?,?,?,?,?,1,0)",
            (cid, name, col, pf, tax))
        self.db.commit()

    def add_tag(self, tid, name):
        if self.tag_exists(name):
            raise ValueError(f"Tag '{name}' already exists")
        self.db.execute(
            "INSERT INTO note_tags VALUES(?,?,1)", (tid, name))
        self.db.commit()
