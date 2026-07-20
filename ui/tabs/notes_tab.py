"""Notes tab — Create, edit, search, tag chips, linked transactions, trash, print."""
import json
import uuid as _uuid
import os, subprocess, sys
from datetime import date

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QLineEdit, QTextEdit, QFrame,
                              QScrollArea, QStackedWidget, QMessageBox,
                              QComboBox, QDateEdit, QSizePolicy, QLayout,
                              QFileDialog)
from PyQt5.QtCore import Qt, QDate, QPoint, pyqtSignal, QRect, QSize
from PyQt5.QtGui import QCursor

from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tx_card, _day_header


# ═══════════════════════════════════════════════
# FLOW LAYOUT
# ═══════════════════════════════════════════════
class FlowLayout(QLayout):
    def __init__(self, parent=None, hSpacing=6, vSpacing=4):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self._h = hSpacing; self._v = vSpacing; self._items = []
    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, i): return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i): return self._items.pop(i) if 0 <= i < len(self._items) else None
    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return self._do(QRect(0, 0, w, 0), True)
    def setGeometry(self, r): super().setGeometry(r); self._do(r, False)
    def sizeHint(self): return self.minimumSize()
    def minimumSize(self):
        s = QSize()
        for it in self._items: s = s.expandedTo(it.minimumSize())
        return s
    def _do(self, rect, test):
        x = rect.x(); y = rect.y(); lineH = 0
        for item in self._items:
            sh = item.sizeHint()
            nx = x + sh.width() + self._h
            if nx - self._h > rect.right() + 1 and lineH > 0:
                x = rect.x(); y += lineH + self._v
                nx = x + sh.width() + self._h; lineH = 0
            if not test:
                item.setGeometry(QRect(QPoint(x, y), sh))
            x = nx; lineH = max(lineH, sh.height())
        return y + lineH - rect.y()


# ═══════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════
_TAG_COLORS = ["#4F46E5", "#0EA5E9", "#059669", "#D97706", "#EC4899", "#8B5CF6", "#DC2626"]

def _tag_color(tag_text):
    h = sum(ord(c) for c in tag_text)
    return _TAG_COLORS[h % len(_TAG_COLORS)]

def _note_accent(note):
    """Get accent color from first tag of a note."""
    tags_str = note.get("tags") or ""
    first_tag = tags_str.split(",")[0].strip() if tags_str else ""
    return _tag_color(first_tag) if first_tag else C['border2']

def _linked_ids(note):
    raw = note.get("linked_transaction_ids")
    if not raw: return []
    try:
        ids = json.loads(raw)
        return ids if isinstance(ids, list) else []
    except: return []

def _btn_primary():
    return f"QPushButton{{background:{C['accent']};color:white;border:none;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:700;}}QPushButton:hover{{background:#4338CA;}}"
def _btn_danger():
    return f"QPushButton{{background:{C['red']};color:white;border:none;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:700;}}QPushButton:hover{{background:#B91C1C;}}"
def _btn_ghost():
    return f"QPushButton{{background:transparent;color:{C['text2']};border:1px solid {C['border']};border-radius:8px;padding:8px 16px;font-size:13px;font-weight:600;}}QPushButton:hover{{border-color:{C['accent']};color:{C['accent']};}}"
def _input_css():
    return f"background:{C['surface']};border:1.5px solid {C['border']};border-radius:8px;padding:8px 12px;font-size:13px;"


# ═══════════════════════════════════════════════
# TAG CHIP
# ═══════════════════════════════════════════════
def _make_tag_chip(text, accent_color=None, removable=False, on_remove=None):
    """Tag chip: white text on accent-colored background."""
    color = accent_color or _tag_color(text)
    label = f" #{text} " + ("✕" if removable else "")
    chip = QPushButton(label)
    chip.setStyleSheet(
        f"QPushButton{{background:{color};color:white;border:none;"
        f"border-radius:12px;padding:3px 10px;font-size:11px;font-weight:700;}}"
        f"QPushButton:hover{{background:{color}CC;}}")
    chip.setCursor(QCursor(Qt.PointingHandCursor) if removable else Qt.ArrowCursor)
    chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    if removable and on_remove:
        chip.clicked.connect(on_remove)
    return chip


