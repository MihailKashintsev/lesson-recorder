from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont

from ui.recording_widget import RecordingWidget
from ui.history_widget import HistoryWidget
from ui.settings_widget import SettingsWidget


NAV_ITEMS = [
    ("⏺", "Запись", 0),
    ("📚", "История", 1),
    ("⚙", "Настройки", 2),
]


class NavButton(QPushButton):
    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setText(f"{icon}\n{label}")
        self.setFixedSize(80, 72)
        self.setStyleSheet(self._style(False))
        self.toggled.connect(lambda checked: self.setStyleSheet(self._style(checked)))

    @staticmethod
    def _style(active: bool) -> str:
        bg = "#2a3a4a" if active else "transparent"
        color = "#ffffff" if active else "#888"
        return f"""
            QPushButton {{
                background: {bg};
                color: {color};
                border: none;
                border-radius: 8px;
                font-size: 11px;
                padding: 4px;
            }}
            QPushButton:hover {{ background: #2a3a4a; color: #fff; }}
        """


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LessonRecorder")
        self.setMinimumSize(1000, 650)
        self.resize(1200, 750)
        self._build_ui()
        self._apply_theme()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(88)
        sidebar.setStyleSheet("background: #111111;")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(4, 16, 4, 16)
        sb_layout.setSpacing(4)
        sb_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # App logo/name
        logo = QLabel("🎙")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("font-size: 28px; margin-bottom: 12px;")
        sb_layout.addWidget(logo)

        app_name = QLabel("Lesson\nRecorder")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_name.setStyleSheet("color: #555; font-size: 10px; margin-bottom: 16px;")
        sb_layout.addWidget(app_name)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #222; margin-bottom: 8px;")
        sb_layout.addWidget(sep)

        self._nav_buttons = []
        for icon, label, idx in NAV_ITEMS:
            btn = NavButton(icon, label)
            btn.clicked.connect(lambda _, i=idx: self._switch_page(i))
            sb_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        sb_layout.addStretch()

        # Версия внизу сайдбара
        try:
            from version import __version__
        except ImportError:
            __version__ = "dev"

        version_label = QLabel(f"v{__version__}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #333; font-size: 10px; margin-bottom: 4px;")
        sb_layout.addWidget(version_label)

        root_layout.addWidget(sidebar)

        # ── Content area ──────────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: #141414;")

        self.recording_widget = RecordingWidget()
        self.history_widget = HistoryWidget()
        self.settings_widget = SettingsWidget()

        self.stack.addWidget(self.recording_widget)
        self.stack.addWidget(self.history_widget)
        self.stack.addWidget(self.settings_widget)

        root_layout.addWidget(self.stack)

        # Connect recording done → refresh history
        self.recording_widget.lesson_saved.connect(self.history_widget.refresh)

        # Start on recording page
        self._switch_page(0)

    def _switch_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == idx)
        if idx == 1:
            self.history_widget.refresh()

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #141414; color: #e0e0e0; }
            QLabel { color: #e0e0e0; }
            QComboBox {
                background: #2a2a2a; color: #e0e0e0;
                border: 1px solid #3a3a3a; border-radius: 6px; padding: 4px 8px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #2a2a2a; color: #e0e0e0; }
            QLineEdit {
                background: #2a2a2a; color: #e0e0e0;
                border: 1px solid #3a3a3a; border-radius: 6px; padding: 4px 8px;
            }
            QScrollBar:vertical {
                background: #1a1a1a; width: 8px; border: none;
            }
            QScrollBar::handle:vertical {
                background: #3a3a3a; border-radius: 4px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QGroupBox {
                color: #c0c0c0; font-weight: bold;
                border: 1px solid #2a2a2a; border-radius: 8px; margin-top: 8px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
            QTabWidget::pane { border: 1px solid #2a2a2a; }
            QTabBar::tab {
                background: #1e1e1e; color: #888;
                padding: 6px 18px;
            }
            QTabBar::tab:selected { color: #4a9eff; border-bottom: 2px solid #4a9eff; }
            QMessageBox { background: #1e1e1e; color: #e0e0e0; }
        """)
