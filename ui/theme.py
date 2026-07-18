"""Finance Manager v3 — Design System. One stylesheet, referenced everywhere."""

C = {
    "bg": "#F0F2F5", "surface": "#FFFFFF", "surface2": "#F8F9FA",
    "border": "#D0D5DD", "border2": "#E5E7EB",
    "text": "#101828", "text2": "#344054", "text3": "#667085",
    "accent": "#4F46E5", "accent_bg": "#EEF2FF",
    "green": "#059669", "green_bg": "#ECFDF5",
    "red": "#DC2626", "red_bg": "#FEF2F2",
    "amber": "#D97706", "amber_bg": "#FFFBEB",
    "sidebar": "#0F172A", "sidebar_text": "#94A3B8",
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
QLineEdit, QTextEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {{
    background: {C['surface']}; border: 1.5px solid {C['border']};
    border-radius: {C['radius_sm']}; padding: 8px 12px;
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {C['accent']}; }}
QTabBar::tab {{ background: transparent; color: {C['text3']}; padding: 10px 18px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {C['accent']}; border-bottom-color: {C['accent']}; }}
QTableWidget {{ background: {C['surface']}; border: 1px solid {C['border2']}; border-radius: {C['radius']}; }}
QHeaderView::section {{ background: {C['surface2']}; color: {C['text3']}; font-weight: 600; font-size: 11px; border: none; padding: 10px 12px; }}
QFrame#card {{ background: {C['surface']}; border: 1px solid {C['border2']}; border-radius: {C['radius']}; padding: 16px; }}
QFrame#metric-card {{ background: {C['surface']}; border: 1px solid {C['border2']}; border-radius: {C['radius']}; padding: 16px 20px; }}
QProgressBar {{ background: {C['surface2']}; border: none; border-radius: 4px; height: 6px; }}
QProgressBar::chunk {{ background: {C['accent']}; border-radius: 4px; }}
QWidget#sidebar {{ background: {C['sidebar']}; }}
QPushButton#sidebar-item {{
    background: transparent; color: {C['sidebar_text']}; border: none;
    border-radius: {C['radius_sm']}; padding: 9px 14px; text-align: left;
}}
QPushButton#sidebar-item:hover {{ background: rgba(255,255,255,0.06); color: white; }}
QPushButton#sidebar-item[active="true"] {{ background: rgba(99,102,241,0.2); color: white; font-weight: 600; }}
QFrame#networth-widget {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {C['accent']},stop:1 #7C3AED);
    border-radius: {C['radius']}; padding: 14px 16px;
}}
QGroupBox {{ font-weight: 600; border: 1px solid {C['border2']}; border-radius: {C['radius']}; margin-top: 12px; padding: 16px 12px 12px; }}
"""
