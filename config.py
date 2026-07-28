"""Finance Manager v3 — Configuration."""
from pathlib import Path
import sys

APP_NAME = "Finance Manager"
APP_VERSION = "3.0.0"

# ── Determine base directory ──
if getattr(sys, 'frozen', False):
    PROJECT_DIR = Path(sys.executable).resolve().parent
else:
    PROJECT_DIR = Path(__file__).resolve().parent

# Paths
DB_DIR = PROJECT_DIR / "finance_data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "finance.db"
BACKUP_DIR = DB_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)
BACKUP_RETENTION = 14

DB_KEY = ""

# ── Google OAuth ─────────────────────────────────────────────────────
# Defaults live here so `from config import GOOGLE_CLIENT_ID` can never raise
# ImportError. Real values belong in config_local.py, which is git-ignored.
GOOGLE_CLIENT_ID = ""
GOOGLE_CLIENT_SECRET = ""

# ── Local overrides ──────────────────────────────────────────────────
# config.py is tracked by git, so `git reset --hard` overwrites it and any
# credentials typed directly into this file are destroyed. That is exactly what
# happened once already. Put machine-specific secrets in config_local.py
# instead: it is git-ignored, so updates leave it alone.
#
#   config_local.py
#   ---------------
#   GOOGLE_CLIENT_ID     = "xxxx.apps.googleusercontent.com"
#   GOOGLE_CLIENT_SECRET = "GOCSPX-xxxx"
#
# Anything defined there wins over the defaults above.
try:
    from config_local import *          # noqa: F401,F403
except ImportError:
    pass


