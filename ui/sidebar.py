"""Collapsible sidebar — clean dark theme, no label backgrounds."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QCursor
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
        ("cards", "💳", "Cards"),
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
COLLAPSED_W = 68
ANIM_STEPS = 10
ANIM_MS = 180


class Sidebar(QWidget):
    nav = pyqtSignal(str)

    def __init__(self, bal_svc, repos=None, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(EXPANDED_W)
        self.bal = bal_svc
        self._cr = repos.get("cards") if repos else None
        self._tx_repo = repos.get("transactions") if repos else None
        self._btns = {}
        self._labels = []
        self._dues_widgets = []
        self._expanded = True
        self._animating = False
        self._build()

    def _build(self):
        # Pure dark background, no gradients
        self.setStyleSheet("background: #111827;")

        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(10, 14, 10, 14)
        self.lay.setSpacing(2)

        # ── Header ──
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        self.title_icon = QLabel("💰")
        self.title_icon.setStyleSheet("font-size: 22px; background: transparent; border: none; outline: none;")
        self.title_icon.setAttribute(Qt.WA_TranslucentBackground)
        hdr.addWidget(self.title_icon)

        self.title_label = QLabel("Finance Manager")
        self.title_label.setStyleSheet(
            "color: #4C1D95; font-size: 15px; font-weight: 800; background: transparent; border: none;")
        hdr.addWidget(self.title_label)

        hdr.addStretch()

        self.toggle_btn = QPushButton("◀")
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: #374151;
                color: #D1D5DB;
                border: 1px solid #4B5563;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #4B5563;
                color: #F9FAFB;
                border-color: #6B7280;
            }
        """)
        self.toggle_btn.clicked.connect(self._toggle)
        hdr.addWidget(self.toggle_btn)
        self.lay.addLayout(hdr)

        self.lay.addSpacing(10)

        # ── Net-worth widget — purple gradient ──
        self.nw_frame = QFrame()
        self.nw_frame.setCursor(QCursor(Qt.PointingHandCursor))
        self.nw_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #7C3AED, stop:1 #A855F7);
                border-radius: 12px;
                padding: 14px 16px;
            }
        """)
        nwl = QVBoxLayout(self.nw_frame)
        nwl.setContentsMargins(14, 10, 14, 10)
        nwl.setSpacing(2)

        self.nw_title = QLabel("NET WORTH")
        self.nw_title.setStyleSheet(
            "color: rgba(255,255,255,0.6); font-size: 9px; font-weight: 700; letter-spacing: 1.5px;")
        nwl.addWidget(self.nw_title)

        self.nw_val = QLabel("₹0")
        self.nw_val.setStyleSheet("color: white; font-size: 18px; font-weight: 800;")
        nwl.addWidget(self.nw_val)

        self.nw_frame.mousePressEvent = lambda e: self.nav.emit("balances")
        self.lay.addWidget(self.nw_frame)
        self.lay.addSpacing(8)

        # ── Grouped nav — NO background on labels ──
        for group_label, items in NAV_GROUPS:
            if group_label:
                lbl = QLabel(group_label)
                lbl.setStyleSheet(
                    "color: #6B7280; font-size: 9px; font-weight: 700; "
                    "letter-spacing: 1.5px; padding: 14px 12px 4px; background: transparent; border: none;")
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

        # ── Payment Dues section ──
        self._dues_header = QLabel("PAYMENT DUES")
        self._dues_header.setStyleSheet(
            "color: #6B7280; font-size: 9px; font-weight: 700; "
            "letter-spacing: 1.5px; padding: 14px 12px 4px; background: transparent; border: none;")
        self.lay.addWidget(self._dues_header)
        self._dues_container = QWidget()
        self._dues_container.setStyleSheet("background:transparent;")
        self._dues_lay = QVBoxLayout(self._dues_container)
        self._dues_lay.setContentsMargins(0, 0, 0, 0)
        self._dues_lay.setSpacing(2)
        self.lay.addWidget(self._dues_container)
        self._dues_header.hide()
        self._dues_container.hide()

        self.ver = QLabel("v3.1.0")
        self.ver.setStyleSheet("color: #374151; font-size: 9px; padding: 4px 8px; background: transparent; border: none;")
        self.lay.addWidget(self.ver)

    def _btn_css(self, active):
        if active:
            return """
                QPushButton {
                    background: rgba(124, 58, 237, 0.15);
                    color: #7C3AED;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 12px;
                    text-align: left;
                    font-size: 13px;
                    font-weight: 700;
                }
            """
        return """
            QPushButton {
                background: transparent;
                color: #1F2937;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                text-align: left;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.06);
                color: #E5E7EB;
            }
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

        # Update text
        self.title_label.setVisible(self._expanded)
        for lbl in self._labels:
            lbl.setVisible(self._expanded)
        self.toggle_btn.setText("◀" if self._expanded else "▶")

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

    def select_home(self):
        self._sel("home")

    def refresh_dues(self):
        """Payment dues removed from sidebar — now in Cards tab."""
        for w in self._dues_widgets:
            w.deleteLater()
        self._dues_widgets.clear()
        self._dues_header.hide(); self._dues_container.hide()

    def update_nw(self):
        self.nw_val.setText(fmt_money(self.bal.net_worth()))
