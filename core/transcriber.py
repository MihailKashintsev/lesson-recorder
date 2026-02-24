"""
Транскрибирует аудио через отдельный subprocess.
Полностью изолировано от Qt — совместимо с Python 3.13.
"""
import sys
import json
import subprocess
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

# Путь к воркеру — рядом с этим файлом
WORKER_PATH = Path(__file__).parent / "transcribe_worker.py"


class Transcriber(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, audio_path: str, model_size: str = "tiny", language: str = "auto"):
        super().__init__()
        self.audio_path = audio_path
        self.model_size = model_size
        self.language = language or "auto"
        self._process = None

    def stop(self):
        if self._process:
            try:
                self._process.kill()
            except Exception:
                pass

    def run(self):
        try:
            cmd = [
                sys.executable,
                str(WORKER_PATH),
                self.audio_path,
                self.model_size,
                self.language,
            ]

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            result_text = ""

            for line in self._process.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    msg_type = msg.get("type", "")
                    text = msg.get("text", "")

                    if msg_type == "progress":
                        self.progress.emit(text)
                    elif msg_type == "done":
                        result_text = text
                    elif msg_type == "error":
                        self.error_occurred.emit(text)
                        return
                except json.JSONDecodeError:
                    self.progress.emit(f"[worker] {line}")

            self._process.wait()

            stderr_output = self._process.stderr.read().strip()
            if self._process.returncode != 0 and not result_text:
                # Показываем stderr если есть — там реальная причина
                detail = stderr_output if stderr_output else f"код {self._process.returncode}"
                # Код 3221226505 = 0xC0000409 = STATUS_STACK_BUFFER_OVERRUN (AVX2/ctranslate2)
                if self._process.returncode == 3221226505:
                    detail = (
                        "Нативный краш ctranslate2 (код 0xC0000409).\n"
                        "Вероятно CPU не поддерживает AVX2 инструкции.\n"
                        "Попробуй: pip install --upgrade faster-whisper ctranslate2"
                    )
                self.error_occurred.emit(f"Ошибка транскрипции:\n{detail}")
                return

            self.finished.emit(result_text)

        except FileNotFoundError:
            self.error_occurred.emit(
                f"Не найден файл воркера:\n{WORKER_PATH}\n"
                "Убедись что файл transcribe_worker.py находится в папке core/"
            )
        except Exception as e:
            import traceback
            self.error_occurred.emit(
                f"Неожиданная ошибка транскрибера:\n{e}\n{traceback.format_exc()}"
            )
