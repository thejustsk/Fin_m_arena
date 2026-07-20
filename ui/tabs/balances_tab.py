"""Balances tab — Account balances, net worth, recent transactions, account drill-down."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QScrollArea, QStackedWidget, QPushButton)
from PyQt5.QtCore import Qt
from datetime import date, timedelta
from collections import OrderedDict
from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tx_card, _day_header, _month_header
from ui.tabs.cards_tab import _build_cycles, _fifo_allocate, _parse_stmt_day, _cycle_name, _stmt_display


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
        self.cards = repos.get("cards")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 24, 40, 24)
        root.setSpacing(16)

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

        nw_col = QVBoxLayout()
        nw_col.setSpacing(2)
        nw_col.addWidget(QLabel(
            "<span style='color:rgba(255,255,255,0.6);font-size:10px;"
            "font-weight:700;letter-spacing:1.5px;'>NET WORTH</span>"))
        self.nw_val = QLabel()
        self.nw_val.setStyleSheet("color:white;font-size:26px;font-weight:900;")
        nw_col.addWidget(self.nw_val)
        nw_lay.addLayout(nw_col)

        sep = QFrame(); sep.setFixedWidth(1)
        sep.setStyleSheet("background:rgba(255,255,255,0.2);")
        nw_lay.addWidget(sep)

        self._bd_vals = {}
        for acct_type in _TYPE_ORDER:
            icon = _ACCT_TYPE_ICON[acct_type]
            label = _ACCT_TYPE_LABEL[acct_type]
            col = QVBoxLayout(); col.setSpacing(2)
            col.addWidget(QLabel(
                f"<span style='color:rgba(255,255,255,0.6);font-size:9px;"
                f"font-weight:600;'>{icon} {label.upper()}</span>"))
            val = QLabel("₹0")
            val.setStyleSheet("color:white;font-size:15px;font-weight:700;")
            col.addWidget(val)
            nw_lay.addLayout(col)
            self._bd_vals[acct_type] = val

        root.addWidget(self.nw_card)

        # ── Two-column: Accounts + Transactions ──
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
        acct_inner = QWidget(); acct_inner.setStyleSheet("background:transparent;")
        self.acct_container = QVBoxLayout(acct_inner)
        self.acct_container.setSpacing(6)
        self.acct_container.setContentsMargins(0, 0, 4, 0)
        self.acct_scroll.setWidget(acct_inner)
        left_col.addWidget(self.acct_scroll, 1)
        cols.addLayout(left_col, 1)

        # RIGHT: Stacked — Recent Transactions / Account Transactions
        right_col = QVBoxLayout()
        right_col.setSpacing(4)

        # Right header row (title + back button)
        self._right_hdr = QHBoxLayout()
        self._right_title = QLabel("Recent Transactions")
        self._right_title.setStyleSheet(f"font-size:16px;font-weight:700;color:{C['text']};")
        self._right_hdr.addWidget(self._right_title)
        self._right_hdr.addStretch()
        self._back_btn = QPushButton("← Back")
        self._back_btn.setStyleSheet(
            f"QPushButton{{background:{C['surface']};color:{C['accent']};border:1px solid {C['border']};"
            f"border-radius:6px;padding:4px 12px;font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{background:{C['accent']};color:white;}}")
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.clicked.connect(self._show_recent)
        self._back_btn.hide()
        self._right_hdr.addWidget(self._back_btn)
        right_col.addLayout(self._right_hdr)

        self._right_stack = QStackedWidget()

        # Page 0: Recent Transactions
        recent_scroll = QScrollArea()
        recent_scroll.setWidgetResizable(True)
        recent_scroll.setFrameShape(QFrame.NoFrame)
        recent_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        recent_inner = QWidget(); recent_inner.setStyleSheet("background:transparent;")
        self.recent_lay = QVBoxLayout(recent_inner)
        self.recent_lay.setSpacing(3)
        self.recent_lay.setContentsMargins(0, 0, 0, 0)
        recent_scroll.setWidget(recent_inner)
        self._right_stack.addWidget(recent_scroll)

        # Page 1: Account Transactions (drill-down)
        acct_tx_scroll = QScrollArea()
        acct_tx_scroll.setWidgetResizable(True)
        acct_tx_scroll.setFrameShape(QFrame.NoFrame)
        acct_tx_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        acct_tx_inner = QWidget(); acct_tx_inner.setStyleSheet("background:transparent;")
        self.acct_tx_lay = QVBoxLayout(acct_tx_inner)
        self.acct_tx_lay.setSpacing(4)
        self.acct_tx_lay.setContentsMargins(0, 0, 0, 0)
        acct_tx_scroll.setWidget(acct_tx_inner)
        self._right_stack.addWidget(acct_tx_scroll)

        right_col.addWidget(self._right_stack, 1)
        cols.addLayout(right_col, 2)
        root.addLayout(cols, 1)

    # ─────────────────────────────────────────
    # REFRESH
    # ─────────────────────────────────────────
    def refresh(self):
        today = date.today()
        today_iso = today.isoformat()

        nw = self.bal.net_worth()
        nw_color = "#10B981" if nw >= 0 else "#EF4444"
        self.nw_val.setText(fmt_money(nw))
        self.nw_val.setStyleSheet(f"color:{nw_color};font-size:26px;font-weight:900;")

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

        self._clear_layout(self.acct_container)
        self._build_account_cards()

        self._clear_layout(self.recent_lay)
        self._build_recent(today, today_iso)

        self._show_recent()

    # ─────────────────────────────────────────
    # RIGHT PANEL: Recent / Account drill-down
    # ─────────────────────────────────────────
    def _show_recent(self):
        self._right_stack.setCurrentIndex(0)
        self._right_title.setText("Recent Transactions")
        self._back_btn.hide()

    def _show_account_txns(self, acct_data, acct_type):
        self._right_stack.setCurrentIndex(1)
        name = acct_data.get("display_name", "Account")
        icon = _ACCT_TYPE_ICON.get(acct_type, "💰")
        self._right_title.setText(f"{icon}  {name}")
        self._back_btn.show()

        self._clear_layout(self.acct_tx_lay)

        if acct_type == "CREDIT_CARD":
            # Fetch card data for statement_date, grace_days, colors
            card_data = dict(acct_data)
            if self.cards:
                try:
                    card = self.cards.get_by_account(acct_data["account_id"])
                    if card:
                        card_data.update(card)
                except:
                    pass
            self._build_cc_detail(card_data)
        else:
            self._build_acct_txns(acct_data)

    # ─────────────────────────────────────────
    # NON-CC: Month/Day grouped transactions
    # ─────────────────────────────────────────
    def _build_acct_txns(self, acct_data):
        aid = acct_data["account_id"]
        txns = self.tx.list_filters(account_id=aid, limit=5000)

        if not txns:
            lbl = QLabel("No transactions for this account.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.acct_tx_lay.addWidget(lbl)
            self.acct_tx_lay.addStretch()
            return

        # Running balances
        bal_map = {}
        running = acct_data.get("opening_balance", 0)
        for tx in sorted(txns, key=lambda t: (t["tx_date"], t.get("created_at", ""))):
            if tx["tx_type"] == "CREDIT":
                running += tx["amount"]
            else:
                running -= tx["amount"]
            bal_map[tx["id"]] = running

        # Group by month → day
        months = OrderedDict()
        for tx in sorted(txns, key=lambda t: t["tx_date"], reverse=True):
            mk = tx["tx_date"][:7]
            dk = tx["tx_date"]
            if mk not in months:
                months[mk] = OrderedDict()
            if dk not in months[mk]:
                months[mk][dk] = []
            months[mk][dk].append(tx)

        for mk, days in months.items():
            try:
                y, m = map(int, mk.split("-"))
                self.acct_tx_lay.addWidget(_month_header(date(y, m, 1).strftime("%B %Y")))
            except:
                self.acct_tx_lay.addWidget(_month_header(mk))
            for dk, day_txns in days.items():
                try:
                    self.acct_tx_lay.addWidget(_day_header(
                        date.fromisoformat(dk).strftime("%A, %d %b")))
                except:
                    self.acct_tx_lay.addWidget(_day_header(dk))
                for tx in day_txns:
                    self.acct_tx_lay.addWidget(_tx_card(tx, bal_map.get(tx["id"])))

        self.acct_tx_lay.addStretch()

    # ─────────────────────────────────────────
    # CC: Cycle headers + transactions (like Cards tab, no settlement/edit)
    # ─────────────────────────────────────────
    def _build_cc_detail(self, acct_data):
        aid = acct_data["account_id"]
        limit = acct_data.get("credit_limit", 0) or acct_data.get("acct_limit", 0)
        balance = abs(self.bal.get_balance(aid))
        util = (balance / limit * 100) if limit > 0 else 0
        c1 = acct_data.get("card_color_1", "#3a3a3a")
        c2 = acct_data.get("card_color_2", "#0f0f0f")
        stmt_str = acct_data.get("statement_date", "")
        grace = acct_data.get("grace_days", 20)
        stmt_date = acct_data.get("statement_date", "—") or "—"
        util_color = "#EF4444" if util > 70 else ("#F59E0B" if util > 30 else "#10B981")

        # Compute FIFO for Amount Due
        all_txns_for_due = self.tx.list_filters(account_id=aid, limit=5000)
        stmt_day = _parse_stmt_day(stmt_str)
        _cycles_for_due = _build_cycles(stmt_day, 12) if stmt_day else []
        _cycle_data_for_due = _fifo_allocate(_cycles_for_due, all_txns_for_due) if _cycles_for_due else []
        amount_due = 0
        today_str = date.today().isoformat()
        for cd in _cycle_data_for_due:
            if cd["end"].isoformat() < today_str:
                amount_due += cd["remaining"]

        # Due date from card
        due_str = acct_data.get("due_date", "") or ""
        if not due_str and amount_due > 0:
            try:
                from ui.tabs.cards_tab import _calc_due
                due_str = _calc_due(stmt_str, grace)
            except: pass
        due_display = "—"
        if due_str and "-" in due_str:
            try: due_display = date.fromisoformat(due_str).strftime("%d %b %Y")
            except: due_display = due_str

        # ── Full header card (same as Cards tab) ──
        hdr = QFrame(); hdr.setFixedHeight(110)
        hdr.setStyleSheet(
            f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {c1},stop:1 {c2});border-radius:12px;}}"
            f"QLabel{{background:transparent;border:none;}}")
        hdr_lay = QVBoxLayout(hdr)
        hdr_lay.setContentsMargins(20, 12, 20, 12); hdr_lay.setSpacing(6)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel(
            f"<b style='font-size:16px;color:white;'>{acct_data.get('card_name', acct_data.get('display_name', 'Card'))}</b>"))
        r1.addStretch()
        net_label = acct_data.get("card_network", "")
        cls_label = acct_data.get("card_class", "")
        sub_text = f"{net_label} {cls_label}".strip()
        if sub_text:
            r1.addWidget(QLabel(
                f"<span style='color:rgba(255,255,255,0.7);font-size:12px;'>{sub_text}</span>"))
        hdr_lay.addLayout(r1)

        # 5 metric labels
        stmt_disp = _stmt_display(stmt_str) if stmt_str else "—"
        r2 = QHBoxLayout(); r2.setSpacing(24)
        for lbl, val, color in [
            ("Limit", fmt_money(limit), "rgba(255,255,255,0.7)"),
            ("Statement", f"Every {stmt_disp}", "rgba(255,255,255,0.9)"),
            ("Amount Due", fmt_money(amount_due), "#FCA5A5" if amount_due > 0 else "rgba(255,255,255,0.9)"),
            ("Due Date", due_display, "#FCA5A5" if amount_due > 0 else "rgba(255,255,255,0.9)"),
            ("Current Outstanding", fmt_money(balance), util_color),
        ]:
            c = QVBoxLayout(); c.setSpacing(0)
            c.addWidget(QLabel(
                f"<span style='color:rgba(255,255,255,0.5);font-size:9px;'>{lbl}</span>"))
            c.addWidget(QLabel(
                f"<b style='color:{color};font-size:13px;'>{val}</b>"))
            r2.addLayout(c)
        r2.addStretch()
        hdr_lay.addLayout(r2)
        self.acct_tx_lay.addWidget(hdr)

        # ── Cycle headers + transactions ──
        all_txns = self.tx.list_filters(account_id=aid, limit=5000)
        stmt_day = _parse_stmt_day(stmt_str)
        cycles = _build_cycles(stmt_day, 12) if stmt_day else []
        cycle_data = _fifo_allocate(cycles, all_txns) if cycles else []

        try:
            saved_cycles = self.cards.get_cycles(aid) if self.cards else []
        except:
            saved_cycles = []

        if not all_txns:
            lbl = QLabel("No transactions for this card.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.acct_tx_lay.addWidget(lbl)
        elif not cycle_data:
            # No cycles — flat list
            from collections import OrderedDict as OD
            by_date = OD()
            for tx in sorted(all_txns, key=lambda t: t["tx_date"], reverse=True):
                d = tx["tx_date"]
                if d not in by_date: by_date[d] = []
                by_date[d].append(tx)
            for d_str, day_txns in by_date.items():
                try:
                    self.acct_tx_lay.addWidget(_day_header(
                        date.fromisoformat(d_str).strftime("%A, %d %b")))
                except:
                    self.acct_tx_lay.addWidget(_day_header(d_str))
                for tx in day_txns:
                    self.acct_tx_lay.addWidget(_tx_card(tx))
        else:
            txn_by_cycle = {i: [] for i in range(len(cycle_data))}
            unassigned = []
            for tx in all_txns:
                tx_date = tx["tx_date"]
                assigned = False
                for i, cd in enumerate(cycle_data):
                    if cd["start"].isoformat() <= tx_date <= cd["end"].isoformat():
                        txn_by_cycle[i].append(tx); assigned = True; break
                if not assigned:
                    unassigned.append(tx)

            for i, cd in enumerate(cycle_data):
                cycle_txns = txn_by_cycle.get(i, [])
                if not cycle_txns:
                    continue

                # Cycle header
                rem_color = "#059669" if cd["remaining"] <= 0 else ("#D97706" if cd["remaining"] <= cd["debits"] * 0.5 else "#DC2626")
                ch = QFrame()
                ch.setMinimumHeight(36)
                ch.setStyleSheet(
                    f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                    f"stop:0 {c1}22,stop:1 {c2}22);border:none;border-radius:8px;padding:6px 8px;}}"
                    f"QLabel{{background:transparent;border:none;}}")
                cl = QHBoxLayout(ch); cl.setContentsMargins(10, 4, 10, 4); cl.setSpacing(8)
                cycle_name = _cycle_name(cd["start"])
                stmt_label = _stmt_display(stmt_str) if stmt_str else ""
                cl.addWidget(QLabel(f"<b style='color:{C['text']};'>📅 {cycle_name}  (stmt: {stmt_label})</b>"))
                cl.addStretch()
                cl.addWidget(QLabel(f"<span style='color:#DC2626;font-weight:700;'>Spent: {fmt_money(cd['debits'])}</span>"))
                if cd["paid"] > 0:
                    cl.addWidget(QLabel(f"<span style='color:#059669;font-weight:700;'>Paid: {fmt_money(cd['paid'])}</span>"))
                cl.addWidget(QLabel(f"<span style='color:{rem_color};font-weight:700;'>Remaining: {fmt_money(cd['remaining'])}</span>"))
                # Due date (read-only)
                saved_due = ""
                for sc in saved_cycles:
                    if sc.get("cycle_start_date", "") == cd["start"].isoformat():
                        saved_due = sc.get("due_date", "") or ""; break
                if not saved_due:
                    try: saved_due = (cd["end"] + timedelta(days=grace)).isoformat()
                    except: pass
                if saved_due:
                    try:
                        due_disp = date.fromisoformat(saved_due).strftime("%d %b %Y")
                    except:
                        due_disp = saved_due
                    cl.addWidget(QLabel(f"<span style='color:{C['text3']};font-size:11px;'>Due: {due_disp}</span>"))
                self.acct_tx_lay.addWidget(ch)

                # Transactions within cycle
                from collections import OrderedDict as OD
                by_date = OD()
                for tx in sorted(cycle_txns, key=lambda t: t["tx_date"], reverse=True):
                    d = tx["tx_date"]
                    if d not in by_date: by_date[d] = []
                    by_date[d].append(tx)
                for d_str, day_txns in by_date.items():
                    try:
                        self.acct_tx_lay.addWidget(_day_header(
                            date.fromisoformat(d_str).strftime("%A, %d %b")))
                    except:
                        self.acct_tx_lay.addWidget(_day_header(d_str))
                    for tx in day_txns:
                        self.acct_tx_lay.addWidget(_tx_card(tx))

            if unassigned:
                lbl = QLabel("<b>Earlier Transactions</b>")
                lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;font-weight:700;padding:8px 0 4px 0;background:transparent;border:none;")
                self.acct_tx_lay.addWidget(lbl)
                for tx in sorted(unassigned, key=lambda t: t["tx_date"], reverse=True):
                    self.acct_tx_lay.addWidget(_tx_card(tx))

        self.acct_tx_lay.addStretch()

    # ─────────────────────────────────────────
    # ACCOUNT CARDS (with click handlers)
    # ─────────────────────────────────────────
    def _build_account_cards(self):
        balances = self.bal.get_all()
        if not balances:
            lbl = QLabel("No accounts yet.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            self.acct_container.addWidget(lbl)
            self.acct_container.addStretch()
            return

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

            # ── Type header card (clickable for single accounts) ──
            hdr = QFrame()
            hdr.setStyleSheet(
                f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                f"stop:0 {g1},stop:1 {g2});border-radius:10px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            hdr_lay = QVBoxLayout(hdr)
            hdr_lay.setContentsMargins(14, 10, 14, 10)
            hdr_lay.setSpacing(4)

            top = QHBoxLayout(); top.setSpacing(8)
            top.addWidget(self._icon_label(icon))
            if single:
                top.addWidget(self._bold_label(accts[0].get("display_name", label)))
            else:
                top.addWidget(self._bold_label(label))
            top.addStretch()
            top.addWidget(self._balance_label(type_total))
            hdr_lay.addLayout(top)

            if single and acct_type == "CREDIT_CARD":
                limit = _get_credit_limit(
                    self.db, accts[0].get("account_id", ""),
                    accts[0].get("credit_limit", 0))
                util = min(abs(type_total) / limit, 1.0) if limit > 0 else 0
                if limit > 0:
                    hdr_lay.addWidget(self._util_bar(util))

            # Make single-account headers clickable
            if single:
                hdr.setCursor(Qt.PointingHandCursor)
                _acct = dict(accts[0])
                _type = acct_type
                hdr.mousePressEvent = lambda e, a=_acct, t=_type: self._show_account_txns(a, t)

            self.acct_container.addWidget(hdr)

            # ── Individual account cards (multi-account, clickable) ──
            if not single:
                for r in accts:
                    bal = r.get("balance", 0)
                    card = QFrame()
                    card.setCursor(Qt.PointingHandCursor)
                    card.setStyleSheet(
                        f"QFrame{{background:{C['surface']};border:1px solid {C['border']};"
                        f"border-radius:8px;}}"
                        f"QFrame:hover{{border-color:{C['accent']};background:{C['accent_bg']};}}"
                        f"QLabel{{background:transparent;border:none;}}")
                    card_lay = QVBoxLayout(card)
                    card_lay.setContentsMargins(14, 8, 14, 8)
                    card_lay.setSpacing(4)

                    row = QHBoxLayout(); row.setSpacing(8)
                    name_lbl = QLabel(r.get("display_name", "—"))
                    name_lbl.setStyleSheet(f"font-size:13px;font-weight:600;color:{C['text']};")
                    row.addWidget(name_lbl, 1)
                    row.addWidget(self._balance_label(bal))
                    card_lay.addLayout(row)

                    if acct_type == "CREDIT_CARD":
                        limit = _get_credit_limit(
                            self.db, r.get("account_id", ""),
                            r.get("credit_limit", 0))
                        util = min(abs(bal) / limit, 1.0) if limit > 0 else 0
                        if limit > 0:
                            card_lay.addWidget(self._util_bar(util))

                    # Click handler
                    _acct = dict(r)
                    _type = acct_type
                    card.mousePressEvent = lambda e, a=_acct, t=_type: self._show_account_txns(a, t)

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
                if d not in by_date: by_date[d] = []
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
        lbl = QLabel(icon); lbl.setStyleSheet("font-size:16px;"); return lbl

    @staticmethod
    def _bold_label(text):
        return QLabel(f"<b style='font-size:13px;color:#111827;'>{text}</b>")

    @staticmethod
    def _balance_label(amount):
        color = "#10B981" if amount >= 0 else "#EF4444"
        sign = "" if amount >= 0 else "- "
        return QLabel(f"<b style='font-size:14px;color:{color};'>{sign}{fmt_money(abs(amount))}</b>")

    @staticmethod
    def _util_bar(util):
        color = _util_color(util)
        bar = QFrame()
        bar.setFixedHeight(6)
        pct = max(0.03, util)
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