# ═══════════════════════════════════════════════
# NOTE CARD
# ═══════════════════════════════════════════════
class NoteCard(QFrame):
    clicked = pyqtSignal(str)
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    print_requested = pyqtSignal(str)

    def __init__(self, note, tx_repo=None, parent=None):
        super().__init__(parent)
        self.note = note
        self.tx_repo = tx_repo
        self.expanded = False
        self._accent = _note_accent(note)
        self._build()

    def _build(self):
        a = self._accent
        self.setStyleSheet(f"""
            QFrame {{ background:{C['surface']}; border:1px solid {C['border2']};
                       border-left:4px solid {a}; border-radius:12px; }}
            QFrame:hover {{ border-left-color:{a}; border-top-color:{a};
                            border-bottom-color:{a}; border-right-color:{a}; }}
            QLabel {{ background:transparent; border:none; }}
        """)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        # Title + linked badge
        top = QHBoxLayout()
        title = QLabel(self.note.get("title") or "Untitled")
        title.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:700;")
        top.addWidget(title, 1)
        ids = _linked_ids(self.note)
        if ids:
            badge = QLabel(f"\U0001f517 {len(ids)}")
            badge.setStyleSheet(f"color:{C['accent']};font-size:11px;font-weight:700;"
                                f"background:{C['accent_bg']};border-radius:8px;padding:2px 8px;")
            top.addWidget(badge)
        lay.addLayout(top)

        # ALL tags as chips with NOTE'S accent color as background
        tags_str = self.note.get("tags") or ""
        tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
        if tags_list:
            chip_row = QHBoxLayout()
            chip_row.setSpacing(4)
            for t in tags_list:
                chip_row.addWidget(_make_tag_chip(t, accent_color=a))
            chip_row.addStretch()
            lay.addLayout(chip_row)

        # ── Expanded content ──
        self._expand_area = QWidget()
        self._expand_area.setStyleSheet("background:transparent;border:none;")
        exp_lay = QVBoxLayout(self._expand_area)
        exp_lay.setContentsMargins(0, 4, 0, 0)
        exp_lay.setSpacing(8)

        # Content
        content_text = self.note.get("content") or ""
        if content_text:
            content_lbl = QLabel(content_text)
            content_lbl.setWordWrap(True)
            content_lbl.setStyleSheet(f"color:{C['text2']};font-size:12px;background:{C['surface2']};"
                                      f"border-radius:8px;padding:10px;")
            content_lbl.setMinimumHeight(50)
            exp_lay.addWidget(content_lbl)

        # Linked transactions — FULL _tx_card format with date
        if ids and self.tx_repo:
            link_title = QLabel(f"\U0001f517 Linked Transactions ({len(ids)})")
            link_title.setStyleSheet(f"color:{C['text2']};font-size:12px;font-weight:700;")
            exp_lay.addWidget(link_title)
            for tid in ids:
                tx = self.tx_repo.get(tid)
                if tx:
                    exp_lay.addWidget(_tx_card(tx))

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        for text, signal_name in [
            ("\U0001f5a8\ufe0f Print", "print_requested"),
            ("\u270f\ufe0f Edit", "edit_requested"),
            ("\U0001f5d1\ufe0f Delete", "delete_requested"),
        ]:
            btn = QPushButton(text)
            btn.setStyleSheet(_btn_ghost())
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            signal = getattr(self, signal_name)
            nid = self.note["id"]
            btn.clicked.connect(lambda _, s=signal, n=nid: s.emit(n))
            btn_row.addWidget(btn)
        exp_lay.addLayout(btn_row)

        self._expand_area.hide()
        lay.addWidget(self._expand_area)

    def mousePressEvent(self, event):
        self.clicked.emit(self.note["id"])
        event.accept()

    def expand(self):
        self.expanded = True
        self._expand_area.show()

    def collapse(self):
        self.expanded = False
        self._expand_area.hide()


