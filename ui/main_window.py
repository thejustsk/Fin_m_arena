"""Main application window with sidebar and stacked content."""
from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget
from PyQt5.QtCore import Qt
from config import APP_NAME, APP_VERSION
from ui.sidebar import Sidebar, COLLAPSED_W


class MainWindow(QMainWindow):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self.repos = repos
        self.services = services
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1280, 800)

        # Set app icon (💸 emoji as window icon — inherited by all dialogs)
        from PyQt5.QtGui import QIcon, QPixmap, QPainter, QFont
        from PyQt5.QtCore import QSize
        _icon_px = QPixmap(64, 64)
        _icon_px.fill(Qt.transparent)
        _p = QPainter(_icon_px)
        _p.setFont(QFont("Segoe UI Emoji", 36))
        _p.drawText(_icon_px.rect(), Qt.AlignCenter, "\U0001f4b8")
        _p.end()
        self.setWindowIcon(QIcon(_icon_px))
        self._build()

    def _build(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar(self.services["balance"], self.repos)
        self.sidebar.nav.connect(self._nav)
        layout.addWidget(self.sidebar)

        # Content stack — import tabs lazily to avoid circular imports
        self.stack = QStackedWidget()
        self._tabs = {}
        self._tab_map = {
            "home": 0, "transaction_entry": 1, "database": 2,
            "audit": 3, "wealth": 4, "notes": 5, "cards": 6,
            "debit_cards": 7, "balances": 8, "settings": 9, "gmail": 10
        }

        # Import and create each tab
        from ui.tabs.home_tab import HomeTab
        from ui.tabs.transaction_entry_tab import TransactionEntryTab
        from ui.tabs.database_tab import DatabaseTab
        from ui.tabs.audit_tab import AuditTab
        from ui.tabs.wealth_tab import WealthTab
        from ui.tabs.notes_tab import NotesTab
        from ui.tabs.cards_tab import CardsTab
        from ui.tabs.debit_cards_tab import DebitCardsTab
        from ui.tabs.balances_tab import BalancesTab
        from ui.tabs.settings_tab import SettingsTab
        from ui.tabs.gmail_tab import GmailTab

        tab_classes = [
            ("home", HomeTab),
            ("transaction_entry", TransactionEntryTab),
            ("database", DatabaseTab),
            ("audit", AuditTab),
            ("wealth", WealthTab),
            ("notes", NotesTab),
            ("cards", CardsTab),
            ("debit_cards", DebitCardsTab),
            ("balances", BalancesTab),
            ("settings", SettingsTab),
            ("gmail", GmailTab),
        ]
        for key, cls in tab_classes:
            tab = cls(self.db, self.repos, self.services)
            self.stack.addWidget(tab)
            self._tabs[key] = tab

        # Connect Home tab's quick-access signal
        self._tabs["home"].go.connect(self._nav)

        # Connect Audit tab's data-changed signal to refresh all tabs
        self._tabs["audit"].set_refresh_callback(self._refresh_all_tabs)
        self._tabs["wealth"].set_refresh_callback(self._refresh_all_tabs)

        layout.addWidget(self.stack)

        # Start with sidebar collapsed
        self.sidebar.setFixedWidth(COLLAPSED_W)
        self.sidebar._expanded = False
        self.sidebar.title_label.hide()
        self.sidebar.hdr_frame.hide()
        self.sidebar.title_icon.show()
        for lbl in self.sidebar._labels:
            lbl.hide()
        from ui.sidebar import NAV_GROUPS
        for group_label, items in NAV_GROUPS:
            for key, icon, label_text in items:
                btn = self.sidebar._btns.get(key)
                if btn:
                    btn.setText(f" {icon}")

        self.sidebar.select_home()

    def _refresh_all_tabs(self):
        """Called by AuditTab when data changes — refresh all visible tabs."""
        # Refresh category icon cache (used by all tabs for transaction cards)
        from ui.tabs.database_tab import _refresh_cat_icons
        _refresh_cat_icons(self.db)
        for tab in self._tabs.values():
            if hasattr(tab, "refresh"):
                try:
                    tab.refresh()
                except Exception as e:
                    print(f"Refresh error: {e}")

    def _nav(self, key):
        idx = self._tab_map.get(key, 0)

        # Tab security check
        if not self._check_tab_security(key):
            return

        # Refresh category icon cache on every navigation
        from ui.tabs.database_tab import _refresh_cat_icons
        _refresh_cat_icons(self.db)

        self.stack.setCurrentIndex(idx)
        # Update sidebar highlight
        self.sidebar.highlight(key)
        tab = self.stack.widget(idx)
        if hasattr(tab, "refresh"):
            try:
                tab.refresh()
            except Exception as e:
                print(f"Refresh error on {key}: {e}")
        self.sidebar.update_nw()
        self.sidebar.refresh_dues()

    def _check_tab_security(self, key):
        """Check if tab requires password/TOTP verification. Returns True if allowed."""
        try:
            row = self.db.execute("SELECT * FROM tab_security WHERE tab_key=?", (key,)).fetchone()
            if not row:
                return True  # No protection
        except:
            return True

        # Tab is protected — verify identity
        sec = self.services.get("security")
        if not sec:
            return True

        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QFrame
        from ui.theme import C

        dlg = QDialog(self)
        dlg.setWindowTitle("\U0001f512  Tab Locked")
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        title = QLabel("\U0001f512  Verification Required")
        title.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        lay.addWidget(title)

        if sec.is_2fa():
            desc = QLabel("Enter your TOTP code to access this tab:")
        else:
            desc = QLabel("Enter your password to access this tab:")
        desc.setStyleSheet(f"font-size:12px;color:{C['text3']};")
        lay.addWidget(desc)

        input_field = QLineEdit()
        input_field.setMinimumHeight(40)
        if sec.is_2fa():
            input_field.setPlaceholderText("000000")
            input_field.setMaxLength(6)
        else:
            input_field.setEchoMode(QLineEdit.Password)
            input_field.setPlaceholderText("Password")
        lay.addWidget(input_field)

        err_lbl = QLabel("")
        err_lbl.setStyleSheet(f"color:{C['red']};font-size:12px;font-weight:600;")
        lay.addWidget(err_lbl)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        ok_btn = QPushButton("\U0001f513  Unlock")
        ok_btn.setObjectName("primary")
        ok_btn.setMinimumHeight(36)
        def do_verify():
            val = input_field.text().strip()
            if not val:
                err_lbl.setText("Enter the code/password.")
                return
            if sec.is_2fa():
                if sec.verify_totp(val):
                    dlg.accept()
                else:
                    err_lbl.setText("Invalid TOTP code.")
                    input_field.clear()
                    input_field.setFocus()
            else:
                if sec.verify(val):
                    dlg.accept()
                else:
                    err_lbl.setText("Invalid password.")
                    input_field.clear()
                    input_field.setFocus()
        ok_btn.clicked.connect(do_verify)
        input_field.returnPressed.connect(do_verify)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

        return dlg.exec_() == QDialog.Accepted

    def closeEvent(self, event):
        try:
            self.db.backup()
        except:
            pass
        event.accept()
