"""Setup wizard — 5 steps: Password → 2FA (optional) → Google (optional) → Accounts → Done."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QComboBox, QPushButton,
                              QStackedWidget, QFrame, QMessageBox,
                              QScrollArea, QApplication, QDoubleSpinBox,
                              QDialog)
from PyQt5.QtCore import pyqtSignal, Qt, QThread
from PyQt5.QtGui import (QCursor, QPixmap)
import io
import re
from ui.theme import C
from ui.widgets.metric_card import add_shadow
from ui.uppercase import force_upper

try:
    import pyotp, qrcode
    HAS_TOTP = True
except ImportError:
    HAS_TOTP = False

INPUT_STYLE = """
    QLineEdit {
        background: rgba(255,255,255,0.07);
        border: none;
        border-bottom: 2px solid rgba(255,255,255,0.2);
        border-radius: 0px;
        padding: 12px 4px;
        font-size: 15px;
        font-weight: 500;
        color: #FFFFFF;
    }
    QLineEdit:focus {
        border-bottom: 2px solid #818CF8;
        background: rgba(255,255,255,0.10);
    }
"""
COMBO_STYLE = """
    QComboBox {
        background: rgba(255,255,255,0.07);
        border: none;
        border-bottom: 2px solid rgba(255,255,255,0.2);
        border-radius: 0px;
        padding: 12px 4px;
        font-size: 14px;
        font-weight: 500;
        color: #FFFFFF;
    }
    QComboBox:focus { border-bottom: 2px solid #818CF8; }
    QComboBox::drop-down { border: none; width: 24px; }
    QComboBox::down-arrow {
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid rgba(255,255,255,0.5);
        margin-right: 8px;
    }
    QComboBox QAbstractItemView {
        background: #1E293B; color: white;
        selection-background-color: #4F46E5;
        border: 1px solid rgba(255,255,255,0.1);
    }
"""
BTN_NEXT = """
    QPushButton {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #4F46E5, stop:1 #7C3AED);
        color: #FFFFFF; border: none; border-radius: 10px;
        padding: 14px; font-size: 16px; font-weight: 700;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #4338CA, stop:1 #6D28D9);
    }
    QPushButton:pressed { background: #3730A3; }
"""
BTN_DONE = """
    QPushButton {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #059669, stop:1 #10B981);
        color: #FFFFFF; border: none; border-radius: 10px;
        padding: 14px; font-size: 16px; font-weight: 700;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #047857, stop:1 #059669);
    }
"""
BTN_BACK = """
    QPushButton {
        background: rgba(255,255,255,0.06);
        color: rgba(255,255,255,0.5);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 14px 28px;
        font-size: 14px;
        font-weight: 500;
    }
    QPushButton:hover {
        background: rgba(255,255,255,0.12);
        color: #F1F5F9;
    }
"""
BTN_SKIP = """
    QPushButton {
        background: transparent;
        color: rgba(255,255,255,0.55);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 8px;
        padding: 10px 20px;
        font-size: 13px;
        font-weight: 600;
    }
    QPushButton:hover {
        color: rgba(255,255,255,0.8);
        border-color: rgba(255,255,255,0.4);
        background: rgba(255,255,255,0.06);
    }
"""

SPIN_STYLE = """
    QDoubleSpinBox {
        background: rgba(255,255,255,0.07);
        border: none;
        border-bottom: 2px solid rgba(255,255,255,0.2);
        border-radius: 0px;
        padding: 12px 4px;
        font-size: 15px;
        font-weight: 500;
        color: #FFFFFF;
    }
    QDoubleSpinBox:focus {
        border-bottom: 2px solid #818CF8;
        background: rgba(255,255,255,0.10);
    }
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
        background: rgba(255,255,255,0.08);
        border: none;
        width: 20px;
    }
    QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
        background: rgba(255,255,255,0.15);
    }
    QDoubleSpinBox::up-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-bottom: 5px solid rgba(255,255,255,0.5);
    }
    QDoubleSpinBox::down-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid rgba(255,255,255,0.5);
    }