# ═══════════════════════════════════════════════
# NOTES TAB
# ═══════════════════════════════════════════════
class NotesTab(QWidget):
    def __init__(self, db, repos, services, parent=None):
        super().__init__(parent)
        self.db = db
        self.nr = repos["notes"]
        self.lu = repos["lookups"]
        self.tx = repos["transactions"]
        self.acc = repos.get("accounts")
        self.edit_note_id = None
        self.linked_ids = set()
        self._loading_tx = False
        self._composer_tags = []
        self._build()
        self.refresh()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(16)

        heading = QLabel("\U0001f4cb  Notes")
        heading.setStyleSheet(f"font-size:22px;font-weight:800;color:{C['text']};")
        outer.addWidget(heading)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)
        self.btn_all = QPushButton("All Notes")
        self.btn_new = QPushButton("\uff0b New Note")
        self.btn_trash = QPushButton("\U0001f5d1\ufe0f Trash")
        self._nav_btns = [self.btn_all, self.btn_new, self.btn_trash]
        for b in self._nav_btns:
            b.setMinimumHeight(34); b.setCursor(QCursor(Qt.PointingHandCursor))
            nav_row.addWidget(b)
        nav_row.addStretch()
        outer.addLayout(nav_row)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_all_page())
        self.stack.addWidget(self._build_compose_page())
        self.stack.addWidget(self._build_trash_page())

        self.btn_all.clicked.connect(lambda: self._goto(0))
        self.btn_new.clicked.connect(lambda: self._goto(1, reset=True))
        self.btn_trash.clicked.connect(lambda: self._goto(2))
        self._goto(0)

    def _goto(self, idx, reset=False):
        for i, b in enumerate(self._nav_btns):
            b.setStyleSheet(_btn_primary() if i == idx else _btn_ghost())
        self.stack.setCurrentIndex(idx)
        if idx == 0: self._load_notes()
        elif idx == 1 and reset: self._reset_composer()
        elif idx == 2: self._load_trash()

    def refresh(self):
        self._load_notes()
        self._load_trash()

    # ─────────────── PAGE 1: All Notes ───────────────
    def _build_all_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("\U0001f50d  Search notes by title or tag\u2026")
        self.search_box.setMinimumHeight(38)
        self.search_box.setStyleSheet(_input_css())
        self.search_box.textChanged.connect(self._load_notes)
        lay.addWidget(self.search_box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self.notes_lay = QVBoxLayout(inner)
        self.notes_lay.setSpacing(10)
        self.notes_lay.setAlignment(Qt.AlignTop)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return page

    def _load_notes(self):
        for i in reversed(range(self.notes_lay.count())):
            item = self.notes_lay.itemAt(i)
            if item.widget():
                item.widget().deleteLater()

        notes = self.nr.list_active(self.search_box.text().strip() or None)
        if not notes:
            empty = QLabel("No notes yet. Click \"+ New Note\" to create one.")
            empty.setStyleSheet(f"color:{C['text3']};font-size:13px;padding:24px;")
            empty.setAlignment(Qt.AlignCenter)
            self.notes_lay.addWidget(empty)
            return

        for n in notes:
            card = NoteCard(n, tx_repo=self.tx)
            card.clicked.connect(self._toggle_card)
            card.edit_requested.connect(self._edit_note)
            card.delete_requested.connect(self._delete_note)
            card.print_requested.connect(self._print_single_note)
            self.notes_lay.addWidget(card)

    def _toggle_card(self, note_id):
        for i in range(self.notes_lay.count()):
            item = self.notes_lay.itemAt(i)
            w = item.widget()
            if isinstance(w, NoteCard):
                if w.note["id"] == note_id:
                    w.expand() if not w.expanded else w.collapse()
                else:
                    w.collapse()

    def _delete_note(self, note_id):
        reply = QMessageBox.question(self, "Delete Note",
            "Move to Trash? You can recover it later.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.nr.soft_delete(note_id)
            self._load_notes()
            self._load_trash()

    def _edit_note(self, note_id):
        note = self.nr.get(note_id)
        if not note: return
        self._reset_composer()
        self.edit_note_id = note_id
        self.compose_title.setText(note.get("title") or "")
        tags_str = note.get("tags") or ""
        self._composer_tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        self._rebuild_tag_chips()
        self.compose_content.setPlainText(note.get("content") or "")
        self.linked_ids = set(_linked_ids(note))
        self._update_linked_summary()
        self._load_tx_picker()
        self.compose_header.setText("\u270f\ufe0f  Edit Note")
        self._goto(1)

    # ─────────────── PAGE 2: Compose ───────────────
    def _build_compose_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        self.compose_header = QLabel("\U0001f4dd  New Note")
        self.compose_header.setStyleSheet(f"font-size:18px;font-weight:800;color:{C['accent']};")
        lay.addWidget(self.compose_header)

        # Title
        self.compose_title = QLineEdit()
        self.compose_title.setPlaceholderText("Title")
        self.compose_title.setMinimumHeight(38)
        self.compose_title.setStyleSheet(_input_css())
        lay.addWidget(self.compose_title)

        # Tags
        tags_label = QLabel("Tags")
        tags_label.setStyleSheet(f"color:{C['text2']};font-size:12px;font-weight:600;")
        lay.addWidget(tags_label)

        self._tag_chip_container = QWidget()
        self._tag_chip_container.setStyleSheet("background:transparent;border:none;")
        self._tag_chip_lay = FlowLayout(self._tag_chip_container, hSpacing=4, vSpacing=4)
        lay.addWidget(self._tag_chip_container)

        tag_input_row = QHBoxLayout()
        tag_input_row.setSpacing(6)
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Type a tag and press Enter\u2026")
        self.tag_input.setMinimumHeight(34)
        self.tag_input.setStyleSheet(_input_css())
        self.tag_input.returnPressed.connect(self._add_tag_from_input)
        self.tag_input.textChanged.connect(self._update_tag_suggestions)
        tag_input_row.addWidget(self.tag_input, 1)

        self.tag_suggestions = QComboBox()
        self.tag_suggestions.setMinimumHeight(34)
        self.tag_suggestions.setMinimumWidth(280)
        self.tag_suggestions.setStyleSheet(_input_css())
        self.tag_suggestions.activated.connect(self._apply_tag_suggestion)
        self.tag_suggestions.hide()
        tag_input_row.addWidget(self.tag_suggestions)
        lay.addLayout(tag_input_row)

        # Content
        self.compose_content = QTextEdit()
        self.compose_content.setPlaceholderText("Write your note here\u2026")
        self.compose_content.setMinimumHeight(120)
        self.compose_content.setStyleSheet(_input_css())
        lay.addWidget(self.compose_content)

        # ── Link Transactions (DB filter style) ──
        link_frame = QFrame()
        link_frame.setStyleSheet(f"QFrame{{background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:8px 12px;}}QLabel{{background:transparent;border:none;}}")
        link_lay = QVBoxLayout(link_frame)
        link_lay.setContentsMargins(12, 10, 12, 10)
        link_lay.setSpacing(8)

        link_header = QLabel("\U0001f517  Link Transactions (optional)")
        link_header.setStyleSheet(f"font-weight:700;color:{C['text2']};font-size:13px;")
        link_lay.addWidget(link_header)

        # Filter bar — same style as DB filtered view
        bar = QFrame()
        bar.setStyleSheet("QFrame{background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:6px 10px;}")
        filt = QHBoxLayout(bar)
        filt.setContentsMargins(4, 4, 4, 4)
        filt.setSpacing(6)

        filt.addWidget(QLabel("From"))
        self.tx_from = QDateEdit(); self.tx_from.setCalendarPopup(True)
        self.tx_from.setDate(QDate.currentDate().addMonths(-1))
        self.tx_from.setMinimumHeight(32); self.tx_from.setMaximumWidth(110)
        filt.addWidget(self.tx_from)
        filt.addWidget(QLabel("To"))
        self.tx_to = QDateEdit(); self.tx_to.setCalendarPopup(True)
        self.tx_to.setDate(QDate.currentDate())
        self.tx_to.setMinimumHeight(32); self.tx_to.setMaximumWidth(110)
        filt.addWidget(self.tx_to)

        # Divider
        div = QFrame(); div.setFixedHeight(24); div.setFixedWidth(1)
        div.setStyleSheet(f"background:{C['border']};")
        filt.addWidget(div)

        self.tx_type_cb = QComboBox(); self.tx_type_cb.addItems(["ALL", "DEBIT", "CREDIT"])
        self.tx_type_cb.setMinimumHeight(32); self.tx_type_cb.setMaximumWidth(80)
        filt.addWidget(self.tx_type_cb)
        self.tx_account_cb = QComboBox()
        self.tx_account_cb.addItem("ALL Accounts", None)
        self.tx_account_cb.setMinimumHeight(32); self.tx_account_cb.setMaximumWidth(150)
        filt.addWidget(self.tx_account_cb)
        self.tx_search = QLineEdit(); self.tx_search.setPlaceholderText("Search person/desc\u2026")
        self.tx_search.setMinimumHeight(32); self.tx_search.setStyleSheet(_input_css())
        filt.addWidget(self.tx_search, 1)
        load_btn = QPushButton("\u27f3 Load")
        load_btn.setStyleSheet(_btn_primary())
        load_btn.setMinimumHeight(32)
        load_btn.setCursor(QCursor(Qt.PointingHandCursor))
        load_btn.clicked.connect(self._load_tx_picker)
        filt.addWidget(load_btn)
        link_lay.addWidget(bar)

        # Transaction list — FULL _tx_card style
        self.tx_scroll = QScrollArea()
        self.tx_scroll.setWidgetResizable(True)
        self.tx_scroll.setFrameShape(QFrame.NoFrame)
        self.tx_scroll.setMaximumHeight(300)
        self.tx_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        tx_inner = QWidget()
        tx_inner.setStyleSheet("background:transparent;")
        self.tx_list_lay = QVBoxLayout(tx_inner)
        self.tx_list_lay.setSpacing(4)
        self.tx_list_lay.setContentsMargins(0, 0, 0, 0)
        self.tx_scroll.setWidget(tx_inner)
        link_lay.addWidget(self.tx_scroll)

        self.linked_summary_lbl = QLabel("No transactions linked.")
        self.linked_summary_lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
        link_lay.addWidget(self.linked_summary_lbl)

        lay.addWidget(link_frame, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_btn_ghost())
        cancel_btn.clicked.connect(lambda: self._goto(0))
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("\U0001f4be  Save Note")
        save_btn.setStyleSheet(_btn_primary())
        save_btn.setCursor(QCursor(Qt.PointingHandCursor))
        save_btn.clicked.connect(self._save_note)
        btn_row.addWidget(save_btn)
        lay.addLayout(btn_row)

        return page

    def _reset_composer(self):
        self.edit_note_id = None
        self.linked_ids = set()
        self._composer_tags = []
        self.compose_header.setText("\U0001f4dd  New Note")
        self.compose_title.clear()
        self.tag_input.clear()
        self.compose_content.clear()
        self.tag_suggestions.hide()
        self._rebuild_tag_chips()
        self._clear_tx_list()
        self._update_linked_summary()

    # ── Tags ──
    def _add_tag_from_input(self):
        tag = self.tag_input.text().strip().lower().replace(" ", "_")
        if not tag or tag in self._composer_tags:
            self.tag_input.clear(); return
        # Auto-create in lookup if new
        existing_tags = [t["display_name"].lower() for t in self.lu.list_tags()]
        if tag not in existing_tags and tag.replace("_", " ") not in existing_tags:
            try: self.lu.add_tag(tag, tag.replace("_", " ").title())
            except: pass
        self._composer_tags.append(tag)
        self.tag_input.clear()
        self.tag_suggestions.hide()
        self._rebuild_tag_chips()

    def _update_tag_suggestions(self, text):
        current = text.strip().lower()
        if len(current) < 1:
            self.tag_suggestions.hide(); return
        matches = [t for t in self.lu.list_tags() if current in t["display_name"].lower()]
        self.tag_suggestions.blockSignals(True)
        self.tag_suggestions.clear()
        for t in matches[:6]:
            self.tag_suggestions.addItem(t["display_name"], t["display_name"])
        if current and not any(t["display_name"].lower() == current for t in matches):
            self.tag_suggestions.addItem(f"\uff0b Create \"{current}\"", current)
        self.tag_suggestions.blockSignals(False)
        self.tag_suggestions.setVisible(self.tag_suggestions.count() > 0)

    def _apply_tag_suggestion(self, idx):
        data = self.tag_suggestions.currentData()
        if not data: return
        tag = data.strip().lower().replace(" ", "_")
        if tag and tag not in self._composer_tags:
            self._composer_tags.append(tag)
        self.tag_input.clear()
        self.tag_suggestions.hide()
        self._rebuild_tag_chips()

    def _remove_tag(self, tag):
        if tag in self._composer_tags:
            self._composer_tags.remove(tag)
            self._rebuild_tag_chips()

    def _rebuild_tag_chips(self):
        while self._tag_chip_lay.count():
            itm = self._tag_chip_lay.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()
        for tag in self._composer_tags:
            chip = _make_tag_chip(tag, removable=True, on_remove=lambda t=tag: self._remove_tag(t))
            self._tag_chip_lay.addWidget(chip)

    # ── Transaction picker — full _tx_card with checkbox overlay ──
    def _populate_account_combo(self):
        self.tx_account_cb.blockSignals(True)
        self.tx_account_cb.clear()
        self.tx_account_cb.addItem("ALL Accounts", None)
        if self.acc:
            for a in self.acc.list_active():
                self.tx_account_cb.addItem(a["display_name"], a["account_id"])
        self.tx_account_cb.blockSignals(False)

    def _clear_tx_list(self):
        while self.tx_list_lay.count():
            itm = self.tx_list_lay.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()

    def _load_tx_picker(self):
        self._clear_tx_list()
        self._populate_account_combo()
        d_from = self.tx_from.date().toString("yyyy-MM-dd")
        d_to = self.tx_to.date().toString("yyyy-MM-dd")
        tx_type = None if self.tx_type_cb.currentText() == "ALL" else self.tx_type_cb.currentText()
        account_id = self.tx_account_cb.currentData()
        rows = self.tx.list_filters(account_id=account_id, tx_type=tx_type,
                                    date_from=d_from, date_to=d_to, limit=200)
        search = self.tx_search.text().strip().lower()
        if search:
            rows = [r for r in rows if search in (r.get("person_org") or "").lower()
                    or search in (r.get("description") or "").lower()]

        if not rows:
            lbl = QLabel("No transactions found.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.tx_list_lay.addWidget(lbl)
            return

        for tx in rows:
            # Wrap _tx_card with a clickable checkbox overlay
            wrapper = QFrame()
            wrapper.setStyleSheet(f"QFrame{{background:transparent;border:none;}}")
            wl = QHBoxLayout(wrapper)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setSpacing(6)

            # Checkbox
            is_linked = tx["id"] in self.linked_ids
            chk = QPushButton("\u2713" if is_linked else "\u25CB")
            chk.setFixedSize(30, 30)
            chk.setStyleSheet(
                f"QPushButton{{background:{C['accent'] if is_linked else C['surface']};"
                f"color:{'white' if is_linked else C['text3']};"
                f"border:2px solid {C['accent'] if is_linked else C['border']};"
                f"border-radius:15px;font-size:14px;font-weight:700;}}"
                f"QPushButton:hover{{background:{C['accent']};color:white;border-color:{C['accent']};}}")
            chk.setCursor(QCursor(Qt.PointingHandCursor))
            tid = tx["id"]
            chk.clicked.connect(lambda _, t=tid: self._toggle_link(t))
            wl.addWidget(chk)

            # Full _tx_card
            card = _tx_card(tx)
            wl.addWidget(card, 1)

            self.tx_list_lay.addWidget(wrapper)

    def _toggle_link(self, tid):
        if tid in self.linked_ids:
            self.linked_ids.discard(tid)
        else:
            self.linked_ids.add(tid)
        self._update_linked_summary()
        self._load_tx_picker()

    def _update_linked_summary(self):
        if not self.linked_ids:
            self.linked_summary_lbl.setText("No transactions linked.")
            return
        net = 0.0
        for tid in self.linked_ids:
            t = self.tx.get(tid)
            if t:
                net += t["amount"] if t["tx_type"] == "CREDIT" else -t["amount"]
        self.linked_summary_lbl.setText(
            f"Linked: {len(self.linked_ids)} transaction(s) \u00b7 Net: {fmt_money(net)}")

    def _save_note(self):
        title = self.compose_title.text().strip()
        tags = ", ".join(self._composer_tags)
        content = self.compose_content.toPlainText().strip()
        if not title:
            QMessageBox.warning(self, "Missing Title", "Please enter a title.")
            return
        # Duplicate check
        existing = self.nr.list_active(title)
        for n in existing:
            if n.get("title", "").lower() == title.lower() and n["id"] != (self.edit_note_id or ""):
                QMessageBox.warning(self, "Duplicate", f"A note titled \"{title}\" already exists.")
                return
        linked = sorted(self.linked_ids)
        if self.edit_note_id:
            self.nr.update(self.edit_note_id, title=title, tags=tags,
                           content=content, linked_transaction_ids=linked)
        else:
            self.nr.create(title=title, tags=tags,
                           content=content, linked_transaction_ids=linked)
        self._goto(0)

    # ─────────────── PAGE 3: Trash ───────────────
    def _build_trash_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)
        header = QLabel("\U0001f5d1\ufe0f  Trash & Recovery")
        header.setStyleSheet(f"font-size:18px;font-weight:800;color:{C['red']};")
        lay.addWidget(header)
        info = QLabel("Recover deleted notes or remove them permanently.")
        info.setStyleSheet(f"color:{C['text3']};font-size:12px;")
        lay.addWidget(info)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self.trash_lay = QVBoxLayout(inner)
        self.trash_lay.setSpacing(8)
        self.trash_lay.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return page

    def _load_trash(self):
        while self.trash_lay.count():
            itm = self.trash_lay.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()
        rows = self.nr.list_trash()
        if not rows:
            lbl = QLabel("Trash is empty.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:13px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.trash_lay.addWidget(lbl)
            return
        for r in rows:
            row = QFrame()
            row.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};"
                              f"border-radius:10px;}}QLabel{{background:transparent;border:none;}}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(16, 10, 16, 10)
            rl.setSpacing(12)
            info_col = QVBoxLayout(); info_col.setSpacing(2)
            t = QLabel(r.get("title") or "Untitled")
            t.setStyleSheet(f"color:{C['text']};font-size:13px;font-weight:600;")
            info_col.addWidget(t)
            tags = QLabel(r.get("tags") or "No tags")
            tags.setStyleSheet(f"color:{C['text3']};font-size:11px;")
            info_col.addWidget(tags)
            rl.addLayout(info_col, 1)
            deleted = QLabel((r.get("deleted_at") or "")[:16])
            deleted.setStyleSheet(f"color:{C['text3']};font-size:11px;")
            rl.addWidget(deleted)
            recover_btn = QPushButton("Recover")
            recover_btn.setStyleSheet(_btn_primary())
            recover_btn.setCursor(QCursor(Qt.PointingHandCursor))
            uid = r["uuid"]
            recover_btn.clicked.connect(lambda _, u=uid: self._recover(u))
            rl.addWidget(recover_btn)
            del_btn = QPushButton("Delete Forever")
            del_btn.setStyleSheet(_btn_danger())
            del_btn.setCursor(QCursor(Qt.PointingHandCursor))
            del_btn.clicked.connect(lambda _, u=uid: self._perm_delete(u))
            rl.addWidget(del_btn)
            self.trash_lay.addWidget(row)
        self.trash_lay.addStretch()

    def _recover(self, uid):
        self.nr.restore(uid)
        self._load_trash(); self._load_notes()

    def _perm_delete(self, uid):
        reply = QMessageBox.question(self, "Delete Forever",
            "This cannot be undone. Delete permanently?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.nr.perm_delete(uid)
            self._load_trash()

    # ─────────────── PRINT ───────────────
    def _print_single_note(self, note_id):
        """Print a single note as PDF — same popup style as DB tab."""
        note = self.nr.get(note_id)
        if not note: return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Note PDF",
            f"Note_{(note.get('title') or 'untitled').replace(' ','_')}.pdf",
            "PDF (*.pdf)")
        if not filepath: return
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            doc = SimpleDocTemplate(filepath, pagesize=A4,
                                    leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
            styles = getSampleStyleSheet()
            story = []
            # Title
            story.append(Paragraph(f"<b>{note.get('title','Untitled')}</b>", styles["Title"]))
            story.append(Spacer(1, 8))
            # Tags
            tags = note.get("tags") or ""
            if tags:
                story.append(Paragraph(f"<i>Tags: {tags}</i>", styles["Normal"]))
                story.append(Spacer(1, 8))
            # Content
            content = note.get("content") or ""
            if content:
                story.append(Paragraph("<b>Content:</b>", styles["Heading3"]))
                for line in content.split("\n"):
                    story.append(Paragraph(line or "&nbsp;", styles["Normal"]))
                story.append(Spacer(1, 12))
            # Linked transactions — full details
            ids = _linked_ids(note)
            if ids:
                story.append(Paragraph(f"<b>Linked Transactions ({len(ids)}):</b>", styles["Heading3"]))
                story.append(Spacer(1, 4))
                for tid in ids:
                    tx = self.tx.get(tid)
                    if tx:
                        tx_type = tx.get("tx_type", "")
                        prefix = "\u2212" if tx_type == "DEBIT" else "+"
                        parts = [
                            tx.get("tx_date", ""),
                            tx.get("person_org") or tx.get("description") or "",
                            f"{prefix}{fmt_money(tx['amount'])}",
                            tx.get("cat_name") or "",
                            tx.get("method_name") or "",
                            tx.get("account_name") or "",
                        ]
                        line = "  \u00b7  ".join(p for p in parts if p)
                        story.append(Paragraph(line, styles["Normal"]))
                story.append(Spacer(1, 8))
            # Metadata
            story.append(Paragraph(f"<i>Created: {note.get('created_at','')[:16]}</i>", styles["Normal"]))
            if note.get("updated_at"):
                story.append(Paragraph(f"<i>Updated: {note.get('updated_at','')[:16]}</i>", styles["Normal"]))
            doc.build(story)
            # Same popup as DB tab
            self._show_pdf_done(filepath)
        except ImportError:
            QMessageBox.warning(self, "Missing", "Install reportlab: pip install reportlab")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _show_pdf_done(self, filepath):
        """Same popup as DB tab — 'Open PDF' button."""
        dlg = QMessageBox(self)
        dlg.setWindowTitle("PDF Saved")
        dlg.setIcon(QMessageBox.Information)
        dlg.setText(f"PDF saved successfully.\n\n{filepath}")
        open_btn = dlg.addButton("  Open PDF  ", QMessageBox.AcceptRole)
        dlg.addButton("Close", QMessageBox.RejectRole)
        dlg.exec_()
        if dlg.clickedButton() == open_btn:
            try:
                if sys.platform == "win32":
                    os.startfile(filepath)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", filepath])
                else:
                    subprocess.Popen(["xdg-open", filepath])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open PDF:\n{e}")
