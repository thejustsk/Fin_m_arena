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
from ui.widgets.searchable_combo import SearchableCombo
from ui.widgets.count_up import animate_value


def _hex_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _export_split_pdf(parent, title, status, info_pairs, analysis_pairs, sections=None):
    """Save a Split overview PDF — same secured template the Wealth tab uses."""
    from PyQt5.QtWidgets import QFileDialog
    safe = "".join(c for c in title if c.isalnum() or c in " -_")[:60]
    filepath, _ = QFileDialog.getSaveFileName(
        parent, "Save PDF", f"{safe}.pdf", "PDF Files (*.pdf)")
    if not filepath:
        return
    try:
        from services.report_service import export_detail_pdf
        doc_id = export_detail_pdf(filepath, title, status,
                                   info_pairs, analysis_pairs, sections)
    except Exception as e:
        QMessageBox.warning(parent, "Error", f"Failed to generate PDF.\n{e}")
        return
    if not doc_id:
        QMessageBox.warning(
            parent, "Error",
            "Failed to generate PDF. Make sure reportlab is installed:\n"
            "pip install reportlab")
        return
    box = QMessageBox(parent)
    box.setWindowTitle("PDF Saved")
    box.setText(f"Document ID: {doc_id}\nSaved to: {filepath}")
    box.setInformativeText("Would you like to open the PDF?")
    open_btn = box.addButton("Open PDF", QMessageBox.AcceptRole)
    box.addButton("Close", QMessageBox.RejectRole)
    box.exec_()
    if box.clickedButton() is open_btn:
        import os, sys
        try:
            if sys.platform == "win32":
                os.startfile(filepath)
            elif sys.platform == "darwin":
                os.system(f"open '{filepath}'")
            else:
                os.system(f"xdg-open '{filepath}'")
        except Exception:
            pass


