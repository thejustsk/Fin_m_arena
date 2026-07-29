"""Finance Manager v3 — Design System.

Two palettes (light / dark) live in ``PALETTES``. ``C`` is the *active*
palette and is deliberately a plain dict that is mutated in place — every
module does ``from ui.theme import C`` and reads ``C['accent']`` at widget
build time, so swapping the contents of this one dict re-themes the whole
app without touching 24 import sites.

Switching theme therefore needs two steps:
    1. ``apply_theme("dark")``   — swaps the palette + rebuilds QSS
    2. rebuild the widget tree   — because inline setStyleSheet() strings
                                   were already baked with the old colours

Dark values were chosen for contrast, not just darkness: body text sits at
>= 7:1 against its background and secondary text at >= 4.5:1 (WCAG AA).
"""

# ── Palettes ──────────────────────────────────────────────────────────────
LIGHT = {
    "bg": "#F0F2F5", "surface": "#FFFFFF", "surface2": "#F8F9FA",
    "border": "#D0D5DD", "border2": "#E5E7EB",
    "text": "#101828", "text2": "#344054", "text3": "#667085",
    "accent": "#4F46E5", "accent_bg": "#EEF2FF", "accent_hover": "#4338CA",
    "on_accent": "#FFFFFF",
    "green": "#059669", "green_bg": "#ECFDF5",
    "red": "#DC2626", "red_bg": "#FEF2F2",
    "amber": "#D97706", "amber_bg": "#FFFBEB",
    "sidebar": "#FFFFFF", "sidebar_text": "#4338CA",
    "tooltip_bg": "#111827", "tooltip_fg": "#FFFFFF", "tooltip_border": "#374151",
    "shadow": "rgba(16,24,40,0.08)",
    "chart_surface": "#FFFFFF",
    "skeleton": "#E9ECEF", "skeleton_hi": "#F4F6F8",
    "radius": "12px", "radius_sm": "8px",
}

# Dark palette. Surfaces step upward (bg < surface < surface2) so stacked
# cards read as raised, matching the light theme's shadow hierarchy.
DARK = {
    "bg": "#0F1117", "surface": "#181B23", "surface2": "#212530",
    "border": "#333846", "border2": "#2A2F3A",
    # 15.8:1, 9.7:1 and 5.4:1 against #181B23
    "text": "#F2F4F8", "text2": "#C3C9D6", "text3": "#949CAD",
    # Lifted from #4F46E5 — indigo goes muddy on dark backgrounds
    "accent": "#8B85F5", "accent_bg": "#232338", "accent_hover": "#A29BFF",
    "on_accent": "#12121C",
    "green": "#3DD68C", "green_bg": "#152B22",
    "red": "#FF6B6B", "red_bg": "#2E1A1D",
    "amber": "#F0B429", "amber_bg": "#2E2415",
    "sidebar": "#141720", "sidebar_text": "#A9A3FF",
    "tooltip_bg": "#F2F4F8", "tooltip_fg": "#0F1117", "tooltip_border": "#4A5163",
    "shadow": "rgba(0,0,0,0.45)",
    # Slightly raised from the normal card surface so charts remain readable.
    "chart_surface": "#202632",
    "skeleton": "#252A35", "skeleton_hi": "#2F3542",
    "radius": "12px", "radius_sm": "8px",
}

PALETTES = {"light": LIGHT, "dark": DARK}

# The live palette. Mutated in place by apply_theme() — never rebind it.
C = dict(LIGHT)

_ACTIVE = "light"


def active_theme():
    """Name of the palette currently in use."""
    return _ACTIVE


def is_dark():
    return _ACTIVE == "dark"


def build_qss(c=None):
    """Render the global stylesheet against a palette (defaults to live C)."""
    c = c if c is not None else C
    return _QSS_TEMPLATE.format(C=c)


def apply_theme(name, app=None):
    """Swap the active palette in place and refresh the global stylesheet.

    Returns the new QSS. Callers must still rebuild widgets that used inline
    setStyleSheet(), since those strings were baked with the old colours.
    """
    global _ACTIVE, QSS
    if name not in PALETTES:
        name = "light"
    _ACTIVE = name
    C.clear()
    C.update(PALETTES[name])
    QSS = build_qss(C)
    if app is not None:
        app.setStyleSheet(QSS)
    return QSS


def chart_vars():
    """Colour substitutions for the Chart.js HTML templates."""
    return {
        "__PAGE_BG__": C["bg"],
        "__CARD_BG__": C["chart_surface"],
        "__CARD_BORDER__": C["border2"],
        "__TITLE__": C["text2"],
        "__SHADOW__": C["shadow"],
        "__GRID__": C["border2"],
        "__TICK__": C["text3"],
        "__SCROLL_TRACK__": C["surface2"],
        "__SCROLL_THUMB__": C["border"],
    }


def apply_chart_theme(html):
    """Substitute palette placeholders and Chart.js defaults into *html*."""
    for k, v in chart_vars().items():
        html = html.replace(k, v)
    # Chart.js draws its own labels; force them onto the themed colours.
    inject = (
        "<script>if(window.Chart){Chart.defaults.color='%s';"
        "Chart.defaults.borderColor='%s';}</script>" % (C["text3"], C["border2"])
    )
    return html.replace("</head>", inject + "</head>", 1)


