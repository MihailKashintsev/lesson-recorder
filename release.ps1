# release.ps1 — публикация новой версии одной командой
# Использование: .\release.ps1 1.1.0 "Исправлен краш при транскрипции"
#            или: .\release.ps1          (спросит версию и changelog)

param(
    [string]$Version = "",
    [string]$Changelog = ""
)

$ErrorActionPreference = "Stop"

# ── Цвета ─────────────────────────────────────────────────────────────────
function Write-Step($msg)  { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "  ✅ $msg" -ForegroundColor Green }
function Write-Err($msg)   { Write-Host "  ❌ $msg" -ForegroundColor Red; exit 1 }
function Write-Info($msg)  { Write-Host "  $msg" -ForegroundColor Gray }

Write-Host "`n=============================" -ForegroundColor Yellow
Write-Host "  LessonRecorder Release Tool" -ForegroundColor Yellow
Write-Host "=============================" -ForegroundColor Yellow

# ── Читаем текущую версию ─────────────────────────────────────────────────
Write-Step "Текущая версия"
$currentVersion = python -c "from version import __version__; print(__version__)"
Write-Info "Сейчас: v$currentVersion"

# ── Запрашиваем новую версию ──────────────────────────────────────────────
if (-not $Version) {
    $Version = Read-Host "`n  Новая версия (например 1.1.0)"
}
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    Write-Err "Неверный формат версии. Используй формат X.Y.Z (например 1.1.0)"
}
if (-not $Changelog) {
    $Changelog = Read-Host "  Что изменилось (для описания релиза)"
}

$tag = "v$Version"
Write-Info "Новая версия: $tag"

# ── Проверяем git статус ──────────────────────────────────────────────────
Write-Step "Проверка git"
$status = git status --porcelain
if ($status) {
    Write-Host "`n  Несохранённые изменения:" -ForegroundColor Yellow
    Write-Host $status -ForegroundColor Gray
    $commit = Read-Host "`n  Закоммитить все изменения? (y/n)"
    if ($commit -eq "y") {
        git add -A
        git commit -m "Release $tag`: $Changelog"
        Write-Ok "Изменения закоммичены"
    } else {
        Write-Err "Закоммить изменения вручную и запусти снова"
    }
}

# ── Обновляем version.py ──────────────────────────────────────────────────
Write-Step "Обновление version.py"
$versionFile = Get-Content "version.py" -Raw
$versionFile = $versionFile -replace '__version__ = "[^"]*"', "__version__ = `"$Version`""
Set-Content "version.py" $versionFile -NoNewline
Write-Ok "version.py → $Version"

# ── Обновляем installer/version_info.txt ─────────────────────────────────
Write-Step "Обновление version_info.txt"
$vparts = $Version.Split('.')
$winVer = "$($vparts[0]), $($vparts[1]), $($vparts[2]), 0"
$infoFile = Get-Content "installer\version_info.txt" -Raw
$infoFile = $infoFile -replace 'filevers=\([^)]*\)', "filevers=($winVer)"
$infoFile = $infoFile -replace 'prodvers=\([^)]*\)', "prodvers=($winVer)"
$infoFile = $infoFile -replace "StringStruct\(u'FileVersion', u'[^']*'\)", "StringStruct(u'FileVersion', u'$Version.0')"
$infoFile = $infoFile -replace "StringStruct\(u'ProductVersion', u'[^']*'\)", "StringStruct(u'ProductVersion', u'$Version.0')"
Set-Content "installer\version_info.txt" $infoFile -NoNewline
Write-Ok "version_info.txt → $Version"

# ── Коммитим версию ───────────────────────────────────────────────────────
Write-Step "Коммит версии"
git add version.py installer\version_info.txt
git commit -m "Bump version to $Version"
Write-Ok "Версия закоммичена"

# ── Создаём тег ───────────────────────────────────────────────────────────
Write-Step "Создание тега $tag"
# Проверяем что тег не существует
$existingTag = git tag -l $tag
if ($existingTag) {
    Write-Err "Тег $tag уже существует! Используй другую версию."
}
git tag -a $tag -m "$Changelog"
Write-Ok "Тег $tag создан"

# ── Пушим ────────────────────────────────────────────────────────────────
Write-Step "Публикация на GitHub"
git push origin main
git push origin $tag
Write-Ok "Код и тег запушены"

# ── Готово ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✅ Релиз $tag запущен!                           " -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║                                                      " -ForegroundColor Green
Write-Host "║  GitHub Actions сейчас:                              " -ForegroundColor Green
Write-Host "║  1. Собирает .exe через PyInstaller                  " -ForegroundColor Green
Write-Host "║  2. Создаёт установщик через Inno Setup              " -ForegroundColor Green
Write-Host "║  3. Публикует релиз с .exe файлом                    " -ForegroundColor Green
Write-Host "║                                                      " -ForegroundColor Green
Write-Host "║  Следи за прогрессом:                                " -ForegroundColor Green

$remote = git remote get-url origin
$repoUrl = $remote -replace '\.git$', ''
Write-Host "║  $repoUrl/actions   " -ForegroundColor Green
Write-Host "║                                                      " -ForegroundColor Green
Write-Host "║  Готово через ~5-7 минут                             " -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
