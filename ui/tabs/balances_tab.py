"""Balances / Account Detail tab."""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

class BalancesTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.bal = services["balance"]; self.acct = repos["accounts"]; self.tx = repos["transactions"]
        lay = QVBoxLayout(self); lay.setContentsMargins(40,24,40,24)
        lay.addWidget(QLabel("Balances"))
    def refresh(self): pass
