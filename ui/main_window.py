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

        # Set app icon from file (inherited by all dialogs)
        from PyQt5.QtGui import QIcon
        from pathlib import Path
        _icon_path = Path(__file__).resolve().parent.parent / "app_icon.png"
        if _icon_path.exists():
            self.setWindowIcon(QIcon(str(_icon_path)))
        else:
            # Fallback to emoji icon
            from PyQt5.QtGui import QPixmap, QPainter, QFont
            _icon_px = QPixmap(64, 64)
            _icon_px.fill(Qt.transparent)
            _p = QPainter(_icon_px)
            _p.setFont(QFont("Segoe UI Emoji", 36))
            _p.drawText(_icon_px.rect(), Qt.AlignCenter, "\U0001f4b8")
            _p.end()
            self.setWindowIcon(QIcon(_icon_px))
        self._build()

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_native_title_bar()

    def _apply_native_title_bar(self):
        """Reapply native title-bar colours after an in-app theme switch."""
        from ui.window_chrome import apply_native_title_bar
        apply_native_title_bar(self)

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
            "audit": 3, "budgets": 4, "wealth": 5, "notes": 6, "cards": 7,
            "debit_cards": 8, "balances": 9, "settings": 10, "gmail": 11,
            "split": 12
        }

        # Import and create each tab
        from ui.tabs.home_tab import HomeTab
        from ui.tabs.transaction_entry_tab import TransactionEntryTab
        from ui.tabs.database_tab import DatabaseTab
        from ui.tabs.audit_tab import AuditTab
        from ui.tabs.budget_tab import BudgetTab
        from ui.tabs.wealth_tab import WealthTab
        from ui.tabs.notes_tab import NotesTab
        from ui.tabs.cards_tab import CardsTab
        from ui.tabs.debit_cards_tab import DebitCardsTab
        from ui.tabs.balances_tab import BalancesTab
        from ui.tabs.settings_tab import SettingsTab
        from ui.tabs.gmail_tab import GmailTab
        from ui.tabs.split_tab import SplitTab

        tab_classes = [
            ("home", HomeTab),
            ("transaction_entry", TransactionEntryTab),
            ("database", DatabaseTab),
            ("audit", AuditTab),
            ("budgets", BudgetTab),
            ("wealth", WealthTab),
            ("notes", NotesTab),
            ("cards", CardsTab),
            ("debit_cards", DebitCardsTab),
            ("balances", BalancesTab),
            ("settings", SettingsTab),
            ("gmail", GmailTab),
            ("split", SplitTab),
        ]
        self._tab_classes = tab_classes
        for key, cls in tab_classes:
            tab = cls(self.db, self.repos, self.services)
            self.stack.addWidget(tab)
            self._tabs[key] = tab

        self._wire_tabs()

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
        self._install_shortcuts()

    # ══════════════════════════════════════════════════════════
    #  Wiring shared by the first build and any theme rebuild
    # ══════════════════════════════════════════════════════════
    def _wire_tabs(self):
        """Reconnect cross-tab signals. Safe to call again after a rebuild."""
        home = self._tabs.get("home")
        if home is not None:
            try:
                home.go.connect(self._nav)
            except Exception:
                pass
        for key in ("audit", "wealth"):
            tab = self._tabs.get(key)
            if tab is not None and hasattr(tab, "set_refresh_callback"):
                try:
                    tab.set_refresh_callback(self._refresh_all_tabs)
                except Exception:
                    pass

    # ══════════════════════════════════════════════════════════
    #  Theme
    # ══════════════════════════════════════════════════════════
    def toggle_theme(self):
        from ui.theme import active_theme
        self.set_theme("light" if active_theme() == "dark" else "dark")

    def set_theme(self, name):
        """Swap palette and rebuild every tab so inline styles pick it up.

        Inline setStyleSheet() strings were baked with the old colours, so a
        global stylesheet swap alone is not enough — the widget tree has to
        be recreated. Done behind setUpdatesEnabled(False) to avoid a visible
        repaint storm.
        """
        from ui.theme import apply_theme, save_theme_pref, active_theme
        from PyQt5.QtWidgets import QApplication

        if name == active_theme():
            return
        current_key = self._current_key()
        app = QApplication.instance()
        old_tabs = []

        self.setUpdatesEnabled(False)
        try:
            # Remove old pages before changing the application stylesheet so
            # Qt does not polish their entire (often large) widget trees.
            # Destruction itself is deliberately staged after the themed page
            # is visible; forcing every deferred deletion here freezes the UI.
            old_tabs = list(self._tabs.values())
            self._tabs = {}
            self._stale_tabs = {k for k, _ in self._tab_classes}
            while self.stack.count():
                w = self.stack.widget(0)
                self.stack.removeWidget(w)
                w.setParent(None)

            apply_theme(name, app)
            save_theme_pref(self.db, name)

            # Category icon cache holds themed colours — drop it.
            try:
                from ui.tabs.database_tab import _refresh_cat_icons
                _refresh_cat_icons(self.db)
            except Exception:
                pass

            # Placeholders keep _tab_map indices valid until each tab is real.
            # Rebuilding all twelve eagerly costs seconds; _nav() materialises
            # each one the first time you open it instead.
            self._placeholders = {}
            for key, _cls in self._tab_classes:
                ph = QWidget()
                ph.setObjectName("central")
                self.stack.addWidget(ph)
                self._placeholders[key] = ph

            # Sidebar owns its own inline styles too.
            self._rebuild_sidebar()
            self._ensure_tab(current_key)
            self._wire_tabs()
        finally:
            self.setUpdatesEnabled(True)

        self._nav(current_key)
        self._apply_native_title_bar()
        try:
            from ui.widgets.toast import Toast
            Toast.show_message(self, f"{name.title()} theme applied", kind="success")
        except Exception:
            pass
        self._dispose_tabs_gradually(old_tabs)

    def _dispose_tabs_gradually(self, tabs):
        """Delete detached pre-theme pages in small event-loop slices.

        Wealth and Notes can contain thousands of child widgets. Releasing all
        of them synchronously makes a theme switch feel frozen even though the
        new themed page is already ready.
        """
        if not tabs:
            return
        tab = tabs.pop()
        tab.deleteLater()
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(20, lambda: self._dispose_tabs_gradually(tabs))

    def _ensure_tab(self, key):
        """Build a tab on demand after a theme switch, swapping out its
        placeholder. No-op once the tab is live."""
        stale = getattr(self, "_stale_tabs", None)
        if not stale or key not in stale:
            return self._tabs.get(key)
        cls = dict(self._tab_classes).get(key)
        if cls is None:
            stale.discard(key)
            return None
        idx = self._tab_map.get(key)
        tab = cls(self.db, self.repos, self.services)
        ph = getattr(self, "_placeholders", {}).get(key)
        if ph is not None:
            self.stack.insertWidget(idx, tab)
            self.stack.removeWidget(ph)
            ph.setParent(None)
            ph.deleteLater()
            self._placeholders.pop(key, None)
        else:
            self.stack.insertWidget(idx, tab)
        self._tabs[key] = tab
        stale.discard(key)
        # Re-attach signals for the tabs that publish them.
        if key == "home":
            try:
                tab.go.connect(self._nav)
            except Exception:
                pass
        elif key in ("audit", "wealth") and hasattr(tab, "set_refresh_callback"):
            try:
                tab.set_refresh_callback(self._refresh_all_tabs)
            except Exception:
                pass
        return tab

    def _current_key(self):
        idx = self.stack.currentIndex()
        for k, v in self._tab_map.items():
            if v == idx:
                return k
        return "home"

    def _rebuild_sidebar(self):
        """Recreate the sidebar against the new palette, preserving state."""
        from ui.sidebar import Sidebar, COLLAPSED_W, EXPANDED_W, NAV_GROUPS
        was_expanded = getattr(self.sidebar, "_expanded", False)
        old = self.sidebar
        layout = self.centralWidget().layout()

        new = Sidebar(self.services["balance"], self.repos)
        new.nav.connect(self._nav)
        layout.insertWidget(0, new)
        old.setParent(None)
        old.deleteLater()
        self.sidebar = new

        if not was_expanded:
            new.setFixedWidth(COLLAPSED_W)
            new._expanded = False
            new.title_label.hide()
            new.hdr_frame.hide()
            new.title_icon.show()
            for lbl in new._labels:
                lbl.hide()
            for _group, items in NAV_GROUPS:
                for key, icon, _label in items:
                    btn = new._btns.get(key)
                    if btn:
                        btn.setText(f" {icon}")
        else:
            new.setFixedWidth(EXPANDED_W)
            new._expanded = True

    # ══════════════════════════════════════════════════════════
    #  Shortcuts
    # ══════════════════════════════════════════════════════════
    def _install_shortcuts(self):
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence
        self._sc_palette = QShortcut(QKeySequence("Ctrl+K"), self)
        self._sc_palette.activated.connect(self.open_command_palette)
        self._sc_theme = QShortcut(QKeySequence("Ctrl+Shift+L"), self)
        self._sc_theme.activated.connect(self.toggle_theme)

    def _palette_entries(self):
        """Build the Ctrl+K list: every tab, plus a few global actions."""
        from ui.sidebar import NAV_GROUPS
        from ui.theme import active_theme
        entries = []
        for group, items in NAV_GROUPS:
            for key, icon, label in items:
                entries.append(
                    (icon, label, group.title() if group else "",
                     lambda k=key: self._nav(k)))
        other = "Light" if active_theme() == "dark" else "Dark"
        entries.append(("\U0001f317", f"Switch to {other} theme",
                        "Appearance", self.toggle_theme))
        entries.append(("\U0001f504", "Refresh all data",
                        "Action", self._refresh_all_tabs))
        return entries

    def open_command_palette(self):
        from ui.widgets.command_palette import CommandPalette
        dlg = CommandPalette(self._palette_entries(), self)
        # Centre it near the top of the window, where the eye already is.
        dlg.adjustSize()
        g = self.geometry()
        dlg.move(g.x() + (g.width() - dlg.width()) // 2, g.y() + 90)
        dlg.exec_()

    def _refresh_all_tabs(self):
        """Called by AuditTab when data changes — refresh all visible tabs."""
        # Refresh category icon cache (used by all tabs for transaction cards)
        from ui.tabs.database_tab import _refresh_cat_icons
        _refresh_cat_icons(self.db)
        for tab in list(self._tabs.values()):
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

        # After a theme switch tabs are rebuilt lazily — realise this one now.
        self._ensure_tab(key)

        self.stack.setCurrentIndex(idx)
        # Update sidebar highlight
        self.sidebar.highlight(key)
        tab = self.stack.widget(idx)
        if hasattr(tab, "on_activated"):
            try:
                tab.on_activated()
            except Exception as e:
                print(f"Activation error on {key}: {e}")
        elif hasattr(tab, "refresh"):
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

    def _exit_summary_confirmed(self):
        """Show a session change summary before the app writes its final backup."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
        from ui.theme import C
        tracker = self.services.get("session_changes")
        activity = self.services.get("session_activity")
        changes = activity.summary() if activity and activity.has_events() else []
        # Keep generic fallback activity for modules not yet explicitly
        # instrumented, while suppressing duplicates covered by domain events.
        if tracker:
            excluded = activity.covered_fallback_nouns() if activity else set()
            if activity and activity.has_events():
                # SQL cannot distinguish supporting rows from the user action
                # that caused them. When explicit events exist, retain only
                # independent Settings/setup fallback activity.
                safe_fallback = {"category", "payment method", "money purpose",
                                 "preference", "recurring rule", "split contact", "split group"}
                changes += tracker.summary(exclude_nouns=excluded, include_nouns=safe_fallback)
            else:
                changes += tracker.summary(exclude_nouns=excluded)
        dlg = QDialog(self)
        dlg.setWindowTitle("Exit Finance Manager")
        dlg.setMinimumWidth(460)
        dlg.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        lay = QVBoxLayout(dlg); lay.setContentsMargins(22,18,22,18); lay.setSpacing(12)
        title = QLabel("📋  Session Changes")
        title.setStyleSheet(f"font-size:17px;font-weight:800;color:{C['text']};")
        lay.addWidget(title)
        subtitle = QLabel("Changes made in this session will be included in the final local backup.")
        subtitle.setWordWrap(True); subtitle.setStyleSheet(f"font-size:12px;color:{C['text3']};")
        lay.addWidget(subtitle)
        box = QFrame(); box.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;}}")
        box_lay = QVBoxLayout(box); box_lay.setContentsMargins(14,10,14,10); box_lay.setSpacing(6)
        if changes:
            for activity in changes:
                line = QLabel(f"•  {activity}")
                line.setStyleSheet(f"font-size:12px;font-weight:600;color:{C['text2']};")
                box_lay.addWidget(line)
        else:
            line = QLabel("No data changes were recorded in this session.")
            line.setStyleSheet(f"font-size:12px;color:{C['text3']};")
            box_lay.addWidget(line)
        lay.addWidget(box)
        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(dlg.reject); buttons.addWidget(cancel)
        exit_btn = QPushButton("Backup and Exit"); exit_btn.setObjectName("primary"); exit_btn.clicked.connect(dlg.accept); buttons.addWidget(exit_btn)
        lay.addLayout(buttons)
        return dlg.exec_() == QDialog.Accepted

    def closeEvent(self, event):
        if not getattr(self, "_exit_confirmed", False):
            if not self._exit_summary_confirmed():
                event.ignore()
                return
            self._exit_confirmed = True
        try:
            self.db.backup()
        except:
            pass
        # Auto-backup to Google Drive if frequency is "on_close"
        try:
            row = self.db.execute("SELECT value FROM preferences WHERE key='gdrive_backup_freq'").fetchone()
            if row and row["value"] == "on_close":
                from services.drive_backup import backup_to_drive
                from datetime import datetime
                ret_row = self.db.execute("SELECT value FROM preferences WHERE key='gdrive_backup_retention'").fetchone()
                retention = int(ret_row["value"]) if ret_row else 14
                success, _ = backup_to_drive(retention=retention)
                if success:
                    self.db.execute("INSERT OR REPLACE INTO preferences VALUES(?, ?)",
                                    ("gdrive_last_backup", datetime.now().isoformat()))
                    self.db.commit()
        except:
            pass  # Non-critical — don't block app close
        event.accept()
