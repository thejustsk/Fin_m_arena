"""Home tab — Visual dashboard with KPI period switchers and Chart.js charts."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QScrollArea, QSizePolicy)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer, QUrl
from PyQt5.QtGui import QCursor
from datetime import datetime, date, timedelta
from collections import OrderedDict
from ui.theme import C, apply_chart_theme
from ui.widgets.count_up import animate_value
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tx_card, _day_header, ChartView
from services.nw_constants import split_need_want
import json


# ── Chart HTML template for Home (4 charts) ──
HOME_CHART_TEMPLATE = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
html, body { min-height:100%; background:__PAGE_BG__; }
body { font-family:'Segoe UI',system-ui,sans-serif; padding:12px; overflow-y:auto; overflow-x:hidden; }
body::-webkit-scrollbar { width:9px; }
body::-webkit-scrollbar-track { background:__SCROLL_TRACK__; }
body::-webkit-scrollbar-thumb { background:__SCROLL_THUMB__; border-radius:5px; }
body::-webkit-scrollbar-thumb:hover { background:__TICK__; }
.grid { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:14px; width:100%; }
.card { min-width:0; background:__CARD_BG__; border-radius:12px; padding:18px; box-shadow:0 1px 3px __SHADOW__; border:1px solid __CARD_BORDER__; }
.card.full { grid-column:1 / -1; }
.title { font-size:12px; font-weight:700; color:__TITLE__; margin-bottom:10px; display:flex; align-items:center; gap:8px; }
.dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
canvas { width:100% !important; }
#c1, #c2 { max-height:200px; }
#c3 { max-height:70px; }
/* Account chart owns its height: each account receives a readable bar row,
   while only this inner panel scrolls for long account lists. */
.account-legend { font-size:11px; color:__TICK__; display:flex; gap:8px; align-items:center; margin-bottom:8px; }
.income-dot,.expense-dot { width:9px; height:9px; border-radius:3px; display:inline-block; }
.income-dot { background:#10B981; } .expense-dot { background:#EF4444; }
.account-rows { overflow:visible; padding-right:6px; border-radius:0 0 10px 10px; }
.account-row { display:grid; grid-template-columns:minmax(105px,28%) 1fr; gap:10px; align-items:center; min-height:52px; border-bottom:1px solid __GRID__; }
.account-name { color:__TICK__; font-size:11px; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; text-align:right; padding-right:8px; }
.account-bars { display:flex; flex-direction:column; gap:5px; }
.account-bar-line { display:flex; align-items:center; gap:6px; }
.account-bar { height:14px; min-width:3px; border-radius:4px; }
.account-value { color:__TICK__; font-size:10px; white-space:nowrap; }
@media (max-width:760px) { .grid { grid-template-columns:minmax(0,1fr); } .card.full { grid-column:auto; } }
</style>
</head><body>
<div class="grid">
  <div class="card">
    <div class="title"><span class="dot" style="background:#4F46E5"></span>Spending by Category</div>
    <canvas id="c1"></canvas>
  </div>
  <div class="card">
    <div class="title"><span class="dot" style="background:#10B981"></span>Spending Trend</div>
    <canvas id="c2"></canvas>
  </div>
  <div class="card full">
    <div class="title"><span class="dot" style="background:#F59E0B"></span>Need vs Want</div>
    <canvas id="c3" style="max-height:70px"></canvas>
  </div>
  <div class="card full">
    <div class="title"><span class="dot" style="background:#8B5CF6"></span>Income vs Expense by Account</div>
    <div class="account-legend"><span class="income-dot"></span> Income <span class="expense-dot"></span> Expense</div>
    <div id="accountRows" class="account-rows"></div>
  </div>
</div>
<script>
const COLORS = ['#4F46E5','#10B981','#F59E0B','#EF4444','#8B5CF6','#EC4899','#06B6D4','#F97316','#14B8A6','#6366F1'];

new Chart(document.getElementById('c1'), {
    type: 'doughnut',
    data: {
        labels: __CAT_L__,
        datasets: [{ data: __CAT_D__, backgroundColor: COLORS, borderWidth: 3, borderColor: '#fff' }]
    },
    options: {
        responsive: true, maintainAspectRatio: false, cutout: '65%',
        plugins: { legend: { position: 'bottom', labels: { padding: 10, usePointStyle: true, pointStyle: 'circle', font: { size: 10 } } } }
    }
});

var todayIdx = __TODAY_IDX__;
var trendData = __TREND_D__;
var pointBg = trendData.map(function(_, i) { return i === todayIdx ? '#EF4444' : '#4F46E5'; });
var pointR = trendData.map(function(_, i) { return i === todayIdx ? 7 : 3; });
var pointBorder = trendData.map(function(_, i) { return i === todayIdx ? '#fff' : '#4F46E5'; });
var borderWidth = trendData.map(function(_, i) { return i === todayIdx ? 3 : 0; });

new Chart(document.getElementById('c2'), {
    type: 'line',
    data: {
        labels: __TREND_L__,
        datasets: [{
            label: 'Spending', data: trendData,
            borderColor: '#4F46E5', backgroundColor: 'rgba(79,70,229,0.08)',
            fill: true, tension: 0.4,
            pointRadius: pointR,
            pointBackgroundColor: pointBg,
            pointBorderColor: pointBorder,
            pointBorderWidth: borderWidth
        }]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { grid: { color: '__GRID__' } }, x: { grid: { display: false } } }
    }
});

new Chart(document.getElementById('c3'), {
    type: 'bar',
    data: {
        labels: ['Spending'],
        datasets: [
            { label: 'Need', data: [__NEED__], backgroundColor: '#4F46E5', borderRadius: 6 },
            { label: 'Want', data: [__WANT__], backgroundColor: '#F59E0B', borderRadius: 6 },
            { label: 'Not Set', data: [__NONE__], backgroundColor: '#9CA3AF', borderRadius: 6 }
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false, indexAxis: 'y', stacked: true,
        plugins: {
            legend: { position: 'top', labels: { usePointStyle: true, font: { size: 11, weight: '600' } } },
            tooltip: {
                callbacks: {
                    label: function(ctx) {
                        var total = __NEED__ + __WANT__ + __NONE__;
                        var pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                        var val = '₹' + ctx.raw.toLocaleString('en-IN');
                        return ctx.dataset.label + ': ' + val + ' (' + pct + '%)';
                    }
                }
            }
        },
        scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, grid: { display: false } } }
    }
});

// 4. Income vs Expense by Account — fixed legend/name column; only bar rows scroll.
var acctLabels = __ACCT_L__;
var acctIncome = __ACCT_CR__;
var acctExpense = __ACCT_DB__;
var accountRows = document.getElementById('accountRows');
var maxAccountValue = Math.max(1, ...acctIncome, ...acctExpense);
acctLabels.forEach(function(name, i) {
    var row = document.createElement('div'); row.className = 'account-row';
    var label = document.createElement('div'); label.className = 'account-name'; label.title = name; label.textContent = name;
    var bars = document.createElement('div'); bars.className = 'account-bars';
    [['#10B981', acctIncome[i] || 0], ['#EF4444', acctExpense[i] || 0]].forEach(function(pair) {
        var line=document.createElement('div'); line.className='account-bar-line';
        var bar=document.createElement('div'); bar.className='account-bar'; bar.style.background=pair[0]; bar.style.width=Math.max(2,(pair[1]/maxAccountValue)*100)+'%';
        var value=document.createElement('span'); value.className='account-value'; value.textContent='₹'+Number(pair[1]).toLocaleString('en-IN');
        line.appendChild(bar); line.appendChild(value); bars.appendChild(line);
    });
    row.appendChild(label); row.appendChild(bars); accountRows.appendChild(row);
});
</script>
</body></html>"""


