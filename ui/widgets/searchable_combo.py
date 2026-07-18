"""Type-to-filter searchable dropdown — uses QCompleter for reliable index tracking."""
from PyQt5.QtWidgets import QComboBox, QCompleter
from PyQt5.QtCore import Qt


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
