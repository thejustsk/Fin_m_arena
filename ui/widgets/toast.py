"""Lightweight toast notification — a non-blocking alternative to QMessageBox.

Usage::

    from ui.widgets.toast import Toast
    Toast.show_message(self, "Marked as WANT", kind="success")

The toast parents itself to the given widget's window, floats near the
bottom-centre, and fades out on its own. It never steals focus and never
blocks, so it is safe to fire from inside a click handler.
"""
from PyQt5.QtWidgets import QLabel, QGraphicsOpacityEffect, QWidget
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve

from ui.theme import C


_KIND_STYLE = {
    "success": ("#065F46", "#D1FAE5", "#10B981"),   # text, bg, border
    "info":    ("#1E3A8A", "#DBEAFE", "#3B82F6"),
    "warning": ("#92400E", "#FEF3C7", "#F59E0B"),
    "error":   ("#991B1B", "#FEE2E2", "#EF4444"),
}


class Toast(QLabel):
    """A self-dismissing message chip."""

    # Only one toast at a time per window, so a rapid series of clicks
    # replaces the message instead of stacking overlapping chips.
    _active = {}

    def __init__(self, parent_window, text, kind="info", msec=1800):
        super().__init__(parent_window)
        fg, bg, border = _KIND_STYLE.get(kind, _KIND_STYLE["info"])
        self.setText(text)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(False)
        self.setTextFormat(Qt.PlainText)
        self.setStyleSheet(
            f"QLabel{{background:{bg};color:{fg};border:1.5px solid {border};"
            f"border-radius:10px;padding:10px 18px;"
            f"font-size:13px;font-weight:700;}}")
        # Purely decorative — must never intercept clicks meant for the UI.
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)

        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()

        self._fade_in = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade_in.setDuration(140)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_in.start()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._begin_fade_out)
        self._timer.start(msec)

    def _reposition(self):
        p = self.parentWidget()
        if not p:
            return
        x = max(0, (p.width() - self.width()) // 2)
        y = max(0, p.height() - self.height() - 40)
        self.move(x, y)

    def _begin_fade_out(self):
        self._fade_out = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade_out.setDuration(260)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.InCubic)
        self._fade_out.finished.connect(self._cleanup)
        self._fade_out.start()

    def _cleanup(self):
        win = self.parentWidget()
        if Toast._active.get(win) is self:
            Toast._active.pop(win, None)
        self.hide()
        self.deleteLater()

    @staticmethod
    def show_message(widget, text, kind="info", msec=1800):
        """Show *text* over *widget*'s window. Returns the Toast, or None.

        Failures are swallowed: a notification must never break the action
        that triggered it.
        """
        try:
            win = widget.window() if widget is not None else None
            if win is None:
                return None
            prev = Toast._active.get(win)
            if prev is not None:
                try:
                    prev._cleanup()
                except Exception:
                    pass
            t = Toast(win, text, kind=kind, msec=msec)
            Toast._active[win] = t
            return t
        except Exception:
            return None
