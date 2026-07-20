"""Notes tab — Create, edit, search, tag chips, linked transactions, trash, print."""
import json
import uuid as _uuid
from datetime import date

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QLineEdit, QTextEdit, QFrame,
                              QScrollArea, QStackedWidget, QMessageBox,
                              QComboBox, QDateEdit, QSizePolicy, QLayout,
                              QFileDialog)
from PyQt5.QtCore import Qt, QDate, pyqtSignal, QPoint, QRect, QSize
from PyQt5.QtGui import QCursor

from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tx_card, _day_header


# ═══════════════════════════════════════════════
# FLOW LAYOUT (for tag chips)
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

TAG_COLORS = ["#4F46E5", "#0EA5E9", "#059669", "#D97706", "#EC4899", "#8B5CF6", "#DC2626"]

def _tag_color(tag_text):
    h = sum(ord(c) for c in tag_text)
    return TAG_COLORS[h % len(TAG_COLORS)]


def _linked_ids(note):
    raw = note.get("linked_transaction_ids")
    if not raw:
        return []
    try:
        ids = json.loads(raw)
        return ids if isinstance(ids, list) else []
    except:
        return []


def _btn_primary():
    return f"QPushButton{{background:{C['accent']};color:white;border:none;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:700;}}QPushButton:hover{{background:#4338CA;}}"

def _btn_danger():
    return f"QPushButton{{background:{C['red']};color:white;border:none;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:700;}}QPushButton:hover{{background:#B91C1C;}}"

def _btn_ghost():
    return f"QPushButton{{background:transparent;color:{C['text2']};border:1px solid {C['border']};border-radius:8px;padding:8px 16px;font-size:13px;font-weight:600;}}QPushButton:hover{{border-color:{C['accent']};color:{C['accent']};}}"

def _input_css():
    return f"background:{C['surface']};border:1.5px solid {C['border']};border-radius:8px;padding:8px 12px;font-size:13px;"


# ═══════════════════════════════════════════════
# TAG CHIP WIDGET
# ═══════════════════════════════════════════════

def _make_tag_chip(text, removable=False, on_remove=None):
    """Create a styled tag chip. If removable, shows ✕ button."""
    color = _tag_color(text)
    chip = QPushButton(f" #{text} " + ("✕" if removable else ""))
    chip.setStyleSheet(
        f"QPushButton{{background:{color}18;color:{color};border:1px solid {color}40;"
        f"border-radius:12px;padding:2px 8px;font-size:11px;font-weight:600;}}"
        f"QPushButton:hover{{background:{color}30;}}")
    chip.setCursor(QCursor(Qt.PointingHandCursor) if removable else Qt.ArrowCursor)
    chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    if removable and on_remove:
        chip.clicked.connect(on_remove)
    return chip


# ═══════════════════════════════════════════════
# NOTE CARD — clean expand/collapse
# ═══════════════════════════════════════════════

