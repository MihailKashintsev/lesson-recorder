from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QGroupBox, QFormLayout, QMessageBox
)
from PyQt6.QtCore import Qt
import json
from pathlib import Path

SETTINGS_PATH = Path.home() / ".lesson_recorder" / "settings.json"

DEFAULTS = {
    "audio_source": "both",
    "whisper_model": "base",
    "language": "auto",
    "ollama_model": "llama3",
    "ollama_url": "http://localhost:11434",
}


def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                data = json.load(f)
                return {**DEFAULTS, **data}
        except Exception:
            pass
    return dict(DEFAULTS)


def save_settings(settings: dict):
    SETTINGS_PATH.parent.mkdir(exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


class SettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("Настройки")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(title)

        # ── Audio ────────────────────────────────────────────────────────
        audio_group = QGroupBox("Запись аудио")
        audio_group.setStyleSheet(self._group_style())
        audio_form = QFormLayout(audio_group)

        self.combo_source = QComboBox()
        self.combo_source.addItems(["Микрофон", "Системный звук", "Оба источника"])
        src_map = {"mic": 0, "system": 1, "both": 2}
        self.combo_source.setCurrentIndex(src_map.get(self.settings["audio_source"], 2))
        audio_form.addRow("Источник:", self.combo_source)
        layout.addWidget(audio_group)

        # ── Whisper ───────────────────────────────────────────────────────
        whisper_group = QGroupBox("Транскрипция (Whisper)")
        whisper_group.setStyleSheet(self._group_style())
        whisper_form = QFormLayout(whisper_group)

        self.combo_model = QComboBox()
        models = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
        self.combo_model.addItems(models)
        if self.settings["whisper_model"] in models:
            self.combo_model.setCurrentIndex(models.index(self.settings["whisper_model"]))
        whisper_form.addRow("Модель:", self.combo_model)

        self.combo_lang = QComboBox()
        langs = {"auto": "Авто-определение", "ru": "Русский", "en": "English",
                 "uk": "Українська", "de": "Deutsch", "fr": "Français",
                 "es": "Español", "zh": "中文"}
        for code, name in langs.items():
            self.combo_lang.addItem(name, code)
        current_lang = self.settings.get("language", "auto")
        for i in range(self.combo_lang.count()):
            if self.combo_lang.itemData(i) == current_lang:
                self.combo_lang.setCurrentIndex(i)
                break
        whisper_form.addRow("Язык:", self.combo_lang)

        model_note = QLabel(
            "tiny — быстро, низкое качество  •  base — баланс  •  "
            "small/medium/large — медленнее, лучше"
        )
        model_note.setStyleSheet("color: #888; font-size: 11px;")
        model_note.setWordWrap(True)
        whisper_form.addRow("", model_note)
        layout.addWidget(whisper_group)

        # ── Ollama ────────────────────────────────────────────────────────
        ollama_group = QGroupBox("ИИ конспектирование (Ollama)")
        ollama_group.setStyleSheet(self._group_style())
        ollama_form = QFormLayout(ollama_group)

        self.edit_ollama_model = QLineEdit(self.settings["ollama_model"])
        ollama_form.addRow("Модель Ollama:", self.edit_ollama_model)

        self.edit_ollama_url = QLineEdit(self.settings["ollama_url"])
        ollama_form.addRow("URL Ollama:", self.edit_ollama_url)

        test_btn = QPushButton("Проверить соединение")
        test_btn.clicked.connect(self._test_ollama)
        test_btn.setStyleSheet(self._btn_style())
        ollama_form.addRow("", test_btn)

        note = QLabel(
            "Установите Ollama: https://ollama.com\n"
            "Затем скачайте модель: ollama pull llama3"
        )
        note.setStyleSheet("color: #888; font-size: 11px;")
        note.setWordWrap(True)
        ollama_form.addRow("", note)
        layout.addWidget(ollama_group)

        # ── Save button ───────────────────────────────────────────────────
        save_btn = QPushButton("Сохранить настройки")
        save_btn.clicked.connect(self._save)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 30px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #5aadff; }
        """)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()

    def _save(self):
        src_keys = ["mic", "system", "both"]
        self.settings["audio_source"] = src_keys[self.combo_source.currentIndex()]
        self.settings["whisper_model"] = self.combo_model.currentText()
        self.settings["language"] = self.combo_lang.currentData()
        self.settings["ollama_model"] = self.edit_ollama_model.text().strip()
        self.settings["ollama_url"] = self.edit_ollama_url.text().strip()
        save_settings(self.settings)
        QMessageBox.information(self, "Сохранено", "Настройки сохранены!")

    def _test_ollama(self):
        import requests
        url = self.edit_ollama_url.text().strip()
        try:
            r = requests.get(f"{url}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            msg = "✅ Ollama доступна!\n\nДоступные модели:\n" + "\n".join(models or ["(нет)"])
            QMessageBox.information(self, "Соединение", msg)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"❌ Не удалось подключиться:\n{e}")

    def get_settings(self) -> dict:
        return load_settings()

    @staticmethod
    def _group_style():
        return """
            QGroupBox {
                color: #c0c0c0;
                font-weight: bold;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 8px;
                padding: 12px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        """

    @staticmethod
    def _btn_style():
        return """
            QPushButton {
                background-color: #2d2d2d;
                color: #c0c0c0;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #3a3a3a; }
        """
