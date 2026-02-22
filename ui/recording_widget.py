import time
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter

from core.recorder import Recorder, get_audio_path
from core.transcriber import Transcriber
from core.summarizer import Summarizer
import core.database as db

# ВАЖНО: PhotoOcrDialog импортируется ЛЕНИВО внутри метода _open_photo_ocr,
# чтобы ошибки в photo_ocr/tesseract_langs НЕ ломали запись звука.


class LevelMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(14)
        self._level = self._peak = 0.0
        self._peak_timer = 0

    def set_level(self, level: float):
        self._level = min(level * 5, 1.0)
        if self._level >= self._peak:
            self._peak = self._level; self._peak_timer = 30
        else:
            self._peak_timer = max(0, self._peak_timer - 1)
            if self._peak_timer == 0:
                self._peak = max(self._peak - 0.02, self._level)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1e1e1e")); p.drawRoundedRect(0, 0, w, h, 4, 4)
        filled = int(w * self._level)
        if filled > 0:
            ge, ye = int(w*0.7), int(w*0.9)
            c = "#4caf50" if filled <= ge else "#ffb300" if filled <= ye else "#f44336"
            p.setBrush(QColor(c)); p.drawRoundedRect(0, 0, filled, h, 4, 4)
        pk = int(w * self._peak)
        if pk > 2:
            p.setBrush(QColor("#ffffff")); p.drawRect(pk-2, 0, 2, h)


STATE_IDLE        = "idle"
STATE_RECORDING   = "recording"
STATE_TRANSCRIBING= "transcribing"
STATE_SUMMARIZING = "summarizing"
STATE_DONE        = "done"


