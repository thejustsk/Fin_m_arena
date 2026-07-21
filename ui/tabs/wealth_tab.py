"""Wealth tab — 5 top-level pages with Entry + Searchable/Sortable List."""
import json as _json
from datetime import date, datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QFrame, QScrollArea,
    QStackedWidget, QMessageBox, QDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFormLayout, QProgressBar, QListWidget,
    QTabWidget, QSizePolicy
)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal as _Signal
from PyQt5.QtGui import QCursor
from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tab_btn_active, _tab_btn_inactive, _switch_tabs
from ui.widgets.searchable_combo import SearchableCombo
from services.loan_service import LoanService
from services.fd_service import FDService
from services.mf_service import MFService


# ── Constants ──────────────────────────────────────────────────────────────
EM_DASH = "\u2014"
MDOT = "\u00b7"


def TODAY():
    return date.today().isoformat()


# ── Workers ────────────────────────────────────────────────────────────────
class _NavWorker(QThread):
    result = _Signal(object)
    error = _Signal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            import urllib.request
            with urllib.request.urlopen(self._url, timeout=8) as resp:
                data = _json.loads(resp.read().decode())
            self.result.emit(data)
        except Exception as e:
            self.error.emit(str(e))


# ── Helpers ────────────────────────────────────────────────────────────────
def _add_months(d, months):
    m = d.month - 1 + int(months)
    y = d.year + m // 12
    m = m % 12 + 1
    leap = (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
    dim = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(y, m, min(d.day, dim[m - 1]))


def status_color(role, status):
    status = (status or "").upper()
    if status == "OVERDUE":
        return C["red"]
    if status == "PARTIALLY_PAID":
        return C["amber"]
    if status == "REPAID":
        return C["green"]
    if status in ("CLOSED", "MATURED", "WITHDRAWN", "CLEARED"):
        return C["green"] if role in ("asset", "loan") else C["text3"]
    if role == "loan":
        return C["accent"]   # ACTIVE → purple
    return C["green"] if role == "asset" else C["accent"]


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()
        child = item.layout()
        if child:
            _clear_layout(child)


def _metric_card(label, value, color=None):
    color = color or C["text"]
    card = QFrame()
    card.setStyleSheet(
        f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;}}"
        f"QLabel{{background:transparent;border:none;}}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(4)
    v = QLabel(value)
    v.setStyleSheet(f"font-size:18px;font-weight:800;color:{color};")
    l = QLabel(label)
    l.setStyleSheet(f"font-size:10px;color:{C['text3']};font-weight:600;text-transform:uppercase;letter-spacing:0.5px;")
    lay.addWidget(v)
    lay.addWidget(l)
    return card


def _badge(text, color):
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:white;background:{color};border-radius:12px;padding:3px 10px;"
        f"font-size:11px;font-weight:700;border:none;"
    )
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return lbl


def _wealth_card(title, subtitle, amount_text, badge_text, badge_color,
                 on_click=None, progress_pct=None, extra_line=None):
    card = QFrame()
    hc = badge_color.lstrip("#")
    r, g, b = int(hc[0:2], 16), int(hc[2:4], 16), int(hc[4:6], 16)
    card.setStyleSheet(
        f"QFrame{{background:rgba({r},{g},{b},0.06);border:1.5px solid {badge_color};border-radius:12px;}}"
        f"QFrame:hover{{background:rgba({r},{g},{b},0.10);border-color:{badge_color};}}"
        f"QLabel{{background:transparent;border:none;outline:none;}}"
    )
    if on_click:
        card.setCursor(QCursor(Qt.PointingHandCursor))
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 12, 16, 12)
    lay.setSpacing(6)
    top = QHBoxLayout()
    t = QLabel(title)
    t.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
    top.addWidget(t, 1)
    top.addWidget(_badge(badge_text, badge_color))
    lay.addLayout(top)
    mid = QHBoxLayout()
    s = QLabel(subtitle)
    s.setStyleSheet(f"font-size:12px;color:{C['text3']};")
    s.setWordWrap(True)
    mid.addWidget(s, 1)
    a = QLabel(amount_text)
    a.setStyleSheet(f"font-size:15px;font-weight:800;color:{C['text']};")
    mid.addWidget(a)
    lay.addLayout(mid)
    if progress_pct is not None:
        bar_bg = QFrame()
        bar_bg.setFixedHeight(6)
        bar_bg.setStyleSheet(f"background:{C['border2']};border-radius:3px;")
        bl = QHBoxLayout(bar_bg)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        bf = QFrame()
        pct = max(0, min(100, int(progress_pct)))
        bf.setStyleSheet(f"background:{badge_color};border-radius:3px;")
        bl.addWidget(bf, pct)
        bl.addStretch(max(1, 100 - pct))
        lay.addWidget(bar_bg)
    if extra_line:
        e = QLabel(extra_line)
        e.setStyleSheet(f"font-size:11px;color:{C['text3']};")
        lay.addWidget(e)
    if on_click:
        card.mousePressEvent = lambda ev, cb=on_click: cb()
    return card


def _account_combo(repo):
    cb = QComboBox()
    for a in repo.list_active():
        cb.addItem(f"{a['display_name']} ({a['account_type']})", a["account_id"])
    return cb


def _method_combo(repo):
    cb = QComboBox()
    for m in repo.list_methods():
        cb.addItem(m["display_name"], m["method_id"])
    return cb


def _category_id(db, preferred_names, fallback=None):
    for name in preferred_names:
        r = db.execute(
            "SELECT category_id FROM categories WHERE LOWER(display_name)=LOWER(?) AND is_active=1",
            (name,)
        ).fetchone()
        if r:
            return r["category_id"]
    r = db.execute("SELECT category_id FROM categories WHERE LOWER(display_name)='other' AND is_active=1").fetchone()
    if r:
        return r["category_id"]
    return fallback


def _log_ledger_txn(tx_repo, db, *, account_id, pay_method, tx_type, amount,
                     person_org=None, description=None, category_names=("Finance", "Other")):
    cat = _category_id(db, category_names)
    try:
        return tx_repo.create(
            tx_date=TODAY(), account_id=account_id, pay_method=pay_method,
            tx_type=tx_type, amount=round(float(amount), 2), person_org=person_org,
            description=description, transaction_kind="REGULAR", category=cat,
            neednwant=0, pf_category=None
        )
    except Exception as e:
        print(f"[WARN] Ledger txn failed: {e}")
        return None


def _confirm(parent, title, msg):
    return QMessageBox.question(
        parent, title, msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
    ) == QMessageBox.Yes


# ── Reusable UI builders ───────────────────────────────────────────────────
def _build_subnav(container_layout, labels):
    nav = QHBoxLayout()
    nav.setSpacing(8)
    btns = [QPushButton(l) for l in labels]
    for b in btns:
        b.setMinimumHeight(32)
        b.setCursor(QCursor(Qt.PointingHandCursor))
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


def _fill_stats_row(row_layout, cards):
    for c in cards:
        row_layout.addWidget(c)


