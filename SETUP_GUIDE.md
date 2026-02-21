# Пошаговая инструкция: VS 2022 + GitHub + автосборка

## Шаг 1 — Создаём репозиторий на GitHub

1. Открой **github.com** → **New repository**
2. Название: `lesson-recorder`
3. Описание: `AI-powered lesson recorder with auto transcription and notes`
4. Выбери **Public** (для бесплатных GitHub Actions минут)
5. **НЕ** добавляй README, .gitignore, license — они уже есть в проекте
6. Нажми **Create repository**

---

## Шаг 2 — Подключаем проект в VS 2022

1. Открой **Visual Studio 2022**
2. **File → Open → Folder…** — выбери папку `lesson_recorder`
3. VS сам распознает Python-проект
4. В нижней строке состояния нажми на **Git** → **Create Git Repository**
5. Выбери **Push to existing remote**
6. В поле Remote URL вставь: `https://github.com/YOUR-GITHUB-USERNAME/lesson-recorder.git`
7. Нажми **Push**

---

## Шаг 3 — Правим `version.py`

Открой `version.py` и замени:
```python
GITHUB_USER = "YOUR-GITHUB-USERNAME"   # ← сюда своё имя на GitHub
```

Также замени в `installer/setup.iss`:
```
#define MyAppPublisher "YOUR-GITHUB-USERNAME"
#define MyAppURL "https://github.com/YOUR-GITHUB-USERNAME/lesson-recorder"
```

---

## Шаг 4 — Настраиваем Python в VS 2022

1. **Tools → Python → Python Environments**
2. Создай виртуальное окружение (venv) или выбери существующее
3. В **Python Environments** нажми **Install from requirements.txt**
4. Подожди пока установятся все пакеты

---

## Шаг 5 — Первый запуск

```bash
python main.py
```

---

## Шаг 6 — Как выпускать новые версии (релиз)

### Автоматически через GitHub Actions (рекомендую)

1. Обнови версию в `version.py`:
   ```python
   __version__ = "1.1.0"
   ```

2. Также обнови версию в `installer/version_info.txt`

3. В VS 2022:
   - **Git → Commit All** (напиши сообщение, например: `Release v1.1.0`)
   - **Git → Push**

4. Создай тег и запушь его:
   ```bash
   git tag v1.1.0
   git push origin v1.1.0
   ```
   Или в VS 2022: **Git → Tags → New Tag**

5. GitHub Actions автоматически:
   - Соберёт `.exe` через PyInstaller
   - Создаст installer через Inno Setup
   - Опубликует релиз на `github.com/YOUR-USERNAME/lesson-recorder/releases`

6. Пользователи при следующем запуске увидят диалог обновления!

### Локально через build.bat

```bash
# Запусти в папке проекта:
build.bat
```
Готовый installer появится в `dist\installer\`

---

## Как работает автообновление

```
Запуск приложения
      ↓ (через 2 сек, в фоне)
GET https://api.github.com/repos/USER/lesson-recorder/releases/latest
      ↓
Сравниваем версии (packaging.version.Version)
      ↓ если новая версия найдена
Показываем диалог "Доступно обновление"
      ↓ пользователь нажимает "Скачать и установить"
Скачиваем *_setup.exe из assets релиза
      ↓
Запускаем установщик с флагом /SILENT /CLOSEAPPLICATIONS
      ↓
Приложение закрывается, установщик обновляет файлы
      ↓
Установщик перезапускает приложение
```

---

## Структура проекта

```
lesson-recorder/
├── .github/
│   └── workflows/
│       └── release.yml      ← GitHub Actions: авто-сборка при теге
├── installer/
│   ├── setup.iss            ← Inno Setup скрипт
│   └── version_info.txt     ← метаданные EXE для Windows
├── core/
│   ├── updater.py           ← проверка обновлений + диалог
│   ├── recorder.py
│   ├── transcriber.py
│   ├── summarizer.py
│   └── database.py
├── ui/
│   ├── main_window.py
│   ├── recording_widget.py
│   ├── history_widget.py
│   └── settings_widget.py
├── main.py
├── version.py               ← единый источник версии
├── LessonRecorder.spec      ← PyInstaller конфиг
├── requirements.txt
├── build.bat                ← локальная сборка
├── .gitignore
└── README.md
```
