"""
Отдельный процесс для транскрипции — полностью изолирован от Qt.
Запускается как subprocess, общается через stdout JSON-строками.

Ключевые исправления:
  - Пробует compute_type в порядке: int8 → float32 → default (фикс 0xC0000409 / AVX2)
  - Аудио предварительно читается в numpy float32, 16kHz, моно — исключает краш FFmpeg
  - Fallback на openai-whisper если faster_whisper недоступен
"""
import sys
import json
import os
import wave


def emit(msg_type: str, text: str):
    print(json.dumps({"type": msg_type, "text": text}), flush=True)


def load_audio_as_float32(audio_path: str) -> tuple:
    """
    Читает WAV-файл в numpy float32 16kHz моно.
    Возвращает (array_float32, sample_rate_original).
    Не использует FFmpeg — только стандартную библиотеку wave + numpy.
    """
    import numpy as np

    with wave.open(audio_path, "rb") as wf:
        n_channels  = wf.getnchannels()
        sampwidth   = wf.getsampwidth()
        framerate   = wf.getframerate()
        n_frames    = wf.getnframes()
        raw         = wf.readframes(n_frames)

    # Декодируем байты в int16 (стандарт WAV)
    if sampwidth == 2:
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        audio = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        # 8-bit WAV: unsigned
        audio = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0

    # Стерео → моно
    if n_channels > 1:
        audio = audio.reshape(-1, n_channels).mean(axis=1)

    # Ресемплинг до 16000 Гц если нужно
    if framerate != 16000:
        from math import gcd
        try:
            from scipy.signal import resample_poly
            g = gcd(16000, framerate)
            audio = resample_poly(audio, 16000 // g, framerate // g).astype(np.float32)
        except ImportError:
            # scipy нет — простая линейная интерполяция
            target_len = int(len(audio) * 16000 / framerate)
            indices = np.linspace(0, len(audio) - 1, target_len)
            audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    return audio, framerate


def transcribe_faster_whisper(audio_path: str, model_size: str, language: str | None):
    """Транскрипция через faster_whisper с автовыбором compute_type."""
    from faster_whisper import WhisperModel
    import numpy as np

    emit("progress", f"Загружаю модель Whisper [{model_size}]…")

    # Пробуем compute_type в порядке безопасности.
    # int8 крашит на CPU без AVX2 (ошибка 0xC0000409 на Windows).
    compute_types = ["int8", "float32", "default"]
    model = None
    for ct in compute_types:
        try:
            model = WhisperModel(model_size, device="cpu", compute_type=ct)
            emit("progress", f"Используется compute_type={ct}")
            break
        except Exception as ex:
            emit("progress", f"compute_type={ct} недоступен: {ex}")
            model = None

    if model is None:
        raise RuntimeError("Не удалось загрузить модель Whisper ни с одним compute_type")

    # Предварительно читаем аудио сами — не через FFmpeg subprocess.
    # Это исключает краши FFmpeg при нестандартном WAV.
    emit("progress", "Читаю аудио файл…")
    audio, orig_rate = load_audio_as_float32(audio_path)
    emit("progress", f"Аудио: {len(audio)/16000:.1f}с, исходный SR={orig_rate}Гц")

    emit("progress", "Распознаю речь…")
    segments, info = model.transcribe(
        audio,                          # numpy float32 array, не путь к файлу
        language=language,
        beam_size=1,
        best_of=1,
        temperature=0.0,
        vad_filter=True,                # фильтр тишины — уменьшает галлюцинации
        vad_parameters={"min_silence_duration_ms": 500},
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


def transcribe_openai_whisper(audio_path: str, model_size: str, language: str | None):
    """Fallback: транскрипция через openai-whisper."""
    import whisper
    import numpy as np

    emit("progress", f"Загружаю модель openai-whisper [{model_size}]…")
    model = whisper.load_model(model_size, device="cpu")

    emit("progress", "Читаю аудио файл…")
    audio, _ = load_audio_as_float32(audio_path)

    emit("progress", "Распознаю речь (openai-whisper)…")
    options = {
        "fp16": False,
        "beam_size": 1,
        "best_of": 1,
        "temperature": 0.0,
    }
    if language:
        options["language"] = language

    result = model.transcribe(audio, **options)
    return result.get("text", "").strip()


def main():
    if len(sys.argv) < 3:
        emit("error", "Usage: transcribe_worker.py <audio_path> <model_size> [language]")
        sys.exit(1)

    audio_path = sys.argv[1]
    model_size = sys.argv[2]
    language   = sys.argv[3] if len(sys.argv) > 3 else None
    if language in ("auto", "", None):
        language = None

    if not os.path.exists(audio_path):
        emit("error", f"Аудио файл не найден: {audio_path}")
        sys.exit(1)

    file_size = os.path.getsize(audio_path)
    emit("progress", f"Файл: {audio_path} ({file_size // 1024} КБ)")

    if file_size < 1000:
        emit("error", "Аудио файл слишком мал — возможно запись не содержит данных")
        sys.exit(1)

    full_text = ""
    last_error = ""

    # 1. Пробуем faster_whisper
    try:
        import faster_whisper  # noqa
        full_text = transcribe_faster_whisper(audio_path, model_size, language)
    except Exception as e:
        last_error = str(e)
        emit("progress", f"faster_whisper упал: {e} — пробую openai-whisper…")

        # 2. Fallback: openai-whisper
        try:
            import whisper  # noqa
            full_text = transcribe_openai_whisper(audio_path, model_size, language)
        except ImportError:
            emit("error",
                 f"Ни faster_whisper, ни openai-whisper не доступны.\n"
                 f"Установи: pip install faster-whisper\n"
                 f"Исходная ошибка: {last_error}")
            sys.exit(1)
        except Exception as e2:
            emit("error", f"Оба движка недоступны.\nfaster_whisper: {last_error}\nopenai-whisper: {e2}")
            sys.exit(1)

    if not full_text:
        emit("progress", "⚠️ Текст не распознан — возможно тишина в записи или неподдерживаемый язык")

    emit("done", full_text)


if __name__ == "__main__":
    main()