def _metric_card(label, value, color=None):
    color = color or C["text"]
    card = QFrame()
    card.setStyleSheet(
        f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;}}"
        f"QLabel{{background:transparent;border:none;}}")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(4)
    v = QLabel()
    v.setStyleSheet(f"font-size:18px;font-weight:800;color:{color};")
    if isinstance(value, (int, float)):
        animate_value(v, value, fmt_money, old_value=0)
    else:
        v.setText(str(value))
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
        self.group_combo = SearchableCombo(placeholder="Search group\u2026")
        self.group_combo.setMinimumHeight(36)
        self.group_combo.currentIndexChanged.connect(self._on_group_changed)
        grp_row.addWidget(self.group_combo, 1)
        new_grp_btn = QPushButton("\uff0b New Group")
        new_grp_btn.setMinimumHeight(36)
        new_grp_btn.setCursor(QCursor(Qt.PointingHandCursor))
        new_grp_btn.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:white;border:none;"
            f"border-radius:8px;padding:8px 16px;font-size:13px;font-weight:700;}}"
            f"QPushButton:hover{{background:#4338CA;}}")
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

        # Print the whole Overview for the selected group
        self.btn_print = QPushButton("\U0001f5a8  Print")
        self.btn_print.setMinimumHeight(34)
        self.btn_print.setFocusPolicy(Qt.NoFocus)
        self.btn_print.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_print.setToolTip("Export this group's overview as a PDF")
        self.btn_print.setStyleSheet(
            f"QPushButton{{background:{C['surface']};color:{C['accent']};"
            f"border:1.5px solid {C['accent']};border-radius:8px;"
            f"padding:8px 16px;font-size:13px;font-weight:700;}}"
            f"QPushButton:hover{{background:{C['accent']};color:white;}}")
        self.btn_print.clicked.connect(self._print_overview)
        nav.addWidget(self.btn_print)

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
    #  PRINT OVERVIEW → PDF
    # ═══════════════════════════════════════════════════════════
    def _print_overview(self):
        """Export everything shown on the Overview page for the current group.

        Mirrors the on-screen order: the 3 KPI boxes, then Balance Matrix,
        Settlement Suggestions and Transactions — using the same colours the
        UI uses, and the app's standard secured PDF (Doc ID, hash, watermark,
        QR verification page).
        """
        if not self.sr:
            return
        gid = self.group_combo.get_data()
        if not gid:
            QMessageBox.information(self, "No Group",
                                    "Select a group before printing.")
            return

        # Identity check — same gate used for wealth/audit edits.
        sec = self.services.get("security") if isinstance(self.services, dict) else None
        if sec is not None:
            try:
                from ui.wealth_verify import WealthEditVerifyDialog
                if not WealthEditVerifyDialog.verify_user(sec, self):
                    return
            except Exception:
                pass

        group_name = self.group_combo.currentText()
        expenses = self.sr.list_expenses(gid)
        settlements = self.sr.list_settlements(gid)
        balances = self.sr.get_group_balances(gid)
        contacts = {c["contact_id"]: self.sr.display_name_for(c)
                    for c in self.sr.list_contacts()}

        # ── The 3 KPI boxes, identical maths to _refresh_overview ──
        total_expenses = sum(e["amount"] for e in expenses)
        total_pending = sum(b for b in balances.values() if b > 0.01)
        total_settled = sum(s["amount"] for s in settlements)
        analysis = [
            ("Total Expenses", fmt_money(total_expenses)),
            ("Pending", fmt_money(total_pending)),
            ("Settled", fmt_money(total_settled)),
        ]

        members = self.sr.list_group_members(gid)
        info = [
            ("Group", group_name),
            ("Members", str(len(members))),
            ("Transactions", str(len(expenses) + len(settlements))),
            ("Expenses", str(len(expenses))),
            ("Settlements", str(len(settlements))),
            ("Generated", date.today().isoformat()),
        ]

        sections = []

        # ── Balance Matrix ──
        bal_rows = []
        self_label = self.sr.self_display_name()
        for cid, bal in sorted(balances.items(), key=lambda x: -x[1]):
            name = contacts.get(cid, "?")
            # "You is owed" reads wrong — use second person for the self row.
            is_self = (name == self_label)
            if bal > 0.01:
                desc = "are owed" if is_self else "is owed"
                amt = bal
            elif bal < -0.01:
                desc = "owe" if is_self else "owes"
                amt = abs(bal)
            else:
                desc = "settled up"
                amt = 0
            bal_rows.append({"date": name, "amount": amt, "description": desc})
        if bal_rows:
            sections.append({"title": "\U0001f4ca  Balance Matrix", "color": "#4F46E5",
                             "type": "repayment", "data": bal_rows})

        # ── Settlement Suggestions ──
        sug_rows = []
        for _fid, fn, _tid, tn, amount in self.sr.suggest_settlements(gid):
            sug_rows.append({"date": f"{fn}  \u2192  {tn}", "amount": amount,
                             "description": "Suggested transfer"})
        if sug_rows:
            sections.append({"title": "\U0001f4a1  Settlement Suggestions", "color": "#D97706",
                             "type": "repayment", "data": sug_rows})
        else:
            sections.append({"title": "\U0001f4a1  Settlement Suggestions", "color": "#059669",
                             "type": "repayment",
                             "data": [{"date": "All settled", "amount": 0,
                                       "description": "No transfers needed"}]})

        # ── Transactions (expenses + settlements, newest first) ──
        items = [("expense", e["expense_date"], e) for e in expenses]
        items += [("settlement", s["settle_date"], s) for s in settlements]
        items.sort(key=lambda x: x[1], reverse=True)
        txn_rows = []
        for kind, dt, data in items:
            if kind == "expense":
                desc = data["description"] or "Expense"
                txn_rows.append({
                    "date": f"{dt}  \u00b7  {desc}",
                    "amount": data["amount"],
                    "description": f"Expense \u00b7 paid by {data['paid_by_name']}"
                                   f"  \u00b7  split {data['split_type']}",
                })
            else:
                # sqlite3.Row has no .get() — index access with a guard.
                try:
                    method = data["method"] or "transfer"
                except (KeyError, IndexError):
                    method = "transfer"
                txn_rows.append({
                    "date": f"{dt}  \u00b7  {data['from_name']} \u2192 {data['to_name']}",
                    "amount": data["amount"],
                    "description": f"Settlement \u00b7 {method}",
                })
        if txn_rows:
            sections.append({"title": "\U0001f4cb  Transactions", "color": "#7C3AED",
                             "type": "repayment", "data": txn_rows})

        status = "SETTLED" if not sug_rows else "PENDING"
        _export_split_pdf(self, f"Split Group \u2014 {group_name}", status,
                          info, analysis, sections)

    # ═══════════════════════════════════════════════════════════
    #  1. VIOLET STATUS CARD
    # ═══════════════════════════════════════════════════════════
    def _build_status_card(self, parent_lay):
        self.status_card = QFrame()
        # Matches the Wealth dashboard's Net Position header gradient
        self.status_card.setStyleSheet(
            "QFrame{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1e1b4b,stop:1 #312e81);"
            "border-radius:14px;}"
            "QLabel{background:transparent;border:none;}")
        sc_lay = QVBoxLayout(self.status_card)
        sc_lay.setContentsMargins(24, 18, 24, 18)
        sc_lay.setSpacing(10)

        self.status_title = QLabel("\U0001f91d  YOUR SPLIT STATUS")
        self.status_title.setStyleSheet("color:white;font-size:13px;font-weight:700;"
                                        "letter-spacing:1px;")
        sc_lay.addWidget(self.status_title)

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
        if hasattr(self, "status_title"):
            who = self.sr.self_display_name()
            self.status_title.setText(
                "\U0001f91d  SPLIT STATUS" if who == "You"
                else f"\U0001f91d  SPLIT STATUS \u2014 {who}")
        replay = getattr(self, "_replay_status", False)
        self._replay_status = False
        animate_value(self.lbl_owed_val, total_owed_to_me, fmt_money, old_value=0 if replay else None)
        animate_value(self.lbl_owe_val, total_i_owe, fmt_money, old_value=0 if replay else None)
        animate_value(self.lbl_settled_val, settled, lambda value: str(int(round(value))), old_value=0 if replay else None)
        animate_value(self.lbl_unset_val, unsettled, lambda value: str(int(round(value))), old_value=0 if replay else None)

    # ═══════════════════════════════════════════════════════════
    #  NAVIGATION
    # ═══════════════════════════════════════════════════════════
    def _goto(self, idx):
        _switch_tabs(self._sub_btns, idx)
        self.sub_stack.setCurrentIndex(idx)
        if idx == 0:
            self._refresh_overview()

    def on_activated(self):
        self._replay_status = True
        self.refresh()

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
        self.group_combo.clear_items()
        self.group_combo.add_item("-- Select Group --", None)
        for g in self.sr.list_groups():
            self.group_combo.add_item(g["name"], g["group_id"])
        self.group_combo.blockSignals(False)
        if self.group_combo.count() > 1:
            self.group_combo.setCurrentIndex(1)

    def _on_group_changed(self):
        gid = self.group_combo.get_data()
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
                combo.addItem(self.sr.display_name_for(m), m["contact_id"])
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
        gid = self.group_combo.get_data()
        if not gid or not self.sr:
            return
        _clear_layout(self.overview_lay)

        # ── 5. KPI Stats — use balance-based calculation ──
        expenses = self.sr.list_expenses(gid)
        settlements = self.sr.list_settlements(gid)
        balances = self.sr.get_group_balances(gid)

        total_expenses = sum(e["amount"] for e in expenses)
        total_pending = sum(b for b in balances.values() if b > 0.01)
        total_settled = sum(s["amount"] for s in settlements)

        _clear_layout(self.stats_row)
        self.stats_row.addWidget(
            _metric_card("Total Expenses", total_expenses, C["accent"]))
        self.stats_row.addWidget(
            _metric_card("Pending", total_pending, C["amber"]))
        self.stats_row.addWidget(
            _metric_card("Settled", total_settled, C["green"]))

        # Balance matrix
        bal_title = QLabel("\U0001f4ca Balance Matrix")
        bal_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        self.overview_lay.addWidget(bal_title)

        balances = self.sr.get_group_balances(gid)
        contacts = {c["contact_id"]: self.sr.display_name_for(c)
                    for c in self.sr.list_contacts()}

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

        items = []
        for e in expenses:
            items.append(("expense", e["expense_date"], e))
        for s in settlements:
            items.append(("settlement", s["settle_date"], s))
        items.sort(key=lambda x: x[1], reverse=True)

        if items:
            for kind, dt, data in items[:20]:
                card = QFrame()
                card.setCursor(QCursor(Qt.PointingHandCursor))
                card.setStyleSheet(
                    f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:8px;}}"
                    f"QFrame:hover{{border-color:{C['accent']};}}"
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
                    t2 = QLabel(f"{data['expense_date']}  \u00b7  Click to edit")
                    t2.setStyleSheet(f"color:{C['text3']};font-size:11px;")
                    info_v.addWidget(t2)
                    cl.addLayout(info_v, 1)
                    amt = QLabel(fmt_money(data["amount"]))
                    amt.setStyleSheet(f"color:{C['red']};font-size:14px;font-weight:800;")
                    cl.addWidget(amt)
                    card.mousePressEvent = lambda e, d=data: self._edit_expense(d)
                else:
                    icon = QLabel("\U0001f4b8")
                    icon.setStyleSheet("font-size:16px;")
                    cl.addWidget(icon)
                    info_v = QVBoxLayout()
                    info_v.setSpacing(2)
                    t1 = QLabel(f"{data['from_name']}  \u2192  {data['to_name']}")
                    t1.setStyleSheet(f"color:{C['text']};font-size:12px;font-weight:800;")
                    info_v.addWidget(t1)
                    t2 = QLabel(f"{data['settle_date']}  \u00b7  Click to edit")
                    t2.setStyleSheet(f"color:{C['text3']};font-size:11px;")
                    info_v.addWidget(t2)
                    cl.addLayout(info_v, 1)
                    amt = QLabel(fmt_money(data["amount"]))
                    amt.setStyleSheet(f"color:{C['green']};font-size:14px;font-weight:800;")
                    cl.addWidget(amt)
                    card.mousePressEvent = lambda e, d=data: self._edit_settlement(d)
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
            lbl = QLabel(self.sr.display_name_for(m))
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
        if mode in (0, 2):  # Equal or Custom Amount — recalc on amount change
            self._locked.clear()
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
        self.stl_method.setMinimumHeight(36)
        for m in self.repos["lookups"].list_methods():
            self.stl_method.addItem(m["display_name"], m["method_id"])
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
        gid = self.group_combo.get_data()
        group_name = self.group_combo.currentText()
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
                person_org=group_name,
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
        gid = self.group_combo.get_data()
        group_name = self.group_combo.currentText()
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

        from_name = self.stl_from.currentText()
        to_name = self.stl_to.currentText()
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
                person_org=group_name,
                description=f"{from_name} \u2192 {to_name}",
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
    #  4. EDIT / DELETE — click card to edit, cascade to transactions
    # ═══════════════════════════════════════════════════════════
    def _edit_expense(self, exp):
        dlg = QDialog(self)
        dlg.setWindowTitle("\u270f\ufe0f Edit Split Expense")
        dlg.setMinimumWidth(480)
        dlg.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        info = QLabel(f"Paid by: {exp['paid_by_name']}  \u00b7  Split: {exp['split_type']}")
        info.setStyleSheet(f"color:{C['text3']};font-size:12px;")
        lay.addWidget(info)

        form = QFormLayout()
        form.setSpacing(8)
        amt = QDoubleSpinBox()
        amt.setRange(0, 99999999)
        amt.setPrefix("\u20b9 ")
        amt.setDecimals(2)
        amt.setValue(exp["amount"])
        amt.setMinimumHeight(36)
        desc = QLineEdit(exp["description"] or "")
        desc.setPlaceholderText("Description")
        desc.setMinimumHeight(36)
        dt = QDateEdit(QDate.fromString(exp["expense_date"], "yyyy-MM-dd"))
        dt.setCalendarPopup(True)
        dt.setMinimumHeight(36)
        form.addRow("Amount", amt)
        form.addRow("Description", desc)
        form.addRow("Date", dt)
        lay.addLayout(form)

        # ── Shares section ──
        shares_data = self.db.execute(
            "SELECT s.share_id, s.contact_id, s.share_amount, c.name "
            "FROM split_shares s JOIN split_contacts c ON c.contact_id=s.contact_id "
            "WHERE s.expense_id=? ORDER BY c.is_self DESC, c.name ASC",
            (exp["expense_id"],)).fetchall()
        share_spins = {}

        if shares_data:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background:{C['border2']};")
            lay.addWidget(sep)
            is_exact = exp["split_type"] == "EXACT"
            shares_title = QLabel("Shares" + (" \u2014 adjust to match amount" if is_exact else " \u2014 auto-calculated"))
            shares_title.setStyleSheet(
                f"font-size:12px;font-weight:700;color:{C['amber'] if is_exact else C['text3']};")
            lay.addWidget(shares_title)

            for s in shares_data:
                row = QHBoxLayout()
                row.setSpacing(6)
                lbl = QLabel(self.sr.display_name_for(s))
                lbl.setStyleSheet(f"font-size:12px;color:{C['text']};")
                lbl.setFixedWidth(110)
                row.addWidget(lbl)
                spin = QDoubleSpinBox()
                spin.setRange(0, 99999999)
                spin.setPrefix("\u20b9 ")
                spin.setDecimals(2)
                spin.setValue(s["share_amount"])
                spin.setMinimumHeight(30)
                spin.setEnabled(is_exact)
                share_spins[s["share_id"]] = spin
                row.addWidget(spin, 1)
                lay.addLayout(row)

        # Auto-recalc for EQUAL / PERCENTAGE on amount change
        def _on_amt_changed(val):
            stype = exp["split_type"]
            if stype == "EQUAL" and shares_data:
                n = len(shares_data)
                if n == 0:
                    return
                share = round(val / n, 2)
                for i, s in enumerate(shares_data):
                    spin = share_spins.get(s["share_id"])
                    if spin:
                        spin.blockSignals(True)
                        spin.setValue(val - share * (n - 1) if i == n - 1 else share)
                        spin.blockSignals(False)
            elif stype == "PERCENTAGE" and shares_data:
                old_amt = exp["amount"]
                if old_amt <= 0:
                    return
                ratio = val / old_amt
                running = 0.0
                for i, s in enumerate(shares_data):
                    spin = share_spins.get(s["share_id"])
                    if spin:
                        spin.blockSignals(True)
                        if i == len(shares_data) - 1:
                            spin.setValue(round(val - running, 2))
                        else:
                            sv = round(s["share_amount"] * ratio, 2)
                            running += sv
                            spin.setValue(sv)
                        spin.blockSignals(False)

        amt.valueChanged.connect(_on_amt_changed)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        delete_btn = QPushButton("\U0001f5d1\ufe0f Delete")
        delete_btn.setStyleSheet(
            f"QPushButton{{background:{C['red_bg']};color:{C['red']};"
            f"border:1.5px solid {C['red']};border-radius:8px;"
            f"padding:6px 14px;font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{background:{C['red']};color:white;}}")
        delete_btn.setCursor(QCursor(Qt.PointingHandCursor))
        delete_btn.clicked.connect(lambda: self._do_delete_expense(exp, dlg))
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel)
        save = QPushButton("\U0001f4be Save")
        save.setObjectName("primary")
        btn_row.addWidget(save)
        lay.addLayout(btn_row)

        def _do_save():
            new_amt = round(amt.value(), 2)
            new_desc = desc.text().strip() or None
            new_date = dt.date().toString("yyyy-MM-dd")

            # Validate EXACT shares sum
            if exp["split_type"] == "EXACT" and share_spins:
                total = sum(round(spin.value(), 2) for spin in share_spins.values())
                if abs(total - new_amt) > 0.01:
                    QMessageBox.warning(dlg, "Mismatch",
                        f"Shares total ({total:.2f}) doesn't match amount ({new_amt:.2f}).\n"
                        f"Please adjust shares to match.")
                    return  # don't close dialog

            # Update expense
            self.db.execute(
                "UPDATE split_expenses SET amount=?, description=?, expense_date=? WHERE expense_id=?",
                (new_amt, new_desc, new_date, exp["expense_id"]))

            # Update shares from spins
            for sid, spin in share_spins.items():
                self.db.execute("UPDATE split_shares SET share_amount=? WHERE share_id=?",
                                (round(spin.value(), 2), sid))

            # Update linked transaction
            if exp["linked_txn_id"]:
                self.db.execute(
                    "UPDATE transactions SET amount=?, description=?, tx_date=? WHERE id=?",
                    (new_amt, f"Split: {new_desc or 'Expense'}", new_date, exp["linked_txn_id"]))
            self.db.commit()
            dlg.accept()
            self._refresh_overview()
            self._refresh_status_card()
            QMessageBox.information(self, "Updated", "Expense updated successfully.")

        save.clicked.connect(_do_save)
        dlg.exec_()

    def _do_delete_expense(self, exp, dlg):
        reply = QMessageBox.question(
            self, "Delete Expense",
            f"Delete expense of {fmt_money(exp['amount'])}?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db.execute("DELETE FROM split_shares WHERE expense_id=?", (exp["expense_id"],))
            self.db.execute("DELETE FROM split_expenses WHERE expense_id=?", (exp["expense_id"],))
            if exp["linked_txn_id"]:
                self.db.execute("DELETE FROM transactions WHERE id=?", (exp["linked_txn_id"],))
            self.db.commit()
            dlg.accept()
            self._refresh_overview()
            self._refresh_status_card()

    def _edit_settlement(self, stl):
        dlg = QDialog(self)
        dlg.setWindowTitle("\u270f\ufe0f Edit Split Settlement")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        info = QLabel(f"{stl['from_name']}  \u2192  {stl['to_name']}")
        info.setStyleSheet(f"color:{C['text3']};font-size:12px;")
        lay.addWidget(info)

        form = QFormLayout()
        form.setSpacing(8)
        amt = QDoubleSpinBox()
        amt.setRange(0, 99999999)
        amt.setPrefix("\u20b9 ")
        amt.setDecimals(2)
        amt.setValue(stl["amount"])
        amt.setMinimumHeight(36)
        dt = QDateEdit(QDate.fromString(stl["settle_date"], "yyyy-MM-dd"))
        dt.setCalendarPopup(True)
        dt.setMinimumHeight(36)
        method = QComboBox()
        method.setMinimumHeight(36)
        for m in self.repos["lookups"].list_methods():
            method.addItem(m["display_name"], m["method_id"])
        idx = method.findText(stl["method"])
        if idx >= 0:
            method.setCurrentIndex(idx)
        form.addRow("Amount", amt)
        form.addRow("Date", dt)
        form.addRow("Method", method)
        lay.addLayout(form)

        btn_row = QHBoxLayout()
        delete_btn = QPushButton("\U0001f5d1\ufe0f Delete")
        delete_btn.setStyleSheet(
            f"QPushButton{{background:{C['red_bg']};color:{C['red']};"
            f"border:1.5px solid {C['red']};border-radius:8px;"
            f"padding:6px 14px;font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{background:{C['red']};color:white;}}")
        delete_btn.setCursor(QCursor(Qt.PointingHandCursor))
        delete_btn.clicked.connect(lambda: self._do_delete_settlement(stl, dlg))
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel)
        save = QPushButton("\U0001f4be Save")
        save.setObjectName("primary")
        save.clicked.connect(dlg.accept)
        btn_row.addWidget(save)
        lay.addLayout(btn_row)

        if dlg.exec_() == QDialog.Accepted:
            new_amt = round(amt.value(), 2)
            new_date = dt.date().toString("yyyy-MM-dd")
            new_method = method.currentText()
            self.db.execute(
                "UPDATE split_settlements SET amount=?, settle_date=?, method=? WHERE settlement_id=?",
                (new_amt, new_date, new_method, stl["settlement_id"]))
            if stl["linked_txn_id"]:
                self.db.execute(
                    "UPDATE transactions SET amount=?, tx_date=?, pay_method=? WHERE id=?",
                    (new_amt, new_date, new_method, stl["linked_txn_id"]))
            self.db.commit()
            self._refresh_overview()
            self._refresh_status_card()
            QMessageBox.information(self, "Updated", "Settlement updated successfully.")

    def _do_delete_settlement(self, stl, dlg):
        reply = QMessageBox.question(
            self, "Delete Settlement",
            f"Delete settlement of {fmt_money(stl['amount'])}?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db.execute("DELETE FROM split_settlements WHERE settlement_id=?", (stl["settlement_id"],))
            if stl["linked_txn_id"]:
                self.db.execute("DELETE FROM transactions WHERE id=?", (stl["linked_txn_id"],))
            self.db.commit()
            dlg.accept()
            self._refresh_overview()
            self._refresh_status_card()

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
                else:
                    match = bool(s) and s in name_l
                    cb.setVisible(match)
                    if match:
                        any_match = True
            # Show "add new" if search text doesn't match any existing contact
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
