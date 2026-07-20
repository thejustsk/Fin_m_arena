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
    "CURRENT": "Current Acc",
    "CREDIT_CARD": "Credit Card",
    "WALLET": "Wallet",
    "CASH": "Cash",
}

_ACCT_TYPE_ICON = {
    "CURRENT": "🏦",
    "CREDIT_CARD": "💳",
    "WALLET": "💼",
    "CASH": "💵",
}

_TYPE_GRADIENTS = {
    "CURRENT":     ("#3B82F6", "#BFDBFE"),
    "CREDIT_CARD": ("#EF4444", "#FECACA"),
    "WALLET":      ("#F59E0B", "#FDE68A"),
    "CASH":        ("#10B981", "#A7F3D0"),
}

_TYPE_ORDER = ["CURRENT", "CREDIT_CARD", "WALLET", "CASH"]


def _get_credit_limit(db, account_id, acct_limit):
    """Get credit limit — accounts table first, cards table fallback."""
    if acct_limit and acct_limit > 0:
        return acct_limit
    try:
        r = db.execute(
            "SELECT credit_limit FROM cards WHERE account_id=? AND is_active=1",
            (account_id,)).fetchone()
        if r and r["credit_limit"] and r["credit_limit"] > 0:
            return r["credit_limit"]
    except:
        pass
    return 0


