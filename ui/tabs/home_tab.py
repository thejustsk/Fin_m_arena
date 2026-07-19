"""Home tab — dashboard with real stats, account balances, recent transactions."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QGridLayout, QFrame, QScrollArea, QSizePolicy)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QCursor, QColor
from datetime import datetime, date, timedelta
from collections import OrderedDict
from ui.theme import C
from ui.sidebar import fmt_money
from ui.widgets.metric_card import MetricCard, add_shadow
from ui.tabs.database_tab import _tx_card, _day_header


_ACCT_TYPE_LABEL = {
    "CURRENT": "Debit",
    "CREDIT_CARD": "Credit Card",
    "WALLET": "Wallet",
    "CASH": "Cash",
}

_ACCT_TYPE_ICON = {
    "CURRENT": "🏦",
    "CREDIT_CARD": "💳",
    "WALLET": "👛",
    "CASH": "💵",
}

# All type headers use the same dark gradient
_TYPE_GRADIENTS = {
    "CURRENT":     ("#6B7280", "#F9FAFB"),
    "CREDIT_CARD": ("#6B7280", "#F9FAFB"),
    "WALLET":      ("#6B7280", "#F9FAFB"),
    "CASH":        ("#6B7280", "#F9FAFB"),
}


class HomeTab(QWidget):
    go = pyqtSignal(str)

    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self.bal = services["balance"]
        self.tx = repos["transactions"]
        self.acct = repos["accounts"]
        self.cards = repos.get("cards")
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

        # ── Net Worth ──
        self.nw_label = QLabel()
        self.nw_label.setStyleSheet(f"font-size:15px;color:{C['text3']};")
        root.addWidget(self.nw_label)

        # ── Metric Cards ──
        self.metrics_row = QHBoxLayout()
        self.metrics_row.setSpacing(14)
        self.m_today_spend = MetricCard("Today's Spend", "₹0", C['red'], "💸")
        self.m_today_txns = MetricCard("Today's Txns", "0", C['accent'], "📊")
        self.m_month_spend = MetricCard("This Month", "₹0", C['amber'], "📅")
        self.m_total_txns = MetricCard("This Month Txns", "0", C['text3'], "📋")
        for mc in [self.m_today_spend, self.m_today_txns, self.m_month_spend, self.m_total_txns]:
            add_shadow(mc)
            self.metrics_row.addWidget(mc)
        root.addLayout(self.metrics_row)

        # ── Two-column: Accounts + Recent Transactions ──
        cols = QHBoxLayout()
        cols.setSpacing(20)

        # LEFT: Account Balances
        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        acct_title = QLabel("💰  Account Balances")
        acct_title.setStyleSheet(f"font-size:15px;font-weight:700;color:{C['text']};")
        left_col.addWidget(acct_title)
        self.acct_scroll = QScrollArea()
        self.acct_scroll.setWidgetResizable(True)
        self.acct_scroll.setFrameShape(QFrame.NoFrame)
        self.acct_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        acct_inner = QWidget()
        acct_inner.setStyleSheet("background:transparent;")
        self.acct_container = QVBoxLayout(acct_inner)
        self.acct_container.setSpacing(6)
        self.acct_container.setContentsMargins(0, 0, 4, 0)
        self.acct_scroll.setWidget(acct_inner)
        left_col.addWidget(self.acct_scroll, 1)
        cols.addLayout(left_col, 1)

        # RIGHT: Recent Transactions
        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        recent_title = QLabel("🕐  Recent Transactions")
        recent_title.setStyleSheet(f"font-size:15px;font-weight:700;color:{C['text']};")
        right_col.addWidget(recent_title)
        recent_scroll = QScrollArea()
        recent_scroll.setWidgetResizable(True)
        recent_scroll.setFrameShape(QFrame.NoFrame)
        recent_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        recent_inner = QWidget()
        recent_inner.setStyleSheet("background:transparent;")
        self.recent_lay = QVBoxLayout(recent_inner)
        self.recent_lay.setSpacing(3)
        self.recent_lay.setContentsMargins(0, 0, 0, 0)
        recent_scroll.setWidget(recent_inner)
        right_col.addWidget(recent_scroll, 1)
        cols.addLayout(right_col, 2)

        root.addLayout(cols, 1)

        # ── Quick Access Tiles ──
        qa_title = QLabel("Quick Access")
        qa_title.setStyleSheet(f"font-size:15px;font-weight:700;color:{C['text']};")
        root.addWidget(qa_title)

        grid = QHBoxLayout()
        grid.setSpacing(10)
        tiles = [
            ("📝", "Transactions", "transaction_entry", C['accent']),
            ("🗄️", "Database", "database", "#8B5CF6"),
            ("💳", "Cards", "cards", C['red']),
            ("⚙️", "Settings", "settings", C['text3']),
            ("🔍", "Audit", "audit", C['amber']),
            ("📈", "Wealth", "wealth", C['green']),
            ("📋", "Notes", "notes", "#EC4899"),
            ("📧", "Gmail", "gmail", "#06B6D4"),
        ]
        for ico, lbl, key, col in tiles:
            t = QFrame()
            t.setObjectName("tile")
            t.setMinimumHeight(56)
            t.setCursor(QCursor(Qt.PointingHandCursor))
            t.setStyleSheet(
                f"QFrame#tile{{background:{C['surface']};border:1px solid {C['border']};"
                f"border-left:4px solid {col};border-radius:10px;}}"
                f"QFrame#tile:hover{{border-color:{col};background:{C['surface2']};}}")
            tl2 = QHBoxLayout(t)
            tl2.setContentsMargins(14, 6, 14, 6)
            tl2.setSpacing(8)
            il = QLabel(ico)
            il.setStyleSheet("font-size:20px;")
            il.setFixedWidth(28)
            tl2.addWidget(il)
            nl = QLabel(lbl)
            nl.setStyleSheet(f"font-size:12px;font-weight:600;color:{C['text']};")
            tl2.addWidget(nl, 1)
            add_shadow(t, blur=6, y_offset=1)
            t.mousePressEvent = lambda e, k=key: self.go.emit(k)
            grid.addWidget(t)
        root.addLayout(grid)

    def refresh(self):
        today = date.today()
        today_iso = today.isoformat()

        # ── Net Worth ──
        nw = self.bal.net_worth()
        self.nw_label.setText(f"Your net worth is <b style='font-size:16px;color:{C['text']};'>{fmt_money(nw)}</b>")

        # ── Today's stats ──
        today_txns = self.tx.list_filters(date_from=today_iso, date_to=today_iso, limit=5000)
        today_spend = sum(t["amount"] for t in today_txns if t["tx_type"] == "DEBIT")
        self.m_today_spend.set_value(fmt_money(today_spend))
        self.m_today_txns.set_value(str(len(today_txns)))

        # ── This month stats ──
        y, m = today.year, today.month
        month_txns = self.tx.get_monthly(y, m)
        month_spend = sum(t["amount"] for t in month_txns if t["tx_type"] == "DEBIT")
        self.m_month_spend.set_value(fmt_money(month_spend))
        self.m_total_txns.set_value(str(len(month_txns)))

        # ── Account Balances ──
        self._clear_layout(self.acct_container)

        balances = self.bal.get_all()
        if balances:
            by_type = OrderedDict()
            for t in ["CURRENT", "CREDIT_CARD", "WALLET", "CASH"]:
                by_type[t] = []
            for r in balances:
                t = r.get("account_type", "CURRENT")
                if t not in by_type:
                    by_type[t] = []
                by_type[t].append(r)

            for acct_type, accts in by_type.items():
                if not accts:
                    continue
                icon = _ACCT_TYPE_ICON.get(acct_type, "💰")
                label = _ACCT_TYPE_LABEL.get(acct_type, acct_type)
                g1, g2 = _TYPE_GRADIENTS.get(acct_type, ("#3a3a3a", "#0f0f0f"))
                type_total = sum(r.get("balance", 0) for r in accts)
                single = len(accts) == 1

                # ── Gradient header card ──
                hdr = QFrame()
                hdr.setStyleSheet(
                    f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                    f"stop:0 {g1},stop:1 {g2});border-radius:10px;}}"
                    f"QLabel{{background:transparent;border:none;}}")
                hdr_lay = QHBoxLayout(hdr)
                hdr_lay.setContentsMargins(14, 10, 14, 10)
                hdr_lay.setSpacing(8)
                # Icon
                h_icon = QLabel(icon)
                h_icon.setStyleSheet("font-size:16px;")
                hdr_lay.addWidget(h_icon)
                # Label
                if single:
                    acct_name = accts[0].get("display_name", label)
                    h_text = QLabel(f"<b style='font-size:13px;color:#111827;'>{acct_name}</b>")
                else:
                    h_text = QLabel(f"<b style='font-size:13px;color:#111827;'>{label}</b>")
                hdr_lay.addWidget(h_text)
                hdr_lay.addStretch()
                # Balance (amount color stays green/red)
                tc = C['green'] if type_total >= 0 else C['red']
                sign = "" if type_total >= 0 else "- "
                h_total = QLabel(f"<b style='font-size:14px;color:{tc};'>{sign}{fmt_money(abs(type_total))}</b>")
                hdr_lay.addWidget(h_total)
                self.acct_container.addWidget(hdr)

                # ── Individual account cards (skip if single account) ──
                if not single:
                    for r in accts:
                        bal = r.get("balance", 0)
                        card = QFrame()
                        card.setStyleSheet(
                            f"QFrame{{background:{C['surface']};border:1px solid {C['border']};"
                            f"border-radius:8px;}}QLabel{{background:transparent;border:none;}}")
                        card_lay = QHBoxLayout(card)
                        card_lay.setContentsMargins(14, 8, 14, 8)
                        card_lay.setSpacing(8)
                        name_lbl = QLabel(r.get("display_name", "—"))
                        name_lbl.setStyleSheet(f"font-size:13px;font-weight:600;color:{C['text']};")
                        card_lay.addWidget(name_lbl, 1)
                        bal_color = C['green'] if bal >= 0 else C['red']
                        s = "" if bal >= 0 else "- "
                        bal_lbl = QLabel(f"{s}{fmt_money(abs(bal))}")
                        bal_lbl.setStyleSheet(f"font-size:13px;font-weight:700;color:{bal_color};")
                        card_lay.addWidget(bal_lbl)
                        self.acct_container.addWidget(card)
        else:
            no_acct = QLabel("No accounts yet.")
            no_acct.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            self.acct_container.addWidget(no_acct)
        self.acct_container.addStretch()

        # ── Recent Transactions (last 7 days, max 8) ──
        self._clear_layout(self.recent_lay)

        recent = self.tx.list_filters(
            date_from=(today - timedelta(days=7)).isoformat(),
            date_to=today_iso, limit=8)
        if recent:
            by_date = OrderedDict()
            for tx in sorted(recent, key=lambda t: t["tx_date"], reverse=True):
                d = tx["tx_date"]
                if d not in by_date:
                    by_date[d] = []
                by_date[d].append(tx)
            for d_str, day_txns in by_date.items():
                try:
                    self.recent_lay.addWidget(_day_header(
                        date.fromisoformat(d_str).strftime("%A, %d %b")))
                except:
                    self.recent_lay.addWidget(_day_header(d_str))
                for tx in day_txns:
                    self.recent_lay.addWidget(_tx_card(tx))
        else:
            no_tx = QLabel("No recent transactions.")
            no_tx.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            no_tx.setAlignment(Qt.AlignCenter)
            self.recent_lay.addWidget(no_tx)
        self.recent_lay.addStretch()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            itm = layout.takeAt(0)
            w = itm.widget()
            if w:
                w.deleteLater()
