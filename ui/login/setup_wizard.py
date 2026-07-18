"""Setup wizard — 4 steps: Password → 2FA (mandatory) → Accounts → Done."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QComboBox, QPushButton,
                              QStackedWidget, QFrame, QMessageBox,
                              QScrollArea)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPixmap
import io
from ui.theme import C
from ui.widgets.metric_card import add_shadow

try:
    import pyotp, qrcode
    HAS_TOTP = True
except ImportError:
    HAS_TOTP = False

# ── Inline button styles (not QSS-dependent) ──
BTN_NEXT = """
    QPushButton {
        background: #4F46E5; color: #FFFFFF; border: none;
        border-radius: 8px; padding: 12px 28px;
        font-size: 15px; font-weight: 700;
    }
    QPushButton:hover { background: #4338CA; }
    QPushButton:pressed { background: #3730A3; }
"""
BTN_DONE = """
    QPushButton {
        background: #059669; color: #FFFFFF; border: none;
        border-radius: 8px; padding: 12px 28px;
        font-size: 15px; font-weight: 700;
    }
    QPushButton:hover { background: #047857; }
    QPushButton:pressed { background: #065F46; }
"""
BTN_BACK = """
    QPushButton {
        background: transparent; color: #667085;
        border: 1px solid #D0D5DD; border-radius: 8px;
        padding: 12px 28px; font-size: 14px; font-weight: 500;
    }
    QPushButton:hover { background: #F0F2F5; color: #101828; }
"""


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
        self.setWindowTitle("Finance Manager — First Time Setup")
        self.setMinimumSize(580, 680)
        self.setStyleSheet(f"background: {C['bg']};")

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        outer.setContentsMargins(20, 20, 20, 20)

        # ── Card container ──
        self.card = QFrame()
        self.card.setFixedSize(540, 640)
        self.card.setStyleSheet(f"""
            QFrame {{
                background: {C['surface']};
                border: 1px solid {C['border2']};
                border-radius: 20px;
            }}
        """)
        add_shadow(self.card, blur=48, y_offset=12)

        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(36, 28, 36, 28)
        cl.setSpacing(12)

        # ── Progress dots ──
        dots_row = QHBoxLayout()
        dots_row.setAlignment(Qt.AlignCenter)
        self.dots = []
        for i in range(4):  # 4 steps now
            d = QLabel("●" if i == 0 else "○")
            d.setStyleSheet(f"font-size: 18px; color: {C['accent'] if i == 0 else C['border']};")
            dots_row.addWidget(d)
            self.dots.append(d)
        cl.addLayout(dots_row)

        # ── Stacked pages ──
        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_password())
        self.stack.addWidget(self._page_2fa())
        self.stack.addWidget(self._page_accounts())
        self.stack.addWidget(self._page_done())
        cl.addWidget(self.stack, 1)

        # ── Navigation ──
        nav = QHBoxLayout()
        nav.setSpacing(12)

        self.back_btn = QPushButton("← Back")
        self.back_btn.setStyleSheet(BTN_BACK)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self._prev)
        self.back_btn.hide()
        nav.addWidget(self.back_btn)

        nav.addStretch()

        self.next_btn = QPushButton("Next  →")
        self.next_btn.setStyleSheet(BTN_NEXT)
        self.next_btn.setCursor(Qt.PointingHandCursor)
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
        lay.setSpacing(16)

        title = QLabel("Create Your Password")
        title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {C['text']};")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        lay.addSpacing(8)

        self.pw1 = QLineEdit()
        self.pw1.setEchoMode(QLineEdit.Password)
        self.pw1.setPlaceholderText("Password  (min 4 characters)")
        self.pw1.setMinimumHeight(46)
        lay.addWidget(self.pw1)

        self.pw2 = QLineEdit()
        self.pw2.setEchoMode(QLineEdit.Password)
        self.pw2.setPlaceholderText("Confirm password")
        self.pw2.setMinimumHeight(46)
        lay.addWidget(self.pw2)

        lay.addStretch()
        return page

    # ══════════════════════════════════════════════
    # PAGE 1 — 2FA (MANDATORY)
    # ══════════════════════════════════════════════
    def _page_2fa(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignCenter)

        title = QLabel("Set Up Two-Factor Authentication")
        title.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {C['text']};")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        # QR code — isolated, no text around it
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setFixedSize(220, 220)
        self.qr_label.setStyleSheet(
            "background: white; border: 2px solid #E5E7EB; border-radius: 12px; padding: 8px;")
        lay.addWidget(self.qr_label, alignment=Qt.AlignCenter)

        lay.addSpacing(6)

        # Secret key — below QR, clearly separated
        sec_lbl = QLabel("Can't scan? Enter this key manually:")
        sec_lbl.setStyleSheet(f"font-size: 12px; color: {C['text3']};")
        sec_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(sec_lbl)

        self.secret_label = QLabel()
        self.secret_label.setAlignment(Qt.AlignCenter)
        self.secret_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.secret_label.setStyleSheet(
            f"font-family: 'Courier New', monospace; font-size: 16px; font-weight: 700; "
            f"color: {C['accent']}; background: {C['accent_bg']}; "
            "padding: 10px 16px; border-radius: 8px; border: 1px solid #C7D2FE; "
            "letter-spacing: 2px;")
        lay.addWidget(self.secret_label)

        lay.addSpacing(6)

        note = QLabel("Open your authenticator app (Google Authenticator, Authy, etc.)\n"
                       "Scan the QR code or enter the key above.\n"
                       "You'll need the 6-digit code every time you log in.")
        note.setStyleSheet(f"font-size: 12px; color: {C['text3']}; line-height: 1.4;")
        note.setAlignment(Qt.AlignCenter)
        note.setWordWrap(True)
        lay.addWidget(note)

        lay.addStretch()
        return page

    # ══════════════════════════════════════════════
    # PAGE 2 — Accounts
    # ══════════════════════════════════════════════
    def _page_accounts(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        title = QLabel("Add Your Accounts")
        title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {C['text']};")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        hint = QLabel("Bank accounts and cash only.\n"
                       "Credit cards & wallets are added from their own tabs.")
        hint.setStyleSheet(f"font-size: 12px; color: {C['text3']};")
        hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(hint)

        # Scrollable area for account rows
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

        add_btn = QPushButton("＋  Add Account")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C['accent_bg']}; color: {C['accent']};
                border: 1.5px dashed {C['accent']}; border-radius: 8px;
                padding: 10px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: #D6DEFF; }}
        """)
        add_btn.clicked.connect(self._add_acct_row)
        lay.addWidget(add_btn)

        return page

    # ══════════════════════════════════════════════
    # PAGE 3 — Done
    # ══════════════════════════════════════════════
    def _page_done(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(16)
        lay.setAlignment(Qt.AlignCenter)

        check = QLabel("✓")
        check.setStyleSheet(f"font-size: 72px; color: {C['green']};")
        check.setAlignment(Qt.AlignCenter)
        lay.addWidget(check)

        self.done_title = QLabel("All Set!")
        self.done_title.setStyleSheet(f"font-size: 24px; font-weight: 800; color: {C['text']};")
        self.done_title.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.done_title)

        self.done_detail = QLabel("")
        self.done_detail.setStyleSheet(f"font-size: 14px; color: {C['text3']};")
        self.done_detail.setAlignment(Qt.AlignCenter)
        self.done_detail.setWordWrap(True)
        lay.addWidget(self.done_detail)

        lay.addStretch()
        return page

    # ══════════════════════════════════════════════
    # Generate 2FA (called when entering step 1)
    # ══════════════════════════════════════════════
    def _generate_2fa(self):
        if self._totp_secret:
            return  # already generated
        if not HAS_TOTP:
            QMessageBox.critical(self, "Missing Dependency",
                                 "2FA requires pyotp and qrcode.\n\n"
                                 "Install them:\n  pip install pyotp qrcode")
            return
        secret = pyotp.random_base32()
        self._totp_secret = secret
        # Persist to DB
        self.sec.repo.set_totp(secret, True)

        # Render QR
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
        self.qr_label.setPixmap(
            pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.secret_label.setText(secret)

    # ══════════════════════════════════════════════
    # Add account row
    # ══════════════════════════════════════════════
    def _add_acct_row(self):
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: {C['surface2']};
                border: 1px solid {C['border2']};
                border-radius: 8px;
                padding: 6px;
            }}
        """)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(8, 6, 8, 6)
        rl.setSpacing(8)

        name = QLineEdit()
        name.setPlaceholderText("Account name")
        name.setMinimumHeight(40)
        rl.addWidget(name, 3)

        atype = QComboBox()
        atype.addItems(["CURRENT", "CASH"])
        atype.setMinimumHeight(40)
        rl.addWidget(atype, 1)

        bal = QLineEdit()
        bal.setPlaceholderText("₹ Opening balance")
        bal.setMinimumHeight(40)
        rl.addWidget(bal, 2)

        x = QPushButton("✕")
        x.setFixedSize(40, 40)
        x.setCursor(Qt.PointingHandCursor)
        x.setStyleSheet(
            f"color:{C['red']}; background:transparent; border:none; font-size:18px; font-weight:bold;")
        entry = (name, atype, bal)
        x.clicked.connect(lambda: (
            self.acct_layout.removeWidget(row),
            row.deleteLater(),
            self.acct_rows.remove(entry) if entry in self.acct_rows else None
        ))
        rl.addWidget(x)

        self.acct_layout.addWidget(row)
        self.acct_rows.append(entry)

    # ══════════════════════════════════════════════
    # Navigation
    # ══════════════════════════════════════════════
    def _update_ui(self):
        self.stack.setCurrentIndex(self.step)
        for i, d in enumerate(self.dots):
            d.setText("●" if i == self.step else "○")
            d.setStyleSheet(
                f"font-size: 18px; color: {C['accent'] if i == self.step else C['border']};")
        self.back_btn.setVisible(self.step > 0)

        if self.step == 3:
            self.next_btn.setText("Go to Home  ✓")
            self.next_btn.setStyleSheet(BTN_DONE)
        else:
            self.next_btn.setText("Next  →")
            self.next_btn.setStyleSheet(BTN_NEXT)

    def _next(self):
        # ── Step 0: validate password ──
        if self.step == 0:
            pw = self.pw1.text()
            if len(pw) < 4:
                QMessageBox.warning(self, "Error", "Password must be at least 4 characters.")
                self.pw1.setFocus()
                return
            if pw != self.pw2.text():
                QMessageBox.warning(self, "Error", "Passwords do not match.")
                self.pw2.setFocus()
                return
            self.sec.set_pw(pw)
            self.step = 1
            self._generate_2fa()  # generate QR when entering 2FA page
            self._update_ui()
            return

        # ── Step 1: 2FA already set up, move on ──
        if self.step == 1:
            self.step = 2
            self._update_ui()
            return

        # ── Step 2: save accounts (with duplicate check) ──
        if self.step == 2:
            created = 0
            seen_names = set()
            for name_edit, type_combo, bal_edit in self.acct_rows:
                nm = name_edit.text().strip()
                if not nm:
                    continue
                # Check duplicates within wizard rows
                if nm.lower() in seen_names:
                    QMessageBox.warning(self, "Duplicate",
                                        f"'{nm}' is entered twice. Please remove the duplicate.")
                    name_edit.setFocus()
                    return
                seen_names.add(nm.lower())
                # Check duplicates in DB
                if self.repo.exists(nm):
                    QMessageBox.warning(self, "Duplicate",
                                        f"Account '{nm}' already exists in the database.")
                    name_edit.setFocus()
                    return
                try:
                    b = float(bal_edit.text() or "0")
                except ValueError:
                    b = 0
                self.repo.create(
                    display_name=nm,
                    short_label=nm[:4].upper(),
                    account_type=type_combo.currentText(),
                    opening_balance=b,
                    color_hex="#4F46E5"
                )
                created += 1
            self.done_detail.setText(
                f"{created} account(s) created.\n\n"
                "Credit cards & wallets can be added later\n"
                "from the Cards and Settings tabs.")
            self.step = 3
            self._update_ui()
            return

        # ── Step 3: finish ──
        if self.step == 3:
            self.done.emit()
            return

    def _prev(self):
        if self.step > 0:
            self.step -= 1
            self._update_ui()