"""


def _show_dark_warning(parent, title, message):
    """Styled warning dialog that matches the dark wizard theme."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(360)
    dlg.setStyleSheet("QDialog { background: #1E293B; }")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 20, 24, 20)
    lay.setSpacing(12)

    icon_lbl = QLabel("\u26a0\ufe0f")
    icon_lbl.setStyleSheet("font-size: 28px; background: transparent; border: none;")
    icon_lbl.setAlignment(Qt.AlignCenter)
    lay.addWidget(icon_lbl)

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #F1F5F9; background: transparent; border: none;")
    title_lbl.setAlignment(Qt.AlignCenter)
    lay.addWidget(title_lbl)

    msg = QLabel(message)
    msg.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.7); background: transparent; border: none;")
    msg.setAlignment(Qt.AlignCenter)
    msg.setWordWrap(True)
    lay.addWidget(msg)

    ok_btn = QPushButton("OK")
    ok_btn.setStyleSheet("""
        QPushButton {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #4F46E5, stop:1 #7C3AED);
            color: #FFFFFF; border: none; border-radius: 10px;
            padding: 12px; font-size: 14px; font-weight: 700;
        }
        QPushButton:hover {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #4338CA, stop:1 #6D28D9);
        }
    """)
    ok_btn.setCursor(QCursor(Qt.PointingHandCursor))
    ok_btn.setMinimumHeight(42)
    ok_btn.clicked.connect(dlg.accept)
    lay.addWidget(ok_btn)

    dlg.exec_()


def _auto_label(name, acct_type):
    """Auto-generate unique label: first 3 chars of name + type suffix.
    
    Examples: 'SBI Bank' + 'CURRENT' -> 'SBIC'
              'Cash' + 'CASH' -> 'CASC'
              'Paytm' + 'WALLET' -> 'PAYW'
    """
    # First 3 alphanumeric chars from name
    clean = ''.join(c for c in name if c.isalnum())[:3].upper()
    if len(clean) < 3:
        clean = clean.ljust(3, acct_type[0])
    # Type suffix: unique per type
    type_map = {"CURRENT": "B", "CASH": "H", "WALLET": "W"}
    suffix = type_map.get(acct_type, "X")
    return clean + suffix


