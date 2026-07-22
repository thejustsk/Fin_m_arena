"""Settings tab — Accounts, Lookups, Security, Preferences. Shared table style."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QTableWidget, QTableWidgetItem,
                              QTabWidget, QLineEdit, QComboBox, QDoubleSpinBox,
                              QFormLayout, QDialog, QDialogButtonBox, QMessageBox,
                              QSpinBox, QCheckBox, QFrame)
from PyQt5.QtCore import Qt
from ui.theme import C
from ui.sidebar import fmt_money
from ui.widgets.searchable_combo import SearchableCombo
from ui.widgets.metric_card import mk_table


class SettingsTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self.acct = repos["accounts"]
        self.cards = repos.get("cards")
        self.lu = repos["lookups"]
        self.sec = services["security"]
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 24, 40, 24)
        lay.setSpacing(16)
        h = QLabel("Settings")
        h.setStyleSheet(f"font-size:24px;font-weight:800;")
        lay.addWidget(h)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._accounts_tab(), "Accounts")
        self.tabs.addTab(self._lookups_tab(), "Categories & Lookups")
        self.tabs.addTab(self._security_tab(), "Security")
        self.tabs.addTab(self._prefs_tab(), "Preferences")
        lay.addWidget(self.tabs)

    def _accounts_tab(self):
        w = QWidget(); l = QVBoxLayout(w)
        ab = QPushButton("+ Add Account"); ab.setObjectName("primary"); ab.clicked.connect(self._add_account)
        l.addWidget(ab)
        self.acct_table = mk_table(["Name", "Label", "Type", "Opening Balance", "Active", "Action"])
        l.addWidget(self.acct_table)
        return w

    def _lookups_tab(self):
        w = QWidget(); l = QVBoxLayout(w)
        t = QTabWidget()
        t.addTab(self._categories_tab(), "Categories")
        t.addTab(self._methods_tab(), "Payment Methods")
        t.addTab(self._tags_tab(), "Note Tags")
        l.addWidget(t)
        return w

    def _categories_tab(self):
        w = QWidget(); l = QVBoxLayout(w)
        ab = QPushButton("+ Add Category"); ab.clicked.connect(self._add_category); l.addWidget(ab)
        self.cat_table = mk_table(["Name", "PF Category", "Tax Deductible", "Color"])
        l.addWidget(self.cat_table)
        return w

    def _methods_tab(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.method_table = mk_table(["Name", "Active"])
        l.addWidget(self.method_table)
        return w

    def _tags_tab(self):
        w = QWidget(); l = QVBoxLayout(w)
        ab = QPushButton("+ Add Tag"); ab.clicked.connect(self._add_tag); l.addWidget(ab)
        self.tag_table = mk_table(["Name", "Active"])
        l.addWidget(self.tag_table)
        return w

    def _security_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(16)

        # ── 2FA / TOTP Section ──
        tfa_frame = QFrame()
        tfa_frame.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        tf = QVBoxLayout(tfa_frame); tf.setContentsMargins(16,16,16,16); tf.setSpacing(10)
        tfa_title = QLabel("🔐  Two-Factor Authentication")
        tfa_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};"); tf.addWidget(tfa_title)

        # Status label
        self.totp_lbl = QLabel(); self.totp_lbl.setStyleSheet("font-size:13px;font-weight:600;"); tf.addWidget(self.totp_lbl)

        # Toggle row
        toggle_row = QHBoxLayout()
        toggle_label = QLabel("Require TOTP for login & edits:")
        toggle_label.setStyleSheet(f"font-size:12px;color:{C['text2']};font-weight:600;")
        toggle_row.addWidget(toggle_label)
        self.tfa_toggle = QPushButton("ON")
        self.tfa_toggle.setCheckable(True)
        self.tfa_toggle.setFixedWidth(80)
        self.tfa_toggle.setCursor(Qt.PointingHandCursor)
        self.tfa_toggle.clicked.connect(self._toggle_2fa)
        toggle_row.addWidget(self.tfa_toggle)
        toggle_row.addStretch()
        tf.addLayout(toggle_row)

        # Edit 2FA button (change secret key)
        tfa_note = QLabel("Toggle changes login method. Secret key stays the same.")
        tfa_note.setStyleSheet(f"font-size:11px;color:{C['text3']};font-style:italic;"); tf.addWidget(tfa_note)
        edit_tfa_btn = QPushButton("✏️  Edit 2FA Key (new secret)")
        edit_tfa_btn.setCursor(Qt.PointingHandCursor)
        edit_tfa_btn.clicked.connect(self._edit_tfa_key)
        tf.addWidget(edit_tfa_btn)

        l.addWidget(tfa_frame)

        # ── Change Password ──
        pw_frame = QFrame()
        pw_frame.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        pf = QVBoxLayout(pw_frame); pf.setContentsMargins(16,16,16,16); pf.setSpacing(10)
        pw_title = QLabel("🔑  Change Password")
        pw_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};"); pf.addWidget(pw_title)
        cpw = QPushButton("Change Password"); cpw.clicked.connect(self._change_pw); pf.addWidget(cpw)
        l.addWidget(pw_frame)
        l.addStretch()
        return w

    def _prefs_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(16)

        # ── Display Settings ──
        grp1 = QFrame()
        grp1.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        f1 = QFormLayout(grp1); f1.setContentsMargins(16,16,16,16); f1.setSpacing(10)
        f1.addRow("Theme:", QLabel("Light (locked)"))
        f1.addRow("Currency:", QLabel("₹ Indian"))
        l.addWidget(grp1)

        # ── Pagination Settings ──
        grp2 = QFrame()
        grp2.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        f2 = QFormLayout(grp2); f2.setContentsMargins(16,16,16,16); f2.setSpacing(10)
        title2 = QLabel("📊  Pagination")
        title2.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        f2.addRow(title2)

        self.pref_page_size = QSpinBox(); self.pref_page_size.setRange(30, 1000); self.pref_page_size.setSingleStep(10)
        self.pref_page_size.setToolTip("Number of transactions loaded per batch")
        f2.addRow("Page Size:", self.pref_page_size)

        self.pref_scroll_trigger = QSpinBox(); self.pref_scroll_trigger.setRange(50, 2000); self.pref_scroll_trigger.setSingleStep(50)
        self.pref_scroll_trigger.setToolTip("Load more when this many pixels from the bottom")
        f2.addRow("Scroll Trigger (px):", self.pref_scroll_trigger)
        l.addWidget(grp2)

        # ── Wealth Pagination ──
        grp_w = QFrame()
        grp_w.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        fw = QFormLayout(grp_w); fw.setContentsMargins(16,16,16,16); fw.setSpacing(10)
        title_w = QLabel("\U0001f4c8  Wealth Pagination")
        title_w.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        fw.addRow(title_w)
        self.pref_wealth_page_size = QSpinBox(); self.pref_wealth_page_size.setRange(10, 1000); self.pref_wealth_page_size.setSingleStep(10)
        self.pref_wealth_page_size.setToolTip("Cards loaded per batch in Wealth tab")
        fw.addRow("Page Size:", self.pref_wealth_page_size)
        self.pref_wealth_scroll_trigger = QSpinBox(); self.pref_wealth_scroll_trigger.setRange(20, 2000); self.pref_wealth_scroll_trigger.setSingleStep(50)
        self.pref_wealth_scroll_trigger.setToolTip("Load more when scrolled near bottom")
        fw.addRow("Scroll Trigger (px):", self.pref_wealth_scroll_trigger)
        l.addWidget(grp_w)

        # ── Notes Pagination ──
        grp_n = QFrame()
        grp_n.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        fn = QFormLayout(grp_n); fn.setContentsMargins(16,16,16,16); fn.setSpacing(10)
        title_n = QLabel("\U0001f4cb  Notes Pagination")
        title_n.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        fn.addRow(title_n)
        self.pref_notes_page_size = QSpinBox(); self.pref_notes_page_size.setRange(10, 500); self.pref_notes_page_size.setSingleStep(10)
        self.pref_notes_page_size.setToolTip("Notes loaded per batch")
        fn.addRow("Page Size:", self.pref_notes_page_size)
        self.pref_notes_scroll_trigger = QSpinBox(); self.pref_notes_scroll_trigger.setRange(20, 2000); self.pref_notes_scroll_trigger.setSingleStep(50)
        self.pref_notes_scroll_trigger.setToolTip("Load more when scrolled near bottom")
        fn.addRow("Scroll Trigger (px):", self.pref_notes_scroll_trigger)
        l.addWidget(grp_n)

        # ── Alert Settings ──
        grp3 = QFrame()
        grp3.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        f3 = QFormLayout(grp3); f3.setContentsMargins(16,16,16,16); f3.setSpacing(10)
        title3 = QLabel("🔔  Alerts")
        title3.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        f3.addRow(title3)

        self.pref_txn_alert = QSpinBox(); self.pref_txn_alert.setRange(100, 100000); self.pref_txn_alert.setSingleStep(100)
        self.pref_txn_alert.setPrefix("₹ "); self.pref_txn_alert.setToolTip("Minimum amount for high-value transaction alerts")
        f3.addRow("High-Value Alert:", self.pref_txn_alert)
        l.addWidget(grp3)

        # ── Save + Backup ──
        btn_row = QHBoxLayout()
        save_btn = QPushButton("💾  Save Settings"); save_btn.setObjectName("primary")
        save_btn.setMinimumHeight(38); save_btn.clicked.connect(self._save_prefs)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        bb = QPushButton("📦  Backup Now"); bb.setMinimumHeight(38)
        bb.clicked.connect(lambda: (self.db.backup(), QMessageBox.information(self, "Done", "Backup created.")))
        btn_row.addWidget(bb)
        l.addLayout(btn_row)
        l.addStretch()
        return w

    def _save_prefs(self):
        try:
            self.db.execute("INSERT OR REPLACE INTO preferences VALUES('complete_page_size', ?)",
                            (str(self.pref_page_size.value()),))
            self.db.execute("INSERT OR REPLACE INTO preferences VALUES('scroll_trigger_px', ?)",
                            (str(self.pref_scroll_trigger.value()),))
            self.db.execute("INSERT OR REPLACE INTO preferences VALUES('wealth_page_size', ?)",
                            (str(self.pref_wealth_page_size.value()),))
            self.db.execute("INSERT OR REPLACE INTO preferences VALUES('wealth_scroll_trigger', ?)",
                            (str(self.pref_wealth_scroll_trigger.value()),))
            self.db.execute("INSERT OR REPLACE INTO preferences VALUES('notes_page_size', ?)",
                            (str(self.pref_notes_page_size.value()),))
            self.db.execute("INSERT OR REPLACE INTO preferences VALUES('notes_scroll_trigger', ?)",
                            (str(self.pref_notes_scroll_trigger.value()),))
            self.db.execute("INSERT OR REPLACE INTO preferences VALUES('min_txn_alert', ?)",
                            (str(self.pref_txn_alert.value()),))
            self.db.commit()
            QMessageBox.information(self, "Saved", "Settings saved successfully.\nRestart the app for pagination changes to take effect.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save: {e}")

    def _get_pref(self, key, default):
        try:
            r = self.db.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
            if r and r["value"]: return int(r["value"])
        except: pass
        return default

    # ── Add Account (CURRENT / CASH / WALLET only) ──
    def _add_account(self):
        d = QDialog(self); d.setWindowTitle("Add Account"); f = QFormLayout(d)
        n = QLineEdit(); n.setPlaceholderText("Account name"); f.addRow("Name:", n)
        lb = QLineEdit(); lb.setPlaceholderText("4-char label"); lb.setMaxLength(4); f.addRow("Label:", lb)
        t = QComboBox(); t.addItems(["CURRENT", "CASH", "WALLET"]); f.addRow("Type:", t)
        ob = QDoubleSpinBox(); ob.setPrefix("₹ "); ob.setRange(-99999999, 99999999); f.addRow("Opening Balance:", ob)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); f.addRow(bb)
        if d.exec_() == QDialog.Accepted and n.text().strip():
            try:
                self.acct.create(display_name=n.text().strip(), short_label=(lb.text() or n.text()[:4]).upper(),
                                 account_type=t.currentText(), opening_balance=ob.value(), color_hex="#4F46E5")
                self.refresh()
            except ValueError as e:
                QMessageBox.warning(self, "Duplicate", str(e))

    # ── Edit Account ──
    def _edit_account(self, acct_data):
        """Open edit dialog. Credit cards → cards tab edit dialog. Others → pre-filled account dialog."""
        acct_type = acct_data.get("account_type", "")
        aid = acct_data["account_id"]

        if acct_type == "CREDIT_CARD" and self.cards:
            # Use the Cards tab edit dialog
            card = self.cards.get_by_account(aid)
            if card:
                from ui.tabs.cards_tab import AddCardDialog
                dlg = AddCardDialog(self.cards, self.acct, card=card, parent=self)
                dlg.card_updated.connect(self.refresh)
                dlg.exec_()
                return
            else:
                QMessageBox.warning(self, "Not Found", "No card record found for this account.")
                return

        # Non-credit: pre-filled account dialog
        d = QDialog(self)
        d.setWindowTitle("Edit Account")
        d.setMinimumWidth(400)
        f = QFormLayout(d)

        n = QLineEdit(); n.setText(acct_data.get("display_name", "")); f.addRow("Name:", n)
        lb = QLineEdit(); lb.setText(acct_data.get("short_label", "")); lb.setMaxLength(4); f.addRow("Label:", lb)
        t = QComboBox(); t.addItems(["CURRENT", "CASH", "WALLET"])
        idx = t.findText(acct_type)
        if idx >= 0: t.setCurrentIndex(idx)
        t.setEnabled(False)  # type can't be changed
        f.addRow("Type:", t)
        ob = QDoubleSpinBox(); ob.setPrefix("₹ "); ob.setRange(-99999999, 99999999)
        ob.setValue(acct_data.get("opening_balance", 0)); f.addRow("Opening Balance:", ob)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Update")
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); f.addRow(bb)

        if d.exec_() == QDialog.Accepted and n.text().strip():
            self.acct.update(aid,
                             display_name=n.text().strip(),
                             short_label=(lb.text() or n.text()[:4]).upper(),
                             opening_balance=ob.value())
            self.refresh()

    def _add_category(self):
        name, ok = QInputDialog_getText(self, "New Category", "Name:")
        if ok and name:
            pf, ok2 = QInputDialog_getItem(self, "PF Category", "Type:",
                                            ["commitment", "consumption", "growth", "safety", "nc"])
            if ok2:
                try:
                    self.lu.add_category(name.lower().replace(" ", "_"), name, "#4F46E5", pf)
                    self.refresh()
                except ValueError as e:
                    QMessageBox.warning(self, "Duplicate", str(e))

    def _add_tag(self):
        name, ok = QInputDialog_getText(self, "New Tag", "Tag name:")
        if ok and name:
            try:
                self.lu.add_tag(name.lower(), name)
                self.refresh()
            except ValueError as e:
                QMessageBox.warning(self, "Duplicate", str(e))

    def _change_pw(self):
        pw, ok = QInputDialog_getText(self, "Change Password", "New password:", echo=QLineEdit.Password)
        if ok and pw:
            pw2, ok2 = QInputDialog_getText(self, "Confirm", "Confirm:", echo=QLineEdit.Password)
            if ok2 and pw == pw2:
                self.sec.set_pw(pw); QMessageBox.information(self, "Done", "Password changed.")
            else:
                QMessageBox.warning(self, "Error", "Passwords don't match.")

    def _toggle_account(self, acct_id, current_active):
        new_active = 0 if current_active else 1
        self.acct.update(acct_id, is_active=new_active)
        # Also update associated cards so they move to Closed/Active
        self.db.execute("UPDATE cards SET is_active=? WHERE account_id=?", (new_active, acct_id))
        self.db.commit()
        self.refresh()

    def _toggle_2fa(self):
        """Toggle 2FA on/off WITHOUT changing the secret key."""
        new_state = self.tfa_toggle.isChecked()
        if new_state:
            # Enabling — check if secret exists
            if not self.sec.get_secret():
                QMessageBox.warning(self, "No Secret Key",
                    "No 2FA secret key found. Please use 'Edit 2FA Key' to set up first.")
                self.tfa_toggle.setChecked(False)
                return
            self.sec.toggle_2fa(True)
            QMessageBox.information(self, "2FA Enabled",
                "TOTP is now required for login and wealth edits.")
        else:
            # Disabling — warn
            reply = QMessageBox.question(self, "Disable 2FA?",
                "Password will be used instead of TOTP for login and edits.\nContinue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.sec.toggle_2fa(False)
                QMessageBox.information(self, "2FA Disabled",
                    "Password is now required for login and wealth edits.")
            else:
                self.tfa_toggle.setChecked(True)
        self.refresh()

    def _edit_tfa_key(self):
        """Generate new TOTP secret key — follows setup wizard flow."""
        try:
            import pyotp, qrcode
            from io import BytesIO
            from PyQt5.QtGui import QPixmap
        except ImportError:
            QMessageBox.warning(self, "Missing", "Install pyotp and qrcode:\npip install pyotp qrcode[pil]")
            return

        # Verify current identity first
        if self.sec.is_2fa():
            code, ok = QInputDialog.getText(self, "Verify", "Enter current TOTP code to proceed:")
            if not ok or not self.sec.verify_totp(code):
                QMessageBox.warning(self, "Failed", "Invalid code. Aborted.")
                return
        else:
            pw, ok = QInputDialog.getText(self, "Verify", "Enter your password:", QLineEdit.Password)
            if not ok or not self.sec.verify(pw):
                QMessageBox.warning(self, "Failed", "Invalid password. Aborted.")
                return

        # Generate new secret
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri("FinanceManager", issuer_name="Finance Manager")

        # Generate QR
        qr = qrcode.make(uri)
        buf = BytesIO()
        qr.save(buf, format="PNG")
        buf.seek(0)
        pixmap = QPixmap()
        pixmap.loadFromData(buf.read())

        # Show dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Setup New 2FA Key")
        dlg.setMinimumWidth(420)
        dl = QVBoxLayout(dlg)
        dl.setSpacing(12)

        info = QLabel("Scan this QR code with your authenticator app:")
        info.setStyleSheet(f"font-size:12px;color:{C['text2']};")
        info.setAlignment(Qt.AlignCenter)
        dl.addWidget(info)

        qr_lbl = QLabel()
        qr_lbl.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        qr_lbl.setAlignment(Qt.AlignCenter)
        qr_lbl.setStyleSheet("background:white;border:2px solid #E5E7EB;border-radius:12px;padding:8px;")
        dl.addWidget(qr_lbl, alignment=Qt.AlignCenter)

        sec_lbl = QLabel(f"Manual key: {secret}")
        sec_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sec_lbl.setStyleSheet(f"font-family:'Courier New',monospace;font-size:14px;font-weight:700;"
                              f"color:{C['accent']};background:{C['accent_bg']};"
                              f"padding:10px 16px;border-radius:8px;letter-spacing:2px;")
        sec_lbl.setAlignment(Qt.AlignCenter)
        dl.addWidget(sec_lbl)

        verify_lbl = QLabel("Enter 6-digit code to verify & save:")
        verify_lbl.setStyleSheet(f"font-size:12px;color:{C['text2']};")
        dl.addWidget(verify_lbl)

        code_input = QLineEdit()
        code_input.setPlaceholderText("000000")
        code_input.setMaxLength(6)
        code_input.setMinimumHeight(44)
        code_input.setStyleSheet(f"font-size:18px;font-weight:700;letter-spacing:4px;padding:10px;")
        code_input.setAlignment(Qt.AlignCenter)
        dl.addWidget(code_input)

        err_lbl = QLabel("")
        err_lbl.setStyleSheet(f"color:{C['red']};font-size:12px;font-weight:600;")
        err_lbl.setAlignment(Qt.AlignCenter)
        dl.addWidget(err_lbl)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(dlg.reject)
        save_btn = QPushButton("✅ Verify & Save"); save_btn.setObjectName("primary")
        def do_save():
            code = code_input.text().strip()
            if not code:
                err_lbl.setText("Enter the code."); return
            if not totp.verify(code, valid_window=1):
                err_lbl.setText("Invalid code. Try again.")
                code_input.clear(); code_input.setFocus()
                return
            # Save new secret + enable
            self.sec.repo.set_totp(secret, True)
            dlg.accept()
            QMessageBox.information(self, "Done", "New 2FA key saved and enabled.")
            self.refresh()
        save_btn.clicked.connect(do_save)
        code_input.returnPressed.connect(do_save)
        btn_row.addStretch(); btn_row.addWidget(cancel_btn); btn_row.addWidget(save_btn)
        dl.addLayout(btn_row)

        dlg.exec_()

    def refresh(self):
        accts = self.acct.list_all()
        self.acct_table.setRowCount(len(accts))
        for i, a in enumerate(accts):
            self.acct_table.setItem(i, 0, QTableWidgetItem(a["display_name"]))
            self.acct_table.setItem(i, 1, QTableWidgetItem(a["short_label"]))
            self.acct_table.setItem(i, 2, QTableWidgetItem(a["account_type"]))
            self.acct_table.setItem(i, 3, QTableWidgetItem(fmt_money(a["opening_balance"])))
            self.acct_table.setItem(i, 4, QTableWidgetItem("✓" if a["is_active"] else "✗"))

            # Action: Edit + Activate/Deactivate in a row
            action_w = QWidget()
            action_lay = QHBoxLayout(action_w)
            action_lay.setContentsMargins(4, 2, 4, 2)
            action_lay.setSpacing(6)

            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet(f"color:{C['accent']};font-weight:600;background:transparent;border:1px solid {C['border']};border-radius:6px;padding:4px 10px;")
            edit_btn.setCursor(Qt.PointingHandCursor)
            acct_data = dict(a)
            edit_btn.clicked.connect(lambda _, ad=acct_data: self._edit_account(ad))
            action_lay.addWidget(edit_btn)

            toggle_btn = QPushButton("Deactivate" if a["is_active"] else "Activate")
            toggle_btn.setStyleSheet(f"color:{C['red'] if a['is_active'] else C['green']};font-weight:600;background:transparent;border:1px solid {C['border']};border-radius:6px;padding:4px 8px;")
            toggle_btn.setCursor(Qt.PointingHandCursor)
            aid = a["account_id"]; active = a["is_active"]
            toggle_btn.clicked.connect(lambda _, aid=aid, act=active: self._toggle_account(aid, act))
            action_lay.addWidget(toggle_btn)

            self.acct_table.setCellWidget(i, 5, action_w)

        cats = self.lu.list_categories()
        self.cat_table.setRowCount(len(cats))
        for i, c in enumerate(cats):
            self.cat_table.setItem(i, 0, QTableWidgetItem(c["display_name"]))
            self.cat_table.setItem(i, 1, QTableWidgetItem(c.get("default_pf_category") or "—"))
            self.cat_table.setItem(i, 2, QTableWidgetItem("Yes" if c.get("tax_deductible") else "No"))
            cl = QLabel("●"); cl.setStyleSheet(f"color:{c.get('color_hex') or '#000'};font-size:18px;")
            self.cat_table.setCellWidget(i, 3, cl)

        methods = self.lu.list_methods()
        self.method_table.setRowCount(len(methods))
        for i, m in enumerate(methods):
            self.method_table.setItem(i, 0, QTableWidgetItem(m["display_name"]))
            self.method_table.setItem(i, 1, QTableWidgetItem("✓" if m["is_active"] else "✗"))

        tags = self.lu.list_tags()
        self.tag_table.setRowCount(len(tags))
        for i, t in enumerate(tags):
            self.tag_table.setItem(i, 0, QTableWidgetItem(t["display_name"]))
            self.tag_table.setItem(i, 1, QTableWidgetItem("✓" if t["is_active"] else "✗"))

        is_on = self.sec.is_2fa()
        self.totp_lbl.setText("✓ TOTP Enabled" if is_on else "✗ TOTP Disabled (password required)")
        self.totp_lbl.setStyleSheet(f"color:{C['green'] if is_on else C['amber']};font-weight:600;")
        self.tfa_toggle.setChecked(is_on)
        self.tfa_toggle.setText("ON" if is_on else "OFF")
        self.tfa_toggle.setStyleSheet(
            f"QPushButton{{background:{C['green'] if is_on else C['text3']};color:white;"
            f"border:none;border-radius:12px;padding:4px 14px;font-size:12px;font-weight:700;}}"
            f"QPushButton:hover{{background:{C['green'] if is_on else C['text2']};}}")


        # Load preference values
        if hasattr(self, 'pref_page_size'):
            self.pref_page_size.setValue(self._get_pref('complete_page_size', 150))
            self.pref_scroll_trigger.setValue(self._get_pref('scroll_trigger_px', 400))
            self.pref_wealth_page_size.setValue(self._get_pref('wealth_page_size', 150))
            self.pref_wealth_scroll_trigger.setValue(self._get_pref('wealth_scroll_trigger', 400))
            self.pref_notes_page_size.setValue(self._get_pref('notes_page_size', 50))
            self.pref_notes_scroll_trigger.setValue(self._get_pref('notes_scroll_trigger', 200))
            self.pref_txn_alert.setValue(self._get_pref('min_txn_alert', 499))


def QInputDialog_getText(parent, title, label, echo=QLineEdit.Normal):
    from PyQt5.QtWidgets import QInputDialog
    return QInputDialog.getText(parent, title, label, echo)

def QInputDialog_getItem(parent, title, label, items, current=0):
    from PyQt5.QtWidgets import QInputDialog
    return QInputDialog.getItem(parent, title, label, items, current, False)

try:
    from PyQt5.QtWidgets import QInputDialog
except ImportError:
    pass

try:
    import pyotp
    HAS_TOTP = True
except ImportError:
    HAS_TOTP = False
