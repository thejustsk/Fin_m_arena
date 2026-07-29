"""Native Windows title-bar theme support for all Qt windows and dialogs."""
import sys
import ctypes
from PyQt5.QtCore import QObject, QEvent, QTimer
from PyQt5.QtWidgets import QDialog, QMessageBox, QMainWindow


def apply_native_title_bar(widget):
    """Apply the active app theme to a native Windows title bar.

    Qt stylesheets affect a dialog's client area only. Windows draws the title
    bar itself, so use DWM immersive-dark-mode attributes when available.
    Safe no-op on non-Windows systems and unsupported Windows versions.
    """
    if sys.platform != "win32" or widget is None:
        return
    try:
        from ui.theme import active_theme
        value = ctypes.c_int(1 if active_theme() == "dark" else 0)
        hwnd = int(widget.winId())
        for attr in (20, 19):  # 20 modern Windows 10/11; 19 older builds
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


class NativeTitleBarThemeFilter(QObject):
    """Theme every shown Qt top-level window without per-dialog plumbing."""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Show and isinstance(obj, (QDialog, QMessageBox, QMainWindow)):
            # At Show time the native window handle may not yet be ready.
            # Delay one event-loop turn and tolerate a deleted dialog.
            QTimer.singleShot(0, lambda w=obj: apply_native_title_bar(w))
        return False
