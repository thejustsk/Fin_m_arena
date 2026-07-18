"""Audit tab — edit transactions, bulk recategorize, month lock."""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from ui.theme import C

class AuditTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db; self.tx = repos["transactions"]
        self.au = services["audit"]; self.sec = services["security"]
        self.lu = repos["lookups"]; self._data = []
        lay = QVBoxLayout(self); lay.setContentsMargins(40,24,40,24)
        lay.addWidget(QLabel("Audit"))
    def refresh(self): pass
