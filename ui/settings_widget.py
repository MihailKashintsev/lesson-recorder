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
        "import_name": "faster_whisper",
        "pip_name":    "faster-whisper",
        "label":       "faster-whisper",
        "desc":        "Офлайн-транскрипция аудио в текст (быстрый Whisper на C++)",
        "used_for":    "🎙 Транскрипция",
        "required":    True,
        "github_url":  "https://github.com/SYSTRAN/faster-whisper",
    },
    {
        "import_name": "numpy",
        "pip_name":    "numpy",
        "label":       "numpy",
        "desc":        "Обработка аудиоданных и матричные операции",
        "used_for":    "🎙 Запись и транскрипция",
        "required":    True,
        "github_url":  "https://github.com/numpy/numpy",
    },
    {
        "import_name": "scipy",
        "pip_name":    "scipy",
        "label":       "scipy",
        "desc":        "Ресемплинг аудио (конвертация частоты дискретизации)",
        "used_for":    "🎙 Обработка аудио",
        "required":    True,
        "github_url":  "https://github.com/scipy/scipy",
    },
    {
        "import_name": "sounddevice",
        "pip_name":    "sounddevice",
        "label":       "sounddevice",
        "desc":        "Захват звука с микрофона",
        "used_for":    "🎙 Запись с микрофона",
        "required":    True,
        "github_url":  "https://github.com/spatialaudio/python-sounddevice",
    },
    {
        "import_name": "requests",
        "pip_name":    "requests",
        "label":       "requests",
        "desc":        "HTTP-запросы: обновления, скачивание языков OCR",
        "used_for":    "🔄 Обновления и языки OCR",
        "required":    True,
        "github_url":  "https://github.com/psf/requests",
    },
    {
        "import_name": "openai",
        "pip_name":    "openai",
        "label":       "openai",
        "desc":        "API-клиент для OpenAI, DeepSeek, Groq, OpenRouter",
        "used_for":    "🤖 ИИ-конспекты",
        "required":    True,
        "github_url":  "https://github.com/openai/openai-python",
    },
    {
        "import_name": "pytesseract",
        "pip_name":    "pytesseract",
        "label":       "pytesseract",
        "desc":        "Python-обёртка для Tesseract OCR",
        "used_for":    "📷 Фото → Текст",
        "required":    False,
        "github_url":  "https://github.com/madmaze/pytesseract",
    },
    {
        "import_name": "PIL",
        "pip_name":    "Pillow",
        "label":       "Pillow",
        "desc":        "Открытие и обработка изображений для OCR",
        "used_for":    "📷 Фото → Текст",
        "required":    False,
        "github_url":  "https://github.com/python-pillow/Pillow",
    },
    {
        "import_name": "pyaudiowpatch",
        "pip_name":    "PyAudioWPatch",
        "label":       "PyAudioWPatch",
        "desc":        "Запись системного звука (WASAPI loopback, только Windows)",
        "used_for":    "🖥 Системный звук",
        "required":    False,
        "github_url":  "https://github.com/s0d3s/PyAudioWPatch",
    },
    {
        "import_name": "cv2",
        "pip_name":    "opencv-python",
        "label":       "OpenCV",
        "desc":        "Веб-камера для съёмки фото в диалоге OCR",
        "used_for":    "📷 Камера → OCR",
        "required":    False,
        "github_url":  "https://github.com/opencv/opencv-python",
    },
    {
        "import_name": "google.generativeai",
        "pip_name":    "google-generativeai",
        "label":       "google-generativeai",
        "desc":        "API-клиент для Google Gemini",
        "used_for":    "🤖 ИИ провайдер Gemini",
        "required":    False,
        "github_url":  "https://github.com/google-gemini/generative-ai-python",
    },
]


def _is_package_installed(import_name: str) -> bool:
    """Проверка с инвалидацией кеша (нужно после pip install)."""
    import importlib
    import importlib.util
    importlib.invalidate_caches()
    root = import_name.split(".")[0]
    return importlib.util.find_spec(root) is not None


