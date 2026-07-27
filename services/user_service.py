"""User profile — the display name shown across the app.

Stored once in ``preferences.user_name`` and mirrored onto the Split
"self" contact so both stay in sync. Every read is defensive: a missing
row, a missing table or a locked DB returns "" rather than raising, so a
profile problem can never stop a page from rendering.
"""

PREF_KEY = "user_name"


def get_user_name(db):
    """Return the saved display name, or "" when it has never been set."""
    try:
        row = db.execute(
            "SELECT value FROM preferences WHERE key=?", (PREF_KEY,)).fetchone()
    except Exception:
        return ""
    if not row:
        return ""
    try:
        return (row["value"] or "").strip()
    except Exception:
        return ""


def set_user_name(db, name):
    """Persist *name* and mirror it onto the Split self-contact.

    Returns the cleaned name that was actually stored.
    """
    clean = (name or "").strip()
    db.execute("INSERT OR REPLACE INTO preferences(key, value) VALUES(?, ?)",
               (PREF_KEY, clean))
    db.commit()
    # Keep the Split "self" contact aligned. Non-critical: a brand-new DB
    # may not have the contact yet, and it gets created on first use.
    try:
        db.execute("UPDATE split_contacts SET name=? WHERE is_self=1",
                   (clean or "You",))
        db.commit()
    except Exception:
        pass
    return clean


def greeting_for(hour):
    """Morning / Afternoon / Evening for a 0-23 hour."""
    if hour < 12:
        return "Morning"
    if hour < 17:
        return "Afternoon"
    return "Evening"