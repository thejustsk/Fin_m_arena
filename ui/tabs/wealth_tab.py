
"""Wealth tab — People / Deposits / Investments.

3 groups, 5 functions: Loans I Give, Loans I Take, FD I Deposit,
FD Others Deposit, Mutual Funds. Every function follows the same
Entry / List / History pattern, with a click-through Detail dialog per
item. Every money-moving action also writes a real ledger transaction
(via TransactionsRepo) so account balances everywhere stay correct —
balances are derived live from `transactions`, so this is the only
place that needs to happen.
"""
import urllib.request
import urllib.parse
import json as _json
from datetime import date, datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QFrame, QScrollArea,
    QStackedWidget, QMessageBox, QDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFormLayout, QProgressBar, QListWidget,
    QTabWidget
)
from PyQt5.QtCore import Qt, QDate

from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tab_btn_active, _tab_btn_inactive, _switch_tabs
from services.loan_service import LoanService
from services.fd_service import FDService
from services.mf_service import MFService


def TODAY():
    return date.today().isoformat()


# ═══════════════════════════════════════════════
# SHARED HELPERS
# ═══════════════════════════════════════════════

def _add_months(d, months):
    """Add calendar months to a date.date without needing dateutil."""
    m = d.month - 1 + int(months)
    y = d.year + m // 12
    m = m % 12 + 1
    leap = (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
    days_in_month = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = min(d.day, days_in_month[m - 1])
    return date(y, m, day)


def status_color(role, status):
    """role: 'asset' (money owed TO the user) or 'liability' (money the user owes)."""
    status = (status or "").upper()
    if status == "OVERDUE":
        return C["red"]
    if status in ("CLOSED", "MATURED", "WITHDRAWN", "CLEARED"):
        return C["text3"] if role != "asset" else C["green"]
    return C["green"] if role == "asset" else C["accent"]


def _metric_card(label, value, color=None):
    color = color or C["text"]
    card = QFrame(); card.setObjectName("metric-card")
    lay = QVBoxLayout(card); lay.setSpacing(4)
    v = QLabel(value); v.setStyleSheet(f"font-size:20px;font-weight:800;color:{color};")
    l = QLabel(label); l.setStyleSheet(f"font-size:11px;color:{C['text3']};font-weight:600;")
    lay.addWidget(v); lay.addWidget(l)
    return card


def _badge(text, color):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{color};background:{color}22;border-radius:10px;"
                       f"padding:3px 10px;font-size:11px;font-weight:700;")
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


def _wealth_card(title, subtitle, amount_text, badge_text, badge_color,
                  on_click=None, progress_pct=None, extra_line=None):
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{ background:{C['surface']}; border:1px solid {C['border2']};
                   border-left:4px solid {badge_color}; border-radius:12px; }}
        QFrame:hover {{ border-color:{badge_color}; background:{C['surface2']}; }}
        QLabel {{ background:transparent; border:none; }}
    """)
    if on_click:
        card.setCursor(Qt.PointingHandCursor)
    lay = QVBoxLayout(card); lay.setContentsMargins(14, 10, 14, 10); lay.setSpacing(5)
    top = QHBoxLayout()
    t = QLabel(title); t.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
    top.addWidget(t, 1)
    top.addWidget(_badge(badge_text, badge_color))
    lay.addLayout(top)
    mid = QHBoxLayout()
    s = QLabel(subtitle); s.setStyleSheet(f"font-size:12px;color:{C['text3']};")
    s.setWordWrap(True)
    mid.addWidget(s, 1)
    a = QLabel(amount_text); a.setStyleSheet(f"font-size:14px;font-weight:800;color:{C['text']};")
    mid.addWidget(a)
    lay.addLayout(mid)
    if progress_pct is not None:
        pb = QProgressBar(); pb.setRange(0, 100); pb.setValue(int(max(0, min(100, progress_pct))))
        pb.setTextVisible(False); pb.setFixedHeight(6)
        lay.addWidget(pb)
    if extra_line:
        e = QLabel(extra_line); e.setStyleSheet(f"font-size:11px;color:{C['text3']};")
        lay.addWidget(e)
    if on_click:
        card.mousePressEvent = lambda ev, cb=on_click: cb()
    return card


def _account_combo(accounts_repo):
    cb = QComboBox()
    for a in accounts_repo.list_active():
        cb.addItem(f"{a['display_name']} ({a['account_type']})", a["account_id"])
    return cb


def _method_combo(lookups_repo):
    cb = QComboBox()
    for m in lookups_repo.list_methods():
        cb.addItem(m["display_name"], m["method_id"])
    return cb


def _person_combo(list_fn, id_keys):
    cb = QComboBox()
    for p in list_fn():
        pid = None
        for k in id_keys:
            if p.get(k):
                pid = p[k]; break
        cb.addItem(p["name"], pid)
    return cb


def _category_id(db, preferred_names, fallback="other"):
    for name in preferred_names:
        r = db.execute(
            "SELECT category_id FROM categories WHERE LOWER(display_name)=LOWER(?) AND is_active=1",
            (name,)).fetchone()
        if r:
            return r["category_id"]
    return fallback


def _log_ledger_txn(tx_repo, db, *, account_id, pay_method, tx_type, amount,
                     person_org=None, description=None, category_names=("Finance", "Other")):
    cat = _category_id(db, category_names)
    return tx_repo.create(
        tx_date=TODAY(), account_id=account_id, pay_method=pay_method,
        tx_type=tx_type, amount=round(float(amount), 2), person_org=person_org,
        description=description, transaction_kind="REGULAR", category=cat,
        neednwant=0, pf_category=None,
    )


def _build_subnav(container_layout, labels):
    """Small secondary pill row + a matching QStackedWidget, pre-wired together."""
    nav = QHBoxLayout()
    btns = [QPushButton(l) for l in labels]
    for b in btns:
        nav.addWidget(b)
    nav.addStretch()
    container_layout.addLayout(nav)
    stack = QStackedWidget()
    container_layout.addWidget(stack)

    def goto(i):
        _switch_tabs(btns, i)
        stack.setCurrentIndex(i)

    for i, b in enumerate(btns):
        b.clicked.connect(lambda _, i=i: goto(i))
    _switch_tabs(btns, 0)
    return stack, btns


def _build_history_shell(container_lay, sort_options):
    stats_row = QHBoxLayout()
    container_lay.addLayout(stats_row)
    top = QHBoxLayout()
    lbl = QLabel("Sort by:"); lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;font-weight:600;")
    top.addWidget(lbl)
    sort_cb = QComboBox(); sort_cb.addItems(sort_options)
    top.addWidget(sort_cb); top.addStretch()
    container_lay.addLayout(top)
    table = QTableWidget()
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    container_lay.addWidget(table, 1)
    return stats_row, sort_cb, table


def _fill_stats_row(row_layout, cards):
    while row_layout.count():
        item = row_layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
    for c in cards:
        row_layout.addWidget(c)


def _confirm(parent, title, msg):
    return QMessageBox.question(parent, title, msg, QMessageBox.Yes | QMessageBox.No,
                                 QMessageBox.No) == QMessageBox.Yes


# ═══════════════════════════════════════════════
# MFAPI.IN — optional live NAV lookup (best-effort, never blocks manual entry)
# ═══════════════════════════════════════════════

def fetch_mf_search(query):
    url = f"https://api.mfapi.in/mf/search?q={urllib.parse.quote(query)}"
    with urllib.request.urlopen(url, timeout=6) as resp:
        return _json.loads(resp.read().decode())


def fetch_mf_latest_nav(scheme_code):
    url = f"https://api.mfapi.in/mf/{scheme_code}/latest"
    with urllib.request.urlopen(url, timeout=6) as resp:
        data = _json.loads(resp.read().decode())
    rows = data.get("data") or []
    return float(rows[0]["nav"]) if rows else None


class NavFetchDialog(QDialog):
    """Search AMFI schemes via mfapi.in and pick one to grab today's NAV."""

    def __init__(self, initial_query="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔎 Fetch Latest NAV")
        self.setMinimumWidth(480)
        self.result_nav = None
        self.result_name = None
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.query_box = QLineEdit(initial_query)
        self.query_box.setPlaceholderText("Scheme name, e.g. Parag Parikh Flexi Cap")
        search_btn = QPushButton("Search"); search_btn.setObjectName("primary")
        search_btn.clicked.connect(self._search)
        row.addWidget(self.query_box, 1); row.addWidget(search_btn)
        lay.addLayout(row)
        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(self._pick)
        lay.addWidget(self.results)
        info = QLabel("Double-click a scheme to fetch its latest NAV. Requires internet access.")
        info.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        lay.addWidget(info)
        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        btn_row.addStretch(); btn_row.addWidget(cancel)
        lay.addLayout(btn_row)
        if initial_query:
            self._search()

    def _search(self):
        q = self.query_box.text().strip()
        if not q:
            return
        self.results.clear()
        try:
            matches = fetch_mf_search(q)
        except Exception as e:
            QMessageBox.warning(self, "Search Failed",
                                 f"Couldn't reach mfapi.in ({e}). Enter the NAV manually instead.")
            return
        if not matches:
            self.results.addItem("No matches found.")
            return
        for m in matches[:30]:
            item_text = f"{m.get('schemeName', '?')}  [{m.get('schemeCode', '?')}]"
            self.results.addItem(item_text)
        self._matches = matches[:30]

    def _pick(self, item):
        idx = self.results.row(item)
        if not hasattr(self, "_matches") or idx >= len(self._matches):
            return
        m = self._matches[idx]
        try:
            nav = fetch_mf_latest_nav(m["schemeCode"])
        except Exception as e:
            QMessageBox.warning(self, "Fetch Failed", f"Couldn't fetch NAV ({e}).")
            return
        if nav is None:
            QMessageBox.warning(self, "No Data", "No NAV data available for that scheme.")
            return
        self.result_nav = nav
        self.result_name = m.get("schemeName")
        self.accept()


# ═══════════════════════════════════════════════
# BASE CLASS — Entry / List / History skeleton shared by all 5 functions
# ═══════════════════════════════════════════════

class _FunctionPage(QWidget):
    ICON = "💰"
    TITLE = "Function"

    def __init__(self, repos, services, parent=None):
        super().__init__(parent)
        self.repos = repos
        self.services = services
        self.db = repos["accounts"].db
        self._build_skeleton()

    def _build_skeleton(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)

        hdr = QLabel(f"{self.ICON}  {self.TITLE}")
        hdr.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        lay.addWidget(hdr)

        nav = QHBoxLayout()
        self.btn_entry = QPushButton("➕ Entry")
        self.btn_list = QPushButton("📋 List")
        self.btn_history = QPushButton("🕒 History")
        self._sub_btns = [self.btn_entry, self.btn_list, self.btn_history]
        for b in self._sub_btns:
            nav.addWidget(b)
        nav.addStretch()
        lay.addLayout(nav)

        self.sub_stack = QStackedWidget()
        lay.addWidget(self.sub_stack, 1)
        self.sub_stack.addWidget(self._build_entry())
        self.sub_stack.addWidget(self._build_list())
        self.sub_stack.addWidget(self._build_history())

        self.btn_entry.clicked.connect(lambda: self._goto(0))
        self.btn_list.clicked.connect(lambda: self._goto(1))
        self.btn_history.clicked.connect(lambda: self._goto(2))
        _switch_tabs(self._sub_btns, 1)
        self.sub_stack.setCurrentIndex(1)

    def _goto(self, idx):
        _switch_tabs(self._sub_btns, idx)
        self.sub_stack.setCurrentIndex(idx)
        if idx == 0:
            self._refresh_entry_dropdowns()
        elif idx == 1:
            self.load_list()
        elif idx == 2:
            self.load_history()

    def refresh(self):
        self._refresh_entry_dropdowns()
        self.load_list()
        self.load_history()

    def _scroll_area(self):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        v = QVBoxLayout(inner); v.setSpacing(10); v.setAlignment(Qt.AlignTop)
        scroll.setWidget(inner)
        return scroll, v

    # subclasses override these:
    def _build_entry(self): return QWidget()
    def _build_list(self): return QWidget()
    def _build_history(self): return QWidget()
    def _refresh_entry_dropdowns(self): pass
    def load_list(self): pass
    def load_history(self): pass


