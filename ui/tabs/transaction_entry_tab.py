"""Transaction Entry — Regular (label) + Transfer (Razorpay-style animation)."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QLineEdit, QDoubleSpinBox,
                              QDateEdit, QFrame, QScrollArea,
                              QGraphicsOpacityEffect, QGraphicsDropShadowEffect,
                              QStackedWidget)
from PyQt5.QtCore import (Qt, QDate, QTimer, QSequentialAnimationGroup,
                           QParallelAnimationGroup, QPropertyAnimation,
                           QEasingCurve, QRect, pyqtProperty, pyqtSignal)
from PyQt5.QtGui import QColor, QCursor, QPainter, QPen, QBrush, QFont
import uuid, math
from datetime import timedelta
from ui.theme import C
from ui.sidebar import fmt_money
from ui.widgets.searchable_combo import SearchableCombo
from ui.tabs.database_tab import _tx_card
from ui.uppercase import force_upper

PAYMENT_METHODS = [
    "PHONEPAY", "SLICE", "DIRECT TRANSFER", "CASH", "AMAZON PAY",
    "FLIPKART 3I", "ATM", "CRED APP", "SUPER MONEY", "PAYTM",
    "GOOGLE PAY", "NAVY UPI", "BHIM UPI", "AIRTEL PAY", "NETBANKING",
    "CHEQUE", "FED UPI", "AXIS UPI", "NAMMA METRO CARD", "YONO",
    "CANARA AI", "SIB MIRROR", "OTHER"
]

_ACCT_TYPE_LABEL = {
    "CURRENT": "Debit",
    "CREDIT_CARD": "Credit Card",
    "WALLET": "Wallet",
    "CASH": "Cash",
}

def _acct_display(name, acct_type):
    """Format account name with type suffix: 'HDFC Savings  ·  Debit'."""
    label = _ACCT_TYPE_LABEL.get(acct_type, "")
    if label:
        return f"{name}  ·  {label}"
    return name

def _toggle_css(on, color):
    if on:
        return (f"background:{color};color:#FFF;border:none;"
                f"border-radius:8px;padding:10px 16px;font-size:13px;font-weight:700;")
    return (f"background:rgba(255,255,255,0.05);color:{C['text3']};"
            f"border:1.5px solid {C['border']};border-radius:8px;"
            f"padding:10px 16px;font-size:13px;font-weight:500;")

def _input_css():
    return (f"background:{C['surface']};border:1.5px solid {C['border']};"
            f"border-radius:8px;padding:10px 12px;font-size:13px;")


# ═══════════════════════════════════════════════════════════
# RAZORPAY-STYLE CHECKMARK WIDGET (custom painted)
# ═══════════════════════════════════════════════════════════

class CheckmarkWidget(QWidget):
    """Animated circle + checkmark, Razorpay style."""

    def __init__(self, color="#4F46E5", size=100, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._color = QColor(color)
        self._scale = 0.0
        self._check_progress = 0.0
        self._ripple = 0.0
        self._ripple_opacity = 0.0

    def getScale(self): return self._scale
    def setScale(self, v): self._scale = v; self.update()
    scale = pyqtProperty(float, getScale, setScale)

    def getCheck(self): return self._check_progress
    def setCheck(self, v): self._check_progress = v; self.update()
    checkProgress = pyqtProperty(float, getCheck, setCheck)

    def getRipple(self): return self._ripple
    def setRipple(self, v): self._ripple = v; self.update()
    ripple = pyqtProperty(float, getRipple, setRipple)

    def getRippleOpacity(self): return self._ripple_opacity
    def setRippleOpacity(self, v): self._ripple_opacity = v; self.update()
    rippleOpacity = pyqtProperty(float, getRippleOpacity, setRippleOpacity)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        r = min(cx, cy) - 8

        # Ripple ring
        if self._ripple_opacity > 0:
            p.setPen(QPen(QColor(self._color.red(), self._color.green(),
                                  self._color.blue(), int(255 * self._ripple_opacity)), 3))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(int(cx - r * self._ripple), int(cy - r * self._ripple),
                          int(2 * r * self._ripple), int(2 * r * self._ripple))

        # Circle (scaled)
        sr = r * self._scale
        if sr > 0:
            p.setPen(Qt.NoPen)
            p.setBrush(self._color)
            p.drawEllipse(int(cx - sr), int(cy - sr), int(2 * sr), int(2 * sr))

            # Checkmark
            if self._check_progress > 0:
                p.setPen(QPen(QColor("white"), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                # Check path: short leg → long leg
                sx, sy = cx - sr * 0.35, cy + sr * 0.0
                mx, my = cx - sr * 0.05, cy + sr * 0.35
                ex, ey = cx + sr * 0.4, cy - sr * 0.3

                cp = self._check_progress
                if cp <= 0.5:
                    # Drawing short leg
                    t = cp / 0.5
                    ex2 = sx + (mx - sx) * t
                    ey2 = sy + (my - sy) * t
                    p.drawLine(int(sx), int(sy), int(ex2), int(ey2))
                else:
                    # Short leg done, drawing long leg
                    p.drawLine(int(sx), int(sy), int(mx), int(my))
                    t = (cp - 0.5) / 0.5
                    ex2 = mx + (ex - mx) * t
                    ey2 = my + (ey - my) * t
                    p.drawLine(int(mx), int(my), int(ex2), int(ey2))
        p.end()


# ═══════════════════════════════════════════════════════════
# RAZORPAY SUCCESS CARD (the full overlay)
# ═══════════════════════════════════════════════════════════

class RazorpaySuccessCard(QFrame):
    """Razorpay-style transfer success overlay with checkmark + count-up."""
    dismissed = pyqtSignal()

    def __init__(self, from_name, to_name, amount, parent=None):
        super().__init__(parent)
        self._amount = amount
        self._current_amount = 0.0
        self._from_name = from_name
        self._to_name = to_name
        self._build()
        self._animate()

    def _build(self):
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(240,253,244,0.97), stop:1 rgba(220,252,231,0.97));
                border-radius: 24px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)
        layout.setContentsMargins(20, 10, 20, 10)

        # Checkmark (smaller to fit form area)
        self.checkmark = CheckmarkWidget(color="#059669", size=60)
        layout.addWidget(self.checkmark, alignment=Qt.AlignCenter)

        # Amount (count-up label)
        self.amt_label = QLabel("₹0")
        self.amt_label.setAlignment(Qt.AlignCenter)
        self.amt_label.setStyleSheet(
            "color: #064E3B; font-size: 24px; font-weight: 900; background: transparent;")
        self.amt_label.hide()
        layout.addWidget(self.amt_label)

        # From → To
        self.flow_label = QLabel(f"{self._from_name}   →   {self._to_name}")
        self.flow_label.setAlignment(Qt.AlignCenter)
        self.flow_label.setStyleSheet(
            "color: #059669; font-size: 13px; font-weight: 700; background: transparent;")
        self.flow_label.hide()
        layout.addWidget(self.flow_label)

        # Status text (single label)
        self.status_label = QLabel("Transfer Successful")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            "color: #047857; font-size: 14px; font-weight: 700; background: transparent;")
        self.status_label.hide()
        layout.addWidget(self.status_label)

        # Done button
        self.done_btn = QPushButton("Done")
        self.done_btn.setCursor(Qt.PointingHandCursor)
        self.done_btn.setFixedSize(140, 36)
        self.done_btn.setStyleSheet("""
            QPushButton {
                background: #059669; color: white; border: none;
                border-radius: 10px; font-size: 14px; font-weight: 700;
            }
            QPushButton:hover { background: #047857; }
        """)
        self.done_btn.clicked.connect(self._dismiss)
        self.done_btn.hide()
        layout.addWidget(self.done_btn, alignment=Qt.AlignCenter)

    def _animate(self):
        """Sequence: checkmark scale → checkmark draw → ripple → amount count-up → labels → done."""
        # 1. Checkmark circle scale (spring overshoot)
        scale_up = QPropertyAnimation(self.checkmark, b"scale")
        scale_up.setDuration(500)
        scale_up.setKeyValueAt(0.0, 0.0)
        scale_up.setKeyValueAt(0.6, 1.15)
        scale_up.setKeyValueAt(0.8, 0.95)
        scale_up.setKeyValueAt(1.0, 1.0)
        scale_up.setEasingCurve(QEasingCurve.OutQuad)

        # 2. Checkmark draw
        check_anim = QPropertyAnimation(self.checkmark, b"checkProgress")
        check_anim.setDuration(400)
        check_anim.setStartValue(0.0)
        check_anim.setEndValue(1.0)
        check_anim.setEasingCurve(QEasingCurve.OutQuad)

        # 3. Ripple
        ripple_expand = QPropertyAnimation(self.checkmark, b"ripple")
        ripple_expand.setDuration(600)
        ripple_expand.setStartValue(1.0)
        ripple_expand.setEndValue(2.5)
        ripple_expand.setEasingCurve(QEasingCurve.OutQuad)

        ripple_fade = QPropertyAnimation(self.checkmark, b"rippleOpacity")
        ripple_fade.setDuration(600)
        ripple_fade.setStartValue(0.6)
        ripple_fade.setEndValue(0.0)

        ripple_group = QParallelAnimationGroup()
        ripple_group.addAnimation(ripple_expand)
        ripple_group.addAnimation(ripple_fade)

        # Sequence
        self._seq = QSequentialAnimationGroup(self)
        self._seq.addAnimation(scale_up)
        self._seq.addAnimation(check_anim)
        self._seq.addAnimation(ripple_group)
        self._seq.addPause(200)
        self._seq.finished.connect(self._show_details)
        self._seq.start()

    def _show_details(self):
        """After checkmark: count-up amount, then labels, then done button."""
        # Amount count-up
        self.amt_label.show()
        self._count_timer = QTimer(self)
        self._count_step = 0
        self._count_total = 30  # 30 steps
        self._count_timer.timeout.connect(self._count_tick)
        self._count_timer.start(25)  # ~750ms total

    def _count_tick(self):
        self._count_step += 1
        t = self._count_step / self._count_total
        t = 1 - (1 - t) ** 3  # ease out
        current = self._amount * t
        self.amt_label.setText(fmt_money(current))

        if self._count_step >= self._count_total:
            self._count_timer.stop()
            self.amt_label.setText(fmt_money(self._amount))
            # Show flow → status + done together
            QTimer.singleShot(200, self._show_flow)
            QTimer.singleShot(500, self._show_status_and_done)

    def _show_flow(self):
        self.flow_label.show()
        eff = QGraphicsOpacityEffect(self.flow_label)
        self.flow_label.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b"opacity")
        a.setDuration(300); a.setStartValue(0.0); a.setEndValue(1.0)
        a.start(); self._flow_anim = a

    def _show_status_and_done(self):
        """Show 'Transfer Successful' + 'Done' button."""
        self.status_label.show()
        self.done_btn.show()
        self.done_btn.setFocus()
        self._sd_anims = []
        for widget in (self.status_label, self.done_btn):
            eff = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(eff)
            a = QPropertyAnimation(eff, b"opacity")
            a.setDuration(300); a.setStartValue(0.0); a.setEndValue(1.0)
            a.start()
            self._sd_anims.append(a)

    def _dismiss(self):
        self.done_btn.setEnabled(False)
        self.dismissed.emit()
        self.hide()
        # Defer deletion so signal fully processes first
        QTimer.singleShot(100, self.deleteLater)


# ═══════════════════════════════════════════════════════════
# MAIN TAB
# ═══════════════════════════════════════════════════════════

class TransactionEntryTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self.acct_repo = repos["accounts"]
        self.tx_repo = repos["transactions"]
        self.lu = repos["lookups"]
        self._cat_pf = {}
        self._is_debit = True
        self._nw = 0
        self._acct_list = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 12, 28, 12)
        root.setSpacing(6)

        h = QLabel("Transaction Entry")
        h.setStyleSheet(f"font-size:22px;font-weight:800;color:{C['text']};")
        root.addWidget(h)

        tabs_row = QHBoxLayout(); tabs_row.setSpacing(8)
        self.tab_regular = QPushButton("📝  Regular")
        self.tab_transfer = QPushButton("🔄  Transfer")
        self.tab_gmail = QPushButton("📧  Gmail Queue")
        self._tab_btns = [self.tab_regular, self.tab_transfer, self.tab_gmail]
        for b in self._tab_btns:
            b.setMinimumHeight(42); b.setCursor(Qt.PointingHandCursor)
        self.tab_regular.clicked.connect(lambda: self._switch(0))
        self.tab_transfer.clicked.connect(lambda: self._switch(1))
        self.tab_gmail.clicked.connect(lambda: self._switch(2))
        for b in self._tab_btns: tabs_row.addWidget(b)
        tabs_row.addStretch()
        root.addLayout(tabs_row)

        # Form container (parent for overlay)
        self.form_container = QFrame()
        self.form_container.setStyleSheet("QFrame{background:transparent;margin:0px;padding:0px;}")
        form_layout = QVBoxLayout(self.form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(0)
        self.stack = QStackedWidget()
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self._build_regular())
        self.stack.addWidget(self._build_transfer())
        self.stack.addWidget(self._build_gmail())
        form_layout.addWidget(self.stack)
        root.addWidget(self.form_container)  # no stretch — form takes only what it needs

        # Recent transactions — card-based (same design as Database tab)
        self.recent_label = QLabel("Recent Transactions")
        self.recent_label.setStyleSheet(f"font-size:13px;font-weight:700;color:{C['text2']};")
        root.addWidget(self.recent_label)

        recent_scroll = QScrollArea()
        recent_scroll.setWidgetResizable(True)
        recent_scroll.setFrameShape(QFrame.NoFrame)
        recent_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        recent_inner = QWidget()
        recent_inner.setStyleSheet("background:transparent;")
        self.recent_lay = QVBoxLayout(recent_inner)
        self.recent_lay.setSpacing(4)
        self.recent_lay.setContentsMargins(0, 0, 0, 0)
        recent_scroll.setWidget(recent_inner)
        root.addWidget(recent_scroll, 1)
        self._switch(0)

    # ═══════════════════════════════════
    # REGULAR FORM
    # ═══════════════════════════════════
    def _build_regular(self):
        w = QWidget()
        lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)

        r1 = QHBoxLayout(); r1.setSpacing(6)
        self.amt = QDoubleSpinBox(); self.amt.setPrefix("₹ "); self.amt.setRange(1, 99999999)
        self.amt.setDecimals(2); self.amt.setMinimumHeight(42); self.amt.setStyleSheet(_input_css())
        r1.addWidget(self.amt, 2)
        self.dc_btn = QPushButton("DEBIT"); self.dc_btn.setMinimumHeight(42); self.dc_btn.setMinimumWidth(85)
        self.dc_btn.setCursor(Qt.PointingHandCursor); self.dc_btn.clicked.connect(self._toggle_dc)
        r1.addWidget(self.dc_btn)
        self.ac_combo = SearchableCombo(placeholder="Account..."); self.ac_combo.setMinimumHeight(42)
        r1.addWidget(self.ac_combo, 3)
        lay.addLayout(r1)

        r2 = QHBoxLayout(); r2.setSpacing(6)
        self.cat_combo = SearchableCombo(placeholder="Category..."); self.cat_combo.setMinimumHeight(42)
        r2.addWidget(self.cat_combo, 2)
        self.method_combo = SearchableCombo(placeholder="Method..."); self.method_combo.setMinimumHeight(42)
        r2.addWidget(self.method_combo, 2)
        self.date_edit = QDateEdit(); self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True); self.date_edit.setMinimumHeight(42)
        self.date_edit.dateChanged.connect(self._on_date)
        r2.addWidget(self.date_edit)
        lay.addLayout(r2)

        r3 = QHBoxLayout(); r3.setSpacing(6)
        self.nw_btns = []
        for i, txt in enumerate(["None", "Need", "Want"]):
            b = QPushButton(txt); b.setMinimumHeight(42); b.setMinimumWidth(65)
            b.setCursor(Qt.PointingHandCursor); b.clicked.connect(lambda _, idx=i: self._set_nw(idx))
            r3.addWidget(b); self.nw_btns.append(b)
        self.person_edit = QLineEdit(); self.person_edit.setPlaceholderText("Person / Org")
        self.person_edit.setMinimumHeight(42); self.person_edit.setStyleSheet(_input_css())
        force_upper(self.person_edit)
        r3.addWidget(self.person_edit, 1)
        self.desc_edit = QLineEdit(); self.desc_edit.setPlaceholderText("Description")
        self.desc_edit.setMinimumHeight(42); self.desc_edit.setStyleSheet(_input_css())
        r3.addWidget(self.desc_edit, 1)
        lay.addLayout(r3)

        r4 = QHBoxLayout(); r4.setSpacing(6)
        self.pf_label = QLabel("PF: —")
        self.pf_label.setStyleSheet(f"color:{C['text3']};font-size:12px;font-style:italic;")
        r4.addWidget(self.pf_label)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"font-size:13px;font-weight:600;")
        r4.addWidget(self.status_label)
        r4.addStretch()
        self.add_btn = QPushButton("➕  Add Transaction")
        self.add_btn.setMinimumHeight(46); self.add_btn.setMinimumWidth(190)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C['accent']};color:white;border:none;
                border-radius:10px;padding:12px 24px;font-size:14px;font-weight:700;
            }}
            QPushButton:hover{{background:#4338CA;}}
        """)
        self.add_btn.clicked.connect(self._add_tx)
        r4.addWidget(self.add_btn)
        lay.addLayout(r4)
        self._update_dc(); self._update_nw()
        return w

    # ═══════════════════════════════════
    # TRANSFER FORM
    # ═══════════════════════════════════
    def _build_transfer(self):
        w = QWidget()
        lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)

        r1 = QHBoxLayout(); r1.setSpacing(6)
        self.tf_from = SearchableCombo(placeholder="From account..."); self.tf_from.setMinimumHeight(42)
        self.tf_from.currentIndexChanged.connect(self._on_from_changed)
        r1.addWidget(self.tf_from, 2)
        self.swap_btn = QPushButton("⇄"); self.swap_btn.setFixedSize(48, 42)
        self.swap_btn.setCursor(Qt.PointingHandCursor)
        self.swap_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C['accent_bg']};color:{C['accent']};
                border:1px solid {C['accent']};border-radius:8px;font-size:20px;font-weight:700;
            }}
            QPushButton:hover{{background:{C['accent']};color:white;}}
        """)
        self.swap_btn.clicked.connect(self._swap)
        r1.addWidget(self.swap_btn)
        self.tf_to = SearchableCombo(placeholder="To account..."); self.tf_to.setMinimumHeight(42)
        self.tf_to.currentIndexChanged.connect(self._on_to_changed)
        r1.addWidget(self.tf_to, 2)
        lay.addLayout(r1)

        r2 = QHBoxLayout(); r2.setSpacing(6)
        self.tf_amt = QDoubleSpinBox(); self.tf_amt.setPrefix("₹ "); self.tf_amt.setRange(1, 99999999)
        self.tf_amt.setDecimals(2); self.tf_amt.setMinimumHeight(42); self.tf_amt.setStyleSheet(_input_css())
        r2.addWidget(self.tf_amt, 2)
        self.tf_method = SearchableCombo(placeholder="Method..."); self.tf_method.setMinimumHeight(42)
        r2.addWidget(self.tf_method, 2)
        self.tf_date = QDateEdit(); self.tf_date.setDate(QDate.currentDate())
        self.tf_date.setCalendarPopup(True); self.tf_date.setMinimumHeight(42)
        self.tf_date.dateChanged.connect(self._on_date)
        r2.addWidget(self.tf_date)
        lay.addLayout(r2)

        self.tf_desc = QLineEdit(); self.tf_desc.setPlaceholderText("Description (optional)")
        self.tf_desc.setMinimumHeight(42); self.tf_desc.setStyleSheet(_input_css())
        lay.addWidget(self.tf_desc)

        r4 = QHBoxLayout(); r4.setSpacing(6)
        self.tf_status = QLabel("")
        self.tf_status.setStyleSheet(f"font-size:13px;font-weight:600;")
        r4.addWidget(self.tf_status)
        r4.addStretch()
        self.tf_btn = QPushButton("💸  Transfer")
        self.tf_btn.setMinimumHeight(46); self.tf_btn.setMinimumWidth(190)
        self.tf_btn.setCursor(Qt.PointingHandCursor)
        self.tf_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C['accent']};color:white;border:none;
                border-radius:10px;padding:12px 24px;font-size:14px;font-weight:700;
            }}
            QPushButton:hover{{background:#4338CA;}}
        """)
        self.tf_btn.clicked.connect(self._do_transfer)
        r4.addWidget(self.tf_btn)
        lay.addLayout(r4)
        return w

    def _build_gmail(self):
        w = QWidget(); lay = QVBoxLayout(w)
        lbl = QLabel("Gmail suggested transactions will appear here once Gmail sync is configured.")
        lbl.setStyleSheet(f"color:{C['text3']};font-size:13px;"); lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl); return w

    # ═══════════════════════════════════
    # SUB-TAB SWITCH (color shift)
    # ═══════════════════════════════════
    def _switch(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, b in enumerate(self._tab_btns):
            if i == idx:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background:{C['accent']};color:white;
                        border:1px solid {C['accent']};border-radius:8px;
                        padding:8px 16px;font-size:13px;font-weight:700;
                    }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background:{C['surface']};color:{C['text2']};
                        border:1px solid {C['border']};border-radius:8px;
                        padding:8px 16px;font-size:13px;font-weight:600;
                    }}
                """)
        self._load_recent("transfer" if idx == 1 else "regular")

    # ═══════════════════════════════════
    # TOGGLES
    # ═══════════════════════════════════
    def _toggle_dc(self):
        self._is_debit = not self._is_debit; self._update_dc()
    def _update_dc(self):
        self.dc_btn.setText("DEBIT" if self._is_debit else "CREDIT")
        self.dc_btn.setStyleSheet(_toggle_css(True, C['red'] if self._is_debit else C['green']))
    def _set_nw(self, idx):
        self._nw = idx; self._update_nw()
    def _update_nw(self):
        colors = [C['text3'], C['accent'], C['amber']]
        for i, b in enumerate(self.nw_btns):
            b.setStyleSheet(_toggle_css(i == self._nw, colors[i]))

    # ═══════════════════════════════════
    # FROM / TO EXCLUSION
    # ═══════════════════════════════════
    def _on_from_changed(self, idx): self._sync_exclusions(self.tf_from, self.tf_to)
    def _on_to_changed(self, idx): self._sync_exclusions(self.tf_to, self.tf_from)
    def _sync_exclusions(self, source, target):
        blocked = source.currentText()
        target.blockSignals(True); cur = target.currentText()
        target.clear_items()
        for name, aid in self._acct_list:
            if name != blocked: target.add_item(name, aid)
        idx = target.findText(cur)
        if idx >= 0: target.setCurrentIndex(idx)
        elif target.count() > 0: target.setCurrentIndex(0)
        target.blockSignals(False)

    def _swap(self):
        ft, tt = self.tf_from.currentText(), self.tf_to.currentText()
        self.tf_from.blockSignals(True); self.tf_to.blockSignals(True)
        self.tf_from.clear_items(); self.tf_to.clear_items()
        for name, aid in self._acct_list:
            self.tf_from.add_item(name, aid); self.tf_to.add_item(name, aid)
        fi = self.tf_from.findText(tt); ti = self.tf_to.findText(ft)
        if fi >= 0: self.tf_from.setCurrentIndex(fi)
        if ti >= 0: self.tf_to.setCurrentIndex(ti)
        self.tf_from.blockSignals(False); self.tf_to.blockSignals(False)
        self._sync_exclusions(self.tf_from, self.tf_to)

    # ═══════════════════════════════════
    # DATE → recent
    # ═══════════════════════════════════
    def _on_date(self, qdate): self._load_recent()

    def _load_recent(self, kind="regular"):
        from collections import OrderedDict
        from datetime import date as dt_cls
        qd = self.date_edit.date() if self.stack.currentIndex() == 0 else self.tf_date.date()
        d = qd.toPyDate()
        kw = {"date_from": (d - timedelta(days=7)).isoformat(),
              "date_to": (d + timedelta(days=7)).isoformat(), "limit": 50}
        if kind == "transfer": kw["kind"] = "TRANSFER"
        txns = self.tx_repo.list_filters(**kw)

        # Clear existing
        while self.recent_lay.count():
            itm = self.recent_lay.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()

        if txns:
            # Group by date (same as DB view)
            from ui.tabs.database_tab import _day_header
            by_date = OrderedDict()
            for tx in sorted(txns, key=lambda t: t["tx_date"], reverse=True):
                dk = tx["tx_date"]
                if dk not in by_date: by_date[dk] = []
                by_date[dk].append(tx)
            for dk, day_txns in by_date.items():
                try:
                    self.recent_lay.addWidget(_day_header(
                        dt_cls.fromisoformat(dk).strftime("%A, %d %b")))
                except:
                    self.recent_lay.addWidget(_day_header(dk))
                for tx in day_txns:
                    self.recent_lay.addWidget(_tx_card(tx))
        else:
            lbl = QLabel("No recent transactions.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.recent_lay.addWidget(lbl)
        self.recent_lay.addStretch()

    # ═══════════════════════════════════
    # STATUS LABEL (persistent — regular tab only)
    # ═══════════════════════════════════
    def _set_status(self, label, text, color):
        label.setText(text)
        label.setStyleSheet(f"color:{color};font-size:13px;font-weight:600;")
        label.show()

    # ═══════════════════════════════════
    # ADD TRANSACTION (regular — label only, no animation)
    # ═══════════════════════════════════
    def _add_tx(self):
        aid = self.ac_combo.get_data(); mid = self.method_combo.get_data(); cid = self.cat_combo.get_data()
        if not aid:
            self._set_status(self.status_label, "⚠ Select account", C['red']); return
        if not mid:
            self._set_status(self.status_label, "⚠ Select method", C['red']); return

        if not self.db.execute("SELECT 1 FROM payment_methods WHERE method_id=?", (mid,)).fetchone():
            self.db.execute("INSERT OR IGNORE INTO payment_methods(method_id,display_name,is_active,sort_order) VALUES(?,?,1,99)", (mid, mid))
            self.db.commit()
        if cid and not self.db.execute("SELECT 1 FROM categories WHERE category_id=?", (cid,)).fetchone():
            cid = None

        amount = self.amt.value()
        tx_type = "DEBIT" if self._is_debit else "CREDIT"
        pf = self._cat_pf.get(cid)

        self.tx_repo.create(
            tx_date=self.date_edit.date().toString("yyyy-MM-dd"),
            account_id=aid, pay_method=mid, tx_type=tx_type, amount=amount,
            person_org=self.person_edit.text() or None,
            description=self.desc_edit.text() or None,
            category=cid, neednwant=self._nw, pf_category=pf)

        # Persistent label (red for debit, green for credit) — no animation
        color = C['red'] if tx_type == "DEBIT" else C['green']
        self._set_status(self.status_label, f"✓ {tx_type} {fmt_money(amount)} added", color)

        self.amt.setValue(1); self.person_edit.clear(); self.desc_edit.clear()
        self._load_recent(); self._refresh_sidebar()
        QTimer.singleShot(50, self.amt.setFocus)

    # ═══════════════════════════════════
    # DO TRANSFER (Razorpay-style animation)
    # ═══════════════════════════════════
    def _do_transfer(self):
        # Guard: prevent double transfer (Enter key, rapid clicks)
        if getattr(self, '_transfer_in_progress', False):
            return
        self._transfer_in_progress = True
        self.tf_btn.setEnabled(False)
        self.tf_btn.setText("Transferring...")

        fid = self.tf_from.get_data(); tid = self.tf_to.get_data()
        mid = self.tf_method.get_data(); amount = self.tf_amt.value()
        if not fid or not tid:
            self._transfer_in_progress = False
            self.tf_btn.setEnabled(True)
            self.tf_btn.setText("💸  Transfer")
            self._set_status(self.tf_status, "⚠ Select both accounts", C['red']); return
        if not mid:
            self._set_status(self.tf_status, "⚠ Select payment method", C['red'])
            self._transfer_in_progress = False; self.tf_btn.setEnabled(True); self.tf_btn.setText("💸  Transfer"); return
        if fid == tid:
            self._set_status(self.tf_status, "⚠ Same account", C['red'])
            self._transfer_in_progress = False; self.tf_btn.setEnabled(True); self.tf_btn.setText("💸  Transfer"); return

        if not self.db.execute("SELECT 1 FROM payment_methods WHERE method_id=?", (mid,)).fetchone():
            self.db.execute("INSERT OR IGNORE INTO payment_methods(method_id,display_name,is_active,sort_order) VALUES(?,?,1,99)", (mid, mid))
            self.db.commit()

        from_name = self.tf_from.currentText()
        to_name = self.tf_to.currentText()
        gid = str(uuid.uuid4())
        d = self.tf_date.date().toString("yyyy-MM-dd")
        desc = self.tf_desc.text() or "Transfer"

        self.tx_repo.create(tx_date=d, account_id=fid, pay_method=mid, tx_type="DEBIT",
                            amount=amount, description=desc, transaction_kind="TRANSFER",
                            transfer_group_id=gid, category="transfer", pf_category="internal_transfer")
        self.tx_repo.create(tx_date=d, account_id=tid, pay_method=mid, tx_type="CREDIT",
                            amount=amount, description=desc, transaction_kind="TRANSFER",
                            transfer_group_id=gid, category="transfer", pf_category="internal_transfer")

        # Persistent status
        self._set_status(self.tf_status, f"✓ {fmt_money(amount)} transferred", C['green'])

        # Razorpay-style animation overlay
        card = RazorpaySuccessCard(from_name, to_name, amount, self.form_container)
        card.setGeometry(self.form_container.rect())
        card.show()
        card.raise_()
        self._overlay_card = card
        # Focus Done button after animation
        if hasattr(card, 'done_btn'):
            card.done_btn.setFocus()
        def _on_dismiss():
            # ALWAYS re-enable button, even if other operations fail
            self._transfer_in_progress = False
            self.tf_btn.setEnabled(True)
            self.tf_btn.setText("💸  Transfer")
            self._overlay_card = None
            try:
                self._load_recent("transfer")
                self._refresh_sidebar()
            except Exception as e:
                print(f"[WARN] Post-transfer refresh failed: {e}")
            self.tf_from.setFocus()
        card.dismissed.connect(_on_dismiss)

        self.tf_amt.setValue(1); self.tf_desc.clear()

    # ═══════════════════════════════════
    # KEYBOARD
    # ═══════════════════════════════════
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            fw = self.focusWidget()
            if fw == self.add_btn: self._add_tx(); return
            if fw == self.tf_btn and not getattr(self, '_overlay_card', None): self._do_transfer(); return
            if fw == self.dc_btn: self._toggle_dc(); return
            if fw in self.nw_btns: self._set_nw(self.nw_btns.index(fw)); return
            if fw == self.swap_btn: self._swap(); return
            # Done button on transfer animation overlay
            if hasattr(self, '_overlay_card') and self._overlay_card:
                if fw == self._overlay_card.done_btn:
                    self._overlay_card.done_btn.click(); return
        super().keyPressEvent(event)

    def focusNextPrevChild(self, next):
        if self.focusWidget() == self.add_btn and next:
            self.amt.setFocus(); return True
        return super().focusNextPrevChild(next)

    # ═══════════════════════════════════
    # REFRESH
    # ═══════════════════════════════════
    def refresh(self):
        self.ac_combo.clear_items(); self.method_combo.clear_items(); self.cat_combo.clear_items()
        self.tf_from.clear_items(); self.tf_to.clear_items(); self.tf_method.clear_items()
        self._acct_list = []
        for a in self.acct_repo.list_active():
            name, aid = a["display_name"], a["account_id"]
            atype = a.get("account_type", "")
            label = _acct_display(name, atype)
            self.ac_combo.add_item(label, aid)
            self.tf_from.add_item(label, aid); self.tf_to.add_item(label, aid)
            self._acct_list.append((label, aid))
        for m in self.lu.list_methods():
            mname = m["display_name"]
            self.method_combo.add_item(mname, mname); self.tf_method.add_item(mname, mname)
        self._cat_pf = {}
        for c in self.lu.list_categories():
            self.cat_combo.add_item(c["display_name"], c["category_id"])
            self._cat_pf[c["category_id"]] = c["default_pf_category"]
        self.cat_combo.currentIndexChanged.connect(self._update_pf)
        self._update_pf(); self._sync_exclusions(self.tf_from, self.tf_to); self._load_recent()

    def _update_pf(self):
        cid = self.cat_combo.get_data(); pf = self._cat_pf.get(cid)
        self.pf_label.setText(f"PF: {pf.replace('_', ' ').title() if pf else '—'}")

    def _refresh_sidebar(self):
        p = self.parent()
        while p:
            if hasattr(p, 'sidebar'): p.sidebar.update_nw(); return
            p = p.parent()
