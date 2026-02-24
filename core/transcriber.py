"""
Transcriber — запускает транскрипцию в отдельном subprocess.

Режимы запуска воркера:
  • НЕ frozen (python main.py):
      [python.exe, transcribe_worker.py, ...]
      — стандартный Python, видит все установленные пакеты.

  • frozen (.exe):
      [user_python.exe, worker_tmp.py, ...]
      — пользовательский Python из реестра/PATH.
      — worker .py извлекается из _MEIPASS во временный файл.
      НЕ используем сам .exe как интерпретатор —
      его bundled Python не видит пакеты из AppData.

При нативном краше ctranslate2 (AVX2) перезапускает с --no-faster-whisper.
"""
import sys
import os
import json
import subprocess
import tempfile
import shutil
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

WORKER_PATH = Path(__file__).parent / "transcribe_worker.py"

NATIVE_CRASH_CODES = {
    3221225477,  # 0xC0000005  ACCESS_VIOLATION
    3221226505,  # 0xC0000409  STACK_BUFFER_OVERRUN
    3221225725,  # 0xC000009D  IO_PRIVILEGE_CONFLICT
    3221226356,  # 0xC0000374  HEAP_CORRUPTION
    0xC0000142,  # DLL init failed
}

_worker_tmp_path: str | None = None   # кешируем путь к извлечённому воркеру


def _get_worker_path() -> Path:
    """
    В разработке — путь к .py файлу рядом.
    В frozen — извлекаем из _MEIPASS во временную папку (один раз).
    """
    global _worker_tmp_path

    if not getattr(sys, "frozen", False):
        return WORKER_PATH

    if _worker_tmp_path and Path(_worker_tmp_path).exists():
        return Path(_worker_tmp_path)

    # Ищем воркер внутри PyInstaller bundle
    meipass = Path(getattr(sys, "_MEIPASS", ""))
    src = meipass / "core" / "transcribe_worker.py"

    if not src.exists():
        # Пробуем рядом с exe
        src = Path(sys.executable).parent / "core" / "transcribe_worker.py"

    if src.exists():
        # Копируем во временную папку
        tmp_dir = Path(tempfile.gettempdir()) / "lr_worker"
        tmp_dir.mkdir(exist_ok=True)
        dst = tmp_dir / "transcribe_worker.py"
        shutil.copy2(src, dst)
        _worker_tmp_path = str(dst)
        return dst

    return WORKER_PATH   # fallback


def _get_user_python() -> str:
    """
    Возвращает путь к пользовательскому Python.
    В frozen-режиме sys.executable = LessonRecorder.exe — его нельзя
    использовать как интерпретатор для запуска .py файлов.
    """
    if not getattr(sys, "frozen", False):
        return sys.executable

    try:
        from core.python_path import find_python_exe
        return find_python_exe()
    except Exception:
        pass

    # Крайний fallback — ищем python в PATH
    for name in ("python", "python3", "python.exe"):
        found = shutil.which(name)
        if found:
            return found

    raise RuntimeError(
        "Не найден python.exe для запуска транскрипции.\n"
        "Убедись что Python установлен и доступен в PATH,\n"
        "или положи python.exe рядом с LessonRecorder.exe."
    )


def _build_cmd(audio: str, model: str, lang: str,
               extra_flags: list | None = None) -> list[str]:
    flags = extra_flags or []
    python = _get_user_python()
    worker = _get_worker_path()
    return [python, str(worker)] + flags + [audio, model, lang]


class Transcriber(QThread):
    progress       = pyqtSignal(str)
    finished       = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, audio_path: str, model_size: str = "tiny",
                 language: str = "auto"):
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
        env.pop("CT2_FORCE_CPU_ISA", None)

        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        try:
            cmd1 = _build_cmd(self.audio_path, self.model_size, lang)
        except RuntimeError as e:
            self.error_occurred.emit(str(e))
            return

        # Попытка 1: с faster_whisper
        rc, result = self._run_worker(cmd1, env, flags)

        # Нативный краш — повтор без faster_whisper
        if rc in NATIVE_CRASH_CODES or (rc is not None and rc < 0):
            self.progress.emit(
                f"⚠️ faster-whisper нативный краш (код {rc}) — "
                "переключаюсь на openai-whisper…"
            )
            cmd2 = _build_cmd(self.audio_path, self.model_size, lang,
                              extra_flags=["--no-faster-whisper"])
            rc, result = self._run_worker(cmd2, env, flags)

        if result is not None:
            if not result:
                self.progress.emit("⚠️ Текст не распознан — тишина или слишком тихо")
            self.finished.emit(result)

    def _run_worker(self, cmd: list, env: dict,
                    flags: int) -> tuple[int | None, str | None]:
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
            if rc not in NATIVE_CRASH_CODES:
                stderr = proc.stderr.read(2000).strip()
                detail = stderr or f"код завершения {rc}"
                self.error_occurred.emit(f"Ошибка транскрипции:\n{detail}")
                return rc, None
            return rc, None

        return rc, result