# ═══════════════════════════════════════════════
# FUNCTION 1 — LOANS I GIVE  (asset: people owe me)
# ═══════════════════════════════════════════════

class LoansGivePage(_FunctionPage):
    ICON = "🤝"; TITLE = "Loans I Give"

    def _build_entry(self):
        page = QWidget(); lay = QVBoxLayout(page)
        self.lg_entry_stack, _ = _build_subnav(lay, ["New Borrower", "New Loan", "Log Repayment"])

        # -- New Borrower --
        p1 = QWidget(); f1 = QFormLayout(p1)
        self.lg_borrower_name = QLineEdit(); self.lg_borrower_name.setPlaceholderText("Full name")
        add_b = QPushButton("➕ Add Borrower"); add_b.setObjectName("primary")
        add_b.clicked.connect(self._add_borrower)
        f1.addRow("Name *", self.lg_borrower_name)
        f1.addRow("", add_b)
        self.lg_entry_stack.addWidget(p1)

        # -- New Loan --
        p2 = QWidget(); f2 = QFormLayout(p2)
        self.lg_loan_borrower = _person_combo(self.repos["loans"].list_borrowers, ["borrower_id"])
        self.lg_loan_amount = QDoubleSpinBox(); self.lg_loan_amount.setRange(0, 99999999)
        self.lg_loan_amount.setPrefix("₹ "); self.lg_loan_amount.setDecimals(2)
        self.lg_loan_account = _account_combo(self.repos["accounts"])
        self.lg_loan_method = _method_combo(self.repos["lookups"])
        self.lg_loan_start = QDateEdit(QDate.currentDate()); self.lg_loan_start.setCalendarPopup(True)
        self.lg_loan_due = QDateEdit(QDate.currentDate().addDays(30)); self.lg_loan_due.setCalendarPopup(True)
        self.lg_loan_desc = QLineEdit(); self.lg_loan_desc.setPlaceholderText("Optional note")
        f2.addRow("Borrower *", self.lg_loan_borrower)
        f2.addRow("Loan Amount *", self.lg_loan_amount)
        f2.addRow("Pay From *", self.lg_loan_account)
        f2.addRow("Method *", self.lg_loan_method)
        f2.addRow("Start Date", self.lg_loan_start)
        f2.addRow("Due Date", self.lg_loan_due)
        f2.addRow("Description", self.lg_loan_desc)
        give_btn = QPushButton("🤝  Give Loan"); give_btn.setObjectName("primary")
        give_btn.clicked.connect(self._give_loan)
        f2.addRow("", give_btn)
        self.lg_entry_stack.addWidget(p2)

        # -- Log Repayment --
        p3 = QWidget(); f3 = QFormLayout(p3)
        self.lg_rep_loan = QComboBox()
        self.lg_rep_pending_lbl = QLabel("")
        self.lg_rep_pending_lbl.setStyleSheet(f"color:{C['amber']};font-weight:700;font-size:12px;")
        self.lg_rep_loan.currentIndexChanged.connect(self._update_lg_pending_label)
        self.lg_rep_amount = QDoubleSpinBox(); self.lg_rep_amount.setRange(0, 99999999)
        self.lg_rep_amount.setPrefix("₹ "); self.lg_rep_amount.setDecimals(2)
        self.lg_rep_account = _account_combo(self.repos["accounts"])
        self.lg_rep_method = _method_combo(self.repos["lookups"])
        self.lg_rep_date = QDateEdit(QDate.currentDate()); self.lg_rep_date.setCalendarPopup(True)
        self.lg_rep_desc = QLineEdit(); self.lg_rep_desc.setPlaceholderText("Optional note")
        f3.addRow("Loan *", self.lg_rep_loan)
        f3.addRow("", self.lg_rep_pending_lbl)
        f3.addRow("Amount Received *", self.lg_rep_amount)
        f3.addRow("Into Account *", self.lg_rep_account)
        f3.addRow("Method *", self.lg_rep_method)
        f3.addRow("Date", self.lg_rep_date)
        f3.addRow("Description", self.lg_rep_desc)
        rep_btn = QPushButton("💰  Log Repayment"); rep_btn.setObjectName("primary")
        rep_btn.clicked.connect(self._log_repayment)
        f3.addRow("", rep_btn)
        self.lg_entry_stack.addWidget(p3)

        return page

    def _refresh_entry_dropdowns(self):
        self.lg_loan_borrower.clear()
        for b in self.repos["loans"].list_borrowers():
            self.lg_loan_borrower.addItem(b["name"], b["borrower_id"])
        self.lg_rep_loan.clear()
        for l in self.repos["loans"].list_loans():
            if l["status"] != "CLOSED":
                self.lg_rep_loan.addItem(f"{l['borrower_name']} — {fmt_money(l['loan_amount'])} ({l['status']})",
                                          l["loan_id"])
        self._update_lg_pending_label()

    def _update_lg_pending_label(self):
        lid = self.lg_rep_loan.currentData()
        if not lid:
            self.lg_rep_pending_lbl.setText(""); return
        loan = self.repos["loans"].get_loan(lid)
        if not loan:
            return
        paid = self.repos["loans"].total_repaid(lid)
        pending = loan["loan_amount"] - paid
        self.lg_rep_pending_lbl.setText(f"Pending: {fmt_money(pending)} of {fmt_money(loan['loan_amount'])}")

    def _add_borrower(self):
        name = self.lg_borrower_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter the borrower's name."); return
        self.repos["loans"].create_borrower(name)
        self.lg_borrower_name.clear()
        self._refresh_entry_dropdowns()
        QMessageBox.information(self, "Added", f"'{name}' added to your borrower directory.")

    def _give_loan(self):
        bid = self.lg_loan_borrower.currentData()
        amount = self.lg_loan_amount.value()
        if not bid or amount <= 0:
            QMessageBox.warning(self, "Missing Info", "Please select a borrower and enter an amount."); return
        account_id = self.lg_loan_account.currentData()
        method = self.lg_loan_method.currentData()
        borrower_name = self.lg_loan_borrower.currentText()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="DEBIT", amount=amount, person_org=borrower_name,
            description=f"Loan given to {borrower_name}", category_names=("Finance", "Other"))
        self.repos["loans"].create_loan(
            borrower_id=bid, loan_amount=amount, payment_method=method,
            start_date=self.lg_loan_start.date().toString("yyyy-MM-dd"),
            due_date=self.lg_loan_due.date().toString("yyyy-MM-dd"),
            status="ACTIVE", description=self.lg_loan_desc.text().strip() or None, trxn_id=txn_id)
        self.lg_loan_amount.setValue(0); self.lg_loan_desc.clear()
        self._refresh_entry_dropdowns(); self.load_list(); self.load_history()
        QMessageBox.information(self, "Loan Recorded", f"₹{amount:,.2f} loan to {borrower_name} recorded.")

    def _log_repayment(self):
        lid = self.lg_rep_loan.currentData()
        amount = self.lg_rep_amount.value()
        if not lid or amount <= 0:
            QMessageBox.warning(self, "Missing Info", "Please select a loan and enter an amount."); return
        loan = self.repos["loans"].get_loan(lid)
        account_id = self.lg_rep_account.currentData()
        method = self.lg_rep_method.currentData()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="CREDIT", amount=amount, person_org=loan["borrower_name"] if loan else None,
            description=f"Loan repayment from {loan['borrower_name']}" if loan else "Loan repayment",
            category_names=("Finance", "Other"))
        self.repos["loans"].add_repayment(
            loan_id=lid, amount_paid=amount, payment_date=self.lg_rep_date.date().toString("yyyy-MM-dd"),
            payment_method=method, description=self.lg_rep_desc.text().strip() or None, linked_txn_id=txn_id)
        self.lg_rep_amount.setValue(0); self.lg_rep_desc.clear()
        self._refresh_entry_dropdowns(); self.load_list(); self.load_history()
        QMessageBox.information(self, "Repayment Logged", "Repayment recorded successfully.")

    def _build_list(self):
        page = QWidget(); lay = QVBoxLayout(page)
        scroll, self.lg_list_lay = self._scroll_area()
        lay.addWidget(scroll)
        return page

    def load_list(self):
        self.repos["loans"].sync_overdue()
        for i in reversed(range(self.lg_list_lay.count())):
            w = self.lg_list_lay.itemAt(i).widget()
            if w: w.deleteLater()
        loans = self.repos["loans"].list_loans()
        if not loans:
            empty = QLabel("No loans given yet."); empty.setStyleSheet(f"color:{C['text3']};padding:20px;")
            empty.setAlignment(Qt.AlignCenter); self.lg_list_lay.addWidget(empty); return
        for l in loans:
            paid = self.repos["loans"].total_repaid(l["loan_id"])
            pending = l["loan_amount"] - paid
            pct = (paid / l["loan_amount"] * 100) if l["loan_amount"] else 0
            color = status_color("asset", l["status"])
            card = _wealth_card(
                title=l["borrower_name"], subtitle=f"Given {l['start_date']} · Due {l['due_date'] or '—'}",
                amount_text=fmt_money(pending) + " pending", badge_text=l["status"], badge_color=color,
                progress_pct=pct, extra_line=f"Loan: {fmt_money(l['loan_amount'])} · Repaid: {fmt_money(paid)}",
                on_click=lambda lid=l["loan_id"]: self._open_detail(lid))
            self.lg_list_lay.addWidget(card)

    def _open_detail(self, loan_id):
        loan = self.repos["loans"].get_loan(loan_id)
        if not loan:
            return
        repayments = self.repos["loans"].get_repayments(loan_id)
        dlg = LoanDetailDialog(role="give", title=f"Loan to {loan['borrower_name']}",
                                principal=loan["loan_amount"], status=loan["status"],
                                start_date=loan["start_date"], due_date=loan["due_date"],
                                description=loan.get("description"), repayments=repayments,
                                amount_key="amount_paid", date_key="payment_date", parent=self)
        dlg.exec_()

    def _build_history(self):
        page = QWidget(); lay = QVBoxLayout(page)
        self.lg_stats_row, self.lg_sort_cb, self.lg_hist_table = _build_history_shell(
            lay, ["Status", "Loan ID", "Person"])
        self.lg_sort_cb.currentIndexChanged.connect(self.load_history)
        self.lg_hist_table.setColumnCount(6)
        self.lg_hist_table.setHorizontalHeaderLabels(
            ["Borrower", "Loan Amount", "Repaid", "Pending", "Status", "Due Date"])
        self.lg_hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        return page

    def load_history(self):
        self.repos["loans"].sync_overdue()
        loans = self.repos["loans"].list_loans()
        total_pending = sum(max(l["loan_amount"] - self.repos["loans"].total_repaid(l["loan_id"]), 0)
                             for l in loans if l["status"] != "CLOSED")
        pending_count = len([l for l in loans if l["status"] != "CLOSED"])
        _fill_stats_row(self.lg_stats_row, [
            _metric_card("Total Pending", fmt_money(total_pending), C["amber"]),
            _metric_card("Pending Loans", str(pending_count)),
            _metric_card("Total Loans", str(len(loans))),
        ])
        sort_mode = self.lg_sort_cb.currentText()
        rank = {"ACTIVE": 0, "OVERDUE": 1, "PARTIALLY_PAID": 2, "CLOSED": 3}
        if sort_mode == "Status":
            loans.sort(key=lambda l: rank.get(l["status"], 9))
        elif sort_mode == "Loan ID":
            loans.sort(key=lambda l: l["loan_id"])
        else:
            loans.sort(key=lambda l: l["borrower_name"])

        self.lg_hist_table.setRowCount(len(loans))
        for i, l in enumerate(loans):
            paid = self.repos["loans"].total_repaid(l["loan_id"])
            pending = l["loan_amount"] - paid
            self.lg_hist_table.setItem(i, 0, QTableWidgetItem(l["borrower_name"]))
            self.lg_hist_table.setItem(i, 1, QTableWidgetItem(fmt_money(l["loan_amount"])))
            self.lg_hist_table.setItem(i, 2, QTableWidgetItem(fmt_money(paid)))
            self.lg_hist_table.setItem(i, 3, QTableWidgetItem(fmt_money(pending)))
            self.lg_hist_table.setItem(i, 4, QTableWidgetItem(l["status"]))
            self.lg_hist_table.setItem(i, 5, QTableWidgetItem(l["due_date"] or "—"))


