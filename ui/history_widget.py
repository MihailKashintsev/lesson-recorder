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
    "recording": "⏺ Запись",
    "transcribing": "📝 Транскрипция",
    "summarizing": "🤖 Конспект",
    "done": "✅ Готово",
}


class LessonListItem(QListWidgetItem):
    def __init__(self, lesson):
        super().__init__()
        self.lesson_id = lesson["id"]
        status = STATUS_LABELS.get(lesson["status"] or "done", "")
        date_str = fmt_date(lesson["created_at"])
        dur_str = fmt_duration(lesson["duration_seconds"])
        self.setText(f"{lesson['title']}\n{date_str}  ·  {dur_str}  {status}")
        self.setSizeHint(QSize(0, 60))


class HistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_lesson = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Left panel – lesson list ──────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(280)
        left.setStyleSheet("background: #1a1a1a; border-right: 1px solid #2a2a2a;")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        list_header = QLabel("  История уроков")
        list_header.setFixedHeight(48)
        list_header.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #c0c0c0;"
            "background: #1f1f1f; border-bottom: 1px solid #2a2a2a;"
        )
        left_layout.addWidget(list_header)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                color: #c0c0c0;
                font-size: 13px;
            }
            QListWidget::item { padding: 8px 12px; border-bottom: 1px solid #222; }
            QListWidget::item:selected { background: #2a3a4a; color: #fff; }
            QListWidget::item:hover { background: #252525; }
        """)
        self.list_widget.currentItemChanged.connect(self._on_select)
        left_layout.addWidget(self.list_widget)

        layout.addWidget(left)

        # ── Right panel – lesson detail ───────────────────────────────────
        self.detail_panel = QWidget()
        self.detail_panel.setStyleSheet("background: #141414;")
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(24, 24, 24, 24)
        detail_layout.setSpacing(12)

        # Header row
        header_row = QHBoxLayout()
        self.detail_title = QLabel("Выберите урок")
        self.detail_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #e0e0e0;")
        header_row.addWidget(self.detail_title)
        header_row.addStretch()

        self.btn_rename = QPushButton("✏ Переименовать")
        self.btn_export = QPushButton("💾 Экспорт")
        self.btn_delete = QPushButton("🗑 Удалить")
        for btn, color in [(self.btn_rename, "#3a3a3a"),
                           (self.btn_export, "#2d4a2d"),
                           (self.btn_delete, "#4a1a1a")]:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    color: #c0c0c0;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-size: 12px;
                }}
                QPushButton:hover {{ background: #555; }}
            """)
            btn.setEnabled(False)
            header_row.addWidget(btn)

        self.btn_rename.clicked.connect(self._rename)
        self.btn_export.clicked.connect(self._export)
        self.btn_delete.clicked.connect(self._delete)

        detail_layout.addLayout(header_row)

        self.detail_meta = QLabel("")
        self.detail_meta.setStyleSheet("color: #666; font-size: 12px;")
        detail_layout.addWidget(self.detail_meta)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a2a2a;")
        detail_layout.addWidget(sep)

        # Tabs: Конспект / Транскрипция
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #2a2a2a; border-radius: 6px; }
            QTabBar::tab {
                background: #1e1e1e; color: #888;
                padding: 8px 20px; border-radius: 0;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected { color: #4a9eff; border-bottom: 2px solid #4a9eff; }
        """)

        self.notes_view = QTextEdit()
        self.notes_view.setReadOnly(True)
        self.notes_view.setPlaceholderText("Конспект появится здесь после обработки…")
        self.notes_view.setStyleSheet(self._text_style())

        self.transcript_view = QTextEdit()
        self.transcript_view.setReadOnly(True)
        self.transcript_view.setPlaceholderText("Транскрипция появится здесь после обработки…")
        self.transcript_view.setStyleSheet(self._text_style())

        self.tabs.addTab(self.notes_view, "📋 Конспект")
        self.tabs.addTab(self.transcript_view, "📝 Транскрипция")
        detail_layout.addWidget(self.tabs)

        layout.addWidget(self.detail_panel)

    def refresh(self):
        current_id = None
        current_item = self.list_widget.currentItem()
        if current_item:
            current_id = current_item.lesson_id

        self.list_widget.clear()
        lessons = db.get_all_lessons()
        if not lessons:
            placeholder = QListWidgetItem("Нет записей")
            placeholder.setForeground(QColor("#555"))
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(placeholder)
            return

        for lesson in lessons:
            item = LessonListItem(lesson)
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
            self, "Удалить урок",
            f"Удалить урок «{self._current_lesson['title']}»?\nАудиофайл тоже будет удалён.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.delete_lesson(self._current_lesson["id"])
            self._current_lesson = None
            self.detail_title.setText("Выберите урок")
            self.detail_meta.setText("")
            self.notes_view.clear()
            self.transcript_view.clear()
            for btn in [self.btn_rename, self.btn_export, self.btn_delete]:
                btn.setEnabled(False)
            self.refresh()

    @staticmethod
    def _text_style():
        return """
            QTextEdit {
                background: #1a1a1a;
                color: #c0c0c0;
                border: none;
                font-size: 13px;
                padding: 12px;
            }
        """
