"""Cards Tab — Professional credit card management with flip carousel."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame, QStackedWidget, QDialog,
                              QFormLayout, QLineEdit, QComboBox, QSpinBox,
                              QDoubleSpinBox, QMessageBox, QSizePolicy,
                              QGraphicsView, QGraphicsScene, QGraphicsObject,
                              QScrollArea)
from PyQt5.QtCore import (Qt, QRectF, QPointF, QTimer, QPropertyAnimation,
                           QEasingCurve, pyqtProperty, pyqtSignal, QSize)
from PyQt5.QtGui import (QPainter, QColor, QLinearGradient, QFont,
                          QPainterPath, QPen, QTransform)
from datetime import date, datetime, timedelta
from ui.theme import C
from ui.sidebar import fmt_money
import uuid, math

# ═══════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════

CARD_W = 320
CARD_H = 200
CARD_RADIUS = 16
GAP = 40
STRIPE_RECT = QRectF(-CARD_W / 2, -CARD_H / 2 + 20, CARD_W, 32)

EASE_FACTOR = 0.16
PX_PER_UNIT = CARD_W * 0.9
DRAG_THRESHOLD = 6

DEFAULT_GRADIENTS = [
    ("#3a3a3a", "#0f0f0f"),
    ("#1c3d5a", "#0a0f14"),
    ("#4b2e2e", "#120909"),
    ("#2e4b34", "#0a120c"),
    ("#3a2e4b", "#0f0a14"),
    ("#4b3a1a", "#120d05"),
    ("#1a3a3a", "#050f0f"),
    ("#4b1a3a", "#12050d"),
    ("#2a2a4b", "#08081b"),
    ("#4b3a2a", "#150f08"),
]


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


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


# ═══════════════════════════════════════════════
# CARD ITEM (QGraphicsObject — flip animation)
# ═══════════════════════════════════════════════

class CardItem(QGraphicsObject):
    """Single flip-able card in the carousel."""
    stripe_clicked = pyqtSignal(str)  # emits card_id

    def __init__(self, card_data, index):
        super().__init__()
        self.data = card_data
        self.index = index
        self.show_back = False
        self._flip_scale = 1.0
        self._anim = None
        self._stripe_hover = False
        self.setAcceptHoverEvents(True)

    def getFlipScale(self): return self._flip_scale
    def setFlipScale(self, value): self._flip_scale = value; self.update()
    flipScale = pyqtProperty(float, getFlipScale, setFlipScale)

    def boundingRect(self):
        return QRectF(-CARD_W / 2 - 2, -CARD_H / 2 - 2, CARD_W + 4, CARD_H + 4)

    def flip(self):
        if self._anim is not None and self._anim.state() == QPropertyAnimation.Running:
            return
        anim = QPropertyAnimation(self, b"flipScale")
        anim.setDuration(130)
        anim.setStartValue(1.0); anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.InQuad)
        anim.finished.connect(self._on_half_flip)
        self._anim = anim; anim.start()

    def _on_half_flip(self):
        self.show_back = not self.show_back
        anim = QPropertyAnimation(self, b"flipScale")
        anim.setDuration(130)
        anim.setStartValue(0.0); anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutQuad)
        self._anim = anim; anim.start()

    def hoverMoveEvent(self, event):
        hovering = self.show_back and STRIPE_RECT.contains(event.pos())
        if hovering != self._stripe_hover:
            self._stripe_hover = hovering
            self.setCursor(Qt.PointingHandCursor if hovering else Qt.ArrowCursor)
            self.update()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        if self._stripe_hover:
            self._stripe_hover = False
            self.setCursor(Qt.ArrowCursor); self.update()
        super().hoverLeaveEvent(event)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = CARD_W, CARD_H
        rect = QRectF(-w / 2, -h / 2, w, h)

        # Shadow
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 110))
        painter.drawRoundedRect(QRectF(-w / 2, -h / 2 + 8, w, h), CARD_RADIUS, CARD_RADIUS)
        painter.restore()

        # Gradient
        c1 = self.data.get("card_color_1", "#3a3a3a")
        c2 = self.data.get("card_color_2", "#0f0f0f")
        gradient = QLinearGradient(-w / 2, -h / 2, w / 2, h / 2)
        gradient.setColorAt(0, QColor(c1))
        gradient.setColorAt(1, QColor(c2))
        painter.setPen(Qt.NoPen); painter.setBrush(gradient)
        painter.drawRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)

        if not self.show_back:
            self._draw_front(painter)
        else:
            self._draw_back(painter)

        # Border
        pen = QPen(QColor(255, 255, 255, 40)); pen.setWidth(1)
        painter.setPen(pen); painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), CARD_RADIUS, CARD_RADIUS)

    def _draw_front(self, painter):
        w, h = CARD_W, CARD_H

        # Bank name
        painter.setPen(QColor(255, 255, 255, 235))
        bank_font = QFont("Arial", 12, QFont.Bold)
        bank_font.setLetterSpacing(QFont.AbsoluteSpacing, 0.6)
        painter.setFont(bank_font)
        painter.drawText(QRectF(-w / 2 + 20, -h / 2 + 14, w - 40, 20),
                         Qt.AlignLeft | Qt.AlignVCenter,
                         self.data.get("issuer_bank", "BANK"))

        # Card name / type
        painter.setPen(QColor(255, 255, 255, 170))
        brand_font = QFont("Arial", 9)
        painter.setFont(brand_font)
        painter.drawText(QRectF(-w / 2 + 20, -h / 2 + 32, w - 40, 16),
                         Qt.AlignLeft | Qt.AlignVCenter,
                         self.data.get("card_type", "PERSONAL"))

        # Chip
        chip_rect = QRectF(-w / 2 + 24, -13, 34, 26)
        chip_gradient = QLinearGradient(chip_rect.topLeft(), chip_rect.bottomLeft())
        chip_gradient.setColorAt(0, QColor("#f2f2f2"))
        chip_gradient.setColorAt(1, QColor("#999999"))
        painter.setPen(Qt.NoPen); painter.setBrush(chip_gradient)
        painter.drawRoundedRect(chip_rect, 4, 4)
        painter.setPen(QPen(QColor("#777777"), 1))
        for i in range(1, 3):
            x = chip_rect.left() + chip_rect.width() * i / 3
            painter.drawLine(QPointF(x, chip_rect.top()), QPointF(x, chip_rect.bottom()))
        painter.drawLine(QPointF(chip_rect.left(), chip_rect.center().y()),
                         QPointF(chip_rect.right(), chip_rect.center().y()))

        # Network
        painter.setPen(QColor(255, 255, 255, 235))
        type_font = QFont("Arial", 13, QFont.Bold)
        type_font.setItalic(True)
        type_font.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
        painter.setFont(type_font)
        painter.drawText(QRectF(-w / 2, h / 2 - 34, w - 20, 24),
                         Qt.AlignRight | Qt.AlignVCenter,
                         self.data.get("card_network", "VISA"))

    def _draw_back(self, painter):
        w, h = CARD_W, CARD_H

        # Stripe (clickable)
        stripe_color = QColor(35, 35, 35, 235) if self._stripe_hover else QColor(0, 0, 0, 220)
        painter.setPen(Qt.NoPen); painter.setBrush(stripe_color)
        painter.drawRect(STRIPE_RECT)
        painter.setPen(QColor(255, 255, 255, 220 if self._stripe_hover else 150))
        btn_font = QFont("Arial", 9, QFont.DemiBold)
        painter.setFont(btn_font)
        painter.drawText(STRIPE_RECT, Qt.AlignCenter,
                         "VIEW CARD DETAILS  \u2192" if self._stripe_hover else "VIEW CARD DETAILS")

        # Card number
        mono = QFont("Courier New", 11, QFont.DemiBold)
        painter.setFont(mono); painter.setPen(QColor(255, 255, 255, 235))
        last4 = self.data.get("last_four", "0000")
        painter.drawText(QRectF(-w / 2 + 20, h / 2 - 56, w - 40, 20),
                         Qt.AlignLeft | Qt.AlignVCenter,
                         f"••••  ••••  ••••  {last4}")

        # Name + expiry
        mono_small = QFont("Courier New", 8)
        painter.setFont(mono_small); painter.setPen(QColor(255, 255, 255, 170))
        name = self.data.get("cardholder_name", "CARDHOLDER")
        em = self.data.get("expiry_month", 12)
        ey = self.data.get("expiry_year", 2028)
        info = f"{name}    EXP: {em:02d}/{str(ey)[-2:]}"
        painter.drawText(QRectF(-w / 2 + 20, h / 2 - 34, w - 40, 20),
                         Qt.AlignLeft | Qt.AlignVCenter, info)


# ═══════════════════════════════════════════════
# CAROUSEL VIEW
# ═══════════════════════════════════════════════

class CarouselView(QGraphicsView):
    """Horizontal carousel with flip cards, drag, wheel, keyboard."""
    card_selected = pyqtSignal(str)  # emits card_id when stripe clicked

    def __init__(self, cards_data, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setStyleSheet("background-color: #111827; border: none; border-radius: 16px;")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)

        self.scene = QGraphicsScene(self)
        self.scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.setScene(self.scene)

        self.card_count = len(cards_data)
        self.items = []
        for i, data in enumerate(cards_data):
            item = CardItem(data, i)
            item.stripe_clicked.connect(self.card_selected.emit)
            self.scene.addItem(item)
            self.items.append(item)

        self.progress = 0.0
        self.target_progress = 0.0
        self._dragging = False
        self._press_pos = None
        self._press_item = None
        self._drag_start_progress = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(16)

    def load_cards(self, cards_data):
        """Reload cards."""
        for item in self.items:
            self.scene.removeItem(item)
        self.items.clear()
        self.card_count = len(cards_data)
        self.progress = 0.0; self.target_progress = 0.0
        for i, data in enumerate(cards_data):
            item = CardItem(data, i)
            item.stripe_clicked.connect(self.card_selected.emit)
            self.scene.addItem(item)
            self.items.append(item)

    def _on_tick(self):
        self.progress += (self.target_progress - self.progress) * EASE_FACTOR
        cx = self.viewport().width() / 2
        cy = self.viewport().height() / 2

        for item in self.items:
            offset = item.index - self.progress
            half = self.card_count / 2
            while offset > half: offset -= self.card_count
            while offset < -half: offset += self.card_count
            abs_off = abs(offset)
            sign = 1 if offset > 0 else (-1 if offset < 0 else 0)

            if abs_off > 3.2:
                item.setVisible(False); continue
            item.setVisible(True)

            if abs_off <= 1:
                t = smoothstep(abs_off)
                x = sign * t * (CARD_W * 0.62 + GAP)
                scale = 1 - t * 0.30; opacity = 1.0; z = 100 - t * 40
            elif abs_off <= 2:
                t = smoothstep(abs_off - 1)
                x = sign * ((CARD_W * 0.62 + GAP) + t * (CARD_W * 0.5))
                scale = 0.70 - t * 0.20; opacity = 1.0 - t * 0.4; z = 60 - t * 40
            else:
                t = smoothstep(min(abs_off - 2, 1))
                x = sign * ((CARD_W * 0.62 + GAP + CARD_W * 0.5) + t * (CARD_W * 0.6))
                scale = max(0.2, 0.50 - t * 0.3); opacity = max(0.0, 0.6 - t * 0.6); z = 20 - t * 20

            transform = QTransform()
            transform.translate(cx + x, cy)
            transform.scale(scale * item.flipScale, scale)
            item.setTransform(transform)
            item.setZValue(z); item.setOpacity(opacity); item.update()

        self.viewport().update()

    def mousePressEvent(self, event):
        self._press_pos = event.pos()
        self._press_item = self.itemAt(event.pos())
        self._dragging = False
        self._drag_start_progress = self.target_progress
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._press_pos is not None:
            dx = event.pos().x() - self._press_pos.x()
            if abs(dx) > DRAG_THRESHOLD: self._dragging = True
            if self._dragging:
                self.target_progress = self._drag_start_progress - dx / PX_PER_UNIT
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self.target_progress = round(self.target_progress)
        else:
            item = self._press_item
            if isinstance(item, CardItem):
                local_pos = item.mapFromScene(self.mapToScene(event.pos()))
                if item.show_back and STRIPE_RECT.contains(local_pos):
                    self.card_selected.emit(item.data.get("card_id", ""))
                else:
                    item.flip()
        self._dragging = False; self._press_pos = None; self._press_item = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        self.target_progress -= event.angleDelta().y() / 240.0
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.target_progress = round(self.target_progress) - 1
        elif event.key() == Qt.Key_Right:
            self.target_progress = round(self.target_progress) + 1
        elif event.key() == Qt.Key_Space:
            nearest = min(self.items, key=lambda it: abs(
                ((it.index - self.progress + self.card_count / 2) % self.card_count) - self.card_count / 2))
            nearest.flip()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        self.scene.setSceneRect(0, 0, self.viewport().width(), self.viewport().height())
        super().resizeEvent(event)


# ═══════════════════════════════════════════════
# ADD CARD DIALOG
# ═══════════════════════════════════════════════

class AddCardDialog(QDialog):
    card_added = pyqtSignal()

    def __init__(self, cards_repo, accounts_repo, parent=None):
        super().__init__(parent)
        self.cr = cards_repo; self.acct = accounts_repo
        self.setWindowTitle("Add Credit Card")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(24, 24, 24, 24); lay.setSpacing(14)
        hdr = QLabel("💳  Add New Credit Card")
        hdr.setStyleSheet("font-size:20px;font-weight:800;color:#111827;")
        lay.addWidget(hdr)

        form = QFormLayout(); form.setSpacing(10); form.setLabelAlignment(Qt.AlignRight)

        self.card_name = QLineEdit(); self.card_name.setPlaceholderText("e.g. HDFC Regalia")
        form.addRow("Card Name *", self.card_name)

        self.last_four = QLineEdit(); self.last_four.setMaxLength(4)
        self.last_four.setPlaceholderText("Last 4 digits")
        form.addRow("Last 4 Digits", self.last_four)

        self.network = QComboBox()
        self.network.addItems(["VISA", "MASTERCARD", "RUPAY", "AMEX", "DINERS"])
        form.addRow("Network", self.network)

        self.card_type = QComboBox()
        self.card_type.addItems(["PERSONAL", "BUSINESS", "CORPORATE", "PREPAID"])
        form.addRow("Card Type", self.card_type)

        self.issuer = QLineEdit(); self.issuer.setPlaceholderText("e.g. HDFC Bank")
        form.addRow("Issuer Bank", self.issuer)

        self.cardholder = QLineEdit(); self.cardholder.setPlaceholderText("Name as on card")
        form.addRow("Cardholder Name", self.cardholder)

        self.credit_limit = QDoubleSpinBox()
        self.credit_limit.setRange(0, 99999999); self.credit_limit.setPrefix("₹ ")
        self.credit_limit.setDecimals(0)
        form.addRow("Credit Limit *", self.credit_limit)

        exp_row = QHBoxLayout()
        self.expiry_month = QSpinBox(); self.expiry_month.setRange(1, 12); self.expiry_month.setValue(12)
        self.expiry_year = QSpinBox(); self.expiry_year.setRange(2024, 2040); self.expiry_year.setValue(2028)
        exp_row.addWidget(self.expiry_month); exp_row.addWidget(QLabel("/"))
        exp_row.addWidget(self.expiry_year); exp_row.addStretch()
        form.addRow("Expiry", exp_row)

        self.billing_day = QSpinBox(); self.billing_day.setRange(1, 28); self.billing_day.setValue(1)
        form.addRow("Billing Day", self.billing_day)

        self.grace_days = QSpinBox(); self.grace_days.setRange(0, 55); self.grace_days.setValue(20)
        form.addRow("Grace Period", self.grace_days)

        self.annual_fee = QDoubleSpinBox()
        self.annual_fee.setRange(0, 99999); self.annual_fee.setPrefix("₹ "); self.annual_fee.setDecimals(0)
        form.addRow("Annual Fee", self.annual_fee)

        self.interest_rate = QDoubleSpinBox()
        self.interest_rate.setRange(0, 100); self.interest_rate.setSuffix(" %")
        self.interest_rate.setDecimals(1); self.interest_rate.setValue(3.5)
        form.addRow("Interest (p.m.)", self.interest_rate)

        self.reward = QLineEdit()
        self.reward.setPlaceholderText("e.g. 2% cashback")
        form.addRow("Rewards", self.reward)

        self.color_idx = QComboBox()
        for i in range(len(DEFAULT_GRADIENTS)):
            self.color_idx.addItem(f"Style {i + 1}")
        form.addRow("Card Style", self.color_idx)

        lay.addLayout(form)

        btn_row = QHBoxLayout(); btn_row.addStretch()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        add_btn = QPushButton("  Add Card  "); add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._save); btn_row.addWidget(add_btn)
        lay.addLayout(btn_row)

    def _save(self):
        name = self.card_name.text().strip()
        limit = self.credit_limit.value()
        if not name or limit <= 0:
            QMessageBox.warning(self, "Missing", "Card name and credit limit required."); return

        # Check if account already exists with this name
        existing_acct = None
        for a in self.acct.list_active():
            if a["display_name"].upper() == name.upper():
                existing_acct = a; break

        if existing_acct:
            acct_id = existing_acct["account_id"]
            # Update credit limit if it changed
            if existing_acct.get("credit_limit", 0) != limit:
                self.acct.update(acct_id, credit_limit=limit)
        else:
            acct_id = str(uuid.uuid4())
            self.acct.create(account_id=acct_id, display_name=name,
                             short_label=name[:8].upper(), account_type="CREDIT_CARD",
                             credit_limit=limit, opening_balance=0, color_hex="#7C3AED")

        c1, c2 = DEFAULT_GRADIENTS[self.color_idx.currentIndex()]
        self.cr.create(
            account_id=acct_id, last_four=self.last_four.text().strip() or "0000",
            card_network=self.network.currentText(), card_type=self.card_type.currentText(),
            issuer_bank=self.issuer.text().strip() or "Bank",
            cardholder_name=self.cardholder.text().strip() or name.upper(),
            expiry_month=self.expiry_month.value(), expiry_year=self.expiry_year.value(),
            billing_day=self.billing_day.value(), grace_days=self.grace_days.value(),
            annual_fee=self.annual_fee.value(), interest_rate=self.interest_rate.value(),
            reward_program=self.reward.text().strip(), card_color_1=c1, card_color_2=c2)

        self.card_added.emit(); self.accept()


# ═══════════════════════════════════════════════
# CARD DETAILS DIALOG (on stripe click)
# ═══════════════════════════════════════════════

def _info_row(label, value, color=None):
    row = QHBoxLayout(); row.setSpacing(8)
    ll = QLabel(label); ll.setStyleSheet(f"color:{C['text3']};font-size:12px;"); ll.setFixedWidth(120)
    row.addWidget(ll)
    vl = QLabel(str(value)); vl.setStyleSheet(f"color:{color or C['text']};font-size:13px;font-weight:600;")
    row.addWidget(vl, 1)
    return row


class CardDetailsDialog(QDialog):
    """Full card details with settlement option."""
    settled = pyqtSignal()

    def __init__(self, card, cards_repo, tx_repo, accounts_repo, parent=None):
        super().__init__(parent)
        self.card = card; self.cr = cards_repo; self.tx_repo = tx_repo; self.acct = accounts_repo
        self.setWindowTitle(f"Card — {card.get('acct_name', 'Details')}")
        self.setMinimumWidth(440)
        self.setStyleSheet(f"QDialog{{background:{C['bg']};}}")
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(24, 24, 24, 24); lay.setSpacing(12)

        hdr = QLabel(f"💳  {self.card.get('acct_name', 'Card')}")
        hdr.setStyleSheet("font-size:18px;font-weight:800;color:#111827;")
        lay.addWidget(hdr)

        frame = QFrame()
        frame.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;padding:16px;")
        fl = QVBoxLayout(frame); fl.setSpacing(6)

        fl.addWidget(QLabel("<b>Card Information</b>"))
        fl.addLayout(_info_row("Network", self.card.get("card_network", "—")))
        fl.addLayout(_info_row("Issuer", self.card.get("issuer_bank", "—")))
        fl.addLayout(_info_row("Cardholder", self.card.get("cardholder_name", "—")))
        fl.addLayout(_info_row("Last 4 Digits", f"•••• {self.card.get('last_four', '0000')}"))
        em = self.card.get("expiry_month", 0); ey = self.card.get("expiry_year", 0)
        fl.addLayout(_info_row("Expiry", f"{em:02d}/{ey}"))
        fl.addLayout(_info_row("Card Type", self.card.get("card_type", "—")))
        fl.addLayout(_info_row("Billing Day", f"Every {self.card.get('billing_day', 1)}th"))
        fl.addLayout(_info_row("Grace Period", f"{self.card.get('grace_days', 20)} days"))
        fl.addLayout(_info_row("Annual Fee", fmt_money(self.card.get("annual_fee", 0))))
        fl.addLayout(_info_row("Interest", f"{self.card.get('interest_rate', 3.5)}% p.m."))
        reward = self.card.get("reward_program") or "—"
        fl.addLayout(_info_row("Rewards", reward))

        # Credit limit
        limit = self.card.get("credit_limit", 0) or self.card.get("acct_limit", 0)
        fl.addLayout(_info_row("Credit Limit", fmt_money(limit), "#4F46E5"))

        lay.addWidget(frame)

        # Latest cycle
        cycle = self.cr.latest_cycle(self.card["account_id"])
        if cycle:
            cf = QFrame()
            cf.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;padding:16px;")
            cl = QVBoxLayout(cf); cl.setSpacing(6)
            cl.addWidget(QLabel("<b>Current Statement</b>"))
            cl.addLayout(_info_row("Statement Date", cycle.get("statement_date", "—")))
            cl.addLayout(_info_row("Due Date", cycle.get("due_date", "—"), "#EF4444"))
            cl.addLayout(_info_row("Total Due", fmt_money(cycle.get("total_due", 0)), "#EF4444"))
            cl.addLayout(_info_row("Minimum Due", fmt_money(cycle.get("minimum_due", 0)), "#F59E0B"))
            lay.addWidget(cf)

        # Buttons
        btn_row = QHBoxLayout(); btn_row.addStretch()
        settle_btn = QPushButton("💰  Settle Bill"); settle_btn.setObjectName("primary")
        settle_btn.setMinimumHeight(38); settle_btn.clicked.connect(self._settle)
        btn_row.addWidget(settle_btn)
        close_btn = QPushButton("Close"); close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

    def _settle(self):
        amt, ok = QDoubleSpinBox(self), None
        amt.setRange(0, 99999999); amt.setPrefix("₹ "); amt.setDecimals(0)
        cycle = self.cr.latest_cycle(self.card["account_id"])
        if cycle: amt.setValue(cycle.get("total_due", 0))

        msg = QMessageBox(self); msg.setWindowTitle("Settle Bill")
        msg.setText("Enter payment amount:")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        # Use a simple input
        from PyQt5.QtWidgets import QInputDialog
        val, ok = QInputDialog.getDouble(self, "Settle Bill", "Payment Amount:",
                                          amt.value(), 0, 99999999, 0)
        if not ok or val <= 0: return

        today = date.today().isoformat()
        self.tx_repo.create(tx_date=today, account_id=self.card["account_id"],
                            pay_method="NETBANKING", tx_type="CREDIT", amount=val,
                            description="Bill settlement", transaction_kind="REGULAR",
                            category="transfer")
        self.settled.emit()
        QMessageBox.information(self, "Done", f"Settlement of {fmt_money(val)} recorded.")
        self.accept()


# ═══════════════════════════════════════════════
# REMINDERS WIDGET
# ═══════════════════════════════════════════════

class RemindersWidget(QWidget):
    """Shows upcoming due dates, billing cycles, fee reminders."""

    def __init__(self, cards_repo, parent=None):
        super().__init__(parent)
        self.cr = cards_repo
        self.setStyleSheet("background:transparent;")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(8)

    def load_reminders(self, cards):
        # Clear
        while self.lay.count():
            itm = self.lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()

        title = QLabel("⏰  Reminders & Due Dates")
        title.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:700;")
        self.lay.addWidget(title)

        today = date.today()
        reminders = []

        for card in cards:
            acct_id = card["account_id"]
            cycle = self.cr.latest_cycle(acct_id)
            name = card.get("acct_name", card.get("issuer_bank", "Card"))
            billing_day = card.get("billing_day", 1)

            # Next billing date
            try:
                next_bill = today.replace(day=min(billing_day, 28))
                if next_bill <= today:
                    if today.month == 12:
                        next_bill = next_bill.replace(year=today.year + 1, month=1)
                    else:
                        next_bill = next_bill.replace(month=today.month + 1)
                days_until = (next_bill - today).days
                reminders.append((days_until, f"📅 {name} — Statement on {next_bill.strftime('%d %b')}",
                                  "#4F46E5" if days_until > 5 else "#F59E0B"))
            except:
                pass

            # Due date from cycle
            if cycle and cycle.get("due_date"):
                try:
                    due = date.fromisoformat(cycle["due_date"])
                    days_due = (due - today).days
                    total = cycle.get("total_due", 0)
                    if days_due >= 0:
                        color = "#EF4444" if days_due <= 3 else ("#F59E0B" if days_due <= 7 else "#10B981")
                        reminders.append((days_due,
                            f"💰 {name} — Due {due.strftime('%d %b')} ({fmt_money(total)})", color))
                    else:
                        reminders.append((-1, f"🚨 {name} — OVERDUE by {abs(days_due)} days ({fmt_money(total)})", "#EF4444"))
                except:
                    pass

            # Annual fee
            fee = card.get("annual_fee", 0)
            if fee > 0:
                em = card.get("expiry_month", 0)
                try:
                    fee_date = today.replace(month=em, day=1)
                    if fee_date < today:
                        fee_date = fee_date.replace(year=today.year + 1)
                    days_fee = (fee_date - today).days
                    if days_fee <= 30:
                        reminders.append((days_fee,
                            f"🏷 {name} — Annual fee {fmt_money(fee)} on {fee_date.strftime('%d %b')}", "#8B5CF6"))
                except:
                    pass

        reminders.sort(key=lambda r: r[0])

        if not reminders:
            lbl = QLabel("No upcoming reminders.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            self.lay.addWidget(lbl)
        else:
            for _, text, color in reminders[:10]:
                row = QFrame()
                row.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border2']};border-radius:8px;padding:8px 12px;")
                rl = QHBoxLayout(row); rl.setContentsMargins(8, 6, 8, 6)
                dot = QLabel("●"); dot.setStyleSheet(f"color:{color};font-size:8px;"); dot.setFixedWidth(12)
                rl.addWidget(dot)
                lbl = QLabel(text); lbl.setStyleSheet(f"color:{C['text']};font-size:12px;")
                rl.addWidget(lbl, 1)
                self.lay.addWidget(row)

        self.lay.addStretch()


# ═══════════════════════════════════════════════
# MAIN CARDS TAB
# ═══════════════════════════════════════════════

class CardsTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db; self.cr = repos["cards"]; self.acct = repos["accounts"]
        self.tx_repo = repos["transactions"]; self.bal = services["balance"]
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(28, 16, 28, 16); root.setSpacing(10)

        # Header
        hdr_row = QHBoxLayout(); hdr_row.setSpacing(12)
        h = QLabel("💳  Credit Cards"); h.setStyleSheet("font-size:24px;font-weight:800;color:#111827;")
        hdr_row.addWidget(h); hdr_row.addStretch()
        add_btn = QPushButton("＋  Add Card"); add_btn.setObjectName("primary")
        add_btn.setMinimumHeight(38); add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._add_card); hdr_row.addWidget(add_btn)
        root.addLayout(hdr_row)

        # Sub-tab switch: Active / Inactive
        tabs_row = QHBoxLayout(); tabs_row.setSpacing(8)
        self.tab_active = QPushButton("✅  Active Cards")
        self.tab_inactive = QPushButton("⏸  Inactive Cards")
        self._sub_btns = [self.tab_active, self.tab_inactive]
        for b in self._sub_btns:
            b.setMinimumHeight(34); b.setCursor(Qt.PointingHandCursor)
        self.tab_active.clicked.connect(lambda: self._switch_sub(0))
        self.tab_inactive.clicked.connect(lambda: self._switch_sub(1))
        for b in self._sub_btns: tabs_row.addWidget(b)
        tabs_row.addStretch(); root.addLayout(tabs_row)

        # Content stack (Active / Inactive)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_sub_tab(True))   # 0 = active
        self.stack.addWidget(self._build_sub_tab(False))  # 1 = inactive
        root.addWidget(self.stack, 1)

        self._switch_sub(0)

    def _build_sub_tab(self, is_active):
        """Each sub-tab: carousel (top) + reminders (bottom)."""
        w = QWidget()
        lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(10)

        # Carousel
        carousel = CarouselView([])
        carousel.setMinimumHeight(240); carousel.setMaximumHeight(280)
        carousel.card_selected.connect(self._show_details)
        lay.addWidget(carousel)

        # Reminders
        reminders = RemindersWidget(self.cr)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        scroll.setWidget(reminders)
        lay.addWidget(scroll, 1)

        if is_active:
            self._active_carousel = carousel
            self._active_reminders = reminders
        else:
            self._inactive_carousel = carousel
            self._inactive_reminders = reminders

        return w

    def _switch_sub(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, b in enumerate(self._sub_btns):
            b.setStyleSheet(_tab_btn_active() if i == idx else _tab_btn_inactive())
        self._load_cards()

    def _load_cards(self):
        all_cards = self.cr.list_active()  # active cards
        # For inactive, we need a separate query — for now use all with is_active=0
        inactive_cards = [dict(r) for r in self.db.execute(
            "SELECT c.*, a.display_name AS acct_name, a.credit_limit AS acct_limit "
            "FROM cards c JOIN accounts a ON a.account_id=c.account_id "
            "WHERE c.is_active=0 ORDER BY c.sort_order").fetchall()]

        idx = self.stack.currentIndex()
        if idx == 0:
            self._active_carousel.load_cards(all_cards)
            self._active_reminders.load_reminders(all_cards)
        else:
            self._inactive_carousel.load_cards(inactive_cards)
            self._inactive_reminders.load_reminders(inactive_cards)

    def _add_card(self):
        dlg = AddCardDialog(self.cr, self.acct, self)
        dlg.card_added.connect(self.refresh)
        dlg.exec_()

    def _show_details(self, card_id):
        card = self.cr.get(card_id)
        if not card: return
        dlg = CardDetailsDialog(card, self.cr, self.tx_repo, self.acct, self)
        dlg.settled.connect(self._load_cards)
        dlg.exec_()

    def refresh(self):
        self._load_cards()
