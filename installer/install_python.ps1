# ============================================================================
#  LessonRecorder — Python Auto-Installer
#  Запускается из Inno Setup во время установки приложения.
#  Проверяет Python 3.10+, если нет — скачивает и ставит Python 3.13.
# ============================================================================

param(
    [string]$PythonVersion = "3.13.2",
    [string]$PythonURL     = "https://www.python.org/ftp/python/3.13.2/python-3.13.2-amd64.exe",
    [string]$MinVersion    = "3.10"
)

$ErrorActionPreference = "Stop"

# ── Лог-файл ─────────────────────────────────────────────────────────────────
$LogFile = "$env:TEMP\LessonRecorder_install.log"

function Log($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    "$ts  $msg" | Add-Content -Path $LogFile -Encoding UTF8
}

Log "=== LessonRecorder Python Installer ==="
Log "Target Python: $PythonVersion  |  Min: $MinVersion"

# ── Поиск существующего Python ────────────────────────────────────────────────
function Find-Python {
    # 1. PATH
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $ver = & $py.Source --version 2>&1
            Log "Found in PATH: $($py.Source) → $ver"
            return $py.Source
        } catch {}
    }

    # 2. Реестр
    $regPaths = @(
        "HKCU:\Software\Python\PythonCore",
        "HKLM:\Software\Python\PythonCore",
        "HKLM:\Software\WOW6432Node\Python\PythonCore"
    )
    $preferred = @("3.13","3.12","3.11","3.10")

    foreach ($pref in $preferred) {
        foreach ($base in $regPaths) {
            $key = "$base\$pref\InstallPath"
            if (Test-Path $key) {
                $exe = (Get-ItemProperty $key -ErrorAction SilentlyContinue).ExecutablePath
                if ($exe -and (Test-Path $exe)) {
                    Log "Found in registry [$pref]: $exe"
                    return $exe
                }
            }
        }
    }

    # 3. Стандартные папки
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe",
        "C:\Program Files\Python313\python.exe",
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            Log "Found at standard path: $c"
            return $c
        }
    }

    return $null
}

function Version-OK($pyExe, $minVer) {
    try {
        $raw = & $pyExe --version 2>&1   # "Python 3.11.5"
        $v   = $raw -replace "Python\s*", ""
        $installed = [version]$v
        $minimum   = [version]$minVer
        $ok = $installed -ge $minimum
        Log "Version check: $v >= $minVer → $ok"
        return $ok
    } catch {
        Log "Version check failed: $_"
        return $false
    }
}

# ── Проверяем текущую ─────────────────────────────────────────────────────────
$existingPy = Find-Python
if ($existingPy -and (Version-OK $existingPy $MinVersion)) {
    Log "Python OK at: $existingPy — skipping install"
    exit 0
}

Log "Python not found or too old — starting download..."

# ── Скачиваем Python ──────────────────────────────────────────────────────────
$installer = "$env:TEMP\python_installer.exe"

try {
    Log "Downloading from: $PythonURL"
    $wc = New-Object System.Net.WebClient
    $wc.Headers.Add("User-Agent", "LessonRecorder-Installer")
    $wc.DownloadFile($PythonURL, $installer)
    Log "Download complete: $installer ($('{0:N1}' -f ((Get-Item $installer).Length/1MB)) MB)"
} catch {
    Log "Download failed: $_"
    # Пробуем через Invoke-WebRequest как fallback
    try {
        Invoke-WebRequest -Uri $PythonURL -OutFile $installer -UseBasicParsing
        Log "Download via IWR complete"
    } catch {
        Log "IWR also failed: $_"
        exit 1
    }
}

# ── Устанавливаем Python ──────────────────────────────────────────────────────
# InstallAllUsers=0  → в %LOCALAPPDATA%\Programs\Python (не требует UAC)
# PrependPath=1      → добавить в PATH текущего пользователя
# Include_pip=1      → включить pip
# Include_launcher=0 → не нужен py.exe лаунчер
# Include_test=0     → не нужны тестовые файлы
# SimpleInstall=1    → упрощённый диалог (тихий режим)
Log "Running Python installer..."
$args = @(
    "/quiet",
    "InstallAllUsers=0",
    "PrependPath=1",
    "Include_pip=1",
    "Include_launcher=0",
    "Include_test=0",
    "SimpleInstall=1"
)
$proc = Start-Process -FilePath $installer -ArgumentList $args -Wait -PassThru
Log "Python installer exit code: $($proc.ExitCode)"

if ($proc.ExitCode -notin @(0, 3010)) {
    Log "FATAL: Python installer returned $($proc.ExitCode)"
    exit 1
}

# Убираем установщик
Remove-Item $installer -ErrorAction SilentlyContinue

# ── Верифицируем установку ────────────────────────────────────────────────────
# PATH обновился только в реестре, процесс ещё не видит — ищем через реестр
Start-Sleep -Seconds 2
$newPy = Find-Python
if (-not $newPy) {
    # Последний шанс — стандартный путь для версии $PythonVersion
    $majorMinor = ($PythonVersion -split "\.")[0..1] -join ""  # "313"
    $guess = "$env:LOCALAPPDATA\Programs\Python\Python$majorMinor\python.exe"
    if (Test-Path $guess) { $newPy = $guess }
}

if ($newPy) {
    Log "Python installed successfully: $newPy"
    Log "Version: $(& $newPy --version 2>&1)"
} else {
    Log "WARNING: Could not verify Python installation"
}

Log "=== Done ==="
exit 0
