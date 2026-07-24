"""Settings tab — Accounts, Lookups, Security, Preferences, Data Management, User Guide."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QTableWidget, QTableWidgetItem,
                              QTabWidget, QLineEdit, QComboBox, QDoubleSpinBox,
                              QFormLayout, QDialog, QDialogButtonBox, QMessageBox,
                              QSpinBox, QCheckBox, QFrame, QScrollArea, QGridLayout,
                              QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal as _Signal
from PyQt5.QtGui import QCursor
from datetime import datetime
from ui.theme import C
from ui.sidebar import fmt_money
from ui.widgets.metric_card import mk_table
from ui.uppercase import force_upper


# Default icons for categories (same as database_tab CAT_ICONS)
_CAT_ICONS = {
    "food_dining": "\U0001f354", "transport": "\U0001f697", "shopping": "\U0001f6cd\ufe0f",
    "bills_utilities": "\U0001f4a1", "rent": "\U0001f3e0", "salary": "\U0001f4b0",
    "investment": "\U0001f4c8", "health": "\U0001f3e5", "education": "\U0001f4da",
    "entertainment": "\U0001f3ac", "finance": "\U0001f4b8", "transfer": "\U0001f504", "other": "\U0001f4cb",
}

# Icon palette for selection
_ICON_PALETTE = [
    # Food & Drink
    "🍔", "🍕", "🍜", "🍞", "🍟", "🍫",
    "🍰", "🍱", "🍦", "🍩", "🧀", "🧁",
    "🥚", "🥛", "🥐", "🍎", "🍊", "🍅",
    # Transport
    "🚗", "🚕", "🚌", "🛵", "✈️", "🛴",
    "🚢", "🚋", "🛹", "🚲", "🏍️", "🚘",
    # Shopping & Money
    "🛍️", "🏪", "🛒", "📱", "💻", "📷",
    "💡", "💰", "💳", "💸", "💵", "💱",
    "🏦", "📈", "📊", "📉", "📅", "📄",
    # Home & Building
    "🏠", "🏡", "🏢", "🏥", "🏨", "🏪",
    "🏫", "🏭", "🏮", "🏯", "🏰", "⛪",
    # Health & Education
    "💊", "💉", "🏥", "📚", "🎓",
    "📖", "📝", "📋", "📑", "📎", "📏",
    # Entertainment & Sports
    "🎬", "🎨", "🎵", "🎶", "🎮", "🎲",
    "⚽", "🏀", "🏈", "🎾", "🎿", "🏆",
    # People & Gestures
    "👍", "👎", "👋", "🙏", "🎉", "🎊",
    "🎁", "🎈", "🥳", "😎", "🔥", "✨",
    # Objects & Symbols
    "⚙️", "🔒", "🔓", "🔔", "❤️", "⭐",
    "🚀", "🎯", "💠", "🌈", "💧", "💣",
    "⚠️", "✅", "❌", "❗", "❓", "☑️",
    # Nature & Animals
    "🐾", "🐱", "🐶", "🐻", "🐰", "🐼",
    "🌹", "🌻", "🌲", "🌿", "🍀", "🌱",
]

# Color palette for selection
_COLOR_PALETTE = [
    "#EF4444", "#F97316", "#F59E0B", "#EAB308", "#84CC16", "#22C55E",
    "#10B981", "#14B8A6", "#06B6D4", "#0EA5E9", "#3B82F6", "#6366F1",
    "#8B5CF6", "#A855F7", "#D946EF", "#EC4899", "#F43F5E", "#78716C",
    "#6B7280", "#9CA3AF", "#374151", "#111827", "#1F2937", "#4B5563",
]

ACCT_TYPE_CONFIG = {
    "CURRENT":  {"icon": "\U0001f3e6", "label": "Bank Accounts",   "color": "#4F46E5"},
    "CASH":     {"icon": "\U0001f4b5", "label": "Cash",            "color": "#F59E0B"},
    "WALLET":   {"icon": "\U0001f45b", "label": "Wallets",         "color": "#8B5CF6"},
    "SAVINGS":  {"icon": "\U0001f3e6", "label": "Savings / FD",    "color": "#059669"},
}


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
        self.tabs.addTab(self._data_mgmt_tab(), "Data Management")
        self.tabs.addTab(self._user_guide_tab(), "User Guide")
        lay.addWidget(self.tabs)

    # ══════════════════════════════════════════════
    # 1. ACCOUNTS — single-line rows, grouped by type
    # ══════════════════════════════════════════════
    def _accounts_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(12)
        ab = QPushButton("+ Add Account"); ab.setObjectName("primary"); ab.clicked.connect(self._add_account)
        l.addWidget(ab)
        self.acct_scroll = QScrollArea()
        self.acct_scroll.setWidgetResizable(True)
        self.acct_scroll.setFrameShape(QFrame.NoFrame)
        self.acct_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.acct_inner = QWidget()
        self.acct_inner.setStyleSheet("background:transparent;")
        self.acct_lay = QVBoxLayout(self.acct_inner)
        self.acct_lay.setSpacing(16)
        self.acct_lay.setContentsMargins(0, 4, 0, 4)
        self.acct_scroll.setWidget(self.acct_inner)
        l.addWidget(self.acct_scroll, 1)
        return w

    def _refresh_accounts(self):
        while self.acct_lay.count():
            itm = self.acct_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()

        accts = self.acct.list_all()
        groups = {}
        for a in accts:
            t = a["account_type"]
            if t not in groups: groups[t] = []
            groups[t].append(a)

        for atype in ["CURRENT", "CASH", "WALLET", "SAVINGS", "CREDIT_CARD"]:
            if atype not in groups: continue
            cfg = ACCT_TYPE_CONFIG.get(atype, {"icon": "\U0001f4b0", "label": atype, "color": "#6B7280"})
            if atype == "CREDIT_CARD":
                cfg = {"icon": "\U0001f4b3", "label": "Credit Cards", "color": "#7C3AED"}

            # Group header
            hdr = QLabel(f"{cfg['icon']}  {cfg['label']} ({len(groups[atype])})")
            hdr.setStyleSheet(f"color:{cfg['color']};font-size:13px;font-weight:700;padding:4px 0;")
            self.acct_lay.addWidget(hdr)

            # Single-line rows
            for a in groups[atype]:
                row = self._make_acct_row(a, cfg["color"])
                self.acct_lay.addWidget(row)

        self.acct_lay.addStretch()

    def _make_acct_row(self, a, accent):
        """Single-line account row."""
        row = QFrame()
        row.setFixedHeight(44)
        row.setStyleSheet(
            f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};"
            f"border-left:3px solid {accent};border-radius:8px;}}"
            f"QLabel{{background:transparent;border:none;}}")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(16)

        # Name
        name = QLabel(f"<b>{a['display_name']}</b>")
        name.setStyleSheet(f"font-size:12px;color:{C['text']};")
        lay.addWidget(name, 2)

        # Label
        lbl = QLabel(a["short_label"])
        lbl.setStyleSheet(f"color:{C['text3']};font-size:11px;font-weight:600;")
        lay.addWidget(lbl, 0)

        # Type badge
        badge = QLabel(a["account_type"])
        badge.setStyleSheet(f"color:{accent};font-size:9px;font-weight:700;background:{accent}15;border-radius:4px;padding:2px 6px;")
        lay.addWidget(badge, 0)

        # Opening Balance
        ob_lbl = QLabel("OPENING BALANCE")
        ob_lbl.setStyleSheet(f"color:{C['text3']};font-size:9px;font-weight:600;")
        lay.addWidget(ob_lbl, 0)
        bal = QLabel(fmt_money(a["opening_balance"]))
        bal.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};")
        lay.addWidget(bal, 0)

        # Status
        if not a["is_active"]:
            status = QLabel("INACTIVE")
            status.setStyleSheet(f"color:{C['text3']};font-size:9px;font-weight:700;background:{C['border2']};border-radius:4px;padding:1px 6px;")
            lay.addWidget(status, 0)

        # Edit button
        edit_btn = QPushButton("Edit")
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.setStyleSheet(f"color:{C['accent']};font-weight:600;background:transparent;border:1px solid {C['border']};border-radius:6px;padding:3px 10px;font-size:11px;")
        acct_data = dict(a)
        edit_btn.clicked.connect(lambda _, ad=acct_data: self._edit_account(ad))
        lay.addWidget(edit_btn, 0)

        # Activate/Deactivate toggle
        toggle_btn = QPushButton("Deactivate" if a["is_active"] else "Activate")
        toggle_btn.setCursor(Qt.PointingHandCursor)
        toggle_btn.setStyleSheet(f"color:{C['red'] if a['is_active'] else C['green']};font-weight:600;background:transparent;border:1px solid {C['border']};border-radius:6px;padding:3px 10px;font-size:11px;")
        aid = a["account_id"]; active = a["is_active"]
        toggle_btn.clicked.connect(lambda _, aid=aid, act=active: self._toggle_account(aid, act))
        lay.addWidget(toggle_btn, 0)

        return row

    # ══════════════════════════════════════════════
    # 2. CATEGORIES — icon palette, color disc, instant update
    # ══════════════════════════════════════════════
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
        self.cat_table = mk_table(["Icon", "Name", "PF Category", "Tax", "Color", "Action"])
        l.addWidget(self.cat_table)
        return w

    def _methods_tab(self):
        w = QWidget(); l = QVBoxLayout(w)
        ab = QPushButton("+ Add Payment Method"); ab.clicked.connect(self._add_method); l.addWidget(ab)
        self.method_table = mk_table(["Name", "Status", "Action"])
        l.addWidget(self.method_table)
        return w

    def _tags_tab(self):
        w = QWidget(); l = QVBoxLayout(w)
        ab = QPushButton("+ Add Tag"); ab.clicked.connect(self._add_tag); l.addWidget(ab)
        self.tag_table = mk_table(["Name", "Active"])
        l.addWidget(self.tag_table)
        return w

    def _get_cat_icon(self, cid):
        """Get icon for category: custom from preferences, or default from CAT_ICONS."""
        try:
            r = self.db.execute("SELECT value FROM preferences WHERE key=?", (f"cat_icon_{cid}",)).fetchone()
            if r and r["value"]: return r["value"]
        except: pass
        return _CAT_ICONS.get(cid, "\U0001f4cb")

    def _add_category(self):
        d = QDialog(self); d.setWindowTitle("Add Category"); d.setMinimumWidth(400)
        f = QFormLayout(d)

        # Icon selector
        icon_row = QHBoxLayout()
        self._new_cat_icon = "\U0001f4cb"
        icon_btn = QPushButton(self._new_cat_icon)
        icon_btn.setFixedSize(48, 48)
        icon_btn.setStyleSheet("font-size:20px;background:transparent;border:1px solid #E5E7EB;border-radius:8px;")
        icon_btn.setCursor(Qt.PointingHandCursor)
        def pick_icon():
            chosen = self._show_icon_palette()
            if chosen:
                self._new_cat_icon = chosen
                icon_btn.setText(chosen)
        icon_btn.clicked.connect(pick_icon)
        icon_row.addWidget(icon_btn)
        icon_row.addWidget(QLabel("Click to pick icon"))
        icon_row.addStretch()
        f.addRow("Icon:", icon_row)

        name = QLineEdit(); name.setPlaceholderText("Category name"); f.addRow("Name:", name)
        pf = QComboBox(); pf.addItems(["commitment", "consumption", "growth", "safety", "nc"]); f.addRow("PF Category:", pf)

        # Color disc selector
        color_row = QHBoxLayout()
        self._new_cat_color = "#4F46E5"
        color_btn = QPushButton()
        color_btn.setFixedSize(32, 32)
        color_btn.setStyleSheet(f"background:{self._new_cat_color};border:2px solid #E5E7EB;border-radius:16px;")
        color_btn.setCursor(Qt.PointingHandCursor)
        def pick_color():
            chosen = self._show_color_palette()
            if chosen:
                self._new_cat_color = chosen
                color_btn.setStyleSheet(f"background:{chosen};border:2px solid #E5E7EB;border-radius:16px;")
        color_btn.clicked.connect(pick_color)
        color_row.addWidget(color_btn)
        color_row.addWidget(QLabel("Click to pick color"))
        color_row.addStretch()
        f.addRow("Color:", color_row)

        tax = QCheckBox("Tax deductible"); f.addRow("", tax)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); f.addRow(bb)

        if d.exec_() == QDialog.Accepted and name.text().strip():
            try:
                cid = name.text().strip().lower().replace(" ", "_")
                self.lu.add_category(cid, name.text().strip(), self._new_cat_color,
                                      pf.currentText(), 1 if tax.isChecked() else 0)
                self.db.execute("INSERT OR REPLACE INTO preferences VALUES(?, ?)",
                                (f"cat_icon_{cid}", self._new_cat_icon))
                self.db.commit()
                self.refresh()
            except ValueError as e:
                QMessageBox.warning(self, "Duplicate", str(e))

    def _edit_category(self, cat_data):
        cid = cat_data.get("category_id", "")
        d = QDialog(self)
        d.setWindowTitle(f"Edit: {cat_data['display_name']}")
        d.setMinimumWidth(400)
        f = QFormLayout(d)

        # Icon selector
        current_icon = self._get_cat_icon(cid)
        icon_row = QHBoxLayout()
        self._edit_cat_icon = current_icon
        icon_btn = QPushButton(current_icon)
        icon_btn.setFixedSize(48, 48)
        icon_btn.setStyleSheet("font-size:20px;background:transparent;border:1px solid #E5E7EB;border-radius:8px;")
        icon_btn.setCursor(Qt.PointingHandCursor)
        def pick_icon():
            chosen = self._show_icon_palette()
            if chosen:
                self._edit_cat_icon = chosen
                icon_btn.setText(chosen)
        icon_btn.clicked.connect(pick_icon)
        icon_row.addWidget(icon_btn)
        icon_row.addWidget(QLabel("Click to pick icon"))
        icon_row.addStretch()
        f.addRow("Icon:", icon_row)

        name = QLineEdit(); name.setText(cat_data.get("display_name", "")); f.addRow("Name:", name)
        pf = QComboBox(); pf.addItems(["commitment", "consumption", "growth", "safety", "nc"])
        pf.setCurrentText(cat_data.get("default_pf_category", "nc")); f.addRow("PF Category:", pf)

        # Color disc selector
        current_color = cat_data.get("color_hex", "#4F46E5")
        color_row = QHBoxLayout()
        self._edit_cat_color = current_color
        color_btn = QPushButton()
        color_btn.setFixedSize(32, 32)
        color_btn.setStyleSheet(f"background:{current_color};border:2px solid #E5E7EB;border-radius:16px;")
        color_btn.setCursor(Qt.PointingHandCursor)
        def pick_color():
            chosen = self._show_color_palette()
            if chosen:
                self._edit_cat_color = chosen
                color_btn.setStyleSheet(f"background:{chosen};border:2px solid #E5E7EB;border-radius:16px;")
        color_btn.clicked.connect(pick_color)
        color_row.addWidget(color_btn)
        color_row.addWidget(QLabel("Click to pick color"))
        color_row.addStretch()
        f.addRow("Color:", color_row)

        tax = QCheckBox("Tax deductible"); tax.setChecked(bool(cat_data.get("tax_deductible", 0))); f.addRow("", tax)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Update")
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); f.addRow(bb)

        if d.exec_() == QDialog.Accepted:
            self.db.execute(
                "UPDATE categories SET display_name=?, color_hex=?, default_pf_category=?, tax_deductible=? WHERE category_id=?",
                (name.text().strip(), self._edit_cat_color, pf.currentText(),
                 1 if tax.isChecked() else 0, cid))
            self.db.execute("INSERT OR REPLACE INTO preferences VALUES(?, ?)",
                            (f"cat_icon_{cid}", self._edit_cat_icon))
            self.db.commit()
            self.refresh()

    def _show_icon_palette(self):
        """Show icon palette dialog, return selected icon or None."""
        d = QDialog(self)
        d.setWindowTitle("Pick Icon")
        d.setMinimumWidth(400)
        lay = QVBoxLayout(d)
        lay.setSpacing(8)
        lbl = QLabel("Click an icon:")
        lbl.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        lay.addWidget(lbl)
        grid = QGridLayout()
        grid.setSpacing(4)
        selected = [None]
        for i, icon in enumerate(_ICON_PALETTE):
            btn = QPushButton(icon)
            btn.setFixedSize(48, 48)
            btn.setStyleSheet("font-size:20px;background:transparent;border:1px solid transparent;border-radius:8px;padding:2px;")
            btn.setCursor(Qt.PointingHandCursor)
            def pick(_, ic=icon):
                selected[0] = ic
                d.accept()
            btn.clicked.connect(pick)
            grid.addWidget(btn, i // 8, i % 8)
        lay.addLayout(grid)
        bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        bb.rejected.connect(d.reject)
        lay.addWidget(bb)
        d.exec_()
        return selected[0]

    def _show_color_palette(self):
        """Show color palette dialog, return selected color or None."""
        d = QDialog(self)
        d.setWindowTitle("Pick Color")
        d.setMinimumWidth(360)
        lay = QVBoxLayout(d)
        lay.setSpacing(8)
        lbl = QLabel("Click a color:")
        lbl.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        lay.addWidget(lbl)
        grid = QGridLayout()
        grid.setSpacing(6)
        selected = [None]
        for i, color in enumerate(_COLOR_PALETTE):
            btn = QPushButton()
            btn.setFixedSize(36, 36)
            btn.setStyleSheet(f"background:{color};border:2px solid #E5E7EB;border-radius:18px;")
            btn.setCursor(Qt.PointingHandCursor)
            def pick(_, c=color):
                selected[0] = c
                d.accept()
            btn.clicked.connect(pick)
            grid.addWidget(btn, i // 8, i % 8)
        lay.addLayout(grid)
        bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        bb.rejected.connect(d.reject)
        lay.addWidget(bb)
        d.exec_()
        return selected[0]

    def _add_method(self):
        d = QDialog(self); d.setWindowTitle("Add Payment Method"); f = QFormLayout(d)
        name = QLineEdit(); name.setPlaceholderText("e.g. PHONEPAY"); f.addRow("Name:", name)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); f.addRow(bb)
        if d.exec_() == QDialog.Accepted and name.text().strip():
            try:
                mid = name.text().strip().upper().replace(" ", "_")
                existing = self.db.execute("SELECT method_id FROM payment_methods WHERE method_id=?", (mid,)).fetchone()
                if existing:
                    QMessageBox.warning(self, "Duplicate", f"Method '{name.text()}' already exists.")
                    return
                max_order = self.db.execute("SELECT MAX(sort_order) FROM payment_methods").fetchone()
                order = (max_order[0] or 0) + 1 if max_order else 0
                self.db.execute("INSERT INTO payment_methods(method_id, display_name, is_active, sort_order) VALUES(?,?,1,?)",
                                (mid, name.text().strip(), order))
                self.db.commit()
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _add_tag(self):
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Tag", "Tag name:")
        if ok and name:
            try:
                self.lu.add_tag(name.lower(), name)
                self.refresh()
            except ValueError as e:
                QMessageBox.warning(self, "Duplicate", str(e))

    # ══════════════════════════════════════════════
    # 3. PAYMENT METHOD TOGGLE (not permanent removal)
    # ══════════════════════════════════════════════
    def _toggle_method(self, method_id, current_active):
        """Toggle payment method active state. Does NOT delete — just hides from dropdown."""
        new_active = 0 if current_active else 1
        self.db.execute("UPDATE payment_methods SET is_active=? WHERE method_id=?", (new_active, method_id))
        self.db.commit()
        self.refresh()

    # ══════════════════════════════════════════════
    # 4. SECURITY — smaller toggle, tab security with auth
    # ══════════════════════════════════════════════
    def _security_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(16)

        # ── 2FA / TOTP Section ──
        tfa_frame = QFrame()
        tfa_frame.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        tf = QVBoxLayout(tfa_frame); tf.setContentsMargins(16,16,16,16); tf.setSpacing(10)
        tfa_title = QLabel("\U0001f510  Two-Factor Authentication")
        tfa_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};"); tf.addWidget(tfa_title)

        self.totp_lbl = QLabel(); self.totp_lbl.setStyleSheet("font-size:13px;font-weight:600;"); tf.addWidget(self.totp_lbl)

        toggle_row = QHBoxLayout()
        toggle_label = QLabel("Require TOTP for login & edits:")
        toggle_label.setStyleSheet(f"font-size:12px;color:{C['text2']};font-weight:600;")
        toggle_row.addWidget(toggle_label)
        self.tfa_toggle = QPushButton("ON")
        self.tfa_toggle.setCheckable(True)
        self.tfa_toggle.setFixedSize(64, 28)
        self.tfa_toggle.setCursor(Qt.PointingHandCursor)
        self.tfa_toggle.clicked.connect(self._toggle_2fa)
        toggle_row.addWidget(self.tfa_toggle)
        toggle_row.addStretch()
        tf.addLayout(toggle_row)

        tfa_note = QLabel("Toggle changes login method. Secret key stays the same.")
        tfa_note.setStyleSheet(f"font-size:11px;color:{C['text3']};font-style:italic;"); tf.addWidget(tfa_note)
        edit_tfa_btn = QPushButton("\u270f\ufe0f  Edit 2FA Key (new secret)")
        edit_tfa_btn.setCursor(Qt.PointingHandCursor)
        edit_tfa_btn.clicked.connect(self._edit_tfa_key)
        tf.addWidget(edit_tfa_btn)
        l.addWidget(tfa_frame)

        # ── Google Account Section ──
        g_frame = QFrame()
        g_frame.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        gf = QVBoxLayout(g_frame); gf.setContentsMargins(16,16,16,16); gf.setSpacing(10)
        g_title = QLabel("\U0001f4e7  Google Account (Optional)")
        g_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};"); gf.addWidget(g_title)
        g_desc = QLabel("Link your Google account to enable 'Sign in with Google' as an alternative login method.")
        g_desc.setStyleSheet(f"font-size:11px;color:{C['text3']};font-style:italic;"); g_desc.setWordWrap(True); gf.addWidget(g_desc)

        self.google_status = QLabel()
        self.google_status.setStyleSheet("font-size:13px;font-weight:600;")
        gf.addWidget(self.google_status)

        self.google_btn_row = QHBoxLayout()
        self.google_link_btn = QPushButton("\U0001f517  Link Google Account")
        self.google_link_btn.setCursor(Qt.PointingHandCursor)
        self.google_link_btn.clicked.connect(self._setup_google)
        self.google_btn_row.addWidget(self.google_link_btn)
        self.google_unlink_btn = QPushButton("Unlink")
        self.google_unlink_btn.setCursor(Qt.PointingHandCursor)
        self.google_unlink_btn.setStyleSheet(f"color:{C['red']};font-weight:600;background:transparent;border:1px solid {C['border']};border-radius:6px;padding:4px 10px;")
        self.google_unlink_btn.clicked.connect(self._unlink_google)
        self.google_btn_row.addWidget(self.google_unlink_btn)
        self.google_btn_row.addStretch()
        gf.addLayout(self.google_btn_row)
        l.addWidget(g_frame)

        # ── Change Password ──
        pw_frame = QFrame()
        pw_frame.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        pf = QVBoxLayout(pw_frame); pf.setContentsMargins(16,16,16,16); pf.setSpacing(10)
        pw_title = QLabel("\U0001f511  Change Password")
        pw_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};"); pf.addWidget(pw_title)
        cpw = QPushButton("Change Password"); cpw.clicked.connect(self._change_pw); pf.addWidget(cpw)
        l.addWidget(pw_frame)

        # ── Tab Security Section ──
        ts_frame = QFrame()
        ts_frame.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        tsf = QVBoxLayout(ts_frame); tsf.setContentsMargins(16,16,16,16); tsf.setSpacing(10)
        ts_title = QLabel("\U0001f512  Tab Security (Optional)")
        ts_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};"); tsf.addWidget(ts_title)
        ts_desc = QLabel("Enable password protection for specific tabs. Login password/TOTP will be used.")
        ts_desc.setStyleSheet(f"font-size:11px;color:{C['text3']};font-style:italic;"); ts_desc.setWordWrap(True); tsf.addWidget(ts_desc)

        self._tab_sec_checks = {}
        tab_names = {
            "wealth": "\U0001f4c8  Wealth",
            "audit": "\U0001f50d  Audit",
            "database": "\U0001f5c4\ufe0f  Database",
            "cards": "\U0001f4b3  Credit Cards",
            "notes": "\U0001f4cb  Notes",
            "gmail": "\U0001f4e7  Gmail",
            "settings": "\u2699\ufe0f  Settings",
        }
        for key, label in tab_names.items():
            is_protected = False
            try:
                existing = self.db.execute("SELECT * FROM tab_security WHERE tab_key=?", (key,)).fetchone()
                is_protected = bool(existing)
            except: pass

            # Container frame for each tab row
            row_frame = QFrame()
            row_frame.setStyleSheet(
                f"QFrame{{background:{C['bg']};border:1px solid {C['border2']};border-radius:8px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            row = QHBoxLayout(row_frame)
            row.setContentsMargins(12, 6, 12, 6)
            row.setSpacing(10)

            lbl = QLabel(label)
            lbl.setStyleSheet(f"font-size:12px;color:{C['text2']};font-weight:600;")
            row.addWidget(lbl)
            row.addStretch()

            # Toggle button (like 2FA toggle)
            toggle = QPushButton("ON" if is_protected else "OFF")
            toggle.setCheckable(True)
            toggle.setChecked(is_protected)
            toggle.setFixedSize(64, 28)
            toggle.setCursor(Qt.PointingHandCursor)
            toggle.setStyleSheet(
                f"QPushButton{{background:{C['green'] if is_protected else C['text3']};color:white;"
                f"border:none;border-radius:14px;padding:2px 16px;font-size:11px;font-weight:700;}}"
                f"QPushButton:hover{{background:{C['green'] if is_protected else C['text2']};}}")
            toggle.clicked.connect(lambda checked, k=key, btn=toggle: self._toggle_tab_security_btn(k, checked, btn))
            self._tab_sec_checks[key] = toggle
            row.addWidget(toggle)
            tsf.addWidget(row_frame)

        l.addWidget(ts_frame)
        l.addStretch()
        return w

    def _toggle_tab_security_btn(self, tab_key, checked, btn):
        """Toggle button handler for tab security — requires password/TOTP verification."""
        btn.setEnabled(False)
        from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        QApplication.processEvents()

        action = "protect" if checked else "remove protection from"

        # Custom styled verification dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("\U0001f512  Verify")
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        title = QLabel("\U0001f512  Verification Required")
        title.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        lay.addWidget(title)

        if self.sec.is_2fa():
            desc = QLabel(f"Enter TOTP code to {action} this tab:")
        else:
            desc = QLabel(f"Enter password to {action} this tab:")
        desc.setStyleSheet(f"font-size:12px;color:{C['text3']};")
        lay.addWidget(desc)

        input_field = QLineEdit()
        input_field.setMinimumHeight(40)
        if self.sec.is_2fa():
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
        ok_btn = QPushButton("\u2705  Verify")
        ok_btn.setObjectName("primary")
        ok_btn.setMinimumHeight(36)
        def do_verify():
            val = input_field.text().strip()
            if not val:
                err_lbl.setText("Enter the code/password.")
                return
            if self.sec.is_2fa():
                if self.sec.verify_totp(val):
                    dlg.accept()
                else:
                    err_lbl.setText("Invalid TOTP code.")
                    input_field.clear()
                    input_field.setFocus()
            else:
                if self.sec.verify(val):
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

        verified = dlg.exec_() == QDialog.Accepted

        if verified:
            if checked:
                self.db.execute("INSERT OR IGNORE INTO tab_security(tab_key, password_hash, failed_attempts, updated_at) VALUES(?, '', 0, ?)",
                                (tab_key, datetime.now().isoformat()))
                self.db.commit()
                btn.setText("ON")
                btn.setStyleSheet(
                    f"QPushButton{{background:{C['green']};color:white;"
                    f"border:none;border-radius:14px;padding:2px 16px;font-size:11px;font-weight:700;}}"
                    f"QPushButton:hover{{background:{C['green']};}}")
            else:
                self.db.execute("DELETE FROM tab_security WHERE tab_key=?", (tab_key,))
                self.db.commit()
                btn.setText("OFF")
                btn.setStyleSheet(
                    f"QPushButton{{background:{C['text3']};color:white;"
                    f"border:none;border-radius:14px;padding:2px 16px;font-size:11px;font-weight:700;}}"
                    f"QPushButton:hover{{background:{C['text2']};}}")
        else:
            # Revert toggle state
            btn.setChecked(not checked)
            btn.setText("ON" if not checked else "OFF")
            btn.setStyleSheet(
                f"QPushButton{{background:{C['green'] if not checked else C['text3']};color:white;"
                f"border:none;border-radius:14px;padding:2px 16px;font-size:11px;font-weight:700;}}"
                f"QPushButton:hover{{background:{C['green'] if not checked else C['text2']};}}")

        btn.setEnabled(True)

    def _toggle_tab_security(self, tab_key, state):
        """Legacy handler — kept for compatibility."""
        pass

    # ══════════════════════════════════════════════
    # PREFERENCES
    # ══════════════════════════════════════════════
    def _prefs_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(16)

        grp1 = QFrame()
        grp1.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        f1 = QFormLayout(grp1); f1.setContentsMargins(16,16,16,16); f1.setSpacing(10)
        f1.addRow("Theme:", QLabel("Light (locked)"))
        f1.addRow("Currency:", QLabel("\u20b9 Indian"))
        l.addWidget(grp1)

        grp2 = QFrame()
        grp2.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        f2 = QFormLayout(grp2); f2.setContentsMargins(16,16,16,16); f2.setSpacing(10)
        title2 = QLabel("\U0001f4ca  Pagination")
        title2.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        f2.addRow(title2)
        self.pref_page_size = QSpinBox(); self.pref_page_size.setRange(30, 1000); self.pref_page_size.setSingleStep(10)
        f2.addRow("Page Size:", self.pref_page_size)
        self.pref_scroll_trigger = QSpinBox(); self.pref_scroll_trigger.setRange(50, 2000); self.pref_scroll_trigger.setSingleStep(50)
        f2.addRow("Scroll Trigger (px):", self.pref_scroll_trigger)
        l.addWidget(grp2)

        grp_w = QFrame()
        grp_w.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        fw = QFormLayout(grp_w); fw.setContentsMargins(16,16,16,16); fw.setSpacing(10)
        title_w = QLabel("\U0001f4c8  Wealth Pagination")
        title_w.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        fw.addRow(title_w)
        self.pref_wealth_page_size = QSpinBox(); self.pref_wealth_page_size.setRange(10, 1000); self.pref_wealth_page_size.setSingleStep(10)
        fw.addRow("Page Size:", self.pref_wealth_page_size)
        self.pref_wealth_scroll_trigger = QSpinBox(); self.pref_wealth_scroll_trigger.setRange(20, 2000); self.pref_wealth_scroll_trigger.setSingleStep(50)
        fw.addRow("Scroll Trigger (px):", self.pref_wealth_scroll_trigger)
        l.addWidget(grp_w)

        grp_n = QFrame()
        grp_n.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        fn = QFormLayout(grp_n); fn.setContentsMargins(16,16,16,16); fn.setSpacing(10)
        title_n = QLabel("\U0001f4cb  Notes Pagination")
        title_n.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        fn.addRow(title_n)
        self.pref_notes_page_size = QSpinBox(); self.pref_notes_page_size.setRange(10, 500); self.pref_notes_page_size.setSingleStep(10)
        fn.addRow("Page Size:", self.pref_notes_page_size)
        self.pref_notes_scroll_trigger = QSpinBox(); self.pref_notes_scroll_trigger.setRange(20, 2000); self.pref_notes_scroll_trigger.setSingleStep(50)
        fn.addRow("Scroll Trigger (px):", self.pref_notes_scroll_trigger)
        l.addWidget(grp_n)

        grp3 = QFrame()
        grp3.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        f3 = QFormLayout(grp3); f3.setContentsMargins(16,16,16,16); f3.setSpacing(10)
        title3 = QLabel("\U0001f514  Alerts")
        title3.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        f3.addRow(title3)
        self.pref_txn_alert = QSpinBox(); self.pref_txn_alert.setRange(100, 100000); self.pref_txn_alert.setSingleStep(100)
        self.pref_txn_alert.setPrefix("\u20b9 ")
        f3.addRow("High-Value Alert:", self.pref_txn_alert)
        l.addWidget(grp3)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("\U0001f4be  Save Settings"); save_btn.setObjectName("primary")
        save_btn.setMinimumHeight(38); save_btn.clicked.connect(self._save_prefs)
        btn_row.addWidget(save_btn); btn_row.addStretch()
        l.addLayout(btn_row); l.addStretch()
        return w

    # ══════════════════════════════════════════════
    # DATA MANAGEMENT
    # ══════════════════════════════════════════════
    def _data_mgmt_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(16)

        bk_frame = QFrame()
        bk_frame.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        bf = QVBoxLayout(bk_frame); bf.setContentsMargins(16,16,16,16); bf.setSpacing(10)
        bk_title = QLabel("\U0001f4e6  Backup")
        bk_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};"); bf.addWidget(bk_title)
        self.bk_info = QLabel()
        self.bk_info.setStyleSheet(f"font-size:12px;color:{C['text2']};")
        self.bk_info.setWordWrap(True); bf.addWidget(self.bk_info)
        bb = QPushButton("\U0001f4e6  Backup Now"); bb.setMinimumHeight(38)
        bb.clicked.connect(self._do_backup); bf.addWidget(bb)
        l.addWidget(bk_frame)

        st_frame = QFrame()
        st_frame.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        sf = QVBoxLayout(st_frame); sf.setContentsMargins(16,16,16,16); sf.setSpacing(10)
        st_title = QLabel("\U0001f4be  Storage Info")
        st_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};"); sf.addWidget(st_title)
        self.storage_info = QLabel()
        self.storage_info.setStyleSheet(f"font-size:12px;color:{C['text2']};")
        self.storage_info.setWordWrap(True); sf.addWidget(self.storage_info)
        l.addWidget(st_frame)

        # Coming soon container
        cs_frame = QFrame()
        cs_frame.setStyleSheet(f"QFrame{{background:{C['accent_bg']};border:1.5px dashed {C['accent']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        cs_lay = QVBoxLayout(cs_frame); cs_lay.setContentsMargins(16,16,16,16); cs_lay.setSpacing(8)
        cs_icon = QLabel("\U0001f680")
        cs_icon.setStyleSheet("font-size:28px;")
        cs_icon.setAlignment(Qt.AlignCenter)
        cs_lay.addWidget(cs_icon)
        cs_title = QLabel("Coming Soon")
        cs_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['accent']};")
        cs_title.setAlignment(Qt.AlignCenter)
        cs_lay.addWidget(cs_title)
        cs_desc = QLabel(
            "\u2022  Data Export (CSV / Excel)\n"
            "\u2022  Data Import from Bank Statements\n"
            "\u2022  Data Take Down (Delete All Data)\n"
            "\u2022  Cloud Backup & Sync"
        )
        cs_desc.setStyleSheet(f"font-size:12px;color:{C['text2']};")
        cs_desc.setAlignment(Qt.AlignCenter)
        cs_desc.setWordWrap(True)
        cs_lay.addWidget(cs_desc)
        l.addWidget(cs_frame)

        l.addStretch()
        return w

    def _do_backup(self):
        self.db.backup()
        QMessageBox.information(self, "Done", "Backup created.")
        self._refresh_backup_info()

    def _refresh_backup_info(self):
        if not hasattr(self, 'bk_info'): return
        from config import BACKUP_DIR, BACKUP_RETENTION
        import os
        backups = sorted(BACKUP_DIR.glob("finance_*.db"), key=lambda f: f.stat().st_mtime, reverse=True)
        count = len(backups)
        last = backups[0].stat().st_mtime if backups else None
        last_str = datetime.fromtimestamp(last).strftime("%d %b %Y, %I:%M %p") if last else "Never"
        self.bk_info.setText(f"Location: {BACKUP_DIR}\nRetention: {BACKUP_RETENTION} backups\nCurrent: {count}\nLast: {last_str}")
        db_size = os.path.getsize(str(self.db.path)) if hasattr(self.db, 'path') else 0
        total_bk = sum(f.stat().st_size for f in backups)
        self.storage_info.setText(f"Database: {db_size/1024:.1f} KB\nBackups: {total_bk/1024:.1f} KB ({count} files)")

    # ══════════════════════════════════════════════
    # USER GUIDE (4 sub-tabs)
    # ══════════════════════════════════════════════
    def _user_guide_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(12)
        t = QTabWidget()
        t.addTab(self._guide_walkthrough(), "Walk Through")
        t.addTab(self._guide_functions(), "Functions")
        t.addTab(self._guide_scheme(), "Working Scheme")
        t.addTab(self._guide_ui(), "UI Details")
        l.addWidget(t)
        return w

    def _guide_walkthrough(self):
        from ui.walkthrough import WalkthroughPage
        page = WalkthroughPage()
        # Connect navigate_to signal to find and call main window _nav
        def _navigate(tab_key):
            parent = self.parent()
            while parent and not hasattr(parent, '_nav'):
                parent = parent.parent()
            if parent:
                parent._nav(tab_key)
        page.navigate_to.connect(_navigate)
        return page

    def _guide_functions(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget(); inner.setStyleSheet("background:transparent;")
        il = QVBoxLayout(inner); il.setSpacing(16); il.setContentsMargins(4, 4, 12, 4)

        # Header
        hdr = QLabel("\U0001f527  Functions")
        hdr.setStyleSheet(f"font-size:20px;font-weight:800;color:{C['text']};background:transparent;border:none;")
        il.addWidget(hdr)
        sub = QLabel("Every feature in the app, explained.")
        sub.setStyleSheet(f"font-size:12px;color:{C['text3']};background:transparent;border:none;margin-bottom:8px;")
        il.addWidget(sub)

        sections = [
            ("\U0001f4dd  Transactions", "#4F46E5", [
                ("Regular Entry", "Record income (CREDIT) and expenses (DEBIT) with account, category, payment method, need/want tagging, person/org, and description. Auto-creates payment methods if not found."),
                ("Transfer", "Move money between your own accounts. Creates two linked transactions (DEBIT + CREDIT) with a shared transfer_group_id. Swap button to flip From/To. Razorpay-style success animation on completion."),
                ("Gmail Queue", "Coming Soon. Will show transactions suggested from Gmail inbox sync."),
            ]),
            ("\U0001f5c4\ufe0f  Database", "#8B5CF6", [
                ("Complete View", "All transactions with running balances. Search by person, description, amount, category, or account. Infinite lazy scroll (configurable page size). Month and day grouping."),
                ("Monthly View", "Select month/year to see transactions, summary (5 KPI cards + account grid), and visualization (4 Chart.js charts). Print Statement exports to PDF."),
                ("Filtered View", "11 filter fields with multi-value chip selection. Exact or Sequential mode. Stats bar shows count, credits, debits, net. Print filtered results to PDF."),
            ]),
            ("\U0001f4b0  Balances", "#10B981", [
                ("Net Worth", "Hero card showing total net worth with breakdown by account type (Current, Credit Card, Wallet, Cash). Credit cards show negative (money owed)."),
                ("Account Drill-down", "Click any account to see its transactions. Non-CC: paginated with running balances. CC: FIFO cycle headers with Spent/Paid/Remaining, editable due dates. Back button to return."),
            ]),
            ("\U0001f4b3  Credit Cards", "#EF4444", [
                ("Card Carousel", "3D carousel with 60fps animation. Drag/scroll to browse, click to flip (front shows bank/brand/utilization, back shows cardholder/number/expiry). Click stripe to view details."),
                ("Billing Cycles", "FIFO (First-In-First-Out) payment allocation. Statement cycles computed from statement_date. Cycle headers show Spent, Paid, Remaining, editable Due Date."),
                ("Settlement", "Footer with Amount Due / Current Outstanding / Custom. Source account (excludes CCs), method, date. Creates transfer pair. Refreshes everything after."),
                ("Reminders", "Right panel: overdue alerts, statement approaching, high-value transactions, card expiry warnings. Up to 15 reminders sorted by urgency."),
            ]),
            ("\U0001f4b3  Debit Cards", "#F59E0B", [
                ("Card Carousel", "Same 3D carousel pattern. 20 metallic gradient themes (Titanium, Gunmetal, Platinum, etc.). Completely independent from CC tab."),
                ("Account Transactions", "Linked to a CURRENT account. Monthly grouping with Debits/Credits/Surplus headers. Smart lazy scroll: 1 month first, expand if < 4 txns, then 3 months per batch."),
            ]),
            ("\U0001f4c8  Wealth", "#059669", [
                ("Loans I Give", "Track money lent to others. Entry: borrower, amount, interest rate/method, dates. List: color-coded cards by status, progress bar, inline edit, repayment history, Print PDF."),
                ("Loans I Take", "Track money borrowed. EMI and Non-EMI types. EMI preview on entry. Amount types: Updated EMI, Original EMI, Full Pay, Custom. Alerts for overdue and upcoming EMIs."),
                ("FD I Deposit", "Track fixed deposits. Simple/Compound interest with compounding frequency. Maturity preview on entry. Mark Matured, Mark Withdrawn (with premature fee calculation)."),
                ("FD Others Deposit", "Track deposits received from others. Interest-free toggle. Log repayments. Mark as Closed when fully returned."),
                ("Mutual Funds", "Track MF investments. Purchase/SIP and Redemption. Auto-fetch NAV from api.mfapi.in. Background NAV fetch on app start. Search & link fund schemes."),
            ]),
            ("\U0001f50d  Audit", "#D97706", [
                ("Filters & Records", "11 filter fields with multi-value chips. Regular and Wealth transaction sub-tabs. Each card has Select (for bulk) and Edit buttons. Lazy scroll with configurable page size."),
                ("Edit & Bulk Update", "Single edit: all fields, cascade to wealth records, transfer cascade. Bulk: change Category, Need/Want, PF Category. Both require 2FA/password verification. Progress popup during updates."),
                ("Insights", "Analytics with quick period buttons. 4 KPI cards + 4 Chart.js charts. Auto-aggregates by month if range > 90 days."),
            ]),
            ("\U0001f4cb  Notes", "#EC4899", [
                ("All Notes", "Search by title or tag. Expandable cards with accent-colored borders. Click to expand: content, linked transactions, Print/Edit/Delete buttons. Lazy scroll."),
                ("New / Edit Note", "Two-column: left has title, tag chips (with autocomplete), content editor. Right has transaction linker with filters and checkbox toggles. Linked IDs stored as JSON array."),
                ("Trash & Recovery", "Soft-delete with Recover and Delete Forever options. Shows title, tags, deleted date."),
                ("Print PDF", "Styled PDF with title, tags, content, linked transactions (card-style), summary, security table (Doc ID, hash, watermark), QR code."),
            ]),
            ("\u2699\ufe0f  Settings", "#6B7280", [
                ("Accounts", "Grouped by type. Single-line rows with name, label, type badge, opening balance, status. Add/Edit/Activate/Deactivate. CC accounts redirect to card editor."),
                ("Categories", "Icon picker (96 emoji palette), color disc picker (24 colors), PF category, tax deductible flag. Instant update on save."),
                ("Payment Methods", "Add new, activate/deactivate toggle (does NOT delete, just hides from dropdowns)."),
                ("Security", "2FA toggle, Edit 2FA Key (QR code), Google OAuth link/unlink, Change Password, Tab Security (per-tab password protection)."),
                ("Preferences", "Pagination settings for Database, Wealth, Notes. High-value transaction alert threshold."),
                ("Data Management", "Backup with retention, storage info. Coming Soon: Export, Import, Take Down, Cloud Sync."),
            ]),
        ]

        for title, color, items in sections:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-top:3px solid {color};border-radius:10px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            cl = QVBoxLayout(card); cl.setContentsMargins(16, 14, 16, 14); cl.setSpacing(10)
            cl.addWidget(self._guide_section_title(title, color))
            for name, desc in items:
                cl.addWidget(self._guide_item(name, desc, color))
            il.addWidget(card)

        il.addStretch()
        scroll.setWidget(inner)
        l.addWidget(scroll, 1)
        return w

    def _guide_scheme(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget(); inner.setStyleSheet("background:transparent;")
        il = QVBoxLayout(inner); il.setSpacing(16); il.setContentsMargins(4, 4, 12, 4)

        hdr = QLabel("\u2699\ufe0f  Working Scheme")
        hdr.setStyleSheet(f"font-size:20px;font-weight:800;color:{C['text']};background:transparent;border:none;")
        il.addWidget(hdr)
        sub = QLabel("How the app works under the hood.")
        sub.setStyleSheet(f"font-size:12px;color:{C['text3']};background:transparent;border:none;margin-bottom:8px;")
        il.addWidget(sub)

        sections = [
            ("\U0001f4be  Data Storage", "#4F46E5", [
                ("SQLite Database", "All data stored locally in finance.db. No internet required. No data sent to external servers. Single file, easy to backup and move."),
                ("Schema", "Tables: accounts, transactions, categories, payment_methods, cards, card_cycles, debit_cards, loans, borrowers, repayments, borrowed_loans, lenders, borrowed_loan_repayments, fixed_deposits, deposits_from_others, depositors, deposit_repayments_to_others, mf_schemes, mf_transactions, notes, notes_trash, tags, audit_log, tab_security, preferences, settings."),
                ("Relationships", "Transactions link to accounts. Wealth items (loans, FDs, MFs, deposits) create linked transactions via linked_txn_id. Transfers use transfer_group_id. Notes link to transactions via JSON array."),
                ("Migrations", "Schema upgrades happen automatically on app start. New columns/tables added via ALTER TABLE or CREATE TABLE IF NOT EXISTS. Data preserved across upgrades."),
            ]),
            ("\U0001f510  Security", "#EF4444", [
                ("Password", "Bcrypt-hashed master password. Required for login. Change password with confirmation dialog."),
                ("2FA / TOTP", "Optional Time-based One-Time Password. QR code setup with authenticator app (Google Authenticator, Authy, etc.). 6-digit code required for login and wealth edits when enabled."),
                ("Google OAuth", "Optional alternative login. Links Google account via browser OAuth flow. Verifies with Google each time (no stored password). Email and refresh token stored locally."),
                ("Tab Security", "Optional per-tab password protection. Toggles for: Wealth, Audit, Database, Credit Cards, Notes, Gmail, Settings. Each toggle requires password/TOTP verification to change."),
                ("Edit Verification", "All wealth edits and audit edits require 2FA/password verification. Custom 400px styled dialog. Cancel reverts the operation."),
            ]),
            ("\U0001f517  Wealth Linking", "#059669", [
                ("Auto-Linking", "When you give a loan, create an FD, or purchase MF units, a linked transaction is automatically created in the transactions table. The linked_txn_id connects them."),
                ("Cascade on Edit", "Editing a transaction's amount in Audit cascades to the linked wealth record (loan_amount, principal_amount, etc.). Editing the date cascades similarly. Status is auto-recalculated."),
                ("Cascade on Delete", "Deleting a transaction in Audit unlinks the wealth record (sets linked_txn_id to NULL). Transfer transactions are deleted in pairs."),
                ("Status Auto-Calc", "Status is computed automatically: ACTIVE (no payments), PARTIALLY_PAID (some payments), OVERDUE (past due date), REPAID (fully paid), CLOSED (manually marked). Recalculated on every refresh."),
                ("Transfer Cascade", "Transfers create two linked transactions. Editing one cascades to the other (except tx_type). Deleting one deletes both."),
            ]),
            ("\U0001f4b3  Card Billing (FIFO)", "#D97706", [
                ("Statement Cycles", "Computed from statement_date (e.g., '6th' means cycles run from 7th of one month to 6th of next). Cycles built going backwards from today."),
                ("FIFO Allocation", "Payments (CREDIT transactions) are allocated to the oldest cycle with remaining balance first. First In, First Out. Each cycle tracks: debits, paid, remaining."),
                ("Amount Due", "Sum of remaining from ALL previous cycles (not current). Current cycle is excluded because its bill hasn't generated yet."),
                ("Due Dates", "Default: cycle end date + grace_days. Editable per cycle in the card details view. Changes saved to card_cycles table."),
                ("Reminders", "Statement approaching (5 days before, if balance > 0). Overdue (past due date with remaining). High-value transactions (configurable threshold). Card expiry warnings."),
            ]),
            ("\U0001f4ca  Charts & Visualization", "#8B5CF6", [
                ("Chart.js", "All charts use Chart.js 4.4.0 loaded via CDN. Rendered in QWebEngineView. HTML built with data injected as JSON, written to temp file, loaded locally."),
                ("Home Charts", "4 charts: Spending by Category (doughnut), Spending Trend (line), Need vs Want (stacked bar), Income vs Expense by Account (horizontal bar)."),
                ("Monthly Charts", "Same 4 charts for selected month. Forced resize when switching to Visualization tab (QWebEngineView layout fix)."),
                ("Audit Insights", "Same chart template. Auto-aggregates by month if date range > 90 days, else by day."),
            ]),
            ("\U0001f4e6  Backup", "#F59E0B", [
                ("Automatic", "Backup created on app close (configurable). Stored in finance_data/backups/. Retention: last 14 backups (oldest auto-deleted)."),
                ("Manual", "Settings > Data Management > Backup Now. Creates a copy of finance.db with timestamp in filename."),
                ("Storage", "Database size and backup size shown in Settings > Data Management. Backup files are standard SQLite databases — can be opened with any SQLite viewer."),
                ("Restore", "Replace finance.db with a backup file. Restart the app. All data restored."),
            ]),
        ]

        for title, color, items in sections:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-top:3px solid {color};border-radius:10px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            cl = QVBoxLayout(card); cl.setContentsMargins(16, 14, 16, 14); cl.setSpacing(10)
            cl.addWidget(self._guide_section_title(title, color))
            for name, desc in items:
                cl.addWidget(self._guide_item(name, desc, color))
            il.addWidget(card)

        il.addStretch()
        scroll.setWidget(inner)
        l.addWidget(scroll, 1)
        return w

    def _guide_ui(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget(); inner.setStyleSheet("background:transparent;")
        il = QVBoxLayout(inner); il.setSpacing(16); il.setContentsMargins(4, 4, 12, 4)

        hdr = QLabel("\U0001f5bc\ufe0f  UI Details")
        hdr.setStyleSheet(f"font-size:20px;font-weight:800;color:{C['text']};background:transparent;border:none;")
        il.addWidget(hdr)
        sub = QLabel("Visual design, layout patterns, and interaction details.")
        sub.setStyleSheet(f"font-size:12px;color:{C['text3']};background:transparent;border:none;margin-bottom:8px;")
        il.addWidget(sub)

        sections = [
            ("\U0001f3e0  Sidebar", "#4F46E5", [
                ("Navigation", "Left sidebar with collapsible icon mode. Click header to toggle between full labels and icon-only. Sections: MAIN (Home, Transactions, Database, Balances), CARDS (Credit Cards, Debit Cards), WEALTH (Wealth), RECORDS (Audit, Notes), SYSTEM (Settings, Gmail)."),
                ("Need/Want Counter", "Shows count of untagged transactions (neednwant is NULL). Clicking scrolls to the first untagged transaction in Transaction Entry."),
                ("Card Reminders", "When expanded, shows credit card payment due reminders below the navigation."),
                ("Highlight", "Active tab highlighted with indigo background. Called via sidebar.highlight(key) from main window on tab switch."),
            ]),
            ("\U0001f3a8  Theme", "#8B5CF6", [
                ("Colors", "Light theme with indigo accent (#4F46E5). Semantic colors: green (income/success), red (expense/danger), amber (warning), text3 (secondary text). All defined in theme.py as C dict."),
                ("Global QSS", "All input widgets styled globally: QDialog (themed bg), QMessageBox (white bg, dark text), QComboBox (rounded, dropdown arrow), QDateEdit (rounded, calendar styled), QSpinBox/QDoubleSpinBox (rounded), QLineEdit (rounded, hover/focus states)."),
                ("Cards", "Standard card: white bg, 1px #E5E7EB border, 12px radius. Hover: #C7D2FE border, #FAFBFF bg. Accent cards: colored border + tinted bg (e.g., accent_bg for indigo)."),
                ("Buttons", "Primary: indigo bg, white text, no border. Ghost: transparent bg, text2 color, border. Pill: rounded, accent border. All have hover states."),
                ("Typography", "Segoe UI / system-ui font family. Sizes: 24px (page titles), 18px (section titles), 14px (card titles), 13px (body), 12px (secondary), 11px (captions), 10px (labels). Weights: 800 (titles), 700 (emphasis), 600 (labels), 500 (body)."),
            ]),
            ("\U0001f4b3  Carousel Pattern", "#EF4444", [
                ("3D Carousel", "QGraphicsView + QGraphicsScene + QGraphicsObject. Continuous 60fps timer (16ms). FullViewportUpdate mode. Cards positioned using smoothstep easing."),
                ("Card Rendering", "Custom QPainter in _draw_front (bank, brand, chip, utilization bar, network) and _draw_back (stripe, cardholder, number, expiry). Flip animation via QPropertyAnimation on flipScale."),
                ("Interaction", "Drag to scroll, scroll wheel, Left/Right arrows, Space to flip nearest card. Click card to flip. Click 'VIEW CARD DETAILS' stripe to open details."),
                ("Timer Management", "showEvent starts timer, hideEvent stops timer. Prevents dual-timer lag when switching between CC and DC tabs."),
                ("Independence", "CC and DC carousels are completely independent. Zero imports between cards_tab.py and debit_cards_tab.py. Each has own CardItem, CarouselView, PreviewWidget classes."),
            ]),
            ("\U0001f4f1  Smart Scroll", "#10B981", [
                ("Lazy Loading", "Transaction lists load in batches (configurable page size, default 150). Scroll trigger: load more when within 400px of bottom. Configurable in Settings > Preferences."),
                ("Wealth Cards", "Cards pre-built in memory, then rendered in batches. Configurable page size (default 150). Scroll connects to _on_scroll for lazy loading."),
                ("DC Transactions", "Smart initial load: 1 month first, expand if < 4 transactions (up to 6 months), then 3 months per batch on scroll. setUpdatesEnabled(False) during widget addition."),
                ("Notes", "Lazy scroll with configurable page size (default 50) and scroll trigger (default 200px)."),
                ("Audit", "Lazy scroll with configurable page size. Disconnects scroll signal when all items loaded."),
            ]),
            ("\u2328\ufe0f  Keyboard Shortcuts", "#D97706", [
                ("General", "Tab: Move between fields. Enter: Submit form / activate button. Escape: Close dialog / cancel."),
                ("Carousel", "Left/Right arrows: Scroll carousel. Space: Flip nearest card. Scroll wheel: Browse cards."),
                ("Transaction Entry", "Enter on DEBIT button: Toggle DEBIT/CREDIT. Enter on Need/Want buttons: Activate that option. Enter on Add button: Submit. Enter blocked during transfer animation."),
                ("SearchableCombo", "Type to filter dropdown. Up/Down arrows navigate filtered results. Enter selects highlighted item. Escape closes dropdown."),
                ("Notes", "Tag input: Type + Enter to add tag. Up/Down arrows navigate suggestions. Enter selects suggestion. Escape hides suggestions."),
            ]),
            ("\U0001f9ed  Walkthrough", "#EC4899", [
                ("Location", "Settings > User Guide > Walk Through. Full-page guided tour of the entire app."),
                ("Structure", "11 topics with 33 sub-tabs. Left panel: accordion sidebar (one topic expanded at a time). Right panel: Live Prototype (Titanium gradient background) + How It Works explanation."),
                ("Navigation", "Previous/Next buttons with step counter (Step 1 of 33). 'Go to this tab' button navigates to the actual tab in the app."),
                ("Prototypes", "Real Qt widgets with sample data. Each prototype shows the actual UI components you'll see in the app, not screenshots."),
            ]),
        ]

        for title, color, items in sections:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-top:3px solid {color};border-radius:10px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            cl = QVBoxLayout(card); cl.setContentsMargins(16, 14, 16, 14); cl.setSpacing(10)
            cl.addWidget(self._guide_section_title(title, color))
            for name, desc in items:
                cl.addWidget(self._guide_item(name, desc, color))
            il.addWidget(card)

        il.addStretch()
        scroll.setWidget(inner)
        l.addWidget(scroll, 1)
        return w

    # ══════════════════════════════════════════════
    # USER GUIDE HELPERS
    # ══════════════════════════════════════════════
    def go_to_walkthrough(self):
        """Navigate to User Guide > Walk Through tab."""
        # Switch to User Guide tab (index 5)
        self.tabs.setCurrentIndex(5)
        # Find the inner QTabWidget and switch to Walk Through (index 0)
        user_guide_widget = self.tabs.widget(5)
        if user_guide_widget:
            inner_tabs = user_guide_widget.findChild(QTabWidget)
            if inner_tabs:
                inner_tabs.setCurrentIndex(0)

    @staticmethod
    def _guide_section_title(text, color):
        """Section title with colored left bar."""
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size:15px;font-weight:800;color:{color};background:transparent;border:none;padding:2px 0;")
        return lbl

    @staticmethod
    def _guide_item(name, desc, accent):
        """Single item: bold name + description."""
        w = QWidget(); w.setStyleSheet("background:transparent;border:none;")
        lay = QVBoxLayout(w); lay.setContentsMargins(12, 0, 0, 0); lay.setSpacing(2)
        nl = QLabel(name)
        nl.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};background:transparent;border:none;")
        lay.addWidget(nl)
        dl = QLabel(desc)
        dl.setStyleSheet(f"font-size:11px;color:{C['text3']};background:transparent;border:none;")
        dl.setWordWrap(True)
        lay.addWidget(dl)
        return w

    # ══════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════
    def _save_prefs(self):
        try:
            for key, val in [
                ('complete_page_size', self.pref_page_size.value()),
                ('scroll_trigger_px', self.pref_scroll_trigger.value()),
                ('wealth_page_size', self.pref_wealth_page_size.value()),
                ('wealth_scroll_trigger', self.pref_wealth_scroll_trigger.value()),
                ('notes_page_size', self.pref_notes_page_size.value()),
                ('notes_scroll_trigger', self.pref_notes_scroll_trigger.value()),
                ('min_txn_alert', self.pref_txn_alert.value()),
            ]:
                self.db.execute("INSERT OR REPLACE INTO preferences VALUES(?, ?)", (key, str(val)))
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

    def _add_account(self):
        d = QDialog(self); d.setWindowTitle("Add Account"); f = QFormLayout(d)
        n = QLineEdit(); n.setPlaceholderText("Account name"); force_upper(n); f.addRow("Name:", n)
        lb = QLineEdit(); lb.setPlaceholderText("4-char label"); lb.setMaxLength(4); f.addRow("Label:", lb)
        t = QComboBox(); t.addItems(["CURRENT", "CASH", "WALLET"]); f.addRow("Type:", t)
        ob = QDoubleSpinBox(); ob.setPrefix("\u20b9 "); ob.setRange(-99999999, 99999999); f.addRow("Opening Balance:", ob)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); f.addRow(bb)
        if d.exec_() == QDialog.Accepted and n.text().strip():
            try:
                self.acct.create(display_name=n.text().strip(), short_label=(lb.text() or n.text()[:4]).upper(),
                                 account_type=t.currentText(), opening_balance=ob.value(), color_hex="#4F46E5")
                self.refresh()
            except ValueError as e:
                QMessageBox.warning(self, "Duplicate", str(e))

    def _edit_account(self, acct_data):
        acct_type = acct_data.get("account_type", "")
        aid = acct_data["account_id"]
        if acct_type == "CREDIT_CARD" and self.cards:
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
        d = QDialog(self); d.setWindowTitle("Edit Account"); d.setMinimumWidth(400)
        f = QFormLayout(d)
        n = QLineEdit(); n.setText(acct_data.get("display_name", "")); force_upper(n); f.addRow("Name:", n)
        lb = QLineEdit(); lb.setText(acct_data.get("short_label", "")); lb.setMaxLength(4); f.addRow("Label:", lb)
        t = QComboBox(); t.addItems(["CURRENT", "CASH", "WALLET"])
        idx = t.findText(acct_type)
        if idx >= 0: t.setCurrentIndex(idx)
        t.setEnabled(False)
        f.addRow("Type:", t)
        ob = QDoubleSpinBox(); ob.setPrefix("\u20b9 "); ob.setRange(-99999999, 99999999)
        ob.setValue(acct_data.get("opening_balance", 0)); f.addRow("Opening Balance:", ob)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Update")
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); f.addRow(bb)
        if d.exec_() == QDialog.Accepted and n.text().strip():
            self.acct.update(aid, display_name=n.text().strip(),
                             short_label=(lb.text() or n.text()[:4]).upper(),
                             opening_balance=ob.value())
            self.refresh()

    def _toggle_account(self, acct_id, current_active):
        new_active = 0 if current_active else 1
        self.acct.update(acct_id, is_active=new_active)
        self.db.execute("UPDATE cards SET is_active=? WHERE account_id=?", (new_active, acct_id))
        self.db.commit()
        self.refresh()

    def _toggle_2fa(self):
        new_state = self.tfa_toggle.isChecked()
        if new_state:
            if not self.sec.get_secret():
                QMessageBox.warning(self, "No Secret Key", "No 2FA secret key found. Please use 'Edit 2FA Key' to set up first.")
                self.tfa_toggle.setChecked(False); return
            self.sec.toggle_2fa(True)
            QMessageBox.information(self, "2FA Enabled", "TOTP is now required for login and wealth edits.")
        else:
            reply = QMessageBox.question(self, "Disable 2FA?",
                "Password will be used instead of TOTP for login and edits.\nContinue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.sec.toggle_2fa(False)
                QMessageBox.information(self, "2FA Disabled", "Password is now required for login and wealth edits.")
            else:
                self.tfa_toggle.setChecked(True)
        self.refresh()

    def _edit_tfa_key(self):
        try:
            import pyotp, qrcode
            from io import BytesIO
            from PyQt5.QtGui import QPixmap
        except ImportError:
            QMessageBox.warning(self, "Missing", "Install pyotp and qrcode:\npip install pyotp qrcode[pil]")
            return
        if self.sec.is_2fa():
            from PyQt5.QtWidgets import QInputDialog
            code, ok = QInputDialog.getText(self, "Verify", "Enter current TOTP code to proceed:")
            if not ok or not self.sec.verify_totp(code):
                QMessageBox.warning(self, "Failed", "Invalid code. Aborted."); return
        else:
            from PyQt5.QtWidgets import QInputDialog
            pw, ok = QInputDialog.getText(self, "Verify", "Enter your password:", QLineEdit.Password)
            if not ok or not self.sec.verify(pw):
                QMessageBox.warning(self, "Failed", "Invalid password. Aborted."); return
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri("FinanceManager", issuer_name="Finance Manager")
        qr = qrcode.make(uri)
        buf = BytesIO(); qr.save(buf, format="PNG"); buf.seek(0)
        pixmap = QPixmap(); pixmap.loadFromData(buf.read())
        dlg = QDialog(self); dlg.setWindowTitle("Setup New 2FA Key"); dlg.setMinimumWidth(420)
        dl = QVBoxLayout(dlg); dl.setSpacing(12)
        info = QLabel("Scan this QR code with your authenticator app:")
        info.setStyleSheet(f"font-size:12px;color:{C['text2']};"); info.setAlignment(Qt.AlignCenter); dl.addWidget(info)
        qr_lbl = QLabel()
        qr_lbl.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        qr_lbl.setAlignment(Qt.AlignCenter)
        qr_lbl.setStyleSheet("background:white;border:2px solid #E5E7EB;border-radius:12px;padding:8px;")
        dl.addWidget(qr_lbl, alignment=Qt.AlignCenter)
        sec_lbl = QLabel(f"Manual key: {secret}")
        sec_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sec_lbl.setStyleSheet(f"font-family:'Courier New',monospace;font-size:14px;font-weight:700;color:{C['accent']};background:{C['accent_bg']};padding:10px 16px;border-radius:8px;letter-spacing:2px;")
        sec_lbl.setAlignment(Qt.AlignCenter); dl.addWidget(sec_lbl)
        verify_lbl = QLabel("Enter 6-digit code to verify & save:")
        verify_lbl.setStyleSheet(f"font-size:12px;color:{C['text2']};"); dl.addWidget(verify_lbl)
        code_input = QLineEdit(); code_input.setPlaceholderText("000000"); code_input.setMaxLength(6)
        code_input.setMinimumHeight(44)
        code_input.setStyleSheet(f"font-size:18px;font-weight:700;letter-spacing:4px;padding:10px;")
        code_input.setAlignment(Qt.AlignCenter); dl.addWidget(code_input)
        err_lbl = QLabel(""); err_lbl.setStyleSheet(f"color:{C['red']};font-size:12px;font-weight:600;")
        err_lbl.setAlignment(Qt.AlignCenter); dl.addWidget(err_lbl)
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(dlg.reject)
        save_btn = QPushButton("\u2705 Verify & Save"); save_btn.setObjectName("primary")
        def do_save():
            code = code_input.text().strip()
            if not code: err_lbl.setText("Enter the code."); return
            if not totp.verify(code, valid_window=1):
                err_lbl.setText("Invalid code. Try again."); code_input.clear(); code_input.setFocus(); return
            self.sec.repo.set_totp(secret, True)
            dlg.accept()
            QMessageBox.information(self, "Done", "New 2FA key saved and enabled.")
            self.refresh()
        save_btn.clicked.connect(do_save); code_input.returnPressed.connect(do_save)
        btn_row.addStretch(); btn_row.addWidget(cancel_btn); btn_row.addWidget(save_btn)
        dl.addLayout(btn_row)
        dlg.exec_()

    def _setup_google(self):
        from ui.login.google_auth import start_oauth_flow, get_client_id, get_client_secret
        cid = get_client_id(); csec = get_client_secret()
        if not cid or not csec:
            QMessageBox.warning(self, "Not Configured", "Google OAuth credentials are not embedded in the app."); return
        existing = self.sec.get_google_email()
        msg = "This will open your browser to sign in with Google.\n\nYour Google account will be used as an alternative login method.\nThis is for security verification only \u2014 no data is shared with Google."
        if existing: msg = f"Currently linked: {existing}\n\n" + msg
        reply = QMessageBox.question(self, "Link Google Account", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply != QMessageBox.Yes: return

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
            finished = _Signal(str, str, str)

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
                QMessageBox.warning(self, "Failed", f"Google linking failed:\n{error}"); return
            self.sec.setup_google(cid, csec, email, refresh_token)
            QMessageBox.information(self, "Linked", f"Google account '{email}' linked successfully.\n\nYou can now use 'Sign in with Google' on the login screen.")
            self.refresh()

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
        cancel_btn.clicked.connect(_cancel)
        al.addWidget(cancel_btn, alignment=Qt.AlignCenter)

        worker.start()
        auth_dlg.exec_()

        if not worker.isFinished():
            worker.terminate()

    def _unlink_google(self):
        email = self.sec.get_google_email()
        if not email: return
        reply = QMessageBox.question(self, "Unlink Google?", f"Remove Google account '{email}'?\nYou will no longer be able to sign in with Google.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.sec.unlink_google()
            QMessageBox.information(self, "Unlinked", "Google account removed.")
            self.refresh()

    def _change_pw(self):
        from PyQt5.QtWidgets import QInputDialog
        pw, ok = QInputDialog.getText(self, "Change Password", "New password:", echo=QLineEdit.Password)
        if ok and pw:
            pw2, ok2 = QInputDialog.getText(self, "Confirm", "Confirm:", echo=QLineEdit.Password)
            if ok2 and pw == pw2:
                self.sec.set_pw(pw); QMessageBox.information(self, "Done", "Password changed.")
            else:
                QMessageBox.warning(self, "Error", "Passwords don't match.")

    # ══════════════════════════════════════════════
    # REFRESH
    # ══════════════════════════════════════════════
    def refresh(self):
        # Accounts
        self._refresh_accounts()

        # Categories — show correct icons
        cats = self.lu.list_categories()
        self.cat_table.setRowCount(len(cats))
        for i, c in enumerate(cats):
            cid = c.get("category_id", "")
            icon_val = self._get_cat_icon(cid)
            icon_lbl = QLabel(icon_val)
            icon_lbl.setStyleSheet("font-size:20px;background:transparent;border:none;")
            icon_lbl.setAlignment(Qt.AlignCenter)
            self.cat_table.setCellWidget(i, 0, icon_lbl)
            self.cat_table.setItem(i, 1, QTableWidgetItem(c["display_name"]))
            self.cat_table.setItem(i, 2, QTableWidgetItem(c.get("default_pf_category") or "\u2014"))
            self.cat_table.setItem(i, 3, QTableWidgetItem("Yes" if c.get("tax_deductible") else "No"))
            cl = QLabel("\u25cf")
            cl.setStyleSheet(f"color:{c.get('color_hex') or '#000'};font-size:18px;background:transparent;border:none;")
            self.cat_table.setCellWidget(i, 4, cl)
            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet(f"color:{C['accent']};font-weight:600;background:transparent;border:1px solid {C['border']};border-radius:6px;padding:3px 10px;font-size:11px;")
            edit_btn.setCursor(Qt.PointingHandCursor)
            cat_data = dict(c)
            edit_btn.clicked.connect(lambda _, cd=cat_data: self._edit_category(cd))
            self.cat_table.setCellWidget(i, 5, edit_btn)

        # Payment methods — show ALL (active + inactive)
        methods = [dict(r) for r in self.db.execute(
            "SELECT * FROM payment_methods ORDER BY sort_order").fetchall()]
        self.method_table.setRowCount(len(methods))
        for i, m in enumerate(methods):
            self.method_table.setItem(i, 0, QTableWidgetItem(m["display_name"]))
            active = bool(m.get("is_active", 1))
            status_lbl = QLabel("\u2713 Active" if active else "\u2717 Inactive")
            status_lbl.setStyleSheet(f"color:{C['green'] if active else C['text3']};font-weight:600;font-size:11px;background:transparent;border:none;")
            self.method_table.setCellWidget(i, 1, status_lbl)
            toggle_btn = QPushButton("Deactivate" if active else "Activate")
            toggle_btn.setStyleSheet(f"color:{C['red'] if active else C['green']};font-weight:600;background:transparent;border:1px solid {C['border']};border-radius:6px;padding:3px 10px;font-size:11px;")
            toggle_btn.setCursor(Qt.PointingHandCursor)
            mid = m["method_id"]; cur_active = m.get("is_active", 1)
            toggle_btn.clicked.connect(lambda _, mid=mid, act=cur_active: self._toggle_method(mid, act))
            self.method_table.setCellWidget(i, 2, toggle_btn)

        # Tags
        tags = self.lu.list_tags()
        self.tag_table.setRowCount(len(tags))
        for i, t in enumerate(tags):
            self.tag_table.setItem(i, 0, QTableWidgetItem(t["display_name"]))
            self.tag_table.setItem(i, 1, QTableWidgetItem("\u2713" if t["is_active"] else "\u2717"))

        # Security — smaller toggle
        is_on = self.sec.is_2fa()
        self.totp_lbl.setText("\u2713 TOTP Enabled" if is_on else "\u2717 TOTP Disabled (password required)")
        self.totp_lbl.setStyleSheet(f"color:{C['green'] if is_on else C['amber']};font-weight:600;")
        self.tfa_toggle.setChecked(is_on)
        self.tfa_toggle.setText("ON" if is_on else "OFF")
        self.tfa_toggle.setStyleSheet(
            f"QPushButton{{background:{C['green'] if is_on else C['text3']};color:white;"
            f"border:none;border-radius:14px;padding:2px 16px;font-size:11px;font-weight:700;}}"
            f"QPushButton:hover{{background:{C['green'] if is_on else C['text2']};}}")

        # Google
        if hasattr(self, 'google_status'):
            g_email = self.sec.get_google_email()
            g_linked = self.sec.is_google_linked()
            if g_linked and g_email:
                self.google_status.setText(f"\u2713 Linked: {g_email}")
                self.google_status.setStyleSheet(f"color:{C['green']};font-weight:600;")
                self.google_link_btn.setText("Re-link (new credentials)")
                self.google_unlink_btn.setVisible(True)
            else:
                self.google_status.setText("\u2717 Not linked")
                self.google_status.setStyleSheet(f"color:{C['text3']};font-weight:600;")
                self.google_link_btn.setText("\U0001f517  Link Google Account")
                self.google_unlink_btn.setVisible(False)

        # Preferences
        if hasattr(self, 'pref_page_size'):
            self.pref_page_size.setValue(self._get_pref('complete_page_size', 150))
            self.pref_scroll_trigger.setValue(self._get_pref('scroll_trigger_px', 400))
            self.pref_wealth_page_size.setValue(self._get_pref('wealth_page_size', 150))
            self.pref_wealth_scroll_trigger.setValue(self._get_pref('wealth_scroll_trigger', 400))
            self.pref_notes_page_size.setValue(self._get_pref('notes_page_size', 50))
            self.pref_notes_scroll_trigger.setValue(self._get_pref('notes_scroll_trigger', 200))
            self.pref_txn_alert.setValue(self._get_pref('min_txn_alert', 499))

        # Backup info
        self._refresh_backup_info()
