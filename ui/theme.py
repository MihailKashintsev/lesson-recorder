"""
Управление темами приложения (тёмная / светлая).
"""
from typing import Literal

ThemeMode = Literal["dark", "light"]

# ── Цветовые токены ──────────────────────────────────────────────────────────

DARK = {
    "bg_main":       "#0d1117",
    "bg_panel":      "#161b22",
    "bg_sidebar":    "#010409",
    "bg_card":       "#1c2128",
    "bg_input":      "#21262d",
    "bg_hover":      "#30363d",
    "bg_selected":   "#1f4280",
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
}

LIGHT = {
    "bg_main":       "#ffffff",
    "bg_panel":      "#f6f8fa",
    "bg_sidebar":    "#f0f2f4",
    "bg_card":       "#ffffff",
    "bg_input":      "#f6f8fa",
    "bg_hover":      "#eaeef2",
    "bg_selected":   "#ddf4ff",
    "border":        "#d0d7de",
    "border_active": "#0969da",
    "text":          "#1f2328",
    "text_muted":    "#656d76",
    "text_dim":      "#b0b8c2",
    "accent_blue":   "#0969da",
    "accent_green":  "#1a7f37",
    "accent_orange": "#9a6700",
    "accent_red":    "#d1242f",
    "accent_purple": "#8250df",
    "accent_teal":   "#2da44e",
    "keyword":       "#cf222e",
    "string":        "#0a3069",
    "number":        "#0550ae",
    "comment":       "#6e7781",
    "function":      "#8250df",
    "type":          "#953800",
    "nav_text":      "#656d76",
    "nav_active":    "#1f2328",
    "rec_start":     "#1a7f37",
    "rec_stop":      "#d1242f",
    "rec_start_hv":  "#2da44e",
    "rec_stop_hv":   "#e5534b",
}


def get_colors(mode: ThemeMode) -> dict:
    return DARK if mode == "dark" else LIGHT


def build_app_stylesheet(mode: ThemeMode) -> str:
    c = get_colors(mode)
    return f"""
    QMainWindow, QWidget {{
        background: {c['bg_main']};
        color: {c['text']};
        font-family: 'Segoe UI', 'Inter', sans-serif;
    }}
    QLabel {{ color: {c['text']}; }}
    QScrollArea {{ background: transparent; border: none; }}
    QComboBox {{
        background: {c['bg_input']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 5px 10px;
        selection-background-color: {c['bg_selected']};
    }}
    QComboBox::drop-down {{
        border: none; width: 26px;
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
        padding: 6px 10px;
        border-radius: 4px;
        min-height: 22px;
    }}
    QComboBox QAbstractItemView::item:hover {{
        background: {c['bg_hover']};
        color: {c['text']};
    }}
    QComboBox QAbstractItemView::item:selected {{
        background: {c['accent_blue']};
        color: #ffffff;
    }}
    QLineEdit {{
        background: {c['bg_input']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 5px 10px;
        selection-background-color: {c['bg_selected']};
    }}
    QLineEdit:focus {{ border-color: {c['border_active']}; }}
    QTextEdit {{
        background: {c['bg_input']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 8px;
        selection-background-color: {c['bg_selected']};
    }}
    QScrollBar:vertical {{
        background: {c['bg_panel']};
        width: 8px;
        border: none;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {c['border']};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {c['text_muted']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{
        background: {c['bg_panel']};
        height: 8px;
        border: none;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['border']};
        border-radius: 4px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {c['text_muted']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QGroupBox {{
        color: {c['text_muted']};
        font-weight: 600;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
        border: 1px solid {c['border']};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 16px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 6px;
        background: {c['bg_main']};
    }}
    QTabWidget::pane {{
        border: 1px solid {c['border']};
        border-radius: 6px;
        background: {c['bg_card']};
    }}
    QTabBar::tab {{
        background: {c['bg_panel']};
        color: {c['text_muted']};
        padding: 8px 20px;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{
        color: {c['accent_blue']};
        border-bottom: 2px solid {c['accent_blue']};
        background: {c['bg_card']};
    }}
    QTabBar::tab:hover {{ color: {c['text']}; }}
    QCheckBox {{ color: {c['text']}; spacing: 8px; }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {c['border']};
        border-radius: 4px;
        background: {c['bg_input']};
    }}
    QCheckBox::indicator:checked {{
        background: {c['accent_blue']};
        border-color: {c['accent_blue']};
    }}
    QMessageBox {{ background: {c['bg_card']}; color: {c['text']}; }}
    QToolTip {{
        background: {c['bg_card']};
        color: {c['text']};
        border: 1px solid {c['border']};
        padding: 4px 8px;
        border-radius: 4px;
    }}
    """
