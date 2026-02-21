"""
Составляет конспект через любой OpenAI-совместимый API.
Поддерживаемые провайдеры: Groq, Google Gemini, OpenRouter, Custom.
"""
import json
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

## Важные факты и детали
- Список конкретных фактов, формул, примеров

## Выводы / Итог
- Главные мысли урока
"""

# Конфигурация провайдеров
PROVIDERS = {
    "groq": {
        "name": "Groq (llama, mixtral)",
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            "llama-3.3-70b-versatile",
            "llama3-8b-8192",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
        ],
        "default_model": "llama-3.3-70b-versatile",
        "key_hint": "gsk_xxxxxxxxxxxxxxxx",
        "signup_url": "console.groq.com",
        "free_info": "Бесплатно · 14 400 запросов/день · без карты",
        "auth_header": "Bearer",
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
        "default_model": "gemini-2.0-flash",
        "key_hint": "AIzaxxxxxxxxxxxxxxxx",
        "signup_url": "aistudio.google.com",
        "free_info": "Бесплатно · 250 запросов/день · без карты",
        "auth_header": "Bearer",
    },
    "openrouter": {
        "name": "OpenRouter (много моделей)",
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemma-2-9b-it:free",
            "mistralai/mistral-7b-instruct:free",
            "deepseek/deepseek-r1:free",
        ],
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
        "key_hint": "sk-or-xxxxxxxxxxxxxxxx",
        "signup_url": "openrouter.ai",
        "free_info": "Бесплатно · 50 запросов/день (free модели)",
        "auth_header": "Bearer",
    },
    "custom": {
        "name": "Свой URL (OpenAI-совместимый)",
        "base_url": "",
        "models": [],
        "default_model": "",
        "key_hint": "Ключ или оставь пустым",
        "signup_url": "",
        "free_info": "Любой OpenAI-совместимый API (LM Studio, vLLM, и др.)",
        "auth_header": "Bearer",
    },
}


def get_provider_config(provider_id: str) -> dict:
    return PROVIDERS.get(provider_id, PROVIDERS["groq"])


class Summarizer(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, transcript: str, provider: str, api_key: str,
                 model: str, base_url: str = ""):
        super().__init__()
        self.transcript = transcript
        self.provider = provider
        self.api_key = api_key
        self.model = model
        # Для custom провайдера base_url берётся из настроек
        cfg = get_provider_config(provider)
        self.base_url = (base_url.rstrip("/") if provider == "custom"
                         else cfg["base_url"])

    def run(self):
        if not self.base_url:
            self.error_occurred.emit("Укажи URL API в настройках.")
            return
        if not self.model:
            self.error_occurred.emit("Укажи модель в настройках.")
            return

        try:
            self.progress.emit(f"Генерирую конспект ({self.provider} / {self.model})…")

            headers = {"Content-Type": "application/json"}
            if self.api_key.strip():
                headers["Authorization"] = f"Bearer {self.api_key.strip()}"
            # OpenRouter требует доп. заголовки
            if self.provider == "openrouter":
                headers["HTTP-Referer"] = "https://github.com/lesson-recorder"
                headers["X-Title"] = "LessonRecorder"

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content":
                        f"Транскрипция урока:\n\n{self.transcript}\n\nСоставь конспект:"},
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
                "stream": True,
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                stream=True,
                timeout=120,
            )

            if response.status_code == 401:
                self.error_occurred.emit(
                    "Неверный API ключ.\n"
                    f"Проверь ключ для провайдера «{self.provider}» в Настройках."
                )
                return
            elif response.status_code == 429:
                self.error_occurred.emit(
                    "Превышен лимит запросов.\n"
                    "Попробуй позже или смени провайдера в Настройках."
                )
                return
            elif response.status_code == 404:
                self.error_occurred.emit(
                    f"Модель «{self.model}» не найдена.\n"
                    "Проверь название модели в Настройках."
                )
                return
            elif response.status_code != 200:
                self.error_occurred.emit(
                    f"Ошибка API {response.status_code}:\n{response.text[:300]}"
                )
                return

            result = []
            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            result.append(delta)
                            self.progress.emit("".join(result))
                    except (json.JSONDecodeError, KeyError):
                        continue

            final = "".join(result)
            if final:
                self.finished.emit(final)
            else:
                self.error_occurred.emit("Получен пустой ответ от API. Попробуй ещё раз.")

        except requests.exceptions.ConnectionError:
            self.error_occurred.emit(
                "Нет подключения к интернету или неверный URL.\n"
                "Проверь соединение и настройки провайдера."
            )
        except requests.exceptions.Timeout:
            self.error_occurred.emit("Сервер не ответил вовремя (таймаут 120с).")
        except Exception as e:
            self.error_occurred.emit(f"Неожиданная ошибка: {e}")
