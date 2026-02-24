"""
Управление темами приложения (тёмная / светлая).
"""
from typing import Literal

ThemeMode = Literal["dark", "light"]

DARK = {
    "bg_main":       "#0d1117",
    "bg_panel":      "#161b22",
    "bg_sidebar":    "#010409",
    "bg_card":       "#1c2128",
    "bg_input":      "#21262d",
    "bg_hover":      "#30363d",
    "bg_selected":   "#1f3a5f",
    "border":        "#30363d",
    "border_active": "#58a6ff",
    "text":          "#e6edf3",
    "text_muted":    "#8b949e",
    "text_dim":      "#484f58",
    "accent_blue":   "#58a6ff",
    "accent_green":  "#3fb950",
    "accent_orange": "#d29922",
    "accent_red":    "#f85149",
    "accent_purple": "#bc8cff",
    "accent_teal":   "#39d353",
    "keyword":       "#ff7b72",
    "string":        "#a5d6ff",
    "number":        "#79c0ff",
    "comment":       "#8b949e",
    "function":      "#d2a8ff",
    "type":          "#ffa657",
    "nav_text":      "#8b949e",
    "nav_active":    "#e6edf3",
    "rec_start":     "#238636",
    "rec_stop":      "#da3633",
    "rec_start_hv":  "#2ea043",
    "rec_stop_hv":   "#f85149",
    "shadow":        "rgba(0,0,0,0.4)",
    "glass":         "rgba(22,27,34,0.85)",
}

LIGHT = {
    "bg_main":       "#f0f4f8",
    "bg_panel":      "#ffffff",
    "bg_sidebar":    "#1e2a3a",
    "bg_card":       "#ffffff",
    "bg_input":      "#f0f4f8",
    "bg_hover":      "#e2e8f0",
    "bg_selected":   "#dbeafe",
    "border":        "#cbd5e1",
    "border_active": "#3b82f6",
    "text":          "#0f172a",
    "text_muted":    "#64748b",
    "text_dim":      "#94a3b8",
    "accent_blue":   "#2563eb",
    "accent_green":  "#16a34a",
    "accent_orange": "#d97706",
    "accent_red":    "#dc2626",
    "accent_purple": "#7c3aed",
    "accent_teal":   "#0d9488",
    "keyword":       "#dc2626",
    "string":        "#0369a1",
    "number":        "#0369a1",
    "comment":       "#64748b",
    "function":      "#7c3aed",
    "type":          "#c2410c",
    # Sidebar в светлой теме — тёмный (как VS Code)
    "nav_text":      "#94a3b8",
    "nav_active":    "#f1f5f9",
    "rec_start":     "#16a34a",
    "rec_stop":      "#dc2626",
    "rec_start_hv":  "#15803d",
    "rec_stop_hv":   "#b91c1c",
    "shadow":        "rgba(0,0,0,0.12)",
    "glass":         "rgba(255,255,255,0.9)",
}


def get_colors(mode: ThemeMode) -> dict:
    return DARK if mode == "dark" else LIGHT


