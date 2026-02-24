"""
Transcriber — запускает транскрипцию в отдельном subprocess.

Если subprocess падает с нативным крашем (ctranslate2 / AVX2),
перезапускает воркер с флагом --no-faster-whisper → openai-whisper.
"""
import sys
import os
import json
import subprocess
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

WORKER_PATH = Path(__file__).parent / "transcribe_worker.py"

# Нативные коды краша Windows (C++ / DLL crash)
NATIVE_CRASH_CODES = {
    3221225477,   # 0xC0000005  ACCESS_VIOLATION
    3221226505,   # 0xC0000409  STACK_BUFFER_OVERRUN
    3221225725,   # 0xC000009D  IO_PRIVILEGE_CONFLICT
    3221226356,   # 0xC0000374  HEAP_CORRUPTION
    0xC0000142,   # DLL init failed
}


def _cmd(audio: str, model: str, lang: str, extra_flags: list = None) -> list[str]:
    flags = extra_flags or []
    if getattr(sys, "frozen", False):
        return [sys.executable, "--transcribe-worker"] + flags + [audio, model, lang]
    return [sys.executable, str(WORKER_PATH)] + flags + [audio, model, lang]


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
        env["OMP_NUM_THREADS"]      = "2"
        env["OPENBLAS_NUM_THREADS"] = "2"
        # Убираем любой CT2_FORCE_CPU_ISA — он не существует и не помогает
        env.pop("CT2_FORCE_CPU_ISA", None)

        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        # Попытка 1: с faster_whisper
        rc, result = self._run_worker(
            cmd=_cmd(self.audio_path, self.model_size, lang),
            env=env, flags=flags,
        )

        # Нативный краш ctranslate2 — повтор без faster_whisper
        if rc in NATIVE_CRASH_CODES or (rc is not None and rc < 0):
            self.progress.emit(
                f"⚠️ faster-whisper нативный краш (код {rc}) — "
                "переключаюсь на openai-whisper…"
            )
            rc, result = self._run_worker(
                cmd=_cmd(self.audio_path, self.model_size, lang,
                         extra_flags=["--no-faster-whisper"]),
                env=env, flags=flags,
            )

        if result is not None:
            if not result:
                self.progress.emit("⚠️ Текст не распознан — тишина или слишком тихо")
            self.finished.emit(result)
        # error_occurred уже был emit внутри _run_worker

    def _run_worker(self, cmd: list, env: dict, flags: int) -> tuple:
        """
        Запускает subprocess, читает JSON stdout.
        Возвращает (return_code, result_text | None).
        None = была emit error_occurred.
        """
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                creationflags=flags,
                env=env,
            )
            self._proc = proc
        except Exception as e:
            self.error_occurred.emit(f"Не удалось запустить воркер:\n{e}")
            return None, None

        result = ""
        had_error = False

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                t, txt = msg.get("type", ""), msg.get("text", "")
                if   t == "progress": self.progress.emit(txt)
                elif t == "done":     result = txt
                elif t == "error":
                    self.error_occurred.emit(txt)
                    had_error = True
            except json.JSONDecodeError:
                self.progress.emit(f"[worker] {line}")

        proc.wait()
        rc = proc.returncode

        if had_error:
            return rc, None

        if rc != 0 and not result:
            stderr = proc.stderr.read(2000).strip()
            if rc not in NATIVE_CRASH_CODES:
                # Не нативный краш — показываем сразу
                detail = stderr or f"код завершения {rc}"
                self.error_occurred.emit(f"Ошибка транскрипции:\n{detail}")
                return rc, None
            # Нативный краш — вернём rc, вызывающий код решит что делать
            return rc, None

        return rc, result
