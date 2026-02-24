"""
Отдельный процесс для транскрипции — полностью изолирован от Qt.
Запускается как subprocess, общается через stdout JSON-строками.

Ключевые исправления:
  - CT2_FORCE_CPU_ISA=SSE2 ДО любого импорта ctranslate2/faster_whisper
    (нативный краш 0xC0000409 не ловится try/except — только env var)
  - Аудио читается в Python через wave+numpy, без FFmpeg subprocess
  - Fallback: если faster_whisper падает — пробуем openai-whisper
"""
import sys
import os
import json
import wave

# ══════════════════════════════════════════════════════════════════════════════
# КРИТИЧНО: установить ДО любого import ctranslate2 / faster_whisper
# Без этого ctranslate2 пытается использовать AVX2 и убивает процесс
# с кодом 0xC0000409 (STATUS_STACK_BUFFER_OVERRUN) до того как Python
# успевает поймать исключение.
# ══════════════════════════════════════════════════════════════════════════════
os.environ.setdefault("CT2_FORCE_CPU_ISA", "SSE2")
os.environ.setdefault("OMP_NUM_THREADS", "2")       # не занимать все ядра


def emit(msg_type: str, text: str):
    print(json.dumps({"type": msg_type, "text": text}), flush=True)


# ──────────────────────────────────────────────────────────────────────────────
# Чтение WAV без FFmpeg
# ──────────────────────────────────────────────────────────────────────────────

def read_wav_as_float32(path: str):
    """
    Читает WAV → numpy float32 массив, моно, 16000 Гц.
    Не вызывает FFmpeg — исключает дополнительные нативные крашы.
    """
    import numpy as np

    with wave.open(path, "rb") as wf:
        n_ch      = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames  = wf.getnframes()
        raw       = wf.readframes(n_frames)

    # Декодируем байты → float32
    if sampwidth == 2:
        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        pcm = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif sampwidth == 1:
        pcm = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"Неподдерживаемый sampwidth={sampwidth}")

    # Стерео → моно
    if n_ch > 1:
        remainder = len(pcm) % n_ch
        if remainder:
            pcm = pcm[:-remainder]
        pcm = pcm.reshape(-1, n_ch).mean(axis=1).astype(np.float32)

    # Ресемплинг → 16000 Гц
    if framerate != 16000:
        emit("progress", f"Ресемплинг {framerate}→16000 Гц…")
        try:
            from scipy.signal import resample_poly
            from math import gcd
            g   = gcd(16000, framerate)
            pcm = resample_poly(pcm, 16000 // g, framerate // g).astype(np.float32)
        except ImportError:
            # scipy нет — линейная интерполяция
            import numpy as np
            target = int(len(pcm) * 16000 / framerate)
            pcm    = np.interp(
                np.linspace(0, len(pcm) - 1, target),
                np.arange(len(pcm)),
                pcm,
            ).astype(np.float32)

    emit("progress", f"Аудио: {len(pcm)/16000:.1f} сек, {n_ch} кан., {framerate} Гц")
    return pcm


# ──────────────────────────────────────────────────────────────────────────────
# faster_whisper
# ──────────────────────────────────────────────────────────────────────────────

def run_faster_whisper(audio, model_size: str, language: str | None) -> str:
    # CT2_FORCE_CPU_ISA уже установлен выше — до этого импорта
    from faster_whisper import WhisperModel

    emit("progress", f"Загружаю faster_whisper [{model_size}] (float32)…")
    # float32 — безопасный тип без AVX2; int8 требует AVX2
    model = WhisperModel(model_size, device="cpu", compute_type="float32")

    emit("progress", "Распознаю речь…")
    segments, info = model.transcribe(
        audio,
        language=language,
        beam_size=5,
        best_of=5,
        temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
        condition_on_previous_text=False,
    )

    emit("progress", f"Язык: {info.language} ({info.language_probability:.0%})")

    parts = []
    for seg in segments:
        t = seg.text.strip()
        if t:
            parts.append(t)
            emit("progress", f"[{seg.start:.1f}s] {t}")

    return " ".join(parts).strip()


# ──────────────────────────────────────────────────────────────────────────────
# openai-whisper (fallback)
# ──────────────────────────────────────────────────────────────────────────────

def run_openai_whisper(audio, model_size: str, language: str | None) -> str:
    import whisper

    emit("progress", f"Загружаю openai-whisper [{model_size}]…")
    model = whisper.load_model(model_size, device="cpu")

    emit("progress", "Распознаю речь (openai-whisper)…")
    opts = {"fp16": False, "beam_size": 5, "best_of": 5}
    if language:
        opts["language"] = language

    result = model.transcribe(audio, **opts)
    return (result.get("text") or "").strip()


# ──────────────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        emit("error", "Usage: transcribe_worker.py <audio_path> <model_size> [language]")
        sys.exit(1)

    audio_path = sys.argv[1]
    model_size = sys.argv[2]
    language   = sys.argv[3] if len(sys.argv) > 3 else None
    if language in ("auto", "", None, "None"):
        language = None

    # Проверяем файл
    if not os.path.exists(audio_path):
        emit("error", f"Файл не найден: {audio_path}")
        sys.exit(1)

    size_kb = os.path.getsize(audio_path) // 1024
    emit("progress", f"Аудио файл: {size_kb} КБ")

    if size_kb < 2:
        emit("error", "Файл слишком мал (< 2 КБ) — запись пустая или не сохранилась")
        sys.exit(1)

    # Читаем аудио
    try:
        audio = read_wav_as_float32(audio_path)
    except Exception as e:
        emit("error", f"Не могу прочитать WAV файл: {e}")
        sys.exit(1)

    # Пробуем faster_whisper
    text = ""
    faster_error = ""
    try:
        import faster_whisper  # noqa — просто проверяем что установлен
        text = run_faster_whisper(audio, model_size, language)
    except ImportError:
        faster_error = "faster_whisper не установлен"
        emit("progress", f"{faster_error} — пробую openai-whisper…")
    except Exception as e:
        faster_error = str(e)
        emit("progress", f"faster_whisper ошибка: {faster_error[:120]} — пробую openai-whisper…")

    # Fallback: openai-whisper
    if not text and faster_error:
        try:
            import whisper  # noqa
            text = run_openai_whisper(audio, model_size, language)
        except ImportError:
            emit("error",
                 "Нет ни faster_whisper, ни openai-whisper.\n"
                 "В настройках → Пакеты → установи Whisper.")
            sys.exit(1)
        except Exception as e2:
            emit("error",
                 f"Оба движка недоступны.\n"
                 f"faster_whisper: {faster_error}\n"
                 f"openai-whisper: {e2}")
            sys.exit(1)

    if not text:
        emit("progress", "⚠️ Текст не распознан — тишина или слишком тихо")

    emit("done", text)


if __name__ == "__main__":
    main()