class RecordingWidget(QWidget):
    lesson_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state        = STATE_IDLE
        self._start_time   = None
        self._lesson_id    = None
        self._audio_path   = None
        self._recorder     = None
        self._transcriber  = None
        self._summarizer   = None
        self._photo_text   = ""   # OCR-текст с фотографий

        self._timer = QTimer()
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(24); layout.setContentsMargins(40,40,40,40)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(QLabel("Запись урока",
            styleSheet="font-size:22px;font-weight:bold;color:#e0e0e0;"))

        center = QHBoxLayout(); center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bc = QVBoxLayout(); bc.setAlignment(Qt.AlignmentFlag.AlignCenter); bc.setSpacing(16)

        self.record_btn = QPushButton("⏺  Начать запись")
        self.record_btn.setFixedSize(220, 64)
        self.record_btn.setStyleSheet(self._rec_style(False))
        self.record_btn.clicked.connect(self._toggle)
        bc.addWidget(self.record_btn)

        # Кнопка фото — lazy import PhotoOcrDialog
        self.photo_btn = QPushButton("📷  Добавить фото")
        self.photo_btn.setFixedSize(220, 36)
        self.photo_btn.setStyleSheet("""
            QPushButton{background:#2a5298;color:white;border:none;border-radius:8px;font-size:13px;}
            QPushButton:hover{background:#3a6fd8;}
            QPushButton:disabled{background:#1a2a4a;color:#555;}
        """)
        self.photo_btn.clicked.connect(self._open_photo_ocr)
        bc.addWidget(self.photo_btn)

        self.photo_lbl = QLabel("")
        self.photo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_lbl.setStyleSheet("color:#4a9eff;font-size:11px;")
        bc.addWidget(self.photo_lbl)

        self.timer_label = QLabel("00:00:00")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setStyleSheet("font-size:36px;font-family:monospace;color:#c0c0c0;")
        bc.addWidget(self.timer_label)

        self.level_meter = LevelMeter(); self.level_meter.setFixedWidth(220)
        bc.addWidget(self.level_meter)

        self.source_label = QLabel("")
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_label.setStyleSheet("color:#888;font-size:12px;")
        bc.addWidget(self.source_label)

        center.addLayout(bc); layout.addLayout(center)

        self.status_bar = QProgressBar()
        self.status_bar.setRange(0, 0); self.status_bar.setVisible(False)
        self.status_bar.setFixedHeight(6)
        self.status_bar.setStyleSheet("QProgressBar{border:none;background:#2a2a2a;border-radius:3px;}QProgressBar::chunk{background:#4a9eff;border-radius:3px;}")
        layout.addWidget(self.status_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#888;font-size:13px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setStyleSheet("color:#2a2a2a;")
        layout.addWidget(sep)

        layout.addWidget(QLabel("Лог / Транскрипция", styleSheet="color:#888;font-size:12px;"))

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText("Здесь будут появляться распознанные фрагменты…")
        self.log_area.setStyleSheet("""
            QTextEdit{background:#1a1a1a;color:#b0b0b0;border:1px solid #2a2a2a;
                      border-radius:8px;font-size:13px;padding:8px;}
        """)
        self.log_area.setMinimumHeight(180)
        layout.addWidget(self.log_area)

    # ── Управление записью ────────────────────────────────────────────────

    def _toggle(self):
        if self._state == STATE_IDLE:
            self._start_recording()
        elif self._state == STATE_RECORDING:
            self._stop_recording()

    def _open_photo_ocr(self):
        """Lazy import — НЕ ломает запись если photo_ocr недоступен."""
        try:
            from core.photo_ocr import PhotoOcrDialog
        except Exception as e:
            self._log(f"⚠️ Модуль фото недоступен: {e}")
            return
        dlg = PhotoOcrDialog(self)
        if dlg.exec() == PhotoOcrDialog.DialogCode.Accepted:
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

    def _start_recording(self):
        from ui.settings_widget import load_settings
        settings = load_settings()

        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        self._lesson_id = db.create_lesson(f"Урок {now}", "")
        audio_path = str(get_audio_path(self._lesson_id))
        self._audio_path = audio_path
        db.update_lesson(self._lesson_id, audio_path=audio_path)

        src = {"mic": "🎙 Микрофон", "system": "🖥 Системный звук",
               "both": "🎙+🖥 Микрофон + Системный звук"}
        self.source_label.setText(src.get(settings["audio_source"], ""))

        self._recorder = Recorder(settings["audio_source"], audio_path)
        self._recorder.level_updated.connect(self.level_meter.set_level)
        self._recorder.error_occurred.connect(self._on_error)
        self._recorder.finished_recording.connect(self._on_recording_done)
        self._recorder.start()

        self._state = STATE_RECORDING
        self._start_time = time.time()
        self._timer.start()
        self.log_area.clear()
        self.photo_btn.setEnabled(False)
        self.record_btn.setText("⏹  Остановить")
        self.record_btn.setStyleSheet(self._rec_style(True))
        self._log("Запись начата…")

    def _stop_recording(self):
        if self._recorder:
            self._recorder.stop()
        self._timer.stop()
        self._state = STATE_TRANSCRIBING
        self.record_btn.setEnabled(False)
        self.record_btn.setText("Обработка…")
        elapsed = int(time.time() - self._start_time)
        db.update_lesson(self._lesson_id, duration_seconds=elapsed, status="transcribing")
        self._log("Запись остановлена. Начинаю транскрипцию…")
        self.status_bar.setVisible(True)

    def _on_recording_done(self, path: str):
        from ui.settings_widget import load_settings
        settings = load_settings()
        self._transcriber = Transcriber(
            path, settings["whisper_model"], settings.get("language", "auto"))
        self._transcriber.progress.connect(self._log)
        self._transcriber.finished.connect(self._on_transcription_done)
        self._transcriber.error_occurred.connect(self._on_error)
        self._transcriber.start()
        self.status_label.setText("Транскрибирую речь… (первый раз модель грузится ~30сек)")

    def _on_transcription_done(self, text: str):
        self._transcript = text
        db.update_lesson(self._lesson_id, transcript=text, status="summarizing")
        self._log("\n── Транскрипция готова ──\n")
        self._state = STATE_SUMMARIZING
        self.status_label.setText("Составляю конспект…")

        combined = text
        if self._photo_text:
            combined = (f"{text}\n\n--- Текст с фотографий ---\n{self._photo_text}")
            self._log("📷 Текст с фото добавлен к транскрипции")

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
        self.status_label.setText("✅ Готово! Конспект сохранён в истории.")
        self._log("\n✅ Конспект составлен и сохранён!")
        self.record_btn.setEnabled(True)
        self.record_btn.setText("⏺  Начать запись")
        self.record_btn.setStyleSheet(self._rec_style(False))
        self.photo_btn.setEnabled(True)
        self._state = STATE_IDLE
        self.source_label.setText("")
        self._photo_text = ""; self.photo_lbl.setText("")
        self.lesson_saved.emit()

    def _on_error(self, msg: str):
        self._log(f"\n❌ Ошибка: {msg}")
        self.status_label.setText(f"Ошибка: {msg[:100]}")
        self.status_bar.setVisible(False)
        self.record_btn.setEnabled(True)
        self.record_btn.setText("⏺  Начать запись")
        self.record_btn.setStyleSheet(self._rec_style(False))
        self.photo_btn.setEnabled(True)
        self._state = STATE_IDLE

    def _tick(self):
        e = int(time.time() - self._start_time)
        self.timer_label.setText(f"{e//3600:02d}:{(e%3600)//60:02d}:{e%60:02d}")

    def _log(self, msg: str):
        self.log_area.append(msg)

    @staticmethod
    def _rec_style(active: bool) -> str:
        bg = "#c0392b" if active else "#27ae60"
        hv = "#e74c3c" if active else "#2ecc71"
        return (f"QPushButton{{background:{bg};color:white;border:none;"
                f"border-radius:32px;font-size:15px;font-weight:bold;}}"
                f"QPushButton:hover{{background:{hv};}}")
