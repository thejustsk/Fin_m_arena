"""Split Expense UI components — used in Transaction Entry and Wealth tabs."""
import uuid
from datetime import date
from collections import OrderedDict
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame, QComboBox, QDoubleSpinBox,
                              QDateEdit, QLineEdit, QScrollArea, QSizePolicy,
                              QDialog, QFormLayout, QMessageBox, QCheckBox)
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtGui import QCursor
from ui.theme import C
from ui.sidebar import fmt_money
from ui.widgets.searchable_combo import SearchableCombo


def _hex_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ══════════════════════════════════════════════
# SPLIT ENTRY WIDGET (for Transaction Entry tab)
# ══════════════════════════════════════════════
class SplitEntryWidget(QWidget):
    """Split expense entry — group management + expense recording + settlement."""

    def __init__(self, split_repo, parent=None):
        super().__init__(parent)
        self.sr = split_repo
        self._selected_group = None
        self._members = []
        self._share_spins = {}
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # Group selector row
        grp_row = QHBoxLayout()
        grp_row.setSpacing(8)
        grp_row.addWidget(QLabel("Group:"))
        self.group_combo = QComboBox()
        self.group_combo.setMinimumHeight(36)
        self.group_combo.currentIndexChanged.connect(self._on_group_changed)
        grp_row.addWidget(self.group_combo, 1)
        add_grp_btn = QPushButton("+ New Group")
        add_grp_btn.setMinimumHeight(36)
        add_grp_btn.clicked.connect(self._new_group)
        grp_row.addWidget(add_grp_btn)
        lay.addLayout(grp_row)

        # Split: Record Expense
        self._build_expense_section(lay)

        # Split: Record Settlement
        self._build_settlement_section(lay)

        # Recent activity
        self._build_recent(lay)

    def _build_expense_section(self, lay):
        title = QLabel("\U0001f4b0  Record Expense")
        title.setStyleSheet(f"font-size:13px;font-weight:700;color:{C['text']};")
        lay.addWidget(title)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(QLabel("Paid by:"))
        self.paid_by_combo = QComboBox()
        self.paid_by_combo.setMinimumHeight(36)
        row1.addWidget(self.paid_by_combo, 1)
        row1.addWidget(QLabel("Amount:"))
        self.expense_amount = QDoubleSpinBox()
        self.expense_amount.setRange(0, 99999999)
        self.expense_amount.setPrefix("\u20b9 ")
        self.expense_amount.setDecimals(2)
        self.expense_amount.setMinimumHeight(36)
        self.expense_amount.valueChanged.connect(self._on_amount_changed)
        row1.addWidget(self.expense_amount, 1)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel("Desc:"))
        self.expense_desc = QLineEdit()
        self.expense_desc.setPlaceholderText("e.g. Dinner at KFC")
        self.expense_desc.setMinimumHeight(36)
        row2.addWidget(self.expense_desc, 2)
        row2.addWidget(QLabel("Date:"))
        self.expense_date = QDateEdit()
        self.expense_date.setDate(date.today())
        self.expense_date.setMinimumHeight(36)
        row2.addWidget(self.expense_date)
        lay.addLayout(row2)

        # Split type
        split_row = QHBoxLayout()
        split_row.setSpacing(8)
        split_row.addWidget(QLabel("Split:"))
        self.split_type = QComboBox()
        self.split_type.addItems(["Equal", "Custom"])
        self.split_type.setMinimumHeight(36)
        self.split_type.currentIndexChanged.connect(self._on_split_type_changed)
        split_row.addWidget(self.split_type)
        split_row.addStretch()
        lay.addLayout(split_row)

        # Shares area
        self.shares_container = QWidget()
        self.shares_container.setStyleSheet("background:transparent;")
        self.shares_lay = QVBoxLayout(self.shares_container)
        self.shares_lay.setContentsMargins(0, 0, 0, 0)
        self.shares_lay.setSpacing(4)
        lay.addWidget(self.shares_container)

        add_exp_btn = QPushButton("\U0001f4b0  Add Expense")
        add_exp_btn.setObjectName("primary")
        add_exp_btn.setMinimumHeight(42)
        add_exp_btn.clicked.connect(self._add_expense)
        lay.addWidget(add_exp_btn)

    def _build_settlement_section(self, lay):
        lay.addWidget(self._make_sep())

        title = QLabel("\U0001f4b8  Record Settlement")
        title.setStyleSheet(f"font-size:13px;font-weight:700;color:{C['text']};")
        lay.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("From:"))
        self.settle_from = QComboBox()
        self.settle_from.setMinimumHeight(36)
        row.addWidget(self.settle_from, 1)
        row.addWidget(QLabel("To:"))
        self.settle_to = QComboBox()
        self.settle_to.setMinimumHeight(36)
        row.addWidget(self.settle_to, 1)
        row.addWidget(QLabel("Amount:"))
        self.settle_amount = QDoubleSpinBox()
        self.settle_amount.setRange(0, 99999999)
        self.settle_amount.setPrefix("\u20b9 ")
        self.settle_amount.setDecimals(2)
        self.settle_amount.setMinimumHeight(36)
        row.addWidget(self.settle_amount, 1)
        lay.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel("Method:"))
        self.settle_method = QComboBox()
        self.settle_method.addItems(["CASH", "PHONEPAY", "GOOGLE PAY", "BHIM UPI", "NETBANKING", "OTHER"])
        self.settle_method.setMinimumHeight(36)
        row2.addWidget(self.settle_method)
        row2.addStretch()
        settle_btn = QPushButton("\U0001f4b8  Record Settlement")
        settle_btn.setMinimumHeight(38)
        settle_btn.clicked.connect(self._add_settlement)
        row2.addWidget(settle_btn)
        lay.addLayout(row2)

    def _build_recent(self, lay):
        lay.addWidget(self._make_sep())
        title = QLabel("\U0001f4cb  Recent Activity")
        title.setStyleSheet(f"font-size:13px;font-weight:700;color:{C['text']};")
        lay.addWidget(title)
        self.recent_scroll = QScrollArea()
        self.recent_scroll.setWidgetResizable(True)
        self.recent_scroll.setFrameShape(QFrame.NoFrame)
        self.recent_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self.recent_lay = QVBoxLayout(inner)
        self.recent_lay.setContentsMargins(0, 0, 0, 0)
        self.recent_lay.setSpacing(4)
        self.recent_scroll.setWidget(inner)
        lay.addWidget(self.recent_scroll, 1)

    @staticmethod
    def _make_sep():
        f = QFrame(); f.setFixedHeight(1); f.setStyleSheet(f"background:{C['border2']};")
        return f

    def refresh(self):
        self._load_groups()

    def _load_groups(self):
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem("-- Select Group --", None)
        for g in self.sr.list_groups():
            self.group_combo.addItem(g["name"], g["group_id"])
        self.group_combo.blockSignals(False)
        if self.group_combo.count() > 1:
            self.group_combo.setCurrentIndex(1)

    def _on_group_changed(self):
        gid = self.group_combo.currentData()
        self._selected_group = gid
        if not gid:
            self._members = []
            self._clear_shares()
            return
        self._members = self.sr.list_group_members(gid)
        self._populate_combos()
        self._on_split_type_changed()
        self._load_recent()

    def _populate_combos(self):
        for combo in (self.paid_by_combo, self.settle_from, self.settle_to):
            combo.blockSignals(True)
            combo.clear()
            for m in self._members:
                combo.addItem(m["name"], m["contact_id"])
            combo.blockSignals(False)

    def _on_split_type_changed(self):
        self._clear_shares()
        if not self._members:
            return
        is_equal = self.split_type.currentIndex() == 0
        for m in self._members:
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(m["name"])
            lbl.setStyleSheet(f"font-size:12px;color:{C['text']};")
            lbl.setFixedWidth(100)
            row.addWidget(lbl)
            spin = QDoubleSpinBox()
            spin.setRange(0, 99999999)
            spin.setPrefix("\u20b9 ")
            spin.setDecimals(2)
            spin.setMinimumHeight(32)
            spin.setEnabled(not is_equal)
            self._share_spins[m["contact_id"]] = spin
            row.addWidget(spin, 1)
            # Wrap in QWidget so we can clear later
            w = QWidget()
            w.setStyleSheet("background:transparent;")
            w.setLayout(row)
            self.shares_lay.addWidget(w)
        if is_equal:
            self._on_amount_changed()

    def _on_amount_changed(self):
        if self.split_type.currentIndex() != 0:
            return
        amt = self.expense_amount.value()
        n = len(self._members)
        if n == 0:
            return
        share = round(amt / n, 2)
        for i, m in enumerate(self._members):
            spin = self._share_spins.get(m["contact_id"])
            if spin:
                if i == n - 1:
                    spin.setValue(amt - share * (n - 1))
                else:
                    spin.setValue(share)

    def _clear_shares(self):
        while self.shares_lay.count():
            itm = self.shares_lay.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()
        self._share_spins.clear()

    def _add_expense(self):
        if not self._selected_group:
            QMessageBox.warning(self, "No Group", "Select a group first.")
            return
        paid_by = self.paid_by_combo.currentData()
        amount = self.expense_amount.value()
        if not paid_by or amount <= 0:
            QMessageBox.warning(self, "Missing", "Select who paid and enter an amount.")
            return
        shares = []
        for m in self._members:
            spin = self._share_spins.get(m["contact_id"])
            if spin:
                shares.append((m["contact_id"], spin.value()))
        if not shares:
            QMessageBox.warning(self, "No Shares", "No participants to split with.")
            return
        total_shares = sum(s[1] for s in shares)
        if abs(total_shares - amount) > 0.01:
            QMessageBox.warning(self, "Mismatch", f"Shares total ({total_shares}) doesn't match amount ({amount}).")
            return
        split_type = "EQUAL" if self.split_type.currentIndex() == 0 else "EXACT"
        self.sr.create_expense(
            self._selected_group, paid_by, amount,
            self.expense_desc.text().strip() or None,
            self.expense_date.date().toString("yyyy-MM-dd"),
            split_type, shares)
        self.expense_amount.setValue(0)
        self.expense_desc.clear()
        self._load_recent()
        QMessageBox.information(self, "Done", f"Expense of {fmt_money(amount)} recorded.")

    def _add_settlement(self):
        if not self._selected_group:
            QMessageBox.warning(self, "No Group", "Select a group first.")
            return
        from_id = self.settle_from.currentData()
        to_id = self.settle_to.currentData()
        amount = self.settle_amount.value()
        if not from_id or not to_id or amount <= 0:
            QMessageBox.warning(self, "Missing", "Select from, to, and amount.")
            return
        if from_id == to_id:
            QMessageBox.warning(self, "Same", "From and To must be different.")
            return
        self.sr.create_settlement(
            self._selected_group, from_id, to_id, amount,
            date.today().isoformat(), self.settle_method.currentText())
        self.settle_amount.setValue(0)
        self._load_recent()
        QMessageBox.information(self, "Done", f"Settlement of {fmt_money(amount)} recorded.")

    def _load_recent(self):
        while self.recent_lay.count():
            itm = self.recent_lay.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()
        if not self._selected_group:
            return
        expenses = self.sr.list_expenses(self._selected_group)
        settlements = self.sr.list_settlements(self._selected_group)

        # Merge and sort by date
        items = []
        for e in expenses:
            items.append(("expense", e["expense_date"], e))
        for s in settlements:
            items.append(("settlement", s["settle_date"], s))
        items.sort(key=lambda x: x[1], reverse=True)

        for kind, dt, data in items[:15]:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:8px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            cl = QHBoxLayout(card)
            cl.setContentsMargins(12, 8, 12, 8)
            cl.setSpacing(10)

            if kind == "expense":
                icon = QLabel("\U0001f4b0")
                icon.setStyleSheet("font-size:16px;")
                cl.addWidget(icon)
                info = QVBoxLayout()
                info.setSpacing(2)
                desc = data["description"] or "Expense"
                info.addWidget(self._lbl(f"{desc} — paid by {data['paid_by_name']}", C['text'], 12, True))
                info.addWidget(self._lbl(data["expense_date"], C['text3'], 11))
                cl.addLayout(info, 1)
                amt = self._lbl(fmt_money(data["amount"]), C['red'], 14, True)
                cl.addWidget(amt)
            else:
                icon = QLabel("\U0001f4b8")
                icon.setStyleSheet("font-size:16px;")
                cl.addWidget(icon)
                info = QVBoxLayout()
                info.setSpacing(2)
                info.addWidget(self._lbl(f"{data['from_name']} \u2192 {data['to_name']}", C['text'], 12, True))
                info.addWidget(self._lbl(data["settle_date"], C['text3'], 11))
                cl.addLayout(info, 1)
                amt = self._lbl(fmt_money(data["amount"]), C['green'], 14, True)
                cl.addWidget(amt)

            self.recent_lay.addWidget(card)
        self.recent_lay.addStretch()

    @staticmethod
    def _lbl(text, color, size, bold=False):
        l = QLabel(text)
        l.setStyleSheet(f"color:{color};font-size:{size}px;font-weight:{'800' if bold else '500'};")
        return l

    def _new_group(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("New Split Group")
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        name_input = QLineEdit()
        name_input.setPlaceholderText("Group name (e.g. Goa Trip)")
        name_input.setMinimumHeight(38)
        lay.addWidget(name_input)

        lay.addWidget(QLabel("Members:"))
        # Show existing contacts as checkboxes
        contacts = self.sr.list_contacts()
        checks = []
        for c in contacts:
            if c["is_self"]:
                continue
            cb = QCheckBox(c["name"])
            cb.setChecked(True)
            cb.contact_id = c["contact_id"]
            lay.addWidget(cb)
            checks.append(cb)

        # Add new contact
        new_row = QHBoxLayout()
        new_row.setSpacing(6)
        new_name = QLineEdit()
        new_name.setPlaceholderText("New member name")
        new_name.setMinimumHeight(36)
        new_row.addWidget(new_name, 1)
        add_btn = QPushButton("+ Add")
        add_btn.setMinimumHeight(36)
        def _add_contact():
            nm = new_name.text().strip()
            if not nm:
                return
            cid = self.sr.create_contact(nm)
            cb = QCheckBox(nm)
            cb.setChecked(True)
            cb.contact_id = cid
            lay.insertWidget(lay.count() - 2, cb)
            checks.append(cb)
            new_name.clear()
        add_btn.clicked.connect(_add_contact)
        new_row.addWidget(add_btn)
        lay.addLayout(new_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel)
        ok = QPushButton("Create Group")
        ok.setObjectName("primary")
        ok.clicked.connect(dlg.accept)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)

        if dlg.exec_() == QDialog.Accepted:
            gname = name_input.text().strip()
            if not gname:
                QMessageBox.warning(self, "Missing", "Enter a group name.")
                return
            self_id = self.sr.get_self_contact()
            member_ids = [self_id]
            for cb in checks:
                if cb.isChecked():
                    member_ids.append(cb.contact_id)
            self.sr.create_group(gname, member_ids)
            self._load_groups()
            # Select the newly created group
            for i in range(self.group_combo.count()):
                if self.group_combo.itemText(i) == gname:
                    self.group_combo.setCurrentIndex(i)
                    break


