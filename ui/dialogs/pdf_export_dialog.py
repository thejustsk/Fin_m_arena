"""PDF export popup — Title + Comment + Generate. Shared by Filtered View & Notes."""
from PyQt5.QtWidgets import (QDialog, QFormLayout, QLineEdit, QTextEdit,
                              QDialogButtonBox)


class PdfExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export PDF")
        self.setMinimumWidth(360)
        lay = QFormLayout(self)

        self.title = QLineEdit()
        self.title.setPlaceholderText("Document title")
        lay.addRow("Title:", self.title)

        self.comment = QTextEdit()
        self.comment.setPlaceholderText("Optional comment")
        self.comment.setMaximumHeight(80)
        lay.addRow("Comment:", self.comment)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Generate PDF")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)

    def data(self):
        return {"title": self.title.text(), "comment": self.comment.toPlainText()}
