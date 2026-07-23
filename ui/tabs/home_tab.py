"""Home tab — Visual dashboard with KPI period switchers and Chart.js charts."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QScrollArea, QSizePolicy)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer, QUrl
from PyQt5.QtGui import QCursor
from datetime import datetime, date, timedelta
from collections import OrderedDict
from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tx_card, _day_header, ChartView
import json


# ── Chart HTML template for Home (4 charts) ──
HOME_CHART_TEMPLATE = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI',system-ui,sans-serif; background:transparent; padding:12px; }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.card { background:#fff; border-radius:12px; padding:18px; box-shadow:0 1px 3px rgba(0,0,0,0.06); border:1px solid #E5E7EB; }
.card.full { grid-column:1 / -1; }
.title { font-size:12px; font-weight:700; color:#374151; margin-bottom:10px; display:flex; align-items:center; gap:8px; }
.dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
canvas { max-height:200px; }
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
    <canvas id="c4"></canvas>
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
        scales: { y: { grid: { color: '#F3F4F6' } }, x: { grid: { display: false } } }
    }
});

new Chart(document.getElementById('c3'), {
    type: 'bar',
    data: {
        labels: ['Spending'],
        datasets: [
            { label: 'Need', data: [__NEED__], backgroundColor: '#4F46E5', borderRadius: 6 },
            { label: 'Want', data: [__WANT__], backgroundColor: '#F59E0B', borderRadius: 6 }
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false, indexAxis: 'y', stacked: true,
        plugins: {
            legend: { position: 'top', labels: { usePointStyle: true, font: { size: 11, weight: '600' } } },
            tooltip: {
                callbacks: {
                    label: function(ctx) {
                        var total = __NEED__ + __WANT__;
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

// 4. Income vs Expense by Account — horizontal bar, auto-scales for 20+ accounts
var acctLabels = __ACCT_L__;
var acctCanvas = document.getElementById('c4');
acctCanvas.style.height = Math.max(200, acctLabels.length * 24) + 'px';

new Chart(acctCanvas, {
    type: 'bar',
    data: {
        labels: acctLabels,
        datasets: [
            { label: 'Income', data: __ACCT_CR__, backgroundColor: '#10B981', borderRadius: 4 },
            { label: 'Expense', data: __ACCT_DB__, backgroundColor: '#EF4444', borderRadius: 4 }
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false, indexAxis: 'y',
        plugins: { legend: { position: 'top', labels: { usePointStyle: true, font: { size: 11 } } } },
        scales: {
            x: { grid: { color: '#F3F4F6' }, ticks: { font: { size: 10 } } },
            y: { grid: { display: false }, ticks: { font: { size: 10 } } }
        }
    }
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

    def set_data(self, amount, count):
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
        self.bal = services["balance"]
        self.tx = repos["transactions"]
        self.acct = repos["accounts"]
        self.lu = repos["lookups"]
        self._period = "month"
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 24, 40, 24)
        root.setSpacing(16)

        # ── Top: Greeting + Date ──
        top_row = QHBoxLayout()
        h = datetime.now().hour
        icon = "☀️" if h < 12 else ("🌤️" if h < 17 else "🌙")
        greet = QLabel(f"Good {'Morning' if h < 12 else 'Afternoon' if h < 17 else 'Evening'} {icon}")
        greet.setStyleSheet(f"font-size:28px;font-weight:800;color:{C['text']};")
        top_row.addWidget(greet)
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

        top_tx_title = QLabel("Top Transactions")
        top_tx_title.setStyleSheet(f"font-size:15px;font-weight:700;color:{C['text']};")
        right_col.addWidget(top_tx_title)

        top_scroll = QScrollArea()
        top_scroll.setWidgetResizable(True)
        top_scroll.setFrameShape(QFrame.NoFrame)
        top_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        top_inner = QWidget()
        top_inner.setStyleSheet("background:transparent;")
        self.top_lay = QVBoxLayout(top_inner)
        self.top_lay.setSpacing(3)
        self.top_lay.setContentsMargins(0, 0, 0, 0)
        top_scroll.setWidget(top_inner)
        right_col.addWidget(top_scroll, 1)

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
            ("💳", "Cards", "cards", C['red']),
            ("💰", "Balances", "balances", C['green']),
            ("⚙️", "Settings", "settings", C['text3']),
            ("🔍", "Audit", "audit", C['amber']),
            ("📈", "Wealth", "wealth", "#10B981"),
            ("📋", "Notes", "notes", "#EC4899"),
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

    def refresh(self):
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
            card.set_data(fmt_money(p_debit), len(ptxns))

        # Get selected period's transactions
        d_from, d_to = self._date_range(self._period)
        txns = self.tx.list_filters(date_from=d_from, date_to=d_to, limit=10000)

        self._render_charts(txns)
        self._render_top(txns)
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

        need_total = sum(t["amount"] for t in txns if t.get("neednwant") == 1 and t["tx_type"] == "DEBIT")
        want_total = sum(t["amount"] for t in txns if t.get("neednwant") == 0 and t["tx_type"] == "DEBIT")
        none_total = sum(t["amount"] for t in txns if t.get("neednwant") not in (0, 1) and t["tx_type"] == "DEBIT")

        acct_cr = {}
        acct_db = {}
        for t in txns:
            an = t.get("account_name") or t["account_id"]
            if t["tx_type"] == "CREDIT" and t.get("transaction_kind", "REGULAR") != "TRANSFER":
                acct_cr[an] = acct_cr.get(an, 0) + t["amount"]
            elif t["tx_type"] == "DEBIT":
                acct_db[an] = acct_db.get(an, 0) + t["amount"]
        all_accts = sorted(set(list(acct_cr.keys()) + list(acct_db.keys())))

        html = HOME_CHART_TEMPLATE
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
        html = html.replace("__NEED__", str(round(need_total, 2)))
        html = html.replace("__WANT__", str(round(want_total + none_total, 2)))
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
            itm = self.top_lay.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()

        debits = sorted([t for t in txns if t["tx_type"] == "DEBIT"],
                        key=lambda t: t["amount"], reverse=True)[:7]
        if debits:
            for tx in debits:
                self.top_lay.addWidget(_tx_card(tx))
        else:
            lbl = QLabel("No transactions.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.top_lay.addWidget(lbl)
        self.top_lay.addStretch()

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

    def _force_resize(self):
        if self.chart_view.view:
            self.chart_view.view.update()
            s = self.chart_view.view.size()
            self.chart_view.view.resize(s.width(), s.height() - 1)
            QTimer.singleShot(50, lambda: self.chart_view.view.resize(s.width(), s.height()))
