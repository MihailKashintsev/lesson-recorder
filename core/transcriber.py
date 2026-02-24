"""
Transcriber — запускает транскрипцию в отдельном subprocess.

Подход:
  • НЕ frozen (python main.py): subprocess = sys.executable + worker.py
  • frozen (.exe): subprocess = сам .exe с флагом --transcribe-worker

Почему subprocess, а не QThread inline:
  ctranslate2/faster_whisper при загрузке DLL может нативно
  крашить процесс (0xC0000409). В subprocess краш убивает только
  воркер, а не главное приложение.
"""
import sys
import os
import json
import subprocess
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

WORKER_PATH = Path(__file__).parent / "transcribe_worker.py"


def _build_cmd(audio_path: str, model_size: str, language: str) -> list[str]:
    """
    Формирует команду для запуска воркера.
    В frozen-режиме: [app.exe, --transcribe-worker, ...]
    В dev-режиме:    [python.exe, worker.py, ...]
    """
    if getattr(sys, "frozen", False):
        # PyInstaller .exe — используем сам exe с флагом-маркером
        return [sys.executable, "--transcribe-worker",
                audio_path, model_size, language]
    else:
        # Разработка — вызываем воркер через python
        return [sys.executable, str(WORKER_PATH),
                audio_path, model_size, language]


class Transcriber(QThread):
    progress       = pyqtSignal(str)
    finished       = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, audio_path: str, model_size: str = "tiny", language: str = "auto"):
        super().__init__()
        self.audio_path = audio_path
        self.model_size = model_size
        self.language   = language or "auto"
        self._proc      = None

    def stop(self):
        if self._proc:
            try: self._proc.kill()
            except Exception: pass

    def run(self):
        lang = self.language if self.language not in ("auto", "", None) else "auto"

        env = os.environ.copy()
        env["CT2_FORCE_CPU_ISA"]    = "SSE2"
        env["OMP_NUM_THREADS"]      = "2"
        env["OPENBLAS_NUM_THREADS"] = "2"

        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW

        cmd = _build_cmd(self.audio_path, self.model_size, lang)

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
                env=env,
            )
        except Exception as e:
            self.error_occurred.emit(f"Не удалось запустить воркер: {e}")
            return

        result = ""
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                t   = msg.get("type", "")
                txt = msg.get("text", "")
                if t == "progress":
                    self.progress.emit(txt)
                elif t == "done":
                    result = txt
                elif t == "error":
                    self.error_occurred.emit(txt)
                    self._proc.wait()
                    return
            except json.JSONDecodeError:
                self.progress.emit(f"[worker] {line}")

        self._proc.wait()
        rc = self._proc.returncode

        if rc != 0 and not result:
            stderr = self._proc.stderr.read(2000).strip()
            if rc == 3221226505:   # 0xC0000409 — AVX2 crash
                detail = (
                    "ctranslate2 нативный краш (AVX2 не поддерживается CPU).\n"
                    "Переустанови faster-whisper:\n"
                    "  pip install --upgrade faster-whisper ctranslate2"
                )
            else:
                detail = stderr or f"код завершения {rc}"
            self.error_occurred.emit(f"Ошибка транскрипции:\n{detail}")
            return

        if not result:
            self.progress.emit("⚠️ Текст не распознан — тишина или слишком тихо")

        self.finished.emit(result)