class KPICard(QFrame):
    """Selectable KPI card — layout created once, content updated via methods."""
    clicked = pyqtSignal(str)

    def __init__(self, period, label, parent=None):
        super().__init__(parent)
        self.period = period
        self._selected = False
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMinimumHeight(80)

        # Create layout ONCE
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(4)

        self._lbl = QLabel(f"💸  {label} · Expense")
        lay.addWidget(self._lbl)

        self._amt = QLabel("₹0")
        lay.addWidget(self._amt)

        self._cnt = QLabel("0 txns")
        lay.addWidget(self._cnt)

        self._update_style()

    def set_data(self, amount, count, replay=False):
        """Set the KPI value; replay selected-period values from zero on click."""
        if isinstance(amount, (int, float)):
            animate_value(self._amt, amount, fmt_money, old_value=0 if replay else None)
        else:
            self._amt.setText(str(amount))
        suffix = "txn" if count == 1 else "txns"
        self._cnt.setText(f"{count} {suffix}")
        self._update_style()

    def set_selected(self, selected):
        self._selected = selected
        self._update_style()

    def _update_style(self):
        if self._selected:
            self.setStyleSheet(
                f"QFrame{{background:{C['accent']};border:none;border-radius:12px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            self._lbl.setStyleSheet("color:rgba(255,255,255,0.7);font-size:10px;font-weight:700;letter-spacing:1px;")
            self._amt.setStyleSheet("color:white;font-size:18px;font-weight:800;")
            self._cnt.setStyleSheet("color:rgba(255,255,255,0.7);font-size:11px;font-weight:600;")
        else:
            self.setStyleSheet(
                f"QFrame{{background:{C['surface']};border:1px solid {C['border']};border-radius:12px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            self._lbl.setStyleSheet(f"color:{C['text3']};font-size:10px;font-weight:700;letter-spacing:1px;")
            self._amt.setStyleSheet(f"color:{C['text']};font-size:18px;font-weight:800;")
            self._cnt.setStyleSheet(f"color:{C['text3']};font-size:11px;font-weight:600;")

    def mousePressEvent(self, event):
        self.clicked.emit(self.period)


class HomeTab(QWidget):
    go = pyqtSignal(str)

    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self.repos = repos
        self.bal = services["balance"]
        self.tx = repos["transactions"]
        self.acct = repos["accounts"]
        self.lu = repos["lookups"]
        self._period = "month"
        # Debounce sidebar/window resize events. Repainting Chart.js on every
        # animation frame looks jittery; one redraw after geometry settles is smooth.
        self._chart_resize_timer = QTimer(self)
        self._chart_resize_timer.setSingleShot(True)
        self._chart_resize_timer.timeout.connect(self._force_resize)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 24, 40, 24)
        root.setSpacing(16)

        # ── Top: Greeting + Date ──
        top_row = QHBoxLayout()
        self.greet = QLabel(self._greeting_text())
        self.greet.setStyleSheet(f"font-size:28px;font-weight:800;color:{C['text']};")
        top_row.addWidget(self.greet)
        top_row.addStretch()
        today_lbl = QLabel(date.today().strftime("%A, %d %B %Y"))
        today_lbl.setStyleSheet(f"font-size:14px;color:{C['text3']};font-weight:600;")
        top_row.addWidget(today_lbl)
        root.addLayout(top_row)

        # ── Subtitle ──
        sub = QLabel("Welcome to your financial summary...")
        sub.setStyleSheet(f"font-size:14px;color:{C['text3']};margin-top:-4px;")
        root.addWidget(sub)

        # ── KPI Period Cards ──
        self.kpi_row = QHBoxLayout()
        self.kpi_row.setSpacing(12)
        self.kpi_cards = {}
        for period, label in [("today", "Today"), ("week", "This Week"), ("month", "This Month"), ("year", "This Year")]:
            card = KPICard(period, label)
            card.clicked.connect(self._on_period)
            self.kpi_cards[period] = card
            self.kpi_row.addWidget(card)
        root.addLayout(self.kpi_row)

        # ── Two-column: Charts + Insights ──
        cols = QHBoxLayout()
        cols.setSpacing(20)

        # LEFT: Charts
        self.chart_view = ChartView()
        cols.addWidget(self.chart_view, 3)

        # RIGHT: Top Transactions + Savings
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        top_tx_title = QLabel("💸  Top Spends")
        top_tx_title.setStyleSheet(f"font-size:15px;font-weight:700;color:{C['text']};")
        right_col.addWidget(top_tx_title)
        top_scroll=QScrollArea(); top_scroll.setWidgetResizable(True); top_scroll.setFrameShape(QFrame.NoFrame)
        top_scroll.setMaximumHeight(260)
        top_scroll.setStyleSheet(
            f"QScrollArea{{background:transparent;border:none;}}"
            f"QScrollBar:vertical{{background:{C['surface2']};width:8px;border-radius:4px;}}"
            f"QScrollBar::handle:vertical{{background:{C['border']};min-height:24px;border-radius:4px;}}"
            f"QScrollBar::handle:vertical:hover{{background:{C['text3']};}}")
        top_inner = QWidget(); top_inner.setStyleSheet("background:transparent;")
        self.top_lay = QVBoxLayout(top_inner); self.top_lay.setSpacing(3); self.top_lay.setContentsMargins(0,0,0,0)
        top_scroll.setWidget(top_inner)
        right_col.addWidget(top_scroll)

        rem_title = QLabel("🔔  Reminders")
        rem_title.setStyleSheet(f"font-size:15px;font-weight:700;color:{C['text']};")
        right_col.addWidget(rem_title)
        rem_box = QFrame(); rem_box.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;}}")
        self.rem_lay = QVBoxLayout(rem_box); self.rem_lay.setContentsMargins(8,8,8,8); self.rem_lay.setSpacing(5)
        right_col.addWidget(rem_box, 1)

        # Savings Rate card
        self.savings_card = QFrame()
        self.savings_card.setStyleSheet(
            f"QFrame{{background:{C['surface']};border:1px solid {C['border']};border-radius:12px;}}"
            f"QLabel{{background:transparent;border:none;}}")
        self.savings_inner = QVBoxLayout(self.savings_card)
        self.savings_inner.setContentsMargins(16, 12, 16, 12)
        self.savings_inner.setSpacing(6)
        right_col.addWidget(self.savings_card)

        cols.addLayout(right_col, 2)
        root.addLayout(cols, 1)

        # ── Quick Access ──
        qa_row = QHBoxLayout()
        qa_row.setSpacing(10)
        tiles = [
            ("📝", "Transactions", "transaction_entry", C['accent']),
            ("🗄️", "Database", "database", "#8B5CF6"),
            ("💰", "Balances", "balances", C['green']),
            ("💳", "Credit Cards", "cards", C['red']),
            ("🏧", "Debit Cards", "debit_cards", "#F59E0B"),
            ("🤝", "Split", "split", "#7C3AED"),
            ("🔍", "Audit", "audit", C['amber']),
            ("📈", "Wealth", "wealth", "#10B981"),
            ("📋", "Notes", "notes", "#EC4899"),
            ("⚙️", "Settings", "settings", C['text3']),
            ("📧", "Gmail", "gmail", "#06B6D4"),
        ]
        for ico, lbl, key, col in tiles:
            t = QFrame()
            t.setObjectName("tile")
            t.setMinimumHeight(44)
            t.setCursor(QCursor(Qt.PointingHandCursor))
            t.setStyleSheet(
                f"QFrame#tile{{background:{C['surface']};border:1px solid {C['border']};"
                f"border-left:3px solid {col};border-radius:8px;}}"
                f"QFrame#tile:hover{{border-color:{col};background:{C['surface2']};}}")
            tl = QHBoxLayout(t)
            tl.setContentsMargins(12, 4, 12, 4)
            tl.setSpacing(6)
            il = QLabel(ico)
            il.setStyleSheet("font-size:16px;")
            il.setFixedWidth(22)
            tl.addWidget(il)
            nl = QLabel(lbl)
            nl.setStyleSheet(f"font-size:11px;font-weight:600;color:{C['text']};")
            tl.addWidget(nl, 1)
            t.mousePressEvent = lambda e, k=key: self.go.emit(k)
            qa_row.addWidget(t)
        root.addLayout(qa_row)

    def _on_period(self, period):
        self._period = period
        for p, card in self.kpi_cards.items():
            card.set_selected(p == period)
        self._load_data()

    def _greeting_text(self):
        """"Good Morning, Alex ☀️" — falls back to no name when unset."""
        h = datetime.now().hour
        icon = "\u2600\ufe0f" if h < 12 else ("\U0001f324\ufe0f" if h < 17 else "\U0001f319")
        try:
            from services.user_service import get_user_name, greeting_for
            part = greeting_for(h)
            name = get_user_name(self.db)
        except Exception:
            part = "Morning" if h < 12 else ("Afternoon" if h < 17 else "Evening")
            name = ""
        return f"Good {part}, {name} {icon}" if name else f"Good {part} {icon}"

    def refresh(self):
        # Name/time can change while the app is open
        if hasattr(self, "greet"):
            self.greet.setText(self._greeting_text())
        self._on_period("month")

    def _date_range(self, period):
        today = date.today()
        if period == "today":
            return today.isoformat(), today.isoformat()
        elif period == "week":
            return (today - timedelta(days=7)).isoformat(), today.isoformat()
        elif period == "year":
            return f"{today.year}-01-01", today.isoformat()
        else:
            return f"{today.year}-{today.month:02d}-01", today.isoformat()

    def _load_data(self):
        # Update ALL KPI cards
        for p, card in self.kpi_cards.items():
            d_from, d_to = self._date_range(p)
            ptxns = self.tx.list_filters(date_from=d_from, date_to=d_to, limit=10000)
            p_debit = sum(t["amount"] for t in ptxns if t["tx_type"] == "DEBIT")
            # The selected period is an explicit user action, so replay its
            # value even when the amount itself has not changed.
            card.set_data(p_debit, len(ptxns), replay=(p == self._period))

        # Get selected period's transactions
        d_from, d_to = self._date_range(self._period)
        txns = self.tx.list_filters(date_from=d_from, date_to=d_to, limit=10000)

        self._render_charts(txns)
        self._render_top(txns)
        self._render_reminders()
        self._render_savings(txns)

        if self.chart_view.view:
            QTimer.singleShot(300, self._force_resize)

    def _render_charts(self, txns):
        if not self.chart_view.view:
            return

        cats = {}
        for t in txns:
            if t["tx_type"] == "DEBIT":
                cn = t.get("cat_name") or "Other"
                cats[cn] = cats.get(cn, 0) + t["amount"]

        # Spending trend — for "today", show last 7 days with today highlighted
        if self._period == "today":
            today_d = date.today()
            week_from = (today_d - timedelta(days=6)).isoformat()
            week_txns = self.tx.list_filters(date_from=week_from, date_to=today_d.isoformat(), limit=10000)
            trend_debit = {}
            for t in week_txns:
                if t["tx_type"] == "DEBIT":
                    trend_debit[t["tx_date"]] = trend_debit.get(t["tx_date"], 0) + t["amount"]
            all_dates = [(today_d - timedelta(days=j)).isoformat() for j in range(6, -1, -1)]
            today_idx = 6
        else:
            trend_debit = {}
            for t in txns:
                if t["tx_type"] == "DEBIT":
                    d = t["tx_date"]
                    key = d[:7] if self._period == "year" else d
                    trend_debit[key] = trend_debit.get(key, 0) + t["amount"]
            all_dates = sorted(trend_debit.keys())
            today_idx = -1

        # Full Split ledger payments are N/A; add only the self contact's
        # allocated share to behavioural spending analytics.
        try:
            from services.split_analytics import personal_share_rows
            dates=[t['tx_date'] for t in txns if t.get('tx_date')]
            split_rows=personal_share_rows(self.db, min(dates) if dates else None, max(dates) if dates else None)
        except Exception:
            split_rows=[]
        need_total, want_total, none_total = split_need_want(txns + split_rows)

        acct_cr = {}
        acct_db = {}
        for t in txns:
            an = t.get("account_name") or t["account_id"]
            if t["tx_type"] == "CREDIT" and t.get("transaction_kind", "REGULAR") != "TRANSFER":
                acct_cr[an] = acct_cr.get(an, 0) + t["amount"]
            elif t["tx_type"] == "DEBIT":
                acct_db[an] = acct_db.get(an, 0) + t["amount"]
        all_accts = sorted(set(list(acct_cr.keys()) + list(acct_db.keys())))

        html = apply_chart_theme(HOME_CHART_TEMPLATE)
        html = html.replace("__CAT_L__", json.dumps(list(cats.keys())))
        html = html.replace("__CAT_D__", json.dumps([round(v, 2) for v in cats.values()]))
        # Format trend labels based on period
        month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        if self._period == "year":
            trend_labels = [month_names[int(d[5:7])-1] for d in all_dates]
        else:
            trend_labels = [d[5:] for d in all_dates]
        html = html.replace("__TREND_L__", json.dumps(trend_labels))
        html = html.replace("__TREND_D__", json.dumps([round(trend_debit.get(d, 0), 2) for d in all_dates]))
        html = html.replace("__TODAY_IDX__", str(today_idx))
        # Untagged spend is its own segment — folding it into Want was the
        # old bug that made ~all spending look like discretionary "Want".
        html = html.replace("__NEED__", str(round(need_total, 2)))
        html = html.replace("__WANT__", str(round(want_total, 2)))
        html = html.replace("__NONE__", str(round(none_total, 2)))
        html = html.replace("__ACCT_L__", json.dumps(all_accts))
        html = html.replace("__ACCT_CR__", json.dumps([round(acct_cr.get(a, 0), 2) for a in all_accts]))
        html = html.replace("__ACCT_DB__", json.dumps([round(acct_db.get(a, 0), 2) for a in all_accts]))

        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        self.chart_view.view.load(QUrl.fromLocalFile(tmp.name))

    def _render_top(self, txns):
        while self.top_lay.count():
            item=self.top_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        debits=sorted([t for t in txns if t['tx_type']=='DEBIT'],key=lambda t:t['amount'],reverse=True)[:6]
        if debits:
            for tx in debits: self.top_lay.addWidget(_tx_card(tx))
        else:
            empty=QLabel('No spending in this period.'); empty.setStyleSheet(f"color:{C['text3']};font-size:12px;"); self.top_lay.addWidget(empty)
        self.top_lay.addStretch()

    def _render_reminders(self):
        reminders=[]; today=date.today(); today_s=today.isoformat()
        def add(key, priority, text, color):
            # Indexing guarantees one aggregate reminder per financial topic.
            existing=reminders_by_key.get(key)
            if existing is None or priority < existing[0]: reminders_by_key[key]=(priority,text,color)
        reminders_by_key={}
        # ── Split totals ──
        split=self.repos.get('split')
        if split:
            try:
                sid=split.get_self_contact(); owed=owe=0
                for group in split.list_groups():
                    bal=split.get_group_balances(group['group_id']).get(sid,0)
                    owed+=max(bal,0); owe+=max(-bal,0)
                if owed>0.01: add('split-owed',3,f"🤝 Split · Owed to you: {fmt_money(owed)}",C['green'])
                if owe>0.01: add('split-owe',3,f"🤝 Split · You owe: {fmt_money(owe)}",C['amber'])
            except Exception: pass
        # ── Credit card expiry, cycle overdue/due, statement soon ──
        cards=self.repos.get('cards')
        if cards:
            try:
                active=cards.list_active()
                for card in active:
                    months=(card.get('expiry_year',9999)-today.year)*12+card.get('expiry_month',12)-today.month
                    if 0<=months<=2:
                        label=card.get('card_name','Credit Card')
                        add('cc-expiry-'+str(card.get('card_id')),2,f"💳 Credit Card · {label} expires {date(card['expiry_year'],card['expiry_month'],1).strftime('%b %Y')}",C['red'] if months==0 else C['amber'])
                rows=self.db.execute("SELECT due_date,remaining,account_id FROM card_cycles WHERE remaining>0").fetchall()
                overdue=[r for r in rows if (r['due_date'] or '') < today_s]
                due=[r for r in rows if (r['due_date'] or '') >= today_s]
                if overdue: add('cc-overdue',0,f"💳 Credit Cards · Overdue: {fmt_money(sum(r['remaining'] or 0 for r in overdue))} ({len({r['account_id'] for r in overdue})} cards)",C['red'])
                if due: add('cc-due',2,f"💳 Credit Cards · Due: {fmt_money(sum(r['remaining'] or 0 for r in due))} ({len({r['account_id'] for r in due})} cards)",C['amber'])
                soon=0
                for card in active:
                    import re as _re
                    m=_re.search(r'\d+',card.get('statement_date') or '')
                    if m:
                        day=min(int(m.group()),28); stmt=date(today.year,today.month,day)
                        if 0 <= (stmt-today).days <= 7: soon+=1
                if soon: add('cc-statement',4,f"💳 Credit Cards · Statements generating soon ({soon} cards)",C['accent'])
            except Exception: pass
        # ── Debit card expiry ──
        dc=self.repos.get('debit_cards')
        if dc:
            try:
                for card in dc.list_active():
                    months=(card.get('expiry_year',9999)-today.year)*12+card.get('expiry_month',12)-today.month
                    if 0<=months<=2: add('dc-expiry-'+str(card.get('card_id')),2,f"🏧 Debit Card · {card.get('card_name','Card')} expires {date(card['expiry_year'],card['expiry_month'],1).strftime('%b %Y')}",C['amber'])
            except Exception: pass
        # ── Budget warnings by period ──
        try:
            from services.budget_service import BudgetService
            engine=BudgetService(self.repos['budgets'],self.tx)
            for ptype in ('MONTHLY','YEARLY','SPECIAL'):
                flagged=[b for b in engine.check_budgets(today.year,today.month,ptype) if b['pct']>=b['alert_threshold_pct']]
                over=sum(max(-b['remaining'],0) for b in flagged)
                warn=sum(max(b['spent'],0) for b in flagged if b['remaining']>=0)
                title={'MONTHLY':'Monthly','YEARLY':'Yearly','SPECIAL':'Special'}[ptype]
                if over>0: add('budget-over-'+ptype,0,f"📊 {title} Budget · Over budget by {fmt_money(over)}",C['red'])
                if warn>0: add('budget-warn-'+ptype,4,f"📊 {title} Budget · Warning: {fmt_money(warn)} used",C['amber'])
        except Exception: pass
        # ── Wealth aggregate reminders ──
        try:
            lent=self.repos['loans'].list_active(); overdue=[x for x in lent if x.get('status')=='OVERDUE']
            pending=sum(max((x.get('loan_amount') or 0)-self.repos['loans'].total_repaid(x['loan_id']),0) for x in lent)
            od_amt=sum(max((x.get('loan_amount') or 0)-self.repos['loans'].total_repaid(x['loan_id']),0) for x in overdue)
            if overdue: add('lent-overdue',0,f"💰 Money Lent · Overdue: {fmt_money(od_amt)} ({len(overdue)} loans)",C['red'])
            if lent: add('lent-pending',4,f"💰 Money Lent · Pending: {fmt_money(pending)} ({len(lent)} loans)",C['amber'])
            borrowed=self.repos['borrowed'].list_active(); bod=[x for x in borrowed if x.get('status')=='OVERDUE']
            if bod: add('borrowed-overdue',1,f"🏦 Money Borrowed · Overdue ({len(bod)} loans)",C['red'])
            fds=self.repos['fd'].list_all(); matured=[x for x in fds if x.get('status')=='MATURED']
            if matured: add('fd-matured',3,f"🏦 My Fixed Deposits · Matured ({len(matured)} deposits)",C['green'])
            deps=self.repos['deposits'].list_active(); matured_deps=[x for x in deps if (x.get('expected_return_date') or '')<=today_s]
            if matured_deps: add('dep-matured',2,f"🧾 Deposits Received · Matured: {fmt_money(sum(x.get('principal_amount') or 0 for x in matured_deps))} ({len(matured_deps)} deposits)",C['amber'])
            inv=cur=0
            for scheme in self.repos['mf'].list_schemes():
                h=self.repos['mf'].holdings(scheme['scheme_id']); txs=self.repos['mf'].list_txns(scheme['scheme_id']); nav=txs[-1]['nav'] if txs else 0
                inv+=(h.get('invested') or 0)-(h.get('redeemed') or 0); cur+=(h.get('units') or 0)*nav
            if inv>0: add('mf-return',4,f"📈 Mutual Funds · Overall return: {((cur-inv)/inv*100):+.1f}%",C['green'] if cur>=inv else C['red'])
        except Exception: pass
        self._reminders=sorted(reminders_by_key.values(),key=lambda x:x[0])
        self._reminder_index=0
        if not hasattr(self,'_reminder_timer'):
            self._reminder_timer=QTimer(self); self._reminder_timer.timeout.connect(self._show_reminder_slice)
        self._reminder_timer.start(3000)
        self._show_reminder_slice()

    def _show_reminder_slice(self):
        while self.rem_lay.count():
            item=self.rem_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        reminders=getattr(self,'_reminders',[])
        if not reminders:
            lbl=QLabel('No current reminders.'); lbl.setAlignment(Qt.AlignCenter); lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;"); self.rem_lay.addWidget(lbl); return
        visible=3
        start=self._reminder_index % len(reminders)
        chosen=[reminders[(start+i)%len(reminders)] for i in range(min(visible,len(reminders)))]
        for _,text,color in chosen:
            row=QLabel(text); row.setWordWrap(True); row.setStyleSheet(f"color:{color};background:{C['surface2']};border-left:3px solid {color};border-radius:7px;padding:6px;font-size:11px;font-weight:700;"); self.rem_lay.addWidget(row)
        self.rem_lay.addStretch()
        self._reminder_index=(start+visible)%len(reminders)

    def _render_savings(self, txns):
        # Fully clear — delete widgets AND layouts
        self._clear_layout(self.savings_inner)

        income = sum(t["amount"] for t in txns if t["tx_type"] == "CREDIT" and t.get("transaction_kind", "REGULAR") != "TRANSFER")
        expense = sum(t["amount"] for t in txns if t["tx_type"] == "DEBIT" and t.get("transaction_kind", "REGULAR") != "TRANSFER")
        savings = income - expense
        if income > 0:
            rate = (savings / income) * 100
        elif expense > 0:
            rate = -100
        else:
            rate = 0

        rate_color = C['green'] if rate >= 0 else C['red']

        # Title + rate
        title = QLabel("Savings Rate")
        title.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};")
        self.savings_inner.addWidget(title)

        rate_lbl = QLabel(f"{rate:.0f}%")
        rate_lbl.setStyleSheet(f"color:{rate_color};font-size:28px;font-weight:900;")
        self.savings_inner.addWidget(rate_lbl)

        # Bar — uses stretch factors for automatic sizing
        bar_bg = QFrame()
        bar_bg.setFixedHeight(8)
        bar_bg.setStyleSheet(f"background:{C['border2']};border-radius:4px;")
        bar_lay = QHBoxLayout(bar_bg)
        bar_lay.setContentsMargins(0, 0, 0, 0)
        bar_lay.setSpacing(0)
        bar_fill = QFrame()
        bar_fill.setStyleSheet(f"background:{rate_color};border-radius:4px;")
        stretch_fill = max(1, int(abs(rate)))
        stretch_rest = max(1, 100 - int(abs(rate)))
        bar_lay.addWidget(bar_fill, stretch_fill)
        bar_lay.addStretch(stretch_rest)
        self.savings_inner.addWidget(bar_bg)

        # Numbers row — created as widgets, not layout (so _clear_layout removes them)
        nums = QHBoxLayout()
        for text, color in [
            (f"↑ Income  {fmt_money(income)}", C['green']),
            (f"= Savings  {fmt_money(savings)}", rate_color),
            (f"↓ Expense  {fmt_money(expense)}", C['red']),
        ]:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color:{color};font-size:11px;font-weight:600;")
            nums.addWidget(lbl)
            nums.addStretch()
        # Wrap in a QWidget so _clear_layout can delete it
        nums_widget = QWidget()
        nums_widget.setStyleSheet("background:transparent;border:none;")
        nums_widget.setLayout(nums)
        self.savings_inner.addWidget(nums_widget)

    @staticmethod
    def _clear_layout(layout):
        """Delete all child widgets AND nested layouts."""
        while layout.count():
            itm = layout.takeAt(0)
            w = itm.widget()
            if w:
                w.deleteLater()
            child_lay = itm.layout()
            if child_lay:
                HomeTab._clear_layout(child_lay)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Sidebar expansion emits many intermediate resize events. Restart one
        # timer so Chart.js redraws only after the expansion has settled.
        self._chart_resize_timer.start(140)

    def _force_resize(self):
        if self.chart_view.view:
            # The widget has already received its final sidebar-adjusted width.
            # Trigger Chart.js directly; artificial width nudges cause flicker.
            self.chart_view.view.update()
            self.chart_view.resize_charts()
