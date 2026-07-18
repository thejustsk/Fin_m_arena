"""Notes tab — All Notes, Create from Transaction, Trash."""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

class NotesTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.nr = repos["notes"]; self.lu = repos["lookups"]; self.tx = repos["transactions"]
        lay = QVBoxLayout(self); lay.setContentsMargins(40,24,40,24)
        lay.addWidget(QLabel("Notes"))
    def refresh(self): pass