def build_app_stylesheet(mode: ThemeMode) -> str:
    c = get_colors(mode)
    is_dark = mode == "dark"

    # Sidebar всегда тёмный для обеих тем — как в VS Code / Figma
    sidebar_bg = "#010409" if is_dark else "#1e2a3a"
    sidebar_border = "#30363d" if is_dark else "#273549"

    return f"""
    /* ── Base ─────────────────────────────────────────────── */
    QMainWindow, QWidget {{
        background: {c['bg_main']};
        color: {c['text']};
        font-family: 'Segoe UI', 'Inter', 'SF Pro Display', sans-serif;
        font-size: 13px;
    }}
    QLabel {{ color: {c['text']}; background: transparent; }}

    /* ── Sidebar (always dark) ────────────────────────────── */
    QWidget#sidebar {{
        background: {sidebar_bg};
        border-right: 1px solid {sidebar_border};
    }}
    QFrame#sidebarSep {{
        color: {sidebar_border};
        max-height: 1px;
    }}

    /* ── Cards / Panels ───────────────────────────────────── */
    QGroupBox {{
        color: {c['text_muted']};
        font-weight: 600;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        border: 1px solid {c['border']};
        border-radius: 10px;
        margin-top: 14px;
        padding-top: 18px;
        background: {c['bg_panel']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 8px;
        background: {c['bg_main']};
        border-radius: 3px;
    }}

    /* ── Inputs ───────────────────────────────────────────── */
    QLineEdit {{
        background: {c['bg_input']};
        color: {c['text']};
        border: 1.5px solid {c['border']};
        border-radius: 7px;
        padding: 6px 12px;
        selection-background-color: {c['bg_selected']};
    }}
    QLineEdit:focus {{
        border-color: {c['border_active']};
        background: {c['bg_card']};
    }}
    QLineEdit:hover {{
        border-color: {c['text_dim']};
    }}

    QTextEdit {{
        background: {c['bg_input']};
        color: {c['text']};
        border: 1.5px solid {c['border']};
        border-radius: 8px;
        padding: 8px 12px;
        selection-background-color: {c['bg_selected']};
    }}
    QTextEdit:focus {{
        border-color: {c['border_active']};
    }}

    /* ── ComboBox ─────────────────────────────────────────── */
    QComboBox {{
        background: {c['bg_input']};
        color: {c['text']};
        border: 1.5px solid {c['border']};
        border-radius: 7px;
        padding: 6px 12px;
        selection-background-color: {c['bg_selected']};
        min-height: 22px;
    }}
    QComboBox:hover {{ border-color: {c['text_dim']}; }}
    QComboBox:focus {{ border-color: {c['border_active']}; }}
    QComboBox::drop-down {{
        border: none; width: 28px;
        border-left: 1px solid {c['border']};
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
    }}
    QComboBox::down-arrow {{
        width: 0; height: 0;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {c['text_muted']};
    }}
    QComboBox QAbstractItemView {{
        background: {c['bg_card']};
        color: {c['text']};
        border: 1px solid {c['border_active']};
        border-radius: 8px;
        padding: 4px;
        outline: none;
        selection-background-color: {c['accent_blue']};
        selection-color: #ffffff;
    }}
    QComboBox QAbstractItemView::item {{
        padding: 7px 12px;
        border-radius: 5px;
        min-height: 24px;
    }}
    QComboBox QAbstractItemView::item:hover {{
        background: {c['bg_hover']};
    }}
    QComboBox QAbstractItemView::item:selected {{
        background: {c['accent_blue']};
        color: #ffffff;
    }}

    /* ── ScrollBars ───────────────────────────────────────── */
    QScrollBar:vertical {{
        background: transparent;
        width: 7px; border: none; border-radius: 3px;
    }}
    QScrollBar::handle:vertical {{
        background: {c['border']};
        border-radius: 3px; min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {c['text_muted']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 7px; border: none; border-radius: 3px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['border']};
        border-radius: 3px; min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {c['text_muted']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QScrollArea {{ background: transparent; border: none; }}

    /* ── Tabs ─────────────────────────────────────────────── */
    QTabWidget::pane {{
        border: 1px solid {c['border']};
        border-radius: 8px;
        background: {c['bg_card']};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {c['text_muted']};
        padding: 9px 22px;
        border-bottom: 2px solid transparent;
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        color: {c['accent_blue']};
        border-bottom: 2px solid {c['accent_blue']};
        font-weight: 600;
    }}
    QTabBar::tab:hover {{ color: {c['text']}; background: {c['bg_hover']}; }}

    /* ── CheckBox ─────────────────────────────────────────── */
    QCheckBox {{ color: {c['text']}; spacing: 9px; }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1.5px solid {c['border']};
        border-radius: 4px;
        background: {c['bg_input']};
    }}
    QCheckBox::indicator:hover {{ border-color: {c['accent_blue']}; }}
    QCheckBox::indicator:checked {{
        background: {c['accent_blue']};
        border-color: {c['accent_blue']};
        image: none;
    }}

    /* ── ProgressBar ──────────────────────────────────────── */
    QProgressBar {{
        background: {c['bg_input']};
        border: none;
        border-radius: 6px;
        text-align: center;
        color: {c['text']};
        font-size: 11px;
        font-weight: 600;
        min-height: 20px;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {c['accent_blue']}, stop:1 {c['accent_purple']});
        border-radius: 6px;
    }}

    /* ── Messages / Dialogs ───────────────────────────────── */
    QMessageBox {{
        background: {c['bg_card']};
        color: {c['text']};
    }}
    QToolTip {{
        background: {c['bg_card']};
        color: {c['text']};
        border: 1px solid {c['border']};
        padding: 5px 10px;
        border-radius: 6px;
        font-size: 12px;
    }}

    /* ── Slider ───────────────────────────────────────────── */
    QSlider::groove:horizontal {{
        background: {c['bg_input']};
        height: 4px; border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {c['accent_blue']};
        width: 14px; height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider::sub-page:horizontal {{
        background: {c['accent_blue']};
        border-radius: 2px;
    }}
    """
