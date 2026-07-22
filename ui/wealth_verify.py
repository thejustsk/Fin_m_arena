"""Wealth edit verification — requires TOTP code before saving."""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QLineEdit, QFormLayout)
from PyQt5.QtCore import Qt
from ui.theme import C


class WealthEditVerifyDialog(QDialog):
    """Verify identity before allowing wealth tab edits.
    If 2FA enabled: ask for TOTP code only (matches login screen).
    Otherwise: ask for password.
    """

    def __init__(self, security_service, parent=None):
        super().__init__(parent)
        self._sec = security_service
        self._verified = False
        self.setWindowTitle("Verify to Save")
        self.setMinimumWidth(320)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        icon = QLabel("\U0001f510")
        icon.setStyleSheet("font-size:28px;")
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)

        title = QLabel("Verification Required")
        title.setStyleSheet(f"font-size:15px;font-weight:800;color:{C['text']};")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        f = QFormLayout()

        if self._sec.is_2fa():
            self.input_field = QLineEdit()
            self.input_field.setPlaceholderText("6-digit code")
            self.input_field.setMaxLength(6)
            self.input_field.setStyleSheet(
                f"font-size:18px;font-weight:700;letter-spacing:4px;padding:10px;")
            f.addRow("TOTP Code:", self.input_field)
            self._mode = "totp"
        else:
            self.input_field = QLineEdit()
            self.input_field.setPlaceholderText("Enter your password")
            self.input_field.setEchoMode(QLineEdit.Password)
            f.addRow("Password:", self.input_field)
            self._mode = "password"

        lay.addLayout(f)

        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet(f"color:{C['red']};font-size:12px;font-weight:600;")
        self.error_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.error_lbl)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        verify_btn = QPushButton("\u2705 Confirm & Save")
        verify_btn.setObjectName("primary")
        verify_btn.clicked.connect(self._verify)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(verify_btn)
        lay.addLayout(btn_row)

        self.input_field.setFocus()
        self.input_field.returnPressed.connect(self._verify)

    def _verify(self):
        text = self.input_field.text().strip()
        if not text:
            self.error_lbl.setText("Please enter the code.")
            return

        if self._mode == "totp":
            if self._sec.verify_totp(text):
                self._verified = True
                self.accept()
            else:
                self.error_lbl.setText("Invalid code. Try again.")
                self.input_field.clear()
                self.input_field.setFocus()
        else:
            if self._sec.verify(text):
                self._verified = True
                self.accept()
            else:
                self.error_lbl.setText("Invalid password. Try again.")
                self.input_field.clear()
                self.input_field.setFocus()

    @staticmethod
    def verify_user(security_service, parent=None):
        """Show dialog and return True if verified."""
        dlg = WealthEditVerifyDialog(security_service, parent)
        return dlg.exec_() == QDialog.Accepted
