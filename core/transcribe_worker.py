"""
transcribe_worker.py — subprocess-воркер транскрипции.

Флаги:
  --transcribe-worker   (добавляет main.py при frozen-запуске, игнорируется)
  --no-faster-whisper   пропустить faster_whisper, сразу openai-whisper
"""
import sys, os, json, wave

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

    if   sw == 2: pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4: pcm = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:         pcm = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0

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


def try_faster_whisper(pcm, model_size: str, language):
    """Возвращает текст или бросает исключение."""
    from faster_whisper import WhisperModel
    emit("progress", f"Загружаю faster-whisper [{model_size}]…")
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
    parts = [seg.text.strip() for seg in segments if seg.text.strip()]
    for p in parts:
        emit("progress", p)
    return " ".join(parts).strip()


def try_openai_whisper(pcm, model_size: str, language):
    """Возвращает текст или бросает исключение."""
    import whisper
    emit("progress", f"Загружаю openai-whisper [{model_size}]…")
    model = whisper.load_model(model_size, device="cpu")
    emit("progress", "Распознаю речь…")
    opts = {"fp16": False, "beam_size": 5}
    if language: opts["language"] = language
    result = model.transcribe(pcm, **opts)
    return (result.get("text") or "").strip()


def main():
    args = [a for a in sys.argv[1:] if a != "--transcribe-worker"]

    skip_faster = "--no-faster-whisper" in args
    args = [a for a in args if a != "--no-faster-whisper"]

    if len(args) < 2:
        emit("error", "Usage: transcribe_worker <audio> <model> [lang]")
        sys.exit(1)

    audio_path = args[0]
    model_size = args[1]
    language   = args[2] if len(args) > 2 else None
    if language in ("auto", "", "None", None): language = None

    if not os.path.exists(audio_path):
        emit("error", f"Файл не найден: {audio_path}")
        sys.exit(1)

    size_kb = os.path.getsize(audio_path) // 1024
    emit("progress", f"Читаю аудио ({size_kb} КБ)…")

    try:
        pcm, rate = read_wav(audio_path)
    except Exception as e:
        emit("error", f"Не могу прочитать WAV: {e}")
        sys.exit(1)

    emit("progress", f"Аудио: {len(pcm)/16000:.1f} сек (SR={rate})")

    if len(pcm) < 1600:
        emit("error", "Запись слишком короткая (< 0.1 сек)")
        sys.exit(1)

    # ── faster_whisper ────────────────────────────────────────────────────
    faster_err = ""
    if not skip_faster:
        try:
            text = try_faster_whisper(pcm, model_size, language)
            emit("done", text)
            return
        except ImportError:
            faster_err = "не установлен"
            emit("progress", f"faster-whisper {faster_err}, пробую openai-whisper…")
        except Exception as e:
            faster_err = str(e)[:120]
            emit("progress", f"faster-whisper ошибка: {faster_err}")
    else:
        emit("progress", "faster-whisper пропущен, использую openai-whisper…")

    # ── openai-whisper ────────────────────────────────────────────────────
    try:
        text = try_openai_whisper(pcm, model_size, language)
        emit("done", text)
    except ImportError:
        emit("error",
             "Нет модуля транскрипции.\n\n"
             "Открой Настройки → Пакеты и установи faster-whisper.\n"
             f"(faster-whisper: {faster_err})")
        sys.exit(1)
    except Exception as e:
        emit("error",
             f"Оба движка недоступны.\n"
             f"faster-whisper: {faster_err}\n"
             f"openai-whisper: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