def _simple_add_dialog(parent, title, label="Name", placeholder="Full name"):
    """Simple dialog to add a named entity. Returns trimmed name string or None."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(360)
    f = QFormLayout(dlg)
    name_input = QLineEdit()
    name_input.setPlaceholderText(placeholder)
    f.addRow(label + " *", name_input)
    btn_row = QHBoxLayout()
    ok = QPushButton("Add")
    ok.setObjectName("primary")
    cancel = QPushButton("Cancel")
    ok.clicked.connect(dlg.accept)
    cancel.clicked.connect(dlg.reject)
    btn_row.addStretch()
    btn_row.addWidget(cancel)
    btn_row.addWidget(ok)
    f.addRow("", btn_row)
    if dlg.exec_() == QDialog.Accepted:
        val = name_input.text().strip()
        return val if val else None
    return None


def _entity_row(combo, add_callback):
    """SearchableCombo + [＋] Add button in a QHBoxLayout."""
    row = QHBoxLayout()
    row.setSpacing(6)
    add_btn = QPushButton("\uff0b Add New")
    add_btn.setFixedHeight(38)
    add_btn.setMinimumWidth(90)
    add_btn.setFocusPolicy(Qt.NoFocus)          # Tab skips this button
    add_btn.setToolTip("Add new")
    add_btn.setCursor(QCursor(Qt.PointingHandCursor))
    add_btn.clicked.connect(add_callback)
    add_btn.setStyleSheet(
        f"QPushButton{{font-size:12px;font-weight:700;padding:6px 12px;"
        f"border:1.5px solid {C['accent']};border-radius:{C['radius_sm']};"
        f"color:{C['accent']};background:{C['accent_bg']};}}"
        f"QPushButton:hover{{background:{C['accent']};color:white;}}"
    )
    row.addWidget(combo, 1)
    row.addWidget(add_btn)
    return row


# ── NAV fetch dialog (MF) ──────────────────────────────────────────────────
class NavFetchDialog(QDialog):
    def __init__(self, initial_query="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("\U0001f50e Fetch Latest NAV")
        self.setMinimumWidth(480)
        self.result_nav = None
        self.result_name = None
        self._matches = []
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.query_box = QLineEdit(initial_query)
        self.query_box.setPlaceholderText("Scheme name, e.g. Parag Parikh Flexi Cap")
        search_btn = QPushButton("Search")
        search_btn.setObjectName("primary")
        search_btn.clicked.connect(self._search)
        row.addWidget(self.query_box, 1)
        row.addWidget(search_btn)
        lay.addLayout(row)
        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(self._pick)
        lay.addWidget(self.results)
        info = QLabel("Double-click a scheme to fetch its latest NAV. Requires internet access.")
        info.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        lay.addWidget(info)
        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel)
        lay.addLayout(btn_row)
        if initial_query:
            self._search()

    def _search(self):
        q = self.query_box.text().strip()
        if not q:
            return
        self.results.clear()
        self.results.addItem("Searching...")
        import urllib.parse
        url = f"https://api.mfapi.in/mf/search?q={urllib.parse.quote(q)}"
        self._worker = _NavWorker(url, self)
        self._worker.result.connect(self._on_search_result)
        self._worker.error.connect(lambda e: (self.results.clear(), self.results.addItem(f"Error: {e}")))
        self._worker.start()

    def _on_search_result(self, data):
        self.results.clear()
        if not data:
            self.results.addItem("No matches found.")
            return
        matches = data[:30] if isinstance(data, list) else []
        for m in matches:
            self.results.addItem(f"{m.get('schemeName', '?')}  [{m.get('schemeCode', '?')}]")
        self._matches = matches

    def _pick(self, item):
        idx = self.results.row(item)
        if not self._matches or idx >= len(self._matches):
            return
        m = self._matches[idx]
        self.results.addItem("Fetching latest NAV...")
        import urllib.parse
        url = f"https://api.mfapi.in/mf/{m['schemeCode']}/latest"
        self._nav_worker = _NavWorker(url, self)
        self._nav_worker.result.connect(lambda data: self._on_nav_result(data, m))
        self._nav_worker.error.connect(
            lambda e: QMessageBox.warning(self, "Fetch Failed", f"Couldn't fetch NAV ({e}).")
        )
        self._nav_worker.start()

    def _on_nav_result(self, data, m):
        rows = data.get("data") or [] if isinstance(data, dict) else []
        nav = float(rows[0]["nav"]) if rows else None
        if nav is None:
            QMessageBox.warning(self, "No Data", "No NAV data available.")
            return
        self.result_nav = nav
        self.result_name = m.get("schemeName")
        self.accept()


# ── Base function page (Entry + List) ──────────────────────────────────────
class _FunctionPage(QWidget):
    ICON = "\U0001f4b0"
    TITLE = "Function"

    def __init__(self, repos, services, parent=None):
        super().__init__(parent)
        self.repos = repos
        self.services = services
        self.db = repos["accounts"].db
        self._list_data = []
        self._build_skeleton()

    # ── skeleton ──
    def _build_skeleton(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)
        hdr = QLabel(f"{self.ICON}  {self.TITLE}")
        hdr.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        lay.addWidget(hdr)
        # sub-nav: Entry | List
        nav = QHBoxLayout()
        nav.setSpacing(8)
        self.btn_entry = QPushButton("\uff0b Entry")
        self.btn_list = QPushButton("\U0001f4cb List")
        self._sub_btns = [self.btn_entry, self.btn_list]
        for b in self._sub_btns:
            b.setMinimumHeight(32)
            b.setCursor(QCursor(Qt.PointingHandCursor))
            nav.addWidget(b)
        nav.addStretch()
        lay.addLayout(nav)
        self.sub_stack = QStackedWidget()
        lay.addWidget(self.sub_stack, 1)
        self.sub_stack.addWidget(self._build_entry())
        self.sub_stack.addWidget(self._build_list())
        self.btn_entry.clicked.connect(lambda: self._goto(0))
        self.btn_list.clicked.connect(lambda: self._goto(1))
        _switch_tabs(self._sub_btns, 1)
        self.sub_stack.setCurrentIndex(1)

    def _goto(self, idx):
        _switch_tabs(self._sub_btns, idx)
        self.sub_stack.setCurrentIndex(idx)
        if idx == 0:
            self._refresh_entry_dropdowns()
        elif idx == 1:
            self.load_list()

    def refresh(self):
        self._refresh_entry_dropdowns()
        self.load_list()

    def _scroll_area(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setSpacing(10)
        v.setAlignment(Qt.AlignTop)
        scroll.setWidget(inner)
        return scroll, v

    # ── override in subclass ──
    def _build_entry(self):
        return QWidget()

    def _build_list(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self._stats_row = QHBoxLayout()
        lay.addLayout(self._stats_row)
        # filter row: sort + direction + search
        fr = QHBoxLayout()
        fr.setSpacing(8)
        sort_lbl = QLabel("Sort by:")
        sort_lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;font-weight:600;")
        self._sort_cb = QComboBox()
        self._sort_cb.addItems(self._sort_options())
        self._sort_cb.currentIndexChanged.connect(self._on_sort_changed)
        # sort direction toggle
        self._sort_asc = True
        self._sort_order_btn = QPushButton("\u25b2")
        self._sort_order_btn.setFixedSize(38, 38)
        self._sort_order_btn.setFocusPolicy(Qt.NoFocus)
        self._sort_order_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._sort_order_btn.setToolTip("Ascending (A\u2192Z). Click to reverse.")
        self._sort_order_btn.clicked.connect(self._toggle_sort_dir)
        self._sort_order_btn.setStyleSheet(
            f"QPushButton{{font-family:'Segoe UI Symbol','Segoe UI',sans-serif;"
            f"font-size:20px;font-weight:900;border:1.5px solid {C['accent']};"
            f"border-radius:{C['radius_sm']};background:{C['surface']};"
            f"color:{C['accent']};padding:0;margin:0;}}"
            f"QPushButton:hover{{background:{C['accent']};color:white;}}"
        )
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("\U0001f50d Search by name\u2026")
        self._search_input.textChanged.connect(self._render_list)
        self._search_input.setClearButtonEnabled(True)
        fr.addWidget(sort_lbl)
        fr.addWidget(self._sort_cb)
        fr.addWidget(self._sort_order_btn)
        fr.addSpacing(12)
        fr.addWidget(self._search_input, 1)
        lay.addLayout(fr)
        scroll, self._list_lay = self._scroll_area()
        lay.addWidget(scroll, 1)
        return page

    def _sort_options(self):
        return ["Status", "ID"]

    def _on_sort_changed(self):
        """Reset direction to default for the chosen sort field, then render."""
        mode = self._sort_cb.currentText() if hasattr(self, "_sort_cb") else ""
        self._sort_asc = not ("Date" in mode or "date" in mode)
        self._sort_order_btn.setText("\u25b2" if self._sort_asc else "\u25bc")
        self._sort_order_btn.setToolTip(
            "Ascending (A\u2192Z). Click to reverse." if self._sort_asc
            else "Descending (Z\u2192A). Click to reverse."
        )
        self._render_list()

    def _toggle_sort_dir(self):
        self._sort_asc = not self._sort_asc
        self._sort_order_btn.setText("\u25b2" if self._sort_asc else "\u25bc")
        self._sort_order_btn.setToolTip(
            "Ascending (A\u2192Z). Click to reverse." if self._sort_asc
            else "Descending (Z\u2192A). Click to reverse."
        )
        self._render_list()

    def _refresh_entry_dropdowns(self):
        pass

    def load_list(self):
        pass

    def _render_list(self):
        pass


# ══════════════════════════════════════════════════════════════════════════
#  LOANS I GIVE
# ══════════════════════════════════════════════════════════════════════════
class LoansGivePage(_FunctionPage):
    ICON = "\U0001f91d"
    TITLE = "Loans I Give"

    def _sort_options(self):
        return ["Status", "Borrower", "Amount", "Due Date"]

    # ── Entry ──
    def _build_entry(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.lg_stack, _ = _build_subnav(lay, ["Give Loan", "Log Repayment"])

        # ── Give Loan ──
        p1 = QWidget()
        f1 = QFormLayout(p1)
        self.lg_loan_borrower = SearchableCombo(placeholder="Search borrower\u2026")
        self.lg_loan_amount = QDoubleSpinBox()
        self.lg_loan_amount.setRange(0, 99999999)
        self.lg_loan_amount.setPrefix("\u20b9 ")
        self.lg_loan_amount.setDecimals(2)
        self.lg_loan_account = _account_combo(self.repos["accounts"])
        self.lg_loan_method = _method_combo(self.repos["lookups"])
        self.lg_loan_start = QDateEdit(QDate.currentDate())
        self.lg_loan_start.setCalendarPopup(True)
        self.lg_loan_due = QDateEdit(QDate.currentDate().addDays(30))
        self.lg_loan_due.setCalendarPopup(True)
        self.lg_loan_desc = QLineEdit()
        self.lg_loan_desc.setPlaceholderText("Optional note")
        give_btn = QPushButton("\U0001f91d  Give Loan")
        give_btn.setObjectName("primary")
        give_btn.clicked.connect(self._give_loan)
        f1.addRow("Borrower *", _entity_row(self.lg_loan_borrower, self._add_borrower_dlg))
        f1.addRow("Loan Amount *", self.lg_loan_amount)
        f1.addRow("Pay From *", self.lg_loan_account)
        f1.addRow("Method *", self.lg_loan_method)
        f1.addRow("Start Date", self.lg_loan_start)
        f1.addRow("Due Date", self.lg_loan_due)
        f1.addRow("Description", self.lg_loan_desc)
        f1.addRow("", give_btn)
        self.lg_stack.addWidget(p1)

        # ── Log Repayment ──
        p2 = QWidget()
        f2 = QFormLayout(p2)
        self.lg_rep_loan = SearchableCombo(placeholder="Search loan\u2026")
        self.lg_rep_pending_lbl = QLabel("")
        self.lg_rep_pending_lbl.setStyleSheet(f"color:{C['amber']};font-weight:700;font-size:12px;")
        self.lg_rep_loan.currentIndexChanged.connect(self._update_lg_pending)
        self.lg_rep_amount = QDoubleSpinBox()
        self.lg_rep_amount.setRange(0, 99999999)
        self.lg_rep_amount.setPrefix("\u20b9 ")
        self.lg_rep_amount.setDecimals(2)
        self.lg_rep_account = _account_combo(self.repos["accounts"])
        self.lg_rep_method = _method_combo(self.repos["lookups"])
        self.lg_rep_date = QDateEdit(QDate.currentDate())
        self.lg_rep_date.setCalendarPopup(True)
        self.lg_rep_desc = QLineEdit()
        self.lg_rep_desc.setPlaceholderText("Optional note")
        rep_btn = QPushButton("\U0001f4b0  Log Repayment")
        rep_btn.setObjectName("primary")
        rep_btn.clicked.connect(self._log_repayment)
        f2.addRow("Loan *", self.lg_rep_loan)
        f2.addRow("", self.lg_rep_pending_lbl)
        f2.addRow("Amount Received *", self.lg_rep_amount)
        f2.addRow("Into Account *", self.lg_rep_account)
        f2.addRow("Method *", self.lg_rep_method)
        f2.addRow("Date", self.lg_rep_date)
        f2.addRow("Description", self.lg_rep_desc)
        f2.addRow("", rep_btn)
        self.lg_stack.addWidget(p2)
        return page

    def _add_borrower_dlg(self):
        name = _simple_add_dialog(self, "Add New Borrower")
        if not name:
            return
        self.repos["loans"].create_borrower(name)
        self._refresh_entry_dropdowns()
        for i in range(self.lg_loan_borrower.count()):
            if self.lg_loan_borrower.itemText(i) == name:
                self.lg_loan_borrower.setCurrentIndex(i)
                break
        QMessageBox.information(self, "Added", f"'{name}' added as a borrower.")

    def _refresh_entry_dropdowns(self):
        self.lg_loan_borrower.clear_items()
        for b in self.repos["loans"].list_borrowers():
            self.lg_loan_borrower.add_item(b["name"], b["borrower_id"])
        self.lg_rep_loan.clear_items()
        # order: OVERDUE → ACTIVE → PARTIALLY_PAID; exclude CLOSED/CLEARED/REPAID
        rank = {"OVERDUE": 0, "ACTIVE": 1, "PARTIALLY_PAID": 2}
        loans = [l for l in self.repos["loans"].list_loans()
                 if l["status"] not in ("CLOSED", "CLEARED", "REPAID")]
        loans.sort(key=lambda l: rank.get(l["status"], 9))
        for l in loans:
            self.lg_rep_loan.add_item(
                f"{l['borrower_name']} \u2014 {fmt_money(l['loan_amount'])} ({l['status']})",
                l["loan_id"]
            )
        self._update_lg_pending()

    def _update_lg_pending(self):
        lid = self.lg_rep_loan.get_data()
        if not lid:
            self.lg_rep_pending_lbl.setText("")
            return
        loan = self.repos["loans"].get_loan(lid)
        if not loan:
            return
        paid = self.repos["loans"].total_repaid(lid)
        pending = loan["loan_amount"] - paid
        self.lg_rep_pending_lbl.setText(f"Pending: {fmt_money(pending)} of {fmt_money(loan['loan_amount'])}")

    def _give_loan(self):
        bid = self.lg_loan_borrower.get_data()
        amount = self.lg_loan_amount.value()
        if not bid or amount <= 0:
            QMessageBox.warning(self, "Missing Info", "Select a borrower and enter an amount.")
            return
        account_id = self.lg_loan_account.currentData()
        method = self.lg_loan_method.currentData()
        borrower_name = self.lg_loan_borrower.currentText()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="DEBIT", amount=amount, person_org=borrower_name,
            description=f"Loan given to {borrower_name}", category_names=("Finance", "Other")
        )
        self.repos["loans"].create_loan(
            borrower_id=bid, loan_amount=amount, payment_method=method,
            start_date=self.lg_loan_start.date().toString("yyyy-MM-dd"),
            due_date=self.lg_loan_due.date().toString("yyyy-MM-dd"),
            status="ACTIVE", description=self.lg_loan_desc.text().strip() or None, trxn_id=txn_id
        )
        self.lg_loan_amount.setValue(0)
        self.lg_loan_desc.clear()
        self._refresh_entry_dropdowns()
        self.load_list()
        QMessageBox.information(self, "Loan Recorded", f"\u20b9{amount:,.2f} loan to {borrower_name} recorded.")

    def _log_repayment(self):
        lid = self.lg_rep_loan.get_data()
        amount = self.lg_rep_amount.value()
        if not lid or amount <= 0:
            QMessageBox.warning(self, "Missing Info", "Select a loan and enter an amount.")
            return
        loan = self.repos["loans"].get_loan(lid)
        account_id = self.lg_rep_account.currentData()
        method = self.lg_rep_method.currentData()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="CREDIT", amount=amount, person_org=loan["borrower_name"] if loan else None,
            description=f"Loan repayment from {loan['borrower_name']}" if loan else "Loan repayment",
            category_names=("Finance", "Other")
        )
        self.repos["loans"].add_repayment(
            loan_id=lid, amount_paid=amount,
            payment_date=self.lg_rep_date.date().toString("yyyy-MM-dd"),
            payment_method=method, description=self.lg_rep_desc.text().strip() or None,
            linked_txn_id=txn_id
        )
        self.lg_rep_amount.setValue(0)
        self.lg_rep_desc.clear()
        self._refresh_entry_dropdowns()
        self.load_list()
        QMessageBox.information(self, "Repayment Logged", "Repayment recorded successfully.")

    # ── List ──
    def load_list(self):
        # normalize CLEARED → CLOSED
        self.db.execute("UPDATE loans SET status='CLOSED' WHERE status='CLEARED'")
        self.repos["loans"].sync_overdue()
        self._list_data = self.repos["loans"].list_loans()
        self._render_list()

    def _render_list(self):
        if not hasattr(self, "_list_lay"):
            return
        _clear_layout(self._stats_row)
        _clear_layout(self._list_lay)
        loans = list(self._list_data)
        # stats from full data
        total_pending = sum(
            max(l["loan_amount"] - self.repos["loans"].total_repaid(l["loan_id"]), 0)
            for l in loans if l["status"] != "CLOSED"
        )
        pending_count = len([l for l in loans if l["status"] != "CLOSED"])
        _fill_stats_row(self._stats_row, [
            _metric_card("Total Pending", fmt_money(total_pending), C["amber"]),
            _metric_card("Pending Loans", str(pending_count)),
            _metric_card("Total Loans", str(len(loans))),
        ])
        # search
        search = self._search_input.text().strip().lower() if hasattr(self, "_search_input") else ""
        if search:
            loans = [l for l in loans if search in l["borrower_name"].lower()]
        # sort (always ascending, then flip if direction is descending)
        mode = self._sort_cb.currentText() if hasattr(self, "_sort_cb") else ""
        rank = {"ACTIVE": 0, "OVERDUE": 1, "PARTIALLY_PAID": 2, "CLOSED": 3}
        if mode == "Status":
            loans.sort(key=lambda l: rank.get(l["status"], 9))
        elif mode == "Borrower":
            loans.sort(key=lambda l: l["borrower_name"].lower())
        elif mode == "Amount":
            loans.sort(key=lambda l: l["loan_amount"])
        elif mode == "Due Date":
            loans.sort(key=lambda l: l["due_date"] or "zzz")
        if not getattr(self, "_sort_asc", True):
            loans.reverse()
        # render
        if not loans:
            empty = QLabel("No matching loans." if search else "No loans given yet.")
            empty.setStyleSheet(f"color:{C['text3']};padding:20px;")
            empty.setAlignment(Qt.AlignCenter)
            self._list_lay.addWidget(empty)
            return
        for l in loans:
            paid = self.repos["loans"].total_repaid(l["loan_id"])
            pending = l["loan_amount"] - paid
            pct = (paid / l["loan_amount"] * 100) if l["loan_amount"] else 0
            color = status_color("loan", l["status"])
            card = _wealth_card(
                title=l["borrower_name"],
                subtitle=f"Given {l['start_date']} {MDOT} Due {l['due_date'] or EM_DASH}",
                amount_text=fmt_money(pending) + " pending", badge_text=l["status"],
                badge_color=color, progress_pct=pct,
                extra_line=f"Loan: {fmt_money(l['loan_amount'])} {MDOT} Repaid: {fmt_money(paid)}",
                on_click=lambda lid=l["loan_id"]: self._open_detail(lid)
            )
            self._list_lay.addWidget(card)

    def _open_detail(self, loan_id):
        loan = self.repos["loans"].get_loan(loan_id)
        if not loan:
            return
        repayments = self.repos["loans"].get_repayments(loan_id)
        dlg = LoanDetailDialog(
            role="give", title=f"Loan to {loan['borrower_name']}",
            principal=loan["loan_amount"], status=loan["status"],
            start_date=loan["start_date"], due_date=loan["due_date"],
            description=loan.get("description"), repayments=repayments,
            amount_key="amount_paid", date_key="payment_date", parent=self
        )
        dlg.exec_()


# ══════════════════════════════════════════════════════════════════════════
#  LOANS I TAKE
# ══════════════════════════════════════════════════════════════════════════
class LoansTakePage(_FunctionPage):
    ICON = "\U0001f3db\ufe0f"
    TITLE = "Loans I Take"

    _FREQ_LABELS = ["Annual", "Quarterly", "Semi-Annual"]
    _FREQ_VALUES = ["ANNUAL", "QUARTERLY", "SEMI_ANNUAL"]

    def _sort_options(self):
        return ["Status", "Lender", "Amount", "Due Date"]

    # ── helpers ───────────────────────────────────────────────────────
    def _loan_months(self, loan):
        """Derive tenure in months from start_date / due_date."""
        sd = date.fromisoformat(loan["start_date"])
        dd = loan.get("due_date")
        if dd:
            ed = date.fromisoformat(dd)
            return max(1, round((ed - sd).days / 30.44))
        return 12

    def _analysis(self, loan):
        """Run LoanService.loan_analysis for a given loan dict."""
        total_paid = self.repos["borrowed"].total_repaid(loan["loan_id"])
        months = self._loan_months(loan)
        freq = loan.get("interest_type") or "ANNUAL"
        return LoanService.loan_analysis(
            loan["principal_amount"], loan["interest_rate"] or 0,
            months, freq, total_paid, loan["start_date"]
        )

    # ── Entry ─────────────────────────────────────────────────────────
    def _build_entry(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.lt_stack, _ = _build_subnav(lay, ["Take Loan", "Log EMI Payment"])

        # ── Take Loan (EMI) ──
        p1 = QWidget()
        f1 = QFormLayout(p1)
        self.lt_loan_lender = SearchableCombo(placeholder="Search lender\u2026")
        self.lt_loan_freq = QComboBox()
        self.lt_loan_freq.addItems(self._FREQ_LABELS)
        self.lt_loan_principal = QDoubleSpinBox()
        self.lt_loan_principal.setRange(0, 999999999)
        self.lt_loan_principal.setPrefix("\u20b9 ")
        self.lt_loan_principal.setDecimals(2)
        self.lt_loan_rate = QDoubleSpinBox()
        self.lt_loan_rate.setRange(0, 60)
        self.lt_loan_rate.setSuffix(" %")
        self.lt_loan_rate.setDecimals(2)
        self.lt_loan_months = QSpinBox()
        self.lt_loan_months.setRange(1, 480)
        self.lt_loan_months.setValue(12)
        self.lt_loan_account = _account_combo(self.repos["accounts"])
        self.lt_loan_method = _method_combo(self.repos["lookups"])
        self.lt_loan_start = QDateEdit(QDate.currentDate())
        self.lt_loan_start.setCalendarPopup(True)
        self.lt_loan_desc = QLineEdit()
        self.lt_loan_desc.setPlaceholderText("Optional note")
        self.lt_emi_preview = QLabel("EMI: \u2014  |  Total Repay: \u2014")
        self.lt_emi_preview.setStyleSheet(f"color:{C['accent']};font-weight:800;font-size:13px;")
        self.lt_emi_preview.setWordWrap(True)
        for w in (self.lt_loan_principal, self.lt_loan_rate, self.lt_loan_months, self.lt_loan_freq):
            if isinstance(w, QComboBox):
                w.currentIndexChanged.connect(self._update_emi)
            else:
                w.valueChanged.connect(self._update_emi)
        take_btn = QPushButton("\U0001f3db\ufe0f  Take Loan")
        take_btn.setObjectName("primary")
        take_btn.clicked.connect(self._take_loan)
        f1.addRow("Lender *", _entity_row(self.lt_loan_lender, self._add_lender_dlg))
        f1.addRow("Interest Type", self.lt_loan_freq)
        f1.addRow("Principal *", self.lt_loan_principal)
        f1.addRow("Interest Rate (annual)", self.lt_loan_rate)
        f1.addRow("Tenure (months) *", self.lt_loan_months)
        f1.addRow("", self.lt_emi_preview)
        f1.addRow("Received Into *", self.lt_loan_account)
        f1.addRow("Method *", self.lt_loan_method)
        f1.addRow("Start Date", self.lt_loan_start)
        f1.addRow("Description", self.lt_loan_desc)
        f1.addRow("", take_btn)
        self.lt_stack.addWidget(p1)
        self._update_emi()

        # ── Log EMI Payment ──
        p2 = QWidget()
        f2 = QFormLayout(p2)
        self.lt_rep_loan = SearchableCombo(placeholder="Search loan\u2026")
        self.lt_rep_info_lbl = QLabel("")
        self.lt_rep_info_lbl.setStyleSheet(f"color:{C['text3']};font-weight:600;font-size:11px;")
        self.lt_rep_info_lbl.setWordWrap(True)
        self.lt_rep_loan.currentIndexChanged.connect(self._on_rep_loan_changed)
        # amount type selector
        self.lt_rep_type = QComboBox()
        self.lt_rep_type.addItems(["Updated EMI", "Original EMI", "Full Pay", "Custom"])
        self.lt_rep_type.currentIndexChanged.connect(self._on_rep_type_changed)
        self.lt_rep_amount = QDoubleSpinBox()
        self.lt_rep_amount.setRange(0, 99999999)
        self.lt_rep_amount.setPrefix("\u20b9 ")
        self.lt_rep_amount.setDecimals(2)
        self.lt_rep_account = _account_combo(self.repos["accounts"])
        self.lt_rep_method = _method_combo(self.repos["lookups"])
        self.lt_rep_date = QDateEdit(QDate.currentDate())
        self.lt_rep_date.setCalendarPopup(True)
        self.lt_rep_desc = QLineEdit()
        self.lt_rep_desc.setPlaceholderText("Optional note")
        pay_btn = QPushButton("\U0001f4b8  Log EMI Payment")
        pay_btn.setObjectName("primary")
        pay_btn.clicked.connect(self._log_emi)
        f2.addRow("Loan *", self.lt_rep_loan)
        f2.addRow("", self.lt_rep_info_lbl)
        f2.addRow("Amount Type", self.lt_rep_type)
        f2.addRow("Amount *", self.lt_rep_amount)
        f2.addRow("Pay From *", self.lt_rep_account)
        f2.addRow("Method *", self.lt_rep_method)
        f2.addRow("Date", self.lt_rep_date)
        f2.addRow("Description", self.lt_rep_desc)
        f2.addRow("", pay_btn)
        self.lt_stack.addWidget(p2)
        return page

    def _add_lender_dlg(self):
        name = _simple_add_dialog(self, "Add New Lender", "Lender Name", "Bank / NBFC / person")
        if not name:
            return
        self.repos["borrowed"].create_lender(name)
        self._refresh_entry_dropdowns()
        for i in range(self.lt_loan_lender.count()):
            if self.lt_loan_lender.itemText(i) == name:
                self.lt_loan_lender.setCurrentIndex(i)
                break
        QMessageBox.information(self, "Added", f"'{name}' added as a lender.")

    def _update_emi(self):
        p = self.lt_loan_principal.value()
        r = self.lt_loan_rate.value()
        m = self.lt_loan_months.value()
        fi = self.lt_loan_freq.currentIndex()
        freq = self._FREQ_VALUES[fi] if fi >= 0 else "ANNUAL"
        if p > 0 and m > 0:
            emi = LoanService.emi(p, r, m, freq)
            total = LoanService.total_expected(emi, m)
            self.lt_emi_preview.setText(
                f"EMI: {fmt_money(emi)}/mo  |  Total Repay: {fmt_money(total)}  ({m} months)"
            )
        else:
            self.lt_emi_preview.setText("EMI: \u2014  |  Total Repay: \u2014")

    def _refresh_entry_dropdowns(self):
        self.lt_loan_lender.clear_items()
        for l in self.repos["borrowed"].list_lenders():
            self.lt_loan_lender.add_item(l["name"], l["lender_id"])
        self.lt_rep_loan.clear_items()
        for l in self.repos["borrowed"].list_loans():
            if l["status"] not in ("CLOSED", "REPAID"):
                self.lt_rep_loan.add_item(
                    f"{l['lender_name']} \u2014 {fmt_money(l['principal_amount'])} ({l['status']})",
                    l["loan_id"]
                )
        self._on_rep_loan_changed()

    def _on_rep_loan_changed(self):
        """Refresh info label + pre-fill amount when loan selection changes."""
        lid = self.lt_rep_loan.get_data()
        if not lid:
            self.lt_rep_info_lbl.setText("")
            return
        loan = self.repos["borrowed"].get_loan(lid)
        if not loan:
            return
        a = self._analysis(loan)
        self.lt_rep_info_lbl.setText(
            f"Original EMI: {fmt_money(a['original_emi'])}  {MDOT}  "
            f"Updated EMI: {fmt_money(a['updated_emi'])}  {MDOT}  "
            f"Current Value: {fmt_money(a['current_value'])}  {MDOT}  "
            f"Paid: {fmt_money(a['total_paid'])}"
        )
        self._on_rep_type_changed()

    def _on_rep_type_changed(self):
        """Auto-fill amount based on selected type."""
        mode = self.lt_rep_type.currentText()
        lid = self.lt_rep_loan.get_data()
        if not lid:
            return
        loan = self.repos["borrowed"].get_loan(lid)
        if not loan:
            return
        a = self._analysis(loan)
        if mode == "Updated EMI":
            self.lt_rep_amount.setValue(a["updated_emi"])
            self.lt_rep_amount.setEnabled(False)
        elif mode == "Original EMI":
            self.lt_rep_amount.setValue(a["original_emi"])
            self.lt_rep_amount.setEnabled(False)
        elif mode == "Full Pay":
            self.lt_rep_amount.setValue(a["full_payoff"])
            self.lt_rep_amount.setEnabled(False)
        else:  # Custom
            self.lt_rep_amount.setValue(0)
            self.lt_rep_amount.setEnabled(True)

    def _take_loan(self):
        lid = self.lt_loan_lender.get_data()
        principal = self.lt_loan_principal.value()
        months = self.lt_loan_months.value()
        rate = self.lt_loan_rate.value()
        fi = self.lt_loan_freq.currentIndex()
        freq = self._FREQ_VALUES[fi] if fi >= 0 else "ANNUAL"
        if not lid or principal <= 0:
            QMessageBox.warning(self, "Missing Info", "Select a lender and enter the principal.")
            return
        emi = LoanService.emi(principal, rate, months, freq)
        start = self.lt_loan_start.date().toPyDate()
        due = _add_months(start, months)
        account_id = self.lt_loan_account.currentData()
        method = self.lt_loan_method.currentData()
        lender_name = self.lt_loan_lender.currentText()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="CREDIT", amount=principal, person_org=lender_name,
            description=f"Loan taken from {lender_name}", category_names=("Finance", "Other")
        )
        self.repos["borrowed"].create_loan(
            lender_id=lid, principal_amount=principal, interest_rate=rate, emi_amount=emi,
            interest_type=freq,
            start_date=start.isoformat(), due_date=due.isoformat(), status="ACTIVE",
            description=self.lt_loan_desc.text().strip() or None, linked_txn_id=txn_id
        )
        self.lt_loan_principal.setValue(0)
        self.lt_loan_desc.clear()
        self._refresh_entry_dropdowns()
        self.load_list()
        total = LoanService.total_expected(emi, months)
        QMessageBox.information(
            self, "Loan Recorded",
            f"\u20b9{principal:,.2f} loan from {lender_name}.\n"
            f"EMI \u2248 {fmt_money(emi)}/mo {MDOT} Total repay: {fmt_money(total)}"
        )

    def _log_emi(self):
        lid = self.lt_rep_loan.get_data()
        amount = self.lt_rep_amount.value()
        if not lid or amount <= 0:
            QMessageBox.warning(self, "Missing Info", "Select a loan and enter an amount.")
            return
        loan = self.repos["borrowed"].get_loan(lid)
        account_id = self.lt_rep_account.currentData()
        method = self.lt_rep_method.currentData()
        desc_extra = self.lt_rep_type.currentText()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="DEBIT", amount=amount, person_org=loan["lender_name"] if loan else None,
            description=f"EMI payment ({desc_extra}) to {loan['lender_name']}" if loan else f"EMI payment ({desc_extra})",
            category_names=("Finance", "Other")
        )
        self.repos["borrowed"].add_repayment(
            loan_id=lid, amount_paid=amount,
            payment_date=self.lt_rep_date.date().toString("yyyy-MM-dd"),
            payment_method=method, description=self.lt_rep_desc.text().strip() or None,
            linked_txn_id=txn_id
        )
        self.lt_rep_desc.clear()
        self._refresh_entry_dropdowns()
        self.load_list()
        # check if now REPAID
        loan = self.repos["borrowed"].get_loan(lid)
        if loan and loan["status"] == "REPAID":
            QMessageBox.information(self, "Loan Fully Repaid",
                "This loan has been fully repaid.\nStatus: REPAID \u2014 waiting for closure confirmation.")
        else:
            QMessageBox.information(self, "Payment Logged", f"{desc_extra} payment recorded successfully.")

    # ── List ──────────────────────────────────────────────────────────
    def load_list(self):
        self.repos["borrowed"].sync_overdue()
        self._list_data = self.repos["borrowed"].list_loans()
        self._render_list()

    def _render_list(self):
        if not hasattr(self, "_list_lay"):
            return
        _clear_layout(self._stats_row)
        _clear_layout(self._list_lay)
        loans = list(self._list_data)
        active = [l for l in loans if l["status"] not in ("CLOSED", "REPAID")]
        total_outstanding = 0
        for l in active:
            a = self._analysis(l)
            total_outstanding += a["current_value"]
        _fill_stats_row(self._stats_row, [
            _metric_card("Total Outstanding", fmt_money(total_outstanding), C["amber"]),
            _metric_card("Active Loans", str(len(active))),
            _metric_card("Total Loans", str(len(loans))),
        ])
        search = self._search_input.text().strip().lower() if hasattr(self, "_search_input") else ""
        if search:
            loans = [l for l in loans if search in l["lender_name"].lower()]
        mode = self._sort_cb.currentText() if hasattr(self, "_sort_cb") else ""
        rank = {"OVERDUE": 0, "ACTIVE": 1, "PARTIALLY_PAID": 2, "REPAID": 3, "CLOSED": 4}
        if mode == "Status":
            loans.sort(key=lambda l: rank.get(l["status"], 9))
        elif mode == "Lender":
            loans.sort(key=lambda l: l["lender_name"].lower())
        elif mode == "Amount":
            loans.sort(key=lambda l: l["principal_amount"])
        elif mode == "Due Date":
            loans.sort(key=lambda l: l["due_date"] or "zzz")
        if not getattr(self, "_sort_asc", True):
            loans.reverse()
        if not loans:
            empty = QLabel("No matching loans." if search else "No loans taken yet.")
            empty.setStyleSheet(f"color:{C['text3']};padding:20px;")
            empty.setAlignment(Qt.AlignCenter)
            self._list_lay.addWidget(empty)
            return
        for l in loans:
            a = self._analysis(l)
            color = status_color("liability", l["status"])
            freq_tag = l.get("interest_type") or "ANNUAL"
            freq_short = {"ANNUAL": "Annual", "QUARTERLY": "Qtr", "SEMI_ANNUAL": "Semi"}.get(freq_tag, "")
            sub = (f"Rate {l['interest_rate']}% {freq_short} {MDOT} "
                   f"EMI {fmt_money(a['original_emi'])} {MDOT} Due {l['due_date'] or EM_DASH}")
            amount_text = fmt_money(a["current_value"]) + " outstanding"
            extra = (f"Updated EMI: {fmt_money(a['updated_emi'])} {MDOT} "
                     f"Paid: {fmt_money(a['total_paid'])} {MDOT} "
                     f"Principal: {fmt_money(l['principal_amount'])}")
            card = _wealth_card(
                title=l["lender_name"], subtitle=sub,
                amount_text=amount_text, badge_text=l["status"],
                badge_color=color, extra_line=extra,
                on_click=lambda lid=l["loan_id"]: self._open_detail(lid)
            )
            self._list_lay.addWidget(card)

    def _open_detail(self, loan_id):
        loan = self.repos["borrowed"].get_loan(loan_id)
        if not loan:
            return
        repayments = self.repos["borrowed"].get_repayments(loan_id)
        months = self._loan_months(loan)
        freq = loan.get("interest_type") or "ANNUAL"
        amort = LoanService.amortize(loan["principal_amount"], loan["interest_rate"] or 0, months, freq)
        a = self._analysis(loan)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Loan from {loan['lender_name']}")
        dlg.setMinimumWidth(580)
        lay = QVBoxLayout(dlg)

        # header
        hdr = QHBoxLayout()
        t = QLabel(f"Loan from {loan['lender_name']}")
        t.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        hdr.addWidget(t, 1)
        hdr.addWidget(_badge(loan["status"], status_color("liability", loan["status"])))
        lay.addLayout(hdr)

        # info grid
        info = QLabel(
            f"Principal: {fmt_money(loan['principal_amount'])}  {MDOT}  "
            f"Rate: {loan['interest_rate']}%  {freq}  {MDOT}  "
            f"Original EMI: {fmt_money(a['original_emi'])}\n"
            f"Start: {loan['start_date']}  {MDOT}  Due: {loan['due_date'] or EM_DASH}  {MDOT}  "
            f"Tenure: {months} months"
        )
        info.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        # analysis row
        a_lbl = QLabel(
            f"Current Value: {fmt_money(a['current_value'])}  {MDOT}  "
            f"Updated EMI: {fmt_money(a['updated_emi'])}  {MDOT}  "
            f"Full Payoff: {fmt_money(a['full_payoff'])}\n"
            f"Total Paid: {fmt_money(a['total_paid'])}  {MDOT}  "
            f"Total Expected: {fmt_money(a['total_expected'])}  {MDOT}  "
            f"Interest Accrued: {fmt_money(a['total_interest_accrued'])}"
        )
        a_lbl.setStyleSheet(f"color:{C['text']};font-weight:700;font-size:12px;padding:6px 0;")
        a_lbl.setWordWrap(True)
        lay.addWidget(a_lbl)

        if loan.get("description"):
            d = QLabel(loan["description"])
            d.setStyleSheet(f"color:{C['text2']};font-size:12px;font-style:italic;")
            d.setWordWrap(True)
            lay.addWidget(d)

        # tabs: repayments + amortization
        tabs = QTabWidget()
        # repayments table
        rtable = QTableWidget()
        rtable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        rtable.verticalHeader().setVisible(False)
        rtable.setColumnCount(3)
        rtable.setHorizontalHeaderLabels(["Date", "Amount", "Description"])
        rtable.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        rtable.setRowCount(len(repayments))
        for i, r in enumerate(repayments):
            rtable.setItem(i, 0, QTableWidgetItem(r.get("payment_date", "")))
            rtable.setItem(i, 1, QTableWidgetItem(fmt_money(r["amount_paid"])))
            rtable.setItem(i, 2, QTableWidgetItem(r.get("description") or ""))
        if not repayments:
            rtable.setRowCount(1)
            rtable.setItem(0, 0, QTableWidgetItem("No repayments logged yet."))
            rtable.setSpan(0, 0, 1, 3)
        tabs.addTab(rtable, "Repayment Log")
        # amortization
        atable = QTableWidget()
        atable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        atable.verticalHeader().setVisible(False)
        atable.setColumnCount(5)
        atable.setHorizontalHeaderLabels(["Month", "EMI", "Principal", "Interest", "Balance"])
        atable.setRowCount(len(amort))
        for i, row in enumerate(amort):
            atable.setItem(i, 0, QTableWidgetItem(str(row["month"])))
            atable.setItem(i, 1, QTableWidgetItem(fmt_money(row["emi"])))
            atable.setItem(i, 2, QTableWidgetItem(fmt_money(row["principal"])))
            atable.setItem(i, 3, QTableWidgetItem(fmt_money(row["interest"])))
            atable.setItem(i, 4, QTableWidgetItem(fmt_money(row["balance"])))
        tabs.addTab(atable, "Amortization Schedule")
        lay.addWidget(tabs, 1)

        # buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if loan["status"] == "REPAID":
            close_btn = QPushButton("\u2705 Mark as Closed")
            close_btn.setObjectName("primary")
            close_btn.clicked.connect(lambda: self._mark_closed(loan_id, dlg))
            btn_row.addWidget(close_btn)
        ok = QPushButton("Close")
        ok.clicked.connect(dlg.accept)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)
        dlg.exec_()

    def _mark_closed(self, loan_id, dlg=None):
        if _confirm(self, "Mark Closed", "Confirm: this loan is fully repaid. Mark as CLOSED?"):
            self.repos["borrowed"].update_status(loan_id, "CLOSED")
            self.load_list()
            if dlg:
                dlg.accept()
            return True
        return False


# ══════════════════════════════════════════════════════════════════════════
#  LOAN DETAIL DIALOG (shared by Give + Take + Deposits)
# ══════════════════════════════════════════════════════════════════════════
class LoanDetailDialog(QDialog):
    def __init__(self, role, title, principal, status, start_date, due_date, description,
                 repayments, amount_key, date_key, amortization=None, emi=None, rate=None,
                 on_mark_closed=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        hdr = QHBoxLayout()
        t = QLabel(title)
        t.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        hdr.addWidget(t, 1)
        color = status_color("loan" if role == "give" else "liability", status)
        hdr.addWidget(_badge(status, color))
        lay.addLayout(hdr)
        info_bits = [
            f"Principal: {fmt_money(principal)}",
            f"Start: {start_date}",
            f"Due: {due_date or EM_DASH}",
        ]
        if rate is not None:
            info_bits.insert(1, f"Rate: {rate}%")
        if emi is not None:
            info_bits.insert(2, f"EMI: {fmt_money(emi)}")
        info = QLabel(f" {MDOT} ".join(info_bits))
        info.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        info.setWordWrap(True)
        lay.addWidget(info)
        if description:
            d = QLabel(description)
            d.setStyleSheet(f"color:{C['text2']};font-size:12px;font-style:italic;")
            d.setWordWrap(True)
            lay.addWidget(d)
        total_paid = sum(r[amount_key] for r in repayments)
        summary = QLabel(
            f"Total Repaid: {fmt_money(total_paid)}  {MDOT}  Remaining: {fmt_money(max(principal - total_paid, 0))}"
        )
        summary.setStyleSheet(f"color:{C['text']};font-weight:700;font-size:12px;padding-top:6px;")
        lay.addWidget(summary)
        if amortization:
            tabs = QTabWidget()
            tabs.addTab(self._repayments_table(repayments, amount_key, date_key), "Repayment Log")
            tabs.addTab(self._amortization_table(amortization), "Amortization Schedule")
            lay.addWidget(tabs, 1)
        else:
            lay.addWidget(self._repayments_table(repayments, amount_key, date_key), 1)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if on_mark_closed and status not in ("CLOSED", "CLEARED"):
            close_btn = QPushButton("\u2705 Mark as Closed")
            close_btn.setObjectName("primary")
            close_btn.clicked.connect(lambda: (on_mark_closed(), self.accept()))
            btn_row.addWidget(close_btn)
        ok = QPushButton("Close")
        ok.clicked.connect(self.accept)
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
            table.setItem(0, 0, QTableWidgetItem("No repayments logged yet."))
            table.setSpan(0, 0, 1, 3)
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


# ══════════════════════════════════════════════════════════════════════════
#  FD I DEPOSIT
# ══════════════════════════════════════════════════════════════════════════
class FDGivePage(_FunctionPage):
    ICON = "\U0001f3e6"
    TITLE = "FD I Deposit"

    def _sort_options(self):
        return ["Status", "Account", "Maturity Date"]

    # ── Entry (single form, no sub-nav needed) ──
    def _build_entry(self):
        page = QWidget()
        f = QFormLayout(page)
        self.fd_principal = QDoubleSpinBox()
        self.fd_principal.setRange(0, 999999999)
        self.fd_principal.setPrefix("\u20b9 ")
        self.fd_principal.setDecimals(2)
        self.fd_rate = QDoubleSpinBox()
        self.fd_rate.setRange(0, 20)
        self.fd_rate.setSuffix(" %")
        self.fd_rate.setDecimals(2)
        self.fd_rate.setValue(7.0)
        self.fd_start = QDateEdit(QDate.currentDate())
        self.fd_start.setCalendarPopup(True)
        self.fd_maturity = QDateEdit(QDate.currentDate().addYears(1))
        self.fd_maturity.setCalendarPopup(True)
        self.fd_account = _account_combo(self.repos["accounts"])
        self.fd_maturity_preview = QLabel("Estimated Maturity Amount: \u2014")
        self.fd_maturity_preview.setStyleSheet(f"color:{C['green']};font-weight:800;font-size:13px;")
        for w in (self.fd_principal, self.fd_rate):
            w.valueChanged.connect(self._update_maturity)
        self.fd_start.dateChanged.connect(self._update_maturity)
        self.fd_maturity.dateChanged.connect(self._update_maturity)
        create_btn = QPushButton("\U0001f3e6  Create Fixed Deposit")
        create_btn.setObjectName("primary")
        create_btn.clicked.connect(self._create_fd)
        f.addRow("Bank Account *", self.fd_account)
        f.addRow("Principal *", self.fd_principal)
        f.addRow("Interest Rate (annual) *", self.fd_rate)
        f.addRow("Start Date", self.fd_start)
        f.addRow("Maturity Date *", self.fd_maturity)
        f.addRow("", self.fd_maturity_preview)
        f.addRow("", create_btn)
        self._update_maturity()
        return page

    def _update_maturity(self):
        p = self.fd_principal.value()
        r = self.fd_rate.value()
        s = self.fd_start.date().toString("yyyy-MM-dd")
        m = self.fd_maturity.date().toString("yyyy-MM-dd")
        if p > 0 and self.fd_maturity.date() > self.fd_start.date():
            amt = FDService.maturity(p, r, s, m)
            self.fd_maturity_preview.setText(f"Estimated Maturity Amount: {fmt_money(amt)} (quarterly compounding)")
        else:
            self.fd_maturity_preview.setText("Estimated Maturity Amount: \u2014")

    def _refresh_entry_dropdowns(self):
        pass

    def _create_fd(self):
        p = self.fd_principal.value()
        if p <= 0:
            QMessageBox.warning(self, "Missing Info", "Please enter the deposit principal.")
            return
        if self.fd_maturity.date() <= self.fd_start.date():
            QMessageBox.warning(self, "Invalid Dates", "Maturity date must be after start date.")
            return
        account_id = self.fd_account.currentData()
        account_name = self.fd_account.currentText()
        default_method = self.repos["lookups"].list_methods()
        method_id = default_method[0]["method_id"] if default_method else None
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method_id,
            tx_type="DEBIT", amount=p, person_org=None,
            description=f"FD deposit at {account_name}", category_names=("Investment", "Finance")
        )
        self.repos["fd"].create(
            bank_account_id=account_id, principal_amount=p, interest_rate=self.fd_rate.value(),
            start_date=self.fd_start.date().toString("yyyy-MM-dd"),
            maturity_date=self.fd_maturity.date().toString("yyyy-MM-dd"),
            status="ACTIVE", linked_txn_id=txn_id
        )
        self.fd_principal.setValue(0)
        self.load_list()
        QMessageBox.information(self, "FD Created", "Fixed deposit recorded successfully.")

    # ── List ──
    def load_list(self):
        self.repos["fd"].sync_matured()
        self._list_data = self.repos["fd"].list_all()
        self._render_list()

    def _render_list(self):
        if not hasattr(self, "_list_lay"):
            return
        _clear_layout(self._stats_row)
        _clear_layout(self._list_lay)
        fds = list(self._list_data)
        total_p = sum(f["principal_amount"] for f in fds)
        total_m = sum(f["maturity_amount"] or f["principal_amount"] for f in fds)
        _fill_stats_row(self._stats_row, [
            _metric_card("Total Invested", fmt_money(total_p)),
            _metric_card("Total Maturity", fmt_money(total_m), C["green"]),
            _metric_card("Total FDs", str(len(fds))),
        ])
        search = self._search_input.text().strip().lower() if hasattr(self, "_search_input") else ""
        if search:
            fds = [f for f in fds if search in (f["account_name"] or "").lower()]
        mode = self._sort_cb.currentText() if hasattr(self, "_sort_cb") else ""
        rank = {"ACTIVE": 0, "MATURED": 1, "WITHDRAWN": 2}
        if mode == "Status":
            fds.sort(key=lambda f: rank.get(f["status"], 9))
        elif mode == "Account":
            fds.sort(key=lambda f: (f["account_name"] or "").lower())
        elif mode == "Maturity Date":
            fds.sort(key=lambda f: f["maturity_date"])
        if not getattr(self, "_sort_asc", True):
            fds.reverse()
        if not fds:
            empty = QLabel("No matching FDs." if search else "No fixed deposits yet.")
            empty.setStyleSheet(f"color:{C['text3']};padding:20px;")
            empty.setAlignment(Qt.AlignCenter)
            self._list_lay.addWidget(empty)
            return
        for fd in fds:
            pct = FDService.progress(fd["start_date"], fd["maturity_date"])
            color = status_color("asset", fd["status"])
            card = _wealth_card(
                title=fd["account_name"] or "Fixed Deposit",
                subtitle=f"{fd['interest_rate']}% {MDOT} {fd['start_date']} \u2192 {fd['maturity_date']}",
                amount_text=fmt_money(fd["maturity_amount"] or fd["principal_amount"]),
                badge_text=fd["status"], badge_color=color, progress_pct=pct,
                extra_line=f"Principal: {fmt_money(fd['principal_amount'])} {MDOT} {pct:.0f}% elapsed",
                on_click=lambda fid=fd["fd_id"]: self._open_detail(fid)
            )
            self._list_lay.addWidget(card)

    def _open_detail(self, fd_id):
        fd = self.repos["fd"].get(fd_id)
        if not fd:
            return
        dlg = FDDetailDialog(
            fd, on_mark_matured=lambda: self._mark_matured(fd_id),
            on_mark_withdrawn=lambda acc, method: self._mark_withdrawn(fd_id, acc, method),
            accounts_repo=self.repos["accounts"], lookups_repo=self.repos["lookups"], parent=self
        )
        dlg.exec_()

    def _mark_matured(self, fd_id):
        if _confirm(self, "Mark Matured", "Mark this FD as matured?"):
            self.repos["fd"].update_status(fd_id, "MATURED")
            self.load_list()
            return True
        return False

    def _mark_withdrawn(self, fd_id, account_id, method_id):
        fd = self.repos["fd"].get(fd_id)
        if not fd:
            return False
        amount = fd["maturity_amount"] or fd["principal_amount"]
        _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method_id,
            tx_type="CREDIT", amount=amount, person_org=None,
            description="FD maturity withdrawal", category_names=("Investment", "Finance")
        )
        self.repos["fd"].update_status(fd_id, "WITHDRAWN")
        self.load_list()
        return True


# ══════════════════════════════════════════════════════════════════════════
#  FD DETAIL DIALOG
# ══════════════════════════════════════════════════════════════════════════
class FDDetailDialog(QDialog):
    def __init__(self, fd, on_mark_matured, on_mark_withdrawn, accounts_repo, lookups_repo, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fixed Deposit Detail")
        self.setMinimumWidth(440)
        self.fd = fd
        self._on_matured = on_mark_matured
        self._on_withdrawn = on_mark_withdrawn
        self.accounts_repo = accounts_repo
        self.lookups_repo = lookups_repo
        lay = QVBoxLayout(self)
        hdr = QHBoxLayout()
        t = QLabel(fd["account_name"] or "Fixed Deposit")
        t.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        hdr.addWidget(t, 1)
        hdr.addWidget(_badge(fd["status"], status_color("asset", fd["status"])))
        lay.addLayout(hdr)
        pct = FDService.progress(fd["start_date"], fd["maturity_date"])
        pb = QProgressBar()
        pb.setRange(0, 100)
        pb.setValue(int(pct))
        pb.setTextVisible(True)
        pb.setFormat(f"{pct:.0f}% of tenure elapsed")
        lay.addWidget(pb)
        info = QLabel(
            f"Principal: {fmt_money(fd['principal_amount'])}  {MDOT}  Rate: {fd['interest_rate']}%  {MDOT}  "
            f"Maturity Amount: {fmt_money(fd['maturity_amount'] or 0)}\n"
            f"Start: {fd['start_date']}  {MDOT}  Maturity: {fd['maturity_date']}"
        )
        info.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        info.setWordWrap(True)
        lay.addWidget(info)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if fd["status"] == "ACTIVE" and pct >= 100:
            m_btn = QPushButton("\u2705 Mark Matured")
            m_btn.setObjectName("primary")
            m_btn.clicked.connect(self._do_matured)
            btn_row.addWidget(m_btn)
        if fd["status"] in ("ACTIVE", "MATURED"):
            w_btn = QPushButton("\U0001f4b5 Mark Withdrawn (credit maturity amount)")
            w_btn.clicked.connect(self._do_withdrawn)
            btn_row.addWidget(w_btn)
        ok = QPushButton("Close")
        ok.clicked.connect(self.accept)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)

    def _do_matured(self):
        if self._on_matured():
            self.accept()

    def _do_withdrawn(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Withdraw FD")
        f = QFormLayout(dlg)
        acc_cb = _account_combo(self.accounts_repo)
        idx = acc_cb.findData(self.fd["bank_account_id"])
        if idx >= 0:
            acc_cb.setCurrentIndex(idx)
        method_cb = _method_combo(self.lookups_repo)
        f.addRow("Credit Into *", acc_cb)
        f.addRow("Method *", method_cb)
        row = QHBoxLayout()
        ok_btn = QPushButton("Confirm")
        ok_btn.setObjectName("primary")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        ok_btn.clicked.connect(dlg.accept)
        row.addStretch()
        row.addWidget(cancel_btn)
        row.addWidget(ok_btn)
        f.addRow("", row)
        if dlg.exec_() == QDialog.Accepted:
            if self._on_withdrawn(acc_cb.currentData(), method_cb.currentData()):
                self.accept()


# ══════════════════════════════════════════════════════════════════════════
#  FD OTHERS DEPOSIT
# ══════════════════════════════════════════════════════════════════════════
class FDOthersPage(_FunctionPage):
    ICON = "\U0001f9fe"
    TITLE = "FD Others Deposit"

    def _sort_options(self):
        return ["Status", "Depositor", "Amount", "Return Date"]

    # ── Entry ──
    def _build_entry(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.fo_stack, _ = _build_subnav(lay, ["Record Deposit", "Log Repayment"])

        # ── Record Deposit ──
        p1 = QWidget()
        f1 = QFormLayout(p1)
        self.fo_dep_depositor = SearchableCombo(placeholder="Search depositor\u2026")
        self.fo_dep_amount = QDoubleSpinBox()
        self.fo_dep_amount.setRange(0, 999999999)
        self.fo_dep_amount.setPrefix("\u20b9 ")
        self.fo_dep_amount.setDecimals(2)
        self.fo_dep_interest_free = QPushButton("Interest-Free")
        self.fo_dep_interest_free.setCheckable(True)
        self.fo_dep_interest_free.setChecked(True)
        self.fo_dep_interest_free.setObjectName("pill")
        self.fo_dep_interest_free.toggled.connect(self._toggle_if)
        self.fo_dep_rate = QDoubleSpinBox()
        self.fo_dep_rate.setRange(0, 30)
        self.fo_dep_rate.setSuffix(" %")
        self.fo_dep_rate.setEnabled(False)
        self.fo_dep_account = _account_combo(self.repos["accounts"])
        self.fo_dep_method = _method_combo(self.repos["lookups"])
        self.fo_dep_date = QDateEdit(QDate.currentDate())
        self.fo_dep_date.setCalendarPopup(True)
        self.fo_dep_return_date = QDateEdit(QDate.currentDate().addMonths(6))
        self.fo_dep_return_date.setCalendarPopup(True)
        self.fo_dep_desc = QLineEdit()
        self.fo_dep_desc.setPlaceholderText("Optional note")
        take_btn = QPushButton("\U0001f9fe  Record Deposit")
        take_btn.setObjectName("primary")
        take_btn.clicked.connect(self._create_deposit)
        f1.addRow("Depositor *", _entity_row(self.fo_dep_depositor, self._add_depositor_dlg))
        f1.addRow("Amount *", self.fo_dep_amount)
        f1.addRow("", self.fo_dep_interest_free)
        f1.addRow("Interest Rate", self.fo_dep_rate)
        f1.addRow("Received Into *", self.fo_dep_account)
        f1.addRow("Method *", self.fo_dep_method)
        f1.addRow("Deposit Date", self.fo_dep_date)
        f1.addRow("Expected Return Date", self.fo_dep_return_date)
        f1.addRow("Description", self.fo_dep_desc)
        f1.addRow("", take_btn)
        self.fo_stack.addWidget(p1)

        # ── Log Repayment ──
        p2 = QWidget()
        f2 = QFormLayout(p2)
        self.fo_rep_deposit = SearchableCombo(placeholder="Search deposit\u2026")
        self.fo_rep_pending_lbl = QLabel("")
        self.fo_rep_pending_lbl.setStyleSheet(f"color:{C['amber']};font-weight:700;font-size:12px;")
        self.fo_rep_deposit.currentIndexChanged.connect(self._update_fo_pending)
        self.fo_rep_amount = QDoubleSpinBox()
        self.fo_rep_amount.setRange(0, 99999999)
        self.fo_rep_amount.setPrefix("\u20b9 ")
        self.fo_rep_amount.setDecimals(2)
        self.fo_rep_account = _account_combo(self.repos["accounts"])
        self.fo_rep_method = _method_combo(self.repos["lookups"])
        self.fo_rep_date = QDateEdit(QDate.currentDate())
        self.fo_rep_date.setCalendarPopup(True)
        self.fo_rep_desc = QLineEdit()
        self.fo_rep_desc.setPlaceholderText("Optional note")
        rep_btn = QPushButton("\U0001f4b8  Log Repayment")
        rep_btn.setObjectName("primary")
        rep_btn.clicked.connect(self._log_repayment)
        f2.addRow("Deposit *", self.fo_rep_deposit)
        f2.addRow("", self.fo_rep_pending_lbl)
        f2.addRow("Amount Returned *", self.fo_rep_amount)
        f2.addRow("Pay From *", self.fo_rep_account)
        f2.addRow("Method *", self.fo_rep_method)
        f2.addRow("Date", self.fo_rep_date)
        f2.addRow("Description", self.fo_rep_desc)
        f2.addRow("", rep_btn)
        self.fo_stack.addWidget(p2)
        return page

    def _toggle_if(self, checked):
        self.fo_dep_interest_free.setText("Interest-Free" if checked else "Interest-Bearing")
        self.fo_dep_rate.setEnabled(not checked)
        if checked:
            self.fo_dep_rate.setValue(0)

    def _add_depositor_dlg(self):
        name = _simple_add_dialog(self, "Add New Depositor")
        if not name:
            return
        self.repos["deposits"].create_depositor(name)
        self._refresh_entry_dropdowns()
        for i in range(self.fo_dep_depositor.count()):
            if self.fo_dep_depositor.itemText(i) == name:
                self.fo_dep_depositor.setCurrentIndex(i)
                break
        QMessageBox.information(self, "Added", f"'{name}' added as a depositor.")

    def _refresh_entry_dropdowns(self):
        self.fo_dep_depositor.clear_items()
        for d in self.repos["deposits"].list_depositors():
            self.fo_dep_depositor.add_item(d["name"], d["depositor_id"])
        self.fo_rep_deposit.clear_items()
        for d in self.repos["deposits"].list_deposits():
            if d["status"] != "CLOSED":
                self.fo_rep_deposit.add_item(
                    f"{d['depositor_name']} \u2014 {fmt_money(d['principal_amount'])} ({d['status']})",
                    d["deposit_id"]
                )
        self._update_fo_pending()

    def _update_fo_pending(self):
        did = self.fo_rep_deposit.get_data()
        if not did:
            self.fo_rep_pending_lbl.setText("")
            return
        dep = self.repos["deposits"].get_deposit(did)
        if not dep:
            return
        paid = self.repos["deposits"].total_repaid(did)
        pending = dep["principal_amount"] - paid
        self.fo_rep_pending_lbl.setText(f"Pending: {fmt_money(pending)} of {fmt_money(dep['principal_amount'])}")

    def _create_deposit(self):
        did = self.fo_dep_depositor.get_data()
        amount = self.fo_dep_amount.value()
        if not did or amount <= 0:
            QMessageBox.warning(self, "Missing Info", "Select a depositor and enter an amount.")
            return
        account_id = self.fo_dep_account.currentData()
        method = self.fo_dep_method.currentData()
        name = self.fo_dep_depositor.currentText()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="CREDIT", amount=amount, person_org=name,
            description=f"Deposit received from {name}", category_names=("Finance", "Other")
        )
        rate = None if self.fo_dep_interest_free.isChecked() else self.fo_dep_rate.value()
        self.repos["deposits"].create_deposit(
            depositor_id=did, principal_amount=amount, interest_rate=rate,
            deposit_date=self.fo_dep_date.date().toString("yyyy-MM-dd"),
            expected_return_date=self.fo_dep_return_date.date().toString("yyyy-MM-dd"),
            status="ACTIVE", description=self.fo_dep_desc.text().strip() or None,
            linked_txn_id=txn_id
        )
        self.fo_dep_amount.setValue(0)
        self.fo_dep_desc.clear()
        self._refresh_entry_dropdowns()
        self.load_list()
        QMessageBox.information(self, "Deposit Recorded", f"\u20b9{amount:,.2f} deposit from {name} recorded.")

    def _log_repayment(self):
        did = self.fo_rep_deposit.get_data()
        amount = self.fo_rep_amount.value()
        if not did or amount <= 0:
            QMessageBox.warning(self, "Missing Info", "Select a deposit and enter an amount.")
            return
        dep = self.repos["deposits"].get_deposit(did)
        account_id = self.fo_rep_account.currentData()
        method = self.fo_rep_method.currentData()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="DEBIT", amount=amount, person_org=dep["depositor_name"] if dep else None,
            description=f"Repayment to {dep['depositor_name']}" if dep else "Deposit repayment",
            category_names=("Finance", "Other")
        )
        self.repos["deposits"].add_repayment(
            deposit_id=did, amount_paid=amount,
            payment_date=self.fo_rep_date.date().toString("yyyy-MM-dd"),
            payment_method=method, description=self.fo_rep_desc.text().strip() or None,
            linked_txn_id=txn_id
        )
        self.fo_rep_amount.setValue(0)
        self.fo_rep_desc.clear()
        self._refresh_entry_dropdowns()
        self.load_list()
        QMessageBox.information(self, "Repayment Logged", "Repayment recorded successfully.")

    # ── List ──
    def load_list(self):
        self._list_data = self.repos["deposits"].list_deposits()
        self._render_list()

    def _render_list(self):
        if not hasattr(self, "_list_lay"):
            return
        _clear_layout(self._stats_row)
        _clear_layout(self._list_lay)
        deps = list(self._list_data)
        active = [d for d in deps if d["status"] != "CLOSED"]
        total_held = sum(
            max(d["principal_amount"] - self.repos["deposits"].total_repaid(d["deposit_id"]), 0)
            for d in active
        )
        _fill_stats_row(self._stats_row, [
            _metric_card("Total Held", fmt_money(total_held), C["accent"]),
            _metric_card("Active Deposits", str(len(active))),
            _metric_card("Total Deposits", str(len(deps))),
        ])
        search = self._search_input.text().strip().lower() if hasattr(self, "_search_input") else ""
        if search:
            deps = [d for d in deps if search in d["depositor_name"].lower()]
        mode = self._sort_cb.currentText() if hasattr(self, "_sort_cb") else ""
        if mode == "Status":
            deps.sort(key=lambda d: 0 if d["status"] != "CLOSED" else 1)
        elif mode == "Depositor":
            deps.sort(key=lambda d: d["depositor_name"].lower())
        elif mode == "Amount":
            deps.sort(key=lambda d: d["principal_amount"])
        elif mode == "Return Date":
            deps.sort(key=lambda d: d["expected_return_date"] or "zzz")
        if not getattr(self, "_sort_asc", True):
            deps.reverse()
        if not deps:
            empty = QLabel("No matching deposits." if search else "No deposits from others yet.")
            empty.setStyleSheet(f"color:{C['text3']};padding:20px;")
            empty.setAlignment(Qt.AlignCenter)
            self._list_lay.addWidget(empty)
            return
        for d in deps:
            paid = self.repos["deposits"].total_repaid(d["deposit_id"])
            pending = d["principal_amount"] - paid
            interest_free = not d["interest_rate"]
            color = C["text3"] if d["status"] == "CLOSED" else C["accent"]
            badge_text = "Interest-Free" if interest_free else f"{d['interest_rate']}%"
            badge_col = C["text3"] if interest_free and d["status"] != "CLOSED" else color
            card = _wealth_card(
                title=d["depositor_name"],
                subtitle=f"Deposited {d['deposit_date']} {MDOT} Return {d['expected_return_date'] or EM_DASH}",
                amount_text=fmt_money(pending) + " held", badge_text=badge_text,
                badge_color=badge_col,
                extra_line=f"Principal: {fmt_money(d['principal_amount'])} {MDOT} Returned: {fmt_money(paid)} {MDOT} {d['status']}",
                on_click=lambda did=d["deposit_id"]: self._open_detail(did)
            )
            self._list_lay.addWidget(card)

    def _open_detail(self, deposit_id):
        dep = self.repos["deposits"].get_deposit(deposit_id)
        if not dep:
            return
        repayments = self.repos["deposits"].get_repayments(deposit_id)
        dlg = LoanDetailDialog(
            role="take", title=f"Deposit from {dep['depositor_name']}",
            principal=dep["principal_amount"], status=dep["status"],
            start_date=dep["deposit_date"], due_date=dep["expected_return_date"],
            description=dep.get("description"), repayments=repayments,
            amount_key="amount_paid", date_key="payment_date",
            on_mark_closed=lambda: self._mark_closed(deposit_id), parent=self
        )
        dlg.exec_()

    def _mark_closed(self, deposit_id):
        if _confirm(self, "Mark Closed", "Mark this deposit as fully returned/closed?"):
            self.repos["deposits"].update_status(deposit_id, "CLOSED")
            self.load_list()
            return True
        return False


# ══════════════════════════════════════════════════════════════════════════
#  MUTUAL FUNDS
# ══════════════════════════════════════════════════════════════════════════
class MFPage(_FunctionPage):
    ICON = "\U0001f4c8"
    TITLE = "Mutual Funds"

    def __init__(self, repos, services, parent=None):
        self._nav_cache = {}
        super().__init__(repos, services, parent)

    def _sort_options(self):
        return ["Return %", "Scheme Name", "Invested", "Current Value"]

    # ── Entry ──
    def _build_entry(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.mf_stack, _ = _build_subnav(lay, ["Purchase / SIP", "Redemption"])

        # ── Purchase / SIP ──
        p1 = QWidget()
        f1 = QFormLayout(p1)
        self.mf_buy_scheme = SearchableCombo(placeholder="Search scheme\u2026")
        self.mf_buy_type = QComboBox()
        self.mf_buy_type.addItems(["PURCHASE", "SIP"])
        self.mf_buy_date = QDateEdit(QDate.currentDate())
        self.mf_buy_date.setCalendarPopup(True)
        self.mf_buy_amount = QDoubleSpinBox()
        self.mf_buy_amount.setRange(0, 99999999)
        self.mf_buy_amount.setPrefix("\u20b9 ")
        self.mf_buy_amount.setDecimals(2)
        nav_row = QHBoxLayout()
        self.mf_buy_nav = QDoubleSpinBox()
        self.mf_buy_nav.setRange(0, 999999)
        self.mf_buy_nav.setDecimals(4)
        fetch_btn = QPushButton("\U0001f50e Fetch NAV")
        fetch_btn.clicked.connect(self._fetch_nav_buy)
        nav_row.addWidget(self.mf_buy_nav, 1)
        nav_row.addWidget(fetch_btn)
        self.mf_buy_units = QLabel("Units: \u2014")
        self.mf_buy_units.setStyleSheet(f"color:{C['accent']};font-weight:700;font-size:12px;")
        for w in (self.mf_buy_amount, self.mf_buy_nav):
            w.valueChanged.connect(self._update_units)
        self.mf_buy_account = _account_combo(self.repos["accounts"])
        self.mf_buy_method = _method_combo(self.repos["lookups"])
        buy_btn = QPushButton("\U0001f4c8  Log Purchase")
        buy_btn.setObjectName("primary")
        buy_btn.clicked.connect(self._log_purchase)
        f1.addRow("Scheme *", _entity_row(self.mf_buy_scheme, self._add_scheme_dlg))
        f1.addRow("Type", self.mf_buy_type)
        f1.addRow("Date", self.mf_buy_date)
        f1.addRow("Amount *", self.mf_buy_amount)
        f1.addRow("NAV *", nav_row)
        f1.addRow("", self.mf_buy_units)
        f1.addRow("Pay From *", self.mf_buy_account)
        f1.addRow("Method *", self.mf_buy_method)
        f1.addRow("", buy_btn)
        self.mf_stack.addWidget(p1)

        # ── Redemption ──
        p2 = QWidget()
        f2 = QFormLayout(p2)
        self.mf_sell_scheme = SearchableCombo(placeholder="Search scheme\u2026")
        self.mf_sell_scheme.currentIndexChanged.connect(self._update_holdings)
        self.mf_holdings_lbl = QLabel("")
        self.mf_holdings_lbl.setStyleSheet(f"color:{C['amber']};font-weight:700;font-size:12px;")
        self.mf_sell_date = QDateEdit(QDate.currentDate())
        self.mf_sell_date.setCalendarPopup(True)
        self.mf_sell_units = QDoubleSpinBox()
        self.mf_sell_units.setRange(0, 9999999)
        self.mf_sell_units.setDecimals(4)
        sell_nav_row = QHBoxLayout()
        self.mf_sell_nav = QDoubleSpinBox()
        self.mf_sell_nav.setRange(0, 999999)
        self.mf_sell_nav.setDecimals(4)
        sell_fetch = QPushButton("\U0001f50e Fetch NAV")
        sell_fetch.clicked.connect(self._fetch_nav_sell)
        sell_nav_row.addWidget(self.mf_sell_nav, 1)
        sell_nav_row.addWidget(sell_fetch)
        self.mf_sell_preview = QLabel("Redemption Amount: \u2014")
        self.mf_sell_preview.setStyleSheet(f"color:{C['green']};font-weight:700;font-size:12px;")
        for w in (self.mf_sell_units, self.mf_sell_nav):
            w.valueChanged.connect(self._update_redemption)
        self.mf_sell_account = _account_combo(self.repos["accounts"])
        self.mf_sell_method = _method_combo(self.repos["lookups"])
        sell_btn = QPushButton("\U0001f4b5  Log Redemption")
        sell_btn.setObjectName("primary")
        sell_btn.clicked.connect(self._log_redemption)
        f2.addRow("Scheme *", self.mf_sell_scheme)
        f2.addRow("", self.mf_holdings_lbl)
        f2.addRow("Date", self.mf_sell_date)
        f2.addRow("Units to Redeem *", self.mf_sell_units)
        f2.addRow("NAV *", sell_nav_row)
        f2.addRow("", self.mf_sell_preview)
        f2.addRow("Credit Into *", self.mf_sell_account)
        f2.addRow("Method *", self.mf_sell_method)
        f2.addRow("", sell_btn)
        self.mf_stack.addWidget(p2)
        return page

    def _add_scheme_dlg(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Add New Scheme")
        dlg.setMinimumWidth(420)
        f = QFormLayout(dlg)
        amc = QLineEdit()
        amc.setPlaceholderText("e.g. Parag Parikh")
        name = QLineEdit()
        name.setPlaceholderText("e.g. Flexi Cap Fund - Direct Growth")
        stype = QComboBox()
        stype.addItems(["Equity", "Debt", "Hybrid", "Index", "ELSS", "Liquid", "Other"])
        folio = QLineEdit()
        folio.setPlaceholderText("Optional")
        f.addRow("AMC *", amc)
        f.addRow("Scheme Name *", name)
        f.addRow("Type", stype)
        f.addRow("Folio Number", folio)
        btn_row = QHBoxLayout()
        ok = QPushButton("Add")
        ok.setObjectName("primary")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        f.addRow("", btn_row)
        if dlg.exec_() != QDialog.Accepted:
            return
        a, n = amc.text().strip(), name.text().strip()
        if not a or not n:
            QMessageBox.warning(self, "Missing Info", "AMC and Scheme Name are required.")
            return
        self.repos["mf"].create_scheme(
            amc_name=a, scheme_name=n, scheme_type=stype.currentText(),
            folio_number=folio.text().strip() or None, is_active=1
        )
        self._refresh_entry_dropdowns()
        label = f"{a} \u2014 {n}"
        for i in range(self.mf_buy_scheme.count()):
            if self.mf_buy_scheme.itemText(i) == label:
                self.mf_buy_scheme.setCurrentIndex(i)
                break
        QMessageBox.information(self, "Scheme Added", f"'{n}' added to your mutual fund schemes.")

    def _update_units(self):
        amt = self.mf_buy_amount.value()
        nav = self.mf_buy_nav.value()
        units = MFService.calculate_units(amt, nav)
        self.mf_buy_units.setText(f"Units: {units:,.4f}" if units else "Units: \u2014")

    def _update_redemption(self):
        units = self.mf_sell_units.value()
        nav = self.mf_sell_nav.value()
        self.mf_sell_preview.setText(f"Redemption Amount: {fmt_money(units * nav)}" if nav else "Redemption Amount: \u2014")

    def _update_holdings(self):
        sid = self.mf_sell_scheme.get_data()
        if not sid:
            self.mf_holdings_lbl.setText("")
            return
        h = self.repos["mf"].holdings(sid)
        self.mf_holdings_lbl.setText(f"You hold {h['units']:,.4f} units in this scheme.")
        self.mf_sell_units.setMaximum(max(h["units"], 0))

    def _fetch_nav_buy(self):
        dlg = NavFetchDialog(initial_query=self.mf_buy_scheme.currentText(), parent=self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_nav:
            self.mf_buy_nav.setValue(dlg.result_nav)

    def _fetch_nav_sell(self):
        dlg = NavFetchDialog(initial_query=self.mf_sell_scheme.currentText(), parent=self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_nav:
            self.mf_sell_nav.setValue(dlg.result_nav)

    def _refresh_entry_dropdowns(self):
        self.mf_buy_scheme.clear_items()
        self.mf_sell_scheme.clear_items()
        for s in self.repos["mf"].list_schemes():
            label = f"{s['amc_name']} \u2014 {s['scheme_name']}"
            self.mf_buy_scheme.add_item(label, s["scheme_id"])
            self.mf_sell_scheme.add_item(label, s["scheme_id"])
        self._update_holdings()

    def _log_purchase(self):
        sid = self.mf_buy_scheme.get_data()
        amount = self.mf_buy_amount.value()
        nav = self.mf_buy_nav.value()
        if not sid or amount <= 0 or nav <= 0:
            QMessageBox.warning(self, "Missing Info", "Select a scheme and enter amount and NAV.")
            return
        units = MFService.calculate_units(amount, nav)
        account_id = self.mf_buy_account.currentData()
        method = self.mf_buy_method.currentData()
        scheme_label = self.mf_buy_scheme.currentText()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="DEBIT", amount=amount, person_org=None,
            description=f"MF {self.mf_buy_type.currentText().title()} \u2014 {scheme_label}",
            category_names=("Investment", "Finance")
        )
        self.repos["mf"].add_txn(
            scheme_id=sid, txn_type=self.mf_buy_type.currentText(),
            txn_date=self.mf_buy_date.date().toString("yyyy-MM-dd"),
            amount=amount, nav=nav, units=units, linked_txn_id=txn_id
        )
        self._nav_cache[sid] = nav
        self.mf_buy_amount.setValue(0)
        self._refresh_entry_dropdowns()
        self.load_list()
        QMessageBox.information(self, "Purchase Logged", f"{units:,.4f} units purchased.")

    def _log_redemption(self):
        sid = self.mf_sell_scheme.get_data()
        units = self.mf_sell_units.value()
        nav = self.mf_sell_nav.value()
        if not sid or units <= 0 or nav <= 0:
            QMessageBox.warning(self, "Missing Info", "Select a scheme and enter units and NAV.")
            return
        held = self.repos["mf"].holdings(sid)["units"]
        if units > held + 1e-6:
            QMessageBox.warning(self, "Not Enough Units", f"You only hold {held:,.4f} units.")
            return
        amount = round(units * nav, 2)
        account_id = self.mf_sell_account.currentData()
        method = self.mf_sell_method.currentData()
        scheme_label = self.mf_sell_scheme.currentText()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method,
            tx_type="CREDIT", amount=amount, person_org=None,
            description=f"MF Redemption \u2014 {scheme_label}",
            category_names=("Investment", "Finance")
        )
        self.repos["mf"].add_txn(
            scheme_id=sid, txn_type="REDEMPTION",
            txn_date=self.mf_sell_date.date().toString("yyyy-MM-dd"),
            amount=amount, nav=nav, units=units, linked_txn_id=txn_id
        )
        self._nav_cache[sid] = nav
        self.mf_sell_units.setValue(0)
        self._refresh_entry_dropdowns()
        self.load_list()
        QMessageBox.information(self, "Redemption Logged", f"{units:,.4f} units redeemed for {fmt_money(amount)}.")

    def _last_nav(self, scheme_id):
        if scheme_id in self._nav_cache:
            return self._nav_cache[scheme_id]
        txns = self.repos["mf"].list_txns(scheme_id)
        return txns[-1]["nav"] if txns else 0

    # ── List ──
    def load_list(self):
        schemes = self.repos["mf"].list_schemes()
        self._list_data = []
        for s in schemes:
            h = self.repos["mf"].holdings(s["scheme_id"])
            nav = self._last_nav(s["scheme_id"])
            net_inv = h["invested"] - h["redeemed"]
            cur_val = h["units"] * nav
            ret = MFService.simple_return(net_inv, cur_val)
            self._list_data.append({
                **s, "holdings": h, "nav": nav, "net_invested": net_inv,
                "current_value": cur_val, "return_pct": ret,
            })
        self._render_list()

    def _render_list(self):
        if not hasattr(self, "_list_lay"):
            return
        _clear_layout(self._stats_row)
        _clear_layout(self._list_lay)
        items = list(self._list_data)
        # portfolio stats from full data
        total_inv = sum(i["net_invested"] for i in items)
        total_cur = sum(i["current_value"] for i in items)
        overall_ret = MFService.simple_return(total_inv, total_cur)
        _fill_stats_row(self._stats_row, [
            _metric_card("Invested", fmt_money(total_inv)),
            _metric_card("Current Value", fmt_money(total_cur), C["accent"]),
            _metric_card("Overall Return", f"{overall_ret:+.2f}%",
                          C["green"] if overall_ret >= 0 else C["red"]),
        ])
        # search
        search = self._search_input.text().strip().lower() if hasattr(self, "_search_input") else ""
        if search:
            items = [i for i in items
                     if search in (i["amc_name"] + " " + i["scheme_name"]).lower()]
        # sort
        mode = self._sort_cb.currentText() if hasattr(self, "_sort_cb") else ""
        if mode == "Return %":
            items.sort(key=lambda i: i["return_pct"])
        elif mode == "Scheme Name":
            items.sort(key=lambda i: (i["amc_name"] + i["scheme_name"]).lower())
        elif mode == "Invested":
            items.sort(key=lambda i: i["net_invested"])
        elif mode == "Current Value":
            items.sort(key=lambda i: i["current_value"])
        if not getattr(self, "_sort_asc", True):
            items.reverse()
        # render
        if not items:
            empty = QLabel("No matching schemes." if search else "No mutual fund schemes yet.")
            empty.setStyleSheet(f"color:{C['text3']};padding:20px;")
            empty.setAlignment(Qt.AlignCenter)
            self._list_lay.addWidget(empty)
            return
        for it in items:
            ret = it["return_pct"]
            color = C["green"] if ret >= 0 else C["red"]
            card = _wealth_card(
                title=f"{it['amc_name']} \u2014 {it['scheme_name']}",
                subtitle=f"{it['scheme_type'] or ''} {MDOT} {it['holdings']['units']:,.4f} units {MDOT} NAV {it['nav']:,.4f}",
                amount_text=fmt_money(it["current_value"]),
                badge_text=f"{ret:+.2f}%", badge_color=color,
                extra_line=f"Invested: {fmt_money(it['net_invested'])}",
                on_click=lambda sid=it["scheme_id"]: self._open_detail(sid)
            )
            self._list_lay.addWidget(card)

    def _open_detail(self, scheme_id):
        scheme = self.repos["mf"].get_scheme(scheme_id)
        if not scheme:
            return
        txns = self.repos["mf"].list_txns(scheme_id)
        h = self.repos["mf"].holdings(scheme_id)
        nav = self._last_nav(scheme_id)
        dlg = MFDetailDialog(scheme, txns, h, nav, parent=self)
        dlg.exec_()


# ══════════════════════════════════════════════════════════════════════════
#  MF DETAIL DIALOG
# ══════════════════════════════════════════════════════════════════════════
class MFDetailDialog(QDialog):
    def __init__(self, scheme, txns, holdings, nav, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{scheme['amc_name']} \u2014 {scheme['scheme_name']}")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        net_inv = holdings["invested"] - holdings["redeemed"]
        cur_val = holdings["units"] * nav
        ret = MFService.simple_return(net_inv, cur_val)
        color = C["green"] if ret >= 0 else C["red"]
        hdr = QHBoxLayout()
        t = QLabel(f"{scheme['amc_name']} \u2014 {scheme['scheme_name']}")
        t.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        t.setWordWrap(True)
        hdr.addWidget(t, 1)
        hdr.addWidget(_badge(f"{ret:+.2f}%", color))
        lay.addLayout(hdr)
        info = QLabel(
            f"Folio: {scheme.get('folio_number') or EM_DASH}  {MDOT}  Type: {scheme.get('scheme_type') or EM_DASH}\n"
            f"Units Held: {holdings['units']:,.4f}  {MDOT}  Latest NAV: {nav:,.4f}\n"
            f"Invested: {fmt_money(net_inv)}  {MDOT}  Current Value: {fmt_money(cur_val)}"
        )
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
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok = QPushButton("Close")
        ok.clicked.connect(self.accept)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)


# ══════════════════════════════════════════════════════════════════════════
#  WEALTH TAB — 5 top-level pages (no grouping)
# ══════════════════════════════════════════════════════════════════════════
class WealthTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self.repos = repos
        self.services = services
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(14)
        heading = QLabel("\U0001f4c8  Wealth")
        heading.setStyleSheet(f"font-size:22px;font-weight:800;color:{C['text']};")
        outer.addWidget(heading)
        # 5 top-level nav buttons
        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)
        self.btn_lg = QPushButton("\U0001f91d Loans I Give")
        self.btn_lt = QPushButton("\U0001f3db\ufe0f Loans I Take")
        self.btn_fd = QPushButton("\U0001f3e6 FD I Deposit")
        self.btn_fo = QPushButton("\U0001f9fe FD Others")
        self.btn_mf = QPushButton("\U0001f4c8 Mutual Funds")
        self._nav_btns = [self.btn_lg, self.btn_lt, self.btn_fd, self.btn_fo, self.btn_mf]
        for b in self._nav_btns:
            b.setMinimumHeight(34)
            b.setCursor(QCursor(Qt.PointingHandCursor))
            nav_row.addWidget(b)
        nav_row.addStretch()
        outer.addLayout(nav_row)
        # page stack
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.loans_give_page = LoansGivePage(self.repos, self.services)
        self.loans_take_page = LoansTakePage(self.repos, self.services)
        self.fd_give_page = FDGivePage(self.repos, self.services)
        self.fd_others_page = FDOthersPage(self.repos, self.services)
        self.mf_page = MFPage(self.repos, self.services)
        self._pages = [
            self.loans_give_page, self.loans_take_page,
            self.fd_give_page, self.fd_others_page, self.mf_page,
        ]
        for p in self._pages:
            self.stack.addWidget(p)
        self.btn_lg.clicked.connect(lambda: self._goto(0))
        self.btn_lt.clicked.connect(lambda: self._goto(1))
        self.btn_fd.clicked.connect(lambda: self._goto(2))
        self.btn_fo.clicked.connect(lambda: self._goto(3))
        self.btn_mf.clicked.connect(lambda: self._goto(4))
        _switch_tabs(self._nav_btns, 0)
        self.stack.setCurrentIndex(0)

    def _goto(self, i):
        _switch_tabs(self._nav_btns, i)
        self.stack.setCurrentIndex(i)
        self._pages[i].load_list()

    def refresh(self):
        for p in self._pages:
            p.refresh()
