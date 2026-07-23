"""Google OAuth2 for Desktop App — no external dependencies.

Flow:
1. Start local HTTP server on random port
2. Open browser to Google consent screen
3. Receive auth code via redirect
4. Exchange code for tokens
5. Get user email from Google's userinfo endpoint
"""

import json
import threading
import webbrowser
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Tuple

# Embedded credentials (fallback)
try:
    from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
except ImportError:
    GOOGLE_CLIENT_ID = ""
    GOOGLE_CLIENT_SECRET = ""


# Google's well-known endpoints
_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
_SCOPES = "openid email profile"


def get_client_id():
    """Return the embedded Client ID."""
    return GOOGLE_CLIENT_ID


def get_client_secret():
    """Return the embedded Client Secret."""
    return GOOGLE_CLIENT_SECRET


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the auth code from Google's redirect."""

    # Class-level storage for the received code
    auth_code: Optional[str] = None
    auth_error: Optional[str] = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body style='font-family:sans-serif;text-align:center;padding-top:60px;'>"
                b"<h2 style='color:#4F46E5;'>&#128274; Authorization received</h2>"
                b"<p>You can close this tab and return to Finance Manager.</p>"
                b"<p style='color:#6B7280;font-size:12px;'>The app will verify your account.</p>"
                b"</body></html>"
            )
        elif "error" in params:
            _OAuthCallbackHandler.auth_error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body style='font-family:sans-serif;text-align:center;padding-top:60px;'>"
                b"<h2 style='color:#DC2626;'>&#10008; Authorization failed</h2>"
                b"<p>Please try again from Finance Manager.</p>"
                b"</body></html>"
            )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress console logging


def _find_free_port() -> int:
    """Find a free port on localhost."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _http_post(url: str, data: dict, timeout: int = 15) -> dict:
    """POST with form-encoded data, return JSON response."""
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _http_get(url: str, access_token: str, timeout: int = 10) -> dict:
    """GET with Bearer token, return JSON response."""
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def start_oauth_flow(client_id: str, client_secret: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Run the full OAuth2 installed-app flow.

    Returns:
        (email, refresh_token, error_message)
        On success, error_message is None.
        On failure, email and refresh_token are None.
    """
    port = _find_free_port()
    redirect_uri = f"http://127.0.0.1:{port}"

    # Reset handler state
    _OAuthCallbackHandler.auth_code = None
    _OAuthCallbackHandler.auth_error = None

    # Start local server in background
    server = HTTPServer(("127.0.0.1", port), _OAuthCallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    # Build authorization URL
    auth_params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": _SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    })
    auth_url = f"{_AUTH_URL}?{auth_params}"

    # Open browser
    try:
        webbrowser.open(auth_url)
    except Exception:
        server.server_close()
        return None, None, "Could not open browser. Please visit the URL manually."

    # Wait for callback (timeout after 120 seconds)
    server_thread.join(timeout=120)
    server.server_close()

    if _OAuthCallbackHandler.auth_error:
        return None, None, f"Google denied access: {_OAuthCallbackHandler.auth_error}"

    if not _OAuthCallbackHandler.auth_code:
        return None, None, "Login timed out. No response from Google."

    # Exchange code for tokens
    try:
        token_response = _http_post(_TOKEN_URL, {
            "code": _OAuthCallbackHandler.auth_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
    except Exception as e:
        return None, None, f"Failed to exchange code: {e}"

    access_token = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")

    if not access_token:
        return None, None, "No access token received from Google."

    # Get user email
    try:
        userinfo = _http_get(_USERINFO_URL, access_token)
        email = userinfo.get("email")
    except Exception as e:
        return None, None, f"Failed to get user info: {e}"

    if not email:
        return None, None, "Could not retrieve email from Google."

    return email, refresh_token, None


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> Optional[str]:
    """Use a refresh token to get a new access token. Returns access_token or None."""
    try:
        resp = _http_post(_TOKEN_URL, {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
        return resp.get("access_token")
    except Exception:
        return None


def verify_google_user(client_id: str, client_secret: str, refresh_token: str) -> Optional[str]:
    """Verify a stored Google account by refreshing the token and fetching email.

    Returns the email address if valid, None if the token is revoked/expired.
    """
    access_token = refresh_access_token(client_id, client_secret, refresh_token)
    if not access_token:
        return None
    try:
        userinfo = _http_get(_USERINFO_URL, access_token)
        return userinfo.get("email")
    except Exception:
        return None
