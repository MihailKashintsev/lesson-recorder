from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QGroupBox, QFormLayout,
    QMessageBox, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt
import json
from pathlib import Path

from core.summarizer import PROVIDERS, get_provider_config

SETTINGS_PATH = Path.home() / ".lesson_recorder" / "settings.json"

DEFAULTS = {
    "audio_source": "both",
    "whisper_model": "tiny",
    "language": "auto",
    "ai_provider": "groq",
    "ai_api_key": "",
    "ai_model": "llama-3.3-70b-versatile",
    "ai_custom_url": "",
    "ai_custom_model": "",
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self._build_ui()

    def _build_ui(self):
        # Scroll area для маленьких экранов
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
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("Настройки")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(title)

        # ── Аудио ─────────────────────────────────────────────────────────
        audio_group = QGroupBox("Запись аудио")
        audio_group.setStyleSheet(self._group_style())
        audio_form = QFormLayout(audio_group)
        audio_form.setSpacing(10)

        self.combo_source = QComboBox()
        self.combo_source.addItems(["Микрофон", "Системный звук", "Оба источника"])
        src_map = {"mic": 0, "system": 1, "both": 2}
        self.combo_source.setCurrentIndex(src_map.get(self.settings["audio_source"], 2))
        audio_form.addRow("Источник:", self.combo_source)
        layout.addWidget(audio_group)

        # ── Whisper ───────────────────────────────────────────────────────
        whisper_group = QGroupBox("Транскрипция (Whisper — работает офлайн)")
        whisper_group.setStyleSheet(self._group_style())
        whisper_form = QFormLayout(whisper_group)
        whisper_form.setSpacing(10)

        self.combo_whisper_model = QComboBox()
        models = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
        self.combo_whisper_model.addItems(models)
        if self.settings["whisper_model"] in models:
            self.combo_whisper_model.setCurrentIndex(models.index(self.settings["whisper_model"]))
        whisper_form.addRow("Модель:", self.combo_whisper_model)

        self.combo_lang = QComboBox()
        langs = {"auto": "Авто-определение", "ru": "Русский", "en": "English",
                 "uk": "Українська", "de": "Deutsch", "fr": "Français",
                 "es": "Español", "zh": "中文"}
        for code, name in langs.items():
            self.combo_lang.addItem(name, code)
        for i in range(self.combo_lang.count()):
            if self.combo_lang.itemData(i) == self.settings.get("language", "auto"):
                self.combo_lang.setCurrentIndex(i)
                break
        whisper_form.addRow("Язык:", self.combo_lang)

        note = QLabel("tiny — быстро  •  base — баланс  •  small/medium/large — медленнее, лучше")
        note.setStyleSheet("color: #666; font-size: 11px;")
        whisper_form.addRow("", note)
        layout.addWidget(whisper_group)

        # ── ИИ провайдер ──────────────────────────────────────────────────
        ai_group = QGroupBox("ИИ для конспектов")
        ai_group.setStyleSheet(self._group_style())
        ai_layout = QVBoxLayout(ai_group)
        ai_layout.setSpacing(14)

        # Выбор провайдера
        provider_row = QHBoxLayout()
        provider_label = QLabel("Провайдер:")
        provider_label.setFixedWidth(110)
        provider_label.setStyleSheet("color: #c0c0c0;")

        self.combo_provider = QComboBox()
        for pid, pcfg in PROVIDERS.items():
            self.combo_provider.addItem(pcfg["name"], pid)
        current_provider = self.settings.get("ai_provider", "groq")
        for i in range(self.combo_provider.count()):
            if self.combo_provider.itemData(i) == current_provider:
                self.combo_provider.setCurrentIndex(i)
                break
        self.combo_provider.currentIndexChanged.connect(self._on_provider_changed)

        provider_row.addWidget(provider_label)
        provider_row.addWidget(self.combo_provider)
        ai_layout.addLayout(provider_row)

        # Инфо о провайдере
        self.provider_info = QLabel("")
        self.provider_info.setStyleSheet(
            "color: #4caf50; font-size: 11px; padding: 4px 8px; "
            "background: #1a2a1a; border-radius: 4px;"
        )
        self.provider_info.setWordWrap(True)
        ai_layout.addWidget(self.provider_info)

        # API ключ
        key_row = QHBoxLayout()
        key_label = QLabel("API ключ:")
        key_label.setFixedWidth(110)
        key_label.setStyleSheet("color: #c0c0c0;")

        self.edit_api_key = QLineEdit(self.settings.get("ai_api_key", ""))
        self.edit_api_key.setEchoMode(QLineEdit.EchoMode.Password)

        self.toggle_key_btn = QPushButton("👁")
        self.toggle_key_btn.setFixedSize(32, 32)
        self.toggle_key_btn.setCheckable(True)
        self.toggle_key_btn.setStyleSheet(self._icon_btn_style())
        self.toggle_key_btn.toggled.connect(
            lambda on: self.edit_api_key.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )

        key_row.addWidget(key_label)
        key_row.addWidget(self.edit_api_key)
        key_row.addWidget(self.toggle_key_btn)
        ai_layout.addLayout(key_row)

        # Модель
        model_row = QHBoxLayout()
        model_label = QLabel("Модель:")
        model_label.setFixedWidth(110)
        model_label.setStyleSheet("color: #c0c0c0;")

        self.combo_ai_model = QComboBox()
        self.edit_custom_model = QLineEdit()
        self.edit_custom_model.setPlaceholderText("Введи название модели вручную")
        self.edit_custom_model.setVisible(False)

        model_row.addWidget(model_label)
        model_row.addWidget(self.combo_ai_model)
        model_row.addWidget(self.edit_custom_model)
        ai_layout.addLayout(model_row)

        # Кастомный URL (только для custom провайдера)
        url_row = QHBoxLayout()
        self.url_label = QLabel("URL API:")
        self.url_label.setFixedWidth(110)
        self.url_label.setStyleSheet("color: #c0c0c0;")
        self.edit_custom_url = QLineEdit(self.settings.get("ai_custom_url", ""))
        self.edit_custom_url.setPlaceholderText("http://localhost:1234/v1")
        url_row.addWidget(self.url_label)
        url_row.addWidget(self.edit_custom_url)
        ai_layout.addLayout(url_row)

        # Кнопки: проверить + ссылка регистрации
        btn_row = QHBoxLayout()
        self.test_btn = QPushButton("🔌 Проверить соединение")
        self.test_btn.setStyleSheet(self._btn_style())
        self.test_btn.clicked.connect(self._test_connection)

        self.signup_btn = QPushButton("🌐 Получить ключ →")
        self.signup_btn.setStyleSheet(self._link_btn_style())
        self.signup_btn.clicked.connect(self._open_signup)

        btn_row.addWidget(self.test_btn)
        btn_row.addWidget(self.signup_btn)
        btn_row.addStretch()
        ai_layout.addLayout(btn_row)

        layout.addWidget(ai_group)

        # ── Сохранить ─────────────────────────────────────────────────────
        save_btn = QPushButton("💾  Сохранить настройки")
        save_btn.clicked.connect(self._save)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #4a9eff; color: white; border: none;
                border-radius: 8px; padding: 10px 30px;
                font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background: #5aadff; }
        """)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()

        # Инициализируем под текущий провайдер
        self._on_provider_changed()

    # ── Провайдер изменился ───────────────────────────────────────────────
    def _on_provider_changed(self):
        provider_id = self.combo_provider.currentData()
        cfg = get_provider_config(provider_id)

        # Инфо
        self.provider_info.setText(cfg["free_info"])

        # Placeholder и лейбл для ключа
        is_gigachat = (provider_id == "gigachat")
        key_label_text = "Авторизация:" if is_gigachat else "API ключ:"
        # Находим лейбл ключа в layout (он в key_row)
        self.edit_api_key.setPlaceholderText(cfg["key_hint"])
        # Показываем подсказку специфичную для GigaChat
        if is_gigachat:
            self.provider_info.setText(
                cfg["free_info"] + "\n"
                "Ключ: developers.sber.ru/studio → создай проект → скопируй «Авторизационные данные»"
            )
        else:
            self.provider_info.setText(cfg["free_info"])

        # Модели
        is_custom = provider_id == "custom"
        self.combo_ai_model.setVisible(not is_custom)
        self.edit_custom_model.setVisible(is_custom)
        self.url_label.setVisible(is_custom)
        self.edit_custom_url.setVisible(is_custom)
        self.signup_btn.setVisible(bool(cfg.get("signup_url")))

        if not is_custom:
            self.combo_ai_model.clear()
            for m in cfg["models"]:
                self.combo_ai_model.addItem(m, m)
            # Восстанавливаем сохранённую модель если подходит
            saved_model = self.settings.get("ai_model", cfg["default_model"])
            for i in range(self.combo_ai_model.count()):
                if self.combo_ai_model.itemData(i) == saved_model:
                    self.combo_ai_model.setCurrentIndex(i)
                    break
        else:
            self.edit_custom_model.setText(self.settings.get("ai_custom_model", ""))

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

        # GigaChat: OAuth токен
        if provider_id == "gigachat":
            if not key:
                QMessageBox.warning(self, "Нет ключа",
                    "Укажи авторизационные данные GigaChat.")
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
                    f"Не удалось получить токен:\n{e}\n\n"
                    "Проверь авторизационные данные на developers.sber.ru/studio")
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
                    f"Модель «{model}» не найдена.\nПроверь название.")
            else:
                QMessageBox.warning(self, "⚠️ Ошибка",
                    f"Код {r.status_code}:\n{r.text[:300]}")
        except req.exceptions.ConnectionError:
            QMessageBox.critical(self, "❌ Нет соединения",
                f"Не удалось подключиться к:\n{base_url}")
        except Exception as e:
            QMessageBox.critical(self, "❌ Ошибка", str(e))

    def _open_signup(self):
        import webbrowser
        provider_id = self.combo_provider.currentData()
        url = get_provider_config(provider_id).get("signup_url", "")
        if url:
            webbrowser.open(f"https://{url}")

    # ── Сохранение ────────────────────────────────────────────────────────
    def _save(self):
        provider_id = self.combo_provider.currentData()
        src_keys = ["mic", "system", "both"]
        self.settings.update({
            "audio_source": src_keys[self.combo_source.currentIndex()],
            "whisper_model": self.combo_whisper_model.currentText(),
            "language": self.combo_lang.currentData(),
            "ai_provider": provider_id,
            "ai_api_key": self.edit_api_key.text().strip(),
            "ai_model": self._get_current_model(),
            "ai_custom_url": self.edit_custom_url.text().strip(),
            "ai_custom_model": self.edit_custom_model.text().strip(),
        })
        save_settings(self.settings)
        QMessageBox.information(self, "Сохранено", "Настройки сохранены!")

    def get_settings(self) -> dict:
        return load_settings()

    # ── Стили ─────────────────────────────────────────────────────────────
    @staticmethod
    def _group_style():
        return """
            QGroupBox {
                color: #c0c0c0; font-weight: bold;
                border: 1px solid #2a2a2a; border-radius: 8px;
                margin-top: 8px; padding-top: 14px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; }
        """

    @staticmethod
    def _btn_style():
        return """
            QPushButton {
                background: #2a2a2a; color: #c0c0c0;
                border: 1px solid #444; border-radius: 6px;
                padding: 6px 16px; font-size: 12px;
            }
            QPushButton:hover { background: #333; color: #fff; }
        """

    @staticmethod
    def _link_btn_style():
        return """
            QPushButton {
                background: transparent; color: #4a9eff;
                border: 1px solid #4a9eff; border-radius: 6px;
                padding: 6px 14px; font-size: 12px;
            }
            QPushButton:hover { background: #1a2a3a; }
        """

    @staticmethod
    def _icon_btn_style():
        return """
            QPushButton {
                background: #2a2a2a; border: 1px solid #444;
                border-radius: 6px; font-size: 14px;
            }
            QPushButton:hover { background: #3a3a3a; }
            QPushButton:checked { background: #2a3a4a; }
        """