# ═══════════════════════════════════════════════
# FUNCTION 2 — LOANS I TAKE  (liability: I owe an institution/person)
# ═══════════════════════════════════════════════

class LoansTakePage(_FunctionPage):
    ICON = "🏛️"; TITLE = "Loans I Take"

    def _build_entry(self):
        page = QWidget(); lay = QVBoxLayout(page)
        self.lt_entry_stack, _ = _build_subnav(lay, ["New Lender", "New Loan (EMI)", "Log EMI Payment"])

        # -- New Lender --
        p1 = QWidget(); f1 = QFormLayout(p1)
        self.lt_lender_name = QLineEdit(); self.lt_lender_name.setPlaceholderText("Bank / NBFC / person name")
        add_l = QPushButton("➕ Add Lender"); add_l.setObjectName("primary")
        add_l.clicked.connect(self._add_lender)
        f1.addRow("Name *", self.lt_lender_name)
        f1.addRow("", add_l)
        self.lt_entry_stack.addWidget(p1)

        # -- New Loan (EMI) --
        p2 = QWidget(); f2 = QFormLayout(p2)
        self.lt_loan_lender = _person_combo(self.repos["borrowed"].list_lenders, ["lender_id"])
        self.lt_loan_principal = QDoubleSpinBox(); self.lt_loan_principal.setRange(0, 999999999)
        self.lt_loan_principal.setPrefix("₹ "); self.lt_loan_principal.setDecimals(2)
        self.lt_loan_rate = QDoubleSpinBox(); self.lt_loan_rate.setRange(0, 60); self.lt_loan_rate.setSuffix(" %")
        self.lt_loan_rate.setDecimals(2)
        self.lt_loan_months = QSpinBox(); self.lt_loan_months.setRange(1, 480); self.lt_loan_months.setValue(12)
        self.lt_loan_account = _account_combo(self.repos["accounts"])
        self.lt_loan_method = _method_combo(self.repos["lookups"])
        self.lt_loan_start = QDateEdit(QDate.currentDate()); self.lt_loan_start.setCalendarPopup(True)
        self.lt_loan_desc = QLineEdit(); self.lt_loan_desc.setPlaceholderText("Optional note")
        self.lt_emi_preview = QLabel("Estimated EMI: —")
        self.lt_emi_preview.setStyleSheet(f"color:{C['accent']};font-weight:800;font-size:13px;")
        for w in (self.lt_loan_principal, self.lt_loan_rate, self.lt_loan_months):
            if isinstance(w, QDoubleSpinBox):
                w.valueChanged.connect(self._update_emi_preview)
            else:
                w.valueChanged.connect(self._update_emi_preview)
        f2.addRow("Lender *", self.lt_loan_lender)
        f2.addRow("Principal *", self.lt_loan_principal)
        f2.addRow("Interest Rate (annual)", self.lt_loan_rate)
        f2.addRow("Tenure (months) *", self.lt_loan_months)
        f2.addRow("", self.lt_emi_preview)
        f2.addRow("Received Into *", self.lt_loan_account)
        f2.addRow("Method *", self.lt_loan_method)
        f2.addRow("Start Date", self.lt_loan_start)
        f2.addRow("Description", self.lt_loan_desc)
        take_btn = QPushButton("🏛️  Take Loan"); take_btn.setObjectName("primary")
        take_btn.clicked.connect(self._take_loan)
        f2.addRow("", take_btn)
        self.lt_entry_stack.addWidget(p2)
        self._update_emi_preview()

        # -- Log EMI Payment --
        p3 = QWidget(); f3 = QFormLayout(p3)
        self.lt_rep_loan = QComboBox()
        self.lt_rep_amount = QDoubleSpinBox(); self.lt_rep_amount.setRange(0, 99999999)
        self.lt_rep_amount.setPrefix("₹ "); self.lt_rep_amount.setDecimals(2)
        self.lt_rep_account = _account_combo(self.repos["accounts"])
        self.lt_rep_method = _method_combo(self.repos["lookups"])
        self.lt_rep_date = QDateEdit(QDate.currentDate()); self.lt_rep_date.setCalendarPopup(True)
        self.lt_rep_desc = QLineEdit(); self.lt_rep_desc.setPlaceholderText("Optional note")
        self.lt_rep_loan.currentIndexChanged.connect(self._prefill_emi_amount)
        f3.addRow("Loan *", self.lt_rep_loan)
        f3.addRow("EMI Amount *", self.lt_rep_amount)
        f3.addRow("Pay From *", self.lt_rep_account)
        f3.addRow("Method *", self.lt_rep_method)
        f3.addRow("Date", self.lt_rep_date)
        f3.addRow("Description", self.lt_rep_desc)
        pay_btn = QPushButton("💸  Log EMI Payment"); pay_btn.setObjectName("primary")
        pay_btn.clicked.connect(self._log_emi_payment)
        f3.addRow("", pay_btn)
        self.lt_entry_stack.addWidget(p3)

        return page

    def _update_emi_preview(self):
        p = self.lt_loan_principal.value(); r = self.lt_loan_rate.value(); m = self.lt_loan_months.value()
        if p > 0 and m > 0:
            emi = LoanService.emi(p, r, m)
            self.lt_emi_preview.setText(f"Estimated EMI: {fmt_money(emi)} / month for {m} months")
        else:
            self.lt_emi_preview.setText("Estimated EMI: —")

    def _refresh_entry_dropdowns(self):
        self.lt_loan_lender.clear()
        for l in self.repos["borrowed"].list_lenders():
            self.lt_loan_lender.addItem(l["name"], l["lender_id"])
        self.lt_rep_loan.clear()
        for l in self.repos["borrowed"].list_loans():
            if l["status"] != "CLOSED":
                self.lt_rep_loan.addItem(
                    f"{l['lender_name']} — {fmt_money(l['principal_amount'])} ({l['status']})", l["loan_id"])
        self._prefill_emi_amount()

    def _prefill_emi_amount(self):
        lid = self.lt_rep_loan.currentData()
        if not lid:
            return
        loan = self.repos["borrowed"].get_loan(lid)
        if loan and loan.get("emi_amount"):
            self.lt_rep_amount.setValue(loan["emi_amount"])

    def _add_lender(self):
        name = self.lt_lender_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter the lender's name."); return
        self.repos["borrowed"].create_lender(name)
        self.lt_lender_name.clear()
        self._refresh_entry_dropdowns()
        QMessageBox.information(self, "Added", f"'{name}' added to your lender directory.")

    def _take_loan(self):
        lid = self.lt_loan_lender.currentData()
        principal = self.lt_loan_principal.value()
        months = self.lt_loan_months.value()
        rate = self.lt_loan_rate.value()
        if not lid or principal <= 0:
            QMessageBox.warning(self, "Missing Info", "Please select a lender and enter the principal."); return
        emi = LoanService.emi(principal, rate, months)
        start = self.lt_loan_start.date().toPyDate()
        due = _add_months(start, months)
        account_id = self.lt_loan_account.currentData()
        method = self.lt_loan_method.currentData()
        lender_name = self.lt_loan_lender.currentText()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="CREDIT", amount=principal, person_org=lender_name,
            description=f"Loan taken from {lender_name}", category_names=("Finance", "Other"))
        self.repos["borrowed"].create_loan(
            lender_id=lid, principal_amount=principal, interest_rate=rate, emi_amount=emi,
            start_date=start.isoformat(), due_date=due.isoformat(), status="ACTIVE",
            description=self.lt_loan_desc.text().strip() or None, linked_txn_id=txn_id)
        self.lt_loan_principal.setValue(0); self.lt_loan_desc.clear()
        self._refresh_entry_dropdowns(); self.load_list(); self.load_history()
        QMessageBox.information(self, "Loan Recorded",
                                 f"₹{principal:,.2f} loan from {lender_name} recorded. EMI ≈ {fmt_money(emi)}/mo.")

    def _log_emi_payment(self):
        lid = self.lt_rep_loan.currentData()
        amount = self.lt_rep_amount.value()
        if not lid or amount <= 0:
            QMessageBox.warning(self, "Missing Info", "Please select a loan and enter an amount."); return
        loan = self.repos["borrowed"].get_loan(lid)
        account_id = self.lt_rep_account.currentData()
        method = self.lt_rep_method.currentData()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="DEBIT", amount=amount, person_org=loan["lender_name"] if loan else None,
            description=f"EMI payment to {loan['lender_name']}" if loan else "EMI payment",
            category_names=("Finance", "Other"))
        self.repos["borrowed"].add_repayment(
            loan_id=lid, amount_paid=amount, payment_date=self.lt_rep_date.date().toString("yyyy-MM-dd"),
            payment_method=method, description=self.lt_rep_desc.text().strip() or None, linked_txn_id=txn_id)
        self.lt_rep_desc.clear()
        self._refresh_entry_dropdowns(); self.load_list(); self.load_history()
        QMessageBox.information(self, "Payment Logged", "EMI payment recorded successfully.")

    def _build_list(self):
        page = QWidget(); lay = QVBoxLayout(page)
        scroll, self.lt_list_lay = self._scroll_area()
        lay.addWidget(scroll)
        return page

    def load_list(self):
        self.repos["borrowed"].sync_overdue()
        for i in reversed(range(self.lt_list_lay.count())):
            w = self.lt_list_lay.itemAt(i).widget()
            if w: w.deleteLater()
        loans = self.repos["borrowed"].list_loans()
        if not loans:
            empty = QLabel("No loans taken yet."); empty.setStyleSheet(f"color:{C['text3']};padding:20px;")
            empty.setAlignment(Qt.AlignCenter); self.lt_list_lay.addWidget(empty); return
        for l in loans:
            paid = self.repos["borrowed"].total_repaid(l["loan_id"])
            color = status_color("liability", l["status"])
            subtitle = f"Rate {l['interest_rate']}% · EMI {fmt_money(l['emi_amount'])} · Due {l['due_date'] or '—'}"
            card = _wealth_card(
                title=l["lender_name"], subtitle=subtitle,
                amount_text=fmt_money(l["principal_amount"]), badge_text=l["status"], badge_color=color,
                extra_line=f"Repaid so far: {fmt_money(paid)}",
                on_click=lambda lid=l["loan_id"]: self._open_detail(lid))
            self.lt_list_lay.addWidget(card)

    def _open_detail(self, loan_id):
        loan = self.repos["borrowed"].get_loan(loan_id)
        if not loan:
            return
        repayments = self.repos["borrowed"].get_repayments(loan_id)
        start = date.fromisoformat(loan["start_date"])
        due = date.fromisoformat(loan["due_date"]) if loan["due_date"] else None
        months = max(1, round((due - start).days / 30.44)) if due else 12
        amort = LoanService.amortize(loan["principal_amount"], loan["interest_rate"] or 0, months)
        dlg = LoanDetailDialog(role="take", title=f"Loan from {loan['lender_name']}",
                                principal=loan["principal_amount"], status=loan["status"],
                                start_date=loan["start_date"], due_date=loan["due_date"],
                                description=loan.get("description"), repayments=repayments,
                                amount_key="amount_paid", date_key="payment_date",
                                amortization=amort, emi=loan["emi_amount"], rate=loan["interest_rate"],
                                on_mark_closed=lambda: self._mark_closed(loan_id), parent=self)
        dlg.exec_()

    def _mark_closed(self, loan_id):
        if _confirm(self, "Mark Closed", "Mark this loan as fully closed?"):
            self.repos["borrowed"].update_status(loan_id, "CLOSED")
            self.load_list(); self.load_history()
            return True
        return False

    def _build_history(self):
        page = QWidget(); lay = QVBoxLayout(page)
        self.lt_stats_row, self.lt_sort_cb, self.lt_hist_table = _build_history_shell(
            lay, ["Status", "Loan ID", "Person"])
        self.lt_sort_cb.currentIndexChanged.connect(self.load_history)
        self.lt_hist_table.setColumnCount(6)
        self.lt_hist_table.setHorizontalHeaderLabels(
            ["Lender", "Principal", "EMI", "Repaid", "Status", "Due Date"])
        self.lt_hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        return page

    def load_history(self):
        self.repos["borrowed"].sync_overdue()
        loans = self.repos["borrowed"].list_loans()
        active = [l for l in loans if l["status"] != "CLOSED"]
        total_pending = sum(max(l["principal_amount"] - self.repos["borrowed"].total_repaid(l["loan_id"]), 0)
                             for l in active)
        _fill_stats_row(self.lt_stats_row, [
            _metric_card("Total Pending", fmt_money(total_pending), C["amber"]),
            _metric_card("Active Loans", str(len(active))),
            _metric_card("Total Loans", str(len(loans))),
        ])
        sort_mode = self.lt_sort_cb.currentText()
        rank = {"ACTIVE": 0, "OVERDUE": 1, "CLOSED": 2}
        if sort_mode == "Status":
            loans.sort(key=lambda l: rank.get(l["status"], 9))
        elif sort_mode == "Loan ID":
            loans.sort(key=lambda l: l["loan_id"])
        else:
            loans.sort(key=lambda l: l["lender_name"])

        self.lt_hist_table.setRowCount(len(loans))
        for i, l in enumerate(loans):
            paid = self.repos["borrowed"].total_repaid(l["loan_id"])
            self.lt_hist_table.setItem(i, 0, QTableWidgetItem(l["lender_name"]))
            self.lt_hist_table.setItem(i, 1, QTableWidgetItem(fmt_money(l["principal_amount"])))
            self.lt_hist_table.setItem(i, 2, QTableWidgetItem(fmt_money(l["emi_amount"])))
            self.lt_hist_table.setItem(i, 3, QTableWidgetItem(fmt_money(paid)))
            self.lt_hist_table.setItem(i, 4, QTableWidgetItem(l["status"]))
            self.lt_hist_table.setItem(i, 5, QTableWidgetItem(l["due_date"] or "—"))


