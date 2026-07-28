"""Friendly empty states — an icon, a headline, a hint and an optional action.

Replaces bare "No transactions." labels, which give the user nothing to do.
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor

from ui.theme import C


class EmptyState(QWidget):
    """Centred placeholder for a list or panel with nothing in it."""

    def __init__(self, icon="\U0001f4ed", title="Nothing here yet",
                 hint="", action_text=None, on_action=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 40, 24, 40)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignCenter)

        ic = QLabel(icon)
        ic.setAlignment(Qt.AlignCenter)
        ic.setStyleSheet("font-size:44px;background:transparent;border:none;")
        lay.addWidget(ic)

        t = QLabel(title)
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(
            f"font-size:15px;font-weight:800;color:{C['text']};"
            f"background:transparent;border:none;")
        lay.addWidget(t)

        if hint:
            h = QLabel(hint)
            h.setAlignment(Qt.AlignCenter)
            h.setWordWrap(True)
            h.setStyleSheet(
                f"font-size:12px;color:{C['text3']};"
                f"background:transparent;border:none;")
            lay.addWidget(h)

        if action_text and callable(on_action):
            btn = QPushButton(action_text)
            btn.setObjectName("primary")
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setMinimumHeight(38)
            btn.setMaximumWidth(260)
            btn.clicked.connect(lambda: on_action())
            lay.addWidget(btn, 0, Qt.AlignCenter)
