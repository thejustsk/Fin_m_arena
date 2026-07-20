"""Notes tab — Create, edit, search, tag chips, linked transactions, trash, print."""
import json
import uuid as _uuid
import os, subprocess, sys, hashlib
from datetime import datetime, date, timedelta
from collections import OrderedDict

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QLineEdit, QTextEdit, QFrame,
                              QScrollArea, QStackedWidget, QMessageBox,
                              QComboBox, QDateEdit, QSizePolicy, QLayout,
                              QFileDialog, QDoubleSpinBox,
                              QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt, QDate, QPoint, pyqtSignal, QRect, QSize
from PyQt5.QtGui import QCursor, QColor

from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tx_card, _day_header, FILTER_FIELDS


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

def _hex_to_rgba(hex_color, alpha):
    """Convert hex color to rgba string."""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def _note_accent(note):
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


def _make_tag_chip(text, accent_color=None, removable=False, on_remove=None):
    """Tag chip: solid accent bg with white text."""
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
        # Full border with accent color, 8% opacity background
        self.setStyleSheet(f"""
            QFrame {{
                background: {_hex_to_rgba(a, 0.08)};
                border: 1.5px solid {a};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border-color: {a};
                background: {_hex_to_rgba(a, 0.12)};
            }}
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

        # Tags with accent color border + 8% bg
        tags_str = self.note.get("tags") or ""
        tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
        if tags_list:
            chip_row = QHBoxLayout()
            chip_row.setSpacing(4)
            for t in tags_list:
                chip_row.addWidget(_make_tag_chip(t, accent_color=a))
            chip_row.addStretch()
            lay.addLayout(chip_row)

        # Expanded content
        self._expand_area = QWidget()
        self._expand_area.setStyleSheet("background:transparent;border:none;")
        exp_lay = QVBoxLayout(self._expand_area)
        exp_lay.setContentsMargins(0, 4, 0, 0)
        exp_lay.setSpacing(8)

        content_text = self.note.get("content") or ""
        if content_text:
            content_lbl = QLabel(content_text)
            content_lbl.setWordWrap(True)
            content_lbl.setStyleSheet(f"color:{C['text2']};font-size:12px;background:{C['surface2']};"
                                      f"border-radius:8px;padding:10px;")
            content_lbl.setMinimumHeight(50)
            exp_lay.addWidget(content_lbl)

        # Linked transactions grouped by date
        if ids and self.tx_repo:
            link_title = QLabel(f"\U0001f517 Linked Transactions ({len(ids)})")
            link_title.setStyleSheet(f"color:{C['text2']};font-size:12px;font-weight:700;")
            exp_lay.addWidget(link_title)

            txns = []
            for tid in ids:
                tx = self.tx_repo.get_detailed(tid) if hasattr(self.tx_repo, 'get_detailed') else self.tx_repo.get(tid)
                if tx: txns.append(tx)

            if txns:
                by_date = OrderedDict()
                for tx in sorted(txns, key=lambda t: t["tx_date"], reverse=True):
                    d = tx["tx_date"]
                    if d not in by_date: by_date[d] = []
                    by_date[d].append(tx)
                for d_str, day_txns in by_date.items():
                    try:
                        exp_lay.addWidget(_day_header(date.fromisoformat(d_str).strftime("%A, %d %b")))
                    except:
                        exp_lay.addWidget(_day_header(d_str))
                    for tx in day_txns:
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
        self.clicked.emit(self.note["id"]); event.accept()

    def expand(self):
        self.expanded = True; self._expand_area.show()

    def collapse(self):
        self.expanded = False; self._expand_area.hide()


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
        self.acct = repos.get("accounts")
        self.edit_note_id = None
        self.linked_ids = set()
        self._loading_tx = False
        self._composer_tags = []
        self._fv = []
        self._all_filtered_ids = []  # for select all
        self._build()
        self.refresh()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(16)

        heading = QLabel("\U0001f4cb  Notes")
        heading.setStyleSheet(f"font-size:22px;font-weight:800;color:{C['text']};")
        outer.addWidget(heading)

        nav_row = QHBoxLayout(); nav_row.setSpacing(8)
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
        self._load_notes(); self._load_trash()

    # ─────────────── PAGE 1: All Notes ───────────────
    def _build_all_page(self):
        page = QWidget()
        lay = QVBoxLayout(page); lay.setSpacing(12)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("\U0001f50d  Search notes by title or tag\u2026")
        self.search_box.setMinimumHeight(38)
        self.search_box.setStyleSheet(_input_css())
        self.search_box.textChanged.connect(self._load_notes)
        lay.addWidget(self.search_box)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget(); inner.setStyleSheet("background:transparent;")
        self.notes_lay = QVBoxLayout(inner)
        self.notes_lay.setSpacing(10); self.notes_lay.setAlignment(Qt.AlignTop)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return page

    def _load_notes(self):
        for i in reversed(range(self.notes_lay.count())):
            item = self.notes_lay.itemAt(i)
            if item.widget(): item.widget().deleteLater()
        notes = self.nr.list_active(self.search_box.text().strip() or None)
        if not notes:
            empty = QLabel("No notes yet. Click \"+ New Note\" to create one.")
            empty.setStyleSheet(f"color:{C['text3']};font-size:13px;padding:24px;")
            empty.setAlignment(Qt.AlignCenter)
            self.notes_lay.addWidget(empty); return
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
        reply = QMessageBox.question(self, "Delete Note", "Move to Trash?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.nr.soft_delete(note_id)
            self._load_notes(); self._load_trash()

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

    # ─────────────── PAGE 2: Compose (two-column) ───────────────
    def _build_compose_page(self):
        page = QWidget()
        lay = QVBoxLayout(page); lay.setSpacing(12)

        self.compose_header = QLabel("\U0001f4dd  New Note")
        self.compose_header.setStyleSheet(f"font-size:18px;font-weight:800;color:{C['accent']};")
        lay.addWidget(self.compose_header)

        cols = QHBoxLayout(); cols.setSpacing(16)

        # ── LEFT: Note content ──
        left = QWidget(); left.setStyleSheet("background:transparent;")
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0); left_lay.setSpacing(10)

        self.compose_title = QLineEdit()
        self.compose_title.setPlaceholderText("Title")
        self.compose_title.setMinimumHeight(38)
        self.compose_title.setStyleSheet(_input_css())
        self.compose_title.returnPressed.connect(lambda: self.tag_input.setFocus())
        left_lay.addWidget(self.compose_title)

        # Tags
        tags_label = QLabel("Tags")
        tags_label.setStyleSheet(f"color:{C['text2']};font-size:12px;font-weight:600;")
        left_lay.addWidget(tags_label)
        self._tag_chip_container = QWidget()
        self._tag_chip_container.setStyleSheet("background:transparent;border:none;")
        self._tag_chip_lay = FlowLayout(self._tag_chip_container, hSpacing=4, vSpacing=4)
        left_lay.addWidget(self._tag_chip_container)

        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Type tag + Enter, or pick below\u2026")
        self.tag_input.setMinimumHeight(34)
        self.tag_input.setStyleSheet(_input_css())
        self.tag_input.returnPressed.connect(self._add_tag_from_input)
        self.tag_input.textChanged.connect(self._update_tag_suggestions)
        left_lay.addWidget(self.tag_input)

        # Tag suggestions (QListWidget — keyboard navigable)
        self.tag_suggestions = QListWidget()
        self.tag_suggestions.setMaximumHeight(100)
        self.tag_suggestions.setStyleSheet(
            f"QListWidget{{background:{C['surface']};border:1px solid {C['border']};border-radius:8px;font-size:12px;}}"
            f"QListWidget::item{{padding:5px 8px;}}"
            f"QListWidget::item:selected{{background:{C['accent_bg']};color:{C['accent']};}}"
            f"QListWidget::item:hover{{background:{C['accent_bg']};}}")
        self.tag_suggestions.itemClicked.connect(self._apply_tag_suggestion)
        self.tag_input.installEventFilter(self)
        self.tag_suggestions.installEventFilter(self)
        self.tag_suggestions.hide()
        left_lay.addWidget(self.tag_suggestions)

        # Content
        self.compose_content = QTextEdit()
        self.compose_content.setPlaceholderText("Write your note here\u2026")
        self.compose_content.setMinimumHeight(160)
        self.compose_content.setStyleSheet(_input_css())
        left_lay.addWidget(self.compose_content, 1)

        # Buttons
        btn_row = QHBoxLayout(); btn_row.addStretch()
        cancel_btn = QPushButton("Cancel"); cancel_btn.setStyleSheet(_btn_ghost())
        cancel_btn.clicked.connect(lambda: self._goto(0)); btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("\U0001f4be  Save Note"); save_btn.setStyleSheet(_btn_primary())
        save_btn.setCursor(QCursor(Qt.PointingHandCursor))
        save_btn.clicked.connect(self._save_note); btn_row.addWidget(save_btn)
        left_lay.addLayout(btn_row)

        cols.addWidget(left, 1)

        # ── RIGHT: Link Transactions ──
        right = QFrame()
        right.setStyleSheet(f"QFrame{{background:#fff;border:1px solid #E5E7EB;border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(14, 12, 14, 12); right_lay.setSpacing(8)

        link_header = QLabel("\U0001f517  Link Transactions")
        link_header.setStyleSheet(f"font-weight:700;color:{C['text2']};font-size:13px;")
        right_lay.addWidget(link_header)

        # Filter bar
        bar = QFrame()
        bar.setStyleSheet("QFrame{background:#fff;border:1px solid #E5E7EB;border-radius:10px;padding:6px 10px;}")
        filt = QVBoxLayout(bar)
        filt.setContentsMargins(4, 4, 4, 4); filt.setSpacing(6)

        # Row 1: Date range — consistent sizing
        r1 = QHBoxLayout(); r1.setSpacing(6)
        r1.addWidget(QLabel("From"))
        self.tx_from = QDateEdit(); self.tx_from.setCalendarPopup(True)
        self.tx_from.setDate(QDate.currentDate().addMonths(-1))
        self.tx_from.setMinimumHeight(34); self.tx_from.setMinimumWidth(110)
        r1.addWidget(self.tx_from)
        r1.addWidget(QLabel("To"))
        self.tx_to = QDateEdit(); self.tx_to.setCalendarPopup(True)
        self.tx_to.setDate(QDate.currentDate())
        self.tx_to.setMinimumHeight(34); self.tx_to.setMinimumWidth(110)
        r1.addWidget(self.tx_to)
        filt.addLayout(r1)

        # Row 2: Filter field + value — consistent sizing
        r2 = QHBoxLayout(); r2.setSpacing(6)
        self.fc = QComboBox()
        for f in FILTER_FIELDS: self.fc.addItem(f["label"], f["key"])
        self.fc.setMinimumHeight(34); self.fc.setMinimumWidth(120)
        r2.addWidget(self.fc)
        self.fstk = QStackedWidget()
        self.ft_combo = QComboBox(); self.ft_combo.setMinimumHeight(34)
        self.ft_text = QLineEdit(); self.ft_text.setMinimumHeight(34)
        self.ft_text.setStyleSheet(_input_css())
        self.ft_num = QDoubleSpinBox(); self.ft_num.setPrefix("\u20b9 ")
        self.ft_num.setRange(0, 99999999); self.ft_num.setMinimumHeight(34)
        self.fstk.addWidget(self.ft_combo); self.fstk.addWidget(self.ft_text); self.fstk.addWidget(self.ft_num)
        r2.addWidget(self.fstk, 1)
        add_filt_btn = QPushButton("+ Add Filter")
        add_filt_btn.setStyleSheet(_btn_primary())
        add_filt_btn.setMinimumHeight(34); add_filt_btn.setMinimumWidth(80)
        add_filt_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_filt_btn.clicked.connect(self._add_f)
        r2.addWidget(add_filt_btn)
        filt.addLayout(r2)

        # Row 3: Actions — consistent sizing
        r3 = QHBoxLayout(); r3.setSpacing(6)
        self._filter_stats = QLabel("")
        self._filter_stats.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        r3.addWidget(self._filter_stats)
        r3.addStretch()
        clear_btn = QPushButton("Clear"); clear_btn.setStyleSheet(_btn_ghost())
        clear_btn.setMinimumHeight(30); clear_btn.clicked.connect(self._clear_f)
        r3.addWidget(clear_btn)
        select_all_btn = QPushButton("Select All")
        select_all_btn.setStyleSheet(_btn_ghost())
        select_all_btn.setMinimumHeight(30)
        select_all_btn.setCursor(QCursor(Qt.PointingHandCursor))
        select_all_btn.clicked.connect(self._select_all)
        r3.addWidget(select_all_btn)
        load_btn = QPushButton("\u27f3 Load"); load_btn.setStyleSheet(_btn_primary())
        load_btn.setMinimumHeight(30); load_btn.setCursor(QCursor(Qt.PointingHandCursor))
        load_btn.clicked.connect(self._load_tx_picker); r3.addWidget(load_btn)
        filt.addLayout(r3)

        right_lay.addWidget(bar)

        # Chips
        self._chips_container = QWidget()
        self._chips_container.setStyleSheet("background:transparent;border:none;")
        self._chips_grid = QVBoxLayout(self._chips_container)
        self._chips_grid.setContentsMargins(0, 2, 0, 2); self._chips_grid.setSpacing(2)
        right_lay.addWidget(self._chips_container)

        # Transaction list
        self.tx_scroll = QScrollArea()
        self.tx_scroll.setWidgetResizable(True); self.tx_scroll.setFrameShape(QFrame.NoFrame)
        self.tx_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        tx_inner = QWidget(); tx_inner.setStyleSheet("background:transparent;")
        self.tx_list_lay = QVBoxLayout(tx_inner)
        self.tx_list_lay.setSpacing(4); self.tx_list_lay.setContentsMargins(0, 0, 0, 0)
        self.tx_scroll.setWidget(tx_inner)
        right_lay.addWidget(self.tx_scroll, 1)

        self.linked_summary_lbl = QLabel("No transactions linked.")
        self.linked_summary_lbl.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        right_lay.addWidget(self.linked_summary_lbl)

        cols.addWidget(right, 1)
        lay.addLayout(cols, 1)

        self.fc.currentIndexChanged.connect(self._on_field); self._on_field(0)

        return page

    # Event filter: forward Up/Down from tag_input to suggestions, Enter to apply
    def eventFilter(self, obj, event):
        if obj == self.tag_input and event.type() == event.KeyPress:
            if self.tag_suggestions.isVisible() and self.tag_suggestions.count() > 0:
                if event.key() == Qt.Key_Down:
                    cur = self.tag_suggestions.currentRow()
                    nxt = cur + 1 if cur < self.tag_suggestions.count() - 1 else 0
                    self.tag_suggestions.setCurrentRow(nxt)
                    return True
                elif event.key() == Qt.Key_Up:
                    cur = self.tag_suggestions.currentRow()
                    prv = cur - 1 if cur > 0 else self.tag_suggestions.count() - 1
                    self.tag_suggestions.setCurrentRow(prv)
                    return True
                elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                    item = self.tag_suggestions.currentItem()
                    if item:
                        self._apply_tag_suggestion(item)
                        return True
        if obj == self.tag_suggestions and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                item = self.tag_suggestions.currentItem()
                if item:
                    self._apply_tag_suggestion(item)
                    return True
            elif event.key() == Qt.Key_Escape:
                self.tag_suggestions.hide()
                self.tag_input.setFocus()
                return True
        return super().eventFilter(obj, event)

    def _reset_composer(self):
        self.edit_note_id = None; self.linked_ids = set(); self._composer_tags = []; self._fv = []
        self._all_filtered_ids = []
        self.compose_header.setText("\U0001f4dd  New Note")
        self.compose_title.clear(); self.tag_input.clear(); self.compose_content.clear()
        self.tag_suggestions.hide(); self._rebuild_tag_chips()
        self._clear_tx_list(); self._update_linked_summary(); self._rebuild_chips()

    # ── Tags ──
    def _add_tag_from_input(self):
        tag = self.tag_input.text().strip().lower().replace(" ", "_")
        if not tag or tag in self._composer_tags:
            self.tag_input.clear(); return
        existing_tags = [t["display_name"].lower() for t in self.lu.list_tags()]
        if tag not in existing_tags and tag.replace("_", " ") not in existing_tags:
            try: self.lu.add_tag(tag, tag.replace("_", " ").title())
            except: pass
        self._composer_tags.append(tag)
        self.tag_input.clear(); self.tag_suggestions.hide()
        self._rebuild_tag_chips()

    def _update_tag_suggestions(self, text):
        current = text.strip().lower()
        if len(current) < 1:
            self.tag_suggestions.hide(); return
        matches = [t for t in self.lu.list_tags() if current in t["display_name"].lower()]
        self.tag_suggestions.clear()
        for t in matches[:6]:
            item = QListWidgetItem(t["display_name"])
            item.setData(Qt.UserRole, t["display_name"])
            self.tag_suggestions.addItem(item)
        if current and not any(t["display_name"].lower() == current for t in matches):
            item = QListWidgetItem(f"\uff0b Create \"{current}\"")
            item.setData(Qt.UserRole, current)
            self.tag_suggestions.addItem(item)
        self.tag_suggestions.setVisible(self.tag_suggestions.count() > 0)
        if self.tag_suggestions.count() > 0:
            self.tag_suggestions.setCurrentRow(0)

    def _apply_tag_suggestion(self, item):
        data = item.data(Qt.UserRole)
        if not data: return
        tag = data.strip().lower().replace(" ", "_")
        if tag and tag not in self._composer_tags:
            self._composer_tags.append(tag)
        self.tag_input.clear(); self.tag_suggestions.hide()
        self._rebuild_tag_chips()

    def _remove_tag(self, tag):
        if tag in self._composer_tags:
            self._composer_tags.remove(tag); self._rebuild_tag_chips()

    def _rebuild_tag_chips(self):
        while self._tag_chip_lay.count():
            itm = self._tag_chip_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()
        for tag in self._composer_tags:
            chip = _make_tag_chip(tag, removable=True, on_remove=lambda t=tag: self._remove_tag(t))
            self._tag_chip_lay.addWidget(chip)

    # ── Transaction filter ──
    def _on_field(self, idx):
        key = self.fc.currentData()
        field = next((f for f in FILTER_FIELDS if f["key"] == key), None)
        if not field: return
        if field["type"] == "combo":
            self.fstk.setCurrentIndex(0); self.ft_combo.clear()
            existing = set()
            for fe in self._fv:
                if fe["key"] == key: existing = set(fe["vals"]); break
            if "source" in field:
                src = field["source"]; items = []
                if src == "accounts": items = [(a["display_name"], a["account_id"]) for a in self.acct.list_active()]
                elif src == "categories": items = [(c["display_name"], c["category_id"]) for c in self.lu.list_categories()]
                elif src == "methods": items = [(m["display_name"], m["method_id"]) for m in self.lu.list_methods()]
                elif src == "pf_categories": items = [(pf["display_name"], pf["pf_id"]) for pf in self.lu.list_pf_categories()]
                for text, data in items:
                    if data not in existing: self.ft_combo.addItem(text, data)
            elif "values" in field:
                for v in field["values"]:
                    if v not in existing: self.ft_combo.addItem(v, v)
        elif field["type"] == "text":
            self.fstk.setCurrentIndex(1); self.ft_text.clear()
            self.ft_text.setPlaceholderText(f"Enter {field['label'].lower()}\u2026")
        else:
            self.fstk.setCurrentIndex(2); self.ft_num.setValue(0)

    def _add_f(self):
        key = self.fc.currentData()
        field = next((f for f in FILTER_FIELDS if f["key"] == key), None)
        if not field: return
        if field["type"] == "combo":
            val = self.ft_combo.currentText(); data = self.ft_combo.currentData()
            if data is None: return
            entry = next((fe for fe in self._fv if fe["key"] == key), None)
            if entry:
                if data in entry["vals"]: return
                entry["vals"].append(data); entry["disp"].append(val)
            else:
                self._fv.append({"key": key, "label": field["label"], "vals": [data], "disp": [val]})
        elif field["type"] == "text":
            val = self.ft_text.text().strip()
            if not val: return
            self._fv = [fe for fe in self._fv if fe["key"] != key]
            self._fv.append({"key": key, "label": field["label"], "vals": [val], "disp": [val]})
        else:
            v = self.ft_num.value()
            if v <= 0: return
            self._fv = [fe for fe in self._fv if fe["key"] != key]
            self._fv.append({"key": key, "label": field["label"], "vals": [v], "disp": [fmt_money(v)]})
        self._rebuild_chips(); self._on_field(self.fc.currentIndex()); self._load_tx_picker()

    def _clear_f(self):
        self._fv = []; self._rebuild_chips()
        self._on_field(self.fc.currentIndex()); self._load_tx_picker()

    def _rebuild_chips(self):
        while self._chips_grid.count():
            itm = self._chips_grid.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()
        if not self._fv: return
        container = QWidget(); container.setStyleSheet("background:transparent;")
        fl = FlowLayout(container, hSpacing=6, vSpacing=4)
        fl.setContentsMargins(0, 0, 0, 0)
        for entry in self._fv:
            key = entry["key"]
            for i, disp in enumerate(entry["disp"]):
                chip = QPushButton(f" {disp} \u2715")
                chip.setStyleSheet(
                    f"QPushButton{{background:{C['accent_bg']};color:{C['accent']};"
                    f"border:1px solid rgba(79,70,229,0.2);border-radius:12px;"
                    f"padding:2px 8px;font-size:11px;font-weight:600;}}"
                    f"QPushButton:hover{{background:#D6DEFF;}}")
                chip.setCursor(QCursor(Qt.PointingHandCursor))
                chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                val_to_remove = entry["vals"][i]
                chip.clicked.connect(lambda _, k=key, v=val_to_remove: self._remove_value(k, v))
                fl.addWidget(chip)
        self._chips_grid.addWidget(container)

    def _remove_value(self, key, val):
        for fe in self._fv:
            if fe["key"] == key:
                try:
                    idx = fe["vals"].index(val); fe["vals"].pop(idx); fe["disp"].pop(idx)
                except ValueError: pass
                if not fe["vals"]: self._fv = [f for f in self._fv if f["key"] != key]
                break
        self._rebuild_chips(); self._on_field(self.fc.currentIndex()); self._load_tx_picker()

    def _apply_filters(self, txns):
        for fe in self._fv:
            key, vals = fe["key"], fe["vals"]
            if key == "account": txns = [t for t in txns if t.get("account_id") in vals]
            elif key == "category": txns = [t for t in txns if t.get("category") in vals]
            elif key == "method": txns = [t for t in txns if t.get("pay_method") in vals]
            elif key == "tx_type": txns = [t for t in txns if t.get("tx_type") in vals]
            elif key == "kind": txns = [t for t in txns if t.get("transaction_kind", "REGULAR") in vals]
            elif key == "neednwant":
                nw_map = {"Need": 1, "Want": 0, "None": 2}
                nw_ints = [nw_map.get(v, -1) for v in vals]
                txns = [t for t in txns if t.get("neednwant") in nw_ints]
            elif key == "pf_category": txns = [t for t in txns if t.get("pf_category") in vals]
            elif key == "person_org":
                p = vals[0].lower()
                txns = [t for t in txns if p in (t.get("person_org") or "").lower()]
            elif key == "description":
                d = vals[0].lower()
                txns = [t for t in txns if d in (t.get("description") or "").lower()]
            elif key == "min_amount": txns = [t for t in txns if t["amount"] >= vals[0]]
            elif key == "max_amount": txns = [t for t in txns if t["amount"] <= vals[0]]
        return txns

    def _clear_tx_list(self):
        while self.tx_list_lay.count():
            itm = self.tx_list_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()

    def _select_all(self):
        """Select all currently filtered transactions."""
        for tid in self._all_filtered_ids:
            self.linked_ids.add(tid)
        self._update_linked_summary()
        self._load_tx_picker()

    def _load_tx_picker(self):
        self._clear_tx_list()
        d_from = self.tx_from.date().toString("yyyy-MM-dd")
        d_to = self.tx_to.date().toString("yyyy-MM-dd")
        txns = self.tx.list_filters(limit=5000, date_from=d_from, date_to=d_to)
        txns = self._apply_filters(txns)
        self._all_filtered_ids = [t["id"] for t in txns]

        cr = sum(t["amount"] for t in txns if t["tx_type"] == "CREDIT")
        db = sum(t["amount"] for t in txns if t["tx_type"] == "DEBIT")
        self._filter_stats.setText(f"{len(txns)} txns | Cr:{fmt_money(cr)} | Db:{fmt_money(db)}")

        if not txns:
            lbl = QLabel("No matching transactions.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.tx_list_lay.addWidget(lbl); return

        by_date = OrderedDict()
        for tx in sorted(txns, key=lambda t: t["tx_date"], reverse=True):
            d = tx["tx_date"]
            if d not in by_date: by_date[d] = []
            by_date[d].append(tx)

        for d_str, day_txns in by_date.items():
            try:
                self.tx_list_lay.addWidget(_day_header(date.fromisoformat(d_str).strftime("%A, %d %b")))
            except:
                self.tx_list_lay.addWidget(_day_header(d_str))
            for tx in day_txns:
                wrapper = QFrame()
                wrapper.setStyleSheet("QFrame{background:transparent;border:none;}")
                wl = QHBoxLayout(wrapper)
                wl.setContentsMargins(0, 0, 0, 0); wl.setSpacing(6)

                is_linked = tx["id"] in self.linked_ids
                chk = QPushButton("\u2713" if is_linked else "\u25CB")
                chk.setFixedSize(28, 28)
                chk.setStyleSheet(
                    f"QPushButton{{background:{C['accent'] if is_linked else C['surface']};"
                    f"color:{'white' if is_linked else C['text3']};"
                    f"border:2px solid {C['accent'] if is_linked else C['border']};"
                    f"border-radius:14px;font-size:12px;font-weight:700;}}"
                    f"QPushButton:hover{{background:{C['accent']};color:white;border-color:{C['accent']};}}")
                chk.setCursor(QCursor(Qt.PointingHandCursor))
                tid = tx["id"]
                chk.clicked.connect(lambda _, t=tid: self._toggle_link(t))
                wl.addWidget(chk)
                card = _tx_card(tx)
                wl.addWidget(card, 1)
                self.tx_list_lay.addWidget(wrapper)

    def _toggle_link(self, tid):
        if tid in self.linked_ids: self.linked_ids.discard(tid)
        else: self.linked_ids.add(tid)
        self._update_linked_summary(); self._load_tx_picker()

    def _update_linked_summary(self):
        if not self.linked_ids:
            self.linked_summary_lbl.setText("No transactions linked."); return
        net = 0.0
        for tid in self.linked_ids:
            t = self.tx.get(tid)
            if t: net += t["amount"] if t["tx_type"] == "CREDIT" else -t["amount"]
        self.linked_summary_lbl.setText(
            f"Linked: {len(self.linked_ids)} txns \u00b7 Net: {fmt_money(net)}")

    def _save_note(self):
        title = self.compose_title.text().strip()
        tags = ", ".join(self._composer_tags)
        content = self.compose_content.toPlainText().strip()
        if not title:
            QMessageBox.warning(self, "Missing Title", "Please enter a title."); return
        existing = self.nr.list_active(title)
        for n in existing:
            if n.get("title", "").lower() == title.lower() and n["id"] != (self.edit_note_id or ""):
                QMessageBox.warning(self, "Duplicate", f"A note titled \"{title}\" already exists."); return
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
        lay = QVBoxLayout(page); lay.setSpacing(12)
        header = QLabel("\U0001f5d1\ufe0f  Trash & Recovery")
        header.setStyleSheet(f"font-size:18px;font-weight:800;color:{C['red']};")
        lay.addWidget(header)
        info = QLabel("Recover deleted notes or remove them permanently.")
        info.setStyleSheet(f"color:{C['text3']};font-size:12px;")
        lay.addWidget(info)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget(); inner.setStyleSheet("background:transparent;")
        self.trash_lay = QVBoxLayout(inner)
        self.trash_lay.setSpacing(8); self.trash_lay.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(inner); lay.addWidget(scroll, 1)
        return page

    def _load_trash(self):
        while self.trash_lay.count():
            itm = self.trash_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()
        rows = self.nr.list_trash()
        if not rows:
            lbl = QLabel("Trash is empty.")
            lbl.setStyleSheet(f"color:{C['text3']};font-size:13px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.trash_lay.addWidget(lbl); return
        for r in rows:
            row = QFrame()
            row.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;}}QLabel{{background:transparent;border:none;}}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(16, 10, 16, 10); rl.setSpacing(12)
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
            recover_btn = QPushButton("Recover"); recover_btn.setStyleSheet(_btn_primary())
            recover_btn.setCursor(QCursor(Qt.PointingHandCursor))
            uid = r["uuid"]
            recover_btn.clicked.connect(lambda _, u=uid: self._recover(u))
            rl.addWidget(recover_btn)
            del_btn = QPushButton("Delete Forever"); del_btn.setStyleSheet(_btn_danger())
            del_btn.setCursor(QCursor(Qt.PointingHandCursor))
            del_btn.clicked.connect(lambda _, u=uid: self._perm_delete(u))
            rl.addWidget(del_btn)
            self.trash_lay.addWidget(row)
        self.trash_lay.addStretch()

    def _recover(self, uid):
        self.nr.restore(uid); self._load_trash(); self._load_notes()

    def _perm_delete(self, uid):
        reply = QMessageBox.question(self, "Delete Forever",
            "This cannot be undone. Delete permanently?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.nr.perm_delete(uid); self._load_trash()

    # ─────────────── PRINT (styled PDF with transaction cards) ───────────────
    def _print_single_note(self, note_id):
        note = self.nr.get(note_id)
        if not note: return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Note PDF",
            f"Note_{(note.get('title') or 'untitled').replace(' ','_')}.pdf",
            "PDF (*.pdf)")
        if not filepath: return
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_RIGHT, TA_CENTER
            from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                             Paragraph, Spacer, KeepTogether)
            from reportlab.graphics.shapes import Drawing
            from reportlab.graphics.barcode.qr import QrCodeWidget

            pw, ph = A4
            doc_id = f"FM-{datetime.now().strftime('%Y%m%d')}-{_uuid.uuid4().hex[:6].upper()}"
            ts = datetime.now().strftime('%d %b %Y at %I:%M %p')
            tx_str = "".join(str(tid) for tid in _linked_ids(note))
            c_hash = hashlib.sha256((tx_str + doc_id + ts).encode()).hexdigest()[:16]

            doc = SimpleDocTemplate(filepath, pagesize=A4,
                                    topMargin=65, bottomMargin=70,
                                    leftMargin=36, rightMargin=36)
            story = []
            S = getSampleStyleSheet()

            WRAP = ParagraphStyle('wrap', parent=S['Normal'], fontSize=10, leading=13)
            WRAP_SM = ParagraphStyle('wrap_sm', parent=S['Normal'], fontSize=9, leading=11)
            WRAP_SM_R = ParagraphStyle('wrap_sm_r', parent=S['Normal'], fontSize=9, leading=11, alignment=TA_RIGHT)
            CARD_TITLE = ParagraphStyle('card_title', parent=S['Normal'], fontSize=11, leading=14,
                                        textColor=colors.HexColor('#111827'))
            CARD_SUB = ParagraphStyle('card_sub', parent=S['Normal'], fontSize=9, leading=11,
                                       textColor=colors.HexColor('#6B7280'))
            CARD_AMT = ParagraphStyle('card_amt', parent=S['Normal'], fontSize=12, leading=15, alignment=TA_RIGHT)

            # Security: watermark
            wm = f"FinanceManager-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            def _header(canvas, doc):
                canvas.saveState()
                # Indigo header bar
                canvas.setFillColor(colors.HexColor('#4F46E5'))
                canvas.rect(0, ph - 50, pw, 50, fill=True, stroke=False)
                canvas.setFillColor(colors.white)
                canvas.setFont('Helvetica-Bold', 15)
                canvas.drawString(30, ph - 32, 'Finance Manager')
                canvas.setFont('Helvetica', 9)
                canvas.drawRightString(pw - 30, ph - 32, 'Note')
                canvas.setFont('Helvetica', 7)
                canvas.setFillColor(colors.Color(1, 1, 1, 0.7))
                canvas.drawString(30, ph - 16, f'Doc ID: {doc_id}')
                canvas.drawRightString(pw - 30, ph - 16, f'Generated: {ts}')
                # Watermark (visible diagonal)
                canvas.setFillColor(colors.Color(0.88, 0.88, 0.88, 0.4))
                canvas.setFont('Helvetica-Bold', 10)
                canvas.saveState()
                canvas.translate(pw / 2, ph / 2)
                canvas.rotate(45)
                canvas.drawString(-120, 0, wm)
                canvas.drawString(-120, 30, wm)
                canvas.restoreState()
                canvas.restoreState()

            def _footer(canvas, doc):
                canvas.saveState()
                # Gray footer bar
                canvas.setFillColor(colors.HexColor('#F3F4F6'))
                canvas.rect(0, 0, pw, 50, fill=True, stroke=False)
                canvas.setFillColor(colors.HexColor('#9CA3AF'))
                canvas.setFont('Helvetica', 7)
                canvas.drawString(36, 22, f'{doc_id}  |  Hash: {c_hash}  |  {wm}')
                canvas.drawRightString(pw - 36, 22, f'Page {doc.page}')
                # QR code is in document body below security table, not in footer
                canvas.restoreState()

            # ── Title ──
            story.append(Paragraph(f"<b>{note.get('title', 'Untitled')}</b>",
                                   ParagraphStyle('title', parent=S['Title'], fontSize=20,
                                                  textColor=colors.HexColor('#111827'))))
            story.append(Spacer(1, 6))

            # ── Tags ──
            tags = note.get("tags") or ""
            if tags:
                story.append(Paragraph(f"<b>Tags:</b> {tags}",
                                       ParagraphStyle('tags', parent=S['Normal'],
                                                      textColor=colors.HexColor('#4F46E5'), fontSize=11)))
                story.append(Spacer(1, 12))

            # ── Content ──
            content = note.get("content") or ""
            if content:
                story.append(Paragraph("<b>Content</b>", S['Heading3']))
                story.append(Spacer(1, 4))
                for line in content.split("\n"):
                    story.append(Paragraph(line or "&nbsp;", WRAP))
                story.append(Spacer(1, 16))

            # ── Linked Transactions — CARD STYLE grouped by date ──
            ids = _linked_ids(note)
            if ids:
                story.append(Paragraph(f"<b>Linked Transactions ({len(ids)})</b>", S['Heading3']))
                story.append(Spacer(1, 8))

                # Collect all transactions
                txns = []
                for tid in ids:
                    tx = self.tx.get_detailed(tid) if hasattr(self.tx, 'get_detailed') else self.tx.get(tid)
                    if tx: txns.append(tx)

                # Group by date
                by_date = OrderedDict()
                for tx in sorted(txns, key=lambda t: t["tx_date"], reverse=True):
                    d = tx["tx_date"]
                    if d not in by_date: by_date[d] = []
                    by_date[d].append(tx)

                cat_icons = {"food_dining": "\U0001f354", "transport": "\U0001f697", "shopping": "\U0001f6cd\ufe0f",
                             "bills_utilities": "\U0001f4a1", "rent": "\U0001f3e0", "salary": "\U0001f4b0",
                             "investment": "\U0001f4c8", "health": "\U0001f3e5", "education": "\U0001f4da",
                             "entertainment": "\U0001f3ac", "transfer": "\U0001f504", "other": "\U0001f4cb"}

                for d_str, day_txns in by_date.items():
                    # Date header
                    try:
                        day_label = date.fromisoformat(d_str).strftime("%A, %d %B %Y")
                    except:
                        day_label = d_str
                    story.append(Paragraph(f"<b>{day_label}</b>",
                                           ParagraphStyle('day', parent=S['Normal'], fontSize=11,
                                                          textColor=colors.HexColor('#374151'),
                                                          spaceBefore=8, spaceAfter=4)))

                    # Each transaction as a styled card (table that looks like a card)
                    for tx in day_txns:
                        tx_type = tx.get("tx_type", "")
                        is_debit = tx_type == "DEBIT"
                        prefix = "\u2212" if is_debit else "+"
                        amt_color = colors.HexColor('#EF4444') if is_debit else colors.HexColor('#10B981')
                        cat_id = tx.get("category") or "other"
                        icon = cat_icons.get(cat_id, "\U0001f4cb")
                        person = tx.get("person_org") or ""
                        tdesc = tx.get("description") or ""
                        if person and tdesc: desc = f"{person} — {tdesc}"
                        elif person: desc = person
                        elif tdesc: desc = tdesc
                        else: desc = "No description"
                        cat_name = tx.get("cat_name") or ""
                        method_name = tx.get("method_name") or ""
                        acct_name = tx.get("account_name") or ""

                        # Build card as a single-row table with styling
                        card_data = [[
                            Paragraph(f"<b>{icon}  {desc}</b><br/><font color='#6B7280' size='9'>{cat_name}  \u00b7  {method_name}  \u00b7  {acct_name}</font>", CARD_TITLE),
                            Paragraph(f"<b>{prefix}{fmt_money(tx['amount'])}</b><br/><font color='#6B7280' size='9'>{tx_type}</font>",
                                      ParagraphStyle('amt', parent=CARD_AMT, textColor=amt_color)),
                        ]]
                        card_table = Table(card_data, colWidths=[pw - 160, 110])
                        card_table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F9FAFB')),
                            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
                            ('TOPPADDING', (0, 0), (-1, -1), 8),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                            ('LEFTPADDING', (0, 0), (-1, -1), 12),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                            # Left accent border
                            ('LINEBEFORE', (0, 0), (0, -1), 3, amt_color),
                        ]))
                        story.append(KeepTogether([card_table, Spacer(1, 4)]))

                # Summary
                total_debit = sum(tx["amount"] for tx in txns if tx.get("tx_type") == "DEBIT")
                total_credit = sum(tx["amount"] for tx in txns if tx.get("tx_type") == "CREDIT")
                story.append(Spacer(1, 10))
                summary_data = [[
                    Paragraph(f"<b>Total Debits</b><br/><font color='#EF4444'>{fmt_money(total_debit)}</font>", CARD_SUB),
                    Paragraph(f"<b>Total Credits</b><br/><font color='#10B981'>{fmt_money(total_credit)}</font>", CARD_SUB),
                    Paragraph(f"<b>Net</b><br/><font color='#374151'>{fmt_money(total_credit - total_debit)}</font>", CARD_SUB),
                ]]
                summary_table = Table(summary_data, colWidths=[(pw - 72) / 3] * 3)
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EEF2FF')),
                    ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#C7D2FE')),
                    ('TOPPADDING', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                story.append(summary_table)
                story.append(Spacer(1, 12))

            # ── Security & Verification ──
            story.append(Spacer(1, 16))
            sec_data = [
                [Paragraph("<b>Document Security</b>", ParagraphStyle('sec_h', parent=S['Normal'], fontSize=10, textColor=colors.HexColor('#4F46E5'))), '', ''],
                [Paragraph("<b>Doc ID</b>", WRAP_SM), Paragraph(f"<font color='#374151'>{doc_id}</font>", WRAP_SM), ''],
                [Paragraph("<b>Content Hash</b>", WRAP_SM), Paragraph(f"<font color='#374151' face='Courier'>{c_hash}</font>", WRAP_SM), ''],
                [Paragraph("<b>Watermark</b>", WRAP_SM), Paragraph(f"<font color='#374151'>{wm}</font>", WRAP_SM), ''],
                [Paragraph("<b>Generated</b>", WRAP_SM), Paragraph(f"<font color='#374151'>{ts}</font>", WRAP_SM), ''],
            ]
            sec_table = Table(sec_data, colWidths=[90, 250, 100])
            sec_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEF2FF')),
                ('SPAN', (0, 0), (-1, 0)),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F9FAFB')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#C7D2FE')),
                ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#C7D2FE')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(sec_table)

            # ── QR Code (below security table) ──
            story.append(Spacer(1, 10))
            qr_data = f"FM-NOTE|{doc_id}|{c_hash}|{wm}|{ts}"
            qr = QrCodeWidget(qr_data)
            qr_drawing = Drawing(80, 80)
            qr_drawing.add(qr)
            # Center the QR code
            qr_table = Table([[qr_drawing]], colWidths=[pw - 72])
            qr_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
            ]))
            story.append(qr_table)
            story.append(Paragraph(f"<para alignment='center'><font color='#9CA3AF' size='9'>Scan to verify document</font></para>",
                                   ParagraphStyle('qr_label', parent=S['Normal'], alignment=TA_CENTER)))

            # ── Metadata ──
            story.append(Spacer(1, 12))
            story.append(Paragraph(f"<i>Created: {note.get('created_at','')[:16]}  ·  Updated: {note.get('updated_at','')[:16] if note.get('updated_at') else '—'}</i>",
                                   ParagraphStyle('meta', parent=S['Normal'],
                                                  textColor=colors.HexColor('#9CA3AF'), fontSize=9)))

            def _page_template(canvas, doc):
                _header(canvas, doc)
                _footer(canvas, doc)
            doc.build(story, onFirstPage=_page_template, onLaterPages=_page_template)
            self._show_pdf_done(filepath)
        except ImportError:
            QMessageBox.warning(self, "Missing", "Install reportlab: pip install reportlab")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _show_pdf_done(self, filepath):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("PDF Saved")
        dlg.setIcon(QMessageBox.Information)
        dlg.setText(f"PDF saved successfully.\n\n{filepath}")
        open_btn = dlg.addButton("  Open PDF  ", QMessageBox.AcceptRole)
        dlg.addButton("Close", QMessageBox.RejectRole)
        dlg.exec_()
        if dlg.clickedButton() == open_btn:
            try:
                if sys.platform == "win32": os.startfile(filepath)
                elif sys.platform == "darwin": subprocess.Popen(["open", filepath])
                else: subprocess.Popen(["xdg-open", filepath])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open PDF:\n{e}")