# ═══════════════════════════════════════════════
# Shared Loan Detail dialog (used by both Give & Take)
# ═══════════════════════════════════════════════

class LoanDetailDialog(QDialog):
    def __init__(self, role, title, principal, status, start_date, due_date, description,
                 repayments, amount_key, date_key, amortization=None, emi=None, rate=None,
                 on_mark_closed=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title); self.setMinimumWidth(560)
        lay = QVBoxLayout(self)

        hdr = QHBoxLayout()
        t = QLabel(title); t.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        hdr.addWidget(t, 1)
        color = status_color("asset" if role == "give" else "liability", status)
        hdr.addWidget(_badge(status, color))
        lay.addLayout(hdr)

        info_bits = [f"Principal: {fmt_money(principal)}", f"Start: {start_date}", f"Due: {due_date or '—'}"]
        if rate is not None:
            info_bits.insert(1, f"Rate: {rate}%")
        if emi is not None:
            info_bits.insert(2, f"EMI: {fmt_money(emi)}")
        info = QLabel(" · ".join(info_bits))
        info.setStyleSheet(f"color:{C['text3']};font-size:12px;")
        info.setWordWrap(True)
        lay.addWidget(info)
        if description:
            d = QLabel(description); d.setStyleSheet(f"color:{C['text2']};font-size:12px;font-style:italic;")
            d.setWordWrap(True); lay.addWidget(d)

        total_paid = sum(r[amount_key] for r in repayments)
        summary = QLabel(f"Total Repaid: {fmt_money(total_paid)}  ·  Remaining: {fmt_money(max(principal - total_paid, 0))}")
        summary.setStyleSheet(f"color:{C['text']};font-weight:700;font-size:12px;padding-top:6px;")
        lay.addWidget(summary)

        if amortization:
            tabs = QTabWidget()
            tabs.addTab(self._repayments_table(repayments, amount_key, date_key), "Repayment Log")
            tabs.addTab(self._amortization_table(amortization), "Amortization Schedule (approx.)")
            lay.addWidget(tabs, 1)
        else:
            lay.addWidget(self._repayments_table(repayments, amount_key, date_key), 1)

        btn_row = QHBoxLayout(); btn_row.addStretch()
        if on_mark_closed and status != "CLOSED":
            close_btn = QPushButton("✅ Mark as Closed"); close_btn.setObjectName("primary")
            close_btn.clicked.connect(lambda: (on_mark_closed(), self.accept()))
            btn_row.addWidget(close_btn)
        ok = QPushButton("Close"); ok.clicked.connect(self.accept)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)

    def _repayments_table(self, repayments, amount_key, date_key):
        table = QTableWidget()
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Date", "Amount", "Description"])
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.setRowCount(len(repayments))
        for i, r in enumerate(repayments):
            table.setItem(i, 0, QTableWidgetItem(r.get(date_key, "")))
            table.setItem(i, 1, QTableWidgetItem(fmt_money(r[amount_key])))
            table.setItem(i, 2, QTableWidgetItem(r.get("description") or ""))
        if not repayments:
            table.setRowCount(1)
            item = QTableWidgetItem("No repayments logged yet.")
            table.setItem(0, 0, item); table.setSpan(0, 0, 1, 3)
        return table

    def _amortization_table(self, schedule):
        table = QTableWidget()
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Month", "EMI", "Principal", "Interest", "Balance"])
        table.setRowCount(len(schedule))
        for i, row in enumerate(schedule):
            table.setItem(i, 0, QTableWidgetItem(str(row["month"])))
            table.setItem(i, 1, QTableWidgetItem(fmt_money(row["emi"])))
            table.setItem(i, 2, QTableWidgetItem(fmt_money(row["principal"])))
            table.setItem(i, 3, QTableWidgetItem(fmt_money(row["interest"])))
            table.setItem(i, 4, QTableWidgetItem(fmt_money(row["balance"])))
        return table


# ═══════════════════════════════════════════════
# FUNCTION 3 — FD I DEPOSIT  (asset: my money, growing)
# ═══════════════════════════════════════════════

