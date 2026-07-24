"""Finance Manager v3 — Configuration."""
from pathlib import Path

APP_NAME = "Finance Manager"
APP_VERSION = "3.0.0"

# Paths
PROJECT_DIR = Path(__file__).resolve().parent
DB_DIR = PROJECT_DIR / "finance_data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "finance.db"
BACKUP_DIR = DB_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)
BACKUP_RETENTION = 14

# Encryption placeholder (SQLCipher-ready)
DB_KEY = ""

