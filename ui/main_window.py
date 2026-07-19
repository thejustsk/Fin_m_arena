"""Main application window with sidebar and stacked content."""
from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget
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
            "balances": 7, "settings": 8, "gmail": 9
        }

        # Import and create each tab
        from ui.tabs.home_tab import HomeTab
        from ui.tabs.transaction_entry_tab import TransactionEntryTab
        from ui.tabs.database_tab import DatabaseTab
        from ui.tabs.audit_tab import AuditTab
        from ui.tabs.wealth_tab import WealthTab
        from ui.tabs.notes_tab import NotesTab
        from ui.tabs.cards_tab import CardsTab
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

    def _nav(self, key):
        idx = self._tab_map.get(key, 0)
        self.stack.setCurrentIndex(idx)
        tab = self.stack.widget(idx)
        if hasattr(tab, "refresh"):
            try:
                tab.refresh()
            except Exception as e:
                print(f"Refresh error on {key}: {e}")
        self.sidebar.update_nw()
        self.sidebar.refresh_dues()

    def closeEvent(self, event):
        try:
            self.db.backup()
        except:
            pass
        event.accept()
