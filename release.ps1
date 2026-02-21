param(
    [string]$Version = "",
    [string]$Changelog = ""
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  OK $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "  ERROR $msg" -ForegroundColor Red; exit 1 }

Write-Host "`n============================" -ForegroundColor Yellow
Write-Host "  LessonRecorder Release Tool" -ForegroundColor Yellow
Write-Host "============================" -ForegroundColor Yellow

Write-Step "Текущая версия"
$currentVersion = python -c "from version import __version__; print(__version__)"
Write-Host "  Сейчас: v$currentVersion" -ForegroundColor Gray

if (-not $Version) {
    $Version = Read-Host "`n  Новая версия (например 1.1.0)"
}

if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    Write-Fail "Неверный формат. Используй X.Y.Z например 1.1.0"
}

if (-not $Changelog) {
    $Changelog = Read-Host "  Что изменилось"
}

$tag = "v$Version"
Write-Host "  Новая версия: $tag" -ForegroundColor Gray

Write-Step "Проверка git"
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "`n  Есть незакоммиченные изменения:" -ForegroundColor Yellow
    Write-Host $gitStatus -ForegroundColor Gray
    $answer = Read-Host "`n  Закоммитить все? (y/n)"
    if ($answer -eq "y") {
        git add -A
        git commit -m "Release ${tag}: $Changelog"
        Write-Ok "Изменения закоммичены"
    } else {
        Write-Fail "Закоммить вручную и запусти снова"
    }
}

Write-Step "Обновление version.py"
$content = Get-Content "version.py" -Raw
$content = $content -replace '__version__ = "[^"]*"', "__version__ = `"$Version`""
[System.IO.File]::WriteAllText("$PWD\version.py", $content)
Write-Ok "version.py -> $Version"

Write-Step "Обновление version_info.txt"
$parts = $Version.Split('.')
$winVer = "$($parts[0]), $($parts[1]), $($parts[2]), 0"
$info = Get-Content "installer\version_info.txt" -Raw
$info = $info -replace 'filevers=\([^)]*\)', "filevers=($winVer)"
$info = $info -replace 'prodvers=\([^)]*\)', "prodvers=($winVer)"
$info = $info -replace "StringStruct\(u'FileVersion', u'[^']*'\)", "StringStruct(u'FileVersion', u'$Version.0')"
$info = $info -replace "StringStruct\(u'ProductVersion', u'[^']*'\)", "StringStruct(u'ProductVersion', u'$Version.0')"
[System.IO.File]::WriteAllText("$PWD\installer\version_info.txt", $info)
Write-Ok "version_info.txt -> $Version"

Write-Step "Коммит версии"
git add version.py "installer\version_info.txt"
git commit -m "Bump version to $Version"
Write-Ok "Закоммичено"

Write-Step "Создание тега $tag"
$existing = git tag -l $tag
if ($existing) {
    Write-Fail "Тег $tag уже существует"
}
git tag -a $tag -m $Changelog
Write-Ok "Тег $tag создан"

Write-Step "Пуш на GitHub"
git push origin main
git push origin $tag
Write-Ok "Запушено"

$remote = git remote get-url origin
$repoUrl = $remote -replace '\.git$', ''

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  ГОТОВО! Релиз $tag запущен" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  Следи за сборкой:" -ForegroundColor Green
Write-Host "  $repoUrl/actions" -ForegroundColor Cyan
Write-Host "  Установщик будет готов через ~7 минут" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""