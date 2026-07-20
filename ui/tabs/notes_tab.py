"""Notes tab — All Notes, Compose (create/edit + link transactions), Trash & Recovery.

Ports the note-taking idea from the legacy single-file app (searchable card
list, collapsible cards, tag autocomplete, trash/recovery) into this repo's
modular tab + repository pattern, styled with ui.theme.C. The old app's
"Create from Transaction" page never actually persisted the link — this
version genuinely writes to notes.linked_transaction_ids.
"""
import json
import uuid as _uuid
from datetime import date

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QFrame, QScrollArea, QStackedWidget, QMessageBox, QComboBox,
    QDateEdit, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QListWidget, QSizePolicy
)
from PyQt5.QtCore import Qt, QDate, pyqtSignal

from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tab_btn_active, _tab_btn_inactive, _switch_tabs

TAG_PALETTE = [C["amber"], C["accent"], "#0EA5E9", C["green"], "#D946EF", "#7C3AED"]


def _tag_color(tags_str):
    n = len([t for t in (tags_str or "").split(",") if t.strip()])
    return TAG_PALETTE[min(n, len(TAG_PALETTE) - 1)]


def _linked_ids(note):
    raw = note.get("linked_transaction_ids")
    if not raw:
        return []
    try:
        ids = json.loads(raw)
        return ids if isinstance(ids, list) else []
    except Exception:
        return []


# ═══════════════════════════════════════════════
# NOTE CARD — collapsible, click to expand
# ═══════════════════════════════════════════════

