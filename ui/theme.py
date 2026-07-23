"""Finance Manager v3 — Design System. One stylesheet, referenced everywhere."""

C = {
    "bg": "#F0F2F5", "surface": "#FFFFFF", "surface2": "#F8F9FA",
    "border": "#D0D5DD", "border2": "#E5E7EB",
    "text": "#101828", "text2": "#344054", "text3": "#667085",
    "accent": "#4F46E5", "accent_bg": "#EEF2FF",
    "green": "#059669", "green_bg": "#ECFDF5",
    "red": "#DC2626", "red_bg": "#FEF2F2",
    "amber": "#D97706", "amber_bg": "#FFFBEB",
    "sidebar": "#FFFFFF", "sidebar_text": "#4338CA",
    "radius": "12px", "radius_sm": "8px",
}

QSS = f"""
* {{ font-family: 'Inter','Segoe UI',system-ui,sans-serif; font-size: 13px; color: {C['text']}; }}
QMainWindow, QWidget#central {{ background: {C['bg']}; }}
QPushButton {{
    background: {C['surface']}; border: 1px solid {C['border']};
    border-radius: {C['radius_sm']}; padding: 8px 16px; font-weight: 500;
}}
QPushButton:hover {{ border-color: {C['accent']}; }}
QPushButton#primary {{ background: {C['accent']}; color: white; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: #4338CA; }}
QPushButton#danger {{ background: {C['red']}; color: white; border: none; }}
QPushButton#pill {{
    background: {C['surface2']}; border: 1px solid {C['border2']};
    border-radius: 20px; padding: 6px 16px; font-size: 12px;
}}
QPushButton#ghost {{ background: transparent; border: none; color: {C['text3']}; }}
QLineEdit, QTextEdit {{
    background: {C['surface']}; border: 1.5px solid {C['border']};
    border-radius: {C['radius_sm']}; padding: 8px 12px;
    font-size: 13px; color: {C['text']};
}}
QLineEdit:hover, QTextEdit:hover {{ border-color: {C['accent']}; }}
QLineEdit:focus, QTextEdit:focus {{ border-color: {C['accent']}; }}
QLineEdit:disabled, QTextEdit:disabled {{
    background: {C['surface2']}; color: {C['text3']}; border-color: {C['border2']};
}}

/* ═══════ QDateEdit — Global Style ═══════ */
QDateEdit {{
    background: {C['surface']};
    border: 1.5px solid {C['border']};
    border-radius: {C['radius_sm']};
    padding: 6px 32px 6px 12px;
    font-size: 13px;
    font-weight: 500;
    color: {C['text']};
    min-height: 24px;
    min-width: 120px;
}}
QDateEdit:hover {{ border-color: {C['accent']}; }}
QDateEdit:focus {{ border-color: {C['accent']}; }}
QDateEdit:disabled {{
    background: {C['surface2']}; color: {C['text3']}; border-color: {C['border2']};
}}
QDateEdit::drop-down {{
    border: none;
    width: 28px;
    subcontrol-position: center right;
}}
QDateEdit::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {C['text3']};
    margin-right: 8px;
}}
QCalendarWidget {{
    background: {C['surface']};
    border: 1px solid {C['border2']};
    border-radius: {C['radius_sm']};
}}
QCalendarWidget QWidget {{
    alternate-background-color: {C['surface2']};
}}
QCalendarWidget QAbstractItemView:enabled {{
    color: {C['text']};
    background: {C['surface']};
    selection-background-color: {C['accent']};
    selection-color: white;
    border: none;
    outline: none;
    font-size: 13px;
}}
QCalendarWidget QAbstractItemView:disabled {{
    color: {C['text3']};
}}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background: {C['accent']};
    padding: 4px;
    border-radius: {C['radius_sm']} {C['radius_sm']} 0 0;
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
    gridline-color: {C['border2']};
}}

/* ═══════ QSpinBox / QDoubleSpinBox — Global Style ═══════ */
QSpinBox, QDoubleSpinBox {{
    background: {C['surface']};
    border: 1.5px solid {C['border']};
    border-radius: {C['radius_sm']};
    padding: 6px 8px;
    font-size: 13px;
    font-weight: 500;
    color: {C['text']};
    min-height: 24px;
}}
QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {C['accent']}; }}
QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {C['accent']}; }}
QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background: {C['surface2']}; color: {C['text3']}; border-color: {C['border2']};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    background: {C['surface2']};
    border: none;
    border-left: 1px solid {C['border']};
    border-bottom: 1px solid {C['border']};
    border-top-right-radius: {C['radius_sm']};
    width: 24px;
    margin: 0;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background: {C['accent_bg']};
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background: {C['surface2']};
    border: none;
    border-left: 1px solid {C['border']};
    border-top: 1px solid {C['border']};
    border-bottom-right-radius: {C['radius_sm']};
    width: 24px;
    margin: 0;
}}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {C['accent_bg']};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-bottom: 6px solid {C['text3']};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {C['text3']};
}}

/* ═══════ QComboBox — Global Style ═══════ */
QComboBox {{
    background: {C['surface']};
    border: 1.5px solid {C['border']};
    border-radius: {C['radius_sm']};
    padding: 6px 32px 6px 12px;
    font-size: 13px;
    font-weight: 500;
    color: {C['text']};
    min-height: 24px;
}}
QComboBox:hover {{
    border-color: {C['accent']};
}}
QComboBox:focus {{
    border-color: {C['accent']};
}}
QComboBox:disabled {{
    background: {C['surface2']};
    color: {C['text3']};
    border-color: {C['border2']};
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
    subcontrol-position: center right;
    padding-right: 4px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {C['text3']};
    margin-right: 8px;
}}
QComboBox::down-arrow:hover {{
    border-top-color: {C['accent']};
}}
QComboBox QAbstractItemView {{
    background: {C['surface']};
    border: 1px solid {C['border2']};
    border-radius: {C['radius_sm']};
    outline: none;
    padding: 4px;
}}
QComboBox QAbstractItemView::item {{
    padding: 8px 12px;
    border-radius: 6px;
    min-height: 20px;
}}
QComboBox QAbstractItemView::item:selected {{
    background: {C['accent']};
    color: white;
}}
QComboBox QAbstractItemView::item:hover {{
    background: {C['accent_bg']};
    color: {C['accent']};
}}
QComboBox QLineEdit {{
    background: transparent;
    border: none;
    padding: 0;
    font-size: 13px;
    color: {C['text']};
}}
QTabBar::tab {{ background: transparent; color: {C['text3']}; padding: 10px 18px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {C['accent']}; border-bottom-color: {C['accent']}; }}
QTableWidget {{ background: {C['surface']}; border: 1px solid {C['border2']}; border-radius: {C['radius']}; }}
QHeaderView::section {{ background: {C['surface2']}; color: {C['text3']}; font-weight: 600; font-size: 11px; border: none; padding: 10px 12px; }}
QFrame#card {{ background: {C['surface']}; border: 1px solid {C['border2']}; border-radius: {C['radius']}; padding: 16px; }}
QFrame#metric-card {{ background: {C['surface']}; border: 1px solid {C['border2']}; border-radius: {C['radius']}; padding: 16px 20px; }}
QProgressBar {{ background: {C['surface2']}; border: none; border-radius: 4px; height: 6px; }}
QProgressBar::chunk {{ background: {C['accent']}; border-radius: 4px; }}
QWidget#sidebar {{ background: white; }}
QPushButton#sidebar-item {{
    background: transparent; color: #4338CA; border: none;
    border-radius: {C['radius_sm']}; padding: 9px 14px; text-align: left; font-weight: 600;
}}
QPushButton#sidebar-item:hover {{ background: {C['surface2']}; color: #111827; font-weight: 700; }}
QGroupBox {{ font-weight: 600; border: 1px solid {C['border2']}; border-radius: {C['radius']}; margin-top: 12px; padding: 16px 12px 12px; }}

/* ═══════ QDialog — Global Style ═══════ */
QDialog {{
    background: {C['bg']};
}}
QDialog QLabel {{
    background: transparent;
    border: none;
}}

/* ═══════ QMessageBox — Global Style ═══════ */
QMessageBox {{
    background: {C['surface']};
}}
QMessageBox QLabel {{
    color: {C['text']};
    font-size: 13px;
    background: transparent;
}}
QMessageBox QPushButton {{
    min-width: 80px;
    min-height: 32px;
}}

"""
