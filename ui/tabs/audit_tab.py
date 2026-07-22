"""Audit tab — Regular Transactions / Wealth Transactions.

Each sub-tab gives full field-level editing, checkbox bulk-recategorize,
and an Insights view with custom-period trend charts.

"Wealth" transactions are ledger rows created by Wealth-tab actions
(linked via linked_txn_id/trxn_id from loans, repayments, borrowed_loans,
borrowed_loan_repayments, deposits, fixed_deposits, mf_transactions).
Everything else is "Regular".
"""
import json
from datetime import date, timedelta

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QDateEdit, QDoubleSpinBox, QFrame, QStackedWidget, QMessageBox,
    QDialog, QFormLayout, QScrollArea
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QCursor

from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tab_btn_active, _tab_btn_inactive, _switch_tabs, ChartView, CHART_TEMPLATE
try:
    from ui.tabs.wealth_tab import _metric_card, _confirm
except ImportError:
    from ui.theme import C
    from PyQt5.QtWidgets import QLabel, QFrame, QVBoxLayout, QMessageBox, QSizePolicy
    from PyQt5.QtCore import Qt
    def _metric_card(label, value, color=None):
        color = color or C.get("text", "#101828")
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{C.get('surface','#fff')};border:1px solid {C.get('border2','#E5E7EB')};border-radius:10px;}}QLabel{{background:transparent;border:none;}}")
        lay = QVBoxLayout(card); lay.setContentsMargins(14,10,14,10); lay.setSpacing(4)
        v = QLabel(value); v.setStyleSheet(f"font-size:18px;font-weight:800;color:{color};"); lay.addWidget(v)
        l = QLabel(label); l.setStyleSheet(f"font-size:10px;color:{C.get('text3','#667085')};font-weight:600;text-transform:uppercase;letter-spacing:0.5px;"); lay.addWidget(l)
        return card
    def _confirm(parent, title, msg):
        return QMessageBox.question(parent, title, msg, QMessageBox.Yes|QMessageBox.No, QMessageBox.No) == QMessageBox.Yes


NEEDNWANT_LABELS = {None: "\u2014 Not Set", 1: "Need", 0: "Want"}
MDOT = "\u00b7"


def TODAY():
    return date.today().isoformat()


# ── Wealth chart template ──────────────────────────────────────────────────
WEALTH_CHART_TEMPLATE = (
    CHART_TEMPLATE
    .replace("Expense by Category", "Flow by Function")
    .replace("Spending by Account", "Flow by Account")
    .replace("Daily Cash Flow", "Wealth Cash Flow Trend")
    .replace("Need vs Want", "Asset-Building vs Liability Flow")
    .replace("Need", "Asset-Building")
    .replace("Want", "Liability Flow")
)


class _WealthChartView(ChartView):
    def render(self, cat_l, cat_d, acct_l, acct_d, trend_l, trend_cr, trend_db,
               asset_flow, liability_flow):
        if not self.view:
            return
        import tempfile
        from PyQt5.QtCore import QUrl
        html = WEALTH_CHART_TEMPLATE
        html = html.replace("__CAT_L__", json.dumps(cat_l))
        html = html.replace("__CAT_D__", json.dumps(cat_d))
        html = html.replace("__ACCT_L__", json.dumps(acct_l))
        html = html.replace("__ACCT_D__", json.dumps(acct_d))
        html = html.replace("__TREND_L__", json.dumps(trend_l))
        html = html.replace("__TREND_CR__", json.dumps(trend_cr))
        html = html.replace("__TREND_DB__", json.dumps(trend_db))
        html = html.replace("__NEED__", str(round(asset_flow, 2)))
        html = html.replace("__WANT__", str(round(liability_flow, 2)))
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        self.view.load(QUrl.fromLocalFile(tmp.name))
        self._tmp_file = tmp.name


# ── Wealth-link lookup ─────────────────────────────────────────────────────
_WEALTH_LINK_SQL = """
SELECT l.trxn_id AS txn_id, 'Loan Given' AS grp, ('Loan given to ' || b.name) AS label
    FROM loans l JOIN borrowers b ON b.borrower_id=l.borrower_id WHERE l.trxn_id IS NOT NULL
UNION ALL
SELECT r.linked_txn_id, 'Loan Repayment', ('Loan repayment from ' || b.name)
    FROM repayments r JOIN loans l ON l.loan_id=r.loan_id JOIN borrowers b ON b.borrower_id=l.borrower_id
    WHERE r.linked_txn_id IS NOT NULL
UNION ALL
SELECT bl.linked_txn_id, 'Loan Taken', ('Loan taken from ' || le.name)
    FROM borrowed_loans bl JOIN lenders le ON le.lender_id=bl.lender_id WHERE bl.linked_txn_id IS NOT NULL
UNION ALL
SELECT blr.linked_txn_id, 'EMI Payment', ('EMI payment to ' || le.name)
    FROM borrowed_loan_repayments blr JOIN borrowed_loans bl ON bl.loan_id=blr.loan_id
    JOIN lenders le ON le.lender_id=bl.lender_id WHERE blr.linked_txn_id IS NOT NULL
UNION ALL
SELECT d.linked_txn_id, 'Deposit Received', ('Deposit received from ' || dep.name)
    FROM deposits_from_others d JOIN depositors dep ON dep.depositor_id=d.depositor_id
    WHERE d.linked_txn_id IS NOT NULL
UNION ALL
SELECT dr.linked_txn_id, 'Deposit Repayment', ('Deposit repayment to ' || dep.name)
    FROM deposit_repayments_to_others dr JOIN deposits_from_others d ON d.deposit_id=dr.deposit_id
    JOIN depositors dep ON dep.depositor_id=d.depositor_id WHERE dr.linked_txn_id IS NOT NULL
UNION ALL
SELECT f.linked_txn_id, 'FD Deposit', ('FD at ' || COALESCE(a.display_name,'Bank'))
    FROM fixed_deposits f LEFT JOIN accounts a ON a.account_id=f.bank_account_id
    WHERE f.linked_txn_id IS NOT NULL
UNION ALL
SELECT m.linked_txn_id, ('MF ' || m.txn_type), ('MF ' || m.txn_type || ' — ' || s.scheme_name)
    FROM mf_transactions m JOIN mf_schemes s ON s.scheme_id=m.scheme_id WHERE m.linked_txn_id IS NOT NULL
"""


