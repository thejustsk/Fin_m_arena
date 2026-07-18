"""Gmail tab — Accounts, Sender Rules, Scan History."""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

class GmailTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self); lay.setContentsMargins(40,24,40,24)
        lay.addWidget(QLabel("Gmail Sync"))
    def refresh(self): pass
