"""Uppercase enforcement for specific QLineEdit fields.

Usage:
    from ui.uppercase import force_upper
    force_upper(self.card_name)    # auto-converts to uppercase as user types
"""

from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtCore import QObject, QEvent


class _UpperCaseFilter(QObject):
    """Event filter that converts text to uppercase on every keystroke."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress or event.type() == QEvent.KeyRelease:
            # Let the key event process normally, then uppercase after
            result = super().eventFilter(obj, event)
            if obj.text() != obj.text().upper():
                cursor_pos = obj.cursorPosition()
                obj.setText(obj.text().upper())
                obj.setCursorPosition(cursor_pos)
            return result
        return super().eventFilter(obj, event)


# Singleton filter — one instance shared across all fields
_filter = _UpperCaseFilter()


def force_upper(line_edit: QLineEdit):
    """Force a QLineEdit to always display UPPERCASE text.
    
    Works by installing an event filter that converts after each keystroke.
    The cursor position is preserved so typing feels natural.
    """
    line_edit.installEventFilter(_filter)
    # Also handle paste / programmatic text changes
    line_edit.textChanged.connect(lambda text, le=line_edit: _on_text_changed(le, text))


def _on_text_changed(line_edit: QLineEdit, text: str):
    if text != text.upper():
        cursor_pos = line_edit.cursorPosition()
        line_edit.blockSignals(True)
        line_edit.setText(text.upper())
        line_edit.setCursorPosition(cursor_pos)
        line_edit.blockSignals(False)