class NoteCard(QFrame):
    clicked = pyqtSignal(str)
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, note, tx_repo=None, parent=None):
        super().__init__(parent)
        self.note = note
        self.tx_repo = tx_repo
        self.expanded = False
        self._build()

    def _build(self):
        tags_str = self.note.get("tags") or ""
        first_tag = tags_str.split(",")[0].strip() if tags_str else ""
        accent = _tag_color(first_tag) if first_tag else C['border2']

        self.setStyleSheet(f"""
            QFrame {{ background:{C['surface']}; border:1px solid {C['border2']};
                       border-left:4px solid {accent}; border-radius:12px; }}
            QFrame:hover {{ border-color:{accent}; }}
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
            badge = QLabel(f"🔗 {len(ids)}")
            badge.setStyleSheet(f"color:{C['accent']};font-size:11px;font-weight:700;"
                                f"background:{C['accent_bg']};border-radius:8px;padding:2px 8px;")
            top.addWidget(badge)
        lay.addLayout(top)

        # Tags as chips (collapsed: first 3 only)
        tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
        if tags_list:
            chip_row = QHBoxLayout()
            chip_row.setSpacing(4)
            for t in tags_list[:3]:
                chip_row.addWidget(_make_tag_chip(t))
            if len(tags_list) > 3:
                more = QLabel(f"+{len(tags_list) - 3}")
                more.setStyleSheet(f"color:{C['text3']};font-size:11px;")
                chip_row.addWidget(more)
            chip_row.addStretch()
            lay.addLayout(chip_row)

        # Expanded content
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
            content_lbl.setMinimumHeight(60)
            exp_lay.addWidget(content_lbl)

        # Linked transactions using _tx_card style
        if ids and self.tx_repo:
            link_title = QLabel(f"🔗 Linked Transactions ({len(ids)})")
            link_title.setStyleSheet(f"color:{C['text2']};font-size:12px;font-weight:700;")
            exp_lay.addWidget(link_title)
            for tid in ids:
                tx = self.tx_repo.get(tid)
                if tx:
                    exp_lay.addWidget(_tx_card(tx))

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        edit_btn = QPushButton("✏️ Edit")
        edit_btn.setStyleSheet(_btn_ghost())
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.note["id"]))
        btn_row.addWidget(edit_btn)
        del_btn = QPushButton("🗑️ Delete")
        del_btn.setStyleSheet(_btn_ghost())
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.note["id"]))
        btn_row.addWidget(del_btn)
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
        self._composer_tags = []  # list of tag strings
        self._build()
        self.refresh()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(16)

        heading = QLabel("📋  Notes")
        heading.setStyleSheet(f"font-size:22px;font-weight:800;color:{C['text']};")
        outer.addWidget(heading)

        # Nav buttons
        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)
        self.btn_all = QPushButton("All Notes")
        self.btn_new = QPushButton("＋ New Note")
        self.btn_trash = QPushButton("🗑️ Trash")
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

    # ──────────────────────────────
    # PAGE 1: All Notes
    # ──────────────────────────────
    def _build_all_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        # Search bar
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  Search notes by title or tag…")
        self.search_box.setMinimumHeight(38)
        self.search_box.setStyleSheet(_input_css())
        self.search_box.textChanged.connect(self._load_notes)
        lay.addWidget(self.search_box)

        # Print button
        print_row = QHBoxLayout()
        print_row.addStretch()
        print_btn = QPushButton("🖨️ Print Notes")
        print_btn.setStyleSheet(_btn_ghost())
        print_btn.setCursor(QCursor(Qt.PointingHandCursor))
        print_btn.clicked.connect(self._print_notes)
        print_row.addWidget(print_btn)
        lay.addLayout(print_row)

        # Notes list
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
        if not note:
            return
        self._reset_composer()
        self.edit_note_id = note_id
        self.compose_title.setText(note.get("title") or "")
        # Restore tag chips
        tags_str = note.get("tags") or ""
        self._composer_tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        self._rebuild_tag_chips()
        self.compose_content.setPlainText(note.get("content") or "")
        self.linked_ids = set(_linked_ids(note))
        self._update_linked_summary()
        self._load_tx_picker()
        self.compose_header.setText("✏️  Edit Note")
        self._goto(1)

    # ──────────────────────────────
    # PAGE 2: Compose
    # ──────────────────────────────
    def _build_compose_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        self.compose_header = QLabel("📝  New Note")
        self.compose_header.setStyleSheet(f"font-size:18px;font-weight:800;color:{C['accent']};")
        lay.addWidget(self.compose_header)

        # Title
        self.compose_title = QLineEdit()
        self.compose_title.setPlaceholderText("Title")
        self.compose_title.setMinimumHeight(38)
        self.compose_title.setStyleSheet(_input_css())
        lay.addWidget(self.compose_title)

        # Tags — chip-based input
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
        self.tag_input.setPlaceholderText("Type a tag and press Enter…")
        self.tag_input.setMinimumHeight(34)
        self.tag_input.setStyleSheet(_input_css())
        self.tag_input.returnPressed.connect(self._add_tag_from_input)
        tag_input_row.addWidget(self.tag_input, 1)

        # Tag suggestions dropdown
        self.tag_suggestions = QComboBox()
        self.tag_suggestions.setMinimumHeight(34)
        self.tag_suggestions.setMaximumWidth(200)
        self.tag_suggestions.setStyleSheet(_input_css())
        self.tag_suggestions.hide()
        tag_input_row.addWidget(self.tag_suggestions)
        lay.addLayout(tag_input_row)

        # Content
        self.compose_content = QTextEdit()
        self.compose_content.setPlaceholderText("Write your note here…")
        self.compose_content.setMinimumHeight(120)
        self.compose_content.setStyleSheet(_input_css())
        lay.addWidget(self.compose_content)

        # ── Link Transactions ──
        link_frame = QFrame()
        link_frame.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        link_lay = QVBoxLayout(link_frame)
        link_lay.setContentsMargins(16, 12, 16, 12)
        link_lay.setSpacing(8)

        link_header = QLabel("🔗  Link Transactions (optional)")
        link_header.setStyleSheet(f"font-weight:700;color:{C['text2']};font-size:13px;")
        link_lay.addWidget(link_header)

        # Filters
        filt = QHBoxLayout()
        filt.setSpacing(6)
        self.tx_from = QDateEdit(); self.tx_from.setCalendarPopup(True)
        self.tx_from.setDate(QDate.currentDate().addMonths(-1))
        self.tx_from.setMinimumHeight(32); self.tx_from.setMaximumWidth(120)
        filt.addWidget(self.tx_from)
        filt.addWidget(QLabel("to"))
        self.tx_to = QDateEdit(); self.tx_to.setCalendarPopup(True)
        self.tx_to.setDate(QDate.currentDate())
        self.tx_to.setMinimumHeight(32); self.tx_to.setMaximumWidth(120)
        filt.addWidget(self.tx_to)
        self.tx_type_cb = QComboBox(); self.tx_type_cb.addItems(["ALL", "DEBIT", "CREDIT"])
        self.tx_type_cb.setMinimumHeight(32); self.tx_type_cb.setMaximumWidth(90)
        filt.addWidget(self.tx_type_cb)
        self.tx_search = QLineEdit(); self.tx_search.setPlaceholderText("Search…")
        self.tx_search.setMinimumHeight(32); self.tx_search.setStyleSheet(_input_css())
        filt.addWidget(self.tx_search, 1)
        load_btn = QPushButton("⟳ Load"); load_btn.setStyleSheet(_btn_primary())
        load_btn.setMinimumHeight(32); load_btn.setCursor(QCursor(Qt.PointingHandCursor))
        load_btn.clicked.connect(self._load_tx_picker)
        filt.addWidget(load_btn)
        link_lay.addLayout(filt)

        # Transaction list (scroll area with _tx_card style)
        self.tx_scroll = QScrollArea()
        self.tx_scroll.setWidgetResizable(True)
        self.tx_scroll.setFrameShape(QFrame.NoFrame)
        self.tx_scroll.setMaximumHeight(260)
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
        save_btn = QPushButton("💾  Save Note")
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
        self.compose_header.setText("📝  New Note")
        self.compose_title.clear()
        self.tag_input.clear()
        self.compose_content.clear()
        self.tag_suggestions.hide()
        self._rebuild_tag_chips()
        self._clear_tx_list()
        self._update_linked_summary()

    # ── Tag chip management ──
    def _add_tag_from_input(self):
        tag = self.tag_input.text().strip().lower().replace(" ", "_")
        if not tag or tag in self._composer_tags:
            self.tag_input.clear(); return
        self._composer_tags.append(tag)
        self.tag_input.clear()
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

    # ── Transaction picker ──
    def _clear_tx_list(self):
        while self.tx_list_lay.count():
            itm = self.tx_list_lay.takeAt(0)
            if itm.widget():
                itm.widget().deleteLater()

    def _load_tx_picker(self):
        self._clear_tx_list()
        d_from = self.tx_from.date().toString("yyyy-MM-dd")
        d_to = self.tx_to.date().toString("yyyy-MM-dd")
        tx_type = None if self.tx_type_cb.currentText() == "ALL" else self.tx_type_cb.currentText()
        rows = self.tx.list_filters(tx_type=tx_type, date_from=d_from, date_to=d_to, limit=200)
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
            row = QFrame()
            row.setStyleSheet(f"QFrame{{background:{C['surface2']};border:1px solid {C['border']};"
                              f"border-radius:8px;}}QLabel{{background:transparent;border:none;}}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 4, 8, 4)
            rl.setSpacing(8)

            # Checkbox
            chk = QPushButton("✓" if tx["id"] in self.linked_ids else "○")
            chk.setFixedSize(28, 28)
            is_linked = tx["id"] in self.linked_ids
            chk.setStyleSheet(
                f"QPushButton{{background:{C['accent'] if is_linked else C['surface']};"
                f"color:{'white' if is_linked else C['text3']};"
                f"border:1px solid {C['accent'] if is_linked else C['border']};"
                f"border-radius:14px;font-size:12px;font-weight:700;}}"
                f"QPushButton:hover{{background:{C['accent']};color:white;}}")
            chk.setCursor(QCursor(Qt.PointingHandCursor))
            tid = tx["id"]
            chk.clicked.connect(lambda _, t=tid: self._toggle_link(t))
            rl.addWidget(chk)

            # Transaction info
            info = QLabel(f"{tx.get('tx_date','')}  ·  {tx.get('person_org') or tx.get('description') or ''}")
            info.setStyleSheet(f"color:{C['text']};font-size:12px;")
            rl.addWidget(info, 1)

            amt_color = C['red'] if tx["tx_type"] == "DEBIT" else C['green']
            prefix = "−" if tx["tx_type"] == "DEBIT" else "+"
            amt = QLabel(f"{prefix}{fmt_money(tx['amount'])}")
            amt.setStyleSheet(f"color:{amt_color};font-size:13px;font-weight:700;")
            rl.addWidget(amt)

            self.tx_list_lay.addWidget(row)

    def _toggle_link(self, tid):
        if tid in self.linked_ids:
            self.linked_ids.discard(tid)
        else:
            self.linked_ids.add(tid)
        self._update_linked_summary()
        self._load_tx_picker()  # refresh checkboxes

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
            f"Linked: {len(self.linked_ids)} transaction(s) · Net: {fmt_money(net)}")

    def _save_note(self):
        title = self.compose_title.text().strip()
        tags = ", ".join(self._composer_tags)
        content = self.compose_content.toPlainText().strip()
        if not title:
            QMessageBox.warning(self, "Missing Title", "Please enter a title.")
            return
        linked = sorted(self.linked_ids)
        if self.edit_note_id:
            self.nr.update(self.edit_note_id, title=title, tags=tags,
                           content=content, linked_transaction_ids=linked)
        else:
            self.nr.create(title=title, tags=tags,
                           content=content, linked_transaction_ids=linked)
        self._goto(0)

    # ──────────────────────────────
    # PAGE 3: Trash
    # ──────────────────────────────
    def _build_trash_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        header = QLabel("🗑️  Trash & Recovery")
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

            # Title + tags
            info_col = QVBoxLayout()
            info_col.setSpacing(2)
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
        self._load_trash()
        self._load_notes()

    def _perm_delete(self, uid):
        reply = QMessageBox.question(self, "Delete Forever",
            "This cannot be undone. Delete permanently?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.nr.perm_delete(uid)
            self._load_trash()

    # ──────────────────────────────
    # PRINT
    # ──────────────────────────────
    def _print_notes(self):
        notes = self.nr.list_active()
        if not notes:
            QMessageBox.warning(self, "No Notes", "Nothing to print.")
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Notes PDF", f"Notes_{date.today().isoformat()}.pdf", "PDF (*.pdf)")
        if not filepath:
            return
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            doc = SimpleDocTemplate(filepath, pagesize=A4,
                                    leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
            styles = getSampleStyleSheet()
            story = []
            for n in notes:
                story.append(Paragraph(f"<b>{n.get('title','Untitled')}</b>", styles["Heading2"]))
                tags = n.get("tags") or ""
                if tags:
                    story.append(Paragraph(f"<i>Tags: {tags}</i>", styles["Normal"]))
                content = n.get("content") or ""
                if content:
                    for line in content.split("\n"):
                        story.append(Paragraph(line, styles["Normal"]))
                story.append(Spacer(1, 16))
            doc.build(story)
            QMessageBox.information(self, "Done", f"Notes saved to:\n{filepath}")
        except ImportError:
            QMessageBox.warning(self, "Missing", "Install reportlab: pip install reportlab")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
