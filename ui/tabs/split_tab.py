"""Split Expenses — standalone tab under DAILY.

Changes:
1. Violet status card — overall owed/owe across all groups + settled/unsettled counts
2. New group dialog — search + filter checkboxes, add-to-directory, inline errors
3. Inline validation (no popups, no dialog close on error)
4. Overview: Transactions (expenses + settlements combined)
5. Record Expense: 7 fields in 2 lines, Equal/Percentage/Custom with cascading logic
6. Record Settlement: date field, auto-fill from suggestions
7. Both expense & settlement transactions: category=finance, pf_category=commitment
"""
from datetime import date
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QDateEdit, QDoubleSpinBox, QFrame, QScrollArea,
    QStackedWidget, QMessageBox, QDialog, QFormLayout, QCheckBox,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QCursor
from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _switch_tabs


def _hex_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _metric_card(label, value, color=None):
    color = color or C["text"]
    card = QFrame()
    card.setStyleSheet(
        f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;}}"
        f"QLabel{{background:transparent;border:none;}}")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(4)
    v = QLabel(value)
    v.setStyleSheet(f"font-size:18px;font-weight:800;color:{color};")
    l = QLabel(label)
    l.setStyleSheet(f"font-size:10px;color:{C['text3']};font-weight:600;"
                     f"text-transform:uppercase;letter-spacing:0.5px;")
    lay.addWidget(v)
    lay.addWidget(l)
    return card


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()
        child = item.layout()
        if child:
            _clear_layout(child)


