"""
Составляет конспект через любой OpenAI-совместимый API.
Поддерживаемые провайдеры: DeepSeek, GigaChat, Groq, Google Gemini, OpenRouter, Custom.
"""
import json
import uuid
import requests
from PyQt6.QtCore import QThread, pyqtSignal

SYSTEM_PROMPT = """Ты — помощник для составления конспектов.
Тебе дают транскрипцию урока/лекции, а также (опционально) текст с фотографий доски, слайдов или заметок.
Составь подробный, структурированный конспект на том же языке, что и транскрипция.
Если есть текст с фотографий — обязательно включи его содержание в конспект.

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
    "deepseek": {
        "name": "DeepSeek",
        "rf_available": True,    # доступен в РФ без VPN
        "base_url": "https://api.deepseek.com/v1",
        "models": [
            "deepseek-chat",
            "deepseek-reasoner",
        ],
        "model_info": {
            "deepseek-chat": "DeepSeek V3 · быстрый, умный · ~$0.07/1M токенов",
            "deepseek-reasoner": "DeepSeek R1 · рассуждения (медленнее) · ~$0.55/1M токенов",
        },
        "default_model": "deepseek-chat",
        "key_hint": "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
        "signup_url": "platform.deepseek.com",
        "free_info": "Платный, очень дёшево · ~$0.07–0.55/1M токенов · ✅ Работает в РФ без VPN",
        "auth_header": "Bearer",
    },
    "gigachat": {
        "name": "GigaChat (Сбер)",
        "rf_available": True,
        "base_url": "https://gigachat.devices.sberbank.ru/api/v1",
        "models": [
            "GigaChat",
            "GigaChat-Plus",
            "GigaChat-Pro",
            "GigaChat-Max",
        ],
        "model_info": {
            "GigaChat": "Базовая модель · бесплатный тариф",
            "GigaChat-Plus": "Улучшенная · платный тариф",
            "GigaChat-Pro": "Профессиональная · платный тариф",
            "GigaChat-Max": "Максимальная · платный тариф",
        },
        "default_model": "GigaChat",
        "key_hint": "Авторизационные данные (base64 client_id:secret)",
        "signup_url": "developers.sber.ru/studio",
        "free_info": "Бесплатно · 150 000 токенов/мес · ✅ Работает в РФ без VPN (от Сбера)",
        "auth_type": "gigachat_oauth",
        "auth_header": "Bearer",
    },
    "groq": {
        "name": "Groq",
        "rf_available": False,
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            "llama-3.3-70b-versatile",
            "llama3-8b-8192",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
            "llama-3.1-70b-versatile",
        ],
        "model_info": {
            "llama-3.3-70b-versatile": "Llama 3.3 70B · лучший бесплатный",
            "llama3-8b-8192": "Llama 3 8B · очень быстрый",
            "mixtral-8x7b-32768": "Mixtral 8x7B · длинный контекст",
            "gemma2-9b-it": "Gemma 2 9B · от Google",
            "llama-3.1-70b-versatile": "Llama 3.1 70B",
        },
        "default_model": "llama-3.3-70b-versatile",
        "key_hint": "gsk_xxxxxxxxxxxxxxxx",
        "signup_url": "console.groq.com",
        "free_info": "Бесплатно · 14 400 запросов/день · без карты · ⚠️ Нужен VPN в РФ",
        "auth_header": "Bearer",
    },
    "gemini": {
        "name": "Google Gemini",
        "rf_available": False,
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-2.0-pro-exp",
        ],
        "model_info": {
            "gemini-2.0-flash": "Gemini 2.0 Flash · быстрый, умный · рекомендуется",
            "gemini-2.0-flash-lite": "Gemini 2.0 Flash Lite · максимально быстрый",
            "gemini-1.5-flash": "Gemini 1.5 Flash · проверенный",
            "gemini-1.5-pro": "Gemini 1.5 Pro · умный, 1M токенов контекст",
            "gemini-2.0-pro-exp": "Gemini 2.0 Pro · экспериментальный",
        },
        "default_model": "gemini-2.0-flash",
        "key_hint": "AIzaxxxxxxxxxxxxxxxx",
        "signup_url": "aistudio.google.com",
        "free_info": "Бесплатно · щедрые лимиты · без карты · ⚠️ Нужен VPN в РФ",
        "auth_header": "Bearer",
    },
    "openrouter": {
        "name": "OpenRouter",
        "rf_available": False,
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemma-2-9b-it:free",
            "mistralai/mistral-7b-instruct:free",
            "deepseek/deepseek-r1:free",
            "deepseek/deepseek-chat:free",
            "anthropic/claude-3.5-haiku",
        ],
        "model_info": {
            "meta-llama/llama-3.3-70b-instruct:free": "Llama 3.3 70B · бесплатно",
            "google/gemma-2-9b-it:free": "Gemma 2 9B · бесплатно",
            "mistralai/mistral-7b-instruct:free": "Mistral 7B · бесплатно",
            "deepseek/deepseek-r1:free": "DeepSeek R1 · рассуждения · бесплатно",
            "deepseek/deepseek-chat:free": "DeepSeek V3 · бесплатно",
            "anthropic/claude-3.5-haiku": "Claude 3.5 Haiku · платно",
        },
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
        "key_hint": "sk-or-xxxxxxxxxxxxxxxx",
        "signup_url": "openrouter.ai",
        "free_info": "Бесплатно · 50 запросов/день (free модели) · ⚠️ Нужен VPN в РФ",
        "auth_header": "Bearer",
    },
    "custom": {
        "name": "Свой URL (OpenAI-совместимый)",
        "rf_available": None,
        "base_url": "",
        "models": [],
        "model_info": {},
        "default_model": "",
        "key_hint": "Ключ или оставь пустым",
        "signup_url": "",
        "free_info": "Любой OpenAI-совместимый API: LM Studio, vLLM, Ollama и др.",
        "auth_header": "Bearer",
    },
}


def get_provider_config(provider_id: str) -> dict:
    return PROVIDERS.get(provider_id, PROVIDERS["deepseek"])


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
        cfg = get_provider_config(provider)
        self.base_url = (base_url.rstrip("/") if provider == "custom"
                         else cfg["base_url"])

    def _get_gigachat_token(self) -> str:
        """Получает OAuth access token для GigaChat."""
        auth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {
            "Authorization": f"Basic {self.api_key.strip()}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = requests.post(
            auth_url,
            headers=headers,
            data={"scope": "GIGACHAT_API_PERS"},
            verify=False,   # GigaChat использует корпоративный сертификат Сбера
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _build_messages(self) -> list:
        """
        ✅ ИСПРАВЛЕНО: GigaChat не поддерживает role='system'.
        Для GigaChat объединяем инструкцию и транскрипцию в один user-запрос.
        Для остальных провайдеров используем стандартный формат system+user.
        """
        user_content = f"Транскрипция урока:\n\n{self.transcript}\n\nСоставь конспект:"

        if self.provider == "gigachat":
            # GigaChat: инструкция + контент в одном user-сообщении
            return [
                {
                    "role": "user",
                    "content": f"{SYSTEM_PROMPT}\n\n{user_content}"
                }
            ]
        else:
            return [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ]

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

            # GigaChat: OAuth авторизация
            if self.provider == "gigachat":
                if not self.api_key.strip():
                    self.error_occurred.emit(
                        "Укажи авторизационные данные GigaChat в настройках.\n"
                        "Получить: developers.sber.ru/studio → Мои проекты → API ключи"
                    )
                    return
                self.progress.emit("Получаю токен GigaChat…")
                token = self._get_gigachat_token()
                headers["Authorization"] = f"Bearer {token}"
            elif self.api_key.strip():
                headers["Authorization"] = f"Bearer {self.api_key.strip()}"

            if self.provider == "openrouter":
                headers["HTTP-Referer"] = "https://github.com/lesson-recorder"
                headers["X-Title"] = "LessonRecorder"

            messages = self._build_messages()

            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 4096,
                "stream": True,
            }

            verify_ssl = (self.provider != "gigachat")
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                stream=True,
                timeout=120,
                verify=verify_ssl,
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
