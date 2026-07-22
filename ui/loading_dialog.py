"""Animated loading splash dialog for app startup."""
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QWidget, QFrame
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QPainter, QPen
from ui.theme import C


class SpinnerWidget(QWidget):
    """Animated spinner — rotating arc."""
    def __init__(self, size=48, color=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._color = QColor(color or C["accent"])
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.start(30)  # ~33fps

    def _rotate(self):
        self._angle = (self._angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self._color, 3, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        size = min(self.width(), self.height())
        margin = 4
        p.drawArc(margin, margin, size - 2*margin, size - 2*margin,
                  self._angle * 16, 270 * 16)
        p.end()


class LoadingDialog(QDialog):
    """Animated loading splash with spinner + status text + progress bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(680, 320)
        self._build()

    def _build(self):
        # Outer container with rounded corners
        container = QFrame(self)
        container.setGeometry(20, 20, 640, 280)
        container.setStyleSheet(f"""
            QFrame {{
                background: {C['surface']};
                border: 1.5px solid {C['border']};
                border-radius: 16px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)

        lay = QVBoxLayout(container)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        # App title
        title = QLabel("💰  Finance Manager")
        title.setStyleSheet(f"font-size:16px;font-weight:800;color:{C['text']};")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        # Spinner
        spinner = SpinnerWidget(size=40, color=C["accent"])
        lay.addWidget(spinner, alignment=Qt.AlignCenter)

        # Status text
        self.status_lbl = QLabel("Initializing...")
        self.status_lbl.setStyleSheet(f"font-size:12px;color:{C['text3']};font-weight:600;")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.status_lbl)

        # Progress bar (indeterminate style)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background: {C['border2']};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {C['accent']};
                border-radius: 2px;
            }}
        """)
        lay.addWidget(self.progress)

    def set_status(self, text):
        """Update the status message."""
        self.status_lbl.setText(text)
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()