class FDGivePage(_FunctionPage):
    ICON = "🏦"; TITLE = "FD I Deposit"

    def _build_entry(self):
        page = QWidget(); f = QFormLayout(page)
        self.fd_principal = QDoubleSpinBox(); self.fd_principal.setRange(0, 999999999)
        self.fd_principal.setPrefix("₹ "); self.fd_principal.setDecimals(2)
        self.fd_rate = QDoubleSpinBox(); self.fd_rate.setRange(0, 20); self.fd_rate.setSuffix(" %")
        self.fd_rate.setDecimals(2); self.fd_rate.setValue(7.0)
        self.fd_start = QDateEdit(QDate.currentDate()); self.fd_start.setCalendarPopup(True)
        self.fd_maturity = QDateEdit(QDate.currentDate().addYears(1)); self.fd_maturity.setCalendarPopup(True)
        self.fd_account = _account_combo(self.repos["accounts"])
        self.fd_maturity_preview = QLabel("Estimated Maturity Amount: —")
        self.fd_maturity_preview.setStyleSheet(f"color:{C['green']};font-weight:800;font-size:13px;")
        for w in (self.fd_principal, self.fd_rate):
            w.valueChanged.connect(self._update_maturity_preview)
        self.fd_start.dateChanged.connect(self._update_maturity_preview)
        self.fd_maturity.dateChanged.connect(self._update_maturity_preview)
        f.addRow("Bank Account *", self.fd_account)
        f.addRow("Principal *", self.fd_principal)
        f.addRow("Interest Rate (annual) *", self.fd_rate)
        f.addRow("Start Date", self.fd_start)
        f.addRow("Maturity Date *", self.fd_maturity)
        f.addRow("", self.fd_maturity_preview)
        create_btn = QPushButton("🏦  Create Fixed Deposit"); create_btn.setObjectName("primary")
        create_btn.clicked.connect(self._create_fd)
        f.addRow("", create_btn)
        self._update_maturity_preview()
        return page

    def _update_maturity_preview(self):
        p = self.fd_principal.value(); r = self.fd_rate.value()
        s = self.fd_start.date().toString("yyyy-MM-dd"); m = self.fd_maturity.date().toString("yyyy-MM-dd")
        if p > 0 and self.fd_maturity.date() > self.fd_start.date():
            amt = FDService.maturity(p, r, s, m)
            self.fd_maturity_preview.setText(f"Estimated Maturity Amount: {fmt_money(amt)} (quarterly compounding)")
        else:
            self.fd_maturity_preview.setText("Estimated Maturity Amount: —")

    def _refresh_entry_dropdowns(self):
        pass

    def _create_fd(self):
        p = self.fd_principal.value()
        if p <= 0:
            QMessageBox.warning(self, "Missing Info", "Please enter the deposit principal."); return
        if self.fd_maturity.date() <= self.fd_start.date():
            QMessageBox.warning(self, "Invalid Dates", "Maturity date must be after the start date."); return
        account_id = self.fd_account.currentData()
        account_name = self.fd_account.currentText()
        default_method = self.repos["lookups"].list_methods()
        method_id = default_method[0]["method_id"] if default_method else None
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method_id,
            tx_type="DEBIT", amount=p, person_org=None,
            description=f"FD deposit at {account_name}", category_names=("Investment", "Finance"))
        self.repos["fd"].create(
            bank_account_id=account_id, principal_amount=p, interest_rate=self.fd_rate.value(),
            start_date=self.fd_start.date().toString("yyyy-MM-dd"),
            maturity_date=self.fd_maturity.date().toString("yyyy-MM-dd"),
            status="ACTIVE", linked_txn_id=txn_id)
        self.fd_principal.setValue(0)
        self.load_list(); self.load_history()
        QMessageBox.information(self, "FD Created", "Fixed deposit recorded successfully.")

    def _build_list(self):
        page = QWidget(); lay = QVBoxLayout(page)
        scroll, self.fd_list_lay = self._scroll_area()
        lay.addWidget(scroll)
        return page

    def load_list(self):
        self.repos["fd"].sync_matured()
        for i in reversed(range(self.fd_list_lay.count())):
            w = self.fd_list_lay.itemAt(i).widget()
            if w: w.deleteLater()
        fds = self.repos["fd"].list_all()
        if not fds:
            empty = QLabel("No fixed deposits yet."); empty.setStyleSheet(f"color:{C['text3']};padding:20px;")
            empty.setAlignment(Qt.AlignCenter); self.fd_list_lay.addWidget(empty); return
        for fd in fds:
            pct = FDService.progress(fd["start_date"], fd["maturity_date"])
            color = status_color("asset", fd["status"])
            card = _wealth_card(
                title=fd["account_name"] or "Fixed Deposit",
                subtitle=f"{fd['interest_rate']}% · {fd['start_date']} → {fd['maturity_date']}",
                amount_text=fmt_money(fd["maturity_amount"] or fd["principal_amount"]),
                badge_text=fd["status"], badge_color=color, progress_pct=pct,
                extra_line=f"Principal: {fmt_money(fd['principal_amount'])} · {pct:.0f}% elapsed",
                on_click=lambda fid=fd["fd_id"]: self._open_detail(fid))
            self.fd_list_lay.addWidget(card)

    def _open_detail(self, fd_id):
        fd = self.repos["fd"].get(fd_id)
        if not fd:
            return
        dlg = FDDetailDialog(fd, on_mark_matured=lambda: self._mark_matured(fd_id),
                              on_mark_withdrawn=lambda acc, method: self._mark_withdrawn(fd_id, acc, method),
                              accounts_repo=self.repos["accounts"], lookups_repo=self.repos["lookups"],
                              parent=self)
        dlg.exec_()

    def _mark_matured(self, fd_id):
        if _confirm(self, "Mark Matured", "Mark this FD as matured?"):
            self.repos["fd"].update_status(fd_id, "MATURED")
            self.load_list(); self.load_history()
            return True
        return False

    def _mark_withdrawn(self, fd_id, account_id, method_id):
        fd = self.repos["fd"].get(fd_id)
        if not fd:
            return False
        amount = fd["maturity_amount"] or fd["principal_amount"]
        _log_ledger_txn(self.repos["transactions"], self.db, account_id=account_id, pay_method=method_id,
                         tx_type="CREDIT", amount=amount, person_org=None,
                         description="FD maturity withdrawal", category_names=("Investment", "Finance"))
        self.repos["fd"].update_status(fd_id, "WITHDRAWN")
        self.load_list(); self.load_history()
        return True

    def _build_history(self):
        page = QWidget(); lay = QVBoxLayout(page)
        self.fd_stats_row, self.fd_sort_cb, self.fd_hist_table = _build_history_shell(
            lay, ["Status", "FD ID", "Maturity Date"])
        self.fd_sort_cb.currentIndexChanged.connect(self.load_history)
        self.fd_hist_table.setColumnCount(6)
        self.fd_hist_table.setHorizontalHeaderLabels(
            ["Account", "Principal", "Rate", "Maturity Amount", "Status", "Maturity Date"])
        self.fd_hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        return page

    def load_history(self):
        self.repos["fd"].sync_matured()
        fds = self.repos["fd"].list_all()
        total_principal = sum(f["principal_amount"] for f in fds)
        total_maturity = sum(f["maturity_amount"] or f["principal_amount"] for f in fds)
        _fill_stats_row(self.fd_stats_row, [
            _metric_card("Total Invested", fmt_money(total_principal)),
            _metric_card("Total Maturity Value", fmt_money(total_maturity), C["green"]),
            _metric_card("Total FDs", str(len(fds))),
        ])
        sort_mode = self.fd_sort_cb.currentText()
        rank = {"ACTIVE": 0, "MATURED": 1, "WITHDRAWN": 2}
        if sort_mode == "Status":
            fds.sort(key=lambda f: rank.get(f["status"], 9))
        elif sort_mode == "FD ID":
            fds.sort(key=lambda f: f["fd_id"])
        else:
            fds.sort(key=lambda f: f["maturity_date"])

        self.fd_hist_table.setRowCount(len(fds))
        for i, f in enumerate(fds):
            self.fd_hist_table.setItem(i, 0, QTableWidgetItem(f["account_name"] or ""))
            self.fd_hist_table.setItem(i, 1, QTableWidgetItem(fmt_money(f["principal_amount"])))
            self.fd_hist_table.setItem(i, 2, QTableWidgetItem(f"{f['interest_rate']}%"))
            self.fd_hist_table.setItem(i, 3, QTableWidgetItem(fmt_money(f["maturity_amount"] or 0)))
            self.fd_hist_table.setItem(i, 4, QTableWidgetItem(f["status"]))
            self.fd_hist_table.setItem(i, 5, QTableWidgetItem(f["maturity_date"]))


class FDDetailDialog(QDialog):
    def __init__(self, fd, on_mark_matured, on_mark_withdrawn, accounts_repo, lookups_repo, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fixed Deposit Detail"); self.setMinimumWidth(440)
        self.fd = fd; self._on_matured = on_mark_matured; self._on_withdrawn = on_mark_withdrawn
        lay = QVBoxLayout(self)
        hdr = QHBoxLayout()
        t = QLabel(fd["account_name"] or "Fixed Deposit")
        t.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        hdr.addWidget(t, 1)
        hdr.addWidget(_badge(fd["status"], status_color("asset", fd["status"])))
        lay.addLayout(hdr)

        pct = FDService.progress(fd["start_date"], fd["maturity_date"])
        pb = QProgressBar(); pb.setRange(0, 100); pb.setValue(int(pct)); pb.setTextVisible(True)
        pb.setFormat(f"{pct:.0f}% of tenure elapsed")
        lay.addWidget(pb)

        info = QLabel(f"Principal: {fmt_money(fd['principal_amount'])}  ·  Rate: {fd['interest_rate']}%  ·  "
                       f"Maturity Amount: {fmt_money(fd['maturity_amount'] or 0)}\n"
                       f"Start: {fd['start_date']}  ·  Maturity: {fd['maturity_date']}")
        info.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        btn_row = QHBoxLayout(); btn_row.addStretch()
        if fd["status"] == "ACTIVE" and pct >= 100:
            m_btn = QPushButton("✅ Mark Matured"); m_btn.setObjectName("primary")
            m_btn.clicked.connect(self._do_mark_matured)
            btn_row.addWidget(m_btn)
        if fd["status"] in ("ACTIVE", "MATURED"):
            w_btn = QPushButton("💵 Mark Withdrawn (credit maturity amount)")
            w_btn.clicked.connect(self._do_mark_withdrawn)
            btn_row.addWidget(w_btn)
        ok = QPushButton("Close"); ok.clicked.connect(self.accept)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)
        self.accounts_repo = accounts_repo
        self.lookups_repo = lookups_repo

    def _do_mark_matured(self):
        if self._on_matured():
            self.accept()

    def _do_mark_withdrawn(self):
        dlg = QDialog(self); dlg.setWindowTitle("Withdraw FD")
        f = QFormLayout(dlg)
        acc_cb = _account_combo(self.accounts_repo)
        idx = acc_cb.findData(self.fd["bank_account_id"])
        if idx >= 0:
            acc_cb.setCurrentIndex(idx)
        method_cb = _method_combo(self.lookups_repo)
        f.addRow("Credit Into *", acc_cb)
        f.addRow("Method *", method_cb)
        row = QHBoxLayout()
        ok_btn = QPushButton("Confirm"); ok_btn.setObjectName("primary")
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(dlg.reject)
        ok_btn.clicked.connect(dlg.accept)
        row.addStretch(); row.addWidget(cancel_btn); row.addWidget(ok_btn)
        f.addRow("", row)
        if dlg.exec_() == QDialog.Accepted:
            if self._on_withdrawn(acc_cb.currentData(), method_cb.currentData()):
                self.accept()


# ═══════════════════════════════════════════════
# FUNCTION 4 — FD OTHERS DEPOSIT  (liability: I hold others' money)
# ═══════════════════════════════════════════════

