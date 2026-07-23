"""View Database — Complete / Monthly / Filtered.
Button-based switching, card views, Paytm charts, grouped account summary."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QComboBox, QDateEdit, QLineEdit,
                              QSpinBox, QDoubleSpinBox, QFrame, QStackedWidget,
                              QScrollArea, QMessageBox, QFileDialog, QGridLayout,
                              QSizePolicy, QLayout)
from PyQt5.QtCore import Qt, QDate, QUrl, QTimer, QPoint, QRect, QSize
from PyQt5.QtGui import QColor, QCursor
from datetime import date, timedelta
from collections import OrderedDict
from ui.theme import C
from ui.sidebar import fmt_money
import json, uuid as _uuid, os, subprocess, sys

COMPLETE_PAGE_SIZE = 150  # default, overridden by preferences table
SCROLL_TRIGGER_PX = 400   # default, overridden by preferences table

def _get_pref(db, key, default):
    try:
        r = db.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
        if r and r["value"]: return int(r["value"])
    except: pass
    return default

_HAS_WEBENGINE = None  # Lazy check

def _check_webengine():
    global _HAS_WEBENGINE
    if _HAS_WEBENGINE is not None:
        return _HAS_WEBENGINE
    try:
        from PyQt5.QtWebEngineWidgets import QWebEngineView
        _HAS_WEBENGINE = True
    except Exception:
        _HAS_WEBENGINE = False
    return _HAS_WEBENGINE


# ═══════════════════════════════════════════════
# FLOW LAYOUT — wraps children to next row on resize
# ═══════════════════════════════════════════════

class FlowLayout(QLayout):
    """Wraps child widgets to the next row when container width runs out."""
    def __init__(self, parent=None, hSpacing=6, vSpacing=4):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self._h = hSpacing; self._v = vSpacing; self._items = []

    def addItem(self, item):       self._items.append(item)
    def count(self):               return len(self._items)
    def itemAt(self, i):           return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i):           return self._items.pop(i) if 0 <= i < len(self._items) else None
    def hasHeightForWidth(self):   return True
    def heightForWidth(self, w):   return self._do(QRect(0, 0, w, 0), True)
    def setGeometry(self, r):
        super().setGeometry(r); self._do(r, False)
    def sizeHint(self):            return self.minimumSize()
    def minimumSize(self):
        s = QSize()
        for it in self._items: s = s.expandedTo(it.minimumSize())
        return s

    def _do(self, rect, test):
        x = rect.x(); y = rect.y(); lineH = 0
        for item in self._items:
            sh = item.sizeHint()
            nx = x + sh.width() + self._h
            if nx - self._h > rect.right() + 1 and lineH > 0:
                x = rect.x(); y += lineH + self._v
                nx = x + sh.width() + self._h; lineH = 0
            if not test:
                item.setGeometry(QRect(QPoint(x, y), sh))
            x = nx; lineH = max(lineH, sh.height())
        return y + lineH - rect.y()


FILTER_FIELDS = [
    {"key": "account", "label": "Account", "type": "combo", "source": "accounts"},
    {"key": "category", "label": "Category", "type": "combo", "source": "categories"},
    {"key": "method", "label": "Payment Method", "type": "combo", "source": "methods"},
    {"key": "tx_type", "label": "Type", "type": "combo", "values": ["CREDIT", "DEBIT"]},
    {"key": "kind", "label": "Kind", "type": "combo", "values": ["REGULAR", "TRANSFER", "LOAN_GIVEN", "LOAN_REPAYMENT", "LOAN_TAKEN", "EMI_PAYMENT", "FD_DEPOSIT", "DEPOSIT_RECEIVED", "DEPOSIT_REPAYMENT", "MF_PURCHASE", "MF_REDEMPTION", "FD_WITHDRAWAL"]},
    {"key": "neednwant", "label": "Need/Want", "type": "combo", "values": ["Need", "Want", "None"]},
    {"key": "pf_category", "label": "PF Category", "type": "combo", "source": "pf_categories"},
    {"key": "person_org", "label": "Person/Org", "type": "text"},
    {"key": "description", "label": "Description", "type": "text"},
    {"key": "min_amount", "label": "Min Amount", "type": "number"},
    {"key": "max_amount", "label": "Max Amount", "type": "number"},
]

CAT_ICONS = {
    "food_dining": "🍔", "transport": "🚗", "shopping": "🛍️",
    "bills_utilities": "💡", "rent": "🏠", "salary": "💰",
    "investment": "📈", "health": "🏥", "education": "📚",
    "entertainment": "🎬", "transfer": "🔄", "other": "📋",
}


# Custom icon cache from preferences — overrides CAT_ICONS
_CAT_ICON_CACHE = {}

def _refresh_cat_icons(db):
    """Load custom category icons from preferences into cache."""
    global _CAT_ICON_CACHE
    try:
        rows = db.execute("SELECT key, value FROM preferences WHERE key LIKE 'cat_icon_%'").fetchall()
        _CAT_ICON_CACHE = {r["key"].replace("cat_icon_", ""): r["value"] for r in rows if r["value"]}
    except:
        _CAT_ICON_CACHE = {}

ACCT_TYPE_LABELS = {
    "CURRENT": "🏦 Bank Accounts",
    "WALLET": "👛 Wallets",
    "CASH": "💵 Cash",
    "CREDIT_CARD": "💳 Credit Cards",
}

ACCT_TYPE_COLORS = {
    "CURRENT": "#4F46E5",
    "WALLET": "#8B5CF6",
    "CASH": "#F59E0B",
    "CREDIT_CARD": "#EF4444",
}


def _tab_btn_active():
    return f"""
        QPushButton {{
            background: {C['accent']}; color: white;
            border: 1px solid {C['accent']}; border-radius: 8px;
            padding: 8px 16px; font-size: 13px; font-weight: 700;
        }}
    """

def _tab_btn_inactive():
    return f"""
        QPushButton {{
            background: {C['surface']}; color: {C['text2']};
            border: 1px solid {C['border']}; border-radius: 8px;
            padding: 8px 16px; font-size: 13px; font-weight: 600;
        }}
        QPushButton:hover {{ border-color: {C['accent']}; color: {C['accent']}; }}
    """

def _switch_tabs(btns, idx):
    for i, b in enumerate(btns):
        b.setStyleSheet(_tab_btn_active() if i == idx else _tab_btn_inactive())


# ═══════════════════════════════════════════════
# TRANSACTION CARD
# ═══════════════════════════════════════════════

def _tx_card(tx, running_bal=None):
    card = QFrame()
    card.setStyleSheet("""
        QFrame { background:#fff; border:1px solid #E5E7EB; border-radius:12px; }
        QFrame:hover { border-color:#C7D2FE; background:#FAFBFF; }
        QLabel { background:transparent; border:none; outline:none; }
    """)
    lay = QHBoxLayout(card)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(14)

    cat_id = tx.get("category") or "other"
    icon = _CAT_ICON_CACHE.get(cat_id) or CAT_ICONS.get(cat_id, "📋")
    cat_color = tx.get("cat_color") or "#6B7280"
    icon_lbl = QLabel(icon)
    icon_lbl.setFixedSize(44, 44)
    icon_lbl.setAlignment(Qt.AlignCenter)
    icon_lbl.setStyleSheet(f"background:{cat_color}15;border-radius:22px;font-size:20px;")
    lay.addWidget(icon_lbl)

    text_col = QVBoxLayout(); text_col.setSpacing(4)
    person = tx.get("person_org") or ""
    desc = tx.get("description") or ""
    if person and desc: main_text = f"<b>{person}</b> — {desc}"
    elif person: main_text = f"<b>{person}</b>"
    elif desc: main_text = desc
    else: main_text = "<i>No description</i>"
    main_lbl = QLabel(main_text)
    main_lbl.setStyleSheet("color:#111827;font-size:13px;")
    main_lbl.setWordWrap(True)
    text_col.addWidget(main_lbl)

    parts = []
    if tx.get("cat_name"): parts.append(tx["cat_name"])
    if tx.get("method_name"): parts.append(tx["method_name"])
    if tx.get("account_name"): parts.append(tx["account_name"])
    if running_bal is not None: parts.append(f"Bal: {fmt_money(running_bal)}")
    sub_lbl = QLabel(" · ".join(parts))
    sub_lbl.setStyleSheet("color:#6B7280;font-size:11px;")
    text_col.addWidget(sub_lbl)
    lay.addLayout(text_col, 1)

    # ── Amount column (amount top-right, badges + type bottom-right) ──
    kind = tx.get("transaction_kind", "REGULAR")
    is_updated = bool(tx.get("updated_at"))
    _KIND_LABELS = {
        "LOAN_GIVEN": "Loan Given", "LOAN_REPAYMENT": "Loan Repayment",
        "LOAN_TAKEN": "Loan Taken", "EMI_PAYMENT": "EMI Payment",
        "FD_DEPOSIT": "FD Deposit", "DEPOSIT_RECEIVED": "Deposit Received",
        "DEPOSIT_REPAYMENT": "Deposit Repayment",
        "MF_PURCHASE": "MF Purchase", "MF_REDEMPTION": "MF Redemption",
    "FD_WITHDRAWAL": "FD Withdrawal",
    }
    is_wealth = kind in _KIND_LABELS
    amount = tx["amount"]; tx_type = tx["tx_type"]
    if kind == "TRANSFER":
        color = "#6B7280"
        prefix = "−" if tx_type == "DEBIT" else "+"
    elif tx_type == "DEBIT":
        color = "#EF4444"; prefix = "−"
    else:
        color = "#10B981"; prefix = "+"

    amt_col = QVBoxLayout(); amt_col.setSpacing(4)
    amt_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    # Top: amount
    amt_lbl = QLabel(f"{prefix}{fmt_money(amount)}")
    amt_lbl.setStyleSheet(f"color:{color};font-size:16px;font-weight:800;")
    amt_lbl.setAlignment(Qt.AlignRight)
    amt_col.addWidget(amt_lbl)

    # Bottom row: [Updated] [Link Badge] [stretch] [DEBIT/CREDIT]
    bottom = QHBoxLayout()
    bottom.setSpacing(6)
    bottom.setAlignment(Qt.AlignRight)
    if is_updated:
        upd = QLabel("Updated")
        upd.setStyleSheet(
            "color:#4F46E5;background:#EEF2FF;border-radius:10px;"
            "padding:2px 8px;font-size:10px;font-weight:700;border:none;")
        bottom.addWidget(upd)
    if is_wealth:
        lk = QLabel(f"🔗 {_KIND_LABELS.get(kind, kind)}")
        lk.setStyleSheet(
            "color:#4F46E5;background:#EEF2FF;border-radius:10px;"
            "padding:2px 8px;font-size:10px;font-weight:700;border:none;")
        bottom.addWidget(lk)
    if kind == "TRANSFER":
        type_text = f"Transfer ({tx_type})"
    else:
        type_text = tx_type
    type_lbl = QLabel(type_text)
    type_lbl.setStyleSheet(f"color:{color};font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;")
    bottom.addWidget(type_lbl)
    amt_col.addLayout(bottom)

    lay.addLayout(amt_col)
    return card


def _day_header(day_str):
    lbl = QLabel(f"  {day_str}")
    lbl.setStyleSheet("color:#374151;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;padding:8px 0 4px 0;background:transparent;border:none;")
    return lbl

def _month_header(month_str):
    lbl = QLabel(month_str)
    lbl.setStyleSheet("color:#111827;font-size:18px;font-weight:800;padding:12px 0 8px 0;background:transparent;border:none;")
    return lbl


# ═══════════════════════════════════════════════
# STAT CARD
# ═══════════════════════════════════════════════

def _stat_card(label, value, icon, accent):
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{ background:#fff; border:1px solid #E5E7EB; border-radius:14px; }}
        QLabel {{ background:transparent; border:none; }}
    """)
    lay = QVBoxLayout(card); lay.setContentsMargins(18,16,18,16); lay.setSpacing(8)
    il = QLabel(icon); il.setFixedSize(40,40); il.setAlignment(Qt.AlignCenter)
    il.setStyleSheet(f"background:{accent}12;border-radius:20px;font-size:18px;")
    lay.addWidget(il)
    vl = QLabel(str(value)); vl.setStyleSheet(f"color:#111827;font-size:22px;font-weight:800;")
    lay.addWidget(vl)
    ll = QLabel(label); ll.setStyleSheet(f"color:#6B7280;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;")
    lay.addWidget(ll)
    return card


# ═══════════════════════════════════════════════
# ENHANCED ACCOUNT CARD (with start/end balance, type)
# ═══════════════════════════════════════════════

def _acct_card(name, acct_type, credit, debit, net, start_bal, end_bal):
    card = QFrame()
    card.setMinimumSize(240, 155)
    card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    type_color = ACCT_TYPE_COLORS.get(acct_type, "#6B7280")
    icons = {"CURRENT": "\U0001f3e6", "WALLET": "\U0001f45b", "CASH": "\U0001f4b5", "CREDIT_CARD": "\U0001f4b3"}
    icon = icons.get(acct_type, "\U0001f4b0")
    net_color = '#10B981' if net >= 0 else '#EF4444'
    net_sign = '' if net >= 0 else '- '
    card.setStyleSheet(f"""
        QFrame {{ background:#ffffff;
                  border:1px solid #E5E7EB; border-radius:12px; border-top:3px solid {type_color}; }}
        QLabel {{ background:transparent; border:none; }}
    """)
    lay = QVBoxLayout(card); lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(6)

    # Icon + Name + Badge
    top = QHBoxLayout()
    il = QLabel(icon); il.setStyleSheet("font-size:18px;")
    top.addWidget(il)
    nl = QLabel(f"<b>{name}</b>"); nl.setStyleSheet("color:#111827;font-size:13px;")
    top.addWidget(nl); top.addStretch()
    badge = QLabel(acct_type.replace("_", " ").title())
    badge.setStyleSheet(f"color:{type_color};font-size:9px;font-weight:700;background:{type_color}15;border-radius:6px;padding:2px 8px;")
    top.addWidget(badge)
    lay.addLayout(top)

    # Net amount (prominent)
    nv = QLabel(f"{net_sign}{fmt_money(abs(net))}")
    nv.setStyleSheet(f"color:{net_color};font-size:18px;font-weight:900;")
    lay.addWidget(nv)

    # Separator
    sep = QFrame(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:{type_color}30;")
    lay.addWidget(sep)

    # Credits / Debits / Start / End in compact row
    grid = QHBoxLayout(); grid.setSpacing(16)
    for lbl, val, col in [("Credits", credit, "#059669"), ("Debits", debit, "#DC2626"),
                           ("Start", start_bal, "#6B7280"), ("End", end_bal, net_color)]:
        c = QVBoxLayout(); c.setSpacing(1)
        ll = QLabel(lbl); ll.setStyleSheet(f"color:#9CA3AF;font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;")
        c.addWidget(ll)
        vv = QLabel(fmt_money(val)); vv.setStyleSheet(f"color:{col};font-size:12px;font-weight:700;")
        c.addWidget(vv)
        grid.addLayout(c)
    lay.addLayout(grid)

    return card




# ═══════════════════════════════════════════════
# CHART VIEW (write HTML to temp file for reliable loading)
# ═══════════════════════════════════════════════

CHART_TEMPLATE = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI',system-ui,sans-serif; background:#F9FAFB; padding:20px; }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.card { background:#fff; border-radius:16px; padding:24px; box-shadow:0 1px 3px rgba(0,0,0,0.06); border:1px solid #E5E7EB; }
.card.full { grid-column:1 / -1; }
.title { font-size:14px; font-weight:700; color:#374151; margin-bottom:16px; display:flex; align-items:center; gap:8px; }
.dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
canvas { max-height:260px; }
</style>
</head><body>
<div class="grid">
  <div class="card">
    <div class="title"><span class="dot" style="background:#4F46E5"></span>Expense by Category</div>
    <canvas id="c1"></canvas>
  </div>
  <div class="card">
    <div class="title"><span class="dot" style="background:#10B981"></span>Spending by Account</div>
    <canvas id="c2"></canvas>
  </div>
  <div class="card full">
    <div class="title"><span class="dot" style="background:#F59E0B"></span>Daily Cash Flow</div>
    <canvas id="c3" style="max-height:200px"></canvas>
  </div>
  <div class="card full">
    <div class="title"><span class="dot" style="background:#8B5CF6"></span>Need vs Want</div>
    <canvas id="c4" style="max-height:100px"></canvas>
  </div>
</div>
<script>
const COLORS = ['#4F46E5','#10B981','#F59E0B','#EF4444','#8B5CF6','#EC4899','#06B6D4','#F97316','#14B8A6','#6366F1'];

// 1. Category doughnut
new Chart(document.getElementById('c1'), {
    type: 'doughnut',
    data: {
        labels: __CAT_L__,
        datasets: [{ data: __CAT_D__, backgroundColor: COLORS, borderWidth: 3, borderColor: '#fff' }]
    },
    options: {
        responsive: true, maintainAspectRatio: false, cutout: '65%',
        plugins: { legend: { position: 'bottom', labels: { padding: 12, usePointStyle: true, pointStyle: 'circle', font: { size: 11 } } } }
    }
});

// 2. Account horizontal bar
new Chart(document.getElementById('c2'), {
    type: 'bar',
    data: {
        labels: __ACCT_L__,
        datasets: [{ data: __ACCT_D__, backgroundColor: COLORS, borderRadius: 8, borderSkipped: false }]
    },
    options: {
        responsive: true, maintainAspectRatio: false, indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: { x: { grid: { display: false } }, y: { grid: { display: false }, ticks: { font: { size: 12 } } } }
    }
});

// 3. Daily trend line
new Chart(document.getElementById('c3'), {
    type: 'line',
    data: {
        labels: __TREND_L__,
        datasets: [
            { label: 'Credit', data: __TREND_CR__, borderColor: '#10B981', backgroundColor: 'rgba(16,185,129,0.08)', fill: true, tension: 0.4, pointRadius: 4, pointBackgroundColor: '#10B981' },
            { label: 'Debit', data: __TREND_DB__, borderColor: '#EF4444', backgroundColor: 'rgba(239,68,68,0.08)', fill: true, tension: 0.4, pointRadius: 4, pointBackgroundColor: '#EF4444' }
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top', labels: { usePointStyle: true } } },
        scales: { y: { grid: { color: '#F3F4F6' } }, x: { grid: { display: false } } }
    }
});

// 4. Need vs Want — shows amount with percentage
new Chart(document.getElementById('c4'), {
    type: 'bar',
    data: {
        labels: ['Total Spend'],
        datasets: [
            { label: 'Need (₹__NEED__)', data: [__NEED__], backgroundColor: '#4F46E5', borderRadius: 6 },
            { label: 'Want (₹__WANT__)', data: [__WANT__], backgroundColor: '#F59E0B', borderRadius: 6 }
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false, indexAxis: 'y', stacked: true,
        plugins: {
            legend: { position: 'top', labels: { usePointStyle: true, font: { size: 12, weight: '600' } } },
            tooltip: {
                callbacks: {
                    label: function(ctx) {
                        var total = __NEED__ + __WANT__;
                        var pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                        return ctx.dataset.label + ' (' + pct + '%)';
                    }
                }
            }
        },
        scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, grid: { display: false } } }
    }
});
</script>
</body></html>"""


class ChartView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        if _check_webengine():
            from PyQt5.QtWebEngineWidgets import QWebEngineView
            self.view = QWebEngineView()
            lay.addWidget(self.view)
        else:
            self.view = None
            lbl = QLabel("Charts require PyQtWebEngine.\n\nInstall with:\n  pip install PyQtWebEngine\n\nThen restart the app.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:14px;padding:40px;")
            lbl.setAlignment(Qt.AlignCenter)
            lay.addWidget(lbl)

    def render(self, cat_l, cat_d, acct_l, acct_d, trend_l, trend_cr, trend_db, need, want):
        if not self.view: return
        html = CHART_TEMPLATE
        html = html.replace("__CAT_L__", json.dumps(cat_l))
        html = html.replace("__CAT_D__", json.dumps(cat_d))
        html = html.replace("__ACCT_L__", json.dumps(acct_l))
        html = html.replace("__ACCT_D__", json.dumps(acct_d))
        html = html.replace("__TREND_L__", json.dumps(trend_l))
        html = html.replace("__TREND_CR__", json.dumps(trend_cr))
        html = html.replace("__TREND_DB__", json.dumps(trend_db))
        html = html.replace("__NEED__", str(round(need, 2)))
        html = html.replace("__WANT__", str(round(want, 2)))
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.write(html); tmp.close()
        self.view.load(QUrl.fromLocalFile(tmp.name))
        self._tmp_file = tmp.name


# ═══════════════════════════════════════════════
# MAIN DATABASE TAB
# ═══════════════════════════════════════════════

class DatabaseTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db; self.tx_repo = repos["transactions"]
        self.acct = repos["accounts"]; self.lu = repos["lookups"]
        self._fv = []; self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(28,16,28,16); root.setSpacing(14)
        h = QLabel("View Database"); h.setStyleSheet("font-size:24px;font-weight:800;color:#111827;")
        root.addWidget(h)

        main_btns_row = QHBoxLayout(); main_btns_row.setSpacing(8)
        self.main_btns = []
        for txt in ["📋  Complete", "📅  Monthly", "🔍  Filtered"]:
            b = QPushButton(txt); b.setMinimumHeight(36); b.setCursor(Qt.PointingHandCursor)
            main_btns_row.addWidget(b); self.main_btns.append(b)
        main_btns_row.addStretch(); root.addLayout(main_btns_row)

        self.main_stack = QStackedWidget()
        self.main_stack.addWidget(self._build_complete())
        self.main_stack.addWidget(self._build_monthly())
        self.main_stack.addWidget(self._build_filtered())
        root.addWidget(self.main_stack)

        self.main_btns[0].clicked.connect(lambda: self._switch_main(0))
        self.main_btns[1].clicked.connect(lambda: self._switch_main(1))
        self.main_btns[2].clicked.connect(lambda: self._switch_main(2))
        self._switch_main(0)

    def _switch_main(self, idx):
        self.main_stack.setCurrentIndex(idx)
        _switch_tabs(self.main_btns, idx)
        if idx == 0: self._load_complete()

    # ── Helpers ──
    def _running_balances(self, txns):
        acct_bals = {a["account_id"]: a["opening_balance"] for a in self.acct.list_all()}
        sorted_txns = sorted(txns, key=lambda t: (t["tx_date"], t.get("created_at", "")))
        bal_map = {}
        for tx in sorted_txns:
            aid = tx["account_id"]
            prev = acct_bals.get(aid, 0)
            new_bal = prev + tx["amount"] if tx["tx_type"] == "CREDIT" else prev - tx["amount"]
            acct_bals[aid] = new_bal; bal_map[tx["id"]] = new_bal
        return bal_map

    def _group_by_month_day(self, txns):
        months = OrderedDict()
        for tx in sorted(txns, key=lambda t: t["tx_date"], reverse=True):
            d = tx["tx_date"]; mk = d[:7]; dk = d
            if mk not in months: months[mk] = OrderedDict()
            if dk not in months[mk]: months[mk][dk] = []
            months[mk][dk].append(tx)
        return months

    def _build_card_list(self, container, txns):
        bal_map = self._running_balances(txns)
        grouped = self._group_by_month_day(txns)
        for mk, days in grouped.items():
            try:
                y, m = map(int, mk.split("-"))
                container.addWidget(_month_header(date(y, m, 1).strftime("%B %Y")))
            except: container.addWidget(_month_header(mk))
            for dk, day_txns in days.items():
                try: container.addWidget(_day_header(date.fromisoformat(dk).strftime("%A, %d %b")))
                except: container.addWidget(_day_header(dk))
                for tx in day_txns:
                    container.addWidget(_tx_card(tx, bal_map.get(tx["id"])))
        container.addStretch()

    # ═══════════════════════════════════
    # COMPLETE VIEW
    # ═══════════════════════════════════
    def _build_complete(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(8)

        # Search bar
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.comp_search = QLineEdit()
        self.comp_search.setPlaceholderText("\U0001f50d Search by person, description, or amount\u2026")
        self.comp_search.setMinimumHeight(36)
        self.comp_search.setStyleSheet(
            f"QLineEdit{{background:{C['surface']};border:1.5px solid {C['border']};"
            f"border-radius:{C['radius_sm']};padding:8px 12px;font-size:13px;}}"
            f"QLineEdit:focus{{border-color:{C['accent']};}}")
        self.comp_search.returnPressed.connect(self._search_complete)
        search_row.addWidget(self.comp_search, 1)

        search_btn = QPushButton("\U0001f50d Search")
        search_btn.setMinimumHeight(36)
        search_btn.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:white;border:none;"
            f"border-radius:{C['radius_sm']};padding:8px 16px;font-size:13px;font-weight:600;}}"
            f"QPushButton:hover{{background:#4338CA;}}")
        search_btn.clicked.connect(self._search_complete)
        search_row.addWidget(search_btn)

        clear_btn = QPushButton("\u2715 Clear")
        clear_btn.setMinimumHeight(36)
        clear_btn.setStyleSheet(
            f"QPushButton{{background:{C['surface']};color:{C['text2']};"
            f"border:1px solid {C['border']};border-radius:{C['radius_sm']};"
            f"padding:8px 12px;font-size:13px;}}"
            f"QPushButton:hover{{border-color:{C['accent']};color:{C['accent']};}}")
        clear_btn.clicked.connect(self._clear_complete_search)
        search_row.addWidget(clear_btn)
        lay.addLayout(search_row)

        self.comp_search_count = QLabel("")
        self.comp_search_count.setStyleSheet(f"color:{C['text3']};font-size:11px;font-weight:600;")
        lay.addWidget(self.comp_search_count)

        # Scroll area
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        self.comp_lay = QVBoxLayout(inner); self.comp_lay.setSpacing(4); self.comp_lay.setContentsMargins(0,4,0,0)
        self.comp_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        self._comp_scroll = scroll
        scroll.verticalScrollBar().valueChanged.connect(self._on_complete_scroll)
        self._comp_search_active = False
        return w

    def _search_complete(self):
        query = self.comp_search.text().strip().lower()
        if not query:
            self._clear_complete_search()
            return
        self._comp_search_active = True
        while self.comp_lay.count() > 1:
            itm = self.comp_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()
        all_txns = self.tx_repo.list_filters(limit=50000)
        matched = [tx for tx in all_txns
                   if query in (tx.get("person_org") or "").lower()
                   or query in (tx.get("description") or "").lower()
                   or query in (tx.get("cat_name") or "").lower()
                   or query in (tx.get("account_name") or "").lower()
                   or query in str(tx["amount"])]
        self.comp_search_count.setText(f"Found {len(matched)} result(s) for \"{self.comp_search.text().strip()}\"" )
        if not matched:
            lbl = QLabel(f"No transactions match \"{self.comp_search.text().strip()}\".")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:13px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.comp_lay.insertWidget(0, lbl)
            return
        bal_map = self._compute_all_running_balances()
        last_m, last_d = None, None
        at = 0
        for tx in sorted(matched, key=lambda t: t["tx_date"], reverse=True):
            d = tx["tx_date"]; mk = d[:7]
            if mk != last_m:
                try:
                    y, m = map(int, mk.split("-"))
                    hdr = _month_header(date(y, m, 1).strftime("%B %Y"))
                except Exception:
                    hdr = _month_header(mk)
                self.comp_lay.insertWidget(at, hdr); at += 1; last_m = mk; last_d = None
            if d != last_d:
                try:
                    hdr = _day_header(date.fromisoformat(d).strftime("%A, %d %b"))
                except Exception:
                    hdr = _day_header(d)
                self.comp_lay.insertWidget(at, hdr); at += 1; last_d = d
            self.comp_lay.insertWidget(at, _tx_card(tx, bal_map.get(tx["id"]))); at += 1

    def _clear_complete_search(self):
        self.comp_search.clear()
        self.comp_search_count.setText("")
        self._comp_search_active = False
        self._load_complete()

    def _load_complete(self):
        # Reset pagination state
        while self.comp_lay.count() > 1:
            itm = self.comp_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()
        self._comp_offset = 0
        self._comp_has_more = True
        self._comp_loading = False
        self._comp_last_month_key = None
        self._comp_last_day_key = None
        self._comp_page_size = _get_pref(self.db, "complete_page_size", COMPLETE_PAGE_SIZE)
        self._comp_scroll_trigger = _get_pref(self.db, "scroll_trigger_px", SCROLL_TRIGGER_PX)
        self._comp_bal_map = self._compute_all_running_balances()
        self._load_more_complete()

    def _on_complete_scroll(self, value):
        if getattr(self, '_comp_search_active', False):
            return  # don't paginate during search
        sb = self._comp_scroll.verticalScrollBar()
        trigger = getattr(self, '_comp_scroll_trigger', SCROLL_TRIGGER_PX)
        if value >= sb.maximum() - trigger:
            self._load_more_complete()

    def _load_more_complete(self):
        if self._comp_loading or not self._comp_has_more:
            return
        self._comp_loading = True
        page_size = getattr(self, '_comp_page_size', COMPLETE_PAGE_SIZE)
        txns = self.tx_repo.list_filters(limit=page_size, offset=self._comp_offset)
        self._comp_has_more = len(txns) == page_size
        self._comp_offset += len(txns)
        if not txns and self._comp_offset == 0:
            lbl = QLabel("No transactions yet.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:14px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.comp_lay.insertWidget(self.comp_lay.count() - 1, lbl)
            self._comp_loading = False
            return
        insert_at = self.comp_lay.count() - 1  # just before sentinel
        for tx in txns:
            d = tx["tx_date"]; mk = d[:7]
            if mk != self._comp_last_month_key:
                try:
                    y, m = map(int, mk.split("-"))
                    hdr = _month_header(date(y, m, 1).strftime("%B %Y"))
                except Exception:
                    hdr = _month_header(mk)
                self.comp_lay.insertWidget(insert_at, hdr); insert_at += 1
                self._comp_last_month_key = mk
                self._comp_last_day_key = None
            if d != self._comp_last_day_key:
                try:
                    hdr = _day_header(date.fromisoformat(d).strftime("%A, %d %b"))
                except Exception:
                    hdr = _day_header(d)
                self.comp_lay.insertWidget(insert_at, hdr); insert_at += 1
                self._comp_last_day_key = d
            card = _tx_card(tx, self._comp_bal_map.get(tx["id"]))
            self.comp_lay.insertWidget(insert_at, card); insert_at += 1
        self._comp_loading = False

    def _compute_all_running_balances(self):
        """One SQL window function pass for all running balances."""
        rows = self.db.execute("""
            SELECT t.id,
                   a.opening_balance
                   + SUM(CASE WHEN t.tx_type='CREDIT' THEN t.amount ELSE -t.amount END)
                     OVER (PARTITION BY t.account_id ORDER BY t.tx_date, t.created_at) AS running_bal
            FROM transactions t
            JOIN accounts a ON a.account_id = t.account_id
        """).fetchall()
        return {r["id"]: r["running_bal"] for r in rows}

    # ═══════════════════════════════════
    # MONTHLY VIEW
    # ═══════════════════════════════════
    def _build_monthly(self):
        w = QWidget()
        lay = QVBoxLayout(w); lay.setContentsMargins(0,8,0,0); lay.setSpacing(10)

        # ── Appealing month selector ──
        sel_frame = QFrame()
        sel_frame.setStyleSheet(f"""
            QFrame {{ background:#fff; border:1px solid #E5E7EB; border-radius:14px; padding:14px 20px; }}
            QLabel {{ background:transparent; border:none; color:{C['text2']}; font-weight:600; }}
            QComboBox {{ min-width:120px; }}
            QSpinBox {{ min-width:80px; }}
        """)
        sel_lay = QHBoxLayout(sel_frame); sel_lay.setSpacing(14)

        ml = QLabel("📅 Month:"); sel_lay.addWidget(ml)
        self.mm = QComboBox()
        for m in range(1, 13): self.mm.addItem(date(2025, m, 1).strftime("%B"), m)
        self.mm.setCurrentIndex(date.today().month - 1)
        sel_lay.addWidget(self.mm)

        yl = QLabel("Year:"); sel_lay.addWidget(yl)
        self.my = QSpinBox(); self.my.setRange(2020, 2030); self.my.setValue(date.today().year)
        sel_lay.addWidget(self.my)

        rb = QPushButton("  Load  "); rb.setObjectName("primary")
        rb.setMinimumHeight(38); rb.clicked.connect(self._load_monthly)
        sel_lay.addWidget(rb)

        sel_lay.addStretch()

        pb = QPushButton("🖨  Print Statement"); pb.setObjectName("primary")
        pb.setMinimumHeight(38); pb.clicked.connect(self._print_monthly)
        sel_lay.addWidget(pb)

        lay.addWidget(sel_frame)

        # Sub-page buttons
        sub_row = QHBoxLayout(); sub_row.setSpacing(8)
        self.m_sub_btns = []
        for txt in ["Transactions", "Summary", "Visualization"]:
            b = QPushButton(txt); b.setMinimumHeight(34); b.setCursor(Qt.PointingHandCursor)
            sub_row.addWidget(b); self.m_sub_btns.append(b)
        sub_row.addStretch(); lay.addLayout(sub_row)

        self.m_stack = QStackedWidget()
        self.m_stack.addWidget(self._m_txns())
        self.m_stack.addWidget(self._m_summary())
        self.m_stack.addWidget(self._m_viz())
        lay.addWidget(self.m_stack)

        self.m_sub_btns[0].clicked.connect(lambda: self._switch_m(0))
        self.m_sub_btns[1].clicked.connect(lambda: self._switch_m(1))
        self.m_sub_btns[2].clicked.connect(lambda: self._switch_m(2))
        self._switch_m(0)
        return w

    def _switch_m(self, idx):
        self.m_stack.setCurrentIndex(idx)
        _switch_tabs(self.m_sub_btns, idx)
        # Trigger chart resize when viz tab becomes visible
        if idx == 2 and hasattr(self, 'mv') and self.mv and self.mv.view:
            QTimer.singleShot(150, self._force_chart_resize)

    def _force_chart_resize(self):
        """Force QWebEngineView to recalculate layout."""
        if hasattr(self, 'mv') and self.mv and self.mv.view:
            self.mv.view.update()
            # Trigger geometry recalculation
            s = self.mv.view.size()
            self.mv.view.resize(s.width(), s.height() - 1)
            QTimer.singleShot(50, lambda: self.mv.view.resize(s.width(), s.height()))

    def _m_txns(self):
        w = QWidget()
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        self.mt_lay = QVBoxLayout(inner); self.mt_lay.setSpacing(4); self.mt_lay.setContentsMargins(0,4,0,0)
        scroll.setWidget(inner)
        lay = QVBoxLayout(w); lay.setContentsMargins(0,4,0,0); lay.addWidget(scroll)
        return w

    def _m_summary(self):
        """Summary page — KPI cards + scrollable account summary."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(12)

        # KPI area (fixed, not scrollable)
        self.ms_kpi_widget = QWidget()
        self.ms_kpi_lay = QHBoxLayout(self.ms_kpi_widget)
        self.ms_kpi_lay.setSpacing(12)
        self.ms_kpi_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.ms_kpi_widget)

        # Account Summary label
        self.ms_acct_label = QLabel("Account Summary")
        self.ms_acct_label.setStyleSheet(f"font-size:16px;font-weight:700;color:#111827;")
        lay.addWidget(self.ms_acct_label)

        # Scrollable account summary area
        acct_scroll = QScrollArea()
        acct_scroll.setWidgetResizable(True)
        acct_scroll.setFrameShape(QFrame.NoFrame)
        acct_scroll.setStyleSheet("QScrollArea { background: transparent; }")

        acct_inner = QWidget()
        acct_inner.setStyleSheet("background: transparent;")
        self.ms_acct_lay = QVBoxLayout(acct_inner)
        self.ms_acct_lay.setSpacing(16)
        self.ms_acct_lay.setContentsMargins(0, 4, 0, 4)
        acct_scroll.setWidget(acct_inner)

        lay.addWidget(acct_scroll, 1)  # stretch=1 so it takes remaining space
        return w

    def _m_viz(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(0,4,0,0)
        self.mv = ChartView(); lay.addWidget(self.mv); return w

    def _load_monthly(self):
        y = self.my.value(); m = self.mm.currentData()
        txns = self.tx_repo.get_monthly(y, m)

        # Transactions
        while self.mt_lay.count():
            itm = self.mt_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()
        if txns:
            self._build_card_list(self.mt_lay, txns)
        else:
            lbl = QLabel("No transactions this month.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:14px;")
            lbl.setAlignment(Qt.AlignCenter); self.mt_lay.addWidget(lbl)

        self._build_monthly_summary(txns, y, m)
        self._build_monthly_charts(txns)
        self._last_monthly = (y, m, txns)
        # Force chart resize after rendering
        if hasattr(self, 'mv') and self.mv and self.mv.view:
            QTimer.singleShot(300, self._force_chart_resize)

    def _build_monthly_summary(self, txns, y, m):
        # Clear KPI area
        while self.ms_kpi_lay.count():
            itm = self.ms_kpi_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()

        # Clear account area
        while self.ms_acct_lay.count():
            itm = self.ms_acct_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()

        cr = sum(t["amount"] for t in txns if t["tx_type"] == "CREDIT" and t["transaction_kind"] != "TRANSFER")
        db = sum(t["amount"] for t in txns if t["tx_type"] == "DEBIT" and t["transaction_kind"] != "TRANSFER")
        tr = sum(t["amount"] for t in txns if t["transaction_kind"] == "TRANSFER" and t["tx_type"] == "DEBIT")
        net = cr - db

        # 5 KPI cards
        for lbl, val, ico, accent in [
            ("Transactions", str(len(txns)), "📊", "#4F46E5"),
            ("Credits", fmt_money(cr), "📈", "#10B981"),
            ("Debits", fmt_money(db), "📉", "#EF4444"),
            ("Net", fmt_money(net), "💰", "#10B981" if net >= 0 else "#EF4444"),
            ("Transfers", fmt_money(tr), "🔄", "#8B5CF6"),
        ]:
            self.ms_kpi_lay.addWidget(_stat_card(lbl, val, ico, accent))

        # Account data
        all_accts = {a["account_id"]: a for a in self.acct.list_all()}
        acct_data = {}
        for t in txns:
            aid = t["account_id"]
            if aid not in acct_data:
                acct_data[aid] = {"cr": 0, "db": 0}
            if t["tx_type"] == "CREDIT": acct_data[aid]["cr"] += t["amount"]
            else: acct_data[aid]["db"] += t["amount"]

        # Compute start/end balance
        acct_bal_map = {}
        for aid in acct_data:
            a = all_accts.get(aid)
            if not a: continue
            start_bal = a["opening_balance"]
            pre_txns = self.tx_repo.list_filters(account_id=aid, date_to=f"{y:04d}-{m:02d}-01", limit=10000)
            for pt in pre_txns:
                if pt["tx_date"] < f"{y:04d}-{m:02d}-01":
                    if pt["tx_type"] == "CREDIT": start_bal += pt["amount"]
                    else: start_bal -= pt["amount"]
            end_bal = start_bal + acct_data[aid]["cr"] - acct_data[aid]["db"]
            acct_bal_map[aid] = {"start": start_bal, "end": end_bal}

        # Group by type
        type_groups = {}
        for aid, d in acct_data.items():
            a = all_accts.get(aid)
            if not a: continue
            at = a["account_type"]
            if at not in type_groups: type_groups[at] = []
            bal_info = acct_bal_map.get(aid, {"start": 0, "end": 0})
            type_groups[at].append((a, d, bal_info))

        # Update label
        total_accts = sum(len(v) for v in type_groups.values())
        self.ms_acct_label.setText(f"Account Summary ({total_accts} accounts)")

        # Build grouped cards — each group wrapped in a container widget
        for atype in ["CURRENT", "WALLET", "CASH", "CREDIT_CARD"]:
            if atype not in type_groups: continue

            # Group container
            group_widget = QWidget()
            group_widget.setStyleSheet("background: transparent;")
            group_lay = QVBoxLayout(group_widget)
            group_lay.setContentsMargins(0, 0, 0, 0)
            group_lay.setSpacing(8)

            # Type header
            group_label = QLabel(ACCT_TYPE_LABELS.get(atype, atype))
            group_label.setStyleSheet(
                f"color:{ACCT_TYPE_COLORS.get(atype, '#6B7280')};"
                f"font-size:13px;font-weight:700;padding:4px 0;")
            group_lay.addWidget(group_label)

            # Grid of cards — max 3 per row
            grid = QGridLayout()
            grid.setSpacing(14)
            grid.setContentsMargins(0, 0, 0, 4)
            for i, (a, d, bal) in enumerate(type_groups[atype]):
                card = _acct_card(
                    a["display_name"], atype,
                    d["cr"], d["db"], d["cr"] - d["db"],
                    bal["start"], bal["end"])
                grid.addWidget(card, i // 3, i % 3)
            group_lay.addLayout(grid)

            self.ms_acct_lay.addWidget(group_widget)

        self.ms_acct_lay.addStretch()

    def _build_monthly_charts(self, txns):
        if not hasattr(self, 'mv') or not self.mv: return

        # 1. Category doughnut (debits only — what you spent on)
        cats = {}
        for t in txns:
            if t["tx_type"] == "DEBIT":
                cn = t.get("cat_name") or "Other"
                cats[cn] = cats.get(cn, 0) + t["amount"]

        # 2. Spending by Account — ALL account types, total debits
        acct_debits = {}
        for t in txns:
            if t["tx_type"] == "DEBIT":
                an = t.get("account_name") or t["account_id"]
                acct_debits[an] = acct_debits.get(an, 0) + t["amount"]
        # Sort by amount descending
        acct_sorted = sorted(acct_debits.items(), key=lambda x: x[1], reverse=True)
        acct_labels = [a[0] for a in acct_sorted]
        acct_data = [round(a[1], 2) for a in acct_sorted]

        # 3. Daily trend
        daily_cr, daily_db = {}, {}
        for t in txns:
            d = t["tx_date"]
            if t["tx_type"] == "CREDIT": daily_cr[d] = daily_cr.get(d, 0) + t["amount"]
            else: daily_db[d] = daily_db.get(d, 0) + t["amount"]
        all_dates = sorted(set(list(daily_cr.keys()) + list(daily_db.keys())))

        # 4. Need vs Want
        need_total = sum(t["amount"] for t in txns if t.get("neednwant") == 1 and t["tx_type"] == "DEBIT")
        want_total = sum(t["amount"] for t in txns if t.get("neednwant") == 0 and t["tx_type"] == "DEBIT")

        self.mv.render(
            list(cats.keys()), [round(v, 2) for v in cats.values()],
            acct_labels, acct_data,
            [d[5:] for d in all_dates],
            [round(daily_cr.get(d, 0), 2) for d in all_dates],
            [round(daily_db.get(d, 0), 2) for d in all_dates],
            need_total, want_total)

    def _print_monthly(self):
        if not hasattr(self, '_last_monthly'):
            QMessageBox.warning(self, "No Data", "Load a month first."); return
        y, m, txns = self._last_monthly
        filepath, _ = QFileDialog.getSaveFileName(self, "Save PDF", f"Statement_{y}_{m:02d}.pdf", "PDF (*.pdf)")
        if not filepath: return

        # Compute raw numbers (not formatted strings) for accuracy
        cr = sum(t["amount"] for t in txns if t["tx_type"] == "CREDIT" and t["transaction_kind"] != "TRANSFER")
        db = sum(t["amount"] for t in txns if t["tx_type"] == "DEBIT" and t["transaction_kind"] != "TRANSFER")
        tr = sum(t["amount"] for t in txns if t["transaction_kind"] == "TRANSFER" and t["tx_type"] == "DEBIT")
        net = cr - db

        # Build summary as raw numbers — PDF will format them
        summary = {"credits": cr, "debits": db, "net": net, "transfers": tr}

        # Build per-account data with start/end balances (raw numbers)
        all_accts = {a["account_id"]: a for a in self.acct.list_all()}
        acct_data = {}
        for t in txns:
            aid = t["account_id"]
            if aid not in acct_data:
                acct_data[aid] = {"cr": 0, "db": 0}
            if t["tx_type"] == "CREDIT": acct_data[aid]["cr"] += t["amount"]
            else: acct_data[aid]["db"] += t["amount"]

        # Compute start/end balances per account
        acct_bal_map = {}
        for aid in acct_data:
            a = all_accts.get(aid)
            if not a: continue
            start_bal = a["opening_balance"]
            pre_txns = self.tx_repo.list_filters(account_id=aid, date_to=f"{y:04d}-{m:02d}-01", limit=10000)
            for pt in pre_txns:
                if pt["tx_date"] < f"{y:04d}-{m:02d}-01":
                    if pt["tx_type"] == "CREDIT": start_bal += pt["amount"]
                    else: start_bal -= pt["amount"]
            end_bal = start_bal + acct_data[aid]["cr"] - acct_data[aid]["db"]
            acct_bal_map[aid] = {"start": start_bal, "end": end_bal}

        from services.report_service import export_monthly_pdf
        doc_id = export_monthly_pdf(
            filepath, date(y, m, 1).strftime("%B"), y,
            summary, acct_data, acct_bal_map, all_accts, txns)
        if doc_id:
            self._show_pdf_done(filepath, doc_id)
        else:
            QMessageBox.warning(self, "Error", "Install reportlab: pip install reportlab")

    # ═══════════════════════════════════
    # ═══════════════════════════════════
    # FILTERED VIEW  (per-value chips, robust multi-value)
    # ═══════════════════════════════════

    # ── Internal filter storage ──
    # self._fv = [ {"key":"category","label":"Category","vals":["food_dining","shopping"],
    #               "disp":["Food & Dining","Shopping"]}, ... ]
    # Each entry = one filter field, vals list = OR-combined values.

    def _build_filtered(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(6)

        # ── Single-line filter bar ──
        bar = QFrame()
        bar.setStyleSheet("QFrame{background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:8px 12px;}")
        row = QHBoxLayout(bar)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(6)

        # From date
        row.addWidget(QLabel("From"))
        self.f_date_from = QDateEdit()
        self.f_date_from.setDate(QDate.currentDate().addMonths(-1))
        self.f_date_from.setCalendarPopup(True)
        self.f_date_from.setMinimumHeight(34)
        self.f_date_from.setMaximumWidth(120)
        row.addWidget(self.f_date_from)

        # To date
        row.addWidget(QLabel("To"))
        self.f_date_to = QDateEdit()
        self.f_date_to.setDate(QDate.currentDate())
        self.f_date_to.setCalendarPopup(True)
        self.f_date_to.setMinimumHeight(34)
        self.f_date_to.setMaximumWidth(120)
        row.addWidget(self.f_date_to)

        # Divider
        div = QFrame(); div.setFixedHeight(24); div.setFixedWidth(1)
        div.setStyleSheet(f"background:{C['border']};")
        row.addWidget(div)

        # Filter mode toggle
        self._filter_exact = True
        self.mode_btn = QPushButton("🎯 Exact")
        self.mode_btn.setMinimumHeight(34)
        self.mode_btn.setCursor(Qt.PointingHandCursor)
        self._style_mode_btn()
        self.mode_btn.clicked.connect(self._toggle_mode)
        row.addWidget(self.mode_btn)

        # Filter field selector
        row.addWidget(QLabel("Filter"))
        self.fc = QComboBox()
        for f in FILTER_FIELDS: self.fc.addItem(f["label"], f["key"])
        self.fc.setMinimumHeight(34); self.fc.setMaximumWidth(130)
        row.addWidget(self.fc)

        # Filter value (dynamic)
        self.fstk = QStackedWidget()
        self.ft_combo = QComboBox(); self.ft_combo.setMinimumHeight(34)
        self.ft_text = QLineEdit(); self.ft_text.setMinimumHeight(34)
        self.ft_num = QDoubleSpinBox(); self.ft_num.setPrefix("₹ ")
        self.ft_num.setRange(0,99999999); self.ft_num.setMinimumHeight(34)
        self.fstk.addWidget(self.ft_combo); self.fstk.addWidget(self.ft_text); self.fstk.addWidget(self.ft_num)
        row.addWidget(self.fstk, 1)

        # Load button
        lb = QPushButton("⟳ Load")
        lb.setObjectName("primary")
        lb.setMinimumWidth(80); lb.setMinimumHeight(34)
        lb.setCursor(Qt.PointingHandCursor)
        lb.clicked.connect(self._load_filtered)
        row.addWidget(lb)

        # Add button
        ab = QPushButton("+ Add")
        ab.setMinimumWidth(80); ab.setMinimumHeight(34)
        ab.setStyleSheet(f"QPushButton{{background:{C['surface']};color:{C['text2']};border:1px solid {C['border']};border-radius:8px;font-size:13px;font-weight:600;}}QPushButton:hover{{border-color:{C['accent']};color:{C['accent']};}}")
        ab.setCursor(Qt.PointingHandCursor)
        ab.clicked.connect(self._add_f)
        row.addWidget(ab)

        lay.addWidget(bar)

        # ── Chips row (wrapping, minimal gap) ──
        self.chips_wrap = QWidget()
        self.chips_wrap.setStyleSheet("background:transparent;")
        self.chips_grid = QVBoxLayout(self.chips_wrap)
        self.chips_grid.setContentsMargins(4, 2, 4, 2)
        self.chips_grid.setSpacing(2)
        lay.addWidget(self.chips_wrap)

        # ── Stats + Clear + Print ──
        bottom = QHBoxLayout()
        bottom.setContentsMargins(4, 0, 4, 0)
        self.f_stats = QLabel("")
        self.f_stats.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        bottom.addWidget(self.f_stats)
        bottom.addStretch()
        fp = QPushButton("🖨 Print"); fp.setObjectName("primary"); fp.setFixedHeight(26)
        fp.clicked.connect(self._print_filtered); bottom.addWidget(fp)
        cb = QPushButton("Clear All"); cb.setObjectName("ghost"); cb.setFixedHeight(26)
        cb.clicked.connect(self._clear_f); bottom.addWidget(cb)
        lay.addLayout(bottom)

        # ── Results ──
        self._fv = []   # list of filter-value dicts
        self.fc.currentIndexChanged.connect(self._on_field); self._on_field(0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        self.ft_lay = QVBoxLayout(inner); self.ft_lay.setSpacing(4); self.ft_lay.setContentsMargins(0,4,0,0)
        scroll.setWidget(inner); lay.addWidget(scroll, 1)
        return w

    def _style_mode_btn(self):
        if self._filter_exact:
            self.mode_btn.setText("🎯 Exact")
            self.mode_btn.setStyleSheet(f"QPushButton{{background:{C['accent_bg']};color:{C['accent']};border:1px solid {C['accent']};border-radius:8px;padding:6px 10px;font-size:11px;font-weight:600;}}QPushButton:hover{{background:{C['accent']};color:white;}}")
        else:
            self.mode_btn.setText("🔗 Sequential")
            self.mode_btn.setStyleSheet(f"QPushButton{{background:{C['amber_bg']};color:{C['amber']};border:1px solid {C['amber']};border-radius:8px;padding:6px 10px;font-size:11px;font-weight:600;}}QPushButton:hover{{background:{C['amber']};color:white;}}")

    def _toggle_mode(self):
        self._filter_exact = not self._filter_exact
        self._style_mode_btn()
        if self._fv: self._load_filtered()

    # ── Populate value combo / text / number based on selected field ──
    def _on_field(self, idx):
        key = self.fc.currentData()
        field = next((f for f in FILTER_FIELDS if f["key"] == key), None)
        if not field:
            return
        if field["type"] == "combo":
            self.fstk.setCurrentIndex(0)
            self.ft_combo.clear()
            # Build set of already-selected values for THIS field
            existing = set()
            for fe in self._fv:
                if fe["key"] == key:
                    existing = set(fe["vals"])
                    break
            if "source" in field:
                src = field["source"]
                items = []
                if src == "accounts":
                    items = [(a["display_name"], a["account_id"]) for a in self.acct.list_active()]
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

    # ── Add a filter value ──
    def _add_f(self):
        key = self.fc.currentData()
        field = next((f for f in FILTER_FIELDS if f["key"] == key), None)
        if not field:
            return

        if field["type"] == "combo":
            val = self.ft_combo.currentText()
            data = self.ft_combo.currentData()
            if data is None:
                return
            # Find existing entry for this key
            entry = None
            for fe in self._fv:
                if fe["key"] == key:
                    entry = fe
                    break
            if entry is not None:
                if data in entry["vals"]:
                    return  # already added
                entry["vals"].append(data)
                entry["disp"].append(val)
            else:
                self._fv.append({
                    "key": key, "label": field["label"],
                    "vals": [data], "disp": [val],
                })
        elif field["type"] == "text":
            val = self.ft_text.text().strip()
            if not val:
                return
            # Replace any existing text filter for same key
            self._fv = [fe for fe in self._fv if fe["key"] != key]
            self._fv.append({
                "key": key, "label": field["label"],
                "vals": [val], "disp": [val],
            })
        else:
            v = self.ft_num.value()
            if v <= 0:
                return
            self._fv = [fe for fe in self._fv if fe["key"] != key]
            self._fv.append({
                "key": key, "label": field["label"],
                "vals": [v], "disp": [fmt_money(v)],
            })

        self._rebuild_chips()
        self._on_field(self.fc.currentIndex())
        self._load_filtered()

    def _clear_f(self):
        self._fv = []
        self._rebuild_chips()
        self._on_field(self.fc.currentIndex())
        self._load_filtered()

    # ── Chips: FlowLayout wrapping — chips flow to next row naturally ──
    def _rebuild_chips(self):
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
                chip = QPushButton(f" {disp} ✕")
                chip.setStyleSheet(
                    f"QPushButton{{background:{C['accent_bg']};color:{C['accent']};"
                    f"border:1px solid rgba(79,70,229,0.2);border-radius:12px;"
                    f"padding:2px 8px;font-size:11px;font-weight:600;}}"
                    f"QPushButton:hover{{background:#D6DEFF;}}")
                chip.setCursor(QCursor(Qt.PointingHandCursor))
                chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                val_to_remove = entry["vals"][i]
                chip.clicked.connect(
                    lambda _, k=key, v=val_to_remove: self._remove_value(k, v))
                fl.addWidget(chip)

        self.chips_grid.addWidget(container)

    def _remove_value(self, key, val):
        """Remove a single value from a filter entry. If last value, remove entry."""
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
        self._rebuild_chips()
        self._on_field(self.fc.currentIndex())
        self._load_filtered()

    # ── Apply all active filters to transaction list ──
    def _apply_filters(self, txns):
        for fe in self._fv:
            key = fe["key"]
            vals = fe["vals"]
            if key == "account":
                txns = [t for t in txns if t.get("account_id") in vals]
            elif key == "category":
                txns = [t for t in txns if t.get("category") in vals]
            elif key == "method":
                txns = [t for t in txns if t.get("pay_method") in vals]
            elif key == "tx_type":
                txns = [t for t in txns if t.get("tx_type") in vals]
            elif key == "kind":
                txns = [t for t in txns if t.get("transaction_kind", "REGULAR") in vals]
            elif key == "neednwant":
                nw_map = {"Need": 1, "Want": 0, "None": 2}
                nw_ints = [nw_map.get(v, -1) for v in vals]
                txns = [t for t in txns if t.get("neednwant") in nw_ints]
            elif key == "pf_category":
                txns = [t for t in txns if t.get("pf_category") in vals]
            elif key == "person_org":
                p = vals[0].lower()
                txns = [t for t in txns if p in (t.get("person_org") or "").lower()]
            elif key == "description":
                d = vals[0].lower()
                txns = [t for t in txns if d in (t.get("description") or "").lower()]
            elif key == "min_amount":
                txns = [t for t in txns if t["amount"] >= vals[0]]
            elif key == "max_amount":
                txns = [t for t in txns if t["amount"] <= vals[0]]
        return txns

    def _load_filtered(self):
        # Clear results
        while self.ft_lay.count():
            itm = self.ft_lay.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()

        d_from = self.f_date_from.date().toString("yyyy-MM-dd")
        d_to = self.f_date_to.date().toString("yyyy-MM-dd")

        if self._filter_exact:
            # EXACT: fetch all in date range, then client-side filter
            txns = self.tx_repo.list_filters(limit=5000, date_from=d_from, date_to=d_to)
            txns = self._apply_filters(txns)
        else:
            # SEQUENTIAL: narrow via DB for single-value filters, rest client-side
            kw = {"limit": 5000, "date_from": d_from, "date_to": d_to}
            for fe in self._fv:
                key, vals = fe["key"], fe["vals"]
                if len(vals) != 1:
                    continue  # multi-value → let client-side handle
                if key == "account":
                    kw["account_id"] = vals[0]
                elif key == "category":
                    kw["category"] = vals[0]
                elif key == "tx_type":
                    kw["tx_type"] = vals[0]
                elif key == "kind":
                    kw["kind"] = vals[0]
            txns = self.tx_repo.list_filters(**kw)
            txns = self._apply_filters(txns)

        cr = sum(t["amount"] for t in txns if t["tx_type"] == "CREDIT")
        db = sum(t["amount"] for t in txns if t["tx_type"] == "DEBIT")
        mode = "Exact" if self._filter_exact else "Sequential"
        self.f_stats.setText(
            f"{mode} | {len(txns)} txns | Cr:{fmt_money(cr)} | Db:{fmt_money(db)} | Net:{fmt_money(cr - db)}")

        self._last_filtered = txns  # store for print

        if txns:
            self._build_card_list(self.ft_lay, txns)
        else:
            lbl = QLabel("No matching transactions.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:14px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.ft_lay.addWidget(lbl)

    def _print_filtered(self):
        """Print filtered results as PDF — same layout as monthly statement."""
        if not hasattr(self, '_last_filtered') or not self._last_filtered:
            QMessageBox.warning(self, "No Data", "Apply filters first.")
            return
        txns = self._last_filtered
        d_from = self.f_date_from.date().toString("yyyy-MM-dd")
        d_to = self.f_date_to.date().toString("yyyy-MM-dd")
        period = f"{self.f_date_from.date().toString('dd MMM yyyy')} \u2014 {self.f_date_to.date().toString('dd MMM yyyy')}"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", f"Filtered_{d_from}_to_{d_to}.pdf", "PDF (*.pdf)")
        if not filepath: return

        # Build filter description for PDF header
        filter_desc = []
        for fe in self._fv:
            filter_desc.append(f"{fe['label']}: {', '.join(fe['disp'])}")
        filter_str = " | ".join(filter_desc) if filter_desc else period

        # Raw numbers
        cr = sum(t["amount"] for t in txns if t["tx_type"] == "CREDIT" and t.get("transaction_kind", "REGULAR") != "TRANSFER")
        db = sum(t["amount"] for t in txns if t["tx_type"] == "DEBIT" and t.get("transaction_kind", "REGULAR") != "TRANSFER")
        tr = sum(t["amount"] for t in txns if t.get("transaction_kind") == "TRANSFER" and t["tx_type"] == "DEBIT")
        summary = {"credits": cr, "debits": db, "net": cr - db, "transfers": tr}

        # Per-account data
        all_accts = {a["account_id"]: a for a in self.acct.list_all()}
        acct_data = {}
        for t in txns:
            aid = t["account_id"]
            if aid not in acct_data: acct_data[aid] = {"cr": 0, "db": 0}
            if t["tx_type"] == "CREDIT": acct_data[aid]["cr"] += t["amount"]
            else: acct_data[aid]["db"] += t["amount"]

        # Start/end balances per account
        acct_bal_map = {}
        for aid in acct_data:
            a = all_accts.get(aid)
            if not a: continue
            start_bal = a["opening_balance"]
            pre_txns = self.tx_repo.list_filters(account_id=aid, date_to=d_from, limit=10000)
            for pt in pre_txns:
                if pt["tx_date"] < d_from:
                    if pt["tx_type"] == "CREDIT": start_bal += pt["amount"]
                    else: start_bal -= pt["amount"]
            end_bal = start_bal + acct_data[aid]["cr"] - acct_data[aid]["db"]
            acct_bal_map[aid] = {"start": start_bal, "end": end_bal}

        from services.report_service import export_monthly_pdf
        doc_id = export_monthly_pdf(
            filepath, f"Filtered ({period})", filter_str,
            summary, acct_data, acct_bal_map, all_accts, txns,
            report_type="filtered")
        if doc_id:
            self._show_pdf_done(filepath, doc_id)
        else:
            QMessageBox.warning(self, "Error", "Install reportlab: pip install reportlab")

    def _show_pdf_done(self, filepath, doc_id):
        """Show PDF saved dialog with 'Open PDF' button."""
        dlg = QMessageBox(self)
        dlg.setWindowTitle("PDF Saved")
        dlg.setIcon(QMessageBox.Information)
        dlg.setText(f"PDF saved successfully.\n\nDoc ID: {doc_id}")
        open_btn = dlg.addButton("  Open PDF  ", QMessageBox.AcceptRole)
        dlg.addButton("Close", QMessageBox.RejectRole)
        dlg.exec_()
        if dlg.clickedButton() == open_btn:
            try:
                if sys.platform == "win32":
                    os.startfile(filepath)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", filepath])
                else:
                    subprocess.Popen(["xdg-open", filepath])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open PDF:\n{e}")

    def refresh(self):
        _refresh_cat_icons(self.db)
        self._load_complete()
