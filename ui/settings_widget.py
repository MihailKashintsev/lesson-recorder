from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QGroupBox, QFormLayout,
    QMessageBox, QScrollArea, QFrame, QButtonGroup, QRadioButton,
    QCheckBox, QStackedWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
import json, sys, subprocess
from pathlib import Path

# ── Python-пакеты — описания и метаданные ────────────────────────────────────
PACKAGES_INFO = [
    {
        "import_name": "whisper",
        "pip_name":    "openai-whisper",
        "label":       "Whisper",
        "desc":        "Офлайн-транскрипция аудио в текст (нейросеть OpenAI)",
        "used_for":    "🎙 Запись и транскрипция",
        "required":    True,
    },
    {
        "import_name": "pytesseract",
        "pip_name":    "pytesseract",
        "label":       "pytesseract",
        "desc":        "Python-обёртка для Tesseract OCR",
        "used_for":    "📷 Фото → Текст",
        "required":    True,
    },
    {
        "import_name": "PIL",
        "pip_name":    "Pillow",
        "label":       "Pillow",
        "desc":        "Открытие и обработка изображений",
        "used_for":    "📷 Фото → Текст",
        "required":    True,
    },
    {
        "import_name": "openai",
        "pip_name":    "openai",
        "label":       "openai",
        "desc":        "API-клиент для OpenAI, DeepSeek, Groq, OpenRouter",
        "used_for":    "🤖 Создание конспектов (ИИ)",
        "required":    True,
    },
    {
        "import_name": "requests",
        "pip_name":    "requests",
        "label":       "requests",
        "desc":        "HTTP-запросы: обновления приложения, скачивание языков",
        "used_for":    "🔄 Обновления и языки OCR",
        "required":    True,
    },
    {
        "import_name": "sounddevice",
        "pip_name":    "sounddevice",
        "label":       "sounddevice",
        "desc":        "Захват звука с микрофона",
        "used_for":    "🎙 Запись аудио",
        "required":    True,
    },
    {
        "import_name": "pyaudiowpatch",
        "pip_name":    "PyAudioWPatch",
        "label":       "PyAudioWPatch",
        "desc":        "Захват системного звука (Windows loopback)",
        "used_for":    "🖥 Запись системного звука",
        "required":    False,
    },
    {
        "import_name": "cv2",
        "pip_name":    "opencv-python",
        "label":       "OpenCV",
        "desc":        "Работа с веб-камерой для съёмки фото",
        "used_for":    "📷 Камера в Фото → Текст",
        "required":    False,
    },
    {
        "import_name": "google.generativeai",
        "pip_name":    "google-generativeai",
        "label":       "google-generativeai",
        "desc":        "API-клиент для Google Gemini",
        "used_for":    "🤖 ИИ провайдер Gemini",
        "required":    False,
    },
]


def _is_package_installed(import_name: str) -> bool:
    """Быстрая проверка через importlib без реального импорта."""
    import importlib.util
    # Для вложенных имён (google.generativeai) берём корневой пакет
    root = import_name.split(".")[0]
    return importlib.util.find_spec(root) is not None