# ══════════════════════════════════════════════════════════════════════════
#  SPLIT TAB
# ══════════════════════════════════════════════════════════════════════════
class SplitTab(QWidget):
    """Standalone Split Expenses tab."""

    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self.repos = repos
        self.services = services
        self.sr = repos.get("split")
        self._loaded = False
        self._members = []
        self._share_spins = {}
        self._locked = set()          # contact_ids manually adjusted
        self._suppress_spin = False   # prevent recursive spin updates
        self._current_suggestions = []
        self._self_id = self.sr.get_self_contact() if self.sr else None
        self._build()

    # ═══════════════════════════════════════════════════════════
    #  BUILD
    # ═══════════════════════════════════════════════════════════
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(14)

        hdr = QLabel("\U0001f91d  Split Expenses")
        hdr.setStyleSheet(f"font-size:22px;font-weight:800;color:{C['text']};")
        outer.addWidget(hdr)

        # ── 1. Violet status card ──
        self._build_status_card(outer)

        # ── Group selector ──
        grp_row = QHBoxLayout()
        grp_row.setSpacing(8)
        grp_lbl = QLabel("Group:")
        grp_lbl.setStyleSheet(f"color:{C['text']};font-size:13px;font-weight:600;")
        grp_row.addWidget(grp_lbl)
        self.group_combo = QComboBox()
        self.group_combo.setMinimumHeight(36)
        self.group_combo.currentIndexChanged.connect(self._on_group_changed)
        grp_row.addWidget(self.group_combo, 1)
        new_grp_btn = QPushButton("+ New Group")
        new_grp_btn.setMinimumHeight(36)
        new_grp_btn.setCursor(QCursor(Qt.PointingHandCursor))
        new_grp_btn.clicked.connect(self._new_group)
        grp_row.addWidget(new_grp_btn)
        outer.addLayout(grp_row)

        # Stats row
        self.stats_row = QHBoxLayout()
        outer.addLayout(self.stats_row)

        # Sub-navigation
        nav = QHBoxLayout()
        nav.setSpacing(8)
        self.btn_overview = QPushButton("\U0001f4ca Overview")
        self.btn_expense = QPushButton("\U0001f4b0 Record Expense")
        self.btn_settle = QPushButton("\U0001f4b8 Record Settlement")
        self._sub_btns = [self.btn_overview, self.btn_expense, self.btn_settle]
        for b in self._sub_btns:
            b.setMinimumHeight(34)
            b.setCursor(QCursor(Qt.PointingHandCursor))
            nav.addWidget(b)
        nav.addStretch()
        outer.addLayout(nav)

        self.sub_stack = QStackedWidget()
        outer.addWidget(self.sub_stack, 1)
        self.sub_stack.addWidget(self._build_overview())
        self.sub_stack.addWidget(self._build_expense_form())
        self.sub_stack.addWidget(self._build_settle_form())

        self.btn_overview.clicked.connect(lambda: self._goto(0))
        self.btn_expense.clicked.connect(lambda: self._goto(1))
        self.btn_settle.clicked.connect(lambda: self._goto(2))
        _switch_tabs(self._sub_btns, 0)
        self.sub_stack.setCurrentIndex(0)

    # ═══════════════════════════════════════════════════════════
    #  1. VIOLET STATUS CARD
    # ═══════════════════════════════════════════════════════════
    def _build_status_card(self, parent_lay):
        self.status_card = QFrame()
        self.status_card.setStyleSheet(
            "QFrame{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #7C3AED,stop:1 #4F46E5);"
            "border-radius:14px;}"
            "QLabel{background:transparent;border:none;}")
        sc_lay = QVBoxLayout(self.status_card)
        sc_lay.setContentsMargins(24, 18, 24, 18)
        sc_lay.setSpacing(10)

        title = QLabel("\U0001f91d  YOUR SPLIT STATUS")
        title.setStyleSheet("color:white;font-size:13px;font-weight:700;"
                            "letter-spacing:1px;")
        sc_lay.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(24)

        # Owed to you
        col_owed = QVBoxLayout()
        col_owed.setSpacing(2)
        self.lbl_owed_val = QLabel("\u20b90")
        self.lbl_owed_val.setStyleSheet("color:#A7F3D0;font-size:22px;font-weight:900;")
        col_owed.addWidget(self.lbl_owed_val)
        lbl_owed_h = QLabel("Owed to you")
        lbl_owed_h.setStyleSheet("color:rgba(255,255,255,0.7);font-size:11px;font-weight:600;")
        col_owed.addWidget(lbl_owed_h)
        row.addLayout(col_owed)

        # You owe
        col_owe = QVBoxLayout()
        col_owe.setSpacing(2)
        self.lbl_owe_val = QLabel("\u20b90")
        self.lbl_owe_val.setStyleSheet("color:#FCA5A5;font-size:22px;font-weight:900;")
        col_owe.addWidget(self.lbl_owe_val)
        lbl_owe_h = QLabel("You owe")
        lbl_owe_h.setStyleSheet("color:rgba(255,255,255,0.7);font-size:11px;font-weight:600;")
        col_owe.addWidget(lbl_owe_h)
        row.addLayout(col_owe)

        row.addStretch()

        # Settled
        col_settled = QVBoxLayout()
        col_settled.setSpacing(2)
        self.lbl_settled_val = QLabel("0")
        self.lbl_settled_val.setStyleSheet("color:#A7F3D0;font-size:20px;font-weight:900;")
        col_settled.addWidget(self.lbl_settled_val)
        lbl_settled_h = QLabel("\u2705 Settled")
        lbl_settled_h.setStyleSheet("color:rgba(255,255,255,0.7);font-size:11px;font-weight:600;")
        col_settled.addWidget(lbl_settled_h)
        row.addLayout(col_settled)

        # Unsettled
        col_unset = QVBoxLayout()
        col_unset.setSpacing(2)
        self.lbl_unset_val = QLabel("0")
        self.lbl_unset_val.setStyleSheet("color:#FCA5A5;font-size:20px;font-weight:900;")
        col_unset.addWidget(self.lbl_unset_val)
        lbl_unset_h = QLabel("\u26a0\ufe0f Unsettled")
        lbl_unset_h.setStyleSheet("color:rgba(255,255,255,0.7);font-size:11px;font-weight:600;")
        col_unset.addWidget(lbl_unset_h)
        row.addLayout(col_unset)

        sc_lay.addLayout(row)
        parent_lay.addWidget(self.status_card)

    def _refresh_status_card(self):
        if not self.sr:
            return
        total_owed_to_me = 0.0
        total_i_owe = 0.0
        settled = 0
        unsettled = 0
        for g in self.sr.list_groups():
            balances = self.sr.get_group_balances(g["group_id"])
            my_bal = balances.get(self._self_id, 0)
            if my_bal > 0.01:
                total_owed_to_me += my_bal
                unsettled += 1
            elif my_bal < -0.01:
                total_i_owe += abs(my_bal)
                unsettled += 1
            else:
                settled += 1
        self.lbl_owed_val.setText(fmt_money(total_owed_to_me))
        self.lbl_owe_val.setText(fmt_money(total_i_owe))
        self.lbl_settled_val.setText(str(settled))
        self.lbl_unset_val.setText(str(unsettled))

    # ═══════════════════════════════════════════════════════════
    #  NAVIGATION
    # ═══════════════════════════════════════════════════════════
    def _goto(self, idx):
        _switch_tabs(self._sub_btns, idx)
        self.sub_stack.setCurrentIndex(idx)
        if idx == 0:
            self._refresh_overview()

    def refresh(self):
        self._load_groups()
        self._refresh_status_card()

    def load_list(self, force=False):
        if self._loaded and not force:
            return
        self._loaded = True
        self._load_groups()
        self._refresh_status_card()

    # ═══════════════════════════════════════════════════════════
    #  GROUPS
    # ═══════════════════════════════════════════════════════════
    def _load_groups(self):
        if not self.sr:
            return
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
            self._current_suggestions = []
            return
        self._members = self.sr.list_group_members(gid)
        self._current_suggestions = self.sr.suggest_settlements(gid)
        self._populate_combos()
        self._refresh_overview()
        self._update_shares()

    def _populate_combos(self):
        self._suppress_settle_auto = True
        for combo in (self.exp_paid_by, self.stl_from, self.stl_to):
            combo.blockSignals(True)
            combo.clear()
            for m in self._members:
                combo.addItem(m["name"], m["contact_id"])
            combo.blockSignals(False)
        self._suppress_settle_auto = False

    # ═══════════════════════════════════════════════════════════
    #  4. OVERVIEW  (balance matrix + suggestions + transactions)
    # ═══════════════════════════════════════════════════════════
    def _build_overview(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self.overview_lay = QVBoxLayout(inner)
        self.overview_lay.setContentsMargins(0, 0, 0, 0)
        self.overview_lay.setSpacing(10)
        scroll.setWidget(inner)
        lay.addWidget(scroll)
        return page

    def _refresh_overview(self):
        gid = self.group_combo.currentData()
        if not gid or not self.sr:
            return
        _clear_layout(self.overview_lay)

        # Stats
        summary = self.sr.get_group_summary(gid)
        _clear_layout(self.stats_row)
        self.stats_row.addWidget(
            _metric_card("Total Expenses", fmt_money(summary["total_expenses"]), C["accent"]))
        self.stats_row.addWidget(
            _metric_card("Pending", fmt_money(summary["total_pending"]), C["amber"]))
        self.stats_row.addWidget(
            _metric_card("Settled", fmt_money(summary["total_settled"]), C["green"]))

        # Balance matrix
        bal_title = QLabel("\U0001f4ca Balance Matrix")
        bal_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        self.overview_lay.addWidget(bal_title)

        balances = self.sr.get_group_balances(gid)
        contacts = {c["contact_id"]: c["name"] for c in self.sr.list_contacts()}

        if balances:
            for cid, balance in sorted(balances.items(), key=lambda x: -x[1]):
                name = contacts.get(cid, "?")
                card = QFrame()
                if balance > 0.01:
                    card.setStyleSheet(
                        f"QFrame{{background:{_hex_rgba(C['green'], 0.08)};"
                        f"border:1px solid {C['green']};border-radius:8px;}}"
                        f"QLabel{{background:transparent;border:none;}}")
                    text = f"{name} is owed {fmt_money(balance)}"
                    color = C["green"]
                elif balance < -0.01:
                    card.setStyleSheet(
                        f"QFrame{{background:{_hex_rgba(C['red'], 0.08)};"
                        f"border:1px solid {C['red']};border-radius:8px;}}"
                        f"QLabel{{background:transparent;border:none;}}")
                    text = f"{name} owes {fmt_money(abs(balance))}"
                    color = C["red"]
                else:
                    card.setStyleSheet(
                        f"QFrame{{background:{C['surface']};"
                        f"border:1px solid {C['border2']};border-radius:8px;}}"
                        f"QLabel{{background:transparent;border:none;}}")
                    text = f"{name} \u2014 settled"
                    color = C["text3"]
                cl = QHBoxLayout(card)
                cl.setContentsMargins(12, 8, 12, 8)
                lbl = QLabel(text)
                lbl.setStyleSheet(f"font-size:13px;font-weight:700;color:{color};")
                cl.addWidget(lbl)
                self.overview_lay.addWidget(card)

        # Settlement suggestions
        sug_title = QLabel("\U0001f4a1 Settlement Suggestions")
        sug_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        self.overview_lay.addWidget(sug_title)

        suggestions = self.sr.suggest_settlements(gid)
        if suggestions:
            for from_id, from_name, to_id, to_name, amount in suggestions:
                card = QFrame()
                card.setStyleSheet(
                    f"QFrame{{background:{_hex_rgba(C['accent'], 0.06)};"
                    f"border:1px solid {_hex_rgba(C['accent'], 0.2)};border-radius:8px;}}"
                    f"QLabel{{background:transparent;border:none;}}")
                cl = QHBoxLayout(card)
                cl.setContentsMargins(12, 8, 12, 8)
                lbl = QLabel(f"{from_name}  \u2192  {to_name}")
                lbl.setStyleSheet(f"font-size:13px;font-weight:700;color:{C['text']};")
                cl.addWidget(lbl, 1)
                amt = QLabel(fmt_money(amount))
                amt.setStyleSheet(f"font-size:14px;font-weight:800;color:{C['accent']};")
                cl.addWidget(amt)
                self.overview_lay.addWidget(card)
        else:
            lbl = QLabel("All settled! No transfers needed.")
            lbl.setStyleSheet(f"color:{C['green']};font-size:12px;font-weight:600;")
            self.overview_lay.addWidget(lbl)

        # ── 4. Transactions (expenses + settlements combined) ──
        txn_title = QLabel("\U0001f4cb Transactions")
        txn_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        self.overview_lay.addWidget(txn_title)

        expenses = self.sr.list_expenses(gid)
        settlements = self.sr.list_settlements(gid)
        items = []
        for e in expenses:
            items.append(("expense", e["expense_date"], e))
        for s in settlements:
            items.append(("settlement", s["settle_date"], s))
        items.sort(key=lambda x: x[1], reverse=True)

        if items:
            for kind, dt, data in items[:20]:
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
                    info_v = QVBoxLayout()
                    info_v.setSpacing(2)
                    desc = data["description"] or "Expense"
                    t1 = QLabel(f"{desc} \u2014 paid by {data['paid_by_name']}")
                    t1.setStyleSheet(f"color:{C['text']};font-size:12px;font-weight:800;")
                    info_v.addWidget(t1)
                    t2 = QLabel(data["expense_date"])
                    t2.setStyleSheet(f"color:{C['text3']};font-size:11px;")
                    info_v.addWidget(t2)
                    cl.addLayout(info_v, 1)
                    amt = QLabel(fmt_money(data["amount"]))
                    amt.setStyleSheet(f"color:{C['red']};font-size:14px;font-weight:800;")
                    cl.addWidget(amt)
                else:
                    icon = QLabel("\U0001f4b8")
                    icon.setStyleSheet("font-size:16px;")
                    cl.addWidget(icon)
                    info_v = QVBoxLayout()
                    info_v.setSpacing(2)
                    t1 = QLabel(f"{data['from_name']}  \u2192  {data['to_name']}")
                    t1.setStyleSheet(f"color:{C['text']};font-size:12px;font-weight:800;")
                    info_v.addWidget(t1)
                    t2 = QLabel(data["settle_date"])
                    t2.setStyleSheet(f"color:{C['text3']};font-size:11px;")
                    info_v.addWidget(t2)
                    cl.addLayout(info_v, 1)
                    amt = QLabel(fmt_money(data["amount"]))
                    amt.setStyleSheet(f"color:{C['green']};font-size:14px;font-weight:800;")
                    cl.addWidget(amt)
                self.overview_lay.addWidget(card)
        else:
            lbl = QLabel("No transactions yet.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            self.overview_lay.addWidget(lbl)

        self.overview_lay.addStretch()

    # ═══════════════════════════════════════════════════════════
    #  5. EXPENSE FORM  (7 fields in 2 lines, cascading splits)
    # ═══════════════════════════════════════════════════════════
    def _build_expense_form(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(8)

        # Line 1: Paid by | Amount | Date | Split Type
        line1 = QHBoxLayout()
        line1.setSpacing(8)
        line1.addWidget(QLabel("Paid by:"))
        self.exp_paid_by = QComboBox()
        self.exp_paid_by.setMinimumHeight(36)
        line1.addWidget(self.exp_paid_by, 2)
        line1.addWidget(QLabel("Amount:"))
        self.exp_amount = QDoubleSpinBox()
        self.exp_amount.setRange(0, 99999999)
        self.exp_amount.setPrefix("\u20b9 ")
        self.exp_amount.setDecimals(2)
        self.exp_amount.setMinimumHeight(36)
        self.exp_amount.valueChanged.connect(self._on_exp_amount_changed)
        line1.addWidget(self.exp_amount, 1)
        line1.addWidget(QLabel("Date:"))
        self.exp_date = QDateEdit(QDate.currentDate())
        self.exp_date.setCalendarPopup(True)
        self.exp_date.setMinimumHeight(36)
        line1.addWidget(self.exp_date, 1)
        line1.addWidget(QLabel("Split:"))
        self.exp_split_type = QComboBox()
        self.exp_split_type.addItems(["Equal", "Percentage", "Custom Amount"])
        self.exp_split_type.setMinimumHeight(36)
        self.exp_split_type.currentIndexChanged.connect(self._on_split_type_changed)
        line1.addWidget(self.exp_split_type, 1)
        lay.addLayout(line1)

        # Line 2: Account | Method | Description
        line2 = QHBoxLayout()
        line2.setSpacing(8)
        line2.addWidget(QLabel("Account:"))
        self.exp_account = QComboBox()
        self.exp_account.setMinimumHeight(36)
        for a in self.repos["accounts"].list_active():
            self.exp_account.addItem(a["display_name"], a["account_id"])
        line2.addWidget(self.exp_account, 2)
        line2.addWidget(QLabel("Method:"))
        self.exp_method = QComboBox()
        self.exp_method.setMinimumHeight(36)
        for m in self.repos["lookups"].list_methods():
            self.exp_method.addItem(m["display_name"], m["method_id"])
        line2.addWidget(self.exp_method, 1)
        line2.addWidget(QLabel("Desc:"))
        self.exp_desc = QLineEdit()
        self.exp_desc.setPlaceholderText("e.g. Dinner at KFC")
        self.exp_desc.setMinimumHeight(36)
        line2.addWidget(self.exp_desc, 2)
        lay.addLayout(line2)

        # Instruction
        self._split_instruction = QLabel(
            "Adjust any value below \u2014 remaining auto-distributes equally to others")
        self._split_instruction.setStyleSheet(
            f"color:{C['text3']};font-size:11px;font-style:italic;padding:2px 0;")
        lay.addWidget(self._split_instruction)

        # Shares area
        self.shares_container = QWidget()
        self.shares_container.setStyleSheet("background:transparent;")
        self.shares_lay = QVBoxLayout(self.shares_container)
        self.shares_lay.setContentsMargins(0, 0, 0, 0)
        self.shares_lay.setSpacing(4)
        lay.addWidget(self.shares_container)

        add_btn = QPushButton("\U0001f4b0  Add Expense")
        add_btn.setObjectName("primary")
        add_btn.setMinimumHeight(42)
        add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_btn.clicked.connect(self._add_expense)
        lay.addWidget(add_btn)

        lay.addStretch()
        return page

    # ── Shares UI ──────────────────────────────────────────────
    def _on_split_type_changed(self):
        self._clear_shares()
        self._locked.clear()
        if not self._members:
            return
        mode = self.exp_split_type.currentIndex()  # 0=Equal 1=Pct 2=Custom
        is_equal = (mode == 0)
        is_pct = (mode == 1)

        # Update instruction
        if is_equal:
            self._split_instruction.setText(
                "Equal split \u2014 amounts auto-calculated from total")
        elif is_pct:
            self._split_instruction.setText(
                "Adjust percentages below \u2014 remaining auto-distributes equally to others")
        else:
            self._split_instruction.setText(
                "Adjust amounts below \u2014 remaining auto-distributes equally to others")

        for m in self._members:
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(m["name"])
            lbl.setStyleSheet(f"font-size:12px;color:{C['text']};")
            lbl.setFixedWidth(100)
            row.addWidget(lbl)

            if is_pct:
                spin = QDoubleSpinBox()
                spin.setRange(0, 100)
                spin.setDecimals(1)
                spin.setSuffix(" %")
            else:
                spin = QDoubleSpinBox()
                spin.setRange(0, 99999999)
                spin.setPrefix("\u20b9 ")
                spin.setDecimals(2)
            spin.setMinimumHeight(32)
            spin.setEnabled(not is_equal)
            self._share_spins[m["contact_id"]] = spin
            row.addWidget(spin, 1)

            if not is_equal:
                spin.valueChanged.connect(
                    lambda val, cid=m["contact_id"]: self._on_spin_changed(cid, val))

            w = QWidget()
            w.setStyleSheet("background:transparent;")
            w.setLayout(row)
            self.shares_lay.addWidget(w)

        self._recalc_shares()

    def _on_spin_changed(self, contact_id, value):
        if self._suppress_spin:
            return
        self._locked.add(contact_id)
        self._recalc_shares()

    def _recalc_shares(self):
        mode = self.exp_split_type.currentIndex()
        if mode == 0:
            # Equal: distribute amount equally
            total = self.exp_amount.value()
            n = len(self._members)
            if n == 0:
                return
            share = total / n
            self._suppress_spin = True
            for i, m in enumerate(self._members):
                spin = self._share_spins.get(m["contact_id"])
                if spin:
                    if i == n - 1:
                        spin.setValue(round(total - round(share, 2) * (n - 1), 2))
                    else:
                        spin.setValue(round(share, 2))
            self._suppress_spin = False
            return

        # Percentage or Custom Amount
        total = 100.0 if mode == 1 else self.exp_amount.value()
        locked_sum = 0.0
        unlocked = []
        for m in self._members:
            cid = m["contact_id"]
            spin = self._share_spins.get(cid)
            if not spin:
                continue
            if cid in self._locked:
                locked_sum += spin.value()
            else:
                unlocked.append(spin)

        remaining = max(total - locked_sum, 0.0)
        if not unlocked:
            return

        n = len(unlocked)
        share = remaining / n
        self._suppress_spin = True
        for i, spin in enumerate(unlocked):
            if i == n - 1:
                spin.setValue(round(remaining - round(share, 2) * (n - 1), 2))
            else:
                spin.setValue(round(share, 2))
        self._suppress_spin = False

    def _on_exp_amount_changed(self):
        mode = self.exp_split_type.currentIndex()
        if mode == 2:  # Custom Amount — recalc unlocked
            self._recalc_shares()

    def _clear_shares(self):
        while self.shares_lay.count():
            itm = self.shares_lay.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()
        self._share_spins.clear()
        self._locked.clear()

    def _update_shares(self):
        self._clear_shares()
        self._on_split_type_changed()

    # ═══════════════════════════════════════════════════════════
    #  6. SETTLEMENT FORM  (with date + auto-fill from suggestions)
    # ═══════════════════════════════════════════════════════════
    def _build_settle_form(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(8)

        # Line 1: From | To | Amount | Date
        line1 = QHBoxLayout()
        line1.setSpacing(8)
        line1.addWidget(QLabel("From:"))
        self.stl_from = QComboBox()
        self.stl_from.setMinimumHeight(36)
        self.stl_from.currentIndexChanged.connect(self._on_settle_combo_changed)
        line1.addWidget(self.stl_from, 2)
        line1.addWidget(QLabel("To:"))
        self.stl_to = QComboBox()
        self.stl_to.setMinimumHeight(36)
        self.stl_to.currentIndexChanged.connect(self._on_settle_combo_changed)
        line1.addWidget(self.stl_to, 2)
        line1.addWidget(QLabel("Amount:"))
        self.stl_amount = QDoubleSpinBox()
        self.stl_amount.setRange(0, 99999999)
        self.stl_amount.setPrefix("\u20b9 ")
        self.stl_amount.setDecimals(2)
        self.stl_amount.setMinimumHeight(36)
        line1.addWidget(self.stl_amount, 1)
        line1.addWidget(QLabel("Date:"))
        self.stl_date = QDateEdit(QDate.currentDate())
        self.stl_date.setCalendarPopup(True)
        self.stl_date.setMinimumHeight(36)
        line1.addWidget(self.stl_date, 1)
        lay.addLayout(line1)

        # Line 2: Method | Account
        line2 = QHBoxLayout()
        line2.setSpacing(8)
        line2.addWidget(QLabel("Method:"))
        self.stl_method = QComboBox()
        self.stl_method.addItems(
            ["CASH", "PHONEPAY", "GOOGLE PAY", "BHIM UPI", "NETBANKING", "OTHER"])
        self.stl_method.setMinimumHeight(36)
        line2.addWidget(self.stl_method, 1)
        line2.addWidget(QLabel("Account:"))
        self.stl_account = QComboBox()
        self.stl_account.setMinimumHeight(36)
        for a in self.repos["accounts"].list_active():
            self.stl_account.addItem(a["display_name"], a["account_id"])
        line2.addWidget(self.stl_account, 2)
        lay.addLayout(line2)

        settle_btn = QPushButton("\U0001f4b8  Record Settlement")
        settle_btn.setMinimumHeight(42)
        settle_btn.setCursor(QCursor(Qt.PointingHandCursor))
        settle_btn.clicked.connect(self._add_settlement)
        lay.addWidget(settle_btn)

        lay.addStretch()
        return page

    def _on_settle_combo_changed(self):
        if getattr(self, '_suppress_settle_auto', False):
            return
        from_id = self.stl_from.currentData()
        to_id = self.stl_to.currentData()
        if not from_id or not to_id or from_id == to_id:
            return
        for f_id, f_name, t_id, t_name, amount in self._current_suggestions:
            if f_id == from_id and t_id == to_id:
                self.stl_amount.setValue(amount)
                return

    # ═══════════════════════════════════════════════════════════
    #  ACTIONS
    # ═══════════════════════════════════════════════════════════
    def _add_expense(self):
        gid = self.group_combo.currentData()
        if not gid:
            QMessageBox.warning(self, "No Group", "Select a group first.")
            return
        paid_by = self.exp_paid_by.currentData()
        amount = self.exp_amount.value()
        if not paid_by or amount <= 0:
            QMessageBox.warning(self, "Missing", "Select who paid and enter an amount.")
            return

        mode = self.exp_split_type.currentIndex()
        shares = []
        for m in self._members:
            spin = self._share_spins.get(m["contact_id"])
            if spin:
                if mode == 1:  # Percentage → convert to amount
                    shares.append((m["contact_id"], round(amount * spin.value() / 100, 2)))
                else:
                    shares.append((m["contact_id"], spin.value()))

        if not shares:
            QMessageBox.warning(self, "No Shares", "No participants to split with.")
            return
        total_shares = sum(s[1] for s in shares)
        if abs(total_shares - amount) > 0.5:
            QMessageBox.warning(self, "Mismatch",
                                f"Shares total ({total_shares:.2f}) doesn't match amount ({amount:.2f}).")
            return

        split_type = ["EQUAL", "PERCENTAGE", "EXACT"][mode]

        # 7. Linked transaction ONLY if self paid, category=finance, pf=commitment
        txn_id = None
        tx_repo = self.repos.get("transactions")
        if (paid_by == self._self_id and tx_repo
                and self.exp_account.currentData() and self.exp_method.currentData()):
            txn_id = tx_repo.create(
                tx_date=self.exp_date.date().toString("yyyy-MM-dd"),
                account_id=self.exp_account.currentData(),
                pay_method=self.exp_method.currentData(),
                tx_type="DEBIT", amount=amount,
                person_org=self.exp_desc.text().strip() or "Split expense",
                description=f"Split: {self.exp_desc.text().strip() or 'Expense'}",
                transaction_kind="SPLIT", category="finance",
                neednwant=0, pf_category="commitment")
        self.sr.create_expense(
            gid, paid_by, amount,
            self.exp_desc.text().strip() or None,
            self.exp_date.date().toString("yyyy-MM-dd"),
            split_type, shares, linked_txn_id=txn_id)
        self.exp_amount.setValue(0)
        self.exp_desc.clear()
        self._refresh_overview()
        self._refresh_status_card()
        QMessageBox.information(self, "Done", f"Expense of {fmt_money(amount)} recorded.")

    def _add_settlement(self):
        gid = self.group_combo.currentData()
        if not gid:
            QMessageBox.warning(self, "No Group", "Select a group first.")
            return
        from_id = self.stl_from.currentData()
        to_id = self.stl_to.currentData()
        amount = self.stl_amount.value()
        if not from_id or not to_id or amount <= 0:
            QMessageBox.warning(self, "Missing", "Select from, to, and amount.")
            return
        if from_id == to_id:
            QMessageBox.warning(self, "Same", "From and To must be different.")
            return

        settle_date = self.stl_date.date().toString("yyyy-MM-dd")

        # 7. Linked transaction ONLY if self involved, category=finance, pf=commitment
        txn_id = None
        tx_repo = self.repos.get("transactions")
        self_involved = (from_id == self._self_id or to_id == self._self_id)
        if self_involved and tx_repo and self.stl_account.currentData():
            tx_type = "DEBIT" if from_id == self._self_id else "CREDIT"
            txn_id = tx_repo.create(
                tx_date=settle_date,
                account_id=self.stl_account.currentData(),
                pay_method=self.stl_method.currentText(),
                tx_type=tx_type, amount=amount,
                person_org=f"{self.stl_from.currentText()} \u2192 {self.stl_to.currentText()}",
                description="Split settlement",
                transaction_kind="SPLIT_SETTLEMENT", category="finance",
                neednwant=0, pf_category="commitment")
        self.sr.create_settlement(
            gid, from_id, to_id, amount,
            settle_date, self.stl_method.currentText(), linked_txn_id=txn_id)
        self.stl_amount.setValue(0)
        self._refresh_overview()
        self._refresh_status_card()
        QMessageBox.information(self, "Done", f"Settlement of {fmt_money(amount)} recorded.")

    # ═══════════════════════════════════════════════════════════
    #  2 & 3. NEW GROUP DIALOG  (search + inline validation)
    # ═══════════════════════════════════════════════════════════
    def _new_group(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("New Split Group")
        dlg.setMinimumWidth(440)
        dlg.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        # Group name
        name_input = QLineEdit()
        name_input.setPlaceholderText("Group name (e.g. Goa Trip)")
        name_input.setMinimumHeight(38)
        lay.addWidget(name_input)

        # Search contacts
        search_input = QLineEdit()
        search_input.setPlaceholderText("\U0001f50d Search contacts to add...")
        search_input.setMinimumHeight(36)
        lay.addWidget(search_input)

        # Checkbox list (filtered by search)
        checks_scroll = QScrollArea()
        checks_scroll.setWidgetResizable(True)
        checks_scroll.setFrameShape(QFrame.NoFrame)
        checks_scroll.setMaximumHeight(200)
        checks_inner = QWidget()
        checks_inner.setStyleSheet("background:transparent;")
        checks_lay = QVBoxLayout(checks_inner)
        checks_lay.setContentsMargins(0, 0, 0, 0)
        checks_lay.setSpacing(4)
        checks_scroll.setWidget(checks_inner)
        lay.addWidget(checks_scroll)

        # Build checkboxes from existing contacts
        all_contacts = self.sr.list_contacts() if self.sr else []
        contact_cbs = []  # (checkbox, name_lower)
        for c in all_contacts:
            if c["is_self"]:
                continue
            cb = QCheckBox(c["name"])
            cb.contact_id = c["contact_id"]
            cb.setChecked(False)
            cb.setVisible(False)  # hidden until search matches
            checks_lay.addWidget(cb)
            contact_cbs.append((cb, c["name"].lower()))

        # Add-new-contact row (hidden by default)
        add_new_row = QWidget()
        add_new_row.setStyleSheet("background:transparent;")
        anr_lay = QHBoxLayout(add_new_row)
        anr_lay.setContentsMargins(0, 0, 0, 0)
        anr_lay.setSpacing(6)
        new_contact_input = QLineEdit()
        new_contact_input.setPlaceholderText("New contact name")
        new_contact_input.setMinimumHeight(34)
        anr_lay.addWidget(new_contact_input, 1)
        add_contact_btn = QPushButton("+ Add to Contacts")
        add_contact_btn.setMinimumHeight(34)
        add_contact_btn.setCursor(QCursor(Qt.PointingHandCursor))
        anr_lay.addWidget(add_contact_btn)
        add_new_row.setVisible(False)
        checks_lay.addWidget(add_new_row)

        def _filter(search_text):
            s = search_text.strip().lower()
            any_match = False
            for cb, name_l in contact_cbs:
                if cb.isChecked():
                    cb.setVisible(True)  # always show checked
                    any_match = True
                else:
                    match = bool(s) and s in name_l
                    cb.setVisible(match)
                    if match:
                        any_match = True
            # Show "add new" if search text has no match
            show_add = bool(s) and not any_match
            add_new_row.setVisible(show_add)
            if show_add:
                new_contact_input.setText(search_text.strip())
            error_lbl.hide()

        search_input.textChanged.connect(_filter)

        def _add_new_contact():
            nm = new_contact_input.text().strip()
            if not nm:
                return
            cid = self.sr.create_contact(nm)
            cb = QCheckBox(nm)
            cb.contact_id = cid
            cb.setChecked(True)
            checks_lay.insertWidget(checks_lay.count() - 1, cb)
            contact_cbs.append((cb, nm.lower()))
            new_contact_input.clear()
            search_input.clear()
            # Show the new checkbox
            for c, _ in contact_cbs:
                c.setVisible(c.isChecked())

        add_contact_btn.clicked.connect(_add_new_contact)
        new_contact_input.returnPressed.connect(_add_new_contact)

        # Error label (inline, red)
        error_lbl = QLabel("")
        error_lbl.setStyleSheet(f"color:{C['red']};font-size:12px;font-weight:600;")
        error_lbl.hide()
        lay.addWidget(error_lbl)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel)
        ok = QPushButton("Create Group")
        ok.clicked.connect(lambda: _try_create())
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)

        def _try_create():
            gname = name_input.text().strip()
            selected = [cb for cb, _ in contact_cbs if cb.isChecked()]
            if not gname:
                error_lbl.setText("\u26a0 Enter a group name.")
                error_lbl.show()
                return
            if not selected:
                error_lbl.setText("\u26a0 Select at least one member.")
                error_lbl.show()
                return
            self_id = self.sr.get_self_contact()
            member_ids = [self_id] + [cb.contact_id for cb in selected]
            self.sr.create_group(gname, member_ids)
            dlg.accept()
            self._load_groups()
            self._refresh_status_card()
            for i in range(self.group_combo.count()):
                if self.group_combo.itemText(i) == gname:
                    self.group_combo.setCurrentIndex(i)
                    break

        dlg.exec_()
