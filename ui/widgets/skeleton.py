"""Skeleton placeholders shown while a list is loading.

Cheap by design: a single shared QTimer drives every visible shimmer, so a
screen full of placeholders costs one timer, not one per bar.
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame
from PyQt5.QtCore import Qt, QTimer

from ui.theme import C


class _Shimmer:
    """One 60fps-ish timer shared by all live skeleton widgets."""

    _timer = None
    _targets = []

    @classmethod
    def register(cls, w):
        if w not in cls._targets:
            cls._targets.append(w)
        if cls._timer is None:
            cls._timer = QTimer()
            cls._timer.setInterval(90)
            cls._timer.timeout.connect(cls._tick)
        if not cls._timer.isActive():
            cls._timer.start()

    @classmethod
    def unregister(cls, w):
        if w in cls._targets:
            cls._targets.remove(w)
        if not cls._targets and cls._timer is not None:
            cls._timer.stop()

    @classmethod
    def _tick(cls):
        dead = []
        for w in cls._targets:
            try:
                w._advance()
            except RuntimeError:
                dead.append(w)      # C++ side already gone
            except Exception:
                dead.append(w)
        for w in dead:
            cls.unregister(w)


class SkeletonBar(QFrame):
    """A single pulsing grey bar."""

    def __init__(self, height=12, width=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        if width:
            self.setFixedWidth(width)
        self._phase = 0
        self._paint()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def _paint(self):
        col = C["skeleton_hi"] if self._phase % 2 else C["skeleton"]
        self.setStyleSheet(
            f"background:{col};border-radius:{self.height() // 2}px;border:none;")

    def _advance(self):
        self._phase += 1
        self._paint()

    def showEvent(self, e):
        _Shimmer.register(self)
        super().showEvent(e)

    def hideEvent(self, e):
        _Shimmer.unregister(self)
        super().hideEvent(e)


class SkeletonCard(QFrame):
    """Placeholder shaped like a transaction / list card."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};"
            f"border-radius:12px;}}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(14)

        icon = SkeletonBar(height=40, width=40)
        icon.setStyleSheet(
            f"background:{C['skeleton']};border-radius:20px;border:none;")
        lay.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(7)
        col.addWidget(SkeletonBar(height=12, width=240))
        col.addWidget(SkeletonBar(height=10, width=150))
        lay.addLayout(col, 1)

        lay.addWidget(SkeletonBar(height=14, width=90))
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)


class SkeletonList(QWidget):
    """A stack of SkeletonCards to fill a list area while data loads."""

    def __init__(self, count=5, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignTop)
        for _ in range(max(1, count)):
            lay.addWidget(SkeletonCard())
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
