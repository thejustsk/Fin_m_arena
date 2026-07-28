"""Lightweight toast notification — a non-blocking alternative to QMessageBox.

Usage::

    from ui.widgets.toast import Toast
    Toast.show_message(self, "Marked as WANT", kind="success")
    Toast.show_undo(self, "Note deleted", on_undo=restore_fn)

The toast parents itself to the given widget's window, floats near the
top-centre, and fades out on its own. It never steals focus and never
blocks, so it is safe to fire from inside a click handler.

Colours come from the live palette, so it follows light/dark automatically.
"""
from PyQt5.QtWidgets import (QLabel, QGraphicsOpacityEffect, QWidget,
                             QHBoxLayout, QPushButton, QFrame)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QCursor

from ui.theme import C, is_dark


# Distance from the top of the window to the toast.
_TOP_MARGIN = 24


def _kind_style(kind):
    """(text, background, border) for a toast kind, per active theme."""
    if is_dark():
        table = {
            "success": (C["green"],  C["green_bg"], C["green"]),
            "info":    (C["accent"], C["accent_bg"], C["accent"]),
            "warning": (C["amber"],  C["amber_bg"], C["amber"]),
            "error":   (C["red"],    C["red_bg"],   C["red"]),
        }
    else:
        table = {
            "success": ("#065F46", "#D1FAE5", "#10B981"),
            "info":    ("#1E3A8A", "#DBEAFE", "#3B82F6"),
            "warning": ("#92400E", "#FEF3C7", "#F59E0B"),
            "error":   ("#991B1B", "#FEE2E2", "#EF4444"),
        }
    return table.get(kind, table["info"])


class Toast(QLabel):
    """A self-dismissing message chip."""

    # Only one toast at a time per window, so a rapid series of clicks
    # replaces the message instead of stacking overlapping chips.
    _active = {}

    def __init__(self, parent_window, text, kind="info", msec=3000):
        super().__init__(parent_window)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(False)
        self.setTextFormat(Qt.PlainText)
        # Purely decorative — must never intercept clicks meant for the UI.
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)

        self._apply_style(text, kind)
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

    def _apply_style(self, text, kind):
        fg, bg, border = _kind_style(kind)
        self.setText(text)
        self.setStyleSheet(
            f"QLabel{{background:{bg};color:{fg};border:1.5px solid {border};"
            f"border-radius:10px;padding:10px 18px;"
            f"font-size:13px;font-weight:700;}}")

    def _reposition(self):
        """Float near the top-centre of the window."""
        p = self.parentWidget()
        if not p:
            return
        x = max(0, (p.width() - self.width()) // 2)
        y = _TOP_MARGIN
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

    def _restyle(self, text, kind, msec):
        """Reuse this chip for a new message instead of rebuilding it."""
        self._apply_style(text, kind)
        self.adjustSize()
        self._reposition()
        # Cancel any in-flight fade-out and snap back to fully visible.
        fade_out = getattr(self, "_fade_out", None)
        if fade_out is not None:
            fade_out.stop()
        self._effect.setOpacity(1.0)
        self.show()
        self.raise_()
        self._timer.start(msec)

    @staticmethod
    def _clear_for(win):
        for cls in (Toast, UndoToast):
            prev = cls._active.get(win)
            if prev is not None:
                try:
                    prev._cleanup()
                except Exception:
                    pass
                cls._active.pop(win, None)

    @staticmethod
    def show_message(widget, text, kind="info", msec=3000):
        """Show *text* over *widget*'s window. Returns the Toast, or None.

        Rapid repeat calls reuse the existing chip — cheaper than tearing a
        widget down and building another, and it avoids a visible flicker
        when tagging several rows in quick succession.

        Failures are swallowed: a notification must never break the action
        that triggered it.
        """
        try:
            win = widget.window() if widget is not None else None
            if win is None:
                return None
            # An undo toast is interactive; never silently replace it.
            u = UndoToast._active.get(win)
            if u is not None:
                try:
                    u._cleanup()
                except Exception:
                    pass
                UndoToast._active.pop(win, None)
            prev = Toast._active.get(win)
            if prev is not None:
                try:
                    prev._restyle(text, kind, msec)
                    return prev
                except RuntimeError:
                    Toast._active.pop(win, None)
                except Exception:
                    Toast._active.pop(win, None)
            t = Toast(win, text, kind=kind, msec=msec)
            Toast._active[win] = t
            return t
        except Exception:
            return None

    @staticmethod
    def show_undo(widget, text, on_undo, msec=6000):
        """Convenience wrapper for an actionable undo toast."""
        return UndoToast.show_undo(widget, text, on_undo, msec=msec)


class UndoToast(QFrame):
    """Toast with an Undo button — delete first, apologise later.

    Sits a little lower than the plain toast so the two never overlap if
    both somehow appear.
    """

    _active = {}

    def __init__(self, parent_window, text, on_undo, msec=6000):
        super().__init__(parent_window)
        self._on_undo = on_undo
        self._done = False

        fg, bg, border = _kind_style("info")
        self.setStyleSheet(
            f"QFrame{{background:{bg};border:1.5px solid {border};"
            f"border-radius:10px;}}"
            f"QLabel{{background:transparent;border:none;color:{fg};"
            f"font-size:13px;font-weight:700;}}")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 9, 10, 9)
        lay.setSpacing(14)

        self._label = QLabel(text)
        lay.addWidget(self._label)

        self._btn = QPushButton("Undo")
        self._btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn.setFocusPolicy(Qt.NoFocus)
        self._btn.setMinimumHeight(28)
        self._btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{fg};"
            f"border:1.5px solid {fg};border-radius:7px;"
            f"padding:3px 14px;font-size:12px;font-weight:800;}}"
            f"QPushButton:hover{{background:{fg};color:{bg};}}")
        self._btn.clicked.connect(self._fire)
        lay.addWidget(self._btn)

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
        self._fade_in.start()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._cleanup)
        self._timer.start(msec)

    def _reposition(self):
        p = self.parentWidget()
        if not p:
            return
        x = max(0, (p.width() - self.width()) // 2)
        self.move(x, _TOP_MARGIN)

    def _fire(self):
        if self._done:
            return
        self._done = True
        self._timer.stop()
        cb = self._on_undo
        self._cleanup()
        if callable(cb):
            try:
                cb()
            except Exception:
                pass

    def _cleanup(self):
        win = self.parentWidget()
        if UndoToast._active.get(win) is self:
            UndoToast._active.pop(win, None)
        self.hide()
        self.deleteLater()

    @staticmethod
    def show_undo(widget, text, on_undo, msec=6000):
        try:
            win = widget.window() if widget is not None else None
            if win is None:
                return None
            Toast._clear_for(win)
            t = UndoToast(win, text, on_undo, msec=msec)
            UndoToast._active[win] = t
            return t
        except Exception:
            return None
