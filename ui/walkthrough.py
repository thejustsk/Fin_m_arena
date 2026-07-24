# -*- coding: utf-8 -*-
"""Walkthrough - Full-page guided tour with real widgets and navigation.
Covers ALL tabs and sub-tabs with detailed explanations and live prototypes.
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame, QScrollArea, QSizePolicy,
                              QLineEdit, QComboBox, QDoubleSpinBox, QDateEdit,
                              QSpinBox, QCheckBox, QFormLayout)
from PyQt5.QtCore import Qt, pyqtSignal, QDate
from PyQt5.QtGui import QCursor
from ui.theme import C
from ui.sidebar import fmt_money
from ui.tabs.database_tab import _tx_card, _day_header


# ═══════════════════════════════════════════════
# REAL WIDGET BUILDERS — using actual app widgets
# ═══════════════════════════════════════════════

def _make_label(text, size=12, color=None, bold=False):
    lbl = QLabel(text)
    color = color or C['text']
    weight = "800" if bold else "500"
    lbl.setStyleSheet(f"font-size:{size}px;font-weight:{weight};color:{color};background:transparent;border:none;")
    return lbl

def _make_badge(text, bg, fg="white"):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{fg};background:{bg};border-radius:10px;padding:2px 8px;font-size:10px;font-weight:700;border:none;")
    lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return lbl

def _make_btn(text, primary=False):
    btn = QPushButton(text)
    if primary:
        btn.setStyleSheet(f"QPushButton{{background:{C['accent']};color:white;border:none;border-radius:8px;padding:6px 14px;font-size:12px;font-weight:600;}}QPushButton:hover{{background:#4338CA;}}")
    else:
        btn.setStyleSheet(f"QPushButton{{background:{C['surface']};color:{C['text2']};border:1px solid {C['border']};border-radius:8px;padding:6px 14px;font-size:12px;font-weight:500;}}QPushButton:hover{{border-color:{C['accent']};color:{C['accent']};}}")
    btn.setFixedHeight(32)
    return btn

def _make_input(text="", placeholder=""):
    inp = QLineEdit()
    if text: inp.setText(text)
    if placeholder: inp.setPlaceholderText(placeholder)
    inp.setStyleSheet(f"QLineEdit{{background:{C['surface']};border:1.5px solid {C['border']};border-radius:8px;padding:6px 10px;font-size:12px;color:{C['text']};}}QLineEdit:focus{{border-color:{C['accent']};}}")
    inp.setFixedHeight(32)
    return inp

def _make_combo(items, current_idx=0):
    cb = QComboBox()
    cb.addItems(items)
    if current_idx < len(items): cb.setCurrentIndex(current_idx)
    cb.setStyleSheet(f"QComboBox{{background:{C['surface']};border:1.5px solid {C['border']};border-radius:8px;padding:6px 10px;font-size:12px;color:{C['text']};min-height:24px;}}QComboBox:focus{{border-color:{C['accent']};}}")
    cb.setFixedHeight(32)
    return cb

def _make_spin(prefix="Rs. ", val=0, lo=0, hi=99999999):
    sp = QDoubleSpinBox()
    sp.setPrefix(prefix); sp.setRange(lo, hi); sp.setDecimals(2); sp.setValue(val)
    sp.setStyleSheet(f"QDoubleSpinBox{{background:{C['surface']};border:1.5px solid {C['border']};border-radius:8px;padding:6px 10px;font-size:12px;}}QDoubleSpinBox:focus{{border-color:{C['accent']};}}")
    sp.setFixedHeight(32)
    return sp

def _make_date():
    d = QDateEdit(QDate.currentDate())
    d.setCalendarPopup(True)
    d.setStyleSheet(f"QDateEdit{{background:{C['surface']};border:1.5px solid {C['border']};border-radius:8px;padding:6px 10px;font-size:12px;}}QDateEdit:focus{{border-color:{C['accent']};}}")
    d.setFixedHeight(32)
    return d

def _make_sep():
    f = QFrame(); f.setFixedHeight(1); f.setStyleSheet(f"background:{C['border2']};")
    return f

def _make_card_frame():
    f = QFrame()
    f.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;}}QLabel{{background:transparent;border:none;}}")
    return f

def _make_section(title, icon="📖"):
    """Section header with icon."""
    lbl = QLabel(f"{icon}  {title}")
    lbl.setStyleSheet(f"font-size:14px;font-weight:800;color:{C['accent']};background:transparent;border:none;padding:4px 0;")
    return lbl

def _make_kv_row(pairs):
    """Key-value row: [(label, value), ...]"""
    row = QHBoxLayout(); row.setSpacing(16)
    for k, v in pairs:
        col = QVBoxLayout(); col.setSpacing(1)
        kl = QLabel(k); kl.setStyleSheet(f"font-size:10px;color:{C['text3']};font-weight:600;text-transform:uppercase;letter-spacing:0.3px;background:transparent;border:none;")
        vl = QLabel(v); vl.setStyleSheet(f"font-size:12px;font-weight:700;color:{C['text']};background:transparent;border:none;")
        col.addWidget(kl); col.addWidget(vl); row.addLayout(col)
    row.addStretch()
    return row

def _sample_tx(tx_type="DEBIT", amount=500.0, person="Swiggy", desc="Food order",
               cat="food_dining", cat_name="Food & Dining", cat_color="#F59E0B",
               method="PHONEPAY", acct="SBI Savings", kind="REGULAR", tx_id="s1"):
    return {"id": tx_id, "tx_date": "2026-07-20", "tx_type": tx_type, "amount": amount,
            "person_org": person, "description": desc, "category": cat,
            "cat_name": cat_name, "cat_color": cat_color, "method_name": method,
            "account_name": acct, "transaction_kind": kind}


# ═══════════════════════════════════════════════
# PROTOTYPE BUILDERS — real widgets with sample data
# ═══════════════════════════════════════════════

# ── 1. HOME ──────────────────────────────────────────────
def _build_home_kpi():
    w = QWidget(); lay = QHBoxLayout(w); lay.setSpacing(10)
    for period, label, amt, cnt in [
        ("today", "Today  |  Expense", "Rs.3,200", "5 txns"),
        ("week", "This Week  |  Expense", "Rs.18,500", "23 txns"),
        ("month", "This Month  |  Expense", "Rs.62,400", "89 txns"),
        ("year", "This Year  |  Expense", "Rs.4,85,000", "1,024 txns"),
    ]:
        card = _make_card_frame()
        is_sel = period == "month"
        if is_sel:
            card.setStyleSheet(f"QFrame{{background:{C['accent']};border:none;border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
        cl = QVBoxLayout(card); cl.setContentsMargins(14, 10, 14, 10); cl.setSpacing(4)
        tl = _make_label(f"💸  {label}", 10, "rgba(255,255,255,0.7)" if is_sel else C['text3'], True)
        tl.setStyleSheet(tl.styleSheet() + ("letter-spacing:1px;" if not is_sel else "letter-spacing:1px;"))
        cl.addWidget(tl)
        cl.addWidget(_make_label(amt, 18, "white" if is_sel else C['text'], True))
        cl.addWidget(_make_label(cnt, 11, "rgba(255,255,255,0.7)" if is_sel else C['text3']))
        lay.addWidget(card)
    return w

def _build_home_charts():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    grid = QHBoxLayout(); grid.setSpacing(12)
    for title, color in [("Spending by Category", "#4F46E5"), ("Spending Trend", "#10B981")]:
        card = _make_card_frame(); cl = QVBoxLayout(card); cl.setContentsMargins(14, 10, 14, 10)
        dot_row = QHBoxLayout()
        dot = QLabel("●"); dot.setStyleSheet(f"color:{color};font-size:8px;background:transparent;border:none;")
        dot_row.addWidget(dot); dot_row.addWidget(_make_label(title, 11, C['text'], True)); dot_row.addStretch()
        cl.addLayout(dot_row)
        placeholder = QLabel("📊 Chart renders here via Chart.js")
        placeholder.setStyleSheet(f"color:{C['text3']};font-size:11px;padding:20px;background:transparent;border:none;")
        placeholder.setAlignment(Qt.AlignCenter); cl.addWidget(placeholder)
        grid.addWidget(card)
    lay.addLayout(grid)
    wide = _make_card_frame(); wl = QVBoxLayout(wide); wl.setContentsMargins(14, 10, 14, 10)
    dot_row = QHBoxLayout()
    dot = QLabel("●"); dot.setStyleSheet(f"color:#F59E0B;font-size:8px;background:transparent;border:none;")
    dot_row.addWidget(dot); dot_row.addWidget(_make_label("Need vs Want", 11, C['text'], True)); dot_row.addStretch()
    wl.addLayout(dot_row)
    bar = QFrame(); bar.setFixedHeight(24); bar.setStyleSheet(f"background:{C['border2']};border-radius:6px;")
    bl = QHBoxLayout(bar); bl.setContentsMargins(0,0,0,0); bl.setSpacing(0)
    need_fill = QFrame(); need_fill.setStyleSheet("background:#4F46E5;border-radius:6px;")
    want_fill = QFrame(); want_fill.setStyleSheet("background:#F59E0B;border-radius:6px;")
    bl.addWidget(need_fill, 65); bl.addWidget(want_fill, 35)
    wl.addWidget(bar)
    nr = QHBoxLayout()
    nr.addWidget(_make_label("Need: Rs.40,560 (65%)", 10, "#4F46E5", True))
    nr.addWidget(_make_label("Want: Rs.21,840 (35%)", 10, "#F59E0B", True))
    nr.addStretch(); wl.addLayout(nr)
    lay.addWidget(wide)
    return w

def _build_home_top_tx():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)
    lay.addWidget(_make_label("Top Transactions", 14, C['text'], True))
    lay.addWidget(_make_label("Sorted by amount (highest first) for the selected period", 11, C['text3']))
    lay.addWidget(_make_sep())
    for tx_data in [
        _sample_tx("DEBIT", 15000, "Landlord", "Rent", "rent", "Rent", "#A855F7", "NETBANKING", "HDFC Bank", tx_id="ht1"),
        _sample_tx("DEBIT", 3500, "Amazon", "Electronics", "shopping", "Shopping", "#EC4899", "AMAZON PAY", "ICICI CC", tx_id="ht2"),
        _sample_tx("DEBIT", 2800, "Swiggy", "Food orders", "food_dining", "Food & Dining", "#F59E0B", "PHONEPAY", "SBI Savings", tx_id="ht3"),
    ]:
        lay.addWidget(_tx_card(tx_data))
    return w

def _build_home_savings():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)
    card = _make_card_frame(); cl = QVBoxLayout(card); cl.setContentsMargins(16, 12, 16, 12); cl.setSpacing(6)
    cl.addWidget(_make_label("Savings Rate", 12, C['text'], True))
    cl.addWidget(_make_label("38%", 28, C['green'], True))
    bar_bg = QFrame(); bar_bg.setFixedHeight(8)
    bar_bg.setStyleSheet(f"background:{C['border2']};border-radius:4px;")
    bl = QHBoxLayout(bar_bg); bl.setContentsMargins(0,0,0,0); bl.setSpacing(0)
    bar_fill = QFrame(); bar_fill.setStyleSheet(f"background:{C['green']};border-radius:4px;")
    bl.addWidget(bar_fill, 38); bl.addStretch(62)
    cl.addWidget(bar_bg)
    nums = QHBoxLayout()
    for text, color in [("↑ Income  Rs.1,00,000", C['green']), ("= Savings  Rs.38,000", C['green']), ("↓ Expense  Rs.62,000", C['red'])]:
        nums.addWidget(_make_label(text, 11, color, True)); nums.addStretch()
    cl.addLayout(nums)
    lay.addWidget(card)
    lay.addWidget(_make_label("Calculation: (Income - Expense) / Income × 100. Excludes transfers.", 10, C['text3']))
    return w

def _build_home_tiles():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)
    tiles = [
        [("📝", "Transactions", C['accent']), ("🗄️", "Database", "#8B5CF6"), ("💰", "Balances", C['green'])],
        [("💳", "Credit Cards", C['red']), ("💳", "Debit Cards", "#F59E0B"), ("🔍", "Audit", C['amber'])],
        [("📈", "Wealth", "#10B981"), ("📋", "Notes", "#EC4899"), ("⚙️", "Settings", C['text3'])],
        [("📧", "Gmail", "#06B6D4")],
    ]
    for row_tiles in tiles:
        row = QHBoxLayout(); row.setSpacing(6)
        for ico, name, color in row_tiles:
            tile = QFrame()
            tile.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border']};border-left:3px solid {color};border-radius:8px;}}QLabel{{background:transparent;border:none;}}")
            tl = QHBoxLayout(tile); tl.setContentsMargins(10, 6, 10, 6)
            il = QLabel(ico); il.setStyleSheet("font-size:16px;background:transparent;border:none;"); il.setFixedWidth(22)
            tl.addWidget(il); tl.addWidget(_make_label(name, 11, C['text']))
            row.addWidget(tile)
        row.addStretch()
        lay.addLayout(row)
    return w


# ── 2. TRANSACTION ENTRY ────────────────────────────────
def _build_tx_entry():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    r1 = QHBoxLayout(); r1.setSpacing(8)
    r1.addWidget(_make_spin("Rs. ", 500)); r1.addWidget(_make_btn("DEBIT"))
    r1.addWidget(_make_combo(["SBI Savings  |  Debit", "HDFC Bank  |  Debit", "Cash at Home"]))
    lay.addLayout(r1)
    r2 = QHBoxLayout(); r2.setSpacing(8)
    r2.addWidget(_make_combo(["Food & Dining", "Transport", "Shopping"]))
    r2.addWidget(_make_combo(["PHONEPAY", "CASH", "NETBANKING"])); r2.addWidget(_make_date())
    lay.addLayout(r2)
    r3 = QHBoxLayout(); r3.setSpacing(8)
    for txt, active in [("None", False), ("Need", True), ("Want", False)]:
        btn = QPushButton(txt)
        btn.setStyleSheet(f"QPushButton{{background:{C['accent'] if active else C['surface']};color:{'white' if active else C['text3']};border:{'none' if active else f'1.5px solid {C[chr(98)+chr(111)+chr(114)+chr(100)+chr(101)+chr(114)]}'};border-radius:8px;padding:10px 16px;font-size:13px;font-weight:{'700' if active else '500'};}}")
        btn.setFixedHeight(42); r3.addWidget(btn)
    r3.addWidget(_make_input("", "Person / Org")); r3.addWidget(_make_input("", "Description"))
    lay.addLayout(r3)
    r4 = QHBoxLayout()
    r4.addWidget(_make_label("PF: consumption", 12, C['text3'])); r4.addStretch()
    r4.addWidget(_make_btn("➕  Add Transaction", True))
    lay.addLayout(r4)
    lay.addWidget(_make_sep())
    lay.addWidget(_make_label("Recent Transactions", 13, C['text'], True))
    lay.addWidget(_tx_card(_sample_tx()))
    return w

def _build_tx_transfer():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    r1 = QHBoxLayout(); r1.setSpacing(8)
    r1.addWidget(_make_combo(["SBI Savings", "HDFC Bank"]))
    swap = QPushButton("⇄"); swap.setStyleSheet(f"QPushButton{{background:{C['accent_bg']};color:{C['accent']};border:1px solid {C['accent']};border-radius:8px;font-size:20px;font-weight:700;}}QPushButton:hover{{background:{C['accent']};color:white;}}"); swap.setFixedSize(48, 42)
    r1.addWidget(swap); r1.addWidget(_make_combo(["SBI Savings", "HDFC Bank"], 1))
    lay.addLayout(r1)
    r2 = QHBoxLayout(); r2.setSpacing(8)
    r2.addWidget(_make_spin("Rs. ", 10000)); r2.addWidget(_make_combo(["NETBANKING", "PHONEPAY"])); r2.addWidget(_make_date())
    lay.addLayout(r2)
    r3 = QHBoxLayout(); r3.addWidget(_make_input("", "Description (optional)")); r3.addStretch()
    r3.addWidget(_make_btn("💸  Transfer", True))
    lay.addLayout(r3)
    lay.addWidget(_make_sep())
    # Razorpay success card preview
    success = QFrame()
    success.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(240,253,244,0.97),stop:1 rgba(220,252,231,0.97));border-radius:24px;}")
    sl = QVBoxLayout(success); sl.setContentsMargins(20, 16, 20, 16); sl.setSpacing(6); sl.setAlignment(Qt.AlignCenter)
    sl.addWidget(_make_label("✅", 32, "#059669", True))
    sl.addWidget(_make_label("Rs.10,000", 24, "#064E3B", True))
    sl.addWidget(_make_label("SBI Savings   ->   HDFC Bank", 13, "#059669", True))
    sl.addWidget(_make_label("Transfer Successful", 14, "#047857", True))
    done = QPushButton("Done"); done.setStyleSheet("QPushButton{background:#059669;color:white;border:none;border-radius:10px;font-size:14px;font-weight:700;padding:8px 24px;}"); done.setFixedSize(140, 36)
    sl.addWidget(done, alignment=Qt.AlignCenter)
    lay.addWidget(success, alignment=Qt.AlignCenter)
    return w

def _build_tx_gmail():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    icon = QLabel("📧"); icon.setStyleSheet("font-size:48px;background:transparent;border:none;"); icon.setAlignment(Qt.AlignCenter)
    lay.addWidget(icon)
    lay.addWidget(_make_label("Gmail Queue", 16, C['text'], True))
    lay.addWidget(_make_label("Gmail suggested transactions will appear here once Gmail sync is configured.", 12, C['text3']))
    lay.addWidget(_make_label("Status: Coming Soon", 11, C['amber']))
    return w


# ── 3. DATABASE ──────────────────────────────────────────
def _build_db_complete():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)
    sr = QHBoxLayout(); sr.setSpacing(6)
    sr.addWidget(_make_input(placeholder="🔍 Search by person, description, or amount..."))
    sr.addWidget(_make_btn("🔍 Search", True)); sr.addWidget(_make_btn("✕ Clear"))
    lay.addLayout(sr)
    lay.addWidget(_make_label("Found 3 results for \"swiggy\"", 11, C['text3']))
    lay.addWidget(_make_label("  July 2026", 18, C['text'], True))
    lay.addWidget(_make_label("  Monday, 20 Jul", 12, C['text3'], True))
    for tx in [
        _sample_tx("DEBIT", 500, "Swiggy", "Food order", "food_dining", "Food & Dining", "#F59E0B", "PHONEPAY", "SBI Savings", tx_id="db1"),
        _sample_tx("CREDIT", 50000, "Company", "Salary", "salary", "Salary", "#10B981", "PHONEPAY", "SBI Savings", tx_id="db2"),
        _sample_tx("DEBIT", 15000, "Landlord", "Rent", "rent", "Rent", "#A855F7", "NETBANKING", "HDFC Bank", tx_id="db3"),
    ]:
        lay.addWidget(_tx_card(tx))
    return w

def _build_db_monthly():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    sel = QFrame(); sel.setStyleSheet(f"QFrame{{background:#fff;border:1px solid #E5E7EB;border-radius:14px;padding:14px 20px;}}QLabel{{background:transparent;border:none;}}")
    sl = QHBoxLayout(sel); sl.setSpacing(14)
    sl.addWidget(_make_label("📅 Month:", 12, C['text2'], True))
    sl.addWidget(_make_combo(["January","February","March","April","May","June","July","August","September","October","November","December"], 6))
    sl.addWidget(_make_label("Year:", 12, C['text2'], True))
    year_sp = QSpinBox(); year_sp.setRange(2020, 2030); year_sp.setValue(2026)
    year_sp.setStyleSheet(f"QSpinBox{{background:{C['surface']};border:1.5px solid {C['border']};border-radius:8px;padding:6px 10px;font-size:12px;}}"); year_sp.setFixedHeight(32)
    sl.addWidget(year_sp); sl.addWidget(_make_btn("  Load  ", True))
    sl.addStretch(); sl.addWidget(_make_btn("🖨  Print Statement"))
    lay.addWidget(sel)
    # Sub-tabs
    tr = QHBoxLayout(); tr.setSpacing(8)
    for txt, active in [("Transactions", True), ("Summary", False), ("Visualization", False)]:
        tr.addWidget(_make_btn(txt, active))
    tr.addStretch(); lay.addLayout(tr)
    # Summary KPIs
    kpi_row = QHBoxLayout(); kpi_row.setSpacing(10)
    for label, val, ico, color in [("Transactions", "89", "📊", "#4F46E5"), ("Credits", "Rs.1,00,000", "📈", "#10B981"),
                                     ("Debits", "Rs.62,400", "📉", "#EF4444"), ("Net", "Rs.37,600", "💰", "#10B981"),
                                     ("Transfers", "Rs.10,000", "🔄", "#8B5CF6")]:
        card = _make_card_frame(); cl = QVBoxLayout(card); cl.setContentsMargins(14, 10, 14, 10); cl.setSpacing(4)
        il = QLabel(ico); il.setStyleSheet(f"font-size:16px;background:{color}12;border-radius:20px;border:none;"); il.setFixedSize(36, 36); il.setAlignment(Qt.AlignCenter)
        cl.addWidget(il); cl.addWidget(_make_label(val, 18, C['text'], True))
        ll = QLabel(label); ll.setStyleSheet(f"color:{C['text3']};font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;background:transparent;border:none;")
        cl.addWidget(ll); kpi_row.addWidget(card)
    lay.addLayout(kpi_row)
    return w

def _build_db_filtered():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)
    bar = QFrame(); bar.setStyleSheet(f"QFrame{{background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:8px 12px;}}")
    br = QHBoxLayout(bar); br.setContentsMargins(4,4,4,4); br.setSpacing(6)
    br.addWidget(_make_label("From", 11, C['text3'])); br.addWidget(_make_date())
    br.addWidget(_make_label("To", 11, C['text3'])); br.addWidget(_make_date())
    div = QFrame(); div.setFixedHeight(24); div.setFixedWidth(1); div.setStyleSheet(f"background:{C['border']};"); br.addWidget(div)
    br.addWidget(_make_btn("🎯 Exact")); br.addWidget(_make_label("Filter", 11, C['text3']))
    br.addWidget(_make_combo(["Category", "Account", "Method", "Type", "Kind"]))
    br.addWidget(_make_combo(["Food & Dining", "Transport"])); br.addWidget(_make_btn("+ Add")); br.addWidget(_make_btn("⟳ Load", True))
    lay.addWidget(bar)
    chip_row = QHBoxLayout()
    chip = QPushButton("  Food & Dining  ✕"); chip.setStyleSheet(f"QPushButton{{background:{C['accent_bg']};color:{C['accent']};border:1px solid rgba(79,70,229,0.2);border-radius:12px;padding:2px 8px;font-size:11px;font-weight:600;}}"); chip.setFixedHeight(24)
    chip_row.addWidget(chip); chip2 = QPushButton("  Account: SBI  ✕"); chip2.setStyleSheet(chip.styleSheet()); chip2.setFixedHeight(24)
    chip_row.addWidget(chip2); chip_row.addStretch()
    lay.addLayout(chip_row)
    lay.addWidget(_make_label("Exact | 23 txns | Cr:Rs.50,000 | Db:Rs.11,500 | Net:Rs.38,500", 11, C['text3']))
    lay.addWidget(_make_sep())
    lay.addWidget(_tx_card(_sample_tx()))
    return w


# ── 4. BALANCES ──────────────────────────────────────────
def _build_balances_overview():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(10)
    # Net Worth Hero
    nw = QFrame(); nw.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #4338CA,stop:1 #6366F1);border-radius:14px;}QLabel{background:transparent;border:none;}")
    nl = QHBoxLayout(nw); nl.setContentsMargins(24, 18, 24, 18); nl.setSpacing(32)
    nc = QVBoxLayout(); nc.setSpacing(2)
    nc.addWidget(QLabel("<span style='color:rgba(255,255,255,0.6);font-size:10px;font-weight:700;letter-spacing:1.5px;'>NET WORTH</span>"))
    nv = QLabel("Rs.4,85,000"); nv.setStyleSheet("color:white;font-size:26px;font-weight:900;background:transparent;border:none;")
    nc.addWidget(nv); nl.addLayout(nc)
    sep = QFrame(); sep.setFixedWidth(1); sep.setStyleSheet("background:rgba(255,255,255,0.2);"); nl.addWidget(sep)
    for icon, label, val in [("🏦", "CURRENT ACC", "Rs.3,20,000"), ("💳", "CREDIT CARD", "-Rs.62,000"), ("💼", "WALLET", "Rs.12,000"), ("💵", "CASH", "Rs.15,000")]:
        tc = QVBoxLayout(); tc.setSpacing(2)
        tc.addWidget(QLabel(f"<span style='color:rgba(255,255,255,0.6);font-size:9px;font-weight:600;'>{icon} {label}</span>"))
        tv = QLabel(val); tv.setStyleSheet("color:white;font-size:15px;font-weight:700;background:transparent;border:none;")
        tc.addWidget(tv); nl.addLayout(tc)
    lay.addWidget(nw)
    # Account cards
    lay.addWidget(_make_label("Account Balances", 16, C['text'], True))
    for name, atype, bal, color in [("SBI Savings", "CURRENT", "Rs.1,20,000", "#4F46E5"), ("HDFC Bank", "CURRENT", "Rs.2,00,000", "#4F46E5"), ("ICICI Amazon CC", "CREDIT_CARD", "Rs.62,000", "#EF4444"), ("Cash at Home", "CASH", "Rs.15,000", "#F59E0B")]:
        card = QFrame(); card.setCursor(QCursor(Qt.PointingHandCursor))
        card.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border']};border-radius:8px;}}QFrame:hover{{border-color:{C['accent']};background:{C['accent_bg']};}}QLabel{{background:transparent;border:none;}}")
        cl = QHBoxLayout(card); cl.setContentsMargins(14, 8, 14, 8); cl.setSpacing(8)
        cl.addWidget(_make_label(name, 13, C['text'], True)); cl.addStretch()
        badge = QLabel(atype); badge.setStyleSheet(f"color:{color};font-size:9px;font-weight:700;background:{color}15;border-radius:6px;padding:2px 8px;background:transparent;border:none;")
        cl.addWidget(badge)
        bl = QLabel(bal); bl.setStyleSheet(f"font-size:14px;font-weight:800;color:{'#EF4444' if bal.startswith('-') else '#10B981'};background:transparent;border:none;")
        cl.addWidget(bl)
        lay.addWidget(card)
    return w

def _build_balances_drilldown():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    # CC drill-down header
    hdr = QFrame(); hdr.setFixedHeight(110)
    hdr.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3a3a3a,stop:1 #0f0f0f);border-radius:12px;}QLabel{background:transparent;border:none;}")
    hl = QVBoxLayout(hdr); hl.setContentsMargins(20, 12, 20, 12); hl.setSpacing(6)
    r1 = QHBoxLayout(); r1.addWidget(_make_label("ICICI Amazon Pay Card", 16, "white", True)); r1.addStretch()
    r1.addWidget(_make_label("VISA Platinum", 12, "rgba(255,255,255,0.7)")); hl.addLayout(r1)
    r2 = QHBoxLayout(); r2.setSpacing(24)
    for label, val, color in [("Limit", "Rs.2,00,000", "rgba(255,255,255,0.7)"), ("Statement", "Every 6th", "rgba(255,255,255,0.9)"),
                                ("Amount Due", "Rs.12,500", "#FCA5A5"), ("Due Date", "26 Jul 2026", "#FCA5A5"),
                                ("Current Outstanding", "Rs.62,000", "#F59E0B")]:
        c = QVBoxLayout(); c.setSpacing(0)
        c.addWidget(QLabel(f"<span style='color:rgba(255,255,255,0.5);font-size:9px;'>{label}</span>"))
        c.addWidget(QLabel(f"<b style='color:{color};font-size:13px;'>{val}</b>"))
        r2.addLayout(c)
    r2.addStretch(); hl.addLayout(r2)
    lay.addWidget(hdr)
    # Cycle header
    ch = QFrame(); ch.setMinimumHeight(40)
    ch.setStyleSheet(f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3a3a3a22,stop:1 #0f0f0f22);border:none;border-radius:8px;}}")
    cl = QHBoxLayout(ch); cl.setContentsMargins(10, 4, 10, 4); cl.setSpacing(8)
    cl.addWidget(_make_label("📅 Jul 2026  (stmt: 6th)", 12, C['text'], True)); cl.addStretch()
    cl.addWidget(_make_label("Spent: Rs.25,000", 12, "#DC2626", True))
    cl.addWidget(_make_label("Paid: Rs.12,500", 12, "#059669", True))
    cl.addWidget(_make_label("Remaining: Rs.12,500", 12, "#D97706", True))
    cl.addWidget(_make_label("Due: 26 Jul 2026", 11, C['text3']))
    lay.addWidget(ch)
    lay.addWidget(_make_label("  Monday, 20 Jul", 12, C['text3'], True))
    lay.addWidget(_tx_card(_sample_tx("DEBIT", 3500, "Amazon", "Electronics", "shopping", "Shopping", "#EC4899", "AMAZON PAY", "ICICI CC", tx_id="bd1")))
    lay.addWidget(_tx_card(_sample_tx("DEBIT", 1200, "Flipkart", "Clothes", "shopping", "Shopping", "#EC4899", "AMAZON PAY", "ICICI CC", tx_id="bd2")))
    return w


# ── 5. CREDIT CARDS ──────────────────────────────────────
def _build_cc_carousel():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    card = QFrame(); card.setFixedHeight(160)
    card.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3a3a3a,stop:1 #0f0f0f);border-radius:16px;}QLabel{background:transparent;border:none;}")
    cl = QVBoxLayout(card); cl.setContentsMargins(20, 12, 20, 12); cl.setSpacing(4)
    cl.addWidget(_make_label("ICICI BANK", 13, "white", True))
    cl.addWidget(_make_label("Amazon Pay", 10, "rgba(255,255,255,0.7)"))
    cl.addStretch()
    # Utilization bar
    bar_bg = QFrame(); bar_bg.setFixedHeight(14); bar_bg.setStyleSheet("background:rgba(255,255,255,0.1);border-radius:7px;")
    bl = QHBoxLayout(bar_bg); bl.setContentsMargins(2,2,2,2); bl.setSpacing(0)
    bar_fill = QFrame(); bar_fill.setStyleSheet("background:#F59E0B;border-radius:5px;")
    bl.addWidget(bar_fill, 65); bl.addStretch(35)
    cl.addWidget(bar_bg)
    pct_lbl = QLabel("65% utilized"); pct_lbl.setStyleSheet("color:rgba(255,255,255,0.9);font-size:7px;font-weight:700;background:transparent;border:none;"); pct_lbl.setAlignment(Qt.AlignCenter)
    cl.addWidget(pct_lbl)
    r = QHBoxLayout(); r.addWidget(_make_label("VISA", 14, "white", True)); r.addStretch(); r.addWidget(_make_label("Platinum", 10, "rgba(255,255,255,0.6)"))
    cl.addLayout(r)
    lay.addWidget(card, alignment=Qt.AlignCenter)
    # Back preview
    back = QFrame(); back.setFixedHeight(160)
    back.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3a3a3a,stop:1 #0f0f0f);border-radius:16px;}QLabel{background:transparent;border:none;}")
    bcl = QVBoxLayout(back); bcl.setContentsMargins(20, 12, 20, 12); bcl.setSpacing(4)
    stripe = QFrame(); stripe.setStyleSheet("background:rgba(0,0,0,0.85);")
    stripe_lay = QHBoxLayout(stripe); stripe_lay.setContentsMargins(0,6,0,6)
    stripe_lay.addWidget(_make_label("VIEW CARD DETAILS  ->", 9, "rgba(255,255,255,0.7)")); stripe_lay.setAlignment(Qt.AlignCenter)
    bcl.addWidget(stripe)
    bcl.addWidget(_make_label("CARDHOLDER NAME", 11, "rgba(255,255,255,0.8)"))
    bcl.addWidget(_make_label("XXXX  XXXX  XXXX  1234", 11, "white", True))
    bcl.addWidget(_make_label("Valid: 12/28", 9, "rgba(255,255,255,0.7)"))
    lay.addWidget(back, alignment=Qt.AlignCenter)
    tr = QHBoxLayout(); tr.setSpacing(8)
    tr.addWidget(_make_btn("✅ Active Cards", True)); tr.addWidget(_make_btn("⏸ Closed Cards"))
    tr.addWidget(_make_btn("＋  Add Card", True)); tr.addStretch()
    lay.addLayout(tr)
    return w

def _build_cc_settlement():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    lay.addWidget(_make_label("Settlement Footer", 13, C['text'], True))
    lay.addWidget(_make_label("Appears below transaction list when a card is selected", 11, C['text3']))
    footer = QFrame(); footer.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;}}")
    fl = QHBoxLayout(footer); fl.setContentsMargins(10, 6, 10, 6); fl.setSpacing(12)
    fl.addWidget(_make_label("Repay:", 12, C['text'], True))
    fl.addWidget(_make_combo(["Amount Due — Rs.12,500", "Current Outstanding — Rs.62,000", "Custom Amount..."]))
    fl.addWidget(_make_label("From:", 11, C['text3'])); fl.addWidget(_make_combo(["SBI Savings", "HDFC Bank"]))
    fl.addWidget(_make_label("Method:", 11, C['text3'])); fl.addWidget(_make_combo(["NETBANKING", "PHONEPAY"]))
    fl.addWidget(_make_label("Date:", 11, C['text3'])); fl.addWidget(_make_date())
    fl.addStretch()
    settle_btn = QPushButton("💰  Settle"); settle_btn.setStyleSheet(f"QPushButton{{background:transparent;color:{C['accent']};border:2px solid {C['accent']};border-radius:8px;padding:6px 20px;font-size:13px;font-weight:700;}}QPushButton:hover{{background:{C['accent']};color:white;}}")
    settle_btn.setFixedHeight(34); fl.addWidget(settle_btn)
    lay.addWidget(footer)
    return w

def _build_cc_reminders():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)
    lay.addWidget(_make_label("⏰  Reminders", 14, C['text'], True))
    reminders = [
        ("#DC2626", "🚨 OVERDUE 5d — ICICI Amazon (Jun 2026)  Rs.12,500"),
        ("#D97706", "📅 ICICI Amazon — Statement in 3d (Rs.62,000)"),
        ("#8B5CF6", "⚡ ICICI Amazon — Rs.3,500 on 18/07"),
        ("#D97706", "📅 SBI Card — Expires next month"),
    ]
    for color, text in reminders:
        row = QFrame(); row.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border2']};border-radius:8px;padding:6px 10px;")
        rl = QHBoxLayout(row); rl.setContentsMargins(8, 4, 8, 4)
        dot = QLabel("■"); dot.setFixedSize(16, 16); dot.setStyleSheet(f"background:{color};border-radius:3px;background:transparent;border:none;")
        rl.addWidget(dot); rl.addWidget(_make_label(text, 11, C['text']))
        lay.addWidget(row)
    return w


# ── 6. DEBIT CARDS ───────────────────────────────────────
def _build_dc_carousel():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    card = QFrame(); card.setFixedHeight(160)
    card.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #b8bcc2,stop:1 #5f656d);border-radius:16px;}QLabel{background:transparent;border:none;}")
    cl = QVBoxLayout(card); cl.setContentsMargins(20, 12, 20, 12); cl.setSpacing(4)
    cl.addWidget(_make_label("SBI Debit Card", 13, "white", True))
    cl.addWidget(_make_label("SBI Savings", 10, "rgba(255,255,255,0.7)"))
    cl.addStretch()
    r = QHBoxLayout(); r.addWidget(_make_label("VISA", 14, "white", True)); r.addStretch(); r.addWidget(_make_label("•••• 1234", 10, "rgba(255,255,255,0.6)"))
    cl.addLayout(r)
    lay.addWidget(card, alignment=Qt.AlignCenter)
    lay.addWidget(_make_label("20 metallic themes: Titanium, Gunmetal, Platinum, Silverforge, Aurum...", 10, C['text3']))
    tr = QHBoxLayout(); tr.setSpacing(8)
    tr.addWidget(_make_btn("✅ Active Cards", True)); tr.addWidget(_make_btn("⏸ Closed Cards"))
    tr.addWidget(_make_btn("＋  Add Card", True)); tr.addStretch()
    lay.addLayout(tr)
    return w

def _build_dc_transactions():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)
    hdr = QFrame(); hdr.setFixedHeight(60)
    hdr.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #b8bcc2,stop:1 #5f656d);border-radius:10px;}QLabel{background:transparent;border:none;}")
    hl = QHBoxLayout(hdr); hl.setContentsMargins(16, 8, 16, 8)
    hl.addWidget(_make_label("SBI Debit Card  VISA", 14, "white", True)); hl.addStretch()
    hl.addWidget(_make_label("-> SBI Savings", 11, "rgba(255,255,255,0.6)"))
    hl.addWidget(_make_btn("✏️ Edit"))
    lay.addWidget(hdr)
    mh = QFrame(); mh.setMinimumHeight(48)
    mh.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;}}QLabel{{background:transparent;border:none;}}")
    ml = QHBoxLayout(mh); ml.setContentsMargins(14, 6, 14, 6); ml.setSpacing(14)
    ml.addWidget(_make_label("📅 July 2026", 14, C['text'], True)); ml.addStretch()
    ml.addWidget(_make_label("Debits: Rs.12,000", 12, "#DC2626", True))
    ml.addWidget(_make_label("Credits: Rs.50,000", 12, "#059669", True))
    ml.addWidget(_make_label("Surplus: Rs.38,000", 12, "#059669", True))
    lay.addWidget(mh)
    lay.addWidget(_make_label("  Monday, 20 Jul", 11, C['text3'], True))
    lay.addWidget(_tx_card(_sample_tx("DEBIT", 500, "Swiggy", "Food order", "food_dining", "Food & Dining", "#F59E0B", "PHONEPAY", "SBI Savings", tx_id="dc1")))
    lay.addWidget(_tx_card(_sample_tx("CREDIT", 50000, "Company", "Salary", "salary", "Salary", "#10B981", "PHONEPAY", "SBI Savings", tx_id="dc2")))
    return w


# ── 7. WEALTH ────────────────────────────────────────────
def _build_wealth_loans_give():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)
    card = _make_card_frame()
    card.setStyleSheet(f"QFrame{{background:{C['accent_bg']};border:1.5px solid {C['accent']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
    cl = QVBoxLayout(card); cl.setContentsMargins(14, 10, 14, 10); cl.setSpacing(4)
    top = QHBoxLayout(); top.addWidget(_make_label("Rahul Kumar", 14, C['text'], True)); top.addStretch()
    top.addWidget(_make_badge("ACTIVE", C['accent'])); cl.addLayout(top)
    mid = QHBoxLayout(); mid.addWidget(_make_label("Given 2026-01-15  |  Due 2026-04-15  |  5% SI", 11, C['text3'])); mid.addStretch()
    mid.addWidget(_make_label("Rs.25,000  Principal", 18, C['text'], True)); cl.addLayout(mid)
    bar_bg = QFrame(); bar_bg.setFixedHeight(6); bar_bg.setStyleSheet(f"background:{C['border2']};border-radius:3px;")
    bl = QHBoxLayout(bar_bg); bl.setContentsMargins(0,0,0,0)
    bf = QFrame(); bf.setStyleSheet(f"background:{C['accent']};border-radius:3px;")
    bl.addWidget(bf, 20); bl.addStretch(80); cl.addWidget(bar_bg)
    cl.addWidget(_make_label("Rs.20,000 Outstanding  |  Interest: Rs.500  |  Paid: Rs.5,000", 11, C['text3']))
    lay.addWidget(card)
    lay.addWidget(_make_label("Click card to expand -> shows: detail table, edit form, repayment history, print PDF", 10, C['text3']))
    return w

def _build_wealth_loans_take():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)
    card = _make_card_frame()
    card.setStyleSheet(f"QFrame{{background:{_hex_rgba(C['amber'], 0.08)};border:1.5px solid {C['amber']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
    cl = QVBoxLayout(card); cl.setContentsMargins(14, 10, 14, 10); cl.setSpacing(4)
    top = QHBoxLayout(); top.addWidget(_make_label("HDFC Bank", 14, C['text'], True)); top.addStretch()
    top.addWidget(_make_badge("OVERDUE", C['red'])); cl.addLayout(top)
    mid = QHBoxLayout(); mid.addWidget(_make_label("Rate 12% CI Ann  |  EMI Rs.8,885  |  Due 2027-01-15", 11, C['text3'])); mid.addStretch()
    mid.addWidget(_make_label("Rs.5,00,000  Principal", 18, C['text'], True)); cl.addLayout(mid)
    bar_bg = QFrame(); bar_bg.setFixedHeight(6); bar_bg.setStyleSheet(f"background:{C['border2']};border-radius:3px;")
    bl = QHBoxLayout(bar_bg); bl.setContentsMargins(0,0,0,0)
    bf = QFrame(); bf.setStyleSheet(f"background:{C['red']};border-radius:3px;")
    bl.addWidget(bf, 35); bl.addStretch(65); cl.addWidget(bar_bg)
    cl.addWidget(_make_label("Rs.3,25,000 Outstanding  |  Updated EMI: Rs.9,120  |  Paid: Rs.1,75,000  |  Interest: Rs.45,000", 11, C['text3']))
    lay.addWidget(card)
    return w

def _build_wealth_fd():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)
    card = _make_card_frame()
    card.setStyleSheet(f"QFrame{{background:{_hex_rgba(C['accent'], 0.06)};border:1.5px solid {C['accent']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
    cl = QVBoxLayout(card); cl.setContentsMargins(14, 10, 14, 10); cl.setSpacing(4)
    top = QHBoxLayout(); top.addWidget(_make_label("SBI Savings", 14, C['text'], True)); top.addStretch()
    top.addWidget(_make_badge("ACTIVE", C['accent'])); cl.addLayout(top)
    mid = QHBoxLayout(); mid.addWidget(_make_label("7.1%  |  2026-01-01 -> 2027-01-01", 11, C['text3'])); mid.addStretch()
    mid.addWidget(_make_label("Rs.1,00,000  Principal", 18, C['text'], True)); cl.addLayout(mid)
    bar_bg = QFrame(); bar_bg.setFixedHeight(6); bar_bg.setStyleSheet(f"background:{C['border2']};border-radius:3px;")
    bl = QHBoxLayout(bar_bg); bl.setContentsMargins(0,0,0,0)
    bf = QFrame(); bf.setStyleSheet(f"background:{C['accent']};border-radius:3px;")
    bl.addWidget(bf, 55); bl.addStretch(45); cl.addWidget(bar_bg)
    cl.addWidget(_make_label("Rs.1,07,100 Maturity Value  |  55% elapsed", 11, C['text3']))
    lay.addWidget(card)
    return w

def _build_wealth_mf():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)
    card = _make_card_frame()
    card.setStyleSheet(f"QFrame{{background:{_hex_rgba(C['green'], 0.06)};border:1.5px solid {C['green']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
    cl = QVBoxLayout(card); cl.setContentsMargins(14, 10, 14, 10); cl.setSpacing(4)
    top = QHBoxLayout(); top.addWidget(_make_label("Parag Parikh — Flexi Cap Fund", 14, C['text'], True)); top.addStretch()
    top.addWidget(_make_badge("+18.5%", C['green'])); cl.addLayout(top)
    mid = QHBoxLayout(); mid.addWidget(_make_label("Equity  |  125.5000 units  |  NAV 58.4320", 11, C['text3'])); mid.addStretch()
    mid.addWidget(_make_label("Rs.7,338", 18, C['text'], True)); cl.addLayout(mid)
    cl.addWidget(_make_label("Invested: Rs.6,191", 11, C['text3']))
    lay.addWidget(card)
    return w


# ── 8. AUDIT ─────────────────────────────────────────────
def _build_audit_filters():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)
    r1 = QHBoxLayout(); r1.setSpacing(6)
    r1.addWidget(_make_label("From", 11, C['text3'])); r1.addWidget(_make_date())
    r1.addWidget(_make_label("To", 11, C['text3'])); r1.addWidget(_make_date())
    r1.addWidget(_make_label("Filter", 11, C['text3'])); r1.addWidget(_make_combo(["Category", "Account", "Method", "Type", "Kind"]))
    r1.addWidget(_make_combo(["Food & Dining", "Transport"])); r1.addWidget(_make_btn("+ Add")); r1.addWidget(_make_btn("⟳ Load", True))
    lay.addLayout(r1)
    chip_row = QHBoxLayout()
    chip = QPushButton("  Food & Dining  ✕"); chip.setStyleSheet(f"QPushButton{{background:{C['accent_bg']};color:{C['accent']};border:1px solid rgba(79,70,229,0.2);border-radius:12px;padding:2px 8px;font-size:11px;font-weight:600;}}"); chip.setFixedHeight(24)
    chip_row.addWidget(chip); chip_row.addStretch()
    lay.addLayout(chip_row)
    lay.addWidget(_make_label("23 txns | Cr:Rs.50,000 | Db:Rs.11,500 | Net:Rs.38,500", 11, C['text3']))
    lay.addWidget(_make_sep())
    lay.addWidget(_tx_card(_sample_tx("DEBIT", 500, "Swiggy", "Food order", "food_dining", "Food & Dining", "#F59E0B", "PHONEPAY", "SBI Savings", tx_id="af1")))
    return w

def _build_audit_bulk():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)
    for checked in [True, True, False]:
        r = QHBoxLayout(); r.setSpacing(8)
        chk = QPushButton("✓ Done" if checked else "  Select  ")
        chk.setStyleSheet(f"QPushButton{{background:{C['accent'] if checked else C['surface']};color:{'white' if checked else C['text3']};border:2px solid {C['accent'] if checked else C['border']};border-radius:8px;font-size:12px;font-weight:700;}}QPushButton:hover{{background:{C['accent']};color:white;}}")
        chk.setFixedHeight(34); chk.setMinimumWidth(82)
        r.addWidget(chk); r.addWidget(_make_btn("✏️ Edit"))
        lay.addLayout(r)
    lay.addWidget(_make_sep())
    toolbar = QHBoxLayout(); toolbar.setSpacing(8)
    toolbar.addWidget(_make_label("2 selected", 12, C['text'], True))
    toolbar.addWidget(_make_label("Category:", 11, C['text3'])); toolbar.addWidget(_make_combo(["Food & Dining", "Transport"]))
    toolbar.addWidget(_make_label("Need/Want:", 11, C['text3'])); toolbar.addWidget(_make_combo(["Need", "Want"]))
    toolbar.addStretch(); toolbar.addWidget(_make_btn("✅ Apply to 2 Selected", True))
    lay.addLayout(toolbar)
    return w

def _build_audit_insights():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    r = QHBoxLayout()
    r.addWidget(_make_label("From", 11, C['text3'])); r.addWidget(_make_date())
    r.addWidget(_make_label("To", 11, C['text3'])); r.addWidget(_make_date())
    for txt in ["This Month", "Last Month", "This Year", "All Time"]:
        r.addWidget(_make_btn(txt))
    r.addStretch(); r.addWidget(_make_btn("Apply", True))
    lay.addLayout(r)
    kpi = QHBoxLayout(); kpi.setSpacing(10)
    for label, val, color in [("Total Credits", "Rs.1,00,000", C['green']), ("Total Debits", "Rs.62,400", C['red']),
                                ("Net", "Rs.37,600", C['green']), ("Transactions", "89", C['text'])]:
        card = _make_card_frame(); cl = QVBoxLayout(card); cl.setContentsMargins(14, 10, 14, 10); cl.setSpacing(4)
        cl.addWidget(_make_label(val, 18, color, True))
        ll = QLabel(label); ll.setStyleSheet(f"color:{C['text3']};font-size:10px;font-weight:600;text-transform:uppercase;background:transparent;border:none;")
        cl.addWidget(ll); kpi.addWidget(card)
    lay.addLayout(kpi)
    lay.addWidget(_make_label("📊 Charts render here (Category doughnut, Account bar, Daily trend, Need vs Want)", 12, C['text3']))
    return w


# ── 9. NOTES ─────────────────────────────────────────────
def _build_notes_all():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    lay.addWidget(_make_input(placeholder="🔍  Search notes by title or tag..."))
    card = _make_card_frame(); card.setStyleSheet(f"QFrame{{background:{_hex_rgba(C['accent'], 0.08)};border:1.5px solid {C['accent']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
    cl = QVBoxLayout(card); cl.setContentsMargins(16, 12, 16, 12); cl.setSpacing(8)
    top = QHBoxLayout(); top.addWidget(_make_label("Grocery List", 14, C['text'], True)); top.addStretch()
    top.addWidget(_make_badge("🔗 2", C['accent'])); cl.addLayout(top)
    chip_row = QHBoxLayout()
    for tag in ["shopping", "monthly"]:
        chip = QPushButton(f" #{tag} "); chip.setStyleSheet(f"QPushButton{{background:{C['accent']};color:white;border:none;border-radius:12px;padding:3px 10px;font-size:11px;font-weight:700;}}")
        chip_row.addWidget(chip)
    chip_row.addStretch(); cl.addLayout(chip_row)
    cl.addWidget(_make_label("Milk, eggs, bread, vegetables, fruits, chicken, rice, dal, oil, spices", 12, C['text2']))
    lay.addWidget(card)
    card2 = _make_card_frame(); card2.setStyleSheet(f"QFrame{{background:{_hex_rgba(C['green'], 0.08)};border:1.5px solid {C['green']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
    c2l = QVBoxLayout(card2); c2l.setContentsMargins(16, 12, 16, 12); c2l.setSpacing(4)
    top2 = QHBoxLayout(); top2.addWidget(_make_label("Meeting Notes", 14, C['text'], True)); top2.addStretch()
    top2.addWidget(_make_badge("🔗 5", C['green'])); c2l.addLayout(top2)
    chip2 = QHBoxLayout(); chip2.addWidget(QPushButton(" #work ")); chip2.addStretch(); c2l.addLayout(chip2)
    lay.addWidget(card2)
    return w

def _build_notes_compose():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    lay.addWidget(_make_label("📝  New Note", 18, C['accent'], True))
    lay.addWidget(_make_input("Grocery List", "Title"))
    lay.addWidget(_make_label("Tags", 12, C['text2'], True))
    tag_row = QHBoxLayout()
    for tag in ["shopping", "monthly"]:
        chip = QPushButton(f" #{tag} ✕"); chip.setStyleSheet(f"QPushButton{{background:{C['accent']};color:white;border:none;border-radius:12px;padding:3px 10px;font-size:11px;font-weight:700;}}")
        tag_row.addWidget(chip)
    tag_row.addStretch(); lay.addLayout(tag_row)
    lay.addWidget(_make_input("", "Type tag + Enter, or pick below..."))
    content = QLabel("Write your note here...\n\nMilk, eggs, bread, vegetables")
    content.setStyleSheet(f"background:{C['surface']};border:1.5px solid {C['border']};border-radius:8px;padding:10px;font-size:12px;color:{C['text2']};")
    content.setMinimumHeight(80); lay.addWidget(content)
    btn_row = QHBoxLayout(); btn_row.addStretch()
    btn_row.addWidget(_make_btn("Cancel")); btn_row.addWidget(_make_btn("💾  Save Note", True))
    lay.addLayout(btn_row)
    return w

def _build_notes_trash():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    lay.addWidget(_make_label("🗑️  Trash & Recovery", 18, C['red'], True))
    lay.addWidget(_make_label("Recover deleted notes or remove them permanently.", 12, C['text3']))
    for title, tags, deleted in [("Old Budget Plan", "finance, budget", "2026-07-15 10:30"), ("Temp Notes", "temp", "2026-07-10 14:20")]:
        row = QFrame(); row.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;}}QLabel{{background:transparent;border:none;}}")
        rl = QHBoxLayout(row); rl.setContentsMargins(16, 10, 16, 10); rl.setSpacing(12)
        ic = QVBoxLayout(); ic.setSpacing(2)
        ic.addWidget(_make_label(title, 13, C['text'], True)); ic.addWidget(_make_label(tags, 11, C['text3']))
        rl.addLayout(ic, 1); rl.addWidget(_make_label(deleted, 11, C['text3']))
        rl.addWidget(_make_btn("Recover", True)); rl.addWidget(_make_btn("Delete Forever"))
        lay.addWidget(row)
    return w


# ── 10. GMAIL ────────────────────────────────────────────
def _build_gmail_stub():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(12)
    icon = QLabel("📧"); icon.setStyleSheet("font-size:64px;background:transparent;border:none;"); icon.setAlignment(Qt.AlignCenter)
    lay.addWidget(icon)
    lay.addWidget(_make_label("Gmail Sync", 22, C['text'], True))
    lay.addWidget(_make_label("Gmail suggested transactions will appear here once Gmail sync is configured.", 13, C['text3']))
    lay.addWidget(_make_badge("Coming Soon", C['amber']))
    return w


# ── 11. SETTINGS ─────────────────────────────────────────
def _build_settings_accounts():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    lay.addWidget(_make_btn("+ Add Account", True))
    for group, color, accounts in [
        ("🏦  Bank Accounts (3)", "#4F46E5", [("SBI Savings", "SBI0", "CURRENT", "Rs.1,20,000"), ("HDFC Bank", "HDFC", "CURRENT", "Rs.2,00,000")]),
        ("💳  Credit Cards (1)", "#7C3AED", [("ICICI Amazon CC", "ICIC", "CREDIT_CARD", "Rs.0")]),
        ("💵  Cash (1)", "#F59E0B", [("Cash at Home", "CASH", "CASH", "Rs.15,000")]),
    ]:
        lay.addWidget(_make_label(group, 13, color, True))
        for name, label, atype, bal in accounts:
            row = QFrame(); row.setFixedHeight(44)
            row.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-left:3px solid {color};border-radius:8px;}}QLabel{{background:transparent;border:none;}}")
            rl = QHBoxLayout(row); rl.setContentsMargins(12, 0, 12, 0); rl.setSpacing(16)
            rl.addWidget(_make_label(f"<b>{name}</b>", 12, C['text'])); rl.addWidget(_make_label(label, 11, C['text3']))
            badge = QLabel(atype); badge.setStyleSheet(f"color:{color};font-size:9px;font-weight:700;background:{color}15;border-radius:4px;padding:2px 6px;background:transparent;border:none;")
            rl.addWidget(badge); rl.addWidget(_make_label("OPENING BALANCE", 9, C['text3']))
            rl.addWidget(_make_label(bal, 12, C['text'], True)); rl.addStretch()
            rl.addWidget(_make_btn("Edit")); rl.addWidget(_make_btn("Deactivate"))
            lay.addWidget(row)
    return w

def _build_settings_categories():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)
    lay.addWidget(_make_btn("+ Add Category", True))
    for icon, name, pf, color in [("🍔", "Food & Dining", "consumption", "#F59E0B"), ("🚗", "Transport", "consumption", "#3B82F6"),
                                     ("🛍️", "Shopping", "consumption", "#EC4899"), ("💰", "Salary", "growth", "#10B981"),
                                     ("📈", "Investment", "growth", "#8B5CF6")]:
        row = QFrame(); row.setStyleSheet(f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:8px;}}QLabel{{background:transparent;border:none;}}")
        rl = QHBoxLayout(row); rl.setContentsMargins(12, 6, 12, 6); rl.setSpacing(16)
        il = QLabel(icon); il.setStyleSheet("font-size:20px;background:transparent;border:none;"); il.setAlignment(Qt.AlignCenter); il.setFixedSize(32, 32)
        rl.addWidget(il); rl.addWidget(_make_label(name, 12, C['text'], True))
        rl.addWidget(_make_label(pf, 11, C['text3']))
        dot = QLabel("●"); dot.setStyleSheet(f"color:{color};font-size:18px;background:transparent;border:none;")
        rl.addWidget(dot); rl.addStretch(); rl.addWidget(_make_btn("Edit"))
        lay.addWidget(row)
    return w

def _build_settings_security():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(10)
    # 2FA
    tfa = _make_card_frame(); tl = QVBoxLayout(tfa); tl.setContentsMargins(16, 12, 16, 12); tl.setSpacing(8)
    tl.addWidget(_make_label("🔐  Two-Factor Authentication", 14, C['text'], True))
    tl.addWidget(_make_label("✓ TOTP Enabled", 13, C['green']))
    r = QHBoxLayout(); r.addWidget(_make_label("Require TOTP for login & edits:", 12, C['text2'])); r.addStretch()
    toggle = QPushButton("ON"); toggle.setFixedSize(64, 28)
    toggle.setStyleSheet(f"QPushButton{{background:{C['green']};color:white;border:none;border-radius:14px;padding:2px 16px;font-size:11px;font-weight:700;}}")
    r.addWidget(toggle); tl.addLayout(r); tl.addWidget(_make_btn("✏️  Edit 2FA Key"))
    lay.addWidget(tfa)
    # Tab Security
    ts = _make_card_frame(); tsl = QVBoxLayout(ts); tsl.setContentsMargins(16, 12, 16, 12); tsl.setSpacing(8)
    tsl.addWidget(_make_label("🔒  Tab Security (Optional)", 14, C['text'], True))
    tsl.addWidget(_make_label("Enable password protection for specific tabs.", 11, C['text3']))
    for name, protected in [("🔐  Wealth", True), ("🔍  Audit", False), ("🗄️  Database", False), ("💳  Credit Cards", False), ("📋  Notes", False), ("⚙️  Settings", False)]:
        row = QFrame(); row.setStyleSheet(f"QFrame{{background:{C['bg']};border:1px solid {C['border2']};border-radius:8px;}}QLabel{{background:transparent;border:none;}}")
        rl = QHBoxLayout(row); rl.setContentsMargins(10, 6, 10, 6)
        rl.addWidget(_make_label(name, 12, C['text2'])); rl.addStretch()
        t = QPushButton("ON" if protected else "OFF"); t.setFixedSize(64, 28)
        t.setStyleSheet(f"QPushButton{{background:{C['green'] if protected else C['text3']};color:white;border:none;border-radius:14px;padding:2px 16px;font-size:11px;font-weight:700;}}")
        rl.addWidget(t); tsl.addWidget(row)
    lay.addWidget(ts)
    return w

def _build_settings_prefs():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(10)
    grp = _make_card_frame(); gl = QFormLayout(grp); gl.setContentsMargins(16, 12, 16, 12); gl.setSpacing(10)
    gl.addRow("Theme:", _make_label("Light (locked)", 12, C['text3']))
    gl.addRow("Currency:", _make_label("Rs. Indian", 12, C['text3']))
    lay.addWidget(grp)
    grp2 = _make_card_frame(); gl2 = QFormLayout(grp2); gl2.setContentsMargins(16, 12, 16, 12); gl2.setSpacing(10)
    gl2.addRow(_make_label("📊  Pagination", 14, C['text'], True))
    ps = QSpinBox(); ps.setRange(30, 1000); ps.setValue(150); ps.setFixedHeight(32)
    gl2.addRow("Page Size:", ps)
    st = QSpinBox(); st.setRange(50, 2000); st.setValue(400); st.setFixedHeight(32)
    gl2.addRow("Scroll Trigger (px):", st)
    lay.addWidget(grp2)
    grp3 = _make_card_frame(); gl3 = QFormLayout(grp3); gl3.setContentsMargins(16, 12, 16, 12); gl3.setSpacing(10)
    gl3.addRow(_make_label("🔔  Alerts", 14, C['text'], True))
    alert = QSpinBox(); alert.setRange(100, 100000); alert.setValue(499); alert.setPrefix("Rs. "); alert.setFixedHeight(32)
    gl3.addRow("High-Value Alert:", alert)
    lay.addWidget(grp3)
    lay.addWidget(_make_btn("💾  Save Settings", True))
    return w

def _build_settings_data():
    w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(10)
    bk = _make_card_frame(); bl = QVBoxLayout(bk); bl.setContentsMargins(16, 12, 16, 12); bl.setSpacing(8)
    bl.addWidget(_make_label("📦  Backup", 14, C['text'], True))
    bl.addWidget(_make_label("Location: finance_data/backups/\nRetention: 14 backups\nCurrent: 3\nLast: 24 Jul 2026, 10:30 AM", 12, C['text2']))
    bl.addWidget(_make_btn("📦  Backup Now", True))
    lay.addWidget(bk)
    cs = QFrame(); cs.setStyleSheet(f"QFrame{{background:{C['accent_bg']};border:1.5px dashed {C['accent']};border-radius:12px;}}QLabel{{background:transparent;border:none;}}")
    csl = QVBoxLayout(cs); csl.setContentsMargins(16, 12, 16, 12); csl.setSpacing(8)
    rocket = QLabel("🚀"); rocket.setStyleSheet("font-size:28px;background:transparent;border:none;"); rocket.setAlignment(Qt.AlignCenter)
    csl.addWidget(rocket)
    csl.addWidget(_make_label("Coming Soon", 14, C['accent'], True))
    csl.addWidget(_make_label("• Data Export (CSV / Excel)\n• Data Import from Bank Statements\n• Data Take Down (Delete All Data)\n• Cloud Backup & Sync", 12, C['text2']))
    lay.addWidget(cs)
    return w


# ═══════════════════════════════════════════════
# HELPER for rgba
# ═══════════════════════════════════════════════
def _hex_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ═══════════════════════════════════════════════
# WALKTHROUGH CONTENT DATABASE
# ═══════════════════════════════════════════════

WALKTHROUGH_DB = [
    {
        "title": "Home",
        "icon": "🏠",
        "tab_key": "home",
        "sub_tabs": [
            {
                "title": "KPI Period Cards",
                "proto_func": _build_home_kpi,
                "explanation": (
                    "Four clickable period cards at the top of the Home page.\n\n"
                    "• Each card shows: period label, total expense, transaction count\n"
                    "• Click a card to select it — selected card turns indigo with white text\n"
                    "• Selection triggers recalculation of ALL content below (charts, top transactions, savings)\n"
                    "• Default selection on app load: 'This Month'\n"
                    "• Date ranges: Today = single day, Week = last 7 days, Month = 1st to today, Year = Jan 1 to today"
                ),
            },
            {
                "title": "Charts",
                "proto_func": _build_home_charts,
                "explanation": (
                    "Four Chart.js charts rendered in a QWebEngineView:\n\n"
                    "• Spending by Category — doughnut chart of debit amounts grouped by category\n"
                    "• Spending Trend — line chart (daily for today/week/month, monthly for year)\n"
                    "  Today's data point highlighted in red\n"
                    "• Need vs Want — horizontal stacked bar showing need vs want split\n"
                    "• Income vs Expense by Account — horizontal grouped bar per account\n\n"
                    "All 4 charts regenerate together when KPI period changes. "
                    "HTML is built with data injected as JSON, written to a temp file, loaded into QWebEngineView."
                ),
            },
            {
                "title": "Top Transactions & Savings",
                "proto_func": _build_home_top_tx,
                "explanation": (
                    "Right column of the Home page:\n\n"
                    "Top Transactions:\n"
                    "• Top 7 debit transactions sorted by amount (highest first)\n"
                    "• Uses the same _tx_card widget as the Database tab\n"
                    "• Display-only — no click action\n\n"
                    "Savings Rate:\n"
                    "• Calculation: (income - expense) / income × 100\n"
                    "• Excludes transfers from both income and expense\n"
                    "• Green bar if positive, red if negative\n"
                    "• Shows: Income, Savings, Expense breakdown"
                ),
            },
            {
                "title": "Quick Access Tiles",
                "proto_func": _build_home_tiles,
                "explanation": (
                    "One-click navigation to every tab in the app.\n\n"
                    "• 10 tiles: Transactions, Database, Balances, Credit Cards, Debit Cards, Audit, Wealth, Notes, Settings, Gmail\n"
                    "• Each tile has emoji icon + label + colored left border\n"
                    "• Click any tile to navigate to that tab\n"
                    "• Hover highlights the tile with accent color border"
                ),
            },
        ],
    },
    {
        "title": "Transactions",
        "icon": "📝",
        "tab_key": "transaction_entry",
        "sub_tabs": [
            {
                "title": "Regular Entry",
                "proto_func": _build_tx_entry,
                "explanation": (
                    "The main transaction entry form:\n\n"
                    "• Amount: Rs. spinner, starts at Rs.1 to prevent accidental zero entries\n"
                    "• DEBIT/CREDIT toggle: Switches between red DEBIT and green CREDIT styling\n"
                    "• Account: Searchable dropdown (type to filter), shows type suffix (e.g. 'SBI Savings  |  Debit')\n"
                    "• Category: Searchable dropdown — updates PF preview label on change\n"
                    "• Method: Searchable dropdown — auto-creates if not found in DB\n"
                    "• Date: Calendar popup, changes reload recent transactions (±7 days)\n"
                    "• Need/Want: 3 toggle buttons (None=gray, Need=indigo, Want=amber)\n"
                    "• Person/Org + Description: Free text fields\n"
                    "• Add Transaction: Validates account + method, creates transaction, shows status label, clears form"
                ),
            },
            {
                "title": "Transfer",
                "proto_func": _build_tx_transfer,
                "explanation": (
                    "Transfer money between your own accounts:\n\n"
                    "• From/To: Searchable account dropdowns with swap button (⇄)\n"
                    "• From/To exclusion: Selecting one account removes it from the other combo\n"
                    "• Creates two linked transactions (DEBIT from source, CREDIT to destination)\n"
                    "• Both share a transfer_group_id for tracking\n"
                    "• Transfer button: Guard flag prevents double-transfer (Enter key + rapid clicks)\n\n"
                    "Razorpay-style success animation:\n"
                    "1. Circle scale-up (spring overshoot)\n"
                    "2. Checkmark draws (short leg -> long leg)\n"
                    "3. Ripple ring expands + fades\n"
                    "4. Amount counts up (30 steps, ease-out)\n"
                    "5. Flow label fades in (From -> To)\n"
                    "6. 'Transfer Successful' + Done button fade in\n"
                    "Done button auto-focused after animation completes."
                ),
            },
            {
                "title": "Gmail Queue",
                "proto_func": _build_tx_gmail,
                "explanation": (
                    "Gmail suggested transactions will appear here.\n\n"
                    "Status: Coming Soon\n"
                    "This tab will show transactions suggested by Gmail sync once configured."
                ),
            },
        ],
    },
    {
        "title": "Database",
        "icon": "🗄️",
        "tab_key": "database",
        "sub_tabs": [
            {
                "title": "Complete View",
                "proto_func": _build_db_complete,
                "explanation": (
                    "Shows ALL transactions with running balances:\n\n"
                    "• Search bar: Client-side filter by person, description, amount, category, account\n"
                    "• Lazy scroll: Loads 150 transactions per batch (configurable in Settings)\n"
                    "• Triggers when within 400px of bottom\n"
                    "• Month -> Day grouping with month headers and day headers\n"
                    "• Each card shows: category icon, description, amount (+/-), type badge, category, method, account\n"
                    "• Running balances computed via SQL window function in single pass\n"
                    "• Transaction kind badges (🔗 for wealth-linked, Updated for edited)"
                ),
            },
            {
                "title": "Monthly View",
                "proto_func": _build_db_monthly,
                "explanation": (
                    "Monthly statement view with 3 sub-tabs:\n\n"
                    "Transactions: Card list grouped by Month -> Day with running balances\n\n"
                    "Summary:\n"
                    "• 5 KPI stat cards (Transactions, Credits, Debits, Net, Transfers)\n"
                    "• Account summary grid grouped by type (Bank/Wallet/Cash/Credit Card)\n"
                    "• Each account card: Credits, Debits, Start Balance, End Balance\n"
                    "• Credit cards show utilization bar\n\n"
                    "Visualization: 4 Chart.js charts (same as Home but for selected month)\n\n"
                    "Print Statement: Exports to PDF with full statement layout"
                ),
            },
            {
                "title": "Filtered View",
                "proto_func": _build_db_filtered,
                "explanation": (
                    "Advanced filter system:\n\n"
                    "• Date range: From/To date pickers\n"
                    "• Mode toggle: 🎯 Exact (client-side) or 🔗 Sequential (DB-level for single-value)\n"
                    "• 11 filter fields: Account, Category, Method, Type, Kind, Need/Want, PF Category, Person/Org, Description, Min/Max Amount\n"
                    "• Multi-value: Same field can have multiple values (OR-combined)\n"
                    "• +Add: Adds current filter value as a chip. Auto-loads results\n"
                    "• Chip click (✕): Removes that specific value, re-loads\n"
                    "• Stats: Shows count, credits, debits, net\n"
                    "• Print: Exports filtered results to PDF"
                ),
            },
        ],
    },
    {
        "title": "Balances",
        "icon": "💰",
        "tab_key": "balances",
        "sub_tabs": [
            {
                "title": "Net Worth & Accounts",
                "proto_func": _build_balances_overview,
                "explanation": (
                    "Account balances overview:\n\n"
                    "Net Worth Hero Card:\n"
                    "• Large indigo gradient card showing total net worth\n"
                    "• Breakdown by account type: Current, Credit Card, Wallet, Cash\n"
                    "• Credit cards show negative (money owed)\n\n"
                    "Account Cards:\n"
                    "• Grouped by type with colored headers\n"
                    "• Each card: Name, type badge, balance (green if positive, red if negative)\n"
                    "• Credit cards show utilization bar\n"
                    "• Single-account type: Group header itself is clickable\n"
                    "• Multi-account type: Individual cards are clickable\n"
                    "• Click any account to drill down into its transactions"
                ),
            },
            {
                "title": "Account Drill-down",
                "proto_func": _build_balances_drilldown,
                "explanation": (
                    "Click an account to see its transactions:\n\n"
                    "Non-CC accounts:\n"
                    "• Paginated month/day grouped transactions with running balances\n"
                    "• Lazy scroll loads more on scroll\n\n"
                    "Credit Card accounts:\n"
                    "• Full header card (like Cards tab) with: Limit, Statement, Amount Due, Due Date, Current Outstanding\n"
                    "• FIFO cycles computed from statement_date\n"
                    "• Cycle headers: Cycle name, Spent, Paid, Remaining, Due Date\n"
                    "• Transactions grouped by date within each cycle\n"
                    "• Unassigned transactions shown under 'Earlier Transactions'\n\n"
                    "← Back button returns to Recent Transactions view"
                ),
            },
        ],
    },
    {
        "title": "Credit Cards",
        "icon": "💳",
        "tab_key": "cards",
        "sub_tabs": [
            {
                "title": "Card Carousel",
                "proto_func": _build_cc_carousel,
                "explanation": (
                    "3D carousel with smooth 60fps animation:\n\n"
                    "• Drag or scroll wheel to browse cards\n"
                    "• Left/Right arrow keys scroll, Space bar flips nearest card\n"
                    "• Front: Bank name, co-brand, utilization bar (color-coded), network name, card class\n"
                    "• Back: 'VIEW CARD DETAILS' stripe, cardholder name, card number, expiry\n"
                    "• Click card to flip (front ↔ back)\n"
                    "• Click 'VIEW CARD DETAILS' stripe -> opens card details below\n"
                    "• Timer: Continuous 60fps (16ms), starts on showEvent, stops on hideEvent\n"
                    "• Active/Closed sub-tabs switch between active and deactivated cards\n"
                    "• Auto-close: Cards past expiry month/year are auto-deactivated on load"
                ),
            },
            {
                "title": "Settlement",
                "proto_func": _build_cc_settlement,
                "explanation": (
                    "Settle credit card bills:\n\n"
                    "• Settlement footer appears below transaction list when a card is selected\n"
                    "• Options: Amount Due (FIFO-accumulated), Current Outstanding, Custom Amount\n"
                    "• Source account combo (excludes credit cards)\n"
                    "• Payment method, Date picker\n"
                    "• Settle button -> creates transfer pair (DEBIT from source, CREDIT to card account)\n"
                    "• Confirmation dialog before settlement\n"
                    "• After settlement: Refreshes details, reminders, carousel utilization\n"
                    "• FIFO cycles are re-computed and saved to card_cycles table"
                ),
            },
            {
                "title": "Reminders",
                "proto_func": _build_cc_reminders,
                "explanation": (
                    "Right panel shows up to 15 reminders sorted by urgency:\n\n"
                    "• 🚨 Overdue: Past due date with remaining > 0 (red)\n"
                    "• 📅 Statement generating: 5 days before statement date, if balance > 0 (amber)\n"
                    "• 💰 Due date reminders: Per cycle from card_cycles table\n"
                    "• ⚡ High-value transactions: ≥ Rs.499 (configurable) in last 5 days (purple)\n"
                    "• ⚠️ Card expiry: This month or next month warnings\n\n"
                    "Reminders update in real-time after settlements and card changes."
                ),
            },
        ],
    },
    {
        "title": "Debit Cards",
        "icon": "💳",
        "tab_key": "debit_cards",
        "sub_tabs": [
            {
                "title": "Card Carousel",
                "proto_func": _build_dc_carousel,
                "explanation": (
                    "Same 3D carousel as Credit Cards with metallic gradient themes:\n\n"
                    "• 20 metallic themes: Titanium, Gunmetal, Platinum, Silverforge, Aurum, Bullion, Copperline, Bronzework, Ironclad, Graphite, Chrome, Carbon, Pewter, Nickel, Zinc, Palladium, Forge, Alloy, Blacksteel, Champagne\n"
                    "• Front: Card name, connected account, chip, network, class\n"
                    "• Back: 'VIEW ACCOUNT DETAILS' stripe, cardholder, number, expiry\n"
                    "• Completely independent from CC tab (zero imports from cards_tab.py)\n"
                    "• Timer: 60fps, starts on showEvent, stops on hideEvent\n"
                    "• Auto-close: Cards past expiry month/year are auto-deactivated"
                ),
            },
            {
                "title": "Account Transactions",
                "proto_func": _build_dc_transactions,
                "explanation": (
                    "Transactions from the connected current account:\n\n"
                    "• Header: Card name, network, connected bank account, Edit button\n"
                    "• Monthly grouping with gradient headers matching card colors\n"
                    "• Each month header: Month name, total Debits, Credits, Surplus/Deficit\n"
                    "• Transactions grouped by day within each month\n\n"
                    "Smart Lazy Scroll:\n"
                    "• Loads 1 month first\n"
                    "• If < 4 transactions, expands to load more (up to 6 months)\n"
                    "• Then 3 months per batch on scroll\n"
                    "• setUpdatesEnabled(False) during widget addition to prevent layout lag"
                ),
            },
        ],
    },
    {
        "title": "Wealth",
        "icon": "📈",
        "tab_key": "wealth",
        "sub_tabs": [
            {
                "title": "Loans I Give",
                "proto_func": _build_wealth_loans_give,
                "explanation": (
                    "Track money you lend to others:\n\n"
                    "Entry: Borrower (searchable + add new), Amount, Interest Rate, Method (Simple/Compound), Pay From, Method, Start/Due Date\n\n"
                    "List:\n"
                    "• Sort by: Status, Borrower, Amount, Due Date\n"
                    "• Search by borrower name\n"
                    "• KPI: Total Pending, Pending Loans, Total Loans\n"
                    "• Cards: Color-coded by status (Active=indigo, Overdue=red, Repaid=green, Closed=gray)\n"
                    "• Progress bar shows repayment percentage\n"
                    "• Click to expand -> detail table, edit form, repayment history (with inline edit), Mark as Closed, Print PDF\n"
                    "• 'Print Pending' button: PDF of all non-closed items for a selected borrower\n\n"
                    "Log Repayment: Select loan, enter amount, creates CREDIT transaction linked to loan"
                ),
            },
            {
                "title": "Loans I Take",
                "proto_func": _build_wealth_loans_take,
                "explanation": (
                    "Track money you borrow from others:\n\n"
                    "Entry: Lender (searchable + add new), Repayment Type (EMI/Non-EMI), Interest Method, Compounding, Principal, Rate, Tenure, EMI preview\n\n"
                    "List:\n"
                    "• Sort by: Status, Lender, Amount, Due Date\n"
                    "• KPI: Total Outstanding, Active Loans, Total Loans\n"
                    "• Alerts: OVERDUE warnings, EMI due soon (within 1 month)\n"
                    "• Cards show: Rate/method/frequency tags, EMI type, progress bar, outstanding/updated EMI/paid/interest\n"
                    "• Click to expand -> edit form, repayment history, Mark as Closed, Print PDF\n\n"
                    "Log EMI: Amount types (Updated EMI, Original EMI, Full Pay, Custom)"
                ),
            },
            {
                "title": "FD I Deposit",
                "proto_func": _build_wealth_fd,
                "explanation": (
                    "Track your fixed deposits:\n\n"
                    "Entry: Bank Account, Principal, Interest Method (Simple/Compound), Compounding, Rate, Start/Maturity Date, Maturity preview\n\n"
                    "List:\n"
                    "• Sort by: Status, Account, Maturity Date\n"
                    "• KPI: Active Principal, Active Maturity, Matured Value, Total FDs\n"
                    "• Progress bar shows % elapsed\n"
                    "• Actions: Mark Matured, Mark Withdrawn (with premature fee calculation)"
                ),
            },
            {
                "title": "FD Others Deposit",
                "proto_func": _build_wealth_fd,
                "explanation": (
                    "Track deposits received from others:\n\n"
                    "Entry: Depositor (searchable + add new), Amount, Interest-Free toggle, Rate, Received Into, Date, Expected Return Date\n\n"
                    "List:\n"
                    "• Sort by: Status, Depositor, Amount, Return Date\n"
                    "• KPI: Total Outstanding, Active Deposits, Total Deposits\n"
                    "• Cards show: Interest tag, progress bar, outstanding/interest/paid\n"
                    "• Click to expand -> edit form, repayment history, Mark as Closed, Print PDF"
                ),
            },
            {
                "title": "Mutual Funds",
                "proto_func": _build_wealth_mf,
                "explanation": (
                    "Track mutual fund investments:\n\n"
                    "Entry:\n"
                    "• Purchase/SIP: Scheme (searchable + add new), Amount, NAV (auto-fetch from API), Units preview\n"
                    "• Redemption: Scheme, Holdings display, Units to Redeem, NAV, Redemption preview\n\n"
                    "List:\n"
                    "• Sort by: Return %, Scheme Name, Invested, Current Value\n"
                    "• KPI: Invested, Current Value, Overall Return %\n"
                    "• Cards show: AMC — Scheme, type, units, NAV, current value, return % badge\n"
                    "• Background NAV fetch: On app start, fetches latest NAVs via api.mfapi.in\n"
                    "• NavFetchDialog: Search funds, double-click to fetch NAV, auto-links scheme code"
                ),
            },
        ],
    },
    {
        "title": "Audit",
        "icon": "🔍",
        "tab_key": "audit",
        "sub_tabs": [
            {
                "title": "Filters & Records",
                "proto_func": _build_audit_filters,
                "explanation": (
                    "Advanced filter system for all transactions:\n\n"
                    "• Date range: From/To date pickers\n"
                    "• 11 filter fields with multi-value chip selection\n"
                    "• Chips show active filters with ✕ to remove individual values\n"
                    "• Stats bar: transaction count, Credits, Debits, Net\n"
                    "• Lazy scroll: Loads in batches (configurable)\n"
                    "• Each card has: Select button (toggle), transaction card, Edit button\n"
                    "• Two sub-tabs: Regular Transactions (all) and Wealth Transactions (linked only)"
                ),
            },
            {
                "title": "Edit & Bulk Update",
                "proto_func": _build_audit_bulk,
                "explanation": (
                    "Edit and bulk update with security verification:\n\n"
                    "Single Edit:\n"
                    "• Click Edit -> TransactionEditDialog with all fields\n"
                    "• Wealth-linked: Type locked, Person/Org locked; Amount/Date locked if CLOSED\n"
                    "• Save requires 2FA/password verification\n"
                    "• Shows 'Updating...' popup -> '✓ Updated!' with OK button\n"
                    "• Cascade: Amount/date changes push to linked wealth records\n"
                    "• Transfer cascade: Changes propagate to related transfer transaction\n\n"
                    "Bulk Update:\n"
                    "• Select/Done toggle buttons on each transaction\n"
                    "• Change Category, Need/Want, PF Category in bulk\n"
                    "• Requires 2FA/password verification\n"
                    "• Progress popup during updates (updates UI every 10 items)"
                ),
            },
            {
                "title": "Insights",
                "proto_func": _build_audit_insights,
                "explanation": (
                    "Analytics view with custom period:\n\n"
                    "• Date range with quick buttons: This Month, Last Month, This Year, All Time\n"
                    "• 4 KPI cards: Total Credits, Total Debits, Net, Transactions\n"
                    "• 4 Chart.js charts: Category doughnut, Account bar, Daily/Monthly trend, Need vs Want\n"
                    "• Auto-aggregates by month if range > 90 days, else by day\n"
                    "• Charts resize when switching to this view"
                ),
            },
        ],
    },
    {
        "title": "Notes",
        "icon": "📋",
        "tab_key": "notes",
        "sub_tabs": [
            {
                "title": "All Notes",
                "proto_func": _build_notes_all,
                "explanation": (
                    "View and search all notes:\n\n"
                    "• Search box: Real-time filter by title or tag\n"
                    "• NoteCard widgets with accent-colored border (derived from first tag)\n"
                    "• Each card shows: Title, linked badge (🔗 count), tag chips\n"
                    "• Click card to expand -> content, linked transactions (grouped by date), action buttons (Print, Edit, Delete)\n"
                    "• Only one card expanded at a time (accordion pattern)\n"
                    "• Lazy scroll: Loads 50 notes per batch (configurable)"
                ),
            },
            {
                "title": "New / Edit Note",
                "proto_func": _build_notes_compose,
                "explanation": (
                    "Two-column compose view:\n\n"
                    "Left — Note Content:\n"
                    "• Title field (required)\n"
                    "• Tags: Chip input with autocomplete suggestions (type + Enter, arrow keys navigate, Enter selects)\n"
                    "  Can create new tags inline. Tags shown as colored chips with ✕ to remove\n"
                    "• Content: Multi-line text editor\n"
                    "• Save/Cancel buttons\n\n"
                    "Right — Link Transactions:\n"
                    "• Date range + filter field/value for finding transactions\n"
                    "• Select All button to link all filtered transactions\n"
                    "• Transaction list with checkbox toggles (✓ linked, ○ unlinked)\n"
                    "• Shows 'Linked: N txns  |  Net: Rs.X' summary\n"
                    "• Linked IDs stored as JSON array in note record"
                ),
            },
            {
                "title": "Trash & Recovery",
                "proto_func": _build_notes_trash,
                "explanation": (
                    "Soft-delete with recovery:\n\n"
                    "• Deleted notes move to Trash (soft delete)\n"
                    "• Each trash item shows: Title, tags, deleted date\n"
                    "• Recover button: Restores note to active\n"
                    "• Delete Forever: Confirmation dialog -> permanent deletion"
                ),
            },
        ],
    },
    {
        "title": "Gmail",
        "icon": "📧",
        "tab_key": "gmail",
        "sub_tabs": [
            {
                "title": "Gmail Sync",
                "proto_func": _build_gmail_stub,
                "explanation": (
                    "Gmail integration — Coming Soon.\n\n"
                    "This tab will show:\n"
                    "• Transactions suggested from Gmail inbox\n"
                    "• Sender rules for auto-categorization\n"
                    "• Scan history"
                ),
            },
        ],
    },
    {
        "title": "Settings",
        "icon": "⚙️",
        "tab_key": "settings",
        "sub_tabs": [
            {
                "title": "Accounts",
                "proto_func": _build_settings_accounts,
                "explanation": (
                    "Manage all your accounts:\n\n"
                    "• Accounts grouped by type: Bank Accounts, Credit Cards, Cash, Wallets\n"
                    "• Single-line rows: Name, Label, Type badge, Opening Balance, INACTIVE badge\n"
                    "• Add: Dialog with Name, Label (4-char), Type (CURRENT/CASH/WALLET), Opening Balance\n"
                    "• Edit: Same dialog (type locked). Credit Card accounts redirect to AddCardDialog\n"
                    "• Activate/Deactivate: Toggles is_active on account + associated cards"
                ),
            },
            {
                "title": "Categories & Lookups",
                "proto_func": _build_settings_categories,
                "explanation": (
                    "Manage categories, payment methods, and tags:\n\n"
                    "Categories:\n"
                    "• Table: Icon, Name, PF Category, Tax, Color, Edit button\n"
                    "• Add: Icon picker (96 emoji palette), name, PF category, color picker (24 disc palette), tax checkbox\n"
                    "• Edit: Same dialog pre-filled. Icon stored in preferences table\n\n"
                    "Payment Methods:\n"
                    "• Table: Name, Status, Activate/Deactivate toggle\n"
                    "• Toggle switches is_active — does NOT delete (hides from dropdowns)\n\n"
                    "Tags:\n"
                    "• Table: Name, Active status\n"
                    "• Add: Simple input dialog"
                ),
            },
            {
                "title": "Security",
                "proto_func": _build_settings_security,
                "explanation": (
                    "Security settings:\n\n"
                    "2FA / TOTP:\n"
                    "• Compact toggle button (64×28) for ON/OFF\n"
                    "• Edit 2FA Key: Generates new secret, shows QR code + manual key, requires 6-digit verification\n"
                    "• If 2FA on: requires current TOTP to edit. If off: requires password\n\n"
                    "Google Account:\n"
                    "• Link: Opens browser OAuth flow, stores email + refresh token\n"
                    "• Unlink: Confirmation -> removes Google account\n\n"
                    "Change Password: Two input dialogs (new + confirm)\n\n"
                    "Tab Security:\n"
                    "• Per-tab toggles: Wealth, Audit, Database, Credit Cards, Notes, Gmail, Settings\n"
                    "• Each toggle requires password/TOTP verification (custom 400px styled dialog)\n"
                    "• ON: Inserts row into tab_security table. OFF: Deletes row\n"
                    "• Cancel reverts toggle state"
                ),
            },
            {
                "title": "Preferences",
                "proto_func": _build_settings_prefs,
                "explanation": (
                    "App preferences:\n\n"
                    "• Theme: Light (locked)\n"
                    "• Currency: Rs. Indian (locked)\n"
                    "• Pagination: Page Size + Scroll Trigger for Database, Wealth, Notes\n"
                    "• Alerts: High-Value Transaction Alert threshold (default Rs.499)\n"
                    "• Save writes all values to preferences table"
                ),
            },
            {
                "title": "Data Management",
                "proto_func": _build_settings_data,
                "explanation": (
                    "Backup and storage:\n\n"
                    "• Backup: Location, retention (14 backups), current count, last backup time\n"
                    "• Backup Now: Creates copy of finance.db in finance_data/backups/\n"
                    "• Storage Info: Database size, backup size\n\n"
                    "Coming Soon:\n"
                    "• Data Export (CSV / Excel)\n"
                    "• Data Import from Bank Statements\n"
                    "• Data Take Down (Delete All Data)\n"
                    "• Cloud Backup & Sync"
                ),
            },
        ],
    },
]


# ═══════════════════════════════════════════════
# WALKTHROUGH PAGE WIDGET
# ═══════════════════════════════════════════════

class WalkthroughPage(QWidget):
    """Full-page walkthrough with expandable topics and real widget prototypes."""
    navigate_to = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = -1
        self._current_sub = (0, 0)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        main = QHBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Left panel ──
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(0)

        hdr = QFrame()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"QFrame{{background:{C['accent']};border:none;}}QLabel{{background:transparent;border:none;}}")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 0, 16, 0)
        hdr_lbl = QLabel("🧭  Walkthrough")
        hdr_lbl.setStyleSheet("color:white;font-size:15px;font-weight:800;background:transparent;border:none;")
        hdr_lay.addWidget(hdr_lbl)
        left.addWidget(hdr)

        left_scroll = QScrollArea()
        left_scroll.setFixedWidth(240)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        left_inner = QWidget()
        left_inner.setStyleSheet(f"background:{C['surface2']};")
        self.left_lay = QVBoxLayout(left_inner)
        self.left_lay.setContentsMargins(8, 8, 8, 8)
        self.left_lay.setSpacing(2)
        self._build_topic_list()
        self.left_lay.addStretch()
        left_scroll.setWidget(left_inner)
        left.addWidget(left_scroll)

        left_container = QWidget()
        left_container.setFixedWidth(240)
        left_container.setStyleSheet(f"background:{C['surface2']};border-right:1px solid {C['border2']};")
        left_container.setLayout(left)
        main.addWidget(left_container)

        # ── Right panel ──
        right = QVBoxLayout()
        right.setContentsMargins(28, 16, 28, 16)
        right.setSpacing(12)

        title_row = QHBoxLayout()
        self.title_label = QLabel()
        self.title_label.setStyleSheet(f"font-size:18px;font-weight:800;color:{C['text']};background:transparent;border:none;")
        title_row.addWidget(self.title_label)
        title_row.addStretch()
        self.goto_btn = QPushButton("🔗  Go to this tab")
        self.goto_btn.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:white;border:none;"
            f"border-radius:8px;padding:6px 18px;font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{background:#4338CA;}}")
        self.goto_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.goto_btn.clicked.connect(self._go_to_tab)
        self.goto_btn.setFixedHeight(32)
        title_row.addWidget(self.goto_btn)
        right.addLayout(title_row)

        right.addWidget(_make_sep())

        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.NoFrame)
        self.content_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background:transparent;")
        self.content_lay = QVBoxLayout(self.content_widget)
        self.content_lay.setSpacing(16)
        self.content_lay.setContentsMargins(0, 0, 8, 0)
        self.content_scroll.setWidget(self.content_widget)
        right.addWidget(self.content_scroll, 1)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(12)
        self.prev_btn = QPushButton("←  Previous")
        self.prev_btn.setStyleSheet(
            f"QPushButton{{background:{C['surface']};color:{C['text2']};border:1px solid {C['border']};"
            f"border-radius:8px;padding:8px 20px;font-size:13px;font-weight:600;}}"
            f"QPushButton:hover{{border-color:{C['accent']};color:{C['accent']};}}")
        self.prev_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.prev_btn.clicked.connect(self._prev)
        nav_row.addWidget(self.prev_btn)
        nav_row.addStretch()
        self.step_label = QLabel()
        self.step_label.setStyleSheet(f"color:{C['text3']};font-size:12px;background:transparent;border:none;")
        nav_row.addWidget(self.step_label)
        nav_row.addStretch()
        self.next_btn = QPushButton("Next  ->")
        self.next_btn.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:white;border:none;"
            f"border-radius:8px;padding:8px 24px;font-size:13px;font-weight:700;}}"
            f"QPushButton:hover{{background:#4338CA;}}")
        self.next_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.next_btn.clicked.connect(self._next)
        self.next_btn.setMinimumHeight(38)
        nav_row.addWidget(self.next_btn)
        right.addLayout(nav_row)

        right_container = QWidget()
        right_container.setLayout(right)
        main.addWidget(right_container, 1)

        outer.addLayout(main)

        # Show first topic
        self._select_sub(0, 0)

    def _build_topic_list(self):
        while self.left_lay.count():
            itm = self.left_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()

        for i, topic in enumerate(WALKTHROUGH_DB):
            is_expanded = (i == self._expanded)
            btn = QPushButton(f"{'▼' if is_expanded else '▶'}  {topic['icon']}  {topic['title']}")
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setMinimumHeight(34)
            btn.setStyleSheet(self._topic_btn_css(is_expanded))
            btn.clicked.connect(lambda _, idx=i: self._toggle_topic(idx))
            self.left_lay.addWidget(btn)

            if is_expanded:
                for j, sub in enumerate(topic.get("sub_tabs", [])):
                    is_selected = (self._current_sub == (i, j))
                    sub_btn = QPushButton(f"      {sub['title']}")
                    sub_btn.setCursor(QCursor(Qt.PointingHandCursor))
                    sub_btn.setMinimumHeight(30)
                    sub_btn.setStyleSheet(self._sub_btn_css(is_selected))
                    sub_btn.clicked.connect(lambda _, ti=i, si=j: self._select_sub(ti, si))
                    self.left_lay.addWidget(sub_btn)

    def _topic_btn_css(self, expanded):
        if expanded:
            return (f"QPushButton{{background:{C['accent']};color:white;border:none;"
                    f"border-radius:8px;padding:8px 12px;text-align:left;font-size:12px;font-weight:700;}}")
        return (f"QPushButton{{background:transparent;color:{C['text2']};border:none;"
                f"border-radius:8px;padding:8px 12px;text-align:left;font-size:12px;font-weight:600;}}"
                f"QPushButton:hover{{background:{C['surface']};color:{C['text']};}}")

    def _sub_btn_css(self, selected):
        if selected:
            return (f"QPushButton{{background:{C['accent_bg']};color:{C['accent']};border:none;"
                    f"border-radius:6px;padding:6px 12px;text-align:left;font-size:11px;font-weight:700;}}")
        return (f"QPushButton{{background:transparent;color:{C['text3']};border:none;"
                f"border-radius:6px;padding:6px 12px;text-align:left;font-size:11px;font-weight:500;}}"
                f"QPushButton:hover{{background:{C['surface']};color:{C['text']};}}")

    def _toggle_topic(self, idx):
        self._expanded = idx if self._expanded != idx else -1
        self._build_topic_list()

    def _select_sub(self, topic_idx, sub_idx):
        self._current_sub = (topic_idx, sub_idx)
        self._expanded = topic_idx
        self._build_topic_list()

        topic = WALKTHROUGH_DB[topic_idx]
        sub = topic["sub_tabs"][sub_idx]

        self.title_label.setText(f"{topic['icon']}  {topic['title']} — {sub['title']}")
        self.goto_btn.setVisible(topic.get("tab_key") is not None)

        while self.content_lay.count():
            itm = self.content_lay.takeAt(0)
            if itm.widget(): itm.widget().deleteLater()

        if sub.get("proto_func"):
            proto_frame = QFrame()
            proto_frame.setStyleSheet(
                f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #c9ced3,stop:1 #59616b);border:1px solid {C['border2']};border-radius:10px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            proto_lay = QVBoxLayout(proto_frame)
            proto_lay.setContentsMargins(16, 12, 16, 12)
            proto_lay.setSpacing(6)
            proto_title = QLabel("🔍 Live Prototype")
            proto_title.setStyleSheet("color:#1E293B;font-size:11px;font-weight:700;background:transparent;border:none;")
            proto_lay.addWidget(proto_title)
            proto_widget = sub["proto_func"]()
            proto_lay.addWidget(proto_widget)
            self.content_lay.addWidget(proto_frame)

        if sub.get("explanation"):
            exp_frame = QFrame()
            exp_frame.setStyleSheet(
                f"QFrame{{background:{C['surface']};border:1px solid {C['border2']};border-radius:10px;}}"
                f"QLabel{{background:transparent;border:none;}}")
            exp_lay = QVBoxLayout(exp_frame)
            exp_lay.setContentsMargins(16, 12, 16, 12)
            exp_lay.setSpacing(6)
            exp_title = QLabel("📖 How It Works")
            exp_title.setStyleSheet(f"color:{C['accent']};font-size:11px;font-weight:700;background:transparent;border:none;")
            exp_lay.addWidget(exp_title)
            exp_lbl = QLabel(sub["explanation"])
            exp_lbl.setStyleSheet(f"font-size:12px;color:{C['text2']};line-height:1.5;background:transparent;border:none;")
            exp_lbl.setWordWrap(True)
            exp_lay.addWidget(exp_lbl)
            self.content_lay.addWidget(exp_frame)

        self.content_lay.addStretch()
        self.content_scroll.verticalScrollBar().setValue(0)
        self._update_nav()

    def _update_nav(self):
        flat_idx = 0
        total = 0
        for i, topic in enumerate(WALKTHROUGH_DB):
            for j, sub in enumerate(topic["sub_tabs"]):
                if i == self._current_sub[0] and j == self._current_sub[1]:
                    flat_idx = total
                total += 1
        self.step_label.setText(f"Step {flat_idx + 1} of {total}")
        self.prev_btn.setEnabled(flat_idx > 0)
        self.next_btn.setText("Finish  ✓" if flat_idx == total - 1 else "Next  ->")

    def _next(self):
        ti, si = self._current_sub
        subs = WALKTHROUGH_DB[ti]["sub_tabs"]
        if si < len(subs) - 1:
            self._select_sub(ti, si + 1)
        elif ti < len(WALKTHROUGH_DB) - 1:
            self._select_sub(ti + 1, 0)

    def _prev(self):
        ti, si = self._current_sub
        if si > 0:
            self._select_sub(ti, si - 1)
        elif ti > 0:
            prev_subs = WALKTHROUGH_DB[ti - 1]["sub_tabs"]
            self._select_sub(ti - 1, len(prev_subs) - 1)

    def _go_to_tab(self):
        topic = WALKTHROUGH_DB[self._current_sub[0]]
        if topic.get("tab_key"):
            self.navigate_to.emit(topic["tab_key"])