def _get_package_path(import_name: str) -> str:
    """Возвращает путь к пакету или пустую строку если не установлен."""
    import importlib
    import importlib.util
    importlib.invalidate_caches()
    root = import_name.split(".")[0]
    spec = importlib.util.find_spec(root)
    if spec is None:
        return ""
    # Предпочитаем папку пакета, а не __init__.py
    if spec.submodule_search_locations:
        try:
            return str(list(spec.submodule_search_locations)[0])
        except Exception:
            pass
    if spec.origin:
        from pathlib import Path
        return str(Path(spec.origin).parent)
    return ""


class PipThread(QThread):
    """Устанавливает или удаляет pip-пакет в фоновом потоке."""
    done = pyqtSignal(str, bool, str)   # (pip_name, success, full_output)

    def __init__(self, action: str, pip_name: str):
        super().__init__()
        self.action   = action    # "install" | "uninstall"
        self.pip_name = pip_name

    def run(self):
        try:
            from core.python_path import find_python_exe
            python = find_python_exe()
        except RuntimeError as e:
            self.done.emit(self.pip_name, False, str(e))
            return

        try:
            if self.action == "install":
                cmd = [python, "-m", "pip", "install", self.pip_name,
                       "--disable-pip-version-check", "-v"]  # -v для подробного вывода
            else:
                cmd = [python, "-m", "pip", "uninstall", self.pip_name, "-y"]

            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW

            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
                creationflags=creation_flags,
            )
            output = (r.stdout + "\n" + r.stderr).strip()
            if r.returncode == 0:
                self.done.emit(self.pip_name, True, output)
            else:
                self.done.emit(self.pip_name, False, output)
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
        self.settings          = load_settings()
        self._theme            = self.settings.get("theme", "dark")
        self._pip_threads: dict[str, PipThread] = {}
        self._pkg_rows:    dict[str, dict]       = {}
        self._pkg_container    = None
        self._pkg_vbox         = None
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
        outer = QVBoxLayout(group)
        outer.setSpacing(6)
        outer.setContentsMargins(16, 16, 16, 16)

        # Кнопка "установить всё"
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Пакет",
            styleSheet=f"color:{c['text_muted']};font-size:11px;font-weight:600;"))
        hdr.addStretch()
        btn_all = QPushButton("⬇  Установить всё отсутствующее")
        btn_all.setFixedHeight(26)
        btn_all.setStyleSheet(
            f"QPushButton{{background:{c['accent_blue']};color:#fff;border:none;"
            f"border-radius:5px;font-size:11px;padding:0 12px;}}"
            f"QPushButton:hover{{background:{c['accent_blue']}cc;}}"
        )
        btn_all.clicked.connect(self._install_missing)
        hdr.addWidget(btn_all)
        outer.addLayout(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{c['border']};")
        outer.addWidget(sep)

        # Контейнер для строк — сохраняем ссылку чтобы перестраивать
        self._pkg_container = QWidget()
        self._pkg_container.setStyleSheet("background:transparent;")
        self._pkg_vbox = QVBoxLayout(self._pkg_container)
        self._pkg_vbox.setSpacing(2)
        self._pkg_vbox.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._pkg_container)

        self._fill_pkg_rows(c)
        return group

    def _fill_pkg_rows(self, c: dict | None = None):
        """Заполняет/перезаполняет строки пакетов."""
        if c is None:
            c = get_colors(self._theme)

        # Очищаем старые виджеты
        while self._pkg_vbox.count():
            item = self._pkg_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._pkg_rows.clear()

        for pkg in PACKAGES_INFO:
            row_w = self._build_pkg_row(pkg, c)
            self._pkg_vbox.addWidget(row_w)

    def _build_pkg_row(self, pkg: dict, c: dict) -> QWidget:
        pip_name  = pkg["pip_name"]
        installed = _is_package_installed(pkg["import_name"])
        pkg_path  = _get_package_path(pkg["import_name"]) if installed else ""

        row_w = QWidget()
        row_w.setStyleSheet("background:transparent;")

        # ── Вертикальная обёртка (основная строка + путь) ────────────────
        outer = QVBoxLayout(row_w)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(2)

        # ── Основная строка ──────────────────────────────────────────────
        main_row = QWidget()
        main_row.setStyleSheet("background:transparent;")
        hl = QHBoxLayout(main_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)

        # Статус
        status_lbl = QLabel("✅" if installed else "❌")
        status_lbl.setFixedWidth(22)
        status_lbl.setStyleSheet("font-size:13px;")
        hl.addWidget(status_lbl)

        # Имя + бейджи
        name_row = QHBoxLayout(); name_row.setSpacing(6)
        name_lbl = QLabel(pkg["label"])
        name_lbl.setStyleSheet(f"color:{c['text']};font-size:12px;font-weight:600;")
        name_row.addWidget(name_lbl)

        badge = QLabel(pkg["used_for"])
        badge.setStyleSheet(f"color:{c['accent_blue']};font-size:10px;")
        name_row.addWidget(badge)

        if pkg.get("required"):
            req = QLabel("обязательный")
            req.setStyleSheet(
                f"color:#888;font-size:10px;background:{c['bg_input']};"
                "border-radius:3px;padding:1px 6px;")
            name_row.addWidget(req)

        name_widget = QWidget(); name_widget.setStyleSheet("background:transparent;")
        name_widget.setLayout(name_row)
        hl.addWidget(name_widget, stretch=1)

        # ── Маленькие кнопки: терминал + github ─────────────────────────
        def _small_btn(icon_text: str, tooltip: str) -> QPushButton:
            b = QPushButton(icon_text)
            b.setFixedSize(26, 26)
            b.setToolTip(tooltip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{c['bg_input']};color:{c['text_muted']};"
                f"border:1px solid {c['border']};border-radius:5px;"
                f"font-size:12px;padding:0;}}"
                f"QPushButton:hover{{background:{c['bg_hover']};color:{c['text']};}}")
            return b

        pip_cmd = f"pip install {pip_name}"

        # Кнопка копирования pip-команды
        btn_copy = _small_btn("⌨", f"Скопировать: {pip_cmd}")
        btn_copy.clicked.connect(
            lambda checked, cmd=pip_cmd: self._copy_pip_cmd(cmd))
        hl.addWidget(btn_copy)

        # Кнопка GitHub
        gh_url = pkg.get("github_url", "")
        if gh_url:
            btn_gh = _small_btn("🐙", f"Открыть GitHub: {gh_url}")
            btn_gh.clicked.connect(
                lambda checked, url=gh_url: __import__("webbrowser").open(url))
            hl.addWidget(btn_gh)

        # Статус-метка (прогресс/готово/ошибка)
        action_lbl = QLabel("")
        action_lbl.setStyleSheet(f"color:{c['text_muted']};font-size:11px;min-width:70px;")
        hl.addWidget(action_lbl)

        # Кнопка установки/удаления
        btn = QPushButton()
        btn.setFixedHeight(26)
        btn.setMinimumWidth(90)
        if installed:
            btn.setText("🗑 Удалить")
            btn.setStyleSheet(
                "QPushButton{background:#3a1a1a;color:#f44336;border:none;"
                "border-radius:5px;font-size:11px;padding:0 10px;}"
                "QPushButton:hover{background:#5a2020;}"
                "QPushButton:disabled{background:#1a1a1a;color:#555;}")
        else:
            btn.setText("⬇ Установить")
            btn.setStyleSheet(
                f"QPushButton{{background:{c['accent_blue']};color:#fff;border:none;"
                f"border-radius:5px;font-size:11px;padding:0 10px;}}"
                f"QPushButton:hover{{background:{c['accent_blue']}cc;}}"
                f"QPushButton:disabled{{background:#1a2a3a;color:#555;}}")
        hl.addWidget(btn)

        outer.addWidget(main_row)

        # ── Строка описания + пути ───────────────────────────────────────
        desc_row = QHBoxLayout(); desc_row.setSpacing(6)
        desc_row.setContentsMargins(30, 0, 0, 0)

        desc_lbl = QLabel(pkg["desc"])
        desc_lbl.setStyleSheet(f"color:{c['text_muted']};font-size:11px;")
        desc_row.addWidget(desc_lbl)

        # Путь к пакету (кликабельный)
        path_lbl = QLabel()
        path_lbl.setStyleSheet(
            f"color:{c['accent_blue']};font-size:10px;"
            "text-decoration:underline;")
        path_lbl.setCursor(Qt.CursorShape.PointingHandCursor)

        if installed and pkg_path:
            short = pkg_path if len(pkg_path) < 55 else "…" + pkg_path[-52:]
            path_lbl.setText(short)
            path_lbl.setToolTip(pkg_path)
            path_lbl.mousePressEvent = lambda e, p=pkg_path: self._open_folder(p)
        elif installed:
            path_lbl.setText("(путь неизвестен)")
            path_lbl.setStyleSheet(f"color:{c['text_muted']};font-size:10px;")

        desc_row.addWidget(path_lbl)
        desc_row.addStretch()
        outer.addLayout(desc_row)

        # ── Разделитель ──────────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{c['border']};margin:2px 0;")
        outer.addWidget(sep)

        # Сохраняем ссылки
        self._pkg_rows[pip_name] = {
            "status_lbl": status_lbl,
            "action_lbl": action_lbl,
            "path_lbl":   path_lbl,
            "btn":        btn,
            "pkg":        pkg,
            "installed":  installed,
        }

        if installed:
            btn.clicked.connect(lambda checked, pn=pip_name: self._uninstall_by_name(pn))
        else:
            btn.clicked.connect(lambda checked, pn=pip_name: self._install_by_name(pn))

        return row_w

    def _copy_pip_cmd(self, cmd: str):
        """Копирует pip-команду в буфер обмена и показывает подсказку."""
        from PyQt6.QtWidgets import QApplication, QToolTip
        from PyQt6.QtGui import QCursor
        QApplication.clipboard().setText(cmd)
        QToolTip.showText(QCursor.pos(), f"Скопировано: {cmd}", None)

    def _open_folder(self, path: str):
        """Открывает папку пакета в проводнике."""
        import os
        from pathlib import Path
        p = Path(path)
        if not p.exists():
            p = p.parent
        if sys.platform == "win32":
            os.startfile(str(p))
        elif sys.platform == "darwin":
            os.system(f'open "{p}"')
        else:
            os.system(f'xdg-open "{p}"')

    def _install_missing(self):
        for pkg in PACKAGES_INFO:
            if not _is_package_installed(pkg["import_name"]):
                self._install_by_name(pkg["pip_name"])

    def _install_by_name(self, pip_name: str):
        if pip_name in self._pip_threads:
            return
        row = self._pkg_rows.get(pip_name)
        if not row:
            return
        # Блокируем кнопку сразу
        row["btn"].setEnabled(False)
        row["btn"].setText("⬇ Скачиваю…")
        row["action_lbl"].setText("")
        row["_action"] = "install"

        t = PipThread("install", pip_name)
        t.done.connect(self._on_pip_done)
        self._pip_threads[pip_name] = t
        t.start()

    def _uninstall_by_name(self, pip_name: str):
        if pip_name in self._pip_threads:
            return
        row = self._pkg_rows.get(pip_name)
        if not row:
            return
        row["btn"].setEnabled(False)
        row["btn"].setText("🗑 Удаляю…")
        row["action_lbl"].setText("")
        row["_action"] = "uninstall"

        t = PipThread("uninstall", pip_name)
        t.done.connect(self._on_pip_done)
        self._pip_threads[pip_name] = t
        t.start()

    # Оставляем для совместимости (вызов из _build_pkg_row старой версии)
    def _install_package(self, pkg: dict):
        self._install_by_name(pkg["pip_name"])

    def _uninstall_package(self, pkg: dict):
        self._uninstall_by_name(pkg["pip_name"])

    def _on_pip_done(self, pip_name: str, success: bool, output: str):
        self._pip_threads.pop(pip_name, None)
        row = self._pkg_rows.get(pip_name)
        if not row:
            return

        c   = get_colors(self._theme)
        pkg = row["pkg"]

        if not success:
            row["btn"].setEnabled(True)
            row["btn"].setText("🗑 Удалить" if row.get("installed") else "⬇ Установить")
            row["action_lbl"].setText("❌ Ошибка")
            row["action_lbl"].setToolTip(output[:300])
            # Показываем диалог с полным выводом pip
            self._show_pip_log(pip_name, success=False, output=output)
            return

        # Успех
        action   = row.get("_action", "install")
        now_inst = (action == "install")
        row["installed"] = now_inst

        row["status_lbl"].setText("✅" if now_inst else "❌")
        row["action_lbl"].setText("✅ Готово")

        # Обновляем путь
        if "path_lbl" in row:
            if now_inst:
                pkg_path = _get_package_path(pkg["import_name"])
                if pkg_path:
                    short = pkg_path if len(pkg_path) < 55 else "…" + pkg_path[-52:]
                    row["path_lbl"].setText(short)
                    row["path_lbl"].setToolTip(pkg_path)
                    row["path_lbl"].setStyleSheet(
                        f"color:{c['accent_blue']};font-size:10px;text-decoration:underline;")
                    row["path_lbl"].mousePressEvent = (
                        lambda e, p=pkg_path: self._open_folder(p))
            else:
                row["path_lbl"].setText("")
                row["path_lbl"].mousePressEvent = lambda e: None

        # Меняем кнопку
        btn = row["btn"]
        btn.setEnabled(True)
        try: btn.clicked.disconnect()
        except Exception: pass

        if now_inst:
            btn.setText("🗑 Удалить")
            btn.setStyleSheet(
                "QPushButton{background:#3a1a1a;color:#f44336;border:none;"
                "border-radius:5px;font-size:11px;padding:0 10px;}"
                "QPushButton:hover{background:#5a2020;}"
                "QPushButton:disabled{background:#1a1a1a;color:#555;}")
            btn.clicked.connect(lambda checked, pn=pip_name: self._uninstall_by_name(pn))
        else:
            btn.setText("⬇ Установить")
            btn.setStyleSheet(
                f"QPushButton{{background:{c['accent_blue']};color:#fff;border:none;"
                f"border-radius:5px;font-size:11px;padding:0 10px;}}"
                f"QPushButton:hover{{background:{c['accent_blue']}cc;}}"
                f"QPushButton:disabled{{background:#1a2a3a;color:#555;}}")
            btn.clicked.connect(lambda checked, pn=pip_name: self._install_by_name(pn))

        btn.repaint()
        row["status_lbl"].repaint()

    def _show_pip_log(self, pip_name: str, success: bool, output: str):
        """Показывает диалог с полным выводом pip."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel
        c = get_colors(self._theme)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"pip {'install' if not success else 'output'} — {pip_name}")
        dlg.setMinimumSize(560, 400)
        dlg.setStyleSheet(f"QDialog{{background:{c['bg_panel']};color:{c['text']};}}")

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        status_text = "❌ Ошибка установки" if not success else "✅ Успешно"
        lbl = QLabel(f"{status_text} — {pip_name}")
        lbl.setStyleSheet(
            f"color:{'#f44336' if not success else '#4caf50'};"
            "font-size:13px;font-weight:600;")
        lay.addWidget(lbl)

        hint = QLabel("Скопируй и запусти команду вручную в терминале:")
        hint.setStyleSheet(f"color:{c['text_muted']};font-size:11px;")
        lay.addWidget(hint)

        cmd_lbl = QLabel(f"pip install {pip_name}")
        cmd_lbl.setStyleSheet(
            f"color:{c['accent_blue']};font-size:12px;font-weight:600;"
            f"background:{c['bg_input']};border-radius:5px;padding:6px 10px;")
        cmd_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(cmd_lbl)

        log = QTextEdit()
        log.setReadOnly(True)
        log.setPlainText(output or "(нет вывода)")
        log.setStyleSheet(
            f"QTextEdit{{background:#0d1117;color:#e6edf3;"
            f"border:1px solid {c['border']};border-radius:6px;"
            f"font-family:Consolas,monospace;font-size:11px;padding:8px;}}")
        lay.addWidget(log, stretch=1)

        from PyQt6.QtWidgets import QHBoxLayout
        btn_row = QHBoxLayout()
        btn_copy = QPushButton("📋  Скопировать лог")
        btn_copy.setStyleSheet(
            f"QPushButton{{background:{c['bg_input']};color:{c['text']};"
            f"border:1px solid {c['border']};border-radius:6px;padding:6px 14px;}}"
            f"QPushButton:hover{{background:{c['bg_hover']};}}")
        btn_copy.clicked.connect(
            lambda: __import__("PyQt6.QtWidgets", fromlist=["QApplication"])
            .QApplication.clipboard().setText(output))
        btn_row.addWidget(btn_copy)
        btn_row.addStretch()
        btn_close = QPushButton("Закрыть")
        btn_close.setStyleSheet(
            f"QPushButton{{background:{c['accent_blue']};color:#fff;"
            f"border:none;border-radius:6px;padding:6px 18px;}}"
            f"QPushButton:hover{{background:{c['accent_blue']}cc;}}")
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)

        dlg.exec()

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
