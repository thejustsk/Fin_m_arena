"""Month lock dialog — 2FA to unlock."""
from PyQt5.QtWidgets import (QDialog, QFormLayout, QLineEdit, QLabel,
                              QDialogButtonBox, QMessageBox)


class MonthLockDialog(QDialog):
    def __init__(self, sec_svc, period_id, parent=None):
        super().__init__(parent)
        self.sec = sec_svc
        self.period_id = period_id
        self.setWindowTitle("Unlock Month")
        lay = QFormLayout(self)

        lay.addWidget(QLabel(f"Enter 2FA code to unlock {period_id}:"))
        self.code = QLineEdit()
        self.code.setPlaceholderText("6-digit code")
        self.code.setMaxLength(6)
        lay.addRow("Code:", self.code)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._verify)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)

    def _verify(self):
        if self.sec.verify_totp(self.code.text()):
            self.sec.unlock(self.period_id)
            self.accept()
        else:
            QMessageBox.warning(self, "Failed", "Invalid code.")