def load_theme_pref(db, default="light"):
    """Read the saved theme from preferences; never raises."""
    try:
        row = db.execute(
            "SELECT value FROM preferences WHERE key='theme'").fetchone()
        if row and row["value"] in PALETTES:
            return row["value"]
    except Exception:
        pass
    return default


def save_theme_pref(db, name):
    """Persist the chosen theme; never raises."""
    try:
        db.execute("INSERT OR REPLACE INTO preferences(key, value) VALUES('theme', ?)",
                   (name,))
        db.commit()
    except Exception:
        pass


_QSS_TEMPLATE = """
* {{ font-family: 'Inter','Segoe UI',system-ui,sans-serif; font-size: 13px; color: {C[text]}; }}
QMainWindow, QWidget#central {{ background: {C[bg]}; }}
QPushButton {{
    background: {C[surface]}; border: 1px solid {C[border]};
    border-radius: {C[radius_sm]}; padding: 8px 16px; font-weight: 500;
}}
QPushButton:hover {{ border-color: {C[accent]}; }}
QPushButton#primary {{ background: {C[accent]}; color: {C[on_accent]}; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: {C[accent_hover]}; }}
QPushButton#danger {{ background: {C[red]}; color: white; border: none; }}
QPushButton#pill {{
    background: {C[surface2]}; border: 1px solid {C[border2]};
    border-radius: 20px; padding: 6px 16px; font-size: 12px;
}}
QPushButton#ghost {{ background: transparent; border: none; color: {C[text3]}; }}
QLineEdit, QTextEdit {{
    background: {C[surface]}; border: 1.5px solid {C[border]};
    border-radius: {C[radius_sm]}; padding: 8px 12px;
    font-size: 13px; color: {C[text]};
}}
QLineEdit:hover, QTextEdit:hover {{ border-color: {C[accent]}; }}
QLineEdit:focus, QTextEdit:focus {{ border-color: {C[accent]}; }}
QLineEdit:disabled, QTextEdit:disabled {{
    background: {C[surface2]}; color: {C[text3]}; border-color: {C[border2]};
}}

/* ═══════ QDateEdit — Global Style ═══════ */
QDateEdit {{
    background: {C[surface]};
    border: 1.5px solid {C[border]};
    border-radius: {C[radius_sm]};
    padding: 6px 32px 6px 12px;
    font-size: 13px;
    font-weight: 500;
    color: {C[text]};
    min-height: 24px;
    min-width: 120px;
}}
QDateEdit:hover {{ border-color: {C[accent]}; }}
QDateEdit:focus {{ border-color: {C[accent]}; }}
QDateEdit:disabled {{
    background: {C[surface2]}; color: {C[text3]}; border-color: {C[border2]};
}}
QDateEdit::drop-down {{
    border: none;
    background: transparent;
    width: 28px;
    subcontrol-position: center right;
}}
QDateEdit::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {C[text3]};
    margin-right: 8px;
}}
QCalendarWidget {{
    background: {C[surface]};
    border: 1px solid {C[border2]};
    border-radius: {C[radius_sm]};
}}
QCalendarWidget QWidget {{
    alternate-background-color: {C[surface2]};
}}
QCalendarWidget QAbstractItemView:enabled {{
    color: {C[text]};
    background: {C[surface]};
    selection-background-color: {C[accent]};
    selection-color: white;
    border: none;
    outline: none;
    font-size: 13px;
}}
QCalendarWidget QAbstractItemView:disabled {{
    color: {C[text3]};
}}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background: {C[accent]};
    padding: 4px;
    border-radius: {C[radius_sm]} {C[radius_sm]} 0 0;
}}
QCalendarWidget QToolButton {{
    color: white;
    background: transparent;
    border: none;
    font-weight: 700;
    font-size: 13px;
    padding: 4px 8px;
    border-radius: 4px;
}}
QCalendarWidget QToolButton:hover {{
    background: rgba(255,255,255,0.2);
}}
QCalendarWidget QToolButton::menu-indicator {{
    image: none;
}}
QCalendarWidget QSpinBox {{
    color: white;
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 4px;
    padding: 2px 4px;
    font-size: 13px;
    font-weight: 700;
}}
QCalendarWidget QSpinBox::up-button, QCalendarWidget QSpinBox::down-button {{
    background: transparent;
    border: none;
}}
QCalendarWidget QSpinBox::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid white;
}}
QCalendarWidget QSpinBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid white;
}}
QCalendarWidget QTableView {{
    gridline-color: {C[border2]};
}}

/* ═══════ QSpinBox / QDoubleSpinBox — Global Style ═══════ */
QSpinBox, QDoubleSpinBox {{
    background: {C[surface]};
    border: 1.5px solid {C[border]};
    border-radius: {C[radius_sm]};
    padding: 6px 8px;
    font-size: 13px;
    font-weight: 500;
    color: {C[text]};
    min-height: 24px;
}}
QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {C[accent]}; }}
QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {C[accent]}; }}
QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background: {C[surface2]}; color: {C[text3]}; border-color: {C[border2]};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    background: {C[surface2]};
    border: none;
    border-left: 1px solid {C[border]};
    border-bottom: 1px solid {C[border]};
    border-top-right-radius: {C[radius_sm]};
    width: 24px;
    margin: 0;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background: {C[accent_bg]};
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background: {C[surface2]};
    border: none;
    border-left: 1px solid {C[border]};
    border-top: 1px solid {C[border]};
    border-bottom-right-radius: {C[radius_sm]};
    width: 24px;
    margin: 0;
}}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {C[accent_bg]};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-bottom: 6px solid {C[text3]};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {C[text3]};
}}

/* ═══════ QComboBox — Global Style ═══════ */
QComboBox {{
    background: {C[surface]};
    border: 1.5px solid {C[border]};
    border-radius: {C[radius_sm]};
    padding: 6px 32px 6px 12px;
    font-size: 13px;
    font-weight: 500;
    color: {C[text]};
    min-height: 24px;
}}
QComboBox:hover {{
    border-color: {C[accent]};
}}
QComboBox:focus {{
    border-color: {C[accent]};
}}
QComboBox:disabled {{
    background: {C[surface2]};
    color: {C[text3]};
    border-color: {C[border2]};
}}
QComboBox::drop-down {{
    border: none;
    background: transparent;
    width: 22px;
    subcontrol-position: center right;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {C[text3]};
    margin-right: 6px;
}}
QComboBox::down-arrow:hover {{
    border-top-color: {C[accent]};
}}
QComboBox QAbstractItemView {{
    background: {C[surface]};
    border: 1px solid {C[border2]};
    border-radius: {C[radius_sm]};
    outline: none;
    padding: 4px;
}}
QComboBox QAbstractItemView::item {{
    padding: 8px 12px;
    border-radius: 6px;
    min-height: 20px;
}}
QComboBox QAbstractItemView::item:selected {{
    background: {C[accent]};
    color: white;
}}
QComboBox QAbstractItemView::item:hover {{
    background: {C[accent_bg]};
    color: {C[accent]};
}}
QComboBox QLineEdit {{
    background: transparent;
    border: none;
    padding: 0;
    font-size: 13px;
    color: {C[text]};
}}
QTabBar::tab {{ background: transparent; color: {C[text3]}; padding: 10px 18px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {C[accent]}; border-bottom-color: {C[accent]}; }}
QTableWidget {{ background: {C[surface]}; border: 1px solid {C[border2]}; border-radius: {C[radius]}; }}
QHeaderView::section {{ background: {C[surface2]}; color: {C[text3]}; font-weight: 600; font-size: 11px; border: none; padding: 10px 12px; }}
QFrame#card {{ background: {C[surface]}; border: 1px solid {C[border2]}; border-radius: {C[radius]}; padding: 16px; }}
QFrame#metric-card {{ background: {C[surface]}; border: 1px solid {C[border2]}; border-radius: {C[radius]}; padding: 16px 20px; }}
QProgressBar {{ background: {C[surface2]}; border: none; border-radius: 4px; height: 6px; }}
QProgressBar::chunk {{ background: {C[accent]}; border-radius: 4px; }}
QWidget#sidebar {{ background: {C[sidebar]}; }}
QPushButton#sidebar-item {{
    background: transparent; color: {C[sidebar_text]}; border: none;
    border-radius: {C[radius_sm]}; padding: 9px 14px; text-align: left; font-weight: 600;
}}
QPushButton#sidebar-item:hover {{ background: {C[surface2]}; color: {C[text]}; font-weight: 700; }}
QGroupBox {{ font-weight: 600; border: 1px solid {C[border2]}; border-radius: {C[radius]}; margin-top: 12px; padding: 16px 12px 12px; }}

/* ═══════ QDialog — Global Style ═══════ */
QDialog {{
    background: {C[bg]};
}}
QDialog QLabel {{
    background: transparent;
    border: none;
}}

/* ═══════ QMessageBox — Global Style ═══════ */
QMessageBox {{
    background: {C[surface]};
}}
QMessageBox QLabel {{
    color: {C[text]};
    font-size: 13px;
    background: transparent;
}}
QMessageBox QPushButton {{
    min-width: 80px;
    min-height: 32px;
}}

/* Scroll containers: inherit the page background so list areas do not
   show a light rectangle in dark mode. */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QAbstractScrollArea {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {C[border]}; border-radius: 5px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {C[text3]}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {C[border]}; border-radius: 5px; min-width: 28px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

/* Tooltips — the global `*` rule above sets a colour but no background,
   which left tooltips rendering as dark-on-dark (effectively invisible).
   Give them an explicit dark chip so setToolTip() is actually readable. */
QToolTip {{
    background: {C[tooltip_bg]};
    color: {C[tooltip_fg]};
    border: 1px solid {C[tooltip_border]};
    border-radius: 6px;
    padding: 6px 9px;
    font-size: 12px;
    font-weight: 600;
    opacity: 240;
}}

"""

# Baked with the default palette; rebuilt by apply_theme().
QSS = build_qss(C)
