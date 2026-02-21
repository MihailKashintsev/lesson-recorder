import time
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QFrame, QInputDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPainter, QPen

from core.recorder import Recorder, get_audio_path
from core.transcriber import Transcriber
from core.summarizer import Summarizer
import core.database as db


class LevelMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(14)
        self._level = 0.0
        self._peak = 0.0
        self._peak_timer = 0

    def set_level(self, level: float):
        self._level = min(level * 5, 1.0)  # boost sensitivity
        if self._level >= self._peak:
            self._peak = self._level
            self._peak_timer = 30
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

        # background
        p.setBrush(QColor("#1e1e1e"))
        p.drawRoundedRect(0, 0, w, h, 4, 4)

        # level bar
        filled = int(w * self._level)
        if filled > 0:
            green_end = int(w * 0.7)
            yellow_end = int(w * 0.9)
            if filled <= green_end:
                color = QColor("#4caf50")
            elif filled <= yellow_end:
                color = QColor("#ffb300")
            else:
                color = QColor("#f44336")
            p.setBrush(color)
            p.drawRoundedRect(0, 0, filled, h, 4, 4)

        # peak marker
        peak_x = int(w * self._peak)
        if peak_x > 2:
            p.setBrush(QColor("#ffffff"))
            p.drawRect(peak_x - 2, 0, 2, h)


STATE_IDLE = "idle"
STATE_RECORDING = "recording"
STATE_TRANSCRIBING = "transcribing"
STATE_SUMMARIZING = "summarizing"
STATE_DONE = "done"


class RecordingWidget(QWidget):
    lesson_saved = pyqtSignal()  # emit to refresh history

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = STATE_IDLE
        self._start_time = None
        self._lesson_id = None
        self._audio_path = None
        self._recorder = None
        self._transcriber = None
        self._summarizer = None
        self._elapsed = 0

        self._timer = QTimer()
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(24)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Title
        title = QLabel("Запись урока")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(title)

        # ── Record button + timer ─────────────────────────────────────────
        center = QHBoxLayout()
        center.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_container = QVBoxLayout()
        btn_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_container.setSpacing(16)

        self.record_btn = QPushButton("⏺  Начать запись")
        self.record_btn.setFixedSize(220, 64)
        self.record_btn.setStyleSheet(self._record_btn_style(False))
        self.record_btn.clicked.connect(self._toggle_recording)
        btn_container.addWidget(self.record_btn)

        self.timer_label = QLabel("00:00:00")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setStyleSheet("font-size: 36px; font-family: monospace; color: #c0c0c0;")
        btn_container.addWidget(self.timer_label)

        self.level_meter = LevelMeter()
        self.level_meter.setFixedWidth(220)
        btn_container.addWidget(self.level_meter)

        self.source_label = QLabel("")
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_label.setStyleSheet("color: #888; font-size: 12px;")
        btn_container.addWidget(self.source_label)

        center.addLayout(btn_container)
        layout.addLayout(center)

        # ── Progress / Status ─────────────────────────────────────────────
        self.status_bar = QProgressBar()
        self.status_bar.setRange(0, 0)
        self.status_bar.setVisible(False)
        self.status_bar.setFixedHeight(6)
        self.status_bar.setStyleSheet("""
            QProgressBar { border: none; background: #2a2a2a; border-radius: 3px; }
            QProgressBar::chunk { background: #4a9eff; border-radius: 3px; }
        """)
        layout.addWidget(self.status_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-size: 13px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # ── Log / Live transcript ─────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a2a2a;")
        layout.addWidget(sep)

        log_label = QLabel("Лог / Транскрипция")
        log_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(log_label)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText("Здесь будут появляться распознанные фрагменты…")
        self.log_area.setStyleSheet("""
            QTextEdit {
                background: #1a1a1a;
                color: #b0b0b0;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                font-size: 13px;
                padding: 8px;
            }
        """)
        self.log_area.setMinimumHeight(180)
        layout.addWidget(self.log_area)

    # ── Controls ──────────────────────────────────────────────────────────
    def _toggle_recording(self):
        if self._state == STATE_IDLE:
            self._start_recording()
        elif self._state == STATE_RECORDING:
            self._stop_recording()

    def _start_recording(self):
        from ui.settings_widget import load_settings
        settings = load_settings()

        # Create lesson in DB
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        self._lesson_id = db.create_lesson(f"Урок {now}", "")
        audio_path = str(get_audio_path(self._lesson_id))
        self._audio_path = audio_path
        db.update_lesson(self._lesson_id, audio_path=audio_path)

        # Source label
        src_names = {"mic": "🎙 Микрофон", "system": "🖥 Системный звук",
                     "both": "🎙+🖥 Микрофон + Системный звук"}
        self.source_label.setText(src_names.get(settings["audio_source"], ""))

        # Start recorder
        self._recorder = Recorder(settings["audio_source"], audio_path)
        self._recorder.level_updated.connect(self.level_meter.set_level)
        self._recorder.error_occurred.connect(self._on_error)
        self._recorder.finished_recording.connect(self._on_recording_done)
        self._recorder.start()

        self._state = STATE_RECORDING
        self._start_time = time.time()
        self._timer.start()
        self.log_area.clear()
        self.record_btn.setText("⏹  Остановить")
        self.record_btn.setStyleSheet(self._record_btn_style(True))
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
            path, settings["whisper_model"], settings.get("language", "auto")
        )
        self._transcriber.progress.connect(self._log)
        self._transcriber.finished.connect(self._on_transcription_done)
        self._transcriber.error_occurred.connect(self._on_error)
        self._transcriber.start()
        self.status_label.setText("Транскрибирую речь…")

    def _on_transcription_done(self, text: str):
        self._transcript = text
        db.update_lesson(self._lesson_id, transcript=text, status="summarizing")
        self._log("\n── Транскрипция готова ──\n")
        self._state = STATE_SUMMARIZING
        self.status_label.setText("Составляю конспект…")

        from ui.settings_widget import load_settings
        settings = load_settings()
        self._summarizer = Summarizer(
            text, settings["ollama_model"], settings["ollama_url"]
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
        self.record_btn.setStyleSheet(self._record_btn_style(False))
        self._state = STATE_IDLE
        self.source_label.setText("")
        self.lesson_saved.emit()

    def _on_error(self, msg: str):
        self._log(f"\n❌ Ошибка: {msg}")
        self.status_label.setText(f"Ошибка: {msg[:100]}")
        self.status_bar.setVisible(False)
        self.record_btn.setEnabled(True)
        self.record_btn.setText("⏺  Начать запись")
        self.record_btn.setStyleSheet(self._record_btn_style(False))
        self._state = STATE_IDLE

    def _tick(self):
        elapsed = int(time.time() - self._start_time)
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        self.timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _log(self, msg: str):
        self.log_area.append(msg)

    @staticmethod
    def _record_btn_style(active: bool) -> str:
        if active:
            return """
                QPushButton {
                    background-color: #c0392b;
                    color: white;
                    border: none;
                    border-radius: 32px;
                    font-size: 15px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #e74c3c; }
            """
        return """
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 32px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2ecc71; }
        """
