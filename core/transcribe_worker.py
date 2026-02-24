"""
transcribe_worker.py

Запускается как ОТДЕЛЬНЫЙ SUBPROCESS — изолирован от Qt.
Если ctranslate2/faster_whisper нативно крашит процесс,
умирает только этот воркер, а не главное приложение.

Вызов:
  python transcribe_worker.py <audio_path> <model_size> <language>
  LessonRecorder.exe --transcribe-worker <audio_path> <model_size> <language>
"""
import sys
import os
import json
import wave

# КРИТИЧНО: установить ДО любого импорта ctranslate2/faster_whisper
# (работает только если установить до загрузки DLL)
os.environ["CT2_FORCE_CPU_ISA"] = "SSE2"
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")


def emit(t: str, text: str):
    print(json.dumps({"type": t, "text": text}), flush=True)


def read_wav(path: str):
    import numpy as np
    with wave.open(path, "rb") as wf:
        n_ch = wf.getnchannels()
        sw   = wf.getsampwidth()
        rate = wf.getframerate()
        raw  = wf.readframes(wf.getnframes())

    if sw == 2:
        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        pcm = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        pcm = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0

    if n_ch > 1:
        rem = len(pcm) % n_ch
        if rem: pcm = pcm[:-rem]
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
            pcm = np2.interp(np2.linspace(0, len(pcm)-1, tgt),
                             np2.arange(len(pcm)), pcm).astype(np.float32)
    return pcm, rate


def run(audio_path: str, model_size: str, language: str | None):
    emit("progress", f"Читаю аудио ({os.path.getsize(audio_path)//1024} КБ)…")

    try:
        pcm, rate = read_wav(audio_path)
    except Exception as e:
        emit("error", f"Не могу прочитать WAV: {e}")
        return

    emit("progress", f"Аудио: {len(pcm)/16000:.1f} сек (SR={rate})")

    if len(pcm) < 1600:
        emit("error", "Запись слишком короткая (< 0.1 сек)")
        return

    # ── faster_whisper ────────────────────────────────────────────────────
    faster_err = ""
    try:
        from faster_whisper import WhisperModel
        emit("progress", f"Загружаю faster-whisper [{model_size}] (float32)…")
        model = WhisperModel(model_size, device="cpu", compute_type="float32",
                             cpu_threads=2, num_workers=1)
        emit("progress", "Распознаю речь…")
        segments, info = model.transcribe(
            pcm, language=language, beam_size=5, best_of=5,
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
        emit("done", " ".join(parts).strip())
        return
    except ImportError:
        faster_err = "faster-whisper не установлен"
        emit("progress", faster_err)
    except Exception as e:
        faster_err = str(e)
        emit("progress", f"faster-whisper ошибка: {str(e)[:120]}")

    # ── openai-whisper fallback ───────────────────────────────────────────
    try:
        import whisper
        emit("progress", f"Загружаю openai-whisper [{model_size}]…")
        model = whisper.load_model(model_size, device="cpu")
        opts = {"fp16": False, "beam_size": 5}
        if language:
            opts["language"] = language
        result = model.transcribe(pcm, **opts)
        emit("done", (result.get("text") or "").strip())
    except ImportError:
        emit("error",
             "Модуль транскрипции не найден.\n"
             "Открой Настройки → Пакеты и установи faster-whisper.\n"
             f"[faster_whisper: {faster_err}]")
    except Exception as e:
        emit("error", f"faster-whisper: {faster_err}\nopenai-whisper: {e}")


def main():
    # Поддерживаем два варианта вызова:
    #   python transcribe_worker.py <path> <model> <lang>
    #   LessonRecorder.exe --transcribe-worker <path> <model> <lang>
    args = sys.argv[1:]
    if args and args[0] == "--transcribe-worker":
        args = args[1:]

    if len(args) < 2:
        emit("error", "Usage: transcribe_worker.py <audio> <model> [lang]")
        sys.exit(1)

    audio_path = args[0]
    model_size = args[1]
    language   = args[2] if len(args) > 2 else None
    if language in ("auto", "", "None", None):
        language = None

    if not os.path.exists(audio_path):
        emit("error", f"Файл не найден: {audio_path}")
        sys.exit(1)

    run(audio_path, model_size, language)


if __name__ == "__main__":
    main()
