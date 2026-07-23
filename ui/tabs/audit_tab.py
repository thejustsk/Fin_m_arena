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
    QDialog, QFormLayout, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QCursor

from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import ChartView, CHART_TEMPLATE, _tx_card, _day_header, _switch_tabs, FILTER_FIELDS, FlowLayout
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
    def __init__(self, tx, accounts_repo, lookups_repo, wealth_link=None, wealth_status=None, parent=None):
        super().__init__(parent)
        self.tx = tx
        self._is_wealth = bool(wealth_link)
        self._wealth_closed = wealth_status in ("CLOSED", "WITHDRAWN", "PREMATURE_WITHDRAWN")
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
            if self._wealth_closed:
                lock_note = QLabel("\U0001f512 Linked record is CLOSED. Amount and date are locked.")
                lock_note.setStyleSheet(f"color:{C['amber']};font-size:11px;font-weight:600;")
                lay.addWidget(lock_note)
            else:
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

        # Lock person/org for wealth-linked (auto-generated from wealth record)
        if self._is_wealth:
            self.f_person.setEnabled(False)

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

        # Lock type for all wealth-linked; lock amount/date for closed wealth records
        if self._is_wealth:
            self.f_type.setEnabled(False)  # DEBIT/CREDIT locked for wealth-linked
        if self._wealth_closed:
            self.f_date.setEnabled(False)
            self.f_amount.setEnabled(False)
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
        # Delete only for non-wealth transactions
        if not self._is_wealth:
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
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self.repos = repos
        self.tx = repos["transactions"]
        self.acc = repos["accounts"]
        self.lu = repos["lookups"]
        self.audit = services["audit"]
        self.services = services
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
        lay.setSpacing(8)

        # ── Filter header ──
        filt_hdr = QLabel("\U0001f50d  Filters")
        filt_hdr.setStyleSheet(f"font-size:13px;font-weight:700;color:{C['text']};")
        lay.addWidget(filt_hdr)

        # ── Filter bar (same style as DB filtered view) ──
        bar = QFrame()
        bar.setStyleSheet(
            f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;padding:8px 12px;}}"
            f"QLabel{{background:transparent;border:none;}}")
        row = QHBoxLayout(bar)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(6)

        # Date range
        row.addWidget(QLabel("From"))
        self.f_from = QDateEdit(QDate.currentDate().addMonths(-1))
        self.f_from.setCalendarPopup(True)
        self.f_from.setMinimumHeight(34)
        self.f_from.setMaximumWidth(120)
        row.addWidget(self.f_from)
        row.addWidget(QLabel("To"))
        self.f_to = QDateEdit(QDate.currentDate())
        self.f_to.setCalendarPopup(True)
        self.f_to.setMinimumHeight(34)
        self.f_to.setMaximumWidth(120)
        row.addWidget(self.f_to)

        # Divider
        div = QFrame(); div.setFixedHeight(24); div.setFixedWidth(1)
        div.setStyleSheet(f"background:{C['border']};")
        row.addWidget(div)

        # Field selector
        row.addWidget(QLabel("Filter"))
        self.fc = QComboBox()
        for f in FILTER_FIELDS:
            self.fc.addItem(f["label"], f["key"])
        self.fc.setMinimumHeight(34)
        self.fc.setMaximumWidth(130)
        row.addWidget(self.fc)

        # Dynamic value input
        self.fstk = QStackedWidget()
        self.ft_combo = QComboBox(); self.ft_combo.setMinimumHeight(34)
        self.ft_text = QLineEdit(); self.ft_text.setMinimumHeight(34)
        self.ft_num = QDoubleSpinBox(); self.ft_num.setPrefix("\u20b9 ")
        self.ft_num.setRange(0, 99999999); self.ft_num.setMinimumHeight(34)
        self.fstk.addWidget(self.ft_combo)
        self.fstk.addWidget(self.ft_text)
        self.fstk.addWidget(self.ft_num)
        row.addWidget(self.fstk, 1)

        # Add + Load + Clear buttons
        ab = QPushButton("+ Add")
        ab.setMinimumHeight(34)
        ab.setStyleSheet(f"QPushButton{{background:{C['surface']};color:{C['text2']};border:1px solid {C['border']};border-radius:8px;font-size:13px;font-weight:600;}}QPushButton:hover{{border-color:{C['accent']};color:{C['accent']};}}")
        ab.setCursor(QCursor(Qt.PointingHandCursor))
        ab.clicked.connect(self._add_audit_filter)
        row.addWidget(ab)

        lb = QPushButton("\u27f3 Load")
        lb.setObjectName("primary")
        lb.setMinimumWidth(80); lb.setMinimumHeight(34)
        lb.setCursor(QCursor(Qt.PointingHandCursor))
        lb.clicked.connect(self._apply_audit_filters)
        row.addWidget(lb)

        lay.addWidget(bar)

        # ── Active filter chips ──
        self.chips_wrap = QWidget()
        self.chips_wrap.setStyleSheet("background:transparent;")
        self.chips_grid = QVBoxLayout(self.chips_wrap)
        self.chips_grid.setContentsMargins(4, 2, 4, 2)
        self.chips_grid.setSpacing(2)
        lay.addWidget(self.chips_wrap)

        # ── Stats + Clear ──
        bottom = QHBoxLayout()
        bottom.setContentsMargins(4, 0, 4, 0)
        self.f_stats = QLabel("")
        self.f_stats.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        bottom.addWidget(self.f_stats)
        bottom.addStretch()
        cb = QPushButton("Clear All"); cb.setObjectName("ghost"); cb.setFixedHeight(26)
        cb.clicked.connect(self._clear_audit_filters)
        bottom.addWidget(cb)
        lay.addLayout(bottom)

        # ── Bulk header ──
        bulk_hdr = QLabel("\U0001f4cb  Bulk Update")
        bulk_hdr.setStyleSheet(f"font-size:13px;font-weight:700;color:{C['text']};")
        lay.addWidget(bulk_hdr)

        # ── Bulk toolbar ──
        bulk = QFrame()
        bulk.setStyleSheet(
            f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}"
            f"QLabel{{background:transparent;border:none;}}"
            f"QComboBox{{border:1.5px solid {C['border']};border-radius:6px;padding:6px 10px;}}"
            f"QComboBox:focus{{border-color:{C['accent']};}}")
        bulk_lay = QHBoxLayout(bulk)
        bulk_lay.setContentsMargins(16, 10, 16, 10)
        bulk_lay.setSpacing(10)
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

        # ── Card scroll area ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        self._cards_lay = QVBoxLayout(inner)
        self._cards_lay.setSpacing(8)
        self._cards_lay.setAlignment(Qt.AlignTop)
        scroll.setWidget(inner)
        self._audit_scroll = scroll
        lay.addWidget(scroll, 1)

        # Init filter system
        self._fv = []
        self.fc.currentIndexChanged.connect(self._on_audit_field)
        self._on_audit_field(0)
        return page

    def _on_audit_field(self, idx):
        """Populate value widget based on selected filter field."""
        key = self.fc.currentData()
        field = next((f for f in FILTER_FIELDS if f["key"] == key), None)
        if not field:
            return
        if field["type"] == "combo":
            self.fstk.setCurrentIndex(0)
            self.ft_combo.clear()
            existing = set()
            for fe in self._fv:
                if fe["key"] == key:
                    existing = set(fe["vals"])
                    break
            if "source" in field:
                src = field["source"]
                items = []
                if src == "accounts":
                    items = [(a["display_name"], a["account_id"]) for a in self.acc.list_active()]
                elif src == "categories":
                    items = [(c["display_name"], c["category_id"]) for c in self.lu.list_categories()]
                elif src == "methods":
                    items = [(m["display_name"], m["method_id"]) for m in self.lu.list_methods()]
                elif src == "pf_categories":
                    items = [(pf["display_name"], pf["pf_id"]) for pf in self.lu.list_pf_categories()]
                for text, data in items:
                    if data not in existing:
                        self.ft_combo.addItem(text, data)
            elif "values" in field:
                for v in field["values"]:
                    if v not in existing:
                        self.ft_combo.addItem(v, v)
        elif field["type"] == "text":
            self.fstk.setCurrentIndex(1)
            self.ft_text.clear()
            self.ft_text.setPlaceholderText(f"Enter {field['label'].lower()}...")
        else:
            self.fstk.setCurrentIndex(2)
            self.ft_num.setValue(0)

    def _add_audit_filter(self):
        """Add a filter chip."""
        key = self.fc.currentData()
        field = next((f for f in FILTER_FIELDS if f["key"] == key), None)
        if not field:
            return
        if field["type"] == "combo":
            val = self.ft_combo.currentText()
            data = self.ft_combo.currentData()
            if data is None:
                return
            entry = next((fe for fe in self._fv if fe["key"] == key), None)
            if entry:
                if data in entry["vals"]:
                    return
                entry["vals"].append(data)
                entry["disp"].append(val)
            else:
                self._fv.append({"key": key, "label": field["label"], "vals": [data], "disp": [val]})
        elif field["type"] == "text":
            val = self.ft_text.text().strip()
            if not val:
                return
            self._fv = [fe for fe in self._fv if fe["key"] != key]
            self._fv.append({"key": key, "label": field["label"], "vals": [val], "disp": [val]})
        else:
            v = self.ft_num.value()
            if v <= 0:
                return
            self._fv = [fe for fe in self._fv if fe["key"] != key]
            self._fv.append({"key": key, "label": field["label"], "vals": [v], "disp": [fmt_money(v)]})
        self._rebuild_audit_chips()
        self._on_audit_field(self.fc.currentIndex())
        self._apply_audit_filters()

    def _clear_audit_filters(self):
        self._fv = []
        self._rebuild_audit_chips()
        self._on_audit_field(self.fc.currentIndex())
        self.load_records()

    def _rebuild_audit_chips(self):
        while self.chips_grid.count():
            itm = self.chips_grid.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()
        if not self._fv:
            return
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        fl = FlowLayout(container, hSpacing=6, vSpacing=4)
        fl.setContentsMargins(0, 0, 0, 0)
        for entry in self._fv:
            key = entry["key"]
            for i, disp in enumerate(entry["disp"]):
                chip = QPushButton(f" {disp} \u2715")
                chip.setStyleSheet(
                    f"QPushButton{{background:{C['accent_bg']};color:{C['accent']};"
                    f"border:1px solid rgba(79,70,229,0.2);border-radius:12px;"
                    f"padding:2px 8px;font-size:11px;font-weight:600;}}"
                    f"QPushButton:hover{{background:#D6DEFF;}}")
                chip.setCursor(QCursor(Qt.PointingHandCursor))
                chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                val_to_remove = entry["vals"][i]
                chip.clicked.connect(lambda _, k=key, v=val_to_remove: self._remove_audit_value(k, v))
                fl.addWidget(chip)
        self.chips_grid.addWidget(container)

    def _remove_audit_value(self, key, val):
        for fe in self._fv:
            if fe["key"] == key:
                try:
                    idx = fe["vals"].index(val)
                    fe["vals"].pop(idx)
                    fe["disp"].pop(idx)
                except ValueError:
                    pass
                if not fe["vals"]:
                    self._fv = [f for f in self._fv if f["key"] != key]
                break
        self._rebuild_audit_chips()
        self._on_audit_field(self.fc.currentIndex())
        self._apply_audit_filters()

    def _apply_audit_filters(self):
        """Apply all active filter chips to reload records."""
        self.load_records()

    def _on_audit_scroll(self, value):
        sb = self._audit_scroll.verticalScrollBar()
        if sb.maximum() <= 0:
            return
        trigger = 400
        try:
            r = self.db.execute("SELECT value FROM preferences WHERE key='scroll_trigger_px'").fetchone()
            if r: trigger = int(r[0])
        except Exception:
            pass
        if value >= sb.maximum() - trigger:
            self._render_next_audit_batch()

    def _render_next_audit_batch(self):
        if not hasattr(self, '_pending_audit_cards') or not self._pending_audit_cards:
            return
        batch_size = 20
        try:
            r = self.db.execute("SELECT value FROM preferences WHERE key='complete_page_size'").fetchone()
            if r: batch_size = int(r[0])
        except Exception:
            pass
        batch = self._pending_audit_cards[:batch_size]
        self._pending_audit_cards = self._pending_audit_cards[batch_size:]
        for row_widget in batch:
            self._cards_lay.addWidget(row_widget)
        if not self._pending_audit_cards:
            try:
                self._audit_scroll.verticalScrollBar().valueChanged.disconnect(self._on_audit_scroll)
            except (TypeError, RuntimeError):
                pass

    def load_records(self):
        d_from = self.f_from.date().toString("yyyy-MM-dd")
        d_to = self.f_to.date().toString("yyyy-MM-dd")
        rows = self.tx.list_filters(date_from=d_from, date_to=d_to, limit=5000)
        self._link_map = _wealth_link_map(self.db)

        # Apply chip filters
        for fe in self._fv:
            key = fe["key"]
            vals = fe["vals"]
            if key == "account":
                rows = [t for t in rows if t.get("account_id") in vals]
            elif key == "category":
                rows = [t for t in rows if t.get("category") in vals]
            elif key == "method":
                rows = [t for t in rows if t.get("pay_method") in vals]
            elif key == "tx_type":
                rows = [t for t in rows if t.get("tx_type") in vals]
            elif key == "kind":
                rows = [t for t in rows if t.get("transaction_kind", "REGULAR") in vals]
            elif key == "neednwant":
                nw_map = {"Need": 1, "Want": 0, "None": 2}
                nw_ints = [nw_map.get(v, -1) for v in vals]
                rows = [t for t in rows if t.get("neednwant") in nw_ints]
            elif key == "pf_category":
                rows = [t for t in rows if t.get("pf_category") in vals]
            elif key == "person_org":
                p = vals[0].lower()
                rows = [t for t in rows if p in (t.get("person_org") or "").lower()]
            elif key == "description":
                d = vals[0].lower()
                rows = [t for t in rows if d in (t.get("description") or "").lower()]
            elif key == "min_amount":
                rows = [t for t in rows if t["amount"] >= vals[0]]
            elif key == "max_amount":
                rows = [t for t in rows if t["amount"] <= vals[0]]

        self._rows = rows
        n = len(rows)
        cr = sum(t["amount"] for t in rows if t["tx_type"] == "CREDIT")
        db = sum(t["amount"] for t in rows if t["tx_type"] == "DEBIT")
        self.f_stats.setText(f"{n} txns | Cr:{fmt_money(cr)} | Db:{fmt_money(db)} | Net:{fmt_money(cr - db)}")
        self._render_table()

    def _render_table(self):
        """Render transactions with date grouping and lazy scroll."""
        from collections import OrderedDict
        from ui.tabs.database_tab import _get_pref, COMPLETE_PAGE_SIZE

        # Clear existing (immediate delete, no ghost widgets)
        import sip
        while self._cards_lay.count():
            item = self._cards_lay.takeAt(0)
            w = item.widget()
            if w:
                try:
                    sip.delete(w)
                except Exception:
                    w.deleteLater()

        self._check_states = {}
        self._all_render_items = []  # list of (type, data) tuples

        if not self._rows:
            empty = QLabel("No transactions found for the selected filters.")
            empty.setStyleSheet(f"color:{C['text3']};padding:24px;font-size:13px;")
            empty.setAlignment(Qt.AlignCenter)
            self._cards_lay.addWidget(empty)
            self._update_bulk_count()
            return

        # Group by date (newest first)
        by_date = OrderedDict()
        for r in sorted(self._rows, key=lambda t: t.get("tx_date", ""), reverse=True):
            d = r.get("tx_date", "")
            by_date.setdefault(d, []).append(r)

        # Pre-build all items (headers + card rows)
        for d_str, day_txns in by_date.items():
            try:
                day_label = date.fromisoformat(d_str).strftime("%A, %d %b")
            except Exception:
                day_label = d_str
            self._all_render_items.append(("header", _day_header(day_label)))

            for r in day_txns:
                tx_id = r["id"]
                # Keep original transaction_kind so _tx_card shows proper badge
                card = _tx_card(r)

                row_widget = QWidget()
                row_widget.setStyleSheet("background:transparent;border:none;")
                row_lay = QHBoxLayout(row_widget)
                row_lay.setContentsMargins(0, 0, 0, 0)
                row_lay.setSpacing(8)

                # Checkbox with "Select" text
                chk = QPushButton("  Select  ")
                chk.setFixedHeight(34)
                chk.setMinimumWidth(82)
                chk.setFocusPolicy(Qt.NoFocus)
                chk.setCursor(QCursor(Qt.PointingHandCursor))
                chk.setStyleSheet(
                    f"QPushButton{{background:{C['surface']};color:{C['text3']};"
                    f"border:2px solid {C['border']};border-radius:8px;font-size:12px;font-weight:700;}}"
                    f"QPushButton:hover{{background:{C['accent']};color:white;border-color:{C['accent']};}}")
                self._check_states[tx_id] = False
                def _toggle_chk(_checked=False, _tid=tx_id, _btn=chk):
                    self._check_states[_tid] = not self._check_states[_tid]
                    is_on = self._check_states[_tid]
                    _btn.setText("  \u2713 Done  " if is_on else "  Select  ")
                    _btn.setStyleSheet(
                        f"QPushButton{{background:{C['accent'] if is_on else C['surface']};"
                        f"color:{'white' if is_on else C['text3']};"
                        f"border:2px solid {C['accent'] if is_on else C['border']};"
                        f"border-radius:8px;font-size:12px;font-weight:700;}}"
                        f"QPushButton:hover{{background:{C['accent']};color:white;border-color:{C['accent']};}}")
                    self._update_bulk_count()
                chk.clicked.connect(_toggle_chk)
                row_lay.addWidget(chk, 0, Qt.AlignVCenter)

                # Card
                row_lay.addWidget(card, 1)

                # Edit button with "Edit" text
                edit_btn = QPushButton("\u270f\ufe0f Edit")
                edit_btn.setFixedHeight(34)
                edit_btn.setMinimumWidth(72)
                edit_btn.setFocusPolicy(Qt.NoFocus)
                edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
                edit_btn.setStyleSheet(
                    f"QPushButton{{background:{C['surface']};color:{C['accent']};"
                    f"border:1.5px solid {C['border']};border-radius:8px;font-size:12px;font-weight:600;}}"
                    f"QPushButton:hover{{background:{C['accent']};color:white;border-color:{C['accent']};}}")
                edit_btn.clicked.connect(lambda _, tid=tx_id: self._open_edit(tid))
                row_lay.addWidget(edit_btn, 0, Qt.AlignVCenter)

                self._all_render_items.append(("card", row_widget))

        # Lazy render: first batch
        page_size = _get_pref(self.db, "complete_page_size", COMPLETE_PAGE_SIZE)
        first_batch = self._all_render_items[:page_size]
        self._pending_render_items = self._all_render_items[page_size:]
        for item_type, widget in first_batch:
            self._cards_lay.addWidget(widget)

        # Connect scroll for lazy loading
        if hasattr(self, '_audit_scroll') and self._pending_render_items:
            try:
                self._audit_scroll.verticalScrollBar().valueChanged.disconnect(self._on_audit_scroll)
            except (TypeError, RuntimeError):
                pass
            self._audit_scroll.verticalScrollBar().valueChanged.connect(self._on_audit_scroll)

        self._update_bulk_count()

    def _on_audit_scroll(self, value):
        sb = self._audit_scroll.verticalScrollBar()
        if sb.maximum() <= 0:
            return
        trigger = 400
        try:
            r = self.db.execute("SELECT value FROM preferences WHERE key='scroll_trigger_px'").fetchone()
            if r:
                trigger = int(r[0])
        except Exception:
            pass
        if value >= sb.maximum() - trigger:
            self._render_next_audit_batch()

    def _render_next_audit_batch(self):
        if not hasattr(self, '_pending_render_items') or not self._pending_render_items:
            return
        from ui.tabs.database_tab import _get_pref, COMPLETE_PAGE_SIZE
        page_size = _get_pref(self.db, "complete_page_size", COMPLETE_PAGE_SIZE)
        batch = self._pending_render_items[:page_size]
        self._pending_render_items = self._pending_render_items[page_size:]
        for item_type, widget in batch:
            self._cards_lay.addWidget(widget)
        if not self._pending_render_items:
            try:
                self._audit_scroll.verticalScrollBar().valueChanged.disconnect(self._on_audit_scroll)
            except (TypeError, RuntimeError):
                pass
    def _verify_edit(self):
        """Require 2FA/password before allowing audit edits."""
        sec = self.services.get("security") if hasattr(self, 'services') else None
        if not sec:
            return True
        try:
            from ui.wealth_verify import WealthEditVerifyDialog
            return WealthEditVerifyDialog.verify_user(sec, self)
        except ImportError:
            return True

    def _checked_ids(self):
        """Get IDs of checked transaction cards."""
        return [tx_id for tx_id, checked in getattr(self, '_check_states', {}).items() if checked]

    def _update_bulk_count(self):
        n = len(self._checked_ids())
        self.bulk_count_lbl.setText(f"{n} selected")
        self.bulk_apply_btn.setEnabled(n > 0)
        self.bulk_apply_btn.setText(f"\u2705 Apply to {n} Selected" if n else "\u2705 Apply to Selected")

    def _get_wealth_status(self, tx_id):
        """Get the status of the linked wealth record, if any."""
        link = self._link_map.get(tx_id)
        if not link:
            return None
        grp = link["group"]
        try:
            if grp in ("Loan Given", "Loan Repayment"):
                row = self.db.execute(
                    "SELECT status FROM loans WHERE trxn_id=? UNION "
                    "SELECT l.status FROM repayments r JOIN loans l ON l.loan_id=r.loan_id WHERE r.linked_txn_id=?",
                    (tx_id, tx_id)).fetchone()
                return row["status"] if row else None
            elif grp in ("Loan Taken", "EMI Payment"):
                row = self.db.execute(
                    "SELECT status FROM borrowed_loans WHERE linked_txn_id=? UNION "
                    "SELECT bl.status FROM borrowed_loan_repayments blr JOIN borrowed_loans bl ON bl.loan_id=blr.loan_id WHERE blr.linked_txn_id=?",
                    (tx_id, tx_id)).fetchone()
                return row["status"] if row else None
            elif grp in ("Deposit Received", "Deposit Repayment"):
                row = self.db.execute(
                    "SELECT status FROM deposits_from_others WHERE linked_txn_id=? UNION "
                    "SELECT d.status FROM deposit_repayments_to_others dr JOIN deposits_from_others d ON d.deposit_id=dr.deposit_id WHERE dr.linked_txn_id=?",
                    (tx_id, tx_id)).fetchone()
                return row["status"] if row else None
            elif grp == "FD Deposit":
                row = self.db.execute(
                    "SELECT status FROM fixed_deposits WHERE linked_txn_id=?",
                    (tx_id,)).fetchone()
                return row["status"] if row else None
        except Exception:
            pass
        return None

    def _open_edit(self, tx_id):
        tx = self.tx.get(tx_id)
        if not tx:
            return
        link = self._link_map.get(tx_id)
        # Fallback: if not in link_map, check transaction_kind for wealth linkage
        if not link:
            _WEALTH_KINDS = {"LOAN_GIVEN", "LOAN_REPAYMENT", "LOAN_TAKEN", "EMI_PAYMENT",
                             "FD_DEPOSIT", "FD_WITHDRAWAL", "DEPOSIT_RECEIVED", "DEPOSIT_REPAYMENT",
                             "MF_PURCHASE", "MF_REDEMPTION"}
            kind = tx.get("transaction_kind", "REGULAR")
            if kind in _WEALTH_KINDS:
                link = {"group": kind, "label": kind.replace("_", " ").title()}
        wealth_status = self._get_wealth_status(tx_id)
        dlg = TransactionEditDialog(tx, self.acc, self.lu, wealth_link=link, wealth_status=wealth_status, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            # Handle deletion with verification + transfer detection
            if dlg.is_deleted():
                self._delete_with_auth(tx_id)
                return
            changes = dlg.changed_fields()
            if not changes:
                return
            # Verify on SAVE, not on open
            if not self._verify_edit():
                return
            # Show updating popup
            from PyQt5.QtWidgets import QApplication
            upd_dlg = QDialog(self)
            upd_dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            upd_dlg.setAttribute(Qt.WA_TranslucentBackground)
            upd_dlg.setFixedSize(340, 140)
            upd_frame = QFrame(upd_dlg)
            upd_frame.setGeometry(10, 10, 320, 120)
            upd_frame.setStyleSheet(
                f"QFrame{{background:{C['surface']};border:1.5px solid {C['accent']};"
                f"border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
            upd_lay = QVBoxLayout(upd_frame)
            upd_lay.setContentsMargins(16, 12, 16, 12)
            upd_lbl = QLabel("\U0001f504  Updating...")
            upd_lbl.setStyleSheet(f"color:{C['accent']};font-size:13px;font-weight:700;")
            upd_lbl.setAlignment(Qt.AlignCenter)
            upd_lay.addWidget(upd_lbl)
            upd_dlg.show()
            QApplication.processEvents()

            update_kw = {field: new for field, (old, new) in changes.items()}
            self.tx.update(tx_id, **update_kw)
            self.db.execute("UPDATE transactions SET updated_at=? WHERE id=?", (TODAY(), tx_id))
            self.db.commit()
            for field, (old, new) in changes.items():
                self.audit.log(tx_id, field, old, new, reason="Manual edit via Audit tab")
            # Cascade changes to linked wealth records
            if "amount" in changes:
                self._cascade_amount(tx_id, changes["amount"][1])
            if "tx_date" in changes:
                self._cascade_date(tx_id, changes["tx_date"][1])
            if "amount" in changes or "tx_date" in changes:
                self._recalc_status(tx_id)
            # Mark linked wealth record as updated (for badge sync)
            self._mark_wealth_updated(tx_id)
            self.load_records()
            # Close updating popup and show done state
            try:
                upd_lbl.setText("\u2705  Updated!")
                upd_lbl.setStyleSheet(f"color:{C['green']};font-size:13px;font-weight:700;")
                ok_btn = QPushButton("OK")
                ok_btn.setObjectName("primary")
                ok_btn.setFixedHeight(28)
                ok_btn.clicked.connect(upd_dlg.accept)
                upd_lay.addWidget(ok_btn)
                ok_btn.setFocus()
                QApplication.processEvents()
            except Exception:
                pass
            # Notify parent to refresh other tabs
            parent_tab = self.parent()
            while parent_tab and not hasattr(parent_tab, '_notify_data_changed'):
                parent_tab = parent_tab.parent()
            if parent_tab and hasattr(parent_tab, '_notify_data_changed'):
                parent_tab._notify_data_changed()


    def _delete_with_auth(self, tx_id):
        """Delete transaction with: transfer detection, warning, auth, updating popup."""
        tx = self.tx.get(tx_id)
        if not tx:
            return

        # ── Step 1: Detect transfer pair ──
        transfer_group = tx.get("transfer_group_id")
        related_txns = []
        if transfer_group:
            rows = self.db.execute(
                "SELECT id, tx_date, tx_type, amount, account_id FROM transactions "
                "WHERE transfer_group_id=? AND id!=?",
                (transfer_group, tx_id)).fetchall()
            related_txns = [dict(r) for r in rows]

        # ── Step 2: Show warning with details ──
        if related_txns:
            details = []
            for rt in related_txns:
                acct = self.db.execute(
                    "SELECT display_name FROM accounts WHERE account_id=?",
                    (rt["account_id"],)).fetchone()
                acct_name = acct["display_name"] if acct else "Unknown"
                details.append(
                    f"  {rt['tx_type']} {fmt_money(rt['amount'])} — {acct_name} ({rt['tx_date']})")
            warning_text = (
                f"This is a TRANSFER transaction.\n\n"
                f"Deleting it will also delete the related transaction:\n"
                f"{chr(10).join(details)}\n\n"
                f"Both transactions will be permanently removed.\n"
                f"This cannot be undone."
            )
        else:
            warning_text = (
                f"Delete transaction of {fmt_money(tx['amount'])}?\n"
                f"This cannot be undone."
            )

        reply = QMessageBox.question(
            self, "Confirm Delete", warning_text,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        # ── Step 3: Verify identity (2FA / password) ──
        if not self._verify_edit():
            return

        # ── Step 4: Show updating popup ──
        from PyQt5.QtWidgets import QApplication
        upd_dlg = QDialog(self)
        upd_dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        upd_dlg.setAttribute(Qt.WA_TranslucentBackground)
        upd_dlg.setFixedSize(340, 140)
        upd_frame = QFrame(upd_dlg)
        upd_frame.setGeometry(10, 10, 320, 120)
        upd_frame.setStyleSheet(
            f"QFrame{{background:{C['surface']};border:1.5px solid {C['red']};"
            f"border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        upd_lay = QVBoxLayout(upd_frame)
        upd_lay.setContentsMargins(16, 12, 16, 12)
        upd_lbl = QLabel("\U0001f504  Deleting...")
        upd_lbl.setStyleSheet(f"color:{C['red']};font-size:13px;font-weight:700;")
        upd_lbl.setAlignment(Qt.AlignCenter)
        upd_lay.addWidget(upd_lbl)
        upd_dlg.show()
        QApplication.processEvents()

        # ── Step 5: Delete all related transactions ──
        all_ids = [tx_id] + [rt["id"] for rt in related_txns]
        # Clean audit_log entries first (no ON DELETE CASCADE)
        for del_id in all_ids:
            try:
                self.db.execute("DELETE FROM audit_log WHERE transaction_id=?", (del_id,))
            except Exception:
                pass
        self.db.commit()
        for del_id in all_ids:
            # Cascade unlink from wealth records
            link = self._link_map.get(del_id)
            if link:
                grp = link["group"]
                try:
                    if grp == "Loan Given":
                        self.db.execute("UPDATE loans SET trxn_id=NULL WHERE trxn_id=?", (del_id,))
                    elif grp == "Loan Repayment":
                        self.db.execute("UPDATE repayments SET linked_txn_id=NULL WHERE linked_txn_id=?", (del_id,))
                    elif grp == "Loan Taken":
                        self.db.execute("UPDATE borrowed_loans SET linked_txn_id=NULL WHERE linked_txn_id=?", (del_id,))
                    elif grp == "EMI Payment":
                        self.db.execute("UPDATE borrowed_loan_repayments SET linked_txn_id=NULL WHERE linked_txn_id=?", (del_id,))
                    elif grp == "Deposit Received":
                        self.db.execute("UPDATE deposits_from_others SET linked_txn_id=NULL WHERE linked_txn_id=?", (del_id,))
                    elif grp == "Deposit Repayment":
                        self.db.execute("UPDATE deposit_repayments_to_others SET linked_txn_id=NULL WHERE linked_txn_id=?", (del_id,))
                    elif grp == "FD Deposit":
                        self.db.execute("UPDATE fixed_deposits SET linked_txn_id=NULL WHERE linked_txn_id=?", (del_id,))
                    elif grp.startswith("MF "):
                        self.db.execute("UPDATE mf_transactions SET linked_txn_id=NULL WHERE linked_txn_id=?", (del_id,))
                    self.db.commit()
                except Exception as e:
                    print(f"[WARN] Cascade unlink failed: {e}")
            self.tx.delete(del_id)

        self.db.commit()
        self.load_records()

        # Notify other tabs
        parent_tab = self.parent()
        while parent_tab and not hasattr(parent_tab, '_notify_data_changed'):
            parent_tab = parent_tab.parent()
        if parent_tab and hasattr(parent_tab, '_notify_data_changed'):
            parent_tab._notify_data_changed()

        # ── Step 6: Show done popup ──
        try:
            count = len(all_ids)
            upd_lbl.setText(f"\u2705  {count} transaction(s) deleted!")
            upd_lbl.setStyleSheet(f"color:{C['green']};font-size:13px;font-weight:700;")
            ok_btn = QPushButton("OK")
            ok_btn.setObjectName("primary")
            ok_btn.setFixedHeight(28)
            ok_btn.clicked.connect(upd_dlg.accept)
            upd_lay.addWidget(ok_btn)
            ok_btn.setFocus()
            QApplication.processEvents()
            upd_dlg.exec_()
        except Exception:
            pass

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

    def _cascade_date(self, tx_id, new_date):
        """Push edited transaction date into the linked wealth record."""
        link = self._link_map.get(tx_id)
        if not link:
            return
        grp = link["group"]
        try:
            if grp == "Loan Given":
                self.db.execute("UPDATE loans SET start_date=? WHERE trxn_id=?", (new_date, tx_id))
            elif grp == "Loan Repayment":
                self.db.execute("UPDATE repayments SET payment_date=? WHERE linked_txn_id=?", (new_date, tx_id))
            elif grp == "Loan Taken":
                self.db.execute("UPDATE borrowed_loans SET start_date=? WHERE linked_txn_id=?", (new_date, tx_id))
            elif grp == "EMI Payment":
                self.db.execute("UPDATE borrowed_loan_repayments SET payment_date=? WHERE linked_txn_id=?", (new_date, tx_id))
            elif grp == "Deposit Received":
                self.db.execute("UPDATE deposits_from_others SET deposit_date=? WHERE linked_txn_id=?", (new_date, tx_id))
            elif grp == "Deposit Repayment":
                self.db.execute("UPDATE deposit_repayments_to_others SET payment_date=? WHERE linked_txn_id=?", (new_date, tx_id))
            elif grp == "FD Deposit":
                self.db.execute("UPDATE fixed_deposits SET start_date=? WHERE linked_txn_id=?", (new_date, tx_id))
            elif grp.startswith("MF "):
                self.db.execute("UPDATE mf_transactions SET txn_date=? WHERE linked_txn_id=?", (new_date, tx_id))
            self.db.commit()
        except Exception as e:
            print(f"[WARN] Date cascade failed: {e}")

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


    def _mark_wealth_updated(self, tx_id):
        """Set updated_at on the linked wealth record so the wealth tab shows Updated badge."""
        link = self._link_map.get(tx_id)
        if not link:
            return
        grp = link["group"]
        try:
            if grp == "Loan Given":
                self.db.execute("UPDATE loans SET updated_at=? WHERE trxn_id=?", (TODAY(), tx_id))
            elif grp == "Loan Repayment":
                row = self.db.execute("SELECT loan_id FROM repayments WHERE linked_txn_id=?", (tx_id,)).fetchone()
                if row: self.db.execute("UPDATE loans SET updated_at=? WHERE loan_id=?", (TODAY(), row["loan_id"]))
            elif grp == "Loan Taken":
                self.db.execute("UPDATE borrowed_loans SET updated_at=? WHERE linked_txn_id=?", (TODAY(), tx_id))
            elif grp == "EMI Payment":
                row = self.db.execute("SELECT loan_id FROM borrowed_loan_repayments WHERE linked_txn_id=?", (tx_id,)).fetchone()
                if row: self.db.execute("UPDATE borrowed_loans SET updated_at=? WHERE loan_id=?", (TODAY(), row["loan_id"]))
            elif grp == "Deposit Received":
                self.db.execute("UPDATE deposits_from_others SET updated_at=? WHERE linked_txn_id=?", (TODAY(), tx_id))
            elif grp == "Deposit Repayment":
                row = self.db.execute("SELECT deposit_id FROM deposit_repayments_to_others WHERE linked_txn_id=?", (tx_id,)).fetchone()
                if row: self.db.execute("UPDATE deposits_from_others SET updated_at=? WHERE deposit_id=?", (TODAY(), row["deposit_id"]))
            elif grp == "FD Deposit":
                self.db.execute("UPDATE fixed_deposits SET updated_at=? WHERE linked_txn_id=?", (TODAY(), tx_id))
            self.db.commit()
        except Exception as e:
            print(f"[WARN] mark_wealth_updated failed: {e}")

    def _apply_bulk(self):
        ids = self._checked_ids()
        if not ids:
            return
        if not self._verify_edit():
            return
        # Show updating popup
        from PyQt5.QtWidgets import QApplication
        upd_dlg = QDialog(self)
        upd_dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        upd_dlg.setAttribute(Qt.WA_TranslucentBackground)
        upd_dlg.setFixedSize(340, 140)
        upd_frame = QFrame(upd_dlg)
        upd_frame.setGeometry(10, 10, 320, 120)
        upd_frame.setStyleSheet(
            f"QFrame{{background:{C['surface']};border:1.5px solid {C['accent']};"
            f"border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        upd_lay = QVBoxLayout(upd_frame)
        upd_lay.setContentsMargins(16, 12, 16, 12)
        upd_lbl = QLabel("\U0001f504  Updating...")
        upd_lbl.setStyleSheet(f"color:{C['accent']};font-size:13px;font-weight:700;")
        upd_lbl.setAlignment(Qt.AlignCenter)
        upd_lay.addWidget(upd_lbl)
        upd_dlg.show()
        QApplication.processEvents()
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
        for tid in ids:
            tx = self.tx.get(tid)
            if not tx:
                continue
            self.tx.update(tid, **updates)
            self.db.execute("UPDATE transactions SET updated_at=? WHERE id=?", (TODAY(), tid))
            self.db.commit()
            self._mark_wealth_updated(tid)
            for field, new_val in updates.items():
                old_val = tx.get(field)
                if old_val != new_val:
                    self.audit.log(tid, field, old_val, new_val, reason="Bulk recategorize via Audit tab")
        self.bulk_category.setCurrentIndex(0)
        self.bulk_neednwant.setCurrentIndex(0)
        self.bulk_pf.setCurrentIndex(0)
        # Show done state in popup
        try:
            upd_lbl.setText(f"\u2705  {len(ids)} transactions updated!")
            upd_lbl.setStyleSheet(f"color:{C['green']};font-size:13px;font-weight:700;")
            ok_btn = QPushButton("OK")
            ok_btn.setObjectName("primary")
            ok_btn.setFixedHeight(28)
            ok_btn.clicked.connect(upd_dlg.accept)
            upd_lay.addWidget(ok_btn)
            ok_btn.setFocus()
            QApplication.processEvents()
            upd_dlg.exec_()
        except Exception:
            pass
        self.load_records()
        parent_tab = self.parent()
        while parent_tab and not hasattr(parent_tab, '_notify_data_changed'):
            parent_tab = parent_tab.parent()
        if parent_tab and hasattr(parent_tab, '_notify_data_changed'):
            parent_tab._notify_data_changed()

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

        self.chart_view = ChartView()
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

        # Determine aggregation: by month if range > 90 days, else by day
        from datetime import datetime as _dtt
        try:
            _d1 = _dtt.strptime(d_from, "%Y-%m-%d")
            _d2 = _dtt.strptime(d_to, "%Y-%m-%d")
            _span_days = (_d2 - _d1).days
        except Exception:
            _span_days = 30
        _by_month = _span_days > 90

        trend_cr, trend_db = {}, {}
        for r in rows:
            if _by_month:
                key = r["tx_date"][:7]  # "YYYY-MM"
            else:
                key = r["tx_date"]      # "YYYY-MM-DD"
            trend_cr.setdefault(key, 0)
            trend_db.setdefault(key, 0)
            if r["tx_type"] == "CREDIT":
                trend_cr[key] += r["amount"]
            else:
                trend_db[key] += r["amount"]
        all_dates = sorted(set(list(trend_cr.keys()) + list(trend_db.keys())))
        if _by_month:
            # Show "Jan", "Feb", etc. for monthly
            _MONTH_NAMES = {"01":"Jan","02":"Feb","03":"Mar","04":"Apr","05":"May","06":"Jun",
                            "07":"Jul","08":"Aug","09":"Sep","10":"Oct","11":"Nov","12":"Dec"}
            trend_labels = [_MONTH_NAMES.get(d[5:], d[5:]) for d in all_dates]
        else:
            trend_labels = [d[5:] for d in all_dates]

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
        sub = QLabel("View and edit all transactions. Wealth-linked items show a \U0001f517 badge.")
        sub.setStyleSheet(f"color:{C['text3']};font-size:12px;")
        outer.addWidget(sub)

        self.audit_tab = _AuditSubTab(self.db, self.repos, self.services)
        outer.addWidget(self.audit_tab, 1)

    def refresh(self):
        self.audit_tab.refresh()
