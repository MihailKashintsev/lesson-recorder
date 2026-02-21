# 🎙 LessonRecorder

Приложение для записи уроков/лекций с автоматической транскрипцией и составлением конспектов с помощью локального ИИ.

## Возможности

- **Запись аудио** — микрофон, системный звук или оба одновременно
- **Транскрипция** — локально через [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (без интернета)
- **ИИ-конспект** — автоматическое структурированное конспектирование через [Ollama](https://ollama.com) (без интернета)
- **История уроков** — все записи хранятся локально, можно просмотреть и экспортировать
- **Экспорт** — сохранение конспекта в Markdown / TXT

---

## Установка

### 1. Python и зависимости

```bash
# Python 3.10+
pip install -r requirements.txt
```

> **Примечание для системного звука:** `pyaudiowpatch` работает только на Windows и требует [Microsoft Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/).
>
> Если установка не удаётся — запись системного звука будет недоступна, но микрофон работает всегда.

### 2. Ollama (локальный ИИ для конспектов)

```bash
# Скачайте Ollama с https://ollama.com
# Установите и скачайте модель:
ollama pull llama3
# или более лёгкую:
ollama pull mistral
# или самую быструю:
ollama pull llama3.2:3b
```

Перед запуском приложения запустите Ollama:
```bash
ollama serve
```

### 3. Запуск приложения

```bash
python main.py
```

---

## Структура проекта

```
lesson_recorder/
├── main.py               # Точка входа
├── requirements.txt
├── core/
│   ├── database.py       # SQLite хранилище уроков
│   ├── recorder.py       # Захват аудио (mic / system / both)
│   ├── transcriber.py    # faster-whisper транскрипция
│   └── summarizer.py     # Ollama конспектирование
└── ui/
    ├── main_window.py    # Главное окно с боковой панелью
    ├── recording_widget.py  # Экран записи
    ├── history_widget.py    # История уроков
    └── settings_widget.py   # Настройки
```

---

## Настройки

| Параметр | По умолчанию | Описание |
|---|---|---|
| Источник аудио | Оба | mic / system / both |
| Whisper модель | base | tiny / base / small / medium / large |
| Язык | Авто | Язык речи для Whisper |
| Ollama модель | llama3 | Любая модель из `ollama list` |
| Ollama URL | localhost:11434 | Можно изменить для удалённой Ollama |

### Выбор модели Whisper

| Модель | Скорость | Качество | RAM |
|---|---|---|---|
| tiny | ⚡⚡⚡⚡ | ⭐ | ~1 GB |
| base | ⚡⚡⚡ | ⭐⭐ | ~1 GB |
| small | ⚡⚡ | ⭐⭐⭐ | ~2 GB |
| medium | ⚡ | ⭐⭐⭐⭐ | ~5 GB |
| large-v3 | 🐢 | ⭐⭐⭐⭐⭐ | ~10 GB |

---

## Хранение данных

Все данные хранятся локально в `~/.lesson_recorder/`:
- `lessons.db` — база данных уроков (SQLite)
- `audio/` — аудиофайлы записей
- `settings.json` — настройки

---

## Требования

- Windows 10/11 (для системного звука через WASAPI)
- Python 3.10+
- 4+ GB RAM (для модели Whisper base)
- Ollama установлена и запущена
