"""Type-to-filter searchable dropdown — uses QCompleter for reliable index tracking."""
from PyQt5.QtWidgets import QComboBox, QCompleter
from PyQt5.QtCore import Qt
from ui.theme import C


class SearchableCombo(QComboBox):
    def __init__(self, parent=None, placeholder="Search..."):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.lineEdit().setPlaceholderText(placeholder)
        self._data = {}  # text → data mapping

        # Completer for type-to-filter
        self._completer = QCompleter([], self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(self._completer)
        # QCompleter uses a separate popup view; it does not inherit the
        # combo box's list stylesheet reliably on every platform.
        self._completer.popup().setStyleSheet(
            f"QAbstractItemView{{background:{C['surface']};color:{C['text']};"
            f"border:1px solid {C['border']};selection-background-color:{C['accent_bg']};"
            f"selection-color:{C['accent']};outline:0;}}"
            f"QAbstractItemView::item{{padding:8px 12px;background:{C['surface']};color:{C['text']};}}"
            f"QAbstractItemView::item:hover{{background:{C['accent_bg']};color:{C['accent']};}}"
            f"QAbstractItemView::item:selected{{background:{C['accent']};color:{C['on_accent']};}}")

        # Update completer model when items change
        self._items_list = []

    def add_item(self, text, data=None):
        self._items_list.append(text)
        self._data[text] = data
        self.addItem(text)
        self._completer.setModel(self.model())

    def get_data(self):
        return self._data.get(self.currentText())

    def clear_items(self):
        self._items_list.clear()
        self._data.clear()
        self.clear()
        self._completer.setModel(self.model())
