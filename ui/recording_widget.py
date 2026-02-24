import time
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QFrame, QDialog,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QFont

from core.recorder import Recorder, get_audio_path
from core.transcriber import Transcriber
from core.summarizer import Summarizer
import core.database as db
from ui.theme import get_colors

# ВАЖНО: PhotoOcrDialog импортируется ЛЕНИВО внутри метода _open_photo_ocr,
# чтобы ошибки в photo_ocr/tesseract_langs НЕ ломали запись звука.


class LevelMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self._level = self._peak = 0.0
        self._peak_timer = 0
        self._theme = "dark"

    def set_level(self, level: float):
        self._level = min(level * 5, 1.0)
        if self._level >= self._peak:
            self._peak = self._level
            self._peak_timer = 30
        else:
            self._peak_timer = max(0, self._peak_timer - 1)
            if self._peak_timer == 0:
                self._peak = max(self._peak - 0.02, self._level)
        self.update()

    def set_theme(self, theme: str):
        self._theme = theme
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        bg = "#21262d" if self._theme == "dark" else "#e6edf3"
        p.setBrush(QColor(bg))
        p.drawRoundedRect(0, 0, w, h, 4, 4)
        filled = int(w * self._level)
        if filled > 0:
            ge, ye = int(w * 0.7), int(w * 0.9)
            c = "#3fb950" if filled <= ge else "#d29922" if filled <= ye else "#f85149"
            p.setBrush(QColor(c))
            p.drawRoundedRect(0, 0, filled, h, 4, 4)
        pk = int(w * self._peak)
        if pk > 2:
            p.setBrush(QColor("#e6edf3" if self._theme == "dark" else "#1f2328"))
            p.drawRect(pk - 2, 0, 2, h)


STATE_IDLE        = "idle"
STATE_RECORDING   = "recording"
STATE_TRANSCRIBING = "transcribing"
STATE_SUMMARIZING = "summarizing"
STATE_DONE        = "done"


def _code_style_text(mode: str) -> str:
    """Возвращает QTextEdit stylesheet в стиле кодового редактора."""
    if mode == "dark":
        return """
            QTextEdit {
                background: #0d1117;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 8px;
                font-family: 'Cascadia Code', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
                font-size: 13px;
                padding: 12px;
                line-height: 1.5;
                selection-background-color: #1f4280;
            }
        """
    else:
        return """
            QTextEdit {
                background: #f6f8fa;
                color: #1f2328;
                border: 1px solid #d0d7de;
                border-radius: 8px;
                font-family: 'Cascadia Code', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
                font-size: 13px;
                padding: 12px;
                line-height: 1.5;
                selection-background-color: #ddf4ff;
            }
        """


