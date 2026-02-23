from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QPixmap

from ui.recording_widget import RecordingWidget
from ui.history_widget import HistoryWidget
from ui.settings_widget import SettingsWidget, load_settings
from ui.theme import get_colors, build_app_stylesheet

NAV_ITEMS = [
    ("REC", "⏺", "Запись",    0),
    ("HST", "📚", "История",   1),
    ("CFG", "⚙",  "Настройки", 2),
]


class NavButton(QPushButton):
    def __init__(self, code: str, icon: str, label: str, colors: dict, parent=None):
        super().__init__(parent)
        self._colors = colors
        self._code = code
        self.setCheckable(True)
        self._icon_str = icon
        self._label_str = label
        self.setFixedSize(76, 68)
        self._refresh_style(False)
        self.toggled.connect(self._refresh_style)

    def _refresh_style(self, active: bool):
        c = self._colors
        if active:
            bg = c["bg_selected"]
            color = c["nav_active"]
            border = f"border-left: 2px solid {c['accent_blue']};"
        else:
            bg = "transparent"
            color = c["nav_text"]
            border = "border-left: 2px solid transparent;"
        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {color};
                border: none;
                {border}
                border-radius: 0;
                font-size: 10px;
                padding: 4px 2px;
            }}
            QPushButton:hover {{
                background: {c['bg_hover']};
                color: {c['nav_active']};
            }}
        """)
        self.setText(f"{self._icon_str}\n{self._label_str}")

    def update_colors(self, colors: dict):
        self._colors = colors
        self._refresh_style(self.isChecked())


class MainWindow(QMainWindow):
    theme_changed = pyqtSignal(str)  # "dark" | "light"

    def __init__(self):
        super().__init__()
        settings = load_settings()
        self._theme = settings.get("theme", "dark")

        self.setWindowTitle("LessonRecorder")
        self.setMinimumSize(1000, 650)
        self.resize(1220, 760)

        # Загружаем иконку
        self._load_icon()
        self._build_ui()
        self.apply_theme(self._theme)

    def _load_icon(self):
        try:
            icon_path = Path(__file__).parent.parent / "app_icon.ico"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass

    def _build_ui(self):
        c = get_colors(self._theme)
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────────
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(80)
        self.sidebar.setObjectName("sidebar")
        sb_layout = QVBoxLayout(self.sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)
        sb_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Logo area
        logo_widget = QWidget()
        logo_widget.setFixedHeight(72)
        logo_widget.setObjectName("logoArea")
        logo_layout = QVBoxLayout(logo_widget)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_lbl = QLabel("🎙")
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setStyleSheet("font-size: 26px; background: transparent;")
        logo_layout.addWidget(logo_lbl)
        sb_layout.addWidget(logo_widget)

        # Divider
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("sidebarSep")
        sb_layout.addWidget(sep)

        sb_layout.addSpacing(8)

        # Nav buttons
        self._nav_buttons: list[NavButton] = []
        for code, icon, label, idx in NAV_ITEMS:
            btn = NavButton(code, icon, label, c)
            btn.clicked.connect(lambda _, i=idx: self._switch_page(i))
            sb_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        sb_layout.addStretch()

        # Version
        try:
            from version import __version__
        except ImportError:
            __version__ = "dev"

        ver_lbl = QLabel(f"v{__version__}")
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_lbl.setObjectName("versionLabel")
        ver_lbl.setStyleSheet(f"color: {c['text_dim']}; font-size: 10px; padding: 8px 0;")
        sb_layout.addWidget(ver_lbl)

        root_layout.addWidget(self.sidebar)

        # ── Vertical divider ──────────────────────────────────────────────
        vdiv = QFrame()
        vdiv.setFrameShape(QFrame.Shape.VLine)
        vdiv.setObjectName("mainVDivider")
        root_layout.addWidget(vdiv)

        # ── Content area ──────────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setObjectName("contentStack")

        self.recording_widget = RecordingWidget()
        self.history_widget = HistoryWidget()
        self.settings_widget = SettingsWidget()

        self.stack.addWidget(self.recording_widget)
        self.stack.addWidget(self.history_widget)
        self.stack.addWidget(self.settings_widget)

        root_layout.addWidget(self.stack)

        # Signals
        self.recording_widget.lesson_saved.connect(self.history_widget.refresh)
        self.settings_widget.theme_changed.connect(self.apply_theme)

        self._switch_page(0)

    def _switch_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == idx)
        if idx == 1:
            self.history_widget.refresh()

    def apply_theme(self, theme: str):
        self._theme = theme
        c = get_colors(theme)

        # App-wide stylesheet
        self.setStyleSheet(build_app_stylesheet(theme))

        # Sidebar specific
        self.sidebar.setStyleSheet(f"""
            QWidget#sidebar {{ background: {c['bg_sidebar']}; }}
            QWidget#logoArea {{ background: {c['bg_sidebar']}; }}
            QFrame#sidebarSep {{ color: {c['border']}; }}
        """)

        self.stack.setStyleSheet(f"QStackedWidget#contentStack {{ background: {c['bg_main']}; }}")

        # Propagate to main_window divider
        for child in self.findChildren(QFrame, "mainVDivider"):
            child.setStyleSheet(f"color: {c['border']};")

        # Update nav button colors
        for btn in self._nav_buttons:
            btn.update_colors(c)

        # Propagate theme change
        try:
            self.recording_widget.apply_theme(theme)
            self.history_widget.apply_theme(theme)
            self.settings_widget.apply_theme(theme)
        except Exception:
            pass
