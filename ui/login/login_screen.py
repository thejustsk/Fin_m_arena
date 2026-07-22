"""Login screen — TOTP only. 2FA is mandatory."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QPushButton, QFrame)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtGui import (QPainter, QColor, QRadialGradient, QLinearGradient,
                          QPen, QPainterPath, QCursor)
from ui.theme import C
from ui.widgets.metric_card import add_shadow

INPUT_STYLE = """
    QLineEdit {
        background: rgba(255,255,255,0.07);
        border: none;
        border-bottom: 2px solid rgba(255,255,255,0.2);
        border-radius: 0px;
        padding: 12px 4px;
        font-size: 15px;
        font-weight: 500;
        color: #FFFFFF;
    }
    QLineEdit:focus {
        border-bottom: 2px solid #818CF8;
        background: rgba(255,255,255,0.10);
    }
"""
BTN_UNLOCK = """
    QPushButton {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #4F46E5, stop:1 #7C3AED);
        color: #FFFFFF; border: none; border-radius: 10px;
        padding: 14px; font-size: 16px; font-weight: 700;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #4338CA, stop:1 #6D28D9);
    }
    QPushButton:pressed { background: #3730A3; }
"""


class LoginScreen(QWidget):
    success = pyqtSignal()

    def __init__(self, sec_svc, parent=None):
        super().__init__(parent)
        self.sec = sec_svc
        self.lamp_on = False
        self._build()

    def _build(self):
        self.setWindowTitle("Finance Manager — Login")
        self.setMinimumSize(520, 580)
        self.setStyleSheet("background: #0B1120;")

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        self.card = QFrame()
        self.card.setFixedSize(460, 520)
        self.card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:0.3,y2:1,
                    stop:0 #1E293B, stop:1 #0F172A);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 24px;
            }
        """)
        add_shadow(self.card, blur=48, y_offset=12)

        cl = QHBoxLayout(self.card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # Lamp
        self.lamp_widget = QWidget(self.card)
        self.lamp_widget.setFixedWidth(130)
        self.lamp_widget.setFixedHeight(520)
        self.lamp_widget.move(0, 0)
        self.lamp_widget.setStyleSheet("background: transparent;")
        self.lamp_widget.paintEvent = self._paint_lamp_and_cord
        self.lamp_widget.setCursor(QCursor(Qt.PointingHandCursor))
        self.lamp_widget.mousePressEvent = lambda e: self._toggle()
        self.lamp_widget.raise_()

        # Form
        self.form = QWidget(self.card)
        self.form.setGeometry(130, 0, 330, 520)
        self.form.setStyleSheet("background: transparent;")
        fl = QVBoxLayout(self.form)
        fl.setContentsMargins(24, 44, 28, 44)
        fl.setSpacing(18)

        title = QLabel("Finance Manager")
        title.setStyleSheet("font-size: 24px; font-weight: 800; color: #F1F5F9; border: none;")
        fl.addWidget(title)

        self.sub = QLabel("Pull the cord to log in")
        self.sub.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 13px; border: none;")
        fl.addWidget(self.sub)

        fl.addSpacing(12)

        # Password input (shown when 2FA is off)
        self.pw_input = QLineEdit()
        self.pw_input.setPlaceholderText("Password")
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.pw_input.setMinimumHeight(48)
        self.pw_input.setStyleSheet(INPUT_STYLE)
        self.pw_input.returnPressed.connect(self._try)
        fl.addWidget(self.pw_input)

        # TOTP input (shown when 2FA is on)
        self.totp = QLineEdit()
        self.totp.setPlaceholderText("6-digit code")
        self.totp.setMaxLength(6)
        self.totp.setMinimumHeight(48)
        self.totp.setStyleSheet(INPUT_STYLE)
        self.totp.returnPressed.connect(self._try)
        fl.addWidget(self.totp)

        self.err = QLabel("")
        self.err.setStyleSheet("color: #EF4444; font-size: 13px; font-weight: 600; border: none;")
        self.err.setAlignment(Qt.AlignCenter)
        fl.addWidget(self.err)

        fl.addSpacing(4)

        self.unlock_btn = QPushButton("🔓  Unlock")
        self.unlock_btn.setStyleSheet(BTN_UNLOCK)
        self.unlock_btn.setMinimumHeight(50)
        self.unlock_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.unlock_btn.clicked.connect(self._try)
        fl.addWidget(self.unlock_btn)

        fl.addStretch()
        self.form.hide()
        outer.addWidget(self.card)

        if self.sec.is_setup():
            QTimer.singleShot(500, self._toggle)

    # ══════════════════════════════════════════════
    # LAMP PAINTING
    # ══════════════════════════════════════════════
    def _paint_lamp_and_cord(self, event):
        p = QPainter(self.lamp_widget)
        p.setRenderHint(QPainter.Antialiasing)
        cx = self.lamp_widget.width() // 2

        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#334155"))
        p.drawRoundedRect(cx - 16, 28, 32, 10, 4, 4)

        p.setPen(QPen(QColor("#475569"), 3))
        p.drawLine(cx, 38, cx, 65)

        p.setPen(QPen(QColor("#64748B"), 2))
        p.setBrush(QColor("#475569"))
        p.drawEllipse(cx - 20, 58, 40, 18)

        if self.lamp_on:
            glow = QRadialGradient(cx, 92, 55)
            glow.setColorAt(0, QColor(255, 240, 150, 200))
            glow.setColorAt(0.4, QColor(255, 220, 100, 100))
            glow.setColorAt(0.7, QColor(255, 200, 50, 30))
            glow.setColorAt(1, QColor(255, 200, 50, 0))
            p.setBrush(glow)
            p.setPen(Qt.NoPen)
            p.drawEllipse(cx - 50, 48, 100, 100)
            bulb_grad = QRadialGradient(cx, 88, 18)
            bulb_grad.setColorAt(0, QColor("#FFFDE7"))
            bulb_grad.setColorAt(1, QColor("#FFD54F"))
            p.setBrush(bulb_grad)
            p.setPen(QPen(QColor("#FFC107"), 1.5))
        else:
            p.setBrush(QColor("#374151"))
            p.setPen(QPen(QColor("#4B5563"), 1.5))

        path = QPainterPath()
        path.moveTo(cx - 12, 80)
        path.quadTo(cx - 16, 68, cx - 7, 68)
        path.lineTo(cx + 7, 68)
        path.quadTo(cx + 16, 68, cx + 12, 80)
        path.lineTo(cx + 10, 98)
        path.quadTo(cx + 10, 110, cx, 110)
        path.quadTo(cx - 10, 110, cx - 10, 98)
        path.closeSubpath()
        p.drawPath(path)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E0E0E0") if self.lamp_on else QColor("#9CA3AF"))
        p.drawRoundedRect(cx - 7, 98, 14, 9, 3, 3)

        cord_start_y = 107
        cord_knob_y = 185
        knob_h = 22
        p.setPen(QPen(QColor("#64748B"), 2))
        p.drawLine(cx, cord_start_y, cx, cord_knob_y)

        knob_grad = QRadialGradient(cx, cord_knob_y + knob_h // 2, knob_h // 2)
        if self.lamp_on:
            knob_grad.setColorAt(0, QColor("#FFD54F"))
            knob_grad.setColorAt(1, QColor("#FF8F00"))
        else:
            knob_grad.setColorAt(0, QColor("#9CA3AF"))
            knob_grad.setColorAt(1, QColor("#6B7280"))
        p.setBrush(knob_grad)
        p.setPen(QPen(QColor("#4B5563"), 1))
        p.drawEllipse(cx - 9, cord_knob_y, 18, knob_h)

        p.setPen(QPen(QColor("#64748B"), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(cx - 4, cord_knob_y - 4, 8, 6)
        p.end()

    # ══════════════════════════════════════════════
    # TOGGLE LAMP
    # ══════════════════════════════════════════════
    def _toggle(self):
        self.lamp_on = not self.lamp_on
        self.lamp_widget.update()
        self.form.setVisible(self.lamp_on)
        if self.lamp_on:
            is_2fa = self.sec.is_2fa()
            self.pw_input.setVisible(not is_2fa)
            self.totp.setVisible(is_2fa)
            if is_2fa:
                self.sub.setText("Enter your 2FA code")
                self.totp.setFocus()
            else:
                self.sub.setText("Enter your password")
                self.pw_input.setFocus()
        else:
            self.sub.setText("Pull the cord to log in")
            self.err.setText("")
            self.totp.clear()
            self.pw_input.clear()

    # ══════════════════════════════════════════════
    # AUTHENTICATION — TOTP only
    # ══════════════════════════════════════════════
    def _try(self):
        self.err.setText("")
        if self.sec.is_2fa():
            code = self.totp.text().strip()
            if not code:
                self.err.setText("Enter the 6-digit code")
                self.totp.setFocus()
                return
            if not self.sec.verify_totp(code):
                self.err.setText("Invalid 2FA code")
                self.totp.clear()
                self.totp.setFocus()
                return
        else:
            pw = self.pw_input.text().strip()
            if not pw:
                self.err.setText("Enter your password")
                self.pw_input.setFocus()
                return
            if not self.sec.verify(pw):
                self.err.setText("Invalid password")
                self.pw_input.clear()
                self.pw_input.setFocus()
                return
        self.success.emit()
