"""Gmail tab — Coming Soon with falling email animation."""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import QPainter, QColor, QCursor
from ui.theme import C
import random


class _FallingEmail(QWidget):
    """Animated email icon that falls from top and fades out, looping forever."""

    def __init__(self, emoji, parent=None):
        super().__init__(parent)
        self._emoji = emoji
        self._opacity = 1.0
        self.setFixedSize(40, 40)

    def getOpacity(self):
        return self._opacity

    def setOpacity(self, v):
        self._opacity = v
        self.update()

    op = pyqtProperty(float, getOpacity, setOpacity)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setOpacity(self._opacity)
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignCenter, self._emoji)
        p.end()


class GmailTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self._emails = []
        self._build()

    def _build(self):
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 24, 40, 24)
        lay.setSpacing(16)

        # Header
        hdr = QLabel("\U0001f4e7  Gmail Sync")
        hdr.setStyleSheet(f"font-size:24px;font-weight:800;color:{C['text']};background:transparent;border:none;")
        lay.addWidget(hdr)

        # Main card
        card = QFrame()
        card.setStyleSheet(
            f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:14px;}}"
            f"QLabel{{background:transparent;border:none;}}")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(32, 28, 32, 28)
        cl.setSpacing(12)

        # Falling animation area
        self._anim_area = QFrame()
        self._anim_area.setFixedHeight(200)
        self._anim_area.setStyleSheet("background:transparent;border:none;")
        cl.addWidget(self._anim_area)

        # Create falling email widgets
        emails = ["\U0001f4e7", "\U0001f4e7", "\U0001f4e7", "\U0001f4e7", "\U0001f4e7"]
        for i, emoji in enumerate(emails):
            em = _FallingEmail(emoji, self._anim_area)
            em.move(40 + i * 80, -40)
            self._emails.append(em)

        # Title
        title = QLabel("Coming Soon")
        title.setStyleSheet(f"font-size:28px;font-weight:900;color:{C['accent']};")
        title.setAlignment(Qt.AlignCenter)
        cl.addWidget(title)

        # Description
        desc = QLabel("Auto-detect transactions from your Gmail receipts.\nBank alerts, UPI confirmations, payment receipts — all parsed automatically.")
        desc.setStyleSheet(f"font-size:13px;color:{C['text2']};")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        cl.addWidget(desc)

        # Hint bullets
        hints = [
            ("\U0001f4e7", "Connect Gmail with read-only access"),
            ("\U0001f916", "AI-powered transaction detection"),
            ("\U0001f4cb", "Review & confirm with one click"),
            ("\U0001f4ca", "Auto-categorization & sender rules"),
        ]
        for icon, text in hints:
            row = QHBoxLayout()
            row.setSpacing(8)
            il = QLabel(icon)
            il.setStyleSheet("font-size:16px;")
            row.addWidget(il)
            tl = QLabel(text)
            tl.setStyleSheet(f"font-size:12px;color:{C['text3']};")
            row.addWidget(tl, 1)
            cl.addLayout(row)

        lay.addWidget(card)
        lay.addStretch()

        # Start animation
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)
        self._tick_count = 0

    def _tick(self):
        import math
        self._tick_count += 1
        area_h = self._anim_area.height()

        for i, em in enumerate(self._emails):
            offset = i * 40
            t = (self._tick_count + offset) % 200

            # Y: top to bottom
            y = int(-40 + (area_h + 80) * (t / 200))
            # X: gentle sine wave
            x = int(40 + i * 80 + 15 * math.sin((self._tick_count + offset * 3) * 0.06))

            # Opacity: fade in at top, fade out at bottom
            if t < 30:
                opacity = t / 30
            elif t > 170:
                opacity = (200 - t) / 30
            else:
                opacity = 1.0

            em.move(x, y)
            em.setOpacity(max(0, min(1, opacity)))

    def refresh(self):
        pass