# ══════════════════════════════════════════════
# SPLIT QUICK WIDGET (for Transaction Entry tab)
# Simplified: group + expense + settlement, no built-in recent.
# ══════════════════════════════════════════════
class SplitQuickWidget(QWidget):
    """Lightweight split widget for Transaction Entry tab.

    Group selector + expense entry + settlement recording.
    No built-in recent activity — parent's bottom panel handles that.
    Emits ``data_changed`` after expense / settlement so parent can refresh.
    Creates linked transactions with transaction_kind='SPLIT'.
    """

    data_changed = pyqtSignal()

    def __init__(self, repos, parent=None):
        super().__init__(parent)
        self.sr = repos.get("split")
        self.tx_repo = repos.get("transactions")
        self.acct_repo = repos.get("accounts")
        self.lu = repos.get("lookups")
        self.db = repos.get("accounts").db if repos.get("accounts") else None
        self._members = []
        self._share_spins = {}
        self._acct_map = {}
        self._self_id = self.sr.get_self_contact() if self.sr else None
        self._build()

    # ── Build ──────────────────────────────────────────────────
    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # Group selector
        grp_row = QHBoxLayout()
        grp_row.setSpacing(8)
        grp_lbl = QLabel("Group:")
        grp_lbl.setStyleSheet(f"color:{C['text']};font-size:13px;font-weight:600;")
        grp_row.addWidget(grp_lbl)
        self.group_combo = QComboBox()
        self.group_combo.setMinimumHeight(36)
        self.group_combo.currentIndexChanged.connect(self._on_group_changed)
        grp_row.addWidget(self.group_combo, 1)
        add_grp_btn = QPushButton("+ New Group")
        add_grp_btn.setMinimumHeight(36)
        add_grp_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_grp_btn.clicked.connect(self._new_group)
        grp_row.addWidget(add_grp_btn)
        lay.addLayout(grp_row)

        self._build_expense(lay)
        self._build_settlement(lay)

    def _build_expense(self, lay):
        title = QLabel("\U0001f4b0  Record Expense")
        title.setStyleSheet(f"font-size:13px;font-weight:700;color:{C['text']};")
        lay.addWidget(title)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(QLabel("Paid by:"))
        self.paid_by_combo = QComboBox()
        self.paid_by_combo.setMinimumHeight(36)
        row1.addWidget(self.paid_by_combo, 1)
        row1.addWidget(QLabel("Amount:"))
        self.expense_amount = QDoubleSpinBox()
        self.expense_amount.setRange(0, 99999999)
        self.expense_amount.setPrefix("\u20b9 ")
        self.expense_amount.setDecimals(2)
        self.expense_amount.setMinimumHeight(36)
        self.expense_amount.valueChanged.connect(self._on_amount_changed)
        row1.addWidget(self.expense_amount, 1)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel("Desc:"))
        self.expense_desc = QLineEdit()
        self.expense_desc.setPlaceholderText("e.g. Dinner at KFC")
        self.expense_desc.setMinimumHeight(36)
        row2.addWidget(self.expense_desc, 2)
        row2.addWidget(QLabel("Date:"))
        self.expense_date = QDateEdit()
        self.expense_date.setDate(QDate.currentDate())
        self.expense_date.setCalendarPopup(True)
        self.expense_date.setMinimumHeight(36)
        row2.addWidget(self.expense_date)
        lay.addLayout(row2)

        # Account + Method row (for linked transaction)
        row_ac = QHBoxLayout()
        row_ac.setSpacing(8)
        row_ac.addWidget(QLabel("Account:"))
        self.exp_account = QComboBox()
        self.exp_account.setMinimumHeight(36)
        if self.acct_repo:
            for a in self.acct_repo.list_active():
                label = f"{a['display_name']}"
                self.exp_account.addItem(label, a["account_id"])
                self._acct_map[a["account_id"]] = a["display_name"]
        row_ac.addWidget(self.exp_account, 1)
        row_ac.addWidget(QLabel("Method:"))
        self.exp_method = QComboBox()
        self.exp_method.setMinimumHeight(36)
        if self.lu:
            for m in self.lu.list_methods():
                self.exp_method.addItem(m["display_name"], m["method_id"])
        row_ac.addWidget(self.exp_method, 1)
        lay.addLayout(row_ac)

        split_row = QHBoxLayout()
        split_row.setSpacing(8)
        split_row.addWidget(QLabel("Split:"))
        self.split_type = QComboBox()
        self.split_type.addItems(["Equal", "Custom"])
        self.split_type.setMinimumHeight(36)
        self.split_type.currentIndexChanged.connect(self._on_split_type_changed)
        split_row.addWidget(self.split_type)
        split_row.addStretch()
        lay.addLayout(split_row)

        self.shares_container = QWidget()
        self.shares_container.setStyleSheet("background:transparent;")
        self.shares_lay = QVBoxLayout(self.shares_container)
        self.shares_lay.setContentsMargins(0, 0, 0, 0)
        self.shares_lay.setSpacing(4)
        lay.addWidget(self.shares_container)

        add_exp_btn = QPushButton("\U0001f4b0  Add Expense")
        add_exp_btn.setMinimumHeight(42)
        add_exp_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_exp_btn.clicked.connect(self._add_expense)
        lay.addWidget(add_exp_btn)

    def _build_settlement(self, lay):
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C['border2']};")
        lay.addWidget(sep)

        title = QLabel("\U0001f4b8  Record Settlement")
        title.setStyleSheet(f"font-size:13px;font-weight:700;color:{C['text']};")
        lay.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("From:"))
        self.settle_from = QComboBox()
        self.settle_from.setMinimumHeight(36)
        row.addWidget(self.settle_from, 1)
        row.addWidget(QLabel("To:"))
        self.settle_to = QComboBox()
        self.settle_to.setMinimumHeight(36)
        row.addWidget(self.settle_to, 1)
        row.addWidget(QLabel("Amount:"))
        self.settle_amount = QDoubleSpinBox()
        self.settle_amount.setRange(0, 99999999)
        self.settle_amount.setPrefix("\u20b9 ")
        self.settle_amount.setDecimals(2)
        self.settle_amount.setMinimumHeight(36)
        row.addWidget(self.settle_amount, 1)
        lay.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel("Method:"))
        self.settle_method = QComboBox()
        self.settle_method.addItems(["CASH", "PHONEPAY", "GOOGLE PAY", "BHIM UPI", "NETBANKING", "OTHER"])
        self.settle_method.setMinimumHeight(36)
        row2.addWidget(self.settle_method)
        row2.addWidget(QLabel("Account:"))
        self.settle_account = QComboBox()
        self.settle_account.setMinimumHeight(36)
        if self.acct_repo:
            for a in self.acct_repo.list_active():
                self.settle_account.addItem(a["display_name"], a["account_id"])
        row2.addWidget(self.settle_account, 1)
        settle_btn = QPushButton("\U0001f4b8  Record Settlement")
        settle_btn.setMinimumHeight(38)
        settle_btn.setCursor(QCursor(Qt.PointingHandCursor))
        settle_btn.clicked.connect(self._add_settlement)
        row2.addWidget(settle_btn)
        lay.addLayout(row2)

    # ── Refresh ────────────────────────────────────────────────
    def refresh(self):
        self._load_groups()

    def _load_groups(self):
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem("-- Select Group --", None)
        for g in self.sr.list_groups():
            self.group_combo.addItem(g["name"], g["group_id"])
        self.group_combo.blockSignals(False)
        if self.group_combo.count() > 1:
            self.group_combo.setCurrentIndex(1)

    def _on_group_changed(self):
        gid = self.group_combo.currentData()
        if not gid:
            self._members = []
            self._clear_shares()
            return
        self._members = self.sr.list_group_members(gid)
        self._populate_combos()
        self._on_split_type_changed()

    def _populate_combos(self):
        for combo in (self.paid_by_combo, self.settle_from, self.settle_to):
            combo.blockSignals(True)
            combo.clear()
            for m in self._members:
                combo.addItem(m["name"], m["contact_id"])
            combo.blockSignals(False)

    # ── Shares ─────────────────────────────────────────────────
    def _on_split_type_changed(self):
        self._clear_shares()
        if not self._members:
            return
        is_equal = self.split_type.currentIndex() == 0
        for m in self._members:
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(m["name"])
            lbl.setStyleSheet(f"font-size:12px;color:{C['text']};")
            lbl.setFixedWidth(100)
            row.addWidget(lbl)
            spin = QDoubleSpinBox()
            spin.setRange(0, 99999999)
            spin.setPrefix("\u20b9 ")
            spin.setDecimals(2)
            spin.setMinimumHeight(32)
            spin.setEnabled(not is_equal)
            self._share_spins[m["contact_id"]] = spin
            row.addWidget(spin, 1)
            w = QWidget()
            w.setStyleSheet("background:transparent;")
            w.setLayout(row)
            self.shares_lay.addWidget(w)
        if is_equal:
            self._on_amount_changed()

    def _on_amount_changed(self):
        if self.split_type.currentIndex() != 0:
            return
        amt = self.expense_amount.value()
        n = len(self._members)
        if n == 0:
            return
        share = round(amt / n, 2)
        for i, m in enumerate(self._members):
            spin = self._share_spins.get(m["contact_id"])
            if spin:
                if i == n - 1:
                    spin.setValue(amt - share * (n - 1))
                else:
                    spin.setValue(share)

    def _clear_shares(self):
        while self.shares_lay.count():
            itm = self.shares_lay.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()
        self._share_spins.clear()

    # ── Add expense / settlement ───────────────────────────────
    def _add_expense(self):
        gid = self.group_combo.currentData()
        if not gid:
            QMessageBox.warning(self, "No Group", "Select a group first.")
            return
        paid_by = self.paid_by_combo.currentData()
        amount = self.expense_amount.value()
        if not paid_by or amount <= 0:
            QMessageBox.warning(self, "Missing", "Select who paid and enter an amount.")
            return
        shares = []
        for m in self._members:
            spin = self._share_spins.get(m["contact_id"])
            if spin:
                shares.append((m["contact_id"], spin.value()))
        if not shares:
            QMessageBox.warning(self, "No Shares", "No participants to split with.")
            return
        total_shares = sum(s[1] for s in shares)
        if abs(total_shares - amount) > 0.01:
            QMessageBox.warning(self, "Mismatch",
                                f"Shares total ({total_shares}) doesn't match amount ({amount}).")
            return
        split_type = "EQUAL" if self.split_type.currentIndex() == 0 else "EXACT"
        # Create linked transaction ONLY if self paid (money left your account)
        txn_id = None
        if (paid_by == self._self_id and self.tx_repo
                and self.exp_account.currentData() and self.exp_method.currentData()):
            txn_id = self.tx_repo.create(
                tx_date=self.expense_date.date().toString("yyyy-MM-dd"),
                account_id=self.exp_account.currentData(),
                pay_method=self.exp_method.currentData(),
                tx_type="DEBIT", amount=amount,
                person_org=self.expense_desc.text().strip() or "Split expense",
                description=f"Split: {self.expense_desc.text().strip() or 'Expense'}",
                transaction_kind="SPLIT", category="other",
                neednwant=0, pf_category=None)
        self.sr.create_expense(
            gid, paid_by, amount,
            self.expense_desc.text().strip() or None,
            self.expense_date.date().toString("yyyy-MM-dd"),
            split_type, shares, linked_txn_id=txn_id)
        self.expense_amount.setValue(0)
        self.expense_desc.clear()
        self.data_changed.emit()
        QMessageBox.information(self, "Done", f"Expense of {fmt_money(amount)} recorded.")

    def _add_settlement(self):
        gid = self.group_combo.currentData()
        if not gid:
            QMessageBox.warning(self, "No Group", "Select a group first.")
            return
        from_id = self.settle_from.currentData()
        to_id = self.settle_to.currentData()
        amount = self.settle_amount.value()
        if not from_id or not to_id or amount <= 0:
            QMessageBox.warning(self, "Missing", "Select from, to, and amount.")
            return
        if from_id == to_id:
            QMessageBox.warning(self, "Same", "From and To must be different.")
            return
        from datetime import date as _dt
        # Create linked transaction ONLY if self is involved
        txn_id = None
        settle_date = _dt.today().isoformat()
        self_involved = (from_id == self._self_id or to_id == self._self_id)
        if self_involved and self.tx_repo and self.settle_account.currentData():
            # DEBIT if self is paying, CREDIT if self is receiving
            tx_type = "DEBIT" if from_id == self._self_id else "CREDIT"
            txn_id = self.tx_repo.create(
                tx_date=settle_date,
                account_id=self.settle_account.currentData(),
                pay_method=self.settle_method.currentText(),
                tx_type=tx_type, amount=amount,
                person_org=f"{self.settle_from.currentText()} \u2192 {self.settle_to.currentText()}",
                description="Split settlement",
                transaction_kind="SPLIT_SETTLEMENT", category="finance",
                neednwant=0, pf_category=None)
        self.sr.create_settlement(
            gid, from_id, to_id, amount,
            settle_date, self.settle_method.currentText(), linked_txn_id=txn_id)
        self.settle_amount.setValue(0)
        self.data_changed.emit()
        QMessageBox.information(self, "Done", f"Settlement of {fmt_money(amount)} recorded.")

    # ── New group dialog ───────────────────────────────────────
    def _new_group(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("New Split Group")
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        name_input = QLineEdit()
        name_input.setPlaceholderText("Group name (e.g. Goa Trip)")
        name_input.setMinimumHeight(38)
        lay.addWidget(name_input)

        lay.addWidget(QLabel("Members:"))
        contacts = self.sr.list_contacts()
        checks = []
        for c in contacts:
            if c["is_self"]:
                continue
            cb = QCheckBox(c["name"])
            cb.setChecked(True)
            cb.contact_id = c["contact_id"]
            lay.addWidget(cb)
            checks.append(cb)

        new_row = QHBoxLayout()
        new_row.setSpacing(6)
        new_name = QLineEdit()
        new_name.setPlaceholderText("New member name")
        new_name.setMinimumHeight(36)
        new_row.addWidget(new_name, 1)
        add_btn = QPushButton("+ Add")
        add_btn.setMinimumHeight(36)

        def _add_contact():
            nm = new_name.text().strip()
            if not nm:
                return
            cid = self.sr.create_contact(nm)
            cb = QCheckBox(nm)
            cb.setChecked(True)
            cb.contact_id = cid
            lay.insertWidget(lay.count() - 2, cb)
            checks.append(cb)
            new_name.clear()

        add_btn.clicked.connect(_add_contact)
        new_row.addWidget(add_btn)
        lay.addLayout(new_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel)
        ok = QPushButton("Create Group")
        ok.clicked.connect(dlg.accept)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)

        if dlg.exec_() == QDialog.Accepted:
            gname = name_input.text().strip()
            if not gname:
                QMessageBox.warning(self, "Missing", "Enter a group name.")
                return
            self_id = self.sr.get_self_contact()
            member_ids = [self_id]
            for cb in checks:
                if cb.isChecked():
                    member_ids.append(cb.contact_id)
            self.sr.create_group(gname, member_ids)
            self._load_groups()
            for i in range(self.group_combo.count()):
                if self.group_combo.itemText(i) == gname:
                    self.group_combo.setCurrentIndex(i)
                    break