def _wealth_link_map(db):
    """Returns {txn_id: {"group": ..., "label": ...}} for wealth-linked transactions."""
    rows = db.execute(_WEALTH_LINK_SQL).fetchall()
    return {r["txn_id"]: {"group": r["grp"], "label": r["label"]} for r in rows}


# ── Date-range helpers ─────────────────────────────────────────────────────
def _month_bounds(d):
    d_from = d.replace(day=1)
    if d.month == 12:
        d_to = date(d.year + 1, 1, 1) - timedelta(days=1)
    else:
        d_to = date(d.year, d.month + 1, 1) - timedelta(days=1)
    return d_from, d_to


def _quick_range(key):
    today = date.today()
    if key == "this_month":
        return _month_bounds(today)
    if key == "last_month":
        first_this = today.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        return _month_bounds(last_month_end)
    if key == "this_year":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    return date(2000, 1, 1), today


# ═══════════════════════════════════════════════════════════════════════════
# Transaction Edit Dialog
# ═══════════════════════════════════════════════════════════════════════════
class TransactionEditDialog(QDialog):
    def __init__(self, tx, accounts_repo, lookups_repo, wealth_link=None, parent=None):
        super().__init__(parent)
        self.tx = tx
        self.setWindowTitle("\u270f\ufe0f  Edit Transaction")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)

        meta = QLabel(
            f"ID: {tx['id']}  \u00b7  Created: {(tx.get('created_at') or '')[:16]}  \u00b7  "
            f"Kind: {tx.get('transaction_kind') or 'REGULAR'}"
        )
        meta.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        meta.setWordWrap(True)
        lay.addWidget(meta)
        if wealth_link:
            wl = QLabel(f"\U0001f517 Linked to: {wealth_link['label']}")
            wl.setStyleSheet(f"color:{C['accent']};font-size:12px;font-weight:700;")
            lay.addWidget(wl)

        note = QLabel("Amount changes cascade to linked wealth records automatically.")
        note.setStyleSheet(f"color:{C['text3']};font-size:11px;font-style:italic;")
        note.setWordWrap(True)
        lay.addWidget(note)

        form = QFormLayout()
        self.f_date = QDateEdit(QDate.fromString(tx["tx_date"], "yyyy-MM-dd"))
        self.f_date.setCalendarPopup(True)

        self.f_account = QComboBox()
        for a in accounts_repo.list_active():
            self.f_account.addItem(f"{a['display_name']} ({a['account_type']})", a["account_id"])
        idx = self.f_account.findData(tx["account_id"])
        if idx >= 0:
            self.f_account.setCurrentIndex(idx)

        self.f_type = QComboBox()
        self.f_type.addItems(["DEBIT", "CREDIT"])
        self.f_type.setCurrentText(tx["tx_type"])

        self.f_amount = QDoubleSpinBox()
        self.f_amount.setRange(0.01, 999999999)
        self.f_amount.setDecimals(2)
        self.f_amount.setPrefix("\u20b9 ")
        self.f_amount.setValue(tx["amount"])

        self.f_category = QComboBox()
        self.f_category.addItem("\u2014 None \u2014", None)
        for c in lookups_repo.list_categories():
            self.f_category.addItem(c["display_name"], c["category_id"])
        idx = self.f_category.findData(tx.get("category"))
        if idx >= 0:
            self.f_category.setCurrentIndex(idx)

        self.f_method = QComboBox()
        for m in lookups_repo.list_methods():
            self.f_method.addItem(m["display_name"], m["method_id"])
        idx = self.f_method.findData(tx.get("pay_method"))
        if idx >= 0:
            self.f_method.setCurrentIndex(idx)

        self.f_person = QLineEdit(tx.get("person_org") or "")
        self.f_desc = QLineEdit(tx.get("description") or "")

        self.f_neednwant = QComboBox()
        for val, label in [(None, "\u2014 Not Set"), (1, "Need"), (0, "Want")]:
            self.f_neednwant.addItem(label, val)
        idx = self.f_neednwant.findData(tx.get("neednwant") if tx.get("neednwant") in (0, 1) else None)
        if idx >= 0:
            self.f_neednwant.setCurrentIndex(idx)

        self.f_pf = QComboBox()
        self.f_pf.addItem("\u2014 None \u2014", None)
        for pf in lookups_repo.list_pf_categories():
            self.f_pf.addItem(pf["display_name"], pf["pf_id"])
        idx = self.f_pf.findData(tx.get("pf_category"))
        if idx >= 0:
            self.f_pf.setCurrentIndex(idx)

        form.addRow("Date", self.f_date)
        form.addRow("Account", self.f_account)
        form.addRow("Type", self.f_type)
        form.addRow("Amount", self.f_amount)
        form.addRow("Category", self.f_category)
        form.addRow("Payment Method", self.f_method)
        form.addRow("Person / Org", self.f_person)
        form.addRow("Description", self.f_desc)
        form.addRow("Need / Want", self.f_neednwant)
        form.addRow("PF Category", self.f_pf)
        lay.addLayout(form)

        btn_row = QHBoxLayout()
        delete = QPushButton("\U0001f5d1\ufe0f Delete")
        delete.setStyleSheet(
            f"QPushButton{{background:{C['red_bg']};color:{C['red']};"
            f"border:1.5px solid {C['red']};border-radius:8px;"
            f"padding:6px 14px;font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{background:{C['red']};color:white;}}")
        delete.clicked.connect(self._delete_tx)
        btn_row.addWidget(delete)
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("\U0001f4be Save Changes")
        save.setObjectName("primary")
        save.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        lay.addLayout(btn_row)
        self._deleted = False

    def _delete_tx(self):
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Delete Transaction",
            f"Delete transaction of {fmt_money(self.tx['amount'])}?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._deleted = True
            self.accept()

    def is_deleted(self):
        return getattr(self, '_deleted', False)

    def changed_fields(self):
        """Returns {field: (old, new)} for every field that changed."""
        out = {}
        checks = [
            ("tx_date", self.tx["tx_date"], self.f_date.date().toString("yyyy-MM-dd")),
            ("account_id", self.tx["account_id"], self.f_account.currentData()),
            ("tx_type", self.tx["tx_type"], self.f_type.currentText()),
            ("amount", self.tx["amount"], round(self.f_amount.value(), 2)),
            ("category", self.tx.get("category"), self.f_category.currentData()),
            ("pay_method", self.tx.get("pay_method"), self.f_method.currentData()),
            ("person_org", self.tx.get("person_org"), self.f_person.text().strip() or None),
            ("description", self.tx.get("description"), self.f_desc.text().strip() or None),
            ("neednwant", self.tx.get("neednwant"), self.f_neednwant.currentData()),
            ("pf_category", self.tx.get("pf_category"), self.f_pf.currentData()),
        ]
        for field, old, new in checks:
            if old != new:
                out[field] = (old, new)
        return out


