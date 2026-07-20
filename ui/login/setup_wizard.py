"""Setup wizard — 4 steps: Password → 2FA (mandatory) → Accounts → Done."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QComboBox, QPushButton,
                              QStackedWidget, QFrame, QMessageBox,
                              QScrollArea)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import (QCursor, QPixmap)
import io
from ui.theme import C
from ui.widgets.metric_card import add_shadow

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

        header = QLabel("💰  Finance Manager")
        header.setStyleSheet("font-size: 22px; font-weight: 800; color: #F1F5F9; background: transparent; border: none;")
        header.setAlignment(Qt.AlignCenter)
        cl.addWidget(header)

        # Progress dots (4 steps)
        dots_row = QHBoxLayout()
        dots_row.setAlignment(Qt.AlignCenter)
        self.dots = []
        for i in range(4):
            d = QLabel("●" if i == 0 else "○")
            d.setStyleSheet(f"font-size: 16px; color: {'#818CF8' if i == 0 else 'rgba(255,255,255,0.2)'}; background: transparent; border: none;")
            dots_row.addWidget(d)
            self.dots.append(d)
        cl.addLayout(dots_row)

        self.step_title = QLabel("Create Your Password")
        self.step_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #F1F5F9; background: transparent; border: none;")
        self.step_title.setAlignment(Qt.AlignCenter)
        cl.addWidget(self.step_title)

        self.step_sub = QLabel("Secure your financial data with a strong password")
        self.step_sub.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.4); background: transparent; border: none;")
        self.step_sub.setAlignment(Qt.AlignCenter)
        self.step_sub.setWordWrap(True)
        cl.addWidget(self.step_sub)

        cl.addSpacing(8)

        # Stacked pages (4 steps)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_password())
        self.stack.addWidget(self._page_2fa())
        self.stack.addWidget(self._page_accounts())
        self.stack.addWidget(self._page_done())
        cl.addWidget(self.stack, 1)

        # Navigation
        nav = QHBoxLayout()
        nav.setSpacing(12)

        self.back_btn = QPushButton("← Back")
        self.back_btn.setStyleSheet(BTN_BACK)
        self.back_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.back_btn.clicked.connect(self._prev)
        self.back_btn.hide()
        nav.addWidget(self.back_btn)

        nav.addStretch()

        self.next_btn = QPushButton("Next  →")
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
    # PAGE 1 — 2FA (mandatory, verify code)
    # ══════════════════════════════════════════════
    def _page_2fa(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setAlignment(Qt.AlignCenter)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setFixedSize(200, 200)
        self.qr_label.setStyleSheet(
            "background: white; border: 2px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 8px;")
        lay.addWidget(self.qr_label, alignment=Qt.AlignCenter)

        sec_lbl = QLabel("Can't scan? Enter this key manually:")
        sec_lbl.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.4); background: transparent; border: none;")
        sec_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(sec_lbl)

        self.secret_label = QLabel()
        self.secret_label.setAlignment(Qt.AlignCenter)
        self.secret_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.secret_label.setStyleSheet(
            "font-family: 'Courier New', monospace; font-size: 15px; font-weight: 700; "
            "color: #818CF8; background: rgba(79,70,229,0.15); "
            "padding: 10px 16px; border-radius: 8px; border: 1px solid rgba(79,70,229,0.3); "
            "letter-spacing: 2px;")
        lay.addWidget(self.secret_label)

        lay.addSpacing(8)

        verify_lbl = QLabel("Enter the 6-digit code to verify:")
        verify_lbl.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.6); background: transparent; border: none;")
        verify_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(verify_lbl)

        self.totp_code = QLineEdit()
        self.totp_code.setPlaceholderText("000000")
        self.totp_code.setMaxLength(6)
        self.totp_code.setMinimumHeight(48)
        self.totp_code.setStyleSheet(INPUT_STYLE)
        self.totp_code.setAlignment(Qt.AlignCenter)
        self.totp_code.returnPressed.connect(self._next)
        lay.addWidget(self.totp_code)

        self.totp_err = QLabel("")
        self.totp_err.setStyleSheet("color: #EF4444; font-size: 13px; font-weight: 600; background: transparent; border: none;")
        self.totp_err.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.totp_err)

        lay.addStretch()
        return page

    # ══════════════════════════════════════════════
    # PAGE 2 — Accounts
    # ══════════════════════════════════════════════
    def _page_accounts(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)
        lay.setContentsMargins(0, 8, 0, 0)

        hint = QLabel("Bank accounts and cash only.\nCredit cards & wallets are added from their own tabs.")
        hint.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.35); background: transparent; border: none;")
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

        add_btn = QPushButton("＋  Add Account")
        add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_btn.setStyleSheet("""
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
        lay.setContentsMargins(0, 20, 0, 0)
        lay.setAlignment(Qt.AlignCenter)

        check = QLabel("✓")
        check.setStyleSheet("font-size: 72px; color: #10B981; background: transparent; border: none;")
        check.setAlignment(Qt.AlignCenter)
        lay.addWidget(check)

        self.done_title = QLabel("All Set!")
        self.done_title.setStyleSheet("font-size: 28px; font-weight: 800; color: #F1F5F9; background: transparent; border: none;")
        self.done_title.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.done_title)

        self.done_detail = QLabel("")
        self.done_detail.setStyleSheet("font-size: 14px; color: rgba(255,255,255,0.5); background: transparent; border: none;")
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
            QMessageBox.critical(self, "Missing Dependency",
                                 "2FA requires pyotp and qrcode.\n\nInstall: pip install pyotp qrcode")
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
        self.qr_label.setPixmap(pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.secret_label.setText(secret)

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
        rl.addWidget(name, 3)

        atype = QComboBox()
        atype.addItems(["CURRENT", "CASH", "WALLET"])
        atype.setMinimumHeight(40)
        atype.setStyleSheet(COMBO_STYLE)
        rl.addWidget(atype, 1)

        bal = QLineEdit()
        bal.setPlaceholderText("₹ Opening balance")
        bal.setMinimumHeight(40)
        bal.setStyleSheet(INPUT_STYLE)
        rl.addWidget(bal, 2)

        x = QPushButton("✕")
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
        name.setFocus()

    # ══════════════════════════════════════════════
    # NAVIGATION
    # ══════════════════════════════════════════════
    def _update_ui(self):
        self.stack.setCurrentIndex(self.step)

        titles = [
            ("Create Your Password", "Secure your financial data with a strong password"),
            ("Set Up Two-Factor Authentication", "Scan the QR code, then enter the code to verify"),
            ("Add Your Accounts", "Add your bank accounts and cash wallets"),
            ("All Set!", "You're ready to start managing your finances"),
        ]
        self.step_title.setText(titles[self.step][0])
        self.step_sub.setText(titles[self.step][1])

        for i, d in enumerate(self.dots):
            d.setText("●" if i == self.step else "○")
            d.setStyleSheet(f"font-size: 16px; color: {'#818CF8' if i == self.step else 'rgba(255,255,255,0.2)'}; background: transparent; border: none;")

        self.back_btn.setVisible(self.step > 0 and self.step < 4)

        btn_texts = ["Next  →", "Next  →", "Finish  ✓", "Go to Home  ✓"]
        self.next_btn.setText(btn_texts[self.step])
        self.next_btn.setStyleSheet(BTN_DONE if self.step >= 2 else BTN_NEXT)

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

        # Step 1: 2FA verify
        if self.step == 1:
            code = self.totp_code.text().strip()
            if not code:
                self.totp_err.setText("Enter the 6-digit code"); return
            if not self.sec.verify_totp(code):
                self.totp_err.setText("Invalid code. Check your authenticator app."); return
            self.totp_err.setText("")
            self.step = 2
            self._update_ui()
            return

        # Step 2: Accounts
        if self.step == 2:
            created = 0
            seen_names = set()
            for name_edit, type_combo, bal_edit in self.acct_rows:
                nm = name_edit.text().strip()
                if not nm:
                    continue
                if nm.lower() in seen_names:
                    QMessageBox.warning(self, "Duplicate", f"'{nm}' is entered twice.")
                    name_edit.setFocus(); return
                seen_names.add(nm.lower())
                if self.repo.exists(nm):
                    QMessageBox.warning(self, "Duplicate", f"Account '{nm}' already exists.")
                    name_edit.setFocus(); return
                try:
                    b = float(bal_edit.text() or "0")
                except ValueError:
                    b = 0
                self.repo.create(
                    display_name=nm, short_label=nm[:4].upper(),
                    account_type=type_combo.currentText(),
                    opening_balance=b, color_hex="#4F46E5")
                created += 1
            self.done_detail.setText(
                f"{created} account(s) created.\n\n"
                "Credit cards & wallets can be added later\n"
                "from the Cards and Settings tabs.")
            self.step = 3
            self._update_ui()
            return

        # Step 3: Done
        if self.step == 3:
            self.done.emit()
            return

    def _prev(self):
        if self.step > 0:
            self.step -= 1
            self._update_ui()