class RecordingWidget(QWidget):
    lesson_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme     = "dark"
        self._state     = STATE_IDLE
        self._start_time   = None
        self._lesson_id    = None
        self._audio_path   = None
        self._recorder     = None
        self._transcriber  = None
        self._summarizer   = None
        self._photo_text   = ""
        self._transcript   = ""

        self._timer = QTimer()
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._build_ui()

    def apply_theme(self, theme: str):
        self._theme = theme
        c = get_colors(theme)
        self.log_area.setStyleSheet(_code_style_text(theme))
        self.level_meter.set_theme(theme)
        self._update_status_label_style()

    def _update_status_label_style(self):
        c = get_colors(self._theme)
        self.status_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 13px;")

    def _build_ui(self):
        c = get_colors(self._theme)
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("recHeader")
        header.setFixedHeight(56)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(28, 0, 28, 0)

        title_lbl = QLabel("Запись урока")
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {c['text']};")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        self.source_label = QLabel("")
        self.source_label.setStyleSheet(f"""
            color: {c['accent_green']};
            font-size: 12px;
            background: transparent;
            padding: 3px 8px;
            border: 1px solid {c['accent_green']};
            border-radius: 10px;
        """)
        self.source_label.setVisible(False)
        header_layout.addWidget(self.source_label)

        layout.addWidget(header)

        # ── Header separator ──────────────────────────────────────────────
        hdr_sep = QFrame()
        hdr_sep.setFrameShape(QFrame.Shape.HLine)
        hdr_sep.setStyleSheet(f"color: {c['border']};")
        layout.addWidget(hdr_sep)

        # ── Main content area ─────────────────────────────────────────────
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(28, 28, 28, 28)

        # ── Record controls ───────────────────────────────────────────────
        controls_card = QWidget()
        controls_card.setObjectName("controlsCard")
        controls_card.setStyleSheet(f"""
            QWidget#controlsCard {{
                background: {c['bg_panel']};
                border: 1px solid {c['border']};
                border-radius: 12px;
            }}
        """)
        controls_layout = QVBoxLayout(controls_card)
        controls_layout.setContentsMargins(24, 20, 24, 20)
        controls_layout.setSpacing(16)

        # Top row: record btn + timer
        top_row = QHBoxLayout()
        top_row.setSpacing(20)
        top_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.record_btn = QPushButton("⏺  Начать запись")
        self.record_btn.setFixedSize(200, 52)
        self.record_btn.setStyleSheet(self._rec_style(False))
        self.record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.record_btn.clicked.connect(self._toggle)
        top_row.addWidget(self.record_btn)

        timer_container = QVBoxLayout()
        timer_container.setSpacing(2)
        timer_container.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.timer_label = QLabel("00:00:00")
        self.timer_label.setStyleSheet(f"""
            font-size: 32px;
            font-family: 'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace;
            font-weight: 300;
            color: {c['text']};
            background: transparent;
            letter-spacing: 2px;
        """)
        timer_container.addWidget(self.timer_label)

        self.level_meter = LevelMeter()
        self.level_meter.setFixedWidth(200)
        timer_container.addWidget(self.level_meter)

        top_row.addLayout(timer_container)
        top_row.addStretch()

        # Photo btn
        self.photo_btn = QPushButton("📷  Добавить фото")
        self.photo_btn.setFixedHeight(40)
        self.photo_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c.get('bg_card', c['bg_input'])};
                color: {c['accent_blue']};
                border: 1px solid {c['accent_blue']};
                border-radius: 8px;
                font-size: 13px;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background: {c['bg_selected']};
                color: {c['accent_blue']};
            }}
            QPushButton:disabled {{
                border-color: {c['border']};
                color: {c['text_dim']};
            }}
        """)
        self.photo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.photo_btn.clicked.connect(self._open_photo_ocr)
        top_row.addWidget(self.photo_btn)

        controls_layout.addLayout(top_row)

        self.photo_lbl = QLabel("")
        self.photo_lbl.setStyleSheet(f"color: {c['accent_blue']}; font-size: 11px;")
        controls_layout.addWidget(self.photo_lbl)

        # Progress bar
        self.status_bar = QProgressBar()
        self.status_bar.setRange(0, 0)
        self.status_bar.setVisible(False)
        self.status_bar.setFixedHeight(3)
        self.status_bar.setStyleSheet(f"""
            QProgressBar {{ border: none; background: {c['border']}; border-radius: 2px; }}
            QProgressBar::chunk {{ background: {c['accent_blue']}; border-radius: 2px; }}
        """)
        controls_layout.addWidget(self.status_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 13px;")
        self.status_label.setWordWrap(True)
        controls_layout.addWidget(self.status_label)

        content_layout.addWidget(controls_card)

        # ── Log / Transcript area ─────────────────────────────────────────
        log_header = QHBoxLayout()
        log_title = QLabel("// Лог транскрипции")
        log_title.setStyleSheet(f"color: {c['comment']}; font-size: 12px; font-family: 'Cascadia Code', 'Consolas', monospace;")
        log_header.addWidget(log_title)
        log_header.addStretch()

        self.clear_btn = QPushButton("Очистить")
        self.clear_btn.setFixedHeight(24)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {c['text_muted']};
                border: 1px solid {c['border']}; border-radius: 4px;
                font-size: 11px; padding: 0 10px;
            }}
            QPushButton:hover {{ color: {c['text']}; border-color: {c['text_muted']}; }}
        """)
        self.clear_btn.clicked.connect(lambda: self.log_area.clear())
        log_header.addWidget(self.clear_btn)
        content_layout.addLayout(log_header)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText("// Здесь будут появляться распознанные фрагменты…")
        self.log_area.setStyleSheet(_code_style_text(self._theme))
        self.log_area.setMinimumHeight(200)
        content_layout.addWidget(self.log_area)

        layout.addWidget(content)

    # ── Управление записью ────────────────────────────────────────────────

    def _toggle(self):
        if self._state == STATE_IDLE:
            self._start_recording()
        elif self._state == STATE_RECORDING:
            self._stop_recording()

    def _open_photo_ocr(self):
        """
        ✅ ИСПРАВЛЕНО: весь вызов обёрнут в try/except,
        включая создание диалога — ранее вылетал без перехвата ошибки.
        """
        try:
            from core.photo_ocr import PhotoOcrDialog
            dlg = PhotoOcrDialog(self)
        except Exception as e:
            self._log(f"⚠️ Не удалось открыть диалог фото: {e}")
            return

        try:
            # ✅ ИСПРАВЛЕНО: QDialog.DialogCode.Accepted, не PhotoOcrDialog.DialogCode
            if dlg.exec() == QDialog.DialogCode.Accepted:
                text = dlg.get_ocr_text()
                if text:
                    self._photo_text = ((self._photo_text + "\n\n" + text)
                                        if self._photo_text else text)
                    cnt = self._photo_text.count("[Фото ")
                    self.photo_lbl.setText(
                        f"📷 {cnt} фото · {len(self._photo_text)} симв. — будут в конспекте")
                    self._log(f"\n📷 Добавлен текст с {cnt} фото ({len(self._photo_text)} симв.)")
                else:
                    self.photo_lbl.setText("📷 Текст не распознан")
        except Exception as e:
            self._log(f"⚠️ Ошибка при OCR: {e}")

    def _start_recording(self):
        from ui.settings_widget import load_settings
        settings = load_settings()

        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        self._lesson_id = db.create_lesson(f"Урок {now}", "")
        audio_path = str(get_audio_path(self._lesson_id))
        self._audio_path = audio_path
        db.update_lesson(self._lesson_id, audio_path=audio_path)

        src_labels = {
            "mic": "🎙 Микрофон",
            "system": "🖥 Системный звук",
            "both": "🎙 + 🖥 Микрофон + Системный"
        }
        source_text = src_labels.get(settings["audio_source"], "")
        self.source_label.setText(source_text)
        self.source_label.setVisible(bool(source_text))

        mic_device_index = settings.get("mic_device_index", None)

        self._recorder = Recorder(settings["audio_source"], audio_path, mic_device_index)
        self._recorder.level_updated.connect(self.level_meter.set_level)
        self._recorder.error_occurred.connect(self._on_error)
        self._recorder.finished_recording.connect(self._on_recording_done)
        self._recorder.start()

        self._state = STATE_RECORDING
        self._start_time = time.time()
        self._timer.start()
        # НЕ очищаем _photo_text здесь — текст с фото добавляется ДО записи
        self.log_area.clear()
        self.photo_btn.setEnabled(False)
        self.record_btn.setText("⏹  Остановить")
        self.record_btn.setStyleSheet(self._rec_style(True))
        self._start_pulse()
        self._log_header("Запись начата")
        self._log_info(f"Источник: {source_text}")

    def _stop_recording(self):
        self._stop_pulse()
        if self._recorder:
            self._recorder.stop()
        self._timer.stop()
        self._state = STATE_TRANSCRIBING
        self.record_btn.setEnabled(False)
        self.record_btn.setText("Обработка…")
        elapsed = int(time.time() - self._start_time)
        db.update_lesson(self._lesson_id, duration_seconds=elapsed, status="transcribing")
        self._log_separator()
        self._log_header("Транскрипция")
        self._log_info("Запись остановлена, начинаю распознавание речи…")
        self.status_bar.setVisible(True)
        self.source_label.setVisible(False)

    def _on_recording_done(self, path: str):
        from ui.settings_widget import load_settings
        settings = load_settings()
        self._transcriber = Transcriber(
            path, settings["whisper_model"], settings.get("language", "auto"))
        self._transcriber.progress.connect(self._on_transcription_progress)
        self._transcriber.finished.connect(self._on_transcription_done)
        self._transcriber.error_occurred.connect(self._on_error)
        self._transcriber.start()
        self.status_label.setText("Транскрибирую речь… (первый раз модель грузится ~30 сек)")

    def _on_transcription_progress(self, text: str):
        """Показываем каждый распознанный фрагмент в реальном времени."""
        self._log(text)

    def _on_transcription_done(self, text: str):
        self._transcript = text
        db.update_lesson(self._lesson_id, transcript=text, status="summarizing")

        # ✅ ИСПРАВЛЕНО: показываем полную транскрипцию в логе
        self._log_separator()
        self._log_header("Транскрипция завершена")
        if text:
            self._log(text)
        else:
            self._log_warn("Текст не распознан — возможно тишина в записи")

        self._state = STATE_SUMMARIZING
        self.status_label.setText("Составляю конспект через ИИ…")

        combined = text
        if self._photo_text:
            combined = (f"{text}\n\n--- Текст с фотографий ---\n{self._photo_text}")
            self._log_separator()
            self._log_info("📷 Текст с фото добавлен к транскрипции")

        from ui.settings_widget import load_settings
        settings = load_settings()
        self._summarizer = Summarizer(
            combined,
            provider=settings.get("ai_provider", "deepseek"),
            api_key=settings.get("ai_api_key", ""),
            model=settings.get("ai_model", ""),
            base_url=settings.get("ai_custom_url", ""),
        )
        self._summarizer.progress.connect(self._on_summary_progress)
        self._summarizer.finished.connect(self._on_summary_done)
        self._summarizer.error_occurred.connect(self._on_error)
        self._summarizer.start()

    def _on_summary_progress(self, text: str):
        self.status_label.setText(text[:120] + ("…" if len(text) > 120 else ""))

    def _on_summary_done(self, notes: str):
        db.update_lesson(self._lesson_id, notes=notes, status="done")
        self._state = STATE_DONE
        self.status_bar.setVisible(False)
        self.status_label.setText("✅ Конспект сохранён в истории.")
        self._log_separator()
        self._log_header("Конспект готов")
        self._log_info("✅ Сохранён в разделе «История»")
        self.record_btn.setEnabled(True)
        self.record_btn.setText("⏺  Начать запись")
        self.record_btn.setStyleSheet(self._rec_style(False))
        self.photo_btn.setEnabled(True)
        self._state = STATE_IDLE
        self._photo_text = ""
        self.photo_lbl.setText("")
        self.lesson_saved.emit()

    def _on_error(self, msg: str):
        self._stop_pulse()
        self._log_separator()
        self._log_error(f"ОШИБКА: {msg}")
        self.status_label.setText(f"Ошибка: {msg[:100]}")
        self.status_bar.setVisible(False)
        self.record_btn.setEnabled(True)
        self.record_btn.setText("⏺  Начать запись")
        self.record_btn.setStyleSheet(self._rec_style(False))
        self.photo_btn.setEnabled(True)
        self.source_label.setVisible(False)
        self._state = STATE_IDLE

    def _tick(self):
        e = int(time.time() - self._start_time)
        self.timer_label.setText(f"{e // 3600:02d}:{(e % 3600) // 60:02d}:{e % 60:02d}")

    # ── Log helpers — code-editor style output ────────────────────────────

    def _log(self, msg: str):
        c = get_colors(self._theme)
        self.log_area.append(
            f'<span style="color:{c["text"]};">{self._esc(msg)}</span>'
        )

    def _log_header(self, msg: str):
        c = get_colors(self._theme)
        self.log_area.append(
            f'<span style="color:{c["function"]};font-weight:bold;"># {self._esc(msg)}</span>'
        )

    def _log_info(self, msg: str):
        c = get_colors(self._theme)
        self.log_area.append(
            f'<span style="color:{c["comment"]};">// {self._esc(msg)}</span>'
        )

    def _log_warn(self, msg: str):
        c = get_colors(self._theme)
        self.log_area.append(
            f'<span style="color:{c["accent_orange"]};">⚠  {self._esc(msg)}</span>'
        )

    def _log_error(self, msg: str):
        c = get_colors(self._theme)
        self.log_area.append(
            f'<span style="color:{c["accent_red"]};">✗  {self._esc(msg)}</span>'
        )

    def _log_separator(self):
        c = get_colors(self._theme)
        line = "─" * 60
        self.log_area.append(
            f'<span style="color:{c["border"]};">{line}</span>'
        )

    @staticmethod
    def _esc(text: str) -> str:
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>"))

    # ── Styles ────────────────────────────────────────────────────────────

    def _start_pulse(self):
        """Пульсирующий эффект кнопки во время записи."""
        if not hasattr(self, "_pulse_anim"):
            self._pulse_anim = QPropertyAnimation(self.record_btn, b"maximumWidth", self)
        anim = self._pulse_anim
        anim.setDuration(900)
        anim.setStartValue(200)
        anim.setKeyValueAt(0.5, 208)
        anim.setEndValue(200)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.setLoopCount(-1)
        anim.start()

    def _stop_pulse(self):
        if hasattr(self, "_pulse_anim"):
            self._pulse_anim.stop()
            self.record_btn.setMaximumWidth(16777215)

    def _rec_style(self, active: bool) -> str:
        c = get_colors(self._theme)
        if active:
            bg = "qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #da3633,stop:1 #f85149)"
            hv = "#f85149"
        else:
            bg = "qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #238636,stop:1 #2ea043)"
            hv = "#2ea043"
        return f"""
            QPushButton {{
                background: {bg};
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 600;
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{ background: {hv}; }}
            QPushButton:pressed {{ padding-top: 2px; }}
            QPushButton:disabled {{
                background: {c['border']};
                color: {c['text_dim']};
            }}
        """