def _util_color(util):
    """Utilization color — same thresholds as carousel."""
    if util < 0.3:
        return "#10B981"
    elif util < 0.7:
        return "#F59E0B"
    else:
        return "#EF4444"


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
        nw_col.addWidget(QLabel(
            "<span style='color:rgba(255,255,255,0.6);font-size:10px;"
            "font-weight:700;letter-spacing:1.5px;'>NET WORTH</span>"))
        self.nw_val = QLabel()
        self.nw_val.setStyleSheet("color:white;font-size:26px;font-weight:900;")
        nw_col.addWidget(self.nw_val)
        nw_lay.addLayout(nw_col)

        # Separator
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background:rgba(255,255,255,0.2);")
        nw_lay.addWidget(sep)

        # Breakdown — 4 fixed label pairs (created once)
        self._bd_vals = {}
        for acct_type in _TYPE_ORDER:
            icon = _ACCT_TYPE_ICON[acct_type]
            label = _ACCT_TYPE_LABEL[acct_type]
            col = QVBoxLayout()
            col.setSpacing(2)
            lbl = QLabel(
                f"<span style='color:rgba(255,255,255,0.6);font-size:9px;"
                f"font-weight:600;'>{icon} {label.upper()}</span>")
            col.addWidget(lbl)
            val = QLabel("₹0")
            val.setStyleSheet("color:white;font-size:15px;font-weight:700;")
            col.addWidget(val)
            nw_lay.addLayout(col)
            self._bd_vals[acct_type] = val

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

    # ─────────────────────────────────────────
    # REFRESH
    # ─────────────────────────────────────────
    def refresh(self):
        today = date.today()
        today_iso = today.isoformat()

        # Net worth
        nw = self.bal.net_worth()
        nw_color = "#10B981" if nw >= 0 else "#EF4444"
        self.nw_val.setText(fmt_money(nw))
        self.nw_val.setStyleSheet(f"color:{nw_color};font-size:26px;font-weight:900;")

        # Breakdown colors
        type_totals = self.bal.by_type()
        for acct_type, val_lbl in self._bd_vals.items():
            val = type_totals.get(acct_type, 0)
            val_lbl.setText(fmt_money(val))
            if acct_type == "CREDIT_CARD":
                vc = "#10B981" if val >= 0 else "#EF4444"
            elif acct_type == "WALLET":
                vc = "#F59E0B"
            elif acct_type == "CASH":
                vc = "#FFFFFF"
            else:
                vc = "#10B981" if val >= 0 else "#EF4444"
            val_lbl.setText(fmt_money(val))
            val_lbl.setStyleSheet(
                f"color:{vc};font-size:15px;font-weight:700;"
                f"background:transparent;border:none;")

        # Account cards
        self._clear_layout(self.acct_container)
        self._build_account_cards()

        # Recent transactions
        self._clear_layout(self.recent_lay)
        self._build_recent(today, today_iso)

    # ─────────────────────────────────────────
    # ACCOUNT CARDS
    # ─────────────────────────────────────────
    def _build_account_cards(self):
        balances = self.bal.get_all()
        if not balances:
            lbl = QLabel("No accounts yet.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            self.acct_container.addWidget(lbl)
            self.acct_container.addStretch()
            return

        # Group by type
        by_type = OrderedDict()
        for t in _TYPE_ORDER:
            by_type[t] = []
        for r in balances:
            t = r.get("account_type", "CURRENT")
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(r)

        for acct_type, accts in by_type.items():
            if not accts:
                continue

            icon = _ACCT_TYPE_ICON[acct_type]
            label = _ACCT_TYPE_LABEL[acct_type]
            g1, g2 = _TYPE_GRADIENTS.get(acct_type, ("#6B7280", "#F9FAFB"))
            type_total = sum(r.get("balance", 0) for r in accts)
            single = len(accts) == 1

            # ── Type header card ──
            hdr = QFrame()
            hdr.setStyleSheet(
                f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                f"stop:0 {g1},stop:1 {g2});border-radius:10px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            hdr_lay = QVBoxLayout(hdr)
            hdr_lay.setContentsMargins(14, 10, 14, 10)
            hdr_lay.setSpacing(4)

            # Icon + name/label + total
            top = QHBoxLayout()
            top.setSpacing(8)
            top.addWidget(self._icon_label(icon))
            if single:
                top.addWidget(self._bold_label(accts[0].get("display_name", label)))
            else:
                top.addWidget(self._bold_label(label))
            top.addStretch()
            top.addWidget(self._balance_label(type_total))
            hdr_lay.addLayout(top)

            # Util bar in header for single credit cards
            if single and acct_type == "CREDIT_CARD":
                limit = _get_credit_limit(
                    self.db, accts[0].get("account_id", ""),
                    accts[0].get("credit_limit", 0))
                util = min(abs(type_total) / limit, 1.0) if limit > 0 else 0
                if limit > 0:
                    hdr_lay.addWidget(self._util_bar(util))

            self.acct_container.addWidget(hdr)

            # ── Individual account cards (multi-account only) ──
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

                    # Name + balance
                    row = QHBoxLayout()
                    row.setSpacing(8)
                    name_lbl = QLabel(r.get("display_name", "—"))
                    name_lbl.setStyleSheet(
                        f"font-size:13px;font-weight:600;color:{C['text']};")
                    row.addWidget(name_lbl, 1)
                    row.addWidget(self._balance_label(bal))
                    card_lay.addLayout(row)

                    # Util bar for credit cards
                    if acct_type == "CREDIT_CARD":
                        limit = _get_credit_limit(
                            self.db, r.get("account_id", ""),
                            r.get("credit_limit", 0))
                        util = min(abs(bal) / limit, 1.0) if limit > 0 else 0
                        if limit > 0:
                            card_lay.addWidget(self._util_bar(util))

                    self.acct_container.addWidget(card)

        self.acct_container.addStretch()

    # ─────────────────────────────────────────
    # RECENT TRANSACTIONS
    # ─────────────────────────────────────────
    def _build_recent(self, today, today_iso):
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
            lbl = QLabel("No recent transactions.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.recent_lay.addWidget(lbl)
        self.recent_lay.addStretch()

    # ─────────────────────────────────────────
    # WIDGET BUILDERS
    # ─────────────────────────────────────────
    @staticmethod
    def _icon_label(icon):
        lbl = QLabel(icon)
        lbl.setStyleSheet("font-size:16px;")
        return lbl

    @staticmethod
    def _bold_label(text):
        lbl = QLabel(f"<b style='font-size:13px;color:#111827;'>{text}</b>")
        return lbl

    @staticmethod
    def _balance_label(amount):
        color = "#10B981" if amount >= 0 else "#EF4444"
        sign = "" if amount >= 0 else "- "
        lbl = QLabel(f"<b style='font-size:14px;color:{color};'>"
                     f"{sign}{fmt_money(abs(amount))}</b>")
        return lbl

    @staticmethod
    def _util_bar(util):
        """Utilization bar — gradient from color to gray."""
        color = _util_color(util)
        bar = QFrame()
        bar.setFixedHeight(6)
        pct = max(0.03, util)  # min 3% so something is always visible
        bar.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {color},stop:{pct} {color},"
            f"stop:{pct} #E5E7EB,stop:1 #E5E7EB);"
            f"border-radius:3px;")
        return bar

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            itm = layout.takeAt(0)
            w = itm.widget()
            if w:
                w.deleteLater()
