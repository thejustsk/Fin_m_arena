"""Wealth tab — 3 groups, 5 functions."""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

class WealthTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.repos = repos; self.services = services
        lay = QVBoxLayout(self); lay.setContentsMargins(40,24,40,24)
        lay.addWidget(QLabel("Wealth"))
    def refresh(self): pass
