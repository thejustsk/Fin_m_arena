"""Reusable metric card widget + shared table styling (use everywhere)."""
from PyQt5.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel,
                              QTableWidget, QHeaderView, QAbstractItemView)
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
from PyQt5.QtGui import QColor
from ui.theme import C


# ═══════════════════════════════════════════════
# SHARED TABLE STYLE — one style for ALL tables
# ═══════════════════════════════════════════════

TABLE_QSS = f"""
    QTableWidget {{
        background: {C['surface']};
        border: 1px solid {C['border2']};
        border-radius: {C['radius']};
        gridline-color: transparent;
    }}
    QTableWidget::item {{
        padding: 10px 14px;
        border-bottom: 1px solid {C['border2']};
    }}
    QTableWidget::item:selected {{
        background: {C['accent_bg']};
        color: {C['text']};
    }}
    QHeaderView::section {{
        background: {C['surface2']};
        color: {C['text3']};
        font-weight: 700;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 12px 14px;
        border: none;
        border-bottom: 2px solid {C['border2']};
    }}
"""


def style_table(table, stretch_last=True):
    """Apply the shared professional style to any QTableWidget."""
    table.setShowGrid(False)
    table.setAlternatingRowColors(False)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    if stretch_last:
        table.horizontalHeader().setStretchLastSection(True)
    table.setStyleSheet(TABLE_QSS)
    return table


def mk_table(headers, stretch_last=True):
    """Create a pre-styled QTableWidget with headers."""
    t = QTableWidget()
    t.setColumnCount(len(headers))
    t.setHorizontalHeaderLabels(headers)
    style_table(t, stretch_last)
    return t


# ═══════════════════════════════════════════════
# METRIC CARD
# ═══════════════════════════════════════════════

class MetricCard(QFrame):
    def __init__(self, label, value="", color=None, icon="", parent=None):
        super().__init__(parent)
        self.setObjectName("metric-card")
        self.setMinimumWidth(150)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        if icon:
            il = QLabel(icon)
            il.setStyleSheet("font-size:20px;")
            top.addWidget(il)
        ll = QLabel(label)
        ll.setStyleSheet(f"color:{C['text3']}; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;")
        top.addWidget(ll)
        top.addStretch()
        lay.addLayout(top)
        self.vl = QLabel(str(value))
        self.vl.setStyleSheet(f"color:{color or C['text']}; font-size:24px; font-weight:800;")
        lay.addWidget(self.vl)

    def set_value(self, v, color=None):
        self.vl.setText(str(v))
        if color:
            self.vl.setStyleSheet(f"color:{color}; font-size:24px; font-weight:800;")


def add_shadow(widget, blur=24, y_offset=4):
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur)
    shadow.setXOffset(0)
    shadow.setYOffset(y_offset)
    shadow.setColor(QColor(16, 24, 40, 20))
    widget.setGraphicsEffect(shadow)