class FDOthersPage(_FunctionPage):
    ICON = "🧾"; TITLE = "FD Others Deposit"

    def _build_entry(self):
        page = QWidget(); lay = QVBoxLayout(page)
        self.fo_entry_stack, _ = _build_subnav(lay, ["New Depositor", "New Deposit", "Log Repayment"])

        p1 = QWidget(); f1 = QFormLayout(p1)
        self.fo_depositor_name = QLineEdit(); self.fo_depositor_name.setPlaceholderText("Full name")
        add_d = QPushButton("➕ Add Depositor"); add_d.setObjectName("primary")
        add_d.clicked.connect(self._add_depositor)
        f1.addRow("Name *", self.fo_depositor_name)
        f1.addRow("", add_d)
        self.fo_entry_stack.addWidget(p1)

        p2 = QWidget(); f2 = QFormLayout(p2)
        self.fo_dep_depositor = _person_combo(self.repos["deposits"].list_depositors, ["depositor_id"])
        self.fo_dep_amount = QDoubleSpinBox(); self.fo_dep_amount.setRange(0, 999999999)
        self.fo_dep_amount.setPrefix("₹ "); self.fo_dep_amount.setDecimals(2)
        self.fo_dep_interest_free = QPushButton("Interest-Free"); self.fo_dep_interest_free.setCheckable(True)
        self.fo_dep_interest_free.setChecked(True)
        self.fo_dep_interest_free.setObjectName("pill")
        self.fo_dep_interest_free.toggled.connect(self._toggle_interest_free)
        self.fo_dep_rate = QDoubleSpinBox(); self.fo_dep_rate.setRange(0, 30); self.fo_dep_rate.setSuffix(" %")
        self.fo_dep_rate.setEnabled(False)
        self.fo_dep_account = _account_combo(self.repos["accounts"])
        self.fo_dep_method = _method_combo(self.repos["lookups"])
        self.fo_dep_date = QDateEdit(QDate.currentDate()); self.fo_dep_date.setCalendarPopup(True)
        self.fo_dep_return_date = QDateEdit(QDate.currentDate().addMonths(6)); self.fo_dep_return_date.setCalendarPopup(True)
        self.fo_dep_desc = QLineEdit(); self.fo_dep_desc.setPlaceholderText("Optional note")
        f2.addRow("Depositor *", self.fo_dep_depositor)
        f2.addRow("Amount *", self.fo_dep_amount)
        f2.addRow("", self.fo_dep_interest_free)
        f2.addRow("Interest Rate", self.fo_dep_rate)
        f2.addRow("Received Into *", self.fo_dep_account)
        f2.addRow("Method *", self.fo_dep_method)
        f2.addRow("Deposit Date", self.fo_dep_date)
        f2.addRow("Expected Return Date", self.fo_dep_return_date)
        f2.addRow("Description", self.fo_dep_desc)
        take_btn = QPushButton("🧾  Record Deposit"); take_btn.setObjectName("primary")
        take_btn.clicked.connect(self._create_deposit)
        f2.addRow("", take_btn)
        self.fo_entry_stack.addWidget(p2)

        p3 = QWidget(); f3 = QFormLayout(p3)
        self.fo_rep_deposit = QComboBox()
        self.fo_rep_pending_lbl = QLabel("")
        self.fo_rep_pending_lbl.setStyleSheet(f"color:{C['amber']};font-weight:700;font-size:12px;")
        self.fo_rep_deposit.currentIndexChanged.connect(self._update_fo_pending_label)
        self.fo_rep_amount = QDoubleSpinBox(); self.fo_rep_amount.setRange(0, 99999999)
        self.fo_rep_amount.setPrefix("₹ "); self.fo_rep_amount.setDecimals(2)
        self.fo_rep_account = _account_combo(self.repos["accounts"])
        self.fo_rep_method = _method_combo(self.repos["lookups"])
        self.fo_rep_date = QDateEdit(QDate.currentDate()); self.fo_rep_date.setCalendarPopup(True)
        self.fo_rep_desc = QLineEdit(); self.fo_rep_desc.setPlaceholderText("Optional note")
        f3.addRow("Deposit *", self.fo_rep_deposit)
        f3.addRow("", self.fo_rep_pending_lbl)
        f3.addRow("Amount Returned *", self.fo_rep_amount)
        f3.addRow("Pay From *", self.fo_rep_account)
        f3.addRow("Method *", self.fo_rep_method)
        f3.addRow("Date", self.fo_rep_date)
        f3.addRow("Description", self.fo_rep_desc)
        rep_btn = QPushButton("💸  Log Repayment"); rep_btn.setObjectName("primary")
        rep_btn.clicked.connect(self._log_repayment)
        f3.addRow("", rep_btn)
        self.fo_entry_stack.addWidget(p3)

        return page

    def _toggle_interest_free(self, checked):
        self.fo_dep_interest_free.setText("Interest-Free" if checked else "Interest-Bearing")
        self.fo_dep_rate.setEnabled(not checked)
        if checked:
            self.fo_dep_rate.setValue(0)

    def _refresh_entry_dropdowns(self):
        self.fo_dep_depositor.clear()
        for d in self.repos["deposits"].list_depositors():
            self.fo_dep_depositor.addItem(d["name"], d["depositor_id"])
        self.fo_rep_deposit.clear()
        for d in self.repos["deposits"].list_deposits():
            if d["status"] != "CLOSED":
                self.fo_rep_deposit.addItem(
                    f"{d['depositor_name']} — {fmt_money(d['principal_amount'])} ({d['status']})", d["deposit_id"])
        self._update_fo_pending_label()

    def _update_fo_pending_label(self):
        did = self.fo_rep_deposit.currentData()
        if not did:
            self.fo_rep_pending_lbl.setText(""); return
        dep = self.repos["deposits"].get_deposit(did)
        if not dep:
            return
        paid = self.repos["deposits"].total_repaid(did)
        pending = dep["principal_amount"] - paid
        self.fo_rep_pending_lbl.setText(f"Pending: {fmt_money(pending)} of {fmt_money(dep['principal_amount'])}")

    def _add_depositor(self):
        name = self.fo_depositor_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter the depositor's name."); return
        self.repos["deposits"].create_depositor(name)
        self.fo_depositor_name.clear()
        self._refresh_entry_dropdowns()
        QMessageBox.information(self, "Added", f"'{name}' added to your depositor directory.")

    def _create_deposit(self):
        did = self.fo_dep_depositor.currentData()
        amount = self.fo_dep_amount.value()
        if not did or amount <= 0:
            QMessageBox.warning(self, "Missing Info", "Please select a depositor and enter an amount."); return
        account_id = self.fo_dep_account.currentData()
        method = self.fo_dep_method.currentData()
        name = self.fo_dep_depositor.currentText()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="CREDIT", amount=amount, person_org=name,
            description=f"Deposit received from {name}", category_names=("Finance", "Other"))
        rate = None if self.fo_dep_interest_free.isChecked() else self.fo_dep_rate.value()
        self.repos["deposits"].create_deposit(
            depositor_id=did, principal_amount=amount, interest_rate=rate,
            deposit_date=self.fo_dep_date.date().toString("yyyy-MM-dd"),
            expected_return_date=self.fo_dep_return_date.date().toString("yyyy-MM-dd"),
            status="ACTIVE", description=self.fo_dep_desc.text().strip() or None, linked_txn_id=txn_id)
        self.fo_dep_amount.setValue(0); self.fo_dep_desc.clear()
        self._refresh_entry_dropdowns(); self.load_list(); self.load_history()
        QMessageBox.information(self, "Deposit Recorded", f"₹{amount:,.2f} deposit from {name} recorded.")

    def _log_repayment(self):
        did = self.fo_rep_deposit.currentData()
        amount = self.fo_rep_amount.value()
        if not did or amount <= 0:
            QMessageBox.warning(self, "Missing Info", "Please select a deposit and enter an amount."); return
        dep = self.repos["deposits"].get_deposit(did)
        account_id = self.fo_rep_account.currentData()
        method = self.fo_rep_method.currentData()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="DEBIT", amount=amount, person_org=dep["depositor_name"] if dep else None,
            description=f"Repayment to {dep['depositor_name']}" if dep else "Deposit repayment",
            category_names=("Finance", "Other"))
        self.repos["deposits"].add_repayment(
            deposit_id=did, amount_paid=amount, payment_date=self.fo_rep_date.date().toString("yyyy-MM-dd"),
            payment_method=method, description=self.fo_rep_desc.text().strip() or None, linked_txn_id=txn_id)
        self.fo_rep_amount.setValue(0); self.fo_rep_desc.clear()
        self._refresh_entry_dropdowns(); self.load_list(); self.load_history()
        QMessageBox.information(self, "Repayment Logged", "Repayment recorded successfully.")

    def _build_list(self):
        page = QWidget(); lay = QVBoxLayout(page)
        scroll, self.fo_list_lay = self._scroll_area()
        lay.addWidget(scroll)
        return page

    def load_list(self):
        for i in reversed(range(self.fo_list_lay.count())):
            w = self.fo_list_lay.itemAt(i).widget()
            if w: w.deleteLater()
        deps = self.repos["deposits"].list_deposits()
        if not deps:
            empty = QLabel("No deposits from others yet."); empty.setStyleSheet(f"color:{C['text3']};padding:20px;")
            empty.setAlignment(Qt.AlignCenter); self.fo_list_lay.addWidget(empty); return
        for d in deps:
            paid = self.repos["deposits"].total_repaid(d["deposit_id"])
            pending = d["principal_amount"] - paid
            interest_free = not d["interest_rate"]
            # Plan: no due-date urgency coloring for this function — always liability-blue unless closed.
            color = C["text3"] if d["status"] == "CLOSED" else C["accent"]
            badge_text = "Interest-Free" if interest_free else f"{d['interest_rate']}%"
            card = _wealth_card(
                title=d["depositor_name"],
                subtitle=f"Deposited {d['deposit_date']} · Expected return {d['expected_return_date'] or '—'}",
                amount_text=fmt_money(pending) + " held", badge_text=badge_text,
                badge_color=(C["text3"] if interest_free and d["status"] != "CLOSED" else color),
                extra_line=f"Principal: {fmt_money(d['principal_amount'])} · Returned: {fmt_money(paid)} · {d['status']}",
                on_click=lambda did=d["deposit_id"]: self._open_detail(did))
            self.fo_list_lay.addWidget(card)

    def _open_detail(self, deposit_id):
        dep = self.repos["deposits"].get_deposit(deposit_id)
        if not dep:
            return
        repayments = self.repos["deposits"].get_repayments(deposit_id)
        dlg = LoanDetailDialog(role="take", title=f"Deposit from {dep['depositor_name']}",
                                principal=dep["principal_amount"], status=dep["status"],
                                start_date=dep["deposit_date"], due_date=dep["expected_return_date"],
                                description=dep.get("description"), repayments=repayments,
                                amount_key="amount_paid", date_key="payment_date",
                                on_mark_closed=lambda: self._mark_closed(deposit_id), parent=self)
        dlg.exec_()

    def _mark_closed(self, deposit_id):
        if _confirm(self, "Mark Closed", "Mark this deposit as fully returned/closed?"):
            self.repos["deposits"].update_status(deposit_id, "CLOSED")
            self.load_list(); self.load_history()
            return True
        return False

    def _build_history(self):
        page = QWidget(); lay = QVBoxLayout(page)
        self.fo_stats_row, self.fo_sort_cb, self.fo_hist_table = _build_history_shell(
            lay, ["Status", "Deposit ID", "Person"])
        self.fo_sort_cb.currentIndexChanged.connect(self.load_history)
        self.fo_hist_table.setColumnCount(6)
        self.fo_hist_table.setHorizontalHeaderLabels(
            ["Depositor", "Principal", "Returned", "Pending", "Rate", "Status"])
        self.fo_hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        return page

    def load_history(self):
        deps = self.repos["deposits"].list_deposits()
        active = [d for d in deps if d["status"] != "CLOSED"]
        total_pending = sum(max(d["principal_amount"] - self.repos["deposits"].total_repaid(d["deposit_id"]), 0)
                             for d in active)
        _fill_stats_row(self.fo_stats_row, [
            _metric_card("Total Held", fmt_money(total_pending), C["accent"]),
            _metric_card("Active Deposits", str(len(active))),
            _metric_card("Total Deposits", str(len(deps))),
        ])
        sort_mode = self.fo_sort_cb.currentText()
        if sort_mode == "Status":
            deps.sort(key=lambda d: 0 if d["status"] != "CLOSED" else 1)
        elif sort_mode == "Deposit ID":
            deps.sort(key=lambda d: d["deposit_id"])
        else:
            deps.sort(key=lambda d: d["depositor_name"])

        self.fo_hist_table.setRowCount(len(deps))
        for i, d in enumerate(deps):
            paid = self.repos["deposits"].total_repaid(d["deposit_id"])
            pending = d["principal_amount"] - paid
            self.fo_hist_table.setItem(i, 0, QTableWidgetItem(d["depositor_name"]))
            self.fo_hist_table.setItem(i, 1, QTableWidgetItem(fmt_money(d["principal_amount"])))
            self.fo_hist_table.setItem(i, 2, QTableWidgetItem(fmt_money(paid)))
            self.fo_hist_table.setItem(i, 3, QTableWidgetItem(fmt_money(pending)))
            self.fo_hist_table.setItem(i, 4, QTableWidgetItem(f"{d['interest_rate']}%" if d["interest_rate"] else "Interest-Free"))
            self.fo_hist_table.setItem(i, 5, QTableWidgetItem(d["status"]))


