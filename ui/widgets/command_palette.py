"""Ctrl+K command palette — fuzzy jump to any tab or action.

With twelve tabs plus sub-pages, hunting the sidebar is slower than typing.
Entries are supplied by the main window so this widget stays generic.
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLineEdit, QListWidget,
                             QListWidgetItem, QLabel, QFrame, QHBoxLayout)
from PyQt5.QtCore import Qt

from ui.theme import C


def fuzzy_score(query, text):
    """Subsequence match. Higher is better; None means no match.

    Rewards prefix matches and consecutive runs so "wea" ranks Wealth above
    "Wallet Expense Audit".
    """
    if not query:
        return 0
    q, t = query.lower(), text.lower()
    if q in t:
        # Direct substring: strongly preferred, best at position 0.
        return 1000 - t.index(q) * 5 - (len(t) - len(q))
    score, qi, streak = 0, 0, 0
    for ch in t:
        if qi < len(q) and ch == q[qi]:
            qi += 1
            streak += 1
            score += 5 + streak * 2
        else:
            streak = 0
    return score if qi == len(q) else None


class CommandPalette(QDialog):
    """Modal fuzzy launcher. ``entries`` = [(icon, label, hint, callable)]."""

    def __init__(self, entries, parent=None):
        super().__init__(parent)
        self._entries = list(entries)
        self.setWindowTitle("Command Palette")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        shell = QFrame()
        shell.setObjectName("paletteShell")
        shell.setStyleSheet(
            f"QFrame#paletteShell{{background:{C['surface']};"
            f"border:1.5px solid {C['border']};border-radius:14px;}}")
        outer.addWidget(shell)

        lay = QVBoxLayout(shell)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(8)
        mag = QLabel("\U0001f50d")
        mag.setStyleSheet("font-size:16px;background:transparent;border:none;")
        row.addWidget(mag)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Jump to\u2026  (type a tab or action)")
        self.input.setMinimumHeight(38)
        self.input.setStyleSheet(
            f"QLineEdit{{background:{C['surface2']};border:1.5px solid {C['border2']};"
            f"border-radius:9px;padding:8px 12px;font-size:14px;color:{C['text']};}}"
            f"QLineEdit:focus{{border-color:{C['accent']};}}")
        row.addWidget(self.input, 1)
        lay.addLayout(row)

        self.list = QListWidget()
        self.list.setFixedHeight(300)
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setStyleSheet(
            f"QListWidget{{background:transparent;border:none;outline:none;}}"
            f"QListWidget::item{{color:{C['text']};padding:9px 10px;"
            f"border-radius:8px;margin:1px 0;}}"
            f"QListWidget::item:selected{{background:{C['accent_bg']};"
            f"color:{C['text']};}}")
        lay.addWidget(self.list)

        tip = QLabel("\u2191\u2193 navigate    \u21b5 open    Esc close")
        tip.setStyleSheet(
            f"font-size:10px;color:{C['text3']};background:transparent;border:none;")
        tip.setAlignment(Qt.AlignCenter)
        lay.addWidget(tip)

        self.input.textChanged.connect(self._refilter)
        self.list.itemActivated.connect(lambda _: self._run())
        self.list.itemClicked.connect(lambda _: self._run())
        self._refilter("")
        self.input.setFocus()

    def _refilter(self, text):
        self.list.clear()
        scored = []
        for icon, label, hint, fn in self._entries:
            s = fuzzy_score(text, f"{label} {hint}")
            if s is not None:
                scored.append((s, icon, label, hint, fn))
        scored.sort(key=lambda x: -x[0])
        for _, icon, label, hint, fn in scored[:40]:
            it = QListWidgetItem(f"  {icon}   {label}" + (f"    \u00b7  {hint}" if hint else ""))
            it.setData(Qt.UserRole, fn)
            self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _run(self):
        it = self.list.currentItem()
        if it is None:
            return
        fn = it.data(Qt.UserRole)
        self.accept()
        if callable(fn):
            try:
                fn()
            except Exception:
                pass

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Escape:
            self.reject()
            return
        if k in (Qt.Key_Return, Qt.Key_Enter):
            self._run()
            return
        if k == Qt.Key_Down:
            self.list.setCurrentRow(min(self.list.currentRow() + 1,
                                        self.list.count() - 1))
            return
        if k == Qt.Key_Up:
            self.list.setCurrentRow(max(self.list.currentRow() - 1, 0))
            return
        super().keyPressEvent(e)
