"""Filter chip bar with add/clear."""
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QDialog, QFormLayout, QComboBox
from PyQt5.QtCore import pyqtSignal
from ui.theme import C


class FilterChipBar(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(6)
        self.filters = {}
        self.add_btn = QPushButton("+ Add Filter")
        self.add_btn.setObjectName("pill")
        self.add_btn.clicked.connect(self._add)
        self.lay.addWidget(self.add_btn)
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setObjectName("ghost")
        self.clear_btn.clicked.connect(self.clear)
        self.lay.addWidget(self.clear_btn)
        self.lay.addStretch()

    def _add(self):
        d = QDialog(self); d.setWindowTitle("Add Filter"); lay = QFormLayout(d)
        fc = QComboBox(); fc.addItems(["Account","Category","Type"])
        lay.addRow("Field:", fc)
        from PyQt5.QtWidgets import QDialogButtonBox
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject)
        lay.addRow(bb)
        if d.exec_() == QDialog.Accepted:
            self.filters[fc.currentText()] = "value"
            self.changed.emit()

    def clear(self):
        self.filters.clear()
        self.changed.emit()

    def get(self):
        return dict(self.filters)
