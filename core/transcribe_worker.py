"""
Отдельный процесс для транскрипции — полностью изолирован от Qt.
Запускается как subprocess, общается через stdout JSON-строками.
"""
import sys
import json


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"type": "error", "text": "Usage: transcribe_worker.py <audio_path> <model_size> [language]"}))
        sys.exit(1)

    audio_path = sys.argv[1]
    model_size = sys.argv[2]
    language = sys.argv[3] if len(sys.argv) > 3 else None
    if language in ("auto", ""):
        language = None

    def emit(msg_type: str, text: str):
        print(json.dumps({"type": msg_type, "text": text}), flush=True)

    try:
        emit("progress", f"Загружаю модель Whisper ({model_size})…")
        from faster_whisper import WhisperModel
        model = WhisperModel(model_size, device="cpu", compute_type="int8")

        emit("progress", "Распознаю речь…")
        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=False,
            condition_on_previous_text=False,
        )

        emit("progress", f"Язык: {info.language} ({info.language_probability:.0%})")

        parts = []
        for seg in segments:
            t = seg.text.strip()
            if t:
                parts.append(t)
                emit("progress", f"[{seg.start:.1f}s] {t}")

        full_text = " ".join(parts).strip()
        if not full_text:
            emit("progress", "⚠️ Текст не распознан — возможно тишина в записи")

        emit("done", full_text)

    except Exception as e:
        import traceback
        emit("error", f"{e}\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
