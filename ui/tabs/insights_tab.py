"""Insights — self-updating, offline financial review."""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QPushButton
from PyQt5.QtCore import Qt
from ui.theme import C
from ui.widgets.empty_state import EmptyState
from services.insight_service import InsightService, MIN_TRANSACTIONS


_STYLE = {
    "critical": ("#EF4444", "🚨", "Critical"),
    "warning": ("#F59E0B", "⚠️", "Review"),
    "positive": (C["green"], "✨", "Positive"),
    "info": (C["accent"], "💡", "Pattern"),
}


class InsightsTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db, self.repos, self.services = db, repos, services
        self.engine = InsightService(repos["transactions"], db, repos)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24); root.setSpacing(12)
        top = QHBoxLayout()
        title_col = QVBoxLayout(); title_col.setSpacing(2)
        title = QLabel("🧠  Insights")
        title.setStyleSheet(f"font-size:22px;font-weight:800;color:{C['text']};")
        subtitle = QLabel("Private, explainable insights from your own finance data")
        subtitle.setStyleSheet(f"font-size:12px;color:{C['text3']};")
        title_col.addWidget(title); title_col.addWidget(subtitle)
        top.addLayout(title_col); top.addStretch()
        refresh = QPushButton("↻ Refresh")
        refresh.setObjectName("primary"); refresh.clicked.connect(self.refresh)
        top.addWidget(refresh); root.addLayout(top)
        self.summary = QLabel()
        self.summary.setStyleSheet(f"color:{C['text3']};font-size:12px;font-weight:600;")
        root.addWidget(self.summary)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.inner = QWidget(); self.inner.setStyleSheet("background:transparent;")
        self.lay = QVBoxLayout(self.inner); self.lay.setContentsMargins(0, 4, 8, 4); self.lay.setSpacing(10)
        self.scroll.setWidget(self.inner); root.addWidget(self.scroll, 1)

    def on_activated(self):
        self.refresh()

    def refresh(self):
        result = self.engine.analyze()
        self._clear()
        count = result["transaction_count"]
        if not result["ready"]:
            remaining = MIN_TRANSACTIONS - count
            self.summary.setText(f"Learning from {count} transaction{'s' if count != 1 else ''}")
            self.lay.addWidget(EmptyState("🌱", "Building your financial picture", f"Add {remaining} more transaction{'s' if remaining != 1 else ''} to unlock personalised insights. Your data stays on this device."))
            self.lay.addStretch(); return
        insights = result["insights"]
        self.summary.setText(f"Analysed {count:,} transactions · {len(insights)} insight{'s' if len(insights) != 1 else ''} found · Updates whenever you open this page")
        if not insights:
            self.lay.addWidget(EmptyState("✨", "Everything looks steady", "No unusual spending patterns or review items were found in the current data."))
        else:
            for insight in insights:
                self.lay.addWidget(self._card(insight))
        self.lay.addStretch()

    def _card(self, insight):
        color, icon, kind = _STYLE.get(insight["severity"], _STYLE["info"])
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-left:4px solid {color};border-radius:10px;}}QLabel{{background:transparent;border:none;}}")
        row = QHBoxLayout(card); row.setContentsMargins(16, 13, 16, 13); row.setSpacing(12)
        badge = QLabel(icon); badge.setFixedWidth(26); badge.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        badge.setStyleSheet("font-size:18px;"); row.addWidget(badge)
        body = QVBoxLayout(); body.setSpacing(4)
        heading = QHBoxLayout(); title = QLabel(insight["title"])
        title.setStyleSheet(f"font-size:14px;font-weight:800;color:{C['text']};"); heading.addWidget(title); heading.addStretch()
        chip = QLabel(kind); chip.setStyleSheet(f"color:{color};background:{color}18;border-radius:8px;padding:3px 8px;font-size:10px;font-weight:800;"); heading.addWidget(chip)
        body.addLayout(heading)
        msg = QLabel(insight["message"]); msg.setWordWrap(True)
        msg.setStyleSheet(f"font-size:12px;color:{C['text2']};line-height:1.4;"); body.addWidget(msg)
        category = QLabel(insight.get("category", "General")); category.setStyleSheet(f"font-size:10px;color:{C['text3']};font-weight:700;"); body.addWidget(category)
        row.addLayout(body, 1)
        return card

    def _clear(self):
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
