# Запуск в режиме разработки (VS Code)

## Быстрый старт

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Запустить
python main.py
```

## VS Code (F5)

1. Открой папку проекта в VS Code (`File → Open Folder`)
2. Выбери интерпретатор: `Ctrl+Shift+P` → `Python: Select Interpreter` → выбери Python 3.10+
3. Нажми **F5** → выбери `▶ Запустить LessonRecorder`

### Если F5 не работает — частые причины:

**Ошибка: `ModuleNotFoundError: No module named 'PyQt6'`**
```bash
pip install PyQt6
```

**Ошибка: `ModuleNotFoundError: No module named 'core'`**
- Убедись что VS Code открыт в корневой папке проекта (там где `main.py`)
- В launch.json уже прописан `"cwd": "${workspaceFolder}"` и `"PYTHONPATH": "${workspaceFolder}"`

**Ошибка: `No module named 'sounddevice'`**
```bash
pip install -r requirements.txt
```

**PyQt6 конфликт версий**
```bash
pip install --upgrade PyQt6 PyQt6-Qt6 PyQt6-sip
```

## Запуск из терминала (альтернатива F5)

```bash
cd путь/к/проекту
python main.py
```

## Тестирование транскрипции отдельно

```bash
python core/transcribe_worker.py путь/к/audio.wav tiny auto
```

## Сборка .exe (когда нужно)

```bash
pip install pyinstaller
pyinstaller LessonRecorder.spec --clean --noconfirm
```

Готовый .exe будет в `dist/LessonRecorder/LessonRecorder.exe`
