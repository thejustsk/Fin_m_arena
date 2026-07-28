"""Wealth tab — 5 top-level pages with expandable inline cards (Notes-tab pattern)."""
import json as _json
from datetime import date, datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QFrame, QScrollArea,
    QStackedWidget, QMessageBox, QDialog, QFormLayout, QSizePolicy, QCheckBox,
    QGridLayout
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
from ui.wealth_verify import WealthEditVerifyDialog
from ui.widgets.count_up import animate_value


# ── Constants ──────────────────────────────────────────────────────────────
EM_DASH = "\u2014"
MDOT = "\u00b7"

# Max alert cards built per refresh. Keeps the dashboard responsive on
# databases with a very large number of overdue items.
ALERT_RENDER_LIMIT = 150


def TODAY():
    return date.today().isoformat()

# Updated badge helper
def _is_updated(row):
    """Check if a row has been edited (updated_at is set)."""
    return bool(row.get("updated_at"))


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
        super().__init__(parent)
        self._items = scheme_codes

    def run(self):
        # Fully guarded: an uncaught exception in QThread.run() aborts the
        # whole process, not just this thread.
        try:
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
        except Exception:
            try:
                self.finished.emit({})
            except Exception:
                pass


# ── Helpers ────────────────────────────────────────────────────────────────
def _add_months(d, months):
    m = d.month - 1 + int(months)
    y = d.year + m // 12
    m = m % 12 + 1
    leap = (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
    dim = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(y, m, min(d.day, dim[m - 1]))


def _hex_rgba(hex_color, alpha):
    """Convert hex color to rgba string."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ── Shared money maths (dashboard <-> sub-pages must never disagree) ───────
def _months_between(start_date, end_date, default=12):
    """Whole months between two ISO dates — mirrors the sub-page helpers.

    Falls back to *default* when the end date is missing or unparseable, so a
    NULL due/return date can never crash a KPI calculation.
    """
    if not end_date:
        return default
    try:
        sd = date.fromisoformat(str(start_date))
        ed = date.fromisoformat(str(end_date))
    except (TypeError, ValueError):
        return default
    return max(1, round((ed - sd).days / 30.44))


def _is_overdue(due_date, today_s):
    """True when *due_date* is a real date already in the past."""
    return bool(due_date) and str(due_date) < today_s


def _days_since(due_date, today):
    """Days elapsed since *due_date* — 0 when the date is missing/invalid."""
    try:
        return (today - date.fromisoformat(str(due_date))).days
    except (TypeError, ValueError):
        return 0


def _batch_sum_db(db, table, id_col, sum_col, ids):
    """{id: SUM(sum_col)} for the given ids — one query instead of N."""
    if not ids:
        return {}
    phs = ",".join(["?"] * len(ids))
    rows = db.execute(
        f"SELECT {id_col}, COALESCE(SUM({sum_col}),0) AS t FROM {table} "
        f"WHERE {id_col} IN ({phs}) GROUP BY {id_col}", list(ids)).fetchall()
    return {r[id_col]: r["t"] for r in rows}


def _batch_rows_db(db, table, id_col, ids):
    """{id: [row, ...]} for the given ids — one query instead of N."""
    if not ids:
        return {}
    phs = ",".join(["?"] * len(ids))
    rows = db.execute(
        f"SELECT * FROM {table} WHERE {id_col} IN ({phs}) ORDER BY {id_col}",
        list(ids)).fetchall()
    grouped = {}
    for r in rows:
        d = dict(r)
        grouped.setdefault(d[id_col], []).append(d)
    return grouped


def borrowed_outstanding(loan, total_paid, payments=None):
    """Outstanding on a loan *I took* — identical maths to LoansTakePage."""
    rate = loan.get("interest_rate") or 0
    if (loan.get("emi_type") or "EMI") == "NON_EMI":
        a = LoanService.non_emi_analysis(
            loan["principal_amount"], rate, total_paid, loan["start_date"],
            payments=payments, method=loan.get("interest_method") or "SIMPLE")
    else:
        months = _months_between(loan["start_date"], loan.get("due_date"))
        a = LoanService.loan_analysis(
            loan["principal_amount"], rate, months,
            loan.get("interest_type") or "ANNUAL", total_paid, loan["start_date"],
            method=loan.get("interest_method") or "COMPOUND")
    return a["current_value"]


def deposit_outstanding(dep, total_paid, payments=None):
    """Outstanding on a deposit *received from someone else*.

    Identical maths to FDOthersPage: interest-free deposits are a plain
    principal-minus-repaid figure, interest-bearing ones go through the
    LoanService analysis.
    """
    rate = dep.get("interest_rate") or 0
    if not rate:
        return max((dep.get("principal_amount") or 0) - total_paid, 0)
    months = _months_between(dep["deposit_date"], dep.get("expected_return_date"))
    a = LoanService.loan_analysis(
        dep["principal_amount"], rate, months, "ANNUAL", total_paid,
        dep["deposit_date"], payments=payments,
        method=dep.get("interest_method") or "SIMPLE")
    return a["current_value"]


def status_color(status):
    """Unified status → color mapping across all 5 sub-tabs.
    
    ACTIVE          → Indigo  (#4F46E5) — money is in play
    PARTIALLY_PAID  → Amber   (#D97706) — partial progress
    OVERDUE         → Red     (#DC2626) — past deadline
    REPAID          → Green   (#059669) — fully done
    MATURED         → Green   (#059669) — FD ready
    CLOSED/WITHDRAWN/PREMATURE_WITHDRAWN → Gray (#667085) — archived
    """
    status = (status or "").upper()
    if status == "OVERDUE":
        return C["red"]
    if status == "PARTIALLY_PAID":
        return C["amber"]
    if status in ("REPAID", "MATURED"):
        return C["green"]
    if status in ("CLOSED", "WITHDRAWN", "CLEARED", "PREMATURE_WITHDRAWN"):
        return C["text3"]
    return C["accent"]  # ACTIVE and fallback


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


def _kv_row(pairs):
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
                     person_org=None, description=None, category_names=("Finance", "Other"),
                     transaction_kind="REGULAR"):
    cat = _category_id(db, category_names)
    try:
        return tx_repo.create(
            tx_date=TODAY(), account_id=account_id, pay_method=pay_method,
            tx_type=tx_type, amount=round(float(amount), 2), person_org=person_org,
            description=description, transaction_kind=transaction_kind, category=cat,
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
    row = QHBoxLayout()
    row.setSpacing(6)
    add_btn = QPushButton("\uff0b Add New")
    add_btn.setFixedHeight(38)
    add_btn.setMinimumWidth(90)
    add_btn.setFocusPolicy(Qt.NoFocus)
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


# ── Button styles ──────────────────────────────────────────────────────────
def _accent_btn_css(accent=None):
    """Accent-styled button: white bg, accent border + text. Uses card's color."""
    accent = accent or C["accent"]
    return (f"QPushButton{{background:{C['surface']};color:{accent};"
            f"border:1.5px solid {accent};border-radius:8px;"
            f"padding:6px 14px;font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{background:{_hex_rgba(accent, 0.08)};}}")


def _accent_save_css(accent=None):
    """Accent-styled save button: solid accent bg, white text."""
    accent = accent or C["accent"]
    hover = _hex_rgba(accent, 0.85)
    return (f"QPushButton{{background:{accent};color:white;border:none;"
            f"border-radius:8px;padding:6px 14px;font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{background:{hover};}}")


# ── Export helper ───────────────────────────────────────────────────────────
def _export_detail_to_pdf(parent, title, status, info_pairs, analysis_pairs, sections=None):
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


# ══════════════════════════════════════════════════════════════════════════
#  EXPANDABLE WEALTH CARD (Notes-tab pattern)
# ══════════════════════════════════════════════════════════════════════════
class WealthCard(QFrame):
    """Expandable card matching the Notes tab pattern.
    
    Card shows: title, subtitle, amount, badge, progress bar, extra line.
    Clicking the card expands it to show: details, repayments, edit form.
    """
    clicked = _Signal(str)  # item_id

    def __init__(self, item_id, title, subtitle, amount_text, badge_text, badge_color,
                 progress_pct=None, extra_line=None, updated=False, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.expanded = False
        self.accent_color = badge_color

        # Style: accent-colored border + tinted background
        bg = _hex_rgba(badge_color, 0.06)
        hover_bg = _hex_rgba(badge_color, 0.10)
        self.setStyleSheet(
            f"QFrame{{background:{bg};border:1.5px solid {badge_color};border-radius:12px;}}"
            f"QFrame:hover{{background:{hover_bg};border-color:{badge_color};}}"
            f"QLabel{{background:transparent;border:none;outline:none;}}"
        )
        self.setCursor(QCursor(Qt.PointingHandCursor))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        # ── Row 1: Title + Badge (right) ──
        top = QHBoxLayout()
        t = QLabel(title)
        t.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        top.addWidget(t, 1)
        if updated:
            upd_lbl = _badge("Updated", C["accent"])
            top.addWidget(upd_lbl)
        self._badge_lbl = _badge(badge_text, badge_color)
        top.addWidget(self._badge_lbl)
        lay.addLayout(top)

        # ── Row 2: Subtitle + Principal (right) ──
        mid = QHBoxLayout()
        s = QLabel(subtitle)
        s.setStyleSheet(f"font-size:12px;color:{C['text3']};")
        s.setWordWrap(True)
        mid.addWidget(s, 1)
        a = QLabel(amount_text)
        a.setStyleSheet(f"font-size:18px;font-weight:900;color:{C['text']};")
        mid.addWidget(a)
        lay.addLayout(mid)

        # ── Row 3: Progress bar ──
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

        # ── Row 5: Extra line (outstanding, interest, etc.) ──
        if extra_line:
            e = QLabel(extra_line)
            e.setTextFormat(Qt.RichText)
            e.setStyleSheet(f"font-size:11px;color:{C['text3']};")
            lay.addWidget(e)

        # ── Expand area (hidden initially) ──
        self._expand_area = QWidget()
        self._expand_area.setStyleSheet("background:transparent;border:none;")
        self._expand_lay = QVBoxLayout(self._expand_area)
        self._expand_lay.setContentsMargins(0, 8, 0, 0)
        self._expand_lay.setSpacing(8)
        self._expand_area.hide()
        lay.addWidget(self._expand_area)

    def add_expand_widget(self, widget):
        self._expand_lay.addWidget(widget)

    def add_expand_layout(self, layout):
        self._expand_lay.addLayout(layout)

    def mousePressEvent(self, event):
        self.clicked.emit(self.item_id)
        event.accept()

    def expand(self):
        self.expanded = True
        self._expand_area.show()

    def collapse(self):
        self.expanded = False
        self._expand_area.hide()


def _make_repayment_card(rep, amount_key, date_key, accent_color=None, on_edit=None):
    """Single repayment row with visible edit button and expandable edit form."""
    accent = accent_color or C["accent"]
    card = QFrame()
    card.setStyleSheet(
        f"QFrame{{background:{_hex_rgba(accent, 0.05)};border:1px solid {_hex_rgba(accent, 0.2)};border-radius:8px;}}"
        f"QFrame:hover{{border-color:{accent};}}"
        f"QLabel{{background:transparent;border:none;}}"
    )
    cl = QVBoxLayout(card)
    cl.setContentsMargins(12, 8, 12, 8)
    cl.setSpacing(4)
    hdr = QHBoxLayout()
    d = QLabel(rep.get(date_key, ""))
    d.setStyleSheet(f"font-size:13px;font-weight:700;color:{C['text']};")
    a = QLabel(fmt_money(rep[amount_key]))
    a.setStyleSheet(f"font-size:15px;font-weight:800;color:{accent};")
    a.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    hdr.addWidget(d)
    hdr.addStretch()
    hdr.addWidget(a)
    cl.addLayout(hdr)
    desc = rep.get("description") or ""
    if desc:
        dl = QLabel(desc)
        dl.setStyleSheet(f"font-size:11px;color:{C['text3']};font-style:italic;")
        dl.setWordWrap(True)
        cl.addWidget(dl)

    # Edit form (hidden)
    edit_frame = QFrame()
    edit_frame.setStyleSheet(
        f"QFrame{{background:transparent;border:1.5px solid {accent};border-radius:6px;}}"
        f"QLabel{{background:transparent;border:none;}}"
        f"QLineEdit, QDoubleSpinBox, QDateEdit{{"
        f"border:1.5px solid {_hex_rgba(accent, 0.3)};border-radius:6px;padding:5px 8px;"
        f"background:{C['surface']};}}"
        f"QLineEdit:focus, QDoubleSpinBox:focus, QDateEdit:focus{{border-color:{accent};}}"
    )
    ef_lay = QVBoxLayout(edit_frame)
    ef_lay.setContentsMargins(10, 8, 10, 8)
    ef_lay.setSpacing(6)
    e_title = QLabel("\u270f\ufe0f Edit Repayment")
    e_title.setStyleSheet(f"font-size:12px;font-weight:700;color:{accent};")
    ef_lay.addWidget(e_title)
    e_form = QFormLayout()
    e_form.setSpacing(4)
    e_amt = QDoubleSpinBox()
    e_amt.setRange(0, 99999999)
    e_amt.setDecimals(2)
    e_amt.setPrefix("\u20b9 ")
    e_amt.setValue(rep[amount_key])
    e_date = QDateEdit(QDate.fromString(rep.get(date_key, ""), "yyyy-MM-dd"))
    e_date.setCalendarPopup(True)
    e_desc = QLineEdit(rep.get("description") or "")
    e_desc.setPlaceholderText("Description (optional)")
    e_form.addRow("Amount", e_amt)
    e_form.addRow("Date", e_date)
    e_form.addRow("Description", e_desc)
    ef_lay.addLayout(e_form)
    e_btns = QHBoxLayout()
    e_save = QPushButton("\U0001f4be Save")
    e_save.setStyleSheet(_accent_save_css(accent))
    e_cancel = QPushButton("Cancel")
    e_cancel.setStyleSheet(_accent_btn_css(accent))
    e_btns.addStretch()
    e_btns.addWidget(e_cancel)
    e_btns.addWidget(e_save)
    ef_lay.addLayout(e_btns)
    edit_frame.hide()
    cl.addWidget(edit_frame)

    # Edit button (hidden until card clicked)
    if on_edit:
        edit_btn = QPushButton("\u270f\ufe0f Edit")
        edit_btn.setFixedHeight(24)
        edit_btn.setFocusPolicy(Qt.NoFocus)
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        edit_btn.setStyleSheet(_accent_btn_css(accent))
        edit_btn.hide()
        cl.addWidget(edit_btn)

        def _toggle_edit():
            show = not edit_frame.isVisible()
            edit_frame.setVisible(show)
            edit_btn.setText("Cancel Edit" if show else "\u270f\ufe0f Edit")

        def _save_edit():
            data = {
                "amount": round(e_amt.value(), 2),
                "date": e_date.date().toString("yyyy-MM-dd"),
                "description": e_desc.text().strip() or None,
            }
            save_fn = on_edit()
            if callable(save_fn):
                save_fn(data)

        edit_btn.clicked.connect(_toggle_edit)
        e_cancel.clicked.connect(_toggle_edit)
        e_save.clicked.connect(_save_edit)

        # Click card → show edit button (2-click pattern)
        def _on_card_click(event):
            edit_btn.show()
        card.mousePressEvent = _on_card_click

    return card


def _repayment_section(repayments, amount_key, date_key, empty_msg="No repayments logged yet.",
                        accent_color=None, on_edit=None):
    """VBox of repayment cards for an expanded detail area.
    
    on_edit(rep_data, save_data) — called with the repayment record and form data.
    """
    container = QWidget()
    container.setStyleSheet("background:transparent;border:none;")
    lay = QVBoxLayout(container)
    lay.setSpacing(6)
    lay.setContentsMargins(0, 0, 0, 0)
    if not repayments:
        lbl = QLabel(empty_msg)
        lbl.setStyleSheet(f"color:{C['text3']};padding:8px;font-size:12px;")
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl)
    else:
        for r in repayments:
            card = _make_repayment_card(r, amount_key, date_key,
                                         accent_color=accent_color,
                                         on_edit=(lambda _r=r, _data=None: on_edit(_r)) if on_edit else None)
            lay.addWidget(card)
    return container


def _build_edit_form(fields, on_save, on_cancel, accent_color=None):
    """Build an inline edit form for a card's fields.
    
    fields: list of (label, "text"|"number"|"rate"|"combo"|"date", current_value, options_or_None)
    Returns: QFrame (hidden by default)
    """
    accent = accent_color or C["accent"]
    form_frame = QFrame()
    form_frame.setStyleSheet(
        f"QFrame{{background:transparent;border:1.5px solid {accent};border-radius:8px;}}"
        f"QLabel{{background:transparent;border:none;}}"
        f"QLineEdit, QDoubleSpinBox, QComboBox, QDateEdit{{"
        f"border:1.5px solid {_hex_rgba(accent, 0.3)};border-radius:6px;padding:6px 10px;"
        f"background:{C['surface']};}}"
        f"QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus{{"
        f"border-color:{accent};}}"
    )
    fl = QVBoxLayout(form_frame)
    fl.setContentsMargins(12, 10, 12, 10)
    fl.setSpacing(6)
    title_lbl = QLabel("\u270f\ufe0f Edit Details")
    title_lbl.setStyleSheet(f"font-size:12px;font-weight:700;color:{accent};")
    fl.addWidget(title_lbl)
    form = QFormLayout()
    form.setSpacing(6)
    widgets = {}
    for label, ftype, value, opts in fields:
        if ftype == "text":
            w = QLineEdit(str(value or ""))
        elif ftype == "number":
            w = QDoubleSpinBox()
            w.setRange(0, 999999999)
            w.setDecimals(2)
            w.setPrefix("\u20b9 ")
            w.setValue(float(value or 0))
        elif ftype == "rate":
            w = QDoubleSpinBox()
            w.setRange(0, 100)
            w.setDecimals(2)
            w.setSuffix(" %")
            w.setValue(float(value or 0))
        elif ftype == "combo":
            w = QComboBox()
            for olbl, oval in opts:
                w.addItem(olbl, oval)
            idx = w.findData(value)
            if idx >= 0:
                w.setCurrentIndex(idx)
        elif ftype == "date":
            w = QDateEdit(QDate.fromString(str(value or ""), "yyyy-MM-dd"))
            w.setCalendarPopup(True)
        else:
            w = QLineEdit(str(value or ""))
        form.addRow(label, w)
        widgets[label] = (w, ftype)
    fl.addLayout(form)
    btn_row = QHBoxLayout()
    save_btn = QPushButton("\U0001f4be Save Changes")
    save_btn.setStyleSheet(_accent_save_css(accent))
    cancel_btn = QPushButton("Cancel")
    cancel_btn.setStyleSheet(_accent_btn_css(accent))
    btn_row.addStretch()
    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(save_btn)
    fl.addLayout(btn_row)
    form_frame.hide()

    def _get_values():
        result = {}
        for lbl, (w, ftype) in widgets.items():
            if ftype == "text":
                result[lbl] = w.text().strip() or None
            elif ftype in ("number", "rate"):
                result[lbl] = w.value()
            elif ftype == "combo":
                result[lbl] = w.currentData()
            elif ftype == "date":
                result[lbl] = w.date().toString("yyyy-MM-dd")
        return result

    def _save():
        on_save(_get_values())
        form_frame.hide()

    cancel_btn.clicked.connect(lambda: (form_frame.hide(), on_cancel()))
    save_btn.clicked.connect(_save)

    return form_frame


# ══════════════════════════════════════════════════════════════════════════
#  BASE FUNCTION PAGE
# ══════════════════════════════════════════════════════════════════════════
class _FunctionPage(QWidget):
    ICON = "\U0001f4b0"
    TITLE = "Function"

    def __init__(self, repos, services, parent=None):
        super().__init__(parent)
        self.repos = repos
        self.services = services
        self.db = repos["accounts"].db
        self._list_data = []
        self._loaded = False
        self._wealth_tab_ref = None  # set by WealthTab after creation
        self._build_skeleton()

    def _notify_data_changed(self):
        """Notify other tabs that data changed. Called after saves."""
        if self._wealth_tab_ref:
            self._wealth_tab_ref._notify_data_changed()

    def _build_skeleton(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)
        hdr = QLabel(f"{self.ICON}  {self.TITLE}")
        hdr.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        lay.addWidget(hdr)
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
        lay.addWidget(self.sub_stack)
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
        self._loaded = False
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
        self._scroll_ref = scroll  # store for lazy loading
        return scroll, v

    def _build_entry(self):
        return QWidget()

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

    def _verify_edit(self):
        """Require 2FA/password before allowing wealth edits."""
        sec = self.services.get("security")
        if not sec:
            return True
        return WealthEditVerifyDialog.verify_user(sec, self)

    def load_list(self, force=False):
        """Override in subclass. force=True rebuilds after edit."""
        pass

    def _render_list(self):
        pass

    # ── Batch query helpers ──
    def _batch_query(self, table, id_col, ids):
        """Batch query: get all rows from table where id_col IN ids, grouped by id_col."""
        if not ids:
            return {}
        phs = ",".join(["?"] * len(ids))
        rows = self.db.execute(
            f"SELECT * FROM {table} WHERE {id_col} IN ({phs}) ORDER BY {id_col}",
            ids).fetchall()
        grouped = {}
        for r in rows:
            d = dict(r)
            grouped.setdefault(d[id_col], []).append(d)
        return grouped

    def _batch_sum(self, table, id_col, sum_col, ids):
        """Batch SUM query: {id: sum} for all ids."""
        if not ids:
            return {}
        phs = ",".join(["?"] * len(ids))
        rows = self.db.execute(
            f"SELECT {id_col}, COALESCE(SUM({sum_col}),0) AS t FROM {table} WHERE {id_col} IN ({phs}) GROUP BY {id_col}",
            ids).fetchall()
        return {r[id_col]: r["t"] for r in rows}

    def _toggle_card(self, item_id):
        for i in range(self._list_lay.count()):
            item = self._list_lay.itemAt(i)
            w = item.widget()
            if isinstance(w, WealthCard):
                if w.item_id == item_id:
                    if w.expanded:
                        w.collapse()
                    else:
                        w.expand()
                else:
                    w.collapse()

    # ── Lazy loading support (uses settings preferences) ──
    def _get_batch_size(self):
        try:
            r = self.db.execute("SELECT value FROM preferences WHERE key='wealth_page_size'").fetchone()
            if r: return int(r[0])
            r = self.db.execute("SELECT value FROM preferences WHERE key='complete_page_size'").fetchone()
            return int(r[0]) if r else 150
        except Exception:
            return 150

    def _get_scroll_trigger(self):
        try:
            r = self.db.execute("SELECT value FROM preferences WHERE key='wealth_scroll_trigger'").fetchone()
            if r: return int(r[0])
            r = self.db.execute("SELECT value FROM preferences WHERE key='scroll_trigger_px'").fetchone()
            return int(r[0]) if r else 400
        except Exception:
            return 400

    def _init_lazy_scroll(self):
        """Connect scroll area scrollbar to lazy loading."""
        scroll = getattr(self, '_scroll_ref', None)
        if isinstance(scroll, QScrollArea):
            try:
                scroll.verticalScrollBar().valueChanged.disconnect(self._on_scroll)
            except (TypeError, RuntimeError):
                pass
            scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def _on_scroll(self, value):
        """Load next batch when scrolled near bottom."""
        scroll = self.sender()
        if not scroll or scroll.maximum() <= 0:
            return
        if value >= scroll.maximum() - self._get_scroll_trigger():
            self._render_next_batch()

    def _render_next_batch(self):
        """Render next batch — override in subclass for lazy card building."""
        pass


# ══════════════════════════════════════════════════════════════════════════
#  LOANS I GIVE
# ══════════════════════════════════════════════════════════════════════════
class LoansGivePage(_FunctionPage):
    ICON = "\U0001f91d"
    TITLE = "Money Lent"

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

        # Give Loan
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

        # Log Repayment
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
            description=f"Loan given to {borrower_name}", category_names=("Finance", "Other"),
            transaction_kind="LOAN_GIVEN"
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
        self._loaded = False
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
            category_names=("Finance", "Other"), transaction_kind="LOAN_REPAYMENT"
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
        self._loaded = False
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
    def _render_list(self):
        if not hasattr(self, "_list_lay"):
            return
        _clear_layout(self._stats_row)
        _clear_layout(self._list_lay)
        loans = list(self._list_data)

        # ── Batch queries (once) ──
        ids = [l["loan_id"] for l in loans]
        repaid_map = self._batch_sum("repayments", "loan_id", "amount_paid", ids)
        self._repay_map = self._batch_query("repayments", "loan_id", ids)
        self._repaid_map = repaid_map

        # ── KPI stats ──
        total_pending = sum(
            max(l["loan_amount"] - repaid_map.get(l["loan_id"], 0), 0)
            for l in loans if l["status"] != "CLOSED"
        )
        pending_count = len([l for l in loans if l["status"] != "CLOSED"])
        _fill_stats_row(self._stats_row, [
            _metric_card("Total Pending", fmt_money(total_pending), C["amber"]),
            _metric_card("Pending Loans", str(pending_count)),
            _metric_card("Total Loans", str(self.repos["loans"].count_total())),
        ])

        # ── Filter & sort ──
        search = self._search_input.text().strip().lower() if hasattr(self, "_search_input") else ""
        if search:
            loans = [l for l in loans if search in l["borrower_name"].lower()]
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
        if not loans:
            empty = QLabel("No matching loans." if search else "No loans given yet.")
            empty.setStyleSheet(f"color:{C['text3']};padding:20px;")
            empty.setAlignment(Qt.AlignCenter)
            self._list_lay.addWidget(empty)
            return

        # ── Pre-compute analysis data (no widget creation) ──
        self._all_items = []
        for l in loans:
            total_paid = repaid_map.get(l["loan_id"], 0)
            months = self._loan_months(l)
            method = l.get("interest_method") or "SIMPLE"
            rate = l.get("interest_rate") or 0
            a = LoanService.loan_analysis(
                l["loan_amount"], rate, months, "ANNUAL", total_paid, l["start_date"], method=method
            )
            self._all_items.append((l, a))

        # ── Build first batch only ──
        batch_size = self._get_batch_size()
        first = self._all_items[:batch_size]
        self._pending_items = self._all_items[batch_size:]
        for l, a in first:
            self._list_lay.addWidget(self._build_lg_card(l, a))
        if self._pending_items:
            self._init_lazy_scroll()

    def _build_lg_card(self, l, a):
        """Build a single Money Lent card from pre-computed data."""
        pct = (a["total_paid"] / a["total_expected"] * 100) if a["total_expected"] else 0
        color = status_color(l["status"])
        mth = l.get("interest_method") or "SIMPLE"
        mth_tag = "SI" if mth == "SIMPLE" else "CI"
        rate = l.get("interest_rate") or 0
        rate_tag = f"{rate}% {mth_tag}" if rate > 0 else "Interest-Free"
        extra = (f"<span style='font-size:15px;font-weight:800;color:{C['text']};'>"
                 f"{fmt_money(a['current_value'])}</span>  "
                 f"<span style='font-size:11px;color:{C['text3']};'>Outstanding</span><br>"
                 f"<span style='font-size:11px;color:{C['text3']};'>"
                 f"Interest: {fmt_money(a['total_interest_accrued'])}  {MDOT}  "
                 f"Paid: {fmt_money(a['total_paid'])}</span>")
        card = WealthCard(
            item_id=l["loan_id"],
            title=l["borrower_name"],
            subtitle=f"Given {l['start_date']} {MDOT} Due {l['due_date'] or EM_DASH} {MDOT} {rate_tag}",
            amount_text=fmt_money(l["loan_amount"]) + "  Principal",
            badge_text=l["status"], badge_color=color,
            progress_pct=pct, extra_line=extra,
            updated=bool(l.get("updated_at")),
        )
        card.clicked.connect(self._toggle_card)
        lid = l["loan_id"]

        # Detail info
        detail_info = QLabel()
        detail_info.setTextFormat(Qt.RichText)
        detail_info.setText(
            f"<table style='font-size:13px;color:{C['text2']};' cellpadding='3'>"
            f"<tr><td style='color:{C['text3']};font-weight:600;'>Rate</td>"
            f"<td style='font-weight:700;color:{C['text']};'>{rate}% {mth_tag}</td>"
            f"<td style='color:{C['text3']};font-weight:600;padding-left:16px;'>Start</td>"
            f"<td style='font-weight:700;color:{C['text']};'>{l['start_date']}</td></tr>"
            f"<tr><td style='color:{C['text3']};font-weight:600;'>Due Date</td>"
            f"<td style='font-weight:700;color:{C['text']};'>{l['due_date'] or EM_DASH}</td>"
            f"<td style='color:{C['text3']};font-weight:600;padding-left:16px;'>Outstanding</td>"
            f"<td style='font-weight:800;color:{color};'>{fmt_money(a['current_value'])}</td></tr>"
            f"<tr><td style='color:{C['text3']};font-weight:600;'>Total Expected</td>"
            f"<td style='font-weight:700;color:{C['text']};'>{fmt_money(a['total_expected'])}</td>"
            f"<td style='color:{C['text3']};font-weight:600;padding-left:16px;'>Interest</td>"
            f"<td style='font-weight:700;color:{C['text']};'>{fmt_money(a['total_interest_accrued'])}</td></tr>"
            f"</table>"
            + (f"<div style='font-size:12px;color:{C['text3']};font-style:italic;padding-top:4px;'>Note: {l['description']}</div>" if l.get("description") else "")
        )
        detail_info.setWordWrap(True)
        card.add_expand_widget(detail_info)

        # Edit form
        fields = [
            ("Loan Amount", "number", l["loan_amount"], None),
            ("Interest Rate", "rate", rate, None),
            ("Interest Method", "combo", mth,
             [("Simple Interest", "SIMPLE"), ("Compound Interest", "COMPOUND")]),
            ("Due Date", "date", l.get("due_date"), None),
            ("Description", "text", l.get("description"), None),
        ]

        def _make_save(_lid=lid):
            def _save(data):
                if not self._verify_edit():
                    return
                self.db.execute(
                    "UPDATE loans SET loan_amount=?, interest_rate=?, interest_method=?, due_date=?, description=? WHERE loan_id=?",
                    (data["Loan Amount"], data["Interest Rate"], data["Interest Method"],
                     data["Due Date"], data["Description"], _lid))
                loan = self.repos["loans"].get_loan(_lid)
                if loan and loan.get("trxn_id"):
                    self.db.execute("UPDATE transactions SET amount=? WHERE id=?",
                                   (data["Loan Amount"], loan["trxn_id"]))
                self.db.commit()
                self.repos["loans"].recalc_status(_lid)
                self.db.execute("UPDATE loans SET updated_at=? WHERE loan_id=?", (TODAY(), _lid))
                self.db.commit()
                self._loaded = False
                self.load_list(force=True)
                self._notify_data_changed()
            return _save

        edit_form = _build_edit_form(fields, _make_save(), lambda: None, accent_color=color)
        edit_btn = QPushButton("\u270f\ufe0f Edit Details")
        edit_btn.setFixedHeight(28)
        edit_btn.setFocusPolicy(Qt.NoFocus)
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        edit_btn.setStyleSheet(_accent_btn_css(color))
        edit_btn.clicked.connect(lambda _, ef=edit_form: ef.setVisible(not ef.isVisible()))
        if l["status"] not in ("CLOSED",):
            card.add_expand_widget(edit_btn)
            card.add_expand_widget(edit_form)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background:{C['border2']};")
        card.add_expand_widget(div)

        # Repayments
        rep_header = QLabel("\U0001f4b0 Repayment History")
        rep_header.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};padding-top:2px;")
        card.add_expand_widget(rep_header)

        def _make_rep_edit(_lid=lid):
            def _on_rep_edit(rep_data):
                def _save(data):
                    if not self._verify_edit():
                        return
                    self.db.execute(
                        "UPDATE repayments SET amount_paid=?, payment_date=?, description=? WHERE repayment_id=?",
                        (data["amount"], data["date"], data["description"], rep_data["repayment_id"]))
                    if rep_data.get("linked_txn_id"):
                        self.db.execute("UPDATE transactions SET amount=?, tx_date=? WHERE id=?",
                                       (data["amount"], data["date"], rep_data["linked_txn_id"]))
                    self.db.commit()
                    self.repos["loans"].recalc_status(_lid)
                    self.db.execute("UPDATE loans SET updated_at=? WHERE loan_id=?", (TODAY(), _lid))
                    self.db.commit()
                    self._loaded = False
                    self.load_list(force=True)
                    self._notify_data_changed()
                return _save
            return _on_rep_edit

        repayments = self._repay_map.get(lid, [])
        rep_section = _repayment_section(
            repayments, "amount_paid", "payment_date",
            accent_color=color,
            on_edit=_make_rep_edit() if l["status"] not in ("CLOSED",) else None
        )
        card.add_expand_widget(rep_section)

        # Mark as Closed for REPAID
        if l["status"] == "REPAID":
            close_btn = QPushButton("\u2705 Mark as Closed")
            close_btn.setFixedHeight(28)
            close_btn.setFocusPolicy(Qt.NoFocus)
            close_btn.setCursor(QCursor(Qt.PointingHandCursor))
            close_btn.setStyleSheet(
                f"QPushButton{{background:{C['green_bg']};color:{C['green']};"
                f"border:1.5px solid {C['green']};border-radius:8px;"
                f"padding:6px 14px;font-size:12px;font-weight:600;}}"
                f"QPushButton:hover{{background:{C['green']};color:white;}}")
            close_btn.clicked.connect(lambda _, _lid=lid: self._mark_closed_lg(_lid))
            card.add_expand_widget(close_btn)

        # Print
        def _make_print(_l=l, _a=a):
            def _print():
                info = [
                    ("Borrower", _l["borrower_name"]),
                    ("Principal", fmt_money(_l["loan_amount"])),
                    ("Rate", f"{_l.get('interest_rate') or 0}%"),
                    ("Method", _l.get("interest_method") or "SIMPLE"),
                    ("Start", _l["start_date"]),
                    ("Due", _l.get("due_date") or EM_DASH),
                ]
                analysis = [
                    ("Outstanding", fmt_money(_a["current_value"])),
                    ("Total Paid", fmt_money(_a["total_paid"])),
                    ("Interest Accrued", fmt_money(_a["total_interest_accrued"])),
                ]
                reps = self.repos["loans"].get_repayments(_l["loan_id"])
                sections = []
                if reps:
                    rdata = [{"date": r.get("payment_date", ""), "amount": r["amount_paid"],
                              "description": r.get("description") or ""} for r in reps]
                    sections.append({"title": "Repayment Log", "color": "#059669",
                                     "type": "repayment", "data": rdata})
                _export_detail_to_pdf(self, f"Loan to {_l['borrower_name']}", _l["status"],
                                      info, analysis, sections)
            return _print

        btn_row = QHBoxLayout()
        print_btn = QPushButton("\U0001f5a8 Print PDF")
        print_btn.setFixedHeight(28)
        print_btn.setFocusPolicy(Qt.NoFocus)
        print_btn.setCursor(QCursor(Qt.PointingHandCursor))
        print_btn.setStyleSheet(_accent_btn_css(color))
        print_btn.clicked.connect(_make_print())
        btn_row.addWidget(print_btn)
        btn_row.addStretch()
        card.add_expand_layout(btn_row)

        return card

    def _render_next_batch(self):
        """Build next batch of cards from pre-computed _pending_items."""
        if not hasattr(self, '_pending_items') or not self._pending_items:
            return
        batch_size = self._get_batch_size()
        batch = self._pending_items[:batch_size]
        self._pending_items = self._pending_items[batch_size:]
        for l, a in batch:
            self._list_lay.addWidget(self._build_lg_card(l, a))

    def load_list(self, force=False):
        if self._loaded and not force:
            return
        self._loaded = True
        self.db.execute("UPDATE loans SET status='CLOSED' WHERE status='CLEARED'")
        self.repos["loans"].sync_overdue()
        loans = self.repos["loans"].list_loans()
        # Batch: single query for all totals
        ids = [l["loan_id"] for l in loans]
        repaid_map = self._batch_sum("repayments", "loan_id", "amount_paid", ids)
        # Batch status recalc using CASE WHEN (single UPDATE)
        today_str = date.today().isoformat()
        case_parts, case_ids = [], []
        for l in loans:
            if l["status"] == "CLOSED":
                continue
            total = repaid_map.get(l["loan_id"], 0)
            due = l.get("due_date")
            if total >= l["loan_amount"]:
                new_status = "REPAID"
            elif due and due < today_str:
                new_status = "OVERDUE"
            elif total > 0:
                new_status = "PARTIALLY_PAID"
            else:
                new_status = "ACTIVE"
            if l["status"] != new_status:
                case_parts.append("WHEN loan_id=? THEN ?")
                case_ids.extend([l["loan_id"], new_status])
        if case_parts:
            phs = " ".join(case_parts)
            where_ids = [case_ids[i] for i in range(0, len(case_ids), 2)]
            self.db.execute(
                f"UPDATE loans SET status=CASE {phs} ELSE status END WHERE loan_id IN ({','.join(['?']*len(where_ids))})",
                case_ids + where_ids)
            self.db.commit()
        # Store for _render_list (no second list_loans call)
        self._list_data = loans
        self._repaid_map = repaid_map
        self._render_list()

    def _mark_closed_lg(self, loan_id):
        if _confirm(self, "Mark Closed", "Confirm: mark this loan as CLOSED?"):
            self.repos["loans"].update_status(loan_id, "CLOSED")
            self._loaded = False
            self.load_list()

    def _print_pending(self):
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


# ══════════════════════════════════════════════════════════════════════════
#  LOANS I TAKE
# ══════════════════════════════════════════════════════════════════════════
class LoansTakePage(_FunctionPage):
    ICON = "\U0001f3db\ufe0f"
    TITLE = "Money Borrowed"

    _FREQ_LABELS = ["Annual", "Quarterly", "Semi-Annual"]
    _FREQ_VALUES = ["ANNUAL", "QUARTERLY", "SEMI_ANNUAL"]

    def _sort_options(self):
        return ["Status", "Lender", "Amount", "Due Date"]

    def _loan_months(self, loan):
        sd = date.fromisoformat(loan["start_date"])
        dd = loan.get("due_date")
        if dd:
            ed = date.fromisoformat(dd)
            return max(1, round((ed - sd).days / 30.44))
        return 12

    def _analysis(self, loan):
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

    # ── Entry ──
    def _build_entry(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.lt_stack, _ = _build_subnav(lay, ["Take Loan", "Log EMI Payment"])

        # Take Loan
        p1 = QWidget()
        f1 = QFormLayout(p1)
        self.lt_loan_lender = SearchableCombo(placeholder="Search lender\u2026")
        self.lt_emi_type = QComboBox()
        self.lt_emi_type.addItems(["EMI Loan (fixed monthly)", "Flexible Repayment (variable)"])
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

        # Log EMI Payment
        p2 = QWidget()
        f2 = QFormLayout(p2)
        self.lt_rep_loan = SearchableCombo(placeholder="Search loan\u2026")
        self.lt_rep_info_lbl = QLabel("")
        self.lt_rep_info_lbl.setStyleSheet(f"color:{C['text3']};font-weight:600;font-size:11px;")
        self.lt_rep_info_lbl.setWordWrap(True)
        self.lt_rep_loan.currentIndexChanged.connect(self._on_rep_loan_changed)
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
        is_compound = self.lt_loan_method_type.currentIndex() == 1
        self.lt_loan_freq.setEnabled(is_compound)
        self._update_emi()

    def _toggle_emi_type(self):
        is_emi = self.lt_emi_type.currentIndex() == 0
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
        else:
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
            description=f"Loan taken from {lender_name}", category_names=("Finance", "Other"),
            transaction_kind="LOAN_TAKEN"
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
        self._loaded = False
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
            category_names=("Finance", "Other"), transaction_kind="EMI_PAYMENT"
        )
        self.repos["borrowed"].add_repayment(
            loan_id=lid, amount_paid=amount,
            payment_date=self.lt_rep_date.date().toString("yyyy-MM-dd"),
            payment_method=method, description=self.lt_rep_desc.text().strip() or None,
            linked_txn_id=txn_id
        )
        self.lt_rep_desc.clear()
        self._refresh_entry_dropdowns()
        self._loaded = False
        self.load_list()
        loan = self.repos["borrowed"].get_loan(lid)
        if loan and loan["status"] == "REPAID":
            QMessageBox.information(self, "Loan Fully Repaid",
                "This loan has been fully repaid.\nStatus: REPAID \u2014 waiting for closure confirmation.")
        else:
            QMessageBox.information(self, "Payment Logged", f"{desc_extra} payment recorded successfully.")

    # ── List ──
    def load_list(self, force=False):
        if self._loaded and not force:
            return
        self._loaded = True
        self.repos["borrowed"].sync_overdue()
        loans = self.repos["borrowed"].list_loans()
        # Batch recalc
        ids = [l["loan_id"] for l in loans]
        repaid_map = self._batch_sum("borrowed_loan_repayments", "loan_id", "amount_paid", ids)
        today_str = date.today().isoformat()
        # Pre-fetch repayments for non-EMI analysis
        repay_map = self._batch_query("borrowed_loan_repayments", "loan_id", ids)
        for l in loans:
            if l["status"] == "CLOSED":
                continue
            total = repaid_map.get(l["loan_id"], 0)
            due = l.get("due_date")
            emi_type = l.get("emi_type") or "EMI"
            rate = l.get("interest_rate") or 0
            if emi_type == "NON_EMI":
                if rate > 0 and total > 0:
                    # Non-EMI with interest: use analysis for accurate outstanding
                    method = l.get("interest_method") or "SIMPLE"
                    payments = repay_map.get(l["loan_id"], [])
                    from services.loan_service import LoanService as _LS
                    a = _LS.non_emi_analysis(
                        l["principal_amount"], rate, total, l["start_date"],
                        payments=payments, method=method)
                    fully_paid = a["current_value"] <= 0
                else:
                    # Non-EMI zero-interest: simple principal check
                    fully_paid = total >= l["principal_amount"]
            else:
                # EMI: simple principal check (EMI analysis handles interest via schedule)
                fully_paid = total >= l["principal_amount"]
            if fully_paid and total > 0:
                new_status = "REPAID"
            elif due and due < today_str:
                new_status = "OVERDUE"
            elif total > 0:
                new_status = "PARTIALLY_PAID"
            else:
                new_status = "ACTIVE"
            if l["status"] != new_status:
                self.db.execute("UPDATE borrowed_loans SET status=? WHERE loan_id=?",
                                (new_status, l["loan_id"]))
        self.db.commit()
        self._list_data = self.repos["borrowed"].list_loans()
        self._render_list()

    def _render_list(self):
        if not hasattr(self, "_list_lay"):
            return
        _clear_layout(self._stats_row)
        _clear_layout(self._list_lay)
        loans = list(self._list_data)

        # Batch queries
        lt_ids = [l["loan_id"] for l in loans]
        self._lt_repaid = self._batch_sum("borrowed_loan_repayments", "loan_id", "amount_paid", lt_ids)
        self._lt_repay = self._batch_query("borrowed_loan_repayments", "loan_id", lt_ids)

        # KPI
        active = [l for l in loans if l["status"] != "CLOSED"]
        total_outstanding = 0
        for l in active:
            total_paid = self._lt_repaid.get(l["loan_id"], 0)
            emi_type = l.get("emi_type") or "EMI"
            if emi_type == "NON_EMI":
                payments = self._lt_repay.get(l["loan_id"], [])
                a = LoanService.non_emi_analysis(
                    l["principal_amount"], l["interest_rate"] or 0,
                    total_paid, l["start_date"], payments=payments,
                    method=l.get("interest_method") or "SIMPLE")
            else:
                months = self._loan_months(l)
                a = LoanService.loan_analysis(
                    l["principal_amount"], l["interest_rate"] or 0,
                    months, l.get("interest_type") or "ANNUAL",
                    total_paid, l["start_date"],
                    method=l.get("interest_method") or "COMPOUND")
            total_outstanding += a["current_value"]
        _fill_stats_row(self._stats_row, [
            _metric_card("Total Outstanding", fmt_money(total_outstanding), C["amber"]),
            _metric_card("Active Loans", str(len(active))),
            _metric_card("Total Loans", str(self.repos["borrowed"].count_total())),
        ])

        # Alerts
        today_str = date.today().isoformat()
        soon_str = _add_months(date.today(), 1).isoformat()
        alerts = []
        for l in active:
            due = l.get("due_date")
            a2 = None
            total_paid = self._lt_repaid.get(l["loan_id"], 0)
            emi_type = l.get("emi_type") or "EMI"
            if emi_type == "NON_EMI":
                payments = self._lt_repay.get(l["loan_id"], [])
                a2 = LoanService.non_emi_analysis(
                    l["principal_amount"], l["interest_rate"] or 0,
                    total_paid, l["start_date"], payments=payments,
                    method=l.get("interest_method") or "SIMPLE")
            else:
                months = self._loan_months(l)
                a2 = LoanService.loan_analysis(
                    l["principal_amount"], l["interest_rate"] or 0,
                    months, l.get("interest_type") or "ANNUAL",
                    total_paid, l["start_date"],
                    method=l.get("interest_method") or "COMPOUND")
            if l["status"] == "OVERDUE":
                alerts.append(f"\u26a0\ufe0f {l['lender_name']} \u2014 OVERDUE \u2014 Outstanding: {fmt_money(a2['current_value'])}")
            elif due and today_str <= due <= soon_str and a2.get("original_emi", 0) > 0:
                alerts.append(f"\U0001f514 {l['lender_name']} \u2014 EMI due {due} \u2014 {fmt_money(a2['original_emi'])}")
        if alerts:
            alert_box = QFrame()
            alert_box.setStyleSheet(
                f"QFrame{{background:{C['amber_bg']};border:1px solid {C['amber']};border-radius:8px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            al = QVBoxLayout(alert_box)
            al.setContentsMargins(12, 8, 12, 8); al.setSpacing(2)
            for a_txt in alerts:
                al.addWidget(QLabel(a_txt))
            self._list_lay.addWidget(alert_box)

        # Filter & sort
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

        # Pre-compute analysis (no widget creation)
        self._all_items = []
        for l in loans:
            total_paid = self._lt_repaid.get(l["loan_id"], 0)
            emi_type = l.get("emi_type") or "EMI"
            if emi_type == "NON_EMI":
                payments = self._lt_repay.get(l["loan_id"], [])
                a = LoanService.non_emi_analysis(
                    l["principal_amount"], l["interest_rate"] or 0,
                    total_paid, l["start_date"], payments=payments,
                    method=l.get("interest_method") or "SIMPLE")
            else:
                months = self._loan_months(l)
                a = LoanService.loan_analysis(
                    l["principal_amount"], l["interest_rate"] or 0,
                    months, l.get("interest_type") or "ANNUAL",
                    total_paid, l["start_date"],
                    method=l.get("interest_method") or "COMPOUND")
            self._all_items.append((l, a))

        # Build first batch only
        batch_size = self._get_batch_size()
        first = self._all_items[:batch_size]
        self._pending_items = self._all_items[batch_size:]
        for l, a in first:
            self._list_lay.addWidget(self._build_lt_card(l, a))
        if self._pending_items:
            self._init_lazy_scroll()

    def _build_lt_card(self, l, a):
        """Build a single Money Borrowed card from pre-computed data."""
        color = status_color(l["status"])
        mth = l.get("interest_method") or "COMPOUND"
        mth_tag = "SI" if mth == "SIMPLE" else "CI"
        freq_tag = l.get("interest_type") or "ANNUAL"
        freq_short = {"ANNUAL": "Ann", "QUARTERLY": "Qtr", "SEMI_ANNUAL": "Semi"}.get(freq_tag, "")
        ci_extra = f" {freq_short}" if mth == "COMPOUND" else ""
        emi_type = l.get("emi_type") or "EMI"
        emi_str = f"EMI {fmt_money(a['original_emi'])}" if emi_type == "EMI" else "Flexible Repayment"
        sub = (f"Rate {l['interest_rate']}% {mth_tag}{ci_extra} {MDOT} "
               f"{emi_str} {MDOT} Due {l['due_date'] or EM_DASH}")
        pct = (a["total_paid"] / a["total_expected"] * 100) if a["total_expected"] else 0
        extra = (f"<span style='font-size:15px;font-weight:800;color:{C['text']};'>"
                 f"{fmt_money(a['current_value'])}</span>  "
                 f"<span style='font-size:11px;color:{C['text3']};'>Outstanding</span><br>"
                 f"<span style='font-size:11px;color:{C['text3']};'>"
                 f"Updated EMI: {fmt_money(a['updated_emi'])}  {MDOT}  "
                 f"Paid: {fmt_money(a['total_paid'])}  {MDOT}  "
                 f"Interest: {fmt_money(a['total_interest_accrued'])}</span>")
        card = WealthCard(
            item_id=l["loan_id"], title=l["lender_name"], subtitle=sub,
            amount_text=fmt_money(l["principal_amount"]) + "  Principal",
            badge_text=l["status"], badge_color=color,
            progress_pct=pct, extra_line=extra,
            updated=bool(l.get("updated_at")))
        card.clicked.connect(self._toggle_card)
        lid = l["loan_id"]

        # Detail info
        mth_label = "Simple" if mth == "SIMPLE" else f"Compound ({freq_tag})"
        detail_info = QLabel()
        detail_info.setTextFormat(Qt.RichText)
        detail_info.setText(
            f"<table style='font-size:13px;color:{C['text2']};' cellpadding='3'>"
            f"<tr><td style='color:{C['text3']};font-weight:600;'>Method</td>"
            f"<td style='font-weight:700;color:{C['text']};'>{mth_label}</td>"
            f"<td style='color:{C['text3']};font-weight:600;padding-left:16px;'>Start</td>"
            f"<td style='font-weight:700;color:{C['text']};'>{l['start_date']}</td></tr>"
            f"<tr><td style='color:{C['text3']};font-weight:600;'>Due Date</td>"
            f"<td style='font-weight:700;color:{C['text']};'>{l['due_date'] or EM_DASH}</td>"
            f"<td style='color:{C['text3']};font-weight:600;padding-left:16px;'>Outstanding</td>"
            f"<td style='font-weight:800;color:{color};'>{fmt_money(a['current_value'])}</td></tr>"
            f"<tr><td style='color:{C['text3']};font-weight:600;'>Total Expected</td>"
            f"<td style='font-weight:700;color:{C['text']};'>{fmt_money(a['total_expected'])}</td>"
            f"<td style='color:{C['text3']};font-weight:600;padding-left:16px;'>Interest</td>"
            f"<td style='font-weight:700;color:{C['text']};'>{fmt_money(a['total_interest_accrued'])}</td></tr>"
            f"</table>"
            + (f"<div style='font-size:12px;color:{C['text3']};font-style:italic;padding-top:4px;'>Note: {l['description']}</div>" if l.get("description") else ""))
        detail_info.setWordWrap(True)
        card.add_expand_widget(detail_info)

        # Edit form
        fields = [
            ("Principal", "number", l["principal_amount"], None),
            ("Interest Rate", "rate", l.get("interest_rate") or 0, None),
            ("Interest Method", "combo", l.get("interest_method") or "COMPOUND",
             [("Simple Interest", "SIMPLE"), ("Compound Interest", "COMPOUND")]),
            ("Due Date", "date", l.get("due_date"), None),
            ("Description", "text", l.get("description"), None),
        ]
        def _make_save(_lid=lid, _l=l):
            def _save(data):
                if not self._verify_edit():
                    return
                emi_type_inner = _l.get("emi_type") or "EMI"
                kw = {"principal_amount": data["Principal"], "interest_rate": data["Interest Rate"],
                      "interest_method": data["Interest Method"], "due_date": data["Due Date"],
                      "description": data["Description"]}
                if emi_type_inner == "EMI":
                    freq = _l.get("interest_type") or "ANNUAL"
                    kw["emi_amount"] = LoanService.emi(data["Principal"], data["Interest Rate"],
                                                       self._loan_months(_l), freq, data["Interest Method"])
                sets = ", ".join(f"{k}=?" for k in kw)
                self.db.execute(f"UPDATE borrowed_loans SET {sets} WHERE loan_id=?", list(kw.values()) + [_lid])
                loan = self.repos["borrowed"].get_loan(_lid)
                if loan and loan.get("linked_txn_id"):
                    self.db.execute("UPDATE transactions SET amount=? WHERE id=?", (data["Principal"], loan["linked_txn_id"]))
                self.db.commit()
                self.repos["borrowed"].recalc_status(_lid)
                self.db.execute("UPDATE borrowed_loans SET updated_at=? WHERE loan_id=?", (TODAY(), _lid))
                self.db.commit()
                self._loaded = False
                self.load_list(force=True)
                self._notify_data_changed()
            return _save
        edit_form = _build_edit_form(fields, _make_save(), lambda: None, accent_color=color)
        edit_btn = QPushButton("\u270f\ufe0f Edit Details")
        edit_btn.setFixedHeight(28); edit_btn.setFocusPolicy(Qt.NoFocus)
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        edit_btn.setStyleSheet(_accent_btn_css(color))
        edit_btn.clicked.connect(lambda _, ef=edit_form: ef.setVisible(not ef.isVisible()))
        if l["status"] not in ("CLOSED",):
            card.add_expand_widget(edit_btn); card.add_expand_widget(edit_form)

        div = QFrame(); div.setFixedHeight(1); div.setStyleSheet(f"background:{C['border2']};")
        card.add_expand_widget(div)

        rep_header = QLabel("\U0001f4b0 Repayment History")
        rep_header.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};padding-top:2px;")
        card.add_expand_widget(rep_header)

        def _make_rep_edit(_lid=lid):
            def _on_rep_edit(rep_data):
                def _save(data):
                    if not self._verify_edit():
                        return
                    self.db.execute("UPDATE borrowed_loan_repayments SET amount_paid=?, payment_date=?, description=? WHERE repayment_id=?",
                                   (data["amount"], data["date"], data["description"], rep_data["repayment_id"]))
                    if rep_data.get("linked_txn_id"):
                        self.db.execute("UPDATE transactions SET amount=?, tx_date=? WHERE id=?", (data["amount"], data["date"], rep_data["linked_txn_id"]))
                    self.db.commit()
                    self.repos["borrowed"].recalc_status(_lid)
                    self.db.execute("UPDATE borrowed_loans SET updated_at=? WHERE loan_id=?", (TODAY(), _lid))
                    self.db.commit()
                    self._loaded = False
                    self.load_list(force=True)
                    self._notify_data_changed()
                return _save
            return _on_rep_edit
        repayments = self._lt_repay.get(lid, [])
        card.add_expand_widget(_repayment_section(repayments, "amount_paid", "payment_date",
                                                   accent_color=color,
                                                   on_edit=_make_rep_edit() if l["status"] not in ("CLOSED",) else None))

        if l["status"] == "REPAID":
            close_btn = QPushButton("\u2705 Mark as Closed")
            close_btn.setFixedHeight(28); close_btn.setFocusPolicy(Qt.NoFocus)
            close_btn.setCursor(QCursor(Qt.PointingHandCursor))
            close_btn.setStyleSheet(f"QPushButton{{background:{C['green_bg']};color:{C['green']};border:1.5px solid {C['green']};border-radius:8px;padding:6px 14px;font-size:12px;font-weight:600;}}QPushButton:hover{{background:{C['green']};color:white;}}")
            close_btn.clicked.connect(lambda _, _lid=lid: self._mark_closed(_lid))
            card.add_expand_widget(close_btn)

        def _make_print(_l=l, _a=a):
            def _print():
                reps = self.repos["borrowed"].get_repayments(_l["loan_id"])
                mthd = _l.get("interest_method") or "COMPOUND"
                freq = _l.get("interest_type") or "ANNUAL"
                info = [("Lender", _l["lender_name"]), ("Principal", fmt_money(_l["principal_amount"])),
                        ("Rate", f"{_l['interest_rate']}%"), ("Method", "Simple" if mthd == "SIMPLE" else f"Compound ({freq})"),
                        ("Start", _l["start_date"]), ("Due", _l.get("due_date") or EM_DASH)]
                if emi_type == "EMI": info.insert(4, ("EMI", fmt_money(_a["original_emi"])))
                analysis = [("Outstanding", fmt_money(_a["current_value"])), ("Total Paid", fmt_money(_a["total_paid"])),
                            ("Interest Accrued", fmt_money(_a["total_interest_accrued"]))]
                sections = []
                if reps:
                    rdata = [{"date": r.get("payment_date", ""), "amount": r["amount_paid"], "description": r.get("description") or ""} for r in reps]
                    sections.append({"title": "Repayment Log", "color": "#059669", "type": "repayment", "data": rdata})
                _export_detail_to_pdf(self, f"Loan from {_l['lender_name']}", _l["status"], info, analysis, sections)
            return _print
        btn_row = QHBoxLayout()
        print_btn = QPushButton("\U0001f5a8 Print PDF")
        print_btn.setFixedHeight(28); print_btn.setFocusPolicy(Qt.NoFocus)
        print_btn.setCursor(QCursor(Qt.PointingHandCursor))
        print_btn.setStyleSheet(_accent_btn_css(color))
        print_btn.clicked.connect(_make_print())
        btn_row.addWidget(print_btn); btn_row.addStretch()
        card.add_expand_layout(btn_row)
        return card

    def _render_next_batch(self):
        if not hasattr(self, '_pending_items') or not self._pending_items:
            return
        batch_size = self._get_batch_size()
        batch = self._pending_items[:batch_size]
        self._pending_items = self._pending_items[batch_size:]
        for l, a in batch:
            self._list_lay.addWidget(self._build_lt_card(l, a))

    def _mark_closed(self, loan_id):
        if _confirm(self, "Mark Closed", "Confirm: mark this loan as CLOSED?"):
            self.repos["borrowed"].update_status(loan_id, "CLOSED")
            self._loaded = False
            self.load_list()


class FDGivePage(_FunctionPage):
    ICON = "\U0001f3e6"
    TITLE = "My Fixed Deposits"

    def _sort_options(self):
        return ["Status", "Account", "Maturity Date"]

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
            description=f"FD deposit at {account_name}", category_names=("Investment", "Finance"),
            transaction_kind="FD_DEPOSIT"
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
        self._loaded = False
        self.load_list()
        QMessageBox.information(self, "FD Created", "Fixed deposit recorded successfully.")

    # ── List ──
    def load_list(self, force=False):
        if self._loaded and not force:
            return
        self._loaded = True
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
        rank = {"ACTIVE": 0, "MATURED": 1, "WITHDRAWN": 2, "PREMATURE_WITHDRAWN": 3}
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
        all_cards = []
        for fd in fds:
            pct = FDService.progress(fd["start_date"], fd["maturity_date"])
            color = status_color(fd["status"])
            extra = (f"<span style='font-size:15px;font-weight:800;color:{C['text']};'>"
                     f"{fmt_money(fd['maturity_amount'] or fd['principal_amount'])}</span>  "
                     f"<span style='font-size:11px;color:{C['text3']};'>Maturity Value</span><br>"
                     f"<span style='font-size:11px;color:{C['text3']};'>"
                     f"{pct:.0f}% elapsed</span>")
            card = WealthCard(
                item_id=fd["fd_id"],
                title=fd["account_name"] or "Fixed Deposit",
                subtitle=f"{fd['interest_rate']}% {MDOT} {fd['start_date']} \u2192 {fd['maturity_date']}",
                amount_text=fmt_money(fd["principal_amount"]) + "  Principal",
                badge_text=fd["status"], badge_color=color, progress_pct=pct,
                extra_line=extra,
                updated=_is_updated(fd),
            )
            card.clicked.connect(self._toggle_card)

            fid = fd["fd_id"]

            # Detail info
            mthd = fd.get("interest_method") or "COMPOUND"
            freq = fd.get("interest_type") or "QUARTERLY"
            mth_label = "Simple" if mthd == "SIMPLE" else f"Compound ({freq})"
            detail_info = QLabel()
            detail_info.setTextFormat(Qt.RichText)
            detail_info.setText(
                f"<table style='font-size:13px;color:{C['text2']};' cellpadding='3'>"
                f"<tr><td style='color:{C['text3']};font-weight:600;'>Method</td>"
                f"<td style='font-weight:700;color:{C['text']};'>{mth_label}</td>"
                f"<td style='color:{C['text3']};font-weight:600;padding-left:16px;'>Rate</td>"
                f"<td style='font-weight:700;color:{C['text']};'>{fd['interest_rate']}%</td></tr>"
                f"<tr><td style='color:{C['text3']};font-weight:600;'>Start</td>"
                f"<td style='font-weight:700;color:{C['text']};'>{fd['start_date']}</td>"
                f"<td style='color:{C['text3']};font-weight:600;padding-left:16px;'>Maturity</td>"
                f"<td style='font-weight:700;color:{C['text']};'>{fd['maturity_date']}</td></tr>"
                f"<tr><td style='color:{C['text3']};font-weight:600;'>Maturity Amt</td>"
                f"<td style='font-weight:800;color:{color};'>{fmt_money(fd['maturity_amount'] or 0)}</td></tr>"
                f"</table>"
            )
            detail_info.setWordWrap(True)
            card.add_expand_widget(detail_info)

            # Edit form (skip for withdrawn)
            fields = [
                ("Principal", "number", fd["principal_amount"], None),
                ("Interest Rate", "rate", fd.get("interest_rate") or 0, None),
                ("Start Date", "date", fd.get("start_date"), None),
                ("Maturity Date", "date", fd.get("maturity_date"), None),
            ]

            def _make_fd_save(_fid):
                def _save(data):
                    if not self._verify_edit():
                        return
                    # Recalculate maturity amount
                    p = data["Principal"]
                    r = data["Interest Rate"]
                    sd = data["Start Date"]
                    md = data["Maturity Date"]
                    mthd = fd.get("interest_method") or "COMPOUND"
                    freq = fd.get("interest_type") or "QUARTERLY"
                    if mthd == "SIMPLE":
                        from datetime import datetime as _dt
                        years = (_dt.strptime(md, "%Y-%m-%d") - _dt.strptime(sd, "%Y-%m-%d")).days / 365.25
                        mat_amt = round(p * (1 + r / 100 * years), 2)
                    else:
                        mat_amt = FDService.maturity(p, r, sd, md, freq)
                    self.db.execute(
                        "UPDATE fixed_deposits SET principal_amount=?, interest_rate=?, start_date=?, maturity_date=?, maturity_amount=? WHERE fd_id=?",
                        (p, r, sd, md, mat_amt, _fid))
                    fd_rec = self.repos["fd"].get(_fid)
                    if fd_rec and fd_rec.get("linked_txn_id"):
                        self.db.execute("UPDATE transactions SET amount=? WHERE id=?",
                                       (data["Principal"], fd_rec["linked_txn_id"]))
                    self.db.commit()
                    self.db.execute("UPDATE fixed_deposits SET updated_at=? WHERE fd_id=?", (TODAY(), _fid))
                    self.db.commit()
                    self._loaded = False
                    self.load_list(force=True)
                    self._notify_data_changed()
                return _save

            edit_form = _build_edit_form(fields, _make_fd_save(fid), lambda: None,
                                         accent_color=color)
            edit_btn = QPushButton("\u270f\ufe0f Edit Details")
            edit_btn.setFixedHeight(28)
            edit_btn.setFocusPolicy(Qt.NoFocus)
            edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
            edit_btn.setStyleSheet(_accent_btn_css(color))
            edit_btn.clicked.connect(lambda _, ef=edit_form: ef.setVisible(not ef.isVisible()))
            if fd["status"] not in ("WITHDRAWN", "PREMATURE_WITHDRAWN"):
                card.add_expand_widget(edit_btn)
                card.add_expand_widget(edit_form)

            # Action buttons
            btn_row = QHBoxLayout()
            if fd["status"] == "ACTIVE" and pct >= 100:
                m_btn = QPushButton("\u2705 Mark Matured")
                m_btn.setObjectName("primary")
                m_btn.setFixedHeight(28)
                m_btn.setFocusPolicy(Qt.NoFocus)
                m_btn.setCursor(QCursor(Qt.PointingHandCursor))
                m_btn.clicked.connect(lambda _, _fid=fid: self._mark_matured(_fid))
                btn_row.addWidget(m_btn)
            if fd["status"] in ("ACTIVE", "MATURED"):
                w_btn = QPushButton("\U0001f4b5 Mark Withdrawn")
                w_btn.setFixedHeight(28)
                w_btn.setFocusPolicy(Qt.NoFocus)
                w_btn.setCursor(QCursor(Qt.PointingHandCursor))
                w_btn.setStyleSheet(_accent_btn_css(color))
                w_btn.clicked.connect(lambda _, _fid=fid: self._mark_withdrawn(_fid))
                btn_row.addWidget(w_btn)
            btn_row.addStretch()
            card.add_expand_layout(btn_row)

            all_cards.append(card)

        # Cache

        # Lazy loading
        if all_cards:
            first_batch = all_cards[:self._get_batch_size()]
            self._pending_cards = all_cards[self._get_batch_size():]
            for c in first_batch:
                self._list_lay.addWidget(c)
            if self._pending_cards:
                self._init_lazy_scroll()

    def _mark_matured(self, fd_id):
        if _confirm(self, "Mark Matured", "Mark this FD as matured?"):
            self.repos["fd"].update_status(fd_id, "MATURED")
            self._loaded = False
            self.load_list()

    def _mark_withdrawn(self, fd_id):
        fd = self.repos["fd"].get(fd_id)
        if not fd:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Withdraw FD")
        dlg.setMinimumWidth(420)
        f = QFormLayout(dlg)
        acc_cb = _account_combo(self.repos["accounts"])
        idx = acc_cb.findData(fd["bank_account_id"])
        if idx >= 0:
            acc_cb.setCurrentIndex(idx)
        method_cb = _method_combo(self.repos["lookups"])
        wd_date = QDateEdit(QDate.currentDate())
        wd_date.setCalendarPopup(True)
        fee_spin = QDoubleSpinBox()
        fee_spin.setRange(0, 999999)
        fee_spin.setPrefix("\u20b9 ")
        fee_spin.setDecimals(2)
        net_lbl = QLabel("")
        net_lbl.setStyleSheet(f"color:{C['green']};font-weight:800;font-size:13px;")
        net_lbl.setWordWrap(True)

        def update_net():
            wd = wd_date.date().toPyDate()
            sd = date.fromisoformat(fd["start_date"])
            days = max((wd - sd).days, 0)
            p = fd["principal_amount"]
            r = fd["interest_rate"] or 0
            freq = fd.get("interest_type") or "QUARTERLY"
            mthd = fd.get("interest_method") or "COMPOUND"
            if mthd == "SIMPLE":
                interest = round(p * r / 100 * days / 365.25, 2)
            else:
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
            sd = date.fromisoformat(fd["start_date"])
            days = max((wd - sd).days, 0)
            p = fd["principal_amount"]
            r = fd["interest_rate"] or 0
            freq = fd.get("interest_type") or "QUARTERLY"
            mthd = fd.get("interest_method") or "COMPOUND"
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
            _log_ledger_txn(
            self.repos["transactions"], self.db, account_id=acc_cb.currentData(),
                pay_method=method_cb.currentData(), tx_type="CREDIT", amount=net, person_org=None,
                description="FD premature withdrawal" + (f" (fee: {fmt_money(fee)})" if fee > 0 else ""),
                category_names=("Investment", "Finance"), transaction_kind="FD_WITHDRAWAL"
            )
            self.repos["fd"].update_status(fd_id, "PREMATURE_WITHDRAWN")
            self._loaded = False
            self.load_list()


# ══════════════════════════════════════════════════════════════════════════
#  FD OTHERS DEPOSIT
# ══════════════════════════════════════════════════════════════════════════
class FDOthersPage(_FunctionPage):
    ICON = "\U0001f9fe"
    TITLE = "Deposits Received"

    def _sort_options(self):
        return ["Status", "Depositor", "Amount", "Return Date"]

    def _build_entry(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.fo_stack, _ = _build_subnav(lay, ["Record Deposit", "Log Repayment"])

        # Record Deposit
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

        # Log Repayment
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
            description=f"Deposit received from {name}", category_names=("Finance", "Other"),
            transaction_kind="DEPOSIT_RECEIVED"
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
        self._loaded = False
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
            category_names=("Finance", "Other"), transaction_kind="DEPOSIT_REPAYMENT"
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
        self._loaded = False
        self.load_list()
        dep = self.repos["deposits"].get_deposit(did)
        if dep and dep["status"] == "REPAID":
            QMessageBox.information(self, "Deposit Fully Returned",
                "This deposit has been fully returned.\nStatus: REPAID \u2014 waiting for closure confirmation.")
        else:
            QMessageBox.information(self, "Repayment Logged", "Repayment recorded successfully.")

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

    def _dep_months(self, dep):
        sd = date.fromisoformat(dep["deposit_date"])
        dd = dep.get("expected_return_date")
        if dd:
            return max(1, round((date.fromisoformat(dd) - sd).days / 30.44))
        return 12

    # ── List ──
    def load_list(self, force=False):
        if self._loaded and not force:
            return
        self._loaded = True
        deps = self.repos["deposits"].list_deposits()
        # Batch recalc
        ids = [d["deposit_id"] for d in deps]
        repaid_map = self._batch_sum("deposit_repayments_to_others", "deposit_id", "amount_paid", ids)
        repay_map = self._batch_query("deposit_repayments_to_others", "deposit_id", ids)
        today_str = date.today().isoformat()
        for d in deps:
            if d["status"] == "CLOSED":
                continue
            total = repaid_map.get(d["deposit_id"], 0)
            return_date = d.get("expected_return_date")
            rate = d.get("interest_rate") or 0
            if not rate:
                fully_paid = total >= d["principal_amount"]
            else:
                # Interest-bearing: repaying the principal alone doesn't clear
                # the debt — the accrued interest is still outstanding.
                fully_paid = deposit_outstanding(
                    d, total, repay_map.get(d["deposit_id"], [])) <= 0
            if fully_paid and total > 0:
                new_status = "REPAID"
            elif return_date and return_date < today_str:
                new_status = "OVERDUE"
            elif total > 0:
                new_status = "PARTIALLY_PAID"
            else:
                new_status = "ACTIVE"
            if d["status"] != new_status:
                self.db.execute("UPDATE deposits_from_others SET status=? WHERE deposit_id=?",
                                (new_status, d["deposit_id"]))
        self.db.commit()
        self._list_data = self.repos["deposits"].list_deposits()
        self._render_list()

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

    def _render_list(self):
        if not hasattr(self, "_list_lay"):
            return
        _clear_layout(self._stats_row)
        _clear_layout(self._list_lay)
        deps = list(self._list_data)
        fo_ids = [d["deposit_id"] for d in deps]
        fo_repaid_map = self._batch_sum("deposit_repayments_to_others", "deposit_id", "amount_paid", fo_ids)
        fo_repay_map = self._batch_query("deposit_repayments_to_others", "deposit_id", fo_ids)
        active = [d for d in deps if d["status"] != "CLOSED"]
        total_outstanding = 0
        for d in active:
            total_paid = fo_repaid_map.get(d["deposit_id"], 0)
            rate = d.get("interest_rate") or 0
            if not rate:
                cv = max(d["principal_amount"] - total_paid, 0)
            else:
                # Use full analysis for interest-bearing deposits
                months = self._dep_months(d)
                payments = fo_repay_map.get(d["deposit_id"], [])
                a = LoanService.loan_analysis(
                    d["principal_amount"], rate, months, "ANNUAL",
                    total_paid, d["deposit_date"], payments=payments,
                    method=d.get("interest_method") or "SIMPLE"
                )
                cv = a["current_value"]
            total_outstanding += cv
        _fill_stats_row(self._stats_row, [
            _metric_card("Total Outstanding", fmt_money(total_outstanding), C["amber"]),
            _metric_card("Active Deposits", str(len(active))),
            _metric_card("Total Deposits", str(self.repos["deposits"].count_total())),
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
        all_cards = []
        for d in deps:
            a = self._analysis(d)
            pct = (a["total_paid"] / a["total_expected"] * 100) if a["total_expected"] else 0
            interest_free = not d["interest_rate"]
            color = status_color(d["status"])
            interest_tag = "Interest-Free" if interest_free else f"{d['interest_rate']}%"
            badge_text = f"{interest_tag} | {d['status']}"
            extra = (f"<span style='font-size:15px;font-weight:800;color:{C['text']};'>"
                     f"{fmt_money(a['current_value'])}</span>  "
                     f"<span style='font-size:11px;color:{C['text3']};'>Outstanding</span><br>"
                     f"<span style='font-size:11px;color:{C['text3']};'>"
                     f"Interest: {fmt_money(a['total_interest_accrued'])}  {MDOT}  "
                     f"Paid: {fmt_money(a['total_paid'])}</span>")
            card = WealthCard(
                item_id=d["deposit_id"],
                title=d["depositor_name"],
                subtitle=f"Deposited {d['deposit_date']} {MDOT} Return {d['expected_return_date'] or EM_DASH}",
                amount_text=fmt_money(d["principal_amount"]) + "  Principal",
                badge_text=badge_text, badge_color=color,
                progress_pct=pct, extra_line=extra,
                updated=_is_updated(d),
            )
            card.clicked.connect(self._toggle_card)
            did = d["deposit_id"]

            # Detail info
            mthd = d.get("interest_method") or "SIMPLE"
            mth_label = "Simple" if mthd == "SIMPLE" else "Compound"
            detail_info = QLabel()
            detail_info.setTextFormat(Qt.RichText)
            detail_info.setText(
                f"<table style='font-size:13px;color:{C['text2']};' cellpadding='3'>"
                f"<tr><td style='color:{C['text3']};font-weight:600;'>Method</td>"
                f"<td style='font-weight:700;color:{C['text']};'>{mth_label}</td>"
                f"<td style='color:{C['text3']};font-weight:600;padding-left:16px;'>Rate</td>"
                f"<td style='font-weight:700;color:{C['text']};'>{d.get('interest_rate') or 0}%</td></tr>"
                f"<tr><td style='color:{C['text3']};font-weight:600;'>Deposit</td>"
                f"<td style='font-weight:700;color:{C['text']};'>{d['deposit_date']}</td>"
                f"<td style='color:{C['text3']};font-weight:600;padding-left:16px;'>Return</td>"
                f"<td style='font-weight:700;color:{C['text']};'>{d['expected_return_date'] or EM_DASH}</td></tr>"
                f"<tr><td style='color:{C['text3']};font-weight:600;'>Outstanding</td>"
                f"<td style='font-weight:800;color:{color};'>{fmt_money(a['current_value'])}</td>"
                f"<td style='color:{C['text3']};font-weight:600;padding-left:16px;'>Total Expected</td>"
                f"<td style='font-weight:700;color:{C['text']};'>{fmt_money(a['total_expected'])}</td></tr>"
                f"</table>"
                + (f"<div style='font-size:12px;color:{C['text3']};font-style:italic;padding-top:4px;'>Note: {d['description']}</div>" if d.get("description") else "")
            )
            detail_info.setWordWrap(True)
            card.add_expand_widget(detail_info)

            # Edit form
            fields = [
                ("Principal", "number", d["principal_amount"], None),
                ("Interest Rate", "rate", d.get("interest_rate") or 0, None),
                ("Interest Method", "combo", d.get("interest_method") or "SIMPLE",
                 [("Simple Interest", "SIMPLE"), ("Compound Interest", "COMPOUND")]),
                ("Return Date", "date", d.get("expected_return_date"), None),
                ("Description", "text", d.get("description"), None),
            ]

            def _make_fo_save(_did, _d=d):
                def _save(data):
                    if not self._verify_edit():
                        return
                    rate = data["Interest Rate"] if _d.get("interest_rate") is not None else None
                    imethod = data["Interest Method"]
                    self.db.execute(
                        "UPDATE deposits_from_others SET principal_amount=?, interest_rate=?, interest_method=?, expected_return_date=?, description=? WHERE deposit_id=?",
                        (data["Principal"], rate, imethod, data["Return Date"], data["Description"], _did))
                    dep = self.repos["deposits"].get_deposit(_did)
                    if dep and dep.get("linked_txn_id"):
                        self.db.execute("UPDATE transactions SET amount=? WHERE id=?",
                                       (data["Principal"], dep["linked_txn_id"]))
                    self.db.commit()
                    self.repos["deposits"].recalc_status(_did)
                    self.db.execute("UPDATE deposits_from_others SET updated_at=? WHERE deposit_id=?", (TODAY(), _did))
                    self.db.commit()
                    self._loaded = False
                    self.load_list(force=True)
                    self._notify_data_changed()
                return _save

            edit_form = _build_edit_form(fields, _make_fo_save(did), lambda: None,
                                         accent_color=color)
            edit_btn = QPushButton("\u270f\ufe0f Edit Details")
            edit_btn.setFixedHeight(28)
            edit_btn.setFocusPolicy(Qt.NoFocus)
            edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
            edit_btn.setStyleSheet(_accent_btn_css(color))
            edit_btn.clicked.connect(lambda _, ef=edit_form: ef.setVisible(not ef.isVisible()))
            if d["status"] not in ("CLOSED",):
                card.add_expand_widget(edit_btn)
                card.add_expand_widget(edit_form)

            # Divider
            div = QFrame()
            div.setFixedHeight(1)
            div.setStyleSheet(f"background:{C['border2']};")
            card.add_expand_widget(div)

            # Repayments
            rep_header = QLabel("\U0001f4b0 Repayment History")
            rep_header.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};padding-top:2px;")
            card.add_expand_widget(rep_header)

            def _make_fo_rep_edit(_did):
                def _on_rep_edit(rep_data):
                    def _save(data):
                        if not self._verify_edit():
                            return
                        self.db.execute(
                            "UPDATE deposit_repayments_to_others SET amount_paid=?, payment_date=?, description=? WHERE repayment_id=?",
                            (data["amount"], data["date"], data["description"], rep_data["repayment_id"]))
                        if rep_data.get("linked_txn_id"):
                            self.db.execute("UPDATE transactions SET amount=?, tx_date=? WHERE id=?",
                                           (data["amount"], data["date"], rep_data["linked_txn_id"]))
                        self.db.commit()
                        self.repos["deposits"].recalc_status(_did)
                        self.db.execute("UPDATE deposits_from_others SET updated_at=? WHERE deposit_id=?", (TODAY(), _did))
                        self.db.commit()
                        self._loaded = False
                        self.load_list(force=True)
                        self._notify_data_changed()
                    return _save
                return _on_rep_edit

            repayments = self.repos["deposits"].get_repayments(did)
            rep_section = _repayment_section(
                repayments, "amount_paid", "payment_date",
                accent_color=color,
                on_edit=_make_fo_rep_edit(did) if d["status"] not in ("CLOSED",) else None
            )
            card.add_expand_widget(rep_section)

            # Mark Closed button (only for REPAID)
            if d["status"] == "REPAID":
                close_btn = QPushButton("\u2705 Mark as Closed")
                close_btn.setFixedHeight(28)
                close_btn.setFocusPolicy(Qt.NoFocus)
                close_btn.setCursor(QCursor(Qt.PointingHandCursor))
                close_btn.setStyleSheet(
                    f"QPushButton{{background:{C['green_bg']};color:{C['green']};"
                    f"border:1.5px solid {C['green']};border-radius:8px;"
                    f"padding:6px 14px;font-size:12px;font-weight:600;}}"
                    f"QPushButton:hover{{background:{C['green']};color:white;}}")
                close_btn.clicked.connect(lambda _, _did=did: self._mark_closed(_did))
                card.add_expand_widget(close_btn)

            # Print
            def _make_fo_print(_d=d, _a=a):
                def _print():
                    reps = self.repos["deposits"].get_repayments(_d["deposit_id"])
                    info = [
                        ("Depositor", _d["depositor_name"]),
                        ("Principal", fmt_money(_d["principal_amount"])),
                        ("Rate", f"{_d.get('interest_rate') or 0}%"),
                        ("Method", _d.get("interest_method") or "SIMPLE"),
                        ("Deposit Date", _d["deposit_date"]),
                        ("Return Date", _d.get("expected_return_date") or EM_DASH),
                    ]
                    analysis = [
                        ("Outstanding", fmt_money(_a["current_value"])),
                        ("Total Paid", fmt_money(_a["total_paid"])),
                        ("Interest Accrued", fmt_money(_a["total_interest_accrued"])),
                    ]
                    sections = []
                    if reps:
                        rdata = [{"date": r.get("payment_date", ""), "amount": r["amount_paid"],
                                  "description": r.get("description") or ""} for r in reps]
                        sections.append({"title": "Repayment Log", "color": "#059669",
                                         "type": "repayment", "data": rdata})
                    _export_detail_to_pdf(self, f"Deposit from {_d['depositor_name']}", _d["status"],
                                          info, analysis, sections)
                return _print

            btn_row = QHBoxLayout()
            print_btn = QPushButton("\U0001f5a8 Print PDF")
            print_btn.setFixedHeight(28)
            print_btn.setFocusPolicy(Qt.NoFocus)
            print_btn.setCursor(QCursor(Qt.PointingHandCursor))
            print_btn.setStyleSheet(_accent_btn_css(color))
            print_btn.clicked.connect(_make_fo_print())
            btn_row.addWidget(print_btn)
            btn_row.addStretch()
            card.add_expand_layout(btn_row)

            all_cards.append(card)

        # Cache

        # Lazy loading
        if all_cards:
            first_batch = all_cards[:self._get_batch_size()]
            self._pending_cards = all_cards[self._get_batch_size():]
            for c in first_batch:
                self._list_lay.addWidget(c)
            if self._pending_cards:
                self._init_lazy_scroll()

    def _mark_closed(self, deposit_id):
        if _confirm(self, "Mark Closed", "Mark this deposit as fully returned/closed?"):
            self.repos["deposits"].update_status(deposit_id, "CLOSED")
            self._loaded = False
            self.load_list()


# ══════════════════════════════════════════════════════════════════════════
#  MUTUAL FUNDS
# ══════════════════════════════════════════════════════════════════════════
class MFPage(_FunctionPage):
    ICON = "\U0001f4c8"
    TITLE = "Mutual Funds"

    # Emitted once live NAVs land so aggregate views (dashboard) can re-read them
    _nav_updated = _Signal()

    def __init__(self, repos, services, parent=None):
        self._nav_cache = {}
        self._nav_fetched = False
        self._nav_worker = None
        self._loading_dlg = None
        self._user_visited = False
        super().__init__(repos, services, parent)
        self._start_background_nav_fetch()

    def refresh(self):
        self._refresh_entry_dropdowns()

    def _start_background_nav_fetch(self):
        all_schemes = self.repos["mf"].list_schemes()
        to_fetch = [(s["scheme_id"], s["api_scheme_code"])
                    for s in all_schemes if s.get("api_scheme_code")]
        if not to_fetch:
            self._nav_fetched = True
            return
        self._nav_worker = _FetchNavsWorker(to_fetch, self)
        self._nav_worker.finished.connect(self._on_navs_fetched)
        self._nav_worker.start()

    def _on_navs_fetched(self, results):
        self._nav_cache.update(results)
        self._nav_fetched = True
        self._nav_worker = None
        if self._loading_dlg:
            self._loading_dlg.accept()
            self._loading_dlg = None
        # Rebuild if page was already loaded with stale NAVs
        if self._loaded:
            self._build_list_data()
        if results:
            self._nav_updated.emit()

    def _make_loading_dlg(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Loading")
        dlg.setMinimumWidth(300)
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowCloseButtonHint)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 20)
        icon = QLabel("\U0001f4c8")
        icon.setStyleSheet("font-size:32px;")
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)
        msg = QLabel("Fetching latest NAV...")
        msg.setStyleSheet(f"color:{C['text']};font-size:13px;font-weight:600;")
        msg.setAlignment(Qt.AlignCenter)
        lay.addWidget(msg)
        return dlg

    def _sort_options(self):
        return ["Return %", "Scheme Name", "Invested", "Current Value"]

    def _build_entry(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.mf_stack, _ = _build_subnav(lay, ["Purchase / SIP", "Redemption"])

        # Purchase / SIP
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

        # Redemption
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
        search_row = QHBoxLayout()
        self._linked_code = None
        self._linked_name = None
        link_lbl = QLabel("Not linked")
        link_lbl.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        cur_nav = QDoubleSpinBox()
        cur_nav.setRange(0, 999999)
        cur_nav.setDecimals(4)
        launch_date = QDateEdit(QDate.currentDate())

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
                cur_nav.setValue(dlg2.result_nav)
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
        status_hint = QLabel("Leave at 0 if this is a new investment")
        status_hint.setStyleSheet(f"color:{C['text3']};font-size:10px;font-style:italic;")
        cur_units = QDoubleSpinBox()
        cur_units.setRange(0, 99999999)
        cur_units.setDecimals(4)
        cur_invested = QDoubleSpinBox()
        cur_invested.setRange(0, 999999999)
        cur_invested.setPrefix("\u20b9 ")
        cur_invested.setDecimals(2)
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
        units = cur_units.value()
        nav = cur_nav.value()
        invested = cur_invested.value()
        if units > 0 and nav > 0 and invested > 0:
            self.repos["mf"].add_txn(
                scheme_id=sid, txn_type="PURCHASE",
                txn_date=TODAY(), amount=invested, nav=nav, units=units, linked_txn_id=None,
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
        try:
            sid = self.mf_buy_scheme.get_data()
        except (AttributeError, RuntimeError):
            return
        if not sid:
            return
        if sid in self._nav_cache and self._nav_cache[sid] > 0:
            self.mf_buy_nav.setValue(self._nav_cache[sid])
            return
        txns = self.repos["mf"].list_txns(sid)
        if txns:
            self.mf_buy_nav.setValue(txns[-1]["nav"])
        scheme = self.repos["mf"].get_scheme(sid)
        api_code = scheme.get("api_scheme_code") if scheme else None
        if api_code:
            url = f"https://api.mfapi.in/mf/{api_code}/latest"
            w = _NavWorker(url, self)
            w.result.connect(lambda data, _sid=sid: self._on_buy_nav(_sid, data))
            w.start()

    def _on_buy_nav(self, sid, data):
        try:
            rows = data.get("data") or [] if isinstance(data, dict) else []
            if rows:
                nav = float(rows[0]["nav"])
                self._nav_cache[sid] = nav
                self.mf_buy_nav.setValue(nav)
        except Exception:
            pass

    def _auto_fetch_sell_nav(self):
        try:
            sid = self.mf_sell_scheme.get_data()
        except (AttributeError, RuntimeError):
            return
        if not sid:
            return
        if sid in self._nav_cache and self._nav_cache[sid] > 0:
            self.mf_sell_nav.setValue(self._nav_cache[sid])
            return
        txns = self.repos["mf"].list_txns(sid)
        if txns:
            self.mf_sell_nav.setValue(txns[-1]["nav"])
        scheme = self.repos["mf"].get_scheme(sid)
        api_code = scheme.get("api_scheme_code") if scheme else None
        if api_code:
            url = f"https://api.mfapi.in/mf/{api_code}/latest"
            w = _NavWorker(url, self)
            w.result.connect(lambda data, _sid=sid: self._on_sell_nav(_sid, data))
            w.start()

    def _on_sell_nav(self, sid, data):
        try:
            rows = data.get("data") or [] if isinstance(data, dict) else []
            if rows:
                nav = float(rows[0]["nav"])
                self._nav_cache[sid] = nav
                self.mf_sell_nav.setValue(nav)
        except Exception:
            pass

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
        try:
            if self.mf_buy_scheme.get_data():
                self._auto_fetch_buy_nav()
        except (AttributeError, RuntimeError):
            pass
        try:
            if self.mf_sell_scheme.get_data():
                self._auto_fetch_sell_nav()
        except (AttributeError, RuntimeError):
            pass

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
            category_names=("Investment", "Finance"), transaction_kind="MF_PURCHASE"
        )
        self.repos["mf"].add_txn(
            scheme_id=sid, txn_type=self.mf_buy_type.currentText(),
            txn_date=self.mf_buy_date.date().toString("yyyy-MM-dd"),
            amount=amount, nav=nav, units=units, linked_txn_id=txn_id
        )
        self._nav_cache[sid] = nav
        self.mf_buy_amount.setValue(0)
        self._refresh_entry_dropdowns()
        self._loaded = False
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
            category_names=("Investment", "Finance"), transaction_kind="MF_REDEMPTION"
        )
        self.repos["mf"].add_txn(
            scheme_id=sid, txn_type="REDEMPTION",
            txn_date=self.mf_sell_date.date().toString("yyyy-MM-dd"),
            amount=amount, nav=nav, units=units, linked_txn_id=txn_id
        )
        self._nav_cache[sid] = nav
        self.mf_sell_units.setValue(0)
        self._refresh_entry_dropdowns()
        self._loaded = False
        self.load_list()
        QMessageBox.information(self, "Redemption Logged", f"{units:,.4f} units redeemed for {fmt_money(amount)}.")

    def _edit_scheme(self, scheme):
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
        cur_code = scheme.get("api_scheme_code") or ""
        link_lbl = QLabel(f"Linked: {cur_code}" if cur_code else "Not linked")
        link_lbl.setStyleSheet(f"color:{C['green'] if cur_code else C['text3']};font-size:11px;font-weight:700;")
        new_code = [cur_code]

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
            self._loaded = False
            self._build_list_data()
            QMessageBox.information(self, "Updated", f"Scheme '{n}' updated successfully.")

    def _last_nav(self, scheme_id):
        # Fast path: cache hit
        if scheme_id in self._nav_cache:
            return self._nav_cache[scheme_id]
        # Fallback: last transaction NAV (no network call)
        txns = self.repos["mf"].list_txns(scheme_id)
        return txns[-1]["nav"] if txns else 0

    # ── List ──
    def load_list(self, force=False):
        if self._loaded and not force:
            return
        self._loaded = True
        if self._nav_fetched:
            self._build_list_data()
        elif self._nav_worker and self._nav_worker.isRunning():
            # Show loading dialog only on explicit user visit, not during pre-load
            if self._user_visited:
                if not self._loading_dlg:
                    self._loading_dlg = self._make_loading_dlg()
                    self._loading_dlg.show()
            else:
                self._build_list_data()  # use last txn NAVs for now
        else:
            self._nav_fetched = True
            self._build_list_data()

    def _build_list_data(self):
        schemes = self.repos["mf"].list_schemes()
        self._list_data = []
        for s in schemes:
            h = self.repos["mf"].holdings(s["scheme_id"])
            nav = self._last_nav(s["scheme_id"])
            net_inv = h["invested"] - h["redeemed"]
            cur_val = h["units"] * nav
            # A scheme with no units left is fully exited (or never bought).
            # simple_return() would report a meaningless -100% against the
            # leftover net-invested figure, so report a flat 0% and mark the
            # card as inactive instead.
            exited = round(h["units"] or 0, 4) <= 0
            ret = 0.0 if exited else MFService.simple_return(net_inv, cur_val)
            self._list_data.append({
                **s, "holdings": h, "nav": nav, "net_invested": net_inv,
                "current_value": cur_val, "return_pct": ret, "exited": exited,
            })
        self._render_list()

    def _render_list(self):
        if not hasattr(self, "_list_lay"):
            return
        _clear_layout(self._stats_row)
        _clear_layout(self._list_lay)
        items = list(self._list_data)
        total_inv = sum(i["net_invested"] for i in items)
        total_cur = sum(i["current_value"] for i in items)
        overall_ret = MFService.simple_return(total_inv, total_cur)
        _fill_stats_row(self._stats_row, [
            _metric_card("Invested", fmt_money(total_inv)),
            _metric_card("Current Value", fmt_money(total_cur), C["accent"]),
            _metric_card("Overall Return", f"{overall_ret:+.2f}%",
                          C["green"] if overall_ret >= 0 else C["red"]),
        ])
        search = self._search_input.text().strip().lower() if hasattr(self, "_search_input") else ""
        if search:
            items = [i for i in items
                     if search in (i["amc_name"] + " " + i["scheme_name"]).lower()]
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
        if not items:
            empty = QLabel("No matching schemes." if search else "No mutual fund schemes yet.")
            empty.setStyleSheet(f"color:{C['text3']};padding:20px;")
            empty.setAlignment(Qt.AlignCenter)
            self._list_lay.addWidget(empty)
            return
        all_cards = []
        for it in items:
            ret = it["return_pct"]
            exited = it.get("exited")
            # Zero-unit schemes render grey (archived look) with a flat 0%.
            if exited:
                color = C["text3"]
                badge = "0.00%"
                extra = (f"Invested: {fmt_money(it['holdings']['invested'])}  {MDOT}  "
                         f"Redeemed: {fmt_money(it['holdings']['redeemed'])}")
            else:
                color = C["green"] if ret >= 0 else C["red"]
                badge = f"{ret:+.2f}%"
                extra = f"Invested: {fmt_money(it['net_invested'])}"
            card = WealthCard(
                item_id=it["scheme_id"],
                title=f"{it['amc_name']} \u2014 {it['scheme_name']}",
                subtitle=f"{it['scheme_type'] or ''} {MDOT} {it['holdings']['units']:,.4f} units {MDOT} NAV {it['nav']:,.4f}",
                amount_text=fmt_money(it["current_value"]),
                badge_text=badge, badge_color=color,
                extra_line=extra,
            )
            card.clicked.connect(self._toggle_card)

            sid = it["scheme_id"]

            # Expanded: transaction history + edit scheme
            detail_lbl = QLabel(
                f"Folio: {it.get('folio_number') or EM_DASH}  {MDOT}  "
                f"Type: {it.get('scheme_type') or EM_DASH}\n"
                f"Units: {it['holdings']['units']:,.4f}  {MDOT}  "
                f"NAV: {it['nav']:,.4f}  {MDOT}  "
                f"Invested: {fmt_money(it['net_invested'])}  {MDOT}  "
                f"Current: {fmt_money(it['current_value'])}  {MDOT}  "
                + ("Return: 0.00% (fully redeemed)" if it.get("exited") else f"Return: {ret:+.2f}%")
            )
            detail_lbl.setStyleSheet(f"color:{C['text2']};font-size:12px;padding:4px 0;")
            detail_lbl.setWordWrap(True)
            card.add_expand_widget(detail_lbl)

            # Transaction history
            txns = self.repos["mf"].list_txns(sid)
            if txns:
                tx_header = QLabel("\U0001f4cb Transaction History")
                tx_header.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};padding-top:4px;")
                card.add_expand_widget(tx_header)
                for tx in txns:
                    tx_card = QFrame()
                    tx_card.setStyleSheet(
                        f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:8px;}}"
                        f"QLabel{{background:transparent;border:none;}}"
                    )
                    tl = QHBoxLayout(tx_card)
                    tl.setContentsMargins(12, 6, 12, 6)
                    tl.setSpacing(12)
                    t_type = QLabel(tx["txn_type"])
                    t_type.setStyleSheet(f"font-size:11px;font-weight:700;color:{C['accent']};")
                    t_date = QLabel(tx["txn_date"])
                    t_date.setStyleSheet(f"font-size:11px;color:{C['text3']};")
                    t_amt = QLabel(fmt_money(tx["amount"]))
                    t_amt.setStyleSheet(f"font-size:13px;font-weight:800;color:{C['text']};")
                    t_nav = QLabel(f"NAV {tx['nav']:,.4f} | {tx['units']:,.4f} units")
                    t_nav.setStyleSheet(f"font-size:10px;color:{C['text3']};")
                    tl.addWidget(t_type)
                    tl.addWidget(t_date)
                    tl.addStretch()
                    tl.addWidget(t_nav)
                    tl.addWidget(t_amt)
                    card.add_expand_widget(tx_card)

            # Edit Scheme button
            def _make_edit_scheme(_scheme=it):
                def _edit():
                    self._edit_scheme(_scheme)
                return _edit

            btn_row = QHBoxLayout()
            edit_btn = QPushButton("\u270f\ufe0f Edit Scheme")
            edit_btn.setFixedHeight(28)
            edit_btn.setFocusPolicy(Qt.NoFocus)
            edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
            edit_btn.setStyleSheet(_accent_btn_css(color))
            edit_btn.clicked.connect(_make_edit_scheme())
            btn_row.addWidget(edit_btn)
            btn_row.addStretch()
            card.add_expand_layout(btn_row)

            all_cards.append(card)

        # Cache

        # Lazy loading
        if all_cards:
            first_batch = all_cards[:self._get_batch_size()]
            self._pending_cards = all_cards[self._get_batch_size():]
            for c in first_batch:
                self._list_lay.addWidget(c)
            if self._pending_cards:
                self._init_lazy_scroll()


# ══════════════════════════════════════════════════════════════════════════
#  NAV FETCH DIALOG (used by MF)
# ══════════════════════════════════════════════════════════════════════════
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
        from PyQt5.QtWidgets import QListWidget
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


# ══════════════════════════════════════════════════════════════════════════
#  SPLIT EXPENSES PAGE (Wealth tab)
# ══════════════════════════════════════════════════════════════════════════
class SplitPage(QWidget):
    """Split Expenses page for the Wealth tab.

    Overview: balance matrix, settlement suggestions, recent expenses.
    Entry: record expenses and settlements.
    """

    def __init__(self, repos, services, parent=None):
        super().__init__(parent)
        self.repos = repos
        self.services = services
        self.db = repos["accounts"].db
        self.sr = repos.get("split")
        self._wealth_tab_ref = None
        self._loaded = False
        self._members = []
        self._share_spins = {}
        self._self_id = self.sr.get_self_contact() if self.sr else None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)

        hdr = QLabel("\U0001f91d  Split Expenses")
        hdr.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        lay.addWidget(hdr)

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
        new_grp_btn = QPushButton("+ New Group")
        new_grp_btn.setMinimumHeight(36)
        new_grp_btn.setCursor(QCursor(Qt.PointingHandCursor))
        new_grp_btn.clicked.connect(self._new_group)
        grp_row.addWidget(new_grp_btn)
        lay.addLayout(grp_row)

        # Stats row
        self.stats_row = QHBoxLayout()
        lay.addLayout(self.stats_row)

        # Sub-navigation
        nav = QHBoxLayout()
        nav.setSpacing(8)
        self.btn_overview = QPushButton("\U0001f4ca Overview")
        self.btn_expense = QPushButton("\U0001f4b0 Record Expense")
        self.btn_settle = QPushButton("\U0001f4b8 Record Settlement")
        self._sub_btns = [self.btn_overview, self.btn_expense, self.btn_settle]
        for b in self._sub_btns:
            b.setMinimumHeight(32)
            b.setCursor(QCursor(Qt.PointingHandCursor))
            nav.addWidget(b)
        nav.addStretch()
        lay.addLayout(nav)

        self.sub_stack = QStackedWidget()
        lay.addWidget(self.sub_stack, 1)
        self.sub_stack.addWidget(self._build_overview())
        self.sub_stack.addWidget(self._build_expense_form())
        self.sub_stack.addWidget(self._build_settle_form())

        self.btn_overview.clicked.connect(lambda: self._goto(0))
        self.btn_expense.clicked.connect(lambda: self._goto(1))
        self.btn_settle.clicked.connect(lambda: self._goto(2))
        _switch_tabs(self._sub_btns, 0)
        self.sub_stack.setCurrentIndex(0)

    # ── Navigation ─────────────────────────────────────────────
    def _goto(self, idx):
        _switch_tabs(self._sub_btns, idx)
        self.sub_stack.setCurrentIndex(idx)
        if idx == 0:
            self._refresh_overview()

    def refresh(self):
        self._load_groups()

    def load_list(self, force=False):
        if self._loaded and not force:
            return
        self._loaded = True
        self._load_groups()

    def _notify_data_changed(self):
        if self._wealth_tab_ref:
            self._wealth_tab_ref._notify_data_changed()

    # ── Groups ─────────────────────────────────────────────────
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
            return
        self._members = self.sr.list_group_members(gid)
        self._populate_combos()
        self._refresh_overview()
        self._update_shares()

    def _populate_combos(self):
        for combo in (self.exp_paid_by, self.stl_from, self.stl_to):
            combo.blockSignals(True)
            combo.clear()
            for m in self._members:
                combo.addItem(m["name"], m["contact_id"])
            combo.blockSignals(False)

    # ── Overview page ──────────────────────────────────────────
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

        # Recent expenses
        exp_title = QLabel("\U0001f4cb Recent Expenses")
        exp_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{C['text']};")
        self.overview_lay.addWidget(exp_title)

        expenses = self.sr.list_expenses(gid)
        if expenses:
            for exp in expenses[:10]:
                card = QFrame()
                card.setStyleSheet(
                    f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:8px;}}"
                    f"QLabel{{background:transparent;border:none;}}")
                cl = QHBoxLayout(card)
                cl.setContentsMargins(12, 8, 12, 8)
                desc = exp["description"] or "Expense"
                info = QLabel(f"{desc} \u2014 paid by {exp['paid_by_name']}")
                info.setStyleSheet(f"font-size:12px;color:{C['text']};font-weight:600;")
                cl.addWidget(info, 1)
                date_lbl = QLabel(exp["expense_date"])
                date_lbl.setStyleSheet(f"font-size:11px;color:{C['text3']};")
                cl.addWidget(date_lbl)
                amt = QLabel(fmt_money(exp["amount"]))
                amt.setStyleSheet(f"font-size:14px;font-weight:800;color:{C['red']};")
                cl.addWidget(amt)
                self.overview_lay.addWidget(card)
        else:
            lbl = QLabel("No expenses yet.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            self.overview_lay.addWidget(lbl)

        self.overview_lay.addStretch()

    # ── Expense form ───────────────────────────────────────────
    def _build_expense_form(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(0, 8, 0, 0)
        form.setSpacing(8)

        self.exp_paid_by = QComboBox()
        self.exp_paid_by.setMinimumHeight(36)

        self.exp_amount = QDoubleSpinBox()
        self.exp_amount.setRange(0, 99999999)
        self.exp_amount.setPrefix("\u20b9 ")
        self.exp_amount.setDecimals(2)
        self.exp_amount.setMinimumHeight(36)
        self.exp_amount.valueChanged.connect(self._on_exp_amount_changed)

        self.exp_desc = QLineEdit()
        self.exp_desc.setPlaceholderText("e.g. Dinner at KFC")
        self.exp_desc.setMinimumHeight(36)

        self.exp_date = QDateEdit(QDate.currentDate())
        self.exp_date.setCalendarPopup(True)
        self.exp_date.setMinimumHeight(36)

        self.exp_account = QComboBox()
        self.exp_account.setMinimumHeight(36)
        for a in self.repos["accounts"].list_active():
            self.exp_account.addItem(a["display_name"], a["account_id"])
        self.exp_method = QComboBox()
        self.exp_method.setMinimumHeight(36)
        for m in self.repos["lookups"].list_methods():
            self.exp_method.addItem(m["display_name"], m["method_id"])

        self.exp_split_type = QComboBox()
        self.exp_split_type.addItems(["Equal", "Custom"])
        self.exp_split_type.setMinimumHeight(36)
        self.exp_split_type.currentIndexChanged.connect(self._on_split_type_changed)

        self.shares_container = QWidget()
        self.shares_container.setStyleSheet("background:transparent;")
        self.shares_lay = QVBoxLayout(self.shares_container)
        self.shares_lay.setContentsMargins(0, 0, 0, 0)
        self.shares_lay.setSpacing(4)

        add_btn = QPushButton("\U0001f4b0  Add Expense")
        add_btn.setObjectName("primary")
        add_btn.setMinimumHeight(42)
        add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_btn.clicked.connect(self._add_expense)

        form.addRow("Paid by *", self.exp_paid_by)
        form.addRow("Amount *", self.exp_amount)
        form.addRow("Description", self.exp_desc)
        form.addRow("Date", self.exp_date)
        form.addRow("Account *", self.exp_account)
        form.addRow("Method *", self.exp_method)
        form.addRow("Split Type", self.exp_split_type)
        form.addRow("Shares", self.shares_container)
        form.addRow("", add_btn)
        return page

    # ── Settlement form ────────────────────────────────────────
    def _build_settle_form(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(0, 8, 0, 0)
        form.setSpacing(8)

        self.stl_from = QComboBox()
        self.stl_from.setMinimumHeight(36)
        self.stl_to = QComboBox()
        self.stl_to.setMinimumHeight(36)

        self.stl_amount = QDoubleSpinBox()
        self.stl_amount.setRange(0, 99999999)
        self.stl_amount.setPrefix("\u20b9 ")
        self.stl_amount.setDecimals(2)
        self.stl_amount.setMinimumHeight(36)

        self.stl_method = QComboBox()
        self.stl_method.addItems(
            ["CASH", "PHONEPAY", "GOOGLE PAY", "BHIM UPI", "NETBANKING", "OTHER"])
        self.stl_method.setMinimumHeight(36)

        self.stl_account = QComboBox()
        self.stl_account.setMinimumHeight(36)
        for a in self.repos["accounts"].list_active():
            self.stl_account.addItem(a["display_name"], a["account_id"])

        settle_btn = QPushButton("\U0001f4b8  Record Settlement")
        settle_btn.setMinimumHeight(42)
        settle_btn.setCursor(QCursor(Qt.PointingHandCursor))
        settle_btn.clicked.connect(self._add_settlement)

        form.addRow("From *", self.stl_from)
        form.addRow("To *", self.stl_to)
        form.addRow("Amount *", self.stl_amount)
        form.addRow("Method", self.stl_method)
        form.addRow("Account *", self.stl_account)
        form.addRow("", settle_btn)
        return page

    # ── Shares logic ───────────────────────────────────────────
    def _on_split_type_changed(self):
        self._clear_shares()
        if not self._members:
            return
        is_equal = self.exp_split_type.currentIndex() == 0
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
            self._on_exp_amount_changed()

    def _on_exp_amount_changed(self):
        if self.exp_split_type.currentIndex() != 0:
            return
        amt = self.exp_amount.value()
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

    def _update_shares(self):
        self._clear_shares()
        self._on_split_type_changed()

    # ── Actions ────────────────────────────────────────────────
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
        split_type = "EQUAL" if self.exp_split_type.currentIndex() == 0 else "EXACT"
        # Create linked transaction ONLY if self paid (money left your account)
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
                transaction_kind="SPLIT", category="other",
                neednwant=0, pf_category=None)
        self.sr.create_expense(
            gid, paid_by, amount,
            self.exp_desc.text().strip() or None,
            self.exp_date.date().toString("yyyy-MM-dd"),
            split_type, shares, linked_txn_id=txn_id)
        self.exp_amount.setValue(0)
        self.exp_desc.clear()
        self._refresh_overview()
        self._notify_data_changed()
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
        # Create linked transaction ONLY if self is involved
        txn_id = None
        tx_repo = self.repos.get("transactions")
        settle_date = date.today().isoformat()
        self_involved = (from_id == self._self_id or to_id == self._self_id)
        if self_involved and tx_repo and self.stl_account.currentData():
            # DEBIT if self is paying, CREDIT if self is receiving
            tx_type = "DEBIT" if from_id == self._self_id else "CREDIT"
            txn_id = tx_repo.create(
                tx_date=settle_date,
                account_id=self.stl_account.currentData(),
                pay_method=self.stl_method.currentText(),
                tx_type=tx_type, amount=amount,
                person_org=f"{self.stl_from.currentText()} \u2192 {self.stl_to.currentText()}",
                description="Split settlement",
                transaction_kind="SPLIT_SETTLEMENT", category="finance",
                neednwant=0, pf_category=None)
        self.sr.create_settlement(
            gid, from_id, to_id, amount,
            settle_date, self.stl_method.currentText(), linked_txn_id=txn_id)
        self.stl_amount.setValue(0)
        self._refresh_overview()
        self._notify_data_changed()
        QMessageBox.information(self, "Done", f"Settlement of {fmt_money(amount)} recorded.")

    # ── New group ──────────────────────────────────────────────
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


# ══════════════════════════════════════════════════════════════════════════
#  WEALTH DASHBOARD — overview of all 6 wealth sub-tabs
# ══════════════════════════════════════════════════════════════════════════
class DashboardPage(QWidget):
    """Wealth Dashboard — KPI cards, net position, alerts, quick access."""

    def __init__(self, repos, services, parent=None):
        super().__init__(parent)
        self.repos = repos
        self.services = services
        self.db = repos["accounts"].db
        self.sr = repos.get("split")
        self._self_id = self.sr.get_self_contact() if self.sr else None
        self._wealth_tab_ref = None
        self._nav_cb = None
        self._kpi = {}
        self._clickables = []   # (widget, page_index) — rebound by set_nav()
        self._build()

    def set_nav(self, cb):
        """Wire up navigation. Called by WealthTab *after* _build(), so the
        click handlers have to be (re)attached here — binding them during
        _build() captured a None callback and left every card/tile dead.
        """
        self._nav_cb = cb
        for widget, idx in self._clickables:
            self._bind_click(widget, idx)

    def _bind_click(self, widget, idx):
        """Attach the click handler for a KPI card / quick-access tile."""
        if idx == 6:  # Split lives in its own top-level tab
            widget.mousePressEvent = lambda e: self._go_to_split()
        else:
            widget.mousePressEvent = lambda e, _i=idx: self._navigate(_i)

    def _navigate(self, idx):
        if self._nav_cb:
            self._nav_cb(idx)

    def _build(self):
        """Fixed header (title + net bar + KPI grid), scrollable alerts below.

        The header keeps its natural height and the alerts region takes every
        remaining pixel, so a long alert list scrolls on its own instead of
        pushing the KPI cards off-screen.
        """
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(16)

        hdr = QLabel("\U0001f4ca  Wealth Dashboard")
        hdr.setStyleSheet(f"font-size:22px;font-weight:800;color:{C['text']};")
        outer.addWidget(hdr)

        # ── Fixed region ──
        net_bar = self._build_net_bar()
        net_bar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        outer.addWidget(net_bar)

        kpi_grid = self._build_kpi_grid()
        kpi_grid.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        outer.addWidget(kpi_grid)

        # ── Scrollable region: Alerts & Upcoming ──
        self.alerts_frame = self._build_alerts_frame()
        outer.addWidget(self.alerts_frame, 1)

    # ── Net Position Bar ───────────────────────────────────────
    def _build_net_bar(self):
        f = QFrame()
        f.setStyleSheet(
            "QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1e1b4b,stop:1 #312e81);border-radius:14px;}"
            "QLabel{background:transparent;border:none;}")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(24, 14, 24, 14)
        lay.setSpacing(8)
        t = QLabel("NET WEALTH POSITION")
        t.setStyleSheet("color:rgba(255,255,255,0.5);font-size:10px;font-weight:700;letter-spacing:1.5px;")
        lay.addWidget(t)
        cols = QHBoxLayout(); cols.setSpacing(24)
        for label, key, tip in [
            ("Investments", "inv", "Fixed deposits (active + matured) and mutual funds"),
            ("Receivable", "recv", "Outstanding on loans you gave out"),
            ("Payable", "pay", "Loans you took plus deposits you're holding for others"),
            ("Split Net", "split", "Owed to you minus what you owe across split groups"),
        ]:
            c = QVBoxLayout(); c.setSpacing(1)
            ll = QLabel(label)
            ll.setStyleSheet("color:rgba(255,255,255,0.45);font-size:10px;font-weight:600;")
            ll.setToolTip(tip)
            c.addWidget(ll)
            vv = QLabel("\u20b90")
            vv.setStyleSheet("color:white;font-size:16px;font-weight:800;")
            c.addWidget(vv)
            cols.addLayout(c)
            setattr(self, f"_np_{key}", vv)
        cols.addStretch()
        lay.addLayout(cols)
        self._np_net = QLabel("\u20b90")
        self._np_net.setStyleSheet("color:#a5f3fc;font-size:28px;font-weight:900;")
        lay.addWidget(self._np_net)
        return f

    # ── KPI Grid ───────────────────────────────────────────────
    def _build_kpi_grid(self):
        wrap = QWidget(); wrap.setStyleSheet("background:transparent;")
        grid = QGridLayout(wrap); grid.setSpacing(12)
        # FD Others is money held for other people -> a liability, so it gets
        # the same warning colour family as "Money Borrowed" rather than green.
        items = [
            ("\U0001f91d", "Money Lent",  C["amber"],  1),
            ("\U0001f3db\ufe0f", "Money Borrowed",  C["red"],    2),
            ("\U0001f3e6", "My Fixed Deposits",  C["accent"], 3),
            ("\U0001f9fe", "Deposits Received",     C["red"],    4),
            ("\U0001f4c8", "Mutual Funds",  "#10B981",   5),
            ("\U0001f91d", "Split Expenses", "#7C3AED",  6),
        ]
        for i, (icon, title, color, idx) in enumerate(items):
            card, vl, dl = self._kpi_card(icon, title, "\u20b90", "\u2014", color, idx)
            grid.addWidget(card, i // 3, i % 3)
            self._kpi[idx] = (vl, dl)
        return wrap

    def _go_to_split(self):
        """Navigate to the standalone Split tab via the main window.

        window() only resolves once the dashboard is inside a shown MainWindow,
        so walk up the parent chain as a fallback instead of silently doing
        nothing.
        """
        w = self.window()
        if hasattr(w, "_nav"):
            w._nav("split")
            return
        node = self.parent()
        while node is not None:
            if hasattr(node, "_nav"):
                node._nav("split")
                return
            node = node.parent()

    def _kpi_card(self, icon, title, value, detail, color, idx):
        card = QFrame()
        card.setCursor(QCursor(Qt.PointingHandCursor))
        bg = _hex_rgba(color, 0.06); hov = _hex_rgba(color, 0.10)
        card.setStyleSheet(
            f"QFrame{{background:{bg};border:1.5px solid {color};border-radius:12px;}}"
            f"QFrame:hover{{background:{hov};}}"
            f"QLabel{{background:transparent;border:none;}}")
        lay = QVBoxLayout(card); lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(6)
        top = QHBoxLayout()
        il = QLabel(icon); il.setStyleSheet("font-size:18px;"); top.addWidget(il)
        tl = QLabel(title); tl.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text2']};")
        top.addWidget(tl, 1); lay.addLayout(top)
        vl = QLabel(value); vl.setStyleSheet(f"font-size:22px;font-weight:900;color:{color};")
        lay.addWidget(vl)
        dl = QLabel(detail); dl.setStyleSheet(f"font-size:11px;color:{C['text3']};font-weight:600;")
        lay.addWidget(dl)
        self._clickables.append((card, idx))
        self._bind_click(card, idx)
        return card, vl, dl

    # ── Alerts ─────────────────────────────────────────────────
    def _build_alerts_frame(self):
        """Alerts panel: fixed title row + independently scrolling list.

        Returns the outer frame. Alert cards are appended to
        ``self._alerts_lay`` by refresh().
        """
        f = QFrame()
        f.setStyleSheet(
            f"QFrame#alertsPanel{{background:{C['surface']};"
            f"border:1px solid {C['border2']};border-radius:12px;}}")
        f.setObjectName("alertsPanel")
        shell = QVBoxLayout(f)
        shell.setContentsMargins(16, 12, 16, 12)
        shell.setSpacing(8)

        # Fixed title (stays put while the list scrolls)
        head = QHBoxLayout()
        head.setSpacing(8)
        self._alerts_title = QLabel("\u23f0  Alerts & Upcoming")
        self._alerts_title.setStyleSheet(
            f"font-size:14px;font-weight:700;color:{C['text']};"
            f"background:transparent;border:none;")
        head.addWidget(self._alerts_title)
        head.addStretch()
        self._alerts_count = QLabel("")
        self._alerts_count.setStyleSheet(
            f"font-size:11px;font-weight:700;color:{C['text3']};"
            f"background:transparent;border:none;")
        head.addWidget(self._alerts_count)
        shell.addLayout(head)

        # Scrollable list
        self._alerts_scroll = QScrollArea()
        self._alerts_scroll.setWidgetResizable(True)
        self._alerts_scroll.setFrameShape(QFrame.NoFrame)
        self._alerts_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._alerts_scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self._alerts_lay = QVBoxLayout(inner)
        self._alerts_lay.setContentsMargins(0, 0, 6, 0)
        self._alerts_lay.setSpacing(8)
        self._alerts_lay.setAlignment(Qt.AlignTop)
        self._alerts_scroll.setWidget(inner)
        shell.addWidget(self._alerts_scroll, 1)
        return f

    def _alert_card(self, alert):
        """One rich alert card — Cards-tab reminder styling, fmt_money amounts.

        *alert* is a dict with: icon, color, title, subtitle, amount,
        amount_caption, badge.
        """
        card = QFrame()
        color = alert["color"]
        card.setStyleSheet(
            f"QFrame#alertCard{{background:{C['surface']};"
            f"border:1px solid {C['border2']};border-left:3px solid {color};"
            f"border-radius:8px;}}"
            f"QFrame#alertCard:hover{{background:{C['surface2']};}}"
            f"QLabel{{background:transparent;border:none;}}")
        card.setObjectName("alertCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(10)

        icon = QLabel(alert["icon"])
        icon.setStyleSheet("font-size:18px;")
        icon.setFixedWidth(24)
        icon.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        row.addWidget(icon)

        mid = QVBoxLayout()
        mid.setSpacing(2)
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title = QLabel(alert["title"])
        title.setStyleSheet(f"font-size:13px;font-weight:700;color:{C['text']};")
        title.setWordWrap(True)
        title_row.addWidget(title)
        if alert.get("badge"):
            badge = QLabel(alert["badge"])
            badge.setStyleSheet(
                f"font-size:9px;font-weight:800;color:{color};"
                f"background:{_hex_rgba(color, 0.12)};border-radius:4px;"
                f"padding:2px 6px;letter-spacing:0.5px;")
            title_row.addWidget(badge)
        title_row.addStretch()
        mid.addLayout(title_row)
        if alert.get("subtitle"):
            sub = QLabel(alert["subtitle"])
            sub.setStyleSheet(f"font-size:11px;color:{C['text3']};font-weight:600;")
            sub.setWordWrap(True)
            mid.addWidget(sub)
        row.addLayout(mid, 1)

        right = QVBoxLayout()
        right.setSpacing(1)
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        amt = QLabel(alert["amount"])
        amt.setStyleSheet(f"font-size:14px;font-weight:800;color:{color};")
        amt.setAlignment(Qt.AlignRight)
        right.addWidget(amt)
        if alert.get("amount_caption"):
            cap = QLabel(alert["amount_caption"])
            cap.setStyleSheet(f"font-size:10px;color:{C['text3']};font-weight:600;")
            cap.setAlignment(Qt.AlignRight)
            right.addWidget(cap)
        row.addLayout(right)
        return card

    # ── Data helpers ───────────────────────────────────────────
    def _sync_statuses(self):
        """Roll stale ACTIVE/PARTIALLY_PAID rows forward to OVERDUE.

        The sub-pages do this in their own load_list(). Without it the
        dashboard reported "0 overdue" until the user happened to open a
        sub-tab, and then the same data suddenly produced different numbers.
        """
        for repo_key in ("loans", "borrowed"):
            repo = self.repos.get(repo_key)
            if repo and hasattr(repo, "sync_overdue"):
                try:
                    repo.sync_overdue()
                except Exception:
                    pass
        # deposits_from_others has no repo-level batch sync
        try:
            self.db.execute(
                "UPDATE deposits_from_others SET status='OVERDUE' "
                "WHERE status IN ('ACTIVE','PARTIALLY_PAID') "
                "AND expected_return_date IS NOT NULL AND expected_return_date < ?",
                (date.today().isoformat(),))
            self.db.commit()
        except Exception:
            pass
        fd = self.repos.get("fd")
        if fd and hasattr(fd, "sync_matured"):
            try:
                fd.sync_matured()
            except Exception:
                pass

    def replay_kpis(self):
        """Replay dashboard figures when the user lands on the Wealth tab."""
        for value_label, _detail_label in self._kpi.values():
            value_label._cu_value = 0.0
        self._np_net._cu_value = 0.0
        self.refresh()

    # ── Refresh ────────────────────────────────────────────────
    def refresh(self):
        db = self.db
        today = date.today()
        today_s = today.isoformat()
        ACTIVE_SET = ("ACTIVE", "PARTIALLY_PAID", "OVERDUE")

        # Bring stale statuses up to date first so every figure below agrees
        # with what the sub-tabs show.
        self._sync_statuses()

        # 1. Money Lent — outstanding = principal - repaid (matches LoansGivePage)
        lg = db.execute("""
            SELECT l.loan_id, l.loan_amount, l.status, l.due_date,
                   COALESCE(SUM(r.amount_paid),0) AS rep
            FROM loans l LEFT JOIN repayments r ON r.loan_id=l.loan_id
            WHERE l.status NOT IN ('CLOSED','REPAID','CLEARED')
            GROUP BY l.loan_id""").fetchall()
        lg_out = sum(max((r["loan_amount"] or 0) - r["rep"], 0) for r in lg)
        lg_od = sum(1 for r in lg if r["status"] == "OVERDUE")
        lg_act = sum(1 for r in lg if r["status"] in ACTIVE_SET)

        # 2. Money Borrowed — full interest-aware analysis (matches LoansTakePage)
        lt = db.execute("""
            SELECT * FROM borrowed_loans
            WHERE status NOT IN ('CLOSED','REPAID')""").fetchall()
        lt = [dict(r) for r in lt]
        lt_ids = [r["loan_id"] for r in lt]
        lt_paid = _batch_sum_db(db, "borrowed_loan_repayments", "loan_id", "amount_paid", lt_ids)
        lt_reps = _batch_rows_db(db, "borrowed_loan_repayments", "loan_id", lt_ids)
        lt_out = 0.0
        for r in lt:
            lt_out += borrowed_outstanding(
                r, lt_paid.get(r["loan_id"], 0), lt_reps.get(r["loan_id"], []))
        lt_od = sum(1 for r in lt if r["status"] == "OVERDUE")
        lt_act = sum(1 for r in lt if r["status"] in ACTIVE_SET)
        # Next upcoming EMI (guard against NULL emi_amount / NULL due_date)
        next_emi = None
        for r in lt:
            dd = r.get("due_date") or ""
            emi = r.get("emi_amount") or 0
            if dd >= today_s and emi > 0:
                if next_emi is None or dd < next_emi[0]:
                    next_emi = (dd, emi)

        # 3. FD Deposits — ACTIVE value + separately tracked matured value
        fd = db.execute("""
            SELECT COUNT(*) AS c, COALESCE(SUM(principal_amount),0) AS p,
                   COALESCE(SUM(CASE WHEN maturity_amount>0 THEN maturity_amount
                                     ELSE principal_amount END),0) AS m
            FROM fixed_deposits WHERE status='ACTIVE'""").fetchone()
        fd_mat = db.execute("""
            SELECT COUNT(*) AS c,
                   COALESCE(SUM(CASE WHEN maturity_amount>0 THEN maturity_amount
                                     ELSE principal_amount END),0) AS m
            FROM fixed_deposits WHERE status='MATURED'""").fetchone()
        # Matured-but-not-withdrawn money is still yours — count it as an asset.
        fd_total = (fd["m"] or 0) + (fd_mat["m"] or 0)

        # 4. FD Others — money received from others; a LIABILITY, not an asset
        fo = db.execute("""
            SELECT * FROM deposits_from_others
            WHERE status NOT IN ('CLOSED','REPAID')""").fetchall()
        fo = [dict(r) for r in fo]
        fo_ids = [d["deposit_id"] for d in fo]
        fo_paid = _batch_sum_db(db, "deposit_repayments_to_others", "deposit_id", "amount_paid", fo_ids)
        fo_reps = _batch_rows_db(db, "deposit_repayments_to_others", "deposit_id", fo_ids)
        fo_out = 0.0
        for d in fo:
            fo_out += deposit_outstanding(
                d, fo_paid.get(d["deposit_id"], 0), fo_reps.get(d["deposit_id"], []))
        fo_od = sum(1 for d in fo if d["status"] == "OVERDUE")
        fo_act = sum(1 for d in fo if d["status"] in ACTIVE_SET)

        # 5. MF — reuse the MF page's live NAV cache when it has one, so the
        #    dashboard doesn't show stale last-transaction NAVs.
        mf_inv = 0.0
        mf_cur = 0.0
        nav_cache = {}
        mf_page = None
        if self._wealth_tab_ref is not None:
            mf_page = getattr(self._wealth_tab_ref, "mf_page", None)
            nav_cache = getattr(mf_page, "_nav_cache", {}) or {}
        for s in self.repos["mf"].list_schemes():
            sid = s["scheme_id"]
            h = self.repos["mf"].holdings(sid)
            nav = nav_cache.get(sid)
            if nav is None:
                txns = self.repos["mf"].list_txns(sid)
                nav = txns[-1]["nav"] if txns else 0
            mf_inv += (h["invested"] or 0) - (h["redeemed"] or 0)
            mf_cur += (h["units"] or 0) * (nav or 0)
        mf_ret = ((mf_cur - mf_inv) / mf_inv * 100) if mf_inv > 0 else 0

        # 6. Split
        sp_owed = 0.0
        sp_owe = 0.0
        sp_unset = 0
        if self.sr:
            # _self_id can be None if the contact row didn't exist at build time
            if self._self_id is None:
                try:
                    self._self_id = self.sr.get_self_contact()
                except Exception:
                    self._self_id = None
            for g in self.sr.list_groups():
                bal = self.sr.get_group_balances(g["group_id"])
                mb = bal.get(self._self_id, 0)
                if mb > 0.01:
                    sp_owed += mb
                    sp_unset += 1
                elif mb < -0.01:
                    sp_owe += abs(mb)
                    sp_unset += 1

        # ── Update KPI cards ──
        v, d = self._kpi[1]
        animate_value(v, lg_out, fmt_money); d.setText(f"{lg_od} overdue / {lg_act} active")
        v, d = self._kpi[2]
        emi_txt = (f"EMI {fmt_money(next_emi[1])} due {next_emi[0]}"
                   if next_emi else f"{lt_od} overdue / {lt_act} active")
        animate_value(v, lt_out, fmt_money); d.setText(emi_txt)
        v, d = self._kpi[3]
        animate_value(v, fd_total, fmt_money)
        d.setText(f"{fd['c']} active / {fd_mat['c']} matured")
        v, d = self._kpi[4]
        animate_value(v, fo_out, fmt_money); d.setText(f"{fo_od} overdue / {fo_act} active")
        v, d = self._kpi[5]
        animate_value(v, mf_cur, fmt_money); d.setText(f"{mf_ret:+.1f}% return")
        v, d = self._kpi[6]
        # The card has a paired Owed / Owe display; animate the leading owed
        # figure while preserving the paired liability figure throughout.
        animate_value(v, sp_owed,
                      lambda value: f"{fmt_money(value)} / {fmt_money(sp_owe)}")
        d.setText(f"{sp_unset} unsettled group{'' if sp_unset == 1 else 's'}")

        # ── Update Net Position ──
        # Assets: FDs + mutual funds.  Receivable: loans I gave out.
        # Payable: loans I took + deposits I'm holding for other people.
        inv = fd_total + mf_cur
        recv = lg_out
        pay = lt_out + fo_out
        sp_net = sp_owed - sp_owe
        net = inv + recv - pay + sp_net
        self._np_inv.setText(fmt_money(inv))
        self._np_recv.setText(fmt_money(recv))
        self._np_pay.setText(fmt_money(pay))
        self._np_split.setText(fmt_money(sp_net))
        animate_value(self._np_net, net, lambda value: f"NET: {fmt_money(value)}")
        net_col = "#a5f3fc" if net >= 0 else "#fca5a5"
        self._np_net.setStyleSheet(f"color:{net_col};font-size:28px;font-weight:900;")

        # ── Update Alerts ──
        # Cards are real QWidgets cleared recursively — nested layouts used to
        # leak their labels because takeAt().widget() is None for a layout.
        _clear_layout(self._alerts_lay)

        def _due_phrase(days):
            if days == 0:
                return "today"
            if days == 1:
                return "tomorrow"
            return f"in {days} days"

        alerts = []   # (sort_key, dict)

        # 1. Overdue loans I gave out
        od_give = db.execute("""
            SELECT b.name, l.loan_amount, l.due_date,
                   COALESCE(SUM(r.amount_paid),0) AS rep
            FROM loans l
            JOIN borrowers b ON b.borrower_id=l.borrower_id
            LEFT JOIN repayments r ON r.loan_id=l.loan_id
            WHERE l.status='OVERDUE' GROUP BY l.loan_id
            ORDER BY l.due_date""").fetchall()
        for r in od_give:
            days = _days_since(r["due_date"], today)
            outstanding = max((r["loan_amount"] or 0) - r["rep"], 0)
            paid = r["rep"] or 0
            sub = f"Due {r['due_date'] or EM_DASH}  {MDOT}  Lent {fmt_money(r['loan_amount'] or 0)}"
            if paid > 0:
                sub += f"  {MDOT}  Repaid {fmt_money(paid)}"
            alerts.append((-1000 - days, {
                "icon": "\u26a0\ufe0f", "color": C["red"], "badge": "OVERDUE",
                "title": f"{r['name']} owes you",
                "subtitle": f"Overdue by {days} day{'' if days == 1 else 's'}  {MDOT}  {sub}",
                "amount": fmt_money(outstanding), "amount_caption": "outstanding",
            }))

        # 2. Overdue loans I took
        lt_by_id = {r["loan_id"]: r for r in lt}
        od_take = db.execute("""
            SELECT l.loan_id, le.name, l.due_date FROM borrowed_loans l
            JOIN lenders le ON le.lender_id=l.lender_id
            WHERE l.status='OVERDUE' ORDER BY l.due_date""").fetchall()
        for r in od_take:
            days = _days_since(r["due_date"], today)
            loan = lt_by_id.get(r["loan_id"])
            outstanding = borrowed_outstanding(
                loan, lt_paid.get(r["loan_id"], 0), lt_reps.get(r["loan_id"], [])
            ) if loan else 0
            paid = lt_paid.get(r["loan_id"], 0)
            sub = f"Overdue by {days} day{'' if days == 1 else 's'}  {MDOT}  Due {r['due_date'] or EM_DASH}"
            if paid > 0:
                sub += f"  {MDOT}  Repaid {fmt_money(paid)}"
            alerts.append((-1000 - days, {
                "icon": "\U0001f3db\ufe0f", "color": C["red"], "badge": "OVERDUE",
                "title": f"You owe {r['name']}",
                "subtitle": sub,
                "amount": fmt_money(outstanding), "amount_caption": "outstanding",
            }))

        # 3. Deposits I hold that are overdue for return
        for d in fo:
            if d["status"] != "OVERDUE":
                continue
            rd = d.get("expected_return_date")
            days = _days_since(rd, today)
            out = deposit_outstanding(
                d, fo_paid.get(d["deposit_id"], 0), fo_reps.get(d["deposit_id"], []))
            rate = d.get("interest_rate") or 0
            sub = f"Overdue by {days} day{'' if days == 1 else 's'}  {MDOT}  Return by {rd or EM_DASH}"
            sub += f"  {MDOT}  {'Interest-free' if not rate else f'{rate}% interest'}"
            alerts.append((-1000 - days, {
                "icon": "\U0001f9fe", "color": C["red"], "badge": "OVERDUE",
                "title": f"Return deposit to {d.get('depositor_name') or 'depositor'}",
                "subtitle": sub,
                "amount": fmt_money(out), "amount_caption": "to return",
            }))

        # 4. EMI due within 7 days
        soon7 = (today + timedelta(days=7)).isoformat()
        emi_due = db.execute("""
            SELECT le.name, b.emi_amount, b.due_date, b.principal_amount
            FROM borrowed_loans b
            JOIN lenders le ON le.lender_id=b.lender_id
            WHERE b.status IN ('ACTIVE','PARTIALLY_PAID')
              AND b.emi_amount IS NOT NULL AND b.emi_amount > 0
              AND b.due_date BETWEEN ? AND ?
            ORDER BY b.due_date""", (today_s, soon7)).fetchall()
        for r in emi_due:
            days = _days_since(r["due_date"], today) * -1
            alerts.append((days, {
                "icon": "\U0001f514", "color": C["amber"],
                "badge": "DUE SOON" if days <= 3 else "",
                "title": f"EMI to {r['name']}",
                "subtitle": (f"Due {_due_phrase(days)} on {r['due_date']}  {MDOT}  "
                             f"Principal {fmt_money(r['principal_amount'] or 0)}"),
                "amount": fmt_money(r["emi_amount"]), "amount_caption": "EMI due",
            }))

        # 5. Deposits due back within 30 days
        soon30 = (today + timedelta(days=30)).isoformat()
        for d in fo:
            rd = d.get("expected_return_date")
            if d["status"] == "OVERDUE" or not rd or not (today_s <= str(rd) <= soon30):
                continue
            days = _days_since(rd, today) * -1
            out = deposit_outstanding(
                d, fo_paid.get(d["deposit_id"], 0), fo_reps.get(d["deposit_id"], []))
            rate = d.get("interest_rate") or 0
            alerts.append((days, {
                "icon": "\U0001f9fe", "color": C["amber"],
                "badge": "DUE SOON" if days <= 7 else "",
                "title": f"Deposit return to {d.get('depositor_name') or 'depositor'}",
                "subtitle": (f"Due {_due_phrase(days)} on {rd}  {MDOT}  "
                             f"{'Interest-free' if not rate else f'{rate}% interest'}"),
                "amount": fmt_money(out), "amount_caption": "to return",
            }))

        # 6. FDs maturing within 30 days
        fd_alerts = db.execute("""
            SELECT COALESCE(a.display_name,'Fixed Deposit') AS display_name,
                   f.maturity_amount, f.principal_amount, f.maturity_date,
                   f.interest_rate
            FROM fixed_deposits f
            LEFT JOIN accounts a ON a.account_id=f.bank_account_id
            WHERE f.status='ACTIVE' AND f.maturity_date BETWEEN ? AND ?
            ORDER BY f.maturity_date""", (today_s, soon30)).fetchall()
        for r in fd_alerts:
            days = _days_since(r["maturity_date"], today) * -1
            amt = r["maturity_amount"] or r["principal_amount"] or 0
            gain = amt - (r["principal_amount"] or 0)
            sub = (f"Matures {_due_phrase(days)} on {r['maturity_date']}  {MDOT}  "
                   f"Principal {fmt_money(r['principal_amount'] or 0)}")
            if gain > 0:
                sub += f"  {MDOT}  Interest {fmt_money(gain)}"
            alerts.append((days, {
                "icon": "\U0001f3e6", "color": C["accent"],
                "badge": "MATURING" if days <= 7 else "",
                "title": f"{r['display_name']} FD matures",
                "subtitle": sub,
                "amount": fmt_money(amt), "amount_caption": "at maturity",
            }))

        # 7. Split settlements involving me
        if self.sr and self._self_id:
            for g in self.sr.list_groups():
                for fid, fn, tid, tn, amt in self.sr.suggest_settlements(g["group_id"]):
                    if fid != self._self_id and tid != self._self_id:
                        continue
                    i_pay = (fid == self._self_id)
                    alerts.append((500, {
                        "icon": "\U0001f4b8", "color": "#7C3AED",
                        "badge": "YOU PAY" if i_pay else "YOU RECEIVE",
                        "title": (f"Pay {tn}" if i_pay else f"Collect from {fn}"),
                        "subtitle": f"Group: {g['name']}  {MDOT}  Suggested settlement",
                        "amount": fmt_money(amt),
                        "amount_caption": "to pay" if i_pay else "to receive",
                    }))

        # Most urgent first (overdue, then soonest due)
        alerts.sort(key=lambda a: a[0])

        if alerts:
            total = len(alerts)
            self._alerts_count.setText(f"{total} item{'' if total == 1 else 's'}")
            # Hard cap on rendered widgets. Building thousands of cards would
            # stall the UI thread; the list is sorted most-urgent-first, so the
            # cap only ever hides the least pressing items.
            shown = alerts[:ALERT_RENDER_LIMIT]
            for _, data in shown:
                self._alerts_lay.addWidget(self._alert_card(data))
            if total > len(shown):
                more = QLabel(
                    f"+ {total - len(shown)} more \u2014 showing the "
                    f"{len(shown)} most urgent")
                more.setStyleSheet(
                    f"font-size:11px;color:{C['text3']};font-weight:600;"
                    f"background:transparent;border:none;padding:8px 4px;")
                more.setAlignment(Qt.AlignCenter)
                self._alerts_lay.addWidget(more)
            self._alerts_scroll.verticalScrollBar().setValue(0)
        else:
            self._alerts_count.setText("")
            empty = QLabel("\u2705  Nothing needs your attention right now.")
            empty.setStyleSheet(
                f"font-size:12px;color:{C['text3']};font-weight:600;"
                f"background:transparent;border:none;padding:18px 4px;")
            empty.setAlignment(Qt.AlignCenter)
            self._alerts_lay.addWidget(empty)
        self.alerts_frame.show()
    def load_list(self, force=False):
        self.refresh()


# ══════════════════════════════════════════════════════════════════════════
#  WEALTH TAB — 7 top-level pages (Dashboard + 5 + Split)
# ══════════════════════════════════════════════════════════════════════════
class WealthTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self.repos = repos
        self.services = services
        self._refresh_callback = None
        self._build()

    def set_refresh_callback(self, callback):
        """Called by MainWindow to notify other tabs when wealth data changes."""
        self._refresh_callback = callback

    def _notify_data_changed(self):
        """Notify other tabs (audit, home, etc.) that wealth data changed."""
        if self._refresh_callback:
            self._refresh_callback()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(14)
        heading = QLabel("\U0001f4c8  Wealth")
        heading.setStyleSheet(f"font-size:22px;font-weight:800;color:{C['text']};")
        outer.addWidget(heading)
        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)
        self.btn_dash = QPushButton("\U0001f4ca Dashboard")
        self.btn_lg = QPushButton("\U0001f91d Money Lent")
        self.btn_lt = QPushButton("\U0001f3db\ufe0f Money Borrowed")
        self.btn_fd = QPushButton("\U0001f3e6 My Fixed Deposits")
        self.btn_fo = QPushButton("\U0001f9fe Deposits Received")
        self.btn_mf = QPushButton("\U0001f4c8 Mutual Funds")
        self._nav_btns = [self.btn_dash, self.btn_lg, self.btn_lt, self.btn_fd,
                          self.btn_fo, self.btn_mf]
        for b in self._nav_btns:
            b.setMinimumHeight(34)
            b.setCursor(QCursor(Qt.PointingHandCursor))
            nav_row.addWidget(b)
        nav_row.addStretch()
        outer.addLayout(nav_row)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.loans_give_page = LoansGivePage(self.repos, self.services)
        self.loans_take_page = LoansTakePage(self.repos, self.services)
        self.fd_give_page = FDGivePage(self.repos, self.services)
        self.fd_others_page = FDOthersPage(self.repos, self.services)
        self.mf_page = MFPage(self.repos, self.services)
        self.dashboard_page = DashboardPage(self.repos, self.services)
        self.dashboard_page.set_nav(self._goto)
        self._pages = [
            self.dashboard_page,
            self.loans_give_page, self.loans_take_page,
            self.fd_give_page, self.fd_others_page, self.mf_page,
        ]
        for p in self._pages:
            p._wealth_tab_ref = self
            self.stack.addWidget(p)
        # When the background NAV fetch lands, the dashboard's MF figures are
        # stale — refresh it so it agrees with the Mutual Funds page.
        try:
            self.mf_page._nav_updated.connect(self._on_mf_navs_updated)
        except Exception:
            pass
        self.btn_dash.clicked.connect(lambda: self._goto(0))
        self.btn_lg.clicked.connect(lambda: self._goto(1))
        self.btn_lt.clicked.connect(lambda: self._goto(2))
        self.btn_fd.clicked.connect(lambda: self._goto(3))
        self.btn_fo.clicked.connect(lambda: self._goto(4))
        self.btn_mf.clicked.connect(lambda: self._goto(5))
        _switch_tabs(self._nav_btns, 0)
        self.stack.setCurrentIndex(0)

    def _on_mf_navs_updated(self):
        """Live NAVs arrived — keep the dashboard in sync with the MF page."""
        if self.stack.currentIndex() == 0:
            self.dashboard_page.refresh()

    def _goto(self, i):
        if not 0 <= i < len(self._pages):
            return
        _switch_tabs(self._nav_btns, i)
        self.stack.setCurrentIndex(i)
        # Catch up if this page was skipped by a previous refresh().
        stale = getattr(self, "_stale_pages", None)
        if stale and i in stale:
            stale.discard(i)
            try:
                self._pages[i].refresh()
            except Exception:
                pass
        # Mark MF page as user-visited (enables loading dialog)
        if hasattr(self._pages[i], '_user_visited'):
            self._pages[i]._user_visited = True
        self._pages[i].load_list()
        # The dashboard aggregates every other page, so it must always
        # recompute — its load_list() short-circuits on nothing, but going
        # through refresh() keeps the intent explicit.
        if i == 0:
            # The dashboard may have refreshed while another Wealth sub-page
            # was visible. Replay only when the user returns to it.
            self.dashboard_page.replay_kpis()

    def on_activated(self):
        """Refresh only the visible page and replay dashboard KPIs on landing."""
        if self.stack.currentIndex() == 0:
            self.dashboard_page.replay_kpis()
        else:
            self.refresh()

    def refresh(self):
        """Refresh the visible sub-page; mark the rest to catch up on demand.

        Rebuilding all five pages cost ~370ms per call even though only one
        is on screen. _goto() already refreshes a page when you open it, so
        the deferred ones stay correct.
        """
        idx = self.stack.currentIndex()
        self._stale_pages = set(range(len(self._pages))) - {idx}
        try:
            self._pages[idx].refresh()
        except Exception:
            pass
