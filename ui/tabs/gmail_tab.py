"""Gmail tab — Professional Coming Soon screen with animated envelope graphic."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QScrollArea, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt5.QtGui import (QPainter, QColor, QLinearGradient, QRadialGradient,
                          QPainterPath, QPen, QBrush, QFont, QCursor)
import math
from ui.theme import C


class _EnvelopeWidget(QWidget):
    """Animated envelope with flying papers and pulse ring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setMinimumWidth(400)
        self._t = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(30)

    def _advance(self):
        self._t += 1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        # ── Background pulse rings ──
        for i in range(3):
            phase = (self._t * 0.02 + i * 0.33) % 1.0
            radius = 40 + phase * 80
            alpha = int(30 * (1 - phase))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(79, 70, 229, alpha))
            p.drawEllipse(int(cx - radius), int(cy - radius + 10),
                          int(radius * 2), int(radius * 2))

        # ── Envelope body ──
        env_w, env_h = 140, 100
        ex = cx - env_w / 2
        ey = cy - env_h / 2 + 10

        # Shadow
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 20))
        p.drawRoundedRect(int(ex + 4), int(ey + 6), env_w, env_h, 12, 12)

        # Body gradient
        grad = QLinearGradient(ex, ey, ex + env_w, ey + env_h)
        grad.setColorAt(0, QColor("#F0F4FF"))
        grad.setColorAt(1, QColor("#E0E7FF"))
        p.setBrush(grad)
        p.setPen(QPen(QColor("#C7D2FE"), 1.5))
        p.drawRoundedRect(int(ex), int(ey), env_w, env_h, 12, 12)

        # ── Envelope flap (animated open/close) ──
        flap_angle = 0.3 + 0.2 * math.sin(self._t * 0.04)

        flap = QPainterPath()
        flap.moveTo(ex, ey)
        flap.lineTo(cx, ey + env_h * flap_angle)
        flap.lineTo(ex + env_w, ey)
        flap.closeSubpath()

        grad2 = QLinearGradient(ex, ey, ex + env_w, ey)
        grad2.setColorAt(0, QColor("#DDD6FE"))
        grad2.setColorAt(0.5, QColor("#E0E7FF"))
        grad2.setColorAt(1, QColor("#DDD6FE"))
        p.setBrush(grad2)
        p.setPen(QPen(QColor("#C7D2FE"), 1))
        p.drawPath(flap)

        # ── Gmail-style M on envelope ──
        p.setPen(QPen(QColor("#4F46E5"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        m_y = ey + env_h * 0.55
        m_cx = cx
        m_w = 30
        p.drawLine(int(m_cx - m_w), int(m_y - 8), int(m_cx - m_w * 0.3), int(m_y + 8))
        p.drawLine(int(m_cx - m_w * 0.3), int(m_y + 8), int(m_cx), int(m_y - 2))
        p.drawLine(int(m_cx), int(m_y - 2), int(m_cx + m_w * 0.3), int(m_y + 8))
        p.drawLine(int(m_cx + m_w * 0.3), int(m_y + 8), int(m_cx + m_w), int(m_y - 8))

        # ── Flying papers ──
        for i in range(3):
            phase = (self._t * 0.015 + i * 0.4) % 1.0
            if phase < 0.7:
                # Paper flying out of envelope
                t = phase / 0.7
                ease = t * t * (3 - 2 * t)  # smoothstep
                px = cx + (i - 1) * 50 * ease
                py = ey - 20 * ease - 15 * math.sin(t * math.pi)
                rot = (i - 1) * 20 * ease

                p.save()
                p.translate(px, py)
                p.rotate(rot)

                # Paper
                paper_w, paper_h = 24, 30
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(255, 255, 255, int(200 * (1 - t * 0.3))))
                p.drawRoundedRect(int(-paper_w / 2), int(-paper_h / 2), paper_w, paper_h, 4, 4)

                # Text lines on paper
                p.setPen(QPen(QColor("#D1D5DB"), 1))
                for j in range(3):
                    line_y = -paper_h / 2 + 8 + j * 8
                    line_w = paper_w * (0.8 if j < 2 else 0.5)
                    p.drawLine(int(-line_w / 2), int(line_y), int(line_w / 2), int(line_y))

                p.restore()

        # ── Sparkle dots ──
        for i in range(6):
            phase = (self._t * 0.025 + i * 0.17) % 1.0
            angle = i * 1.05 + self._t * 0.01
            dist = 70 + 20 * math.sin(phase * math.pi * 2)
            sx = cx + math.cos(angle) * dist
            sy = cy + math.sin(angle) * dist * 0.5
            alpha = int(180 * math.sin(phase * math.pi))
            size = 2 + 2 * math.sin(phase * math.pi)

            p.setPen(Qt.NoPen)
            p.setBrush(QColor(129, 140, 248, alpha))
            p.drawEllipse(int(sx - size), int(sy - size), int(size * 2), int(size * 2))

        p.end()


class GmailTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 24, 40, 24)
        root.setSpacing(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(inner)
        lay.setSpacing(20)
        lay.setContentsMargins(0, 0, 8, 0)

        # ── Header ──
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(12)
        icon = QLabel("\U0001f4e7")
        icon.setStyleSheet("font-size:32px;background:transparent;border:none;")
        hdr_row.addWidget(icon)
        hdr_col = QVBoxLayout()
        hdr_col.setSpacing(2)
        title = QLabel("Gmail Sync")
        title.setStyleSheet(f"font-size:24px;font-weight:800;color:{C['text']};background:transparent;border:none;")
        hdr_col.addWidget(title)
        sub = QLabel("Auto-detect transactions from your email receipts")
        sub.setStyleSheet(f"font-size:13px;color:{C['text3']};background:transparent;border:none;")
        hdr_col.addWidget(sub)
        hdr_row.addLayout(hdr_col, 1)
        lay.addLayout(hdr_row)

        # ── Animated envelope ──
        envelope_frame = QFrame()
        envelope_frame.setStyleSheet(
            f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:14px;}}"
            f"QLabel{{background:transparent;border:none;}}")
        ef_lay = QVBoxLayout(envelope_frame)
        ef_lay.setContentsMargins(0, 0, 0, 0)
        self._envelope = _EnvelopeWidget()
        ef_lay.addWidget(self._envelope)

        # Overlay text on envelope area
        coming = QLabel("COMING SOON")
        coming.setStyleSheet(
            f"color:{C['accent']};font-size:22px;font-weight:900;letter-spacing:4px;"
            f"background:transparent;border:none;")
        coming.setAlignment(Qt.AlignCenter)
        ef_lay.addWidget(coming)

        tagline = QLabel("Intelligent email parsing for automatic transaction capture")
        tagline.setStyleSheet(f"color:{C['text2']};font-size:12px;background:transparent;border:none;")
        tagline.setAlignment(Qt.AlignCenter)
        ef_lay.addWidget(tagline)
        ef_lay.addSpacing(12)

        lay.addWidget(envelope_frame)

        # ── How it works — 4 step cards in a grid ──
        steps_title = QLabel("How It Will Work")
        steps_title.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};background:transparent;border:none;")
        lay.addWidget(steps_title)

        steps = [
            ("\U0001f50c", "Connect", "Link Gmail with read-only access. We never send or delete emails.", "#4F46E5"),
            ("\U0001f916", "Scan", "AI parses bank alerts, UPI receipts, and payment confirmations.", "#8B5CF6"),
            ("\U0001f44d", "Confirm", "Review detected transactions. One tap to add to your database.", "#10B981"),
            ("\U0001f9e0", "Learn", "Sender rules and auto-categorization improve over time.", "#F59E0B"),
        ]

        grid = QHBoxLayout()
        grid.setSpacing(12)
        for icon, title, desc, color in steps:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};"
                f"border-top:3px solid {color};border-radius:10px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            card.setMinimumHeight(100)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(6)

            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet("font-size:24px;")
            cl.addWidget(icon_lbl)

            t = QLabel(title)
            t.setStyleSheet(f"font-size:13px;font-weight:800;color:{C['text']};")
            cl.addWidget(t)

            d = QLabel(desc)
            d.setStyleSheet(f"font-size:11px;color:{C['text3']};")
            d.setWordWrap(True)
            cl.addWidget(d)

            grid.addWidget(card)
        lay.addLayout(grid)

        # ── Supported sources ──
        sources_title = QLabel("Supported Email Sources")
        sources_title.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};background:transparent;border:none;")
        lay.addWidget(sources_title)

        sources = [
            ("\U0001f3e6", "Banks", "HDFC, ICICI, SBI, Axis, Federal, Kotak, Yes Bank, IDFC, RBL"),
            ("\U0001f4f1", "UPI Apps", "Google Pay, PhonePe, Paytm, BHIM, Amazon Pay"),
            ("\U0001f4b3", "Credit Cards", "CRED, Slice, Uni, OneCard, Amazon Pay ICICI"),
            ("\U0001f6d2", "Shopping", "Amazon, Flipkart, Myntra order confirmations"),
        ]

        for icon, category, details in sources:
            row = QFrame()
            row.setStyleSheet(
                f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:8px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 10, 14, 10)
            rl.setSpacing(12)

            il = QLabel(icon)
            il.setStyleSheet("font-size:20px;")
            rl.addWidget(il)

            col = QVBoxLayout()
            col.setSpacing(2)
            cat = QLabel(category)
            cat.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};")
            col.addWidget(cat)
            det = QLabel(details)
            det.setStyleSheet(f"font-size:11px;color:{C['text3']};")
            det.setWordWrap(True)
            col.addWidget(det)
            rl.addLayout(col, 1)

            status = QLabel("PLANNED")
            status.setStyleSheet(
                f"color:{C['accent']};font-size:9px;font-weight:700;"
                f"background:{C['accent_bg']};border-radius:6px;padding:3px 8px;")
            rl.addWidget(status)

            lay.addWidget(row)

        # ── Footer note ──
        footer = QLabel("\U0001f512  All email processing happens locally on your device. No data leaves your computer.")
        footer.setStyleSheet(f"font-size:11px;color:{C['text3']};background:transparent;border:none;font-style:italic;")
        footer.setAlignment(Qt.AlignCenter)
        lay.addWidget(footer)

        lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

    def refresh(self):
        pass
