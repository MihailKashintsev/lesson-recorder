from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QSplitter,
    QFrame, QTabWidget, QFileDialog, QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor

import core.database as db
from ui.theme import get_colors


def fmt_duration(seconds: int) -> str:
    if not seconds:
        return "—"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}ч {m:02d}м"
    return f"{m}м {s:02d}с"


def fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d.%m.%Y  %H:%M")
    except Exception:
        return iso


STATUS_LABELS = {
    "recording":    "⏺ Запись",
    "transcribing": "📝 Транскрипция",
    "summarizing":  "🤖 Конспект",
    "done":         "✅ Готово",
}

STATUS_COLORS = {
    "recording":    "#f85149",
    "transcribing": "#d29922",
    "summarizing":  "#58a6ff",
    "done":         "#3fb950",
}


class LessonListItem(QListWidgetItem):
    def __init__(self, lesson, c: dict):
        super().__init__()
        self.lesson_id = lesson["id"]
        status = lesson["status"] or "done"
        status_label = STATUS_LABELS.get(status, "")
        date_str = fmt_date(lesson["created_at"])
        dur_str = fmt_duration(lesson["duration_seconds"])
        self.setText(f"{lesson['title']}\n{date_str}  ·  {dur_str}  {status_label}")
        self.setSizeHint(QSize(0, 62))


class HistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_lesson = None
        self._theme = "dark"
        self._build_ui()
        self.refresh()

    def apply_theme(self, theme: str):
        self._theme = theme
        c = get_colors(theme)
        self._apply_colors(c)

    def _apply_colors(self, c: dict):
        self.left_panel.setStyleSheet(f"""
            QWidget#leftPanel {{
                background: {c['bg_panel']};
                border-right: 1px solid {c['border']};
            }}
        """)
        self.list_header.setStyleSheet(f"""
            font-size: 12px; font-weight: 600;
            color: {c['text_muted']};
            background: {c['bg_panel']};
            border-bottom: 1px solid {c['border']};
            padding-left: 16px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background: {c['bg_panel']};
                border: none; color: {c['text']};
                font-size: 13px; outline: none;
            }}
            QListWidget::item {{
                padding: 10px 16px;
                border-bottom: 1px solid {c['border']};
            }}
            QListWidget::item:selected {{
                background: {c['bg_selected']};
                color: {c['text']};
            }}
            QListWidget::item:hover:!selected {{
                background: {c['bg_hover']};
            }}
        """)
        self.detail_panel.setStyleSheet(f"background: {c['bg_main']};")
        self.detail_title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {c['text']};")
        self.detail_meta.setStyleSheet(f"color: {c['text_muted']}; font-size: 12px;")
        self.notes_view.setStyleSheet(self._text_style(c))
        self.transcript_view.setStyleSheet(self._text_style_mono(c))
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {c['border']};
                border-radius: 8px;
                background: {c['bg_panel']};
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
            }}
            QTabBar::tab:hover {{ color: {c['text']}; }}
        """)
        for btn in [self.btn_rename, self.btn_export, self.btn_delete]:
            btn.setStyleSheet(self._action_btn_style(c, btn.objectName()))

    def _build_ui(self):
        c = get_colors(self._theme)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Left panel ────────────────────────────────────────────────────
        self.left_panel = QWidget()
        self.left_panel.setObjectName("leftPanel")
        self.left_panel.setFixedWidth(290)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.list_header = QLabel("  Записи")
        self.list_header.setFixedHeight(46)
        left_layout.addWidget(self.list_header)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_select)
        left_layout.addWidget(self.list_widget)

        layout.addWidget(self.left_panel)

        # ── Right panel ───────────────────────────────────────────────────
        self.detail_panel = QWidget()
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(28, 24, 28, 24)
        detail_layout.setSpacing(12)

        # Header row
        header_row = QHBoxLayout()
        self.detail_title = QLabel("Выберите запись")
        header_row.addWidget(self.detail_title)
        header_row.addStretch()

        self.btn_rename = QPushButton("✏ Переименовать")
        self.btn_rename.setObjectName("rename")
        self.btn_export = QPushButton("💾 Экспорт")
        self.btn_export.setObjectName("export")
        self.btn_delete = QPushButton("🗑 Удалить")
        self.btn_delete.setObjectName("delete")

        for btn in [self.btn_rename, self.btn_export, self.btn_delete]:
            btn.setEnabled(False)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            header_row.addWidget(btn)

        self.btn_rename.clicked.connect(self._rename)
        self.btn_export.clicked.connect(self._export)
        self.btn_delete.clicked.connect(self._delete)
        detail_layout.addLayout(header_row)

        self.detail_meta = QLabel("")
        detail_layout.addWidget(self.detail_meta)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {c['border']};")
        detail_layout.addWidget(sep)

        # Tabs
        self.tabs = QTabWidget()
        self.notes_view = QTextEdit()
        self.notes_view.setReadOnly(True)
        self.notes_view.setPlaceholderText("Конспект появится здесь после обработки…")

        self.transcript_view = QTextEdit()
        self.transcript_view.setReadOnly(True)
        self.transcript_view.setPlaceholderText("Транскрипция появится здесь после обработки…")

        self.tabs.addTab(self.notes_view, "📋  Конспект")
        self.tabs.addTab(self.transcript_view, "📝  Транскрипция")
        detail_layout.addWidget(self.tabs)

        layout.addWidget(self.detail_panel)

        # Apply colors
        self._apply_colors(c)

    def refresh(self):
        current_id = None
        current_item = self.list_widget.currentItem()
        if current_item and hasattr(current_item, "lesson_id"):
            current_id = current_item.lesson_id

        self.list_widget.clear()
        c = get_colors(self._theme)
        lessons = db.get_all_lessons()

        if not lessons:
            placeholder = QListWidgetItem("Нет записей")
            placeholder.setForeground(QColor(c["text_dim"]))
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(placeholder)
            return

        for lesson in lessons:
            item = LessonListItem(lesson, c)
            self.list_widget.addItem(item)
            if lesson["id"] == current_id:
                self.list_widget.setCurrentItem(item)

    def _on_select(self, item: QListWidgetItem):
        if not item or not hasattr(item, "lesson_id"):
            return
        lesson = db.get_lesson(item.lesson_id)
        if not lesson:
            return
        self._current_lesson = dict(lesson)

        self.detail_title.setText(lesson["title"])
        date_str = fmt_date(lesson["created_at"])
        dur_str = fmt_duration(lesson["duration_seconds"])
        status = STATUS_LABELS.get(lesson["status"] or "done", "")
        self.detail_meta.setText(f"{date_str}  ·  {dur_str}  ·  {status}")

        self.notes_view.setMarkdown(lesson["notes"] or "")
        self.transcript_view.setPlainText(lesson["transcript"] or "")

        for btn in [self.btn_rename, self.btn_export, self.btn_delete]:
            btn.setEnabled(True)

    def _rename(self):
        if not self._current_lesson:
            return
        new_name, ok = QInputDialog.getText(
            self, "Переименовать", "Новое название:",
            text=self._current_lesson["title"]
        )
        if ok and new_name.strip():
            db.update_lesson(self._current_lesson["id"], title=new_name.strip())
            self.refresh()

    def _export(self):
        if not self._current_lesson:
            return
        lesson = db.get_lesson(self._current_lesson["id"])
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить конспект", f"{lesson['title']}.md",
            "Markdown (*.md);;Text (*.txt)"
        )
        if not path:
            return
        content = f"# {lesson['title']}\n"
        content += f"*{fmt_date(lesson['created_at'])}  ·  {fmt_duration(lesson['duration_seconds'])}*\n\n"
        if lesson["notes"]:
            content += lesson["notes"] + "\n\n"
        if lesson["transcript"]:
            content += "---\n## Транскрипция\n\n" + lesson["transcript"]
        try:
            Path(path).write_text(content, encoding="utf-8")
            QMessageBox.information(self, "Готово", f"Сохранено в:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _delete(self):
        if not self._current_lesson:
            return
        reply = QMessageBox.question(
            self, "Удалить запись",
            f"Удалить «{self._current_lesson['title']}»?\nАудиофайл тоже будет удалён.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.delete_lesson(self._current_lesson["id"])
            self._current_lesson = None
            self.detail_title.setText("Выберите запись")
            self.detail_meta.setText("")
            self.notes_view.clear()
            self.transcript_view.clear()
            for btn in [self.btn_rename, self.btn_export, self.btn_delete]:
                btn.setEnabled(False)
            self.refresh()

    @staticmethod
    def _text_style(c: dict) -> str:
        return f"""
            QTextEdit {{
                background: {c['bg_panel']};
                color: {c['text']};
                border: none;
                font-size: 14px;
                line-height: 1.6;
                padding: 16px;
            }}
        """

    @staticmethod
    def _text_style_mono(c: dict) -> str:
        return f"""
            QTextEdit {{
                background: {c['bg_panel']};
                color: {c['text']};
                border: none;
                font-family: 'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace;
                font-size: 13px;
                padding: 16px;
            }}
        """

    @staticmethod
    def _action_btn_style(c: dict, name: str) -> str:
        if name == "delete":
            bg = "transparent"
            color = c["accent_red"]
            border = c["accent_red"]
            hover_bg = "#f8514920"
        elif name == "export":
            bg = "transparent"
            color = c["accent_green"]
            border = c["accent_green"]
            hover_bg = "#3fb95020"
        else:
            bg = "transparent"
            color = c["text_muted"]
            border = c["border"]
            hover_bg = c["bg_hover"]
        return f"""
            QPushButton {{
                background: {bg}; color: {color};
                border: 1px solid {border}; border-radius: 6px;
                padding: 5px 12px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {hover_bg}; }}
            QPushButton:disabled {{ color: {c['text_dim']}; border-color: {c['border']}; }}
        """
