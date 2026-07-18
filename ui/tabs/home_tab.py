"""Home tab — greeting, stats, quick-access tiles."""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QCursor
from datetime import datetime, date
from ui.theme import C
from ui.sidebar import fmt_money
from ui.widgets.metric_card import MetricCard, add_shadow


class HomeTab(QWidget):
    go = pyqtSignal(str)

    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.bal = services["balance"]
        self.tx = repos["transactions"]
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 32, 40, 32)
        lay.setSpacing(24)

        h = datetime.now().hour
        greet = QLabel("Good Morning ☀️" if h < 12 else "Good Afternoon 🌤️" if h < 17 else "Good Evening 🌙")
        greet.setStyleSheet(f"font-size:32px;font-weight:800;color:{C['text']};")
        lay.addWidget(greet)

        nw = self.bal.net_worth()
        nwl = QLabel(f"Your net worth is <b>{fmt_money(nw)}</b>")
        nwl.setStyleSheet(f"font-size:16px;color:{C['text3']};")
        lay.addWidget(nwl)

        sr = QHBoxLayout()
        sr.setSpacing(16)
        for lbl, val, col, ico in [
            ("Today's Spend", "₹0", C['red'], "💸"),
            ("Today's Txns", "0", C['accent'], "📊"),
            ("This Month", "₹0", C['amber'], "📅"),
            ("Total Txns", "0", C['text3'], "📋"),
        ]:
            mc = MetricCard(lbl, val, col, ico)
            add_shadow(mc)
            sr.addWidget(mc)
        lay.addLayout(sr)

        tl = QLabel("Quick Access")
        tl.setStyleSheet(f"font-size:18px;font-weight:700;")
        lay.addWidget(tl)

        grid = QGridLayout()
        grid.setSpacing(14)
        tiles = [
            ("📝", "Transactions", "transaction_entry", C['accent']),
            ("🗄️", "Database", "database", "#8B5CF6"),
            ("🔍", "Audit", "audit", C['amber']),
            ("📈", "Wealth", "wealth", C['green']),
            ("📋", "Notes", "notes", "#EC4899"),
            ("💳", "Cards", "cards", C['red']),
            ("⚙️", "Settings", "settings", C['text3']),
            ("📧", "Gmail", "gmail", "#06B6D4"),
        ]
        for i, (ico, lbl, key, col) in enumerate(tiles):
            t = QFrame()
            t.setObjectName("card")
            t.setMinimumSize(150, 100)
            t.setCursor(QCursor(Qt.PointingHandCursor))
            t.setStyleSheet(f"QFrame#card{{border-left:4px solid {col};}} QFrame#card:hover{{border-color:{col};}}")
            tl2 = QVBoxLayout(t)
            tl2.setAlignment(Qt.AlignCenter)
            il = QLabel(ico)
            il.setStyleSheet("font-size:28px;")
            il.setAlignment(Qt.AlignCenter)
            tl2.addWidget(il)
            nl = QLabel(lbl)
            nl.setStyleSheet(f"font-size:12px;font-weight:600;")
            nl.setAlignment(Qt.AlignCenter)
            tl2.addWidget(nl)
            add_shadow(t, blur=12, y_offset=2)
            t.mousePressEvent = lambda e, k=key: self.go.emit(k)
            grid.addWidget(t, i // 4, i % 4)
        lay.addLayout(grid)
        lay.addStretch()

    def refresh(self):
        pass