class SetupWizard(QWidget):
    done = pyqtSignal()

    def __init__(self, sec_svc, acct_repo, parent=None):
        super().__init__(parent)
        self.sec = sec_svc
        self.repo = acct_repo
        self.step = 0
        self.acct_rows = []
        self._totp_secret = None
        self._build()

    def _build(self):
        self.setWindowTitle("Finance Manager \u2014 First Time Setup")
        self.setMinimumSize(580, 720)
        self.setStyleSheet("background: #0B1120;")

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        outer.setContentsMargins(20, 20, 20, 20)

        self.card = QFrame()
        self.card.setFixedSize(520, 680)
        self.card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:0.3,y2:1,
                    stop:0 #1E293B, stop:1 #0F172A);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 24px;
            }
        """)
        add_shadow(self.card, blur=48, y_offset=12)

        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(36, 28, 36, 28)
        cl.setSpacing(16)

        header = QLabel("\U0001f4b0  Finance Manager")
        header.setStyleSheet("font-size: 22px; font-weight: 800; color: #F1F5F9; background: transparent; border: none;")
        header.setAlignment(Qt.AlignCenter)
        cl.addWidget(header)

        # Progress dots (5 steps)
        dots_row = QHBoxLayout()
        dots_row.setAlignment(Qt.AlignCenter)
        self.dots = []
        for i in range(5):
            d = QLabel("\u25cf" if i == 0 else "\u25cb")
            d.setStyleSheet(f"font-size: 14px; color: {'#818CF8' if i == 0 else 'rgba(255,255,255,0.4)'}; background: transparent; border: none;")
            dots_row.addWidget(d)
            self.dots.append(d)
        cl.addLayout(dots_row)

        self.step_title = QLabel("Create Your Password")
        self.step_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #F1F5F9; background: transparent; border: none;")
        self.step_title.setAlignment(Qt.AlignCenter)
        cl.addWidget(self.step_title)

        self.step_sub = QLabel("Secure your financial data with a strong password")
        self.step_sub.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.6); background: transparent; border: none;")
        self.step_sub.setAlignment(Qt.AlignCenter)
        self.step_sub.setWordWrap(True)
        cl.addWidget(self.step_sub)

        cl.addSpacing(8)

        # Stacked pages (5 steps)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_password())    # 0
        self.stack.addWidget(self._page_2fa())          # 1
        self.stack.addWidget(self._page_google())       # 2
        self.stack.addWidget(self._page_accounts())     # 3
        self.stack.addWidget(self._page_done())         # 4
        cl.addWidget(self.stack, 1)

        # Navigation
        nav = QHBoxLayout()
        nav.setSpacing(12)

        self.back_btn = QPushButton("\u2190 Back")
        self.back_btn.setStyleSheet(BTN_BACK)
        self.back_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.back_btn.clicked.connect(self._prev)
        self.back_btn.hide()
        nav.addWidget(self.back_btn)

        nav.addStretch()

        self.skip_btn = QPushButton("Skip for now \u2192")
        self.skip_btn.setStyleSheet(BTN_SKIP)
        self.skip_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.skip_btn.clicked.connect(self._skip_step)
        self.skip_btn.hide()
        nav.addWidget(self.skip_btn)

        self.next_btn = QPushButton("Next  \u2192")
        self.next_btn.setStyleSheet(BTN_NEXT)
        self.next_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.next_btn.setMinimumHeight(48)
        self.next_btn.setMinimumWidth(160)
        self.next_btn.clicked.connect(self._next)
        nav.addWidget(self.next_btn)

        cl.addLayout(nav)
        outer.addWidget(self.card)

    # ══════════════════════════════════════════════
    # PAGE 0 — Password
    # ══════════════════════════════════════════════
    def _page_password(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(20)
        lay.setContentsMargins(0, 8, 0, 0)

        self.pw1 = QLineEdit()
        self.pw1.setEchoMode(QLineEdit.Password)
        self.pw1.setPlaceholderText("Password (min 4 characters)")
        self.pw1.setMinimumHeight(48)
        self.pw1.setStyleSheet(INPUT_STYLE)
        self.pw1.returnPressed.connect(self._next)
        lay.addWidget(self.pw1)

        self.pw2 = QLineEdit()
        self.pw2.setEchoMode(QLineEdit.Password)
        self.pw2.setPlaceholderText("Confirm password")
        self.pw2.setMinimumHeight(48)
        self.pw2.setStyleSheet(INPUT_STYLE)
        self.pw2.returnPressed.connect(self._next)
        lay.addWidget(self.pw2)

        self.pw_err = QLabel("")
        self.pw_err.setStyleSheet("color: #EF4444; font-size: 13px; font-weight: 600; background: transparent; border: none;")
        self.pw_err.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.pw_err)

        lay.addStretch()
        return page

    # ══════════════════════════════════════════════
    # PAGE 1 — 2FA (OPTIONAL)
    # ══════════════════════════════════════════════
    def _page_2fa(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(6)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)

        # Recommendation note
        rec = QLabel("\U0001f6e1\ufe0f  Recommended for security")
        rec.setStyleSheet("font-size: 11px; color: #F59E0B; font-weight: 700; background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.2); border-radius: 6px; padding: 4px 12px;")
        rec.setAlignment(Qt.AlignCenter)
        rec.setFixedHeight(26)
        lay.addWidget(rec)

        # QR Code (centered)
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setFixedSize(110, 110)
        self.qr_label.setStyleSheet(
            "background: white; border: 2px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 3px;")
        lay.addWidget(self.qr_label, alignment=Qt.AlignCenter)

        # Manual Key (below QR, centered)
        key_hint = QLabel("\U0001f511  Manual Key")
        key_hint.setStyleSheet("font-size: 10px; color: rgba(255,255,255,0.6); background: transparent; border: none; font-weight: 700;")
        key_hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(key_hint)

        self.secret_label = QLabel()
        self.secret_label.setAlignment(Qt.AlignCenter)
        self.secret_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.secret_label.setStyleSheet(
            "font-family: 'Courier New', monospace; font-size: 12px; font-weight: 700; "
            "color: #818CF8; background: rgba(79,70,229,0.15); "
            "padding: 6px 14px; border-radius: 8px; border: 1px solid rgba(79,70,229,0.3); "
            "letter-spacing: 2px;")
        lay.addWidget(self.secret_label, alignment=Qt.AlignCenter)

        lay.addSpacing(4)

        # Verification code (below key)
        verify_lbl = QLabel("Enter the 6-digit code to verify:")
        verify_lbl.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.7); background: transparent; border: none;")
        verify_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(verify_lbl)

        self.totp_code = QLineEdit()
        self.totp_code.setPlaceholderText("000000")
        self.totp_code.setMaxLength(6)
        self.totp_code.setFixedWidth(160)
        self.totp_code.setMinimumHeight(38)
        self.totp_code.setStyleSheet(INPUT_STYLE)
        self.totp_code.setAlignment(Qt.AlignCenter)
        self.totp_code.returnPressed.connect(self._next)
        lay.addWidget(self.totp_code, alignment=Qt.AlignCenter)

        self.totp_err = QLabel("")
        self.totp_err.setStyleSheet("color: #EF4444; font-size: 12px; font-weight: 600; background: transparent; border: none;")
        self.totp_err.setAlignment(Qt.AlignCenter)
        self.totp_err.setFixedHeight(18)
        lay.addWidget(self.totp_err)

        note = QLabel("You can enable 2FA later in Settings \u2192 Security")
        note.setStyleSheet("font-size: 10px; color: rgba(255,255,255,0.45); background: transparent; border: none;")
        note.setAlignment(Qt.AlignCenter)
        lay.addWidget(note)

        lay.addStretch()
        return page

    # ══════════════════════════════════════════════
    # PAGE 2 — GOOGLE (OPTIONAL)
    # ══════════════════════════════════════════════
    def _page_google(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(16)
        lay.setContentsMargins(0, 20, 0, 0)
        lay.setAlignment(Qt.AlignCenter)

        icon = QLabel("\U0001f4e7")
        icon.setStyleSheet("font-size: 48px; background: transparent; border: none;")
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)

        desc = QLabel(
            "Link your Google account for easy sign-in.\n\n"
            "If you ever forget your password or lose your\n"
            "authenticator app, you can still log in with Google.\n\n"
            "This is for login verification only \u2014\n"
            "no financial data is shared with Google."
        )
        desc.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.65); background: transparent; border: none; line-height: 1.4;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        lay.addWidget(desc)

        self.google_link_btn_wizard = QPushButton("\U0001f517  Sign in with Google")
        self.google_link_btn_wizard.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.07);
                color: #E2E8F0; border: 1px solid rgba(255,255,255,0.15);
                border-radius: 10px; padding: 14px 24px;
                font-size: 15px; font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.12);
                border-color: rgba(255,255,255,0.3);
            }
        """)
        self.google_link_btn_wizard.setMinimumHeight(48)
        self.google_link_btn_wizard.setCursor(QCursor(Qt.PointingHandCursor))
        self.google_link_btn_wizard.clicked.connect(self._wizard_google_link)
        lay.addWidget(self.google_link_btn_wizard, alignment=Qt.AlignCenter)

        self.google_status_wizard = QLabel("")
        self.google_status_wizard.setStyleSheet("font-size: 12px; font-weight: 600; background: transparent; border: none;")
        self.google_status_wizard.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.google_status_wizard)

        note = QLabel("You can link Google later in Settings \u2192 Security")
        note.setStyleSheet("font-size: 10px; color: rgba(255,255,255,0.45); background: transparent; border: none;")
        note.setAlignment(Qt.AlignCenter)
        lay.addWidget(note)

        lay.addStretch()
        return page

    # ══════════════════════════════════════════════
    # PAGE 3 — Accounts
    # ══════════════════════════════════════════════
    def _page_accounts(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)
        lay.setContentsMargins(0, 8, 0, 0)

        hint = QLabel("Bank accounts and cash only.\nCredit cards & wallets are added from their own tabs.\nLabels are auto-generated from name + type.")
        hint.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.55); background: transparent; border: none;")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        lay.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll_inner = QWidget()
        scroll_inner.setStyleSheet("background: transparent;")
        self.acct_layout = QVBoxLayout(scroll_inner)
        self.acct_layout.setSpacing(8)
        scroll.setWidget(scroll_inner)
        lay.addWidget(scroll, 1)

        self.add_acct_btn = QPushButton("\uff0b  Add Account")
        self.add_acct_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.add_acct_btn.setStyleSheet("""
            QPushButton {
                background: rgba(79,70,229,0.12);
                color: #818CF8;
                border: 1.5px dashed rgba(79,70,229,0.4);
                border-radius: 10px;
                padding: 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: rgba(79,70,229,0.2); }
        """)
        self.add_acct_btn.clicked.connect(self._add_acct_row)
        lay.addWidget(self.add_acct_btn)

        return page

    # ══════════════════════════════════════════════
    # PAGE 4 — Done
    # ══════════════════════════════════════════════
    def _page_done(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(16)
        lay.setContentsMargins(0, 20, 0, 0)
        lay.setAlignment(Qt.AlignCenter)

        check = QLabel("\u2713")
        check.setStyleSheet("font-size: 72px; color: #10B981; background: transparent; border: none;")
        check.setAlignment(Qt.AlignCenter)
        lay.addWidget(check)

        self.done_title = QLabel("All Set!")
        self.done_title.setStyleSheet("font-size: 28px; font-weight: 800; color: #F1F5F9; background: transparent; border: none;")
        self.done_title.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.done_title)

        self.done_detail = QLabel("")
        self.done_detail.setStyleSheet("font-size: 14px; color: rgba(255,255,255,0.65); background: transparent; border: none;")
        self.done_detail.setAlignment(Qt.AlignCenter)
        self.done_detail.setWordWrap(True)
        lay.addWidget(self.done_detail)

        lay.addStretch()
        return page

    # ══════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════
    def _generate_2fa(self):
        if self._totp_secret:
            return
        if not HAS_TOTP:
            # TOTP not available, skip automatically
            return
        secret = pyotp.random_base32()
        self._totp_secret = secret
        self.sec.repo.set_totp(secret, True)

        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri("FinanceManager", issuer_name="FinanceManager")
        qr = qrcode.QRCode(version=1, box_size=6, border=2)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        pixmap = QPixmap()
        pixmap.loadFromData(buf.read())
        self.qr_label.setPixmap(pixmap.scaled(110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.secret_label.setText(secret)

    def _wizard_google_link(self):
        """Link Google account from setup wizard."""
        from ui.login.google_auth import start_oauth_flow, get_client_id, get_client_secret
        cid = get_client_id()
        csec = get_client_secret()
        if not cid or not csec:
            self.google_status_wizard.setText("Google credentials not configured.")
            self.google_status_wizard.setStyleSheet("font-size: 12px; color: #EF4444; font-weight: 600; background: transparent; border: none;")
            return

        self.google_link_btn_wizard.setEnabled(False)
        self.google_link_btn_wizard.setText("Opening browser...")

        # Show modal auth dialog
        auth_dlg = QDialog(self)
        auth_dlg.setWindowTitle("Authenticating")
        auth_dlg.setFixedSize(340, 160)
        auth_dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        auth_dlg.setModal(True)
        auth_dlg.setStyleSheet("QDialog { background: #1E293B; border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; }")
        al = QVBoxLayout(auth_dlg)
        al.setContentsMargins(24, 20, 24, 20)
        al.setSpacing(10)

        icon_lbl = QLabel("\U0001f510")
        icon_lbl.setStyleSheet("font-size: 28px; background: transparent; border: none;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        al.addWidget(icon_lbl)

        auth_msg = QLabel("Waiting for Google sign-in...\nPlease complete in your browser.")
        auth_msg.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 13px; font-weight: 600; background: transparent; border: none;")
        auth_msg.setAlignment(Qt.AlignCenter)
        auth_msg.setWordWrap(True)
        al.addWidget(auth_msg)

        class _OAuthWorker(QThread):
            finished = pyqtSignal(str, str, str)

            def __init__(self, _cid, _csec):
                super().__init__()
                self._cid = _cid
                self._csec = _csec

            def run(self):
                try:
                    _email, _token, _err = start_oauth_flow(self._cid, self._csec)
                    self.finished.emit(_email or "", _token or "", _err or "")
                except Exception as e:
                    self.finished.emit("", "", str(e))

        def _on_done(email, refresh_token, error):
            auth_dlg.accept()
            if error:
                self.google_status_wizard.setText(f"Failed: {error}")
                self.google_status_wizard.setStyleSheet("font-size: 12px; color: #EF4444; font-weight: 600; background: transparent; border: none;")
                self.google_link_btn_wizard.setEnabled(True)
                self.google_link_btn_wizard.setText("\U0001f517  Sign in with Google")
                return
            self.sec.setup_google(cid, csec, email, refresh_token)
            self.google_status_wizard.setText(f"\u2713 Linked: {email}")
            self.google_status_wizard.setStyleSheet("font-size: 12px; color: #10B981; font-weight: 700; background: transparent; border: none;")
            self.google_link_btn_wizard.setText("Linked \u2713")
            self.google_link_btn_wizard.setEnabled(False)

        worker = _OAuthWorker(cid, csec)
        worker.finished.connect(_on_done)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "QPushButton { background: transparent; color: rgba(255,255,255,0.5); "
            "border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; "
            "padding: 6px 16px; font-size: 12px; }"
            "QPushButton:hover { color: rgba(255,255,255,0.8); }")
        cancel_btn.setCursor(QCursor(Qt.PointingHandCursor))
        def _cancel():
            worker.terminate()
            auth_dlg.reject()
            self.google_link_btn_wizard.setEnabled(True)
            self.google_link_btn_wizard.setText("\U0001f517  Sign in with Google")
        cancel_btn.clicked.connect(_cancel)
        al.addWidget(cancel_btn, alignment=Qt.AlignCenter)

        worker.start()
        auth_dlg.exec_()

        if not worker.isFinished():
            worker.terminate()
            self.google_link_btn_wizard.setEnabled(True)
            self.google_link_btn_wizard.setText("\U0001f517  Sign in with Google")

    def _add_acct_row(self):
        row = QFrame()
        row.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
            }
        """)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(10, 8, 10, 8)
        rl.setSpacing(8)

        name = QLineEdit()
        name.setPlaceholderText("Account name")
        name.setMinimumHeight(40)
        name.setStyleSheet(INPUT_STYLE)
        force_upper(name)
        rl.addWidget(name, 3)

        atype = QComboBox()
        atype.addItems(["CURRENT", "CASH", "WALLET"])
        atype.setMinimumHeight(40)
        atype.setStyleSheet(COMBO_STYLE)
        rl.addWidget(atype, 1)

        bal = QDoubleSpinBox()
        bal.setPrefix("\u20b9 ")
        bal.setRange(-99999999, 99999999)
        bal.setDecimals(2)
        bal.setValue(0)
        bal.setMinimumHeight(40)
        bal.setStyleSheet(SPIN_STYLE)
        rl.addWidget(bal, 2)

        x = QPushButton("\u2715")
        x.setFixedSize(36, 36)
        x.setCursor(QCursor(Qt.PointingHandCursor))
        x.setStyleSheet("color:#EF4444; background:rgba(239,68,68,0.1); border:none; border-radius:8px; font-size:16px; font-weight:bold;")
        entry = (name, atype, bal)
        x.clicked.connect(lambda: (
            self.acct_layout.removeWidget(row),
            row.deleteLater(),
            self.acct_rows.remove(entry) if entry in self.acct_rows else None
        ))
        rl.addWidget(x)

        self.acct_layout.addWidget(row)
        self.acct_rows.append(entry)

        # Keyboard navigation: Enter on name -> type combo
        name.returnPressed.connect(lambda: atype.setFocus())
        atype.activated.connect(lambda: bal.setFocus())

        name.setFocus()

    # ══════════════════════════════════════════════
    # NAVIGATION
    # ══════════════════════════════════════════════
    def _update_ui(self):
        self.stack.setCurrentIndex(self.step)

        titles = [
            ("Create Your Password", "Secure your financial data with a strong password"),
            ("Two-Factor Authentication", "Scan the QR code with Google Authenticator or similar app"),
            ("Sign in with Google", "Optional \u2014 alternative login if you forget your password"),
            ("Add Your Accounts", "Add your bank accounts and cash wallets"),
            ("All Set!", "You're ready to start managing your finances"),
        ]
        self.step_title.setText(titles[self.step][0])
        self.step_sub.setText(titles[self.step][1])

        for i, d in enumerate(self.dots):
            d.setText("\u25cf" if i == self.step else "\u25cb")
            d.setStyleSheet(f"font-size: 14px; color: {'#818CF8' if i == self.step else 'rgba(255,255,255,0.4)'}; background: transparent; border: none;")

        self.back_btn.setVisible(self.step > 0 and self.step < 5)
        # Show skip button on optional steps (1=2FA, 2=Google)
        self.skip_btn.setVisible(self.step in (1, 2))

        btn_texts = ["Next  \u2192", "Next  \u2192", "Next  \u2192", "Finish  \u2713", "Go to Home  \u2713"]
        self.next_btn.setText(btn_texts[self.step])
        self.next_btn.setStyleSheet(BTN_DONE if self.step >= 3 else BTN_NEXT)

    def _skip_step(self):
        """Skip the current optional step (2FA or Google)."""
        if self.step == 1:
            self.sec.toggle_2fa(False)
            self._totp_secret = None
            self.step = 2
        elif self.step == 2:
            self.step = 3
        self._update_ui()

    def _next(self):
        # Step 0: Password
        if self.step == 0:
            pw = self.pw1.text()
            if len(pw) < 4:
                self.pw_err.setText("Password must be at least 4 characters."); return
            if pw != self.pw2.text():
                self.pw_err.setText("Passwords do not match."); return
            self.pw_err.setText("")
            self.sec.set_pw(pw)
            self.step = 1
            self._generate_2fa()
            self._update_ui()
            return

        # Step 1: 2FA verify (optional — can also skip via button)
        if self.step == 1:
            code = self.totp_code.text().strip()
            if not code:
                self.totp_err.setText("Enter the 6-digit code, or click 'Skip for now'")
                return
            if not self.sec.verify_totp(code):
                self.totp_err.setText("Invalid code. Check your authenticator app."); return
            self.totp_err.setText("")
            self.step = 2
            self._update_ui()
            return

        # Step 2: Google (optional — can also skip via button)
        if self.step == 2:
            self.step = 3
            self._update_ui()
            return

        # Step 3: Accounts (at least 1 required)
        if self.step == 3:
            created = 0
            seen_names = set()
            # Count non-empty rows first
            non_empty = [e for e in self.acct_rows if e[0].text().strip()]
            if not non_empty:
                _show_dark_warning(self, "Required", "Please add at least one account to continue.")
                self._add_acct_row()
                return
            for name_edit, type_combo, bal_spin in self.acct_rows:
                nm = name_edit.text().strip()
                if not nm:
                    continue
                if nm.lower() in seen_names:
                    _show_dark_warning(self, "Duplicate", f"'{nm}' is entered twice.")
                    name_edit.setFocus(); return
                seen_names.add(nm.lower())
                if self.repo.exists(nm):
                    _show_dark_warning(self, "Duplicate", f"Account '{nm}' already exists.")
                    name_edit.setFocus(); return
                b = bal_spin.value()
                self.repo.create(
                    display_name=nm, short_label=_auto_label(nm, type_combo.currentText()),
                    account_type=type_combo.currentText(),
                    opening_balance=b, color_hex="#4F46E5")
                created += 1

            # Build summary
            summary_parts = [f"{created} account(s) created."]
            if self.sec.is_2fa():
                summary_parts.append("\u2713 Two-Factor Authentication enabled")
            else:
                summary_parts.append("\u25cb 2FA not set \u2014 enable in Settings \u2192 Security")
            if self.sec.is_google_linked():
                summary_parts.append(f"\u2713 Google: {self.sec.get_google_email()}")
            else:
                summary_parts.append("\u25cb Google not linked \u2014 link in Settings \u2192 Security")

            self.done_detail.setText(
                "\n".join(summary_parts) + "\n\n"
                "Credit cards & wallets can be added later\n"
                "from the Cards and Settings tabs.")
            self.step = 4
            self._update_ui()
            return

        # Step 4: Done
        if self.step == 4:
            self.done.emit()
            return

    def _prev(self):
        if self.step > 0:
            self.step -= 1
            self._update_ui()