# ═══════════════════════════════════════════════
# FUNCTION 5 — MUTUAL FUNDS
# ═══════════════════════════════════════════════

class MFPage(_FunctionPage):
    ICON = "📈"; TITLE = "Mutual Funds"

    def __init__(self, repos, services, parent=None):
        self._nav_cache = {}
        super().__init__(repos, services, parent)

    def _build_entry(self):
        page = QWidget(); lay = QVBoxLayout(page)
        self.mf_entry_stack, _ = _build_subnav(lay, ["New Scheme", "Log Purchase/SIP", "Log Redemption"])

        # -- New Scheme --
        p1 = QWidget(); f1 = QFormLayout(p1)
        self.mf_amc = QLineEdit(); self.mf_amc.setPlaceholderText("e.g. Parag Parikh")
        self.mf_scheme_name = QLineEdit(); self.mf_scheme_name.setPlaceholderText("e.g. Flexi Cap Fund - Direct Growth")
        self.mf_scheme_type = QComboBox(); self.mf_scheme_type.addItems(
            ["Equity", "Debt", "Hybrid", "Index", "ELSS", "Liquid", "Other"])
        self.mf_folio = QLineEdit(); self.mf_folio.setPlaceholderText("Folio number (optional)")
        add_s = QPushButton("➕ Add Scheme"); add_s.setObjectName("primary")
        add_s.clicked.connect(self._add_scheme)
        f1.addRow("AMC *", self.mf_amc)
        f1.addRow("Scheme Name *", self.mf_scheme_name)
        f1.addRow("Type", self.mf_scheme_type)
        f1.addRow("Folio Number", self.mf_folio)
        f1.addRow("", add_s)
        self.mf_entry_stack.addWidget(p1)

        # -- Log Purchase/SIP --
        p2 = QWidget(); f2 = QFormLayout(p2)
        self.mf_buy_scheme = QComboBox()
        self.mf_buy_type = QComboBox(); self.mf_buy_type.addItems(["PURCHASE", "SIP"])
        self.mf_buy_date = QDateEdit(QDate.currentDate()); self.mf_buy_date.setCalendarPopup(True)
        self.mf_buy_amount = QDoubleSpinBox(); self.mf_buy_amount.setRange(0, 99999999)
        self.mf_buy_amount.setPrefix("₹ "); self.mf_buy_amount.setDecimals(2)
        nav_row = QHBoxLayout()
        self.mf_buy_nav = QDoubleSpinBox(); self.mf_buy_nav.setRange(0, 999999); self.mf_buy_nav.setDecimals(4)
        fetch_btn = QPushButton("🔎 Fetch NAV"); fetch_btn.clicked.connect(self._fetch_nav_for_buy)
        nav_row.addWidget(self.mf_buy_nav); nav_row.addWidget(fetch_btn)
        self.mf_buy_units_preview = QLabel("Units: —")
        self.mf_buy_units_preview.setStyleSheet(f"color:{C['accent']};font-weight:700;font-size:12px;")
        for w in (self.mf_buy_amount, self.mf_buy_nav):
            w.valueChanged.connect(self._update_units_preview)
        self.mf_buy_account = _account_combo(self.repos["accounts"])
        self.mf_buy_method = _method_combo(self.repos["lookups"])
        f2.addRow("Scheme *", self.mf_buy_scheme)
        f2.addRow("Type", self.mf_buy_type)
        f2.addRow("Date", self.mf_buy_date)
        f2.addRow("Amount *", self.mf_buy_amount)
        f2.addRow("NAV *", nav_row)
        f2.addRow("", self.mf_buy_units_preview)
        f2.addRow("Pay From *", self.mf_buy_account)
        f2.addRow("Method *", self.mf_buy_method)
        buy_btn = QPushButton("📈  Log Purchase"); buy_btn.setObjectName("primary")
        buy_btn.clicked.connect(self._log_purchase)
        f2.addRow("", buy_btn)
        self.mf_entry_stack.addWidget(p2)

        # -- Log Redemption --
        p3 = QWidget(); f3 = QFormLayout(p3)
        self.mf_sell_scheme = QComboBox()
        self.mf_sell_scheme.currentIndexChanged.connect(self._update_holdings_label)
        self.mf_holdings_lbl = QLabel("")
        self.mf_holdings_lbl.setStyleSheet(f"color:{C['amber']};font-weight:700;font-size:12px;")
        self.mf_sell_date = QDateEdit(QDate.currentDate()); self.mf_sell_date.setCalendarPopup(True)
        self.mf_sell_units = QDoubleSpinBox(); self.mf_sell_units.setRange(0, 9999999); self.mf_sell_units.setDecimals(4)
        sell_nav_row = QHBoxLayout()
        self.mf_sell_nav = QDoubleSpinBox(); self.mf_sell_nav.setRange(0, 999999); self.mf_sell_nav.setDecimals(4)
        sell_fetch_btn = QPushButton("🔎 Fetch NAV"); sell_fetch_btn.clicked.connect(self._fetch_nav_for_sell)
        sell_nav_row.addWidget(self.mf_sell_nav); sell_nav_row.addWidget(sell_fetch_btn)
        self.mf_sell_amount_preview = QLabel("Redemption Amount: —")
        self.mf_sell_amount_preview.setStyleSheet(f"color:{C['green']};font-weight:700;font-size:12px;")
        for w in (self.mf_sell_units, self.mf_sell_nav):
            w.valueChanged.connect(self._update_redemption_preview)
        self.mf_sell_account = _account_combo(self.repos["accounts"])
        self.mf_sell_method = _method_combo(self.repos["lookups"])
        f3.addRow("Scheme *", self.mf_sell_scheme)
        f3.addRow("", self.mf_holdings_lbl)
        f3.addRow("Date", self.mf_sell_date)
        f3.addRow("Units to Redeem *", self.mf_sell_units)
        f3.addRow("NAV *", sell_nav_row)
        f3.addRow("", self.mf_sell_amount_preview)
        f3.addRow("Credit Into *", self.mf_sell_account)
        f3.addRow("Method *", self.mf_sell_method)
        sell_btn = QPushButton("💵  Log Redemption"); sell_btn.setObjectName("primary")
        sell_btn.clicked.connect(self._log_redemption)
        f3.addRow("", sell_btn)
        self.mf_entry_stack.addWidget(p3)

        return page

    def _update_units_preview(self):
        amt = self.mf_buy_amount.value(); nav = self.mf_buy_nav.value()
        units = MFService.calculate_units(amt, nav)
        self.mf_buy_units_preview.setText(f"Units: {units:,.4f}" if units else "Units: —")

    def _update_redemption_preview(self):
        units = self.mf_sell_units.value(); nav = self.mf_sell_nav.value()
        self.mf_sell_amount_preview.setText(f"Redemption Amount: {fmt_money(units * nav)}" if nav else "Redemption Amount: —")

    def _update_holdings_label(self):
        sid = self.mf_sell_scheme.currentData()
        if not sid:
            self.mf_holdings_lbl.setText(""); return
        h = self.repos["mf"].holdings(sid)
        self.mf_holdings_lbl.setText(f"You hold {h['units']:,.4f} units in this scheme.")
        self.mf_sell_units.setMaximum(max(h["units"], 0))

    def _fetch_nav_for_buy(self):
        scheme_name = self.mf_buy_scheme.currentText()
        dlg = NavFetchDialog(initial_query=scheme_name, parent=self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_nav:
            self.mf_buy_nav.setValue(dlg.result_nav)

    def _fetch_nav_for_sell(self):
        scheme_name = self.mf_sell_scheme.currentText()
        dlg = NavFetchDialog(initial_query=scheme_name, parent=self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_nav:
            self.mf_sell_nav.setValue(dlg.result_nav)

    def _refresh_entry_dropdowns(self):
        self.mf_buy_scheme.clear(); self.mf_sell_scheme.clear()
        for s in self.repos["mf"].list_schemes():
            label = f"{s['amc_name']} — {s['scheme_name']}"
            self.mf_buy_scheme.addItem(label, s["scheme_id"])
            self.mf_sell_scheme.addItem(label, s["scheme_id"])
        self._update_holdings_label()

    def _add_scheme(self):
        amc = self.mf_amc.text().strip(); name = self.mf_scheme_name.text().strip()
        if not amc or not name:
            QMessageBox.warning(self, "Missing Info", "Please enter both AMC and scheme name."); return
        self.repos["mf"].create_scheme(
            amc_name=amc, scheme_name=name, scheme_type=self.mf_scheme_type.currentText(),
            folio_number=self.mf_folio.text().strip() or None, is_active=1)
        self.mf_amc.clear(); self.mf_scheme_name.clear(); self.mf_folio.clear()
        self._refresh_entry_dropdowns()
        QMessageBox.information(self, "Scheme Added", f"'{name}' added to your mutual fund schemes.")

    def _log_purchase(self):
        sid = self.mf_buy_scheme.currentData()
        amount = self.mf_buy_amount.value(); nav = self.mf_buy_nav.value()
        if not sid or amount <= 0 or nav <= 0:
            QMessageBox.warning(self, "Missing Info", "Please select a scheme and enter amount and NAV."); return
        units = MFService.calculate_units(amount, nav)
        account_id = self.mf_buy_account.currentData()
        method = self.mf_buy_method.currentData()
        scheme_label = self.mf_buy_scheme.currentText()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="DEBIT", amount=amount, person_org=None,
            description=f"MF {self.mf_buy_type.currentText().title()} — {scheme_label}",
            category_names=("Investment", "Finance"))
        self.repos["mf"].add_txn(
            scheme_id=sid, txn_type=self.mf_buy_type.currentText(),
            txn_date=self.mf_buy_date.date().toString("yyyy-MM-dd"),
            amount=amount, nav=nav, units=units, linked_txn_id=txn_id)
        self._nav_cache[sid] = nav
        self.mf_buy_amount.setValue(0)
        self._refresh_entry_dropdowns(); self.load_list(); self.load_history()
        QMessageBox.information(self, "Purchase Logged", f"{units:,.4f} units purchased.")

    def _log_redemption(self):
        sid = self.mf_sell_scheme.currentData()
        units = self.mf_sell_units.value(); nav = self.mf_sell_nav.value()
        if not sid or units <= 0 or nav <= 0:
            QMessageBox.warning(self, "Missing Info", "Please select a scheme and enter units and NAV."); return
        held = self.repos["mf"].holdings(sid)["units"]
        if units > held + 1e-6:
            QMessageBox.warning(self, "Not Enough Units",
                                 f"You only hold {held:,.4f} units in this scheme.")
            return
        amount = round(units * nav, 2)
        account_id = self.mf_sell_account.currentData()
        method = self.mf_sell_method.currentData()
        scheme_label = self.mf_sell_scheme.currentText()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="CREDIT", amount=amount, person_org=None,
            description=f"MF Redemption — {scheme_label}", category_names=("Investment", "Finance"))
        self.repos["mf"].add_txn(
            scheme_id=sid, txn_type="REDEMPTION", txn_date=self.mf_sell_date.date().toString("yyyy-MM-dd"),
            amount=amount, nav=nav, units=units, linked_txn_id=txn_id)
        self._nav_cache[sid] = nav
        self.mf_sell_units.setValue(0)
        self._refresh_entry_dropdowns(); self.load_list(); self.load_history()
        QMessageBox.information(self, "Redemption Logged", f"{units:,.4f} units redeemed for {fmt_money(amount)}.")

    def _last_nav(self, scheme_id):
        if scheme_id in self._nav_cache:
            return self._nav_cache[scheme_id]
        txns = self.repos["mf"].list_txns(scheme_id)
        return txns[-1]["nav"] if txns else 0

    def _build_list(self):
        page = QWidget(); lay = QVBoxLayout(page)
        self.mf_portfolio_row = QHBoxLayout()
        lay.addLayout(self.mf_portfolio_row)
        scroll, self.mf_list_lay = self._scroll_area()
        lay.addWidget(scroll)
        return page

    def load_list(self):
        for i in reversed(range(self.mf_list_lay.count())):
            w = self.mf_list_lay.itemAt(i).widget()
            if w: w.deleteLater()
        schemes = self.repos["mf"].list_schemes()

        total_invested = total_current = 0
        for s in schemes:
            h = self.repos["mf"].holdings(s["scheme_id"])
            net_invested = h["invested"] - h["redeemed"]
            nav = self._last_nav(s["scheme_id"])
            current_value = h["units"] * nav
            total_invested += net_invested
            total_current += current_value
        overall_return = MFService.simple_return(total_invested, total_current)
        _fill_stats_row(self.mf_portfolio_row, [
            _metric_card("Invested", fmt_money(total_invested)),
            _metric_card("Current Value", fmt_money(total_current), C["accent"]),
            _metric_card("Overall Return", f"{overall_return:+.2f}%",
                         C["green"] if overall_return >= 0 else C["red"]),
        ])

        if not schemes:
            empty = QLabel("No mutual fund schemes yet."); empty.setStyleSheet(f"color:{C['text3']};padding:20px;")
            empty.setAlignment(Qt.AlignCenter); self.mf_list_lay.addWidget(empty); return

        for s in schemes:
            h = self.repos["mf"].holdings(s["scheme_id"])
            net_invested = h["invested"] - h["redeemed"]
            nav = self._last_nav(s["scheme_id"])
            current_value = h["units"] * nav
            ret = MFService.simple_return(net_invested, current_value)
            color = C["green"] if ret >= 0 else C["red"]
            card = _wealth_card(
                title=f"{s['amc_name']} — {s['scheme_name']}",
                subtitle=f"{s['scheme_type'] or ''} · {h['units']:,.4f} units · NAV {nav:,.4f}",
                amount_text=fmt_money(current_value), badge_text=f"{ret:+.2f}%", badge_color=color,
                extra_line=f"Invested: {fmt_money(net_invested)}",
                on_click=lambda sid=s["scheme_id"]: self._open_detail(sid))
            self.mf_list_lay.addWidget(card)

    def _open_detail(self, scheme_id):
        scheme = self.repos["mf"].get_scheme(scheme_id)
        if not scheme:
            return
        txns = self.repos["mf"].list_txns(scheme_id)
        h = self.repos["mf"].holdings(scheme_id)
        nav = self._last_nav(scheme_id)
        dlg = MFDetailDialog(scheme, txns, h, nav, parent=self)
        dlg.exec_()

    def _build_history(self):
        page = QWidget(); lay = QVBoxLayout(page)
        self.mf_stats_row, self.mf_sort_cb, self.mf_hist_table = _build_history_shell(
            lay, ["Date", "Scheme", "Type"])
        self.mf_sort_cb.currentIndexChanged.connect(self.load_history)
        self.mf_hist_table.setColumnCount(6)
        self.mf_hist_table.setHorizontalHeaderLabels(
            ["Date", "Scheme", "Type", "Amount", "NAV", "Units"])
        self.mf_hist_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        return page

    def load_history(self):
        schemes = {s["scheme_id"]: s for s in self.repos["mf"].list_schemes()}
        all_txns = []
        for sid in schemes:
            for t in self.repos["mf"].list_txns(sid):
                t = dict(t); t["scheme_label"] = f"{schemes[sid]['amc_name']} — {schemes[sid]['scheme_name']}"
                all_txns.append(t)

        total_purchased = sum(t["amount"] for t in all_txns if t["txn_type"] in ("PURCHASE", "SIP"))
        total_redeemed = sum(t["amount"] for t in all_txns if t["txn_type"] == "REDEMPTION")
        _fill_stats_row(self.mf_stats_row, [
            _metric_card("Total Purchased", fmt_money(total_purchased)),
            _metric_card("Total Redeemed", fmt_money(total_redeemed)),
            _metric_card("Total Schemes", str(len(schemes))),
        ])
        sort_mode = self.mf_sort_cb.currentText()
        if sort_mode == "Date":
            all_txns.sort(key=lambda t: t["txn_date"], reverse=True)
        elif sort_mode == "Scheme":
            all_txns.sort(key=lambda t: t["scheme_label"])
        else:
            all_txns.sort(key=lambda t: t["txn_type"])

        self.mf_hist_table.setRowCount(len(all_txns))
        for i, t in enumerate(all_txns):
            self.mf_hist_table.setItem(i, 0, QTableWidgetItem(t["txn_date"]))
            self.mf_hist_table.setItem(i, 1, QTableWidgetItem(t["scheme_label"]))
            self.mf_hist_table.setItem(i, 2, QTableWidgetItem(t["txn_type"]))
            self.mf_hist_table.setItem(i, 3, QTableWidgetItem(fmt_money(t["amount"])))
            self.mf_hist_table.setItem(i, 4, QTableWidgetItem(f"{t['nav']:,.4f}"))
            self.mf_hist_table.setItem(i, 5, QTableWidgetItem(f"{t['units']:,.4f}"))