class NoteCard(QFrame):
    clicked = pyqtSignal(str)
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, note, parent=None):
        super().__init__(parent)
        self.note = note
        self.expanded = False
        self._build()

    def _build(self):
        accent = _tag_color(self.note.get("tags"))
        self.setStyleSheet(f"""
            QFrame {{ background:{C['surface']}; border:1px solid {C['border2']};
                       border-left: 4px solid {accent}; border-radius:12px; }}
            QFrame:hover {{ border-color:{accent}; }}
            QLabel {{ background:transparent; border:none; }}
        """)
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)

        top = QHBoxLayout()
        title = QLabel(self.note.get("title") or "Untitled")
        title.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:700;")
        top.addWidget(title, 1)
        n_linked = len(_linked_ids(self.note))
        if n_linked:
            badge = QLabel(f"🔗 {n_linked}")
            badge.setStyleSheet(f"color:{C['accent']};font-size:11px;font-weight:700;"
                                 f"background:{C['accent_bg']};border-radius:8px;padding:2px 8px;")
            top.addWidget(badge)
        lay.addLayout(top)

        tag_text = self.note.get("tags") or ""
        tags_lbl = QLabel(" ".join(f"#{t.strip()}" for t in tag_text.split(",") if t.strip()) or "No tags")
        tags_lbl.setStyleSheet(f"color:{accent};font-size:11px;font-weight:600;")
        lay.addWidget(tags_lbl)

        self.content_lbl = QTextEdit(self.note.get("content") or "")
        self.content_lbl.setReadOnly(True)
        self.content_lbl.setStyleSheet(f"""
            QTextEdit {{ color:{C['text2']}; background:{C['surface2']};
                          border-radius:8px; padding:8px; font-size:12px; }}
        """)
        self.content_lbl.setFixedHeight(120)
        self.content_lbl.hide()
        lay.addWidget(self.content_lbl)

        self.linked_lbl = QLabel("")
        self.linked_lbl.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        self.linked_lbl.setWordWrap(True)
        self.linked_lbl.hide()
        lay.addWidget(self.linked_lbl)

        self.btn_row = QHBoxLayout()
        self.btn_row.addStretch()
        self.btn_edit = QPushButton("✏️ Edit"); self.btn_edit.setObjectName("pill")
        self.btn_delete = QPushButton("🗑️ Delete"); self.btn_delete.setObjectName("pill")
        self.btn_row.addWidget(self.btn_edit)
        self.btn_row.addWidget(self.btn_delete)
        self.btn_edit.hide(); self.btn_delete.hide()
        lay.addLayout(self.btn_row)

        self.btn_edit.clicked.connect(lambda: self.edit_requested.emit(self.note["id"]))
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.note["id"]))

    def mousePressEvent(self, event):
        self.clicked.emit(self.note["id"])
        event.accept()

    def set_linked_preview(self, text):
        self.linked_lbl.setText(text)

    def expand(self):
        self.expanded = True
        self.content_lbl.show()
        if self.linked_lbl.text():
            self.linked_lbl.show()
        self.btn_edit.show(); self.btn_delete.show()

    def collapse(self):
        self.expanded = False
        self.content_lbl.hide()
        self.linked_lbl.hide()
        self.btn_edit.hide(); self.btn_delete.hide()


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
        self.edit_note_id = None       # None => creating a new note
        self.linked_ids = set()        # transaction ids linked in the composer
        self._loading_tx_table = False
        self._build()
        self.refresh()

    # ---------------------------------------------------------- layout
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(16)

        heading = QLabel("Notes")
        heading.setStyleSheet(f"font-size:22px;font-weight:800;color:{C['text']};")
        outer.addWidget(heading)

        nav_row = QHBoxLayout()
        self.btn_all = QPushButton("All Notes")
        self.btn_new = QPushButton("＋ New Note")
        self.btn_trash = QPushButton("🗑️ Trash & Recovery")
        self._nav_btns = [self.btn_all, self.btn_new, self.btn_trash]
        for b in self._nav_btns:
            nav_row.addWidget(b)
        nav_row.addStretch()
        outer.addLayout(nav_row)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_all_notes_page())
        self.stack.addWidget(self._build_compose_page())
        self.stack.addWidget(self._build_trash_page())

        self.btn_all.clicked.connect(lambda: self._goto(0))
        self.btn_new.clicked.connect(lambda: self._goto(1, reset=True))
        self.btn_trash.clicked.connect(lambda: self._goto(2))
        self._goto(0)

    def _goto(self, idx, reset=False):
        _switch_tabs(self._nav_btns, idx)
        self.stack.setCurrentIndex(idx)
        if idx == 0:
            self._load_notes()
        elif idx == 1 and reset:
            self._reset_composer()
        elif idx == 2:
            self._load_trash()

    def refresh(self):
        self._load_notes()
        self._load_trash()

    # ---------------------------------------------------------- PAGE 1: All Notes
    def _build_all_notes_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search notes by title or tag…")
        self.search_box.setMinimumHeight(38)
        self.search_box.textChanged.connect(self._load_notes)
        lay.addWidget(self.search_box)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
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
            empty = QLabel("No notes yet. Tap “＋ New Note” to add one.")
            empty.setStyleSheet(f"color:{C['text3']};font-size:13px;padding:24px;")
            empty.setAlignment(Qt.AlignCenter)
            self.notes_lay.addWidget(empty)
            return

        for n in notes:
            card = NoteCard(n)
            ids = _linked_ids(n)
            if ids:
                card.set_linked_preview(self._linked_preview_text(ids))
            card.clicked.connect(self._toggle_card)
            card.edit_requested.connect(self._edit_note)
            card.delete_requested.connect(self._delete_note)
            self.notes_lay.addWidget(card)

    def _linked_preview_text(self, ids, max_show=3):
        shown = []
        for tid in ids[:max_show]:
            t = self.tx.get(tid)
            if t:
                shown.append(f"{t.get('tx_date','')} · {t.get('person_org') or t.get('description') or t['id'][:8]} "
                              f"({fmt_money(t['amount'])})")
        more = len(ids) - len(shown)
        text = "Linked: " + "; ".join(shown)
        if more > 0:
            text += f"  +{more} more"
        return text

    def _toggle_card(self, note_id):
        for i in range(self.notes_lay.count()):
            item = self.notes_lay.itemAt(i)
            w = item.widget()
            if isinstance(w, NoteCard) and w.note["id"] == note_id:
                w.collapse() if w.expanded else w.expand()
            elif isinstance(w, NoteCard):
                w.collapse()

    def _delete_note(self, note_id):
        reply = QMessageBox.question(
            self, "Delete Note", "Move this note to Trash? You can recover it later.",
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
        self.compose_tags.setText(note.get("tags") or "")
        self.compose_content.setPlainText(note.get("content") or "")
        self.linked_ids = set(_linked_ids(note))
        self._update_linked_summary()
        self.compose_header.setText("✏️ Edit Note")
        self._goto(1)

    # ---------------------------------------------------------- PAGE 2: Compose
    def _build_compose_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(14)

        self.compose_header = QLabel("📝 New Note")
        self.compose_header.setStyleSheet(f"font-size:18px;font-weight:800;color:{C['accent']};")
        lay.addWidget(self.compose_header)

        self.compose_title = QLineEdit()
        self.compose_title.setPlaceholderText("Title")
        self.compose_title.setMinimumHeight(38)
        lay.addWidget(self.compose_title)

        tags_row = QHBoxLayout()
        self.compose_tags = QLineEdit()
        self.compose_tags.setPlaceholderText("Tags (comma-separated) — e.g. card, emi, tax")
        self.compose_tags.setMinimumHeight(38)
        self.compose_tags.textChanged.connect(self._update_tag_suggestions)
        tags_row.addWidget(self.compose_tags, 1)
        lay.addLayout(tags_row)

        self.tag_suggestions = QListWidget()
        self.tag_suggestions.setMaximumHeight(90)
        self.tag_suggestions.itemClicked.connect(self._apply_tag_suggestion)
        self.tag_suggestions.hide()
        lay.addWidget(self.tag_suggestions)

        self.compose_content = QTextEdit()
        self.compose_content.setPlaceholderText("Write your note here…")
        self.compose_content.setMinimumHeight(140)
        lay.addWidget(self.compose_content)

        # ---- Link Transactions ----
        link_frame = QFrame(); link_frame.setObjectName("card")
        link_lay = QVBoxLayout(link_frame)
        link_header = QLabel("🔗 Link Transactions (optional)")
        link_header.setStyleSheet(f"font-weight:700;color:{C['text2']};font-size:13px;")
        link_lay.addWidget(link_header)

        filt = QHBoxLayout()
        self.tx_from = QDateEdit(); self.tx_from.setCalendarPopup(True)
        self.tx_from.setDate(QDate.currentDate().addMonths(-1))
        self.tx_to = QDateEdit(); self.tx_to.setCalendarPopup(True)
        self.tx_to.setDate(QDate.currentDate())
        self.tx_type_cb = QComboBox(); self.tx_type_cb.addItems(["ALL", "DEBIT", "CREDIT"])
        self.tx_account_cb = QComboBox()
        self.tx_account_cb.addItem("ALL", None)
        if self.acc:
            for a in self.acc.list_active():
                self.tx_account_cb.addItem(a["display_name"], a["account_id"])
        self.tx_search = QLineEdit(); self.tx_search.setPlaceholderText("Search person / description…")
        load_btn = QPushButton("⟳ Load"); load_btn.setObjectName("primary")
        load_btn.clicked.connect(self._load_tx_picker)
        for w in [self.tx_from, self.tx_to, self.tx_type_cb, self.tx_account_cb, self.tx_search, load_btn]:
            filt.addWidget(w)
        link_lay.addLayout(filt)

        self.tx_table = QTableWidget()
        self.tx_table.setColumnCount(6)
        self.tx_table.setHorizontalHeaderLabels(["✓", "Date", "Type", "Amount", "Person/Desc", "Account"])
        self.tx_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tx_table.verticalHeader().setVisible(False)
        self.tx_table.setMaximumHeight(220)
        hh = self.tx_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.Stretch)
        self.tx_table.itemChanged.connect(self._on_tx_check_changed)
        link_lay.addWidget(self.tx_table)

        self.linked_summary_lbl = QLabel("No transactions linked.")
        self.linked_summary_lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
        link_lay.addWidget(self.linked_summary_lbl)

        lay.addWidget(link_frame)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        save_btn = QPushButton("💾 Save Note"); save_btn.setObjectName("primary")
        cancel_btn.clicked.connect(lambda: self._goto(0))
        save_btn.clicked.connect(self._save_note)
        btn_row.addStretch(); btn_row.addWidget(cancel_btn); btn_row.addWidget(save_btn)
        lay.addLayout(btn_row)

        return page

    def _reset_composer(self):
        self.edit_note_id = None
        self.linked_ids = set()
        self.compose_header.setText("📝 New Note")
        self.compose_title.clear()
        self.compose_tags.clear()
        self.compose_content.clear()
        self.tag_suggestions.hide()
        self.tx_table.setRowCount(0)
        self._update_linked_summary()

    def _update_tag_suggestions(self):
        text = self.compose_tags.text()
        current = text.rsplit(",", 1)[-1].strip().lower()
        if len(current) < 1:
            self.tag_suggestions.hide()
            return
        matches = [t for t in self.lu.list_tags() if current in t["display_name"].lower()]
        self.tag_suggestions.clear()
        for t in matches[:8]:
            self.tag_suggestions.addItem(t["display_name"])
        # offer to create a brand-new tag if nothing matches exactly
        if current and not any(t["display_name"].lower() == current for t in matches):
            self.tag_suggestions.addItem(f"＋ Add new tag “{current}”")
        self.tag_suggestions.setVisible(self.tag_suggestions.count() > 0)

    def _apply_tag_suggestion(self, item):
        text = self.compose_tags.text()
        label = item.text()
        if label.startswith("＋ Add new tag"):
            new_tag = label.split("“")[1].rstrip("”")
            try:
                self.lu.add_tag(new_tag.lower().replace(" ", "_"), new_tag)
            except ValueError:
                pass
            chosen = new_tag
        else:
            chosen = label
        head = text.rsplit(",", 1)[0] if "," in text else ""
        new_text = (head + ", " if head else "") + chosen + ", "
        self.compose_tags.setText(new_text)
        self.tag_suggestions.hide()
        self.compose_tags.setFocus()

    # ---- transaction picker ----
    def _load_tx_picker(self):
        self._loading_tx_table = True
        self.tx_table.setRowCount(0)
        d_from = self.tx_from.date().toString("yyyy-MM-dd")
        d_to = self.tx_to.date().toString("yyyy-MM-dd")
        tx_type = None if self.tx_type_cb.currentText() == "ALL" else self.tx_type_cb.currentText()
        account_id = self.tx_account_cb.currentData()
        rows = self.tx.list_filters(account_id=account_id, tx_type=tx_type,
                                     date_from=d_from, date_to=d_to, limit=1000)
        search = self.tx_search.text().strip().lower()
        if search:
            rows = [r for r in rows if search in (r.get("person_org") or "").lower()
                    or search in (r.get("description") or "").lower()]

        self.tx_table.setRowCount(len(rows))
        for i, t in enumerate(rows):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Checked if t["id"] in self.linked_ids else Qt.Unchecked)
            chk.setData(Qt.UserRole, t["id"])
            self.tx_table.setItem(i, 0, chk)
            self.tx_table.setItem(i, 1, QTableWidgetItem(t.get("tx_date", "")))
            self.tx_table.setItem(i, 2, QTableWidgetItem(t.get("tx_type", "")))
            self.tx_table.setItem(i, 3, QTableWidgetItem(fmt_money(t["amount"])))
            desc = t.get("person_org") or t.get("description") or ""
            self.tx_table.setItem(i, 4, QTableWidgetItem(desc))
            self.tx_table.setItem(i, 5, QTableWidgetItem(t.get("account_name", "")))
        self._loading_tx_table = False

    def _on_tx_check_changed(self, item):
        if self._loading_tx_table or item.column() != 0:
            return
        tid = item.data(Qt.UserRole)
        if not tid:
            return
        if item.checkState() == Qt.Checked:
            self.linked_ids.add(tid)
        else:
            self.linked_ids.discard(tid)
        self._update_linked_summary()

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
        tags = self.compose_tags.text().strip().strip(",").strip()
        content = self.compose_content.toPlainText().strip()
        if not title:
            QMessageBox.warning(self, "Missing Title", "Please enter a title for the note.")
            return

        linked = sorted(self.linked_ids)
        if self.edit_note_id:
            self.nr.update(self.edit_note_id, title=title, tags=tags, content=content,
                           linked_transaction_ids=linked)
        else:
            self.nr.create(title=title, tags=tags, content=content,
                            linked_transaction_ids=linked)
        self._goto(0)

    # ---------------------------------------------------------- PAGE 3: Trash
    def _build_trash_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        header = QLabel("🗑️ Trash & Recovery")
        header.setStyleSheet(f"font-size:18px;font-weight:800;color:{C['red']};")
        lay.addWidget(header)
        info = QLabel("Recover deleted notes or remove them permanently.")
        info.setStyleSheet(f"color:{C['text3']};font-size:12px;")
        lay.addWidget(info)

        self.trash_table = QTableWidget()
        self.trash_table.setColumnCount(5)
        self.trash_table.setHorizontalHeaderLabels(["Title", "Tags", "Deleted", "", ""])
        self.trash_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.trash_table.verticalHeader().setVisible(False)
        hh = self.trash_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.trash_table, 1)
        return page

    def _load_trash(self):
        rows = self.nr.list_trash()
        self.trash_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.trash_table.setItem(i, 0, QTableWidgetItem(r.get("title") or "Untitled"))
            self.trash_table.setItem(i, 1, QTableWidgetItem(r.get("tags") or ""))
            self.trash_table.setItem(i, 2, QTableWidgetItem((r.get("deleted_at") or "")[:16]))

            recover_btn = QPushButton("Recover"); recover_btn.setObjectName("primary")
            recover_btn.clicked.connect(lambda _, u=r["uuid"]: self._recover(u))
            self.trash_table.setCellWidget(i, 3, recover_btn)

            delete_btn = QPushButton("Delete Forever"); delete_btn.setObjectName("danger")
            delete_btn.clicked.connect(lambda _, u=r["uuid"]: self._perm_delete(u))
            self.trash_table.setCellWidget(i, 4, delete_btn)

    def _recover(self, uid):
        self.nr.restore(uid)
        self._load_trash()
        self._load_notes()

    def _perm_delete(self, uid):
        reply = QMessageBox.question(
            self, "Delete Forever", "This cannot be undone. Delete this note permanently?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.nr.perm_delete(uid)
            self._load_trash()