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


class _FetchNavsWorker(QThread):
    """Background worker to fetch latest NAVs for all linked schemes."""
    finished = _Signal(dict)  # {scheme_id: nav_value}

    def __init__(self, scheme_codes, parent=None):
        """scheme_codes: list of (scheme_id, api_scheme_code)"""
        super().__init__(parent)
        self._items = scheme_codes

    def run(self):
        import urllib.request
        result = {}
        for sid, code in self._items:
            try:
                url = f"https://api.mfapi.in/mf/{code}/latest"
                with urllib.request.urlopen(url, timeout=3) as resp:
                    data = _json.loads(resp.read().decode())
                rows = data.get("data") or [] if isinstance(data, dict) else []
                if rows:
                    result[sid] = float(rows[0]["nav"])
            except Exception:
                pass
        self.finished.emit(result)


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
    a.setStyleSheet(f"font-size:18px;font-weight:900;color:{C['text']};")
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
        e.setTextFormat(Qt.RichText)
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


# ── Card-rendering helpers (replace tables in detail dialogs) ─────────
_CARD_SS = (f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};"
            f"border-radius:8px;}}QLabel{{background:transparent;border:none;}}")


def _card_scroll(card_widgets, empty_msg="No data yet."):
    """Wrap a list of QFrame cards in a scroll area."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    inner = QWidget()
    lay = QVBoxLayout(inner)
    lay.setSpacing(6)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setAlignment(Qt.AlignTop)
    if not card_widgets:
        lbl = QLabel(empty_msg)
        lbl.setStyleSheet(f"color:{C['text3']};padding:16px;font-size:12px;")
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl)
    else:
        for w in card_widgets:
            lay.addWidget(w)
    scroll.setWidget(inner)
    return scroll


def _kv_pairs(pairs):
    """HBox of label:value mini-columns."""
    row = QHBoxLayout()
    row.setSpacing(20)
    for label, value in pairs:
        col = QVBoxLayout()
        col.setSpacing(1)
        l = QLabel(str(label))
        l.setStyleSheet(f"font-size:10px;color:{C['text3']};font-weight:600;text-transform:uppercase;letter-spacing:0.3px;")
        v = QLabel(str(value))
        v.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};")
        col.addWidget(l)
        col.addWidget(v)
        row.addLayout(col)
    row.addStretch()
    return row


def _repayment_cards(repayments, amount_key, date_key, empty_msg="No repayments logged yet."):
    """Render repayment list as cards."""
    cards = []
    for r in repayments:
        card = QFrame()
        card.setStyleSheet(_CARD_SS)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 8, 12, 8)
        cl.setSpacing(4)
        hdr = QHBoxLayout()
        d = QLabel(r.get(date_key, ""))
        d.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};")
        a = QLabel(fmt_money(r[amount_key]))
        a.setStyleSheet(f"font-size:14px;font-weight:800;color:{C['accent']};")
        a.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        hdr.addWidget(d)
        hdr.addStretch()
        hdr.addWidget(a)
        cl.addLayout(hdr)
        desc = r.get("description") or ""
        if desc:
            dl = QLabel(desc)
            dl.setStyleSheet(f"font-size:11px;color:{C['text3']};font-style:italic;")
            dl.setWordWrap(True)
            cl.addWidget(dl)
        cards.append(card)
    return _card_scroll(cards, empty_msg)


def _amort_cards(schedule):
    """Render amortization schedule as cards."""
    cards = []
    for row in schedule:
        card = QFrame()
        card.setStyleSheet(_CARD_SS)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 8, 12, 8)
        cl.setSpacing(4)
        hdr = QLabel(f"Month {row['month']}")
        hdr.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};")
        cl.addWidget(hdr)
        cl.addLayout(_kv_pairs([
            ("EMI", fmt_money(row["emi"])),
            ("Principal", fmt_money(row["principal"])),
            ("Interest", fmt_money(row["interest"])),
            ("Balance", fmt_money(row["balance"])),
        ]))
        cards.append(card)
    return _card_scroll(cards)


def _amort_actuals_cards(rows):
    """Render amortization + actual payments as cards."""
    cards = []
    for rw in rows:
        card = QFrame()
        card.setStyleSheet(_CARD_SS)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 8, 12, 8)
        cl.setSpacing(4)
        hdr = QHBoxLayout()
        title = QLabel(f"Month {rw['month']} {MDOT} {rw['date']}")
        title.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};")
        hdr.addWidget(title)
        hdr.addStretch()
        sc = {"Paid": C["green"], "Extra Paid": C["accent"], "Partially Paid": C["amber"],
              "Missed": C["red"], "Upcoming": C["text3"]}
        hdr.addWidget(_badge(rw["status"], sc.get(rw["status"], C["text3"])))
        cl.addLayout(hdr)
        cl.addLayout(_kv_pairs([
            ("Planned EMI", fmt_money(rw["p_emi"])),
            ("Actual Paid", fmt_money(rw["a_paid"])),
        ]))
        cl.addLayout(_kv_pairs([
            ("Planned Bal", fmt_money(rw["p_bal"])),
            ("Actual Bal", fmt_money(rw["a_bal"])),
        ]))
        cards.append(card)
    return _card_scroll(cards)


def _mf_txn_cards(txns):
    """Render MF transaction list as cards."""
    cards = []
    for tx in txns:
        card = QFrame()
        card.setStyleSheet(_CARD_SS)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 8, 12, 8)
        cl.setSpacing(4)
        hdr = QHBoxLayout()
        title = QLabel(f"{tx['txn_type']} {MDOT} {tx['txn_date']}")
        title.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};")
        hdr.addWidget(title)
        hdr.addStretch()
        amt = QLabel(fmt_money(tx["amount"]))
        amt.setStyleSheet(f"font-size:14px;font-weight:800;color:{C['accent']};")
        hdr.addWidget(amt)
        cl.addLayout(hdr)
        cl.addLayout(_kv_pairs([
            ("NAV", f"{tx['nav']:,.4f}"),
            ("Units", f"{tx['units']:,.4f}"),
        ]))
        cards.append(card)
    return _card_scroll(cards)


def _export_detail_to_pdf(parent, title, status, info_pairs, analysis_pairs, sections=None):
    """Show save dialog and generate a detail PDF."""
    from PyQt5.QtWidgets import QFileDialog
    safe = "".join(c for c in title if c.isalnum() or c in " -_")[:60]
    filepath, _ = QFileDialog.getSaveFileName(
        parent, "Save PDF", f"{safe}.pdf", "PDF Files (*.pdf)")
    if not filepath:
        return
    from services.report_service import export_detail_pdf
    doc_id = export_detail_pdf(filepath, title, status, info_pairs, analysis_pairs, sections)
    if doc_id:
        box = QMessageBox(parent)
        box.setWindowTitle("PDF Saved")
        box.setText(f"Document ID: {doc_id}\nSaved to: {filepath}")
        box.setInformativeText("Would you like to open the PDF?")
        open_btn = box.addButton("Open PDF", QMessageBox.AcceptRole)
        box.addButton("Close", QMessageBox.RejectRole)
        box.exec_()
        if box.clickedButton() == open_btn:
            import os, sys
            if sys.platform == "win32":
                os.startfile(filepath)
            elif sys.platform == "darwin":
                os.system(f"open '{filepath}'")
            else:
                os.system(f"xdg-open '{filepath}'")
    else:
        QMessageBox.warning(parent, "Error",
            "Failed to generate PDF. Make sure reportlab is installed:\npip install reportlab")


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

    def _build_list(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self._stats_row = QHBoxLayout()
        lay.addLayout(self._stats_row)
        fr = QHBoxLayout()
        fr.setSpacing(8)
        sort_lbl = QLabel("Sort by:")
        sort_lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;font-weight:600;")
        self._sort_cb = QComboBox()
        self._sort_cb.addItems(self._sort_options())
        self._sort_cb.currentIndexChanged.connect(self._on_sort_changed)
        self._sort_asc = True
        self._sort_order_btn = QPushButton("\u25b2")
        self._sort_order_btn.setFixedSize(38, 38)
        self._sort_order_btn.setFocusPolicy(Qt.NoFocus)
        self._sort_order_btn.setCursor(QCursor(Qt.PointingHandCursor))
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
        # Print button
        print_btn = QPushButton("\U0001f5a8 Print Pending")
        print_btn.setFocusPolicy(Qt.NoFocus)
        print_btn.setCursor(QCursor(Qt.PointingHandCursor))
        print_btn.clicked.connect(self._print_pending)
        print_btn.setFixedHeight(36)
        fr.addWidget(sort_lbl)
        fr.addWidget(self._sort_cb)
        fr.addWidget(self._sort_order_btn)
        fr.addSpacing(12)
        fr.addWidget(self._search_input, 1)
        fr.addWidget(print_btn)
        lay.addLayout(fr)
        scroll, self._list_lay = self._scroll_area()
        lay.addWidget(scroll, 1)
        return page

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
        self.lg_loan_rate = QDoubleSpinBox()
        self.lg_loan_rate.setRange(0, 60)
        self.lg_loan_rate.setSuffix(" %")
        self.lg_loan_rate.setDecimals(2)
        self.lg_loan_method_type = QComboBox()
        self.lg_loan_method_type.addItems(["Simple Interest", "Compound Interest"])
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
        give_btn.setAutoDefault(True)
        give_btn.clicked.connect(self._give_loan)
        f1.addRow("Borrower *", _entity_row(self.lg_loan_borrower, self._add_borrower_dlg))
        f1.addRow("Loan Amount *", self.lg_loan_amount)
        f1.addRow("Interest Rate", self.lg_loan_rate)
        f1.addRow("Interest Method", self.lg_loan_method_type)
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
        rep_btn.setAutoDefault(True)
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
        a = self._analysis(loan)
        self.lg_rep_pending_lbl.setText(
            f"Outstanding: {fmt_money(a['current_value'])}  {MDOT}  "
            f"Principal: {fmt_money(loan['loan_amount'])}  {MDOT}  "
            f"Paid: {fmt_money(a['total_paid'])}"
        )

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
        rate = self.lg_loan_rate.value()
        imethod = "COMPOUND" if self.lg_loan_method_type.currentIndex() == 1 else "SIMPLE"
        self.repos["loans"].create_loan(
            borrower_id=bid, loan_amount=amount, payment_method=method,
            interest_rate=rate, interest_method=imethod,
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
        if not loan:
            return
        a = self._analysis(loan)
        if amount > a["current_value"] + 0.01:
            QMessageBox.warning(self, "Amount Exceeds Outstanding",
                f"Entered: {fmt_money(amount)}\n"
                f"Outstanding: {fmt_money(a['current_value'])}\n"
                f"Please enter a valid amount.")
            return
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

    # ── analysis helper ──
    def _loan_months(self, loan):
        sd = date.fromisoformat(loan["start_date"])
        dd = loan.get("due_date")
        if dd:
            return max(1, round((date.fromisoformat(dd) - sd).days / 30.44))
        return 12

    def _analysis(self, loan):
        total_paid = self.repos["loans"].total_repaid(loan["loan_id"])
        months = self._loan_months(loan)
        method = loan.get("interest_method") or "SIMPLE"
        rate = loan.get("interest_rate") or 0
        return LoanService.loan_analysis(
            loan["loan_amount"], rate, months, "ANNUAL", total_paid, loan["start_date"], method=method
        )

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
        rank = {"OVERDUE": 0, "ACTIVE": 1, "PARTIALLY_PAID": 2, "REPAID": 3, "CLOSED": 4}
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
            a = self._analysis(l)
            pct = (a["total_paid"] / a["total_expected"] * 100) if a["total_expected"] else 0
            color = status_color("loan", l["status"])
            mth = l.get("interest_method") or "SIMPLE"
            mth_tag = "SI" if mth == "SIMPLE" else "CI"
            rate_tag = f"{l.get('interest_rate') or 0}% {mth_tag}" if (l.get("interest_rate") or 0) > 0 else "Interest-Free"
            extra = (f"<span style='font-size:15px;font-weight:800;color:{C['text']};'>"
                     f"{fmt_money(a['current_value'])}</span>  "
                     f"<span style='font-size:11px;color:{C['text3']};'>Outstanding</span><br>"
                     f"<span style='font-size:11px;color:{C['text3']};'>"
                     f"Interest: {fmt_money(a['total_interest_accrued'])}  {MDOT}  "
                     f"Paid: {fmt_money(a['total_paid'])}</span>")
            card = _wealth_card(
                title=l["borrower_name"],
                subtitle=f"Given {l['start_date']} {MDOT} Due {l['due_date'] or EM_DASH} {MDOT} {rate_tag}",
                amount_text=fmt_money(l["loan_amount"]) + "  Principal",
                badge_text=l["status"], badge_color=color,
                progress_pct=pct, extra_line=extra,
                on_click=lambda lid=l["loan_id"]: self._open_detail(lid)
            )
            self._list_lay.addWidget(card)

    def _print_pending(self):
        """Print all non-closed pendings for a selected borrower."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Print Pendings")
        dlg.setMinimumWidth(400)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Select person to print non-closed pendings:"))
        combo = SearchableCombo(placeholder="Search person...")
        for b in self.repos["loans"].list_borrowers():
            combo.add_item(b["name"], b["borrower_id"])
        lay.addWidget(combo)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("\U0001f5a8  Print")
        ok_btn.setObjectName("primary")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)
        if dlg.exec_() != QDialog.Accepted:
            return
        bid = combo.get_data()
        if not bid:
            return
        borrower_name = combo.currentText()
        # get all non-closed loans for this borrower
        all_loans = self.repos["loans"].list_loans()
        borrower_loans = [l for l in all_loans
                          if l["borrower_id"] == bid and l["status"] not in ("CLOSED", "CLEARED")]
        if not borrower_loans:
            QMessageBox.information(self, "No Pendings", f"No pending items for {borrower_name}.")
            return
        info = [("Person", borrower_name), ("Date", TODAY()), ("Count", str(len(borrower_loans)))]
        sections = []
        for l in borrower_loans:
            a = self._analysis(l)
            rdata = [{"date": l["start_date"], "amount": a["current_value"],
                      "description": f"Due: {l['due_date'] or EM_DASH} | {l['status']}"}]
            sections.append({
                "title": f"{fmt_money(a['current_value'])} outstanding",
                "color": "#4F46E5", "type": "repayment", "data": rdata,
            })
        total = sum(self._analysis(l)["current_value"] for l in borrower_loans)
        analysis = [("Total Outstanding", fmt_money(total)), ("Items", str(len(borrower_loans)))]
        _export_detail_to_pdf(self, f"Pendings from {borrower_name}", "ACTIVE",
                              info, analysis, sections)

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
        """Run analysis for a given loan dict — handles EMI and Non-EMI."""
        total_paid = self.repos["borrowed"].total_repaid(loan["loan_id"])
        emi_type = loan.get("emi_type") or "EMI"
        if emi_type == "NON_EMI":
            method = loan.get("interest_method") or "SIMPLE"
            payments = self.repos["borrowed"].get_repayments(loan["loan_id"])
            return LoanService.non_emi_analysis(
                loan["principal_amount"], loan["interest_rate"] or 0,
                total_paid, loan["start_date"], payments=payments, method=method
            )
        months = self._loan_months(loan)
        freq = loan.get("interest_type") or "ANNUAL"
        method = loan.get("interest_method") or "COMPOUND"
        return LoanService.loan_analysis(
            loan["principal_amount"], loan["interest_rate"] or 0,
            months, freq, total_paid, loan["start_date"], method=method
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
        self.lt_emi_type = QComboBox()
        self.lt_emi_type.addItems(["EMI Loan (fixed monthly)", "Non-EMI Loan (variable)"])
        self.lt_emi_type.currentIndexChanged.connect(self._toggle_emi_type)
        self.lt_loan_freq = QComboBox()
        self.lt_loan_freq.addItems(self._FREQ_LABELS)
        self.lt_loan_method_type = QComboBox()
        self.lt_loan_method_type.addItems(["Simple Interest", "Compound Interest"])
        self.lt_loan_method_type.currentIndexChanged.connect(self._toggle_freq_visible)
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
        take_btn.setAutoDefault(True)
        take_btn.clicked.connect(self._take_loan)
        f1.addRow("Lender *", _entity_row(self.lt_loan_lender, self._add_lender_dlg))
        f1.addRow("Repayment Type", self.lt_emi_type)
        f1.addRow("Interest Method", self.lt_loan_method_type)
        f1.addRow("Compounding", self.lt_loan_freq)
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
        pay_btn.setAutoDefault(True)
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

    def _toggle_freq_visible(self):
        """Enable/disable compounding based on interest method."""
        is_compound = self.lt_loan_method_type.currentIndex() == 1
        self.lt_loan_freq.setEnabled(is_compound)
        self._update_emi()

    def _toggle_emi_type(self):
        """Show/hide EMI-specific fields based on repayment type."""
        is_emi = self.lt_emi_type.currentIndex() == 0
        # Keep tenure visible for both (needed for overdue detection + due date)
        self.lt_emi_preview.setVisible(is_emi)
        if not is_emi:
            self.lt_loan_freq.setEnabled(False)
        else:
            self._toggle_freq_visible()

    def _update_emi(self):
        p = self.lt_loan_principal.value()
        r = self.lt_loan_rate.value()
        m = self.lt_loan_months.value()
        fi = self.lt_loan_freq.currentIndex()
        freq = self._FREQ_VALUES[fi] if fi >= 0 else "ANNUAL"
        method = "COMPOUND" if self.lt_loan_method_type.currentIndex() == 1 else "SIMPLE"
        if p > 0 and m > 0:
            emi = LoanService.emi(p, r, m, freq, method)
            total = LoanService.total_expected(emi, m)
            method_tag = "Simple" if method == "SIMPLE" else f"Compound ({freq})"
            self.lt_emi_preview.setText(
                f"EMI: {fmt_money(emi)}/mo  |  Total Repay: {fmt_money(total)}  ({method_tag})"
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
        emi_type = loan.get("emi_type") or "EMI"
        if emi_type == "NON_EMI" and mode in ("Updated EMI", "Original EMI"):
            self.lt_rep_type.setCurrentText("Custom")
            return
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
        method = "COMPOUND" if self.lt_loan_method_type.currentIndex() == 1 else "SIMPLE"
        emi_type = "NON_EMI" if self.lt_emi_type.currentIndex() == 1 else "EMI"
        emi = LoanService.emi(principal, rate, months, freq, method) if emi_type == "EMI" else 0
        start = self.lt_loan_start.date().toPyDate()
        due = _add_months(start, months)
        account_id = self.lt_loan_account.currentData()
        method_id = self.lt_loan_method.currentData()
        lender_name = self.lt_loan_lender.currentText()
        txn_id = _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method_id,
            tx_type="CREDIT", amount=principal, person_org=lender_name,
            description=f"Loan taken from {lender_name}", category_names=("Finance", "Other")
        )
        self.repos["borrowed"].create_loan(
            lender_id=lid, principal_amount=principal, interest_rate=rate, emi_amount=emi,
            interest_type=freq, interest_method=method, emi_type=emi_type,
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
        if not loan:
            return
        a = self._analysis(loan)
        if amount > a["current_value"] + 0.01:
            QMessageBox.warning(self, "Amount Exceeds Outstanding",
                f"Entered: {fmt_money(amount)}\n"
                f"Outstanding: {fmt_money(a['current_value'])}\n"
                f"Please enter a valid amount.")
            return
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
        active = [l for l in loans if l["status"] != "CLOSED"]
        total_outstanding = 0
        for l in active:
            a = self._analysis(l)
            total_outstanding += a["current_value"]
        _fill_stats_row(self._stats_row, [
            _metric_card("Total Outstanding", fmt_money(total_outstanding), C["amber"]),
            _metric_card("Active Loans", str(len(active))),
            _metric_card("Total Loans", str(len(loans))),
        ])
        # ── loan alerts: upcoming EMIs + overdue ──
        today_str = date.today().isoformat()
        soon_str = _add_months(date.today(), 1).isoformat()
        alerts = []
        for l in active:
            due = l.get("due_date")
            a2 = self._analysis(l)
            if l["status"] == "OVERDUE":
                alerts.append(f"⚠️ {l['lender_name']} — OVERDUE — Outstanding: {fmt_money(a2['current_value'])}")
            elif due and today_str <= due <= soon_str and a2.get("original_emi", 0) > 0:
                alerts.append(f"🔔 {l['lender_name']} — EMI due {due} — {fmt_money(a2['original_emi'])}")
        if alerts:
            alert_box = QFrame()
            alert_box.setStyleSheet(
                f"QFrame{{background:{C['amber_bg']};border:1px solid {C['amber']};border-radius:8px;}}"
                f"QLabel{{background:transparent;border:none;}}"
            )
            al = QVBoxLayout(alert_box)
            al.setContentsMargins(12, 8, 12, 8)
            al.setSpacing(2)
            for a_txt in alerts:
                al.addWidget(QLabel(a_txt))
            self._list_lay.addWidget(alert_box)
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
            mth = l.get("interest_method") or "COMPOUND"
            mth_tag = "SI" if mth == "SIMPLE" else "CI"
            freq_tag = l.get("interest_type") or "ANNUAL"
            freq_short = {"ANNUAL": "Ann", "QUARTERLY": "Qtr", "SEMI_ANNUAL": "Semi"}.get(freq_tag, "")
            ci_extra = f" {freq_short}" if mth == "COMPOUND" else ""
            sub = (f"Rate {l['interest_rate']}% {mth_tag}{ci_extra} {MDOT} "
                   f"EMI {fmt_money(a['original_emi'])} {MDOT} Due {l['due_date'] or EM_DASH}")
            pct = (a["total_paid"] / a["total_expected"] * 100) if a["total_expected"] else 0
            extra = (f"<span style='font-size:15px;font-weight:800;color:{C['text']};'>"
                     f"{fmt_money(a['current_value'])}</span>  "
                     f"<span style='font-size:11px;color:{C['text3']};'>Outstanding</span><br>"
                     f"<span style='font-size:11px;color:{C['text3']};'>"
                     f"Updated EMI: {fmt_money(a['updated_emi'])}  {MDOT}  "
                     f"Paid: {fmt_money(a['total_paid'])}  {MDOT}  "
                     f"Interest: {fmt_money(a['total_interest_accrued'])}</span>")
            card = _wealth_card(
                title=l["lender_name"], subtitle=sub,
                amount_text=fmt_money(l["principal_amount"]) + "  Principal",
                badge_text=l["status"], badge_color=color,
                progress_pct=pct, extra_line=extra,
                on_click=lambda lid=l["loan_id"]: self._open_detail(lid)
            )
            self._list_lay.addWidget(card)

    def _open_detail(self, loan_id):
        loan = self.repos["borrowed"].get_loan(loan_id)
        if not loan:
            return
        repayments = self.repos["borrowed"].get_repayments(loan_id)
        a = self._analysis(loan)
        emi_type = loan.get("emi_type") or "EMI"
        mthd = loan.get("interest_method") or "COMPOUND"
        freq = loan.get("interest_type") or "ANNUAL"
        months = self._loan_months(loan)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Loan from {loan['lender_name']}")
        dlg.setMinimumWidth(560)
        lay = QVBoxLayout(dlg)

        # header
        hdr = QHBoxLayout()
        t = QLabel(f"Loan from {loan['lender_name']}")
        t.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        hdr.addWidget(t, 1)
        hdr.addWidget(_badge(loan["status"], status_color("liability", loan["status"])))
        lay.addLayout(hdr)

        # info
        mth_label = "Simple" if mthd == "SIMPLE" else f"Compound ({freq})"
        emi_info = f"  {MDOT}  EMI: {fmt_money(a['original_emi'])}" if emi_type == "EMI" else ""
        tenure_info = f"  {MDOT}  Tenure: {months} months"
        info = QLabel(
            f"Principal: {fmt_money(loan['principal_amount'])}  {MDOT}  "
            f"Rate: {loan['interest_rate']}%  {mth_label}{emi_info}\n"
            f"Start: {loan['start_date']}  {MDOT}  Due: {loan['due_date'] or EM_DASH}{tenure_info}"
        )
        info.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        # analysis
        a_lbl = QLabel(
            f"Outstanding: {fmt_money(a['current_value'])}  {MDOT}  "
            f"Current Value: {fmt_money(a['current_value'])}\n"
            f"Total Paid: {fmt_money(a['total_paid'])}  {MDOT}  "
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

        # repayment log
        lay.addWidget(_repayment_cards(repayments, "amount_paid", "payment_date"), 1)

        # buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if loan["status"] == "REPAID":
            close_btn = QPushButton("\u2705 Mark as Closed")
            close_btn.setObjectName("primary")
            close_btn.clicked.connect(lambda: self._mark_closed(loan_id, dlg))
            btn_row.addWidget(close_btn)
        pbtn = QPushButton("\U0001f5a8  Print PDF")
        pbtn.clicked.connect(lambda: self._print_take_loan(loan, a, repayments))
        btn_row.addWidget(pbtn)
        ok = QPushButton("Close")
        ok.clicked.connect(dlg.accept)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)
        dlg.exec_()

    def _plan_closure_and_close(self, loan, a, detail_dlg):
        pass  # removed

    def _create_plan_and_close(self, loan, a, detail_dlg):
        pass  # removed

    def _mark_closed(self, loan_id, dlg=None):
        if _confirm(self, "Mark Closed", "Confirm: mark this loan as CLOSED?"):
            self.repos["borrowed"].update_status(loan_id, "CLOSED")
            self.load_list()
            if dlg:
                dlg.accept()
            return True
        return False

    def _print_take_loan(self, loan, a, repayments):
        emi_type = loan.get("emi_type") or "EMI"
        mthd = loan.get("interest_method") or "COMPOUND"
        freq = loan.get("interest_type") or "ANNUAL"
        mth_label = "Simple" if mthd == "SIMPLE" else f"Compound ({freq})"
        info = [
            ("Principal", fmt_money(loan["principal_amount"])),
            ("Rate", f"{loan['interest_rate']}%"),
            ("Method", mth_label),
            ("Start", loan["start_date"]),
            ("Due", loan.get("due_date") or EM_DASH),
        ]
        if emi_type == "EMI":
            info.insert(3, ("EMI", fmt_money(a["original_emi"])))
        analysis = [
            ("Outstanding", fmt_money(a["current_value"])),
            ("Current Value", fmt_money(a["current_value"])),
            ("Total Paid", fmt_money(a["total_paid"])),
            ("Interest Accrued", fmt_money(a["total_interest_accrued"])),
        ]
        sections = []
        if repayments:
            rdata = [{"date": r.get("payment_date", ""), "amount": r["amount_paid"],
                      "description": r.get("description") or ""} for r in repayments]
            sections.append({"title": "Repayment Log", "color": "#059669",
                             "type": "repayment", "data": rdata})
        _export_detail_to_pdf(self, f"Loan from {loan['lender_name']}", loan["status"],
                              info, analysis, sections)


# ══════════════════════════════════════════════════════════════════════════
#  LOAN DETAIL DIALOG (shared by Give + Take + Deposits)
# ══════════════════════════════════════════════════════════════════════════
class LoanDetailDialog(QDialog):
    def __init__(self, role, title, principal, status, start_date, due_date, description,
                 repayments, amount_key, date_key, amortization=None, emi=None, rate=None,
                 on_mark_closed=None, on_print=None, parent=None):
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
            tabs.addTab(_repayment_cards(repayments, amount_key, date_key), "Repayment Log")
            tabs.addTab(_amort_cards(amortization), "Amortization Schedule")
            lay.addWidget(tabs, 1)
        else:
            lay.addWidget(_repayment_cards(repayments, amount_key, date_key), 1)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if on_mark_closed and status == "REPAID":
            close_btn = QPushButton("\u2705 Mark as Closed")
            close_btn.setObjectName("primary")
            close_btn.clicked.connect(lambda: (on_mark_closed(), self.accept()))
            btn_row.addWidget(close_btn)
        if on_print:
            pbtn = QPushButton("\U0001f5a8  Print PDF")
            pbtn.clicked.connect(on_print)
            btn_row.addWidget(pbtn)
        ok = QPushButton("Close")
        ok.clicked.connect(self.accept)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)



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
        self.fd_method_type = QComboBox()
        self.fd_method_type.addItems(["Simple Interest", "Compound Interest"])
        self.fd_method_type.currentIndexChanged.connect(self._toggle_fd_freq)
        self.fd_freq = QComboBox()
        self.fd_freq.addItems(["Annual", "Semi-Annual", "Quarterly"])
        self.fd_freq.setCurrentIndex(2)
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
        create_btn.setAutoDefault(True)
        create_btn.clicked.connect(self._create_fd)
        f.addRow("Bank Account *", self.fd_account)
        f.addRow("Principal *", self.fd_principal)
        f.addRow("Interest Method", self.fd_method_type)
        f.addRow("Compounding", self.fd_freq)
        f.addRow("Interest Rate (annual) *", self.fd_rate)
        f.addRow("Start Date", self.fd_start)
        f.addRow("Maturity Date *", self.fd_maturity)
        f.addRow("", self.fd_maturity_preview)
        f.addRow("", create_btn)
        self._update_maturity()
        return page

    def _toggle_fd_freq(self):
        self.fd_freq.setEnabled(self.fd_method_type.currentIndex() == 1)
        self._update_maturity()

    def _update_maturity(self):
        p = self.fd_principal.value()
        r = self.fd_rate.value()
        s = self.fd_start.date().toString("yyyy-MM-dd")
        m = self.fd_maturity.date().toString("yyyy-MM-dd")
        freq_vals = ["ANNUAL", "SEMI_ANNUAL", "QUARTERLY"]
        freq = freq_vals[self.fd_freq.currentIndex()] if self.fd_method_type.currentIndex() == 1 else "ANNUAL"
        if p > 0 and self.fd_maturity.date() > self.fd_start.date():
            if self.fd_method_type.currentIndex() == 1:
                amt = FDService.maturity(p, r, s, m, freq)
                freq_label = self.fd_freq.currentText().lower()
                self.fd_maturity_preview.setText(f"Estimated Maturity: {fmt_money(amt)} ({freq_label} compounding)")
            else:
                # simple interest
                from datetime import datetime as _dt
                years = (_dt.strptime(m, "%Y-%m-%d") - _dt.strptime(s, "%Y-%m-%d")).days / 365.25
                amt = round(p * (1 + r / 100 * years), 2)
                self.fd_maturity_preview.setText(f"Estimated Maturity: {fmt_money(amt)} (simple interest)")
        else:
            self.fd_maturity_preview.setText("Estimated Maturity: \u2014")

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
        freq_vals = ["ANNUAL", "SEMI_ANNUAL", "QUARTERLY"]
        imethod = "COMPOUND" if self.fd_method_type.currentIndex() == 1 else "SIMPLE"
        itype = freq_vals[self.fd_freq.currentIndex()] if imethod == "COMPOUND" else "ANNUAL"
        self.repos["fd"].create(
            bank_account_id=account_id, principal_amount=p, interest_rate=self.fd_rate.value(),
            interest_method=imethod, interest_type=itype,
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
        active_fds = [f for f in fds if f["status"] == "ACTIVE"]
        matured_fds = [f for f in fds if f["status"] == "MATURED"]
        total_active_p = sum(f["principal_amount"] for f in active_fds)
        total_active_m = sum(f["maturity_amount"] or f["principal_amount"] for f in active_fds)
        total_matured_m = sum(f["maturity_amount"] or f["principal_amount"] for f in matured_fds)
        _fill_stats_row(self._stats_row, [
            _metric_card("Active Principal", fmt_money(total_active_p), C["accent"]),
            _metric_card("Active Maturity", fmt_money(total_active_m), C["accent"]),
            _metric_card("Matured Value", fmt_money(total_matured_m), C["green"]),
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
            fd_colors = {"ACTIVE": C["accent"], "MATURED": C["green"],
                         "WITHDRAWN": C["text3"], "PREMATURE_WITHDRAWN": C["text3"]}
            color = fd_colors.get(fd["status"], C["text3"])
            extra = (f"<span style='font-size:15px;font-weight:800;color:{C['text']};'>"
                     f"{fmt_money(fd['maturity_amount'] or fd['principal_amount'])}</span>  "
                     f"<span style='font-size:11px;color:{C['text3']};'>Maturity Value</span><br>"
                     f"<span style='font-size:11px;color:{C['text3']};'>"
                     f"{pct:.0f}% elapsed</span>")
            card = _wealth_card(
                title=fd["account_name"] or "Fixed Deposit",
                subtitle=f"{fd['interest_rate']}% {MDOT} {fd['start_date']} \u2192 {fd['maturity_date']}",
                amount_text=fmt_money(fd["principal_amount"]) + "  Principal",
                badge_text=fd["status"], badge_color=color, progress_pct=pct,
                extra_line=extra,
                on_click=lambda fid=fd["fd_id"]: self._open_detail(fid)
            )
            self._list_lay.addWidget(card)

    def _open_detail(self, fd_id):
        fd = self.repos["fd"].get(fd_id)
        if not fd:
            return
        dlg = FDDetailDialog(
            fd, on_mark_matured=lambda: self._mark_matured(fd_id),
            on_mark_withdrawn=lambda acc, method, fee=0, net=0: self._mark_withdrawn(fd_id, acc, method, fee, net),
            accounts_repo=self.repos["accounts"], lookups_repo=self.repos["lookups"], parent=self
        )
        dlg.exec_()

    def _mark_matured(self, fd_id):
        if _confirm(self, "Mark Matured", "Mark this FD as matured?"):
            self.repos["fd"].update_status(fd_id, "MATURED")
            self.load_list()
            return True
        return False

    def _mark_withdrawn(self, fd_id, account_id, method_id, fee=0, net=0):
        fd = self.repos["fd"].get(fd_id)
        if not fd:
            return False
        amount = net if net > 0 else max((fd["maturity_amount"] or fd["principal_amount"]) - fee, 0)
        _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=account_id, pay_method=method_id,
            tx_type="CREDIT", amount=amount, person_org=None,
            description="FD premature withdrawal" + (f" (fee: {fmt_money(fee)})" if fee > 0 else ""),
            category_names=("Investment", "Finance")
        )
        self.repos["fd"].update_status(fd_id, "PREMATURE_WITHDRAWN")
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
        dlg.setMinimumWidth(420)
        f = QFormLayout(dlg)
        acc_cb = _account_combo(self.accounts_repo)
        idx = acc_cb.findData(self.fd["bank_account_id"])
        if idx >= 0:
            acc_cb.setCurrentIndex(idx)
        method_cb = _method_combo(self.lookups_repo)
        # withdrawal date
        wd_date = QDateEdit(QDate.currentDate())
        wd_date.setCalendarPopup(True)
        # fee
        fee_spin = QDoubleSpinBox()
        fee_spin.setRange(0, 999999)
        fee_spin.setPrefix("\u20b9 ")
        fee_spin.setDecimals(2)
        fee_spin.setValue(0)
        # preview
        net_lbl = QLabel("")
        net_lbl.setStyleSheet(f"color:{C['green']};font-weight:800;font-size:13px;")
        net_lbl.setWordWrap(True)

        def update_net():
            wd = wd_date.date().toPyDate()
            sd = date.fromisoformat(self.fd["start_date"])
            days = max((wd - sd).days, 0)
            p = self.fd["principal_amount"]
            r = self.fd["interest_rate"] or 0
            freq = self.fd.get("interest_type") or "QUARTERLY"
            mthd = self.fd.get("interest_method") or "COMPOUND"
            if mthd == "SIMPLE":
                interest = round(p * r / 100 * days / 365.25, 2)
            else:
                # compound up to withdrawal date
                years = days / 365.25
                periods = {"ANNUAL": 1, "SEMI_ANNUAL": 2, "QUARTERLY": 4}.get(freq, 4)
                rate_per = r / (100 * periods)
                n = periods * years
                interest = round(p * ((1 + rate_per) ** n - 1), 2) if n > 0 else 0
            gross = p + interest
            fee = fee_spin.value()
            net = max(gross - fee, 0)
            net_lbl.setText(
                f"Principal: {fmt_money(p)}\n"
                f"Interest ({days} days): {fmt_money(interest)}\n"
                f"Gross: {fmt_money(gross)}  -  Fee: {fmt_money(fee)}\n"
                f"Net Credit: {fmt_money(net)}"
            )

        wd_date.dateChanged.connect(update_net)
        fee_spin.valueChanged.connect(update_net)
        update_net()

        f.addRow("Withdrawal Date", wd_date)
        f.addRow("Credit Into *", acc_cb)
        f.addRow("Method *", method_cb)
        f.addRow("Premature Fee / Charges", fee_spin)
        f.addRow("", net_lbl)
        row = QHBoxLayout()
        ok_btn = QPushButton("Confirm Withdrawal")
        ok_btn.setObjectName("primary")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        ok_btn.clicked.connect(dlg.accept)
        row.addStretch()
        row.addWidget(cancel_btn)
        row.addWidget(ok_btn)
        f.addRow("", row)
        if dlg.exec_() == QDialog.Accepted:
            wd = wd_date.date().toPyDate()
            sd = date.fromisoformat(self.fd["start_date"])
            days = max((wd - sd).days, 0)
            p = self.fd["principal_amount"]
            r = self.fd["interest_rate"] or 0
            freq = self.fd.get("interest_type") or "QUARTERLY"
            mthd = self.fd.get("interest_method") or "COMPOUND"
            if mthd == "SIMPLE":
                interest = round(p * r / 100 * days / 365.25, 2)
            else:
                years = days / 365.25
                periods = {"ANNUAL": 1, "SEMI_ANNUAL": 2, "QUARTERLY": 4}.get(freq, 4)
                rate_per = r / (100 * periods)
                n = periods * years
                interest = round(p * ((1 + rate_per) ** n - 1), 2) if n > 0 else 0
            fee = fee_spin.value()
            net = max(p + interest - fee, 0)
            if self._on_withdrawn(acc_cb.currentData(), method_cb.currentData(), fee, net):
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
        self.fo_dep_method_type = QComboBox()
        self.fo_dep_method_type.addItems(["Simple Interest", "Compound Interest"])
        self.fo_dep_method_type.currentIndexChanged.connect(self._toggle_fo_freq)
        self.fo_dep_freq = QComboBox()
        self.fo_dep_freq.addItems(["Annual", "Semi-Annual", "Quarterly"])
        self.fo_dep_freq.setCurrentIndex(0)
        self.fo_dep_freq.setEnabled(False)
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
        take_btn.setAutoDefault(True)
        take_btn.clicked.connect(self._create_deposit)
        f1.addRow("Depositor *", _entity_row(self.fo_dep_depositor, self._add_depositor_dlg))
        f1.addRow("Amount *", self.fo_dep_amount)
        f1.addRow("", self.fo_dep_interest_free)
        f1.addRow("Interest Method", self.fo_dep_method_type)
        f1.addRow("Compounding", self.fo_dep_freq)
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
        rep_btn.setAutoDefault(True)
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

    def _toggle_fo_freq(self):
        self.fo_dep_freq.setEnabled(self.fo_dep_method_type.currentIndex() == 1)

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
            if d["status"] not in ("CLOSED", "REPAID"):
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
        a = self._analysis(dep)
        self.fo_rep_pending_lbl.setText(
            f"Outstanding: {fmt_money(a['current_value'])}  {MDOT}  "
            f"Principal: {fmt_money(dep['principal_amount'])}  {MDOT}  "
            f"Paid: {fmt_money(a['total_paid'])}"
        )

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
        imethod = "COMPOUND" if self.fo_dep_method_type.currentIndex() == 1 else "SIMPLE"
        freq_vals = ["ANNUAL", "SEMI_ANNUAL", "QUARTERLY"]
        itype = freq_vals[self.fo_dep_freq.currentIndex()] if imethod == "COMPOUND" else "ANNUAL"
        self.repos["deposits"].create_deposit(
            depositor_id=did, principal_amount=amount, interest_rate=rate,
            deposit_date=self.fo_dep_date.date().toString("yyyy-MM-dd"),
            expected_return_date=self.fo_dep_return_date.date().toString("yyyy-MM-dd"),
            interest_method=imethod, interest_type=itype,
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
        if not dep:
            return
        a = self._analysis(dep)
        if amount > a["current_value"] + 0.01:
            QMessageBox.warning(self, "Amount Exceeds Outstanding",
                f"Entered: {fmt_money(amount)}\n"
                f"Outstanding: {fmt_money(a['current_value'])}\n"
                f"Please enter a valid amount.")
            return
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
        self._check_repaid(did)
        self._refresh_entry_dropdowns()
        self.load_list()
        dep = self.repos["deposits"].get_deposit(did)
        if dep and dep["status"] == "REPAID":
            QMessageBox.information(self, "Deposit Fully Returned",
                "This deposit has been fully returned.\nStatus: REPAID \u2014 waiting for closure confirmation.")
        else:
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
        total_outstanding = 0
        for d in active:
            a = self._analysis(d)
            total_outstanding += a["current_value"]
        _fill_stats_row(self._stats_row, [
            _metric_card("Total Outstanding", fmt_money(total_outstanding), C["amber"]),
            _metric_card("Active Deposits", str(len(active))),
            _metric_card("Total Deposits", str(len(deps))),
        ])
        search = self._search_input.text().strip().lower() if hasattr(self, "_search_input") else ""
        if search:
            deps = [d for d in deps if search in d["depositor_name"].lower()]
        mode = self._sort_cb.currentText() if hasattr(self, "_sort_cb") else ""
        rank = {"OVERDUE": 0, "ACTIVE": 1, "PARTIALLY_PAID": 2, "REPAID": 3, "CLOSED": 4}
        if mode == "Status":
            deps.sort(key=lambda d: rank.get(d["status"], 9))
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
            a = self._analysis(d)
            pct = (a["total_paid"] / a["total_expected"] * 100) if a["total_expected"] else 0
            interest_free = not d["interest_rate"]
            if d["status"] == "CLOSED":
                color = C["text3"]
            elif d["status"] == "REPAID":
                color = C["green"]
            elif a["total_paid"] > 0 and a["current_value"] > 0:
                color = C["amber"]
            else:
                color = C["accent"]
            interest_tag = "Interest-Free" if interest_free else f"{d['interest_rate']}%"
            status_tag = d["status"]
            badge_text = f"{interest_tag} | {status_tag}"
            extra = (f"<span style='font-size:15px;font-weight:800;color:{C['text']};'>"
                     f"{fmt_money(a['current_value'])}</span>  "
                     f"<span style='font-size:11px;color:{C['text3']};'>Outstanding</span><br>"
                     f"<span style='font-size:11px;color:{C['text3']};'>"
                     f"Interest: {fmt_money(a['total_interest_accrued'])}  {MDOT}  "
                     f"Paid: {fmt_money(a['total_paid'])}</span>")
            card = _wealth_card(
                title=d["depositor_name"],
                subtitle=f"Deposited {d['deposit_date']} {MDOT} Return {d['expected_return_date'] or EM_DASH}",
                amount_text=fmt_money(d["principal_amount"]) + "  Principal",
                badge_text=badge_text, badge_color=color,
                progress_pct=pct, extra_line=extra,
                on_click=lambda did=d["deposit_id"]: self._open_detail(did)
            )
            self._list_lay.addWidget(card)

    def _open_detail(self, deposit_id):
        dep = self.repos["deposits"].get_deposit(deposit_id)
        if not dep:
            return
        repayments = self.repos["deposits"].get_repayments(deposit_id)
        a = self._analysis(dep)
        def print_dep():
            info = [
                ("Principal", fmt_money(dep["principal_amount"])),
                ("Rate", f"{dep.get('interest_rate') or 0}%"),
                ("Method", dep.get("interest_method") or "SIMPLE"),
                ("Deposit Date", dep["deposit_date"]),
                ("Return Date", dep.get("expected_return_date") or EM_DASH),
            ]
            analysis = [
                ("Outstanding", fmt_money(a["current_value"])),
                ("Total Paid", fmt_money(a["total_paid"])),
                ("Interest Accrued", fmt_money(a["total_interest_accrued"])),
            ]
            sections = []
            if repayments:
                rdata = [{"date": r.get("payment_date", ""), "amount": r["amount_paid"],
                          "description": r.get("description") or ""} for r in repayments]
                sections.append({"title": "Repayment Log", "color": "#059669",
                                 "type": "repayment", "data": rdata})
            _export_detail_to_pdf(self, f"Deposit from {dep['depositor_name']}", dep["status"],
                                  info, analysis, sections)
        dlg = LoanDetailDialog(
            role="take", title=f"Deposit from {dep['depositor_name']}",
            principal=dep["principal_amount"], status=dep["status"],
            start_date=dep["deposit_date"], due_date=dep["expected_return_date"],
            description=dep.get("description"), repayments=repayments,
            amount_key="amount_paid", date_key="payment_date",
            on_mark_closed=lambda: self._mark_closed(deposit_id),
            on_print=print_dep, parent=self
        )
        dlg.exec_()

    def _mark_closed(self, deposit_id):
        if _confirm(self, "Mark Closed", "Mark this deposit as fully returned/closed?"):
            self.repos["deposits"].update_status(deposit_id, "CLOSED")
            self.load_list()
            return True
        return False

    # ── analysis helper ──
    def _dep_months(self, dep):
        sd = date.fromisoformat(dep["deposit_date"])
        dd = dep.get("expected_return_date")
        if dd:
            return max(1, round((date.fromisoformat(dd) - sd).days / 30.44))
        return 12

    def _analysis(self, dep):
        total_paid = self.repos["deposits"].total_repaid(dep["deposit_id"])
        months = self._dep_months(dep)
        method = dep.get("interest_method") or "SIMPLE"
        rate = dep.get("interest_rate") or 0
        if not rate:
            cv = max(dep["principal_amount"] - total_paid, 0)
            return {"current_value": cv, "original_emi": 0, "updated_emi": 0,
                    "full_payoff": cv, "total_expected": dep["principal_amount"],
                    "total_paid": total_paid, "total_interest_accrued": 0,
                    "months_elapsed": 0, "months_remaining": 0}
        payments = self.repos["deposits"].get_repayments(dep["deposit_id"])
        return LoanService.loan_analysis(
            dep["principal_amount"], rate, months, "ANNUAL",
            total_paid, dep["deposit_date"], payments=payments, method=method
        )

    def _check_repaid(self, deposit_id):
        dep = self.repos["deposits"].get_deposit(deposit_id)
        if not dep or dep["status"] in ("CLOSED", "REPAID"):
            return
        a = self._analysis(dep)
        if a["current_value"] <= 0 and a["total_paid"] > 0:
            self.repos["deposits"].update_status(deposit_id, "REPAID")


# ══════════════════════════════════════════════════════════════════════════
#  MUTUAL FUNDS
# ══════════════════════════════════════════════════════════════════════════
class MFPage(_FunctionPage):
    ICON = "\U0001f4c8"
    TITLE = "Mutual Funds"

    def __init__(self, repos, services, parent=None):
        self._nav_cache = {}
        self._nav_fetched = False
        super().__init__(repos, services, parent)

    def refresh(self):
        """Override: don't fetch NAVs on tab open, only update dropdowns."""
        self._refresh_entry_dropdowns()

    def _sort_options(self):
        return ["Return %", "Scheme Name", "Invested", "Current Value"]

    def _build_entry(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.mf_stack, _ = _build_subnav(lay, ["Purchase / SIP", "Redemption"])

        # ── Purchase / SIP ──
        p1 = QWidget()
        f1 = QFormLayout(p1)
        self.mf_buy_scheme = SearchableCombo(placeholder="Search scheme\u2026")
        self.mf_buy_scheme.currentIndexChanged.connect(self._auto_fetch_buy_nav)
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
        buy_btn.setAutoDefault(True)
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
        self.mf_sell_scheme.currentIndexChanged.connect(self._auto_fetch_sell_nav)
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
        sell_btn.setAutoDefault(True)
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
        dlg.setMinimumWidth(480)
        f = QFormLayout(dlg)
        amc = QLineEdit()
        amc.setPlaceholderText("e.g. Parag Parikh")
        name = QLineEdit()
        name.setPlaceholderText("e.g. Flexi Cap Fund - Direct Growth")
        stype = QComboBox()
        stype.addItems(["Equity", "Debt", "Hybrid", "Index", "ELSS", "Liquid", "Other"])
        folio = QLineEdit()
        folio.setPlaceholderText("Optional")
        # Search fund to link API scheme code
        search_row = QHBoxLayout()
        self._linked_code = None
        self._linked_name = None
        link_lbl = QLabel("Not linked")
        link_lbl.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        def search_fund():
            dlg2 = NavFetchDialog(initial_query=name.text(), parent=dlg)
            if dlg2.exec_() == QDialog.Accepted and dlg2.result_nav:
                idx = dlg2.results.currentRow()
                if idx >= 0 and idx < len(dlg2._matches):
                    code = dlg2._matches[idx].get("schemeCode")
                    self._linked_code = str(code) if code else None
                self._linked_name = dlg2.result_name
                link_lbl.setText(f"Linked: {dlg2.result_name}")
                link_lbl.setStyleSheet(f"color:{C['green']};font-size:11px;font-weight:700;")
                # Auto-fill NAV
                cur_nav.setValue(dlg2.result_nav)
                # Fetch scheme details for launch date
                if self._linked_code:
                    try:
                        import urllib.request
                        url = f"https://api.mfapi.in/mf/{self._linked_code}"
                        with urllib.request.urlopen(url, timeout=5) as resp:
                            data = _json.loads(resp.read().decode())
                        meta = data.get("meta", {})
                        start = meta.get("scheme_start_date") or meta.get("scheme_start")
                        if start:
                            from datetime import datetime as _dt
                            for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
                                try:
                                    dt = _dt.strptime(str(start), fmt)
                                    launch_date.setDate(QDate(dt.year, dt.month, dt.day))
                                    break
                                except ValueError:
                                    continue
                    except Exception:
                        pass
        link_btn = QPushButton("\U0001f50d Search & Link")
        link_btn.clicked.connect(search_fund)
        search_row.addWidget(link_btn)
        search_row.addWidget(link_lbl)
        # Current status for existing investments
        status_hint = QLabel("Leave at 0 if this is a new investment")
        status_hint.setStyleSheet(f"color:{C['text3']};font-size:10px;font-style:italic;")
        cur_units = QDoubleSpinBox()
        cur_units.setRange(0, 99999999)
        cur_units.setDecimals(4)
        cur_units.setValue(0)
        cur_nav = QDoubleSpinBox()
        cur_nav.setRange(0, 999999)
        cur_nav.setDecimals(4)
        cur_nav.setValue(0)
        cur_invested = QDoubleSpinBox()
        cur_invested.setRange(0, 999999999)
        cur_invested.setPrefix("\u20b9 ")
        cur_invested.setDecimals(2)
        cur_invested.setValue(0)

        f.addRow("AMC *", amc)
        f.addRow("Scheme Name *", name)
        f.addRow("Type", stype)
        f.addRow("Folio Number", folio)
        f.addRow("Link Fund", search_row)
        f.addRow("", status_hint)
        f.addRow("Current Units Held", cur_units)
        f.addRow("Current NAV", cur_nav)
        f.addRow("Total Invested", cur_invested)
        btn_row = QHBoxLayout()
        ok = QPushButton("Add Scheme")
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
        sid = self.repos["mf"].create_scheme(
            amc_name=a, scheme_name=n, scheme_type=stype.currentText(),
            folio_number=folio.text().strip() or None, is_active=1,
            api_scheme_code=self._linked_code,
        )
        # If existing holdings, create initial PURCHASE transaction
        units = cur_units.value()
        nav = cur_nav.value()
        invested = cur_invested.value()
        if units > 0 and nav > 0 and invested > 0:
            self.repos["mf"].add_txn(
                scheme_id=sid, txn_type="PURCHASE",
                txn_date=TODAY(),
                amount=invested, nav=nav, units=units, linked_txn_id=None,
            )
        self._refresh_entry_dropdowns()
        label = f"{a} \u2014 {n}"
        for i in range(self.mf_buy_scheme.count()):
            if self.mf_buy_scheme.itemText(i) == label:
                self.mf_buy_scheme.setCurrentIndex(i)
                break
        QMessageBox.information(self, "Scheme Added",
            f"'{n}' added to your mutual fund schemes."
            + (f"\nInitial holdings: {units:,.4f} units at NAV {nav:,.4f}" if units > 0 else ""))

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

    def _auto_fetch_buy_nav(self):
        """Auto-fill NAV from cache or saved API link when scheme is selected."""
        sid = self.mf_buy_scheme.get_data()
        if not sid:
            return
        nav = self._last_nav(sid)
        if nav > 0:
            self.mf_buy_nav.setValue(nav)

    def _auto_fetch_sell_nav(self):
        """Auto-fill NAV from cache or saved API link when scheme is selected."""
        sid = self.mf_sell_scheme.get_data()
        if not sid:
            return
        nav = self._last_nav(sid)
        if nav > 0:
            self.mf_sell_nav.setValue(nav)

    def _fetch_nav_buy(self):
        dlg = NavFetchDialog(initial_query=self.mf_buy_scheme.currentText(), parent=self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_nav:
            self.mf_buy_nav.setValue(dlg.result_nav)

    def _fetch_nav_sell(self):
        dlg = NavFetchDialog(initial_query=self.mf_sell_scheme.currentText(), parent=self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_nav:
            self.mf_sell_nav.setValue(dlg.result_nav)

    def _refresh_entry_dropdowns(self):
        try:
            self.mf_buy_scheme.blockSignals(True)
            self.mf_sell_scheme.blockSignals(True)
        except (AttributeError, RuntimeError):
            return
        self.mf_buy_scheme.clear_items()
        self.mf_sell_scheme.clear_items()
        for s in self.repos["mf"].list_schemes():
            label = f"{s['amc_name']} \u2014 {s['scheme_name']}"
            self.mf_buy_scheme.add_item(label, s["scheme_id"])
            self.mf_sell_scheme.add_item(label, s["scheme_id"])
        try:
            self.mf_buy_scheme.blockSignals(False)
            self.mf_sell_scheme.blockSignals(False)
        except (AttributeError, RuntimeError):
            pass
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

    def _edit_scheme(self, scheme):
        """Edit scheme details dialog."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Scheme")
        dlg.setMinimumWidth(480)
        f = QFormLayout(dlg)
        amc = QLineEdit(scheme.get("amc_name", ""))
        name = QLineEdit(scheme.get("scheme_name", ""))
        stype = QComboBox()
        stype.addItems(["Equity", "Debt", "Hybrid", "Index", "ELSS", "Liquid", "Other"])
        stype.setCurrentText(scheme.get("scheme_type") or "Equity")
        folio = QLineEdit(scheme.get("folio_number") or "")
        # Link fund section
        cur_code = scheme.get("api_scheme_code") or ""
        link_lbl = QLabel(f"Linked: {cur_code}" if cur_code else "Not linked")
        link_lbl.setStyleSheet(f"color:{C['green'] if cur_code else C['text3']};font-size:11px;font-weight:700;")
        new_code = [cur_code]  # mutable for closure
        def relink():
            d = NavFetchDialog(initial_query=name.text(), parent=dlg)
            if d.exec_() == QDialog.Accepted and d.result_nav:
                idx = d.results.currentRow()
                if 0 <= idx < len(d._matches):
                    new_code[0] = str(d._matches[idx].get("schemeCode", ""))
                link_lbl.setText(f"Linked: {d.result_name}")
                link_lbl.setStyleSheet(f"color:{C['green']};font-size:11px;font-weight:700;")
        link_row = QHBoxLayout()
        link_btn = QPushButton("\U0001f50d Re-Link Fund")
        link_btn.clicked.connect(relink)
        link_row.addWidget(link_btn)
        link_row.addWidget(link_lbl)

        f.addRow("AMC *", amc)
        f.addRow("Scheme Name *", name)
        f.addRow("Type", stype)
        f.addRow("Folio Number", folio)
        f.addRow("Link Fund", link_row)
        btn_row = QHBoxLayout()
        ok = QPushButton("Save")
        ok.setObjectName("primary")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        f.addRow("", btn_row)
        if dlg.exec_() == QDialog.Accepted:
            a, n = amc.text().strip(), name.text().strip()
            if not a or not n:
                QMessageBox.warning(self, "Missing Info", "AMC and Scheme Name are required.")
                return
            self.db.execute(
                "UPDATE mf_schemes SET amc_name=?, scheme_name=?, scheme_type=?, folio_number=?, api_scheme_code=? WHERE scheme_id=?",
                (a, n, stype.currentText(), folio.text().strip() or None, new_code[0] or None, scheme["scheme_id"]))
            self.db.commit()
            self._nav_cache.pop(scheme["scheme_id"], None)
            if hasattr(self, 'mf_buy_scheme'):
                self._refresh_entry_dropdowns()
            self._build_list_data()
            QMessageBox.information(self, "Updated", f"Scheme '{n}' updated successfully.")

    def _last_nav(self, scheme_id):
        if scheme_id in self._nav_cache:
            return self._nav_cache[scheme_id]
        # Try auto-fetch from saved API scheme code (with short timeout)
        scheme = self.repos["mf"].get_scheme(scheme_id)
        api_code = scheme.get("api_scheme_code") if scheme else None
        if api_code:
            try:
                import urllib.request
                url = f"https://api.mfapi.in/mf/{api_code}/latest"
                with urllib.request.urlopen(url, timeout=3) as resp:
                    data = _json.loads(resp.read().decode())
                rows = data.get("data") or [] if isinstance(data, dict) else []
                if rows:
                    nav = float(rows[0]["nav"])
                    self._nav_cache[scheme_id] = nav
                    return nav
            except Exception:
                pass  # fall through to txn-based NAV
        txns = self.repos["mf"].list_txns(scheme_id)
        return txns[-1]["nav"] if txns else 0

    # ── List ──
    def load_list(self):
        """Fetch NAVs once on first open, then use cache."""
        if not self._nav_fetched:
            self._nav_fetched = True
            all_schemes = self.repos["mf"].list_schemes()
            to_fetch = [(s["scheme_id"], s["api_scheme_code"])
                        for s in all_schemes if s.get("api_scheme_code")]
            if to_fetch:
                self._fetch_navs_and_load(to_fetch)
                return
        self._build_list_data()

    def _fetch_navs_and_load(self, to_fetch):
        """Show loading popup, fetch NAVs in background, then load list."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Loading")
        dlg.setMinimumWidth(320)
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowCloseButtonHint)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 20)
        icon_lbl = QLabel("\U0001f4c8")
        icon_lbl.setStyleSheet("font-size:32px;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon_lbl)
        msg = QLabel(f"Fetching latest NAV for {len(to_fetch)} scheme{'s' if len(to_fetch)!=1 else ''}...")
        msg.setStyleSheet(f"color:{C['text']};font-size:13px;font-weight:600;")
        msg.setAlignment(Qt.AlignCenter)
        lay.addWidget(msg)
        hint = QLabel("This only happens once per session")
        hint.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(hint)
        dlg.show()

        worker = _FetchNavsWorker(to_fetch, self)

        def on_done(results):
            self._nav_cache.update(results)
            dlg.accept()
            self._build_list_data()

        worker.finished.connect(on_done)
        worker.start()

    def _build_list_data(self):
        """Build MF list data using cached/fetched NAVs."""
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
        dlg = MFDetailDialog(scheme, txns, h, nav,
                             on_edit=lambda: self._edit_scheme(scheme),
                             parent=self)
        dlg.exec_()


# ══════════════════════════════════════════════════════════════════════════
#  MF DETAIL DIALOG
# ══════════════════════════════════════════════════════════════════════════
class MFDetailDialog(QDialog):
    def __init__(self, scheme, txns, holdings, nav, on_edit=None, parent=None):
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
        lay.addWidget(_mf_txn_cards(txns), 1)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if on_edit:
            edit_btn = QPushButton("\u270f\ufe0f  Edit Scheme")
            edit_btn.clicked.connect(lambda checked=False, _cb=on_edit: (_cb(), self.accept()))
            btn_row.addWidget(edit_btn)
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
