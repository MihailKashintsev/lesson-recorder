from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QGraphicsOpacityEffect,
)
from PyQt6.QtCore import (
    Qt, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QTimer,
)
from PyQt6.QtGui import QIcon, QFont, QColor

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
    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self._icon_str  = icon
        self._label_str = label
        self.setCheckable(True)
        self.setFixedSize(80, 72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style(False)
        self.toggled.connect(self._apply_style)

    def _apply_style(self, active: bool):
        # Sidebar всегда тёмный
        if active:
            bg     = "rgba(88,166,255,0.15)"
            color  = "#e6edf3"
            dot    = "#58a6ff"
            weight = "600"
        else:
            bg     = "transparent"
            color  = "#8b949e"
            dot    = "transparent"
            weight = "400"

        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {color};
                border: none;
                border-left: 3px solid {dot};
                border-radius: 0;
                font-size: 10px;
                font-weight: {weight};
                padding: 6px 2px 6px 0;
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{
                background: rgba(139,148,158,0.1);
                color: #e6edf3;
            }}
        """)
        self.setText(f"{self._icon_str}\n{self._label_str}")

    def update_colors(self, _colors: dict):
        # Sidebar фиксированно тёмный — перерисовываем без изменений
        self._apply_style(self.isChecked())


class FadeStackedWidget(QStackedWidget):
    """QStackedWidget с анимацией fade при переключении страниц."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim_duration = 180

    def setCurrentIndex(self, index: int):
        if index == self.currentIndex():
            return
        current = self.currentWidget()
        super().setCurrentIndex(index)
        next_w = self.currentWidget()
        if not next_w or not current:
            return

        # Fade-in нового виджета
        effect = QGraphicsOpacityEffect(next_w)
        next_w.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(self._anim_duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: next_w.setGraphicsEffect(None))
        anim.start()


class MainWindow(QMainWindow):
    theme_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        settings = load_settings()
        self._theme = settings.get("theme", "dark")

        self.setWindowTitle("LessonRecorder")
        self.setMinimumSize(1000, 650)
        self.resize(1240, 780)

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
        rl = QHBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(80)
        self.sidebar.setObjectName("sidebar")
        sb = QVBoxLayout(self.sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)
        sb.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Logo
        logo_w = QWidget()
        logo_w.setFixedHeight(76)
        logo_l = QVBoxLayout(logo_w)
        logo_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo = QLabel("🎙")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("font-size:28px; background:transparent;")
        logo_l.addWidget(logo)
        sb.addWidget(logo_w)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("sidebarSep")
        sep.setStyleSheet("color:#30363d; margin:0;")
        sb.addWidget(sep)
        sb.addSpacing(6)

        self._nav_buttons: list[NavButton] = []
        for _code, icon, label, idx in NAV_ITEMS:
            btn = NavButton(icon, label)
            btn.clicked.connect(lambda _, i=idx: self._switch_page(i))
            sb.addWidget(btn)
            self._nav_buttons.append(btn)

        sb.addStretch()

        # Version
        try:
            from version import __version__
        except ImportError:
            __version__ = "dev"
        ver = QLabel(f"v{__version__}")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet("color:#484f58; font-size:10px; padding:10px 0;")
        sb.addWidget(ver)

        rl.addWidget(self.sidebar)

        # Divider
        vdiv = QFrame()
        vdiv.setFrameShape(QFrame.Shape.VLine)
        vdiv.setObjectName("mainVDivider")
        rl.addWidget(vdiv)

        # ── Content ───────────────────────────────────────────
        self.stack = FadeStackedWidget()
        self.stack.setObjectName("contentStack")

        self.recording_widget = RecordingWidget()
        self.history_widget   = HistoryWidget()
        self.settings_widget  = SettingsWidget()

        self.stack.addWidget(self.recording_widget)
        self.stack.addWidget(self.history_widget)
        self.stack.addWidget(self.settings_widget)

        rl.addWidget(self.stack)

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

        self.setStyleSheet(build_app_stylesheet(theme))

        # Sidebar всегда тёмный
        sidebar_bg = "#010409" if theme == "dark" else "#1e2a3a"
        sidebar_sep = "#30363d" if theme == "dark" else "#273549"
        self.sidebar.setStyleSheet(f"""
            QWidget#sidebar {{ background: {sidebar_bg}; }}
            QFrame#sidebarSep {{ color: {sidebar_sep}; }}
        """)

        vdiv_color = "#30363d" if theme == "dark" else "#cbd5e1"
        for child in self.findChildren(QFrame, "mainVDivider"):
            child.setStyleSheet(f"color: {vdiv_color};")

        self.stack.setStyleSheet(
            f"QStackedWidget#contentStack {{ background: {c['bg_main']}; }}")

        for btn in self._nav_buttons:
            btn.update_colors(c)

        try:
            self.recording_widget.apply_theme(theme)
            self.history_widget.apply_theme(theme)
            self.settings_widget.apply_theme(theme)
        except Exception:
            pass
