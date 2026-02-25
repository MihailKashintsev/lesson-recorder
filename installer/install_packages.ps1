# install_packages.ps1
# Finds Python and installs required pip packages for LessonRecorder.
# Called from Inno Setup [Run] section after install_python.ps1.

$ErrorActionPreference = "SilentlyContinue"
$LogFile = "$env:TEMP\LessonRecorder_install.log"

function Log($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    "$ts  $msg" | Add-Content -Path $LogFile -Encoding UTF8
}

Log "=== install_packages.ps1 started ==="

function Find-Python {
    # 1. PATH
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($py -and (Test-Path $py)) { Log "Found in PATH: $py"; return $py }

    # 2. Registry
    $regBases = @(
        "HKCU:\Software\Python\PythonCore",
        "HKLM:\Software\Python\PythonCore",
        "HKLM:\Software\WOW6432Node\Python\PythonCore"
    )
    foreach ($ver in @("3.13","3.12","3.11","3.10")) {
        foreach ($base in $regBases) {
            $key = "$base\$ver\InstallPath"
            if (Test-Path $key) {
                $exe = (Get-ItemProperty $key -ErrorAction SilentlyContinue).ExecutablePath
                if ($exe -and (Test-Path $exe)) {
                    Log "Found in registry [$ver]: $exe"
                    return $exe
                }
            }
        }
    }

    # 3. Standard install folders
    $localApp = $env:LOCALAPPDATA
    $candidates = @(
        "$localApp\Programs\Python\Python313\python.exe",
        "$localApp\Programs\Python\Python312\python.exe",
        "$localApp\Programs\Python\Python311\python.exe",
        "$localApp\Programs\Python\Python310\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe",
        "C:\Program Files\Python313\python.exe",
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { Log "Found at: $c"; return $c }
    }

    Log "Python not found"
    return $null
}

$py = Find-Python
if (-not $py) {
    Log "ERROR: No Python found, skipping package install"
    exit 0
}

Log "Using Python: $py"
Log "Installing packages..."

& $py -m pip install --upgrade pip --quiet 2>&1 | ForEach-Object { Log $_ }
& $py -m pip install openai-whisper --quiet 2>&1 | ForEach-Object { Log $_ }
& $py -m pip install PyAudioWPatch sounddevice --quiet 2>&1 | ForEach-Object { Log $_ }
& $py -m pip install pytesseract Pillow --quiet 2>&1 | ForEach-Object { Log $_ }

Log "=== install_packages.ps1 done ==="
exit 0
