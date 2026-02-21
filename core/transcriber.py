from PyQt6.QtCore import QThread, pyqtSignal


class Transcriber(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, audio_path: str, model_size: str = "base", language: str = "auto"):
        super().__init__()
        self.audio_path = audio_path
        self.model_size = model_size
        self.language = language if language != "auto" else None

    def run(self):
        try:
            self.progress.emit(f"Загружаю модель Whisper ({self.model_size})…")
            from faster_whisper import WhisperModel
            model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8"
            )
            self.progress.emit("Распознаю речь…")
            segments, info = model.transcribe(
                self.audio_path,
                language=self.language,
                beam_size=5,
                vad_filter=True,
            )
            self.progress.emit(
                f"Язык определён: {info.language} "
                f"(вероятность {info.language_probability:.0%})"
            )
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())
                self.progress.emit(f"[{segment.start:.1f}s] {segment.text.strip()}")

            full_text = "\n".join(text_parts)
            self.finished.emit(full_text)
        except Exception as e:
            self.error_occurred.emit(str(e))
