"""
Транскрипция аудио — всегда inline в QThread, никаких subprocess.

Порядок попыток:
  1. faster_whisper (ctranslate2, float32, без AVX2)
  2. openai-whisper (PyTorch, совместим с любым CPU)

Если ни один не установлен — понятное сообщение пользователю.
"""
import sys
import os
import wave as _wave

from PyQt6.QtCore import QThread, pyqtSignal

# Устанавливаем ДО любого импорта ctranslate2 / faster_whisper.
# Без этого ctranslate2 выбирает ISA при загрузке DLL и может упасть.
os.environ["CT2_FORCE_CPU_ISA"] = "SSE2"
os.environ.setdefault("OMP_NUM_THREADS", "2")


def _read_wav(path: str):
    """WAV → numpy float32, моно, 16 кГц. Без FFmpeg."""
    import numpy as np

    with _wave.open(path, "rb") as wf:
        n_ch      = wf.getnchannels()
        sw        = wf.getsampwidth()
        rate      = wf.getframerate()
        n_frames  = wf.getnframes()
        raw       = wf.readframes(n_frames)

    if sw == 2:
        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        pcm = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        pcm = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0

    if n_ch > 1:
        rem = len(pcm) % n_ch
        if rem:
            pcm = pcm[:-rem]
        pcm = pcm.reshape(-1, n_ch).mean(axis=1).astype(np.float32)

    if rate != 16000:
        try:
            from scipy.signal import resample_poly
            from math import gcd
            g = gcd(16000, rate)
            pcm = resample_poly(pcm, 16000 // g, rate // g).astype(np.float32)
        except ImportError:
            import numpy as np2
            tgt = int(len(pcm) * 16000 / rate)
            pcm = np2.interp(
                np2.linspace(0, len(pcm) - 1, tgt),
                np2.arange(len(pcm)), pcm
            ).astype(np.float32)

    return pcm, rate


class Transcriber(QThread):
    progress       = pyqtSignal(str)
    finished       = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, audio_path: str, model_size: str = "tiny", language: str = "auto"):
        super().__init__()
        self.audio_path = audio_path
        self.model_size = model_size
        self.language   = language or "auto"

    def stop(self):
        """QThread не имеет надёжного kill — помечаем для будущей поддержки."""
        pass

    def run(self):
        lang = None if self.language in ("auto", "", None) else self.language

        # Шаг 1: читаем аудио
        try:
            self.progress.emit("Читаю аудио файл…")
            pcm, orig_rate = _read_wav(self.audio_path)
        except Exception as e:
            self.error_occurred.emit(f"Не могу прочитать WAV: {e}")
            return

        import os as _os
        size_kb = _os.path.getsize(self.audio_path) // 1024
        self.progress.emit(f"Аудио: {len(pcm)/16000:.1f} сек, исходный SR={orig_rate} Гц ({size_kb} КБ)")

        if len(pcm) < 1600:   # < 0.1 сек
            self.error_occurred.emit("Запись слишком короткая (< 0.1 сек)")
            return

        # Шаг 2: пробуем faster_whisper
        text = None
        faster_error = ""
        try:
            from faster_whisper import WhisperModel  # noqa — импорт здесь, после env vars
            self.progress.emit(f"Загружаю faster-whisper [{self.model_size}]…")
            model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="float32",   # float32 — нет AVX2 зависимости
                cpu_threads=2,
                num_workers=1,
            )
            self.progress.emit("Распознаю речь (faster-whisper)…")
            segments, info = model.transcribe(
                pcm,
                language=lang,
                beam_size=5,
                best_of=5,
                temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
                condition_on_previous_text=False,
            )
            self.progress.emit(f"Язык: {info.language} ({info.language_probability:.0%})")
            parts = []
            for seg in segments:
                t = seg.text.strip()
                if t:
                    parts.append(t)
                    self.progress.emit(f"[{seg.start:.1f}s] {t}")
            text = " ".join(parts).strip()
        except ImportError:
            faster_error = "faster-whisper не установлен"
            self.progress.emit(faster_error)
        except Exception as e:
            faster_error = str(e)
            self.progress.emit(f"faster-whisper ошибка: {faster_error[:100]}")

        # Шаг 3: если faster_whisper не сработал — пробуем openai-whisper
        if text is None:
            try:
                import whisper
                self.progress.emit(f"Загружаю openai-whisper [{self.model_size}]…")
                model = whisper.load_model(self.model_size, device="cpu")
                self.progress.emit("Распознаю речь (openai-whisper)…")
                opts = {"fp16": False, "beam_size": 5}
                if lang:
                    opts["language"] = lang
                result = model.transcribe(pcm, **opts)
                text = (result.get("text") or "").strip()
            except ImportError:
                self.error_occurred.emit(
                    "Модуль транскрипции не найден.\n\n"
                    "Открой Настройки → Пакеты и установи:\n"
                    "  • faster-whisper  (рекомендуется)\n"
                    "или\n"
                    "  • openai-whisper\n\n"
                    f"Детали: {faster_error}"
                )
                return
            except Exception as e:
                self.error_occurred.emit(
                    f"Ошибка транскрипции.\n\n"
                    f"faster-whisper: {faster_error}\n"
                    f"openai-whisper: {e}\n\n"
                    "Попробуй переустановить пакеты в Настройки → Пакеты."
                )
                return

        if not text:
            self.progress.emit("⚠️ Текст не распознан — тишина или слишком тихо")

        self.finished.emit(text or "")
