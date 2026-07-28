"""Sidebar — white theme with indigo accent, icon toggle, due reminders."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame, QScrollArea, QSizePolicy)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QCursor
from datetime import date, timedelta
from ui.theme import C


def fmt_money(v):
    if v is None:
        return "₹0"
    neg = v < 0
    v = abs(v)
    s = f"{v:,.2f}"
    parts = s.split(".")
    int_part = parts[0].replace(",", "")
    if len(int_part) > 3:
        last3 = int_part[-3:]
        rest = int_part[:-3]
        groups = []
        while rest:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        s = ",".join(groups) + "," + last3 + "." + parts[1]
    return ("-" if neg else "") + "₹" + s


NAV_GROUPS = [
    ("", [("home", "🏠", "Home")]),
    ("DAILY", [
        ("transaction_entry", "📝", "Transactions"),
        ("database", "🗄️", "Database"),
        ("balances", "💰", "Balances"),
        ("split", "🤝", "Split"),
    ]),
    ("CARDS", [
        ("cards", "💳", "Credit Cards"),
        ("debit_cards", "🏧", "Debit Cards"),
    ]),
    ("REVIEW & PLANNING", [
        ("audit", "🔍", "Audit"),
        ("wealth", "📈", "Wealth"),
    ]),
    ("TOOLS", [
        ("notes", "📋", "Notes"),
        ("settings", "⚙️", "Settings"),
        ("gmail", "📧", "Gmail"),
    ]),
]

EXPANDED_W = 230
COLLAPSED_W = 76

# Reminder cards live inside the expanded sidebar. Width is pinned so a long
# card name can never stretch the layout past the sidebar edge, and kept well
# inside the sidebar so the cards read as an indented sub-list.
_REM_CARD_W = EXPANDED_W - 56      # sidebar padding + layout margins + scrollbar gutter
_REM_TEXT_W = _REM_CARD_W - 24     # room for the overdue flag + padding
_REM_MAX_CARDS = 10                # cards rendered; heading shows the true total
_REM_CARD_H = 46                   # natural two-row height; never compress below this
_REM_PANEL_MIN_H = 108             # ~2 cards visible even on short windows
_REM_PANEL_MAX_H = 210             # beyond this the list scrolls
ANIM_STEPS = 10
ANIM_MS = 180

# Indigo palette — white bg
_PRIMARY = "#4338CA"
_PRIMARY_LIGHT = "#6366F1"
_PRIMARY_PALE = "#E0E7FF"


def _parse_stmt_day(stmt_str):
    try:
        day_str = "".join(c for c in stmt_str if c.isdigit())
        if day_str: return int(day_str)
    except: pass
    return None


def _cycle_name(start_date):
    return start_date.strftime("%b %Y")


class Sidebar(QWidget):
    nav = pyqtSignal(str)

    def __init__(self, bal_svc, repos=None, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(EXPANDED_W)
        self.bal = bal_svc
        self._cr = repos.get("cards") if repos else None
        self._tx_repo = repos.get("transactions") if repos else None
        self._acct_repo = repos.get("accounts") if repos else None
        self._btns = {}
        self._labels = []
        self._expanded = True
        self._animating = False
        self._has_dues = False
        self._due_count = 0
        self._due_dots = []
        self._build()

    def _build(self):
        self.setStyleSheet("background: transparent;")

        # Outer layout with margins so the card floats
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(8, 8, 0, 8)
        self._outer.setSpacing(0)

        # Card container
        self.card = QFrame()
        self.card.setObjectName("sidebar-card")
        self.card.setStyleSheet(
            f"QFrame#sidebar-card{{background:#F0EEFF;border:1px solid {C['border2']};"
            f"border-radius:12px;}}"
            f"QLabel{{background:transparent;border:none;outline:none;}}")
        from ui.widgets.metric_card import add_shadow
        add_shadow(self.card, blur=16, y_offset=2)

        self.lay = QVBoxLayout(self.card)
        self.lay.setContentsMargins(10, 14, 10, 14)
        self.lay.setSpacing(2)
        self._outer.addWidget(self.card)

        # ── Header — click to toggle ──
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        # Collapsed: FM monogram — same height/style as selected nav button
        self.title_icon = QLabel(" FM ")
        self.title_icon.setFixedHeight(40)
        self.title_icon.setAlignment(Qt.AlignCenter)
        self.title_icon.setStyleSheet(
            "font-size: 14px; font-weight: 800; color: white; "
            "background: #4338CA; border: none; border-radius: 8px; "
            "padding: 8px 12px;")
        self.title_icon.setCursor(QCursor(Qt.PointingHandCursor))
        self.title_icon.mousePressEvent = lambda e: self._toggle()
        hdr.addWidget(self.title_icon)

        # Expanded: app name in white container
        self.hdr_frame = QFrame()
        self.hdr_frame.setCursor(QCursor(Qt.PointingHandCursor))
        self.hdr_frame.setStyleSheet(
            f"QFrame{{background:white;border:1px solid {C['border']};border-radius:10px;}}"
            f"QLabel{{background:transparent;border:none;outline:none;}}")
        self.hdr_frame.mousePressEvent = lambda e: self._toggle()
        hf_lay = QHBoxLayout(self.hdr_frame)
        hf_lay.setContentsMargins(12, 8, 12, 8)
        hf_lay.setSpacing(6)
        self.title_label = QLabel("Finance Manager")
        self.title_label.setStyleSheet(
            f"color: {_PRIMARY}; font-size: 15px; font-weight: 800;")
        hf_lay.addWidget(self.title_label)
        hdr.addWidget(self.hdr_frame, 1)

        hdr.addStretch()
        self.lay.addLayout(hdr)
        self.lay.addSpacing(10)

        # Initially expanded — monogram hidden
        self.title_icon.hide()

        # ── Grouped nav ──
        for group_label, items in NAV_GROUPS:
            if group_label:
                lbl = QLabel(group_label)
                lbl.setStyleSheet(
                    "color: #111827; font-size: 9px; font-weight: 700; "
                    "letter-spacing: 1.5px; padding: 14px 12px 4px; background: transparent; border:none;")
                self.lay.addWidget(lbl)
                self._labels.append(lbl)

            for key, icon, label_text in items:
                btn = QPushButton(f" {icon}  {label_text}")
                btn.setObjectName("sidebar-item")
                btn.setCursor(QCursor(Qt.PointingHandCursor))
                btn.setMinimumHeight(40)
                btn.setStyleSheet(self._btn_css(False))
                btn.clicked.connect(lambda _, kk=key: self._sel(kk))
                self.lay.addWidget(btn)
                self._btns[key] = btn

        self.lay.addStretch()

        # ── Collapsed due dots container (bottom-left) ──
        self._dots_container = QWidget()
        self._dots_container.setStyleSheet("background:transparent;border:none;")
        self._dots_lay = QVBoxLayout(self._dots_container)
        self._dots_lay.setContentsMargins(0, 0, 0, 0)
        self._dots_lay.setSpacing(4)
        self._dots_container.hide()
        self.lay.addWidget(self._dots_container)

        # ── Due / Overdue Reminders (expanded) ──
        self._rem_header = QLabel("PAYMENT DUES")
        self._rem_header.setStyleSheet(
            f"color: {_PRIMARY}; font-size: 9px; font-weight: 700; "
            f"letter-spacing: 1.5px; padding: 10px 12px 4px; background: transparent; border: none;")
        self.lay.addWidget(self._rem_header)
        self._rem_header.hide()

        self._rem_scroll = QScrollArea()
        self._rem_scroll.setWidgetResizable(True)
        self._rem_scroll.setFrameShape(QFrame.NoFrame)
        # Reserve real vertical space. Without a minimum the surrounding layout
        # squeezes this panel down to a few pixels on shorter windows and the
        # cards get crushed instead of scrolling.
        self._rem_scroll.setMinimumHeight(_REM_PANEL_MIN_H)
        self._rem_scroll.setMaximumHeight(_REM_PANEL_MAX_H)
        # Never let content dictate width — the sidebar is a fixed 230px and a
        # long card name would otherwise force a horizontal scrollbar and push
        # the amount out of view.
        self._rem_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._rem_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._rem_scroll.setSizeAdjustPolicy(QScrollArea.AdjustIgnored)
        self._rem_scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{background:transparent;width:6px;margin:0;}"
            "QScrollBar::handle:vertical{background:rgba(0,0,0,0.18);"
            "border-radius:3px;min-height:24px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent;}")
        rem_inner = QWidget()
        rem_inner.setStyleSheet("background:transparent;")
        # Grow to the natural height of the cards; the QScrollArea then scrolls
        # it. Without this the widget is squeezed to the viewport and the cards
        # overlap each other.
        rem_inner.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        self._rem_lay = QVBoxLayout(rem_inner)
        # Right padding reserves room for the thin scrollbar so cards don't
        # sit underneath it.
        self._rem_lay.setContentsMargins(10, 0, 8, 0)
        self._rem_lay.setSpacing(5)
        self._rem_lay.setSizeConstraint(QVBoxLayout.SetMinAndMaxSize)
        self._rem_scroll.setWidget(rem_inner)
        self.lay.addWidget(self._rem_scroll)
        self._rem_scroll.hide()

        self.ver = QLabel("v3.1.0")
        self.ver.setStyleSheet(f"color: {C['text3']}; font-size: 9px; padding: 4px 8px; background: transparent; border: none;")
        self.lay.addWidget(self.ver)

    def _btn_css(self, active):
        if active:
            return f"""
                QPushButton {{
                    background: {_PRIMARY};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 12px;
                    text-align: left;
                    font-size: 13px;
                    font-weight: 700;
                }}
            """
        return f"""
            QPushButton {{
                background: transparent;
                color: {_PRIMARY};
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                text-align: left;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {C['surface']};
                color: #111827;
                font-weight: 700;
            }}
        """

    # ── Smooth collapse / expand ──
    def _toggle(self):
        if self._animating:
            return
        self._expanded = not self._expanded
        self._animating = True

        start = self.width()
        end = EXPANDED_W if self._expanded else COLLAPSED_W
        self._anim_step = 0
        self._anim_start = start
        self._anim_delta = end - start

        # Reduce margins on collapse to prevent icon clipping
        m = 8 if self._expanded else 4
        self._outer.setContentsMargins(m, m, 0, m)

        self.title_label.setVisible(self._expanded)
        self.hdr_frame.setVisible(self._expanded)
        self.title_icon.setVisible(not self._expanded)
        for lbl in self._labels:
            lbl.setVisible(self._expanded)

        # Toggle reminders / dots
        if self._expanded:
            self._dots_container.hide()
            if self._has_dues:
                self._rem_header.show()
                self._rem_scroll.show()
        else:
            self._rem_header.hide()
            self._rem_scroll.hide()
            self._refresh_dots()

        for group_label, items in NAV_GROUPS:
            for key, icon, label_text in items:
                btn = self._btns.get(key)
                if btn:
                    btn.setText(f" {icon}  {label_text}" if self._expanded else f" {icon}")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._anim_tick)
        self._timer.start(ANIM_MS // ANIM_STEPS)

    def _anim_tick(self):
        self._anim_step += 1
        t = self._anim_step / ANIM_STEPS
        ease = 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2
        w = int(self._anim_start + self._anim_delta * ease)
        self.setFixedWidth(w)
        if self._anim_step >= ANIM_STEPS:
            self._timer.stop()
            self.setFixedWidth(EXPANDED_W if self._expanded else COLLAPSED_W)
            self._animating = False

    def _sel(self, key):
        for k, b in self._btns.items():
            b.setStyleSheet(self._btn_css(k == key))
        self.nav.emit(key)

    def highlight(self, key):
        """Update button highlight without emitting nav signal."""
        for k, b in self._btns.items():
            b.setStyleSheet(self._btn_css(k == key))

    def select_home(self):
        self._sel("home")

    def _refresh_dots(self):
        """Show/hide stacked indigo dots for collapsed state."""
        for w in self._due_dots:
            w.deleteLater()
        self._due_dots.clear()

        if not self._expanded and self._has_dues:
            self._dots_container.show()
            count = self._due_count
            for _ in range(min(count, 8)):
                dot = QFrame()
                dot.setFixedSize(32, 6)
                dot.setStyleSheet(f"background:{_PRIMARY};border-radius:3px;")
                self._dots_lay.addWidget(dot, 0, Qt.AlignHCenter)
                self._due_dots.append(dot)
        else:
            self._dots_container.hide()

    def refresh_dues(self):
        """Load due/overdue reminders from card_cycles table."""
        # Clear existing reminders
        while self._rem_lay.count():
            itm = self._rem_lay.takeAt(0)
            w = itm.widget()
            if w:
                w.deleteLater()

        if not self._cr:
            # Reset the caption too, or a stale "(8)" lingers after the data goes.
            self._rem_header.setText("PAYMENT DUES")
            self._rem_header.setToolTip("")
            self._rem_header.hide(); self._rem_scroll.hide()
            self._has_dues = False; self._due_count = 0; self._refresh_dots()
            return

        today = date.today()
        today_iso = today.isoformat()
        reminders = []

        cards = self._cr.list_active()
        for card in cards:
            name = card.get("card_name", card.get("issuer_bank", "Card"))
            aid = card["account_id"]
            try:
                cycles = self._cr.get_cycles(aid)
            except:
                continue
            for cyc in cycles:
                cyc_end = cyc.get("statement_date", "")
                if not cyc_end or cyc_end >= today_iso:
                    continue
                remaining = cyc.get("remaining", 0) or 0
                if remaining <= 0:
                    continue
                due_str = cyc.get("due_date", "") or ""
                if not due_str or "-" not in due_str:
                    continue
                cs_str = cyc.get("cycle_start_date", "")
                try:
                    cycle_nm = _cycle_name(date.fromisoformat(cs_str))
                except:
                    cycle_nm = cs_str
                try:
                    due_dt = date.fromisoformat(due_str)
                    dd = (due_dt - today).days
                except:
                    continue
                if dd < 0:
                    reminders.append((-100, name, cycle_nm, remaining, "#EF4444", True))
                else:
                    col = "#D97706" if dd <= 3 else "#059669"
                    reminders.append((dd, name, cycle_nm, remaining, col, False))

        reminders.sort(key=lambda r: r[0])
        self._has_dues = len(reminders) > 0
        self._due_count = len(reminders)

        if not reminders:
            self._rem_header.setText("PAYMENT DUES")
            self._rem_header.setToolTip("")
            self._rem_header.hide(); self._rem_scroll.hide()
            self._has_dues = False; self._due_count = 0; self._refresh_dots()
            return

        # Show the count beside the heading, e.g. "PAYMENT DUES (3)".
        shown = min(len(reminders), _REM_MAX_CARDS)
        if len(reminders) > shown:
            self._rem_header.setText(f"PAYMENT DUES ({shown} of {len(reminders)})")
        else:
            self._rem_header.setText(f"PAYMENT DUES ({len(reminders)})")
        n_overdue = sum(1 for r in reminders if r[5])
        self._rem_header.setToolTip(
            f"{len(reminders)} pending due{'' if len(reminders) == 1 else 's'}"
            + (f"  \u00b7  {n_overdue} overdue" if n_overdue else ""))

        # Expanded: show cards. Collapsed: show dots.
        if self._expanded:
            self._rem_header.show(); self._rem_scroll.show()
            self._dots_container.hide()
        else:
            self._rem_header.hide(); self._rem_scroll.hide()
            self._refresh_dots()

        # Two-row card: name on top (elided, never wraps), cycle + amount below.
        # A single row could not fit "name · cycle · amount" in 230px — the
        # amount got squeezed to nothing or the card grew past the sidebar.
        for _, name, cycle_nm, amount, color, is_overdue in reminders[:_REM_MAX_CARDS]:
            row = QFrame()
            row.setStyleSheet(
                f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};"
                f"border-left:3px solid {color};border-radius:8px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            # Fixed width keeps every card identical and inside the sidebar,
            # regardless of how long the card name is.
            row.setFixedWidth(_REM_CARD_W)
            # Fixed height as well — otherwise a short sidebar compresses the
            # cards into unreadable slivers instead of scrolling them.
            row.setFixedHeight(_REM_CARD_H)
            # Tooltip on the card (and every child) so hovering anywhere works.
            # Setting it only on the elided label meant the surrounding padding
            # showed nothing.
            due_word = "Overdue" if is_overdue else "Due"
            row.setToolTip(
                f"{name}\n{cycle_nm}\n{due_word}: {fmt_money(amount)}")
            outer = QVBoxLayout(row)
            outer.setContentsMargins(9, 6, 9, 6)
            outer.setSpacing(3)

            top = QHBoxLayout()
            top.setContentsMargins(0, 0, 0, 0)
            top.setSpacing(5)
            name_lbl = QLabel()
            name_lbl.setStyleSheet(f"color:{C['text']};font-size:11px;font-weight:700;")
            # Elide rather than wrap — keeps every card the same height.
            fm = name_lbl.fontMetrics()
            name_lbl.setText(fm.elidedText(name, Qt.ElideRight, _REM_TEXT_W))
            # Children must not eat the hover, or the card tooltip never shows.
            name_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            top.addWidget(name_lbl, 1)
            if is_overdue:
                flag = QLabel("!")
                flag.setFixedSize(14, 14)
                flag.setAlignment(Qt.AlignCenter)
                flag.setStyleSheet(
                    f"background:{color};color:white;border-radius:7px;"
                    f"font-size:9px;font-weight:800;")
                flag.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                top.addWidget(flag, 0)
            outer.addLayout(top)

            bottom = QHBoxLayout()
            bottom.setContentsMargins(0, 0, 0, 0)
            bottom.setSpacing(5)
            cyc = QLabel()
            cyc.setStyleSheet(f"color:{C['text3']};font-size:10px;")
            cyc.setText(cyc.fontMetrics().elidedText(cycle_nm, Qt.ElideRight, 84))
            cyc.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            bottom.addWidget(cyc, 1)
            amt = QLabel(fmt_money(amount))
            amt.setStyleSheet(f"color:{color};font-size:11px;font-weight:800;")
            amt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amt.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            bottom.addWidget(amt, 0)
            outer.addLayout(bottom)

            self._rem_lay.addWidget(row, 0, Qt.AlignTop)

    def update_nw(self):
        """No-op — net worth now shown on Home tab."""
        pass