# ═══════════════════════════════════════════════════════════════════════════
# Audit Sub-Tab (one instance for Regular, one for Wealth)
# ═══════════════════════════════════════════════════════════════════════════
class _AuditSubTab(QWidget):
    def __init__(self, db, repos, services, wealth_mode, parent=None):
        super().__init__(parent)
        self.db = db
        self.repos = repos
        self.tx = repos["transactions"]
        self.acc = repos["accounts"]
        self.lu = repos["lookups"]
        self.audit = services["audit"]
        self.wealth_mode = wealth_mode
        self._rows = []
        self._link_map = {}
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)

        nav = QHBoxLayout()
        self.btn_records = QPushButton("\U0001f4cb Records")
        self.btn_insights = QPushButton("\U0001f4ca Insights")
        self._sub_btns = [self.btn_records, self.btn_insights]
        for b in self._sub_btns:
            b.setMinimumHeight(32)
            b.setCursor(QCursor(Qt.PointingHandCursor))
            nav.addWidget(b)
        nav.addStretch()
        lay.addLayout(nav)

        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_records())
        self.stack.addWidget(self._build_insights())

        self.btn_records.clicked.connect(lambda: self._goto(0))
        self.btn_insights.clicked.connect(lambda: self._goto(1))
        _switch_tabs(self._sub_btns, 0)

    def _goto(self, idx):
        _switch_tabs(self._sub_btns, idx)
        self.stack.setCurrentIndex(idx)
        if idx == 0:
            self.load_records()
        else:
            self.load_insights()

    def refresh(self):
        self.load_records()
        self.load_insights()

    # ───────────────────────── RECORDS ─────────────────────────────────
    def _build_records(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        # Filter bar
        filt = QFrame()
        filt.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        filt_lay = QVBoxLayout(filt)
        filt_lay.setContentsMargins(14, 10, 14, 10)
        row1 = QHBoxLayout()
        self.f_from = QDateEdit(QDate.currentDate().addMonths(-1))
        self.f_from.setCalendarPopup(True)
        self.f_to = QDateEdit(QDate.currentDate())
        self.f_to.setCalendarPopup(True)
        row1.addWidget(QLabel("From"))
        row1.addWidget(self.f_from)
        row1.addWidget(QLabel("To"))
        row1.addWidget(self.f_to)
        for label, key in [("This Month", "this_month"), ("Last Month", "last_month"),
                           ("This Year", "this_year"), ("All Time", "all")]:
            b = QPushButton(label)
            b.setObjectName("pill")
            b.clicked.connect(lambda *, k=key: self._apply_quick_range(k))
            row1.addWidget(b)
        row1.addStretch()
        filt_lay.addLayout(row1)

        row2 = QHBoxLayout()
        self.f_account_filter = QComboBox()
        self.f_account_filter.addItem("All Accounts", None)
        for a in self.acc.list_active():
            self.f_account_filter.addItem(a["display_name"], a["account_id"])
        self.f_group_filter = QComboBox()
        if self.wealth_mode:
            self.f_group_filter.addItem("All Functions", None)
        else:
            self.f_group_filter.addItem("All Categories", None)
            for c in self.lu.list_categories():
                self.f_group_filter.addItem(c["display_name"], c["category_id"])
        self.f_search = QLineEdit()
        self.f_search.setPlaceholderText("Search person / description\u2026")
        search_btn = QPushButton("\U0001f50d Apply Filters")
        search_btn.setObjectName("primary")
        search_btn.clicked.connect(self.load_records)
        row2.addWidget(self.f_account_filter)
        row2.addWidget(self.f_group_filter)
        row2.addWidget(self.f_search, 1)
        row2.addWidget(search_btn)
        filt_lay.addLayout(row2)
        lay.addWidget(filt)

        # Bulk toolbar
        bulk = QFrame()
        bulk.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        bulk_lay = QHBoxLayout(bulk)
        bulk_lay.setContentsMargins(14, 8, 14, 8)
        self.bulk_count_lbl = QLabel("0 selected")
        self.bulk_count_lbl.setStyleSheet(f"font-weight:700;color:{C['text2']};")
        bulk_lay.addWidget(self.bulk_count_lbl)
        self.bulk_category = QComboBox()
        self.bulk_category.addItem("\u2014 No Change \u2014", "__nochange__")
        for c in self.lu.list_categories():
            self.bulk_category.addItem(c["display_name"], c["category_id"])
        self.bulk_neednwant = QComboBox()
        for val, label in [("__nochange__", "\u2014 No Change \u2014"), (1, "Need"), (0, "Want"),
                           ("__clear__", "Clear (Not Set)")]:
            self.bulk_neednwant.addItem(label, val)
        self.bulk_pf = QComboBox()
        self.bulk_pf.addItem("\u2014 No Change \u2014", "__nochange__")
        for pf in self.lu.list_pf_categories():
            self.bulk_pf.addItem(pf["display_name"], pf["pf_id"])
        self.bulk_pf.addItem("Clear (Not Set)", "__clear__")
        self.bulk_apply_btn = QPushButton("\u2705 Apply to Selected")
        self.bulk_apply_btn.setObjectName("primary")
        self.bulk_apply_btn.setEnabled(False)
        self.bulk_apply_btn.clicked.connect(self._apply_bulk)
        bulk_lay.addWidget(QLabel("Category:"))
        bulk_lay.addWidget(self.bulk_category)
        bulk_lay.addWidget(QLabel("Need/Want:"))
        bulk_lay.addWidget(self.bulk_neednwant)
        bulk_lay.addWidget(QLabel("PF Category:"))
        bulk_lay.addWidget(self.bulk_pf)
        bulk_lay.addStretch()
        bulk_lay.addWidget(self.bulk_apply_btn)
        lay.addWidget(bulk)

        # Card scroll area (replaces table)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        self._cards_lay = QVBoxLayout(inner)
        self._cards_lay.setSpacing(8)
        self._cards_lay.setAlignment(Qt.AlignTop)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return page

    def _apply_quick_range(self, key):
        d_from, d_to = _quick_range(key)
        self.f_from.setDate(QDate(d_from.year, d_from.month, d_from.day))
        self.f_to.setDate(QDate(d_to.year, d_to.month, d_to.day))
        self.load_records()

    def load_records(self):
        d_from = self.f_from.date().toString("yyyy-MM-dd")
        d_to = self.f_to.date().toString("yyyy-MM-dd")
        account_id = self.f_account_filter.currentData()
        rows = self.tx.list_filters(account_id=account_id, date_from=d_from, date_to=d_to, limit=5000)

        self._link_map = _wealth_link_map(self.db)
        if self.wealth_mode:
            rows = [r for r in rows if r["id"] in self._link_map]
            group = self.f_group_filter.currentData()
            if group:
                rows = [r for r in rows if self._link_map.get(r["id"], {}).get("group") == group]
        else:
            wealth_ids = set(self._link_map.keys())
            rows = [r for r in rows if r["id"] not in wealth_ids]
            cat = self.f_group_filter.currentData()
            if cat:
                rows = [r for r in rows if r.get("category") == cat]

        search = self.f_search.text().strip().lower()
        if search:
            rows = [r for r in rows if search in (r.get("person_org") or "").lower()
                    or search in (r.get("description") or "").lower()]

        self._rows = rows
        self._refresh_group_filter_options()
        self._render_table()

    def _refresh_group_filter_options(self):
        if not self.wealth_mode:
            return
        current = self.f_group_filter.currentData()
        groups = sorted({v["group"] for v in self._link_map.values()})
        self.f_group_filter.blockSignals(True)
        self.f_group_filter.clear()
        self.f_group_filter.addItem("All Functions", None)
        for g in groups:
            self.f_group_filter.addItem(g, g)
        idx = self.f_group_filter.findData(current)
        if idx >= 0:
            self.f_group_filter.setCurrentIndex(idx)
        self.f_group_filter.blockSignals(False)

    def _render_table(self):
        """Render transactions as expandable cards."""
        from PyQt5.QtWidgets import QSizePolicy
        # Clear existing cards
        while self._cards_lay.count():
            item = self._cards_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._check_btns = {}  # {tx_id: QPushButton checkbox}

        if not self._rows:
            empty = QLabel("No transactions found for the selected filters.")
            empty.setStyleSheet(f"color:{C['text3']};padding:24px;font-size:13px;")
            empty.setAlignment(Qt.AlignCenter)
            self._cards_lay.addWidget(empty)
            self._update_bulk_count()
            return

        for r in self._rows:
            tx_id = r["id"]
            is_credit = r["tx_type"] == "CREDIT"
            amt_color = C["green"] if is_credit else C["red"]
            prefix = "+" if is_credit else "\u2212"
            link = self._link_map.get(tx_id, {}) if self.wealth_mode else {}
            linked_label = link.get("label", "")

            # Card
            card = QFrame()
            card.setStyleSheet(
                f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;}}"
                f"QFrame:hover{{border-color:{C['accent']};}}"
                f"QLabel{{background:transparent;border:none;}}")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 10, 14, 10)
            cl.setSpacing(4)

            # Row 1: Checkbox + Date + Type badge + Amount
            top = QHBoxLayout()
            chk = QPushButton("\u25CB")
            chk.setFixedSize(24, 24)
            chk.setFocusPolicy(Qt.NoFocus)
            chk.setCursor(QCursor(Qt.PointingHandCursor))
            chk.setStyleSheet(
                f"QPushButton{{background:{C['surface']};color:{C['text3']};"
                f"border:2px solid {C['border']};border-radius:12px;font-size:10px;font-weight:700;}}"
                f"QPushButton:hover{{background:{C['accent']};color:white;border-color:{C['accent']};}}")
            self._check_states = getattr(self, '_check_states', {})
            self._check_states[tx_id] = False
            def _toggle_chk(_checked=False, _tid=tx_id, _btn=chk):
                self._check_states[_tid] = not self._check_states[_tid]
                is_on = self._check_states[_tid]
                _btn.setText("\u2713" if is_on else "\u25CB")
                _btn.setStyleSheet(
                    f"QPushButton{{background:{C['accent'] if is_on else C['surface']};"
                    f"color:{'white' if is_on else C['text3']};"
                    f"border:2px solid {C['accent'] if is_on else C['border']};"
                    f"border-radius:12px;font-size:10px;font-weight:700;}}"
                    f"QPushButton:hover{{background:{C['accent']};color:white;border-color:{C['accent']};}}")
                self._update_bulk_count()
            chk.clicked.connect(_toggle_chk)
            self._check_btns[tx_id] = chk
            top.addWidget(chk)

            date_lbl = QLabel(r.get("tx_date", ""))
            date_lbl.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};")
            top.addWidget(date_lbl)

            type_badge = QLabel(r["tx_type"])
            type_badge.setStyleSheet(
                f"color:white;background:{amt_color};border-radius:10px;"
                f"padding:2px 8px;font-size:10px;font-weight:700;border:none;")
            top.addWidget(type_badge)

            if self.wealth_mode and linked_label:
                link_badge = QLabel(f"\U0001f517 {link.get('group', '')}")
                link_badge.setStyleSheet(
                    f"color:{C['accent']};background:{C['accent_bg']};border-radius:10px;"
                    f"padding:2px 8px;font-size:10px;font-weight:700;border:none;")
                top.addWidget(link_badge)

            top.addStretch()

            amt_lbl = QLabel(f"{prefix}{fmt_money(r['amount'])}")
            amt_lbl.setStyleSheet(f"font-size:16px;font-weight:900;color:{amt_color};")
            top.addWidget(amt_lbl)
            cl.addLayout(top)

            # Row 2: Details
            details = []
            if r.get("account_name"):
                details.append(f"\U0001f3e6 {r['account_name']}")
            if r.get("cat_name"):
                details.append(f"\U0001f4cb {r['cat_name']}")
            if r.get("method_name"):
                details.append(f"\U0001f4b3 {r['method_name']}")
            person = r.get("person_org") or ""
            desc = r.get("description") or ""
            if person or desc:
                _em_dash = "\u2014"
            details.append(f"\U0001f464 {person}{(' ' + _em_dash + ' ' + desc) if desc else ''}")
            nw = NEEDNWANT_LABELS.get(
                r.get("neednwant") if r.get("neednwant") in (0, 1) else None)
            if nw and nw != "\u2014 Not Set":
                details.append(f"\U0001f3af {nw}")

            det_lbl = QLabel(f"  {MDOT}  ".join(details))
            det_lbl.setStyleSheet(f"font-size:11px;color:{C['text3']};")
            det_lbl.setWordWrap(True)
            cl.addWidget(det_lbl)

            # Row 3: Edit button (hidden, shown on card click)
            edit_btn = QPushButton("\u270f\ufe0f Edit")
            edit_btn.setFixedHeight(24)
            edit_btn.setFocusPolicy(Qt.NoFocus)
            edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
            edit_btn.setStyleSheet(
                f"QPushButton{{background:{C['surface']};color:{C['accent']};"
                f"border:1.5px solid {C['accent']};border-radius:8px;"
                f"padding:4px 12px;font-size:11px;font-weight:600;}}"
                f"QPushButton:hover{{background:{C['accent_bg']};}}")
            edit_btn.hide()
            edit_btn.clicked.connect(lambda _, tid=tx_id: self._open_edit(tid))
            cl.addWidget(edit_btn)

            # Click card → show edit button
            def _show_edit(event, btn=edit_btn):
                btn.show()
            card.mousePressEvent = _show_edit

            self._cards_lay.addWidget(card)

        self._update_bulk_count()

    def _checked_ids(self):
        """Get IDs of checked transaction cards."""
        return [tx_id for tx_id, checked in getattr(self, '_check_states', {}).items() if checked]

    def _update_bulk_count(self):
        n = len(self._checked_ids())
        self.bulk_count_lbl.setText(f"{n} selected")
        self.bulk_apply_btn.setEnabled(n > 0)
        self.bulk_apply_btn.setText(f"\u2705 Apply to {n} Selected" if n else "\u2705 Apply to Selected")

    def _open_edit(self, tx_id):
        tx = self.tx.get(tx_id)
        if not tx:
            return
        link = self._link_map.get(tx_id) if self.wealth_mode else None
        dlg = TransactionEditDialog(tx, self.acc, self.lu, wealth_link=link, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            # Handle deletion
            if dlg.is_deleted():
                self._delete_transaction(tx_id)
                return
            changes = dlg.changed_fields()
            if not changes:
                return
            update_kw = {field: new for field, (old, new) in changes.items()}
            self.tx.update(tx_id, **update_kw)
            for field, (old, new) in changes.items():
                self.audit.log(tx_id, field, old, new, reason="Manual edit via Audit tab")
            # Cascade amount changes to linked wealth records
            if self.wealth_mode and "amount" in changes:
                self._cascade_amount(tx_id, changes["amount"][1])
                self._recalc_status(tx_id)
            self.load_records()
            # Notify parent to refresh other tabs
            parent_tab = self.parent()
            while parent_tab and not hasattr(parent_tab, '_notify_data_changed'):
                parent_tab = parent_tab.parent()
            if parent_tab and hasattr(parent_tab, '_notify_data_changed'):
                parent_tab._notify_data_changed()
            QMessageBox.information(self, "Saved", f"Updated {len(changes)} field(s).")

    def _delete_transaction(self, tx_id):
        """Delete transaction with cascade to linked wealth records."""
        link = self._link_map.get(tx_id)
        if link:
            grp = link["group"]
            try:
                if grp == "Loan Given":
                    self.db.execute("UPDATE loans SET trxn_id=NULL WHERE trxn_id=?", (tx_id,))
                elif grp == "Loan Repayment":
                    self.db.execute("UPDATE repayments SET linked_txn_id=NULL WHERE linked_txn_id=?", (tx_id,))
                elif grp == "Loan Taken":
                    self.db.execute("UPDATE borrowed_loans SET linked_txn_id=NULL WHERE linked_txn_id=?", (tx_id,))
                elif grp == "EMI Payment":
                    self.db.execute("UPDATE borrowed_loan_repayments SET linked_txn_id=NULL WHERE linked_txn_id=?", (tx_id,))
                elif grp == "Deposit Received":
                    self.db.execute("UPDATE deposits_from_others SET linked_txn_id=NULL WHERE linked_txn_id=?", (tx_id,))
                elif grp == "Deposit Repayment":
                    self.db.execute("UPDATE deposit_repayments_to_others SET linked_txn_id=NULL WHERE linked_txn_id=?", (tx_id,))
                elif grp == "FD Deposit":
                    self.db.execute("UPDATE fixed_deposits SET linked_txn_id=NULL WHERE linked_txn_id=?", (tx_id,))
                elif grp.startswith("MF "):
                    self.db.execute("UPDATE mf_transactions SET linked_txn_id=NULL WHERE linked_txn_id=?", (tx_id,))
                self.db.commit()
            except Exception as e:
                print(f"[WARN] Cascade unlink failed: {e}")
        self.tx.delete(tx_id)
        self.load_records()
        parent_tab = self.parent()
        while parent_tab and not hasattr(parent_tab, '_notify_data_changed'):
            parent_tab = parent_tab.parent()
        if parent_tab and hasattr(parent_tab, '_notify_data_changed'):
            parent_tab._notify_data_changed()
        QMessageBox.information(self, "Deleted", "Transaction deleted successfully.")

    def _cascade_amount(self, tx_id, new_amount):
        """Push edited transaction amount into the linked wealth table."""
        link = self._link_map.get(tx_id)
        if not link:
            return
        grp = link["group"]
        try:
            if grp == "Loan Given":
                self.db.execute("UPDATE loans SET loan_amount=? WHERE trxn_id=?", (new_amount, tx_id))
            elif grp == "Loan Taken":
                self.db.execute("UPDATE borrowed_loans SET principal_amount=? WHERE linked_txn_id=?",
                                (new_amount, tx_id))
            elif grp == "Loan Repayment":
                self.db.execute("UPDATE repayments SET amount_paid=? WHERE linked_txn_id=?",
                                (new_amount, tx_id))
            elif grp == "EMI Payment":
                self.db.execute("UPDATE borrowed_loan_repayments SET amount_paid=? WHERE linked_txn_id=?",
                                (new_amount, tx_id))
            elif grp == "Deposit Received":
                self.db.execute("UPDATE deposits_from_others SET principal_amount=? WHERE linked_txn_id=?",
                                (new_amount, tx_id))
            elif grp == "Deposit Repayment":
                self.db.execute("UPDATE deposit_repayments_to_others SET amount_paid=? WHERE linked_txn_id=?",
                                (new_amount, tx_id))
            elif grp == "FD Deposit":
                self.db.execute("UPDATE fixed_deposits SET principal_amount=? WHERE linked_txn_id=?",
                                (new_amount, tx_id))
            elif grp.startswith("MF "):
                row = self.db.execute("SELECT nav FROM mf_transactions WHERE linked_txn_id=?",
                                      (tx_id,)).fetchone()
                if row:
                    nav = row["nav"]
                    units = round(new_amount / nav, 4) if nav > 0 else 0
                    self.db.execute(
                        "UPDATE mf_transactions SET amount=?, units=? WHERE linked_txn_id=?",
                        (new_amount, units, tx_id))
            self.db.commit()
        except Exception as e:
            print(f"[WARN] Cascade failed: {e}")

    def _recalc_status(self, tx_id):
        """Recalculate linked wealth record status using the same algo as each tab's repo."""
        link = self._link_map.get(tx_id)
        if not link:
            return
        grp = link["group"]
        try:
            if grp in ("Loan Given", "Loan Repayment"):
                if grp == "Loan Given":
                    row = self.db.execute("SELECT loan_id FROM loans WHERE trxn_id=?", (tx_id,)).fetchone()
                else:
                    row = self.db.execute("SELECT loan_id FROM repayments WHERE linked_txn_id=?", (tx_id,)).fetchone()
                if row:
                    self.repos["loans"].recalc_status(row["loan_id"])

            elif grp in ("Loan Taken", "EMI Payment"):
                if grp == "Loan Taken":
                    row = self.db.execute("SELECT loan_id FROM borrowed_loans WHERE linked_txn_id=?", (tx_id,)).fetchone()
                else:
                    row = self.db.execute("SELECT loan_id FROM borrowed_loan_repayments WHERE linked_txn_id=?", (tx_id,)).fetchone()
                if row:
                    self.repos["borrowed"].recalc_status(row["loan_id"])

            elif grp in ("Deposit Received", "Deposit Repayment"):
                if grp == "Deposit Received":
                    row = self.db.execute("SELECT deposit_id FROM deposits_from_others WHERE linked_txn_id=?", (tx_id,)).fetchone()
                else:
                    row = self.db.execute("SELECT deposit_id FROM deposit_repayments_to_others WHERE linked_txn_id=?", (tx_id,)).fetchone()
                if row:
                    self.repos["deposits"].recalc_status(row["deposit_id"])
        except Exception as e:
            print(f"[WARN] Status recalc failed: {e}")


    def _apply_bulk(self):
        ids = self._checked_ids()
        if not ids:
            return
        cat_val = self.bulk_category.currentData()
        nw_val = self.bulk_neednwant.currentData()
        pf_val = self.bulk_pf.currentData()
        updates = {}
        if cat_val != "__nochange__":
            updates["category"] = cat_val
        if nw_val != "__nochange__":
            updates["neednwant"] = None if nw_val == "__clear__" else nw_val
        if pf_val != "__nochange__":
            updates["pf_category"] = None if pf_val == "__clear__" else pf_val
        if not updates:
            QMessageBox.information(self, "Nothing to Apply",
                                    "Pick at least one field to change.")
            return
        if not _confirm(self, "Bulk Update",
                        f"Apply these changes to {len(ids)} selected transaction(s)?"):
            return
        for tid in ids:
            tx = self.tx.get(tid)
            if not tx:
                continue
            self.tx.update(tid, **updates)
            for field, new_val in updates.items():
                old_val = tx.get(field)
                if old_val != new_val:
                    self.audit.log(tid, field, old_val, new_val, reason="Bulk recategorize via Audit tab")
        self.bulk_category.setCurrentIndex(0)
        self.bulk_neednwant.setCurrentIndex(0)
        self.bulk_pf.setCurrentIndex(0)
        self.load_records()
        QMessageBox.information(self, "Updated", f"{len(ids)} transaction(s) updated.")

    # ───────────────────────── INSIGHTS ────────────────────────────────
    def _build_insights(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        row = QHBoxLayout()
        self.i_from = QDateEdit(QDate.currentDate().addMonths(-1))
        self.i_from.setCalendarPopup(True)
        self.i_to = QDateEdit(QDate.currentDate())
        self.i_to.setCalendarPopup(True)
        row.addWidget(QLabel("From"))
        row.addWidget(self.i_from)
        row.addWidget(QLabel("To"))
        row.addWidget(self.i_to)
        for label, key in [("This Month", "this_month"), ("Last Month", "last_month"),
                           ("This Year", "this_year"), ("All Time", "all")]:
            b = QPushButton(label)
            b.setObjectName("pill")
            b.clicked.connect(lambda *, k=key: self._apply_insight_range(k))
            row.addWidget(b)
        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("primary")
        apply_btn.clicked.connect(self.load_insights)
        row.addStretch()
        row.addWidget(apply_btn)
        lay.addLayout(row)

        self.stats_row = QHBoxLayout()
        lay.addLayout(self.stats_row)

        self.chart_view = _WealthChartView() if self.wealth_mode else ChartView()
        lay.addWidget(self.chart_view, 1)
        return page

    def _apply_insight_range(self, key):
        d_from, d_to = _quick_range(key)
        self.i_from.setDate(QDate(d_from.year, d_from.month, d_from.day))
        self.i_to.setDate(QDate(d_to.year, d_to.month, d_to.day))
        self.load_insights()

    def load_insights(self):
        d_from = self.i_from.date().toString("yyyy-MM-dd")
        d_to = self.i_to.date().toString("yyyy-MM-dd")
        rows = self.tx.list_filters(date_from=d_from, date_to=d_to, limit=20000)
        # Reuse cached link map if available
        link_map = self._link_map if self._link_map else _wealth_link_map(self.db)
        if self.wealth_mode:
            rows = [r for r in rows if r["id"] in link_map]
        else:
            rows = [r for r in rows if r["id"] not in link_map]

        credits = sum(r["amount"] for r in rows if r["tx_type"] == "CREDIT")
        debits = sum(r["amount"] for r in rows if r["tx_type"] == "DEBIT")

        while self.stats_row.count():
            item = self.stats_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for card in [
            _metric_card("Total Credits", fmt_money(credits), C["green"]),
            _metric_card("Total Debits", fmt_money(debits), C["red"]),
            _metric_card("Net", fmt_money(credits - debits), C["green"] if credits >= debits else C["red"]),
            _metric_card("Transactions", str(len(rows))),
        ]:
            self.stats_row.addWidget(card)

        acct_cr, acct_db = {}, {}
        for r in rows:
            an = r.get("account_name") or r["account_id"]
            if r["tx_type"] == "CREDIT":
                acct_cr[an] = acct_cr.get(an, 0) + r["amount"]
            else:
                acct_db[an] = acct_db.get(an, 0) + r["amount"]
        all_accts = sorted(set(list(acct_cr.keys()) + list(acct_db.keys())))
        acct_totals = [round(acct_cr.get(a, 0) + acct_db.get(a, 0), 2) for a in all_accts]

        trend_cr, trend_db = {}, {}
        for r in rows:
            trend_cr.setdefault(r["tx_date"], 0)
            trend_db.setdefault(r["tx_date"], 0)
            if r["tx_type"] == "CREDIT":
                trend_cr[r["tx_date"]] += r["amount"]
            else:
                trend_db[r["tx_date"]] += r["amount"]
        all_dates = sorted(set(list(trend_cr.keys()) + list(trend_db.keys())))
        trend_labels = [d[5:] for d in all_dates]

        if self.wealth_mode:
            grp_totals = {}
            asset_flow = liability_flow = 0.0
            asset_groups = {"Loan Given", "FD Deposit"}
            liability_groups = {"Loan Taken", "Deposit Received"}
            for r in rows:
                grp = link_map.get(r["id"], {}).get("group", "Other")
                grp_totals[grp] = grp_totals.get(grp, 0) + r["amount"]
                if grp in asset_groups and r["tx_type"] == "DEBIT":
                    asset_flow += r["amount"]
                if grp in liability_groups and r["tx_type"] == "CREDIT":
                    liability_flow += r["amount"]
            self.chart_view.render(
                list(grp_totals.keys()), [round(v, 2) for v in grp_totals.values()],
                all_accts, acct_totals, trend_labels,
                [round(trend_cr.get(d, 0), 2) for d in all_dates],
                [round(trend_db.get(d, 0), 2) for d in all_dates],
                round(asset_flow, 2), round(liability_flow, 2))
        else:
            cats = {}
            for r in rows:
                if r["tx_type"] == "DEBIT":
                    cn = r.get("cat_name") or "Other"
                    cats[cn] = cats.get(cn, 0) + r["amount"]
            need = sum(r["amount"] for r in rows if r.get("neednwant") == 1 and r["tx_type"] == "DEBIT")
            want = sum(r["amount"] for r in rows if r.get("neednwant") == 0 and r["tx_type"] == "DEBIT")
            self.chart_view.render(
                list(cats.keys()), [round(v, 2) for v in cats.values()],
                all_accts, acct_totals, trend_labels,
                [round(trend_cr.get(d, 0), 2) for d in all_dates],
                [round(trend_db.get(d, 0), 2) for d in all_dates],
                round(need, 2), round(want, 2))


# ═══════════════════════════════════════════════════════════════════════════
# AUDIT TAB
# ═══════════════════════════════════════════════════════════════════════════
class AuditTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self.repos = repos
        self.services = services
        self._build()

    def set_refresh_callback(self, callback):
        """Set callback to refresh all tabs when data changes."""
        self._refresh_all = callback

    def _notify_data_changed(self):
        if hasattr(self, '_refresh_all') and self._refresh_all:
            self._refresh_all()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(14)

        heading = QLabel("\U0001f50d  Audit")
        heading.setStyleSheet(f"font-size:22px;font-weight:800;color:{C['text']};")
        outer.addWidget(heading)
        sub = QLabel("Edit any transaction field, bulk recategorize, and explore trends.")
        sub.setStyleSheet(f"color:{C['text3']};font-size:12px;")
        outer.addWidget(sub)

        nav = QHBoxLayout()
        self.regular_tab = _AuditSubTab(self.db, self.repos, self.services, wealth_mode=False)
        outer.addWidget(self.regular_tab)

    def refresh(self):
        self.regular_tab.refresh()
