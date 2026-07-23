"""Security service — password, 2FA, period locks."""
import hashlib

try:
    import pyotp
    HAS_TOTP = True
except ImportError:
    HAS_TOTP = False


class SecurityService:
    def __init__(self, repo):
        self.repo = repo

    @staticmethod
    def hash_pw(pw):
        return hashlib.sha256(pw.encode()).hexdigest()

    def verify(self, pw):
        s = self.repo.get_app()
        return bool(s and s["password_hash"] == self.hash_pw(pw))

    def set_pw(self, pw):
        self.repo.set_password(self.hash_pw(pw))

    def is_setup(self):
        s = self.repo.get_app()
        return bool(s and s["password_hash"])

    def is_2fa(self):
        s = self.repo.get_app()
        return bool(s and s["totp_enabled"])

    def get_secret(self):
        s = self.repo.get_app()
        return s["totp_secret"] if s else None

    def toggle_2fa(self, enabled):
        """Enable or disable 2FA WITHOUT changing the secret key."""
        self.repo.set_totp(self.get_secret(), bool(enabled))

    def setup_2fa(self):
        """Generate NEW secret key and enable 2FA. Used during setup wizard."""
        if not HAS_TOTP:
            return None
        secret = pyotp.random_base32()
        self.repo.set_totp(secret, True)
        return secret

    def verify_totp(self, code):
        if not HAS_TOTP:
            return True
        s = self.get_secret()
        return pyotp.TOTP(s).verify(code, valid_window=1) if s else True

    def is_google_linked(self):
        """Check if a Google account is linked (has client_id + email)."""
        cfg = self.repo.get_google_config()
        return bool(cfg and cfg["client_id"] and cfg["email"])

    def get_google_email(self):
        """Return the linked Google email, or None."""
        cfg = self.repo.get_google_config()
        return cfg["email"] if cfg else None

    def setup_google(self, client_id, client_secret, email, refresh_token):
        """Save Google OAuth credentials after successful linking."""
        self.repo.set_google_credentials(client_id, client_secret, email, refresh_token)

    def verify_google_login(self):
        """Verify the stored Google account is still valid. Returns email or None."""
        from ui.login.google_auth import verify_google_user
        cfg = self.repo.get_google_config()
        if not cfg or not cfg["client_id"] or not cfg["refresh_token"]:
            return None
        return verify_google_user(cfg["client_id"], cfg["client_secret"], cfg["refresh_token"])

    def unlink_google(self):
        """Remove Google account link."""
        self.repo.clear_google()

    def is_locked(self, period_id):
        p = self.repo.get_period(period_id)
        return bool(p and p["is_locked"])

    def lock(self, period_id):
        self.repo.set_period(period_id, True)

    def unlock(self, period_id):
        self.repo.set_period(period_id, False)