class MFDetailDialog(QDialog):
    def __init__(self, scheme, txns, holdings, nav, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{scheme['amc_name']} — {scheme['scheme_name']}")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)

        net_invested = holdings["invested"] - holdings["redeemed"]
        current_value = holdings["units"] * nav
        ret = MFService.simple_return(net_invested, current_value)
        color = C["green"] if ret >= 0 else C["red"]

        hdr = QHBoxLayout()
        t = QLabel(f"{scheme['amc_name']} — {scheme['scheme_name']}")
        t.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        t.setWordWrap(True)
        hdr.addWidget(t, 1)
        hdr.addWidget(_badge(f"{ret:+.2f}%", color))
        lay.addLayout(hdr)

        info = QLabel(f"Folio: {scheme.get('folio_number') or '—'}  ·  Type: {scheme.get('scheme_type') or '—'}\n"
                       f"Units Held: {holdings['units']:,.4f}  ·  Latest NAV: {nav:,.4f}\n"
                       f"Invested: {fmt_money(net_invested)}  ·  Current Value: {fmt_money(current_value)}")
        info.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        lay.addWidget(info)

        table = QTableWidget()
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Date", "Type", "Amount", "NAV", "Units"])
        table.setRowCount(len(txns))
        for i, tx in enumerate(txns):
            table.setItem(i, 0, QTableWidgetItem(tx["txn_date"]))
            table.setItem(i, 1, QTableWidgetItem(tx["txn_type"]))
            table.setItem(i, 2, QTableWidgetItem(fmt_money(tx["amount"])))
            table.setItem(i, 3, QTableWidgetItem(f"{tx['nav']:,.4f}"))
            table.setItem(i, 4, QTableWidgetItem(f"{tx['units']:,.4f}"))
        lay.addWidget(table, 1)

        btn_row = QHBoxLayout(); btn_row.addStretch()
        ok = QPushButton("Close"); ok.clicked.connect(self.accept)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)


# ═══════════════════════════════════════════════
# WEALTH TAB — group pills → function pills → function page
# ═══════════════════════════════════════════════

class WealthTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db; self.repos = repos; self.services = services
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(14)

        heading = QLabel("Wealth")
        heading.setStyleSheet(f"font-size:22px;font-weight:800;color:{C['text']};")
        outer.addWidget(heading)

        group_row = QHBoxLayout()
        self.btn_people = QPushButton("👥 People")
        self.btn_deposits_grp = QPushButton("🏦 Deposits")
        self.btn_invest_grp = QPushButton("📈 Investments")
        self._group_btns = [self.btn_people, self.btn_deposits_grp, self.btn_invest_grp]
        for b in self._group_btns:
            group_row.addWidget(b)
        group_row.addStretch()
        outer.addLayout(group_row)

        self.group_stack = QStackedWidget()
        outer.addWidget(self.group_stack, 1)

        self.loans_give_page = LoansGivePage(self.repos, self.services)
        self.loans_take_page = LoansTakePage(self.repos, self.services)
        self.fd_give_page = FDGivePage(self.repos, self.services)
        self.fd_others_page = FDOthersPage(self.repos, self.services)
        self.mf_page = MFPage(self.repos, self.services)

        self.group_stack.addWidget(self._wrap_group(
            [("🤝 Loans I Give", self.loans_give_page), ("🏛️ Loans I Take", self.loans_take_page)]))
        self.group_stack.addWidget(self._wrap_group(
            [("🏦 FD I Deposit", self.fd_give_page), ("🧾 FD Others Deposit", self.fd_others_page)]))
        self.group_stack.addWidget(self._wrap_group(
            [("📈 Mutual Funds", self.mf_page)]))

        self.btn_people.clicked.connect(lambda: self._goto_group(0))
        self.btn_deposits_grp.clicked.connect(lambda: self._goto_group(1))
        self.btn_invest_grp.clicked.connect(lambda: self._goto_group(2))
        _switch_tabs(self._group_btns, 0)
        self.group_stack.setCurrentIndex(0)

    def _wrap_group(self, function_pages):
        """function_pages: list of (label, page_widget). Builds the function-pill row + stack."""
        wrapper = QWidget()
        lay = QVBoxLayout(wrapper); lay.setContentsMargins(0, 4, 0, 0); lay.setSpacing(10)
        fn_row = QHBoxLayout()
        btns = [QPushButton(label) for label, _ in function_pages]
        for b in btns:
            fn_row.addWidget(b)
        fn_row.addStretch()
        lay.addLayout(fn_row)
        stack = QStackedWidget()
        for _, page in function_pages:
            stack.addWidget(page)
        lay.addWidget(stack, 1)

        def goto(i):
            _switch_tabs(btns, i)
            stack.setCurrentIndex(i)

        for i, b in enumerate(btns):
            b.clicked.connect(lambda _, i=i: goto(i))
        _switch_tabs(btns, 0)
        return wrapper

    def _goto_group(self, i):
        _switch_tabs(self._group_btns, i)
        self.group_stack.setCurrentIndex(i)

    def refresh(self):
        for page in (self.loans_give_page, self.loans_take_page, self.fd_give_page,
                     self.fd_others_page, self.mf_page):
            page.refresh()