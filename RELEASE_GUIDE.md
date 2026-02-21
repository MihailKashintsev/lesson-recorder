# 🚀 Как публиковать обновления

## Первый релиз (делается один раз)

### 1. Замени `YOUR-GITHUB-USERNAME` везде

В `version.py`:
```python
GITHUB_USER = "YOUR-GITHUB-USERNAME"  # ← твой username на GitHub
```

В `installer/setup.iss` (2 места):
```
#define MyAppPublisher "YOUR-GITHUB-USERNAME"
#define MyAppURL "https://github.com/YOUR-GITHUB-USERNAME/lesson-recorder"
```

### 2. Запушь проект на GitHub (если ещё не сделал)

В VS 2022: **Git → Push** или в PowerShell:
```powershell
git push origin main
```

### 3. Разреши GitHub Actions создавать релизы

На GitHub: **Settings → Actions → General → Workflow permissions**  
Выбери: **"Read and write permissions"** → Save

---

## Публикация обновления (каждый раз)

### Способ 1 — Автоматически через скрипт ⚡ (рекомендую)

```powershell
.\release.ps1
```

Скрипт спросит новую версию и changelog, сам всё сделает:
- Обновит `version.py`
- Закоммитит
- Создаст тег
- Запушит на GitHub
- GitHub Actions соберёт установщик (~5-7 мин)

Или сразу с параметрами:
```powershell
.\release.ps1 1.1.0 "Исправлен краш при транскрипции"
```

### Способ 2 — Вручную через VS 2022

1. Измени версию в `version.py`:
   ```python
   __version__ = "1.1.0"
   ```

2. В VS 2022: **Git → Commit All** с сообщением `Release v1.1.0`

3. Создай тег: **Git → Tags → New Tag** → введи `v1.1.0`

4. Запушь тег: **Git → Push** → отметь "Push tags"

---

## Что происходит после пуша тега

```
Ты: git push origin v1.1.0
         ↓ (~5-7 минут)
GitHub Actions (Windows Server):
  ├── pip install requirements.txt
  ├── pyinstaller LessonRecorder.spec
  ├── iscc installer\setup.iss
  └── Создаёт релиз на GitHub с .exe файлом
         ↓
Пользователи: при следующем запуске приложения
  └── Видят диалог "Доступно обновление v1.1.0"
      └── Нажимают "Скачать и установить"
          └── Установщик обновляет приложение автоматически
```

Следить за сборкой: `github.com/ВАШ-USERNAME/lesson-recorder/actions`

---

## Нумерация версий

| Изменение | Пример | Когда |
|---|---|---|
| Патч | 1.0.0 → 1.0.1 | Исправление бага |
| Минорная | 1.0.1 → 1.1.0 | Новая функция |
| Мажорная | 1.1.0 → 2.0.0 | Большие изменения |

---

## Если сборка упала на GitHub Actions

1. Открой `github.com/USERNAME/lesson-recorder/actions`
2. Нажми на упавший workflow
3. Раскрой шаг с ошибкой — там будет текст
4. Скинь ошибку — помогу разобраться
