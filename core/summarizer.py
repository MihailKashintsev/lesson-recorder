import requests
from PyQt6.QtCore import QThread, pyqtSignal

SYSTEM_PROMPT = """Ты — помощник для составления конспектов. 
Тебе дают транскрипцию урока/лекции. 
Составь подробный, структурированный конспект на том же языке, что и транскрипция.

Формат конспекта:
# Тема урока (определи самостоятельно)

## Ключевые понятия
- Список важных терминов и определений

## Основные темы
### 1. [Название темы]
- Краткое изложение

### 2. [Название темы]
- Краткое изложение

## Важные факты и детали
- Список конкретных фактов, формул, примеров

## Выводы / Итог
- Главные мысли урока

Если транскрипция короткая или нечёткая — напиши лучшее, что можешь извлечь.
"""


class Summarizer(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, transcript: str, model: str = "llama3",
                 ollama_url: str = "http://localhost:11434"):
        super().__init__()
        self.transcript = transcript
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")

    def run(self):
        try:
            self.progress.emit(f"Генерирую конспект с помощью {self.model}…")
            prompt = f"Транскрипция урока:\n\n{self.transcript}\n\nСоставь конспект:"
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": True,
                },
                stream=True,
                timeout=300,
            )
            response.raise_for_status()

            import json
            result = []
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    result.append(token)
                    if token:
                        self.progress.emit("".join(result))

            self.finished.emit("".join(result))
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit(
                "Не удаётся подключиться к Ollama.\n"
                "Убедитесь, что Ollama запущена: `ollama serve`\n"
                f"URL: {self.ollama_url}"
            )
        except Exception as e:
            self.error_occurred.emit(str(e))
