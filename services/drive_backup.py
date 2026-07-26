"""Google Drive backup — uploads finance.db to a specific folder in the linked Google account.

Uses the existing OAuth credentials (Client ID, Secret, Refresh Token) stored in the app.
No external dependencies — only stdlib (urllib, json).

Backup behavior:
- Always versioned with timestamps (finance_20260724_143022.db)
- Keeps last N files in Drive (configurable, default 14)
- Reuses existing "Finance Manager Backups" folder if found
- Stores folder_id in preferences for fast access
"""

import json
import os
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional, Tuple, List
from datetime import datetime

from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_DRIVE_API = "https://www.googleapis.com/drive/v3"
_DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3"

BACKUP_FOLDER_NAME = "Finance Manager Backups"


def _get_access_token() -> Optional[str]:
    """Get a valid access token using the stored refresh token."""
    try:
        from db.connection import Database
        from config import DB_PATH
        db = Database(str(DB_PATH))
        db.connect()
        row = db.execute("SELECT google_refresh_token FROM app_security WHERE id=1").fetchone()
        db.close()
        if not row or not row["google_refresh_token"]:
            print("[DRIVE] No refresh token found")
            return None
        refresh_token = row["google_refresh_token"]
    except Exception as e:
        print(f"[DRIVE] Error reading refresh token: {e}")
        return None

    # Exchange refresh token for access token
    try:
        data = urllib.parse.urlencode({
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode()
        req = urllib.request.Request(_TOKEN_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            access_token = result.get("access_token")
            if access_token:
                print("[DRIVE] Access token obtained successfully")
            else:
                print(f"[DRIVE] No access token in response: {result}")
            return access_token
    except Exception as e:
        print(f"[DRIVE] Failed to get access token: {e}")
        return None


def _get_pref(key, default=None):
    """Read a preference value."""
    try:
        from db.connection import Database
        from config import DB_PATH
        db = Database(str(DB_PATH))
        db.connect()
        row = db.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
        db.close()
        if row and row["value"]:
            return row["value"]
    except Exception:
        pass
    return default


def _set_pref(key, value):
    """Write a preference value."""
    try:
        from db.connection import Database
        from config import DB_PATH
        db = Database(str(DB_PATH))
        db.connect()
        db.execute("INSERT OR REPLACE INTO preferences VALUES(?, ?)", (key, str(value)))
        db.commit()
        db.close()
    except Exception:
        pass


def _find_folder(access_token: str, folder_name: str) -> Optional[str]:
    """Find an existing folder by name. Returns folder ID or None."""
    query = urllib.parse.urlencode({
        "q": f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        "fields": "files(id, name)",
    })
    try:
        url = f"{_DRIVE_API}/files?{query}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {access_token}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            files = result.get("files", [])
            if files:
                return files[0]["id"]
    except urllib.error.HTTPError as e:
        print(f"[DRIVE] Find folder failed: HTTP {e.code}")
        return None
    except Exception as e:
        print(f"[DRIVE] Find folder failed: {e}")
    return None


def _create_folder(access_token: str, folder_name: str) -> Optional[str]:
    """Create a folder in Google Drive. Returns folder ID."""
    try:
        url = f"{_DRIVE_API}/files"
        body = json.dumps({
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {access_token}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            return result.get("id")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.readable() else ""
        print(f"[DRIVE] Create folder failed: HTTP {e.code} — {error_body}")
        return None
    except Exception as e:
        print(f"[DRIVE] Create folder failed: {e}")
        return None


def _get_or_create_folder(access_token: str) -> Optional[str]:
    """Find existing folder or create new one. Caches folder_id in preferences."""
    # Check cached folder_id first
    cached = _get_pref("gdrive_backup_folder_id")
    if cached:
        # Verify it still exists
        try:
            url = f"{_DRIVE_API}/files/{cached}?fields=id,name,trashed"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {access_token}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                if result.get("id") and not result.get("trashed"):
                    print(f"[DRIVE] Using cached folder: {cached}")
                    return cached
        except Exception as e:
            print(f"[DRIVE] Cached folder verification failed: {e}")

    # Search for existing folder
    folder_id = _find_folder(access_token, BACKUP_FOLDER_NAME)
    if folder_id:
        _set_pref("gdrive_backup_folder_id", folder_id)
        print(f"[DRIVE] Found existing folder: {folder_id}")
        return folder_id

    # Create new folder
    folder_id = _create_folder(access_token, BACKUP_FOLDER_NAME)
    if folder_id:
        _set_pref("gdrive_backup_folder_id", folder_id)
        print(f"[DRIVE] Created new folder: {folder_id}")
    else:
        print("[DRIVE] Failed to create folder")
    return folder_id


def _list_backup_files(access_token: str, folder_id: str) -> List[dict]:
    """List all backup files in the folder, sorted by name (newest last)."""
    query = urllib.parse.urlencode({
        "q": f"'{folder_id}' in parents and trashed=false",
        "fields": "files(id, name, createdTime, size)",
        "orderBy": "name",
        "pageSize": 100,
    })
    try:
        url = f"{_DRIVE_API}/files?{query}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {access_token}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            return result.get("files", [])
    except Exception:
        return []


def _delete_file(access_token: str, file_id: str) -> bool:
    """Delete a file from Google Drive."""
    try:
        url = f"{_DRIVE_API}/files/{file_id}"
        req = urllib.request.Request(url, method="DELETE")
        req.add_header("Authorization", f"Bearer {access_token}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True
    except Exception:
        return False


def _upload_file(access_token: str, folder_id: str, file_path: str) -> Tuple[bool, str]:
    """Upload a file to a specific Google Drive folder using resumable upload."""
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    # Step 1: Initiate resumable upload
    metadata = json.dumps({
        "name": file_name,
        "parents": [folder_id],
    })
    url = f"{_DRIVE_UPLOAD}/files?uploadType=resumable"
    req = urllib.request.Request(url, data=metadata.encode(), method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json; charset=UTF-8")
    req.add_header("X-Upload-Content-Type", "application/x-sqlite3")
    req.add_header("X-Upload-Content-Length", str(file_size))

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            upload_url = resp.headers.get("Location")
            if not upload_url:
                return False, "Failed to get upload URL from Google."
    except Exception as e:
        return False, f"Failed to initiate upload: {e}"

    # Step 2: Upload the file data
    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
        req = urllib.request.Request(upload_url, data=file_data, method="PUT")
        req.add_header("Content-Type", "application/x-sqlite3")
        req.add_header("Content-Length", str(file_size))
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            file_id = result.get("id", "")
            return True, f"Uploaded as '{file_name}' (ID: {file_id[:12]}...)"
    except Exception as e:
        return False, f"Upload failed: {e}"


def backup_to_drive(retention: int = 14) -> Tuple[bool, str]:
    """
    Backup finance.db to Google Drive with versioning.
    
    - Creates timestamped backup: finance_20260724_143022.db
    - Keeps last `retention` files, deletes oldest
    - Reuses existing folder if found
    
    Returns:
        (success: bool, message: str)
    """
    # Step 1: Get access token
    access_token = _get_access_token()
    if not access_token:
        return False, "Google account not linked or token expired. Please re-link in Settings > Security."

    # Step 2: Get or create backup folder
    folder_id = _get_or_create_folder(access_token)
    if not folder_id:
        return False, (
            "Could not access Google Drive.\n\n"
            "Most likely the Google Drive API is not enabled.\n\n"
            "Fix: Go to console.cloud.google.com > APIs & Services > "
            "Library > Search 'Google Drive API' > Enable.\n\n"
            "Then wait 1-2 minutes and try again."
        )

    # Step 3: Upload with timestamped name
    from config import DB_PATH
    db_path = str(DB_PATH)
    if not os.path.exists(db_path):
        return False, f"Database file not found: {db_path}"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"finance_{ts}.db"
    # Create a temp copy with timestamped name
    import shutil
    temp_path = os.path.join(os.path.dirname(db_path), backup_name)
    try:
        shutil.copy2(db_path, temp_path)
    except Exception as e:
        return False, f"Failed to copy database: {e}"

    success, msg = _upload_file(access_token, folder_id, temp_path)

    # Clean up temp file
    try:
        os.remove(temp_path)
    except Exception:
        pass

    if not success:
        return False, msg

    # Step 4: Clean up old backups (keep last N)
    try:
        files = _list_backup_files(access_token, folder_id)
        backup_files = [f for f in files if f["name"].startswith("finance_") and f["name"].endswith(".db")]
        if len(backup_files) > retention:
            # Sort by name (timestamps sort correctly)
            backup_files.sort(key=lambda f: f["name"])
            to_delete = backup_files[:len(backup_files) - retention]
            for f in to_delete:
                _delete_file(access_token, f["id"])
    except Exception:
        pass  # Non-critical — cleanup failed but backup succeeded

    return True, msg


def get_drive_backup_status() -> dict:
    """Get a summary of Drive backups for display.
    
    Returns dict with keys:
        - status: str (display text)
        - count: int (number of backups)
        - last_name: str (filename of latest backup)
        - folder_exists: bool (whether backup folder was found)
    """
    result = {"status": "Not connected", "count": 0, "last_name": "", "folder_exists": False}
    
    access_token = _get_access_token()
    if not access_token:
        return result

    folder_id = _get_or_create_folder(access_token)
    if not folder_id:
        result["status"] = "No backup folder"
        return result

    files = _list_backup_files(access_token, folder_id)
    # Match any .db file (backup files may be named finance_*.db or just *.db)
    backup_files = [f for f in files if f["name"].endswith(".db")]

    result["folder_exists"] = True
    result["count"] = len(backup_files)

    if not backup_files:
        result["status"] = "Folder exists, no backups yet"
    else:
        # Sort by name to get latest
        backup_files.sort(key=lambda f: f["name"])
        result["last_name"] = backup_files[-1]["name"]
        result["status"] = f"{len(backup_files)} backups | Last: {backup_files[-1]['name']}"

    return result


def check_existing_backups() -> dict:
    """Check if existing backups are found in Drive when linking Google account.
    
    Returns dict with keys:
        - found: bool
        - count: int
        - last_name: str
        - last_size: str (human-readable)
    """
    result = {"found": False, "count": 0, "last_name": "", "last_size": ""}
    
    access_token = _get_access_token()
    if not access_token:
        return result

    # Check for existing folder (don't create one)
    folder_id = _find_folder(access_token, BACKUP_FOLDER_NAME)
    if not folder_id:
        return result

    files = _list_backup_files(access_token, folder_id)
    backup_files = [f for f in files if f["name"].startswith("finance_") and f["name"].endswith(".db")]

    if not backup_files:
        return result

    result["found"] = True
    result["count"] = len(backup_files)
    result["last_name"] = backup_files[-1]["name"]

    # Get size of latest backup
    try:
        size_bytes = int(backup_files[-1].get("size", 0))
        if size_bytes > 1024 * 1024:
            result["last_size"] = f"{size_bytes / 1024 / 1024:.1f} MB"
        else:
            result["last_size"] = f"{size_bytes / 1024:.1f} KB"
    except (ValueError, TypeError):
        result["last_size"] = "unknown size"

    return result
