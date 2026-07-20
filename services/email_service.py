"""Email service — SMTP sending for verification codes."""
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class EmailService:
    def __init__(self, db):
        self.db = db

    def get_email(self):
        """Get stored user email."""
        try:
            r = self.db.execute("SELECT value FROM preferences WHERE key='user_email'").fetchone()
            if r and r["value"]:
                return r["value"]
        except:
            pass
        return ""

    def set_email(self, email):
        """Store user email."""
        self.db.execute("INSERT OR REPLACE INTO preferences VALUES('user_email', ?)", (email,))
        self.db.commit()

    def get_smtp_password(self):
        """Get stored SMTP app password."""
        try:
            r = self.db.execute("SELECT value FROM preferences WHERE key='smtp_password'").fetchone()
            if r and r["value"]:
                return r["value"]
        except:
            pass
        return ""

    def set_smtp_password(self, pw):
        """Store SMTP app password."""
        self.db.execute("INSERT OR REPLACE INTO preferences VALUES('smtp_password', ?)", (pw,))
        self.db.commit()

    def is_configured(self):
        """Check if email is configured."""
        return bool(self.get_email() and self.get_smtp_password())

    @staticmethod
    def generate_code(length=6):
        """Generate a random numeric code."""
        return ''.join(random.choices(string.digits, k=length))

    def send_code(self, to_email, code, purpose="verification"):
        """Send verification code via Gmail SMTP.
        Returns (success: bool, error_message: str).
        """
        from_email = self.get_email()
        app_password = self.get_smtp_password()

        if not from_email or not app_password:
            return False, "Email not configured. Set email and app password in Settings."

        subject = f"Finance Manager — {purpose.title()} Code"
        body = (
            f"Your {purpose} code is:\n\n"
            f"    {code}\n\n"
            f"This code expires in 10 minutes.\n"
            f"If you didn't request this, ignore this email.\n\n"
            f"— Finance Manager"
        )

        msg = MIMEMultipart()
        msg["From"] = from_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
            server.starttls()
            server.login(from_email, app_password)
            server.sendmail(from_email, to_email, msg.as_string())
            server.quit()
            return True, ""
        except smtplib.SMTPAuthenticationError:
            return False, "Gmail authentication failed. Check your app password."
        except smtplib.SMTPException as e:
            return False, f"SMTP error: {e}"
        except Exception as e:
            return False, f"Email error: {e}"

    def send_and_store(self, to_email, purpose="verification"):
        """Generate code, send email, store code in DB.
        Returns (code, success, error).
        """
        code = self.generate_code()
        success, error = self.send_code(to_email, code, purpose)
        if success:
            # Store code with expiry (10 minutes)
            from datetime import datetime, timedelta
            expires = (datetime.now() + timedelta(minutes=10)).isoformat()
            self.db.execute(
                "INSERT OR REPLACE INTO preferences VALUES('verify_code', ?)", (code,))
            self.db.execute(
                "INSERT OR REPLACE INTO preferences VALUES('verify_expires', ?)", (expires,))
            self.db.execute(
                "INSERT OR REPLACE INTO preferences VALUES('verify_email', ?)", (to_email,))
            self.db.commit()
        return code, success, error

    def verify_code(self, input_code):
        """Verify the input code against stored code.
        Returns (valid: bool, email: str).
        """
        try:
            from datetime import datetime
            r = self.db.execute("SELECT value FROM preferences WHERE key='verify_code'").fetchone()
            e = self.db.execute("SELECT value FROM preferences WHERE key='verify_expires'").fetchone()
            em = self.db.execute("SELECT value FROM preferences WHERE key='verify_email'").fetchone()

            if not r or not r["value"]:
                return False, ""

            stored_code = r["value"]
            expires = e["value"] if e else ""
            email = em["value"] if em else ""

            if expires and datetime.now().isoformat() > expires:
                return False, ""  # Expired

            if input_code.strip() == stored_code:
                # Clear used code
                self.db.execute("DELETE FROM preferences WHERE key='verify_code'")
                self.db.commit()
                return True, email

            return False, ""
        except:
            return False, ""

    def clear_verify(self):
        """Clear verification data."""
        for key in ["verify_code", "verify_expires", "verify_email"]:
            try:
                self.db.execute(f"DELETE FROM preferences WHERE key='{key}'")
            except:
                pass
        self.db.commit()