class PipThread(QThread):
    """Устанавливает или удаляет pip-пакет в фоновом потоке."""
    done = pyqtSignal(str, bool, str)   # (pip_name, success, message)

    def __init__(self, action: str, pip_name: str):
        super().__init__()
        self.action   = action    # "install" | "uninstall"
        self.pip_name = pip_name

    def run(self):
        try:
            if self.action == "install":
                cmd = [sys.executable, "-m", "pip", "install", self.pip_name, "--quiet",
                       "--disable-pip-version-check"]
            else:
                cmd = [sys.executable, "-m", "pip", "uninstall", self.pip_name,
                       "-y", "--quiet"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if r.returncode == 0:
                self.done.emit(self.pip_name, True, "")
            else:
                err = (r.stderr or r.stdout or "Неизвестная ошибка")[:300]
                self.done.emit(self.pip_name, False, err)
        except Exception as e:
            self.done.emit(self.pip_name, False, str(e))

from core.summarizer import PROVIDERS, get_provider_config
from ui.theme import get_colors

SETTINGS_PATH = Path.home() / ".lesson_recorder" / "settings.json"

DEFAULTS = {
    "audio_source": "both",
    "mic_device_index": None,
    "whisper_model": "tiny",
    "language": "auto",
    "ai_provider": "deepseek",
    "ai_api_key": "",
    "ai_model": "deepseek-chat",
    "ai_custom_url": "",
    "ai_custom_model": "",
    "theme": "dark",
}


def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                return {**DEFAULTS, **json.load(f)}
        except Exception:
            pass
    return dict(DEFAULTS)


def save_settings(settings: dict):
    SETTINGS_PATH.parent.mkdir(exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


class SettingsWidget(QWidget):
    theme_changed = pyqtSignal(str)   # "dark" | "light"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings     = load_settings()
        self._theme       = self.settings.get("theme", "dark")
        self._pip_threads: dict[str, PipThread] = {}
        self._pkg_rows:    dict[str, dict]       = {}
        self._build_ui()

    def apply_theme(self, theme: str):
        self._theme = theme
        # Full rebuild would be heavy; easier to just re-apply stylesheet
        c = get_colors(theme)
        self.setStyleSheet(self._widget_stylesheet(c))

    def _widget_stylesheet(self, c: dict) -> str:
        bg_card = c.get("bg_card", c["bg_input"])
        return f"""
            QWidget {{ background: {c['bg_main']}; color: {c['text']}; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ background: {c['bg_main']}; }}
            QGroupBox {{
                color: {c['text_muted']};
                font-weight: 600; font-size: 11px;
                text-transform: uppercase; letter-spacing: 0.8px;
                border: 1px solid {c['border']};
                border-radius: 10px; margin-top: 14px; padding-top: 18px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 12px; padding: 0 6px;
                background: {c['bg_main']};
            }}
            QLabel {{ color: {c['text']}; background: transparent; }}

            /* ── ComboBox ── */
            QComboBox {{
                background: {c['bg_input']}; color: {c['text']};
                border: 1px solid {c['border']}; border-radius: 6px;
                padding: 5px 32px 5px 10px;
                min-height: 20px;
            }}
            QComboBox:hover {{ border-color: {c['border_active']}; }}
            QComboBox:focus {{ border-color: {c['border_active']}; outline: none; }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 26px;
                border-left: 1px solid {c['border']};
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: {c['bg_input']};
            }}
            QComboBox::down-arrow {{
                width: 10px; height: 10px;
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {c['text_muted']};
            }}

            /* ── Выпадающий список (dropdown popup) ── */
            QComboBox QAbstractItemView {{
                background: {bg_card};
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
                min-height: 24px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: {c['bg_hover']};
                color: {c['text']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background: {c['accent_blue']};
                color: #ffffff;
            }}
            QComboBox QAbstractItemView QScrollBar:vertical {{
                background: {bg_card};
                width: 7px; border-radius: 4px;
            }}
            QComboBox QAbstractItemView QScrollBar::handle:vertical {{
                background: {c['border']}; border-radius: 4px; min-height: 20px;
            }}

            QLineEdit {{
                background: {c['bg_input']}; color: {c['text']};
                border: 1px solid {c['border']}; border-radius: 6px; padding: 5px 10px;
            }}
            QLineEdit:focus {{ border-color: {c['border_active']}; }}
            QCheckBox {{ color: {c['text']}; }}
        """

    def _build_ui(self):
        c = get_colors(self._theme)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        layout = QVBoxLayout(container)
        layout.setSpacing(24)
        layout.setContentsMargins(32, 32, 32, 32)

        # ── Page title ────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel("Настройки")
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {c['text']};")
        title_row.addWidget(title)
        title_row.addStretch()

        # Theme toggle
        self.theme_btn = QPushButton()
        self._update_theme_btn(c)
        self.theme_btn.setFixedSize(100, 32)
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(self._toggle_theme)
        title_row.addWidget(self.theme_btn)

        layout.addLayout(title_row)

        # ── Аудио ─────────────────────────────────────────────────────────
        audio_group = QGroupBox("Запись аудио")
        audio_form = QFormLayout(audio_group)
        audio_form.setSpacing(12)
        audio_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.combo_source = QComboBox()
        self.combo_source.addItems(["Микрофон", "Системный звук", "Оба источника"])
        src_map = {"mic": 0, "system": 1, "both": 2}
        self.combo_source.setCurrentIndex(src_map.get(self.settings["audio_source"], 2))
        audio_form.addRow("Источник:", self.combo_source)

        # ✅ НОВОЕ: Выбор устройства ввода
        self.combo_mic_device = QComboBox()
        # Ограничиваем ширину — длинные имена устройств не должны растягивать форму
        self.combo_mic_device.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_mic_device.setMinimumContentsLength(20)
        self.combo_mic_device.setMaximumWidth(360)
        self._populate_mic_devices()
        audio_form.addRow("Микрофон:", self.combo_mic_device)

        mic_hint = QLabel("Выбор устройства применяется при записи микрофона или обоих источников")
        mic_hint.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
        mic_hint.setWordWrap(True)
        audio_form.addRow("", mic_hint)

        layout.addWidget(audio_group)

        # ── Whisper ───────────────────────────────────────────────────────
        whisper_group = QGroupBox("Транскрипция — Whisper (офлайн)")
        whisper_form = QFormLayout(whisper_group)
        whisper_form.setSpacing(12)
        whisper_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.combo_whisper_model = QComboBox()
        models = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
        self.combo_whisper_model.addItems(models)
        if self.settings["whisper_model"] in models:
            self.combo_whisper_model.setCurrentIndex(models.index(self.settings["whisper_model"]))
        whisper_form.addRow("Модель:", self.combo_whisper_model)

        whisper_info = QLabel(
            "<b>tiny</b> — самая быстрая, загрузка ~75 МБ  ·  "
            "<b>base</b> — быстрая, ~140 МБ  ·  "
            "<b>small</b> — хорошая, ~460 МБ  ·  "
            "<b>medium</b> — отличная, ~1.5 ГБ  ·  "
            "<b>large</b> — лучшая, ~3 ГБ"
        )
        whisper_info.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
        whisper_info.setWordWrap(True)
        whisper_form.addRow("", whisper_info)

        self.combo_lang = QComboBox()
        langs = {
            "auto": "Авто-определение", "ru": "Русский", "en": "English",
            "uk": "Українська", "de": "Deutsch", "fr": "Français",
            "es": "Español", "zh": "中文", "ja": "日本語",
        }
        for code, name in langs.items():
            self.combo_lang.addItem(name, code)
        for i in range(self.combo_lang.count()):
            if self.combo_lang.itemData(i) == self.settings.get("language", "auto"):
                self.combo_lang.setCurrentIndex(i)
                break
        whisper_form.addRow("Язык:", self.combo_lang)

        layout.addWidget(whisper_group)

        # ── ИИ провайдер ──────────────────────────────────────────────────
        ai_group = QGroupBox("ИИ для конспектов")
        ai_layout = QVBoxLayout(ai_group)
        ai_layout.setSpacing(14)

        # Выбор провайдера
        provider_row = QHBoxLayout()
        provider_lbl = QLabel("Провайдер:")
        provider_lbl.setFixedWidth(120)
        provider_lbl.setStyleSheet(f"color: {c['text_muted']};")

        self.combo_provider = QComboBox()
        self.combo_provider.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_provider.setMinimumContentsLength(18)
        self.combo_provider.setMaximumWidth(320)
        for pid, pcfg in PROVIDERS.items():
            rf_tag = " ✅ РФ" if pcfg.get("rf_available") else ""
            self.combo_provider.addItem(pcfg["name"] + rf_tag, pid)

        current_provider = self.settings.get("ai_provider", "deepseek")
        for i in range(self.combo_provider.count()):
            if self.combo_provider.itemData(i) == current_provider:
                self.combo_provider.setCurrentIndex(i)
                break
        self.combo_provider.currentIndexChanged.connect(self._on_provider_changed)

        provider_row.addWidget(provider_lbl)
        provider_row.addWidget(self.combo_provider)
        ai_layout.addLayout(provider_row)

        # Инфо о провайдере
        self.provider_info = QLabel("")
        self.provider_info.setStyleSheet(f"""
            color: {c['accent_green']};
            font-size: 11px;
            padding: 6px 10px;
            background: transparent;
            border: 1px solid {c['accent_green']};
            border-radius: 6px;
        """)
        self.provider_info.setWordWrap(True)
        ai_layout.addWidget(self.provider_info)

        # API ключ
        key_row = QHBoxLayout()
        key_lbl = QLabel("API ключ:")
        key_lbl.setFixedWidth(120)
        key_lbl.setStyleSheet(f"color: {c['text_muted']};")

        self.edit_api_key = QLineEdit(self.settings.get("ai_api_key", ""))
        self.edit_api_key.setEchoMode(QLineEdit.EchoMode.Password)

        self.toggle_key_btn = QPushButton("👁")
        self.toggle_key_btn.setFixedSize(32, 32)
        self.toggle_key_btn.setCheckable(True)
        self.toggle_key_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['bg_input']}; border: 1px solid {c['border']};
                border-radius: 6px; font-size: 14px;
            }}
            QPushButton:hover {{ background: {c['bg_hover']}; }}
            QPushButton:checked {{ background: {c['bg_selected']}; }}
        """)
        self.toggle_key_btn.toggled.connect(
            lambda on: self.edit_api_key.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )

        key_row.addWidget(key_lbl)
        key_row.addWidget(self.edit_api_key)
        key_row.addWidget(self.toggle_key_btn)
        ai_layout.addLayout(key_row)

        # Модель — QStackedWidget вместо двух виджетов в одной строке
        model_row = QHBoxLayout()
        model_lbl = QLabel("Модель:")
        model_lbl.setFixedWidth(120)
        model_lbl.setStyleSheet(f"color: {c['text_muted']};")

        # ✅ ИСПРАВЛЕНО: раньше combo и lineEdit были в одной строке одновременно,
        # при растяжении окна они визуально накладывались.
        # Теперь — один контейнер-стек, который показывает только один виджет.
        self._model_stack = QStackedWidget()
        self.combo_ai_model = QComboBox()
        self.combo_ai_model.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_ai_model.setMinimumContentsLength(20)

        self.edit_custom_model = QLineEdit()
        self.edit_custom_model.setPlaceholderText("Введи название модели вручную")

        self._model_stack.addWidget(self.combo_ai_model)   # index 0 — стандартный
        self._model_stack.addWidget(self.edit_custom_model) # index 1 — кастомный

        model_row.addWidget(model_lbl)
        model_row.addWidget(self._model_stack)
        ai_layout.addLayout(model_row)

        # Инфо о выбранной модели — отступ через пустой лейбл, без хардкодного padding-left
        model_info_row = QHBoxLayout()
        _spacer_lbl = QLabel()
        _spacer_lbl.setFixedWidth(120)
        self.model_info_lbl = QLabel("")
        self.model_info_lbl.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
        self.model_info_lbl.setWordWrap(True)
        model_info_row.addWidget(_spacer_lbl)
        model_info_row.addWidget(self.model_info_lbl)
        ai_layout.addLayout(model_info_row)
        self.combo_ai_model.currentIndexChanged.connect(self._on_model_changed)

        # Кастомный URL
        url_row = QHBoxLayout()
        self.url_lbl = QLabel("URL API:")
        self.url_lbl.setFixedWidth(120)
        self.url_lbl.setStyleSheet(f"color: {c['text_muted']};")
        self.edit_custom_url = QLineEdit(self.settings.get("ai_custom_url", ""))
        self.edit_custom_url.setPlaceholderText("http://localhost:1234/v1")
        url_row.addWidget(self.url_lbl)
        url_row.addWidget(self.edit_custom_url)
        ai_layout.addLayout(url_row)

        # Кнопки
        btn_row = QHBoxLayout()
        self.test_btn = QPushButton("🔌 Проверить соединение")
        self.test_btn.setStyleSheet(self._secondary_btn_style(c))
        self.test_btn.clicked.connect(self._test_connection)

        self.signup_btn = QPushButton("🌐 Получить ключ →")
        self.signup_btn.setStyleSheet(self._link_btn_style(c))
        self.signup_btn.clicked.connect(self._open_signup)

        btn_row.addWidget(self.test_btn)
        btn_row.addWidget(self.signup_btn)
        btn_row.addStretch()
        ai_layout.addLayout(btn_row)

        layout.addWidget(ai_group)

        # ── Пакеты Python ─────────────────────────────────────────────────
        layout.addWidget(self._build_packages_group(c))

        # ── Сохранить ─────────────────────────────────────────────────────
        save_btn = QPushButton("💾  Сохранить настройки")
        save_btn.clicked.connect(self._save)
        save_btn.setFixedHeight(44)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['accent_blue']};
                color: white; border: none;
                border-radius: 8px;
                font-size: 14px; font-weight: 600;
                padding: 0 32px;
            }}
            QPushButton:hover {{ background: {c['accent_blue']}cc; }}
        """)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()

        # Инициализируем под текущий провайдер
        self._on_provider_changed()
        self.setStyleSheet(self._widget_stylesheet(c))

    # ── Устройства ввода ──────────────────────────────────────────────────

    def _populate_mic_devices(self):
        self.combo_mic_device.clear()
        self.combo_mic_device.addItem("По умолчанию", None)

        try:
            from core.recorder import get_input_devices
            devices = get_input_devices()
            for dev in devices:
                name = dev["name"][:60]
                self.combo_mic_device.addItem(f"{name}", dev["index"])
        except Exception:
            pass

        # Восстанавливаем выбранное устройство
        saved_idx = self.settings.get("mic_device_index", None)
        for i in range(self.combo_mic_device.count()):
            if self.combo_mic_device.itemData(i) == saved_idx:
                self.combo_mic_device.setCurrentIndex(i)
                break

    # ── Тема ──────────────────────────────────────────────────────────────

    def _update_theme_btn(self, c: dict):
        if self._theme == "dark":
            self.theme_btn.setText("☀  Светлая")
            self.theme_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {c['bg_input']}; color: {c['text']};
                    border: 1px solid {c['border']}; border-radius: 8px;
                    font-size: 12px;
                }}
                QPushButton:hover {{ background: {c['bg_hover']}; }}
            """)
        else:
            self.theme_btn.setText("🌙  Тёмная")
            self.theme_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {c['bg_input']}; color: {c['text']};
                    border: 1px solid {c['border']}; border-radius: 8px;
                    font-size: 12px;
                }}
                QPushButton:hover {{ background: {c['bg_hover']}; }}
            """)

    def _toggle_theme(self):
        new_theme = "light" if self._theme == "dark" else "dark"
        self._theme = new_theme
        c = get_colors(new_theme)
        self._update_theme_btn(c)
        self.theme_changed.emit(new_theme)

    # ── Провайдер изменился ───────────────────────────────────────────────

    def _on_provider_changed(self):
        provider_id = self.combo_provider.currentData()
        cfg = get_provider_config(provider_id)
        c = get_colors(self._theme)

        self.provider_info.setText(cfg["free_info"])

        is_gigachat = (provider_id == "gigachat")
        if is_gigachat:
            self.provider_info.setText(
                cfg["free_info"] + "\n"
                "Ключ: developers.sber.ru/studio → создай проект → «Авторизационные данные»"
            )

        self.edit_api_key.setPlaceholderText(cfg.get("key_hint", ""))

        is_custom = provider_id == "custom"
        # ✅ ИСПРАВЛЕНО: переключаем стек (index 0 = combo, 1 = lineEdit)
        # вместо setVisible() на двух виджетах в одной строке
        self._model_stack.setCurrentIndex(1 if is_custom else 0)
        self.url_lbl.setVisible(is_custom)
        self.edit_custom_url.setVisible(is_custom)
        self.signup_btn.setVisible(bool(cfg.get("signup_url")))

        if not is_custom:
            self.combo_ai_model.clear()
            model_info = cfg.get("model_info", {})
            for m in cfg["models"]:
                # Добавляем информацию о модели в tooltip через addItem
                self.combo_ai_model.addItem(m, m)

            saved_model = self.settings.get("ai_model", cfg["default_model"])
            restored = False
            for i in range(self.combo_ai_model.count()):
                if self.combo_ai_model.itemData(i) == saved_model:
                    self.combo_ai_model.setCurrentIndex(i)
                    restored = True
                    break
            if not restored and self.combo_ai_model.count() > 0:
                # Восстанавливаем default
                for i in range(self.combo_ai_model.count()):
                    if self.combo_ai_model.itemData(i) == cfg["default_model"]:
                        self.combo_ai_model.setCurrentIndex(i)
                        break

            self._on_model_changed()
        else:
            self.edit_custom_model.setText(self.settings.get("ai_custom_model", ""))
            self.model_info_lbl.setText("")

    def _on_model_changed(self):
        provider_id = self.combo_provider.currentData()
        cfg = get_provider_config(provider_id)
        model = self.combo_ai_model.currentData() or ""
        info = cfg.get("model_info", {}).get(model, "")
        self.model_info_lbl.setText(info)

    # ── Получить текущую модель ───────────────────────────────────────────

    def _get_current_model(self) -> str:
        provider_id = self.combo_provider.currentData()
        if provider_id == "custom":
            return self.edit_custom_model.text().strip()
        return self.combo_ai_model.currentData() or ""

    def _get_current_url(self) -> str:
        provider_id = self.combo_provider.currentData()
        if provider_id == "custom":
            return self.edit_custom_url.text().strip()
        return get_provider_config(provider_id)["base_url"]

    # ── Проверка соединения ───────────────────────────────────────────────

    def _test_connection(self):
        import requests as req
        provider_id = self.combo_provider.currentData()
        key = self.edit_api_key.text().strip()
        model = self._get_current_model()
        base_url = self._get_current_url()

        if not base_url:
            QMessageBox.warning(self, "Нет URL", "Укажи URL API.")
            return
        if not model:
            QMessageBox.warning(self, "Нет модели", "Укажи модель.")
            return

        headers = {"Content-Type": "application/json"}

        if provider_id == "gigachat":
            if not key:
                QMessageBox.warning(self, "Нет ключа", "Укажи авторизационные данные GigaChat.")
                return
            try:
                import uuid
                auth_resp = req.post(
                    "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
                    headers={
                        "Authorization": f"Basic {key}",
                        "RqUID": str(uuid.uuid4()),
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={"scope": "GIGACHAT_API_PERS"},
                    verify=False,
                    timeout=10,
                )
                auth_resp.raise_for_status()
                token = auth_resp.json()["access_token"]
                headers["Authorization"] = f"Bearer {token}"
            except Exception as e:
                QMessageBox.critical(self, "❌ Ошибка авторизации GigaChat",
                    f"Не удалось получить токен:\n{e}")
                return
        elif key:
            headers["Authorization"] = f"Bearer {key}"

        if provider_id == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/lesson-recorder"
            headers["X-Title"] = "LessonRecorder"

        verify_ssl = (provider_id != "gigachat")
        try:
            r = req.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5,
                },
                timeout=15,
                verify=verify_ssl,
            )
            if r.status_code == 200:
                QMessageBox.information(self, "✅ Успех",
                    f"Соединение с «{self.combo_provider.currentText()}» работает!\n"
                    f"Модель: {model}")
            elif r.status_code == 401:
                QMessageBox.critical(self, "❌ Ошибка", "Неверный API ключ.")
            elif r.status_code == 404:
                QMessageBox.warning(self, "⚠️ Модель не найдена",
                    f"Модель «{model}» не найдена.")
            else:
                QMessageBox.warning(self, "⚠️ Ошибка",
                    f"Код {r.status_code}:\n{r.text[:300]}")
        except req.exceptions.ConnectionError:
            QMessageBox.critical(self, "❌ Нет соединения", f"Не удалось подключиться:\n{base_url}")
        except Exception as e:
            QMessageBox.critical(self, "❌ Ошибка", str(e))

    def _open_signup(self):
        import webbrowser
        provider_id = self.combo_provider.currentData()
        url = get_provider_config(provider_id).get("signup_url", "")
        if url:
            webbrowser.open(f"https://{url}")

    # ── Пакеты ────────────────────────────────────────────────────────────

    def _build_packages_group(self, c: dict) -> QGroupBox:
        group = QGroupBox("Python-зависимости")
        vbox  = QVBoxLayout(group)
        vbox.setSpacing(6)
        vbox.setContentsMargins(16, 16, 16, 16)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Пакет", styleSheet=f"color:{c['text_muted']};font-size:11px;font-weight:600;"))
        header_row.addStretch()
        install_all_btn = QPushButton("⬇  Установить всё отсутствующее")
        install_all_btn.setFixedHeight(26)
        install_all_btn.setStyleSheet(
            f"QPushButton{{background:{c['accent_blue']};color:#fff;border:none;"
            f"border-radius:5px;font-size:11px;padding:0 12px;}}"
            f"QPushButton:hover{{background:{c['accent_blue']}cc;}}"
        )
        install_all_btn.clicked.connect(self._install_missing)
        header_row.addWidget(install_all_btn)
        vbox.addLayout(header_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{c['border']};")
        vbox.addWidget(sep)

        for pkg in PACKAGES_INFO:
            row = self._build_pkg_row(pkg, c)
            vbox.addWidget(row)

        return group

    def _build_pkg_row(self, pkg: dict, c: dict) -> QWidget:
        row_w = QWidget()
        row_w.setStyleSheet("background:transparent;")
        row_layout = QHBoxLayout(row_w)
        row_layout.setContentsMargins(0, 3, 0, 3)
        row_layout.setSpacing(10)

        # Иконка статуса
        installed = _is_package_installed(pkg["import_name"])
        status_lbl = QLabel("✅" if installed else "❌")
        status_lbl.setFixedWidth(20)
        status_lbl.setStyleSheet("font-size:13px;")
        row_layout.addWidget(status_lbl)

        # Имя + описание
        info_block = QVBoxLayout()
        info_block.setSpacing(1)
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_lbl = QLabel(pkg["label"])
        name_lbl.setStyleSheet(f"color:{c['text']};font-size:12px;font-weight:600;")
        name_row.addWidget(name_lbl)
        badge = QLabel(pkg["used_for"])
        badge.setStyleSheet(
            f"color:{c['accent_blue']};font-size:10px;background:transparent;"
        )
        name_row.addWidget(badge)
        if pkg["required"]:
            req_lbl = QLabel("обязательный")
            req_lbl.setStyleSheet(
                f"color:#888;font-size:10px;background:{c['bg_input']};"
                f"border-radius:3px;padding:1px 6px;"
            )
            name_row.addWidget(req_lbl)
        name_row.addStretch()
        info_block.addLayout(name_row)
        desc_lbl = QLabel(pkg["desc"])
        desc_lbl.setStyleSheet(f"color:{c['text_muted']};font-size:11px;")
        info_block.addWidget(desc_lbl)
        row_layout.addLayout(info_block, stretch=1)

        # Кнопка + прогресс
        action_lbl = QLabel("")
        action_lbl.setStyleSheet(f"color:{c['text_muted']};font-size:11px;min-width:80px;")

        if installed:
            btn = QPushButton("🗑 Удалить")
            btn.setFixedHeight(26)
            btn.setStyleSheet(
                "QPushButton{background:#3a1a1a;color:#f44336;border:none;"
                "border-radius:5px;font-size:11px;padding:0 10px;}"
                "QPushButton:hover{background:#5a2020;}"
                "QPushButton:disabled{background:#222;color:#555;}"
            )
            btn.clicked.connect(lambda _, p=pkg: self._uninstall_package(p))
        else:
            btn = QPushButton("⬇ Установить")
            btn.setFixedHeight(26)
            btn.setStyleSheet(
                f"QPushButton{{background:{c['accent_blue']};color:#fff;border:none;"
                f"border-radius:5px;font-size:11px;padding:0 10px;}}"
                f"QPushButton:hover{{background:{c['accent_blue']}cc;}}"
                f"QPushButton:disabled{{background:#1a2a3a;color:#555;}}"
            )
            btn.clicked.connect(lambda _, p=pkg: self._install_package(p))

        row_layout.addWidget(action_lbl)
        row_layout.addWidget(btn)

        self._pkg_rows[pkg["pip_name"]] = {
            "status_lbl": status_lbl,
            "action_lbl": action_lbl,
            "btn":        btn,
            "pkg":        pkg,
        }
        return row_w

    def _install_missing(self):
        for pkg in PACKAGES_INFO:
            if not _is_package_installed(pkg["import_name"]):
                if pkg["pip_name"] not in self._pip_threads:
                    self._install_package(pkg)

    def _install_package(self, pkg: dict):
        pip_name = pkg["pip_name"]
        if pip_name in self._pip_threads:
            return
        row = self._pkg_rows.get(pip_name, {})
        if row.get("btn"):
            row["btn"].setEnabled(False)
        if row.get("action_lbl"):
            row["action_lbl"].setText("Скачиваю…")
        t = PipThread("install", pip_name)
        t.done.connect(self._on_pip_done)
        self._pip_threads[pip_name] = t
        t.start()

    def _uninstall_package(self, pkg: dict):
        pip_name = pkg["pip_name"]
        if pip_name in self._pip_threads:
            return
        row = self._pkg_rows.get(pip_name, {})
        if row.get("btn"):
            row["btn"].setEnabled(False)
        if row.get("action_lbl"):
            row["action_lbl"].setText("Удаляю…")
        t = PipThread("uninstall", pip_name)
        t.done.connect(self._on_pip_done)
        self._pip_threads[pip_name] = t
        t.start()

    def _on_pip_done(self, pip_name: str, success: bool, message: str):
        self._pip_threads.pop(pip_name, None)
        row = self._pkg_rows.get(pip_name, {})
        if not row:
            return
        pkg       = row["pkg"]
        installed = _is_package_installed(pkg["import_name"])
        c         = get_colors(self._theme)

        # Обновляем иконку
        if row.get("status_lbl"):
            row["status_lbl"].setText("✅" if installed else "❌")

        # Обновляем кнопку
        btn = row.get("btn")
        if btn:
            btn.setEnabled(True)
            if installed:
                btn.setText("🗑 Удалить")
                btn.setStyleSheet(
                    "QPushButton{background:#3a1a1a;color:#f44336;border:none;"
                    "border-radius:5px;font-size:11px;padding:0 10px;}"
                    "QPushButton:hover{background:#5a2020;}"
                    "QPushButton:disabled{background:#222;color:#555;}"
                )
                try:
                    btn.clicked.disconnect()
                except Exception:
                    pass
                btn.clicked.connect(lambda _, p=pkg: self._uninstall_package(p))
            else:
                btn.setText("⬇ Установить")
                btn.setStyleSheet(
                    f"QPushButton{{background:{c['accent_blue']};color:#fff;border:none;"
                    f"border-radius:5px;font-size:11px;padding:0 10px;}}"
                    f"QPushButton:hover{{background:{c['accent_blue']}cc;}}"
                    f"QPushButton:disabled{{background:#1a2a3a;color:#555;}}"
                )
                try:
                    btn.clicked.disconnect()
                except Exception:
                    pass
                btn.clicked.connect(lambda _, p=pkg: self._install_package(p))

        if row.get("action_lbl"):
            row["action_lbl"].setText("✅ Готово" if success else f"❌ {message[:40]}")

    # ── Сохранение ────────────────────────────────────────────────────────

    def _save(self):
        provider_id = self.combo_provider.currentData()
        src_keys = ["mic", "system", "both"]

        mic_device_index = self.combo_mic_device.currentData()

        self.settings.update({
            "audio_source": src_keys[self.combo_source.currentIndex()],
            "mic_device_index": mic_device_index,
            "whisper_model": self.combo_whisper_model.currentText(),
            "language": self.combo_lang.currentData(),
            "ai_provider": provider_id,
            "ai_api_key": self.edit_api_key.text().strip(),
            "ai_model": self._get_current_model(),
            "ai_custom_url": self.edit_custom_url.text().strip(),
            "ai_custom_model": self.edit_custom_model.text().strip(),
            "theme": self._theme,
        })
        save_settings(self.settings)

        # ✅ НЕТ перезапуска приложения — только инфо
        c = get_colors(self._theme)
        msg = QMessageBox(self)
        msg.setWindowTitle("Настройки сохранены")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("✅ Настройки успешно сохранены!")
        msg.setStyleSheet(f"QMessageBox {{ background: {c['bg_card'] if 'bg_card' in c else c['bg_panel']}; color: {c['text']}; }}")
        msg.exec()

    def get_settings(self) -> dict:
        return load_settings()

    # ── Стили ─────────────────────────────────────────────────────────────

    def _secondary_btn_style(self, c: dict) -> str:
        return f"""
            QPushButton {{
                background: {c['bg_input']}; color: {c['text']};
                border: 1px solid {c['border']}; border-radius: 6px;
                padding: 6px 16px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {c['bg_hover']}; color: {c['text']}; }}
        """

    def _link_btn_style(self, c: dict) -> str:
        return f"""
            QPushButton {{
                background: transparent; color: {c['accent_blue']};
                border: 1px solid {c['accent_blue']}; border-radius: 6px;
                padding: 6px 14px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {c['bg_selected']}; }}
        """
