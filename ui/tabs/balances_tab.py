"""Balances tab — Account balances, net worth, recent transactions."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QScrollArea)
from PyQt5.QtCore import Qt
from datetime import date, timedelta
from collections import OrderedDict
from ui.theme import C
from ui.sidebar import fmt_money
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

# Gradient pairs for type header cards
_TYPE_GRADIENTS = {
    "CURRENT":     ("#3B82F6", "#BFDBFE"),  # blue
    "CREDIT_CARD": ("#EF4444", "#FECACA"),  # red
    "WALLET":      ("#F59E0B", "#FDE68A"),  # amber
    "CASH":        ("#10B981", "#A7F3D0"),  # green
}


class BalancesTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self.bal = services["balance"]
        self.tx = repos["transactions"]
        self.acct = repos["accounts"]
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 24, 40, 24)
        root.setSpacing(16)

        # ── Title ──
        h = QLabel("💰  Balances")
        h.setStyleSheet(f"font-size:24px;font-weight:800;color:{C['text']};")
        root.addWidget(h)

        # ── Net Worth Hero Card ──
        self.nw_card = QFrame()
        self.nw_card.setStyleSheet(
            f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 #4338CA,stop:1 #6366F1);border-radius:14px;}}"
            f"QLabel{{background:transparent;border:none;}}")
        nw_lay = QHBoxLayout(self.nw_card)
        nw_lay.setContentsMargins(24, 18, 24, 18)
        nw_lay.setSpacing(32)

        # Net worth value
        nw_col = QVBoxLayout()
        nw_col.setSpacing(2)
        nw_col.addWidget(QLabel("<span style='color:rgba(255,255,255,0.6);font-size:10px;font-weight:700;letter-spacing:1.5px;'>NET WORTH</span>"))
        self.nw_val = QLabel()
        self.nw_val.setStyleSheet("color:white;font-size:26px;font-weight:900;")
        nw_col.addWidget(self.nw_val)
        nw_lay.addLayout(nw_col)

        # Separator
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background:rgba(255,255,255,0.2);")
        nw_lay.addWidget(sep)

        # Breakdown — 4 fixed label pairs (created once, updated via refs)
        self._bd_labels = {}
        for acct_type in ["CURRENT", "CREDIT_CARD", "WALLET", "CASH"]:
            icon = _ACCT_TYPE_ICON.get(acct_type, "💰")
            label = _ACCT_TYPE_LABEL.get(acct_type, acct_type)
            col = QVBoxLayout()
            col.setSpacing(2)
            lbl = QLabel(f"<span style='color:rgba(255,255,255,0.6);font-size:9px;font-weight:600;'>{icon} {label.upper()}</span>")
            col.addWidget(lbl)
            val = QLabel("₹0")
            val.setStyleSheet("color:white;font-size:15px;font-weight:700;")
            col.addWidget(val)
            nw_lay.addLayout(col)
            self._bd_labels[acct_type] = val

        root.addWidget(self.nw_card)

        # ── Two-column: Accounts + Recent Transactions ──
        cols = QHBoxLayout()
        cols.setSpacing(20)

        # LEFT: Account Balances
        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        acct_title = QLabel("Account Balances")
        acct_title.setStyleSheet(f"font-size:16px;font-weight:700;color:{C['text']};")
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
        recent_title = QLabel("Recent Transactions")
        recent_title.setStyleSheet(f"font-size:16px;font-weight:700;color:{C['text']};")
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

    def refresh(self):
        today = date.today()
        today_iso = today.isoformat()

        # ── Net Worth ──
        nw = self.bal.net_worth()
        nw_color = "#10B981" if nw >= 0 else "#EF4444"
        self.nw_val.setText(fmt_money(nw))
        self.nw_val.setStyleSheet(f"color:{nw_color};font-size:26px;font-weight:900;")

        # ── Breakdown by type — update existing labels ──
        type_totals = self.bal.by_type()
        for acct_type, val_lbl in self._bd_labels.items():
            val = type_totals.get(acct_type, 0)
            val_lbl.setText(fmt_money(val))
            # Credit cards: balance is liability, so negative = good (green), positive = red
            # Others: positive = good (green), negative = red
            if acct_type == "CREDIT_CARD":
                vc = "#10B981" if val <= 0 else "#EF4444"
            else:
                vc = "#10B981" if val >= 0 else "#EF4444"
            val_lbl.setStyleSheet(f"color:{vc};font-size:15px;font-weight:700;")

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
                type_total = sum(r.get("balance", 0) for r in accts)
                single = len(accts) == 1

                # Type header card
                g1, g2 = _TYPE_GRADIENTS.get(acct_type, ("#6B7280", "#F9FAFB"))
                hdr = QFrame()
                hdr.setStyleSheet(
                    f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                    f"stop:0 {g1},stop:1 {g2});border-radius:10px;}}"
                    f"QLabel{{background:transparent;border:none;}}")
                hdr_lay = QVBoxLayout(hdr)
                hdr_lay.setContentsMargins(14, 10, 14, 10)
                hdr_lay.setSpacing(4)
                # Icon + name + amount row
                top_row = QHBoxLayout()
                top_row.setSpacing(8)
                h_icon = QLabel(icon)
                h_icon.setStyleSheet("font-size:16px;")
                top_row.addWidget(h_icon)
                if single:
                    acct_name = accts[0].get("display_name", label)
                    h_text = QLabel(f"<b style='font-size:13px;color:#111827;'>{acct_name}</b>")
                else:
                    h_text = QLabel(f"<b style='font-size:13px;color:#111827;'>{label}</b>")
                top_row.addWidget(h_text)
                top_row.addStretch()
                tc = C['green'] if type_total >= 0 else C['red']
                sign = "" if type_total >= 0 else "- "
                h_total = QLabel(f"<b style='font-size:14px;color:{tc};'>{sign}{fmt_money(abs(type_total))}</b>")
                top_row.addWidget(h_total)
                hdr_lay.addLayout(top_row)
                # Utilization bar for single credit card accounts
                if single and acct_type == "CREDIT_CARD":
                    limit = accts[0].get("credit_limit", 0) or 0
                    util = min(abs(type_total) / limit, 1.0) if limit > 0 else 0
                    if util < 0.3:
                        util_color = "#10B981"
                    elif util < 0.7:
                        util_color = "#F59E0B"
                    else:
                        util_color = "#EF4444"
                    bar_bg = QFrame()
                    bar_bg.setFixedHeight(4)
                    bar_bg.setStyleSheet(f"background:rgba(0,0,0,0.1);border-radius:2px;")
                    bar_lay = QHBoxLayout(bar_bg)
                    bar_lay.setContentsMargins(0, 0, 0, 0)
                    bar_lay.setSpacing(0)
                    bar_fill = QFrame()
                    bar_fill.setStyleSheet(f"background:{util_color};border-radius:2px;")
                    fs = max(1, int(util * 100))
                    rs = max(1, 100 - fs)
                    bar_lay.addWidget(bar_fill, fs)
                    bar_lay.addStretch(rs)
                    hdr_lay.addWidget(bar_bg)
                self.acct_container.addWidget(hdr)

                # Individual account cards
                if not single:
                    for r in accts:
                        bal = r.get("balance", 0)
                        card = QFrame()
                        card.setStyleSheet(
                            f"QFrame{{background:{C['surface']};border:1px solid {C['border']};"
                            f"border-radius:8px;}}QLabel{{background:transparent;border:none;}}")
                        card_lay = QVBoxLayout(card)
                        card_lay.setContentsMargins(14, 8, 14, 8)
                        card_lay.setSpacing(4)
                        # Name + balance row
                        row = QHBoxLayout()
                        row.setSpacing(8)
                        name_lbl = QLabel(r.get("display_name", "—"))
                        name_lbl.setStyleSheet(f"font-size:13px;font-weight:600;color:{C['text']};")
                        row.addWidget(name_lbl, 1)
                        bal_color = C['green'] if bal >= 0 else C['red']
                        s = "" if bal >= 0 else "- "
                        bal_lbl = QLabel(f"{s}{fmt_money(abs(bal))}")
                        bal_lbl.setStyleSheet(f"font-size:13px;font-weight:700;color:{bal_color};")
                        row.addWidget(bal_lbl)
                        card_lay.addLayout(row)
                        # Utilization bar for credit cards (no text) — same as carousel
                        if acct_type == "CREDIT_CARD":
                            limit = r.get("credit_limit", 0) or 0
                            util = min(abs(bal) / limit, 1.0) if limit > 0 else 0
                            # Exact same color thresholds as CardItem._draw_front
                            if util < 0.3:
                                util_color = "#10B981"
                            elif util < 0.7:
                                util_color = "#F59E0B"
                            else:
                                util_color = "#EF4444"
                            bar_bg = QFrame()
                            bar_bg.setFixedHeight(4)
                            bar_bg.setStyleSheet(f"background:{C['border2']};border-radius:2px;")
                            bar_lay = QHBoxLayout(bar_bg)
                            bar_lay.setContentsMargins(0, 0, 0, 0)
                            bar_lay.setSpacing(0)
                            bar_fill = QFrame()
                            bar_fill.setStyleSheet(f"background:{util_color};border-radius:2px;")
                            fs = max(1, int(util * 100))
                            rs = max(1, 100 - fs)
                            bar_lay.addWidget(bar_fill, fs)
                            bar_lay.addStretch(rs)
                            card_lay.addWidget(bar_bg)
                        self.acct_container.addWidget(card)
        else:
            no_acct = QLabel("No accounts yet.")
            no_acct.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            self.acct_container.addWidget(no_acct)
        self.acct_container.addStretch()

        # ── Recent Transactions ──
        self._clear_layout(self.recent_lay)

        recent = self.tx.list_filters(
            date_from=(today - timedelta(days=7)).isoformat(),
            date_to=today_iso, limit=20)
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
